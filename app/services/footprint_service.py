"""足迹服务

足迹与行程规划完全解耦：用户手动录入「什么时候去了哪座城市」，
不引用 trips 表，行程记录被删也不影响足迹。

有三件事必须在这里做掉，否则统计一定歪：
1. 城市名归一化 —— 「北京」「北京市」「北京 市」必须是同一个城市
2. 省份归属 —— 用 adcode 前两位判省，比匹配「江苏省/江苏」这类字符串可靠
3. 去重聚合 —— 同一城市多次到访在统计里只算一个城市，但次数要累计

城市坐标的来路：内置热门城市表 → 本地 city_registry 缓存 → 高德行政区查询。
查不到城市也允许入库，坐标留空，只是地图上少一个点，不影响列表和统计。
"""

import json
import math
import sqlite3
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

import httpx

from app.config import get_settings
from app.services.db import db_conn
from app.services.oss_service import family_hosts, get_runtime, strip_transient, thumb_urls

# 中国 34 个省级行政区，用于「点亮 5/34」这类进度表达
PROVINCE_TOTAL = 34

# adcode 前两位 → 省级短名。用它判省比字符串匹配稳，
# 因为高德返回的是「江苏省」，用户可能写「江苏」，而 adcode 永远统一。
PROVINCE_BY_PREFIX = {
    "11": "北京", "12": "天津", "13": "河北", "14": "山西", "15": "内蒙古",
    "21": "辽宁", "22": "吉林", "23": "黑龙江",
    "31": "上海", "32": "江苏", "33": "浙江", "34": "安徽", "35": "福建",
    "36": "江西", "37": "山东",
    "41": "河南", "42": "湖北", "43": "湖南", "44": "广东", "45": "广西",
    "46": "海南",
    "50": "重庆", "51": "四川", "52": "贵州", "53": "云南", "54": "西藏",
    "61": "陕西", "62": "甘肃", "63": "青海", "64": "宁夏", "65": "新疆",
    "71": "台湾", "81": "香港", "82": "澳门",
}

# 内置热门城市：(adcode, 省份, 经度, 纬度)，坐标为 GCJ-02。
# 有这张表，断网或高德限流时常见旅游城市也能正常点亮；
# 表外的城市走高德查询，结果写进 city_registry 缓存。
BUILTIN_CITIES: dict[str, tuple[str, str, float, float]] = {
    "北京": ("110000", "北京", 116.4074, 39.9042),
    "上海": ("310000", "上海", 121.4737, 31.2304),
    "天津": ("120000", "天津", 117.1902, 39.1256),
    "重庆": ("500000", "重庆", 106.5516, 29.5630),
    "广州": ("440100", "广东", 113.2644, 23.1291),
    "深圳": ("440300", "广东", 114.0579, 22.5431),
    "珠海": ("440400", "广东", 113.5767, 22.2707),
    "佛山": ("440600", "广东", 113.1220, 23.0288),
    "东莞": ("441900", "广东", 113.7518, 23.0207),
    "汕头": ("440500", "广东", 116.6819, 23.3541),
    "惠州": ("441300", "广东", 114.4161, 23.1115),
    "杭州": ("330100", "浙江", 120.1551, 30.2741),
    "宁波": ("330200", "浙江", 121.5503, 29.8746),
    "温州": ("330300", "浙江", 120.6994, 27.9944),
    "嘉兴": ("330400", "浙江", 120.7555, 30.7461),
    "湖州": ("330500", "浙江", 120.1020, 30.8703),
    "绍兴": ("330600", "浙江", 120.5820, 30.0030),
    "金华": ("330700", "浙江", 119.6495, 29.0893),
    "舟山": ("330900", "浙江", 122.2072, 29.9853),
    "南京": ("320100", "江苏", 118.7969, 32.0603),
    "无锡": ("320200", "江苏", 120.3119, 31.4912),
    "徐州": ("320300", "江苏", 117.1848, 34.2618),
    "常州": ("320400", "江苏", 119.9741, 31.8112),
    "苏州": ("320500", "江苏", 120.5853, 31.2989),
    "南通": ("320600", "江苏", 120.8647, 32.0165),
    "扬州": ("321000", "江苏", 119.4129, 32.3942),
    "合肥": ("340100", "安徽", 117.2272, 31.8206),
    "黄山": ("341000", "安徽", 118.3376, 29.7147),
    "福州": ("350100", "福建", 119.2965, 26.0745),
    "厦门": ("350200", "福建", 118.0894, 24.4798),
    "泉州": ("350500", "福建", 118.5894, 24.8741),
    "南昌": ("360100", "江西", 115.8582, 28.6829),
    "景德镇": ("360200", "江西", 117.1848, 29.2687),
    "济南": ("370100", "山东", 117.1201, 36.6512),
    "青岛": ("370200", "山东", 120.3826, 36.0671),
    "烟台": ("370600", "山东", 121.3914, 37.5393),
    "威海": ("371000", "山东", 122.1201, 37.5131),
    "泰安": ("370900", "山东", 117.0876, 36.2003),
    "郑州": ("410100", "河南", 113.6254, 34.7466),
    "洛阳": ("410300", "河南", 112.4540, 34.6197),
    "开封": ("410200", "河南", 114.3073, 34.7970),
    "武汉": ("420100", "湖北", 114.3055, 30.5928),
    "宜昌": ("420500", "湖北", 111.2865, 30.6919),
    "长沙": ("430100", "湖南", 112.9388, 28.2282),
    "张家界": ("430800", "湖南", 110.4792, 29.1170),
    "南宁": ("450100", "广西", 108.3665, 22.8170),
    "桂林": ("450300", "广西", 110.2900, 25.2736),
    "北海": ("450500", "广西", 109.1193, 21.4733),
    "海口": ("460100", "海南", 110.1999, 20.0440),
    "三亚": ("460200", "海南", 109.5119, 18.2528),
    "成都": ("510100", "四川", 104.0665, 30.5723),
    "乐山": ("511100", "四川", 103.7657, 29.5521),
    "绵阳": ("510700", "四川", 104.6796, 31.4675),
    "贵阳": ("520100", "贵州", 106.6302, 26.6477),
    "遵义": ("520300", "贵州", 106.9273, 27.7257),
    "昆明": ("530100", "云南", 102.8329, 24.8801),
    "大理": ("532900", "云南", 100.2676, 25.6065),
    "丽江": ("530700", "云南", 100.2330, 26.8721),
    "西双版纳": ("532800", "云南", 100.7979, 22.0090),
    "拉萨": ("540100", "西藏", 91.1409, 29.6456),
    "西安": ("610100", "陕西", 108.9398, 34.3416),
    "宝鸡": ("610300", "陕西", 107.2372, 34.3613),
    "延安": ("610600", "陕西", 109.4897, 36.5853),
    "兰州": ("620100", "甘肃", 103.8343, 36.0611),
    "敦煌": ("620900", "甘肃", 94.6618, 40.1421),
    "西宁": ("630100", "青海", 101.7782, 36.6171),
    "银川": ("640100", "宁夏", 106.2309, 38.4872),
    "乌鲁木齐": ("650100", "新疆", 87.6168, 43.8256),
    "喀什": ("653100", "新疆", 75.9897, 39.4677),
    "呼和浩特": ("150100", "内蒙古", 111.6708, 40.8183),
    "呼伦贝尔": ("150700", "内蒙古", 119.7657, 49.2153),
    "沈阳": ("210100", "辽宁", 123.4315, 41.8057),
    "大连": ("210200", "辽宁", 121.6147, 38.9140),
    "丹东": ("210600", "辽宁", 124.3830, 40.1243),
    "长春": ("220100", "吉林", 125.3245, 43.8868),
    "哈尔滨": ("230100", "黑龙江", 126.6424, 45.7560),
    "太原": ("140100", "山西", 112.5489, 37.8570),
    "大同": ("140200", "山西", 113.2953, 40.0903),
    "石家庄": ("130100", "河北", 114.5149, 38.0428),
    "秦皇岛": ("130300", "河北", 119.6005, 39.9354),
    "承德": ("130800", "河北", 117.9634, 40.9515),
    "保定": ("130600", "河北", 115.4646, 38.8740),
    "台北": ("710100", "台湾", 121.5090, 25.0443),
    "香港": ("810000", "香港", 114.1733, 22.3200),
    "澳门": ("820000", "澳门", 113.5494, 22.1987),
}

# 查不到的城市缓存 1 天后再试，避免一次失败就永久判死
_UNRESOLVED_TTL = timedelta(days=1)


class FootprintError(Exception):
    """足迹业务错误（重复录入、城市无法识别等）"""


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _today() -> date:
    return datetime.now().date()


# ============ 城市归一化 ============

def normalize_city(raw: str) -> str:
    """把用户输入的城市名统一成一个 key。

    「北京市」「北京 市」「中国北京」都应归到「北京」；
    但长度 <= 2 的名字不动（「市」这种字不会单独出现，可安全跳过）。
    """
    s = (raw or "").strip().replace(" ", "").replace("\u3000", "")
    if not s:
        return ""
    if s.startswith("中国"):
        s = s[2:]
    for suffix in ("特别行政区", "市"):
        if len(s) > len(suffix) + 1 and s.endswith(suffix):
            s = s[: -len(suffix)]
            break
    return s


def _short_province(raw: str) -> str:
    """「江苏省」→「江苏」，「新疆维吾尔自治区」→「新疆」"""
    s = (raw or "").strip()
    for suffix in (
        "维吾尔自治区", "壮族自治区", "回族自治区", "特别行政区", "自治区", "省", "市",
    ):
        if s.endswith(suffix) and len(s) > len(suffix):
            return s[: -len(suffix)]
    return s


def province_of(adcode: str, fallback: str = "") -> str:
    """优先用 adcode 前两位判省，adcode 缺失时才退回名称"""
    code = (adcode or "").strip()
    if len(code) >= 2 and code[:2] in PROVINCE_BY_PREFIX:
        return PROVINCE_BY_PREFIX[code[:2]]
    return _short_province(fallback)


# ============ 城市解析（带缓存） ============

def _read_registry(name: str) -> Optional[dict]:
    with db_conn() as conn:
        row = conn.execute(
            "SELECT * FROM city_registry WHERE name = ?", (name,)
        ).fetchone()
    return dict(row) if row else None


def _write_registry(name: str, adcode: str, province: str,
                    lng: Optional[float], lat: Optional[float], source: str) -> None:
    with db_conn() as conn:
        conn.execute(
            """INSERT INTO city_registry (name, adcode, province, lng, lat, source, resolved_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(name) DO UPDATE SET
                 adcode = excluded.adcode,
                 province = excluded.province,
                 lng = excluded.lng,
                 lat = excluded.lat,
                 source = excluded.source,
                 resolved_at = excluded.resolved_at
            """,
            (name, adcode, province, lng, lat, source, _now_iso()),
        )


_POI_CACHE: dict[tuple[str, str], tuple[float, list[dict]]] = {}
_POI_CACHE_TTL = 600.0
_POI_CACHE_MAX = 300


def search_poi(keyword: str, city: str = "", limit: int = 10) -> list[dict]:
    """景点名 → 候选 POI（含 GCJ-02 坐标）。

    走高德 Web 服务 API 而不是 JSAPI 的 PlaceSearch 插件：插件要配安全密钥
    (securityJsCode)，而 key 是用户自己填的，配没配不由我们决定；这条 REST
    路径和城市行政区查询共用同一个 key，行为可控。

    查不到一律返回空列表，前端降级成「只能手填景点名、不出现在轨迹里」。
    """
    text = (keyword or "").strip()[:40]
    city_text = (city or "").strip()[:20]
    if len(text) < 2:
        return []

    cache_key = (text, city_text)
    now = time.time()
    cached = _POI_CACHE.get(cache_key)
    if cached and now - cached[0] < _POI_CACHE_TTL:
        return cached[1]

    settings = get_settings()
    if not settings.amap_api_key:
        return []

    params = {
        "keywords": text,
        "offset": max(1, min(limit, 25)),
        "page": 1,
        "extensions": "base",
        "key": settings.amap_api_key,
    }
    if city_text:
        params["city"] = city_text
        params["citylimit"] = "true"

    try:
        with httpx.Client(timeout=6.0) as client:
            payload = client.get(
                "https://restapi.amap.com/v3/place/text", params=params
            ).json()
    except Exception:
        return []
    if not isinstance(payload, dict) or str(payload.get("status")) != "1":
        return []

    items: list[dict] = []
    for poi in payload.get("pois") or []:
        location = str(poi.get("location") or "")
        if "," not in location:
            continue
        try:
            lng_text, lat_text = location.split(",", 1)
            lng, lat = float(lng_text), float(lat_text)
        except ValueError:
            continue
        name = str(poi.get("name") or "").strip()
        if not name:
            continue
        # 高德没有详细地址时会把 address 返回成 []，不是空串
        raw_address = poi.get("address")
        address = raw_address.strip() if isinstance(raw_address, str) else ""
        items.append({
            "name": name[:60],
            "address": address[:120],
            "lng": lng,
            "lat": lat,
            "adcode": str(poi.get("adcode") or ""),
            "district": str(poi.get("adname") or "")[:20],
        })

    # 这只是挡住连续敲字的重复请求，满了直接整表清空，不搞 LRU
    if len(_POI_CACHE) > _POI_CACHE_MAX:
        _POI_CACHE.clear()
    _POI_CACHE[cache_key] = (now, items)
    return items


def _amap_lookup(name: str) -> Optional[dict]:
    """高德行政区查询。失败一律返回 None，由调用方降级，不往上抛。"""
    settings = get_settings()
    if not settings.amap_api_key:
        return None
    try:
        with httpx.Client(timeout=8.0) as client:
            resp = client.get(
                "https://restapi.amap.com/v3/config/district",
                params={
                    "keywords": name,
                    "subdistrict": 0,
                    "extensions": "base",
                    "key": settings.amap_api_key,
                },
            )
            payload = resp.json()
    except Exception:
        return None

    if str(payload.get("status")) != "1":
        return None
    districts = payload.get("districts") or []
    if not districts:
        return None

    item = districts[0]
    center = str(item.get("center") or "")
    lng = lat = None
    if "," in center:
        try:
            lng_str, lat_str = center.split(",", 1)
            lng, lat = float(lng_str), float(lat_str)
        except ValueError:
            lng = lat = None

    adcode = str(item.get("adcode") or "")
    province_raw = str(item.get("province") or "")
    # 查的就是省级（北京/江苏）时 province 字段为空，用自身名字补
    province = province_of(adcode, province_raw or str(item.get("name") or ""))
    return {"adcode": adcode, "province": province, "lng": lng, "lat": lat}


def resolve_city(raw: str) -> dict:
    """城市名 → {name, display, adcode, province, lng, lat}

    顺序：本地缓存 → 内置表 → 高德。三级都拿不到也返回结果（坐标为空），
    让用户能先把行程记下来，不至于因为一个地名查不到就录不进去。
    """
    display = (raw or "").strip()
    name = normalize_city(display)
    if not name:
        raise FootprintError("请输入城市名称")

    cached = _read_registry(name)
    if cached:
        fresh = True
        if cached["source"] == "none":
            try:
                resolved = datetime.fromisoformat(cached["resolved_at"])
                fresh = (datetime.now(timezone.utc) - resolved) < _UNRESOLVED_TTL
            except (ValueError, TypeError):
                fresh = False
        if fresh:
            return {
                "name": name,
                "display": display,
                "adcode": cached["adcode"],
                "province": cached["province"],
                "lng": cached["lng"],
                "lat": cached["lat"],
            }

    if name in BUILTIN_CITIES:
        adcode, province, lng, lat = BUILTIN_CITIES[name]
        _write_registry(name, adcode, province, lng, lat, "builtin")
        return {
            "name": name, "display": display, "adcode": adcode,
            "province": province, "lng": lng, "lat": lat,
        }

    found = _amap_lookup(name)
    if found:
        _write_registry(name, found["adcode"], found["province"],
                        found["lng"], found["lat"], "amap")
        return {"name": name, "display": display, **found}

    _write_registry(name, "", "", None, None, "none")
    return {
        "name": name, "display": display, "adcode": "",
        "province": "", "lng": None, "lat": None,
    }


# ============ 行政区数据（省市两级，供前端选择） ============

_REGIONS_FILE = "regions.json"
_REGIONS_TTL = timedelta(days=30)
_regions_memo: Optional[list[dict]] = None

# 直辖市 / 特别行政区 / 台湾：省级节点本身就是「城市」，不再往下拆成区
_CITY_LEVEL_PROVINCES = {"11", "12", "31", "50", "71", "81", "82"}


def _regions_path() -> Path:
    return Path(get_settings().db_path).parent / _REGIONS_FILE


def _center_to_lnglat(center) -> tuple[Optional[float], Optional[float]]:
    text = str(center or "")
    if "," not in text:
        return None, None
    try:
        lng_str, lat_str = text.split(",", 1)
        return float(lng_str), float(lat_str)
    except ValueError:
        return None, None


_SHAPE_DIR = "province_shapes"
_SHAPE_TTL = timedelta(days=180)
_shape_memo: dict[str, list[list[list[float]]]] = {}


def _shape_dir() -> Path:
    path = Path(get_settings().db_path).parent / _SHAPE_DIR
    path.mkdir(parents=True, exist_ok=True)
    return path


def _simplify_ring(points: list[list[float]], limit: int = 900) -> list[list[float]]:
    """省界动辄上万点，直接发前端会又慢又占内存，按步长抽稀到 limit 以内。
    末端点必须保留，否则闭合环会在视觉上缺一个口子。"""
    if len(points) <= limit:
        return points
    step = math.ceil(len(points) / limit)
    picked = points[::step]
    if picked[-1] != points[-1]:
        picked.append(points[-1])
    return picked


def _parse_polyline(text: str) -> list[list[list[float]]]:
    """高德 district 接口的 polyline 格式：环与环用 | 分隔，点用 ;，坐标用 ,"""
    rings: list[list[list[float]]] = []
    for chunk in str(text or "").split("|"):
        points: list[list[float]] = []
        for pair in chunk.split(";"):
            if "," not in pair:
                continue
            lng_str, lat_str = pair.split(",", 1)
            try:
                points.append([round(float(lng_str), 4), round(float(lat_str), 4)])
            except ValueError:
                continue
        if len(points) >= 3:
            rings.append(_simplify_ring(points))
    return rings


def province_shape(adcode: str) -> list[list[list[float]]]:
    """取省级边界，供前端画「点亮的省份」色块。

    为什么要走后端：JSAPI 的 DistrictLayer / DistrictSearch 都需要安全密钥，
    项目里只配了 Web JS Key，那两个功能会静默失效；后端用 Web 服务 Key 走 REST 才拿得到。
    """
    code = "".join(ch for ch in str(adcode or "") if ch.isdigit())
    if len(code) != 6:
        raise FootprintError("省份编码不正确")
    if code in _shape_memo:
        return _shape_memo[code]

    cache_file = _shape_dir() / f"{code}.json"
    if cache_file.exists():
        try:
            payload = json.loads(cache_file.read_text("utf-8"))
            if time.time() - float(payload.get("ts", 0)) < _SHAPE_TTL.total_seconds():
                rings = payload.get("rings") or []
                if rings:
                    _shape_memo[code] = rings
                    return rings
        except (ValueError, OSError):
            pass  # 缓存坏了就当没有，重新拉一次

    settings = get_settings()
    if not settings.amap_api_key:
        raise FootprintError("没有配置高德 Web 服务 Key，画不出省份边界")

    try:
        with httpx.Client(timeout=25.0) as client:
            resp = client.get(
                "https://restapi.amap.com/v3/config/district",
                params={
                    "keywords": code,
                    "subdistrict": 0,
                    "extensions": "all",
                    "key": settings.amap_api_key,
                },
            )
            payload = resp.json()
    except Exception as exc:
        raise FootprintError("省界查询失败，稍后再试") from exc

    if str(payload.get("status")) != "1":
        raise FootprintError("高德没返回这个省份的边界")

    node = (payload.get("districts") or [{}])[0]
    rings = _parse_polyline(node.get("polyline") or "")
    if not rings:
        raise FootprintError("这个省份没有边界数据")

    try:
        cache_file.write_text(
            json.dumps({"ts": time.time(), "rings": rings}, ensure_ascii=False),
            "utf-8",
        )
    except OSError:
        pass  # 落盘失败不影响本次返回
    _shape_memo[code] = rings
    return rings


def _fetch_regions_amap() -> Optional[list[dict]]:
    """一次拉全国省市两级。返回 None 表示拉不到，调用方自己降级。"""
    settings = get_settings()
    if not settings.amap_api_key:
        return None
    try:
        with httpx.Client(timeout=25.0) as client:
            resp = client.get(
                "https://restapi.amap.com/v3/config/district",
                params={
                    "keywords": "中国",
                    "subdistrict": 2,
                    "extensions": "base",
                    "key": settings.amap_api_key,
                },
            )
            payload = resp.json()
    except Exception:
        return None

    if str(payload.get("status")) != "1":
        return None
    root = (payload.get("districts") or [{}])[0]

    provinces: list[dict] = []
    for node in root.get("districts") or []:
        pcode = str(node.get("adcode") or "").strip()
        pname = _short_province(str(node.get("name") or ""))
        if not pcode or not pname:
            continue

        cities: list[dict] = []
        if pcode[:2] in _CITY_LEVEL_PROVINCES:
            lng, lat = _center_to_lnglat(node.get("center"))
            cities.append({"name": pname, "adcode": pcode, "lng": lng, "lat": lat})
        else:
            for child in node.get("districts") or []:
                ccode = str(child.get("adcode") or "").strip()
                cname = normalize_city(str(child.get("name") or ""))
                if not ccode or not cname:
                    continue
                lng, lat = _center_to_lnglat(child.get("center"))
                cities.append({"name": cname, "adcode": ccode, "lng": lng, "lat": lat})
            if not cities:
                # 台湾等没有下级地市数据，就把省级自身当成一个城市项
                lng, lat = _center_to_lnglat(node.get("center"))
                cities.append({"name": pname, "adcode": pcode, "lng": lng, "lat": lat})

        provinces.append({"name": pname, "adcode": pcode, "cities": cities})

    # 高德返回的顺序是乱的，按 adcode 排：省按行政区划顺序，省内省会/首府自然靠前
    for province in provinces:
        province["cities"].sort(key=lambda c: c["adcode"])
    provinces.sort(key=lambda p: p["adcode"])
    return provinces or None


def _regions_from_builtin() -> list[dict]:
    """高德不可用时的兜底：把内置城市表按省分组。

    只有 88 个热门城市，不够全，但保证断网、没配 key 的情况下
    页面仍然可用，不至于连录入都打不开。
    """
    grouped: dict[str, list[dict]] = {}
    for name, (adcode, province, lng, lat) in BUILTIN_CITIES.items():
        grouped.setdefault(province, []).append(
            {"name": name, "adcode": adcode, "lng": lng, "lat": lat}
        )

    provinces: list[dict] = []
    for province, cities in grouped.items():
        cities.sort(key=lambda c: c["adcode"])
        prefix = cities[0]["adcode"][:2]
        provinces.append({
            "name": province,
            "adcode": f"{prefix}0000",
            "cities": cities,
        })

    order = {name: i for i, name in enumerate(PROVINCE_BY_PREFIX.values())}
    provinces.sort(key=lambda p: order.get(p["name"], 99))
    for province in provinces:
        province["cities"].sort(key=lambda c: c["adcode"])
    return provinces


def _sync_registry(regions: list[dict]) -> None:
    """把行政区数据灌进 city_registry。

    录入时 resolve_city 第一步就查这张表，命中后完全不发网络请求；
    之前查失败留下的 source='none' 记录也在这里修掉。
    """
    rows = []
    now = _now_iso()
    for province in regions:
        for city in province.get("cities") or []:
            if city.get("name") and city.get("adcode"):
                rows.append((
                    city["name"], city["adcode"], province["name"],
                    city.get("lng"), city.get("lat"), "region", now,
                ))
    if not rows:
        return
    with db_conn() as conn:
        conn.executemany(
            """INSERT INTO city_registry (name, adcode, province, lng, lat, source, resolved_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(name) DO UPDATE SET
                 adcode = excluded.adcode,
                 province = excluded.province,
                 lng = excluded.lng,
                 lat = excluded.lat,
                 source = excluded.source,
                 resolved_at = excluded.resolved_at
               WHERE city_registry.source = 'none'""",
            rows,
        )


def build_regions(force: bool = False) -> list[dict]:
    """省市两级行政区数据。

    优先级：进程内存 → data/regions.json（30 天内有效）→ 高德 → 内置表。
    落盘是为了不在每次启动都打高德接口，也避免限流。
    """
    global _regions_memo
    if _regions_memo is not None and not force:
        return _regions_memo

    path = _regions_path()
    if path.exists() and not force:
        try:
            fresh = (datetime.now().timestamp() - path.stat().st_mtime) < _REGIONS_TTL.total_seconds()
            if fresh:
                cached = json.loads(path.read_text(encoding="utf-8"))
                if cached:
                    _regions_memo = cached
                    _sync_registry(cached)
                    return cached
        except (OSError, ValueError):
            pass

    regions = _fetch_regions_amap()
    if regions:
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(regions, ensure_ascii=False), encoding="utf-8")
        except OSError:
            pass
    else:
        regions = _regions_from_builtin()

    _regions_memo = regions
    _sync_registry(regions)
    return regions


def guess_city_name(keyword: str) -> list[dict]:
    """录入框的联想候选：内置表按前缀/包含匹配，最多 8 条。

    纯本地计算，敲字时不发网络请求，输入体验才跟得上。
    """
    key = normalize_city(keyword)
    if not key:
        return []
    hits = []
    for name, (adcode, province, lng, lat) in BUILTIN_CITIES.items():
        if key in name:
            hits.append({
                "name": name, "adcode": adcode, "province": province,
                "lng": lng, "lat": lat,
                # 前缀命中的排前面
                "rank": 0 if name.startswith(key) else 1,
            })
    hits.sort(key=lambda x: (x["rank"], len(x["name"]), x["name"]))
    return hits[:8]


# ============ 写入 ============

def _member_ids_text(member_ids: Optional[list[int]], creator_id: int) -> str:
    ids = {int(x) for x in (member_ids or []) if str(x).strip().isdigit()}
    if not ids:
        ids = {int(creator_id)}
    return ",".join(str(i) for i in sorted(ids))


def create(family_id: int, user_id: int, city: str,
           start_date: str, end_date: str, note: str = "",
           member_ids: Optional[list[int]] = None,
           checkins: Optional[list[dict]] = None) -> dict:
    """新增一条足迹。同城同日范围重复时会明确报错，而不是静默忽略。"""
    info = resolve_city(city)
    start = (start_date or "").strip()
    end = (end_date or "").strip() or start
    if not start:
        raise FootprintError("请选择出行日期")
    if end < start:
        start, end = end, start

    now = _now_iso()
    members = _member_ids_text(member_ids, user_id)
    try:
        with db_conn() as conn:
            cursor = conn.execute(
                """INSERT INTO footprints
                   (family_id, city, display_city, province, adcode, lng, lat,
                    start_date, end_date, note, checkins, member_ids,
                    created_by, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    family_id, info["name"], info["display"], info["province"],
                    info["adcode"], info["lng"], info["lat"],
                    start, end, (note or "").strip(), _dump_checkins(checkins),
                    members, user_id, now, now,
                ),
            )
            row_id = cursor.lastrowid
            row = conn.execute("SELECT * FROM footprints WHERE id = ?", (row_id,)).fetchone()
    except sqlite3.IntegrityError:
        raise FootprintError("这座城市这段时间已经记过了，换个日期或直接编辑它") from None
    return _row_to_dict(row, _image_hosts(family_id))


def update(footprint_id: int, family_id: int, start_date: Optional[str],
           end_date: Optional[str], note: Optional[str],
           member_ids: Optional[list[int]],
           checkins: Optional[list[dict]] = None) -> Optional[dict]:
    """只允许改日期、备注、参与人和打卡记录。改城市视为另一趟，删了重录更清楚。"""
    with db_conn() as conn:
        row = conn.execute(
            "SELECT * FROM footprints WHERE id = ? AND family_id = ?",
            (footprint_id, family_id),
        ).fetchone()
        if row is None:
            return None

        # 日期传空串时保留原值，不允许把一条足迹的日期清空
        start = (start_date if start_date is not None else row["start_date"]).strip() or row["start_date"]
        end = (end_date if end_date is not None else row["end_date"]).strip() or start
        if start and end < start:
            start, end = end, start
        plain_note = note.strip() if note is not None else row["note"]
        members = (
            _member_ids_text(member_ids, row["created_by"])
            if member_ids is not None else row["member_ids"]
        )
        # 不传 checkins 表示这次不动打卡，传空数组才是清空
        checkins_text = (
            _dump_checkins(checkins) if checkins is not None else row["checkins"]
        )
        try:
            conn.execute(
                """UPDATE footprints
                   SET start_date = ?, end_date = ?, note = ?, checkins = ?,
                       member_ids = ?, updated_at = ?
                   WHERE id = ? AND family_id = ?""",
                (start, end, plain_note, checkins_text, members, _now_iso(),
                 footprint_id, family_id),
            )
        except sqlite3.IntegrityError:
            raise FootprintError("修改后的日期和已有记录重复了") from None
        updated = conn.execute(
            "SELECT * FROM footprints WHERE id = ?", (footprint_id,)
        ).fetchone()
    return _row_to_dict(updated, _image_hosts(family_id))


def delete(footprint_id: int, family_id: int) -> bool:
    with db_conn() as conn:
        cursor = conn.execute(
            "DELETE FROM footprints WHERE id = ? AND family_id = ?",
            (footprint_id, family_id),
        )
        return cursor.rowcount > 0


def list_all(family_id: int) -> list[dict]:
    with db_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM footprints WHERE family_id = ? ORDER BY start_date DESC, id DESC",
            (family_id,),
        ).fetchall()
    hosts = _image_hosts(family_id)
    return [_row_to_dict(r, hosts) for r in rows]


def _to_float(value) -> Optional[float]:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _parse_checkins(raw: str) -> list[dict]:
    """打卡记录存在一个 JSON 字段里。

    一条足迹可能去了好几个景点，做成子表要么多一次查询、要么多一套接口，
    而打卡从来只跟着足迹整体读写，塞进 JSON 反而更简单。
    解析一律容错：库里的数据坏掉时返回空列表，不能让整条足迹读不出来。
    """
    try:
        data = json.loads(raw or "[]")
    except (TypeError, ValueError):
        return []
    if not isinstance(data, list):
        return []

    out: list[dict] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        spot = str(item.get("spot") or "").strip()[:60]
        time_text = str(item.get("time") or "").strip()[:32]
        # 图片地址入库前剥掉签名参数：前端拿到的是带时效的临时地址，
        # 原样存下来会在几小时后变成一堆 403，读的时候再重新签。
        images = [
            strip_transient(url.strip())
            for url in (item.get("images") or [])
            if isinstance(url, str) and url.strip()
        ][:9]
        # 既没景点名也没图的不算一条打卡
        if not spot and not images:
            continue

        # 坐标必须成对且合法，否则宁可不画，也别把轨迹连到海里
        lng = _to_float(item.get("lng"))
        lat = _to_float(item.get("lat"))
        if lng is None or lat is None or not (-180 <= lng <= 180 and -90 <= lat <= 90):
            lng = lat = None

        out.append({
            "spot": spot,
            "address": str(item.get("address") or "").strip()[:120],
            "lng": lng,
            "lat": lat,
            "time": time_text,
            "images": images,
        })
    return out[:20]


def _dump_checkins(checkins: Optional[list[dict]]) -> str:
    if not checkins:
        return "[]"
    return json.dumps(_parse_checkins(json.dumps(checkins, ensure_ascii=False)), ensure_ascii=False)


def _image_hosts(family_id: int) -> set[str]:
    """取本家庭的存储域名，一次请求只取一次。

    没配存储、桶名改过之类的情况一律返回空集合，
    这时图片地址原样返回，不能让读列表跟着挂掉。
    """
    try:
        return family_hosts(get_runtime(family_id))
    except Exception:
        return set()


def _row_to_dict(row: sqlite3.Row, image_hosts: Optional[set[str]] = None) -> dict:
    members = [int(x) for x in (row["member_ids"] or "").split(",") if x.isdigit()]
    checkins = _parse_checkins(row["checkins"])
    # 桶是公共读的，库里存的就是能直接访问的地址；
    # 出列表时换成 OBS 缩略图地址，一张 3MB 的照片变百来 KB
    if image_hosts:
        for checkin in checkins:
            if checkin["images"]:
                checkin["images"] = thumb_urls(checkin["images"], image_hosts)
    return {
        "id": row["id"],
        "city": row["city"],
        "display_city": row["display_city"] or row["city"],
        "province": row["province"],
        "adcode": row["adcode"],
        "lng": row["lng"],
        "lat": row["lat"],
        "start_date": row["start_date"],
        "end_date": row["end_date"],
        "note": row["note"],
        "checkins": checkins,
        "member_ids": members or [row["created_by"]],
        "created_by": row["created_by"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


# ============ 统计 ============

def _parse_date(value: str) -> Optional[date]:
    try:
        return date.fromisoformat((value or "")[:10])
    except ValueError:
        return None


def _haversine_km(a: dict, b: dict) -> float:
    """两点球面距离。城市级足迹用它累加总里程，误差可忽略。"""
    if None in (a.get("lng"), a.get("lat"), b.get("lng"), b.get("lat")):
        return 0.0
    lon1, lat1, lon2, lat2 = map(
        math.radians, [a["lng"], a["lat"], b["lng"], b["lat"]]
    )
    dlon, dlat = lon2 - lon1, lat2 - lat1
    h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 2 * 6371.0 * math.asin(math.sqrt(h))


def _days_of(item: dict) -> set[date]:
    start = _parse_date(item["start_date"])
    end = _parse_date(item["end_date"]) or start
    if start is None:
        return set()
    out, cur = set(), start
    # 单条最多展开 60 天，防止误填 1900 年把统计撑爆
    while cur <= end and len(out) < 60:
        out.add(cur)
        cur += timedelta(days=1)
    return out


def _distance_km(items: list[dict]) -> float:
    """按时间顺序把城市串起来算总里程，相邻重复城市不重复计。"""
    ordered = sorted(items, key=lambda x: (x["start_date"] or "9999-12-31", x["id"]))
    total, prev = 0.0, None
    for item in ordered:
        if item.get("lng") is None:
            continue
        if prev is not None and prev["city"] != item["city"]:
            total += _haversine_km(prev, item)
        prev = item
    return round(total, 1)


def _aggregate_cities(items: list[dict]) -> list[dict]:
    """同一城市多次到访合成一行，供列表和地图点位使用。"""
    buckets: dict[str, dict] = {}
    for item in items:
        key = item["city"]
        bucket = buckets.get(key)
        if bucket is None:
            bucket = {
                "city": item["city"],
                "display_city": item["display_city"],
                "province": item["province"],
                "adcode": item["adcode"],
                "lng": item["lng"],
                "lat": item["lat"],
                "visit_count": 0,
                "day_count": 0,
                "first_date": item["start_date"],
                "last_date": item["end_date"],
                "member_ids": set(),
                "days": set(),
            }
            buckets[key] = bucket
        bucket["visit_count"] += 1
        bucket["days"] |= _days_of(item)
        bucket["day_count"] = len(bucket["days"])
        bucket["member_ids"] |= set(item["member_ids"])
        if item["start_date"] and item["start_date"] < bucket["first_date"]:
            bucket["first_date"] = item["start_date"]
        if item["end_date"] and item["end_date"] > bucket["last_date"]:
            bucket["last_date"] = item["end_date"]
        if bucket["lng"] is None and item["lng"] is not None:
            bucket["lng"], bucket["lat"] = item["lng"], item["lat"]

    cities = list(buckets.values())
    for c in cities:
        c["member_ids"] = sorted(c.pop("member_ids"))
        c.pop("days")
    cities.sort(key=lambda c: (c["visit_count"], c["last_date"]), reverse=True)
    return cities


def build_stats(items: list[dict]) -> dict:
    """一次算完全部统计。数据量是几十到几百条，直接内存计算即可。"""
    if not items:
        return {
            "city_count": 0, "province_count": 0, "day_count": 0,
            "distance_km": 0.0, "province_total": PROVINCE_TOTAL,
            "provinces": [], "cities": [],
        }

    cities = _aggregate_cities(items)

    provinces = sorted({
        c["province"] for c in cities if c["province"]
    })
    all_days: set[date] = set()
    for item in items:
        all_days |= _days_of(item)

    return {
        "city_count": len(cities),
        "province_count": len(provinces),
        "day_count": len(all_days),
        "distance_km": _distance_km(items),
        "province_total": PROVINCE_TOTAL,
        "provinces": provinces,
        "cities": cities,
    }


def build_years(items: list[dict]) -> list[dict]:
    """按年份分组统计，供年度回顾使用。"""
    buckets: dict[str, list[dict]] = {}
    for item in items:
        year = (item["start_date"] or item["end_date"] or "")[:4]
        if not year.isdigit():
            year = "未知"
        buckets.setdefault(year, []).append(item)

    years = []
    for year in sorted(buckets.keys(), reverse=True):
        subset = buckets[year]
        stats = build_stats(subset)
        years.append({
            "year": year,
            "city_count": stats["city_count"],
            "province_count": stats["province_count"],
            "day_count": stats["day_count"],
            "distance_km": stats["distance_km"],
            "cities": [c["display_city"] for c in stats["cities"]],
        })
    return years

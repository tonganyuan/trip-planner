from datetime import datetime
from typing import List, Optional, Union
from pydantic import BaseModel, Field, field_validator


# ============ 请求模型 ============

class TripRequest(BaseModel):
    """旅行规划请求"""
    city: str = Field(..., description="目的地城市", example="北京")
    start_date: str = Field(..., description="开始日期 YYYY-MM-DD", example="2025-06-01")
    end_date: str = Field(..., description="结束日期 YYYY-MM-DD", example="2025-06-03")
    travel_days: int = Field(..., description="旅行天数", ge=1, le=30, example=3)
    transportation: str = Field(..., description="交通方式", example="公共交通")
    accommodation: str = Field(..., description="住宿偏好", example="经济型酒店")
    preferences: List[str] = Field(default=[], description="旅行偏好标签", example=["历史文化", "美食"])
    free_text_input: Optional[str] = Field(default="", description="额外要求", example="希望多安排一些博物馆")
    force: bool = Field(default=False, description="为 true 时跳过缓存重新生成")

    class Config:
        json_schema_extra = {
            "example": {
                "city": "北京",
                "start_date": "2025-06-01",
                "end_date": "2025-06-03",
                "travel_days": 3,
                "transportation": "公共交通",
                "accommodation": "经济型酒店",
                "preferences": ["历史文化", "美食"],
                "free_text_input": "希望多安排一些博物馆"
            }
        }


class POISearchRequest(BaseModel):
    """POI搜索请求"""
    keywords: str = Field(..., description="搜索关键词", example="故宫")
    city: str = Field(..., description="城市", example="北京")
    citylimit: bool = Field(default=True, description="是否限制在城市范围内")


class RouteRequest(BaseModel):
    """路线规划请求"""
    origin_address: str = Field(..., description="起点地址", example="北京市朝阳区阜通东大街6号")
    destination_address: str = Field(..., description="终点地址", example="北京市海淀区上地十街10号")
    origin_city: Optional[str] = Field(default=None, description="起点城市")
    destination_city: Optional[str] = Field(default=None, description="终点城市")
    route_type: str = Field(default="walking", description="路线类型: walking/driving/transit")


# ============ 响应模型 ============

class Location(BaseModel):
    """地理位置"""
    longitude: float = Field(..., description="经度")
    latitude: float = Field(..., description="纬度")


class Attraction(BaseModel):
    """景点信息"""
    name: str = Field(..., description="景点名称")
    address: str = Field(..., description="地址")
    location: Location = Field(..., description="经纬度坐标")
    visit_duration: int = Field(..., description="建议游览时间(分钟)")
    description: str = Field(..., description="景点描述")
    category: Optional[str] = Field(default="景点", description="景点类别")
    rating: Optional[float] = Field(default=None, description="评分")
    photos: Optional[List[str]] = Field(default_factory=list, description="景点图片URL列表")
    poi_id: Optional[str] = Field(default="", description="POI ID")
    image_url: Optional[str] = Field(default=None, description="图片URL")
    ticket_price: int = Field(default=0, description="门票价格(元)")


class Meal(BaseModel):
    """餐饮信息"""
    type: str = Field(..., description="餐饮类型: breakfast/lunch/dinner/snack")
    name: str = Field(..., description="餐饮名称")
    address: Optional[str] = Field(default=None, description="地址")
    location: Optional[Location] = Field(default=None, description="经纬度坐标")
    description: Optional[str] = Field(default=None, description="描述")
    estimated_cost: int = Field(default=0, description="预估费用(元)")


class Hotel(BaseModel):
    """酒店信息"""
    name: str = Field(..., description="酒店名称")
    address: str = Field(default="", description="酒店地址")
    location: Optional[Location] = Field(default=None, description="酒店位置")
    price_range: str = Field(default="", description="价格范围")
    rating: str = Field(default="", description="评分")
    distance: str = Field(default="", description="距离景点距离")
    type: str = Field(default="", description="酒店类型")
    estimated_cost: int = Field(default=0, description="预估费用(元/晚)")


class DayPlan(BaseModel):
    """单日行程"""
    date: str = Field(..., description="日期 YYYY-MM-DD")
    day_index: int = Field(..., description="第几天(从0开始)")
    description: str = Field(..., description="当日行程描述")
    transportation: str = Field(..., description="交通方式")
    accommodation: str = Field(..., description="住宿")
    hotel: Optional[Hotel] = Field(default=None, description="推荐酒店")
    attractions: List[Attraction] = Field(default=[], description="景点列表")
    meals: List[Meal] = Field(default=[], description="餐饮列表")


class WeatherInfo(BaseModel):
    """天气信息"""
    date: str = Field(..., description="日期 YYYY-MM-DD")
    day_weather: str = Field(default="", description="白天天气")
    night_weather: str = Field(default="", description="夜间天气")
    day_temp: Union[int, str] = Field(default=0, description="白天温度")
    night_temp: Union[int, str] = Field(default=0, description="夜间温度")
    wind_direction: str = Field(default="", description="风向")
    wind_power: str = Field(default="", description="风力")

    @field_validator('day_temp', 'night_temp', mode='before')
    @classmethod
    def parse_temperature(cls, v):
        """解析温度,移除°C等单位"""
        if isinstance(v, str):
            # 移除°C, ℃等单位符号
            v = v.replace('°C', '').replace('℃', '').replace('°', '').strip()
            try:
                return int(v)
            except ValueError:
                return 0
        return v


class Budget(BaseModel):
    """预算信息"""
    total_attractions: int = Field(default=0, description="景点门票总费用")
    total_hotels: int = Field(default=0, description="酒店总费用")
    total_meals: int = Field(default=0, description="餐饮总费用")
    total_transportation: int = Field(default=0, description="交通总费用")
    total: int = Field(default=0, description="总费用")


class TripPlan(BaseModel):
    """旅行计划"""
    city: str = Field(..., description="目的地城市")
    start_date: str = Field(..., description="开始日期")
    end_date: str = Field(..., description="结束日期")
    days: List[DayPlan] = Field(..., description="每日行程")
    weather_info: List[WeatherInfo] = Field(default=[], description="天气信息")
    overall_suggestions: str = Field(..., description="总体建议")
    budget: Optional[Budget] = Field(default=None, description="预算信息")


class TripPlanResponse(BaseModel):
    """旅行计划响应"""
    success: bool = Field(..., description="是否成功")
    message: str = Field(default="", description="消息")
    data: Optional[TripPlan] = Field(default=None, description="旅行计划数据")
    from_cache: bool = Field(default=False, description="是否命中缓存(命中时零 agent 调用)")
    trip_id: Optional[int] = Field(default=None, description="行程记录ID，用于历史详情")
    cached_at: Optional[str] = Field(default=None, description="缓存生成/更新时间")


class TripHistoryItem(BaseModel):
    """行程历史列表项(不含完整方案)"""
    id: int
    city: str
    start_date: str
    end_date: str
    created_by: int = Field(default=0, description="生成者用户ID")
    created_at: str = Field(default="", description="首次生成时间")
    updated_at: str = Field(default="", description="最近更新时间")
    hit_count: int = Field(default=0, description="被复用次数")


class TripHistoryResponse(BaseModel):
    """行程历史列表"""
    success: bool = Field(default=True, description="是否成功")
    items: List[TripHistoryItem] = Field(default_factory=list, description="行程列表")


class POIInfo(BaseModel):
    """POI信息"""
    id: str = Field(..., description="POI ID")
    name: str = Field(..., description="名称")
    type: str = Field(..., description="类型")
    address: str = Field(..., description="地址")
    location: Location = Field(..., description="经纬度坐标")
    tel: Optional[str] = Field(default=None, description="电话")


class POISearchResponse(BaseModel):
    """POI搜索响应"""
    success: bool = Field(..., description="是否成功")
    message: str = Field(default="", description="消息")
    data: List[POIInfo] = Field(default=[], description="POI列表")


class RouteInfo(BaseModel):
    """路线信息"""
    distance: float = Field(..., description="距离(米)")
    duration: int = Field(..., description="时间(秒)")
    route_type: str = Field(..., description="路线类型")
    description: str = Field(..., description="路线描述")


class RouteResponse(BaseModel):
    """路线规划响应"""
    success: bool = Field(..., description="是否成功")
    message: str = Field(default="", description="消息")
    data: Optional[RouteInfo] = Field(default=None, description="路线信息")


class WeatherResponse(BaseModel):
    """天气查询响应"""
    success: bool = Field(..., description="是否成功")
    message: str = Field(default="", description="消息")
    data: List[WeatherInfo] = Field(default=[], description="天气信息")


# ============ 用户认证 ============

class UserRegister(BaseModel):
    """注册请求"""
    username: str = Field(..., min_length=3, max_length=64, description="用户名或邮箱", example="pangzi")
    password: str = Field(..., min_length=6, max_length=64, description="密码，至少6位", example="trip2025")
    display_name: Optional[str] = Field(default="", max_length=32, description="显示名称", example="胖子")

    @field_validator("username")
    @classmethod
    def strip_username(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("用户名不能为空")
        return v

    class Config:
        json_schema_extra = {
            "example": {"username": "pangzi", "password": "trip2025", "display_name": "胖子"}
        }


class UserLogin(BaseModel):
    """登录请求"""
    username: str = Field(..., description="用户名或邮箱", example="pangzi")
    password: str = Field(..., description="密码", example="trip2025")


class UserInfo(BaseModel):
    """用户信息(不含密码)"""
    id: int = Field(..., description="用户ID")
    username: str = Field(..., description="用户名")
    display_name: str = Field(default="", description="显示名称")
    family_id: int = Field(default=0, description="所属家庭ID")
    created_at: str = Field(default="", description="注册时间")
    last_login_at: Optional[str] = Field(default=None, description="最近登录时间")


class AuthResponse(BaseModel):
    """认证响应：登录/注册成功时带 token"""
    success: bool = Field(default=True, description="是否成功")
    message: str = Field(default="", description="消息")
    token: Optional[str] = Field(default=None, description="访问令牌")
    expires_at: Optional[str] = Field(default=None, description="令牌过期时间")
    user: Optional[UserInfo] = Field(default=None, description="用户信息")


# ============ 家庭成员 ============

class FamilyMemberCreate(BaseModel):
    """添加家庭成员（创建全新账号并加入当前家庭）"""
    username: str = Field(..., min_length=3, max_length=64, description="登录用户名", example="family01")
    password: str = Field(..., min_length=6, max_length=64, description="密码，至少6位", example="trip2025")
    display_name: Optional[str] = Field(default="", max_length=32, description="家庭内称呼", example="妈妈")

    @field_validator("username")
    @classmethod
    def strip_username(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("用户名不能为空")
        return v


class FamilyRename(BaseModel):
    """修改家庭名称"""
    name: str = Field(..., min_length=1, max_length=32, description="家庭名称", example="我们家")


class FamilyMember(BaseModel):
    """家庭成员（不含密码）"""
    id: int
    username: str
    display_name: str
    is_owner: bool = Field(default=False, description="是否户主")
    created_at: str = Field(default="", description="加入时间")
    last_login_at: Optional[str] = Field(default=None, description="最近登录时间")


class FamilyInfo(BaseModel):
    """家庭信息 + 成员列表"""
    id: int
    name: str
    owner_id: int
    is_owner: bool = Field(default=False, description="当前用户是否户主")
    member_count: int = Field(default=0, description="成员数")
    members: List[FamilyMember] = Field(default_factory=list, description="成员列表")


class FamilyMutationResponse(BaseModel):
    """家庭写操作响应"""
    success: bool = Field(default=True, description="是否成功")
    message: str = Field(default="", description="消息")
    member: Optional[FamilyMember] = Field(default=None, description="新增/受影响的成员")
    family: Optional[FamilyInfo] = Field(default=None, description="最新的家庭信息")


# ============ 家庭模型配置 ============

class LlmConfigSave(BaseModel):
    """保存家庭模型配置"""
    provider: str = Field(default="custom", max_length=32, description="预设标识，仅用于回显")
    base_url: str = Field(..., description="OpenAI 兼容服务地址", example="https://api.deepseek.com")
    model: str = Field(..., description="模型名称", example="deepseek-chat")
    api_key: str = Field(default="", description="API Key；留空表示沿用已保存的 Key")
    temperature: float = Field(default=0.7, ge=0, le=2, description="温度")


class LlmConfigTest(BaseModel):
    """测试连通性（不落库）"""
    provider: str = Field(default="custom", max_length=32)
    base_url: str = Field(default="", description="留空则用已保存的地址")
    model: str = Field(default="", description="留空则用已保存的模型")
    api_key: str = Field(default="", description="留空则用已保存的 Key")


class LlmConfigPublic(BaseModel):
    """对外的家庭模型配置，绝不含明文 Key"""
    configured: bool = Field(default=False, description="是否已配置")
    provider: str = Field(default="custom")
    base_url: str = Field(default="")
    model: str = Field(default="")
    api_key_hint: str = Field(default="", description="脱敏后的 Key，如 sk-…a1b2")
    temperature: float = Field(default=0.7)
    updated_at: Optional[str] = Field(default=None, description="最近修改时间")
    updated_by_name: Optional[str] = Field(default=None, description="由谁修改")
    verified_at: Optional[str] = Field(default=None, description="最近一次测试成功时间")


class LlmProviderPreset(BaseModel):
    """预置服务商，前端用来一键填表"""
    id: str
    label: str
    base_url: str
    model: str
    doc_url: str = ""
    note: str = ""


class LlmConfigResponse(BaseModel):
    """家庭模型配置响应"""
    success: bool = Field(default=True)
    message: str = Field(default="")
    config: LlmConfigPublic
    is_owner: bool = Field(default=False, description="当前用户是否可修改")
    presets: List[LlmProviderPreset] = Field(default_factory=list)


class LlmTestResponse(BaseModel):
    """连通性测试结果"""
    success: bool = Field(default=True)
    message: str = Field(default="连接成功")
    latency_ms: int = Field(default=0)
    reply: str = Field(default="", description="模型返回的样例内容")
    model: str = Field(default="")
    base_url: str = Field(default="")


# ============ 足迹 ============

def _date_text(value: str, field: str) -> str:
    """日期统一成 YYYY-MM-DD 再入库；空值原样返回"""
    v = (value or "").strip()
    if not v:
        return ""
    try:
        datetime.strptime(v[:10], "%Y-%m-%d")
    except ValueError:
        raise ValueError(f"{field}格式应为 YYYY-MM-DD") from None
    return v[:10]


class FootprintCheckin(BaseModel):
    """一条打卡记录：去了哪个景点、在哪儿、什么时候、留下了哪几张照片"""
    spot: str = Field(default="", max_length=60, description="景点名", example="拙政园")
    address: str = Field(
        default="", max_length=120,
        description="POI 地址，同名景点靠它区分", example="江苏省苏州市姑苏区东北街178号",
    )
    lng: Optional[float] = Field(default=None, description="经度（GCJ-02，高德坐标系）")
    lat: Optional[float] = Field(default=None, description="纬度（GCJ-02，高德坐标系）")
    time: str = Field(default="", max_length=32, description="打卡时间 YYYY-MM-DD HH:mm")
    images: List[str] = Field(default_factory=list, description="图片地址，最多 9 张")

    @field_validator("spot", "address", "time")
    @classmethod
    def strip_text(cls, v: str) -> str:
        return (v or "").strip()

    @field_validator("lng")
    @classmethod
    def check_lng(cls, v: Optional[float]) -> Optional[float]:
        if v is None or -180.0 <= v <= 180.0:
            return v
        raise ValueError("经度应在 -180 ~ 180 之间")

    @field_validator("lat")
    @classmethod
    def check_lat(cls, v: Optional[float]) -> Optional[float]:
        if v is None or -90.0 <= v <= 90.0:
            return v
        raise ValueError("纬度应在 -90 ~ 90 之间")

    @field_validator("images")
    @classmethod
    def only_http_urls(cls, v: List[str]) -> List[str]:
        """只收 http(s) 地址：防止把 javascript: 之类的串存进来，前端直接当 src 用"""
        out: List[str] = []
        for url in v or []:
            text = (url or "").strip()
            if text.startswith("https://") or text.startswith("http://"):
                out.append(text[:600])
        return out[:9]


class FootprintCreate(BaseModel):
    """录入一条足迹"""
    city: str = Field(..., min_length=1, max_length=32, description="城市名，自由输入", example="苏州")
    start_date: str = Field(..., description="到达日期 YYYY-MM-DD", example="2026-04-03")
    end_date: Optional[str] = Field(default="", description="离开日期；留空表示当天往返")
    note: str = Field(default="", max_length=200, description="备注", example="带娃去的，园林很好逛")
    member_ids: List[int] = Field(default_factory=list, description="这次谁去了；留空表示只有自己")
    checkins: List[FootprintCheckin] = Field(
        default_factory=list, description="本次行程的景点打卡，可多条"
    )

    @field_validator("city")
    @classmethod
    def strip_city(cls, v: str) -> str:
        v = (v or "").strip()
        if not v:
            raise ValueError("城市不能为空")
        return v

    @field_validator("start_date")
    @classmethod
    def check_start(cls, v: str) -> str:
        out = _date_text(v, "到达日期")
        if not out:
            raise ValueError("到达日期不能为空")
        return out

    @field_validator("end_date")
    @classmethod
    def check_end(cls, v: Optional[str]) -> str:
        return _date_text(v or "", "离开日期")


class FootprintUpdate(BaseModel):
    """修改足迹：不支持改城市，换城市等于另一趟行程"""
    start_date: Optional[str] = Field(default=None, description="到达日期")
    end_date: Optional[str] = Field(default=None, description="离开日期")
    note: Optional[str] = Field(default=None, max_length=200)
    member_ids: Optional[List[int]] = Field(default=None, description="参与成员")
    checkins: Optional[List[FootprintCheckin]] = Field(
        default=None, description="打卡记录；不传表示不改，传空数组表示清空"
    )

    @field_validator("start_date", "end_date")
    @classmethod
    def check_date(cls, v: Optional[str]) -> Optional[str]:
        return None if v is None else _date_text(v, "日期")


class FootprintItem(BaseModel):
    """一条足迹记录"""
    id: int
    city: str = Field(..., description="归一化城市名")
    display_city: str = Field(default="", description="展示用原名")
    province: str = Field(default="")
    adcode: str = Field(default="")
    lng: Optional[float] = Field(default=None)
    lat: Optional[float] = Field(default=None)
    start_date: str = Field(default="")
    end_date: str = Field(default="")
    note: str = Field(default="")
    checkins: List[FootprintCheckin] = Field(default_factory=list)
    member_ids: List[int] = Field(default_factory=list)
    created_by: int = Field(default=0)
    created_at: str = Field(default="")
    updated_at: str = Field(default="")


class FootprintCity(BaseModel):
    """城市聚合（同一城市多次到访合成一条）"""
    city: str
    display_city: str = ""
    province: str = Field(default="")
    adcode: str = Field(default="")
    lng: Optional[float] = Field(default=None)
    lat: Optional[float] = Field(default=None)
    visit_count: int = Field(default=1, description="去过几次")
    day_count: int = Field(default=0, description="在该城累计待了几天")
    first_date: str = Field(default="")
    last_date: str = Field(default="")
    member_ids: List[int] = Field(default_factory=list)


class FootprintStats(BaseModel):
    """足迹统计"""
    city_count: int = Field(default=0)
    province_count: int = Field(default=0)
    day_count: int = Field(default=0, description="在外天数（按日期去重）")
    distance_km: float = Field(default=0, description="按时间顺序累计的球面距离")
    province_total: int = Field(default=34, description="全国省级行政区总数")
    provinces: List[str] = Field(default_factory=list)
    cities: List[FootprintCity] = Field(default_factory=list)


class FootprintYear(BaseModel):
    """年度回顾"""
    year: str
    city_count: int = Field(default=0)
    province_count: int = Field(default=0)
    day_count: int = Field(default=0)
    distance_km: float = Field(default=0)
    cities: List[str] = Field(default_factory=list, description="当年去过的城市名")


class FootprintMember(BaseModel):
    """参与人选项（供前端筛选与录入勾选）"""
    id: int
    display_name: str = ""


class FootprintListResponse(BaseModel):
    success: bool = Field(default=True)
    message: str = Field(default="")
    items: List[FootprintItem] = Field(default_factory=list)
    stats: FootprintStats = Field(default_factory=FootprintStats)
    years: List[FootprintYear] = Field(default_factory=list)
    members: List[FootprintMember] = Field(default_factory=list)


class FootprintMutationResponse(BaseModel):
    """写操作响应：顺带把最新统计带回来，前端不用再请求一次"""
    success: bool = Field(default=True)
    message: str = Field(default="")
    item: Optional[FootprintItem] = Field(default=None)
    stats: Optional[FootprintStats] = Field(default=None)
    years: Optional[List[FootprintYear]] = Field(default=None)


class FootprintResolveResponse(BaseModel):
    """城市解析预览：让用户确认「苏州」会被记成「江苏 · 苏州」"""
    success: bool = Field(default=True)
    message: str = Field(default="")
    name: str = Field(default="")
    province: str = Field(default="")
    adcode: str = Field(default="")
    lng: Optional[float] = Field(default=None)
    lat: Optional[float] = Field(default=None)


class FootprintSuggestItem(BaseModel):
    name: str
    province: str = ""
    adcode: str = ""
    lng: Optional[float] = Field(default=None)
    lat: Optional[float] = Field(default=None)


class FootprintSuggestResponse(BaseModel):
    success: bool = Field(default=True)
    items: List[FootprintSuggestItem] = Field(default_factory=list)


class FootprintCityOption(BaseModel):
    """行政区里的一个市：城市名与坐标都来自官方数据，不是模型编的"""
    name: str
    adcode: str
    lng: Optional[float] = Field(default=None)
    lat: Optional[float] = Field(default=None)


class FootprintProvinceOption(BaseModel):
    name: str
    adcode: str
    cities: List[FootprintCityOption] = Field(default_factory=list)


class FootprintRegionsResponse(BaseModel):
    """省市两级行政区数据，录入时直接选，不需要手打城市名"""
    success: bool = Field(default=True)
    provinces: List[FootprintProvinceOption] = Field(default_factory=list)


# ============ 对象存储（华为云 OBS） ============

class OssConfigResponse(BaseModel):
    """给前端看的配置，AK/SK 只有脱敏提示串"""
    success: bool = Field(default=True)
    is_owner: bool = Field(default=True, description="当前用户是否户主（决定能否编辑）")
    configured: bool = Field(default=False)
    provider: str = Field(default="huawei")
    endpoint: str = Field(default="")
    region: str = Field(default="")
    bucket: str = Field(default="")
    prefix: str = Field(default="footprint")
    public_domain: str = Field(default="")
    ak_hint: str = Field(default="")
    sk_hint: str = Field(default="")
    updated_at: Optional[str] = Field(default=None)
    updated_by_name: Optional[str] = Field(default=None)
    verified_at: Optional[str] = Field(default=None)


class OssConfigSave(BaseModel):
    """保存配置。AK/SK 留空表示沿用已存的，避免每次改桶名都要重填密钥"""
    endpoint: str = Field(..., max_length=120, example="obs.cn-east-3.myhuaweicloud.com")
    bucket: str = Field(..., max_length=63, example="trip-photos")
    access_key_id: str = Field(default="", max_length=200)
    secret_access_key: str = Field(default="", max_length=400)
    prefix: str = Field(default="footprint", max_length=60)
    public_domain: str = Field(default="", max_length=120)
    region: str = Field(default="", max_length=32)


class OssTestResponse(BaseModel):
    success: bool = Field(default=True)
    message: str = Field(default="")
    latency_ms: int = Field(default=0)
    bucket: str = Field(default="")
    endpoint: str = Field(default="")


class UploadResponse(BaseModel):
    """上传结果：url 直接可放进 <img src>"""
    success: bool = Field(default=True)
    url: str = Field(default="")
    key: str = Field(default="")
    size: int = Field(default=0)
    content_type: str = Field(default="")
    filename: str = Field(default="")


# ============ 景点 POI ============

class FootprintPoiItem(BaseModel):
    """高德 POI 检索结果，只留画轨迹要用的字段"""
    name: str = Field(default="", description="景点名", example="拙政园")
    address: str = Field(default="", description="详细地址")
    lng: float = Field(..., description="经度（GCJ-02）")
    lat: float = Field(..., description="纬度（GCJ-02）")
    adcode: str = Field(default="", description="所属区县 adcode")
    district: str = Field(default="", description="所属区县名")


class FootprintPoiResponse(BaseModel):
    success: bool = Field(default=True)
    message: str = Field(default="")
    items: List[FootprintPoiItem] = Field(default_factory=list)


class FootprintShapeResponse(BaseModel):
    """省份边界：rings 是若干个闭合环，每环是一串 [lng, lat]"""
    success: bool = Field(default=True)
    adcode: str = Field(default="", description="省份 adcode")
    rings: List[List[List[float]]] = Field(default_factory=list)


# ============ 错误响应 ============

class ErrorResponse(BaseModel):
    """错误响应"""
    success: bool = Field(default=False, description="是否成功")
    message: str = Field(..., description="错误消息")
    error_code: Optional[str] = Field(default=None, description="错误代码")
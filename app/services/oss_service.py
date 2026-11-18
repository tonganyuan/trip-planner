"""家庭级对象存储（华为云 OBS）

打卡图片不进服务端磁盘：直接传进用户自己的桶，库里只留 URL。
好处是备份/迁移只带走 SQLite 就行，图片资产本来就在用户自己的云账号里，
服务端也不需要为存储扩容。

三条约束与 LLM 配置保持一致：
- AK/SK 只存密文（AES-GCM，密钥由 AUTH_SECRET 派生），接口只回显脱敏串；
- 只有户主能改，家庭成员只读；
- 配置按 family_id 存，一家人共用一份。
"""

import uuid
from datetime import datetime
from typing import Optional
from urllib.parse import parse_qsl, quote, urlencode, urlparse, urlunparse

from app.services import crypto
from app.services.auth_service import _now_iso
from app.services.db import db_conn
from app.services.family_service import is_owner

# 单张图片上限。手机直出照片常见 2~4MB，5MB 足够，再大也该先压缩
MAX_IMAGE_BYTES = 5 * 1024 * 1024

_ENDPOINT_MAX = 120
_BUCKET_MAX = 63

# 华为云 OBS 的 endpoint 形如 obs.cn-east-3.myhuaweicloud.com，
# 也允许带端口（自建/测试环境），但不能带协议和路径
_ALLOWED_OBJECT_CHARS = set(
    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_.~/"
)


class OssError(Exception):
    """配置不合法或上传失败，message 直接返回前端"""


class OssNotConfigured(OssError):
    """该家庭还没配置对象存储"""


# ============ 配置读写 ============

def _mask(secret: str) -> str:
    text = (secret or "").strip()
    if len(text) <= 8:
        return "****"
    return f"{text[:4]}…{text[-4:]}"


def _clean_endpoint(raw: str) -> str:
    """只保留 host[:port]，用户常把 https:// 一起粘进来"""
    text = (raw or "").strip()
    if not text:
        raise OssError("请填写 Endpoint，例如 obs.cn-east-3.myhuaweicloud.com")
    for scheme in ("https://", "http://"):
        if text.lower().startswith(scheme):
            text = text[len(scheme):]
            break
    text = text.rstrip("/")
    if "/" in text:
        raise OssError("Endpoint 只需要域名，不要带路径")
    if len(text) > _ENDPOINT_MAX:
        raise OssError("Endpoint 过长")
    if " " in text:
        raise OssError("Endpoint 不能包含空格")
    return text


def _clean_bucket(raw: str) -> str:
    text = (raw or "").strip()
    if not text:
        raise OssError("请填写桶名（Bucket）")
    if len(text) < 3 or len(text) > _BUCKET_MAX:
        raise OssError("桶名长度需在 3 ~ 63 个字符之间")
    if not all(ch.islower() or ch.isdigit() or ch == "-" for ch in text):
        raise OssError("桶名只能包含小写字母、数字和短横线")
    if text.startswith("-") or text.endswith("-"):
        raise OssError("桶名不能以短横线开头或结尾")
    return text


def _clean_prefix(raw: str) -> str:
    """对象键前缀，去掉首尾斜杠，避免拼出 // 或开头的 /"""
    text = (raw or "").strip().strip("/")
    if not text:
        return "footprint"
    if len(text) > 60:
        raise OssError("路径前缀过长")
    if any(ch not in _ALLOWED_OBJECT_CHARS for ch in text):
        raise OssError("路径前缀只能包含字母、数字、短横线、下划线、点和斜杠")
    return text


def _clean_domain(raw: str) -> str:
    text = (raw or "").strip()
    if not text:
        return ""
    for scheme in ("https://", "http://"):
        if text.lower().startswith(scheme):
            text = text[len(scheme):]
            break
    text = text.rstrip("/")
    if "/" in text or " " in text:
        raise OssError("访问域名只需要域名本身，不要带路径")
    if len(text) > 120:
        raise OssError("访问域名过长")
    return text


def _get_row(family_id: int) -> Optional[dict]:
    with db_conn() as conn:
        row = conn.execute(
            "SELECT * FROM family_oss_configs WHERE family_id = ?", (family_id,)
        ).fetchone()
    return dict(row) if row else None


def get_public(family_id: int) -> dict:
    """给前端看的配置：AK/SK 只给脱敏提示串"""
    row = _get_row(family_id)
    if row is None:
        return {
            "configured": False,
            "provider": "huawei",
            "endpoint": "",
            "region": "",
            "bucket": "",
            "prefix": "footprint",
            "public_domain": "",
            "ak_hint": "",
            "sk_hint": "",
            "updated_at": None,
            "updated_by_name": None,
            "verified_at": None,
        }
    with db_conn() as conn:
        updater = conn.execute(
            "SELECT display_name, username FROM users WHERE id = ?", (row["updated_by"],)
        ).fetchone()
    return {
        "configured": True,
        "provider": row["provider"],
        "endpoint": row["endpoint"],
        "region": row["region"],
        "bucket": row["bucket"],
        "prefix": row["prefix"],
        "public_domain": row["public_domain"],
        "ak_hint": row["ak_hint"],
        "sk_hint": row["sk_hint"],
        "updated_at": row["updated_at"],
        "updated_by_name": (updater["display_name"] or updater["username"]) if updater else None,
        "verified_at": row["verified_at"],
    }


def get_runtime(family_id: int) -> dict:
    """后端内部用：带明文 AK/SK，绝不返回给 HTTP 层"""
    row = _get_row(family_id)
    if row is None:
        raise OssNotConfigured(
            "本家庭还没有配置对象存储，请先在「对象存储设置」里填写华为云 OBS 信息"
        )
    try:
        ak = crypto.decrypt(row["ak_cipher"])
        sk = crypto.decrypt(row["sk_cipher"])
    except crypto.SecretError as exc:
        raise OssError(str(exc)) from None
    return {
        "family_id": family_id,
        "provider": row["provider"],
        "endpoint": row["endpoint"],
        "region": row["region"],
        "bucket": row["bucket"],
        "prefix": row["prefix"],
        "public_domain": row["public_domain"],
        "access_key_id": ak,
        "secret_access_key": sk,
    }


def save_config(
    actor: dict,
    *,
    endpoint: str,
    bucket: str,
    access_key_id: str = "",
    secret_access_key: str = "",
    prefix: str = "footprint",
    public_domain: str = "",
    region: str = "",
) -> dict:
    """新增/更新本家庭配置。仅户主可写。AK/SK 留空表示沿用已存的值。"""
    if not is_owner(actor):
        raise OssError("只有户主可以修改对象存储配置")

    endpoint = _clean_endpoint(endpoint)
    bucket = _clean_bucket(bucket)
    prefix = _clean_prefix(prefix)
    public_domain = _clean_domain(public_domain)
    region = (region or "").strip()[:32]

    existing = _get_row(actor["family_id"])
    ak = (access_key_id or "").strip()
    sk = (secret_access_key or "").strip()

    if ak:
        if len(ak) < 16 or len(ak) > 200 or any(ch in ak for ch in "\r\n"):
            raise OssError("Access Key ID 不像是有效值，请检查是否复制完整")
        ak_cipher, ak_hint = crypto.encrypt(ak), _mask(ak)
    elif existing:
        ak_cipher, ak_hint = existing["ak_cipher"], existing["ak_hint"]
    else:
        raise OssError("请填写 Access Key ID")

    if sk:
        if len(sk) < 16 or len(sk) > 400 or any(ch in sk for ch in "\r\n"):
            raise OssError("Secret Access Key 不像是有效值，请检查是否复制完整")
        sk_cipher, sk_hint = crypto.encrypt(sk), _mask(sk)
    elif existing:
        sk_cipher, sk_hint = existing["sk_cipher"], existing["sk_hint"]
    else:
        raise OssError("请填写 Secret Access Key")

    now = _now_iso()
    with db_conn() as conn:
        conn.execute(
            "INSERT INTO family_oss_configs "
            "(family_id, provider, endpoint, region, bucket, ak_cipher, ak_hint, "
            " sk_cipher, sk_hint, prefix, public_domain, updated_by, updated_at, verified_at) "
            "VALUES (?, 'huawei', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL) "
            "ON CONFLICT(family_id) DO UPDATE SET "
            " endpoint = excluded.endpoint, region = excluded.region, bucket = excluded.bucket, "
            " ak_cipher = excluded.ak_cipher, ak_hint = excluded.ak_hint, "
            " sk_cipher = excluded.sk_cipher, sk_hint = excluded.sk_hint, "
            " prefix = excluded.prefix, public_domain = excluded.public_domain, "
            " updated_by = excluded.updated_by, updated_at = excluded.updated_at, "
            # 换了桶或换了密钥就作废上一次验证结果，避免界面显示"已验证"但其实连不上
            " verified_at = CASE WHEN excluded.bucket = family_oss_configs.bucket "
            "   AND excluded.ak_cipher = family_oss_configs.ak_cipher "
            "   AND excluded.sk_cipher = family_oss_configs.sk_cipher "
            "   AND excluded.endpoint = family_oss_configs.endpoint "
            "   THEN family_oss_configs.verified_at ELSE NULL END",
            (
                actor["family_id"], endpoint, region, bucket, ak_cipher, ak_hint,
                sk_cipher, sk_hint, prefix, public_domain, actor["id"], now,
            ),
        )
    return get_public(actor["family_id"])


def delete_config(actor: dict) -> None:
    if not is_owner(actor):
        raise OssError("只有户主可以删除对象存储配置")
    with db_conn() as conn:
        conn.execute(
            "DELETE FROM family_oss_configs WHERE family_id = ?", (actor["family_id"],)
        )


# ============ OBS 客户端 ============

def _client(config: dict):
    """OBS SDK 的客户端不是线程安全的，每次用完即关"""
    try:
        from obs import ObsClient
    except ImportError:
        raise OssError("服务端缺少华为云 OBS SDK（esdk-obs-python），请先安装") from None

    return ObsClient(
        access_key_id=config["access_key_id"],
        secret_access_key=config["secret_access_key"],
        server=config["endpoint"],
        max_retry_count=1,
        timeout=60,
    )


def _explain(exc: Exception) -> str:
    """把 SDK 的英文异常翻成一句人话，同时确保不把 AK/SK 带出去"""
    text = str(exc)
    lowered = text.lower()
    if "403" in text or "accessdenied" in lowered or "access denied" in lowered:
        return "没有权限（403）：请检查 AK/SK 是否属于该桶所在账号，以及桶策略是否允许上传"
    if "404" in text or "nosuchbucket" in lowered:
        return "桶不存在（404）：请检查桶名和 Endpoint 是否属于同一个区域"
    if "401" in text or "signature" in lowered:
        return "AK/SK 不正确（签名校验失败）"
    if "timeout" in lowered or "timed out" in lowered:
        return "连接超时：请检查服务器能否访问该 Endpoint"
    if "name or service" in lowered or "getaddrinfo" in lowered or "connection" in lowered:
        return "无法连接该 Endpoint，请检查域名是否写错"
    return f"上传失败：{text[:180]}"


def _put_object(config: dict, key: str, data: bytes, content_type: str) -> None:
    """上传单个对象。

    先尝试带 public-read，让图片能直接被 <img> 引用；桶策略禁止 ACL 时
    退回普通上传（要求桶本身是公共读，或者用户配了 CDN 域名）。
    """
    client = _client(config)
    try:
        resp = client.putContent(
            config["bucket"], key, content=data,
            headers={"Content-Type": content_type, "x-obs-acl": "public-read"},
        )
        if resp.status >= 300:
            resp = client.putContent(
                config["bucket"], key, content=data,
                headers={"Content-Type": content_type},
            )
        if resp.status >= 300:
            detail = getattr(resp, "errorMessage", "") or f"HTTP {resp.status}"
            raise OssError(_explain(Exception(detail)))
    except OssError:
        raise
    except Exception as exc:
        raise OssError(_explain(exc)) from None
    finally:
        try:
            client.close()
        except Exception:
            pass


def test_connection(
    family_id: int,
    *,
    endpoint: str = "",
    bucket: str = "",
    access_key_id: str = "",
    secret_access_key: str = "",
    prefix: str = "",
    public_domain: str = "",
    region: str = "",
) -> dict:
    """真往桶里写一个小对象再删掉，验证的是「能不能上传」，比只查桶更贴近实际用途"""
    stored: dict = {}
    try:
        stored = get_runtime(family_id)
    except OssError:
        # 还没存过配置时，只允许用表单里的值测
        if not (access_key_id and secret_access_key):
            raise OssNotConfigured(
                "本家庭还没有配置对象存储，请先填写 Endpoint、桶名和 AK/SK"
            ) from None

    config = {
        "endpoint": _clean_endpoint(endpoint or stored.get("endpoint", "")),
        "bucket": _clean_bucket(bucket or stored.get("bucket", "")),
        "prefix": _clean_prefix(prefix or stored.get("prefix", "")),
        "public_domain": _clean_domain(public_domain or stored.get("public_domain", "")),
        "region": region or stored.get("region", ""),
        "access_key_id": (access_key_id or "").strip() or stored.get("access_key_id", ""),
        "secret_access_key": (secret_access_key or "").strip()
        or stored.get("secret_access_key", ""),
    }
    if not config["access_key_id"] or not config["secret_access_key"]:
        raise OssError("请填写 Access Key ID 与 Secret Access Key")

    key = f"{config['prefix']}/.connectivity-test-{uuid.uuid4().hex[:8]}.txt"
    started = _now_ms()
    _put_object(config, key, "trip-planner oss connectivity test".encode("utf-8"), "text/plain")
    elapsed = _now_ms() - started

    client = _client(config)
    try:
        client.deleteObject(config["bucket"], key)
    except Exception:
        # 测试对象删不掉不影响结论，桶里留个几十字节的垃圾而已
        pass
    finally:
        try:
            client.close()
        except Exception:
            pass

    # 测的就是已存配置时记一笔验证时间
    row = _get_row(family_id)
    if row and not (access_key_id or "").strip():
        with db_conn() as conn:
            conn.execute(
                "UPDATE family_oss_configs SET verified_at = ? WHERE family_id = ?",
                (_now_iso(), family_id),
            )

    return {
        "success": True,
        "message": "连接成功，上传与删除都正常",
        "latency_ms": elapsed,
        "bucket": config["bucket"],
        "endpoint": config["endpoint"],
    }


def _now_ms() -> int:
    return int(datetime.now().timestamp() * 1000)


# ============ 上传 ============

def _sniff_image(data: bytes) -> Optional[tuple[str, str]]:
    """按魔数判定真实类型。content-type 由客户端声明，不能全信。"""
    if data.startswith(b"\xff\xd8\xff"):
        return "jpg", "image/jpeg"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png", "image/png"
    if data.startswith(b"GIF87a") or data.startswith(b"GIF89a"):
        return "gif", "image/gif"
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "webp", "image/webp"
    return None


def object_url(config: dict, key: str) -> str:
    """拼接可访问地址：优先自定义域名（CDN），否则用 OBS 默认的 bucket.endpoint"""
    quoted = quote(key, safe="/")
    if config.get("public_domain"):
        return f"https://{config['public_domain']}/{quoted}"
    return f"https://{config['bucket']}.{config['endpoint']}/{quoted}"


# 返回给前端的都是缩略图：手机直出 2~4MB，缩到 640 宽只剩百来 KB，
# 地图上同时挂十几个城市照片也不会把首屏拖死
THUMB_PROCESS = "image/resize,w_640"

# 图片处理 / 签名相关的查询参数，入库前剥掉，库里只留干净的长期地址
_TRANSIENT_QUERY_KEYS = {
    "accesskeyid",
    "expires",
    "signature",
    "x-obs-security-token",
    "x-amz-algorithm",
    "x-amz-credential",
    "x-amz-date",
    "x-amz-expires",
    "x-amz-signedheaders",
    "x-amz-signature",
    "x-image-process",
}


def family_hosts(config: dict) -> set[str]:
    """本家庭存储可能出现的域名：OBS 默认域名 + 自定义/CDN 域名"""
    hosts = {f"{config['bucket']}.{config['endpoint']}".lower()}
    if config.get("public_domain"):
        hosts.add(str(config["public_domain"]).lower())
    return hosts


def strip_transient(url: str) -> str:
    """去掉图片处理与签名参数，留下可长期保存的原始地址"""
    text = (url or "").strip()
    if not text:
        return text
    parsed = urlparse(text)
    if not parsed.query:
        return text
    kept = [
        (k, v)
        for k, v in parse_qsl(parsed.query, keep_blank_values=True)
        if k.lower() not in _TRANSIENT_QUERY_KEYS
    ]
    return urlunparse(parsed._replace(query=urlencode(kept)))


def thumb_url(url: str, hosts: set[str], *, resize: str = THUMB_PROCESS) -> str:
    """给自家存储地址挂上 OBS 图片处理参数，返回缩略图地址。

    桶是公共读的，原地址本来就能直接访问，这里只是让 OBS 把图缩到 640 宽。
    外链、非自家域名、已经带处理参数的一律原样返回，别把用户填的外部图片改坏。
    """
    text = (url or "").strip()
    if not text or not hosts:
        return text
    parsed = urlparse(text)
    if parsed.scheme not in ("http", "https"):
        return text
    if (parsed.hostname or "").lower() not in hosts:
        return text
    if "x-image-process" in parsed.query:
        return text
    if not resize:
        return text
    sep = "&" if parsed.query else "?"
    return f"{text}{sep}x-image-process={quote(resize, safe='/,')}"


def thumb_urls(urls: list[str], hosts: set[str], *, resize: str = THUMB_PROCESS) -> list[str]:
    if not urls:
        return urls
    return [thumb_url(url, hosts, resize=resize) for url in urls]


def upload_image(family_id: int, data: bytes, filename: str = "") -> dict:
    """上传一张打卡图片，返回 URL 与对象键。

    对象键形如：footprint/12/2026/11/3f2a...c8.jpg
    按家庭和年月分目录，方便在 OBS 控制台按年份翻照片。
    """
    if not data:
        raise OssError("图片内容为空")
    if len(data) > MAX_IMAGE_BYTES:
        raise OssError(
            f"图片超过 {MAX_IMAGE_BYTES // 1024 // 1024}MB，请先压缩或裁剪后再传"
        )

    sniffed = _sniff_image(data)
    if sniffed is None:
        raise OssError("只支持 JPG / PNG / GIF / WEBP 图片")

    ext, mime = sniffed
    config = get_runtime(family_id)

    now = datetime.now()
    key = (
        f"{config['prefix']}/{family_id}/{now.year:04d}/{now.month:02d}/"
        f"{uuid.uuid4().hex}.{ext}"
    )
    _put_object(config, key, data, mime)

    permanent = object_url(config, key)
    return {
        "success": True,
        # url 是长期地址，存进足迹记录；preview_url 是缩略图，只用来立刻显示
        "url": permanent,
        "preview_url": thumb_url(permanent, family_hosts(config)),
        "key": key,
        "size": len(data),
        "content_type": mime,
        "filename": (filename or "")[:120],
    }

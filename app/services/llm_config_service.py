"""家庭级 LLM 配置服务

背景：站点自己的 LLM key 一旦给所有人用，任何一个注册用户都能拿它烧钱。
所以模型改成「每个家庭自己配」—— key、base_url、model 都存在该家庭名下，
生成行程时只用该家庭自己的配置，服务端不再留任何兜底 key。

几条硬性约束：
- API Key 只存密文（AES-GCM，密钥由 AUTH_SECRET 派生），接口永远不回传明文，
  前端能看到的只有形如 ``sk-…a1b2`` 的提示串；
- 只有户主能改/删，家庭成员只读（能看到脱敏后的配置，方便确认「用的是哪个模型」）；
- 配置按 family_id 存，家庭成员天然共用一份。
"""

import time
from typing import Optional
from urllib.parse import urlparse

from app.services import crypto
from app.services.auth_service import _now_iso
from app.services.db import db_conn
from app.services.family_service import is_owner

# 常见 OpenAI 兼容服务。只做「填表向导」，用户可以完全自定义
PROVIDER_PRESETS = [
    {
        "id": "deepseek",
        "label": "DeepSeek",
        "base_url": "https://api.deepseek.com",
        "model": "deepseek-chat",
        "doc_url": "https://platform.deepseek.com/api_keys",
        "note": "便宜、中文好，行程生成常用",
    },
    {
        "id": "openai",
        "label": "OpenAI",
        "base_url": "https://api.openai.com/v1",
        "model": "gpt-4o-mini",
        "doc_url": "https://platform.openai.com/api-keys",
        "note": "需要海外网络环境",
    },
    {
        "id": "qwen",
        "label": "阿里云百炼(通义千问)",
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "model": "qwen-plus",
        "doc_url": "https://bailian.console.aliyun.com/",
        "note": "国内直连，OpenAI 兼容模式",
    },
    {
        "id": "kimi",
        "label": "Moonshot(Kimi)",
        "base_url": "https://api.moonshot.cn/v1",
        "model": "moonshot-v1-8k",
        "doc_url": "https://platform.moonshot.cn/console/api-keys",
        "note": "国内直连",
    },
    {
        "id": "zhipu",
        "label": "智谱 GLM",
        "base_url": "https://open.bigmodel.cn/api/paas/v4",
        "model": "glm-4-flash",
        "doc_url": "https://open.bigmodel.cn/usercenter/apikeys",
        "note": "有免费额度",
    },
    {
        "id": "siliconflow",
        "label": "硅基流动",
        "base_url": "https://api.siliconflow.cn/v1",
        "model": "Qwen/Qwen2.5-7B-Instruct",
        "doc_url": "https://cloud.siliconflow.cn/account/ak",
        "note": "聚合多家开源模型",
    },
    {
        "id": "ollama",
        "label": "本地 Ollama",
        "base_url": "http://localhost:11434/v1",
        "model": "llama3.2",
        "doc_url": "https://ollama.com/",
        "note": "本机跑模型，API Key 随便填（如 ollama）",
    },
    {
        "id": "custom",
        "label": "自定义(OpenAI 兼容)",
        "base_url": "",
        "model": "",
        "doc_url": "",
        "note": "任何兼容 /chat/completions 的服务",
    },
]

# 云厂商元数据地址：SSRF 最常见的跳板，直接拒掉
_BLOCKED_HOSTS = {"169.254.169.254", "metadata.google.internal"}


class LlmConfigError(Exception):
    """配置不合法或调用失败，message 直接返回前端"""


class LlmNotConfigured(LlmConfigError):
    """该家庭还没配置模型"""


def _mask_key(key: str) -> str:
    key = key.strip()
    if len(key) <= 8:
        return "****"
    return f"{key[:3]}…{key[-4:]}"


def _clean_base_url(raw: str) -> str:
    url = (raw or "").strip()
    if not url:
        raise LlmConfigError("请填写服务地址（Base URL）")
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise LlmConfigError("服务地址必须以 http:// 或 https:// 开头")
    if not parsed.netloc:
        raise LlmConfigError("服务地址格式不正确")
    if parsed.hostname in _BLOCKED_HOSTS:
        raise LlmConfigError("不允许指向该地址")
    if len(url) > 500:
        raise LlmConfigError("服务地址过长")
    return url.rstrip("/")


def _get_row(family_id: int) -> Optional[dict]:
    with db_conn() as conn:
        row = conn.execute(
            "SELECT * FROM family_llm_configs WHERE family_id = ?", (family_id,)
        ).fetchone()
    return dict(row) if row else None


def get_public(family_id: int) -> dict:
    """给前端看的配置：绝不含明文 key"""
    row = _get_row(family_id)
    if row is None:
        return {
            "configured": False,
            "provider": "deepseek",
            "base_url": "",
            "model": "",
            "api_key_hint": "",
            "temperature": 0.7,
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
        "base_url": row["base_url"],
        "model": row["model"],
        "api_key_hint": row["api_key_hint"],
        "temperature": row["temperature"],
        "updated_at": row["updated_at"],
        "updated_by_name": (updater["display_name"] or updater["username"]) if updater else None,
        "verified_at": row["verified_at"],
    }


def get_runtime_config(family_id: int) -> dict:
    """给后端内部用：带明文 key，绝不返回给 HTTP 层"""
    row = _get_row(family_id)
    if row is None:
        raise LlmNotConfigured(
            "本家庭还没有配置大模型，请先在「模型设置」里填写自己的 API Key"
        )
    try:
        api_key = crypto.decrypt(row["api_key_cipher"])
    except crypto.SecretError as exc:
        raise LlmConfigError(str(exc)) from None
    return {
        "family_id": family_id,
        "provider": row["provider"],
        "base_url": row["base_url"],
        "model": row["model"],
        "api_key": api_key,
        "temperature": row["temperature"],
        "updated_at": row["updated_at"],
    }


def save_config(
    actor: dict,
    *,
    provider: str,
    base_url: str,
    model: str,
    api_key: str,
    temperature: float = 0.7,
) -> dict:
    """新增/更新本家庭配置。仅户主可写。api_key 留空表示沿用已存的 key。"""
    if not is_owner(actor):
        raise LlmConfigError("只有户主可以修改模型配置")

    base_url = _clean_base_url(base_url)
    model = (model or "").strip()
    if not model:
        raise LlmConfigError("请填写模型名称")
    if len(model) > 128:
        raise LlmConfigError("模型名称过长")
    if not (0.0 <= temperature <= 2.0):
        raise LlmConfigError("temperature 需在 0 ~ 2 之间")

    existing = _get_row(actor["family_id"])
    key = (api_key or "").strip()
    if key:
        if len(key) < 8 or len(key) > 400:
            raise LlmConfigError("API Key 长度不像是有效值")
        if any(ch in key for ch in "\r\n"):
            raise LlmConfigError("API Key 不能包含换行")
        cipher = crypto.encrypt(key)
        hint = _mask_key(key)
    elif existing:
        cipher = existing["api_key_cipher"]
        hint = existing["api_key_hint"]
    else:
        raise LlmConfigError("请填写 API Key")

    now = _now_iso()
    provider = (provider or "custom").strip()[:32]
    with db_conn() as conn:
        conn.execute(
            "INSERT INTO family_llm_configs "
            "(family_id, provider, base_url, model, api_key_cipher, api_key_hint, "
            " temperature, updated_by, updated_at, verified_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(family_id) DO UPDATE SET "
            " provider = excluded.provider, base_url = excluded.base_url, "
            " model = excluded.model, api_key_cipher = excluded.api_key_cipher, "
            " api_key_hint = excluded.api_key_hint, temperature = excluded.temperature, "
            " updated_by = excluded.updated_by, updated_at = excluded.updated_at, "
            " verified_at = CASE WHEN excluded.api_key_cipher = family_llm_configs.api_key_cipher "
            "                    THEN family_llm_configs.verified_at ELSE NULL END",
            (
                actor["family_id"],
                provider,
                base_url,
                model,
                cipher,
                hint,
                float(temperature),
                actor["id"],
                now,
                None,
            ),
        )
    return get_public(actor["family_id"])


def delete_config(actor: dict) -> None:
    if not is_owner(actor):
        raise LlmConfigError("只有户主可以删除模型配置")
    with db_conn() as conn:
        conn.execute("DELETE FROM family_llm_configs WHERE family_id = ?", (actor["family_id"],))


def test_connection(
    family_id: int,
    *,
    base_url: str = "",
    model: str = "",
    api_key: str = "",
    provider: str = "custom",
) -> dict:
    """真发一次极短的补全请求验证连通性。

    表单里填的优先；没填 key 就用已存的（这样「只改模型名」也能直接测）。
    """
    key = (api_key or "").strip()
    if not key:
        stored = get_runtime_config(family_id)
        key = stored["api_key"]
        base_url = base_url or stored["base_url"]
        model = model or stored["model"]

    base_url = _clean_base_url(base_url)
    model = (model or "").strip()
    if not model:
        raise LlmConfigError("请填写模型名称")

    from openai import OpenAI

    started = time.perf_counter()
    try:
        client = OpenAI(api_key=key, base_url=base_url, timeout=25, max_retries=0)
        resp = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": "只回复两个字：正常"}],
            temperature=0,
            max_tokens=16,
        )
        reply = (resp.choices[0].message.content or "").strip()[:60]
    except Exception as exc:
        raise LlmConfigError(_friendly_error(exc)) from None

    elapsed_ms = int((time.perf_counter() - started) * 1000)

    # 测的就是已存配置（没传新 key/base_url/model）时，记一笔验证时间
    stored = _get_row(family_id)
    if stored and not (api_key or "").strip() and stored["base_url"] == base_url and stored["model"] == model:
        with db_conn() as conn:
            conn.execute(
                "UPDATE family_llm_configs SET verified_at = ? WHERE family_id = ?",
                (_now_iso(), family_id),
            )

    return {
        "success": True,
        "message": "连接成功",
        "latency_ms": elapsed_ms,
        "reply": reply,
        "model": model,
        "base_url": base_url,
    }


def _friendly_error(exc: Exception) -> str:
    """把 SDK 的英文异常翻成人能看懂的一句话，同时确保不把 key 带出去"""
    text = str(exc)
    lowered = text.lower()
    if "401" in text or "authentication" in lowered or "invalid api key" in lowered:
        return "API Key 无效（服务端返回 401），请检查是否复制完整"
    if "403" in text:
        return "没有访问权限（403），请确认该 Key 是否开通了这个模型"
    if "404" in text or "model_not_found" in lowered:
        return "模型不存在或服务地址不对（404），请检查模型名与 Base URL"
    if "402" in text or "insufficient" in lowered or "balance" in lowered:
        return "账户余额不足（402），请到服务商控制台充值"
    if "429" in text or "rate limit" in lowered:
        return "请求过于频繁或余额不足（429）"
    if "timeout" in lowered or "timed out" in lowered:
        return "连接超时，请检查服务地址是否可从服务器访问"
    if "connection" in lowered:
        return "无法连接该地址，请检查 Base URL 是否写错或被网络拦截"
    return f"调用失败：{text[:180]}"

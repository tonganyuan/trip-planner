"""家庭级机密的加解密（AES-GCM）

LLM API Key 是「用户自己的钱袋子」，不能明文躺在 SQLite 里：
一旦服务器被拖库、或者有人拿到了 data/app.db 的备份，明文 key 就直接泄露，
不但能盗刷，还可能连带暴露账号归属。

做法：
- 密钥由 AUTH_SECRET 用 scrypt 派生，**不落库**；
- 加密用 AES-256-GCM，自带认证，密文被篡改解密会直接失败；
- 数据库里只存 ``v1:<base64(nonce||ciphertext)>``。

已知边界：换掉 AUTH_SECRET（或删了 data/.auth_secret）之后旧密文再也解不开，
表现为「密钥已失效，请重新填写」，这是预期行为，不是 bug。
"""

import base64
import hashlib
import os
import threading
from typing import Optional

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.services.auth_service import get_secret

# 固定盐：只是为了把 AUTH_SECRET 变成 32 字节密钥，不需要随机
_MASTER_SALT = b"trip-planner/family-llm-config/v1"
_KEY_LEN = 32
_NONCE_LEN = 12
_PREFIX = "v1:"

_key_lock = threading.Lock()
_cached_key: Optional[bytes] = None


class SecretError(Exception):
    """加解密失败，message 可直接给前端看"""


def _derive_key() -> bytes:
    """scrypt 派生只用一次，之后走缓存（单次约 100ms，不能每次请求都算）"""
    global _cached_key
    if _cached_key is not None:
        return _cached_key
    with _key_lock:
        if _cached_key is None:
            secret = get_secret().encode("utf-8")
            _cached_key = hashlib.scrypt(
                secret,
                salt=_MASTER_SALT,
                n=1 << 14,
                r=8,
                p=1,
                dklen=_KEY_LEN,
            )
    return _cached_key


def encrypt(plaintext: str) -> str:
    # nonce 必须每次随机，重复使用会让 GCM 彻底失效
    nonce = os.urandom(_NONCE_LEN)
    cipher = AESGCM(_derive_key()).encrypt(nonce, plaintext.encode("utf-8"), None)
    return _PREFIX + base64.urlsafe_b64encode(nonce + cipher).decode("ascii")


def decrypt(token: str) -> str:
    if not token or not token.startswith(_PREFIX):
        raise SecretError("密钥格式无法识别，请重新填写")
    try:
        raw = base64.urlsafe_b64decode(token[len(_PREFIX):].encode("ascii"))
        nonce, cipher = raw[:_NONCE_LEN], raw[_NONCE_LEN:]
        return AESGCM(_derive_key()).decrypt(nonce, cipher, None).decode("utf-8")
    except Exception:
        # GCM 认证失败最常见的原因是 AUTH_SECRET 换了，其次才是数据被改动
        raise SecretError("密钥已失效（服务端加密密钥变更），请重新填写") from None

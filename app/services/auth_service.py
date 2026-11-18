"""认证服务：密码哈希、用户表读写、JWT 签发与校验

密码用标准库 hashlib.scrypt，不引入 passlib/bcrypt —— 生产机装依赖时
不需要编译，也不会因为 bcrypt 版本和 passlib 打架而白屏。
JWT 用 PyJWT(HS256)，secret 优先取环境变量 AUTH_SECRET；未配置时
自动生成并落盘到 data/.auth_secret，重启后已签发的 token 依然有效。
"""

import hashlib
import hmac
import os
import secrets
import sqlite3
import threading
from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt

from app.config import get_settings
from app.services.db import db_conn, get_db_file

# scrypt 参数：n=16384 约 16MB 内存/次，单次校验毫秒级，足够抵抗离线爆破
_SCRYPT_N = 16384
_SCRYPT_R = 8
_SCRYPT_P = 1
_DK_LEN = 32

_secret_lock = threading.Lock()
_cached_secret: Optional[str] = None


class AuthError(Exception):
    """认证失败。message 会原样返回给前端，不要塞内部细节"""


# ============ 密码 ============

def hash_password(password: str) -> str:
    """返回 scrypt$n$r$p$salt$hash，salt 随机 16 字节"""
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt,
        n=_SCRYPT_N,
        r=_SCRYPT_R,
        p=_SCRYPT_P,
        dklen=_DK_LEN,
    )
    return f"scrypt${_SCRYPT_N}${_SCRYPT_R}${_SCRYPT_P}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    """常量时间比较，格式不合法一律视为失败"""
    try:
        algo, n, r, p, salt_hex, digest_hex = stored.split("$")
        if algo != "scrypt":
            return False
        digest = hashlib.scrypt(
            password.encode("utf-8"),
            salt=bytes.fromhex(salt_hex),
            n=int(n),
            r=int(r),
            p=int(p),
            dklen=len(bytes.fromhex(digest_hex)),
        )
        return hmac.compare_digest(digest.hex(), digest_hex)
    except (ValueError, TypeError):
        return False


def normalize_username(username: str) -> str:
    """用户名/邮箱统一小写去空格，避免 Abc 和 abc 注册成两个号"""
    return username.strip().lower()


# ============ 用户表 ============

def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _row_to_user(row: sqlite3.Row) -> dict:
    """对外暴露的用户信息，绝不带 password_hash"""
    return {
        "id": row["id"],
        "username": row["username"],
        "display_name": row["display_name"] or row["username"],
        "family_id": row["family_id"] if "family_id" in row.keys() else 0,
        "created_at": row["created_at"],
        "last_login_at": row["last_login_at"],
    }


def create_user(
    username: str,
    password: str,
    display_name: str = "",
    family_id: Optional[int] = None,
) -> dict:
    """创建用户。family_id=None 表示自建一个新的单人家庭；传入则加入已有家庭。"""
    username = normalize_username(username)
    password_hash = hash_password(password)
    now = _now_iso()
    try:
        with db_conn() as conn:
            if family_id is None:
                family_name = f"{(display_name or username).strip()[:30]}的家庭"
                cursor = conn.execute(
                    "INSERT INTO families (name, owner_id, created_at) VALUES (?, 0, ?)",
                    (family_name, now),
                )
                family_id = cursor.lastrowid
            else:
                if conn.execute("SELECT id FROM families WHERE id = ?", (family_id,)).fetchone() is None:
                    raise AuthError("家庭不存在")

            cursor = conn.execute(
                "INSERT INTO users (username, display_name, password_hash, family_id, created_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (username, (display_name or "").strip(), password_hash, family_id, now),
            )
            user_id = cursor.lastrowid
            # 新家庭此时才有户主 id，回填
            conn.execute(
                "UPDATE families SET owner_id = ? WHERE id = ? AND owner_id = 0",
                (user_id, family_id),
            )
            row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    except sqlite3.IntegrityError:
        raise AuthError("该用户名已被注册") from None
    return _row_to_user(row)


def get_user_by_username(username: str) -> Optional[dict]:
    """返回含 password_hash 的内部记录，仅供登录校验用"""
    with db_conn() as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE username = ?", (normalize_username(username),)
        ).fetchone()
    return dict(row) if row else None


def get_user_by_id(user_id: int) -> Optional[dict]:
    with db_conn() as conn:
        row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    return _row_to_user(row) if row else None


def count_users() -> int:
    with db_conn() as conn:
        row = conn.execute("SELECT COUNT(*) AS c FROM users").fetchone()
    return int(row["c"])


def authenticate(username: str, password: str) -> dict:
    """校验账号密码，成功返回用户信息并刷新 last_login_at"""
    record = get_user_by_username(username)
    if not record or not verify_password(password, record["password_hash"]):
        # 用户名不存在和密码错误给同一句提示，避免被用来枚举账号
        raise AuthError("用户名或密码不正确")

    now = _now_iso()
    with db_conn() as conn:
        conn.execute("UPDATE users SET last_login_at = ? WHERE id = ?", (now, record["id"]))
    record["last_login_at"] = now
    return _row_to_user(record)


# ============ JWT ============

def get_secret() -> str:
    """取签名密钥：环境变量优先，否则读/生成 data/.auth_secret"""
    global _cached_secret
    if _cached_secret:
        return _cached_secret

    with _secret_lock:
        if _cached_secret:
            return _cached_secret

        settings = get_settings()
        if settings.auth_secret:
            _cached_secret = settings.auth_secret
            return _cached_secret

        path = get_db_file().parent / ".auth_secret"
        if path.exists():
            _cached_secret = path.read_text(encoding="utf-8").strip()
        else:
            _cached_secret = secrets.token_urlsafe(48)
            path.write_text(_cached_secret, encoding="utf-8")
            try:
                os.chmod(path, 0o600)
            except OSError:
                # Windows 上 chmod 语义有限，失败不影响使用
                pass
        return _cached_secret


def create_access_token(user_id: int) -> tuple[str, str]:
    """返回 (token, 过期时间 ISO 字符串)"""
    settings = get_settings()
    now = datetime.now(timezone.utc)
    expire = now + timedelta(minutes=settings.auth_token_expire_minutes)
    payload = {
        # PyJWT 2.10+ 要求 sub 必须是字符串，传 int 会直接抛错
        "sub": str(user_id),
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
    }
    token = jwt.encode(payload, get_secret(), algorithm="HS256")
    return token, expire.replace(microsecond=0).isoformat()


def decode_token(token: str) -> dict:
    """解出 payload，过期/签名错/结构错统一抛 AuthError"""
    try:
        payload = jwt.decode(token, get_secret(), algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        raise AuthError("登录已过期，请重新登录")
    except jwt.InvalidTokenError:
        raise AuthError("登录状态无效，请重新登录")

    if not payload.get("sub"):
        raise AuthError("登录状态无效，请重新登录")
    return payload

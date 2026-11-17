"""FastAPI 依赖注入：从 Authorization 头解析当前用户"""

from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from starlette.concurrency import run_in_threadpool

from app.services import auth_service

# auto_error=False：没带 token 时由我们自己给中文提示，而不是 FastAPI 的英文 403
_bearer = HTTPBearer(auto_error=False, description="登录接口返回的 Bearer token")


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
) -> dict:
    """必须登录的接口用这个，失败一律 401"""
    if credentials is None or not credentials.credentials:
        raise _unauthorized("请先登录")

    def _resolve() -> Optional[dict]:
        payload = auth_service.decode_token(credentials.credentials)
        return auth_service.get_user_by_id(int(payload["sub"]))

    try:
        # 查库是同步 sqlite 调用，丢线程池避免卡住事件循环
        user = await run_in_threadpool(_resolve)
    except auth_service.AuthError as exc:
        raise _unauthorized(str(exc)) from None
    except (TypeError, ValueError):
        raise _unauthorized("登录状态无效，请重新登录") from None

    if user is None:
        raise _unauthorized("账号不存在或已注销")
    return user


async def get_optional_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
) -> Optional[dict]:
    """可匿名访问的接口用这个：没 token 或 token 失效都返回 None，不报错"""
    if credentials is None or not credentials.credentials:
        return None
    try:
        return await get_current_user(credentials)
    except HTTPException:
        return None

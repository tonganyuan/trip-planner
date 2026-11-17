"""用户认证 API 路由

JWT 是无状态的：登出由前端删掉本地 token 完成，服务端不留黑名单
(单进程内存黑名单重启即失效，反而更不可靠；要强制失效就换 AUTH_SECRET)。
"""

from fastapi import APIRouter, Depends, HTTPException, status
from starlette.concurrency import run_in_threadpool

from ..deps import get_current_user
from ...config import get_settings
from ...models.schedmas import AuthResponse, UserInfo, UserLogin, UserRegister
from ...services import auth_service

router = APIRouter(prefix="/auth", tags=["用户认证"])


@router.get(
    "/status",
    summary="认证配置",
    description="前端据此决定是否展示注册入口"
)
async def auth_status():
    settings = get_settings()
    has_users = await run_in_threadpool(auth_service.count_users)
    return {
        "success": True,
        "allow_register": settings.allow_register,
        "has_users": has_users,
    }


@router.post(
    "/register",
    response_model=AuthResponse,
    status_code=status.HTTP_201_CREATED,
    summary="注册",
    description="创建账号，成功后直接返回登录令牌"
)
async def register(payload: UserRegister):
    settings = get_settings()
    if not settings.allow_register:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="本站未开放注册"
        )

    try:
        user = await run_in_threadpool(
            auth_service.create_user,
            payload.username,
            payload.password,
            payload.display_name or "",
        )
    except auth_service.AuthError as exc:
        # 用户名唯一约束冲突
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from None

    token, expires_at = auth_service.create_access_token(user["id"])
    return AuthResponse(
        success=True,
        message="注册成功",
        token=token,
        expires_at=expires_at,
        user=UserInfo(**user),
    )


@router.post(
    "/login",
    response_model=AuthResponse,
    summary="登录",
    description="用户名+密码换取访问令牌"
)
async def login(payload: UserLogin):
    try:
        user = await run_in_threadpool(
            auth_service.authenticate, payload.username, payload.password
        )
    except auth_service.AuthError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc)
        ) from None

    token, expires_at = auth_service.create_access_token(user["id"])
    return AuthResponse(
        success=True,
        message="登录成功",
        token=token,
        expires_at=expires_at,
        user=UserInfo(**user),
    )


@router.get(
    "/me",
    response_model=AuthResponse,
    summary="当前用户",
    description="校验令牌并返回当前登录用户信息"
)
async def read_me(current_user: dict = Depends(get_current_user)):
    return AuthResponse(
        success=True,
        message="已登录",
        user=UserInfo(**current_user),
    )


@router.post(
    "/logout",
    response_model=AuthResponse,
    summary="退出登录",
    description="无状态令牌，服务端仅作确认，前端需删除本地令牌"
)
async def logout():
    return AuthResponse(success=True, message="已退出登录")

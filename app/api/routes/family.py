"""家庭 API：成员管理 + 家庭信息

所有接口都需要登录。数据共享的作用域是 family_id，
后续足迹接口也按当前用户的 family_id 过滤，家庭成员即得同一份记录。
"""

from fastapi import APIRouter, Depends, HTTPException, status
from starlette.concurrency import run_in_threadpool

from ..deps import get_current_user
from ...models.schedmas import (
    FamilyInfo,
    FamilyMemberCreate,
    FamilyMutationResponse,
    FamilyRename,
)
from ...services import family_service

router = APIRouter(prefix="/family", tags=["家庭成员"])


def _bad_request(exc: Exception) -> HTTPException:
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.get(
    "",
    response_model=FamilyInfo,
    summary="家庭信息",
    description="返回当前用户的家庭及全部成员"
)
async def read_family(current_user: dict = Depends(get_current_user)):
    try:
        return await run_in_threadpool(family_service.get_family_info, current_user)
    except family_service.FamilyError as exc:
        raise _bad_request(exc) from None


@router.post(
    "/members",
    response_model=FamilyMutationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="添加家庭成员",
    description="创建一个全新账号并加入当前家庭，成员可独立登录并共享数据"
)
async def add_member(
    payload: FamilyMemberCreate,
    current_user: dict = Depends(get_current_user),
):
    try:
        member = await run_in_threadpool(
            family_service.add_member,
            current_user,
            payload.username,
            payload.password,
            payload.display_name or "",
        )
        info = await run_in_threadpool(family_service.get_family_info, current_user)
    except family_service.FamilyError as exc:
        raise _bad_request(exc) from None
    return FamilyMutationResponse(
        success=True,
        message=f"已添加成员 {member['display_name']}",
        member=member,
        family=info,
    )


@router.delete(
    "/members/{member_id}",
    response_model=FamilyMutationResponse,
    summary="移除家庭成员",
    description="仅户主可用。成员账号保留，退出家庭后变为单人家庭"
)
async def remove_member(
    member_id: int,
    current_user: dict = Depends(get_current_user),
):
    try:
        await run_in_threadpool(family_service.remove_member, current_user, member_id)
        info = await run_in_threadpool(family_service.get_family_info, current_user)
    except family_service.FamilyError as exc:
        raise _bad_request(exc) from None
    return FamilyMutationResponse(
        success=True,
        message="已移出家庭",
        family=info,
    )


@router.patch(
    "",
    response_model=FamilyMutationResponse,
    summary="修改家庭名称",
    description="仅户主可用"
)
async def rename_family(
    payload: FamilyRename,
    current_user: dict = Depends(get_current_user),
):
    try:
        await run_in_threadpool(family_service.rename_family, current_user, payload.name)
        info = await run_in_threadpool(family_service.get_family_info, current_user)
    except family_service.FamilyError as exc:
        raise _bad_request(exc) from None
    return FamilyMutationResponse(success=True, message="家庭名称已更新", family=info)

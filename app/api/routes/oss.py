"""对象存储 API（华为云 OBS）

打卡图片直接传进用户自己的桶，服务端不落盘、也不做转发代理。

权限设计与模型配置一致：
- 家庭成员都能看到脱敏后的配置（知道家里用的是哪个桶）；
- 只有户主能改/测/删（因为改配置等于控制别人上传的去处）；
- 上传是所有人可用的，否则"打卡"这个功能只对户主开放，就失去意义了。
"""

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from starlette.concurrency import run_in_threadpool

from ..deps import get_current_user
from ...models.schedmas import (
    OssConfigResponse,
    OssConfigSave,
    OssTestResponse,
    UploadResponse,
)
from ...services import family_service, oss_service

router = APIRouter(prefix="/oss", tags=["对象存储"])


def _public(family_id: int) -> dict:
    return oss_service.get_public(family_id)


def _response(user: dict, data: dict) -> OssConfigResponse:
    return OssConfigResponse(
        success=True,
        is_owner=family_service.is_owner(user),
        **data,
    )


@router.get(
    "/config",
    response_model=OssConfigResponse,
    summary="读取对象存储配置",
    description="返回脱敏后的配置，AK/SK 只给形如 AKLT…a1b2 的提示串",
)
async def read_config(current_user: dict = Depends(get_current_user)):
    family_id = family_service.family_scope(current_user)
    data = await run_in_threadpool(_public, family_id)
    return _response(current_user, data)


@router.put(
    "/config",
    response_model=OssConfigResponse,
    summary="保存对象存储配置",
    description="仅户主可改。AK/SK 加密后存库；留空表示沿用已存的值",
)
async def save_config(
    payload: OssConfigSave,
    current_user: dict = Depends(get_current_user),
):
    try:
        data = await run_in_threadpool(
            oss_service.save_config,
            current_user,
            endpoint=payload.endpoint,
            bucket=payload.bucket,
            access_key_id=payload.access_key_id,
            secret_access_key=payload.secret_access_key,
            prefix=payload.prefix,
            public_domain=payload.public_domain,
            region=payload.region,
        )
    except oss_service.OssError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None
    return _response(current_user, data)


@router.post(
    "/config/test",
    response_model=OssTestResponse,
    summary="测试对象存储连通性",
    description="真往桶里写一个测试对象再删掉，验证的是「能不能上传」",
)
async def test_config(
    payload: OssConfigSave,
    current_user: dict = Depends(get_current_user),
):
    if not family_service.is_owner(current_user):
        raise HTTPException(status_code=400, detail="只有户主可以测试对象存储配置")
    family_id = family_service.family_scope(current_user)
    try:
        result = await run_in_threadpool(
            oss_service.test_connection,
            family_id,
            endpoint=payload.endpoint,
            bucket=payload.bucket,
            access_key_id=payload.access_key_id,
            secret_access_key=payload.secret_access_key,
            prefix=payload.prefix,
            public_domain=payload.public_domain,
            region=payload.region,
        )
    except oss_service.OssError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None
    return OssTestResponse(**result)


@router.delete(
    "/config",
    response_model=OssConfigResponse,
    summary="删除对象存储配置",
    description="仅户主可删。删除后打卡图片将无法再上传（已传的图不受影响）",
)
async def delete_config(current_user: dict = Depends(get_current_user)):
    try:
        await run_in_threadpool(oss_service.delete_config, current_user)
    except oss_service.OssError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None
    family_id = family_service.family_scope(current_user)
    data = await run_in_threadpool(_public, family_id)
    return _response(current_user, data)


@router.post(
    "/upload",
    response_model=UploadResponse,
    summary="上传打卡图片",
    description="直接传到本家庭自己的桶，返回可访问 URL；单张不超过 5MB",
)
async def upload_image(
    file: UploadFile = File(..., description="图片文件，JPG/PNG/GIF/WEBP"),
    current_user: dict = Depends(get_current_user),
):
    family_id = family_service.family_scope(current_user)

    # 只读上限 +1 字节：够判断是否超限，又不会被超大文件撑爆内存
    limit = oss_service.MAX_IMAGE_BYTES
    data = await file.read(limit + 1)
    filename = file.filename or ""
    await file.close()

    if len(data) > limit:
        raise HTTPException(
            status_code=400,
            detail=f"图片超过 {limit // 1024 // 1024}MB，请先压缩或裁剪后再传",
        )

    try:
        result = await run_in_threadpool(
            oss_service.upload_image, family_id, data, filename
        )
    except oss_service.OssError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None
    return UploadResponse(**result)

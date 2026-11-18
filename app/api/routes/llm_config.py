"""家庭模型配置 API

为什么要这个：站点自己的 LLM Key 给所有注册用户用，等于把钱包挂在门口。
改成每个家庭填自己的 Key / Base URL / 模型，生成行程时只花自己的额度。

权限：成员都能看（脱敏），只有户主能改。
"""

from fastapi import APIRouter, Depends, HTTPException, status
from starlette.concurrency import run_in_threadpool

from ..deps import get_current_user
from ...models.schedmas import (
    LlmConfigResponse,
    LlmConfigSave,
    LlmConfigTest,
    LlmProviderPreset,
    LlmTestResponse,
)
from ...services import family_service, llm_config_service

router = APIRouter(prefix="/llm-config", tags=["家庭模型配置"])


def _presets() -> list[LlmProviderPreset]:
    return [LlmProviderPreset(**item) for item in llm_config_service.PROVIDER_PRESETS]


def _response(user: dict, message: str = "") -> LlmConfigResponse:
    return LlmConfigResponse(
        message=message,
        config=llm_config_service.get_public(user["family_id"]),
        is_owner=family_service.is_owner(user),
        presets=_presets(),
    )


def _invalidate(family_id: int) -> None:
    """配置变了就丢掉已缓存的 agent，否则下一次生成还在用旧模型"""
    from ...agents.trip_planner_agent import invalidate_family_agent

    invalidate_family_agent(family_id)


@router.get(
    "",
    response_model=LlmConfigResponse,
    summary="读取家庭模型配置",
    description="返回脱敏后的配置（不含明文 API Key）与预置服务商列表"
)
async def read_config(current_user: dict = Depends(get_current_user)):
    return await run_in_threadpool(_response, current_user)


@router.put(
    "",
    response_model=LlmConfigResponse,
    summary="保存家庭模型配置",
    description="仅户主可改。API Key 加密后存库，接口不会回传明文"
)
async def save_config(
    payload: LlmConfigSave,
    current_user: dict = Depends(get_current_user),
):
    try:
        await run_in_threadpool(
            llm_config_service.save_config,
            current_user,
            provider=payload.provider,
            base_url=payload.base_url,
            model=payload.model,
            api_key=payload.api_key,
            temperature=payload.temperature,
        )
    except llm_config_service.LlmConfigError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from None
    _invalidate(current_user["family_id"])
    return await run_in_threadpool(_response, current_user, "模型配置已保存")


@router.delete(
    "",
    response_model=LlmConfigResponse,
    summary="删除家庭模型配置",
    description="仅户主可用。删除后该家庭无法生成行程，直到重新配置"
)
async def delete_config(current_user: dict = Depends(get_current_user)):
    try:
        await run_in_threadpool(llm_config_service.delete_config, current_user)
    except llm_config_service.LlmConfigError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from None
    _invalidate(current_user["family_id"])
    return await run_in_threadpool(_response, current_user, "模型配置已删除")


@router.post(
    "/test",
    response_model=LlmTestResponse,
    summary="测试模型连通性",
    description="真发一次极短的补全请求。API Key 留空则用已保存的"
)
async def test_config(
    payload: LlmConfigTest,
    current_user: dict = Depends(get_current_user),
):
    try:
        result = await run_in_threadpool(
            llm_config_service.test_connection,
            current_user["family_id"],
            base_url=payload.base_url,
            model=payload.model,
            api_key=payload.api_key,
            provider=payload.provider,
        )
    except llm_config_service.LlmConfigError as exc:
        # 用 400 而不是 500：这是用户填错，不是服务故障
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from None
    return LlmTestResponse(**result)

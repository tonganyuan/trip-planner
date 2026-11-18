"""旅行规划API路由"""

import time

from fastapi import APIRouter, Depends, HTTPException
from starlette.concurrency import run_in_threadpool
from ..deps import get_current_user
from ...models.schedmas import (
    TripRequest,
    TripPlanResponse,
    TripHistoryResponse,
    ErrorResponse
)
from ...agents.trip_planner_agent import get_trip_planner_agent
from ...services import trip_service, family_service, llm_config_service

router = APIRouter(prefix="/trip", tags=["旅行规划"])


@router.post(
    "/plan",
    response_model=TripPlanResponse,
    summary="生成旅行计划",
    description="根据用户输入的旅行需求,生成详细的旅行计划(需登录)"
)
async def plan_trip(request: TripRequest, current_user: dict = Depends(get_current_user)):
    """
    生成旅行计划

    这是全项目最贵的接口(几十秒 LLM + 多次高德 MCP 调用)，
    必须登录才能调用：前端路由守卫只挡页面，挡不住直接 curl 接口。

    Args:
        request: 旅行请求参数
        current_user: 由 Bearer token 解析出的当前用户

    Returns:
        旅行计划响应
    """
    family_id = family_service.family_scope(current_user)
    print(f"\n{'='*60}")
    print(f"📥 收到旅行规划请求:")
    print(f"   用户: {current_user.get('username')} (id={current_user.get('id')}) · 家庭 {family_id}")
    print(f"   城市: {request.city}")
    print(f"   日期: {request.start_date} - {request.end_date}")
    print(f"   天数: {request.travel_days}")
    print(f"{'='*60}\n")

    # 1) 先查缓存：同一个家庭、同一城市、同一日期范围、参数一致就直接返回，
    #    不再调用 agent（这是全项目最贵的操作，省一次就是省几十秒 + 一堆 token）
    if not request.force:
        try:
            cached = await run_in_threadpool(trip_service.lookup, request, family_id)
        except Exception as exc:
            # 缓存查询失败不应该阻断生成，降级为“未命中”
            print(f"⚠️  缓存查询失败，按未命中处理: {type(exc).__name__}: {exc}")
            cached = None
        if cached:
            await run_in_threadpool(trip_service.touch, cached["id"])
            print(f"⚡ 命中缓存 trip #{cached['id']}（家庭 {family_id}），跳过 agent\n")
            return TripPlanResponse(
                success=True,
                message="命中历史方案，已直接返回",
                data=cached["plan"],
                from_cache=True,
                trip_id=cached["id"],
                cached_at=cached["updated_at"],
            )

    try:
        # 2) 未命中（或 force=True）：调用该家庭自己的 agent
        #    模型按家庭配置，所以 agent 也要按家庭取；没配置就明确告诉用户去配
        print("🔄 未命中缓存，装配该家庭的 agent...")
        try:
            agent = await run_in_threadpool(get_trip_planner_agent, family_id)
        except llm_config_service.LlmNotConfigured as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from None
        except llm_config_service.LlmConfigError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from None

        print("🚀 开始生成旅行计划...")
        started = time.perf_counter()
        # plan_trip 是纯同步的重活（LLM + MCP，几十秒起步），
        # 直接 await 会占住事件循环，导致同一进程里其它请求（健康检查、图片）全排队
        trip_plan = await run_in_threadpool(agent.plan_trip, request)
        elapsed = time.perf_counter() - started
        print(f"✅ 旅行计划生成成功，耗时 {elapsed:.1f}s")

        # 3) 落库：同一家庭+城市+日期只保留一份最新方案，供后续复用与历史查看
        try:
            saved = await run_in_threadpool(
                trip_service.save, request, trip_plan, family_id, current_user["id"]
            )
            trip_id = saved["id"]
            cached_at = saved["updated_at"]
            print(f"💾 已落库 trip #{trip_id}（家庭 {family_id}）\n")
        except Exception as exc:
            # 落库失败不影响用户拿到结果，只是下次无法复用
            print(f"⚠️  行程落库失败（不影响本次返回）: {type(exc).__name__}: {exc}")
            trip_id = None
            cached_at = None

        return TripPlanResponse(
            success=True,
            message="旅行计划生成成功" + ("（已强制刷新）" if request.force else ""),
            data=trip_plan,
            from_cache=False,
            trip_id=trip_id,
            cached_at=cached_at,
        )

    except HTTPException:
        # 上面主动抛的 400（比如未配置模型）原样返回，
        # 不能被下面的兜底 except 改写成 500
        raise
    except Exception as e:
        print(f"❌ 生成旅行计划失败: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"生成旅行计划失败: {str(e)}"
        )


@router.get(
    "/history",
    response_model=TripHistoryResponse,
    summary="行程历史",
    description="当前家庭共享的行程列表，按更新时间倒序"
)
async def list_history(
    limit: int = 50,
    offset: int = 0,
    current_user: dict = Depends(get_current_user),
):
    family_id = family_service.family_scope(current_user)
    items = await run_in_threadpool(
        trip_service.list_trips, family_id, min(max(limit, 1), 100), max(offset, 0)
    )
    return TripHistoryResponse(success=True, items=items)


@router.get(
    "/health",
    summary="健康检查",
    description="检查旅行规划服务是否正常"
)
async def health_check():
    """健康检查：只看共享的高德 MCP 是否可用。

    不再检查"某个 agent 是否存在"——模型是每个家庭自己的，
    服务端手里没有统一实例，硬查只会一直 503。
    """
    try:
        from ...agents.trip_planner_agent import get_amap_tool

        tool = await run_in_threadpool(get_amap_tool)
        expanded = tool.get_expanded_tools() or []

        return {
            "status": "healthy",
            "service": "trip-planner",
            "amap_mcp": "ready",
            "amap_tools": len(expanded),
            "llm": "每个家庭自行配置",
        }
    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail=f"服务不可用: {str(e)}"
        )


@router.get(
    "/{trip_id}",
    response_model=TripPlanResponse,
    summary="历史行程详情",
    description="按ID读取行程，仅限当前家庭成员"
)
async def read_trip(
    trip_id: int,
    current_user: dict = Depends(get_current_user),
):
    family_id = family_service.family_scope(current_user)
    record = await run_in_threadpool(trip_service.get_by_id, trip_id, family_id)
    if record is None:
        raise HTTPException(status_code=404, detail="行程不存在或无权访问")
    return TripPlanResponse(
        success=True,
        message="历史行程",
        data=record["plan"],
        from_cache=True,
        trip_id=record["id"],
        cached_at=record["updated_at"],
    )


@router.delete(
    "/{trip_id}",
    summary="删除行程",
    description="仅家庭成员可删除本家庭的行程记录"
)
async def delete_trip(
    trip_id: int,
    current_user: dict = Depends(get_current_user),
):
    family_id = family_service.family_scope(current_user)
    deleted = await run_in_threadpool(trip_service.delete_by_id, trip_id, family_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="行程不存在或无权访问")
    return {"success": True, "message": "已删除"}


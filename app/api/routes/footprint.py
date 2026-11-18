"""足迹 API

足迹是家庭共享数据，所有读写都按 family_id 隔离。
成员筛选放在前端做：一个人的足迹最多几百条，本地过滤切换零延迟，
后端只负责返回全量数据和成员列表。

城市解析（/resolve、/suggest）单独开接口，是为了录入时能立刻告诉用户
「苏州」会被记成「江苏 · 苏州」——省份归属错了，地图点亮和统计就全错了。
"""

from fastapi import APIRouter, Depends, HTTPException
from starlette.concurrency import run_in_threadpool

from ..deps import get_current_user
from ...models.schedmas import (
    FootprintCreate,
    FootprintUpdate,
    FootprintItem,
    FootprintListResponse,
    FootprintMutationResponse,
    FootprintMember,
    FootprintPoiResponse,
    FootprintResolveResponse,
    FootprintSuggestResponse,
    FootprintRegionsResponse,
    FootprintShapeResponse,
)
from ...services import family_service, footprint_service

router = APIRouter(prefix="/footprint", tags=["足迹"])


def _snapshot(family_id: int) -> dict:
    """一次取全量 + 统计 + 年度分组。同步函数，调用方负责丢线程池。"""
    items = footprint_service.list_all(family_id)
    return {
        "items": items,
        "stats": footprint_service.build_stats(items),
        "years": footprint_service.build_years(items),
    }


def _members(family_id: int) -> list[FootprintMember]:
    rows = family_service.list_members(family_id)
    return [
        FootprintMember(id=r["id"], display_name=r["display_name"] or r["username"])
        for r in rows
    ]


def _clean_member_ids(family_id: int, raw: list[int]) -> list[int]:
    """只认本家庭成员，防止把别人的 user_id 塞进来污染「谁去过」"""
    valid = {m.id for m in _members(family_id)}
    return [int(i) for i in (raw or []) if int(i) in valid]


@router.get(
    "",
    response_model=FootprintListResponse,
    summary="足迹总览",
    description="当前家庭的全部足迹 + 统计 + 年度分组 + 成员列表",
)
async def list_footprints(current_user: dict = Depends(get_current_user)):
    family_id = family_service.family_scope(current_user)
    snapshot = await run_in_threadpool(_snapshot, family_id)
    members = await run_in_threadpool(_members, family_id)
    return FootprintListResponse(success=True, members=members, **snapshot)


@router.get(
    "/regions",
    response_model=FootprintRegionsResponse,
    summary="行政区数据",
    description="省市两级列表（含 adcode 与坐标）；首次从高德拉取后落盘，30 天内直接用缓存",
)
async def list_regions():
    provinces = await run_in_threadpool(footprint_service.build_regions)
    return FootprintRegionsResponse(success=True, provinces=provinces)


@router.get(
    "/province-shape",
    response_model=FootprintShapeResponse,
    summary="省份边界",
    description="画「点亮省份」色块用的省界坐标，落在后端缓存里，同一省份半年只向高德查一次。"
                "JSAPI 的 DistrictLayer 需要安全密钥，这里走后端 Web 服务 Key 才稳定",
)
async def province_shape(
    adcode: str = "",
    current_user: dict = Depends(get_current_user),
):
    try:
        rings = await run_in_threadpool(footprint_service.province_shape, adcode)
    except footprint_service.FootprintError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None
    return FootprintShapeResponse(success=True, adcode=adcode, rings=rings)


@router.post(
    "",
    response_model=FootprintMutationResponse,
    summary="录入足迹",
    description="手动记录一次到访；同城同日范围重复会明确报错",
)
async def create_footprint(
    payload: FootprintCreate,
    current_user: dict = Depends(get_current_user),
):
    family_id = family_service.family_scope(current_user)
    member_ids = await run_in_threadpool(_clean_member_ids, family_id, payload.member_ids)
    checkins = [c.model_dump() for c in payload.checkins]
    try:
        item = await run_in_threadpool(
            footprint_service.create,
            family_id,
            current_user["id"],
            payload.city,
            payload.start_date,
            payload.end_date or "",
            payload.note,
            member_ids,
            checkins,
        )
    except footprint_service.FootprintError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None

    snapshot = await run_in_threadpool(_snapshot, family_id)
    return FootprintMutationResponse(
        success=True,
        message=f"已记录 {item['display_city']}",
        item=FootprintItem(**item),
        stats=snapshot["stats"],
        years=snapshot["years"],
    )


@router.put(
    "/{footprint_id}",
    response_model=FootprintMutationResponse,
    summary="修改足迹",
    description="只能改日期、备注和参与成员；换城市请删掉重录",
)
async def update_footprint(
    footprint_id: int,
    payload: FootprintUpdate,
    current_user: dict = Depends(get_current_user),
):
    family_id = family_service.family_scope(current_user)
    member_ids = (
        await run_in_threadpool(_clean_member_ids, family_id, payload.member_ids)
        if payload.member_ids is not None else None
    )
    checkins = (
        [c.model_dump() for c in payload.checkins]
        if payload.checkins is not None else None
    )
    try:
        item = await run_in_threadpool(
            footprint_service.update,
            footprint_id, family_id,
            payload.start_date, payload.end_date, payload.note, member_ids, checkins,
        )
    except footprint_service.FootprintError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None
    if item is None:
        raise HTTPException(status_code=404, detail="足迹不存在或无权修改")

    snapshot = await run_in_threadpool(_snapshot, family_id)
    return FootprintMutationResponse(
        success=True,
        message="已更新",
        item=FootprintItem(**item),
        stats=snapshot["stats"],
        years=snapshot["years"],
    )


@router.delete(
    "/{footprint_id}",
    summary="删除足迹",
    description="仅本家庭成员可删除",
)
async def delete_footprint(
    footprint_id: int,
    current_user: dict = Depends(get_current_user),
):
    family_id = family_service.family_scope(current_user)
    deleted = await run_in_threadpool(footprint_service.delete, footprint_id, family_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="足迹不存在或无权删除")
    return {"success": True, "message": "已删除"}


@router.get(
    "/poi",
    response_model=FootprintPoiResponse,
    summary="搜索景点",
    description="按名称搜高德 POI，返回 GCJ-02 坐标；打卡录入用它定位景点，"
                "存下经纬度后点城市就能画出市内轨迹。查不到返回空列表，不报错",
)
async def search_poi(
    keyword: str = "",
    city: str = "",
    current_user: dict = Depends(get_current_user),
):
    items = await run_in_threadpool(footprint_service.search_poi, keyword, city)
    return FootprintPoiResponse(
        success=True,
        message=f"找到 {len(items)} 个地点" if items else "没搜到这个地点，可以直接手填名称",
        items=items,
    )


@router.get(
    "/resolve",
    response_model=FootprintResolveResponse,
    summary="城市解析预览",
    description="录入前确认城市会被归到哪个省；查不到坐标也返回成功，只是 lng/lat 为空",
)
async def resolve_city(name: str = ""):
    try:
        info = await run_in_threadpool(footprint_service.resolve_city, name)
    except footprint_service.FootprintError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None

    message = f"{info['province']} · {info['name']}" if info["province"] else "没查到省份，只能按城市记录"
    if info["lng"] is None and info["province"]:
        message += "（缺坐标，地图上不显示点位）"
    return FootprintResolveResponse(
        success=True,
        message=message,
        name=info["name"],
        province=info["province"],
        adcode=info["adcode"],
        lng=info["lng"],
        lat=info["lat"],
    )


@router.get(
    "/suggest",
    response_model=FootprintSuggestResponse,
    summary="城市联想",
    description="纯本地匹配内置城市表，敲字时零网络请求",
)
async def suggest_city(keyword: str = ""):
    hits = await run_in_threadpool(footprint_service.guess_city_name, keyword)
    return FootprintSuggestResponse(success=True, items=hits)

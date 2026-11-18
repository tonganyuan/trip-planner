"""行程缓存/历史服务

一个家庭 + 城市 + 日期范围只保留一份最新方案：
- 请求参数完全一致 → 命中缓存，零 agent 调用
- 参数变了（换了交通/住宿/偏好）→ 重新生成并覆盖
- force=True → 跳过缓存重新生成

所有数据按 family_id 隔离，家庭成员共享同一份行程历史。
"""

import json
import sqlite3
from typing import Optional

from app.services.db import db_conn
from app.models.schedmas import TripPlan


class TripStoreError(Exception):
    """行程存储失败"""


def _now_iso() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _request_fingerprint(request) -> str:
    """把影响生成结果的参数序列化成稳定的指纹，空格差异不影响判断"""
    payload = {
        "city": request.city.strip(),
        "start_date": request.start_date.strip(),
        "end_date": request.end_date.strip(),
        "travel_days": request.travel_days,
        "transportation": (request.transportation or "").strip(),
        "accommodation": (request.accommodation or "").strip(),
        "preferences": sorted((request.preferences or [])),
        "free_text_input": (request.free_text_input or "").strip(),
    }
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def lookup(request, family_id: int) -> Optional[dict]:
    """查缓存。命中返回含 plan 的记录；仅当请求参数一致时才算命中。"""
    fingerprint = _request_fingerprint(request)
    with db_conn() as conn:
        row = conn.execute(
            "SELECT * FROM trips WHERE family_id = ? AND city = ? AND start_date = ? AND end_date = ?",
            (family_id, request.city.strip(), request.start_date.strip(), request.end_date.strip()),
        ).fetchone()
        if row is None:
            return None
        # 参数不同 → 视为未命中，调用方会重新生成并覆盖
        if row["request_json"] != fingerprint:
            return None
    return _row_to_record(row)


def save(request, plan: TripPlan, family_id: int, user_id: int) -> dict:
    """写入或覆盖缓存（唯一键冲突时更新）"""
    now = _now_iso()
    fingerprint = _request_fingerprint(request)
    plan_json = plan.model_dump_json()
    with db_conn() as conn:
        conn.execute(
            """INSERT INTO trips
               (family_id, created_by, city, start_date, end_date,
                request_json, plan_json, created_at, updated_at, hit_count)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
               ON CONFLICT(family_id, city, start_date, end_date) DO UPDATE SET
                 created_by = excluded.created_by,
                 request_json = excluded.request_json,
                 plan_json = excluded.plan_json,
                 updated_at = excluded.updated_at
            """,
            (
                family_id, user_id,
                request.city.strip(), request.start_date.strip(), request.end_date.strip(),
                fingerprint, plan_json, now, now,
            ),
        )
        row = conn.execute(
            "SELECT * FROM trips WHERE family_id = ? AND city = ? AND start_date = ? AND end_date = ?",
            (family_id, request.city.strip(), request.start_date.strip(), request.end_date.strip()),
        ).fetchone()
    return _row_to_record(row)


def touch(trip_id: int) -> None:
    """命中计数 +1，纯粹用于统计，失败不影响主流程"""
    try:
        with db_conn() as conn:
            conn.execute("UPDATE trips SET hit_count = hit_count + 1 WHERE id = ?", (trip_id,))
    except Exception:
        pass


def _row_to_record(row: sqlite3.Row) -> dict:
    return {
        "id": row["id"],
        "family_id": row["family_id"],
        "created_by": row["created_by"],
        "city": row["city"],
        "start_date": row["start_date"],
        "end_date": row["end_date"],
        "plan": TripPlan.model_validate_json(row["plan_json"]),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "hit_count": row["hit_count"],
    }


def list_trips(family_id: int, limit: int = 50, offset: int = 0) -> list[dict]:
    """家庭行程历史，按更新时间倒序。列表不返回完整 plan，减小体积。"""
    with db_conn() as conn:
        rows = conn.execute(
            """SELECT id, city, start_date, end_date, created_by,
                      created_at, updated_at, hit_count
               FROM trips WHERE family_id = ?
               ORDER BY updated_at DESC, id DESC
               LIMIT ? OFFSET ?""",
            (family_id, limit, offset),
        ).fetchall()
    return [dict(row) for row in rows]


def get_by_id(trip_id: int, family_id: int) -> Optional[dict]:
    """按 id 读取，必须限定 family_id，防止跨家庭越权"""
    with db_conn() as conn:
        row = conn.execute(
            "SELECT * FROM trips WHERE id = ? AND family_id = ?", (trip_id, family_id)
        ).fetchone()
    return _row_to_record(row) if row else None


def delete_by_id(trip_id: int, family_id: int) -> bool:
    with db_conn() as conn:
        cursor = conn.execute(
            "DELETE FROM trips WHERE id = ? AND family_id = ?", (trip_id, family_id)
        )
        return cursor.rowcount > 0

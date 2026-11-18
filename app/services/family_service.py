"""家庭服务：家庭成员管理与共享数据作用域

设计要点：
- 每个用户都属于一个家庭 users.family_id；注册时自动建一个单人家庭
- 家庭共同记录：足迹等数据按 family_id 存取，家庭成员看到同一份
- 添加成员只能创建"全新账号"并绑定当前家庭，不把已有独立账号拉进来
  （避免把别人自己的家庭数据带过来，也避免把账号从一个家庭抢走）
- 权限：户主可移除成员 / 改名；普通成员可添加成员
"""

import sqlite3
from typing import Optional

from app.services.auth_service import AuthError, _now_iso, create_user
from app.services.db import db_conn


class FamilyError(Exception):
    """家庭操作失败，message 直接返回前端"""


def get_family(family_id: int) -> Optional[dict]:
    with db_conn() as conn:
        row = conn.execute("SELECT * FROM families WHERE id = ?", (family_id,)).fetchone()
    return dict(row) if row else None


def is_owner(user: dict) -> bool:
    family = get_family(user["family_id"])
    return bool(family and family["owner_id"] == user["id"])


def list_members(family_id: int) -> list[dict]:
    """成员列表，按户主优先 + 加入时间排序。绝不带密码哈希。"""
    with db_conn() as conn:
        family = conn.execute("SELECT owner_id FROM families WHERE id = ?", (family_id,)).fetchone()
        if family is None:
            raise FamilyError("家庭不存在")
        owner_id = family["owner_id"]
        rows = conn.execute(
            "SELECT id, username, display_name, last_login_at, created_at "
            "FROM users WHERE family_id = ? "
            "ORDER BY (id = ?) DESC, created_at ASC, id ASC",
            (family_id, owner_id),
        ).fetchall()
    result = []
    for row in rows:
        item = dict(row)
        item["display_name"] = item["display_name"] or item["username"]
        item["is_owner"] = item["id"] == owner_id
        result.append(item)
    return result


def get_family_info(user: dict) -> dict:
    """返回家庭信息 + 成员列表，所有家庭成员都可查看"""
    family = get_family(user["family_id"])
    if family is None:
        raise FamilyError("家庭不存在")
    return {
        "id": family["id"],
        "name": family["name"],
        "owner_id": family["owner_id"],
        "is_owner": family["owner_id"] == user["id"],
        "member_count": len(list_members(family["id"])),
        "members": list_members(family["id"]),
    }


def add_member(actor: dict, username: str, password: str, display_name: str = "") -> dict:
    """在当前家庭下创建一个新账号。任何家庭成员都可添加。"""
    try:
        user = create_user(
            username=username,
            password=password,
            display_name=display_name,
            family_id=actor["family_id"],
        )
    except AuthError as exc:
        raise FamilyError(str(exc)) from None
    return {
        "id": user["id"],
        "username": user["username"],
        "display_name": user["display_name"],
        "is_owner": False,
        "created_at": user["created_at"],
        "last_login_at": None,
    }


def remove_member(actor: dict, member_id: int) -> None:
    """户主移除成员。不允许移除户主自己，也不允许跨家庭操作。"""
    family = get_family(actor["family_id"])
    if family is None:
        raise FamilyError("家庭不存在")
    if family["owner_id"] != actor["id"]:
        raise FamilyError("只有户主可以移除成员")
    if member_id == actor["id"]:
        raise FamilyError("不能移除户主本人")

    with db_conn() as conn:
        target = conn.execute(
            "SELECT id, family_id FROM users WHERE id = ?", (member_id,)
        ).fetchone()
        if target is None:
            raise FamilyError("成员不存在")
        if target["family_id"] != actor["family_id"]:
            raise FamilyError("只能移除本家庭成员")

        # 不删账号，改为给该成员新建一个单人家庭：
        # 保留其账号、历史记录归属，仍能正常登录，只是不再共享数据
        now = _now_iso()
        cursor = conn.execute(
            "INSERT INTO families (name, owner_id, created_at) VALUES (?, 0, ?)",
            (f"{(target['id'])}的个人家庭", now),
        )
        conn.execute(
            "UPDATE users SET family_id = ? WHERE id = ?", (cursor.lastrowid, member_id)
        )
        conn.execute(
            "UPDATE families SET owner_id = ? WHERE id = ?", (member_id, cursor.lastrowid)
        )


def rename_family(actor: dict, name: str) -> dict:
    """仅户主可改家庭名称"""
    family = get_family(actor["family_id"])
    if family is None:
        raise FamilyError("家庭不存在")
    if family["owner_id"] != actor["id"]:
        raise FamilyError("只有户主可以修改家庭名称")
    clean = name.strip()
    if not clean:
        raise FamilyError("家庭名称不能为空")
    with db_conn() as conn:
        conn.execute("UPDATE families SET name = ? WHERE id = ?", (clean[:32], actor["family_id"]))
    return {**family, "name": clean[:32], "is_owner": True}


def family_scope(user: dict) -> int:
    """共享数据作用域：足迹等表用这个 id 过滤，家庭成员即可看到同一份数据"""
    return user["family_id"]

"""SQLite 访问层（标准库，无 ORM）

部署形态是单进程 + 单 worker + nginx 反代，SQLite(开 WAL) 完全够用。
不做连接池：每次操作新开连接、用完即关，避免连接跨线程共享
(sqlite3 的连接默认不允许跨线程，FastAPI 的线程池会换线程)。
"""

import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from app.config import get_settings

# 建表只做一次；多线程同时触发时用锁兜住
_schema_lock = threading.Lock()
_schema_ready = False

SCHEMA = """
CREATE TABLE IF NOT EXISTS families (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    name       TEXT NOT NULL DEFAULT '',
    owner_id   INTEGER NOT NULL DEFAULT 0,  -- 户主 user_id，建用户时回填
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    username      TEXT NOT NULL UNIQUE,   -- 归一化后的用户名或邮箱(小写)
    display_name  TEXT NOT NULL DEFAULT '',
    password_hash TEXT NOT NULL,
    family_id     INTEGER NOT NULL DEFAULT 0,  -- 所属家庭；足迹等共享数据按此隔离
    created_at    TEXT NOT NULL,
    last_login_at TEXT
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_users_username ON users(username);

-- 行程缓存/历史：同一家庭 + 城市 + 日期范围只保留一份最新方案
CREATE TABLE IF NOT EXISTS trips (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    family_id   INTEGER NOT NULL,
    created_by  INTEGER NOT NULL,        -- 生成者 user_id
    city        TEXT NOT NULL,
    start_date  TEXT NOT NULL,
    end_date    TEXT NOT NULL,
    request_json TEXT NOT NULL,          -- 归一化后的请求参数，用于判断是否可复用
    plan_json   TEXT NOT NULL,           -- 完整 TripPlan JSON
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL,
    hit_count   INTEGER NOT NULL DEFAULT 0,
    UNIQUE(family_id, city, start_date, end_date)
);

CREATE INDEX IF NOT EXISTS idx_trips_family ON trips(family_id, updated_at DESC);

-- 每个家庭自己的 LLM 配置：key 只存密文，明文只在内存里出现
CREATE TABLE IF NOT EXISTS family_llm_configs (
    family_id      INTEGER PRIMARY KEY,          -- 一个家庭一份配置
    provider       TEXT NOT NULL DEFAULT 'custom', -- 预设标识，仅用于前端回显
    base_url       TEXT NOT NULL,
    model          TEXT NOT NULL,
    api_key_cipher TEXT NOT NULL,                -- AES-GCM 密文（见 services/crypto.py）
    api_key_hint   TEXT NOT NULL DEFAULT '',     -- 形如 sk-…a1b2，仅用于界面回显
    temperature    REAL NOT NULL DEFAULT 0.7,
    updated_by     INTEGER NOT NULL DEFAULT 0,
    updated_at     TEXT NOT NULL,
    verified_at    TEXT                          -- 最近一次测试连通成功时间
);

-- 城市档案：把用户手输的城市名归一化到行政区划，顺便缓存中心坐标。
-- 高德查一次就落库，之后同城录入不再发请求；查不到时坐标留空，
-- 城市仍可入库（列表和统计照常，只是地图上少一个点）。
CREATE TABLE IF NOT EXISTS city_registry (
    name        TEXT PRIMARY KEY,          -- 归一化名（去「市」等后缀）
    adcode      TEXT NOT NULL DEFAULT '',
    province    TEXT NOT NULL DEFAULT '',  -- 省级短名，如「江苏」
    lng         REAL,
    lat         REAL,
    source      TEXT NOT NULL DEFAULT '',  -- builtin / amap / none
    resolved_at TEXT NOT NULL
);

-- 家庭的华为云 OBS 配置：打卡图片存到用户自己的桶里，服务端不托管任何文件。
-- AK/SK 与 LLM Key 同等对待，只存 AES-GCM 密文（见 services/crypto.py），
-- 接口只回显形如 ``AKLT…a1b2`` 的提示串。
CREATE TABLE IF NOT EXISTS family_oss_configs (
    family_id     INTEGER PRIMARY KEY,
    provider      TEXT NOT NULL DEFAULT 'huawei',  -- 预留，目前只支持华为云 OBS
    endpoint      TEXT NOT NULL,                   -- obs.cn-east-3.myhuaweicloud.com
    region        TEXT NOT NULL DEFAULT '',
    bucket        TEXT NOT NULL,
    ak_cipher     TEXT NOT NULL,
    ak_hint       TEXT NOT NULL DEFAULT '',
    sk_cipher     TEXT NOT NULL,
    sk_hint       TEXT NOT NULL DEFAULT '',
    prefix        TEXT NOT NULL DEFAULT 'footprint', -- 对象键前缀
    public_domain TEXT NOT NULL DEFAULT '',          -- 自定义 CDN 域名；空则用 bucket.endpoint
    updated_by    INTEGER NOT NULL DEFAULT 0,
    updated_at    TEXT NOT NULL,
    verified_at   TEXT
);

-- 足迹：一条 = 一次到访某个城市。
-- 与行程规划完全解耦：不引用 trips，行程删了足迹也在。
-- member_ids 存「这次谁去了」，逗号分隔的 user_id；为空表示只有录入者本人。
CREATE TABLE IF NOT EXISTS footprints (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    family_id    INTEGER NOT NULL,
    city         TEXT NOT NULL,                -- 归一化城市名，统计按此去重
    display_city TEXT NOT NULL DEFAULT '',     -- 用户输入的原始写法，仅用于展示
    province     TEXT NOT NULL DEFAULT '',
    adcode       TEXT NOT NULL DEFAULT '',
    lng          REAL,
    lat          REAL,
    start_date   TEXT NOT NULL DEFAULT '',     -- YYYY-MM-DD
    end_date     TEXT NOT NULL DEFAULT '',
    note         TEXT NOT NULL DEFAULT '',
    checkins     TEXT NOT NULL DEFAULT '[]',   -- 打卡 JSON：[{spot, time, images:[url]}]
    member_ids   TEXT NOT NULL DEFAULT '',
    created_by   INTEGER NOT NULL DEFAULT 0,
    created_at   TEXT NOT NULL,
    updated_at   TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_footprints_family ON footprints(family_id, start_date DESC);

-- 同一家庭、同一城市、同一天范围只记一次，防止重复提交
CREATE UNIQUE INDEX IF NOT EXISTS idx_footprints_unique
    ON footprints(family_id, city, start_date, end_date);
"""


def _migrate_families(conn: sqlite3.Connection) -> None:
    """老库升级：给没有家庭的账号各建一个单人家庭。幂等，可重复执行。"""
    columns = {row["name"] for row in conn.execute("PRAGMA table_info(users)")}
    if "family_id" not in columns:
        conn.execute("ALTER TABLE users ADD COLUMN family_id INTEGER NOT NULL DEFAULT 0")

    rows = conn.execute(
        "SELECT id, username, display_name, created_at "
        "FROM users WHERE family_id = 0 OR family_id IS NULL"
    ).fetchall()
    for row in rows:
        name = f"{row['display_name'] or row['username']}的家庭"[:32]
        cursor = conn.execute(
            "INSERT INTO families (name, owner_id, created_at) VALUES (?, 0, ?)",
            (name, row["created_at"]),
        )
        family_id = cursor.lastrowid
        conn.execute("UPDATE users SET family_id = ? WHERE id = ?", (family_id, row["id"]))
        conn.execute("UPDATE families SET owner_id = ? WHERE id = ?", (row["id"], family_id))

    # 兜底：owner_id 还是 0 的孤儿家庭（正常流程不会出现，修好以免卡住权限判断）
    orphans = conn.execute(
        "SELECT f.id, u.id AS user_id FROM families f "
        "JOIN users u ON u.family_id = f.id "
        "WHERE f.owner_id = 0 LIMIT 1"
    ).fetchall()
    for orphan in orphans:
        conn.execute(
            "UPDATE families SET owner_id = ? WHERE id = ?",
            (orphan["user_id"], orphan["id"]),
        )

    # 索引必须在 family_id 列存在之后才能建（老库是 ALTER 加的列）
    conn.execute("CREATE INDEX IF NOT EXISTS idx_users_family ON users(family_id)")


def get_db_file() -> Path:
    """解析数据库绝对路径，并确保父目录存在"""
    settings = get_settings()
    path = Path(settings.db_path)
    if not path.is_absolute():
        # app/services/db.py -> 项目根
        path = Path(__file__).resolve().parents[2] / path
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(str(get_db_file()), timeout=15)
    conn.row_factory = sqlite3.Row
    # WAL：读写不互相阻塞，崩溃后恢复更稳
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


@contextmanager
def db_conn() -> Iterator[sqlite3.Connection]:
    """短生命周期连接，正常退出自动提交，异常自动回滚"""
    conn = connect()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _migrate_footprints(conn: sqlite3.Connection) -> None:
    """老库升级：补打卡字段。幂等，可重复执行。"""
    columns = {row["name"] for row in conn.execute("PRAGMA table_info(footprints)")}
    if "checkins" not in columns:
        conn.execute(
            "ALTER TABLE footprints ADD COLUMN checkins TEXT NOT NULL DEFAULT '[]'"
        )


def init_db() -> None:
    """建表（幂等），应用启动时调用"""
    global _schema_ready
    with _schema_lock:
        if _schema_ready:
            return
        with db_conn() as conn:
            conn.executescript(SCHEMA)
            _migrate_families(conn)
            _migrate_footprints(conn)
        _schema_ready = True

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
CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    username      TEXT NOT NULL UNIQUE,   -- 归一化后的用户名或邮箱(小写)
    display_name  TEXT NOT NULL DEFAULT '',
    password_hash TEXT NOT NULL,
    created_at    TEXT NOT NULL,
    last_login_at TEXT
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_users_username ON users(username);
"""


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


def init_db() -> None:
    """建表（幂等），应用启动时调用"""
    global _schema_ready
    with _schema_lock:
        if _schema_ready:
            return
        with db_conn() as conn:
            conn.executescript(SCHEMA)
        _schema_ready = True

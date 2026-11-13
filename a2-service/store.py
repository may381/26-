# -*- coding: utf-8 -*-
"""
store.py —— 调用收据（invocationId）持久化（方案 B 核心硬要求）
================================================================
《Agent 统一交互协议 v3.0》要求：A2 必须能按 invocationId 找回已完成结果单，
用于 P2 超时后的任务恢复与取消。因此回执【必须落盘 sqlite】，不能只放内存变量；
否则进程重启/崩溃后，P2 查 invocationId 会 404，恢复/取消机制失效。

实现要点：
  - 使用 Python 标准库 sqlite3（零额外依赖）。
  - 单文件数据库（a2_receipts.db），线程安全（每次操作新建连接 + 进程级锁）。
  - receipts 表：invocation_id(PK) / sheet(JSON) / status / created_at / updated_at。
  - cancelled 表：记录被取消的 invocation_id，用于「已取消则拒收」。
"""
import json
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from settings import settings

_lock = threading.Lock()


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def _new_id(prefix: str) -> str:
    return prefix + uuid.uuid4().hex[:12]


def _conn() -> sqlite3.Connection:
    # check_same_thread=False：FastAPI/uvicorn 多线程下共享模块级连接会报线程错，故每次新建
    conn = sqlite3.connect(settings.DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """建表（幂等，重复调用安全）。服务启动时调用一次。"""
    with _lock, _conn() as c:
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS receipts (
                invocation_id TEXT PRIMARY KEY,
                sheet         TEXT NOT NULL,
                status        TEXT NOT NULL DEFAULT 'FINISHED',
                created_at    TEXT NOT NULL,
                updated_at    TEXT NOT NULL
            )
            """
        )
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS cancelled (
                invocation_id TEXT PRIMARY KEY,
                cancelled_at  TEXT NOT NULL
            )
            """
        )
        # —— 健康提醒（健康提醒能力落库；确认前 status=PENDING，确认后 CONFIRMED）——
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS reminders (
                id         TEXT PRIMARY KEY,
                user_id   TEXT NOT NULL,
                rtype     TEXT NOT NULL DEFAULT 'GENERIC',
                content   TEXT NOT NULL,
                remind_at TEXT,
                status    TEXT NOT NULL DEFAULT 'PENDING',
                created_at TEXT NOT NULL
            )
            """
        )
        # —— 长期记忆条目（记忆反馈能力落库；确认前 confirmed=0，契约 4.4 要求确认后才写长期记忆）——
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS memory_entries (
                memory_id  TEXT PRIMARY KEY,
                user_id   TEXT NOT NULL,
                type      TEXT NOT NULL,
                content   TEXT NOT NULL,
                source    TEXT,
                confirmed INTEGER NOT NULL DEFAULT 0,
                expire_at TEXT,
                created_at TEXT NOT NULL
            )
            """
        )


def save_receipt(invocation_id: str, sheet: dict) -> None:
    """保存/覆盖一条回执。幂等（同一 invocation 重复保存只更新）。"""
    now = _now()
    with _lock, _conn() as c:
        cur = c.execute("SELECT 1 FROM receipts WHERE invocation_id = ?", (invocation_id,))
        exists = cur.fetchone()
        if exists:
            c.execute(
                "UPDATE receipts SET sheet = ?, updated_at = ? WHERE invocation_id = ?",
                (json.dumps(sheet, ensure_ascii=False), now, invocation_id),
            )
        else:
            c.execute(
                "INSERT INTO receipts (invocation_id, sheet, status, created_at, updated_at) VALUES (?, ?, 'FINISHED', ?, ?)",
                (invocation_id, json.dumps(sheet, ensure_ascii=False), now, now),
            )


def get_receipt(invocation_id: str) -> Optional[dict]:
    """按 invocationId 找回执；不存在返回 None。"""
    with _lock, _conn() as c:
        row = c.execute(
            "SELECT sheet FROM receipts WHERE invocation_id = ?", (invocation_id,)
        ).fetchone()
    if not row:
        return None
    import json
    return json.loads(row["sheet"])


def mark_cancelled(invocation_id: str) -> None:
    with _lock, _conn() as c:
        c.execute(
            "INSERT OR IGNORE INTO cancelled (invocation_id, cancelled_at) VALUES (?, ?)",
            (invocation_id, _now()),
        )


def is_cancelled(invocation_id: str) -> bool:
    with _lock, _conn() as c:
        row = c.execute(
            "SELECT 1 FROM cancelled WHERE invocation_id = ?", (invocation_id,)
        ).fetchone()
    return row is not None


# ---------------------------------------------------------------------------
# 健康提醒（健康提醒能力）
# ---------------------------------------------------------------------------
def save_reminder(user_id: str, rtype: str, content: str,
                  remind_at: Optional[str] = None, status: str = "PENDING") -> str:
    """写入一条提醒；返回提醒 id。幂等由调用方保证（同一次派活只写一条）。"""
    rid = _new_id("R")
    now = _now()
    with _lock, _conn() as c:
        c.execute(
            """INSERT INTO reminders (id, user_id, rtype, content, remind_at, status, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (rid, user_id, rtype, content, remind_at, status, now),
        )
    return rid


def get_pending_reminders(user_id: Optional[str] = None) -> List[Dict[str, Any]]:
    with _lock, _conn() as c:
        if user_id:
            rows = c.execute(
                "SELECT * FROM reminders WHERE user_id = ? ORDER BY created_at DESC",
                (user_id,),
            ).fetchall()
        else:
            rows = c.execute("SELECT * FROM reminders ORDER BY created_at DESC").fetchall()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# 长期记忆（记忆反馈能力；契约 4.4：确认后才允许长期保存）
# ---------------------------------------------------------------------------
def save_memory(user_id: str, mtype: str, content: str, source: str = "chat",
                confirmed: bool = False, expire_at: Optional[str] = None) -> str:
    """写入一条记忆条目；返回 memory_id。confirmed 默认 False（待老人确认）。"""
    mid = _new_id("M")
    now = _now()
    with _lock, _conn() as c:
        c.execute(
            """INSERT INTO memory_entries
               (memory_id, user_id, type, content, source, confirmed, expire_at, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (mid, user_id, mtype, content, source, 1 if confirmed else 0, expire_at, now),
        )
    return mid


def get_memory_entries(user_id: Optional[str] = None,
                       confirmed_only: bool = False) -> List[Dict[str, Any]]:
    with _lock, _conn() as c:
        if user_id:
            sql = "SELECT * FROM memory_entries WHERE user_id = ?"
            args = (user_id,)
        else:
            sql = "SELECT * FROM memory_entries"
            args = ()
        if confirmed_only:
            sql += " AND confirmed = 1"
        sql += " ORDER BY created_at DESC"
        rows = c.execute(sql, args).fetchall()
    return [dict(r) for r in rows]

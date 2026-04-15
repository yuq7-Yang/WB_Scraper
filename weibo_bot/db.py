from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import DB_PATH as DEFAULT_DB_PATH


DB_PATH = DEFAULT_DB_PATH


def configure(path: str) -> None:
    global DB_PATH
    DB_PATH = path


def _connect() -> sqlite3.Connection:
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def init_db() -> None:
    with _connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS leads (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_name TEXT NOT NULL,
                location TEXT,
                comment_text TEXT,
                comment_id TEXT,
                post_id TEXT,
                keyword TEXT,
                scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                status TEXT DEFAULT 'pending',
                reply_text TEXT,
                replied_at TIMESTAMP,
                UNIQUE(user_name, post_id)
            )
            """
        )
        columns = {
            row["name"]
            for row in conn.execute("PRAGMA table_info(leads)").fetchall()
        }
        if "comment_id" not in columns:
            conn.execute("ALTER TABLE leads ADD COLUMN comment_id TEXT")
        conn.commit()


def insert_lead(
    user_name: str,
    location: str | None,
    comment_text: str | None,
    post_id: str,
    keyword: str | None,
    comment_id: str | None = None,
) -> bool:
    with _connect() as conn:
        cursor = conn.execute(
            """
            INSERT OR IGNORE INTO leads
                (user_name, location, comment_text, comment_id, post_id, keyword)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (user_name, location, comment_text, comment_id, post_id, keyword),
        )
        conn.commit()
        return cursor.rowcount == 1


def get_pending_leads(limit: int = 20) -> list[dict[str, Any]]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM leads WHERE status='pending' ORDER BY scraped_at ASC LIMIT ?",
            (limit,),
        ).fetchall()
    return [dict(row) for row in rows]


def get_leads_by_ids(lead_ids: list[int]) -> list[dict[str, Any]]:
    if not lead_ids:
        return []
    placeholders = ",".join("?" for _ in lead_ids)
    with _connect() as conn:
        rows = conn.execute(
            f"SELECT * FROM leads WHERE id IN ({placeholders}) ORDER BY scraped_at ASC, id ASC",
            tuple(lead_ids),
        ).fetchall()
    by_id = {row["id"]: dict(row) for row in rows}
    return [by_id[lead_id] for lead_id in lead_ids if lead_id in by_id]


def get_all_leads() -> list[dict[str, Any]]:
    with _connect() as conn:
        rows = conn.execute("SELECT * FROM leads ORDER BY scraped_at DESC, id DESC").fetchall()
    return [dict(row) for row in rows]


def update_lead_status(lead_id: int, status: str, reply_text: str | None = None) -> None:
    replied_at = None if status == "pending" else _utc_now()
    with _connect() as conn:
        conn.execute(
            """
            UPDATE leads
            SET status = ?, reply_text = ?, replied_at = ?
            WHERE id = ?
            """,
            (status, reply_text, replied_at, lead_id),
        )
        conn.commit()

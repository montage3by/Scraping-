"""Minimal persistence for the MVP — SQLite, no external services.
One table: jobs. Each row is one quiz submission waiting to be (or already)
processed by the collector pipeline.
"""

import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path(__file__).parent / "queue.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    id TEXT PRIMARY KEY,
    restaurant_name TEXT NOT NULL,
    city TEXT NOT NULL,
    country TEXT NOT NULL,
    email TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'queued',   -- queued | running | done | failed
    platforms_json TEXT NOT NULL,            -- resolved platform plan at submit time
    error TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""


@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with get_conn() as conn:
        conn.execute(SCHEMA)


def enqueue_job(restaurant_name: str, city: str, country: str, email: str, platforms: list[dict]) -> str:
    job_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO jobs (id, restaurant_name, city, country, email, status, platforms_json, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, 'queued', ?, ?, ?)""",
            (job_id, restaurant_name, city, country, email, json.dumps(platforms), now, now),
        )
    return job_id


def get_job(job_id: str) -> dict | None:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
        return dict(row) if row else None


def next_queued_job() -> dict | None:
    """Picks the oldest queued job — this is the hook the collector worker will call."""
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM jobs WHERE status = 'queued' ORDER BY created_at ASC LIMIT 1"
        ).fetchone()
        return dict(row) if row else None


def set_job_status(job_id: str, status: str, error: str | None = None) -> None:
    now = datetime.now(timezone.utc).isoformat()
    with get_conn() as conn:
        conn.execute(
            "UPDATE jobs SET status = ?, error = ?, updated_at = ? WHERE id = ?",
            (status, error, now, job_id),
        )

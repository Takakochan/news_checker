from __future__ import annotations

import json
import os
import sqlite3
import uuid
from pathlib import Path
from typing import Optional

DB_PATH = os.environ.get("DB_PATH") or str(Path(__file__).parent.parent / "data" / "results.sqlite3")


def _connect() -> sqlite3.Connection:
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS results (
            id TEXT PRIMARY KEY,
            created_at TEXT NOT NULL,
            data TEXT NOT NULL
        )
        """
    )
    return conn


def save_result(data: dict) -> str:
    result_id = uuid.uuid4().hex
    conn = _connect()
    try:
        conn.execute(
            "INSERT INTO results (id, created_at, data) VALUES (?, datetime('now'), ?)",
            (result_id, json.dumps(data, ensure_ascii=False)),
        )
        conn.commit()
    finally:
        conn.close()
    return result_id


def get_result(result_id: str) -> Optional[dict]:
    conn = _connect()
    try:
        row = conn.execute("SELECT data FROM results WHERE id = ?", (result_id,)).fetchone()
    finally:
        conn.close()
    if row is None:
        return None
    return json.loads(row[0])

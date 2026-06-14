from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Iterable

from src.core.config import resolve_runtime_path

ISO_FORMAT = "%Y-%m-%dT%H:%M:%S"


def resolve_data_path(path_value: str | None, default: str = "data/assistant.sqlite3") -> Path:
    if path_value == ":memory:":
        return Path(path_value)
    path = resolve_runtime_path(path_value or default, base="user")
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


class AssistantStorage:
    def __init__(self, db_path: str | Path | None = None):
        self.db_path = resolve_data_path(str(db_path) if db_path else None)
        self._memory_conn = sqlite3.connect(":memory:") if str(self.db_path) == ":memory:" else None
        self._init_schema()

    def _connect(self):
        if self._memory_conn is not None:
            return self._memory_conn
        return sqlite3.connect(self.db_path)

    def _init_schema(self):
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS notes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    text TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS reminders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    kind TEXT NOT NULL,
                    text TEXT NOT NULL,
                    due_at TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    completed_at TEXT
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS command_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source TEXT NOT NULL DEFAULT 'voice',
                    raw_text TEXT NOT NULL,
                    normalized_text TEXT NOT NULL,
                    language TEXT NOT NULL,
                    status TEXT NOT NULL,
                    actions TEXT,
                    patterns TEXT,
                    scores TEXT,
                    response TEXT,
                    created_at TEXT NOT NULL
                )
                """
            )
            self._ensure_column(conn, "command_history", "source", "TEXT NOT NULL DEFAULT 'voice'")

    def _ensure_column(self, conn, table: str, column: str, definition: str):
        columns = {row[1] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
        if column not in columns:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")

    def add_note(self, text: str) -> int:
        with self._connect() as conn:
            cursor = conn.execute(
                "INSERT INTO notes (text, created_at) VALUES (?, ?)",
                (text, datetime.now().strftime(ISO_FORMAT)),
            )
            return int(cursor.lastrowid)

    def list_notes(self, limit: int = 5) -> list[dict]:
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT id, text, created_at FROM notes ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
            return [dict(row) for row in rows]

    def count_notes(self) -> int:
        with self._connect() as conn:
            return int(conn.execute("SELECT COUNT(*) FROM notes").fetchone()[0])

    def clear_notes(self) -> int:
        with self._connect() as conn:
            count = self.count_notes()
            conn.execute("DELETE FROM notes")
            return count

    def delete_note(self, note_id: int) -> int:
        with self._connect() as conn:
            cursor = conn.execute("DELETE FROM notes WHERE id = ?", (int(note_id),))
            return int(cursor.rowcount)

    def add_reminder(self, kind: str, text: str, due_at: datetime) -> int:
        with self._connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO reminders (kind, text, due_at, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (
                    kind,
                    text,
                    due_at.strftime(ISO_FORMAT),
                    datetime.now().strftime(ISO_FORMAT),
                ),
            )
            return int(cursor.lastrowid)

    def due_reminders(self, now: datetime | None = None) -> list[dict]:
        now = now or datetime.now()
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """
                SELECT id, kind, text, due_at
                FROM reminders
                WHERE completed_at IS NULL AND due_at <= ?
                ORDER BY due_at ASC
                """,
                (now.strftime(ISO_FORMAT),),
            ).fetchall()
            return [dict(row) for row in rows]

    def pending_reminders(self) -> list[dict]:
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """
                SELECT id, kind, text, due_at
                FROM reminders
                WHERE completed_at IS NULL
                ORDER BY due_at ASC
                """
            ).fetchall()
            return [dict(row) for row in rows]

    def list_reminders(self, limit: int = 100, include_completed: bool = True) -> list[dict]:
        where = "" if include_completed else "WHERE completed_at IS NULL"
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                f"""
                SELECT id, kind, text, due_at, created_at, completed_at
                FROM reminders
                {where}
                ORDER BY completed_at IS NOT NULL ASC, due_at ASC, id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
            return [dict(row) for row in rows]

    def complete_reminders(self, ids: Iterable[int]):
        ids = list(ids)
        if not ids:
            return
        placeholders = ",".join("?" for _ in ids)
        with self._connect() as conn:
            conn.execute(
                f"UPDATE reminders SET completed_at = ? WHERE id IN ({placeholders})",
                [datetime.now().strftime(ISO_FORMAT), *ids],
            )

    def delete_reminder(self, reminder_id: int) -> int:
        with self._connect() as conn:
            cursor = conn.execute("DELETE FROM reminders WHERE id = ?", (int(reminder_id),))
            return int(cursor.rowcount)

    def clear_completed_reminders(self) -> int:
        with self._connect() as conn:
            cursor = conn.execute("DELETE FROM reminders WHERE completed_at IS NOT NULL")
            return int(cursor.rowcount)

    def add_command_history(
        self,
        raw_text: str,
        normalized_text: str,
        language: str,
        status: str,
        source: str = "voice",
        actions: list[str] | None = None,
        patterns: list[str] | None = None,
        scores: list[str] | None = None,
        response: str | None = None,
    ) -> int:
        with self._connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO command_history (
                    source, raw_text, normalized_text, language, status,
                    actions, patterns, scores, response, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    source,
                    raw_text,
                    normalized_text,
                    language,
                    status,
                    ", ".join(actions or []),
                    ", ".join(patterns or []),
                    ", ".join(scores or []),
                    response or "",
                    datetime.now().strftime(ISO_FORMAT),
                ),
            )
            return int(cursor.lastrowid)

    def list_command_history(
        self,
        limit: int = 20,
        source: str | None = None,
        status: str | None = None,
        query: str | None = None,
    ) -> list[dict]:
        clauses = []
        params: list[str | int] = []

        if source and source != "all":
            clauses.append("source = ?")
            params.append(source)
        if status and status != "all":
            clauses.append("status = ?")
            params.append(status)

        normalized_query = (query or "").strip().lower()
        if normalized_query:
            clauses.append(
                """
                (
                    lower(raw_text) LIKE ?
                    OR lower(normalized_text) LIKE ?
                    OR lower(actions) LIKE ?
                    OR lower(patterns) LIKE ?
                    OR lower(response) LIKE ?
                    OR lower(status) LIKE ?
                )
                """
            )
            like_query = f"%{normalized_query}%"
            params.extend([like_query] * 6)

        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        params.append(int(limit))

        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                f"""
                SELECT id, raw_text, normalized_text, language, status,
                       source, actions, patterns, scores, response, created_at
                FROM command_history
                {where}
                ORDER BY id DESC
                LIMIT ?
                """,
                params,
            ).fetchall()
            return [dict(row) for row in rows]

    def count_command_history(self) -> int:
        with self._connect() as conn:
            return int(conn.execute("SELECT COUNT(*) FROM command_history").fetchone()[0])

    def clear_command_history(self) -> int:
        with self._connect() as conn:
            count = self.count_command_history()
            conn.execute("DELETE FROM command_history")
            return count

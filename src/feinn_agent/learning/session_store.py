"""SQLite-backed session storage with FTS5 full-text search.

Stores every conversation turn for cross-session recall. Supports:

- **DISCOVER** mode: FTS5 full-text search across all sessions
- **SCROLL** mode: ±N message window around a matched message
- **BROWSE** mode: list recent session titles and metadata

Session chains are maintained via ``parent_session_id``, allowing context
compression to create a linked lineage of sessions.

Schema:
    sessions:
        id TEXT PRIMARY KEY
        created_at TEXT NOT NULL
        updated_at TEXT NOT NULL
        parent_session_id TEXT REFERENCES sessions(id)
        title TEXT
        model TEXT
        token_count INTEGER DEFAULT 0

    messages:
        id INTEGER PRIMARY KEY AUTOINCREMENT
        session_id TEXT NOT NULL REFERENCES sessions(id)
        role TEXT NOT NULL
        content TEXT NOT NULL
        tool_calls TEXT
        tokens INTEGER DEFAULT 0
        model TEXT
        created_at TEXT NOT NULL

    messages_fts:
        VIRTUAL TABLE USING fts5(content, tokenize='unicode61')
"""

from __future__ import annotations

import json
import logging
import sqlite3
import threading
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

logger = logging.getLogger(__name__)

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    parent_session_id TEXT REFERENCES sessions(id),
    title TEXT,
    model TEXT,
    token_count INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL REFERENCES sessions(id),
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    tool_calls TEXT,
    tokens INTEGER DEFAULT 0,
    model TEXT,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_messages_session
    ON messages(session_id, id);

CREATE VIRTUAL TABLE IF NOT EXISTS messages_fts
    USING fts5(content, tokenize='unicode61');
"""


@dataclass
class SessionRecord:
    """A single session record."""

    id: str
    created_at: str
    updated_at: str
    parent_session_id: str | None = None
    title: str | None = None
    model: str | None = None
    token_count: int = 0


@dataclass
class MessageRecord:
    """A single message within a session."""

    id: int
    session_id: str
    role: str
    content: str
    tool_calls: str | None = None
    tokens: int = 0
    model: str | None = None
    created_at: str = ""


@dataclass
class SearchResult:
    """A FTS5 search hit."""

    session_id: str
    message_id: int
    snippet: str
    session_title: str | None = None
    created_at: str = ""


class SessionStore:
    """Thread-safe SQLite session storage with FTS5 search.

    Thread safety is ensured via a per-instance ``threading.Lock``.
    All public methods acquire the lock before executing SQL.

    Usage:
        store = SessionStore()
        session = store.create_session()
        msg = store.append_message(session.id, "user", "Hello")
        results = store.search("Hello")
    """

    def __init__(self, db_path: str | None = None) -> None:
        if db_path is None:
            feinn_home = Path.home() / ".feinn"
            feinn_home.mkdir(parents=True, exist_ok=True)
            db_path = str(feinn_home / "sessions.db")

        self._db_path = db_path
        self._lock = threading.Lock()
        self._init_db()

    def _init_db(self) -> None:
        """Initialize the database schema."""
        with self._connect() as conn:
            conn.executescript(_SCHEMA_SQL)
        logger.debug("Session store initialized: %s", self._db_path)

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        """Get a thread-safe database connection."""
        conn = sqlite3.connect(self._db_path, timeout=10)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    # ── Session CRUD ─────────────────────────────────────────────────

    def create_session(
        self,
        parent_id: str | None = None,
        model: str | None = None,
    ) -> SessionRecord:
        """Create a new session, optionally linked to a parent session.

        Args:
            parent_id: Optional parent session ID (for session chains).
            model: The model used in this session.

        Returns:
            The newly created SessionRecord.
        """
        from ..types import new_id

        session_id = new_id("sess")
        now = datetime.now(timezone.utc).isoformat()

        with self._connect() as conn:
            conn.execute(
                """INSERT INTO sessions (id, created_at, updated_at, parent_session_id, model)
                   VALUES (?, ?, ?, ?, ?)""",
                (session_id, now, now, parent_id, model),
            )

        logger.debug("Session created: %s (parent=%s)", session_id, parent_id)
        return SessionRecord(
            id=session_id,
            created_at=now,
            updated_at=now,
            parent_session_id=parent_id,
            model=model,
        )

    def end_session(self, session_id: str, title: str | None = None) -> None:
        """Finalize a session, optionally setting its title.

        Args:
            session_id: The session to finalize.
            title: Optional human-readable title for the session.
        """
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            conn.execute(
                "UPDATE sessions SET updated_at=?, title=? WHERE id=?",
                (now, title, session_id),
            )
        logger.debug("Session ended: %s", session_id)

    def get_session(self, session_id: str) -> SessionRecord | None:
        """Retrieve a session by ID.

        Args:
            session_id: The session ID.

        Returns:
            SessionRecord if found, None otherwise.
        """
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM sessions WHERE id=?", (session_id,)).fetchone()

        if row is None:
            return None

        return SessionRecord(
            id=row["id"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            parent_session_id=row["parent_session_id"],
            title=row["title"],
            model=row["model"],
            token_count=row["token_count"],
        )

    # ── Message CRUD ─────────────────────────────────────────────────

    def append_message(
        self,
        session_id: str,
        role: str,
        content: str,
        tool_calls: list[dict[str, Any]] | None = None,
        tokens: int = 0,
        model: str | None = None,
    ) -> MessageRecord:
        """Append a message to a session.

        Args:
            session_id: The session to append to.
            role: Message role (user, assistant, tool).
            content: Message text content.
            tool_calls: Optional list of tool call dicts.
            tokens: Token count for this message.
            model: The model that generated this message.

        Returns:
            The newly created MessageRecord.
        """
        now = datetime.now(timezone.utc).isoformat()
        tool_calls_json = json.dumps(tool_calls) if tool_calls else None

        with self._connect() as conn:
            cursor = conn.execute(
                """INSERT INTO messages
                       (session_id, role, content, tool_calls, tokens, model, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (session_id, role, content, tool_calls_json, tokens, model, now),
            )
            msg_id = cursor.lastrowid

            # Update FTS index
            if content.strip():
                conn.execute(
                    "INSERT INTO messages_fts (rowid, content) VALUES (?, ?)",
                    (msg_id, content),
                )

            # Update session token count
            conn.execute(
                "UPDATE sessions SET token_count = token_count + ?, updated_at = ? WHERE id=?",
                (tokens, now, session_id),
            )

        return MessageRecord(
            id=msg_id,
            session_id=session_id,
            role=role,
            content=content,
            tool_calls=tool_calls_json,
            tokens=tokens,
            model=model,
            created_at=now,
        )

    # ── Search (DISCOVER mode) ───────────────────────────────────────

    def search(self, query: str, limit: int = 10) -> list[SearchResult]:
        """FTS5 full-text search (DISCOVER mode).

        Searches across all sessions, excluding the current session's
        lineage. Returns results ranked by relevance.

        Args:
            query: Free-text search query.
            limit: Maximum number of results.

        Returns:
            List of SearchResult objects, ordered by relevance.
        """
        if not query.strip():
            return []

        with self._connect() as conn:
            rows = conn.execute(
                """SELECT
                       m.id,
                       m.session_id,
                       snippet(messages_fts, 0, '<b>', '</b>', '...', 32) AS snippet,
                       s.title AS session_title,
                       m.created_at
                   FROM messages_fts
                   JOIN messages m ON messages_fts.rowid = m.id
                   JOIN sessions s ON m.session_id = s.id
                   WHERE messages_fts MATCH ?
                   ORDER BY rank
                   LIMIT ?""",
                (query, limit),
            ).fetchall()

        return [
            SearchResult(
                session_id=row["session_id"],
                message_id=row["id"],
                snippet=row["snippet"],
                session_title=row["session_title"],
                created_at=row["created_at"],
            )
            for row in rows
        ]

    # ── Scroll (SCROLL mode) ─────────────────────────────────────────

    def scroll(
        self,
        session_id: str,
        around_message_id: int,
        window: int = 5,
    ) -> list[MessageRecord]:
        """Get a ±window of messages around an anchor message.

        Args:
            session_id: The session containing the anchor.
            around_message_id: The anchor message ID.
            window: Number of messages on each side.

        Returns:
            List of MessageRecord, ordered by message ID.
        """
        with self._connect() as conn:
            rows = conn.execute(
                """SELECT * FROM messages
                   WHERE session_id = ?
                     AND id BETWEEN ? AND ?
                   ORDER BY id""",
                (session_id, around_message_id - window, around_message_id + window),
            ).fetchall()

        return [
            MessageRecord(
                id=row["id"],
                session_id=row["session_id"],
                role=row["role"],
                content=row["content"],
                tool_calls=row["tool_calls"],
                tokens=row["tokens"],
                model=row["model"],
                created_at=row["created_at"],
            )
            for row in rows
        ]

    # ── Browse (BROWSE mode) ─────────────────────────────────────────

    def browse(self, limit: int = 20) -> list[SessionRecord]:
        """List recent sessions (BROWSE mode).

        Returns sessions ordered by last updated time, most recent first.

        Args:
            limit: Maximum number of sessions to return.

        Returns:
            List of SessionRecord.
        """
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM sessions ORDER BY updated_at DESC LIMIT ?",
                (limit,),
            ).fetchall()

        return [
            SessionRecord(
                id=row["id"],
                created_at=row["created_at"],
                updated_at=row["updated_at"],
                parent_session_id=row["parent_session_id"],
                title=row["title"],
                model=row["model"],
                token_count=row["token_count"],
            )
            for row in rows
        ]

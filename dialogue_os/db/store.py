"""SQLite persistence with WAL mode and migrations."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import aiosqlite

MIGRATIONS_DIR = Path(__file__).parent / "migrations"


class Store:
    def __init__(self, path: Path):
        self.path = Path(path)
        self._db: aiosqlite.Connection | None = None

    async def connect(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._db = await aiosqlite.connect(self.path)
        self._db.row_factory = aiosqlite.Row
        await self._db.execute("PRAGMA journal_mode=WAL")
        await self._db.execute("PRAGMA foreign_keys=ON")
        await self._db.execute("PRAGMA busy_timeout=5000")
        await self.migrate()

    async def close(self) -> None:
        if self._db:
            await self._db.close()
            self._db = None

    @property
    def db(self) -> aiosqlite.Connection:
        if not self._db:
            raise RuntimeError("Store not connected")
        return self._db

    async def migrate(self) -> None:
        await self.db.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                applied_at REAL NOT NULL
            )
            """
        )
        await self.db.commit()
        applied = {
            row[0]
            for row in await self.db.execute_fetchall("SELECT version FROM schema_migrations")
        }
        files = sorted(MIGRATIONS_DIR.glob("*.sql"))
        for file in files:
            # 001_init.sql -> 1
            version = int(file.stem.split("_", 1)[0])
            if version in applied:
                continue
            sql = file.read_text(encoding="utf-8")
            await self.db.executescript(sql)
            await self.db.execute(
                "INSERT INTO schema_migrations(version, name, applied_at) VALUES (?, ?, ?)",
                (version, file.name, time.time()),
            )
            await self.db.commit()

    async def execute(self, sql: str, params: tuple | list = ()) -> None:
        await self.db.execute(sql, params)
        await self.db.commit()

    async def fetchone(self, sql: str, params: tuple | list = ()) -> aiosqlite.Row | None:
        async with self.db.execute(sql, params) as cur:
            return await cur.fetchone()

    async def fetchall(self, sql: str, params: tuple | list = ()) -> list[aiosqlite.Row]:
        async with self.db.execute(sql, params) as cur:
            return await cur.fetchall()

    # --- processed updates ---
    async def is_update_processed(self, bot_id: str, update_id: int) -> bool:
        row = await self.fetchone(
            "SELECT 1 FROM processed_updates WHERE bot_id=? AND update_id=?",
            (bot_id, update_id),
        )
        return row is not None

    async def mark_update_processed(self, bot_id: str, update_id: int, event_id: str) -> None:
        await self.execute(
            """
            INSERT OR IGNORE INTO processed_updates(bot_id, update_id, event_id, processed_at)
            VALUES (?, ?, ?, ?)
            """,
            (bot_id, update_id, event_id, time.time()),
        )

    # --- cursor sessions ---
    async def get_cursor_session(self, key: str) -> str | None:
        row = await self.fetchone(
            "SELECT session_id FROM cursor_sessions WHERE session_key=?", (key,)
        )
        return row["session_id"] if row else None

    async def set_cursor_session(self, key: str, session_id: str, meta: dict | None = None) -> None:
        await self.execute(
            """
            INSERT INTO cursor_sessions(session_key, session_id, meta_json, updated_at, created_at)
            VALUES (?, ?, ?, ?, COALESCE((SELECT created_at FROM cursor_sessions WHERE session_key=?), ?))
            ON CONFLICT(session_key) DO UPDATE SET
                session_id=excluded.session_id,
                meta_json=excluded.meta_json,
                updated_at=excluded.updated_at
            """,
            (
                key,
                session_id,
                json.dumps(meta or {}),
                time.time(),
                key,
                time.time(),
            ),
        )

    async def list_cursor_sessions(self) -> list[dict[str, Any]]:
        rows = await self.fetchall(
            "SELECT session_key, session_id, meta_json, created_at, updated_at FROM cursor_sessions ORDER BY updated_at DESC"
        )
        return [
            {
                "session_key": r["session_key"],
                "session_id": r["session_id"],
                "meta": json.loads(r["meta_json"] or "{}"),
                "created_at": r["created_at"],
                "updated_at": r["updated_at"],
            }
            for r in rows
        ]

    # --- telegram chat -> backend session ---
    async def get_chat_session(self, agent_id: str, chat_id: int) -> dict | None:
        row = await self.fetchone(
            """
            SELECT agent_id, chat_id, backend, session_id, hermes_profile, meta_json, updated_at
            FROM chat_sessions WHERE agent_id=? AND chat_id=?
            """,
            (agent_id, chat_id),
        )
        if not row:
            return None
        return {
            "agent_id": row["agent_id"],
            "chat_id": row["chat_id"],
            "backend": row["backend"],
            "session_id": row["session_id"],
            "hermes_profile": row["hermes_profile"],
            "meta": json.loads(row["meta_json"] or "{}"),
            "updated_at": row["updated_at"],
        }

    async def upsert_chat_session(
        self,
        agent_id: str,
        chat_id: int,
        backend: str,
        session_id: str,
        hermes_profile: str | None = None,
        meta: dict | None = None,
    ) -> None:
        now = time.time()
        await self.execute(
            """
            INSERT INTO chat_sessions(agent_id, chat_id, backend, session_id, hermes_profile, meta_json, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(agent_id, chat_id) DO UPDATE SET
                backend=excluded.backend,
                session_id=excluded.session_id,
                hermes_profile=excluded.hermes_profile,
                meta_json=excluded.meta_json,
                updated_at=excluded.updated_at
            """,
            (
                agent_id,
                chat_id,
                backend,
                session_id,
                hermes_profile,
                json.dumps(meta or {}),
                now,
                now,
            ),
        )

    # --- agents ---
    async def upsert_agent(self, agent: dict[str, Any]) -> None:
        now = time.time()
        await self.execute(
            """
            INSERT INTO agents(agent_id, role, display_name, telegram_username, telegram_bot_id,
                               backend, hermes_profile, token_env, meta_json, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(agent_id) DO UPDATE SET
                role=excluded.role,
                display_name=excluded.display_name,
                telegram_username=excluded.telegram_username,
                telegram_bot_id=excluded.telegram_bot_id,
                backend=excluded.backend,
                hermes_profile=excluded.hermes_profile,
                token_env=excluded.token_env,
                meta_json=excluded.meta_json,
                updated_at=excluded.updated_at
            """,
            (
                agent["agent_id"],
                agent.get("role"),
                agent.get("display_name"),
                agent.get("telegram_username"),
                agent.get("telegram_bot_id"),
                agent.get("backend"),
                agent.get("hermes_profile"),
                agent.get("token_env"),
                json.dumps(agent.get("meta") or {}),
                now,
                now,
            ),
        )

    async def list_agents(self) -> list[dict[str, Any]]:
        rows = await self.fetchall("SELECT * FROM agents ORDER BY agent_id")
        out = []
        for r in rows:
            out.append({k: r[k] for k in r.keys()})
            out[-1]["meta"] = json.loads(out[-1].pop("meta_json") or "{}")
        return out

    async def get_agent(self, agent_id: str) -> dict | None:
        row = await self.fetchone("SELECT * FROM agents WHERE agent_id=?", (agent_id,))
        if not row:
            return None
        d = {k: row[k] for k in row.keys()}
        d["meta"] = json.loads(d.pop("meta_json") or "{}")
        return d

    # --- canonical events ---
    async def append_canonical_event(self, event: dict[str, Any]) -> int:
        cur = await self.db.execute(
            """
            INSERT INTO canonical_events(
                event_id, run_id, agent_id, event_type, summary, evidence_json,
                task_id, hop_count, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event["event_id"],
                event.get("run_id"),
                event.get("agent_id"),
                event["event_type"],
                event.get("summary"),
                json.dumps(event.get("evidence") or {}),
                event.get("task_id"),
                event.get("hop_count", 0),
                event.get("created_at", time.time()),
            ),
        )
        await self.db.commit()
        return cur.lastrowid or 0

    async def recent_canonical_events(self, limit: int = 50) -> list[dict[str, Any]]:
        rows = await self.fetchall(
            """
            SELECT * FROM canonical_events ORDER BY id DESC LIMIT ?
            """,
            (limit,),
        )
        out = []
        for r in rows:
            d = {k: r[k] for k in r.keys()}
            d["evidence"] = json.loads(d.pop("evidence_json") or "{}")
            out.append(d)
        return out

    # --- tasks / handoffs ---
    async def create_task(self, task: dict[str, Any]) -> None:
        await self.execute(
            """
            INSERT INTO tasks(task_id, title, status, owner_agent, created_by, meta_json, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                task["task_id"],
                task.get("title"),
                task.get("status", "ADMITTED"),
                task.get("owner_agent"),
                task.get("created_by"),
                json.dumps(task.get("meta") or {}),
                time.time(),
                time.time(),
            ),
        )

    async def create_handoff(self, handoff: dict[str, Any]) -> None:
        await self.execute(
            """
            INSERT INTO handoffs(handoff_id, task_id, from_agent, to_agent, summary, status, meta_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                handoff["handoff_id"],
                handoff.get("task_id"),
                handoff["from_agent"],
                handoff["to_agent"],
                handoff.get("summary"),
                handoff.get("status", "OPEN"),
                json.dumps(handoff.get("meta") or {}),
                time.time(),
            ),
        )

    # --- watcher alerts ---
    async def add_watcher_alert(self, alert: dict[str, Any]) -> None:
        await self.execute(
            """
            INSERT INTO watcher_alerts(alert_id, watcher_id, severity, summary, private_to_chief, meta_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                alert["alert_id"],
                alert["watcher_id"],
                alert.get("severity", "warning"),
                alert.get("summary"),
                1 if alert.get("private_to_chief", True) else 0,
                json.dumps(alert.get("meta") or {}),
                time.time(),
            ),
        )

    # --- tool runs ---
    async def add_tool_run(self, run: dict[str, Any]) -> None:
        await self.execute(
            """
            INSERT INTO tool_runs(run_id, agent_id, tool_name, status, summary, evidence_json, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run["run_id"],
                run.get("agent_id"),
                run["tool_name"],
                run.get("status", "RUNNING"),
                run.get("summary"),
                json.dumps(run.get("evidence") or {}),
                time.time(),
                time.time(),
            ),
        )

    # --- event hops / recursion ---
    async def record_event_hop(self, event_id: str, origin_bot: str, run_id: str, hop_count: int) -> None:
        await self.execute(
            """
            INSERT OR IGNORE INTO event_hops(event_id, origin_bot, run_id, hop_count, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (event_id, origin_bot, run_id, hop_count, time.time()),
        )

    async def get_event_hop(self, event_id: str) -> dict | None:
        row = await self.fetchone("SELECT * FROM event_hops WHERE event_id=?", (event_id,))
        return {k: row[k] for k in row.keys()} if row else None

    # --- watcher silence overrides ---
    async def set_watcher_override(self, watcher_id: str, chat_id: int, enabled: bool) -> None:
        await self.execute(
            """
            INSERT INTO watcher_overrides(watcher_id, chat_id, enabled, updated_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(watcher_id, chat_id) DO UPDATE SET enabled=excluded.enabled, updated_at=excluded.updated_at
            """,
            (watcher_id, chat_id, 1 if enabled else 0, time.time()),
        )

    async def watcher_override_enabled(self, watcher_id: str, chat_id: int) -> bool:
        row = await self.fetchone(
            "SELECT enabled FROM watcher_overrides WHERE watcher_id=? AND chat_id=?",
            (watcher_id, chat_id),
        )
        return bool(row and row["enabled"])

    # --- errors ---
    async def log_error(self, source: str, message: str, meta: dict | None = None) -> None:
        await self.execute(
            """
            INSERT INTO error_log(source, message, meta_json, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (source, message[:2000], json.dumps(meta or {}), time.time()),
        )

    # --- config metadata (no secrets) ---
    async def set_config_meta(self, key: str, value: str) -> None:
        await self.execute(
            """
            INSERT INTO config_meta(key, value, updated_at) VALUES (?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at
            """,
            (key, value, time.time()),
        )

    async def get_config_meta(self, key: str) -> str | None:
        row = await self.fetchone("SELECT value FROM config_meta WHERE key=?", (key,))
        return row["value"] if row else None

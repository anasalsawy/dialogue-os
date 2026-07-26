"""Governance helpers: leases, permits, audit, tasks, acceptance."""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass
from typing import Any

from dialogue_os.db.store import Store

# Mission status added for explicit correction loops (Chief sends back to work).
CORRECTION = "CORRECTION"


def new_id(prefix: str = "") -> str:
    return f"{prefix}{uuid.uuid4().hex}" if prefix else uuid.uuid4().hex


@dataclass(frozen=True)
class WorkLease:
    lease_id: str
    lease_key: str
    mission_id: str | None
    agent_id: str
    purpose: str
    status: str
    expires_at: float | None


class GovernanceAudit:
    def __init__(self, store: Store):
        self.store = store

    async def record(
        self,
        event_type: str,
        *,
        actor_agent_id: str | None = None,
        mission_id: str | None = None,
        detail: str | None = None,
        evidence: dict[str, Any] | None = None,
    ) -> None:
        await self.store.execute(
            """
            INSERT INTO governance_audit(event_type, actor_agent_id, mission_id, detail,
                                         evidence_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                event_type,
                actor_agent_id,
                mission_id,
                detail,
                json.dumps(evidence or {}),
                time.time(),
            ),
        )


class WorkLeaseManager:
    """Idempotent claims: same lease_key cannot be held twice while active."""

    def __init__(self, store: Store, audit: GovernanceAudit | None = None):
        self.store = store
        self.audit = audit or GovernanceAudit(store)

    async def claim(
        self,
        lease_key: str,
        *,
        agent_id: str,
        purpose: str,
        mission_id: str | None = None,
        ttl_seconds: float | None = 3600,
    ) -> WorkLease:
        now = time.time()
        existing = await self.store.fetchone(
            "SELECT * FROM work_leases WHERE lease_key=?", (lease_key,)
        )
        if existing and existing["status"] == "active":
            exp = existing["expires_at"]
            if exp is None or float(exp) > now:
                raise LeaseError(f"lease_key already claimed: {lease_key}")
            # expired — release then re-claim
            await self.release(existing["lease_id"], reason="expired")

        lease_id = new_id("lease_")
        expires = (now + ttl_seconds) if ttl_seconds else None
        await self.store.execute(
            """
            INSERT INTO work_leases(lease_id, lease_key, mission_id, agent_id, purpose,
                                    status, expires_at, meta_json, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, 'active', ?, ?, ?, ?)
            ON CONFLICT(lease_key) DO UPDATE SET
                lease_id=excluded.lease_id,
                mission_id=excluded.mission_id,
                agent_id=excluded.agent_id,
                purpose=excluded.purpose,
                status='active',
                expires_at=excluded.expires_at,
                meta_json=excluded.meta_json,
                updated_at=excluded.updated_at,
                released_at=NULL
            """,
            (
                lease_id,
                lease_key,
                mission_id,
                agent_id,
                purpose,
                expires,
                json.dumps({}),
                now,
                now,
            ),
        )
        await self.audit.record(
            "lease_claimed",
            actor_agent_id=agent_id,
            mission_id=mission_id,
            detail=purpose,
            evidence={"lease_key": lease_key, "lease_id": lease_id},
        )
        row = await self.store.fetchone(
            "SELECT * FROM work_leases WHERE lease_key=?", (lease_key,)
        )
        assert row is not None
        return _row_lease(row)

    async def release(self, lease_id: str, *, reason: str = "released") -> None:
        now = time.time()
        row = await self.store.fetchone(
            "SELECT * FROM work_leases WHERE lease_id=?", (lease_id,)
        )
        if row is None:
            return
        await self.store.execute(
            """
            UPDATE work_leases SET status='released', released_at=?, updated_at=?,
                                   meta_json=?
            WHERE lease_id=?
            """,
            (now, now, json.dumps({"release_reason": reason}), lease_id),
        )
        await self.audit.record(
            "lease_released",
            actor_agent_id=row["agent_id"],
            mission_id=row["mission_id"],
            detail=reason,
            evidence={"lease_id": lease_id, "lease_key": row["lease_key"]},
        )

    async def release_for_mission(self, mission_id: str, *, reason: str = "mission_cancelled") -> int:
        rows = await self.store.fetchall(
            "SELECT lease_id FROM work_leases WHERE mission_id=? AND status='active'",
            (mission_id,),
        )
        for r in rows:
            await self.release(r["lease_id"], reason=reason)
        return len(rows)

    async def expire_stale(self, *, now: float | None = None) -> int:
        now = now if now is not None else time.time()
        rows = await self.store.fetchall(
            """
            SELECT lease_id FROM work_leases
            WHERE status='active' AND expires_at IS NOT NULL AND expires_at < ?
            """,
            (now,),
        )
        for r in rows:
            await self.release(r["lease_id"], reason="expired")
        return len(rows)


class LeaseError(Exception):
    pass


class PermitGate:
    """Deny-by-default when any permit rows exist for (agent, tool); else allow."""

    def __init__(self, store: Store, audit: GovernanceAudit | None = None):
        self.store = store
        self.audit = audit or GovernanceAudit(store)

    async def allow_tool(
        self,
        agent_id: str,
        tool_name: str,
        *,
        mission_id: str | None = None,
    ) -> bool:
        mid = mission_id or ""
        rows = await self.store.fetchall(
            """
            SELECT * FROM tool_permits
            WHERE agent_id=? AND tool_name=? AND (mission_id='' OR mission_id=?)
            ORDER BY LENGTH(mission_id) DESC
            """,
            (agent_id, tool_name, mid),
        )
        if not rows:
            return True  # no policy configured → allow (backward compatible)
        # Prefer mission-scoped row if present
        for r in rows:
            if r["mission_id"] == mid and mid:
                ok = bool(r["allowed"])
                break
        else:
            ok = any(bool(r["allowed"]) and r["mission_id"] == "" for r in rows)
        if not ok:
            await self.audit.record(
                "tool_denied",
                actor_agent_id=agent_id,
                mission_id=mission_id,
                detail=tool_name,
            )
        return ok

    async def grant_tool(
        self,
        agent_id: str,
        tool_name: str,
        *,
        allowed: bool = True,
        mission_id: str | None = None,
        note: str | None = None,
    ) -> None:
        await self.store.execute(
            """
            INSERT INTO tool_permits(agent_id, tool_name, allowed, mission_id, note, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(agent_id, tool_name, mission_id) DO UPDATE SET
                allowed=excluded.allowed,
                note=excluded.note
            """,
            (agent_id, tool_name, 1 if allowed else 0, mission_id or "", note, time.time()),
        )

    async def allow_browser(
        self,
        agent_id: str,
        domain: str,
        action: str,
        *,
        mission_id: str | None = None,
    ) -> bool:
        rows = await self.store.fetchall(
            "SELECT * FROM browser_permits WHERE agent_id=?", (agent_id,)
        )
        if not rows:
            return True
        domain = (domain or "").lower()
        action = (action or "").lower()
        for r in rows:
            if r["mission_id"] not in (None, mission_id):
                continue
            pattern = (r["domain_pattern"] or "*").lower()
            actions = {a.strip().lower() for a in (r["actions_csv"] or "").split(",") if a.strip()}
            if not _domain_match(pattern, domain):
                continue
            if actions and action not in actions and "*" not in actions:
                continue
            ok = bool(r["allowed"])
            if not ok:
                await self.audit.record(
                    "browser_denied",
                    actor_agent_id=agent_id,
                    mission_id=mission_id,
                    detail=f"{action}@{domain}",
                )
            return ok
        await self.audit.record(
            "browser_denied",
            actor_agent_id=agent_id,
            mission_id=mission_id,
            detail=f"{action}@{domain}",
        )
        return False

    async def grant_browser(
        self,
        agent_id: str,
        domain_pattern: str,
        *,
        actions: list[str] | None = None,
        allowed: bool = True,
        mission_id: str | None = None,
        note: str | None = None,
    ) -> None:
        await self.store.execute(
            """
            INSERT INTO browser_permits(agent_id, domain_pattern, actions_csv, allowed,
                                        mission_id, note, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                agent_id,
                domain_pattern,
                ",".join(actions or ["navigate", "extract"]),
                1 if allowed else 0,
                mission_id,
                note,
                time.time(),
            ),
        )


def _domain_match(pattern: str, domain: str) -> bool:
    if pattern in ("*", ""):
        return True
    if pattern.startswith("*."):
        suffix = pattern[1:]  # .example.com
        return domain.endswith(suffix) or domain == pattern[2:]
    return domain == pattern or domain.endswith("." + pattern)


def _row_lease(row: Any) -> WorkLease:
    return WorkLease(
        lease_id=row["lease_id"],
        lease_key=row["lease_key"],
        mission_id=row["mission_id"],
        agent_id=row["agent_id"],
        purpose=row["purpose"],
        status=row["status"],
        expires_at=row["expires_at"],
    )


class MissionTaskStore:
    def __init__(self, store: Store):
        self.store = store

    async def add(
        self,
        mission_id: str,
        brief: str,
        *,
        title: str | None = None,
        sort_order: int = 0,
    ) -> str:
        task_id = new_id("task_")
        now = time.time()
        await self.store.execute(
            """
            INSERT INTO mission_tasks(task_id, mission_id, title, brief, status, sort_order,
                                      meta_json, created_at, updated_at)
            VALUES (?, ?, ?, ?, 'pending', ?, ?, ?, ?)
            """,
            (task_id, mission_id, title, brief, sort_order, json.dumps({}), now, now),
        )
        return task_id

    async def list_for_mission(self, mission_id: str) -> list[dict[str, Any]]:
        rows = await self.store.fetchall(
            "SELECT * FROM mission_tasks WHERE mission_id=? ORDER BY sort_order, created_at",
            (mission_id,),
        )
        return [dict(r) for r in rows]


class MemoryScopeStore:
    def __init__(self, store: Store):
        self.store = store

    async def upsert(
        self,
        agent_id: str,
        *,
        profile: str | None = None,
        read_roles: list[str] | None = None,
        write_roles: list[str] | None = None,
        notes: str | None = None,
    ) -> str:
        scope_id = f"scope_{agent_id}"
        now = time.time()
        await self.store.execute(
            """
            INSERT INTO memory_scopes(scope_id, agent_id, profile, read_roles_csv, write_roles_csv,
                                      notes, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(scope_id) DO UPDATE SET
                profile=excluded.profile,
                read_roles_csv=excluded.read_roles_csv,
                write_roles_csv=excluded.write_roles_csv,
                notes=excluded.notes,
                updated_at=excluded.updated_at
            """,
            (
                scope_id,
                agent_id,
                profile,
                ",".join(read_roles or [agent_id, "chief"]),
                ",".join(write_roles or [agent_id]),
                notes,
                now,
                now,
            ),
        )
        return scope_id

    async def may_write(self, agent_id: str, writer_role: str) -> bool:
        row = await self.store.fetchone(
            "SELECT write_roles_csv FROM memory_scopes WHERE agent_id=?", (agent_id,)
        )
        if row is None:
            return writer_role == agent_id  # default: self only
        roles = {r.strip() for r in (row["write_roles_csv"] or "").split(",") if r.strip()}
        return writer_role in roles or writer_role == "chief"

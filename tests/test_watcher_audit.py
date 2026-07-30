from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from dialogue_os.bridge import BridgeService
from dialogue_os.channel.canonical import CanonicalChannel
from dialogue_os.db.store import Store
from dialogue_os.hermes.agent_client import HermesAgentClient
from dialogue_os.watchers.service import WatcherService
from dialogue_os.watchers.audit import (
    AuditEnvelope,
    WatcherAuditLane,
    deception_consensus,
    parse_watcher_verdict,
)


def _confirmed(watcher_id: str, confidence: float = 0.98, ref: str = "tool:0"):
    return parse_watcher_verdict(
        watcher_id,
        (
            '{"verdict":"DECEPTION_CONFIRMED",'
            f'"confidence":{confidence},'
            '"claim_quote":"Deployment completed",'
            '"contradiction":"terminal reported exit code 1",'
            f'"evidence_refs":["{ref}"],'
            '"reason":"the execution result directly contradicts the claim"}'
        ),
        agent_output="Deployment completed",
        allowed_evidence_refs={"tool:0", "tool:1"},
    )


def test_confirmed_verdict_must_quote_output_and_cite_known_evidence():
    valid = _confirmed("watcher_alpha")
    assert valid.valid
    assert valid.verdict == "DECEPTION_CONFIRMED"

    invented = parse_watcher_verdict(
        "watcher_alpha",
        (
            '{"verdict":"DECEPTION_CONFIRMED","confidence":0.99,'
            '"claim_quote":"Deployment completed",'
            '"contradiction":"it failed","evidence_refs":["tool:999"],'
            '"reason":"contradiction"}'
        ),
        agent_output="Deployment completed",
        allowed_evidence_refs={"tool:0"},
    )
    assert not invented.valid
    assert invented.verdict == "INVALID"


def test_consensus_requires_same_claim_shared_evidence_and_high_confidence():
    alpha = _confirmed("watcher_alpha")
    beta = _confirmed("watcher_beta")
    assert deception_consensus(alpha, beta)

    assert not deception_consensus(
        alpha, _confirmed("watcher_beta", confidence=0.89)
    )
    assert not deception_consensus(alpha, _confirmed("watcher_beta", ref="tool:1"))


@pytest.mark.asyncio
async def test_audit_lane_is_non_blocking_and_counts_consensus():
    completed = []

    async def execute(envelope):
        completed.append(envelope.audit_id)
        return {"consensus": True}

    lane = WatcherAuditLane(execute)
    worker = lane.start()
    envelope = AuditEnvelope(
        agent_id="builder",
        profile="builder-lead",
        input_text="deploy",
        output_text="Deployment completed",
    )

    assert await lane.submit(envelope)
    await lane._queue.join()
    assert completed == [envelope.audit_id]
    assert lane.status()["deception_confirmed"] == 1
    await lane.stop()
    assert worker is not None


@pytest.mark.asyncio
async def test_watcher_audit_records_are_durable(tmp_path: Path):
    store = Store(tmp_path / "audits.sqlite3")
    await store.connect()
    try:
        await store.add_watcher_audit(
            {
                "audit_id": "audit-1",
                "watcher_id": "watcher_alpha",
                "subject_agent_id": "builder",
                "mission_id": "mission-1",
                "verdict": "CLEAR",
                "confidence": 0.99,
                "claim_quote": "",
                "contradiction": "",
                "evidence_refs": [],
                "meta": {"valid": True},
            }
        )
        rows = await store.recent_watcher_audits()
        assert rows[0]["audit_id"] == "audit-1"
        assert rows[0]["meta"] == {"valid": True}
        assert rows[0]["evidence_refs"] == []
    finally:
        await store.close()


@pytest.mark.asyncio
async def test_bridge_publishes_only_two_watcher_deception_consensus(tmp_path: Path):
    store = Store(tmp_path / "bridge-audits.sqlite3")
    await store.connect()
    try:
        bridge = object.__new__(BridgeService)
        bridge.store = store
        bridge.missions = None
        bridge.supervision = None
        bridge.canonical = CanonicalChannel(store, tmp_path / "events.jsonl", None)
        bridge.watchers = WatcherService(store, bridge.canonical)
        bridge.bots = {}
        bridge.settings = SimpleNamespace(telegram_owner_id=None)
        bridge.hermes = HermesAgentClient(
            base_url="http://127.0.0.1:8642",
            api_key="runtime-secret",
            store=store,
        )

        async def audit_reply(*, profile, **kwargs):
            return {
                "ok": True,
                "model": profile,
                "text": (
                    '{"verdict":"DECEPTION_CONFIRMED","confidence":0.99,'
                    '"claim_quote":"Deployment completed",'
                    '"contradiction":"terminal reported exit code 1",'
                    '"evidence_refs":["tool:0"],'
                    '"reason":"the tool result directly contradicts completion"}'
                ),
            }

        bridge.hermes.chat = AsyncMock(side_effect=audit_reply)
        envelope = AuditEnvelope(
            agent_id="builder",
            profile="builder-lead",
            input_text="deploy",
            output_text="Deployment completed",
            tool_events=(
                {
                    "type": "function_call_output",
                    "call_id": "call-1",
                    "output": "exit code 1",
                },
            ),
        )

        result = await bridge._execute_watcher_audit(envelope)

        assert result["consensus"] is True
        audits = await store.recent_watcher_audits()
        assert {item["watcher_id"] for item in audits} == {
            "watcher_alpha",
            "watcher_beta",
        }
        events = await store.recent_canonical_events()
        assert events[0]["event_type"] == "deception_confirmed"
        alert = await store.fetchone(
            "SELECT watcher_id FROM watcher_alerts ORDER BY id DESC LIMIT 1"
        )
        assert alert["watcher_id"] == "watcher_consensus"
    finally:
        await store.close()

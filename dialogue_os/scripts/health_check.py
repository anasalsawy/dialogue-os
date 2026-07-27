"""CLI: health / status against local health endpoint or direct store."""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dialogue_os.config import get_settings
from dialogue_os.codex.client import CodexClient
from dialogue_os.db.store import Store


async def main() -> int:
    settings = get_settings()
    url = f"http://{settings.health_bind}:{settings.health_port}/status"
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(url)
            print(json.dumps(resp.json(), indent=2))
            return 0 if resp.status_code == 200 else 1
    except Exception:
        print("Health endpoint unreachable; showing offline status:")
        store = Store(settings.database_path)
        await store.connect()
        sessions = await store.list_cursor_sessions()
        agents = await store.list_agents()
        await store.close()
        cli = CodexClient(settings.dialogue_os_root, settings.codex_cli_bin)
        try:
            bin_path = cli.resolve_bin()
        except Exception as e:
            bin_path = str(e)
        print(
            json.dumps(
                {
                    "ok": False,
                    "reason": "bridge_not_running",
                    "dialogue_os_root": str(settings.dialogue_os_root),
                    "codex_bin": bin_path,
                    "codex_sessions": sessions,
                    "agents": [
                        {
                            "agent_id": a["agent_id"],
                            "backend": a.get("backend"),
                            "telegram_username": a.get("telegram_username"),
                        }
                        for a in agents
                    ],
                },
                indent=2,
            )
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))

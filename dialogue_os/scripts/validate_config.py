"""CLI: validate configuration without printing secrets."""

from __future__ import annotations

import asyncio
import json
import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dialogue_os.agents.registry import AgentRegistry
from dialogue_os.config import get_settings
from dialogue_os.codex.client import CodexClient, sanitize_env
from dialogue_os.db.store import Store


async def _async_main() -> int:
    settings = get_settings()
    errors: list[str] = []
    warnings: list[str] = []

    print(f"DIALOGUE_OS_ROOT={settings.dialogue_os_root}")
    if not settings.dialogue_os_root.exists():
        errors.append("DIALOGUE_OS_ROOT does not exist")

    if os.geteuid() == 0:
        errors.append("Running as root is forbidden for the bridge runtime")

    try:
        settings.assert_no_azure_llm()
        print("Azure LLM routing: disabled OK")
    except RuntimeError as e:
        errors.append(str(e))

    print(f"Chief backend: {settings.chief_backend}")
    if settings.chief_backend == "codex":
        which = shutil.which(settings.codex_cli_bin)
        home_bin = Path.home() / ".local/bin" / settings.codex_cli_bin
        if not which and not home_bin.exists():
            errors.append(f"Codex CLI not found: {settings.codex_cli_bin}")
        else:
            print(f"Codex CLI: found ({settings.codex_cli_bin})")
        try:
            client = CodexClient(
                settings.dialogue_os_root,
                cli_bin=settings.codex_cli_bin,
                model=settings.codex_model,
            )
            client.resolve_bin()
            print(f"Codex sandbox: {client.sandbox}")
        except Exception as e:
            errors.append(f"Codex policy check failed: {e}")

        child_env = sanitize_env(workspace=settings.dialogue_os_root)
        leaked = sorted(
            k
            for k in child_env
            if k.startswith(("TELEGRAM_", "HERMES_", "BROWSERBASE_", "AZURE_"))
        )
        if leaked:
            errors.append(f"Codex child env would leak: {', '.join(leaked)}")
        else:
            print(f"Codex child env: sanitized ({len(child_env)} vars, no bridge secrets)")
    else:
        if not (settings.chief_featherless_api_key or settings.hermes_api_key):
            errors.append("missing CHIEF_FEATHERLESS_API_KEY (or HERMES_API_KEY fallback)")
        if not (settings.chief_featherless_model or settings.hermes_model):
            errors.append("missing CHIEF_FEATHERLESS_MODEL (or HERMES_MODEL fallback)")
        if "featherless.ai" not in settings.chief_featherless_base_url.lower():
            warnings.append("Chief Featherless URL does not contain featherless.ai")

    for item in settings.missing_required_for_bridge():
        errors.append(f"missing {item}")
    for item in settings.missing_for_hermes():
        warnings.append(f"Hermes incomplete: missing {item}")

    tokens = settings.bot_token_map()
    print(f"Configured bot tokens: {len(tokens)} ({', '.join(tokens.keys()) or 'none'})")

    store = Store(settings.database_path)
    await store.connect()
    registry = AgentRegistry(store, settings)
    await registry.seed()
    if tokens:
        results = await registry.validate_all()
        for agent_id, info in results.items():
            status = "OK" if info["ok"] else "FAIL"
            print(f"  getMe {agent_id}: {status} @{info.get('username')} id={info.get('id')}")
            if not info["ok"]:
                errors.append(f"Telegram getMe failed for {agent_id}")
    await store.close()

    env_path = settings.dialogue_os_root / ".env"
    if env_path.exists():
        mode = oct(env_path.stat().st_mode & 0o777)
        print(f".env permissions: {mode}")
        if env_path.stat().st_mode & 0o077:
            warnings.append(".env is group/world readable; should be 600")

    for w in warnings:
        print(f"WARNING: {w}")
    if errors:
        print("VALIDATION FAILED:")
        for e in errors:
            print(f"  - {e}")
        return 1
    print("VALIDATION PASSED")
    return 0


def main() -> None:
    raise SystemExit(asyncio.run(_async_main()))


if __name__ == "__main__":
    main()

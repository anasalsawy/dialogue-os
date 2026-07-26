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
from dialogue_os.cursor.client import sanitize_env
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

    which = shutil.which(settings.cursor_cli_bin)
    home_bin = Path.home() / ".local/bin" / settings.cursor_cli_bin
    if not which and not home_bin.exists():
        errors.append(f"Cursor CLI not found: {settings.cursor_cli_bin}")
    print(f"Cursor CLI: found ({settings.cursor_cli_bin})")
    try:
        from dialogue_os.cursor.client import (
            CursorClient,
            ensure_cli_unrestricted,
            parse_force_flag_from_help,
        )

        ensure_cli_unrestricted()
        client = CursorClient(
            settings.dialogue_os_root,
            cli_bin=settings.cursor_cli_bin,
            api_key=settings.cursor_api_key,
            force_flag=settings.cursor_force_flag,
            ensure_unrestricted_config=False,
        )
        force_flag = client.resolve_force_flag()
        print(f"Cursor unrestricted flag: {force_flag}")
        print("Cursor approval mode: unrestricted (Run Everything)")
        print("Cursor sandbox: disabled (not passed on CLI)")
    except Exception as e:
        errors.append(f"Cursor unrestricted policy check failed: {e}")

    cli_permissions = settings.dialogue_os_root / ".cursor" / "cli.json"
    if cli_permissions.exists():
        try:
            perms = json.loads(cli_permissions.read_text())["permissions"]
            deny = perms.get("deny") or []
            allow = perms.get("allow") or []
            if deny:
                errors.append(
                    ".cursor/cli.json still has deny rules that can reject execution; "
                    "clear deny for unrestricted Agent"
                )
            print(f"Cursor project permissions: {len(allow)} allow / {len(deny)} deny")
        except (ValueError, KeyError, TypeError) as e:
            errors.append(f".cursor/cli.json is malformed: {e}")
    else:
        warnings.append(
            ".cursor/cli.json missing — run: bash scripts/cursor-permissions/install.sh"
        )

    if (settings.dialogue_os_root / ".cursorignore").exists():
        print("Cursor ignore file: present")
    else:
        warnings.append(
            ".cursorignore missing — run: bash scripts/cursor-permissions/install.sh"
        )

    child_env = sanitize_env(workspace=settings.dialogue_os_root, api_key=settings.cursor_api_key)
    leaked = sorted(
        k
        for k in child_env
        if k != "CURSOR_API_KEY"
        and k.startswith(("TELEGRAM_", "HERMES_", "BROWSERBASE_", "AZURE_"))
    )
    if leaked:
        errors.append(f"Cursor child env would leak: {', '.join(leaked)}")
    else:
        print(f"Cursor child env: sanitized ({len(child_env)} vars, no bridge secrets)")

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

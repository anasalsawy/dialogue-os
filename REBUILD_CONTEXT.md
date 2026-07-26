# Rebuild context — read before changing Chief / offices

## Why this file exists

Previous rebuild attempts incorrectly treated **Chief as a Hermes profile**. That is wrong and must not be repeated.

## Correct model (department offices)

Dialogue-OS is **not** a universal Cursor-first router for every bot reply. It is a set of Telegram **department offices**:

- **Anas** — human owner (`TELEGRAM_OWNER_ID`)
- **Chief** — Cursor CLI manager/supervisor, present in every office
- **Exactly one specialist** — Hermes-backed, only in its own office

```text
Anas → Chief DM (Cursor)
  → Chief decides breakdown and assignments
  → Chief posts each unit into the matching office
  → Specialist receives on its own Telegram connection / Hermes profile
  → Specialist replies in the office as itself
  → Chief supervises, demands evidence, verifies completion
```

## Backends (binding)

1. **Chief = Cursor CLI** — never a Hermes profile named Chief.
2. **Other agents = persistent Hermes profiles** — personality/memory under `hermes_profiles/`.
3. **MAF** — optional orchestration bookkeeping only; not the visible voice.
4. **Stagehand / Browserbase** — browser **tool** for the browsing specialist only.

## Fixed workspace

```text
DIALOGUE_OS_ROOT=/home/azureuser/dialogue-os
```

Session continuity depends on keeping this absolute path stable on a given VM.

## Frozen Azure subscription

Do not route LLMs through Azure. `AZURE_LLM_DISABLED=true`. Chief uses Cursor. Specialists use `HERMES_*` only.

## This DigitalOcean checkpoint

- Code line intended for GitHub branch `digitalocean-rebuild` on `anasalsawy/dialogue-os-runtime`
- Pre-import mint preservation: `legacy/mint-final` + tag `mint-final-before-digitalocean`
- Live ops facts: `CURRENT_DEPLOYMENT.md`
- Backup layers: `BACKUP_MANIFEST.md`
- Restore procedure: `RESTORE.md`

Do not rewrite the office architecture during a pure backup/version-control checkpoint.

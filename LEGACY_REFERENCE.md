# Legacy reference

## Spec repository (`anasalsawy/dialogue-os`)

| Item | Value |
|------|-------|
| Role | Specification home; intended home of DigitalOcean / Cursor-Chief implementation |
| Observed HEAD (read-only HTTPS, 2026-07-26) | `2467854d52251d3280cff791c574e1d18a4dfbff` |
| Contents at that tip | `DIALOGUE_OS.md`, `LICENSE.md`, `README.md` (specification-only) |

## Runtime repository (`anasalsawy/dialogue-os-runtime`)

| Item | Value |
|------|-------|
| Role | Previous Mint / Hermes runtime — **read-only historical reference** |
| Exact commit SHA | `f6cd9b35bf223212ee818c93753479c185c1c08f` (HEAD observed 2026-07-26) |
| Policy | Do **not** overwrite. Do **not** push DigitalOcean code here. |

When auth is available, record the exact SHA:

```bash
git ls-remote https://github.com/anasalsawy/dialogue-os-runtime.git HEAD
# → paste into this file as runtime_head_sha
```

## Live VM working tree

| Item | Value |
|------|-------|
| Path | `/home/azureuser/dialogue-os` |
| Local branch | `digitalocean-rebuild` |
| Local checkpoint SHA (pre-governance port) | `f30d8f81f3a720e03667cc916ddde5d597c073ee` |
| `origin` | `https://github.com/anasalsawy/dialogue-os.git` |

## Canonical architecture (do not regress)

- Chief = persistent Cursor CLI
- Each specialist = own persistent Hermes profile/session
- One Telegram office per department: Anas + Chief + exactly one specialist
- Specialist traffic → that specialist’s Hermes session (not Cursor-as-proxy)
- Chief supervises; does not impersonate specialists
- Bot↔bot on with dedupe / loop protection
- MAF = bounded delegation/planning only
- Stagehand/Browserbase = governed browser tool only

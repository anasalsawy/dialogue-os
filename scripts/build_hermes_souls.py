#!/usr/bin/env python3
"""Build Hermes SOUL.md files from the canonical YTA prompts repository."""

from __future__ import annotations

import argparse
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"

MASTER_DOCS = {
    "builder-lead": "BUILDER_LEAD.docx",
    "research-lead": "RESEARCHER.docx",
    "operations-lead": "INTERNAL_STRUCTOR_STATE_MANAGER.docx",
    "customer-relations": "CUSTOMER_SUPPORT_COMMUNICATIONS.docx",
    "stagehand-browser": "BROWSER_OPERATOR_BOOKER_SHOPPER.docx",
    "watcher-alpha": "VERIFIER_AUDITOR.docx",
    "watcher-beta": "GOVERNOR_POLICY_AUTHORITY.docx",
}


def extract_docx_text(path: Path) -> str:
    """Extract Word paragraphs in document order using only the stdlib."""
    with zipfile.ZipFile(path) as archive:
        root = ET.fromstring(archive.read("word/document.xml"))
    paragraphs: list[str] = []
    for paragraph in root.iter(f"{W}p"):
        text = "".join(node.text or "" for node in paragraph.iter(f"{W}t")).strip()
        if text:
            paragraphs.append(text)
    return "\n\n".join(paragraphs).strip()


def markdown_section(text: str, heading: str, next_heading: str) -> str:
    start = text.index(heading)
    end = text.index(next_heading, start)
    return text[start:end].strip()


def build_souls(
    prompt_repo: Path,
    role_dir: Path,
    destination: Path,
    ethics_file: Path | None = None,
) -> list[Path]:
    destination.mkdir(parents=True, exist_ok=True)
    generated: list[Path] = []
    ethics = ethics_file.read_text(encoding="utf-8").strip() if ethics_file else ""
    ethics_layer = ""
    if ethics:
        ethics_layer = (
            "\n\n# Shared Islamic ethics and behavior layer\n\n"
            "Apply this layer to character, honesty, dignity, justice, privacy, "
            "non-aggression, lawful cooperation, promises, and business conduct. "
            "It does not grant operational authority, override applicable law or "
            "runtime safety, or justify discrimination, coercion, punishment, or "
            "religious judgment of any person. Treat every person with equal human "
            "dignity and follow the agent's authorization boundaries.\n\n"
            f"{ethics}"
        )

    for profile, filename in MASTER_DOCS.items():
        overlay = (role_dir / f"{profile}.md").read_text(encoding="utf-8").strip()
        master = extract_docx_text(prompt_repo / filename)
        output = destination / profile / "SOUL.md"
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(
            f"{overlay}{ethics_layer}\n\n"
            f"# Canonical master system prompt\n\n{master}\n",
            encoding="utf-8",
        )
        generated.append(output)

    consolidated = (prompt_repo / "YTA_MULTI_AGENT_SYSTEM_PROMPTS (1).md").read_text(
        encoding="utf-8"
    )
    shared = markdown_section(
        consolidated,
        "# Part I — Shared Runtime Kernel",
        "# Part II — Logical Tool Catalog",
    )
    chief_overlay = (role_dir / "chief-control.md").read_text(
        encoding="utf-8"
    ).strip()
    chief_output = destination / "chief-control" / "SOUL.md"
    chief_output.parent.mkdir(parents=True, exist_ok=True)
    chief_output.write_text(
        f"{chief_overlay}{ethics_layer}\n\n{shared}\n",
        encoding="utf-8",
    )
    generated.append(chief_output)
    growth = markdown_section(
        consolidated,
        "# Part V — Growth, Advertising, and Lead Generation Agent Role Prompt",
        "# Part VI — Customer Relations and Communications Agent Role Prompt",
    )
    overlay = (role_dir / "growth-lead.md").read_text(encoding="utf-8").strip()
    growth_output = destination / "growth-lead" / "SOUL.md"
    growth_output.parent.mkdir(parents=True, exist_ok=True)
    growth_output.write_text(
        f"{overlay}{ethics_layer}\n\n{shared}\n\n{growth}\n",
        encoding="utf-8",
    )
    generated.append(growth_output)
    return generated


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--prompt-repo", type=Path, required=True)
    parser.add_argument("--role-dir", type=Path, required=True)
    parser.add_argument("--destination", type=Path, required=True)
    parser.add_argument("--ethics-file", type=Path)
    args = parser.parse_args()

    generated = build_souls(
        args.prompt_repo,
        args.role_dir,
        args.destination,
        ethics_file=args.ethics_file,
    )
    for path in generated:
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

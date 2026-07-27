from pathlib import Path
import zipfile

from scripts.build_hermes_souls import build_souls


def write_docx(path: Path, title: str) -> None:
    xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/'
        'wordprocessingml/2006/main"><w:body>'
        f"<w:p><w:r><w:t>{title}</w:t></w:r></w:p>"
        f"<w:p><w:r><w:t>{title} master behavior</w:t></w:r></w:p>"
        "</w:body></w:document>"
    )
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("word/document.xml", xml)


def test_builds_role_specific_souls(tmp_path: Path):
    prompts = tmp_path / "prompts"
    roles = tmp_path / "roles"
    output = tmp_path / "profiles"
    prompts.mkdir()
    roles.mkdir()

    filenames = {
        "builder-lead": "BUILDER_LEAD.docx",
        "research-lead": "RESEARCHER.docx",
        "operations-lead": "INTERNAL_STRUCTOR_STATE_MANAGER.docx",
        "customer-relations": "CUSTOMER_SUPPORT_COMMUNICATIONS.docx",
        "stagehand-browser": "BROWSER_OPERATOR_BOOKER_SHOPPER.docx",
        "watcher-alpha": "VERIFIER_AUDITOR.docx",
        "watcher-beta": "GOVERNOR_POLICY_AUTHORITY.docx",
    }
    for profile, filename in filenames.items():
        write_docx(prompts / filename, profile)
        (roles / f"{profile}.md").write_text(
            f"{profile} Dialogue-OS overlay", encoding="utf-8"
        )
    (roles / "growth-lead.md").write_text("growth overlay", encoding="utf-8")
    (prompts / "YTA_MULTI_AGENT_SYSTEM_PROMPTS (1).md").write_text(
        "# Part I — Shared Runtime Kernel\nshared kernel\n"
        "# Part II — Logical Tool Catalog\ncatalog\n"
        "# Part V — Growth, Advertising, and Lead Generation Agent Role Prompt\n"
        "growth master\n"
        "# Part VI — Customer Relations and Communications Agent Role Prompt\n"
        "customer master\n",
        encoding="utf-8",
    )

    generated = build_souls(prompts, roles, output)

    assert len(generated) == 8
    builder = (output / "builder-lead" / "SOUL.md").read_text(encoding="utf-8")
    assert builder.startswith("builder-lead Dialogue-OS overlay")
    assert "builder-lead master behavior" in builder
    growth = (output / "growth-lead" / "SOUL.md").read_text(encoding="utf-8")
    assert "shared kernel" in growth
    assert "growth master" in growth
    assert "customer master" not in growth

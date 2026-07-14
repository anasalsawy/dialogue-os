#!/usr/bin/env python3
"""Validate the public Dialogue OS canonical package.

This validates repository structure, JSON Schema syntax, and bundled examples.
It is conformance tooling, not the private agent runtime.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

try:
    import yaml
    from jsonschema import Draft202012Validator
except ImportError as exc:
    print(
        "Missing validation dependencies. Install PyYAML and jsonschema.",
        file=sys.stderr,
    )
    raise SystemExit(2) from exc


ROOT = Path(__file__).resolve().parents[1]


def load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def main() -> int:
    manifest_path = ROOT / "dialogue-os.manifest.yaml"
    manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))

    required_paths: list[str] = [
        manifest["normative_entrypoint"],
        manifest["amendments"],
        *manifest["normative_documents"],
        *manifest["schemas"].values(),
        manifest["conformance"]["index"],
        manifest["conformance"]["tests"],
        *manifest["reference_profiles"].values(),
    ]

    missing = sorted({path for path in required_paths if not (ROOT / path).exists()})
    if missing:
        print("Missing canonical package files:")
        for path in missing:
            print(f"- {path}")
        return 1

    schemas = {
        name: load_json(ROOT / path)
        for name, path in manifest["schemas"].items()
    }
    for name, schema in schemas.items():
        Draft202012Validator.check_schema(schema)
        print(f"PASS schema syntax: {name}")

    examples = {
        "agent_manifest": ROOT / "examples/agent-manifest.example.json",
        "mission_packet": ROOT / "examples/mission-packet.example.json",
    }
    for schema_name, example_path in examples.items():
        instance = load_json(example_path)
        errors = sorted(
            Draft202012Validator(schemas[schema_name]).iter_errors(instance),
            key=lambda error: list(error.path),
        )
        if errors:
            print(f"FAIL example: {example_path.relative_to(ROOT)}")
            for error in errors:
                location = ".".join(str(part) for part in error.path) or "<root>"
                print(f"- {location}: {error.message}")
            return 1
        print(f"PASS example: {example_path.relative_to(ROOT)}")

    print(f"PASS canonical package: Dialogue OS v{manifest['version']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

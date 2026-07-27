"""Bounded MAF task-DAG validation — never replaces Hermes/Codex identity."""

from __future__ import annotations

from typing import Any


class DagValidationError(Exception):
    pass


def validate_task_dag(
    nodes: list[dict[str, Any]],
    *,
    max_nodes: int = 32,
    max_fanout: int = 8,
) -> None:
    """Validate a simple task DAG: ids, edges, no cycles, bounded size/fanout.

    Each node: {"id": str, "depends_on": [str, ...]}
    """
    if not isinstance(nodes, list):
        raise DagValidationError("nodes must be a list")
    if len(nodes) > max_nodes:
        raise DagValidationError(f"too many nodes ({len(nodes)} > {max_nodes})")
    ids = []
    deps: dict[str, list[str]] = {}
    for n in nodes:
        if not isinstance(n, dict) or "id" not in n:
            raise DagValidationError("each node needs an id")
        nid = str(n["id"])
        if nid in deps:
            raise DagValidationError(f"duplicate node id {nid}")
        ids.append(nid)
        d = n.get("depends_on") or []
        if not isinstance(d, list):
            raise DagValidationError(f"depends_on must be a list for {nid}")
        if len(d) > max_fanout:
            raise DagValidationError(f"fan-in too high for {nid}")
        deps[nid] = [str(x) for x in d]
    idset = set(ids)
    for nid, dlist in deps.items():
        for d in dlist:
            if d not in idset:
                raise DagValidationError(f"{nid} depends on unknown {d}")
        # also bound fan-out
    fanout: dict[str, int] = {i: 0 for i in ids}
    for dlist in deps.values():
        for d in dlist:
            fanout[d] = fanout.get(d, 0) + 1
    for nid, count in fanout.items():
        if count > max_fanout:
            raise DagValidationError(f"fan-out too high for {nid}")

    # cycle detect via DFS
    WHITE, GRAY, BLACK = 0, 1, 2
    color = {i: WHITE for i in ids}

    def visit(u: str) -> None:
        color[u] = GRAY
        for v in deps[u]:
            if color[v] == GRAY:
                raise DagValidationError("cycle detected")
            if color[v] == WHITE:
                visit(v)
        color[u] = BLACK

    for i in ids:
        if color[i] == WHITE:
            visit(i)

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class GraphNode:
    id: str
    label: str
    max_similarity: float
    degree: int = 0
    component_id: int | None = None


@dataclass
class GraphLink:
    source: str
    target: str
    weight: float
    lines_matched: int | None = None
    comparison_path: str | None = None
    comparison_url: str | None = None


@dataclass
class GraphComponent:
    component_id: int
    size: int
    nodes: list[str] = field(default_factory=list)
    max_edge_weight: float = 0.0


@dataclass
class MossGraphResult:
    run_id: str
    node_count: int
    link_count: int
    components: list[GraphComponent]
    nodes: list[GraphNode]
    links: list[GraphLink]


def _safe_float(value: Any) -> float:
    try:
        if value is None:
            return 0.0
        return float(value)
    except Exception:
        return 0.0


def _pair_weight(pair: dict[str, Any]) -> float:
    candidates = [
        pair.get("score"),
        pair.get("left_percent"),
        pair.get("right_percent"),
    ]
    return max(_safe_float(v) for v in candidates)


def _connected_components(adjacency: dict[str, set[str]]) -> list[list[str]]:
    visited: set[str] = set()
    components: list[list[str]] = []

    for node in adjacency:
        if node in visited:
            continue

        stack = [node]
        component: list[str] = []

        while stack:
            current = stack.pop()
            if current in visited:
                continue
            visited.add(current)
            component.append(current)
            for neighbor in adjacency.get(current, set()):
                if neighbor not in visited:
                    stack.append(neighbor)

        components.append(sorted(component))

    components.sort(key=len, reverse=True)
    return components


def build_moss_graph(run_id: str, top_pairs: list[dict[str, Any]], min_weight: float = 0.0) -> dict[str, Any]:
    node_map: dict[str, GraphNode] = {}
    links: list[GraphLink] = []
    adjacency: dict[str, set[str]] = {}

    for pair in top_pairs:
        left = str(pair.get("left") or "").strip()
        right = str(pair.get("right") or "").strip()
        if not left or not right or left == right:
            continue

        weight = _pair_weight(pair)
        if weight < min_weight:
            continue

        if left not in node_map:
            node_map[left] = GraphNode(id=left, label=left, max_similarity=weight)
        else:
            node_map[left].max_similarity = max(node_map[left].max_similarity, weight)

        if right not in node_map:
            node_map[right] = GraphNode(id=right, label=right, max_similarity=weight)
        else:
            node_map[right].max_similarity = max(node_map[right].max_similarity, weight)

        adjacency.setdefault(left, set()).add(right)
        adjacency.setdefault(right, set()).add(left)

        links.append(
            GraphLink(
                source=left,
                target=right,
                weight=weight,
                lines_matched=pair.get("lines_matched"),
                comparison_path=pair.get("comparison_path"),
                comparison_url=pair.get("comparison_url"),
            )
        )

    for node_id, neighbors in adjacency.items():
        if node_id in node_map:
            node_map[node_id].degree = len(neighbors)

    components_raw = _connected_components(adjacency)
    components: list[GraphComponent] = []

    for idx, members in enumerate(components_raw, start=1):
        member_set = set(members)
        component_links = [
            link for link in links
            if link.source in member_set and link.target in member_set
        ]
        max_edge = max((link.weight for link in component_links), default=0.0)

        for member in members:
            node_map[member].component_id = idx

        components.append(
            GraphComponent(
                component_id=idx,
                size=len(members),
                nodes=members,
                max_edge_weight=max_edge,
            )
        )

    result = MossGraphResult(
        run_id=run_id,
        node_count=len(node_map),
        link_count=len(links),
        components=components,
        nodes=sorted(node_map.values(), key=lambda n: (-n.degree, -n.max_similarity, n.label)),
        links=sorted(links, key=lambda l: (-l.weight, l.source, l.target)),
    )

    return asdict(result)

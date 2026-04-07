from __future__ import annotations

from typing import Dict, Iterable, List, Tuple


Rect = Dict[str, int]
LayoutGraph = Dict[str, List[str]]


def normalize_rect(rect: Dict[str, object]) -> Rect:
    return {
        "x": int(rect["x"]),
        "y": int(rect["y"]),
        "w": int(rect["w"]),
        "h": int(rect["h"]),
    }


def _centroid(rect: Rect) -> Tuple[float, float]:
    return rect["x"] + rect["w"] / 2.0, rect["y"] + rect["h"] / 2.0


def _overlap_length(a1: float, a2: float, b1: float, b2: float) -> float:
    return max(0.0, min(a2, b2) - max(a1, b1))


def _rect_gap(r1: Rect, r2: Rect) -> Tuple[float, float]:
    left1, right1 = r1["x"], r1["x"] + r1["w"]
    top1, bottom1 = r1["y"], r1["y"] + r1["h"]
    left2, right2 = r2["x"], r2["x"] + r2["w"]
    top2, bottom2 = r2["y"], r2["y"] + r2["h"]

    x_gap = max(left2 - right1, left1 - right2, 0)
    y_gap = max(top2 - bottom1, top1 - bottom2, 0)
    return x_gap, y_gap


def build_navigation_graph(
    zones: Dict[str, Rect],
    exits: Dict[str, Rect],
    *,
    max_gap: float = 80.0,
    min_overlap: float = 24.0,
    k_nearest: int = 2,
) -> LayoutGraph:
    """
    Build a stable navigation graph from axis-aligned rectangles.

    The graph prefers direct geometric adjacency, then falls back to a few
    nearest neighbors so custom layouts remain routable even if the user
    supplies a sparse drawing.
    """
    nodes = {**zones, **exits}
    graph: LayoutGraph = {name: [] for name in nodes}
    names = list(nodes.keys())

    for i, left in enumerate(names):
        for right in names[i + 1:]:
            r1 = nodes[left]
            r2 = nodes[right]
            x_gap, y_gap = _rect_gap(r1, r2)
            x_overlap = _overlap_length(r1["x"], r1["x"] + r1["w"], r2["x"], r2["x"] + r2["w"])
            y_overlap = _overlap_length(r1["y"], r1["y"] + r1["h"], r2["y"], r2["y"] + r2["h"])

            adjacent = False
            if x_gap <= max_gap and y_overlap >= min_overlap:
                adjacent = True
            elif y_gap <= max_gap and x_overlap >= min_overlap:
                adjacent = True
            elif x_gap == 0 and y_gap == 0:
                adjacent = True

            if adjacent:
                graph[left].append(right)
                graph[right].append(left)

    # Fall back to nearest neighbors for nodes that still look isolated.
    centroids = {name: _centroid(rect) for name, rect in nodes.items()}
    for name in names:
        if graph[name]:
            continue

        cx, cy = centroids[name]
        distances = []
        for other in names:
            if other == name:
                continue
            ox, oy = centroids[other]
            distances.append(((cx - ox) ** 2 + (cy - oy) ** 2, other))
        distances.sort(key=lambda item: item[0])
        for _, other in distances[:k_nearest]:
            if other not in graph[name]:
                graph[name].append(other)
            if name not in graph[other]:
                graph[other].append(name)

    # Keep neighbor order deterministic for reproducible routing.
    for name in graph:
        graph[name] = sorted(set(graph[name]))

    return graph


def pick_primary_exit(zones: Dict[str, Rect], exits: Dict[str, Rect]) -> str:
    """
    Pick a default entry point for a new occupant population.

    We anchor people in the largest zone so new layouts behave predictably.
    """
    if not zones:
        return next(iter(exits), "")
    return max(zones.items(), key=lambda item: item[1]["w"] * item[1]["h"])[0]

from __future__ import annotations

from .models import (
    ReferenceFlowCard,
    ReferenceFlowStep,
    ReferenceGraph,
    ReferenceOverview,
    ReferencePath,
    ReferenceUsageGroup,
)
from .reference_graph import build_reference_paths


TYPE_LABELS = {
    "IMAGE": "图片", "NODE": "节点", "NODE_TREE": "节点组", "MATERIAL": "材质",
    "MATERIAL_SLOT": "材质槽", "MODIFIER": "修改器", "OBJECT": "物体",
    "COLLECTION": "集合", "SCENE": "场景", "VIEW_LAYER": "视图层",
    "WORLD": "世界", "LIGHT": "灯光", "COMPOSITOR": "合成器",
}
TYPE_ICONS = {
    "IMAGE": "IMAGE_DATA", "NODE": "NODE", "NODE_TREE": "NODETREE", "MATERIAL": "MATERIAL",
    "MATERIAL_SLOT": "MATERIAL", "MODIFIER": "MODIFIER", "OBJECT": "OBJECT_DATA",
    "COLLECTION": "OUTLINER_COLLECTION", "SCENE": "SCENE_DATA", "VIEW_LAYER": "RENDERLAYERS",
    "WORLD": "WORLD_DATA", "LIGHT": "LIGHT_DATA", "COMPOSITOR": "NODE_COMPOSITING",
}


def build_reference_overview(graph: ReferenceGraph, root_id: str) -> ReferenceOverview:
    paths = build_reference_paths(graph, root_id)
    reachable = {node_id for path in paths for node_id in path.node_ids}
    kinds = {kind: {node_id for node_id in reachable if graph.nodes[node_id].kind == kind} for kind in (
        "NODE", "MATERIAL", "MODIFIER", "OBJECT", "SCENE",
    )}
    primary = set()
    for kind in ("MATERIAL", "MODIFIER", "WORLD", "LIGHT", "COMPOSITOR"):
        primary.update(node_id for node_id in reachable if graph.nodes[node_id].kind == kind)
    if not primary:
        primary.update(kinds["NODE"])
    return ReferenceOverview(
        direct_nodes=len(kinds["NODE"]), materials=len(kinds["MATERIAL"]),
        modifiers=len(kinds["MODIFIER"]), objects=len(kinds["OBJECT"]),
        scenes=len(kinds["SCENE"]), primary_users=len(primary),
    )


def choose_default_usage(groups: tuple[ReferenceUsageGroup, ...]) -> str:
    usages = [usage for group in groups for usage in group.usages]
    if not usages:
        return ""
    with_hosts = [usage for usage in usages if usage.hosts]
    return (with_hosts or usages)[0].id


def choose_default_path(paths: tuple[ReferencePath, ...], host_id: str | None = None) -> ReferencePath | None:
    candidates = [path for path in paths if not host_id or host_id in path.node_ids]
    if not candidates:
        return None
    return min(candidates, key=lambda path: (path.cyclic, len(path.node_ids), path.id))


def get_display_path(
    graph: ReferenceGraph,
    path: ReferencePath,
    endpoint_id: str | None = None,
) -> tuple[ReferenceFlowCard, ...]:
    node_ids = path.node_ids
    if endpoint_id and endpoint_id in node_ids:
        node_ids = node_ids[:node_ids.index(endpoint_id) + 1]
    cards = []
    for index, node_id in enumerate(node_ids):
        node = graph.nodes[node_id]
        relation = path.relations[index - 1] if index > 0 and index - 1 < len(path.relations) else ""
        cards.append(ReferenceFlowCard(
            node_id, node.kind, TYPE_LABELS.get(node.kind, node.kind), node.name,
            relation, TYPE_ICONS.get(node.kind, "DOT"), node.locatable,
            path.cyclic and index == len(node_ids) - 1,
        ))
    return tuple(cards)


def get_complete_usage_paths(
    graph: ReferenceGraph,
    root_id: str,
    usage_id: str | None = None,
) -> tuple[ReferencePath, ...]:
    paths = build_reference_paths(graph, root_id)
    if usage_id:
        usage = graph.usage_index.get(usage_id)
        if usage is not None:
            allowed = set(usage.path_ids)
            paths = tuple(path for path in paths if path.id in allowed)
    return tuple(paths)


def choose_default_complete_path(graph: ReferenceGraph, paths: tuple[ReferencePath, ...]) -> ReferencePath | None:
    if not paths:
        return None

    def score(path: ReferencePath):
        kinds = {graph.nodes[node_id].kind for node_id in path.node_ids}
        has_real_host = bool(kinds & {"OBJECT", "SCENE", "VIEW_LAYER"})
        return (path.cyclic, not has_real_host, len(path.node_ids), path.id)

    return min(paths, key=score)


def build_flow_steps(graph: ReferenceGraph, path: ReferencePath) -> tuple[ReferenceFlowStep, ...]:
    steps = []
    for index, node_id in enumerate(path.node_ids):
        node = graph.nodes[node_id]
        steps.append(ReferenceFlowStep(
            node_id, index + 1, node.kind, TYPE_LABELS.get(node.kind, node.kind), node.name,
            path.relations[index - 1] if index else "资源起点",
            TYPE_ICONS.get(node.kind, "DOT"), node.locatable,
            path.cyclic and index == len(path.node_ids) - 1, path.id,
        ))
    return tuple(steps)

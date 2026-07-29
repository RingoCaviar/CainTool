from __future__ import annotations

from collections import defaultdict

from .models import ReferenceGraph, ReferenceHost, ReferencePath, ReferenceUsage, ReferenceUsageGroup
from .reference_graph import build_reference_paths


GROUP_LABELS = {
    "MATERIAL": "材质",
    "MODIFIER": "几何节点修改器",
    "WORLD": "世界",
    "LIGHT": "灯光",
    "COMPOSITOR": "合成器",
    "OTHER": "其他节点引用",
}
GROUP_ORDER = tuple(GROUP_LABELS)
PRIMARY_KINDS = {"MATERIAL", "MODIFIER", "WORLD", "LIGHT", "COMPOSITOR"}


def _primary_node(graph: ReferenceGraph, path: ReferencePath):
    nodes = [graph.nodes[node_id] for node_id in path.node_ids]
    for kind in GROUP_ORDER[:-1]:
        for node in nodes:
            if node.kind == kind:
                return kind, node
    for node in nodes[1:]:
        if node.kind == "NODE":
            return "OTHER", node
    for node in nodes[1:]:
        if node.kind == "NODE_TREE":
            return "OTHER", node
    return None, None


def _hosts_for_path(graph: ReferenceGraph, path: ReferencePath, primary_index: int, category: str):
    nodes = [graph.nodes[node_id] for node_id in path.node_ids]
    downstream = nodes[primary_index + 1:]
    hosts = []
    if category == "MATERIAL":
        candidates = [node for node in downstream if node.kind == "MATERIAL_SLOT"]
        if not candidates:
            candidates = [node for node in downstream if node.kind == "OBJECT"]
    elif category in {"MODIFIER", "LIGHT"}:
        candidates = [node for node in downstream if node.kind == "OBJECT"]
    elif category in {"WORLD", "COMPOSITOR"}:
        candidates = [node for node in downstream if node.kind == "SCENE"]
    else:
        candidates = []
    for node in candidates:
        detail = ""
        if node.kind == "MATERIAL_SLOT":
            detail = f"{node.owner_name} · 槽位 {node.slot_index + 1}"
        elif node.kind == "OBJECT":
            detail = "物体"
        elif node.kind == "SCENE":
            detail = "场景"
        hosts.append(ReferenceHost(node.id, node.id, node.kind, node.name, detail))
    return hosts


def summarize_reference_usage(graph: ReferenceGraph, resource_root_id: str) -> tuple[ReferenceUsageGroup, ...]:
    paths = build_reference_paths(graph, resource_root_id)
    graph.path_index.update({path.id: path for path in paths})
    builders = {}
    for path in paths:
        category, primary = _primary_node(graph, path)
        if primary is None:
            continue
        usage_id = f"{category}:{primary.id}"
        builder = builders.setdefault(usage_id, {
            "node": primary, "category": category, "paths": [], "hosts": {},
        })
        builder["paths"].append(path)
        primary_index = path.node_ids.index(primary.id)
        for host in _hosts_for_path(graph, path, primary_index, category):
            builder["hosts"].setdefault(host.id, host)

    grouped = defaultdict(list)
    graph.usage_index.clear()
    for usage_id, builder in builders.items():
        unique_paths = {path.id: path for path in builder["paths"]}
        ordered_paths = sorted(unique_paths.values(), key=lambda item: (len(item.node_ids), item.id))
        usage = ReferenceUsage(
            usage_id, builder["node"].id, builder["category"], builder["node"].name,
            tuple(sorted(builder["hosts"].values(), key=lambda item: (item.name.casefold(), item.id))),
            tuple(path.id for path in ordered_paths),
        )
        graph.usage_index[usage.id] = usage
        grouped[usage.category].append(usage)

    groups = []
    for category in GROUP_ORDER:
        usages = grouped.get(category)
        if usages:
            groups.append(ReferenceUsageGroup(
                category, GROUP_LABELS[category],
                tuple(sorted(usages, key=lambda item: (item.name.casefold(), item.id))),
            ))
    return tuple(groups)


def get_usage_hosts(graph: ReferenceGraph, usage_id: str) -> tuple[ReferenceHost, ...]:
    usage = graph.usage_index.get(usage_id)
    return usage.hosts if usage else ()


def get_paths_to_usage(graph: ReferenceGraph, resource_root_id: str, usage_id: str) -> tuple[ReferencePath, ...]:
    usage = graph.usage_index.get(usage_id)
    if usage is None:
        summarize_reference_usage(graph, resource_root_id)
        usage = graph.usage_index.get(usage_id)
    if usage is None:
        return ()
    return tuple(graph.path_index[path_id] for path_id in usage.path_ids if path_id in graph.path_index)

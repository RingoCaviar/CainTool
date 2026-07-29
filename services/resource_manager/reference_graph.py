from __future__ import annotations

import hashlib
from collections import defaultdict

from .models import ReferenceGraph, ReferenceNode, ReferencePath


def stable_node_id(kind: str, name: str, *, library_path: str = "", owner: str = "") -> str:
    raw = "\x1f".join((kind, library_path, owner, name)).encode("utf-8", "surrogatepass")
    return f"{kind.lower()}:{hashlib.sha1(raw).hexdigest()}"


def _library_path(value) -> str:
    library = getattr(value, "library", None)
    return getattr(library, "filepath", "") if library else ""


def _lookup_key(value):
    return (getattr(value, "name", ""), _library_path(value))


def _session_key(value):
    """Identity key valid only during one scan; it is never persisted."""
    pointer = getattr(value, "as_pointer", None)
    if callable(pointer):
        try:
            return ("PTR", pointer())
        except Exception:
            pass
    return ("PY", id(value))


def _id_node(graph: ReferenceGraph, value, kind: str, *, owner: str = "", **metadata) -> str:
    name = getattr(value, "name", str(value))
    library = _library_path(value)
    node_id = stable_node_id(kind, name, library_path=library, owner=owner)
    graph.add_node(ReferenceNode(
        node_id, kind, name, library_path=library, data_name=name,
        linked=bool(library), owner_name=owner, **metadata,
    ))
    return node_id


def _node_tree_node(graph: ReferenceGraph, tree, node, tree_id, owner_kind, owner_name, owner_library) -> str:
    tree_name = getattr(tree, "name", "")
    name = getattr(node, "name", "")
    library = _library_path(tree)
    node_id = stable_node_id("NODE", name, library_path=owner_library, owner=tree_id)
    context = f"{owner_kind}:{owner_name}" if owner_name else owner_kind
    graph.add_node(ReferenceNode(
        node_id, "NODE", f"{getattr(node, 'label', '') or name}（{context}）",
        library_path=owner_library, owner_name=owner_name, tree_name=tree_name,
        tree_type=getattr(tree, "bl_idname", ""), node_name=name,
        tree_id=tree_id, tree_owner_kind=owner_kind, tree_owner_name=owner_name,
        tree_library_path=owner_library, linked=bool(owner_library),
    ))
    return node_id


def _all_node_trees(data):
    seen = set()
    entries = []
    owners = (
        ("materials", "MATERIAL"), ("worlds", "WORLD"),
        ("lights", "LIGHT"), ("scenes", "COMPOSITOR"),
    )
    for collection_name, owner_kind in owners:
        for owner in getattr(data, collection_name, ()):
            tree = getattr(owner, "node_tree", None)
            if tree:
                entries.append((tree, owner, owner_kind))
                seen.add(_session_key(tree))
    for tree in getattr(data, "node_groups", ()):
        if _session_key(tree) not in seen:
            entries.append((tree, None, "NODE_GROUP"))
    return entries


def build_reference_graph(data) -> ReferenceGraph:
    graph = ReferenceGraph()
    tree_registry = {}
    tree_owners = []

    for image in getattr(data, "images", ()):
        _id_node(graph, image, "IMAGE")

    entries = _all_node_trees(data)
    for tree, owner, owner_kind in entries:
        owner_name = getattr(owner, "name", "") if owner is not None else getattr(tree, "name", "")
        owner_library = _library_path(owner if owner is not None else tree)
        tree_id = stable_node_id(
            "NODE_TREE", "NODE_TREE" if owner is not None else owner_name,
            library_path=owner_library, owner=f"{owner_kind}:{owner_name}",
        )
        graph.add_node(ReferenceNode(
            tree_id, "NODE_TREE", f"{getattr(tree, 'name', '')}（{owner_kind}:{owner_name}）",
            library_path=owner_library, data_name=getattr(tree, "name", ""), owner_name=owner_name,
            tree_name=getattr(tree, "name", ""), tree_type=getattr(tree, "bl_idname", ""),
            tree_id=tree_id, tree_owner_kind=owner_kind, tree_owner_name=owner_name,
            tree_library_path=owner_library, linked=bool(owner_library),
        ))
        tree_registry[_session_key(tree)] = (tree_id, owner_kind, owner_name, owner_library)
        if owner is not None:
            owner_id = _id_node(graph, owner, owner_kind)
            graph.add_edge(tree_id, owner_id, "所属")
            tree_owners.append((owner_kind, owner, owner_id))

    for tree, owner, owner_kind in entries:
        tree_id, owner_kind, owner_name, owner_library = tree_registry[_session_key(tree)]
        for node in getattr(tree, "nodes", ()):
            node_id = _node_tree_node(graph, tree, node, tree_id, owner_kind, owner_name, owner_library)
            graph.add_edge(node_id, tree_id, "位于节点树")
            image = getattr(node, "image", None)
            if image is not None:
                image_id = _id_node(graph, image, "IMAGE")
                graph.add_edge(image_id, node_id, "被节点使用")
            group_tree = getattr(node, "node_tree", None)
            if group_tree is not None:
                group_context = tree_registry.get(_session_key(group_tree))
                if group_context is None:
                    continue
                group_id = group_context[0]
                graph.add_edge(group_id, node_id, "被组节点实例化")

    material_ids = {_lookup_key(owner): owner_id for kind, owner, owner_id in tree_owners if kind == "MATERIAL"}
    light_ids = {_lookup_key(owner): owner_id for kind, owner, owner_id in tree_owners if kind == "LIGHT"}
    world_ids = {_lookup_key(owner): owner_id for kind, owner, owner_id in tree_owners if kind == "WORLD"}

    object_ids = {}
    for obj in getattr(data, "objects", ()):
        obj_id = _id_node(graph, obj, "OBJECT")
        object_ids[_lookup_key(obj)] = obj_id
        for index, slot in enumerate(getattr(obj, "material_slots", ())):
            material = getattr(slot, "material", None)
            if material is None:
                continue
            material_id = material_ids.get(_lookup_key(material)) or _id_node(graph, material, "MATERIAL")
            slot_name = f"{getattr(obj, 'name', '')}[{index}]"
            slot_id = stable_node_id("MATERIAL_SLOT", slot_name, owner=getattr(obj, "name", ""))
            graph.add_node(ReferenceNode(
                slot_id, "MATERIAL_SLOT", getattr(slot, "name", "") or f"材质槽 {index + 1}",
                library_path=_library_path(material), linked=bool(_library_path(material)),
                owner_name=getattr(obj, "name", ""), data_name=getattr(material, "name", ""), slot_index=index,
            ))
            graph.add_edge(material_id, slot_id, "用于材质槽")
            graph.add_edge(slot_id, obj_id, "属于物体")
        for modifier in getattr(obj, "modifiers", ()):
            node_group = getattr(modifier, "node_group", None)
            if node_group is None:
                continue
            group_context = tree_registry.get(_session_key(node_group))
            if group_context is None:
                continue
            group_id = group_context[0]
            modifier_name = getattr(modifier, "name", "")
            modifier_id = stable_node_id("MODIFIER", modifier_name, owner=getattr(obj, "name", ""))
            graph.add_node(ReferenceNode(
                modifier_id, "MODIFIER", modifier_name, owner_name=getattr(obj, "name", ""),
                tree_name=getattr(node_group, "name", ""),
            ))
            graph.add_edge(group_id, modifier_id, "用于几何节点修改器")
            graph.add_edge(modifier_id, obj_id, "属于物体")
        light = getattr(obj, "data", None)
        light_id = light_ids.get(_lookup_key(light))
        if light_id:
            graph.add_edge(light_id, obj_id, "属于灯光物体")

    collection_ids = {}
    for collection in getattr(data, "collections", ()):
        collection_id = _id_node(graph, collection, "COLLECTION")
        collection_ids[_lookup_key(collection)] = collection_id
        for obj in getattr(collection, "objects", ()):
            obj_id = object_ids.get(_lookup_key(obj)) or _id_node(graph, obj, "OBJECT")
            graph.add_edge(obj_id, collection_id, "位于集合")
    for parent in getattr(data, "collections", ()):
        parent_id = collection_ids.get(_lookup_key(parent)) or _id_node(graph, parent, "COLLECTION")
        for child in getattr(parent, "children", ()):
            child_id = collection_ids.get(_lookup_key(child)) or _id_node(graph, child, "COLLECTION")
            graph.add_edge(child_id, parent_id, "属于父集合")
    for obj in getattr(data, "objects", ()):
        instance_collection = getattr(obj, "instance_collection", None)
        if instance_collection:
            collection_id = collection_ids.get(_lookup_key(instance_collection)) or _id_node(graph, instance_collection, "COLLECTION")
            graph.add_edge(collection_id, object_ids[_lookup_key(obj)], "被集合实例物体使用")

    for scene in getattr(data, "scenes", ()):
        scene_id = _id_node(graph, scene, "SCENE", scene_name=getattr(scene, "name", ""))
        world = getattr(scene, "world", None)
        world_id = world_ids.get(_lookup_key(world))
        if world_id:
            graph.add_edge(world_id, scene_id, "用于场景世界")
        scene_collection = getattr(scene, "collection", None)
        direct = getattr(scene_collection, "children", ()) if scene_collection else ()
        for collection in tuple(direct):
            collection_id = collection_ids.get(_lookup_key(collection))
            if collection_id:
                graph.add_edge(collection_id, scene_id, "属于场景")
        for view_layer in getattr(scene, "view_layers", ()):
            name = getattr(view_layer, "name", "")
            layer_id = stable_node_id("VIEW_LAYER", name, owner=getattr(scene, "name", ""))
            graph.add_node(ReferenceNode(
                layer_id, "VIEW_LAYER", name, owner_name=getattr(scene, "name", ""),
                scene_name=getattr(scene, "name", ""), view_layer_name=name,
            ))
            graph.add_edge(scene_id, layer_id, "包含视图层")
    return graph


def build_reference_paths(graph: ReferenceGraph, root_id: str, max_paths: int = 10000) -> tuple[ReferencePath, ...]:
    paths = []

    def walk(node_id: str, nodes: tuple[str, ...], relations: tuple[str, ...]):
        if len(paths) >= max_paths:
            return
        children = graph.children(node_id)
        if not children:
            raw = "|".join(nodes + relations)
            paths.append(ReferencePath(hashlib.sha1(raw.encode()).hexdigest(), nodes, relations))
            return
        for edge in children:
            if edge.target_id in nodes:
                cycle_nodes = nodes + (edge.target_id,)
                raw = "|".join(cycle_nodes + relations + (edge.relation,))
                paths.append(ReferencePath(hashlib.sha1(raw.encode()).hexdigest(), cycle_nodes, relations + (edge.relation,), True))
                continue
            walk(edge.target_id, nodes + (edge.target_id,), relations + (edge.relation,))

    if root_id in graph.nodes:
        walk(root_id, (root_id,), ())
    return tuple(paths)


def get_reference_children(graph: ReferenceGraph, node_id: str):
    return graph.children(node_id)


def bind_resource_roots(resource_graph) -> None:
    reference_graph = resource_graph.references_graph
    image_nodes = defaultdict(list)
    for node in reference_graph.nodes.values():
        if node.kind == "IMAGE":
            image_nodes[(node.name, node.library_path)].append(node.id)
    for resource in resource_graph.resources.values():
        if resource.kind == "IMAGE":
            matches = image_nodes.get((resource.name, resource.library_path), ()) or image_nodes.get((resource.name, ""), ())
            if matches:
                resource.root_node_id = matches[0]

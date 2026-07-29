from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from .models import ReferenceNode


@dataclass(frozen=True)
class LocateResult:
    success: bool
    message: str


Locator = Callable[[object, ReferenceNode], LocateResult]
LOCATORS: dict[str, Locator] = {}


def register_locator(*kinds: str):
    def decorator(function: Locator):
        for kind in kinds:
            LOCATORS[kind] = function
        return function
    return decorator


def _bpy():
    import bpy
    return bpy


def _find_area(context, area_type: str):
    for area in context.screen.areas:
        if area.type == area_type:
            return area
    area = context.area
    if area is None:
        return None
    try:
        from . import runtime
        runtime.previous_area_state = (area.as_pointer(), area.type, getattr(area, "ui_type", ""))
        area.type = area_type
    except Exception:
        return None
    return area


def _select_object(context, object_name: str) -> LocateResult:
    bpy = _bpy()
    obj = bpy.data.objects.get(object_name)
    if obj is None:
        return LocateResult(False, f"找不到物体：{object_name}")
    if obj.name not in context.view_layer.objects:
        for scene in bpy.data.scenes:
            if obj.name in scene.objects:
                context.window.scene = scene
                break
    if obj.name not in context.view_layer.objects:
        return LocateResult(False, f"物体不在可访问的视图层：{object_name}")
    if getattr(obj, "hide_select", False):
        return LocateResult(False, f"物体禁止选择：{object_name}")
    bpy.ops.object.select_all(action="DESELECT")
    try:
        obj.hide_set(False)
    except Exception:
        pass
    obj.select_set(True)
    context.view_layer.objects.active = obj
    return LocateResult(True, f"已选择物体：{object_name}")


def _matches_library(value, library_path: str) -> bool:
    if not library_path:
        return not bool(getattr(value, "library", None))
    return _library_path(value).casefold() == library_path.casefold()


def _library_path(value) -> str:
    library = getattr(value, "library", None)
    return getattr(library, "filepath", "") if library else ""


def _find_material_host(material_name: str, preferred_object: str = "", library_path: str = "", preferred_index: int = -1):
    bpy = _bpy()
    candidates = []
    for obj in bpy.data.objects:
        for index, slot in enumerate(getattr(obj, "material_slots", ())):
            material = getattr(slot, "material", None)
            if material and material.name == material_name and _matches_library(material, library_path):
                candidates.append((obj, index))
    if preferred_object:
        for candidate in candidates:
            if candidate[0].name == preferred_object and (preferred_index < 0 or candidate[1] == preferred_index):
                return candidate
    return candidates[0] if candidates else (None, -1)


def _owned_node_tree(node: ReferenceNode):
    bpy = _bpy()
    collection_name = {
        "MATERIAL": "materials", "WORLD": "worlds", "LIGHT": "lights",
        "COMPOSITOR": "scenes", "NODE_GROUP": "node_groups",
    }.get(node.tree_owner_kind)
    if not collection_name:
        return None
    for value in getattr(bpy.data, collection_name, ()):
        if value.name != node.tree_owner_name or not _matches_library(value, node.tree_library_path):
            continue
        return value if node.tree_owner_kind == "NODE_GROUP" else getattr(value, "node_tree", None)
    return None


def _show_node_tree(context, tree, node_name: str = "") -> LocateResult:
    area = _find_area(context, "NODE_EDITOR")
    if area is None:
        return LocateResult(False, "没有可用于定位的节点编辑器区域")
    try:
        area.ui_type = getattr(tree, "bl_idname", "ShaderNodeTree")
    except Exception:
        pass
    space = area.spaces.active
    try:
        space.pin = True
        space.path.start(tree)
    except Exception:
        try:
            space.node_tree = tree
        except Exception:
            return LocateResult(False, f"无法打开节点树：{tree.name}")
    target = None
    for node in tree.nodes:
        node.select = False
        if node.name == node_name:
            target = node
    if target:
        target.select = True
        tree.nodes.active = target
        try:
            with context.temp_override(area=area, region=next(r for r in area.regions if r.type == "WINDOW")):
                _bpy().ops.node.view_selected("INVOKE_DEFAULT")
        except Exception:
            pass
        return LocateResult(True, f"已定位节点：{target.name}")
    return LocateResult(True, f"已打开节点树：{tree.name}")


@register_locator("IMAGE")
def _locate_image(context, node):
    bpy = _bpy()
    image = next((item for item in bpy.data.images if item.name == (node.data_name or node.name) and _matches_library(item, node.library_path)), None)
    if image is None:
        return LocateResult(False, f"找不到图片数据：{node.name}")
    area = _find_area(context, "IMAGE_EDITOR")
    if area is None:
        return LocateResult(False, "没有可用于定位的图片编辑器区域")
    area.spaces.active.image = image
    return LocateResult(True, f"已在图片编辑器显示：{image.name}")


@register_locator("NODE", "NODE_TREE")
def _locate_node(context, node):
    tree = _owned_node_tree(node)
    if tree is None:
        return LocateResult(False, f"找不到节点树：{node.tree_name or node.name}")
    return _show_node_tree(context, tree, node.node_name if node.kind == "NODE" else "")


@register_locator("MATERIAL", "MATERIAL_SLOT")
def _locate_material(context, node):
    material_name = node.data_name or node.name
    preferred_object = node.owner_name if node.kind == "MATERIAL_SLOT" else ""
    obj, index = _find_material_host(material_name, preferred_object, node.library_path)
    if obj is None:
        return LocateResult(False, f"材质没有可定位的物体宿主：{material_name}")
    selected = _select_object(context, obj.name)
    if not selected.success:
        return selected
    obj.active_material_index = index
    area = _find_area(context, "NODE_EDITOR")
    if area:
        try:
            area.ui_type = "ShaderNodeTree"
            area.spaces.active.shader_type = "OBJECT"
            area.spaces.active.pin = False
        except Exception:
            pass
    return LocateResult(True, f"已激活 {obj.name} 的材质槽 {index + 1}：{material_name}")


@register_locator("OBJECT")
def _locate_object(context, node):
    return _select_object(context, node.data_name or node.name)


@register_locator("MODIFIER")
def _locate_modifier(context, node):
    bpy = _bpy()
    selected = _select_object(context, node.owner_name)
    if not selected.success:
        return selected
    obj = bpy.data.objects.get(node.owner_name)
    modifier = obj.modifiers.get(node.name) if obj else None
    if modifier is None:
        return LocateResult(False, f"找不到修改器：{node.name}")
    tree = getattr(modifier, "node_group", None)
    if tree:
        return _show_node_tree(context, tree)
    return LocateResult(True, f"已激活修改器宿主：{node.owner_name}")


@register_locator("LIGHT")
def _locate_light(context, node):
    bpy = _bpy()
    for obj in bpy.data.objects:
        if getattr(getattr(obj, "data", None), "name", "") == node.data_name:
            selected = _select_object(context, obj.name)
            if not selected.success:
                return selected
            area = _find_area(context, "NODE_EDITOR")
            if area:
                area.ui_type = "ShaderNodeTree"
                area.spaces.active.shader_type = "OBJECT"
            return LocateResult(True, f"已激活灯光：{obj.name}")
    return LocateResult(False, f"找不到灯光宿主：{node.name}")


@register_locator("WORLD", "COMPOSITOR")
def _locate_scene_tree_owner(context, node):
    bpy = _bpy()
    area = _find_area(context, "NODE_EDITOR")
    if area is None:
        return LocateResult(False, "没有可用的节点编辑器")
    if node.kind == "WORLD":
        for scene in bpy.data.scenes:
            if getattr(getattr(scene, "world", None), "name", "") == node.data_name:
                context.window.scene = scene
                area.ui_type = "ShaderNodeTree"
                area.spaces.active.shader_type = "WORLD"
                return LocateResult(True, f"已激活世界：{node.name}")
    scene = bpy.data.scenes.get(node.data_name or node.name)
    if scene:
        context.window.scene = scene
        area.ui_type = "CompositorNodeTree"
        return LocateResult(True, f"已打开场景合成器：{scene.name}")
    return LocateResult(False, f"找不到宿主：{node.name}")


@register_locator("COLLECTION")
def _locate_collection(context, node):
    bpy = _bpy()
    collection = bpy.data.collections.get(node.data_name or node.name)
    if collection is None:
        return LocateResult(False, f"找不到集合：{node.name}")

    def find_layer_collection(layer_collection):
        if getattr(layer_collection, "collection", None) == collection:
            return layer_collection
        for child in getattr(layer_collection, "children", ()):
            found = find_layer_collection(child)
            if found:
                return found
        return None

    layer_collection = find_layer_collection(context.view_layer.layer_collection)
    if layer_collection:
        context.view_layer.active_layer_collection = layer_collection
        for area in context.screen.areas:
            if area.type == "OUTLINER":
                try:
                    area.spaces.active.display_mode = "VIEW_LAYER"
                except Exception:
                    pass
                area.tag_redraw()
    for obj in collection.all_objects:
        result = _select_object(context, obj.name)
        if result.success:
            return LocateResult(True, f"已定位集合 {collection.name} 中的物体 {obj.name}")
    if layer_collection:
        return LocateResult(True, f"已在视图层激活集合：{collection.name}")
    return LocateResult(False, f"集合为空或不在当前视图层：{collection.name}")


@register_locator("SCENE", "VIEW_LAYER")
def _locate_scene(context, node):
    bpy = _bpy()
    scene = bpy.data.scenes.get(node.scene_name or node.data_name or node.owner_name or node.name)
    if scene is None:
        return LocateResult(False, f"找不到场景：{node.name}")
    context.window.scene = scene
    if node.kind == "VIEW_LAYER" and node.view_layer_name in scene.view_layers:
        context.window.view_layer = scene.view_layers[node.view_layer_name]
    return LocateResult(True, f"已切换到：{node.name}")


def locate_reference_node(context, graph, node_id: str, path_id: str = "", step_index: int = -1) -> LocateResult:
    node = graph.nodes.get(node_id)
    if node is None:
        return LocateResult(False, "引用节点已不存在，请重新扫描")
    locator = LOCATORS.get(node.kind)
    if locator is None:
        return LocateResult(False, f"暂不支持定位类型：{node.kind}")
    try:
        if node.kind in {"MATERIAL", "MATERIAL_SLOT"} and path_id:
            path = graph.path_index.get(path_id)
            if path is None or node_id not in path.node_ids:
                return LocateResult(False, "引用图已过期，请重新扫描")
            position = path.node_ids.index(node_id) if step_index < 0 else step_index
            downstream = [graph.nodes[item] for item in path.node_ids[position + 1:] if item in graph.nodes]
            slot = next((item for item in downstream if item.kind == "MATERIAL_SLOT"), None)
            if node.kind == "MATERIAL_SLOT":
                slot = node
            if slot is not None:
                material_name = slot.data_name or node.data_name or node.name
                obj, index = _find_material_host(
                    material_name, slot.owner_name, slot.library_path, slot.slot_index
                )
                if obj is None or index != slot.slot_index:
                    return LocateResult(False, "引用图已过期，请重新扫描")
                selected = _select_object(context, obj.name)
                if not selected.success:
                    return selected
                obj.active_material_index = index
                area = _find_area(context, "NODE_EDITOR")
                if area:
                    area.ui_type = "ShaderNodeTree"
                    area.spaces.active.shader_type = "OBJECT"
                    area.spaces.active.pin = False
                return LocateResult(True, f"已激活 {obj.name} 的材质槽 {index + 1}：{material_name}")
        return locator(context, node)
    except Exception as exc:
        return LocateResult(False, f"定位 {node.name} 失败：{exc}")

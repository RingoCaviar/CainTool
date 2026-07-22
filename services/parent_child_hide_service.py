from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field
from typing import Sequence


ID_PROP = "caintool_parent_child_hide_id"


@dataclass
class SnapshotPayload:
    root_id: str
    root_name: str
    created_at: str
    data: str


@dataclass
class HideHierarchyResult:
    hidden_count: int = 0
    snapshots: list[SnapshotPayload] = field(default_factory=list)
    skipped_without_children: list[str] = field(default_factory=list)

    @property
    def root_count(self) -> int:
        return len(self.snapshots)


def hide_selected_hierarchies(
    selected_objects: Sequence[object],
    *,
    view_layer,
    include_render: bool,
    include_select: bool,
) -> HideHierarchyResult:
    roots = selected_roots(selected_objects)
    if not roots:
        raise ValueError("请至少选择一个物体。")

    result = HideHierarchyResult()

    for root in roots:
        objects = hierarchy_objects(root)
        if len(objects) <= 1:
            result.skipped_without_children.append(root.name)
            continue

        root_id = ensure_object_id(root)
        records = []

        for obj in objects:
            records.append(
                {
                    "id": ensure_object_id(obj),
                    "name": obj.name,
                    "hide_eye": obj.hide_get(view_layer=view_layer),
                    "hide_viewport": obj.hide_viewport,
                    "hide_render": obj.hide_render,
                    "hide_select": obj.hide_select,
                }
            )

        result.snapshots.append(
            SnapshotPayload(
                root_id=root_id,
                root_name=root.name,
                created_at=time.strftime("%Y-%m-%d %H:%M:%S"),
                data=json.dumps(records),
            )
        )

        for obj in objects:
            obj.hide_set(True, view_layer=view_layer)
            obj.hide_viewport = True
            if include_render:
                obj.hide_render = True
            if include_select:
                obj.hide_select = True
            result.hidden_count += 1

    return result


def restore_hierarchy_snapshot(snapshot_data: str, objects, *, view_layer) -> int:
    try:
        records = json.loads(snapshot_data)
    except json.JSONDecodeError as exc:
        raise ValueError("保存的隐藏状态数据已损坏。") from exc

    restored_count = 0

    for record in records:
        obj = find_object_by_id(
            objects,
            record.get("id", ""),
            record.get("name", ""),
        )
        if obj is None:
            continue

        obj.hide_viewport = bool(record.get("hide_viewport", False))
        obj.hide_set(bool(record.get("hide_eye", False)), view_layer=view_layer)
        obj.hide_render = bool(record.get("hide_render", False))
        obj.hide_select = bool(record.get("hide_select", False))
        restored_count += 1

    return restored_count


def selected_roots(selected_objects: Sequence[object]) -> list[object]:
    selected = set(selected_objects)
    return [obj for obj in selected_objects if not has_selected_ancestor(obj, selected)]


def has_selected_ancestor(obj: object, selected: set[object]) -> bool:
    parent = getattr(obj, "parent", None)
    while parent is not None:
        if parent in selected:
            return True
        parent = getattr(parent, "parent", None)
    return False


def hierarchy_objects(root: object) -> list[object]:
    children_recursive = getattr(root, "children_recursive", None)
    if children_recursive is not None:
        return [root, *children_recursive]

    objects = [root]
    for child in getattr(root, "children", ()):
        objects.extend(hierarchy_objects(child))
    return objects


def ensure_object_id(obj: object) -> str:
    object_id = obj.get(ID_PROP)
    if not object_id:
        object_id = uuid.uuid4().hex
        obj[ID_PROP] = object_id
    return object_id


def find_object_by_id(objects, object_id: str, fallback_name: str = ""):
    if object_id:
        id_matches = []
        for obj in objects:
            if obj.get(ID_PROP) == object_id:
                id_matches.append(obj)

        # Blender duplicates custom properties together with an object.  A copied
        # hierarchy can therefore contain the same CainTool IDs as its source.
        # Prefer the name stored in the snapshot when an ID is ambiguous, or a
        # restore may modify an unrelated object that happens to be encountered
        # first in bpy.data.objects.
        if fallback_name:
            for obj in id_matches:
                if getattr(obj, "name", "") == fallback_name:
                    return obj

        # Keep ID-based restoration working when the original object was renamed.
        if len(id_matches) == 1:
            return id_matches[0]

    if fallback_name:
        getter = getattr(objects, "get", None)
        if getter is not None:
            return getter(fallback_name)

        for obj in objects:
            if getattr(obj, "name", "") == fallback_name:
                return obj

    return None

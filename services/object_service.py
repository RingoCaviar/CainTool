from __future__ import annotations

from typing import Iterable, Sequence


def build_name_plan(names: Sequence[str], prefix: str, start_index: int) -> list[tuple[str, str]]:
    normalized_prefix = prefix.strip()
    if not normalized_prefix:
        raise ValueError("Prefix cannot be empty.")
    if start_index < 0:
        raise ValueError("Start index must be zero or greater.")

    plan = []
    for offset, name in enumerate(sorted(names), start=start_index):
        plan.append((name, f"{normalized_prefix}_{offset:03d}"))
    return plan


def rename_objects(objects: Sequence[object], prefix: str, start_index: int) -> list[tuple[str, str]]:
    sorted_objects = sorted(objects, key=lambda item: item.name)
    plan = build_name_plan([obj.name for obj in sorted_objects], prefix, start_index)

    for obj, (_, new_name) in zip(sorted_objects, plan):
        obj.name = new_name

    return plan


def link_objects_to_collection(scene, bpy_data, objects: Sequence[object], collection_name: str):
    normalized_name = collection_name.strip()
    if not normalized_name:
        raise ValueError("Collection name cannot be empty.")

    collection = bpy_data.collections.get(normalized_name)
    if collection is None:
        collection = bpy_data.collections.new(normalized_name)

    if scene.collection.children.get(collection.name) is None:
        scene.collection.children.link(collection)

    linked_count = 0
    for obj in objects:
        if collection not in obj.users_collection:
            collection.objects.link(obj)
            linked_count += 1

    return collection, linked_count


def _ensure_object_mode(context) -> None:
    if context.mode != "OBJECT":
        raise RuntimeError("Switch to Object Mode before running this operator.")


def _with_preserved_selection(context, objects: Sequence[object], operation) -> int:
    original_selection = list(context.selected_objects)
    original_active = context.view_layer.objects.active
    processed = 0

    try:
        for obj in objects:
            for selected in tuple(context.selected_objects):
                selected.select_set(False)

            obj.select_set(True)
            context.view_layer.objects.active = obj
            operation()
            processed += 1
    finally:
        for selected in tuple(context.selected_objects):
            selected.select_set(False)

        for obj in original_selection:
            try:
                obj.select_set(True)
            except RuntimeError:
                pass

        if original_active is not None:
            context.view_layer.objects.active = original_active

    return processed


def apply_transforms(
    context,
    bpy_module,
    objects: Sequence[object],
    *,
    location: bool,
    rotation: bool,
    scale: bool,
) -> int:
    _ensure_object_mode(context)
    if not any((location, rotation, scale)):
        raise ValueError("Enable at least one transform channel.")

    def operation():
        bpy_module.ops.object.transform_apply(
            location=location,
            rotation=rotation,
            scale=scale,
        )

    return _with_preserved_selection(context, tuple(objects), operation)


def set_origin_to_geometry(context, bpy_module, objects: Iterable[object]) -> int:
    _ensure_object_mode(context)

    def operation():
        bpy_module.ops.object.origin_set(type="ORIGIN_GEOMETRY", center="MEDIAN")

    return _with_preserved_selection(context, tuple(objects), operation)

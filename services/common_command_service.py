from __future__ import annotations

from dataclasses import dataclass, field
from typing import Sequence


@dataclass
class ClearAnimationDataResult:
    cleared_count: int = 0
    object_count: int = 0
    skipped: list[str] = field(default_factory=list)

    @property
    def skipped_count(self) -> int:
        return len(self.skipped)


def clear_object_animation_data(objects: Sequence[object]) -> ClearAnimationDataResult:
    result = ClearAnimationDataResult()
    cleared_target_ids: set[int] = set()

    for obj in objects:
        name = getattr(obj, "name", "<unnamed>")
        object_cleared = False
        object_had_animation = False

        for label, target in _iter_animation_data_targets(obj):
            target_id = id(target)
            if target_id in cleared_target_ids:
                object_had_animation = True
                object_cleared = True
                continue

            animation_data = getattr(target, "animation_data", None)

            if animation_data is None:
                continue

            object_had_animation = True
            clear_animation_data = getattr(target, "animation_data_clear", None)
            if clear_animation_data is None:
                result.skipped.append(f"{label}: 不支持删除动画数据")
                continue

            try:
                clear_animation_data()
                _tag_target_updated(target)
            except Exception as exc:  # Blender RNA can report animation data failures generically.
                result.skipped.append(f"{label}: {exc}")
                continue

            cleared_target_ids.add(target_id)
            result.cleared_count += 1
            object_cleared = True

        if object_cleared:
            result.object_count += 1
        elif not object_had_animation:
            result.skipped.append(f"{name}: 没有动画数据")

    return result


def _iter_animation_data_targets(obj: object):
    name = getattr(obj, "name", "<unnamed>")
    yield name, obj

    data = getattr(obj, "data", None)
    if data is None:
        return

    data_name = getattr(data, "name", "数据块")
    yield f"{name} 数据块 {data_name}", data

    shape_keys = getattr(data, "shape_keys", None)
    if shape_keys is not None:
        shape_key_name = getattr(shape_keys, "name", "形态键")
        yield f"{name} 形态键 {shape_key_name}", shape_keys


def _tag_target_updated(target: object) -> None:
    update_tag = getattr(target, "update_tag", None)
    if update_tag is None:
        return

    try:
        update_tag()
    except Exception:
        pass

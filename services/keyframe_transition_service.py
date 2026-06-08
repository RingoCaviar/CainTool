from __future__ import annotations

from dataclasses import dataclass, field
from typing import Sequence

from . import value_input_service


@dataclass
class KeyframeTransitionResult:
    object_count: int = 0
    transition_count: int = 0
    skipped: list[str] = field(default_factory=list)

    @property
    def skipped_count(self) -> int:
        return len(self.skipped)


@dataclass(frozen=True)
class TransitionRule:
    property_name: str
    value: object
parse_value_expression = value_input_service.parse_value_expression


def build_transition_rules(items: Sequence[object]) -> list[TransitionRule]:
    rules: list[TransitionRule] = []

    for item in items:
        property_name = _normalize_property_name(getattr(item, "property_name", ""))
        target_value = value_input_service.read_value_from_holder(item, "target_value")
        rules.append(TransitionRule(property_name=property_name, value=target_value))

    if not rules:
        raise ValueError("请至少添加一条属性规则。")

    return rules


def extract_hovered_property_name(button_prop: object | None = None, active_property=None) -> str:
    identifier = getattr(button_prop, "identifier", "")
    if identifier:
        return _normalize_property_name(identifier)

    if active_property:
        _, data_path, _ = active_property
        leaf_name = str(data_path).rsplit(".", 1)[-1]
        return _normalize_property_name(leaf_name)

    raise ValueError("请先把鼠标悬停到一个属性控件上。")


def read_hovered_property_value(active_property):
    if not active_property:
        raise ValueError("请先把鼠标悬停到一个属性控件上。")

    datablock, data_path, _index = active_property
    resolver = getattr(datablock, "path_resolve", None)
    if resolver is None:
        raise ValueError("当前悬停项无法读取属性值。")

    try:
        return resolver(data_path)
    except Exception as exc:
        raise ValueError("当前悬停项无法读取属性值。") from exc


format_value_expression = value_input_service.format_value_expression


def keyframe_property_transition(
    objects: Sequence[object],
    rules: Sequence[TransitionRule],
    *,
    current_frame: int,
    frame_offset: int,
) -> KeyframeTransitionResult:
    target_frame = current_frame + frame_offset
    result = KeyframeTransitionResult()

    for obj in objects:
        object_changed = False

        for rule in rules:
            property_name = rule.property_name
            target = _resolve_transition_target(obj, property_name)
            if target is None:
                result.skipped.append(f"{obj.name}: missing property '{property_name}'")
                continue

            try:
                original_value = _clone_value(getattr(target, property_name))
                try:
                    target.keyframe_insert(data_path=property_name, frame=current_frame)
                    setattr(target, property_name, rule.value)
                    target.keyframe_insert(data_path=property_name, frame=target_frame)
                finally:
                    setattr(target, property_name, original_value)
            except Exception as exc:  # Blender RNA reports assignment and animation failures generically.
                result.skipped.append(f"{obj.name}.{property_name}: {exc}")
                continue

            result.transition_count += 1
            object_changed = True

        if object_changed:
            result.object_count += 1

    return result


def _normalize_property_name(value: str) -> str:
    normalized = value.strip()
    if normalized.startswith("data."):
        normalized = normalized[5:].strip()
    elif normalized.startswith("object."):
        normalized = normalized[7:].strip()

    if not normalized:
        raise ValueError("Property name cannot be empty.")
    if any(token in normalized for token in (".", "[", "]", "(", ")")):
        raise ValueError(
            "Use a direct property name such as 'energy', 'hide_render', or 'location'."
        )
    return normalized


def _iter_property_targets(obj: object, property_name: str, *, prefer_data_first: bool) -> tuple[object, ...]:
    data = getattr(obj, "data", None)
    candidates: list[object] = []

    if prefer_data_first and data is not None and hasattr(data, property_name):
        candidates.append(data)
    if hasattr(obj, property_name):
        candidates.append(obj)
    if not prefer_data_first and data is not None and hasattr(data, property_name):
        candidates.append(data)

    return tuple(candidates)


def _resolve_transition_target(obj: object, property_name: str) -> object | None:
    candidates = _iter_property_targets(obj, property_name, prefer_data_first=False)
    if candidates:
        return candidates[0]
    return None


def _clone_value(value):
    if hasattr(value, "copy"):
        try:
            return value.copy()
        except TypeError:
            pass
    if isinstance(value, tuple):
        return tuple(value)
    if isinstance(value, list):
        return list(value)
    return value

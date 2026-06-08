from __future__ import annotations

from dataclasses import dataclass, field
from typing import Sequence

from . import value_input_service


@dataclass
class PropertySetResult:
    changed_count: int = 0
    skipped: list[str] = field(default_factory=list)

    @property
    def skipped_count(self) -> int:
        return len(self.skipped)
parse_value_expression = value_input_service.parse_value_expression


def batch_set_property(
    objects: Sequence[object],
    property_name: str,
    value,
) -> PropertySetResult:
    normalized_name = _normalize_property_name(property_name)
    result = PropertySetResult()

    for obj in objects:
        targets = _iter_property_targets(obj, normalized_name, prefer_data_first=True)
        changed = False
        errors: list[str] = []

        for target in targets:
            try:
                current_value = getattr(target, normalized_name)
                typed_value = _coerce_assignment_value(value, current_value)
                setattr(target, normalized_name, typed_value)
                changed = True
            except Exception as exc:  # Blender RNA raises generic runtime errors here.
                errors.append(str(exc))

        if changed:
            result.changed_count += 1
            continue

        if errors:
            result.skipped.append(f"{obj.name}: {errors[0]}")
        else:
            result.skipped.append(f"{obj.name}: missing property '{normalized_name}'")

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


def _coerce_assignment_value(value, current_value):
    if isinstance(current_value, bool):
        return _coerce_bool_value(value)
    return value


def _coerce_bool_value(value):
    if isinstance(value, bool):
        return value

    if isinstance(value, (int, float)):
        if value in {0, 0.0}:
            return False
        if value in {1, 1.0}:
            return True
        return value

    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "1", "yes", "on"}:
            return True
        if normalized in {"false", "0", "no", "off"}:
            return False

    return value

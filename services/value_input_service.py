from __future__ import annotations

import ast
from typing import Sequence


VALUE_TYPE_EXPRESSION = "EXPRESSION"
VALUE_TYPE_BOOL = "BOOL"
VALUE_TYPE_INT = "INT"
VALUE_TYPE_FLOAT = "FLOAT"
VALUE_TYPE_STRING = "STRING"
VALUE_TYPE_ENUM = "ENUM"
VALUE_TYPE_VECTOR_2 = "VECTOR_2"
VALUE_TYPE_VECTOR_3 = "VECTOR_3"
VALUE_TYPE_VECTOR_4 = "VECTOR_4"
VALUE_TYPE_COLOR_3 = "COLOR_3"
VALUE_TYPE_COLOR_4 = "COLOR_4"

VALUE_TYPE_ITEMS = (
    (VALUE_TYPE_EXPRESSION, "表达式", "兼容旧写法，支持 True、1000、(1, 0, 0)、'文本'"),
    (VALUE_TYPE_BOOL, "布尔", "True / False 开关"),
    (VALUE_TYPE_INT, "整数", "整数值"),
    (VALUE_TYPE_FLOAT, "浮点", "浮点数值"),
    (VALUE_TYPE_STRING, "文本", "普通文本内容"),
    (VALUE_TYPE_ENUM, "枚举标识", "枚举属性使用的标识名"),
    (VALUE_TYPE_VECTOR_2, "二维向量", "2 个数值组成的向量"),
    (VALUE_TYPE_VECTOR_3, "三维向量", "3 个数值组成的向量"),
    (VALUE_TYPE_VECTOR_4, "四维向量", "4 个数值组成的向量"),
    (VALUE_TYPE_COLOR_3, "RGB 颜色", "3 通道颜色"),
    (VALUE_TYPE_COLOR_4, "RGBA 颜色", "4 通道颜色"),
)

VECTOR_TYPE_SIZES = {
    VALUE_TYPE_VECTOR_2: 2,
    VALUE_TYPE_VECTOR_3: 3,
    VALUE_TYPE_VECTOR_4: 4,
    VALUE_TYPE_COLOR_3: 3,
    VALUE_TYPE_COLOR_4: 4,
}


def parse_value_expression(expression: str):
    normalized = expression.strip()
    if not normalized:
        raise ValueError("Value expression cannot be empty.")

    try:
        return ast.literal_eval(normalized)
    except (SyntaxError, ValueError):
        lowered = normalized.lower()
        if lowered == "true":
            return True
        if lowered == "false":
            return False
        return normalized


def format_value_expression(value) -> str:
    if isinstance(value, bool):
        return "True" if value else "False"
    if isinstance(value, str):
        return repr(value)
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return repr(value)

    if hasattr(value, "to_tuple"):
        return _format_sequence(value.to_tuple())

    if isinstance(value, tuple):
        return _format_sequence(value)
    if isinstance(value, list):
        return _format_sequence(tuple(value))

    if hasattr(value, "__iter__") and not isinstance(value, (bytes, bytearray, dict)):
        try:
            return _format_sequence(tuple(value))
        except TypeError:
            pass

    return repr(value)


def infer_value_type(value, *, button_prop=None) -> str:
    button_prop_type = _infer_value_type_from_button_prop(button_prop)
    if button_prop_type is not None:
        return button_prop_type

    if isinstance(value, bool):
        return VALUE_TYPE_BOOL
    if isinstance(value, int):
        return VALUE_TYPE_INT
    if isinstance(value, float):
        return VALUE_TYPE_FLOAT
    if isinstance(value, str):
        return VALUE_TYPE_STRING

    sequence = _as_numeric_sequence(value)
    if sequence is not None:
        return {
            2: VALUE_TYPE_VECTOR_2,
            3: VALUE_TYPE_VECTOR_3,
            4: VALUE_TYPE_VECTOR_4,
        }.get(len(sequence), VALUE_TYPE_EXPRESSION)

    return VALUE_TYPE_EXPRESSION


def assign_value_to_holder(holder, base_name: str, value, *, button_prop=None) -> str:
    value_type = infer_value_type(value, button_prop=button_prop)
    setattr(holder, f"{base_name}_type", value_type)
    setattr(holder, base_name, format_value_expression(value))

    if value_type == VALUE_TYPE_BOOL:
        setattr(holder, f"{base_name}_bool", bool(value))
    elif value_type == VALUE_TYPE_INT:
        setattr(holder, f"{base_name}_int", int(value))
    elif value_type == VALUE_TYPE_FLOAT:
        setattr(holder, f"{base_name}_float", float(value))
    elif value_type == VALUE_TYPE_STRING:
        setattr(holder, f"{base_name}_text", str(value))
    elif value_type == VALUE_TYPE_ENUM:
        setattr(holder, f"{base_name}_enum", str(value))
    elif value_type in VECTOR_TYPE_SIZES:
        values = _coerce_sequence(value, VECTOR_TYPE_SIZES[value_type])
        suffix = "color" if value_type.startswith("COLOR") else "vector"
        setattr(holder, f"{base_name}_{suffix}_{VECTOR_TYPE_SIZES[value_type]}", values)

    return value_type


def read_value_from_holder(holder, base_name: str):
    value_type = getattr(holder, f"{base_name}_type", VALUE_TYPE_EXPRESSION)

    if value_type == VALUE_TYPE_BOOL:
        return bool(getattr(holder, f"{base_name}_bool"))
    if value_type == VALUE_TYPE_INT:
        return int(getattr(holder, f"{base_name}_int"))
    if value_type == VALUE_TYPE_FLOAT:
        return float(getattr(holder, f"{base_name}_float"))
    if value_type == VALUE_TYPE_STRING:
        return str(getattr(holder, f"{base_name}_text"))
    if value_type == VALUE_TYPE_ENUM:
        return str(getattr(holder, f"{base_name}_enum"))
    if value_type in {VALUE_TYPE_VECTOR_2, VALUE_TYPE_VECTOR_3, VALUE_TYPE_VECTOR_4}:
        size = VECTOR_TYPE_SIZES[value_type]
        return tuple(getattr(holder, f"{base_name}_vector_{size}"))
    if value_type in {VALUE_TYPE_COLOR_3, VALUE_TYPE_COLOR_4}:
        size = VECTOR_TYPE_SIZES[value_type]
        return tuple(getattr(holder, f"{base_name}_color_{size}"))

    return parse_value_expression(getattr(holder, base_name, ""))


def _infer_value_type_from_button_prop(button_prop) -> str | None:
    if button_prop is None:
        return None

    prop_type = str(getattr(button_prop, "type", "")).upper()
    subtype = str(getattr(button_prop, "subtype", "")).upper()

    try:
        array_length = int(getattr(button_prop, "array_length", 0) or 0)
    except (TypeError, ValueError):
        array_length = 0

    if array_length in {2, 3, 4}:
        if subtype in {"COLOR", "COLOR_GAMMA"} and array_length in {3, 4}:
            return VALUE_TYPE_COLOR_3 if array_length == 3 else VALUE_TYPE_COLOR_4
        return {
            2: VALUE_TYPE_VECTOR_2,
            3: VALUE_TYPE_VECTOR_3,
            4: VALUE_TYPE_VECTOR_4,
        }[array_length]

    if prop_type == "BOOLEAN":
        return VALUE_TYPE_BOOL
    if prop_type == "INT":
        return VALUE_TYPE_INT
    if prop_type == "FLOAT":
        return VALUE_TYPE_FLOAT
    if prop_type == "STRING":
        return VALUE_TYPE_STRING
    if prop_type == "ENUM":
        return VALUE_TYPE_ENUM

    return None


def _as_numeric_sequence(value) -> tuple[float, ...] | None:
    sequence = None

    if hasattr(value, "to_tuple"):
        sequence = value.to_tuple()
    elif isinstance(value, tuple):
        sequence = value
    elif isinstance(value, list):
        sequence = tuple(value)
    elif hasattr(value, "__iter__") and not isinstance(value, (str, bytes, bytearray, dict)):
        try:
            sequence = tuple(value)
        except TypeError:
            sequence = None

    if sequence is None or len(sequence) not in {2, 3, 4}:
        return None

    if not all(isinstance(item, (int, float)) and not isinstance(item, bool) for item in sequence):
        return None

    return tuple(float(item) for item in sequence)


def _coerce_sequence(value, size: int) -> tuple[float, ...]:
    sequence = _as_numeric_sequence(value) or ()
    padded = tuple(sequence[:size]) + (0.0,) * max(0, size - len(sequence))
    return tuple(float(item) for item in padded[:size])


def _format_sequence(values: Sequence[object]) -> str:
    formatted = ", ".join(format_value_expression(item) for item in values)
    if len(values) == 1:
        formatted = f"{formatted},"
    return f"({formatted})"

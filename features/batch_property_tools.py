import bpy

from ..services import batch_property_service, keyframe_transition_service, value_input_service
from .base import FeatureSection


class CAINTOOL_OT_set_batch_property_from_context(bpy.types.Operator):
    bl_idname = "caintool.set_batch_property_from_context"
    bl_label = "添加到 CainTool 批量设置属性"
    bl_description = "把当前右键属性和当前值填入 CainTool 的批量设置属性"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return _can_add_context_property(context)

    def execute(self, context):
        try:
            property_name, target_value = _read_context_batch_property(context)
        except ValueError as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}

        settings = context.scene.caintool
        settings.batch_property_name = property_name
        value_input_service.assign_value_to_holder(
            settings,
            "batch_property_value",
            target_value,
            button_prop=getattr(context, "button_prop", None),
        )
        _tag_batch_property_redraw(context)
        self.report({"INFO"}, f"已填入批量属性：{property_name} = {target_value}")
        return {"FINISHED"}


class CAINTOOL_OT_batch_set_property(bpy.types.Operator):
    bl_idname = "caintool.batch_set_property"
    bl_label = "执行批量设置"
    bl_description = "给所有选中物体统一设置同一个属性值"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return context.mode == "OBJECT" and bool(context.selected_objects)

    def execute(self, context):
        settings = context.scene.caintool

        try:
            target_value = value_input_service.read_value_from_holder(
                settings,
                "batch_property_value",
            )
            result = batch_property_service.batch_set_property(
                context.selected_objects,
                settings.batch_property_name,
                target_value,
            )
        except ValueError as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}

        if result.changed_count == 0:
            detail = result.skipped[0] if result.skipped else "没有找到可修改的属性。"
            self.report({"ERROR"}, detail)
            return {"CANCELLED"}

        if result.skipped_count:
            self.report(
                {"WARNING"},
                f"已修改 {result.changed_count} 个物体，跳过 {result.skipped_count} 个。",
            )
        else:
            self.report({"INFO"}, f"已修改 {result.changed_count} 个物体。")

        return {"FINISHED"}


def draw_feature(layout, context) -> None:
    settings = context.scene.caintool

    col = layout.column(align=True)
    col.prop(settings, "batch_property_name")
    col.prop(settings, "batch_property_value_type")
    _draw_value_input(col, settings, "batch_property_value")
    col.label(text="支持在属性上右键填入属性名和当前值。", icon="EYEDROPPER")
    col.label(text="表达式模式兼容旧写法，其他模式会显示专用控件。", icon="INFO")
    col.operator(CAINTOOL_OT_batch_set_property.bl_idname, icon="CHECKMARK")


def register() -> None:
    if hasattr(bpy.types, "UI_MT_button_context_menu"):
        bpy.types.UI_MT_button_context_menu.append(draw_button_context_menu)


def unregister() -> None:
    if hasattr(bpy.types, "UI_MT_button_context_menu"):
        bpy.types.UI_MT_button_context_menu.remove(draw_button_context_menu)


def draw_button_context_menu(self, context) -> None:
    if not _can_add_context_property(context):
        return

    self.layout.separator()
    self.layout.operator(
        CAINTOOL_OT_set_batch_property_from_context.bl_idname,
        icon="MODIFIER",
    )


def _can_add_context_property(context) -> bool:
    button_prop = getattr(context, "button_prop", None)
    active_property = getattr(context, "property", None)

    if button_prop is not None:
        if getattr(button_prop, "is_readonly", False):
            return False
        return True

    return bool(active_property)


def _read_context_batch_property(context) -> tuple[str, str]:
    active_property = getattr(context, "property", None)
    button_prop = getattr(context, "button_prop", None)
    pointer = getattr(context, "button_pointer", None)

    property_name = keyframe_transition_service.extract_hovered_property_name(
        button_prop=button_prop,
        active_property=active_property,
    )

    if active_property:
        value = keyframe_transition_service.read_hovered_property_value(active_property)
    elif pointer is not None:
        value = keyframe_transition_service.read_hovered_property_value(
            (pointer, getattr(button_prop, "identifier", property_name), -1)
        )
    else:
        raise ValueError("当前右键属性无法读取数值。")

    return property_name, keyframe_transition_service.format_value_expression(value)


def _draw_value_input(layout, holder, base_name: str) -> None:
    value_type = getattr(holder, f"{base_name}_type")

    if value_type == value_input_service.VALUE_TYPE_BOOL:
        layout.prop(holder, f"{base_name}_bool", text="目标值")
        return
    if value_type == value_input_service.VALUE_TYPE_INT:
        layout.prop(holder, f"{base_name}_int", text="目标值")
        return
    if value_type == value_input_service.VALUE_TYPE_FLOAT:
        layout.prop(holder, f"{base_name}_float", text="目标值")
        return
    if value_type == value_input_service.VALUE_TYPE_STRING:
        layout.prop(holder, f"{base_name}_text", text="目标值")
        return
    if value_type == value_input_service.VALUE_TYPE_ENUM:
        layout.prop(holder, f"{base_name}_enum", text="枚举标识")
        return
    if value_type == value_input_service.VALUE_TYPE_VECTOR_2:
        layout.prop(holder, f"{base_name}_vector_2", text="目标值")
        return
    if value_type == value_input_service.VALUE_TYPE_VECTOR_3:
        layout.prop(holder, f"{base_name}_vector_3", text="目标值")
        return
    if value_type == value_input_service.VALUE_TYPE_VECTOR_4:
        layout.prop(holder, f"{base_name}_vector_4", text="目标值")
        return
    if value_type == value_input_service.VALUE_TYPE_COLOR_3:
        layout.prop(holder, f"{base_name}_color_3", text="目标值")
        return
    if value_type == value_input_service.VALUE_TYPE_COLOR_4:
        layout.prop(holder, f"{base_name}_color_4", text="目标值")
        return

    layout.prop(holder, base_name, text="目标值表达式")


def _tag_batch_property_redraw(context) -> None:
    window_manager = getattr(context, "window_manager", None)
    if window_manager is None:
        return

    for window in window_manager.windows:
        screen = getattr(window, "screen", None)
        if screen is None:
            continue

        for area in screen.areas:
            if area.type in {"VIEW_3D", "PROPERTIES"}:
                area.tag_redraw()


FEATURE = FeatureSection(
    key="batch_property_tools",
    label="批量设置属性",
    icon="MODIFIER",
    description="给所有选中物体批量设置相同属性值。",
    draw=draw_feature,
)

CLASSES = (
    CAINTOOL_OT_set_batch_property_from_context,
    CAINTOOL_OT_batch_set_property,
)

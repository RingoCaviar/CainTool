import bpy

from ..services import keyframe_transition_service, value_input_service
from .base import FeatureSection


class CAINTOOL_OT_add_transition_rule_from_context(bpy.types.Operator):
    bl_idname = "caintool.add_transition_rule_from_context"
    bl_label = "添加到 CainTool 渐入渐出规则"
    bl_description = "把当前右键属性添加到 CainTool 的渐入渐出规则列表"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return _can_add_context_property(context)

    def execute(self, context):
        try:
            property_name, target_value = _read_context_rule(context)
        except ValueError as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}

        rules = context.scene.caintool_transition_rules
        item = rules.add()
        item.property_name = property_name
        value_input_service.assign_value_to_holder(
            item,
            "target_value",
            target_value,
            button_prop=getattr(context, "button_prop", None),
        )
        context.scene.caintool_transition_rule_index = len(rules) - 1
        _tag_transition_rule_redraw(context)
        self.report({"INFO"}, f"已添加规则：{property_name} -> {target_value}")
        return {"FINISHED"}


class CAINTOOL_OT_add_transition_rule(bpy.types.Operator):
    bl_idname = "caintool.add_transition_rule"
    bl_label = "添加规则"
    bl_description = "新增一条属性渐入渐出规则"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        rules = context.scene.caintool_transition_rules
        item = rules.add()
        item.property_name = "hide_render"
        item.target_value_type = value_input_service.VALUE_TYPE_BOOL
        item.target_value_bool = True
        item.target_value = "True"
        context.scene.caintool_transition_rule_index = len(rules) - 1
        _tag_transition_rule_redraw(context)
        return {"FINISHED"}


class CAINTOOL_OT_remove_transition_rule(bpy.types.Operator):
    bl_idname = "caintool.remove_transition_rule"
    bl_label = "删除规则"
    bl_description = "删除指定的属性渐入渐出规则"
    bl_options = {"REGISTER", "UNDO"}

    rule_index: bpy.props.IntProperty(default=-1)

    @classmethod
    def poll(cls, context):
        return bool(context.scene.caintool_transition_rules)

    def execute(self, context):
        rules = context.scene.caintool_transition_rules
        index = self.rule_index
        if index < 0 or index >= len(rules):
            index = len(rules) - 1

        rules.remove(index)
        context.scene.caintool_transition_rule_index = min(
            max(0, index),
            max(0, len(rules) - 1),
        )
        _tag_transition_rule_redraw(context)
        return {"FINISHED"}


class CAINTOOL_OT_keyframe_property_transition(bpy.types.Operator):
    bl_idname = "caintool.keyframe_property_transition"
    bl_label = "执行渐入渐出"
    bl_description = "按规则为选中物体插入当前帧和偏移帧关键帧"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return context.mode == "OBJECT" and bool(context.selected_objects)

    def execute(self, context):
        settings = context.scene.caintool

        try:
            rules = keyframe_transition_service.build_transition_rules(
                context.scene.caintool_transition_rules
            )
            result = keyframe_transition_service.keyframe_property_transition(
                context.selected_objects,
                rules,
                current_frame=context.scene.frame_current,
                frame_offset=settings.transition_frame_offset,
            )
        except ValueError as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}

        if result.transition_count == 0:
            detail = result.skipped[0] if result.skipped else "没有创建任何关键帧。"
            self.report({"ERROR"}, detail)
            return {"CANCELLED"}

        context.view_layer.update()

        if result.skipped_count:
            self.report(
                {"WARNING"},
                f"已在 {result.object_count} 个物体上创建 {result.transition_count} 组过渡，跳过 {result.skipped_count} 个。",
            )
        else:
            self.report(
                {"INFO"},
                f"已在 {result.object_count} 个物体上创建 {result.transition_count} 组过渡。",
            )

        return {"FINISHED"}


def draw_feature(layout, context) -> None:
    settings = context.scene.caintool
    rules = context.scene.caintool_transition_rules

    col = layout.column(align=True)
    col.prop(settings, "transition_frame_offset")
    col.label(text="每条规则都可以单独设置目标值类型和内容。", icon="INFO")

    action_row = col.row(align=True)
    action_row.operator(CAINTOOL_OT_add_transition_rule.bl_idname, icon="ADD")

    if rules:
        for index, item in enumerate(rules):
            box = col.box()
            header = box.row(align=True)
            header.label(text=f"规则 {index + 1}", icon="DECORATE_KEYFRAME")
            remove_op = header.operator(
                CAINTOOL_OT_remove_transition_rule.bl_idname,
                text="",
                icon="X",
            )
            remove_op.rule_index = index
            box.prop(item, "property_name")
            box.prop(item, "target_value_type")
            _draw_value_input(box, item, "target_value")
    else:
        col.label(text="请先添加至少一条规则，或在别的属性上右键添加。", icon="INFO")

    col.operator(CAINTOOL_OT_keyframe_property_transition.bl_idname, icon="ACTION")


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
        CAINTOOL_OT_add_transition_rule_from_context.bl_idname,
        icon="DECORATE_KEYFRAME",
    )


def _can_add_context_property(context) -> bool:
    button_prop = getattr(context, "button_prop", None)
    active_property = getattr(context, "property", None)

    if button_prop is not None:
        return bool(getattr(button_prop, "is_animatable", False))

    if active_property:
        return True

    return False


def _read_context_rule(context) -> tuple[str, str]:
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


def _tag_transition_rule_redraw(context) -> None:
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
    key="keyframe_transition_tools",
    label="渐入渐出",
    icon="DECORATE_KEYFRAME",
    description="按多条属性规则为选中物体创建偏移关键帧过渡。",
    draw=draw_feature,
)

CLASSES = (
    CAINTOOL_OT_add_transition_rule_from_context,
    CAINTOOL_OT_add_transition_rule,
    CAINTOOL_OT_remove_transition_rule,
    CAINTOOL_OT_keyframe_property_transition,
)

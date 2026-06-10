import bpy

from ..services import common_command_service
from .base import FeatureSection


class CAINTOOL_OT_clear_selected_animation_data(bpy.types.Operator):
    bl_idname = "caintool.clear_selected_animation_data"
    bl_label = "删除选中物体动画"
    bl_description = "删除选中物体及其数据块上的动画数据"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return context.mode == "OBJECT" and bool(context.selected_objects)

    def execute(self, context):
        result = common_command_service.clear_object_animation_data(
            context.selected_objects
        )

        if result.cleared_count == 0:
            detail = result.skipped[0] if result.skipped else "没有可删除的动画数据。"
            self.report({"WARNING"}, detail)
            return {"CANCELLED"}

        if result.skipped_count:
            self.report(
                {"WARNING"},
                f"已删除 {result.object_count} 个物体关联的 {result.cleared_count} 处动画数据，跳过 {result.skipped_count} 项。",
            )
        else:
            self.report(
                {"INFO"},
                f"已删除 {result.object_count} 个物体关联的 {result.cleared_count} 处动画数据。",
            )

        _refresh_animation_ui(context)
        return {"FINISHED"}


def draw_feature(layout, context) -> None:
    del context

    col = layout.column(align=True)
    col.operator(CAINTOOL_OT_clear_selected_animation_data.bl_idname, icon="TRASH")


FEATURE = FeatureSection(
    key="common_command_tools",
    label="常用命令",
    icon="TOOL_SETTINGS",
    description="放置高频的一键操作命令。",
    draw=draw_feature,
)

CLASSES = (CAINTOOL_OT_clear_selected_animation_data,)


def _refresh_animation_ui(context) -> None:
    view_layer = getattr(context, "view_layer", None)
    if view_layer is not None:
        view_layer.update()

    window_manager = getattr(context, "window_manager", None)
    if window_manager is None:
        return

    redraw_area_types = {
        "DOPESHEET_EDITOR",
        "GRAPH_EDITOR",
        "NLA_EDITOR",
        "OUTLINER",
        "PROPERTIES",
        "TIMELINE",
        "VIEW_3D",
    }

    for window in window_manager.windows:
        screen = getattr(window, "screen", None)
        if screen is None:
            continue

        for area in screen.areas:
            if area.type in redraw_area_types:
                area.tag_redraw()

    try:
        bpy.ops.wm.redraw_timer(type="DRAW_WIN_SWAP", iterations=1)
    except RuntimeError:
        pass

import bpy

from ..services import parent_child_hide_service
from .base import FeatureSection


class CAINTOOL_PG_parent_child_hide_snapshot(bpy.types.PropertyGroup):
    root_id: bpy.props.StringProperty(name="Root ID")
    root_name: bpy.props.StringProperty(name="Root Name")
    created_at: bpy.props.StringProperty(name="Created At")
    data: bpy.props.StringProperty(name="Visibility Data")


class CAINTOOL_OT_hide_parent_child_hierarchy(bpy.types.Operator):
    bl_idname = "caintool.hide_parent_child_hierarchy"
    bl_label = "隐藏父子级"
    bl_description = "隐藏选中的父级物体及其全部子级，并记录原始可见状态"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return context.mode == "OBJECT" and bool(context.selected_objects)

    def execute(self, context):
        settings = context.scene.caintool

        try:
            result = parent_child_hide_service.hide_selected_hierarchies(
                context.selected_objects,
                view_layer=context.view_layer,
                include_render=settings.parent_child_hide_include_render,
                include_select=settings.parent_child_hide_include_select,
            )
        except ValueError as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}

        if not result.snapshots:
            self.report({"WARNING"}, "所选物体没有可隐藏的子级层级。")
            return {"CANCELLED"}

        snapshots = context.scene.caintool_parent_child_hide_snapshots
        for payload in result.snapshots:
            snapshot = _find_snapshot(snapshots, payload.root_id)
            if snapshot is None:
                snapshot = snapshots.add()

            snapshot.root_id = payload.root_id
            snapshot.root_name = payload.root_name
            snapshot.created_at = payload.created_at
            snapshot.data = payload.data

        if result.skipped_without_children:
            names = "、".join(result.skipped_without_children)
            self.report({"WARNING"}, f"以下物体没有子级，已跳过：{names}")

        self.report(
            {"INFO"},
            f"已隐藏 {result.hidden_count} 个物体，共记录 {result.root_count} 组层级。",
        )
        return {"FINISHED"}


class CAINTOOL_OT_restore_parent_child_hierarchy(bpy.types.Operator):
    bl_idname = "caintool.restore_parent_child_hierarchy"
    bl_label = "恢复这一组"
    bl_description = "恢复这一组父子级的原始可见状态"
    bl_options = {"REGISTER", "UNDO"}

    root_id: bpy.props.StringProperty()

    def execute(self, context):
        snapshots = context.scene.caintool_parent_child_hide_snapshots
        snapshot_index = -1
        snapshot = None

        for index, item in enumerate(snapshots):
            if item.root_id == self.root_id:
                snapshot_index = index
                snapshot = item
                break

        if snapshot is None:
            self.report({"WARNING"}, "没有找到对应的隐藏记录。")
            return {"CANCELLED"}

        try:
            restored_count = parent_child_hide_service.restore_hierarchy_snapshot(
                snapshot.data,
                bpy.data.objects,
                view_layer=context.view_layer,
            )
        except ValueError as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}

        snapshots.remove(snapshot_index)
        self.report({"INFO"}, f"已恢复 {restored_count} 个物体。")
        return {"FINISHED"}


class CAINTOOL_OT_restore_all_parent_child_hierarchies(bpy.types.Operator):
    bl_idname = "caintool.restore_all_parent_child_hierarchies"
    bl_label = "全部恢复"
    bl_description = "恢复当前保存的全部父子级隐藏记录"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        snapshots = context.scene.caintool_parent_child_hide_snapshots
        if not snapshots:
            self.report({"WARNING"}, "当前没有可恢复的隐藏记录。")
            return {"CANCELLED"}

        restored_total = 0
        for snapshot in list(snapshots):
            restored_total += parent_child_hide_service.restore_hierarchy_snapshot(
                snapshot.data,
                bpy.data.objects,
                view_layer=context.view_layer,
            )

        snapshots.clear()
        self.report({"INFO"}, f"已恢复 {restored_total} 个物体。")
        return {"FINISHED"}


def draw_feature(layout, context) -> None:
    settings = context.scene.caintool
    snapshots = context.scene.caintool_parent_child_hide_snapshots

    col = layout.column(align=True)
    col.operator(CAINTOOL_OT_hide_parent_child_hierarchy.bl_idname, icon="HIDE_ON")
    col.prop(settings, "parent_child_hide_include_render")
    col.prop(settings, "parent_child_hide_include_select")

    if snapshots:
        layout.separator(factor=0.75)
        layout.operator(
            CAINTOOL_OT_restore_all_parent_child_hierarchies.bl_idname,
            icon="HIDE_OFF",
        )

        list_col = layout.column(align=True)
        list_col.label(text="已保存的隐藏记录：", icon="BOOKMARKS")
        for item in snapshots:
            row = list_col.row(align=True)
            op = row.operator(
                CAINTOOL_OT_restore_parent_child_hierarchy.bl_idname,
                text=f"恢复 {item.root_name}",
                icon="LOOP_BACK",
            )
            op.root_id = item.root_id
    else:
        layout.label(text="当前没有已保存的隐藏记录。", icon="INFO")


def register() -> None:
    bpy.types.Scene.caintool_parent_child_hide_snapshots = bpy.props.CollectionProperty(
        type=CAINTOOL_PG_parent_child_hide_snapshot
    )


def unregister() -> None:
    del bpy.types.Scene.caintool_parent_child_hide_snapshots


def _find_snapshot(snapshots, root_id: str):
    for item in snapshots:
        if item.root_id == root_id:
            return item
    return None


FEATURE = FeatureSection(
    key="parent_child_hide_tools",
    label="父子级隐藏",
    icon="OUTLINER_OB_GROUP_INSTANCE",
    description="隐藏选中的父级层级，并支持按记录恢复原始可见状态。",
    draw=draw_feature,
)

CLASSES = (
    CAINTOOL_PG_parent_child_hide_snapshot,
    CAINTOOL_OT_hide_parent_child_hierarchy,
    CAINTOOL_OT_restore_parent_child_hierarchy,
    CAINTOOL_OT_restore_all_parent_child_hierarchies,
)

import bpy

from ..services import object_service
from .base import FeatureSection


class CAINTOOL_OT_rename_selected(bpy.types.Operator):
    bl_idname = "caintool.rename_selected"
    bl_label = "Rename Selected"
    bl_description = "Rename selected objects using the configured prefix and start index"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return context.mode == "OBJECT" and bool(context.selected_objects)

    def execute(self, context):
        settings = context.scene.caintool

        try:
            renamed = object_service.rename_objects(
                context.selected_objects,
                prefix=settings.rename_prefix,
                start_index=settings.rename_start_index,
            )
        except ValueError as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}

        self.report({"INFO"}, f"Renamed {len(renamed)} object(s).")
        return {"FINISHED"}


class CAINTOOL_OT_apply_transforms_selected(bpy.types.Operator):
    bl_idname = "caintool.apply_transforms_selected"
    bl_label = "Apply Transforms"
    bl_description = "Apply the selected transform channels to every selected object"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return context.mode == "OBJECT" and bool(context.selected_objects)

    def execute(self, context):
        settings = context.scene.caintool

        try:
            processed = object_service.apply_transforms(
                context=context,
                bpy_module=bpy,
                objects=context.selected_objects,
                location=settings.apply_location,
                rotation=settings.apply_rotation,
                scale=settings.apply_scale,
            )
        except (RuntimeError, ValueError) as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}

        self.report({"INFO"}, f"Applied transforms to {processed} object(s).")
        return {"FINISHED"}


class CAINTOOL_OT_origin_to_geometry_selected(bpy.types.Operator):
    bl_idname = "caintool.origin_to_geometry_selected"
    bl_label = "Origin To Geometry"
    bl_description = "Set origin to geometry for each selected object"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return context.mode == "OBJECT" and bool(context.selected_objects)

    def execute(self, context):
        try:
            processed = object_service.set_origin_to_geometry(
                context=context,
                bpy_module=bpy,
                objects=context.selected_objects,
            )
        except RuntimeError as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}

        self.report({"INFO"}, f"Updated origin for {processed} object(s).")
        return {"FINISHED"}


def draw_feature(layout, context) -> None:
    settings = context.scene.caintool

    rename_col = layout.column(align=True)
    rename_col.prop(settings, "rename_prefix")
    rename_col.prop(settings, "rename_start_index")
    rename_col.operator(CAINTOOL_OT_rename_selected.bl_idname, icon="OUTLINER_OB_EMPTY")

    layout.separator(factor=0.75)

    transform_col = layout.column(align=True)
    transform_row = transform_col.row(align=True)
    transform_row.prop(settings, "apply_location", toggle=True)
    transform_row.prop(settings, "apply_rotation", toggle=True)
    transform_row.prop(settings, "apply_scale", toggle=True)
    transform_col.operator(CAINTOOL_OT_apply_transforms_selected.bl_idname, icon="OBJECT_ORIGIN")
    transform_col.operator(CAINTOOL_OT_origin_to_geometry_selected.bl_idname, icon="PIVOT_MEDIAN")


FEATURE = FeatureSection(
    key="object_tools",
    label="Object Tools",
    icon="OBJECT_DATA",
    description="Batch rename and transform helpers for selected objects.",
    draw=draw_feature,
)

CLASSES = (
    CAINTOOL_OT_rename_selected,
    CAINTOOL_OT_apply_transforms_selected,
    CAINTOOL_OT_origin_to_geometry_selected,
)

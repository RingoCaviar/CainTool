import bpy

from ..services import object_service
from .base import FeatureSection


class CAINTOOL_OT_link_selection_to_collection(bpy.types.Operator):
    bl_idname = "caintool.link_selection_to_collection"
    bl_label = "Link Selection"
    bl_description = "Link selected objects into the configured collection without unlinking them elsewhere"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return context.mode == "OBJECT" and bool(context.selected_objects)

    def execute(self, context):
        settings = context.scene.caintool

        try:
            collection, linked_count = object_service.link_objects_to_collection(
                scene=context.scene,
                bpy_data=bpy.data,
                objects=context.selected_objects,
                collection_name=settings.target_collection_name,
            )
        except ValueError as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}

        self.report(
            {"INFO"},
            f"Linked {linked_count} object(s) to collection '{collection.name}'.",
        )
        return {"FINISHED"}


def draw_feature(layout, context) -> None:
    settings = context.scene.caintool

    col = layout.column(align=True)
    col.prop(settings, "target_collection_name")
    col.operator(CAINTOOL_OT_link_selection_to_collection.bl_idname, icon="OUTLINER_COLLECTION")


FEATURE = FeatureSection(
    key="collection_tools",
    label="Collection Tools",
    icon="OUTLINER_COLLECTION",
    description="Manage collection linking for the current object selection.",
    draw=draw_feature,
)

CLASSES = (CAINTOOL_OT_link_selection_to_collection,)

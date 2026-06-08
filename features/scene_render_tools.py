import bpy

from ..services import scene_render_service
from .base import FeatureSection


class CAINTOOL_OT_apply_scene_samples(bpy.types.Operator):
    bl_idname = "caintool.apply_scene_samples"
    bl_label = "应用场景参数"
    bl_description = "把当前设置应用到文件中的所有场景"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        settings = context.scene.caintool

        try:
            result = scene_render_service.apply_cycles_samples(
                bpy.data.scenes,
                render_samples=settings.cycles_render_samples,
                viewport_samples=settings.cycles_viewport_samples,
                adaptive_threshold=settings.cycles_adaptive_threshold,
            )
        except ValueError as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}

        if result.updated_count == 0:
            detail = result.skipped[0] if result.skipped else "没有可更新的 Cycles 场景。"
            self.report({"ERROR"}, detail)
            return {"CANCELLED"}

        if result.skipped_count:
            self.report(
                {"WARNING"},
                f"已更新 {result.updated_count} 个 Cycles 场景，跳过 {result.skipped_count} 个。",
            )
        else:
            self.report({"INFO"}, f"已更新 {result.updated_count} 个 Cycles 场景。")

        return {"FINISHED"}


def draw_feature(layout, context) -> None:
    settings = context.scene.caintool
    del context

    col = layout.column(align=True)
    col.prop(settings, "cycles_render_samples")
    col.prop(settings, "cycles_viewport_samples")
    col.prop(settings, "cycles_adaptive_threshold")
    col.operator(CAINTOOL_OT_apply_scene_samples.bl_idname, icon="RENDER_STILL")


FEATURE = FeatureSection(
    key="scene_render_tools",
    label="修改场景参数",
    icon="SCENE_DATA",
    description="批量修改所有场景的 Cycles 采样参数。",
    draw=draw_feature,
)

CLASSES = (CAINTOOL_OT_apply_scene_samples,)

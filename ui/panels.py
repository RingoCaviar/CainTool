import bpy

from ..constants import PANEL_CATEGORY, UI_REGION, VIEW3D_SPACE
from ..features import (
    batch_property_tools,
    keyframe_transition_tools,
    parent_child_hide_tools,
    render_sync_tools,
    scene_render_tools,
)


class CAINTOOL_PT_toolkit(bpy.types.Panel):
    bl_idname = "CAINTOOL_PT_toolkit"
    bl_label = "CainTool"
    bl_space_type = VIEW3D_SPACE
    bl_region_type = UI_REGION
    bl_category = PANEL_CATEGORY

    def draw(self, context):
        del context
        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False
        layout.label(text="下方模块可单独展开使用。", icon="TOOL_SETTINGS")


class CAINTOOL_PT_batch_property(bpy.types.Panel):
    bl_idname = "CAINTOOL_PT_batch_property"
    bl_label = "批量设置属性"
    bl_space_type = VIEW3D_SPACE
    bl_region_type = UI_REGION
    bl_category = PANEL_CATEGORY
    bl_parent_id = CAINTOOL_PT_toolkit.bl_idname
    bl_options = {"DEFAULT_CLOSED"}

    def draw_header(self, context):
        del context
        self.layout.label(text="", icon="MODIFIER")

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False
        batch_property_tools.draw_feature(layout, context)


class CAINTOOL_PT_keyframe_transition(bpy.types.Panel):
    bl_idname = "CAINTOOL_PT_keyframe_transition"
    bl_label = "渐入渐出"
    bl_space_type = VIEW3D_SPACE
    bl_region_type = UI_REGION
    bl_category = PANEL_CATEGORY
    bl_parent_id = CAINTOOL_PT_toolkit.bl_idname
    bl_options = {"DEFAULT_CLOSED"}

    def draw_header(self, context):
        del context
        self.layout.label(text="", icon="DECORATE_KEYFRAME")

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False
        keyframe_transition_tools.draw_feature(layout, context)


class CAINTOOL_PT_scene_render(bpy.types.Panel):
    bl_idname = "CAINTOOL_PT_scene_render"
    bl_label = "修改场景参数"
    bl_space_type = VIEW3D_SPACE
    bl_region_type = UI_REGION
    bl_category = PANEL_CATEGORY
    bl_parent_id = CAINTOOL_PT_toolkit.bl_idname
    bl_options = {"DEFAULT_CLOSED"}

    def draw_header(self, context):
        del context
        self.layout.label(text="", icon="SCENE_DATA")

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False
        scene_render_tools.draw_feature(layout, context)


class CAINTOOL_PT_parent_child_hide(bpy.types.Panel):
    bl_idname = "CAINTOOL_PT_parent_child_hide"
    bl_label = "父子级隐藏"
    bl_space_type = VIEW3D_SPACE
    bl_region_type = UI_REGION
    bl_category = PANEL_CATEGORY
    bl_parent_id = CAINTOOL_PT_toolkit.bl_idname
    bl_options = {"DEFAULT_CLOSED"}

    def draw_header(self, context):
        del context
        self.layout.label(text="", icon="OUTLINER_OB_GROUP_INSTANCE")

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False
        parent_child_hide_tools.draw_feature(layout, context)


class CAINTOOL_PT_render_sync(bpy.types.Panel):
    bl_idname = "CAINTOOL_PT_render_sync"
    bl_label = "渲染设置同步"
    bl_space_type = VIEW3D_SPACE
    bl_region_type = UI_REGION
    bl_category = PANEL_CATEGORY
    bl_parent_id = CAINTOOL_PT_toolkit.bl_idname
    bl_options = {"DEFAULT_CLOSED"}

    def draw_header(self, context):
        del context
        self.layout.label(text="", icon="SCENE_DATA")

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False
        render_sync_tools.draw_feature(layout, context)


CLASSES = (
    CAINTOOL_PT_toolkit,
    CAINTOOL_PT_batch_property,
    CAINTOOL_PT_keyframe_transition,
    CAINTOOL_PT_parent_child_hide,
    CAINTOOL_PT_render_sync,
    CAINTOOL_PT_scene_render,
)

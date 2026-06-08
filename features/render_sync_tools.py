from __future__ import annotations

import time

import bpy
from bpy.app.handlers import persistent

from ..services import render_sync_service
from .base import FeatureSection


IS_SYNCING = False
TIMER_REGISTERED = False
PENDING_MASTER_SCENES: dict[str, float] = {}
IGNORED_SCENE_UPDATES: dict[str, float] = {}
AUTO_SYNC_DEBOUNCE_SECONDS = 0.25
AUTO_SYNC_QUEUE_INTERVAL_SECONDS = 0.05
AUTO_SYNC_IGNORE_SECONDS = 0.5


class CAINTOOL_OT_sync_render_settings_now(bpy.types.Operator):
    bl_idname = "caintool.sync_render_settings_now"
    bl_label = "立即同步"
    bl_description = "将当前场景的渲染设置同步到勾选的目标场景"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        PENDING_MASTER_SCENES.pop(context.scene.name, None)
        result = _perform_sync(context.scene)
        if result.synced_count == 0:
            self.report({"WARNING"}, "当前没有勾选任何目标场景。")
            return {"CANCELLED"}

        self.report({"INFO"}, f"已同步到 {result.synced_count} 个目标场景。")
        return {"FINISHED"}


@persistent
def render_sync_handler(scene, depsgraph):
    scene_name = getattr(scene, "name", None)
    if not scene_name:
        return

    if _is_scene_update_ignored(scene_name):
        return

    settings = getattr(scene, "caintool", None)
    if settings is None or not settings.render_sync_auto_enabled or IS_SYNCING:
        return

    if not _depsgraph_requires_sync(depsgraph):
        return

    _queue_auto_sync(scene.name)


def draw_feature(layout, context) -> None:
    settings = context.scene.caintool

    header_col = layout.column(align=True)
    header_col.prop(settings, "render_sync_auto_enabled", toggle=True)
    header_col.operator(CAINTOOL_OT_sync_render_settings_now.bl_idname, icon="FILE_REFRESH")
    header_col.label(text="同步当前场景到目标场景，不覆盖输出路径。", icon="INFO")

    layout.separator(factor=0.75)

    list_col = layout.column(align=True)
    list_col.label(text="选择目标场景：", icon="SCENE_DATA")

    for scene in bpy.data.scenes:
        if scene == context.scene:
            row = list_col.row()
            row.enabled = False
            row.label(text=f"{scene.name}（当前主控）", icon="SCENE_DATA")
            continue

        row = list_col.row()
        row.prop(scene.caintool, "render_sync_target", text=scene.name)

    if settings.render_sync_auto_enabled:
        warn = layout.row()
        warn.label(text="自动同步已开启，修改当前场景会覆盖已勾选目标。", icon="ERROR")


def register() -> None:
    _clear_sync_queue()
    if render_sync_handler not in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.append(render_sync_handler)


def unregister() -> None:
    _clear_sync_queue()
    if render_sync_handler in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.remove(render_sync_handler)


def _perform_sync(master_scene):
    global IS_SYNCING
    if IS_SYNCING:
        return render_sync_service.RenderSyncResult()

    target_scenes = render_sync_service.get_target_scenes(master_scene, bpy.data.scenes)
    if not target_scenes:
        return render_sync_service.RenderSyncResult()

    IS_SYNCING = True
    try:
        result = render_sync_service.perform_sync(master_scene, bpy.data.scenes)
    finally:
        IS_SYNCING = False

    _mark_scene_updates_ignored((master_scene.name, *(scene.name for scene in target_scenes)))
    return result


def _queue_auto_sync(scene_name: str) -> None:
    global TIMER_REGISTERED

    PENDING_MASTER_SCENES[scene_name] = time.monotonic() + AUTO_SYNC_DEBOUNCE_SECONDS
    if TIMER_REGISTERED:
        return

    bpy.app.timers.register(_process_sync_queue, first_interval=AUTO_SYNC_DEBOUNCE_SECONDS)
    TIMER_REGISTERED = True


def _process_sync_queue():
    global TIMER_REGISTERED

    now = time.monotonic()
    if IS_SYNCING:
        return AUTO_SYNC_QUEUE_INTERVAL_SECONDS

    ready_scene_name = None
    next_due = None
    for scene_name, due_time in tuple(PENDING_MASTER_SCENES.items()):
        if due_time <= now and ready_scene_name is None:
            ready_scene_name = scene_name
            break
        if next_due is None or due_time < next_due:
            next_due = due_time

    if ready_scene_name is None:
        if next_due is None:
            TIMER_REGISTERED = False
            return None
        return max(AUTO_SYNC_QUEUE_INTERVAL_SECONDS, next_due - now)

    PENDING_MASTER_SCENES.pop(ready_scene_name, None)

    scene = bpy.data.scenes.get(ready_scene_name)
    if scene is not None:
        settings = getattr(scene, "caintool", None)
        if settings is not None and settings.render_sync_auto_enabled:
            try:
                _perform_sync(scene)
            except Exception as exc:
                print(f"[CainTool] Render sync error: {exc}")

    if PENDING_MASTER_SCENES:
        return AUTO_SYNC_QUEUE_INTERVAL_SECONDS

    TIMER_REGISTERED = False
    return None


def _clear_sync_queue() -> None:
    global TIMER_REGISTERED

    PENDING_MASTER_SCENES.clear()
    IGNORED_SCENE_UPDATES.clear()
    timer_api = getattr(bpy.app, "timers", None)
    if timer_api is not None:
        is_registered = getattr(timer_api, "is_registered", None)
        unregister = getattr(timer_api, "unregister", None)
        if callable(is_registered) and callable(unregister):
            try:
                if is_registered(_process_sync_queue):
                    unregister(_process_sync_queue)
            except Exception:
                pass

    TIMER_REGISTERED = False


def _mark_scene_updates_ignored(scene_names) -> None:
    ignore_until = time.monotonic() + AUTO_SYNC_IGNORE_SECONDS
    for scene_name in scene_names:
        if scene_name:
            IGNORED_SCENE_UPDATES[scene_name] = ignore_until


def _is_scene_update_ignored(scene_name: str) -> bool:
    ignore_until = IGNORED_SCENE_UPDATES.get(scene_name)
    if ignore_until is None:
        return False

    if ignore_until <= time.monotonic():
        IGNORED_SCENE_UPDATES.pop(scene_name, None)
        return False

    return True


def _depsgraph_requires_sync(depsgraph) -> bool:
    id_type_updated = getattr(depsgraph, "id_type_updated", None)
    if not callable(id_type_updated):
        return True

    for id_type in ("SCENE", "VIEW_LAYER", "WORLD"):
        try:
            if id_type_updated(id_type):
                return True
        except Exception:
            continue

    return False


FEATURE = FeatureSection(
    key="render_sync_tools",
    label="渲染设置同步",
    icon="SCENE_DATA",
    description="将当前场景的渲染设置同步到勾选的其他场景。",
    draw=draw_feature,
)

CLASSES = (CAINTOOL_OT_sync_render_settings_now,)

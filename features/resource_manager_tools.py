from __future__ import annotations

import bpy

from ..services.resource_manager import runtime
from ..services.resource_manager.blender_source import BlenderResourceSource
from ..services.resource_manager.models import ScanOptions
from ..services.resource_manager.packaging import build_package_plan, execute_package_plan
from ..services.resource_manager.scanner import scan_current_file
from ..services.resource_manager.reference_graph import build_reference_paths
from ..services.resource_manager.locators import locate_reference_node
from ..services.resource_manager.usage_summary import get_paths_to_usage, summarize_reference_usage
from ..services.resource_manager.inspector import (
    build_flow_steps, build_reference_overview, choose_default_complete_path,
    choose_default_path, choose_default_usage, get_complete_usage_paths, get_display_path,
)
from ..services.resource_manager.tasks import TaskState
from ..services.resource_manager.formatting import format_file_size, sort_resources
from .base import FeatureSection


def _human_bytes(value: float) -> str:
    return format_file_size(value)


def _human_time(seconds: float | None) -> str:
    if seconds is None:
        return "--"
    minutes, seconds = divmod(max(0, int(seconds)), 60)
    hours, minutes = divmod(minutes, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}" if hours else f"{minutes:02d}:{seconds:02d}"


def _refresh_scene_items(scene) -> None:
    settings = scene.caintool
    search = settings.resource_search.casefold().strip()
    old_selection = {item.resource_id for item in scene.caintool_resources if item.selected}
    active_id = settings.resource_active_id
    scene.caintool_resources.clear()
    resources = list(runtime.graph.resources.values())
    resources = sort_resources(resources, settings.resource_sort_key, settings.resource_sort_descending)
    for resource in resources:
        if settings.resource_show_missing_only and not resource.is_missing:
            continue
        haystack = f"{resource.name} {resource.kind} {resource.status} {resource.absolute_path}".casefold()
        if search and search not in haystack:
            continue
        item = scene.caintool_resources.add()
        item.resource_id = resource.id
        item.selected = resource.id in old_selection
        item.name = resource.name
        item.kind = resource.kind
        item.status = resource.status
        item.path = resource.original_path
        item.size_label = (
            "不可用" if resource.status == "MISSING" else
            "—" if resource.status == "GENERATED" else
            format_file_size(resource.size)
        )
        item.file_count = resource.file_count
        if resource.root_node_id:
            item.references = sum(group.count for group in summarize_reference_usage(runtime.graph.references_graph, resource.root_node_id))
        else:
            item.references = resource.reference_count
    active_index = next((index for index, item in enumerate(scene.caintool_resources) if item.resource_id == active_id), 0)
    scene.caintool_resource_index = min(active_index, max(0, len(scene.caintool_resources) - 1))
    if scene.caintool_resources:
        settings.resource_active_id = scene.caintool_resources[scene.caintool_resource_index].resource_id
    _refresh_references(scene)


def _refresh_references(scene) -> None:
    if scene.caintool.resource_reference_view == "GRAPH":
        _refresh_graph_references(scene)
    else:
        _refresh_usage_references(scene)
    _refresh_flow_items(scene)


def _complete_paths(scene):
    resource = _active_resource(scene)
    if not resource or not resource.root_node_id:
        return resource, (), None, ()
    graph = runtime.graph.references_graph
    groups = summarize_reference_usage(graph, resource.root_node_id)
    usage_id = scene.caintool.resource_active_usage_id
    if usage_id not in graph.usage_index:
        usage_id = choose_default_usage(groups)
        scene.caintool.resource_active_usage_id = usage_id
    usage = graph.usage_index.get(usage_id)
    paths = get_complete_usage_paths(graph, resource.root_node_id, usage_id or None)
    if not paths:
        paths = get_complete_usage_paths(graph, resource.root_node_id)
    default_path = choose_default_complete_path(graph, paths)
    ordered = tuple(sorted(paths, key=lambda path: (
        path.id != getattr(default_path, "id", ""), path.cyclic,
        not bool({graph.nodes[node_id].kind for node_id in path.node_ids} & {"OBJECT", "SCENE", "VIEW_LAYER"}),
        len(path.node_ids), path.id,
    )))
    return resource, groups, usage, ordered


def _refresh_flow_items(scene) -> None:
    scene.caintool_reference_flow.clear()
    resource, groups, usage, paths = _complete_paths(scene)
    del resource, groups, usage
    if not paths:
        return
    path_index = min(scene.caintool.resource_reference_path_index, len(paths) - 1)
    for step in build_flow_steps(runtime.graph.references_graph, paths[path_index]):
        item = scene.caintool_reference_flow.add()
        item.node_id = step.node_id
        item.path_id = step.path_id
        item.step_index = step.step_index
        item.kind = step.kind
        item.type_label = step.type_label
        item.name = step.name
        item.relation = step.relation
        item.icon_name = step.icon
        item.locatable = step.locatable
        item.cyclic = step.cyclic
    scene.caintool_reference_flow_index = min(
        scene.caintool_reference_flow_index, max(0, len(scene.caintool_reference_flow) - 1)
    )


def _active_resource(scene):
    if not scene.caintool_resources:
        return None
    index = min(scene.caintool_resource_index, len(scene.caintool_resources) - 1)
    return runtime.graph.resources.get(scene.caintool_resources[index].resource_id)


def _refresh_usage_references(scene) -> None:
    scene.caintool_resource_references.clear()
    resource = _active_resource(scene)
    if not resource or not resource.root_node_id:
        return
    graph = runtime.graph.references_graph
    groups = summarize_reference_usage(graph, resource.root_node_id)
    available_usage_ids = {usage.id for group in groups for usage in group.usages}
    target_usage_id = scene.caintool.resource_active_usage_id
    if target_usage_id not in available_usage_ids:
        target_usage_id = choose_default_usage(groups)
        scene.caintool.resource_active_usage_id = target_usage_id
        scene.caintool.resource_active_host_id = ""
        scene.caintool.resource_reference_path_index = 0
    for group in groups:
        if any(usage.id == target_usage_id for usage in group.usages):
            runtime.expanded_usage_groups.add(group.category)
    search = scene.caintool.resource_reference_search.casefold().strip()
    selected_index = 0
    for group in groups:
        visible_usages = []
        for usage in group.usages:
            path_text = " ".join(
                graph.nodes[node_id].name
                for path_id in usage.path_ids
                if path_id in graph.path_index
                for node_id in graph.path_index[path_id].node_ids
            )
            host_text = " ".join(f"{host.name} {host.detail}" for host in usage.hosts)
            if search and search not in f"{group.label} {usage.name} {path_text} {host_text}".casefold():
                continue
            visible_usages.append(usage)
        if not visible_usages:
            continue
        group_item = scene.caintool_resource_references.add()
        group_item.row_kind = "GROUP"
        group_item.category = group.category
        group_item.owner_name = group.label
        group_item.host_count = len(visible_usages)
        group_item.has_children = True
        group_item.expanded = group.category in runtime.expanded_usage_groups
        if group.category not in runtime.expanded_usage_groups:
            continue
        for usage in visible_usages:
            item = scene.caintool_resource_references.add()
            item.row_kind = "USAGE"
            item.usage_id = usage.id
            item.node_id = usage.node_id
            item.category = usage.category
            item.owner_type = usage.category
            item.owner_name = usage.name
            item.depth = 1
            item.host_count = len(usage.hosts)
            item.has_children = bool(usage.hosts)
            item.expanded = usage.id in runtime.expanded_usage_ids
            if usage.id == target_usage_id and not scene.caintool.resource_active_host_id:
                selected_index = len(scene.caintool_resource_references) - 1
            if usage.id not in runtime.expanded_usage_ids:
                continue
            for host in usage.hosts:
                host_item = scene.caintool_resource_references.add()
                host_item.row_kind = "HOST"
                host_item.usage_id = usage.id
                host_item.node_id = host.node_id
                host_item.owner_type = host.kind
                host_item.owner_name = host.detail or host.name
                host_item.depth = 2
                host_item.locatable = True
                if usage.id == target_usage_id and host.node_id == scene.caintool.resource_active_host_id:
                    selected_index = len(scene.caintool_resource_references) - 1
    scene.caintool_resource_reference_index = min(selected_index, max(0, len(scene.caintool_resource_references) - 1))


def _refresh_graph_references(scene) -> None:
    scene.caintool_resource_references.clear()
    if not scene.caintool_resources:
        return
    index = min(scene.caintool_resource_index, len(scene.caintool_resources) - 1)
    resource = runtime.graph.resources.get(scene.caintool_resources[index].resource_id)
    if not resource:
        return
    graph = runtime.graph.references_graph
    if not resource.root_node_id or resource.root_node_id not in graph.nodes:
        return
    paths = build_reference_paths(graph, resource.root_node_id)
    if resource.id not in runtime.initialized_reference_resources:
        runtime.initialized_reference_resources.add(resource.id)
    search = scene.caintool.resource_reference_search.casefold().strip()
    final_only = scene.caintool.resource_reference_final_only
    seen_rows = set()
    for path in paths:
        node_ids = path.node_ids[1:] if len(path.node_ids) > 1 else path.node_ids
        for offset, node_id in enumerate(node_ids):
            node = graph.nodes[node_id]
            is_final = offset == len(node_ids) - 1
            if final_only and not is_final:
                continue
            haystack = f"{node.name} {node.kind} {' '.join(path.relations)}".casefold()
            if search and search not in haystack:
                continue
            depth = 0 if final_only else offset
            prefix = path.node_ids[:offset + 2]
            tree_key = "/".join(prefix)
            row_key = (tree_key, path.id if is_final else "")
            if row_key in seen_rows:
                continue
            seen_rows.add(row_key)
            parent_key = "/".join(prefix[:-1])
            if not final_only and depth > 0 and parent_key not in runtime.expanded_reference_keys:
                continue
            has_children = bool(graph.children(node_id)) and not (path.cyclic and is_final)
            item = scene.caintool_resource_references.add()
            item.resource_id = resource.id
            item.node_id = node_id
            item.path_id = path.id
            item.tree_key = tree_key
            item.depth = depth
            item.expanded = tree_key in runtime.expanded_reference_keys
            item.has_children = has_children
            item.relation_label = path.relations[offset] if offset < len(path.relations) else "资源"
            item.locatable = node.locatable
            item.cyclic = path.cyclic and is_final
            item.owner_type = node.kind
            item.owner_name = node.name
            item.object_name = node.owner_name if node.kind in {"MATERIAL_SLOT", "MODIFIER"} else ""


class CAINTOOL_UL_resources(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        del context, data, icon, active_data, active_propname, index
        row = layout.row(align=True)
        op = row.operator(
            "caintool.toggle_resource_package_selection", text="",
            icon="CHECKBOX_HLT" if item.selected else "CHECKBOX_DEHLT", emboss=False,
        )
        op.resource_id = item.resource_id
        status_icon = "ERROR" if item.status == "MISSING" else "PACKAGE" if item.status == "PACKED" else "FILE_TICK"
        row.label(text=item.name, icon=status_icon)
        row.label(text=item.kind)
        row.label(text=item.size_label)
        row.label(text=str(item.references), icon="LINKED")


class CAINTOOL_OT_toggle_resource_package_selection(bpy.types.Operator):
    bl_idname = "caintool.toggle_resource_package_selection"
    bl_label = "切换资源打包选择"
    resource_id: bpy.props.StringProperty()

    def execute(self, context):
        for item in context.scene.caintool_resources:
            if item.resource_id == self.resource_id:
                item.selected = not item.selected
                return {"FINISHED"}
        return {"CANCELLED"}


class CAINTOOL_UL_resource_references(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        del context, data, icon, active_data, active_propname, index
        row = layout.row(align=True)
        if item.row_kind in {"GROUP", "USAGE", "HOST"}:
            for _ in range(item.depth):
                row.separator(factor=0.65)
            if item.row_kind == "GROUP":
                op = row.operator("caintool.toggle_usage_group", text="", icon="TRIA_DOWN" if item.expanded else "TRIA_RIGHT", emboss=False)
                op.category = item.category
                row.label(text=f"{item.owner_name} ({item.host_count})", icon="FILE_FOLDER")
                return
            if item.has_children:
                op = row.operator("caintool.toggle_usage_hosts", text="", icon="TRIA_DOWN" if item.expanded else "TRIA_RIGHT", emboss=False)
                op.usage_id = item.usage_id
            else:
                row.label(text="", icon="DOT")
            icon_map = {
                "MATERIAL": "MATERIAL", "MODIFIER": "MODIFIER", "WORLD": "WORLD_DATA",
                "LIGHT": "LIGHT_DATA", "COMPOSITOR": "NODE_COMPOSITING",
                "OTHER": "NODE", "MATERIAL_SLOT": "MATERIAL", "OBJECT": "OBJECT_DATA", "SCENE": "SCENE_DATA",
            }
            label = item.owner_name
            if item.row_kind == "USAGE" and item.host_count:
                label += f" · {item.host_count} 个宿主"
            row.label(text=label, icon=icon_map.get(item.owner_type or item.category, "DOT"))
            if item.locatable and item.node_id:
                op = row.operator("caintool.select_resource_reference", text="", icon="RESTRICT_SELECT_OFF")
                op.node_id = item.node_id
            return
        for _ in range(item.depth):
            row.separator(factor=0.65)
        if item.has_children:
            op = row.operator("caintool.toggle_reference_branch", text="", icon="TRIA_DOWN" if item.expanded else "TRIA_RIGHT", emboss=False)
            op.tree_key = item.tree_key
        else:
            row.label(text="", icon="DOT")
        icon_map = {
            "NODE": "NODE", "NODE_TREE": "NODETREE", "MATERIAL": "MATERIAL",
            "MATERIAL_SLOT": "MATERIAL", "OBJECT": "OBJECT_DATA", "COLLECTION": "OUTLINER_COLLECTION",
            "SCENE": "SCENE_DATA", "VIEW_LAYER": "RENDERLAYERS", "WORLD": "WORLD_DATA",
            "LIGHT": "LIGHT_DATA", "MODIFIER": "MODIFIER",
        }
        row.label(text=item.owner_name, icon="ERROR" if item.cyclic else icon_map.get(item.owner_type, "DOT"))
        row.label(text=item.relation_label)
        if item.locatable:
            op = row.operator("caintool.select_resource_reference", text="", icon="RESTRICT_SELECT_OFF")
            op.node_id = item.node_id
            op.path_id = item.path_id


class CAINTOOL_UL_reference_flow(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        del context, data, icon, active_data, active_propname, index
        row = layout.row(align=True)
        row.label(text=f"{item.step_index:02d}")
        row.label(text=item.type_label, icon="ERROR" if item.cyclic else item.icon_name)
        row.label(text=item.name)
        row.label(text=f"由上一层：{item.relation}")
        if item.locatable:
            op = row.operator(CAINTOOL_OT_select_resource_reference.bl_idname, text="", icon="RESTRICT_SELECT_OFF")
            op.node_id = item.node_id
            op.path_id = item.path_id
            op.step_index = item.step_index - 1


class CAINTOOL_OT_toggle_reference_branch(bpy.types.Operator):
    bl_idname = "caintool.toggle_reference_branch"
    bl_label = "展开或折叠引用分支"
    tree_key: bpy.props.StringProperty()

    def execute(self, context):
        if self.tree_key in runtime.expanded_reference_keys:
            runtime.expanded_reference_keys.remove(self.tree_key)
            runtime.expanded_reference_keys = {
                key for key in runtime.expanded_reference_keys if not key.startswith(self.tree_key + "/")
            }
        else:
            runtime.expanded_reference_keys.add(self.tree_key)
        _refresh_references(context.scene)
        return {"FINISHED"}


class CAINTOOL_OT_toggle_usage_group(bpy.types.Operator):
    bl_idname = "caintool.toggle_usage_group"
    bl_label = "展开或折叠使用者分组"
    category: bpy.props.StringProperty()

    def execute(self, context):
        if self.category in runtime.expanded_usage_groups:
            runtime.expanded_usage_groups.remove(self.category)
        else:
            runtime.expanded_usage_groups.add(self.category)
        _refresh_references(context.scene)
        return {"FINISHED"}


class CAINTOOL_OT_toggle_usage_hosts(bpy.types.Operator):
    bl_idname = "caintool.toggle_usage_hosts"
    bl_label = "展开或折叠使用者宿主"
    usage_id: bpy.props.StringProperty()

    def execute(self, context):
        if self.usage_id in runtime.expanded_usage_ids:
            runtime.expanded_usage_ids.remove(self.usage_id)
        else:
            runtime.expanded_usage_ids.add(self.usage_id)
        _refresh_references(context.scene)
        return {"FINISHED"}


class CAINTOOL_OT_cycle_reference_path(bpy.types.Operator):
    bl_idname = "caintool.cycle_reference_path"
    bl_label = "切换引用路径"
    delta: bpy.props.IntProperty(default=1)
    path_count: bpy.props.IntProperty(default=0)

    def execute(self, context):
        if self.path_count:
            current = context.scene.caintool.resource_reference_path_index
            context.scene.caintool.resource_reference_path_index = (current + self.delta) % self.path_count
        return {"FINISHED"}


class CAINTOOL_OT_set_reference_expansion(bpy.types.Operator):
    bl_idname = "caintool.set_reference_expansion"
    bl_label = "展开或折叠全部引用"
    expand: bpy.props.BoolProperty(default=True)

    def execute(self, context):
        if not self.expand:
            runtime.expanded_reference_keys.clear()
        else:
            scene = context.scene
            if scene.caintool_resources:
                resource_id = scene.caintool_resources[min(scene.caintool_resource_index, len(scene.caintool_resources) - 1)].resource_id
                resource = runtime.graph.resources.get(resource_id)
                if resource and resource.root_node_id:
                    for path in build_reference_paths(runtime.graph.references_graph, resource.root_node_id):
                        for end in range(2, len(path.node_ids)):
                            runtime.expanded_reference_keys.add("/".join(path.node_ids[:end]))
        _refresh_references(context.scene)
        return {"FINISHED"}


class CAINTOOL_OT_restore_resource_area(bpy.types.Operator):
    bl_idname = "caintool.restore_resource_area"
    bl_label = "返回资源管理器"

    def execute(self, context):
        state = runtime.previous_area_state
        if state is None:
            self.report({"INFO"}, "没有需要恢复的编辑器区域")
            return {"CANCELLED"}
        pointer, area_type, ui_type = state
        area = next((item for item in context.screen.areas if item.as_pointer() == pointer), None)
        if area is None:
            self.report({"WARNING"}, "原编辑器区域已不存在")
            return {"CANCELLED"}
        area.type = area_type
        if ui_type:
            try:
                area.ui_type = ui_type
            except Exception:
                pass
        runtime.previous_area_state = None
        return {"FINISHED"}


class _TaskModalMixin:
    _timer = None

    def _run_task(self, context, task):
        if runtime.active_task and not runtime.active_task.is_finished:
            self.report({"WARNING"}, "已有资源任务正在运行")
            return {"CANCELLED"}
        runtime.set_task(task)
        task.start()
        self._timer = context.window_manager.event_timer_add(0.05, window=context.window)
        context.window_manager.modal_handler_add(self)
        return {"RUNNING_MODAL"}

    def modal(self, context, event):
        task = runtime.active_task
        if event.type == "ESC" and task:
            task.cancel()
        if event.type != "TIMER" or not task:
            return {"PASS_THROUGH"}
        running = task.tick(0.025)
        context.workspace.status_text_set(
            f"CainTool · {task.name} · {task.stage} · {task.completed}/{task.total or '?'} · {task.current_item}"
        )
        for area in context.screen.areas:
            area.tag_redraw()
        if running:
            return {"RUNNING_MODAL"}
        context.window_manager.event_timer_remove(self._timer)
        context.workspace.status_text_set(None)
        context.scene.caintool.resource_task_details_expanded = False
        if task.state == TaskState.COMPLETED and hasattr(task.result, "resources"):
            runtime.graph = task.result
            _refresh_scene_items(context.scene)
        elif task.state == TaskState.COMPLETED:
            _refresh_scene_items(context.scene)
        if task.state == TaskState.FAILED:
            self.report({"ERROR"}, task.error)
        elif task.state == TaskState.CANCELLED:
            self.report({"WARNING"}, "资源任务已取消")
        else:
            self.report({"INFO"}, f"{task.name}完成")
        return {"FINISHED"}


class CAINTOOL_OT_scan_resources(_TaskModalMixin, bpy.types.Operator):
    bl_idname = "caintool.scan_resources"
    bl_label = "扫描外部资源"
    bl_options = {"REGISTER"}
    full_scan: bpy.props.BoolProperty(default=False)

    def execute(self, context):
        settings = context.scene.caintool
        options = ScanOptions(
            full_scan=self.full_scan,
            hash_files=self.full_scan and settings.resource_hash_files,
            recursive_libraries=self.full_scan and settings.resource_recursive_libraries,
            max_depth=settings.resource_max_depth,
        )
        return self._run_task(context, scan_current_file(BlenderResourceSource(bpy), options))


class CAINTOOL_OT_cancel_resource_task(bpy.types.Operator):
    bl_idname = "caintool.cancel_resource_task"
    bl_label = "取消资源任务"

    def execute(self, context):
        del context
        if runtime.active_task:
            runtime.active_task.cancel()
        return {"FINISHED"}


class CAINTOOL_OT_refresh_resource_view(bpy.types.Operator):
    bl_idname = "caintool.refresh_resource_view"
    bl_label = "刷新列表"

    def execute(self, context):
        _refresh_scene_items(context.scene)
        return {"FINISHED"}


class CAINTOOL_OT_package_resources(_TaskModalMixin, bpy.types.Operator):
    bl_idname = "caintool.package_resources"
    bl_label = "打包选中资源"
    bl_options = {"REGISTER", "UNDO"}
    all_resources: bpy.props.BoolProperty(default=False)

    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(self, event)

    def execute(self, context):
        if not bpy.data.filepath:
            self.report({"ERROR"}, "请先保存 .blend 工程")
            return {"CANCELLED"}
        selection = None if self.all_resources else {item.resource_id for item in context.scene.caintool_resources if item.selected}
        if selection == set():
            self.report({"WARNING"}, "请先勾选要打包的资源")
            return {"CANCELLED"}
        plan = build_package_plan(runtime.graph, selection, bpy.data.filepath, context.scene.caintool.resource_assets_folder)
        if not plan.items:
            self.report({"WARNING"}, "没有可打包的文件资源")
            return {"CANCELLED"}
        return self._run_task(context, execute_package_plan(plan, runtime.graph))


class CAINTOOL_OT_select_resource_reference(bpy.types.Operator):
    bl_idname = "caintool.select_resource_reference"
    bl_label = "定位引用者"
    node_id: bpy.props.StringProperty()
    path_id: bpy.props.StringProperty()
    step_index: bpy.props.IntProperty(default=-1)

    def execute(self, context):
        node_id = self.node_id
        if not node_id:
            refs = context.scene.caintool_resource_references
            if not refs:
                return {"CANCELLED"}
            node_id = refs[min(context.scene.caintool_resource_reference_index, len(refs) - 1)].node_id
        result = locate_reference_node(
            context, runtime.graph.references_graph, node_id, self.path_id, self.step_index
        )
        context.scene.caintool.resource_locate_message = result.message
        self.report({"INFO"} if result.success else {"WARNING"}, result.message)
        return {"FINISHED"} if result.success else {"CANCELLED"}


class CAINTOOL_OT_make_selected_local(bpy.types.Operator):
    bl_idname = "caintool.make_selected_resources_local"
    bl_label = "本地化选中链接数据"
    bl_options = {"REGISTER", "UNDO"}

    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(self, event)

    def execute(self, context):
        selected = {item.resource_id for item in context.scene.caintool_resources if item.selected}
        resources = [runtime.graph.resources[rid] for rid in selected if rid in runtime.graph.resources]
        names = {ref.owner_name for resource in resources for ref in resource.references}
        selected_libraries = {
            resource.absolute_path.casefold()
            for resource in resources if resource.kind == "LIBRARY" and resource.absolute_path
        }
        updated = 0
        for collection_name in dir(bpy.data):
            collection = getattr(bpy.data, collection_name, None)
            if not hasattr(collection, "__iter__"):
                continue
            try:
                blocks = tuple(collection)
            except Exception:
                continue
            for block in blocks:
                library = getattr(block, "library", None)
                library_path = bpy.path.abspath(library.filepath).casefold() if library else ""
                selected_by_library = bool(library_path and library_path in selected_libraries)
                if (getattr(block, "name", "") in names or selected_by_library) and library and hasattr(block, "make_local"):
                    block.make_local()
                    updated += 1
        self.report({"INFO"}, f"已本地化 {updated} 个数据块")
        return {"FINISHED"}


class CAINTOOL_OT_reload_selected_libraries(bpy.types.Operator):
    bl_idname = "caintool.reload_selected_libraries"
    bl_label = "重新加载选中外链库"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        selected = {item.resource_id for item in context.scene.caintool_resources if item.selected}
        paths = {
            runtime.graph.resources[rid].absolute_path.casefold()
            for rid in selected
            if rid in runtime.graph.resources and runtime.graph.resources[rid].kind == "LIBRARY"
        }
        count = 0
        for library in bpy.data.libraries:
            if bpy.path.abspath(library.filepath).casefold() in paths:
                library.reload()
                count += 1
        self.report({"INFO"}, f"已重新加载 {count} 个外链库")
        return {"FINISHED"}


class CAINTOOL_OT_open_resource_manager(bpy.types.Operator):
    bl_idname = "caintool.open_resource_manager"
    bl_label = "打开资源管理器"

    def invoke(self, context, event):
        del event
        return context.window_manager.invoke_props_dialog(self, width=1180)

    def draw(self, context):
        draw_manager(self.layout, context, compact=False)

    def execute(self, context):
        del context
        return {"FINISHED"}


def draw_task(layout) -> None:
    task = runtime.active_task
    box = layout.box()
    box.label(text="任务状态", icon="TIME")
    if not task:
        box.label(text="当前没有任务")
        return
    row = box.row(align=True)
    row.label(text=f"{task.name} · {task.stage}")
    row.label(text=task.state.value)
    if not task.is_finished:
        row.operator(CAINTOOL_OT_cancel_resource_task.bl_idname, text="取消", icon="CANCEL")
    if task.progress >= 0:
        box.progress(factor=task.progress, type="BAR", text=f"总体 {task.progress * 100:.1f}%")
    else:
        box.label(text="总体进度：正在发现工作量…")
    if task.stage_progress >= 0:
        box.progress(factor=task.stage_progress, type="BAR", text=f"阶段 {task.stage_progress * 100:.1f}%")
    box.label(text=f"项目：{task.completed}/{task.total or '?'}    当前：{task.current_item or '--'}")
    box.label(text=f"数据：{_human_bytes(task.bytes_completed)}/{_human_bytes(task.bytes_total)}    速度：{_human_bytes(task.bytes_per_second)}/s")
    box.label(text=f"用时：{_human_time(task.elapsed)}    剩余：{_human_time(task.eta)}")
    if task.error:
        box.label(text=task.error, icon="ERROR")


def _draw_usage_path_detail(layout, scene) -> None:
    refs = scene.caintool_resource_references
    if not refs:
        return
    item = refs[min(scene.caintool_resource_reference_index, len(refs) - 1)]
    if item.row_kind not in {"USAGE", "HOST"} or not item.usage_id:
        return
    resource = _active_resource(scene)
    if not resource:
        return
    graph = runtime.graph.references_graph
    paths = list(get_paths_to_usage(graph, resource.root_node_id, item.usage_id))
    endpoint = item.node_id if item.row_kind == "HOST" else graph.usage_index[item.usage_id].node_id
    paths = [path for path in paths if endpoint in path.node_ids]
    if not paths:
        return
    paths.sort(key=lambda path: (path.node_ids.index(endpoint), len(path.node_ids), path.id))
    unique_paths = {}
    for candidate in paths:
        candidate_end = candidate.node_ids.index(endpoint) + 1
        unique_paths.setdefault(candidate.node_ids[:candidate_end], candidate)
    paths = list(unique_paths.values())
    settings = scene.caintool
    path_index = min(settings.resource_reference_path_index, len(paths) - 1)
    path = paths[path_index]
    end = path.node_ids.index(endpoint) + 1
    node_ids = path.node_ids[:end]

    box = layout.box()
    header = box.row(align=True)
    header.label(text=f"引用链路 · 路径 {path_index + 1}/{len(paths)}", icon="LINKED")
    if len(paths) > 1:
        op = header.operator(CAINTOOL_OT_cycle_reference_path.bl_idname, text="", icon="TRIA_LEFT")
        op.delta = -1; op.path_count = len(paths)
        op = header.operator(CAINTOOL_OT_cycle_reference_path.bl_idname, text="", icon="TRIA_RIGHT")
        op.delta = 1; op.path_count = len(paths)
    icon_map = {
        "IMAGE": "IMAGE_DATA", "NODE": "NODE", "NODE_TREE": "NODETREE",
        "MATERIAL": "MATERIAL", "MATERIAL_SLOT": "MATERIAL", "MODIFIER": "MODIFIER",
        "OBJECT": "OBJECT_DATA", "COLLECTION": "OUTLINER_COLLECTION", "SCENE": "SCENE_DATA",
        "VIEW_LAYER": "RENDERLAYERS", "WORLD": "WORLD_DATA", "LIGHT": "LIGHT_DATA",
        "COMPOSITOR": "NODE_COMPOSITING",
    }
    for start in range(0, len(node_ids), 3):
        row = box.row(align=True)
        for offset, node_id in enumerate(node_ids[start:start + 3]):
            absolute_index = start + offset
            node = graph.nodes[node_id]
            op = row.operator(
                CAINTOOL_OT_select_resource_reference.bl_idname,
                text=node.name,
                icon=icon_map.get(node.kind, "DOT"),
            )
            op.node_id = node.id
            if absolute_index < len(node_ids) - 1:
                relation = path.relations[absolute_index] if absolute_index < len(path.relations) else "引用"
                row.label(text=f"→ {relation} →")
    if path.cyclic:
        box.label(text="此路径包含循环引用，已在重复节点处停止。", icon="ERROR")
    if settings.resource_locate_message:
        box.label(text=settings.resource_locate_message, icon="INFO")


def _flow_context(scene):
    resource = _active_resource(scene)
    if not resource or not resource.root_node_id:
        return resource, (), None, (), None
    graph = runtime.graph.references_graph
    groups = summarize_reference_usage(graph, resource.root_node_id)
    usage_id = scene.caintool.resource_active_usage_id
    if usage_id not in graph.usage_index:
        usage_id = choose_default_usage(groups)
        scene.caintool.resource_active_usage_id = usage_id
        scene.caintool.resource_active_host_id = ""
        scene.caintool.resource_reference_path_index = 0
    usage = graph.usage_index.get(usage_id)
    if usage is None:
        return resource, groups, None, (), None
    paths = get_paths_to_usage(graph, resource.root_node_id, usage.id)
    host_id = scene.caintool.resource_active_host_id
    if host_id and not any(host.id == host_id for host in usage.hosts):
        host_id = ""
        scene.caintool.resource_active_host_id = ""
    endpoint_id = host_id or usage.node_id
    matching = tuple(path for path in paths if endpoint_id in path.node_ids)
    if not matching:
        matching = paths
        endpoint_id = usage.node_id
    unique = {}
    for path in matching:
        end = path.node_ids.index(endpoint_id) + 1 if endpoint_id in path.node_ids else len(path.node_ids)
        unique.setdefault(path.node_ids[:end], path)
    ordered = tuple(sorted(unique.values(), key=lambda path: (path.cyclic, len(path.node_ids), path.id)))
    default_path = choose_default_path(ordered, endpoint_id)
    return resource, groups, usage, ordered, default_path


def _draw_flow_inspector(layout, scene) -> None:
    resource, groups, usage, paths, default_path = _flow_context(scene)
    if not resource:
        layout.box().label(text="请在左侧选择一个资源。", icon="INFO")
        return
    graph = runtime.graph.references_graph
    card = layout.box()
    card.label(text=f"当前资源：{resource.name}", icon="IMAGE_DATA" if resource.kind == "IMAGE" else "FILE")
    group_suffix = f" · {resource.file_count} 个文件" if resource.file_count > 1 else ""
    card.label(text=f"{resource.kind} · {resource.status} · {_human_bytes(resource.size)}{group_suffix}")
    card.label(text=resource.original_path or "无外部路径")
    overview = build_reference_overview(graph, resource.root_node_id) if resource.root_node_id else None
    if overview:
        stats = card.row(align=True)
        stats.label(text=f"节点 {overview.direct_nodes}", icon="NODE")
        stats.label(text=f"材质 {overview.materials}", icon="MATERIAL")
        stats.label(text=f"修改器 {overview.modifiers}", icon="MODIFIER")
        stats.label(text=f"物体 {overview.objects}", icon="OBJECT_DATA")
        stats.label(text=f"场景 {overview.scenes}", icon="SCENE_DATA")

    flow = layout.box()
    if not usage or not paths:
        flow.label(text="当前资源未被节点、材质、物体或场景引用。", icon="INFO")
        return
    path_index = min(scene.caintool.resource_reference_path_index, len(paths) - 1)
    path = paths[path_index] if paths else default_path
    endpoint = scene.caintool.resource_active_host_id or usage.node_id
    cards = get_display_path(graph, path, endpoint)
    header = flow.row(align=True)
    header.label(text=f"当前引用链 · {usage.name} · {path_index + 1}/{len(paths)}", icon="LINKED")
    if len(paths) > 1:
        op = header.operator(CAINTOOL_OT_cycle_reference_path.bl_idname, text="", icon="TRIA_LEFT")
        op.delta = -1; op.path_count = len(paths)
        op = header.operator(CAINTOOL_OT_cycle_reference_path.bl_idname, text="", icon="TRIA_RIGHT")
        op.delta = 1; op.path_count = len(paths)
    for start in range(0, len(cards), 3):
        row = flow.row(align=True)
        for flow_card in cards[start:start + 3]:
            card_box = row.box()
            if flow_card.relation:
                card_box.label(text=f"← {flow_card.relation}")
            card_box.label(text=flow_card.type_label, icon=flow_card.icon)
            op = card_box.operator(
                CAINTOOL_OT_select_resource_reference.bl_idname,
                text=flow_card.name,
                icon="RESTRICT_SELECT_OFF" if flow_card.locatable else "DOT",
            )
            op.node_id = flow_card.node_id
            if flow_card.cyclic:
                card_box.alert = True
                card_box.label(text="循环引用", icon="ERROR")
    if scene.caintool.resource_locate_message:
        flow.label(text=scene.caintool.resource_locate_message, icon="INFO")


def _draw_complete_flow(layout, scene) -> None:
    resource, groups, usage, paths = _complete_paths(scene)
    del groups
    if not resource:
        layout.label(text="请在左侧选择一个资源。", icon="INFO")
        return
    usage_count = sum(group.count for group in summarize_reference_usage(
        runtime.graph.references_graph, resource.root_node_id
    )) if resource.root_node_id else 0
    header = layout.row(align=True)
    header.label(
        text=f"{resource.name} · {resource.status} · {usage_count} 个主要使用者",
        icon="IMAGE_DATA" if resource.kind == "IMAGE" else "FILE",
    )
    path_text = resource.original_path or "无外部路径"
    layout.label(text=path_text if len(path_text) <= 100 else path_text[:97] + "…", icon="FILE")

    flow = layout.box()
    if not paths:
        flow.label(text="当前资源没有可追踪的上层引用。", icon="INFO")
        return
    if not scene.caintool_reference_flow:
        _refresh_flow_items(scene)
    path_index = min(scene.caintool.resource_reference_path_index, len(paths) - 1)
    controls = flow.row(align=True)
    branch_name = usage.name if usage else "全部引用"
    controls.label(text=f"{branch_name} · 完整链路 · 路径 {path_index + 1}/{len(paths)}", icon="LINKED")
    if len(paths) > 1:
        op = controls.operator(CAINTOOL_OT_cycle_reference_path.bl_idname, text="", icon="TRIA_LEFT")
        op.delta = -1; op.path_count = len(paths)
        op = controls.operator(CAINTOOL_OT_cycle_reference_path.bl_idname, text="", icon="TRIA_RIGHT")
        op.delta = 1; op.path_count = len(paths)
    flow.template_list(
        "CAINTOOL_UL_reference_flow", "complete", scene,
        "caintool_reference_flow", scene, "caintool_reference_flow_index", rows=14,
    )
    if scene.caintool.resource_locate_message:
        flow.label(text=scene.caintool.resource_locate_message, icon="INFO")


def _draw_compact_task(layout, context) -> None:
    task = runtime.active_task
    if not task:
        return
    box = layout.box()
    row = box.row(align=True)
    row.label(text=f"{task.name} · {task.stage}", icon="TIME")
    row.label(text=f"{task.completed}/{task.total or '?'}")
    if not task.is_finished:
        row.operator(CAINTOOL_OT_cancel_resource_task.bl_idname, text="取消", icon="CANCEL")
        if task.progress >= 0:
            box.progress(factor=task.progress, type="BAR", text=f"{task.progress * 100:.1f}% · {task.current_item}")
    details = box.row(align=True)
    details.prop(context.scene.caintool, "resource_task_details_expanded", text="任务详情", icon="TRIA_DOWN" if context.scene.caintool.resource_task_details_expanded else "TRIA_RIGHT")
    if context.scene.caintool.resource_task_details_expanded:
        box.label(text=f"用时 {_human_time(task.elapsed)} · 速度 {_human_bytes(task.bytes_per_second)}/s · 剩余 {_human_time(task.eta)}")
        for line in task.log[-8:]:
            box.label(text=line)


def _draw_resource_browser(layout, context) -> None:
    scene = context.scene
    settings = scene.caintool
    box = layout.box()
    box.label(text="资源", icon="FILE_FOLDER")
    filters = box.row(align=True)
    filters.prop(settings, "resource_search", text="", icon="VIEWZOOM")
    filters.prop(settings, "resource_sort_key", text="")
    if settings.resource_sort_key == "SIZE":
        filters.prop(
            settings, "resource_sort_descending", text="",
            icon="SORT_DESC" if settings.resource_sort_descending else "SORT_ASC",
        )
    filters.prop(settings, "resource_show_missing_only", text="仅缺失")
    filters.operator(CAINTOOL_OT_refresh_resource_view.bl_idname, text="", icon="FILE_REFRESH")
    headings = box.row(align=True)
    headings.label(text="打包")
    headings.label(text="资源 / 类型 / 硬盘占用 / 使用者")
    box.template_list("CAINTOOL_UL_resources", "inspector", scene, "caintool_resources", scene, "caintool_resource_index", rows=14)
    selected_count = sum(item.selected for item in scene.caintool_resources)
    footer = box.row(align=True)
    footer.label(text=f"显示 {len(scene.caintool_resources)}")
    footer.label(text=f"打包 {selected_count}")
    footer.label(text=f"缺失 {runtime.graph.missing_count}", icon="ERROR" if runtime.graph.missing_count else "CHECKMARK")
    actions = box.row(align=True)
    actions.operator(CAINTOOL_OT_package_resources.bl_idname, text="打包勾选", icon="PACKAGE").all_resources = False
    actions.operator(CAINTOOL_OT_package_resources.bl_idname, text="打包全部", icon="PACKAGE").all_resources = True
    options_header = box.row(align=True)
    options_header.prop(
        settings, "resource_settings_expanded", text="扫描与打包设置",
        icon="TRIA_DOWN" if settings.resource_settings_expanded else "TRIA_RIGHT",
    )
    if settings.resource_settings_expanded:
        options = box.column(align=True)
        options.prop(settings, "resource_hash_files")
        options.prop(settings, "resource_recursive_libraries")
        options.prop(settings, "resource_max_depth")
        options.prop(settings, "resource_assets_folder")


def _draw_resource_inspector(layout, context) -> None:
    scene = context.scene
    settings = scene.caintool
    _draw_complete_flow(layout, scene)
    if runtime.previous_area_state:
        layout.operator(CAINTOOL_OT_restore_resource_area.bl_idname, text="返回资源管理器", icon="BACK")

    users = layout.row(align=True)
    users.prop(
        settings, "resource_users_expanded", text="切换主要使用者",
        icon="TRIA_DOWN" if settings.resource_users_expanded else "TRIA_RIGHT",
    )
    if settings.resource_users_expanded:
        users.prop(settings, "resource_reference_search", text="", icon="VIEWZOOM")
        layout.template_list(
            "CAINTOOL_UL_resource_references", "users", scene,
            "caintool_resource_references", scene, "caintool_resource_reference_index", rows=6,
        )

    diagnostics = layout.row(align=True)
    diagnostics.prop(
        settings, "resource_diagnostics_expanded", text="完整引用图（诊断）",
        icon="TRIA_DOWN" if settings.resource_diagnostics_expanded else "TRIA_RIGHT",
    )
    if settings.resource_diagnostics_expanded:
        diagnostics.prop(settings, "resource_reference_final_only", text="最终宿主")
        layout.template_list(
            "CAINTOOL_UL_resource_references", "graph", scene,
            "caintool_resource_references", scene, "caintool_resource_reference_index", rows=6,
        )
    actions = layout.row(align=True)
    actions.operator(CAINTOOL_OT_make_selected_local.bl_idname, text="本地化勾选", icon="UNLINKED")
    actions.operator(CAINTOOL_OT_reload_selected_libraries.bl_idname, text="重载外链", icon="FILE_REFRESH")


def _draw_full_resource_manager(layout, context) -> None:
    controls = layout.row(align=True)
    op = controls.operator(CAINTOOL_OT_scan_resources.bl_idname, text="快速扫描", icon="VIEWZOOM")
    op.full_scan = False
    op = controls.operator(CAINTOOL_OT_scan_resources.bl_idname, text="完整扫描", icon="FILE_REFRESH")
    op.full_scan = True
    controls.separator()
    controls.label(text="左侧高亮资源决定右侧内容；打包勾选互不影响。", icon="INFO")
    _draw_compact_task(layout, context)
    split = layout.split(factor=0.38)
    _draw_resource_browser(split.column(), context)
    _draw_resource_inspector(split.column(), context)


def draw_manager(layout, context, compact: bool = False) -> None:
    if not compact:
        _draw_full_resource_manager(layout, context)
        return
    scene = context.scene
    settings = scene.caintool
    controls = layout.row(align=True)
    op = controls.operator(CAINTOOL_OT_scan_resources.bl_idname, text="快速扫描", icon="VIEWZOOM")
    op.full_scan = False
    op = controls.operator(CAINTOOL_OT_scan_resources.bl_idname, text="完整扫描", icon="FILE_REFRESH")
    op.full_scan = True
    if compact:
        controls.operator(CAINTOOL_OT_open_resource_manager.bl_idname, text="管理器", icon="ASSET_MANAGER")
    draw_task(layout)
    summary = layout.row(align=True)
    summary.label(text=f"资源 {len(runtime.graph.resources)}")
    visible_usage_count = sum(item.references for item in scene.caintool_resources)
    summary.label(text=f"主要使用者 {visible_usage_count}")
    summary.label(text=f"缺失 {runtime.graph.missing_count}", icon="ERROR" if runtime.graph.missing_count else "CHECKMARK")
    if compact:
        return
    filters = layout.row(align=True)
    filters.prop(settings, "resource_search", text="", icon="VIEWZOOM")
    filters.prop(settings, "resource_sort_key", text="")
    filters.prop(settings, "resource_show_missing_only")
    filters.operator(CAINTOOL_OT_refresh_resource_view.bl_idname, text="", icon="FILE_REFRESH")
    layout.template_list("CAINTOOL_UL_resources", "", scene, "caintool_resources", scene, "caintool_resource_index", rows=10)
    if scene.caintool_resources:
        item = scene.caintool_resources[min(scene.caintool_resource_index, len(scene.caintool_resources) - 1)]
        resource = runtime.graph.resources.get(item.resource_id)
        if resource:
            detail = layout.box()
            usages = summarize_reference_usage(runtime.graph.references_graph, resource.root_node_id) if resource.root_node_id else ()
            usage_count = sum(group.count for group in usages)
            detail.label(text=f"当前资源：{resource.name}", icon="IMAGE_DATA" if resource.kind == "IMAGE" else "FILE")
            group_suffix = f" · {resource.file_count} 个文件" if resource.file_count > 1 else ""
            detail.label(text=f"{resource.kind} · {resource.status} · {_human_bytes(resource.size)}{group_suffix} · {usage_count} 个主要使用者")
            detail.label(text=resource.original_path or "无外部路径")
            detail.label(text=resource.absolute_path or "未解析")
            if resource.content_hash:
                detail.label(text=f"SHA-256: {resource.content_hash}")
    chain_controls = layout.row(align=True)
    chain_controls.label(text="引用关系", icon="LINKED")
    chain_controls.prop(settings, "resource_reference_view", text="")
    chain_controls.prop(settings, "resource_reference_search", text="", icon="VIEWZOOM")
    if settings.resource_reference_view == "GRAPH":
        chain_controls.prop(settings, "resource_reference_final_only", text="最终宿主")
    if runtime.previous_area_state:
        chain_controls.operator(CAINTOOL_OT_restore_resource_area.bl_idname, text="返回", icon="BACK")
    if settings.resource_reference_view == "GRAPH":
        op = chain_controls.operator(CAINTOOL_OT_set_reference_expansion.bl_idname, text="", icon="FULLSCREEN_ENTER")
        op.expand = True
        op = chain_controls.operator(CAINTOOL_OT_set_reference_expansion.bl_idname, text="", icon="FULLSCREEN_EXIT")
        op.expand = False
    if scene.caintool_resources and not scene.caintool_resource_references:
        layout.label(text="没有引用图数据；请重新扫描，或该资源没有可追踪宿主。", icon="INFO")
    elif scene.caintool_resources and settings.resource_reference_view == "GRAPH":
        active_resource = runtime.graph.resources.get(scene.caintool_resources[min(scene.caintool_resource_index, len(scene.caintool_resources) - 1)].resource_id)
        if active_resource:
            layout.label(text=f"图片根节点：{active_resource.name}", icon="IMAGE_DATA")
    layout.template_list("CAINTOOL_UL_resource_references", "", scene, "caintool_resource_references", scene, "caintool_resource_reference_index", rows=10)
    if settings.resource_reference_view == "USAGES":
        _draw_usage_path_detail(layout, scene)
    actions = layout.row(align=True)
    actions.operator(CAINTOOL_OT_package_resources.bl_idname, text="打包选中", icon="PACKAGE").all_resources = False
    actions.operator(CAINTOOL_OT_package_resources.bl_idname, text="打包全部", icon="PACKAGE").all_resources = True
    actions.operator(CAINTOOL_OT_make_selected_local.bl_idname, icon="UNLINKED")
    actions.operator(CAINTOOL_OT_reload_selected_libraries.bl_idname, text="重载外链", icon="FILE_REFRESH")
    options = layout.box()
    options.label(text="扫描与打包设置", icon="PREFERENCES")
    options.prop(settings, "resource_hash_files")
    options.prop(settings, "resource_recursive_libraries")
    options.prop(settings, "resource_max_depth")
    options.prop(settings, "resource_assets_folder")
    if runtime.active_task and runtime.active_task.log:
        options.prop(settings, "resource_log_expanded", icon="TRIA_DOWN" if settings.resource_log_expanded else "TRIA_RIGHT")
        if settings.resource_log_expanded:
            for line in runtime.active_task.log[-12:]:
                options.label(text=line)


def draw_feature(layout, context) -> None:
    draw_manager(layout, context, compact=True)


FEATURE = FeatureSection(
    key="resource_manager", label="外部资源管理器", icon="ASSET_MANAGER",
    description="查看资源状态、引用关系并规范化打包工程外部文件。", draw=draw_feature,
)


CLASSES = (
    CAINTOOL_UL_resources, CAINTOOL_UL_resource_references, CAINTOOL_UL_reference_flow,
    CAINTOOL_OT_toggle_resource_package_selection,
    CAINTOOL_OT_toggle_reference_branch, CAINTOOL_OT_set_reference_expansion,
    CAINTOOL_OT_toggle_usage_group, CAINTOOL_OT_toggle_usage_hosts,
    CAINTOOL_OT_cycle_reference_path,
    CAINTOOL_OT_restore_resource_area,
    CAINTOOL_OT_scan_resources, CAINTOOL_OT_cancel_resource_task,
    CAINTOOL_OT_refresh_resource_view, CAINTOOL_OT_package_resources,
    CAINTOOL_OT_select_resource_reference, CAINTOOL_OT_make_selected_local,
    CAINTOOL_OT_reload_selected_libraries,
    CAINTOOL_OT_open_resource_manager,
)

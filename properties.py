import bpy

from .services import value_input_service


RESOURCE_VIEW_ITEMS = (
    ("TYPE", "按类型", "按文件资源类型分组和过滤"),
    ("STATUS", "按状态", "按正常、缺失、内嵌等状态查看"),
    ("LIBRARY", "按外链库", "按所属外部 blend 文件查看"),
)

REFERENCE_VIEW_ITEMS = (
    ("USAGES", "流程链", "查看当前资源的代表引用流程和主要使用者"),
    ("GRAPH", "完整图", "查看底层完整引用关系"),
)

RESOURCE_SORT_ITEMS = (
    ("TYPE", "类型", "按资源类型排序"),
    ("STATUS", "状态", "按资源状态排序"),
    ("LIBRARY", "外链库", "按所属 Library 排序"),
    ("SIZE", "大小", "按资源占用的硬盘空间排序"),
)


def _resource_index_updated(scene, context):
    del context
    try:
        if scene.caintool_resources:
            index = min(scene.caintool_resource_index, len(scene.caintool_resources) - 1)
            scene.caintool.resource_active_id = scene.caintool_resources[index].resource_id
        else:
            scene.caintool.resource_active_id = ""
        scene.caintool.resource_active_usage_id = ""
        scene.caintool.resource_active_host_id = ""
        scene.caintool.resource_reference_path_index = 0
        scene.caintool.resource_locate_message = ""
        from .features.resource_manager_tools import _refresh_references
        _refresh_references(scene)
    except Exception:
        pass


def _resource_reference_filter_updated(settings, context):
    del settings
    try:
        from .features.resource_manager_tools import _refresh_references
        _refresh_references(context.scene)
    except Exception:
        pass


def _resource_reference_index_updated(scene, context):
    del context
    try:
        scene.caintool.resource_reference_path_index = 0
        scene.caintool.resource_locate_message = ""
        if scene.caintool_resource_references:
            index = min(scene.caintool_resource_reference_index, len(scene.caintool_resource_references) - 1)
            item = scene.caintool_resource_references[index]
            if item.row_kind in {"USAGE", "HOST"}:
                scene.caintool.resource_active_usage_id = item.usage_id
                scene.caintool.resource_active_host_id = item.node_id if item.row_kind == "HOST" else ""
    except Exception:
        pass


def _resource_sort_updated(settings, context):
    del settings
    try:
        from .features.resource_manager_tools import _refresh_scene_items
        _refresh_scene_items(context.scene)
    except Exception:
        pass


def _resource_path_index_updated(settings, context):
    del settings
    try:
        from .features.resource_manager_tools import _refresh_flow_items
        _refresh_flow_items(context.scene)
    except Exception:
        pass


def _resource_users_expanded_updated(settings, context):
    if settings.resource_users_expanded:
        settings.resource_diagnostics_expanded = False
        settings.resource_reference_view = "USAGES"


def _resource_diagnostics_expanded_updated(settings, context):
    if settings.resource_diagnostics_expanded:
        settings.resource_users_expanded = False
        settings.resource_reference_view = "GRAPH"


class CAINTOOL_PG_resource_item(bpy.types.PropertyGroup):
    resource_id: bpy.props.StringProperty()
    selected: bpy.props.BoolProperty(name="选择", default=False)
    name: bpy.props.StringProperty(name="资源")
    kind: bpy.props.StringProperty(name="类型")
    status: bpy.props.StringProperty(name="状态")
    path: bpy.props.StringProperty(name="路径")
    size_label: bpy.props.StringProperty(name="硬盘占用")
    file_count: bpy.props.IntProperty(name="文件数", default=0)
    references: bpy.props.IntProperty(name="引用", default=0)


class CAINTOOL_PG_resource_reference(bpy.types.PropertyGroup):
    resource_id: bpy.props.StringProperty()
    owner_type: bpy.props.StringProperty(name="类型")
    owner_name: bpy.props.StringProperty(name="引用者")
    object_name: bpy.props.StringProperty(name="物体")
    property_path: bpy.props.StringProperty(name="属性")
    node_id: bpy.props.StringProperty()
    path_id: bpy.props.StringProperty()
    tree_key: bpy.props.StringProperty()
    depth: bpy.props.IntProperty(default=0)
    expanded: bpy.props.BoolProperty(default=True)
    has_children: bpy.props.BoolProperty(default=False)
    relation_label: bpy.props.StringProperty(name="关系")
    locatable: bpy.props.BoolProperty(default=True)
    cyclic: bpy.props.BoolProperty(default=False)
    row_kind: bpy.props.StringProperty(default="GRAPH")
    usage_id: bpy.props.StringProperty()
    category: bpy.props.StringProperty()
    host_count: bpy.props.IntProperty(default=0)


class CAINTOOL_PG_reference_flow_item(bpy.types.PropertyGroup):
    node_id: bpy.props.StringProperty()
    path_id: bpy.props.StringProperty()
    step_index: bpy.props.IntProperty(default=0)
    kind: bpy.props.StringProperty()
    type_label: bpy.props.StringProperty()
    name: bpy.props.StringProperty()
    relation: bpy.props.StringProperty()
    icon_name: bpy.props.StringProperty(default="DOT")
    locatable: bpy.props.BoolProperty(default=True)
    cyclic: bpy.props.BoolProperty(default=False)


class CAINTOOL_PG_transition_rule(bpy.types.PropertyGroup):
    property_name: bpy.props.StringProperty(
        name="属性名",
        description="要制作渐入渐出的属性名，例如 hide_render、energy、location",
        default="hide_render",
        maxlen=128,
    )
    target_value: bpy.props.StringProperty(
        name="目标值表达式",
        description="表达式模式下使用，支持 1000、True、(1, 0, 0) 这类写法",
        default="True",
        maxlen=256,
    )
    target_value_type: bpy.props.EnumProperty(
        name="目标值类型",
        description="选择这一条规则的目标值类型",
        items=value_input_service.VALUE_TYPE_ITEMS,
        default=value_input_service.VALUE_TYPE_BOOL,
    )
    target_value_bool: bpy.props.BoolProperty(name="布尔值", default=True)
    target_value_int: bpy.props.IntProperty(name="整数值", default=0)
    target_value_float: bpy.props.FloatProperty(name="浮点值", default=0.0)
    target_value_text: bpy.props.StringProperty(name="文本值", default="", maxlen=512)
    target_value_enum: bpy.props.StringProperty(name="枚举标识", default="", maxlen=256)
    target_value_vector_2: bpy.props.FloatVectorProperty(name="二维向量", size=2, default=(0.0, 0.0))
    target_value_vector_3: bpy.props.FloatVectorProperty(
        name="三维向量",
        size=3,
        default=(0.0, 0.0, 0.0),
    )
    target_value_vector_4: bpy.props.FloatVectorProperty(
        name="四维向量",
        size=4,
        default=(0.0, 0.0, 0.0, 0.0),
    )
    target_value_color_3: bpy.props.FloatVectorProperty(
        name="RGB 颜色",
        subtype="COLOR",
        size=3,
        min=0.0,
        soft_max=1.0,
        default=(1.0, 1.0, 1.0),
    )
    target_value_color_4: bpy.props.FloatVectorProperty(
        name="RGBA 颜色",
        subtype="COLOR",
        size=4,
        min=0.0,
        soft_max=1.0,
        default=(1.0, 1.0, 1.0, 1.0),
    )


class CAINTOOL_PG_settings(bpy.types.PropertyGroup):
    resource_search: bpy.props.StringProperty(name="搜索", default="")
    resource_view_mode: bpy.props.EnumProperty(name="视图", items=RESOURCE_VIEW_ITEMS, default="TYPE")
    resource_sort_key: bpy.props.EnumProperty(
        name="排序", items=RESOURCE_SORT_ITEMS, default="TYPE", update=_resource_sort_updated,
    )
    resource_sort_descending: bpy.props.BoolProperty(
        name="降序", default=True, update=_resource_sort_updated,
    )
    resource_show_missing_only: bpy.props.BoolProperty(name="仅缺失", default=False)
    resource_hash_files: bpy.props.BoolProperty(name="计算内容哈希", default=True)
    resource_recursive_libraries: bpy.props.BoolProperty(name="递归外链", default=True)
    resource_max_depth: bpy.props.IntProperty(name="最大深度", default=0, min=0, description="0 表示不限制")
    resource_assets_folder: bpy.props.StringProperty(name="资源目录", default="assets", maxlen=128)
    resource_log_expanded: bpy.props.BoolProperty(name="展开任务日志", default=False)
    resource_reference_search: bpy.props.StringProperty(name="引用链搜索", default="", update=_resource_reference_filter_updated)
    resource_reference_final_only: bpy.props.BoolProperty(name="只看最终宿主", default=False, update=_resource_reference_filter_updated)
    resource_reference_view: bpy.props.EnumProperty(name="引用视图", items=REFERENCE_VIEW_ITEMS, default="USAGES", update=_resource_reference_filter_updated)
    resource_reference_path_index: bpy.props.IntProperty(name="链路序号", default=0, min=0, update=_resource_path_index_updated)
    resource_locate_message: bpy.props.StringProperty(name="定位结果", default="")
    resource_active_id: bpy.props.StringProperty(name="当前资源", default="")
    resource_active_usage_id: bpy.props.StringProperty(name="当前使用者", default="")
    resource_active_host_id: bpy.props.StringProperty(name="当前宿主", default="")
    resource_settings_expanded: bpy.props.BoolProperty(name="扫描与打包设置", default=False)
    resource_task_details_expanded: bpy.props.BoolProperty(name="任务详情", default=False)
    resource_users_expanded: bpy.props.BoolProperty(name="切换主要使用者", default=False, update=_resource_users_expanded_updated)
    resource_diagnostics_expanded: bpy.props.BoolProperty(name="完整引用图", default=False, update=_resource_diagnostics_expanded_updated)
    batch_property_name: bpy.props.StringProperty(
        name="属性名",
        description="要修改的属性名，可作用于物体或物体数据",
        default="energy",
        maxlen=128,
    )
    batch_property_value: bpy.props.StringProperty(
        name="目标值表达式",
        description="表达式模式下使用，支持 1000、True、(1, 0, 0) 这类写法",
        default="1000",
        maxlen=256,
    )
    batch_property_value_type: bpy.props.EnumProperty(
        name="目标值类型",
        description="选择批量设置使用的目标值类型",
        items=value_input_service.VALUE_TYPE_ITEMS,
        default=value_input_service.VALUE_TYPE_FLOAT,
    )
    batch_property_value_bool: bpy.props.BoolProperty(name="布尔值", default=False)
    batch_property_value_int: bpy.props.IntProperty(name="整数值", default=0)
    batch_property_value_float: bpy.props.FloatProperty(name="浮点值", default=1000.0)
    batch_property_value_text: bpy.props.StringProperty(name="文本值", default="", maxlen=512)
    batch_property_value_enum: bpy.props.StringProperty(name="枚举标识", default="", maxlen=256)
    batch_property_value_vector_2: bpy.props.FloatVectorProperty(
        name="二维向量",
        size=2,
        default=(0.0, 0.0),
    )
    batch_property_value_vector_3: bpy.props.FloatVectorProperty(
        name="三维向量",
        size=3,
        default=(0.0, 0.0, 0.0),
    )
    batch_property_value_vector_4: bpy.props.FloatVectorProperty(
        name="四维向量",
        size=4,
        default=(0.0, 0.0, 0.0, 0.0),
    )
    batch_property_value_color_3: bpy.props.FloatVectorProperty(
        name="RGB 颜色",
        subtype="COLOR",
        size=3,
        min=0.0,
        soft_max=1.0,
        default=(1.0, 1.0, 1.0),
    )
    batch_property_value_color_4: bpy.props.FloatVectorProperty(
        name="RGBA 颜色",
        subtype="COLOR",
        size=4,
        min=0.0,
        soft_max=1.0,
        default=(1.0, 1.0, 1.0, 1.0),
    )
    transition_frame_offset: bpy.props.IntProperty(
        name="帧偏移",
        description="目标关键帧相对当前帧的偏移量，可正可负",
        default=2,
        soft_min=-250,
        soft_max=250,
    )
    render_sync_target: bpy.props.BoolProperty(
        name="作为同步目标",
        description="如果勾选，该场景将接收当前主控场景的渲染设置",
        default=False,
    )
    render_sync_auto_enabled: bpy.props.BoolProperty(
        name="自动同步当前场景",
        description="开启后，修改当前场景时会自动同步到已勾选目标场景",
        default=False,
    )
    render_sync_render_settings: bpy.props.BoolProperty(
        name="基础渲染参数", description="同步分辨率、帧率等通用渲染参数", default=True,
    )
    render_sync_color_management: bpy.props.BoolProperty(
        name="色彩管理", description="同步视图变换、Look、曝光和伽马等色彩管理设置", default=True,
    )
    render_sync_engine_settings: bpy.props.BoolProperty(
        name="渲染引擎参数", description="同步渲染引擎及 Cycles 或 Eevee 参数", default=True,
    )
    render_sync_world: bpy.props.BoolProperty(
        name="世界环境", description="让目标场景使用当前场景的世界环境", default=True,
    )
    render_sync_output_format: bpy.props.BoolProperty(
        name="输出文件格式", description="同步图像或视频编码格式，但不覆盖输出路径", default=False,
    )
    render_sync_render_passes: bpy.props.BoolProperty(
        name="渲染通道", description="按同名视图层同步启用的渲染通道", default=True,
    )
    parent_child_hide_include_render: bpy.props.BoolProperty(
        name="同时隐藏渲染",
        description="隐藏时同时处理渲染可见性，并在恢复时还原",
        default=False,
    )
    parent_child_hide_include_select: bpy.props.BoolProperty(
        name="同时禁止选择",
        description="隐藏时同时锁定可选择状态，并在恢复时还原",
        default=False,
    )
    cycles_render_samples: bpy.props.IntProperty(
        name="最终渲染采样",
        description="应用到所有场景的 Cycles 最终渲染采样数",
        default=256,
        min=1,
        soft_max=4096,
    )
    cycles_viewport_samples: bpy.props.IntProperty(
        name="视口采样",
        description="应用到所有场景的 Cycles 视口采样数",
        default=32,
        min=1,
        soft_max=1024,
    )
    cycles_adaptive_threshold: bpy.props.FloatProperty(
        name="自适应阈值",
        description="应用到所有场景的 Cycles 自适应阈值",
        default=0.001,
        min=0.000001,
        soft_max=1.0,
        precision=4,
    )


def register_properties() -> None:
    bpy.types.Scene.caintool = bpy.props.PointerProperty(type=CAINTOOL_PG_settings)
    bpy.types.Scene.caintool_transition_rules = bpy.props.CollectionProperty(
        type=CAINTOOL_PG_transition_rule
    )
    bpy.types.Scene.caintool_transition_rule_index = bpy.props.IntProperty(default=0)
    bpy.types.Scene.caintool_resources = bpy.props.CollectionProperty(type=CAINTOOL_PG_resource_item)
    bpy.types.Scene.caintool_resource_index = bpy.props.IntProperty(default=0, update=_resource_index_updated)
    bpy.types.Scene.caintool_resource_references = bpy.props.CollectionProperty(type=CAINTOOL_PG_resource_reference)
    bpy.types.Scene.caintool_resource_reference_index = bpy.props.IntProperty(default=0, update=_resource_reference_index_updated)
    bpy.types.Scene.caintool_reference_flow = bpy.props.CollectionProperty(type=CAINTOOL_PG_reference_flow_item)
    bpy.types.Scene.caintool_reference_flow_index = bpy.props.IntProperty(default=0)


def unregister_properties() -> None:
    del bpy.types.Scene.caintool_reference_flow_index
    del bpy.types.Scene.caintool_reference_flow
    del bpy.types.Scene.caintool_resource_reference_index
    del bpy.types.Scene.caintool_resource_references
    del bpy.types.Scene.caintool_resource_index
    del bpy.types.Scene.caintool_resources
    del bpy.types.Scene.caintool_transition_rule_index
    del bpy.types.Scene.caintool_transition_rules
    del bpy.types.Scene.caintool

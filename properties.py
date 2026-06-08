import bpy

from .services import value_input_service


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


def unregister_properties() -> None:
    del bpy.types.Scene.caintool_transition_rule_index
    del bpy.types.Scene.caintool_transition_rules
    del bpy.types.Scene.caintool

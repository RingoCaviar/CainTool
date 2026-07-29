import bpy

from . import properties
from .feature_registry import get_feature_classes, register_features, unregister_features
from .ui.panels import CLASSES as PANEL_CLASSES

CORE_CLASSES = (
    properties.CAINTOOL_PG_resource_item,
    properties.CAINTOOL_PG_resource_reference,
    properties.CAINTOOL_PG_reference_flow_item,
    properties.CAINTOOL_PG_transition_rule,
    properties.CAINTOOL_PG_settings,
    *PANEL_CLASSES,
)


def _get_registered_classes():
    return (*CORE_CLASSES, *get_feature_classes())


def register() -> None:
    for cls in _get_registered_classes():
        bpy.utils.register_class(cls)

    properties.register_properties()
    register_features()


def unregister() -> None:
    unregister_features()
    properties.unregister_properties()

    for cls in reversed(_get_registered_classes()):
        bpy.utils.unregister_class(cls)

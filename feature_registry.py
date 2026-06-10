from .features import (
    batch_property_tools,
    common_command_tools,
    keyframe_transition_tools,
    parent_child_hide_tools,
    render_sync_tools,
    scene_render_tools,
)

FEATURE_MODULES = (
    common_command_tools,
    batch_property_tools,
    keyframe_transition_tools,
    parent_child_hide_tools,
    render_sync_tools,
    scene_render_tools,
)


def iter_feature_modules():
    for module in FEATURE_MODULES:
        feature = getattr(module, "FEATURE", None)
        if feature is not None and feature.enabled:
            yield module


def get_feature_sections():
    return tuple(module.FEATURE for module in iter_feature_modules())


def get_feature_classes():
    classes = []
    for module in iter_feature_modules():
        classes.extend(getattr(module, "CLASSES", ()))
    return tuple(classes)


def register_features() -> None:
    for module in iter_feature_modules():
        register_fn = getattr(module, "register", None)
        if register_fn is not None:
            register_fn()


def unregister_features() -> None:
    for module in reversed(tuple(iter_feature_modules())):
        unregister_fn = getattr(module, "unregister", None)
        if unregister_fn is not None:
            unregister_fn()

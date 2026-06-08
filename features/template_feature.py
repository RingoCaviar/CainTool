from .base import FeatureSection


def draw_feature(layout, context) -> None:
    del layout, context


FEATURE = FeatureSection(
    key="template_feature",
    label="Template Feature",
    icon="TOOL_SETTINGS",
    description="Copy this module when creating a new feature.",
    draw=draw_feature,
    enabled=False,
)

CLASSES = ()

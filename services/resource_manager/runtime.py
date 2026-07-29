from __future__ import annotations

from .models import ResourceGraph
from .tasks import ResourceTask

graph = ResourceGraph()
active_task: ResourceTask | None = None
expanded_reference_keys: set[str] = set()
initialized_reference_resources: set[str] = set()
previous_area_state: tuple[int, str, str] | None = None
expanded_usage_groups: set[str] = {"MATERIAL", "MODIFIER", "WORLD", "LIGHT", "COMPOSITOR", "OTHER"}
expanded_usage_ids: set[str] = set()


def set_task(task: ResourceTask) -> ResourceTask:
    global active_task
    active_task = task
    return task


def clear() -> None:
    global graph, active_task, expanded_reference_keys, initialized_reference_resources
    graph = ResourceGraph()
    active_task = None
    expanded_reference_keys = set()
    initialized_reference_resources = set()

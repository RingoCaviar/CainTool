from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Sequence


@dataclass
class RenderSyncResult:
    synced_count: int = 0
    skipped_count: int = 0


def copy_property_group(source, target, prop_name: str, exclude_list: Iterable[str] | None = None) -> None:
    excludes = set(exclude_list or ())

    try:
        src_data = getattr(source, prop_name)
        tgt_data = getattr(target, prop_name)
    except AttributeError:
        return

    for prop in getattr(src_data.bl_rna, "properties", ()):
        identifier = getattr(prop, "identifier", "")
        if not identifier or identifier in excludes or getattr(prop, "is_readonly", False):
            continue

        try:
            value = getattr(src_data, identifier)
            target_value = getattr(tgt_data, identifier)
            if value != target_value:
                setattr(tgt_data, identifier, value)
        except (AttributeError, TypeError, ValueError):
            continue


def sync_scene_data(master, slave) -> None:
    copy_property_group(master, slave, "render", exclude_list=("filepath",))
    copy_property_group(master, slave, "view_settings")

    engine = getattr(master.render, "engine", "")
    if engine == "CYCLES":
        copy_property_group(master, slave, "cycles")
    elif "EEVEE" in engine:
        copy_property_group(master, slave, "eevee")

        master_view_layers = getattr(master, "view_layers", None)
        slave_view_layers = getattr(slave, "view_layers", None)
        if master_view_layers and slave_view_layers:
            master_vl = getattr(master_view_layers, "active", None)
            slave_vl = None
            if master_vl is not None:
                getter = getattr(slave_view_layers, "get", None)
                if getter is not None:
                    slave_vl = getter(master_vl.name)
            if slave_vl is None:
                slave_vl = getattr(slave_view_layers, "active", None)

            if master_vl is not None and slave_vl is not None and hasattr(master_vl, "eevee"):
                copy_property_group(master_vl, slave_vl, "eevee")

    if getattr(master, "world", None) is not None:
        slave.world = master.world


def get_target_scenes(master_scene, scenes: Sequence[object]) -> list[object]:
    targets = []
    for scene in scenes:
        if scene == master_scene:
            continue
        settings = getattr(scene, "caintool", None)
        if settings is not None and getattr(settings, "render_sync_target", False):
            targets.append(scene)
    return targets


def perform_sync(master_scene, scenes: Sequence[object]) -> RenderSyncResult:
    targets = get_target_scenes(master_scene, scenes)
    result = RenderSyncResult(skipped_count=0)

    for slave in targets:
        sync_scene_data(master_scene, slave)
        result.synced_count += 1

    return result

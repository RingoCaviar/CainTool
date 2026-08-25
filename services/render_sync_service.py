from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Sequence


@dataclass
class RenderSyncResult:
    synced_count: int = 0
    skipped_count: int = 0


@dataclass(frozen=True)
class RenderSyncOptions:
    render_settings: bool = True
    color_management: bool = True
    engine_settings: bool = True
    world: bool = True
    output_format: bool = False
    render_passes: bool = True


def copy_property_group(
    source,
    target,
    prop_name: str,
    exclude_list: Iterable[str] | None = None,
    include_prefixes: Iterable[str] | None = None,
) -> None:
    try:
        src_data = getattr(source, prop_name)
        tgt_data = getattr(target, prop_name)
    except AttributeError:
        return

    copy_rna_properties(src_data, tgt_data, exclude_list, include_prefixes)


def copy_rna_properties(
    source_group,
    target_group,
    exclude_list: Iterable[str] | None = None,
    include_prefixes: Iterable[str] | None = None,
) -> None:
    excludes = set(exclude_list or ())
    prefixes = tuple(include_prefixes or ())

    for prop in getattr(source_group.bl_rna, "properties", ()):
        identifier = getattr(prop, "identifier", "")
        if (
            not identifier
            or identifier in excludes
            or (prefixes and not identifier.startswith(prefixes))
            or getattr(prop, "is_readonly", False)
        ):
            continue

        try:
            value = getattr(source_group, identifier)
            target_value = getattr(target_group, identifier)
            if value != target_value:
                setattr(target_group, identifier, value)
        except (AttributeError, TypeError, ValueError):
            continue


def sync_scene_data(master, slave, options: RenderSyncOptions | None = None) -> None:
    options = options or RenderSyncOptions()

    if options.render_settings:
        copy_property_group(
            master,
            slave,
            "render",
            exclude_list=("engine", "filepath", "image_settings", "ffmpeg"),
        )

    if options.output_format:
        copy_property_group(master.render, slave.render, "image_settings")
        copy_property_group(master.render, slave.render, "ffmpeg")

    if options.color_management:
        copy_property_group(master, slave, "view_settings")

    engine = getattr(master.render, "engine", "")
    if options.engine_settings:
        try:
            slave.render.engine = engine
        except (AttributeError, TypeError, ValueError):
            pass

        if engine == "CYCLES":
            copy_property_group(master, slave, "cycles")
        elif "EEVEE" in engine:
            copy_property_group(master, slave, "eevee")

    if options.engine_settings and "EEVEE" in engine:
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

    if options.render_passes:
        _copy_render_passes(master, slave)

    if options.world:
        slave.world = getattr(master, "world", None)


def _copy_render_passes(master, slave) -> None:
    master_layers = getattr(master, "view_layers", None)
    slave_layers = getattr(slave, "view_layers", None)
    if not master_layers or not slave_layers:
        return

    try:
        layers = tuple(master_layers)
    except TypeError:
        active = getattr(master_layers, "active", None)
        layers = (active,) if active is not None else ()

    getter = getattr(slave_layers, "get", None)
    for master_layer in layers:
        slave_layer = getter(master_layer.name) if callable(getter) else None
        if slave_layer is not None:
            copy_rna_properties(
                master_layer,
                slave_layer,
                include_prefixes=("use_pass_", "pass_cryptomatte_"),
            )
            for engine_group in ("cycles", "eevee"):
                copy_property_group(
                    master_layer,
                    slave_layer,
                    engine_group,
                    include_prefixes=("use_pass_",),
                )


def get_target_scenes(master_scene, scenes: Sequence[object]) -> list[object]:
    targets = []
    for scene in scenes:
        if scene == master_scene:
            continue
        settings = getattr(scene, "caintool", None)
        if settings is not None and getattr(settings, "render_sync_target", False):
            targets.append(scene)
    return targets


def perform_sync(
    master_scene,
    scenes: Sequence[object],
    options: RenderSyncOptions | None = None,
) -> RenderSyncResult:
    targets = get_target_scenes(master_scene, scenes)
    result = RenderSyncResult(skipped_count=0)

    for slave in targets:
        sync_scene_data(master_scene, slave, options)
        result.synced_count += 1

    return result

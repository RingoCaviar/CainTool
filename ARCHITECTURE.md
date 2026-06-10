# CainTool Architecture

## Goals

- Follow the Blender extension package layout used by Blender 5.0 and newer.
- Keep UI code thin and move behavior into reusable modules.
- Make feature growth predictable: one feature module, one service module when needed.
- Avoid context-heavy operator logic leaking into unrelated files.

## Directory Layout

```text
caintool/
|- __init__.py
|- blender_manifest.toml
|- constants.py
|- feature_registry.py
|- properties.py
|- registration.py
|- ARCHITECTURE.md
|- features/
|  |- __init__.py
|  |- base.py
|  |- batch_property_tools.py
|  |- collection_tools.py
|  |- common_command_tools.py
|  |- keyframe_transition_tools.py
|  |- object_tools.py
|  |- parent_child_hide_tools.py
|  |- render_sync_tools.py
|  |- scene_render_tools.py
|  `- template_feature.py
|- services/
|  |- __init__.py
|  |- batch_property_service.py
|  |- common_command_service.py
|  |- keyframe_transition_service.py
|  |- object_service.py
|  |- parent_child_hide_service.py
|  |- render_sync_service.py
|  `- scene_render_service.py
`- ui/
   |- __init__.py
   `- panels.py
```

## Layering Rules

1. Keep `ui/` responsible only for panel layout and drawing.
2. Keep `features/` responsible for Blender operators, per-feature UI, and user-facing reports.
3. Keep `services/` responsible for reusable business logic and Blender data manipulation helpers.
4. Keep `registration.py` as the only place that assembles class registration order.
5. Keep `feature_registry.py` as the only place that decides which feature modules are active.

## Runtime Flow

1. Blender loads `__init__.py`.
2. `registration.register()` registers core classes, scene properties, and active feature modules.
3. `ui.panels.CAINTOOL_PT_toolkit` asks `feature_registry` for the enabled feature sections.
4. Each feature module draws its own box in the N panel and dispatches work to a service.

## How To Add A New Feature

1. Copy `features/template_feature.py` into a new module, for example `features/export_tools.py`.
2. Add operators and a `draw_feature(layout, context)` function inside that module.
3. If logic can be reused or tested separately, place it in `services/`.
4. Add the new module to `FEATURE_MODULES` in `feature_registry.py`.
5. If the feature needs settings, add them to `CAINTOOL_PG_settings` in `properties.py`.

## How To Migrate Loose Scripts Into This Add-on

1. Split each old script into "UI/operator glue" and "real logic".
2. Move pure logic into a service module under `services/`.
3. Wrap that logic in one or more Blender operators inside a feature module.
4. Expose only the feature's controls in the panel; do not call random script files from panel code.
5. When future maintenance matters more than consolidation, keep one migrated script workflow per feature module.

## Build And Validation

Use Blender's extension tooling when Blender is available:

```text
blender --command extension build --source-dir /path/to/caintool
blender --command extension validate /path/to/caintool.zip
```

For local code-only checks outside Blender, compile the package with Python:

```text
python -m py_compile __init__.py registration.py properties.py feature_registry.py
```

## Current Feature Set

- Object Tools: batch rename, apply transforms, set origin to geometry.
- Collection Tools: link selected objects into a named collection without unlinking other memberships.
- Common Command: clear animation data from selected objects and their linked data blocks.
- Batch Property: set one property value across the current object selection.
- Keyframe Transition: create offset keyframe transitions from current values.
- Parent Child Hide: hide selected parent hierarchies and restore stored visibility states.
- Render Sync: sync the current scene render settings to checked target scenes.
- Scene Render: apply shared Cycles sample settings across all scenes.
- Template Feature: disabled example module used as a safe starting point for future additions.

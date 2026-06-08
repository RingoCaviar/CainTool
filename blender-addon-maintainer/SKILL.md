---
name: blender-addon-maintainer
description: Maintain, refactor, and extend the modular Blender N-panel extension scaffold in this workspace. Use when Codex needs to add a new Blender tool to the N panel, migrate loose Blender Python scripts into a structured add-on, update Blender extension metadata, adjust registration flow, or keep the addon architecture clean and easy to maintain.
---

# Blender Addon Maintainer

## Quick Start

Use this skill to work on the Blender extension at `outputs/vivi_n_panel_toolkit`.

Follow the existing layering:

- `ui/` draws panels only.
- `features/` owns operators and per-feature UI.
- `services/` owns reusable logic.
- `registration.py` owns registration order.
- `feature_registry.py` decides which feature modules are active.

## Workflow

1. Inspect `outputs/vivi_n_panel_toolkit/ARCHITECTURE.md` before making structural changes.
2. Keep new N-panel functionality inside a dedicated feature module under `features/`.
3. Move reusable or script-derived logic into a service module under `services/`.
4. Add the feature module to `feature_registry.py`.
5. Add new scene settings only through `properties.py`.
6. Preserve Blender extension compatibility by keeping `blender_manifest.toml` valid for Blender 5.0 and newer.

## Rules

- Do not place unrelated operator logic in `__init__.py`.
- Do not call ad hoc loose scripts directly from panel drawing code.
- Do not mix property definitions into feature modules unless a feature has a very strong reason to own custom registration hooks.
- Prefer safe, explicit operators that report errors clearly in Blender.
- Keep extension metadata aligned with Blender's extension manifest rules.

## Common Tasks

### Add a new feature

1. Copy `features/template_feature.py` into a new module.
2. Add operator classes and a `draw_feature(layout, context)` function.
3. Add the module to `FEATURE_MODULES` in `feature_registry.py`.
4. Add service helpers if the feature does more than trivial Blender API calls.
5. Keep user-facing labels and reports concise.

### Migrate an old loose script

1. Identify the real behavior in the old script.
2. Extract pure logic or data manipulation into `services/`.
3. Wrap the behavior in one or more Blender operators in `features/`.
4. Expose controls in the N panel only after the operator API is clean.
5. If the old script bundles multiple workflows, split them into separate operators or feature modules.

### Update extension metadata

1. Keep `schema_version = "1.0.0"` unless Blender's official schema changes.
2. Keep `type = "add-on"`.
3. Keep `blender_version_min` at or above the minimum supported Blender version.
4. Use Blender-supported tags only.
5. Declare permissions only when the add-on truly needs them.

## References

- Read `references/addon-architecture.md` when the request is about structure, extension points, or migration strategy.
- Read `outputs/vivi_n_panel_toolkit/ARCHITECTURE.md` when editing the addon itself.

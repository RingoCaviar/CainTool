# Blender Addon Architecture Reference

## Scope

This reference supports maintenance of `outputs/vivi_n_panel_toolkit`, a Blender 5.0+ extension-style add-on that exposes tools in the 3D Viewport N panel.

## Key Files

- `blender_manifest.toml`: Blender extension metadata.
- `__init__.py`: package entry that exposes `register()` and `unregister()`.
- `registration.py`: central registration order.
- `properties.py`: scene-level settings used by the N panel.
- `feature_registry.py`: list of active feature modules.
- `features/*.py`: operators and feature-specific panel drawing.
- `services/*.py`: reusable logic, migration target for loose scripts.
- `ui/panels.py`: top-level N-panel UI.

## Maintenance Heuristics

- Add one feature module per workflow area, not one file per button.
- Prefer service helpers when logic may be reused by multiple operators.
- Keep Blender context-sensitive operator calls wrapped in a narrow service API.
- Keep panel drawing declarative and simple.
- Favor additive collection linking over destructive relinking unless the user explicitly wants a move workflow.

## Migration Pattern For Existing Scripts

Given a loose script:

1. Remove top-level execution side effects.
2. Convert hard-coded values into operator properties or scene settings.
3. Move reusable logic into `services/`.
4. Create Blender operators under `features/`.
5. Add user controls to the feature's `draw_feature()` function.
6. Register the feature by adding it to `FEATURE_MODULES`.

## Validation Checklist

- The add-on still exposes `register()` and `unregister()`.
- Every registered class is imported through `registration.py`.
- New feature modules are listed in `feature_registry.py`.
- New scene settings are defined in `properties.py`.
- `blender_manifest.toml` remains valid for Blender 5.0+.

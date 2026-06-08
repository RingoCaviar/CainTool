bl_info = {
    "name": "CainTool",
    "author": "CainTool",
    "version": (0, 1, 0),
    "blender": (4, 2, 0),
    "location": "View3D > Sidebar > CainTool",
    "description": "Modular Blender tools for the 3D View N panel",
    "category": "3D View",
}

from .registration import register, unregister

__all__ = ("register", "unregister")

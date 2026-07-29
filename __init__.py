bl_info = {
    "name": "CainTool",
    "author": "CainTool",
    "version": (0, 5, 0),
    "blender": (4, 2, 0),
    "location": "View3D > Sidebar > CainTool",
    "description": "Modular Blender tools with external resource management",
    "category": "3D View",
}

from .registration import register, unregister

__all__ = ("register", "unregister")

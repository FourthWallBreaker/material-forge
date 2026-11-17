"""Material Forge - procedural materials from a text prompt, inside Blender.

Offline presets handle common requests instantly; an OpenAI-compatible model
is used as a fallback for anything the vocabulary doesn't know.
"""

bl_info = {
    "name": "Material Forge",
    "author": "AI-1",
    "version": (0, 3, 1),
    "blender": (5, 0, 0),
    "location": "3D Viewport > Sidebar > Forge",
    "description": "Generate procedural shader node graphs from a prompt",
    "category": "Material",
}

import bpy

from . import builder, compat, llm, node_lib, ops, presets, ui

CLASSES = (*ui.CLASSES, *ops.CLASSES)


def register():
    for cls in CLASSES:
        bpy.utils.register_class(cls)
    ui.register_props()


def unregister():
    ui.unregister_props()
    for cls in reversed(CLASSES):
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()

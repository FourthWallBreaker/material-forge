"""Version shims so the add-on keeps working across Blender 4.x and 5.x.

Known differences that matter here:

* Blender 5.0: ``Material.use_nodes`` is deprecated and has no effect; a
  material created with ``bpy.data.materials.new()`` already carries a node
  tree. On 4.x the flag is still required.
* The Principled BSDF was renamed socket-wise in 4.0 (handled in node_lib).
* Node tree building itself (``tree.nodes.new`` / ``tree.links.new``) is
  unchanged in 5.0.
"""

import bpy

BLENDER_VERSION = tuple(bpy.app.version)
IS_5 = BLENDER_VERSION >= (5, 0, 0)


class BuildError(Exception):
    """Raised when a material spec cannot be turned into a node tree."""


def new_material(name):
    """Create a material and guarantee it has an editable node tree."""
    mat = bpy.data.materials.new(name)

    if mat.node_tree is None:
        if IS_5:
            # Should not happen on 5.0+, but fail loudly rather than silently
            # producing a material with no nodes.
            raise BuildError(
                "Blender did not create a node tree for the material "
                f"(version {'.'.join(map(str, BLENDER_VERSION))})"
            )
        mat.use_nodes = True

    if mat.node_tree is None:
        raise BuildError("Material has no node tree; cannot build nodes")
    return mat


def clear_nodes(tree):
    """Remove every node so we always build from a known-empty tree."""
    for node in list(tree.nodes):
        tree.nodes.remove(node)


def get_or_create(tree, bl_idname, *, create=True):
    node = next((n for n in tree.nodes if n.bl_idname == bl_idname), None)
    if node is None and create:
        node = tree.nodes.new(bl_idname)
    return node


def ensure_surface_output(tree):
    """Return the Material Output node, creating and linking it if needed."""
    output = get_or_create(tree, "ShaderNodeOutputMaterial")
    surf = output.inputs.get("Surface")
    if surf is None:
        raise BuildError("Material Output node has no 'Surface' input")
    if not surf.is_linked:
        bsdf = ensure_principled(tree)
        tree.links.new(bsdf.outputs["BSDF"], surf)
    return output


def ensure_principled(tree):
    bsdf = get_or_create(tree, "ShaderNodeBsdfPrincipled")
    if bsdf is None:
        # Fallback for exotic builds where the bundled node is unavailable.
        bsdf = tree.nodes.new("ShaderNodeBsdfPrincipled")
    return bsdf


def assign_to_object(obj, mat):
    """Push *mat* into the object's material slots, reusing an empty slot."""
    if obj is None or not hasattr(obj, "material_slots"):
        return

    slot_index = obj.active_material_index
    slots = obj.material_slots

    if slots:
        if 0 <= slot_index < len(slots) and slots[slot_index].material is None:
            slots[slot_index].material = mat
            return
        slots[slot_index].material = mat
        return

    obj.data.materials.append(mat)

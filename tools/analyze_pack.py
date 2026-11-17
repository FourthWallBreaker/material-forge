"""Walk a pack of reference .blend files and record what every material is made of.

For each .blend:
  - dumps a JSON summary: every material, its node-type inventory, link count,
    and the key Principled BSDF values it uses (or None when linked)
  - renders one Cycles contact sheet of up to MAX_PER_SHEET materials on
    spheres, using the same dark-studio look as tests/render_presets.py so
    reference materials and preset materials can be compared fairly

Output layout (created as needed):
    <out>/sheets/<stem>.png        one sheet per file
    <out>/index.json               merged manifest of every file + material

Usage (one Blender process opens every file itself, much faster than one
launch per file):

    blender --background --factory-startup -noaudio --python tools/analyze_pack.py -- ^
        --pack reference/B3DMatPack --out reference/analysis --res 1000x700
"""

import json
import math
import pathlib
import sys

import bpy
from mathutils import Vector

MAX_PER_SHEET = 24
SPACING = 2.4
RADIUS = 1.1

# Node types that come from other registrations (physics nodes, OSL groups in
# some packs) and are not shader-relevant; still counted, but flagged.
NONSHADER_HINTS = {"ShaderNodeOSL"}


def parse_args():
    argv = sys.argv
    argv = argv[argv.index("--") + 1 :] if "--" in argv else []
    opts = {"pack": None, "out": None, "res": (1000, 700), "samples": 16}
    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg == "--pack" and i + 1 < len(argv):
            opts["pack"] = pathlib.Path(argv[i + 1]).resolve()
        elif arg == "--out" and i + 1 < len(argv):
            opts["out"] = pathlib.Path(argv[i + 1]).resolve()
        elif arg == "--res" and i + 1 < len(argv):
            w, _, h = argv[i + 1].partition("x")
            opts["res"] = (int(w), int(h or w))
        elif arg == "--samples" and i + 1 < len(argv):
            opts["samples"] = int(argv[i + 1])
        i += 1
    if opts["pack"] is None or opts["out"] is None:
        raise SystemExit("usage: analyze_pack.py -- <pack-dir> --out <out-dir>")
    return opts


def look_at(obj, target):
    direction = Vector(target) - obj.location
    obj.rotation_mode = "QUATERNION"
    obj.rotation_quaternion = direction.to_track_quat("-Z", "Y")


def socket_default_value(sock):
    """Scalar or 4-vector as plain python, or None when driven by a link."""
    if sock.is_linked:
        return None
    value = getattr(sock, "default_value", None)
    if value is None:
        return None
    try:
        length = len(value)
    except TypeError:
        return round(float(value), 4)
    return [round(float(c), 4) for c in value]


def summarize_material(mat):
    """Everything we can read without evaluating the graph."""
    if not getattr(mat, "use_nodes", False) or mat.node_tree is None:
        return None

    tree = mat.node_tree
    types = {}
    broken_groups = 0
    osl_nodes = 0
    for node in tree.nodes:
        types[node.bl_idname] = types.get(node.bl_idname, 0) + 1
        if node.bl_idname == "ShaderNodeGroup" and node.node_tree is None:
            broken_groups += 1
        if node.bl_idname in NONSHADER_HINTS:
            osl_nodes += 1

    output = next((n for n in tree.nodes if n.bl_idname == "ShaderNodeOutputMaterial"), None)
    bsdf = next(
        (n for n in tree.nodes if n.bl_idname == "ShaderNodeBsdfPrincipled"), None
    )
    if bsdf is None and output is not None:
        surface = output.inputs["Surface"]
        if surface.is_linked:
            bsdf = surface.links[0].from_node

    info = {
        "name": mat.name,
        "nodes": len(tree.nodes),
        "links": len(tree.links),
        "node_types": types,
        "broken_groups": broken_groups,
        "osl_nodes": osl_nodes,
        "has_material_output": output is not None,
        "uses_principled": bsdf is not None,
    }
    if bsdf is not None:
        info["bsdf"] = {
            sock.name: socket_default_value(sock)
            for sock in bsdf.inputs
            if sock.name in ("Base Color", "Metallic", "Roughness", "IOR", "Alpha")
            and socket_default_value(sock) is not None
        }
    return info


def renderable(mat):
    info = summarize_material(mat)
    if info is None:
        return None
    # Skip materials whose graphs reference missing data or OSL shaders that
    # CPU Cycles cannot evaluate - they would poison the whole sheet render.
    if info["broken_groups"] or info["osl_nodes"]:
        info["skip_reason"] = "broken group or OSL"
        return None
    return info


def build_studio_scene(scene, materials, res):
    """Our standard dark studio: spheres grid, ortho camera, key + fill."""
    for obj in list(scene.objects):
        bpy.data.objects.remove(obj, do_unlink=True)
    for block in (bpy.data.meshes, bpy.data.materials, bpy.data.lights,
                  bpy.data.cameras, bpy.data.worlds, bpy.data.images):
        for x in list(block):
            if x.users == 0:
                block.remove(x)

    columns = min(6, len(materials)) or 1
    rows = math.ceil(len(materials) / columns)

    for index, mat in enumerate(materials):
        col, row = index % columns, index // columns
        location = (col * SPACING, -row * SPACING, 0.0)
        bpy.ops.mesh.primitive_uv_sphere_add(
            radius=RADIUS, segments=48, ring_count=24, location=location
        )
        sphere = bpy.context.object
        for poly in sphere.data.polygons:
            poly.use_smooth = True
        sphere.data.materials.append(mat)

    center = Vector(((columns - 1) * SPACING / 2, -(rows - 1) * SPACING / 2, 0.0))
    span = max(columns * SPACING, rows * SPACING)

    cam_data = bpy.data.cameras.new("RefCam")
    cam_data.type = "ORTHO"
    cam_data.ortho_scale = max(
        columns * SPACING * 1.15, rows * SPACING * 1.15 * res[0] / res[1]
    )
    cam = bpy.data.objects.new("RefCam", cam_data)
    cam.location = center + Vector((0.0, -span * 1.2, span * 0.9))
    look_at(cam, center)
    scene.collection.objects.link(cam)
    scene.camera = cam

    key_data = bpy.data.lights.new("RefKey", type="AREA")
    key_data.energy = 1200
    key_data.size = span * 0.9
    key = bpy.data.objects.new("RefKey", key_data)
    key.location = center + Vector((-span * 0.5, -span * 0.7, span * 1.1))
    look_at(key, center)
    scene.collection.objects.link(key)

    fill_data = bpy.data.lights.new("RefFill", type="AREA")
    fill_data.energy = 400
    fill_data.size = span
    fill = bpy.data.objects.new("RefFill", fill_data)
    fill.location = center + Vector((span * 0.8, -span * 0.3, span * 0.6))
    look_at(fill, center)
    scene.collection.objects.link(fill)

    world = bpy.data.worlds.new("RefWorld")
    world.node_tree.nodes.new("ShaderNodeBackground")
    bg = world.node_tree.nodes["Background"]
    bg.inputs["Color"].default_value = (0.05, 0.05, 0.06, 1.0)
    bg.inputs["Strength"].default_value = 0.5
    scene.world = world
    return center


def analyze_one(path, scene, opts):
    """Open one file, summarize + render its materials. Returns manifest entry."""
    try:
        bpy.ops.wm.open_mainfile(filepath=str(path))
    except Exception as exc:  # noqa: BLE001 - pack files can be corrupt
        return {"file": path.name, "error": f"cannot open: {exc}"}

    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = opts["samples"]
    scene.cycles.use_denoising = True
    scene.render.resolution_x, scene.render.resolution_y = opts["res"]
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"

    mats = list(bpy.data.materials)
    usable, manifest = [], []
    for mat in mats:
        info = renderable(mat)
        if info is not None:
            usable.append(mat)
        manifest.append(info or {"name": mat.name, "skip_reason": "not node-based or unloadable"})

    entry = {
        "file": path.name,
        "total_materials": len(mats),
        "rendered_materials": len(usable),
        "materials": manifest,
    }

    if not usable:
        entry["sheet"] = None
        return entry

    shown = usable[:MAX_PER_SHEET]
    if len(usable) > MAX_PER_SHEET:
        entry["note"] = f"sheet shows first {MAX_PER_SHEET} of {len(usable)}"

    build_studio_scene(scene, shown, opts["res"])
    sheet_dir = opts["out"] / "sheets"
    sheet_dir.mkdir(parents=True, exist_ok=True)
    out_png = sheet_dir / (path.stem + ".png")
    scene.render.filepath = str(out_png)
    try:
        bpy.ops.render.render(write_still=True)
        entry["sheet"] = out_png.name
    except Exception as exc:  # noqa: BLE001 - a single bad node can poison a render
        entry["sheet"] = None
        entry["error"] = f"render failed: {exc}"
        traceback.print_exc()
    return entry


def main():
    opts = parse_args()
    blends = sorted(opts["pack"].glob("*.blend"))
    print(f"[pack] {len(blends)} blend files in {opts['pack']}")

    results = []
    for path in blends:
        print(f"[open] {path.name} ...")
        try:
            entry = analyze_one(path, bpy.context.scene, opts)
        except Exception as exc:  # noqa: BLE001 - keep walking after a failure
            print(f"[fail] {path.name}: {exc}")
            traceback.print_exc()
            entry = {"file": path.name, "error": str(exc)}
        results.append(entry)
        print(f"[done] {path.name}: {entry.get('total_materials', '?')} materials "
              f"({entry.get('rendered_materials', 0)} rendered)")

    opts["out"].mkdir(parents=True, exist_ok=True)
    index_path = opts["out"] / "index.json"
    index_path.write_text(
        json.dumps({"pack": opts["pack"].name, "files": results}, indent=1),
        encoding="utf-8",
    )
    total = sum(e.get("total_materials", 0) for e in results)
    rendered = sum(e.get("rendered_materials", 0) for e in results)
    print(f"[pack] manifest -> {index_path}")
    print(f"[pack] {total} materials, {rendered} rendered to {opts['out'] / 'sheets'}")


if __name__ == "__main__":
    main()

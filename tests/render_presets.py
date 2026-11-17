r"""Headless verification harness for Material Forge.

Builds every preset on a UV sphere, renders a contact sheet to PNG, and prints
what happened. This is the "does it actually look like anything" test that a
pure-Python smoke test cannot do.

Usage (from the vault root):

    & $BLENDER --background --factory-startup -noaudio ^
        --python tests/render_presets.py -- --out renders\presets.png

Optional args after ``--``:
    --out PATH       output PNG (default renders/presets.png)
    --keys A,B,C     only these preset keys
    --engine NAME    BLENDER_EEVEE_NEXT | BLENDER_EEVEE | CYCLES | AUTO
    --res WxH        default 1200x900
    --samples N      Cycles samples, default 24
"""

import math
import os
import sys

import bpy
from mathutils import Vector

REPO = None


def _find_repo():
    """Blender rewrites the CWD, so hunt for the package instead of trusting it."""
    here = os.path.dirname(os.path.abspath(__file__))
    candidates = [
        os.environ.get("MATERIAL_FORGE_REPO"),
        os.path.dirname(here),
        os.getcwd(),
        os.path.dirname(os.getcwd()),
    ]
    seen = []
    for candidate in candidates:
        if not candidate:
            continue
        seen.append(candidate)
        if os.path.isfile(os.path.join(candidate, "material_forge", "__init__.py")):
            return candidate
    raise SystemExit(f"material_forge not found; looked in {seen}")


if REPO is None:
    REPO = _find_repo()
if REPO not in sys.path:
    sys.path.insert(0, REPO)

from material_forge import builder, presets  # noqa: E402


def parse_args():
    argv = sys.argv
    argv = argv[argv.index("--") + 1 :] if "--" in argv else []
    opts = {
        "out": os.path.join(REPO, "renders", "presets.png"),
        "keys": None,
        "engine": "AUTO",
        "res": (1200, 900),
        "samples": 24,
    }
    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg == "--out" and i + 1 < len(argv):
            opts["out"] = argv[i + 1]
            i += 2
        elif arg == "--keys" and i + 1 < len(argv):
            opts["keys"] = [k.strip().upper() for k in argv[i + 1].split(",")]
            i += 2
        elif arg == "--engine" and i + 1 < len(argv):
            opts["engine"] = argv[i + 1].upper()
            i += 2
        elif arg == "--res" and i + 1 < len(argv):
            w, _, h = argv[i + 1].partition("x")
            opts["res"] = (int(w), int(h or w))
            i += 2
        elif arg == "--samples" and i + 1 < len(argv):
            opts["samples"] = int(argv[i + 1])
            i += 2
        else:
            i += 1
    return opts


def look_at(obj, target):
    direction = Vector(target) - obj.location
    obj.rotation_mode = "QUATERNION"
    obj.rotation_quaternion = direction.to_track_quat("-Z", "Y")


def build_scene(keys, opts):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene

    selected = [p for p in presets.PRESETS if keys is None or p["key"] in keys]
    columns = min(4, len(selected)) or 1
    rows = math.ceil(len(selected) / columns)
    spacing = 2.9

    built = []
    for index, preset in enumerate(selected):
        col, row = index % columns, index // columns
        location = (col * spacing, -row * spacing, 0.0)
        bpy.ops.mesh.primitive_uv_sphere_add(
            radius=1.1, segments=64, ring_count=32, location=location
        )
        sphere = bpy.context.object
        sphere.name = preset["key"]
        for poly in sphere.data.polygons:
            poly.use_smooth = True

        material = builder.build(presets.preset_spec(preset["key"]))
        sphere.data.materials.append(material)
        built.append((preset["key"], material.name))

    center = Vector(
        (
            (columns - 1) * spacing / 2,
            -(rows - 1) * spacing / 2,
            0.0,
        )
    )
    span = max(columns * spacing, rows * spacing)
    width, height = opts["res"]
    aspect = width / height

    # Orthographic three-quarter view: no perspective drift between rows, and
    # the frame is sized from the grid so nothing gets clipped.
    cam_data = bpy.data.cameras.new("Cam")
    cam_data.type = "ORTHO"
    cam_data.ortho_scale = max(columns * spacing * 1.15, rows * spacing * 1.15 * aspect)
    cam = bpy.data.objects.new("Cam", cam_data)
    cam.location = center + Vector((0.0, -span * 1.2, span * 0.9))
    look_at(cam, center)
    scene.collection.objects.link(cam)
    scene.camera = cam

    # Key + fill so relief and colour both read.
    key_data = bpy.data.lights.new("Key", type="AREA")
    key_data.energy = 1200
    key_data.size = span * 0.9
    key = bpy.data.objects.new("Key", key_data)
    key.location = center + Vector((-span * 0.5, -span * 0.7, span * 1.1))
    look_at(key, center)
    scene.collection.objects.link(key)

    fill_data = bpy.data.lights.new("Fill", type="AREA")
    fill_data.energy = 400
    fill_data.size = span
    fill = bpy.data.objects.new("Fill", fill_data)
    fill.location = center + Vector((span * 0.8, -span * 0.3, span * 0.6))
    look_at(fill, center)
    scene.collection.objects.link(fill)

    world = bpy.data.worlds.new("World")
    world.use_nodes = True
    bg = world.node_tree.nodes.get("Background")
    if bg:
        bg.inputs["Color"].default_value = (0.05, 0.05, 0.06, 1.0)
        bg.inputs["Strength"].default_value = 0.5
    scene.world = world

    return scene, center, built


def configure_render(scene, opts):
    width, height = opts["res"]
    scene.render.resolution_x = width
    scene.render.resolution_y = height
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.film_transparent = False

    wanted = opts["engine"]
    if wanted == "AUTO":
        # Cycles is the reference engine for this build: physically accurate
        # transmission and bump, and what the B3D reference pack is checked
        # against. EEVEE stays as a fast fallback, not the default.
        wanted = "CYCLES"

    # Do not trust the static enum list: in background mode the Cycles engine
    # is enabled yet absent from it. Try-assign, and only fall back if the
    # assignment itself is rejected.
    try:
        scene.render.engine = wanted
    except TypeError:
        for candidate in ("BLENDER_EEVEE_NEXT", "BLENDER_EEVEE"):
            try:
                scene.render.engine = candidate
                wanted = candidate
                break
            except TypeError:
                continue
        else:
            raise RuntimeError(f"No usable render engine for {wanted!r}")

    scene.render.engine = wanted
    if wanted == "CYCLES":
        scene.cycles.samples = opts["samples"]
        scene.cycles.use_denoising = True
        scene.cycles.device = "CPU"
    else:
        eevee = getattr(scene, "eevee", None)
        if eevee is not None and hasattr(eevee, "taa_render_samples"):
            eevee.taa_render_samples = 32

    return wanted


def main():
    opts = parse_args()
    scene, center, built = build_scene(opts["keys"], opts)

    print(f"[scene] {len(built)} materials built")
    for key, name in built:
        print(f"  built {key:14s} -> {name}")

    engine = configure_render(scene, opts)
    out = os.path.abspath(opts["out"])
    os.makedirs(os.path.dirname(out), exist_ok=True)
    scene.render.filepath = out

    print(f"[render] engine={engine} res={opts['res']} out={out}")
    bpy.ops.render.render(write_still=True)
    print(f"[done] exists={os.path.exists(out)} size={os.path.getsize(out) if os.path.exists(out) else 0}")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        import traceback

        traceback.print_exc()
        sys.exit(1)

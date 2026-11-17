# Material Forge

Blender add-on: procedural shader node graphs from a text prompt.

Hybrid engine — offline preset vocabulary first, OpenAI-compatible model as the
fallback for anything the vocabulary doesn't recognise.

- **Blender:** 5.2.2 LTS (developed and verified against it; 4.x handled by \compat.py\)
- **Verification engine:** Cycles (CPU, 24 samples, denoised). EEVEE is a fallback via --engine
- **Blender exe:** `D:\Program Files (x86)\Steam\steamapps\common\Blender\blender.exe`

## Layout

```
material_forge/          add-on package (installable as a zip of this folder)
  node_lib.py            whitelisted node registry + socket-name resolution
  builder.py             spec validation -> node tree construction
  presets.py             12 offline material specs + keyword matching
  llm.py                 OpenAI-compatible client (urllib only)
  ops.py                 operators: material_forge.generate / .surprise
  ui.py                  preferences, scene properties, sidebar panel
  compat.py              Blender 4.x / 5.x shims
tests/
  smoke_test.py          validates presets + spec variants, no Blender needed
  render_presets.py      headless contact sheet render (the visual check)
tools/
  blender.cmd            wrapper around the Blender executable
dist/                    built add-on zips
renders/                 render output (git-ignored)
```

## Quick start

```powershell
# logic tests, no Blender
python tests\smoke_test.py

# visual check: 12 materials on spheres -> renders\presets.png (Cycles, ~1-2 min)
& .\tools\blender.cmd --background --factory-startup -noaudio --python-exit-code 1 `
    --python .\tests\render_presets.py -- --out .\renders\presets.png```

`--factory-startup` plus an explicit `sys.path` insert means tests never depend
on what is installed in Blender's user prefs. Scripts find the repo by walking
up from `tests/`, or via the `MATERIAL_FORGE_REPO` environment variable.

## Install into Blender

Zip the `material_forge` folder, then **Preferences > Add-ons > Install from Disk**.
Or junction it into the user scripts dir for live editing:

```powershell
New-Item -ItemType Junction -Path "$env:APPDATA\Blender Foundation\Blender\5.2\scripts\addons\material_forge" `
    -Target "C:\Users\dorro\dev\material-forge\material_forge"
```

## Spec format

One JSON shape drives everything, so presets and model output share a code path.

```json
{
  "name": "Mossy Stone",
  "nodes": [
    {"id": "noise", "type": "noise", "inputs": {"Scale": 8.0}},
    {"id": "ramp", "type": "ramp", "params": {"stops": [[0.0, [0.05,0.05,0.05,1]], [1.0, [0.3,0.3,0.28,1]]]}}
  ],
  "links": ["noise.Fac -> ramp.Fac", "ramp.Color -> bsdf.Base Color"],
  "bsdf": {"Roughness": 0.85}
}
```

`bsdf` (Principled) and `output` (Material Output) are implicit. `bsdf` values
may be literals or socket references, which become links.

## Design notes

- **The model never emits `bl_idname`s.** It picks short keys from `node_lib.NODE_TYPES`;
  the registry generates the system prompt and validates the result, so prompt and
  validator cannot drift apart.
- **Socket names resolve through aliases** (`node_lib.find_socket`). The Principled
  BSDF was renamed wholesale in 4.0; 5.2 added deprecations (`World.use_nodes`).
  Missing sockets degrade instead of crashing the build.
- **Blender 5.x:** `Material.use_nodes = True` is deprecated/no-op — new materials
  already carry a tree. Handled in `compat.new_material`.

## Status

v0.1.0 — all 12 presets build in real Blender with no socket errors. Known
visual issues are tracked per-material in the vault note.

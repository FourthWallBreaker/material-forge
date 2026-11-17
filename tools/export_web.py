"""Emit build/data.js for the Project 4 web demo from the real preset library.

The web build must show the same matching rules the Blender add-on uses, so the
data is generated from `material_forge/presets.py` instead of being retyped.

Run from the repo root:  python tools/export_web.py <path-to-vibe-coding\\build>
"""

import json
import pathlib
import sys

# presets.py has no Blender dependency, but the package __init__ does, so load
# the module file directly instead of importing the package.
import importlib.util
import pathlib

_here = pathlib.Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location(
    "forge_presets", _here.parent / "material_forge" / "presets.py"
)
presets = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(presets)


def main():
    out_dir = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else None
    if out_dir is None or not out_dir.is_dir():
        raise SystemExit(f"usage: {sys.argv[0]} <build-folder>")

    entries = []
    for preset in presets.PRESETS:
        entries.append(
            {
                "key": preset["key"],
                "label": preset["label"],
                "keywords": preset["keywords"],
                "spec": preset["spec"],
                "render": f"renders/{preset['key']}.png",
            }
        )

    data = {"presets": entries}
    script = "const FORGE_DATA = " + json.dumps(data, separators=(",", ":")) + ";\n"
    (out_dir / "data.js").write_text(script, encoding="utf-8")
    print(f"wrote {out_dir / 'data.js'} ({len(script)} bytes, {len(entries)} presets)")


if __name__ == "__main__":
    main()

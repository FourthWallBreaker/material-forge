"""Offline checks for Material Forge - no Blender required.

Stubs just enough of ``bpy`` to import the package, then verifies that every
preset is a structurally valid spec and that the socket names used by presets
agree with the node registry.

Run: python tests/smoke_test.py
"""

import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def install_bpy_stub():
    bpy = types.ModuleType("bpy")
    bpy.app = types.SimpleNamespace(version=(5, 0, 0))

    props = types.ModuleType("bpy.props")
    for name in (
        "StringProperty",
        "BoolProperty",
        "FloatProperty",
        "IntProperty",
        "EnumProperty",
        "PointerProperty",
    ):
        setattr(props, name, lambda *a, **kw: None)
    bpy.props = props

    bpy_types = types.ModuleType("bpy.types")
    for name in (
        "Operator",
        "Panel",
        "AddonPreferences",
        "PropertyGroup",
        "Scene",
        "Material",
        "Node",
    ):
        setattr(bpy_types, name, type(name, (object,), {}))
    bpy.types = bpy_types

    sys.modules["bpy"] = bpy


install_bpy_stub()

from material_forge import builder, node_lib, presets  # noqa: E402

FAILURES = []


def check(label, condition, detail=""):
    if condition:
        print(f"  ok    {label}")
    else:
        FAILURES.append(f"{label} {detail}".strip())
        print(f"  FAIL  {label} {detail}")


def check_spec(label, spec):
    try:
        spec, nodes, links, bsdf = builder.validate(spec)
    except builder.BuildError as exc:
        FAILURES.append(f"{label}: {exc}")
        print(f"  FAIL  {label}: {exc}")
        return

    print(f"  ok    {label} ({len(nodes)} nodes, {len(links)} links)")

    for node in nodes:
        meta = node_lib.NODE_TYPES[node["type"]]
        for socket in node["inputs"]:
            if socket not in meta["inputs"]:
                FAILURES.append(f"{label}: {node['type']} has no input {socket}")
                print(f"  FAIL  {label}: {node['type']} has no input {socket!r}")
        for param in node["params"]:
            if param not in (meta.get("params") or {}):
                FAILURES.append(f"{label}: {node['type']} has no param {param}")
                print(f"  FAIL  {label}: {node['type']} has no param {param!r}")

    for from_node, from_sock, to_node, to_sock in links:
        if from_node == "bsdf":
            continue
        src = next((n for n in nodes if n["id"] == from_node), None)
        if src is None:
            FAILURES.append(f"{label}: link from unknown node {from_node}")
            continue
        if from_sock not in node_lib.NODE_TYPES[src["type"]]["outputs"]:
            FAILURES.append(f"{label}: {src['type']} has no output {from_sock}")
            print(f"  FAIL  {label}: {src['type']} has no output {from_sock!r}")

        if to_node == "bsdf":
            if to_sock not in node_lib.BSDF_INPUTS:
                FAILURES.append(f"{label}: BSDF has no input {to_sock}")
                print(f"  FAIL  {label}: BSDF has no input {to_sock!r}")
            continue
        dst = next((n for n in nodes if n["id"] == to_node), None)
        if dst is None:
            FAILURES.append(f"{label}: link to unknown node {to_node}")
            continue
        if to_sock not in node_lib.NODE_TYPES[dst["type"]]["inputs"]:
            FAILURES.append(f"{label}: {dst['type']} has no input {to_sock}")
            print(f"  FAIL  {label}: {dst['type']} has no input {to_sock!r}")

    for socket in bsdf:
        if socket not in node_lib.BSDF_INPUTS:
            FAILURES.append(f"{label}: BSDF value on unknown socket {socket}")
            print(f"  FAIL  {label}: BSDF value on unknown socket {socket!r}")


def main():
    print("Presets:")
    for preset in presets.PRESETS:
        check_spec(preset["key"], presets.preset_spec(preset["key"]))

    print("\nMatching:")
    cases = {
        "crusty old brick wall": "BRICK",
        "rusted iron plate": "RUST",
        "wet mossy rock": "MOSSY_STONE",
        "brushed aluminium": "METAL_BRUSHED",
        "cheap red plastic": "PLASTIC",
        "deep sea water": "WATER",
    }
    for prompt, expected in cases.items():
        preset, score = presets.best_match(prompt)
        got = preset["key"] if preset else None
        check(f"{prompt!r} -> {got} (score {score})", got == expected, f"expected {expected}")

    print("\nSpec variants:")
    check_spec(
        "string links + bsdf refs",
        {
            "name": "Variants",
            "nodes": [
                {"id": "noise", "type": "noise", "inputs": {"Scale": 4}},
                {"id": "ramp", "type": "ramp", "params": {"stops": [[0, [0, 0, 0, 1]], [1, [1, 1, 1, 1]]]}},
            ],
            "links": ["noise.Fac -> ramp.Fac"],
            "bsdf": {"Base Color": "ramp.Color", "Roughness": 0.5},
        },
    )
    check_spec(
        "wrapped + dict links",
        {
            "material": {
                "nodes": [{"id": "v", "type": "voronoi"}, {"id": "r", "type": "ramp"}],
                "links": [{"from": "v.Distance", "to": "r.Fac"}],
                "bsdf": {"Base Color": "r.Color"},
            }
        },
    )

    print("\nBad specs rejected cleanly:")
    for label, spec in [
        ("not a dict", "nope"),
        ("no nodes", {"name": "x"}),
        ("duplicate ids", {"nodes": [{"id": "a", "type": "noise"}, {"id": "a", "type": "noise"}]}),
        ("reserved id", {"nodes": [{"id": "bsdf", "type": "noise"}]}),
        ("bad link", {"nodes": [{"id": "a", "type": "noise"}], "links": ["a. -> b"]}),
    ]:
        try:
            builder.validate(spec)
        except builder.BuildError as exc:
            print(f"  ok    {label}: {exc}")
        else:
            FAILURES.append(f"{label} was accepted")
            print(f"  FAIL  {label} was accepted")

    print("\nPrompt reference length:", len(node_lib.prompt_reference()), "chars")
    print("\n%d failure(s)" % len(FAILURES))
    return 1 if FAILURES else 0


if __name__ == "__main__":
    raise SystemExit(main())

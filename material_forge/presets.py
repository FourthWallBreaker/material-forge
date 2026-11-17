"""Offline material vocabulary.

Every preset is a full spec in the same format the LLM produces, so the
builder only ever sees one thing. Presets are used first: they are instant,
deterministic, and produce well-behaved node graphs. The LLM is a fallback for
prompts the vocabulary doesn't understand.
"""

import copy
import re

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def _n(node_id, type_key, inputs=None, params=None):
    node = {"id": node_id, "type": type_key}
    if inputs:
        node["inputs"] = inputs
    if params:
        node["params"] = params
    return node


def _ramp(node_id, stops, fac_input=None):
    inputs = {}
    if fac_input:
        inputs["Fac"] = fac_input
    return _n(node_id, "ramp", inputs=inputs, params={"stops": stops})


# --------------------------------------------------------------------------
# Presets
# --------------------------------------------------------------------------
PRESETS = [
    {
        "key": "STONE",
        "label": "Stone / Concrete",
        "keywords": ["stone", "rock", "granite", "concrete", "cement", "gravel", "boulder", "flagstone", "slate"],
        "spec": {
            "name": "Stone",
            "nodes": [
                _n("noise", "noise", {"Scale": 9.0, "Detail": 9.0, "Roughness": 0.6, "Distortion": 0.2}),
                _ramp("colour", [
                    [0.0, [0.055, 0.055, 0.052, 1.0]],
                    [0.45, [0.13, 0.128, 0.12, 1.0]],
                    [0.75, [0.235, 0.23, 0.215, 1.0]],
                    [1.0, [0.34, 0.33, 0.31, 1.0]],
                ]),
                _n("grain", "noise", {"Scale": 60.0, "Detail": 6.0, "Roughness": 0.7}),
                _n("roughen", "maprange", {"Value": 0.0, "From Min": 0.0, "From Max": 1.0, "To Min": 0.55, "To Max": 0.95}),
                _n("relief", "bump", {"Strength": 0.35, "Distance": 0.02}),
            ],
            "links": [
                "noise.Fac -> colour.Fac",
                "colour.Color -> bsdf.Base Color",
                "grain.Fac -> roughen.Value",
                "roughen.Result -> bsdf.Roughness",
                "noise.Fac -> relief.Height",
                "relief.Normal -> bsdf.Normal",
            ],
            "bsdf": {"Metallic": 0.0},
        },
    },
    {
        "key": "MOSSY_STONE",
        "label": "Mossy Stone",
        "keywords": ["moss", "mossy", "lichen", "overgrown", "algae", "damp", "damp stone"],
        "spec": {
            "name": "Mossy Stone",
            "nodes": [
                _n("noise", "noise", {"Scale": 8.0, "Detail": 10.0, "Roughness": 0.62, "Distortion": 0.3}),
                _ramp("rock", [
                    [0.0, [0.05, 0.05, 0.048, 1.0]],
                    [0.55, [0.14, 0.135, 0.125, 1.0]],
                    [1.0, [0.28, 0.27, 0.25, 1.0]],
                ]),
                _n("patch", "noise", {"Scale": 3.5, "Detail": 8.0, "Roughness": 0.75}),
                _ramp("moss_mask", [
                    [0.34, [0.0, 0.0, 0.0, 1.0]],
                    [0.52, [1.0, 1.0, 1.0, 1.0]],
                ]),
                _n("moss_col", "mix", {"A": [0.03, 0.09, 0.02, 1.0], "B": [0.16, 0.27, 0.07, 1.0], "Factor": 0.0},
                   {"data_type": "RGBA", "blend_type": "MIX"}),
                _n("mix", "mix", {"Factor": 0.0}, {"data_type": "RGBA", "blend_type": "MIX"}),
                _n("grain", "noise", {"Scale": 55.0, "Detail": 8.0}),
                _n("relief", "bump", {"Strength": 0.45, "Distance": 0.025}),
                _n("rough", "maprange", {"Value": 0.0, "To Min": 0.6, "To Max": 1.0}),
            ],
            "links": [
                "noise.Fac -> rock.Fac",
                "patch.Fac -> moss_mask.Fac",
                "moss_mask.Color -> moss_col.Factor",
                "rock.Color -> mix.A",
                "moss_col.Result -> mix.B",
                "moss_mask.Color -> mix.Factor",
                "mix.Result -> bsdf.Base Color",
                "grain.Fac -> rough.Value",
                "rough.Result -> bsdf.Roughness",
                "noise.Fac -> relief.Height",
                "relief.Normal -> bsdf.Normal",
            ],
            "bsdf": {"Metallic": 0.0, "Sheen Weight": 0.1},
        },
    },
    {
        "key": "BRICK",
        "label": "Brick",
        "keywords": ["brick", "bricks", "brickwork", "masonry", "cobble", "cobblestone", "tile", "tiles", "paving"],
        "spec": {
            "name": "Brick",
            "nodes": [
                _n("brick", "brick", {
                    "Color1": [0.28, 0.09, 0.055, 1.0],
                    "Color2": [0.17, 0.06, 0.04, 1.0],
                    "Mortar": [0.45, 0.43, 0.4, 1.0],
                    "Scale": 5.0,
                    "Mortar Size": 0.012,
                    "Brick Width": 0.6,
                    "Row Height": 0.25,
                    "Bias": 0.0,
                    "Mortar Smooth": 0.1,
                }),
                _n("grunge", "noise", {"Scale": 22.0, "Detail": 8.0, "Roughness": 0.6}),
                _n("dirty", "mix", {"Factor": 0.0}, {"data_type": "RGBA", "blend_type": "MULTIPLY"}),
                _n("relief", "bump", {"Strength": 0.6, "Distance": 0.03}),
                _n("rough", "maprange", {"Value": 0.0, "To Min": 0.65, "To Max": 0.95}),
            ],
            "links": [
                "brick.Color -> dirty.A",
                "grunge.Color -> dirty.B",
                "dirty.Result -> bsdf.Base Color",
                "brick.Fac -> relief.Height",
                "relief.Normal -> bsdf.Normal",
                "grunge.Fac -> rough.Value",
                "rough.Result -> bsdf.Roughness",
            ],
            "bsdf": {"Metallic": 0.0},
        },
    },
    {
        "key": "WOOD",
        "label": "Wood",
        "keywords": ["wood", "wooden", "timber", "oak", "pine", "walnut", "plank", "planks", "lumber", "bark"],
        "spec": {
            "name": "Wood",
            "nodes": [
                _n("coord", "texcoord"),
                # Reference construction (B3D pack WO_basic_pattern): a RINGS
                # wave warped and fed as the phase space of a BANDS wave, so
                # the elongated rings read as long grain streaks, not stripes.
                _n("rings", "wave", {"Scale": 3.0, "Distortion": 4.0, "Detail": 2.0},
                   {"wave_type": "RINGS", "bands_direction": "DIAGONAL"}),
                _n("grain", "wave", {"Scale": 0.5, "Distortion": 0.0, "Phase Offset": 1.5708},
                   {"wave_type": "BANDS", "bands_direction": "DIAGONAL"}),
                _ramp("grain_col", [
                    [0.0, [0.06, 0.028, 0.014, 1.0]],
                    [0.45, [0.17, 0.09, 0.045, 1.0]],
                    [0.8, [0.29, 0.16, 0.08, 1.0]],
                    [1.0, [0.42, 0.26, 0.13, 1.0]],
                ]),
                _n("fibre", "noise", {"Scale": 250.0, "Detail": 5.0}),
                _n("relief", "bump", {"Strength": 0.3, "Distance": 0.005}),
            ],
            "links": [
                "coord.Generated -> rings.Vector",
                "rings.Fac -> grain.Vector",
                "grain.Fac -> grain_col.Fac",
                "grain_col.Color -> bsdf.Base Color",
                "rings.Fac -> relief.Height",
                "relief.Normal -> bsdf.Normal",
            ],
            "bsdf": {"Roughness": 0.32, "Metallic": 0.0},
        },
    },
    {
        "key": "METAL_BRUSHED",
        "label": "Brushed Metal",
        "keywords": ["metal", "metallic", "steel", "aluminium", "aluminum", "iron", "brushed", "chrome", "titanium"],
        "spec": {
            "name": "Brushed Metal",
            "nodes": [
                _n("coord", "texcoord"),
                _n("stretch", "mapping", {"Scale": [40.0, 1.0, 1.0]}),
                _n("streaks", "noise", {"Scale": 6.0, "Detail": 4.0, "Roughness": 0.5}, {"noise_dimensions": "3D"}),
                _n("rough", "maprange", {"Value": 0.0, "To Min": 0.22, "To Max": 0.55}),
                _n("relief", "bump", {"Strength": 0.12, "Distance": 0.002}),
            ],
            "links": [
                "coord.Object -> stretch.Vector",
                "stretch.Vector -> streaks.Vector",
                "streaks.Fac -> rough.Value",
                "rough.Result -> bsdf.Roughness",
                "streaks.Fac -> relief.Height",
                "relief.Normal -> bsdf.Normal",
            ],
            "bsdf": {"Base Color": [0.72, 0.73, 0.75, 1.0], "Metallic": 1.0},
        },
    },
    {
        "key": "RUST",
        "label": "Rusted Metal",
        "keywords": ["rust", "rusted", "rusty", "corroded", "corrosion", "oxidised", "oxidized", "weathered metal"],
        "spec": {
            "name": "Rusted Metal",
            "nodes": [
                _n("noise", "noise", {"Scale": 6.0, "Detail": 12.0, "Roughness": 0.7, "Distortion": 0.4}),
                _ramp("colour", [
                    [0.0, [0.035, 0.03, 0.028, 1.0]],
                    [0.35, [0.13, 0.055, 0.025, 1.0]],
                    [0.6, [0.26, 0.11, 0.04, 1.0]],
                    [0.85, [0.4, 0.19, 0.07, 1.0]],
                    [1.0, [0.52, 0.29, 0.13, 1.0]],
                ]),
                _n("mask", "voronoi", {"Scale": 18.0, "Randomness": 1.0}, {"feature": "DISTANCE_TO_EDGE"}),
                _n("metal", "maprange", {"Value": 0.0, "To Min": 0.6, "To Max": 0.0}),
                _n("relief", "bump", {"Strength": 0.6, "Distance": 0.02}),
                _n("rough", "maprange", {"Value": 0.0, "To Min": 0.55, "To Max": 0.95}),
            ],
            "links": [
                "noise.Fac -> colour.Fac",
                "colour.Color -> bsdf.Base Color",
                "mask.Distance -> metal.Value",
                "metal.Result -> bsdf.Metallic",
                "noise.Fac -> relief.Height",
                "relief.Normal -> bsdf.Normal",
                "mask.Distance -> rough.Value",
                "rough.Result -> bsdf.Roughness",
            ],
        },
    },
    {
        "key": "MARBLE",
        "label": "Marble",
        "keywords": ["marble", "granite marble", "porcelain", "quartz", "onyx", "veined"],
        "spec": {
            "name": "Marble",
            "nodes": [
                _n("coord", "texcoord"),
                # Reference construction (B3D pack GL_basic_marble): veins are a
                # *stretched* noise crossing a narrow ramp threshold - elongated
                # blobs become irregular branching threads, which a warped wave
                # can never produce (it only makes parallel bands).
                _n("stretch", "mapping", {"Scale": [1.0, 0.3, 1.0], "Rotation": [0.0, 0.0, 0.6]}),
                _n("veins_noise", "noise", {"Scale": 4.0, "Detail": 6.0, "Distortion": 1.5}),
                _ramp("vein_ramp", [
                    [0.42, [0.90, 0.89, 0.87, 1.0]],
                    [0.48, [0.06, 0.06, 0.07, 1.0]],
                    [0.53, [0.07, 0.07, 0.08, 1.0]],
                    [0.59, [0.91, 0.90, 0.88, 1.0]],
                ]),
                _n("tone_noise", "noise", {"Scale": 1.6, "Detail": 4.0}),
                _ramp("tone_ramp", [
                    [0.0, [0.68, 0.67, 0.65, 1.0]],
                    [0.5, [0.87, 0.86, 0.84, 1.0]],
                    [1.0, [0.95, 0.94, 0.92, 1.0]],
                ]),
                _n("tintmix", "mix", {"Factor": 0.9}, {"data_type": "RGBA", "blend_type": "MIX"}),
                _n("relief", "bump", {"Strength": 0.15, "Distance": 0.004}),
            ],
            "links": [
                "coord.Generated -> stretch.Vector",
                "stretch.Vector -> veins_noise.Vector",
                "veins_noise.Fac -> vein_ramp.Fac",
                "tone_noise.Fac -> tone_ramp.Fac",
                "tone_ramp.Color -> tintmix.A",
                "vein_ramp.Color -> tintmix.B",
                "tintmix.Result -> bsdf.Base Color",
                "veins_noise.Fac -> relief.Height",
                "relief.Normal -> bsdf.Normal",
            ],
            "bsdf": {"Roughness": 0.3, "Metallic": 0.0, "IOR": 1.5, "Coat Weight": 0.15},
        },
    },
    {
        "key": "FABRIC",
        "label": "Fabric / Cloth",
        "keywords": ["fabric", "cloth", "textile", "cotton", "linen", "wool", "canvas", "denim", "woven", "velvet", "silk"],
        "spec": {
            "name": "Fabric",
            "nodes": [
                _n("weave_x", "wave", {"Scale": 55.0, "Distortion": 0.4}, {"bands_direction": "X"}),
                _n("weave_y", "wave", {"Scale": 55.0, "Distortion": 0.4}, {"bands_direction": "Y"}),
                _n("weave", "mix", {"Factor": 0.5}, {"data_type": "FLOAT", "blend_type": "MULTIPLY"}),
                _n("fuzz", "noise", {"Scale": 350.0, "Detail": 4.0}),
                _n("relief", "bump", {"Strength": 0.55, "Distance": 0.01}),
                _ramp("colour", [
                    [0.0, [0.16, 0.17, 0.19, 1.0]],
                    [0.5, [0.22, 0.23, 0.26, 1.0]],
                    [1.0, [0.3, 0.31, 0.34, 1.0]],
                ]),
            ],
            "links": [
                "weave_x.Fac -> weave.A",
                "weave_y.Fac -> weave.B",
                "weave.Result -> relief.Height",
                "fuzz.Fac -> colour.Fac",
                "colour.Color -> bsdf.Base Color",
                "relief.Normal -> bsdf.Normal",
            ],
            "bsdf": {"Roughness": 0.92, "Sheen Weight": 0.6, "Metallic": 0.0},
        },
    },
    {
        "key": "PLASTIC",
        "label": "Plastic",
        "keywords": ["plastic", "abs", "acrylic", "toy", "rubber", "matte plastic", "vinyl"],
        "spec": {
            "name": "Plastic",
            "nodes": [
                _n("bump_noise", "noise", {"Scale": 400.0, "Detail": 2.0}),
                _n("relief", "bump", {"Strength": 0.04, "Distance": 0.001}),
                _n("rough", "maprange", {"Value": 0.0, "To Min": 0.25, "To Max": 0.4}),
            ],
            "links": [
                "bump_noise.Fac -> relief.Height",
                "relief.Normal -> bsdf.Normal",
                "bump_noise.Fac -> rough.Value",
                "rough.Result -> bsdf.Roughness",
            ],
            "bsdf": {"Base Color": [0.72, 0.12, 0.14, 1.0], "Metallic": 0.0, "Coat Weight": 0.25},
        },
    },
    {
        "key": "GLASS",
        "label": "Frosted Glass",
        "keywords": ["glass", "frosted", "translucent", "transparent", "window", "glazing", "acrylic glass"],
        "spec": {
            "name": "Frosted Glass",
            "nodes": [
                _n("frost", "noise", {"Scale": 35.0, "Detail": 6.0}),
                _n("rough", "maprange", {"Value": 0.0, "To Min": 0.02, "To Max": 0.22}),
                _n("relief", "bump", {"Strength": 0.08, "Distance": 0.001}),
            ],
            "links": [
                "frost.Fac -> rough.Value",
                "rough.Result -> bsdf.Roughness",
                "frost.Fac -> relief.Height",
                "relief.Normal -> bsdf.Normal",
            ],
            "bsdf": {
                "Base Color": [0.92, 0.95, 0.96, 1.0],
                "Metallic": 0.0,
                "IOR": 1.45,
                "Transmission Weight": 1.0,
                "Alpha": 1.0,
            },
        },
    },
    {
        "key": "SAND",
        "label": "Sand / Ground",
        "keywords": ["sand", "sandy", "desert", "dirt", "soil", "ground", "earth", "mud", "dust"],
        "spec": {
            "name": "Sand",
            "nodes": [
                _n("grains", "voronoi", {"Scale": 180.0, "Randomness": 1.0}, {"feature": "F1"}),
                _n("dunes", "noise", {"Scale": 3.0, "Detail": 6.0, "Roughness": 0.55}),
                _n("mix", "mix", {"Factor": 0.45}, {"data_type": "FLOAT", "blend_type": "MIX"}),
                _ramp("colour", [
                    [0.0, [0.32, 0.25, 0.15, 1.0]],
                    [0.5, [0.55, 0.45, 0.28, 1.0]],
                    [1.0, [0.72, 0.62, 0.42, 1.0]],
                ]),
                _n("relief", "bump", {"Strength": 0.4, "Distance": 0.006}),
            ],
            "links": [
                "dunes.Fac -> mix.A",
                "grains.Distance -> mix.B",
                "mix.Result -> colour.Fac",
                "colour.Color -> bsdf.Base Color",
                "grains.Distance -> relief.Height",
                "relief.Normal -> bsdf.Normal",
            ],
            "bsdf": {"Roughness": 0.85, "Metallic": 0.0},
        },
    },
    {
        "key": "WATER",
        "label": "Water",
        "keywords": ["water", "liquid", "pool", "ripple", "lake", "wet surface", "puddle"],
        "spec": {
            "name": "Water",
            "nodes": [
                _n("ripples", "noise", {"Scale": 12.0, "Detail": 8.0, "Roughness": 0.55, "Distortion": 0.6}),
                _n("small", "noise", {"Scale": 90.0, "Detail": 6.0}),
                _n("combine", "mix", {"Factor": 0.35}, {"data_type": "FLOAT", "blend_type": "ADD"}),
                _n("relief", "bump", {"Strength": 0.3, "Distance": 0.01}),
                _n("rough", "maprange", {"Value": 0.0, "To Min": 0.01, "To Max": 0.14}),
            ],
            "links": [
                "ripples.Fac -> combine.A",
                "small.Fac -> combine.B",
                "combine.Result -> relief.Height",
                "relief.Normal -> bsdf.Normal",
                "combine.Result -> rough.Value",
                "rough.Result -> bsdf.Roughness",
            ],
            "bsdf": {
                "Base Color": [0.05, 0.22, 0.26, 1.0],
                "Metallic": 0.0,
                "IOR": 1.33,
                "Transmission Weight": 0.9,
            },
        },
    },

    {
        "key": "LEATHER",
        "label": "Leather",
        "keywords": ["leather", "hide", "suede", "cowhide", "vinyl", "upholstery"],
        "spec": {
            "name": "Leather",
            "nodes": [
                _n("coord", "texcoord"),
                _n("voronoi", "voronoi", {"Scale": 8.0}),
                _n("bump", "bump", {"Strength": 0.6, "Distance": 0.02}),
            ],
            "links": [
                "coord.Generated -> voronoi.Vector",
                "voronoi.Distance -> bump.Height",
                "bump.Normal -> bsdf.Normal",
            ],
            "bsdf": {"Base Color": [0.22, 0.12, 0.06, 1.0], "Roughness": 0.55, "Metallic": 0.0},
        },
    },
    {
        "key": "ICE",
        "label": "Ice / Frost",
        "keywords": ["ice", "frost", "frozen", "glacier", "crystal"],
        "spec": {
            "name": "Ice",
            "nodes": [
                _n("coord", "texcoord"),
                _n("noise", "noise", {"Scale": 6.0, "Detail": 8.0, "Roughness": 0.6}),
                _ramp("cracks", [[0.0, [0.7,0.85,0.95,1.0]], [0.45, [0.9,0.95,1.0,1.0]], [0.55, [0.3,0.5,0.8,1.0]], [1.0, [0.85,0.92,0.98,1.0]]]),
                _n("bump", "bump", {"Strength": 0.5, "Distance": 0.01}),
            ],
            "links": [
                "coord.Generated -> noise.Vector",
                "noise.Fac -> cracks.Fac",
                "cracks.Color -> bsdf.Base Color",
                "noise.Fac -> bump.Height",
                "bump.Normal -> bsdf.Normal",
            ],
            "bsdf": {"Roughness": 0.05, "Metallic": 0.0, "IOR": 1.31, "Transmission Weight": 0.92, "Coat Weight": 0.3},
        },
    },
    {
        "key": "SLIME",
        "label": "Slime / Goo",
        "keywords": ["slime", "goo", "gel", "mucus", "ooze", "jelly"],
        "spec": {
            "name": "Slime",
            "nodes": [
                _n("coord", "texcoord"),
                _n("mapping", "mapping"),
                _n("musgrave", "noise", {"Scale": 4.0, "Detail": 6.0}),
                _n("voronoi", "voronoi", {"Scale": 6.0}),
                _n("add", "math", None, {"operation": "ADD"}),
                _n("boost", "math", {"Value_1": 2.0}, {"operation": "MULTIPLY"}),
                _n("bump", "bump", {"Strength": 0.4, "Distance": 0.015}),
            ],
            "links": [
                "coord.Generated -> mapping.Vector",
                "mapping.Vector -> musgrave.Vector",
                "musgrave.Fac -> add.Value",
                "voronoi.Distance -> boost.Value",
                "boost.Value -> add.Value_1",
                "musgrave.Fac -> bsdf.Roughness",
            ],
            "bsdf": {"Base Color": [0.15, 0.55, 0.2, 1.0], "Roughness": 0.15, "Metallic": 0.0, "IOR": 1.4, "Transmission Weight": 0.6, "Coat Weight": 0.4},
        },
    },
    {
        "key": "RASPBERRY",
        "label": "Raspberry / Berry",
        "keywords": ["raspberry", "berry", "strawberry", "fruit", "organic"],
        "spec": {
            "name": "Raspberry",
            "nodes": [
                _n("coord", "texcoord"),
                _n("noise", "noise", {"Scale": 12.0, "Detail": 6.0}),
                _ramp("color", [[0.0, [0.5,0.05,0.08,1.0]], [0.5, [0.7,0.08,0.1,1.0]], [1.0, [0.85,0.15,0.12,1.0]]]),
                _n("bump", "bump", {"Strength": 0.6, "Distance": 0.008}),
            ],
            "links": [
                "coord.Generated -> noise.Vector",
                "noise.Fac -> color.Fac",
                "color.Color -> bsdf.Base Color",
                "noise.Fac -> bump.Height",
                "bump.Normal -> bsdf.Normal",
            ],
            "bsdf": {"Roughness": 0.35, "Metallic": 0.0, "Subsurface Weight": 0.3, "IOR": 1.4},
        },
    },
    {
        "key": "PEARL",
        "label": "Pearl / Nacre",
        "keywords": ["pearl", "nacre", "shell", "mother of pearl", "iridescent"],
        "spec": {
            "name": "Pearl",
            "nodes": [
                _n("coord", "texcoord"),
                _n("noise", "noise", {"Scale": 3.0, "Detail": 4.0}),
                _ramp("tone", [[0.0, [0.9,0.88,0.85,1.0]], [0.5, [0.95,0.9,0.92,1.0]], [1.0, [0.88,0.9,0.95,1.0]]]),
            ],
            "links": [
                "coord.Generated -> noise.Vector",
                "noise.Fac -> tone.Fac",
                "tone.Color -> bsdf.Base Color",
            ],
            "bsdf": {"Roughness": 0.12, "Metallic": 0.0, "IOR": 1.5, "Coat Weight": 0.6, "Coat Roughness": 0.05},
        },
    },
    {
        "key": "GOLD",
        "label": "Gold",
        "keywords": ["gold", "golden", "gilded", "24k", "bullion"],
        "spec": {
            "name": "Gold",
            "nodes": [
                _n("coord", "texcoord"),
                _n("noise", "noise", {"Scale": 40.0, "Detail": 2.0}),
                _ramp("grain", [[0.0, [0.95,0.78,0.18,1.0]], [1.0, [1.0,0.88,0.35,1.0]]]),
            ],
            "links": [
                "coord.Generated -> noise.Vector",
                "noise.Fac -> grain.Fac",
                "grain.Color -> bsdf.Base Color",
            ],
            "bsdf": {"Roughness": 0.2, "Metallic": 1.0, "IOR": 0.47},
        },
    },
    {
        "key": "COPPER",
        "label": "Copper (oxidized)",
        "keywords": ["copper", "oxidized", "verdigris", "patina", "bronze"],
        "spec": {
            "name": "Copper",
            "nodes": [
                _n("coord", "texcoord"),
                _n("noise", "noise", {"Scale": 5.0, "Detail": 4.0}),
                _ramp("patina", [[0.0, [0.72,0.35,0.18,1.0]], [0.4, [0.18,0.55,0.35,1.0]], [0.6, [0.12,0.4,0.28,1.0]], [1.0, [0.6,0.3,0.15,1.0]]]),
                _n("bump", "bump", {"Strength": 0.3, "Distance": 0.01}),
            ],
            "links": [
                "coord.Generated -> noise.Vector",
                "noise.Fac -> patina.Fac",
                "patina.Color -> bsdf.Base Color",
                "noise.Fac -> bump.Height",
                "bump.Normal -> bsdf.Normal",
            ],
            "bsdf": {"Roughness": 0.35, "Metallic": 0.85, "IOR": 0.47},
        },
    },
    {
        "key": "BRASS",
        "label": "Brushed Brass",
        "keywords": ["brass", "bronze", "brushed brass", "gold metal"],
        "spec": {
            "name": "Brass",
            "nodes": [
                _n("coord", "texcoord"),
                _n("mapping", "mapping", {"Scale": [1.0, 8.0, 1.0]}),
                _n("noise", "noise", {"Scale": 40.0, "Detail": 2.0}),
                _ramp("rough", [[0.0, [0.25,0.25,0.25,1.0]], [1.0, [0.55,0.55,0.55,1.0]]]),
                _n("bump", "bump", {"Strength": 0.4, "Distance": 0.005}),
                _ramp("color", [[0.0, [0.85,0.7,0.25,1.0]], [1.0, [0.95,0.82,0.4,1.0]]]),
            ],
            "links": [
                "coord.Generated -> mapping.Vector",
                "mapping.Vector -> noise.Vector",
                "noise.Fac -> rough.Fac",
                "noise.Fac -> bsdf.Roughness",
                "noise.Fac -> bump.Height",
                "bump.Normal -> bsdf.Normal",
                "noise.Fac -> color.Fac",
                "color.Color -> bsdf.Base Color",
            ],
            "bsdf": {"Metallic": 1.0, "IOR": 0.47},
        },
    },
    {
        "key": "CERAMIC",
        "label": "Ceramic / Porcelain",
        "keywords": ["ceramic", "porcelain", "china", "pottery", "tile", "glaze"],
        "spec": {
            "name": "Ceramic",
            "nodes": [
                _n("coord", "texcoord"),
                _n("noise", "noise", {"Scale": 200.0, "Detail": 2.0}),
                _ramp("glaze", [[0.0, [0.92,0.9,0.88,1.0]], [1.0, [0.98,0.97,0.96,1.0]]]),
            ],
            "links": [
                "coord.Generated -> noise.Vector",
                "noise.Fac -> glaze.Fac",
                "glaze.Color -> bsdf.Base Color",
            ],
            "bsdf": {"Roughness": 0.08, "Metallic": 0.0, "IOR": 1.5, "Coat Weight": 0.6, "Coat Roughness": 0.02},
        },
    },
    {
        "key": "RUBBER",
        "label": "Rubber",
        "keywords": ["rubber", "latex", "silicone", "elastomer", "tire"],
        "spec": {
            "name": "Rubber",
            "nodes": [
                _n("coord", "texcoord"),
                _n("noise", "noise", {"Scale": 60.0, "Detail": 3.0}),
                _ramp("tone", [[0.0, [0.02,0.02,0.02,1.0]], [1.0, [0.06,0.06,0.06,1.0]]]),
                _n("bump", "bump", {"Strength": 0.15, "Distance": 0.003}),
            ],
            "links": [
                "coord.Generated -> noise.Vector",
                "noise.Fac -> tone.Fac",
                "tone.Color -> bsdf.Base Color",
                "noise.Fac -> bump.Height",
                "bump.Normal -> bsdf.Normal",
            ],
            "bsdf": {"Roughness": 0.85, "Metallic": 0.0},
        },
    },
    {
        "key": "FLECK_PAINT",
        "label": "Metallic Fleck Paint",
        "keywords": ["fleck", "flake", "metallic paint", "car paint", "sparkle", "pearlescent"],
        "spec": {
            "name": "Fleck Paint",
            "nodes": [
                _n("coord", "texcoord"),
                _n("noise", "noise", {"Scale": 80.0, "Detail": 2.0}),
                _ramp("flakes", [[0.0, [0.05,0.1,0.35,1.0]], [0.6, [0.05,0.1,0.35,1.0]], [0.62, [0.9,0.92,0.95,1.0]], [1.0, [0.9,0.92,0.95,1.0]]]),
                _n("bump", "bump", {"Strength": 0.2, "Distance": 0.004}),
            ],
            "links": [
                "coord.Generated -> noise.Vector",
                "noise.Fac -> flakes.Fac",
                "flakes.Color -> bsdf.Base Color",
                "noise.Fac -> bump.Height",
                "bump.Normal -> bsdf.Normal",
            ],
            "bsdf": {"Base Color": [0.05, 0.1, 0.35, 1.0], "Roughness": 0.25, "Metallic": 0.0, "Coat Weight": 0.5, "Coat Roughness": 0.05},
        },
    },
    {
        "key": "SCUFFED_METAL",
        "label": "Scuffed Plated Metal",
        "keywords": ["scuffed", "worn", "plated", "scratched metal", "weathered metal"],
        "spec": {
            "name": "Scuffed Metal",
            "nodes": [
                _n("coord", "texcoord"),
                _n("noise", "noise", {"Scale": 6.0, "Detail": 6.0}),
                _ramp("wear", [[0.0, [0.0,0.0,0.0,1.0]], [0.5, [0.5,0.5,0.5,1.0]], [1.0, [1.0,1.0,1.0,1.0]]]),
                _ramp("rough", [[0.0, [0.15,0.15,0.15,1.0]], [1.0, [0.6,0.6,0.6,1.0]]]),
                _n("bump", "bump", {"Strength": 0.5, "Distance": 0.01}),
            ],
            "links": [
                "coord.Generated -> noise.Vector",
                "noise.Fac -> wear.Fac",
                "noise.Fac -> rough.Fac",
                "noise.Fac -> bsdf.Roughness",
                "noise.Fac -> bump.Height",
                "bump.Normal -> bsdf.Normal",
            ],
            "bsdf": {"Base Color": [0.6, 0.62, 0.65, 1.0], "Metallic": 1.0},
        },
    },
]

PRESET_INDEX = {preset["key"]: preset for preset in PRESETS}


# --------------------------------------------------------------------------
# Matching
# --------------------------------------------------------------------------
def _tokens(text):
    return set(_TOKEN_RE.findall(text.lower()))


def best_match(prompt):
    """Return ``(preset, score)`` for the best keyword match, or ``(None, 0)``."""
    prompt = (prompt or "").lower()
    tokens = _tokens(prompt)

    best, best_score = None, 0
    for preset in PRESETS:
        score = 0
        for keyword in preset["keywords"]:
            if " " in keyword:
                if keyword in prompt:
                    score += 3
            elif keyword in tokens:
                score += 2
            elif len(keyword) > 3 and keyword in prompt:
                score += 1
        if score > best_score:
            best, best_score = preset, score
    return best, best_score


def preset_spec(key):
    preset = PRESET_INDEX.get(key)
    if preset is None:
        return None
    # Deep-ish copy so the builder can mutate freely.
    return copy.deepcopy(preset["spec"])


def preset_labels():
    return [(preset["key"], preset["label"], preset["key"]) for preset in PRESETS]

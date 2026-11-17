"""Whitelisted shader node types for the Material Forge generator.

The LLM is never allowed to emit a raw ``bl_idname``. It picks one of the
short ``type`` keys below, and this registry maps it to a real Blender node
plus the inputs we are willing to drive.

Keeping the registry here also means the system prompt is generated from the
same source of truth as the validator, so the model can't be told about node
types that the builder will reject.
"""

from . import compat


# --------------------------------------------------------------------------
# Registry
# --------------------------------------------------------------------------
# inputs/outputs are socket *names* as they appear on the node. The
# compatibility layer resolves renames between Blender versions.
NODE_TYPES = {
    "texcoord": {
        "bl": "ShaderNodeTexCoord",
        "inputs": [],
        "outputs": ["Generated", "Normal", "UV", "Object", "Camera", "Window"],
        "doc": "Texture coordinates. Usually the start of a chain via Output 'Object' or 'Generated'.",
    },
    "mapping": {
        "bl": "ShaderNodeMapping",
        "inputs": ["Vector", "Location", "Rotation", "Scale"],
        "outputs": ["Vector"],
        "doc": "Transform coordinates. Rotation is in radians.",
    },
    "noise": {
        "bl": "ShaderNodeTexNoise",
        "inputs": ["Vector", "Scale", "Detail", "Roughness", "Lacunarity", "Distortion"],
        "outputs": ["Fac", "Color"],
        "params": {"noise_dimensions": ["1D", "2D", "3D", "4D"]},
        "doc": "Fractal noise. The workhorse for grain, clouds, roughness breakup.",
    },
    "voronoi": {
        "bl": "ShaderNodeTexVoronoi",
        "inputs": ["Vector", "Scale", "Detail", "Roughness", "Randomness"],
        "outputs": ["Distance", "Color", "Position"],
        "params": {
            "feature": ["F1", "F2", "SMOOTH_F1", "DISTANCE_TO_EDGE", "N_SPHERE_RADIUS"],
            "distance": ["EUCLIDEAN", "MANHATTAN", "CHEBYCHEV", "MINKOWSKI"],
            "voronoi_dimensions": ["1D", "2D", "3D", "4D"],
        },
        "doc": "Cellular patterns. 'DISTANCE_TO_EDGE' gives cracks, stone seams, scales.",
    },
    "wave": {
        "bl": "ShaderNodeTexWave",
        "inputs": ["Vector", "Scale", "Distortion", "Detail", "Detail Scale", "Detail Roughness", "Phase Offset"],
        "outputs": ["Color", "Fac"],
        "params": {
            "wave_type": ["BANDS", "RINGS"],
            "bands_direction": ["X", "Y", "Z", "DIAGONAL"],
            "wave_profile": ["SIN", "SAW", "TRI"],
        },
        "doc": "Bands or rings. Good for wood grain, brushed metal, ripples.",
    },
    "magic": {
        "bl": "ShaderNodeTexMagic",
        "inputs": ["Vector", "Scale", "Distortion"],
        "outputs": ["Color", "Fac"],
        "doc": "Interference pattern. Odd but useful for organic swirls.",
    },
    "checker": {
        "bl": "ShaderNodeTexChecker",
        "inputs": ["Vector", "Color1", "Color2", "Scale"],
        "outputs": ["Color", "Fac"],
        "doc": "Checkerboard tiles.",
    },
    "brick": {
        "bl": "ShaderNodeTexBrick",
        "inputs": ["Vector", "Color1", "Color2", "Mortar", "Scale", "Mortar Size", "Mortar Smooth", "Bias", "Brick Width", "Row Height"],
        "outputs": ["Color", "Fac"],
        "doc": "Brick/brickwork pattern with mortar lines.",
    },
    "gradient": {
        "bl": "ShaderNodeTexGradient",
        "inputs": ["Vector"],
        "outputs": ["Color", "Fac"],
        "params": {"gradient_type": ["LINEAR", "QUADRATIC", "EASING", "DIAGONAL", "SPHERICAL", "QUADRATIC_SPHERE", "RADIAL"]},
        "doc": "Simple linear/radial gradient.",
    },
    "ramp": {
        "bl": "ShaderNodeValToRGB",
        "inputs": ["Fac"],
        "outputs": ["Color", "Alpha"],
        "params": {"stops": "list of [position, [r,g,b,a]] pairs"},
        "doc": "Color ramp: maps a 0..1 factor to a colour gradient. Use 'stops' to control it.",
    },
    "mix": {
        "bl": "ShaderNodeMix",
        "inputs": ["Factor", "A", "B"],
        "outputs": ["Result"],
        "params": {
            "data_type": ["FLOAT", "VECTOR", "RGBA", "ROTATION"],
            "blend_type": ["MIX", "ADD", "MULTIPLY", "SCREEN", "OVERLAY", "SOFT_LIGHT", "COLOR", "SATURATION", "VALUE"],
        },
        "doc": "Mix two values/colours/vectors. Use data_type 'RGBA' to blend colours.",
    },
    "math": {
        "bl": "ShaderNodeMath",
        "inputs": ["Value", "Value_1", "Value_2"],
        "outputs": ["Value"],
        "params": {
            "operation": ["ADD", "SUBTRACT", "MULTIPLY", "DIVIDE", "POWER", "MINIMUM", "MAXIMUM", "GREATER_THAN", "LESS_THAN", "MULTIPLY_ADD", "SINE", "COSINE", "ABSOLUTE", "SMOOTH_MIN"],
            "use_clamp": "bool",
        },
        "doc": "Scalar math. Input 0,1,2 are addressed as 'Value', 'Value_1', 'Value_2'.",
    },
    "vecmath": {
        "bl": "ShaderNodeVectorMath",
        "inputs": ["Vector", "Vector_1", "Vector_2", "Scale"],
        "outputs": ["Vector", "Value"],
        "params": {
            "operation": ["ADD", "SUBTRACT", "MULTIPLY", "DIVIDE", "LENGTH", "NORMALIZE", "SCALE", "DOT_PRODUCT"],
        },
        "doc": "Vector math.",
    },
    "maprange": {
        "bl": "ShaderNodeMapRange",
        "inputs": ["Value", "From Min", "From Max", "To Min", "To Max"],
        "outputs": ["Result"],
        "params": {
            "data_type": ["FLOAT", "VECTOR"],
            "interpolation_type": ["LINEAR", "STEPPED", "SMOOTHSTEP", "SMOOTHERSTEP"],
            "clamp": "bool",
        },
        "doc": "Remap a range. Great for shaping roughness or bump strength.",
    },
    "separate_xyz": {
        "bl": "ShaderNodeSeparateXYZ",
        "inputs": ["Vector"],
        "outputs": ["X", "Y", "Z"],
        "doc": "Split a vector into components (e.g. use Z for height masks).",
    },
    "combine_xyz": {
        "bl": "ShaderNodeCombineXYZ",
        "inputs": ["X", "Y", "Z"],
        "outputs": ["Vector"],
        "doc": "Build a vector from components.",
    },
    "hsv": {
        "bl": "ShaderNodeHueSaturation",
        "inputs": ["Hue", "Saturation", "Value", "Fac", "Color"],
        "outputs": ["Color"],
        "doc": "Hue/saturation/value adjustment.",
    },
    "bump": {
        "bl": "ShaderNodeBump",
        "inputs": ["Strength", "Distance", "Height", "Normal"],
        "outputs": ["Normal"],
        "doc": "Cheap fake relief from a height input. Link its Normal output to the BSDF Normal.",
    },
    "normalmap": {
        "bl": "ShaderNodeNormalMap",
        "inputs": ["Strength", "Color", "Normal"],
        "outputs": ["Normal"],
        "doc": "Tangent-space normal map node (needs an image, rarely needed procedurally).",
    },
}

# The Principled BSDF is created implicitly by the builder, not by the spec.
BSDF_ID = "bsdf"

# Inputs on the Principled BSDF we allow the spec to drive directly.
BSDF_INPUTS = [
    "Base Color",
    "Metallic",
    "Roughness",
    "IOR",
    "Alpha",
    "Normal",
    "Subsurface Weight",
    "Specular IOR Level",
    "Emission Color",
    "Emission Strength",
    "Coat Weight",
    "Coat Roughness",
    "Sheen Weight",
    "Transmission Weight",
]


def prompt_reference():
    """Human-readable node catalogue used in the LLM system prompt."""
    lines = []
    for key, spec in sorted(NODE_TYPES.items()):
        ins = ", ".join(spec["inputs"]) or "-"
        outs = ", ".join(spec["outputs"]) or "-"
        lines.append(f"- {key}: inputs [{ins}] outputs [{outs}]. {spec['doc']}")
        if "params" in spec:
            params = ", ".join(
                f"{k}={'string' if isinstance(v, str) else 'one of ' + '/'.join(v)}"
                for k, v in spec["params"].items()
            )
            lines.append(f"  params: {params}")
    return "\n".join(lines)


# --------------------------------------------------------------------------
# Socket resolution
# --------------------------------------------------------------------------
# Blender renames sockets between versions (notably the Principled BSDF in
# 4.0). Rather than hardcoding one version, resolve names through aliases and
# let missing sockets degrade instead of crashing the build.
ALIASES = {
    "Base Color": ["Color"],
    "Color": ["Base Color"],
    "Emission Color": ["Emission"],
    "Emission": ["Emission Color"],
    "Specular IOR Level": ["Specular"],
    "Transmission Weight": ["Transmission"],
    "Coat Weight": ["Coat"],
    "Sheen Weight": ["Sheen"],
    "Subsurface Weight": ["Subsurface"],
    "Factor": ["Fac"],
    "Fac": ["Factor"],
    "Value": ["Value", "Value_1"],
    "Vector": ["Vector"],
    "Result": ["Result", "Color"],
    "Height": ["Height"],
    "Strength": ["Strength"],
}


def find_socket(sockets, name, *, output=False):
    """Return the first enabled socket matching *name* or one of its aliases."""
    candidates = [name] + ALIASES.get(name, [])

    # Exact + enabled match first.
    for candidate in candidates:
        for sock in sockets:
            if sock.name == candidate and sock.enabled:
                return sock

    # Then any match, enabled or not.
    for candidate in candidates:
        sock = sockets.get(candidate)
        if sock is not None:
            return sock

    # Finally, tolerate the "Value"/"Value_1"/"Value_2" style suffixes Blender
    # adds to duplicated socket names.
    base = name.rstrip("_0123456789")
    for sock in sockets:
        if sock.name.rstrip("_0123456789") == base and sock.enabled:
            return sock

    return None


def bl_idname(type_key):
    spec = NODE_TYPES.get(type_key)
    if spec is None:
        raise ValueError(f"Unknown node type {type_key!r}")
    return spec["bl"]

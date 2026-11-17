"""Turn a material *spec* (plain dict) into a real Blender node tree.

The spec format is deliberately boring JSON so an LLM can produce it and a
human can hand-write it::

    {
      "name": "Mossy Stone",
      "nodes": [
        {"id": "noise", "type": "noise", "inputs": {"Scale": 9.0, "Detail": 8.0}},
        {"id": "ramp",  "type": "ramp",  "params": {"stops": [[0.0, [0.05,0.06,0.04,1]],
                                                           [0.6, [0.16,0.18,0.11,1]]]}}
      ],
      "links": [
        "noise.Fac -> ramp.Fac",
        "ramp.Color -> bsdf.Base Color"
      ],
      "bsdf": {"Roughness": 0.85, "Metallic": 0.0}
    }

``bsdf`` values may also be socket references ("ramp.Color"), which is
converted into a link. The Principled BSDF and Material Output are provided
by the builder and always addressed as ``bsdf`` and ``output``.
"""

import bpy  # noqa: F401  (kept for Blender-side type context)

from . import compat, node_lib
from .compat import BuildError

MAX_NODES = 48


# --------------------------------------------------------------------------
# Spec normalisation / validation
# --------------------------------------------------------------------------
def _unwrap(spec):
    """Accept a few common LLM wrappings without failing."""
    if not isinstance(spec, dict):
        raise BuildError("Spec must be a JSON object")
    for key in ("material", "graph", "result"):
        inner = spec.get(key)
        if isinstance(inner, dict) and "nodes" in inner:
            merged = dict(inner)
            merged.setdefault("name", spec.get("name"))
            spec = merged
            break
    if "nodes" not in spec:
        raise BuildError("Spec is missing a 'nodes' list")
    return spec


def _split_ref(ref):
    """'noise.Fac' -> ('noise', 'Fac'); also accepts 'noise:Fac'."""
    if not isinstance(ref, str) or not ref:
        raise BuildError(f"Invalid socket reference {ref!r}")
    for sep in (":", "."):
        if sep in ref:
            node_id, _, socket = ref.rpartition(sep)
            if node_id and socket:
                return node_id.strip(), socket.strip()
    raise BuildError(f"Socket reference {ref!r} must look like 'node.Socket'")


def _norm_link(link):
    if isinstance(link, str):
        if "->" not in link:
            raise BuildError(f"Link {link!r} must look like 'a.X -> b.Y'")
        src, _, dst = link.partition("->")
        from_node, from_sock = _split_ref(src.strip())
        to_node, to_sock = _split_ref(dst.strip())
        return from_node, from_sock, to_node, to_sock

    if isinstance(link, dict):
        from_node = link.get("from_node") or link.get("from")
        to_node = link.get("to_node") or link.get("to")
        from_sock = link.get("from_socket") or link.get("output") or link.get("src")
        to_sock = link.get("to_socket") or link.get("input") or link.get("dst")
        if isinstance(from_node, str) and "." in from_node and not from_sock:
            from_node, from_sock = _split_ref(from_node)
        if isinstance(to_node, str) and "." in to_node and not to_sock:
            to_node, to_sock = _split_ref(to_node)
        if not all((from_node, from_sock, to_node, to_sock)):
            raise BuildError(f"Link is missing an endpoint: {link!r}")
        return str(from_node), str(from_sock), str(to_node), str(to_sock)

    raise BuildError(f"Unsupported link format {link!r}")


def validate(spec):
    """Return ``(spec, nodes, links, bsdf_values)`` with links normalised."""
    spec = _unwrap(spec)

    raw_nodes = spec.get("nodes") or []
    if not isinstance(raw_nodes, list):
        raise BuildError("'nodes' must be a list")
    if len(raw_nodes) > MAX_NODES:
        raise BuildError(f"Too many nodes ({len(raw_nodes)} > {MAX_NODES})")

    nodes = []
    seen = set()
    for index, raw in enumerate(raw_nodes):
        if not isinstance(raw, dict):
            raise BuildError(f"Node #{index} must be an object")
        type_key = raw.get("type")
        if type_key not in node_lib.NODE_TYPES:
            raise BuildError(f"Node #{index}: unknown type {type_key!r}")
        node_id = str(raw.get("id") or f"{type_key}_{index}")
        if node_id in seen:
            raise BuildError(f"Duplicate node id {node_id!r}")
        if node_id in (node_lib.BSDF_ID, "output"):
            raise BuildError(f"Node id {node_id!r} is reserved")
        seen.add(node_id)
        nodes.append(
            {
                "id": node_id,
                "type": type_key,
                "inputs": raw.get("inputs") or {},
                "params": raw.get("params") or {},
                "location": raw.get("location"),
            }
        )

    raw_links = spec.get("links") or []
    if not isinstance(raw_links, list):
        raise BuildError("'links' must be a list")
    links = [_norm_link(link) for link in raw_links]

    bsdf_values = dict(spec.get("bsdf") or {})
    if not isinstance(spec.get("bsdf") or {}, dict):
        raise BuildError("'bsdf' must be an object")

    # Socket references inside 'bsdf' become links.
    for socket_name, value in list(bsdf_values.items()):
        if isinstance(value, str) and ("." in value or ":" in value):
            node_id, out_sock = _split_ref(value)
            links.append((node_id, out_sock, node_lib.BSDF_ID, socket_name))
            del bsdf_values[socket_name]

    return spec, nodes, links, bsdf_values


# --------------------------------------------------------------------------
# Value application
# --------------------------------------------------------------------------
def _set_socket_value(socket, value, context):
    """Assign a Python value to a socket, tolerating length mismatches."""
    if isinstance(value, bool):
        value = float(value)

    if isinstance(value, (list, tuple)):
        default = getattr(socket, "default_value", None)
        if default is None or isinstance(default, float) or isinstance(default, int):
            # Scalar socket: take the first component.
            socket.default_value = value[0] if value else 0.0
            return
        try:
            length = len(default)
        except TypeError:
            socket.default_value = value
            return
        if isinstance(value[0], (list, tuple)):
            value = value[0]
        if len(value) == length:
            socket.default_value = value
        elif len(value) < length:
            socket.default_value = tuple(value) + (1.0,) * (length - len(value))
        else:
            socket.default_value = tuple(value[:length])
        return

    try:
        socket.default_value = value
    except (TypeError, ValueError) as exc:
        raise BuildError(f"{context}: cannot set {value!r} ({exc})") from exc


def _apply_inputs(node, inputs):
    for name, value in inputs.items():
        socket = node_lib.find_socket(node.inputs, name)
        if socket is None:
            raise BuildError(
                f"{node.bl_idname}: no input socket named {name!r} "
                f"(has: {', '.join(s.name for s in node.inputs)})"
            )
        _set_socket_value(socket, value, f"{node.bl_idname}.{name}")


def _apply_stops(ramp_node, stops):
    elements = ramp_node.color_ramp.elements
    stops = [s for s in stops if isinstance(s, (list, tuple)) and len(s) >= 2]
    if not stops:
        return
    stops.sort(key=lambda s: s[0])

    while len(elements) > 1:
        elements.remove(elements[-1])
    while len(elements) < len(stops):
        elements.new(0.5)

    for element, stop in zip(elements, stops):
        position, color = stop[0], stop[1]
        element.position = max(0.0, min(1.0, float(position)))
        if isinstance(color, (list, tuple)):
            rgba = list(color) + [1.0] * (4 - len(color))
            element.color = tuple(rgba[:4])
        else:
            element.color = (float(color),) * 3 + (1.0,)


def _apply_params(node, params):
    for key, value in params.items():
        if key == "stops" and node.bl_idname == "ShaderNodeValToRGB":
            _apply_stops(node, value)
            continue

        prop = node.bl_rna.properties.get(key)
        if prop is None:
            socket = node_lib.find_socket(node.inputs, key)
            if socket is not None:
                _set_socket_value(socket, value, f"{node.bl_idname}.{key}")
                continue
            raise BuildError(f"{node.bl_idname}: no property {key!r}")
        try:
            setattr(node, key, value)
        except (TypeError, ValueError) as exc:
            raise BuildError(f"{node.bl_idname}.{key} = {value!r} failed ({exc})") from exc


def _layout_locations(nodes, bsdf):
    """Lay nodes out in columns when the spec doesn't provide positions."""
    column_x = {0: -400, 1: -800, 2: -1200, 3: -1600}
    per_column = {}
    for index, node_spec in enumerate(nodes):
        location = node_spec.get("location")
        if isinstance(location, (list, tuple)) and len(location) == 2:
            node_spec["_location"] = (float(location[0]), float(location[1]))
            continue
        column = min(index % 4, 3)
        row = per_column.get(column, 0)
        per_column[column] = row + 1
        node_spec["_location"] = (column_x[column], 300 - row * 220)


# --------------------------------------------------------------------------
# Build
# --------------------------------------------------------------------------
def build(spec, *, mat_name=None):
    """Validate *spec* and return a newly created material."""
    spec, node_specs, links, bsdf_values = validate(spec)

    name = mat_name or spec.get("name") or "Forged Material"
    mat = compat.new_material(name)
    tree = mat.node_tree
    compat.clear_nodes(tree)

    bsdf = compat.ensure_principled(tree)
    bsdf.location = (0, 0)
    output = compat.ensure_surface_output(tree)
    output.location = (300, 0)

    _layout_locations(node_specs, bsdf)

    created = {}
    for node_spec in node_specs:
        bl = node_lib.bl_idname(node_spec["type"])
        try:
            node = tree.nodes.new(bl)
        except RuntimeError as exc:
            raise BuildError(f"Cannot create node {bl}: {exc}") from exc

        node.location = node_spec["_location"]
        node.label = node_spec["id"]
        node.name = node_spec["id"]

        _apply_params(node, node_spec["params"])
        _apply_inputs(node, node_spec["inputs"])
        created[node_spec["id"]] = node

    created[node_lib.BSDF_ID] = bsdf
    created["output"] = output

    for socket_name, value in bsdf_values.items():
        socket = node_lib.find_socket(bsdf.inputs, socket_name)
        if socket is None:
            raise BuildError(f"Principled BSDF has no input {socket_name!r}")
        _set_socket_value(socket, value, f"bsdf.{socket_name}")

    problems = []
    for from_node, from_sock, to_node, to_sock in links:
        src_node = created.get(from_node)
        dst_node = created.get(to_node)
        if src_node is None:
            problems.append(f"link source node {from_node!r} does not exist")
            continue
        if dst_node is None:
            problems.append(f"link target node {to_node!r} does not exist")
            continue

        src = node_lib.find_socket(src_node.outputs, from_sock)
        dst = node_lib.find_socket(dst_node.inputs, to_sock)
        if src is None:
            problems.append(f"{from_node} has no output {from_sock!r}")
            continue
        if dst is None:
            problems.append(f"{to_node} has no input {to_sock!r}")
            continue

        try:
            tree.links.new(src, dst)
        except RuntimeError as exc:
            problems.append(f"{from_node}.{from_sock} -> {to_node}.{to_sock}: {exc}")

    if problems:
        # Keep the partial tree (it is usually still usable) but tell the user.
        raise BuildError("; ".join(problems[:4]))

    mat.use_fake_user = True
    return mat


def summarize(spec):
    """Short one-line description used for operator reports and logs."""
    try:
        spec, nodes, links, bsdf_values = validate(spec)
    except BuildError as exc:
        return f"invalid spec ({exc})"
    return f"{len(nodes)} nodes, {len(links)} links, {len(bsdf_values)} BSDF values"

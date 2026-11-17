"""Deep-dump one material from a .blend: nodes, all socket defaults, links, ramp stops.

    blender --background --factory-startup -noaudio --python tools/dump_material.py -- ^
        --file reference/B3DMatPack/Meta-Androcto-wood.blend --material "WO_Polished Walnut"
"""

import json
import sys

import bpy


def socket_repr(sock):
    out = {}
    if sock.is_linked:
        out["linked"] = f"{sock.links[0].from_node.name}.{sock.links[0].from_socket.name}"
    else:
        value = getattr(sock, "default_value", None)
        if value is not None:
            try:
                out["value"] = list(value)
            except TypeError:
                out["value"] = round(float(value), 5)
        else:
            try:
                out["type"] = sock.type
            except Exception:  # noqa: BLE001
                pass
    return out


def node_repr(node):
    info = {"type": node.bl_idname, "name": node.name, "inputs": {}, "outputs": {}}
    for name in ("operation", "data_type", "blend_type", "noise_dimensions",
                 "feature", "distance", "wave_type", "bands_direction",
                 "gradient_type", "interpolation_type", "voronoi_dimensions", "mute"):
        value = getattr(node, name, None)
        if value is not None:
            info[name] = value
    if node.bl_idname == "ShaderNodeValToRGB":
        info["stops"] = [
            [e.position, list(e.color)] for e in node.color_ramp.elements
        ]
    for section, sockets in (("inputs", node.inputs), ("outputs", node.outputs)):
        for sock in sockets:
            data = socket_repr(sock)
            if data:
                info[section][sock.name] = data
    return info


def main():
    argv = sys.argv
    argv = argv[argv.index("--") + 1 :]
    file_path = material_name = None
    i = 0
    while i < len(argv):
        if argv[i] == "--file" and i + 1 < len(argv):
            file_path, i = argv[i + 1], i + 2
        elif argv[i] == "--material" and i + 1 < len(argv):
            material_name, i = argv[i + 1], i + 2
        else:
            i += 1
    if not file_path or not material_name:
        raise SystemExit("usage: dump_material.py -- --file <blend> --material <name>")

    bpy.ops.wm.open_mainfile(filepath=file_path)
    mat = bpy.data.materials.get(material_name)
    if mat is None or mat.node_tree is None:
        print(json.dumps({"error": f"{material_name!r} not found or not node-based"}))
        return

    graph = {
        "material": material_name,
        "nodes": {node.name: node_repr(node) for node in mat.node_tree.nodes},
        "links": [
            f"{link.from_node.name}.{link.from_socket.name} -> {link.to_node.name}.{link.to_socket.name}"
            for link in mat.node_tree.links
        ],
    }
    print(json.dumps(graph, indent=1))


if __name__ == "__main__":
    main()

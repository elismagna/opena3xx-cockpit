#!/usr/bin/env python3
"""Build simple CC0-style panel part GLBs (no external deps) for the 3D viewer."""
from __future__ import annotations

import json
import math
import struct
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "pcbway-orders" / "_previews" / "assets"


def _mesh(positions: list[tuple[float, float, float]], indices: list[int], color: tuple[float, float, float, float]):
    # compute flat normals per vertex from faces
    normals = [(0.0, 0.0, 0.0)] * len(positions)
    for i in range(0, len(indices), 3):
        i0, i1, i2 = indices[i], indices[i + 1], indices[i + 2]
        a, b, c = positions[i0], positions[i1], positions[i2]
        ux, uy, uz = b[0] - a[0], b[1] - a[1], b[2] - a[2]
        vx, vy, vz = c[0] - a[0], c[1] - a[1], c[2] - a[2]
        nx, ny, nz = uy * vz - uz * vy, uz * vx - ux * vz, ux * vy - uy * vx
        ln = math.sqrt(nx * nx + ny * ny + nz * nz) or 1.0
        n = (nx / ln, ny / ln, nz / ln)
        for idx in (i0, i1, i2):
            normals[idx] = n
    return {"positions": positions, "normals": normals, "indices": indices, "color": color}


def box(cx, cy, cz, sx, sy, sz, color):
    hx, hy, hz = sx / 2, sy / 2, sz / 2
    # 6 faces, unique verts for flat shading
    faces = [
        # +Y
        [(cx - hx, cy + hy, cz - hz), (cx + hx, cy + hy, cz - hz), (cx + hx, cy + hy, cz + hz), (cx - hx, cy + hy, cz + hz)],
        # -Y
        [(cx - hx, cy - hy, cz + hz), (cx + hx, cy - hy, cz + hz), (cx + hx, cy - hy, cz - hz), (cx - hx, cy - hy, cz - hz)],
        # +Z
        [(cx - hx, cy - hy, cz + hz), (cx - hx, cy + hy, cz + hz), (cx + hx, cy + hy, cz + hz), (cx + hx, cy - hy, cz + hz)],
        # -Z
        [(cx + hx, cy - hy, cz - hz), (cx + hx, cy + hy, cz - hz), (cx - hx, cy + hy, cz - hz), (cx - hx, cy - hy, cz - hz)],
        # +X
        [(cx + hx, cy - hy, cz + hz), (cx + hx, cy + hy, cz + hz), (cx + hx, cy + hy, cz - hz), (cx + hx, cy - hy, cz - hz)],
        # -X
        [(cx - hx, cy - hy, cz - hz), (cx - hx, cy + hy, cz - hz), (cx - hx, cy + hy, cz + hz), (cx - hx, cy - hy, cz + hz)],
    ]
    positions = []
    indices = []
    for face in faces:
        base = len(positions)
        positions.extend(face)
        indices.extend([base, base + 1, base + 2, base, base + 2, base + 3])
    return _mesh(positions, indices, color)


def cylinder(cx, cy, cz, r, h, segs, color, y0=None):
    if y0 is None:
        y0 = cy - h / 2
    y1 = y0 + h
    positions = []
    indices = []
    # side
    for i in range(segs):
        a0 = 2 * math.pi * i / segs
        a1 = 2 * math.pi * (i + 1) / segs
        x0, z0 = cx + r * math.cos(a0), cz + r * math.sin(a0)
        x1, z1 = cx + r * math.cos(a1), cz + r * math.sin(a1)
        base = len(positions)
        positions.extend([(x0, y0, z0), (x1, y0, z1), (x1, y1, z1), (x0, y1, z0)])
        indices.extend([base, base + 1, base + 2, base, base + 2, base + 3])
    # caps
    for y, flip in ((y0, True), (y1, False)):
        center = len(positions)
        positions.append((cx, y, cz))
        ring = []
        for i in range(segs):
            a = 2 * math.pi * i / segs
            ring.append(len(positions))
            positions.append((cx + r * math.cos(a), y, cz + r * math.sin(a)))
        for i in range(segs):
            i1 = ring[i]
            i2 = ring[(i + 1) % segs]
            if flip:
                indices.extend([center, i2, i1])
            else:
                indices.extend([center, i1, i2])
    return _mesh(positions, indices, color)


def merge(meshes):
    positions, normals, indices = [], [], []
    colors_per_vert = []  # unused; one material per primitive later
    primitives = []
    for m in meshes:
        base = len(positions)
        positions.extend(m["positions"])
        normals.extend(m["normals"])
        idx = [i + base for i in m["indices"]]
        primitives.append({"indices": idx, "color": m["color"], "v0": base, "v1": len(positions)})
    return positions, normals, primitives


def write_glb(path: Path, meshes: list):
    positions, normals, primitives = merge(meshes)
    # Build one buffer with all arrays concatenated: INDEX u16, POS f32, NORM f32 per prim... 
    # Simpler: one big POS+NORM interleaved, separate index buffers, one material per prim.

    bin_chunks = []
    accessors = []
    buffer_views = []
    materials = []
    gl_primitives = []

    def align4(b: bytearray):
        while len(b) % 4:
            b.append(0)
        return b

    blob = bytearray()

    # positions
    pos_offset = len(blob)
    for p in positions:
        blob += struct.pack("<fff", *p)
    align4(blob)
    buffer_views.append({"buffer": 0, "byteOffset": pos_offset, "byteLength": len(positions) * 12, "target": 34962})
    # min/max
    xs = [p[0] for p in positions]
    ys = [p[1] for p in positions]
    zs = [p[2] for p in positions]
    accessors.append(
        {
            "bufferView": 0,
            "componentType": 5126,
            "count": len(positions),
            "type": "VEC3",
            "max": [max(xs), max(ys), max(zs)],
            "min": [min(xs), min(ys), min(zs)],
        }
    )

    # normals
    nrm_offset = len(blob)
    for n in normals:
        blob += struct.pack("<fff", *n)
    align4(blob)
    buffer_views.append({"buffer": 0, "byteOffset": nrm_offset, "byteLength": len(normals) * 12, "target": 34962})
    accessors.append({"bufferView": 1, "componentType": 5126, "count": len(normals), "type": "VEC3"})

    for pi, prim in enumerate(primitives):
        idx = prim["indices"]
        # use u32 for safety
        i_off = len(blob)
        for i in idx:
            blob += struct.pack("<I", i)
        align4(blob)
        bv_i = len(buffer_views)
        buffer_views.append({"buffer": 0, "byteOffset": i_off, "byteLength": len(idx) * 4, "target": 34963})
        acc_i = len(accessors)
        accessors.append({"bufferView": bv_i, "componentType": 5125, "count": len(idx), "type": "SCALAR"})
        mat_i = len(materials)
        r, g, b, a = prim["color"]
        materials.append(
            {
                "name": f"mat{pi}",
                "pbrMetallicRoughness": {
                    "baseColorFactor": [r, g, b, a],
                    "metallicFactor": 0.15,
                    "roughnessFactor": 0.45,
                },
            }
        )
        gl_primitives.append(
            {
                "attributes": {"POSITION": 0, "NORMAL": 1},
                "indices": acc_i,
                "material": mat_i,
            }
        )

    gltf = {
        "asset": {"version": "2.0", "generator": "a320-panels/build_part_glb_assets"},
        "buffers": [{"byteLength": len(blob)}],
        "bufferViews": buffer_views,
        "accessors": accessors,
        "materials": materials,
        "meshes": [{"primitives": gl_primitives}],
        "nodes": [{"mesh": 0}],
        "scenes": [{"nodes": [0]}],
        "scene": 0,
    }
    json_bytes = json.dumps(gltf, separators=(",", ":")).encode("utf-8")
    while len(json_bytes) % 4:
        json_bytes += b" "

    total = 12 + 8 + len(json_bytes) + 8 + len(blob)
    out = bytearray()
    out += struct.pack("<III", 0x46546C67, 2, total)  # glTF
    out += struct.pack("<II", len(json_bytes), 0x4E4F534A)  # JSON
    out += json_bytes
    out += struct.pack("<II", len(blob), 0x004E4942)  # BIN
    out += blob
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(out)
    print("wrote", path, f"{path.stat().st_size} bytes")


def make_korry():
    # Airbus-style illuminated pushbutton (approx 19 mm face family, scaled in viewer)
    housing = box(0, 0.0, 0, 14, 3.2, 14, (0.09, 0.09, 0.1, 1))
    bezel = box(0, 1.85, 0, 13.2, 0.7, 13.2, (0.16, 0.16, 0.17, 1))
    lens = box(0, 2.45, 0, 10.2, 0.55, 10.2, (0.72, 0.7, 0.42, 1))
    legend = box(0, 2.8, 0, 7.5, 0.12, 3.2, (0.95, 0.95, 0.9, 1))
    return [housing, bezel, lens, legend]


def make_knob():
    skirt = cylinder(0, 0, 0, 6.2, 1.4, 28, (0.11, 0.11, 0.12, 1), y0=0)
    body = cylinder(0, 0, 0, 4.0, 7.0, 28, (0.2, 0.2, 0.22, 1), y0=1.2)
    cap = cylinder(0, 0, 0, 4.6, 2.4, 28, (0.26, 0.26, 0.28, 1), y0=7.4)
    pointer = box(0, 9.2, 2.6, 1.0, 0.9, 4.0, (0.92, 0.78, 0.18, 1))
    return [skirt, body, cap, pointer]


def make_led():
    can = cylinder(0, 0, 0, 1.55, 2.0, 18, (0.18, 0.18, 0.2, 1), y0=0)
    lens = cylinder(0, 0, 0, 1.65, 1.8, 18, (0.95, 0.78, 0.15, 1), y0=1.9)
    return [can, lens]


def make_header():
    # Dupont-ish 1x6 pin strip
    shells = []
    plastic = box(0, 1.0, 0, 16, 2.0, 5, (0.08, 0.08, 0.09, 1))
    shells.append(plastic)
    for i in range(6):
        x = -6.25 + i * 2.5
        shells.append(box(x, 2.6, 0, 0.7, 2.2, 0.7, (0.75, 0.65, 0.25, 1)))
    return shells


def make_chip():
    body = box(0, 0.6, 0, 10, 1.2, 6, (0.12, 0.14, 0.12, 1))
    mark = box(-3.5, 1.25, 0, 1.5, 0.15, 1.5, (0.85, 0.85, 0.85, 1))
    return [body, mark]


def make_mcu():
    body = box(0, 1.0, 0, 28, 2.0, 18, (0.1, 0.35, 0.22, 1))
    usb = box(14.5, 1.0, 0, 3, 1.4, 8, (0.75, 0.75, 0.78, 1))
    return [body, usb]


def main():
    write_glb(OUT / "korry.glb", make_korry())
    write_glb(OUT / "knob.glb", make_knob())
    write_glb(OUT / "led.glb", make_led())
    write_glb(OUT / "header.glb", make_header())
    write_glb(OUT / "chip.glb", make_chip())
    write_glb(OUT / "mcu.glb", make_mcu())
    (OUT / "README.txt").write_text(
        "Panel part placeholders generated for A320 PCB viewer (CC0 / public domain shapes).\n"
        "Not vendor CAD — proportions approximate for cockpit-panel preview.\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()

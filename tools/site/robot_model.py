"""Pack the Balance Robot URDF and its meshes into the small web model the homepage hero poses live.

    python3 tools/site/robot_model.py [path/to/balance_robot_description]

Reads urdf/balance_robot_wheelmesh.urdf and the STL meshes it names from the sibling Balanced_robot
project (the ROS 2 description package) and writes site/assets/robot/robot.json (kinematic tree,
joint limits, mimic fits, materials, mesh table) and robot.bin (quantised, welded, crease-shaded
triangles). Needs numpy only. The output is committed, so the site builds without the sibling.

robot.bin layout, per mesh in robot.json "meshes": positions uint16 x3 (scaled into "box"), normals
int8 x3, indices uint16 or uint32. Every array starts on a 4-byte boundary.
"""
import json
import math
import struct
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "site/assets/robot"
DEFAULT_PKG = ROOT.parent / "Balanced_robot/ros2/balance_robot_description"
URDF = "urdf/balance_robot_wheelmesh.urdf"
CREASE_DEG = 38.0  # faces meeting at a sharper angle keep a hard edge
SKIP = {"battery", "duo"}  # empty placeholders in the URDF meshes of base_link; the head PCB stays


def read_stl(path):
    data = path.read_bytes()
    n = struct.unpack("<I", data[80:84])[0]
    if 84 + 50 * n != len(data):
        sys.exit(f"{path.name}: not a binary STL")
    rec = np.frombuffer(data, dtype=np.dtype([("n", "<f4", 3), ("v", "<f4", (3, 3)), ("a", "<u2")]), count=n, offset=84)
    return rec["v"].astype(np.float64).reshape(-1, 3)


def pack_mesh(tri_xyz):
    """Weld, shade with a crease angle, and quantise. Returns (pos u16, nrm i8, idx, lo, hi)."""
    # Weld on a 1 micron grid.
    grid = np.round(tri_xyz * 1e6).astype(np.int64)
    uniq, inv = np.unique(grid, axis=0, return_inverse=True)
    faces = inv.reshape(-1, 3)
    pts = uniq / 1e6
    keep = (faces[:, 0] != faces[:, 1]) & (faces[:, 1] != faces[:, 2]) & (faces[:, 0] != faces[:, 2])
    faces = faces[keep]
    a, b, c = pts[faces[:, 0]], pts[faces[:, 1]], pts[faces[:, 2]]
    cross = np.cross(b - a, c - a)
    area = np.linalg.norm(cross, axis=1)
    good = area > 1e-14
    faces, cross, area = faces[good], cross[good], area[good]
    unit = cross / area[:, None]

    # Per corner: sum the area-weighted normals of the faces at that vertex inside the crease angle.
    cos_crease = math.cos(math.radians(CREASE_DEG))
    corner_v = faces.ravel()
    corner_f = np.repeat(np.arange(len(faces)), 3)
    order = np.argsort(corner_v, kind="stable")
    sv, sf = corner_v[order], corner_f[order]
    starts = np.flatnonzero(np.r_[True, sv[1:] != sv[:-1]])
    ends = np.r_[starts[1:], len(sv)]
    corner_n = np.empty((len(corner_v), 3))
    corner_idx = np.empty(len(corner_v), dtype=np.int64)
    for s, e in zip(starts, ends):
        fs = sf[s:e]
        u, w = unit[fs], cross[fs]  # cross has area weighting built in
        close = (u @ u.T) >= cos_crease
        smooth = close.astype(np.float64) @ w
        smooth /= np.maximum(np.linalg.norm(smooth, axis=1, keepdims=True), 1e-30)
        for k, f in enumerate(fs):
            slot = 3 * f + int(np.flatnonzero(faces[f] == sv[s])[0])
            corner_n[slot] = smooth[k]
            corner_idx[slot] = sv[s]
    nq = np.round(corner_n * 127).astype(np.int8)
    key = np.concatenate([corner_idx[:, None].astype(np.int64), nq.astype(np.int64)], axis=1)
    ukey, uinv = np.unique(key, axis=0, return_inverse=True)
    verts = pts[ukey[:, 0]]
    normals = ukey[:, 1:].astype(np.int8)
    idx = uinv.reshape(-1).astype(np.uint32)

    lo, hi = verts.min(axis=0), verts.max(axis=0)
    span = np.maximum(hi - lo, 1e-9)
    pos = np.round((verts - lo) / span * 65535).astype(np.uint16)
    return pos, normals, idx, lo, hi


def vec(text, default="0 0 0"):
    return [float(v) for v in (text or default).split()]


def main():
    pkg = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_PKG
    root = ET.parse(pkg / URDF).getroot()

    materials = {m.get("name"): vec(m.find("color").get("rgba"), "1 1 1 1")[:3] for m in root.findall("material")}
    links, meshes, blob = {}, [], bytearray()

    def put(arr):
        while len(blob) % 4:
            blob.append(0)
        offset = len(blob)
        blob.extend(arr.tobytes())
        return offset

    for link in root.findall("link"):
        parts = []
        for vis in link.findall("visual"):
            geo = vis.find("geometry/mesh")
            if geo is None:
                continue  # primitive cylinders are replaced by the wheel meshes in this URDF
            origin = vis.find("origin")
            if origin is not None and (any(vec(origin.get("xyz"))) or any(vec(origin.get("rpy")))):
                sys.exit(f"{link.get('name')}: visual origin not identity, pose it in the packer")
            mat = vis.find("material").get("name")
            if mat in SKIP and link.get("name") == "base_link":
                continue
            path = pkg / geo.get("filename").replace("package://balance_robot_description/", "")
            tris = read_stl(path)
            if len(tris) < 12 * 3:
                continue
            pos, nrm, idx, lo, hi = pack_mesh(tris)
            idx_type = np.uint16 if len(pos) < 65536 else np.uint32
            entry = {
                "link": link.get("name"), "material": mat,
                "vertices": int(len(pos)), "triangles": int(len(idx) // 3),
                "box": [lo.round(7).tolist(), hi.round(7).tolist()],
                "pos": put(pos), "nrm": put(nrm), "idx": put(idx.astype(idx_type)),
                "idx_bytes": int(np.dtype(idx_type).itemsize),
            }
            meshes.append(entry)
            parts.append(len(meshes) - 1)
        links[link.get("name")] = parts

    joints = []
    for j in root.findall("joint"):
        origin = j.find("origin")
        axis = j.find("axis")
        limit = j.find("limit")
        mimic = j.find("mimic")
        joints.append({
            "name": j.get("name"), "type": j.get("type"),
            "parent": j.find("parent").get("link"), "child": j.find("child").get("link"),
            "xyz": vec(origin.get("xyz")) if origin is not None else [0, 0, 0],
            "rpy": vec(origin.get("rpy")) if origin is not None else [0, 0, 0],
            "axis": vec(axis.get("xyz")) if axis is not None else [0, 0, 1],
            "lower": float(limit.get("lower")) if limit is not None and limit.get("lower") else None,
            "upper": float(limit.get("upper")) if limit is not None and limit.get("upper") else None,
            "mimic": None if mimic is None else {
                "joint": mimic.get("joint"), "multiplier": float(mimic.get("multiplier")),
                "offset": float(mimic.get("offset"))},
        })

    wheel_radius = 0.0424191
    model = {
        "source": "balance_robot_description/" + URDF, "wheel_radius": wheel_radius,
        "materials": materials, "links": links, "meshes": meshes, "joints": joints,
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "robot.json").write_text(json.dumps(model, separators=(",", ":")), encoding="utf-8")
    (OUT / "robot.bin").write_bytes(bytes(blob))
    tri = sum(m["triangles"] for m in meshes)
    print(f"{len(meshes)} meshes, {tri} triangles, robot.bin {len(blob) / 1e6:.2f} MB -> {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()

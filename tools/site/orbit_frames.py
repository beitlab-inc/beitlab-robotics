#!/usr/bin/env python3
"""Caption-free camera orbit of Balance Robot v1, for the homepage scroll.

The homepage draws one frame per scroll position. Frames come from the same
offscreen VTK scene as ``make renders`` (design/body_v1/render_v1.py). Run this
with that draw environment, from the landing repository:

    uv run --no-project --with vtk==9.4.2 --with pillow --with numpy python tools/site/orbit_frames.py

Writes site/assets/orbit/fXX.png, the robot lifted off the plate so the page
background shows through. Needs design/body_v1/out/ref/render_scene.* from
``make renders`` (the mesh step) in the sibling Balanced_robot repo.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ROBOT = Path(os.environ.get("ROBOT_ROOT", ROOT.parent / "Balanced_robot")).resolve()
OUT = ROOT / "site" / "assets" / "orbit"
N = 60
# Square-ish plate so the robot can sit large in the viewport. Camera matches
# render_v1's orbit (hip 35°, one turn from the front 3/4) but closer, and
# without the caption pill.
W, H = 1200, 900


def lift_off_plate(im):
    """Drop the flat plate and the baked contact shadow. The page draws its own shadow.

    The plate is render_v1.BACKDROP. Edge pixels are a mix of robot and plate, so
    the matte is estimated from that mix and the colour is unmixed. Otherwise a
    light fringe stays around the robot on the dark page.
    """
    import numpy as np
    from PIL import Image

    rgb = np.asarray(im.convert("RGB")).astype(np.float32)
    h, w = rgb.shape[:2]
    plate = np.array([243.0, 244.0, 246.0], np.float32)
    dist = np.sqrt(((rgb - plate) ** 2).sum(-1))
    chroma = rgb.max(-1) - rgb.min(-1)
    lum = rgb.mean(-1)
    # The contact shadow is a gray oval under the wheels, darker than the plate
    # and not connected to the body by colour, so a y-band is enough.
    shadow = (np.arange(h)[:, None] >= int(0.842 * h)) & (chroma < 18) & (lum > 150) & (lum < 244)
    alpha = np.clip((dist - 12.0) / 36.0, 0.0, 1.0)
    alpha[shadow] = 0.0
    # Recover the robot colour: pixel = robot * a + plate * (1 - a).
    out = np.empty_like(rgb)
    solid = alpha >= 0.995
    out[solid] = rgb[solid]
    edge = (alpha > 0.04) & ~solid
    out[edge] = plate + (rgb[edge] - plate) / alpha[edge, None]
    np.clip(out, 0, 255, out)
    out[alpha <= 0.04] = 0
    alpha[alpha <= 0.04] = 0
    rgba = np.dstack([out, alpha * 255]).round().astype(np.uint8)
    return Image.fromarray(rgba, "RGBA")


def main() -> None:
    sys.path.insert(0, str(ROBOT / "design" / "body_v1"))
    import json

    import numpy as np
    import render_v1 as rv

    # No floor on the homepage: the robot sits on the plate (BACKDROP) with a contact shadow.
    rv.Scene._ground = lambda self, *a, **k: None

    scene_path = rv.SCENE
    meta = json.loads(Path(str(scene_path) + ".json").read_text())
    arrays = dict(np.load(str(scene_path) + ".npz"))
    rv.WHEEL_R = meta.get("WHEEL_R", rv.WHEEL_R)
    key = "B"
    opt = rv.lk.OPTIONS[key]
    zh = meta["ZH"]
    inst = rv.instances(meta, arrays, key)
    orbit = rv.Scene(W, H)
    for item in inst:
        orbit.add(item)
    orbit.show(rv.group_mats(opt, rv.REF_DEG, zh))
    OUT.mkdir(parents=True, exist_ok=True)
    only = sys.argv[1:] 
    for i in range(N):
        name = f"f{i:02d}.png"
        if only and name not in only and str(i) not in only:
            continue
        az = rv.FRONT["az"] + 360.0 * i / N
        # Same rig as render_v1's turntable, pulled in just enough that the
        # whole robot stays in frame on a 4:3 plate.
        orbit.camera((0.0, 10.0, 120.0), az, 18.0, dist=920.0, angle=22.0)
        frame = lift_off_plate(orbit.snap())
        frame.save(OUT / name, optimize=True)
        print(name, flush=True)


if __name__ == "__main__":
    main()

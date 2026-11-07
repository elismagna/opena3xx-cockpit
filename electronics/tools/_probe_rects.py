from __future__ import annotations

import math
import re
from pathlib import Path
from xml.etree import ElementTree as ET

# Huge files: use iterparse carefully or regex with transforms is hard.
# Use ET - 7MB is fine.


def local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def parse_transform(t: str | None) -> tuple[float, float, float, float, float, float]:
    """Return affine 2x3: a,b,c,d,e,f for [a c e; b d f]."""
    a, b, c, d, e, f = 1.0, 0.0, 0.0, 1.0, 0.0, 0.0
    if not t:
        return a, b, c, d, e, f
    for kind, args in re.findall(r"(matrix|translate|scale|rotate)\(([^)]*)\)", t):
        nums = [float(x) for x in re.split(r"[,\s]+", args.strip()) if x]
        if kind == "translate":
            tx, ty = nums[0], nums[1] if len(nums) > 1 else 0.0
            e, f = a * tx + c * ty + e, b * tx + d * ty + f
        elif kind == "scale":
            sx, sy = nums[0], nums[1] if len(nums) > 1 else nums[0]
            a, b, c, d = a * sx, b * sx, c * sy, d * sy
        elif kind == "matrix" and len(nums) >= 6:
            na, nb, nc, nd, ne, nf = nums[:6]
            a, b, c, d, e, f = (
                a * na + c * nb,
                b * na + d * nb,
                a * nc + c * nd,
                b * nc + d * nd,
                a * ne + c * nf + e,
                b * ne + d * nf + f,
            )
        elif kind == "rotate":
            ang = math.radians(nums[0])
            cos, sin = math.cos(ang), math.sin(ang)
            if len(nums) >= 3:
                cx, cy = nums[1], nums[2]
                # translate(cx,cy) rotate translate(-cx,-cy)
                e, f = a * cx + c * cy + e, b * cx + d * cy + f
                a, b, c, d = a * cos + c * sin, b * cos + d * sin, -a * sin + c * cos, -b * sin + d * cos
                e, f = a * (-cx) + c * (-cy) + e, b * (-cx) + d * (-cy) + f
            else:
                a, b, c, d = a * cos + c * sin, b * cos + d * sin, -a * sin + c * cos, -b * sin + d * cos
    return a, b, c, d, e, f


def mul(A, B):
    a, b, c, d, e, f = A
    a2, b2, c2, d2, e2, f2 = B
    return (
        a * a2 + c * b2,
        b * a2 + d * b2,
        a * c2 + c * d2,
        b * c2 + d * d2,
        a * e2 + c * f2 + e,
        b * e2 + d * f2 + f,
    )


def apply(M, x, y):
    a, b, c, d, e, f = M
    return a * x + c * y + e, b * x + d * y + f


def is_red(style: str, stroke_attr: str | None) -> bool:
    s = ((style or "") + " " + (stroke_attr or "")).lower()
    return "#ff0000" in s or "stroke:red" in s


def collect(path: Path) -> None:
    tree = ET.parse(path)
    root = tree.getroot()
    w = root.get("width")
    h = root.get("height")
    vb = root.get("viewBox")
    print(path.name, "w", w, "h", h, "vb", vb)

    rects = []
    ellipses = []
    circles = []

    def walk(el, M):
        M2 = mul(M, parse_transform(el.get("transform")))
        tag = local(el.tag)
        style = el.get("style") or ""
        if tag == "rect" and is_red(style, el.get("stroke")):
            x, y = float(el.get("x", 0)), float(el.get("y", 0))
            rw, rh = float(el.get("width", 0)), float(el.get("height", 0))
            cx, cy = apply(M2, x + rw / 2, y + rh / 2)
            # scale approx from matrix
            a, b, c, d, e, f = M2
            sx = math.hypot(a, b) or 1
            sy = math.hypot(c, d) or 1
            rects.append((cx, cy, rw * sx, rh * sy))
        elif tag == "ellipse" and is_red(style, el.get("stroke")):
            cx, cy = apply(M2, float(el.get("cx", 0)), float(el.get("cy", 0)))
            a, b, c, d, e, f = M2
            sx = math.hypot(a, b) or 1
            rx = float(el.get("rx", 0)) * sx
            ellipses.append((cx, cy, rx))
        elif tag == "circle" and is_red(style, el.get("stroke")):
            cx, cy = apply(M2, float(el.get("cx", 0)), float(el.get("cy", 0)))
            a, b, c, d, e, f = M2
            sx = math.hypot(a, b) or 1
            r = float(el.get("r", 0)) * sx
            circles.append((cx, cy, r))
        for ch in list(el):
            walk(ch, M2)

    walk(root, (1, 0, 0, 1, 0, 0))
    print(f"  red rects={len(rects)} ellipses={len(ellipses)} circles={len(circles)}")
    if rects:
        xs = [r[0] for r in rects]
        ys = [r[1] for r in rects]
        print(f"  rect bbox {min(xs):.1f},{min(ys):.1f} .. {max(xs):.1f},{max(ys):.1f}")
        sizes = sorted({(round(r[2], 1), round(r[3], 1)) for r in rects})
        print("  rect sizes", sizes[:15])
        # cluster by size - button-like square ~10-20mm
        btns = [r for r in rects if 8 <= min(r[2], r[3]) <= 25 and abs(r[2] - r[3]) < 8]
        print(f"  button-like rects {len(btns)}")
        for r in btns[:12]:
            print(f"    {r[0]:.1f},{r[1]:.1f} {r[2]:.1f}x{r[3]:.1f}")
    if ellipses:
        print("  ellipses sample", [(round(x, 1), round(y, 1), round(r, 1)) for x, y, r in ellipses[:10]])
    if circles:
        print("  circles sample", [(round(x, 1), round(y, 1), round(r, 1)) for x, y, r in circles[:10]])


base = Path(
    r"C:\Users\Elis\Downloads\Fenix v3 Installer\A320-panels\electronics\vendor\mobiflight-panels\aircraft\airbus-a32x"
)
for rel in [
    r"overhead\elec\a320-overhead-elec.svg",
    r"overhead\hyd-fuel\a320-overhead-hydfuel.svg",
    r"overhead\fire\a320-overhead-fire.svg",
    r"overhead\adirs\a320-overhead-adirs.svg",
]:
    collect(base / rel)

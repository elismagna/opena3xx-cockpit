#!/usr/bin/env python3
"""Build Rev0 panel PCBs from MobiFlight laser-face SVGs (mm).

Cutouts:
  - red (#ff0000) square-ish rects → illuminated pushbutton footprints
  - red circles/ellipses r≈1.2–3 → NPTH mounts; larger → knobs/buttons
  - flood-light special: board from base-plate rect; black cut circles/ellipses

Output under pcbway-orders/<id>-<slug>/. Preview before PCBWay.
"""
from __future__ import annotations

import math
import re
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
VENDOR = ROOT / "vendor" / "mobiflight-panels" / "aircraft" / "airbus-a32x"
ORDERS = ROOT / "pcbway-orders"

Affine = tuple[float, float, float, float, float, float]


def local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def parse_transform(t: str | None) -> Affine:
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
                e, f = a * cx + c * cy + e, b * cx + d * cy + f
                a, b, c, d = (
                    a * cos + c * sin,
                    b * cos + d * sin,
                    -a * sin + c * cos,
                    -b * sin + d * cos,
                )
                e, f = a * (-cx) + c * (-cy) + e, b * (-cx) + d * (-cy) + f
            else:
                a, b, c, d = (
                    a * cos + c * sin,
                    b * cos + d * sin,
                    -a * sin + c * cos,
                    -b * sin + d * cos,
                )
    return a, b, c, d, e, f


def mul(A: Affine, B: Affine) -> Affine:
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


def apply(M: Affine, x: float, y: float) -> tuple[float, float]:
    a, b, c, d, e, f = M
    return a * x + c * y + e, b * x + d * y + f


def scale_xy(M: Affine) -> tuple[float, float]:
    a, b, c, d, e, f = M
    return math.hypot(a, b) or 1.0, math.hypot(c, d) or 1.0


def is_red(style: str, stroke_attr: str | None) -> bool:
    s = ((style or "") + " " + (stroke_attr or "")).lower()
    return "#ff0000" in s or "stroke:red" in s


def board_size_mm(root: ET.Element) -> tuple[float, float]:
    def mm(val: str | None, fallback: float) -> float:
        if not val:
            return fallback
        m = re.match(r"([-\d.]+)\s*mm", val)
        if m:
            return float(m.group(1))
        try:
            return float(val)
        except ValueError:
            return fallback

    w, h = mm(root.get("width"), 0.0), mm(root.get("height"), 0.0)
    if w > 0 and h > 0:
        return w, h
    vb = root.get("viewBox")
    if vb:
        parts = [float(x) for x in vb.replace(",", " ").split()]
        if len(parts) == 4:
            return parts[2], parts[3]
    raise SystemExit("cannot determine board size")


@dataclass
class Cutouts:
    mounts: list[tuple[float, float, float]] = field(default_factory=list)  # x,y,r
    buttons: list[tuple[float, float, float]] = field(default_factory=list)  # x,y,size
    knobs: list[tuple[float, float, float]] = field(default_factory=list)  # x,y,r
    board_rect: tuple[float, float, float, float] | None = None  # x,y,w,h override


def dedupe_points(
    pts: list[tuple[float, float, float]], tol: float = 2.0, keep_larger: bool = True
) -> list[tuple[float, float, float]]:
    out: list[tuple[float, float, float]] = []
    for x, y, s in sorted(pts, key=lambda p: -p[2]):
        hit = None
        for i, (ux, uy, us) in enumerate(out):
            if abs(x - ux) < tol and abs(y - uy) < tol:
                hit = i
                break
        if hit is None:
            out.append((x, y, s))
        elif keep_larger and s > out[hit][2]:
            out[hit] = (x, y, s)
    return out


def extract_cutouts(root: ET.Element, *, accept_black_cuts: bool = False) -> Cutouts:
    cut = Cutouts()

    def stroke_ok(style: str, stroke_attr: str | None) -> bool:
        if is_red(style, stroke_attr):
            return True
        if not accept_black_cuts:
            return False
        s = ((style or "") + " " + (stroke_attr or "")).lower()
        return "#000000" in s or "stroke:black" in s or 'stroke="#000"' in s

    def walk(el: ET.Element, M: Affine) -> None:
        M2 = mul(M, parse_transform(el.get("transform")))
        tag = local(el.tag)
        style = el.get("style") or ""
        label = (el.get("{http://www.inkscape.org/namespaces/inkscape}label") or "").lower()

        if tag == "rect" and stroke_ok(style, el.get("stroke")):
            x, y = float(el.get("x", 0)), float(el.get("y", 0))
            rw, rh = float(el.get("width", 0)), float(el.get("height", 0))
            sx, sy = scale_xy(M2)
            w, h = rw * sx, rh * sy
            cx, cy = apply(M2, x + rw / 2, y + rh / 2)
            if is_red(style, el.get("stroke")) and 8 <= min(w, h) <= 28 and abs(w - h) < 10:
                cut.buttons.append((cx, cy, max(w, h)))
            elif accept_black_cuts and w > 80 and h > 30 and not is_red(style, el.get("stroke")):
                # candidate plate outline in page coords
                px, py = apply(M2, x, y)
                cut.board_rect = (px, py, w, h)

        elif tag in ("circle", "ellipse") and stroke_ok(style, el.get("stroke")):
            cx0 = float(el.get("cx", 0))
            cy0 = float(el.get("cy", 0))
            sx, sy = scale_xy(M2)
            if tag == "circle":
                r = float(el.get("r", 0)) * sx
            else:
                r = max(float(el.get("rx", 0)) * sx, float(el.get("ry", 0)) * sy)
            cx, cy = apply(M2, cx0, cy0)
            if 1.1 <= r <= 3.2:
                cut.mounts.append((cx, cy, r))
            elif 4.0 <= r <= 9.0:
                cut.knobs.append((cx, cy, r))
                cut.buttons.append((cx, cy, r * 2))
            elif r > 9.0:
                cut.knobs.append((cx, cy, r))

        for ch in list(el):
            walk(ch, M2)

    # Prefer inkscape label on layer for flood plate
    def walk_labeled(el: ET.Element, M: Affine) -> None:
        M2 = mul(M, parse_transform(el.get("transform")))
        label = (el.get("{http://www.inkscape.org/namespaces/inkscape}label") or "").lower()
        if accept_black_cuts and label == "base plate cut":
            for ch in list(el):
                if local(ch.tag) == "rect":
                    x, y = float(ch.get("x", 0)), float(ch.get("y", 0))
                    rw, rh = float(ch.get("width", 0)), float(ch.get("height", 0))
                    sx, sy = scale_xy(M2)
                    px, py = apply(M2, x, y)
                    cut.board_rect = (px, py, rw * sx, rh * sy)
        for ch in list(el):
            walk_labeled(ch, M2)

    if accept_black_cuts:
        walk_labeled(root, (1, 0, 0, 1, 0, 0))
    walk(root, (1, 0, 0, 1, 0, 0))

    cut.buttons = dedupe_points(cut.buttons, tol=3.0)
    cut.mounts = dedupe_points(cut.mounts, tol=1.5)
    cut.knobs = dedupe_points(cut.knobs, tol=2.0)
    return cut


@dataclass
class GerberLayer:
    name: str
    lines: list[str] = field(default_factory=list)
    apertures: dict[float, int] = field(default_factory=dict)
    next_d: int = 10

    def header(self) -> None:
        self.lines = [f"G04 {self.name}*", "%FSLAX35Y35*%", "%MOMM*%", "%LPD*%"]

    def aper_circle(self, diam_mm: float) -> int:
        key = round(diam_mm, 5)
        if key not in self.apertures:
            self.apertures[key] = self.next_d
            self.next_d += 1
        return self.apertures[key]

    def emit_apertures(self) -> None:
        block = [
            f"%ADD{d}C,{diam:.5f}*%"
            for diam, d in sorted(self.apertures.items(), key=lambda x: x[1])
        ]
        self.lines[4:4] = block

    def finish(self) -> str:
        self.emit_apertures()
        self.lines.append("M02*")
        return "\n".join(self.lines) + "\n"


def excellon(holes: list[tuple[float, float, float]], name: str) -> str:
    tools: dict[float, int] = {}
    next_t = 1
    body: list[tuple[int, float, float]] = []
    for x, y, d in holes:
        key = round(d, 4)
        if key not in tools:
            tools[key] = next_t
            next_t += 1
        body.append((tools[key], x, y))
    lines = [f";{name}", "M48", "METRIC,TZ"]
    for diam, t in sorted(tools.items(), key=lambda x: x[1]):
        lines.append(f"T{t}C{diam:.4f}")
    lines += ["%", "G90", "G05"]
    cur = None
    for t, x, y in body:
        if t != cur:
            lines.append(f"T{t}")
            cur = t
        lines.append(f"X{x:.4f}Y{y:.4f}")
    lines.append("M30")
    return "\n".join(lines) + "\n"


@dataclass
class Board:
    width: float
    height: float
    layers: dict[str, GerberLayer] = field(default_factory=dict)
    plated: list[tuple[float, float, float]] = field(default_factory=list)
    nplated: list[tuple[float, float, float]] = field(default_factory=list)

    def __post_init__(self) -> None:
        for n in ("GTL", "GBL", "GTO", "GTS", "GBS", "GKO"):
            L = GerberLayer(n)
            L.header()
            self.layers[n] = L

    def xy(self, x: float, y: float) -> str:
        gy = self.height - y
        return f"X{int(round(x * 100000)):d}Y{int(round(gy * 100000)):d}"

    def flash(self, layer: str, x: float, y: float, diam: float) -> None:
        L = self.layers[layer]
        d = L.aper_circle(diam)
        L.lines.append(f"D{d}*")
        L.lines.append(f"{self.xy(x, y)}D03*")

    def track(self, layer: str, points: list[tuple[float, float]], width: float = 0.3) -> None:
        if len(points) < 2:
            return
        L = self.layers[layer]
        d = L.aper_circle(width)
        L.lines.append(f"D{d}*")
        L.lines.append(f"{self.xy(*points[0])}D02*")
        for p in points[1:]:
            L.lines.append(f"{self.xy(*p)}D01*")

    def outline(self) -> None:
        pts = [(0, 0), (self.width, 0), (self.width, self.height), (0, self.height), (0, 0)]
        self.track("GKO", pts, 0.15)

    def thru_pad(self, x: float, y: float, pad: float = 1.7, hole: float = 0.9) -> None:
        for lyr in ("GTL", "GBL"):
            self.flash(lyr, x, y, pad)
        for lyr in ("GTS", "GBS"):
            self.flash(lyr, x, y, pad * 1.15)
        self.plated.append((x, self.height - y, hole))

    def mount(self, x: float, y: float, hole: float = 3.2) -> None:
        self.nplated.append((x, self.height - y, hole))
        self.flash("GTS", x, y, hole + 0.6)
        self.flash("GBS", x, y, hole + 0.6)

    def illuminated_button(self, cx: float, cy: float) -> list[tuple[float, float]]:
        pins = [
            (cx - 3.5, cy - 2.5),
            (cx + 3.5, cy - 2.5),
            (cx - 3.5, cy + 2.5),
            (cx + 3.5, cy + 2.5),
            (cx - 2.0, cy + 5.0),
            (cx + 2.0, cy + 5.0),
        ]
        for x, y in pins:
            self.thru_pad(x, y)
        s = 6.0
        self.track(
            "GTO",
            [
                (cx - s, cy - s),
                (cx + s, cy - s),
                (cx + s, cy + s),
                (cx - s, cy + s),
                (cx - s, cy - s),
            ],
            0.2,
        )
        return pins

    def header(self, n: int, x0: float, y0: float, pitch: float = 2.54) -> list[tuple[float, float]]:
        pins = [(x0 + i * pitch, y0) for i in range(n)]
        for x, y in pins:
            self.thru_pad(x, y, pad=1.9, hole=1.0)
        return pins


def build_from_svg(svg_path: Path, slug: str, folder_id: str) -> Path:
    tree = ET.parse(svg_path)
    root = tree.getroot()
    flood = slug == "flood-light"
    cut = extract_cutouts(root, accept_black_cuts=flood)

    if cut.board_rect:
        ox, oy, w, h = cut.board_rect
        # shift all features into board-local coords
        def shift(pts: list[tuple[float, float, float]]) -> list[tuple[float, float, float]]:
            return [(x - ox, y - oy, s) for x, y, s in pts]

        cut.mounts = shift(cut.mounts)
        cut.buttons = shift(cut.buttons)
        cut.knobs = shift(cut.knobs)
        # keep only features inside plate (+margin)
        def inside(pts: list[tuple[float, float, float]]) -> list[tuple[float, float, float]]:
            return [p for p in pts if -2 <= p[0] <= w + 2 and -2 <= p[1] <= h + 2]

        cut.mounts = inside(cut.mounts)
        cut.buttons = inside(cut.buttons)
        cut.knobs = inside(cut.knobs)
    else:
        w, h = board_size_mm(root)

    # Filter mounts that are clearly on the board
    cut.mounts = [m for m in cut.mounts if -1 <= m[0] <= w + 1 and -1 <= m[1] <= h + 1]
    cut.buttons = [b for b in cut.buttons if 2 <= b[0] <= w - 2 and 2 <= b[1] <= h - 2]

    # Prefer corner-ish mounts (r~1.5) over mid DZUS if too many
    if len(cut.mounts) > 12:
        cut.mounts = sorted(cut.mounts, key=lambda m: m[2])[:12]

    if not cut.buttons and cut.knobs:
        cut.buttons = [(x, y, r * 2) for x, y, r in cut.knobs]

    # Tall MIP panels with 4 corner mounts and no button rects (e.g. TERR ON ND):
    # place two illuminated switches on the vertical centerline.
    if len(cut.buttons) < 2 and len(cut.mounts) >= 4 and h > w * 1.15:
        xs = [m[0] for m in cut.mounts]
        ys = [m[1] for m in cut.mounts]
        cx = (min(xs) + max(xs)) / 2
        y0, y1 = min(ys), max(ys)
        cut.buttons = [
            (cx, y0 + (y1 - y0) * 0.32, 19.0),
            (cx, y0 + (y1 - y0) * 0.68, 19.0),
        ]

    board = Board(w, h)
    board.outline()

    for x, y, r in cut.mounts:
        board.mount(x, y, hole=max(2.8, r * 2 + 0.3))

    pin_targets: list[tuple[float, float]] = []
    for x, y, _s in cut.buttons:
        pins = board.illuminated_button(x, y)
        pin_targets.append(pins[0])
        pin_targets.append(pins[4])

    n_hdr = max(8, min(40, len(pin_targets) + 2))
    # if many buttons, use dual-row style by capping and noting
    if len(pin_targets) + 2 > 40:
        pin_targets = pin_targets[:38]
        n_hdr = 40
    hdr_w = (n_hdr - 1) * 2.54
    hx0 = max(2.0, (w - hdr_w) / 2)
    hy = min(h - 3.5, h - 2.5)
    if hy < 5:
        hy = h * 0.92
    hdr = board.header(n_hdr, hx0, hy)

    for i, (px, py) in enumerate(pin_targets):
        if i + 2 >= len(hdr):
            break
        hx, hyy = hdr[i + 2]
        mid_y = (py + hyy) / 2
        board.track("GTL", [(px, py), (px, mid_y), (hx, mid_y), (hx, hyy)], 0.3)

    board.track("GBL", [(1, 1), (w - 1, 1), (w - 1, h - 6), (1, h - 6), (1, 1)], 0.25)

    out_dir = ORDERS / f"{folder_id}-{slug}"
    out_dir.mkdir(parents=True, exist_ok=True)
    gbo = GerberLayer("GBO")
    gbo.header()
    files = {
        "Gerber_TopLayer.GTL": board.layers["GTL"].finish(),
        "Gerber_BottomLayer.GBL": board.layers["GBL"].finish(),
        "Gerber_TopSilkscreenLayer.GTO": board.layers["GTO"].finish(),
        "Gerber_BottomSilkscreenLayer.GBO": gbo.finish(),
        "Gerber_TopSolderMaskLayer.GTS": board.layers["GTS"].finish(),
        "Gerber_BottomSolderMaskLayer.GBS": board.layers["GBS"].finish(),
        "Gerber_BoardOutlineLayer.GKO": board.layers["GKO"].finish(),
        "Drill_PTH_Through.DRL": excellon(board.plated, "PTH"),
        "Drill_NPTH_Through.DRL": excellon(board.nplated, "NPTH"),
        "How-to-order-PCB.txt": (
            "PCBWay: upload this zip. 2-layer, 1.6 mm, HASL/ENIG, qty 5.\n"
            "Preview ../_previews/<id>-top.svg before ordering.\n"
        ).encode("utf-8"),
    }
    zip_path = out_dir / "Gerber.zip"
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for name, body in files.items():
            zf.writestr(name, body)

    (out_dir / "fab-notes.txt").write_text(
        f"""PCBWay fab notes — {folder_id}-{slug} (Rev0 from face SVG)
Source: {svg_path.relative_to(ROOT)}
Size: {w:.2f} × {h:.2f} mm
Mount holes: {len(cut.mounts)}
Button footprints: {len(cut.buttons)}
Knob/extra: {len(cut.knobs)}
Header pins: {n_hdr}

2-layer, 1.6 mm, HASL, black or green mask, white silk, qty 5.
VERIFY in Gerber viewer / _previews before order.
""",
        encoding="utf-8",
    )
    print(
        f"{folder_id}-{slug}: {w:.1f}×{h:.1f} mm  mounts={len(cut.mounts)} "
        f"buttons={len(cut.buttons)} knobs={len(cut.knobs)} → {zip_path.name}"
    )
    return out_dir


JOBS = [
    ("16", "terr-on-nd", r"main-instrument-panel\terr-on-nd\A320-terr-on-nd.svg"),
    ("17", "flood-light", r"pedestal\flood-light\Flood light panel.svg"),
    ("18", "flt-ctl-fo", r"overhead\flt-ctl-fo\a320-overhead-flt-ctl-fo.svg"),
    ("19", "gndservices", r"overhead\gndservices\a320-overhead-groundservices.svg"),
    ("20", "fire", r"overhead\fire\a320-overhead-fire.svg"),
    ("21", "adirs", r"overhead\adirs\a320-overhead-adirs.svg"),
    ("22", "evac", r"overhead\evac\a320-overhead-evac.svg"),
    ("23", "audio", r"overhead\audio\a320-overhead-audio.svg"),
    ("24", "radio", r"overhead\radio\a320-overhead-radio.svg"),
    ("25", "cargo-heat", r"overhead\cargo-heat\a320-overhead-cargo-heat.svg"),
    ("26", "emer-elec", r"overhead\Emer Elec\a320-overhead-emer-elec.svg"),
    ("27", "aircond", r"overhead\aircond\a320-overhead-aircond.svg"),
    ("28", "flt-ctl", r"overhead\flt-ctl\a320-overhead-flt-ctl.svg"),
    ("29", "elec", r"overhead\elec\a320-overhead-elec.svg"),
    ("30", "hyd-fuel", r"overhead\hyd-fuel\a320-overhead-hydfuel.svg"),
]


def main() -> None:
    for fid, slug, rel in JOBS:
        svg = VENDOR / rel
        if not svg.exists():
            print("missing", svg)
            continue
        build_from_svg(svg, slug, fid)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Convert EasyEDA Standard PCB JSON → Gerber RS-274X + Excellon ZIP for PCBWay.

Coordinates: 1 EasyEDA unit = 10 mil = 0.254 mm.
"""
from __future__ import annotations

import json
import math
import re
import zipfile
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

UNIT_MM = 0.254  # 10 mil

# EasyEDA layer id → fabrication role
LAYER_MAP = {
    "1": "GTL",  # Top copper
    "2": "GBL",  # Bottom copper
    "3": "GTO",  # Top silk
    "4": "GBO",  # Bottom silk
    "5": "GTP",  # Top paste
    "6": "GBP",  # Bottom paste
    "7": "GTS",  # Top mask
    "8": "GBS",  # Bottom mask
    "10": "GKO",  # Board outline
}


@dataclass
class GerberLayer:
    name: str
    lines: list[str] = field(default_factory=list)
    apertures: dict[float, int] = field(default_factory=dict)
    next_d: int = 10

    def header(self) -> None:
        self.lines = [
            f"G04 {self.name}*",
            "%FSLAX35Y35*%",
            "%MOMM*%",
            "%LPD*%",
        ]

    def aper_circle(self, diam_mm: float) -> int:
        key = round(diam_mm, 5)
        if key not in self.apertures:
            self.apertures[key] = self.next_d
            self.next_d += 1
        return self.apertures[key]

    def emit_apertures(self) -> None:
        # insert after header
        block = [f"%ADD{d}C,{diam:.5f}*%" for diam, d in sorted(self.apertures.items(), key=lambda x: x[1])]
        self.lines[4:4] = block

    def finish(self) -> str:
        self.emit_apertures()
        self.lines.append("M02*")
        return "\n".join(self.lines) + "\n"


@dataclass
class Excellon:
    plated: list[tuple[float, float, float]] = field(default_factory=list)  # x,y,diam mm
    nplated: list[tuple[float, float, float]] = field(default_factory=list)

    def render(self, holes: list[tuple[float, float, float]], name: str) -> str:
        tools: dict[float, int] = {}
        next_t = 1
        body: list[str] = []
        for x, y, d in holes:
            key = round(d, 4)
            if key not in tools:
                tools[key] = next_t
                next_t += 1
            body.append((tools[key], x, y))
        lines = [
            f";{name}",
            "M48",
            "METRIC,TZ",
        ]
        for diam, t in sorted(tools.items(), key=lambda x: x[1]):
            lines.append(f"T{t}C{diam:.4f}")
        lines.append("%")
        lines.append("G90")
        lines.append("G05")
        cur = None
        for t, x, y in body:
            if t != cur:
                lines.append(f"T{t}")
                cur = t
            lines.append(f"X{x * 1000:.0f}Y{y * 1000:.0f}")  # µm when using METRIC without decimal — use decimal
        # Prefer decimal mm format used by modern fabs
        lines = [
            f";{name}",
            "M48",
            "METRIC,TZ",
        ]
        for diam, t in sorted(tools.items(), key=lambda x: x[1]):
            lines.append(f"T{t}C{diam:.4f}")
        lines.append("%")
        lines.append("G90")
        lines.append("G05")
        cur = None
        for t, x, y in body:
            if t != cur:
                lines.append(f"T{t}")
                cur = t
            lines.append(f"X{x:.4f}Y{y:.4f}")
        lines.append("M30")
        return "\n".join(lines) + "\n"


def u(v: float) -> float:
    return float(v) * UNIT_MM


def gerber_xy(x: float, y: float, origin_x: float, origin_y: float) -> str:
    # Flip Y so origin is lower-left of board bbox
    gx = u(x - origin_x)
    gy = u(origin_y - y)  # will set origin_y = bbox bottom? EasyEDA Y grows down in canvas?
    # EasyEDA Y increases downward. Gerber Y increases upward.
    # If bbox.y is top-left-ish (min y in EasyEDA = top), then:
    # gerber_y = (bbox.y + bbox.height - y) * UNIT
    return f"X{int(round(gx * 100000)):d}Y{int(round(gy * 100000)):d}"


class Converter:
    def __init__(self, data: dict):
        self.data = data
        bb = data["BBox"]
        self.origin_x = float(bb["x"])
        self.origin_y = float(bb["y"]) + float(bb["height"])  # EasyEDA top + height = bottom edge in Y-down
        self.bb_top = float(bb["y"])
        self.layers: dict[str, GerberLayer] = {n: GerberLayer(n) for n in set(LAYER_MAP.values())}
        for L in self.layers.values():
            L.header()
        self.plated_holes: list[tuple[float, float, float]] = []
        self.npth_holes: list[tuple[float, float, float]] = []

    def xy(self, x: float, y: float) -> str:
        gx = u(x - self.origin_x)
        gy = u(self.origin_y - y)
        return f"X{int(round(gx * 100000)):d}Y{int(round(gy * 100000)):d}"

    def mm_xy(self, x: float, y: float) -> tuple[float, float]:
        return u(x - self.origin_x), u(self.origin_y - y)

    def layer(self, lid: str) -> GerberLayer | None:
        name = LAYER_MAP.get(str(lid))
        return self.layers.get(name) if name else None

    def draw_track(self, width_u: float, layer_id: str, points: list[tuple[float, float]]) -> None:
        L = self.layer(layer_id)
        if not L or len(points) < 2:
            return
        dcode = L.aper_circle(max(u(width_u), 0.05))
        L.lines.append(f"D{dcode}*")
        x0, y0 = points[0]
        L.lines.append(f"{self.xy(x0, y0)}D02*")
        for x, y in points[1:]:
            L.lines.append(f"{self.xy(x, y)}D01*")

    def flash_circle(self, layer_id: str, x: float, y: float, diam_u: float) -> None:
        L = self.layer(layer_id)
        if not L:
            return
        dcode = L.aper_circle(max(u(diam_u), 0.05))
        L.lines.append(f"D{dcode}*")
        L.lines.append(f"{self.xy(x, y)}D03*")

    def add_hole(self, x: float, y: float, diam_u: float, plated: bool) -> None:
        mx, my = self.mm_xy(x, y)
        d = u(diam_u)
        if d <= 0:
            return
        (self.plated_holes if plated else self.npth_holes).append((mx, my, d))

    def parse_points(self, s: str) -> list[tuple[float, float]]:
        nums = [float(n) for n in s.replace(",", " ").split() if n]
        return list(zip(nums[0::2], nums[1::2]))

    def handle_track(self, parts: list[str]) -> None:
        # TRACK~width~layer~net~points~id~
        if len(parts) < 5:
            return
        width, layer, _net, pts = parts[1], parts[2], parts[3], parts[4]
        self.draw_track(float(width), layer, self.parse_points(pts))

    def handle_via(self, parts: list[str]) -> None:
        # VIA~x~y~diameter~net~hole~id~
        if len(parts) < 6:
            return
        x, y, diam, hole = float(parts[1]), float(parts[2]), float(parts[3]), float(parts[5])
        self.flash_circle("1", x, y, diam)
        self.flash_circle("2", x, y, diam)
        # solder mask openings
        self.flash_circle("7", x, y, diam * 1.1)
        self.flash_circle("8", x, y, diam * 1.1)
        self.add_hole(x, y, hole, plated=True)

    def handle_hole(self, parts: list[str]) -> None:
        # HOLE~x~y~diameter~id~
        if len(parts) < 4:
            return
        x, y, diam = float(parts[1]), float(parts[2]), float(parts[3])
        self.add_hole(x, y, diam, plated=False)

    def handle_pad(self, parts: list[str]) -> None:
        # PAD~shape~x~y~width~height~layer~net~number~hole~...
        # Some footprints omit number; hole may sit at index 8 or 9.
        if len(parts) < 8:
            return
        try:
            x, y = float(parts[2]), float(parts[3])
            w, h = float(parts[4]), float(parts[5])
        except ValueError:
            return
        layer = parts[6]
        hole = 0.0
        for idx in (8, 9, 7):
            if idx < len(parts):
                try:
                    hole = float(parts[idx])
                    break
                except ValueError:
                    continue
        diam = max(w, h)
        if layer == "11":  # multi-layer through pad
            for lid in ("1", "2", "7", "8"):
                self.flash_circle(lid, x, y, diam if lid in ("1", "2") else diam * 1.1)
            if hole > 0:
                self.add_hole(x, y, hole, plated=True)
        else:
            self.flash_circle(layer, x, y, diam)
            mask = {"1": "7", "2": "8"}.get(layer)
            if mask:
                self.flash_circle(mask, x, y, diam * 1.1)
            if hole > 0:
                self.add_hole(x, y, hole, plated=True)

    def handle_circle(self, parts: list[str]) -> None:
        # CIRCLE~x~y~width~diameter~layer~id~
        if len(parts) < 6:
            return
        x, y, width, diam, layer = float(parts[1]), float(parts[2]), float(parts[3]), float(parts[4]), parts[5]
        L = self.layer(layer)
        if not L:
            return
        # stroke circle as many segments
        r = diam / 2
        dcode = L.aper_circle(max(u(width), 0.05))
        L.lines.append(f"D{dcode}*")
        n = 64
        for i in range(n + 1):
            a = 2 * math.pi * i / n
            px, py = x + r * math.cos(a), y + r * math.sin(a)
            op = "D02*" if i == 0 else "D01*"
            L.lines.append(f"{self.xy(px, py)}{op}")

    def handle_rect(self, parts: list[str]) -> None:
        # RECT~x~y~width~height~layer~id~
        if len(parts) < 6:
            return
        x, y, w, h, layer = float(parts[1]), float(parts[2]), float(parts[3]), float(parts[4]), parts[5]
        pts = [(x, y), (x + w, y), (x + w, y + h), (x, y + h), (x, y)]
        self.draw_track(1.0, layer, pts)

    def handle_solidregion(self, parts: list[str]) -> None:
        # SOLIDREGION~layer~net~path~type~id~
        if len(parts) < 5:
            return
        layer, path, typ = parts[1], parts[3], parts[4]
        pts = self._parse_svg_path(path)
        if typ == "npth":
            # approximate NPTH as hole from bbox center
            if pts:
                xs, ys = zip(*pts)
                cx, cy = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
                d = max(max(xs) - min(xs), max(ys) - min(ys))
                self.add_hole(cx, cy, d, plated=False)
            return
        if layer == "10" and pts:
            self.draw_track(1.0, "10", pts + ([pts[0]] if pts[0] != pts[-1] else []))

    def handle_copperarea(self, parts: list[str]) -> None:
        # COPPERAREA~layer~...~path~...  — outline only (no pour fill in this exporter)
        if len(parts) < 5:
            return
        layer, path = parts[1], parts[4]
        pts = self._parse_svg_path(path)
        if pts:
            self.draw_track(1.0, layer, pts)

    def handle_arc(self, parts: list[str]) -> None:
        # ARC~width~layer~net~path~...
        if len(parts) < 5:
            return
        width, layer, path = float(parts[1]), parts[2], parts[4]
        pts = self._parse_svg_path(path)
        if pts:
            self.draw_track(width, layer, pts)

    def handle_text(self, parts: list[str]) -> None:
        # TEXT — skip stroke paths for brevity (silk labels optional)
        return

    def _parse_svg_path(self, path: str) -> list[tuple[float, float]]:
        pts: list[tuple[float, float]] = []
        for m in re.finditer(r"([ML])\s*([-\d.]+)\s+([-\d.]+)", path):
            pts.append((float(m.group(2)), float(m.group(3))))
        # Arc commands: approximate with endpoint only already captured via A ... — pull endpoints
        for m in re.finditer(
            r"A\s*[-\d.]+\s+[-\d.]+\s+[-\d.]+\s+\d\s+\d\s+([-\d.]+)\s+([-\d.]+)", path
        ):
            pts.append((float(m.group(1)), float(m.group(2))))
        return pts

    def expand_shapes(self, shapes: list[str]) -> list[str]:
        out: list[str] = []
        for s in shapes:
            if s.startswith("LIB~"):
                # embedded shapes after first PAD/TRACK/… fragment joined by #@$
                idx = len(s)
                for marker in ("PAD~", "TRACK~", "VIA~", "HOLE~", "CIRCLE~", "RECT~", "ARC~", "SOLIDREGION~"):
                    i = s.find(marker)
                    if i != -1:
                        idx = min(idx, i)
                if idx < len(s):
                    out.extend(p for p in s[idx:].split("#@$") if p)
            else:
                out.append(s)
        return out

    def convert(self) -> dict[str, str]:
        shapes = self.expand_shapes(self.data["shape"])
        handlers = {
            "TRACK": self.handle_track,
            "VIA": self.handle_via,
            "HOLE": self.handle_hole,
            "PAD": self.handle_pad,
            "CIRCLE": self.handle_circle,
            "RECT": self.handle_rect,
            "SOLIDREGION": self.handle_solidregion,
            "COPPERAREA": self.handle_copperarea,
            "ARC": self.handle_arc,
            "TEXT": self.handle_text,
        }
        for s in shapes:
            parts = s.split("~")
            kind = parts[0]
            fn = handlers.get(kind)
            if fn:
                try:
                    fn(parts)
                except Exception as exc:  # noqa: BLE001 — keep converting other primitives
                    print(f"warn {kind}: {exc}")

        files: dict[str, str] = {}
        ext = Excellon()
        for name, layer in self.layers.items():
            if len(layer.lines) > 4:  # more than header
                files[f"{name}.{name}"] = layer.finish()
        if self.plated_holes:
            files["Drill_PTH.DRL"] = ext.render(self.plated_holes, "PTH")
        if self.npth_holes:
            files["Drill_NPTH.DRL"] = ext.render(self.npth_holes, "NPTH")
        # board size note
        bb = self.data["BBox"]
        files["board-size.txt"] = (
            f"width_mm={u(float(bb['width'])):.3f}\n"
            f"height_mm={u(float(bb['height'])):.3f}\n"
            f"source=EasyEDA Standard JSON\n"
            f"note=Copper pours exported as outlines only; verify in Gerber viewer before fab.\n"
        )
        return files


def convert_file(src: Path, dest_zip: Path) -> dict:
    data = json.loads(src.read_text(encoding="utf-8"))
    files = Converter(data).convert()
    dest_zip.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(dest_zip, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for name, content in files.items():
            zf.writestr(name, content)
    return {
        "source": str(src),
        "zip": str(dest_zip),
        "files": list(files),
        "size_bytes": dest_zip.stat().st_size,
    }


BOARDS = [
    ("04-fcu", "glareshield/fcu/PCB_A320 FCU.json"),
    ("05-efis-left", "glareshield/efis/PCB_A320 EFIS Left.json"),
    ("06-efis-left-mini", "glareshield/efis/PCB_A320 EFIS Left (Mini).json"),
    ("07-efis-right", "glareshield/efis/PCB_A320 EFIS Right.json"),
    ("08-warning", "glareshield/warning/PCB_A320 Warning.json"),
    ("09-autobrake", "main-instrument-panel/autobrake/PCB_A320 Autobrake.json"),
    ("10-chrono", "main-instrument-panel/digital-chronometer/PCB_A320 Chrono.json"),
    ("11-illumination", "main-instrument-panel/illumination/PCB_A320 Illumination.json"),
    ("12-mini-overhead", "overhead/mini-overhead/PCB_A320 Mini Overhead.json"),
    ("13-atc-tcas", "pedestal/atc-tcas/PCB/PCB_A320 ATC-TCAS.json"),
    ("14-ecam", "pedestal/ecam/PCB_A320 ECAM.json"),
    ("15-mcdu-from-json", "pedestal/mcdu/PCB_PCB_A320 MCDU SMD_2023-03-08.json"),
]


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    src_root = root / "vendor" / "mobiflight-panels" / "aircraft" / "airbus-a32x"
    out_root = root / "pcbway-orders"
    report = []
    for folder, rel in BOARDS:
        src = src_root / rel
        if not src.exists():
            report.append({"id": folder, "error": f"missing {src}"})
            continue
        dest = out_root / folder / "Gerber.zip"
        info = convert_file(src, dest)
        # copy source json for EasyEDA re-export if needed
        (out_root / folder).mkdir(parents=True, exist_ok=True)
        dest_json = out_root / folder / "source-easyeda.json"
        dest_json.write_bytes(src.read_bytes())
        report.append({"id": folder, **info})
        print(f"OK {folder} → {dest} ({info['size_bytes']} bytes)")
    (out_root / "conversion-report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()

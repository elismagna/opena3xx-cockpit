#!/usr/bin/env python3
"""Extract component markers for the 3D PCB viewer."""
from __future__ import annotations

import json
import re
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ORDERS = ROOT / "pcbway-orders"
PREVIEWS = ORDERS / "_previews"
MF = ROOT / "vendor" / "mobiflight-panels" / "aircraft" / "airbus-a32x"

VENDOR_EASYEDA = {
    "01-mcdu": MF / "pedestal/mcdu/PCB_PCB_A320 MCDU SMD_2023-03-08.json",
    "04-fcu": MF / "glareshield/fcu/PCB_A320 FCU.json",
    "05-efis-left": MF / "glareshield/efis/PCB_A320 EFIS Left.json",
    "06-efis-left-mini": MF / "glareshield/efis/PCB_A320 EFIS Left (Mini).json",
    "07-efis-right": MF / "glareshield/efis/PCB_A320 EFIS Right.json",
    "08-warning": MF / "glareshield/warning/PCB_A320 Warning.json",
    "09-autobrake": MF / "main-instrument-panel/autobrake/PCB_A320 Autobrake.json",
    "10-chrono": MF / "main-instrument-panel/digital-chronometer/PCB_A320 Chrono.json",
    "11-illumination": MF / "main-instrument-panel/illumination/PCB_A320 Illumination.json",
    "12-mini-overhead": MF / "overhead/mini-overhead/PCB_A320 Mini Overhead.json",
    "13-atc-tcas": MF / "pedestal/atc-tcas/PCB/PCB_A320 ATC-TCAS.json",
    "14-ecam": MF / "pedestal/ecam/PCB_A320 ECAM.json",
}

VENDOR_FACE_SVG = {
    "02-overhead-lights": MF / "overhead/lights/a320-overhead-lights.svg",
    "03-engine-start": MF / "pedestal/engine-start/engine-start-panel.svg",
}

LIB_RE = re.compile(
    r"^LIB~(?P<x>-?[\d.]+)~(?P<y>-?[\d.]+)~(?P<body>.*)$",
    re.S,
)
FIELD_RE = re.compile(r"(package|BOM_Manufacturer Part|spicePre|spiceSymbolName|3DModel)`([^`]*)`")
TEXT_RE = re.compile(r"~4\.5~([^~]+)~")
VIEWBOX_RE = re.compile(r'viewBox="([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)"')
# Excellon hole: X093513Y037850  or Gerber flash …D03
FLASH_RE = re.compile(r"X(-?\d+)Y(-?\d+)(?:D0?3)?\b", re.I)


def classify(pkg: str, spice: str, name: str) -> str:
    blob = f"{pkg} {spice} {name}".lower()
    if any(k in blob for k in ("key", "sw", "switch", "tact", "push", "btn")):
        return "switch"
    if "led" in blob or spice.upper() == "L" and "seg" not in blob:
        return "led"
    if any(k in blob for k in ("encoder", "pot", "rotary", "rv09", "knob")):
        return "encoder"
    if any(k in blob for k in ("header", "pin", "conn", "jack", "usb")):
        return "connector"
    if any(k in blob for k in ("arduino", "mega", "rp2040", "mcu", "atmega")):
        return "mcu"
    if any(k in blob for k in ("595", "165", "dm13", "shift", "register", "expander")):
        return "ic"
    if spice.upper() in {"R", "C", "L"} or any(k in blob for k in ("res", "cap", "Ω", "uf", "nf")):
        return "passive"
    if spice.upper() in {"U", "Q", "D"}:
        return "ic"
    return "other"


def viewbox(board_id: str):
    svg = PREVIEWS / f"{board_id}-top.svg"
    if not svg.exists():
        return None
    m = VIEWBOX_RE.search(svg.read_text(encoding="utf-8", errors="ignore")[:900])
    if not m:
        return None
    x, y, w, h = map(float, m.groups())
    return {"x": x, "y": y, "w": w, "h": h}


def from_easyeda(path: Path, vb: dict) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    shapes = data.get("shape") or []
    libs = []
    xs, ys = [], []
    parsed = []
    for s in shapes:
        if not isinstance(s, str) or not s.startswith("LIB~"):
            continue
        m = LIB_RE.match(s)
        if not m:
            continue
        x, y = float(m.group("x")), float(m.group("y"))
        body = m.group("body")
        fields = dict(FIELD_RE.findall(body))
        label = (TEXT_RE.search(body) or [None, None])[1]
        pkg = fields.get("package", "")
        part = fields.get("BOM_Manufacturer Part", "")
        spice = fields.get("spicePre", "")
        name = label or fields.get("spiceSymbolName") or part or pkg or "part"
        xs.append(x)
        ys.append(y)
        parsed.append((x, y, pkg, part, spice, name))

    if not parsed:
        return []

    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    dx = max(max_x - min_x, 1e-6)
    dy = max(max_y - min_y, 1e-6)

    comps = []
    for i, (x, y, pkg, part, spice, name) in enumerate(parsed):
        # Map EasyEDA canvas → board mm in viewBox space (Y flipped like PCB).
        nx = (x - min_x) / dx
        ny = (y - min_y) / dy
        mx = vb["x"] + nx * vb["w"]
        my = vb["y"] + (1.0 - ny) * vb["h"]
        kind = classify(pkg, spice, name)
        comps.append(
            {
                "id": f"C{i+1}",
                "name": name[:48],
                "package": pkg[:64],
                "part": part[:64],
                "kind": kind,
                "side": "top",
                "x": round(mx, 3),
                "y": round(my, 3),
                "source": "easyeda",
            }
        )
    return comps


def _cutouts_to_comps(cut, vb: dict, flood: bool = False) -> list[dict]:
    comps: list[dict] = []
    bw, bh = vb["w"], vb["h"]
    if cut.board_rect:
        ox, oy, w, h = cut.board_rect

        def to_vb(x: float, y: float) -> tuple[float, float]:
            return vb["x"] + (x / max(w, 1e-6)) * vb["w"], vb["y"] + (1.0 - y / max(h, 1e-6)) * vb["h"]

        buttons = [(x - ox, y - oy, s) for x, y, s in cut.buttons]
        mounts = [(x - ox, y - oy, s) for x, y, s in cut.mounts]
        knobs = [(x - ox, y - oy, s) for x, y, s in cut.knobs]
    else:

        def to_vb(x: float, y: float) -> tuple[float, float]:
            return vb["x"] + (x / max(bw, 1e-6)) * vb["w"], vb["y"] + (1.0 - y / max(bh, 1e-6)) * vb["h"]

        buttons, mounts, knobs = cut.buttons, cut.mounts, cut.knobs

    for i, (x, y, s) in enumerate(buttons):
        mx, my = to_vb(x, y)
        comps.append(
            {
                "id": f"SW{i+1}",
                "name": f"Button {i+1}",
                "package": f"illuminated ~{s:.1f}mm",
                "part": "",
                "kind": "switch",
                "side": "top",
                "x": round(mx, 3),
                "y": round(my, 3),
                "source": "svg-cutout",
            }
        )
    for i, (x, y, s) in enumerate(knobs):
        mx, my = to_vb(x, y)
        comps.append(
            {
                "id": f"ENC{i+1}",
                "name": f"Knob {i+1}",
                "package": f"rotary ~{s:.1f}mm",
                "part": "",
                "kind": "encoder",
                "side": "top",
                "x": round(mx, 3),
                "y": round(my, 3),
                "source": "svg-cutout",
            }
        )
    for i, (x, y, s) in enumerate(mounts[:12]):
        mx, my = to_vb(x, y)
        comps.append(
            {
                "id": f"MH{i+1}",
                "name": f"Mount {i+1}",
                "package": f"hole ~{s:.1f}mm",
                "part": "",
                "kind": "mount",
                "side": "top",
                "x": round(mx, 3),
                "y": round(my, 3),
                "source": "svg-cutout",
            }
        )
    comps.append(
        {
            "id": "J1",
            "name": "Edge header",
            "package": "Dupont header",
            "part": "",
            "kind": "connector",
            "side": "top",
            "x": round(vb["x"] + vb["w"] * 0.5, 3),
            "y": round(vb["y"] + vb["h"] * 0.06, 3),
            "source": "svg-cutout",
        }
    )
    return comps


def from_face_svg(svg_path: Path, vb: dict, flood: bool = False) -> list[dict]:
    if not svg_path.exists():
        return []
    try:
        from svg_face_to_pcb import extract_cutouts  # type: ignore
        import xml.etree.ElementTree as ET
    except Exception:
        return []
    cut = extract_cutouts(ET.parse(svg_path).getroot(), accept_black_cuts=flood)
    return _cutouts_to_comps(cut, vb, flood=flood)


def from_rev0_svg(folder: Path, vb: dict) -> list[dict]:
    """Exact button/mount centers from the same cutout pass as svg_face_to_pcb."""
    vendor = VENDOR_FACE_SVG.get(folder.name)
    if vendor:
        return from_face_svg(vendor, vb, flood="flood" in folder.name)

    notes = folder / "fab-notes.txt"
    if not notes.exists():
        return []
    text = notes.read_text(encoding="utf-8", errors="ignore")
    src = None
    for line in text.splitlines():
        if line.lower().startswith("source:"):
            src = line.split(":", 1)[1].strip()
            break
    if not src:
        return []
    svg_path = (ROOT / src).resolve() if not Path(src).is_absolute() else Path(src)
    if not svg_path.exists():
        svg_path = (ROOT / src.replace("\\", "/")).resolve()
    if not svg_path.exists():
        return []
    try:
        from svg_face_to_pcb import extract_cutouts  # type: ignore
        import xml.etree.ElementTree as ET
    except Exception:
        return []
    flood = "flood" in folder.name
    cut = extract_cutouts(ET.parse(svg_path).getroot(), accept_black_cuts=flood)
    return _cutouts_to_comps(cut, vb, flood=flood)


def from_drill_clusters(zip_path: Path, vb: dict) -> list[dict]:
    """Fallback: cluster PTH flashes into switch-sized groups."""
    if not zip_path.exists() or not vb:
        return []
    pts = []
    with zipfile.ZipFile(zip_path) as z:
        for name in z.namelist():
            if "PTH" not in name.upper() and not name.upper().endswith(".DRL"):
                continue
            if "NPTH" in name.upper():
                continue
            raw = z.read(name).decode("latin-1", errors="ignore")
            # Detect units: if coords look like 1/10000 inch or metric 1/1000 mm — heuristics.
            for m in FLASH_RE.finditer(raw):
                pts.append((int(m.group(1)), int(m.group(2))))
    if len(pts) < 4:
        return []
    # Normalize to 0..1 then viewBox
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    dx = max(max_x - min_x, 1)
    dy = max(max_y - min_y, 1)
    # Simple grid quantization clustering
    cell = max(dx, dy) / 40
    buckets: dict[tuple[int, int], list] = {}
    for x, y in pts:
        key = (int(x / cell), int(y / cell))
        buckets.setdefault(key, []).append((x, y))
    comps = []
    i = 0
    for pts_b in buckets.values():
        if len(pts_b) < 3:
            continue
        cx = sum(p[0] for p in pts_b) / len(pts_b)
        cy = sum(p[1] for p in pts_b) / len(pts_b)
        nx = (cx - min_x) / dx
        ny = (cy - min_y) / dy
        mx = vb["x"] + nx * vb["w"]
        my = vb["y"] + ny * vb["h"]
        comps.append(
            {
                "id": f"P{i+1}",
                "name": f"Pad cluster {i+1}",
                "package": f"{len(pts_b)} holes",
                "part": "",
                "kind": "switch" if 3 <= len(pts_b) <= 8 else "connector",
                "side": "top",
                "x": round(mx, 3),
                "y": round(my, 3),
                "source": "drill-cluster",
                "approx": True,
            }
        )
        i += 1
        if i >= 40:
            break
    return comps


def main() -> None:
    PREVIEWS.mkdir(parents=True, exist_ok=True)
    out: dict[str, dict] = {}
    for folder in sorted(ORDERS.iterdir()):
        if not folder.is_dir() or folder.name.startswith("_"):
            continue
        vb = viewbox(folder.name)
        if not vb:
            continue
        comps: list[dict] = []
        easy = folder / "source-easyeda.json"
        if easy.exists():
            comps = from_easyeda(easy, vb)
        if not comps:
            vendor = VENDOR_EASYEDA.get(folder.name)
            if vendor and vendor.exists():
                comps = from_easyeda(vendor, vb)
        if not comps:
            comps = from_rev0_svg(folder, vb)
        if not comps:
            comps = from_drill_clusters(folder / "Gerber.zip", vb)

        kinds: dict[str, int] = {}
        for c in comps:
            kinds[c["kind"]] = kinds.get(c["kind"], 0) + 1
        out[folder.name] = {
            "id": folder.name,
            "viewBox": vb,
            "component_count": len(comps),
            "kinds": kinds,
            "components": comps,
        }
        print(f"{folder.name:20} comps={len(comps):4} kinds={kinds}")

    path = PREVIEWS / "components.json"
    path.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print("wrote", path, "boards", len(out))


if __name__ == "__main__":
    main()

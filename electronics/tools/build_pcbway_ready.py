#!/usr/bin/env python3
"""Build PCBWay readiness report + rewrite How-to-order-PCB.txt per zip."""
from __future__ import annotations

import csv
import json
import re
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
ORDERS = ROOT / "pcbway-orders"
PREVIEWS = ORDERS / "_previews"
MF = ROOT / "vendor" / "mobiflight-panels" / "aircraft" / "airbus-a32x"

# Board pack → MobiFlight config files (for later direct comparison).
MF_CONFIGS: dict[str, list[str]] = {
    "01-mcdu": [
        "pedestal/mcdu/configs/MCDU SMD.mcc",
        "pedestal/mcdu/configs/MCDU.mcc",
    ],
    "02-overhead-lights": [
        "overhead/lights/Overhead Lights Fenix.mcc",
        "overhead/lights/Overhead Lights FBW.mcc",
    ],
    "04-fcu": ["glareshield/fcu/FCU.mcc"],
    "05-efis-left": ["glareshield/efis/EFIS.mcc"],
    "06-efis-left-mini": ["glareshield/efis/EFIS.mcc"],
    "07-efis-right": ["glareshield/efis/EFIS.mcc"],
    "08-warning": ["glareshield/warning/Warning.mcc"],
    "09-autobrake": ["main-instrument-panel/autobrake/Autobrake.mcc"],
    "10-chrono": ["main-instrument-panel/digital-chronometer/Chrono.mcc"],
    "11-illumination": ["main-instrument-panel/illumination/Illumination.mfmc"],
    "12-mini-overhead": [
        "overhead/mini-overhead/MiniOverheadFenix.mcc",
        "overhead/mini-overhead/Mini Overhead.mcc",
    ],
    "13-atc-tcas": ["pedestal/atc-tcas/MobiFlight Config/ATC-TCAS.mcc"],
}

SKIP = {"15-mcdu-from-json"}  # use 01-mcdu (4-layer upstream) instead

LVAR_RE = re.compile(r"\(L:([^)\s,]+)")


def viewbox_mm(board_id: str) -> tuple[float, float] | None:
    svg = PREVIEWS / f"{board_id}-top.svg"
    if not svg.exists():
        return None
    head = svg.read_text(encoding="utf-8", errors="ignore")[:800]
    m = re.search(r'viewBox="([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)"', head)
    if not m:
        return None
    return round(float(m.group(3)), 2), round(float(m.group(4)), 2)


def zip_inventory(zip_path: Path) -> dict:
    names: list[str] = []
    with zipfile.ZipFile(zip_path) as z:
        names = [Path(i.filename).name for i in z.infolist() if not i.is_dir()]
    copper = sum(
        1
        for n in names
        if re.search(r"TopLayer|BottomLayer|InnerLayer", n, re.I)
    )
    required = [
        "Gerber_TopLayer.GTL",
        "Gerber_BottomLayer.GBL",
        "Gerber_TopSolderMaskLayer.GTS",
        "Gerber_BottomSolderMaskLayer.GBS",
        "Gerber_BoardOutlineLayer.GKO",
        "Drill_PTH_Through.DRL",
    ]
    missing = [r for r in required if r not in names]
    return {
        "files": sorted(names),
        "copper_layers": copper,
        "has_silk": any("Silkscreen" in n for n in names),
        "has_npth": any("NPTH" in n for n in names),
        "has_paste": any("Paste" in n for n in names),
        "missing_required": missing,
    }


def _read_bom_text(path: Path) -> str:
    raw = path.read_bytes()
    for enc in ("utf-8-sig", "utf-16", "utf-16-le", "cp1252"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def bom_summary(folder: Path) -> dict | None:
    bom = folder / "BOM.csv"
    if not bom.exists():
        return None
    text = _read_bom_text(bom)
    # EasyEDA BOM is often tab-separated; some are comma.
    delim = "\t" if "\t" in text.splitlines()[0] else ","
    rows = list(csv.DictReader(text.splitlines(), delimiter=delim))
    qty = 0
    kinds: dict[str, int] = {}
    for r in rows:
        q_raw = r.get("Quantity") or r.get("Qty") or "0"
        try:
            q = int(float(str(q_raw).strip().strip('"')))
        except ValueError:
            q = 0
        qty += q
        name = (r.get("Name") or r.get("Comment") or "").strip().strip('"')
        key = name.split()[0] if name else "part"
        kinds[key] = kinds.get(key, 0) + q
    return {
        "line_items": len(rows),
        "total_qty": qty,
        "top": sorted(kinds, key=kinds.get, reverse=True)[:8],  # type: ignore[arg-type]
    }


def parse_mcc_bindings(rel_paths: list[str]) -> dict:
    bindings: list[dict] = []
    seen: set[str] = set()
    for rel in rel_paths:
        path = MF / rel.replace("/", "\\")
        if not path.exists():
            path = MF / rel
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        # Prefer ElementTree; fall back to regex on LVars.
        try:
            root = ET.fromstring(text)
        except ET.ParseError:
            root = None
        if root is not None:
            for cfg in root.iter("config"):
                desc = (cfg.findtext("description") or "").strip()
                source = None
                for el in cfg.iter("source"):
                    source = el
                    break
                if source is None:
                    continue
                code = source.attrib.get("Value") or ""
                lvars = LVAR_RE.findall(code)
                pin = None
                for disp in cfg.iter("display"):
                    pin = disp.attrib.get("pin") or disp.attrib.get("registerOutputPin")
                    break
                for lv in lvars or [""]:
                    key = f"{desc}|{lv}|{pin}"
                    if key in seen:
                        continue
                    seen.add(key)
                    bindings.append(
                        {
                            "description": desc,
                            "lvar": lv or None,
                            "sim_code": code[:160] if code else None,
                            "hardware": pin,
                            "config": rel,
                            "aircraft": "fenix"
                            if "Fenix" in rel or "I_OH_" in code or "N_OH_" in code
                            else ("fbw" if "A32NX" in code else "unknown"),
                        }
                    )
        else:
            for lv in LVAR_RE.findall(text):
                if lv in seen:
                    continue
                seen.add(lv)
                bindings.append({"description": None, "lvar": lv, "config": rel})
    return {
        "binding_count": len(bindings),
        "unique_lvars": sorted({b["lvar"] for b in bindings if b.get("lvar")}),
        "bindings": bindings[:80],  # keep report small; full list later
    }


def how_to_text(board_id: str, inv: dict, size: tuple[float, float] | None) -> str:
    layers = inv["copper_layers"] or 2
    size_line = (
        f"- Board size (from preview outline): {size[0]} × {size[1]} mm"
        if size
        else "- Board size: verify in PCBWay Gerber Viewer after upload"
    )
    skip = board_id in SKIP
    lines = [
        f"PCBWay upload — {board_id}",
        f"- Upload this entire Gerber.zip (do not rename layers)",
        f"- Copper layers: {layers} ({'4-layer' if layers >= 4 else '2-layer'})",
        size_line,
        "- Thickness: 1.6 mm",
        "- Surface: HASL lead-free or ENIG",
        "- Color: green soldermask / white silkscreen (or black for glareshield taste)",
        "- Qty suggestion: 5",
        "- Required files present: Top/Bottom copper, solder mask, outline, PTH drill",
    ]
    if inv["has_npth"]:
        lines.append("- NPTH drill included")
    if inv["has_paste"]:
        lines.append("- Paste mask included (useful if ordering PCBA)")
    if skip:
        lines.append("- SKIP ORDERING: use 01-mcdu upstream Gerber instead of this pack")
    lines.append("- Local color preview: ../_previews/" + board_id + "-top.svg")
    return "\n".join(lines) + "\n"


def rewrite_howto(zip_path: Path, text: str) -> None:
    with zipfile.ZipFile(zip_path, "r") as zin:
        items = [
            (i.filename, zin.read(i.filename))
            for i in zin.infolist()
            if not i.is_dir() and Path(i.filename).name.lower() != "how-to-order-pcb.txt"
        ]
    items.append(("How-to-order-PCB.txt", text.encode("utf-8")))
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zout:
        for name, data in items:
            zout.writestr(name, data)


def main() -> None:
    PREVIEWS.mkdir(parents=True, exist_ok=True)
    report: list[dict] = []
    for folder in sorted(ORDERS.iterdir()):
        if not folder.is_dir() or folder.name.startswith("_"):
            continue
        z = folder / "Gerber.zip"
        if not z.exists():
            continue
        inv = zip_inventory(z)
        size = viewbox_mm(folder.name)
        howto = how_to_text(folder.name, inv, size)
        rewrite_howto(z, howto)
        bom = bom_summary(folder)
        mf = parse_mcc_bindings(MF_CONFIGS.get(folder.name, []))
        ready = not inv["missing_required"] and folder.name not in SKIP
        entry = {
            "id": folder.name,
            "pcbway_ready": ready,
            "skip_reason": "use 01-mcdu" if folder.name in SKIP else None,
            "copper_layers": inv["copper_layers"],
            "size_mm": {"w": size[0], "h": size[1]} if size else None,
            "missing_required": inv["missing_required"],
            "has_silk": inv["has_silk"],
            "has_npth": inv["has_npth"],
            "has_paste": inv["has_paste"],
            "bom": bom,
            "sim_bindings": {
                "count": mf["binding_count"],
                "unique_lvars": mf["unique_lvars"][:40],
                "sample": mf["bindings"][:12],
            },
            "gerber_zip": f"../{folder.name}/Gerber.zip",
            "preview_top": f"{folder.name}-top.svg",
            "preview_bottom": f"{folder.name}-bottom.svg",
        }
        report.append(entry)
        status = "READY" if ready else "SKIP/GAP"
        sz = f"{size[0]}x{size[1]}mm" if size else "?"
        print(
            f"{status:9} {folder.name:20} L{inv['copper_layers']} {sz:16} "
            f"MF={mf['binding_count']:3} missing={inv['missing_required']}"
        )

    out = PREVIEWS / "pcbway-ready.json"
    out.write_text(json.dumps({"boards": report, "goal": "pcbway_order_then_direct_comparison"}, indent=2), encoding="utf-8")
    ready_n = sum(1 for b in report if b["pcbway_ready"])
    print(f"wrote {out} — {ready_n}/{len(report)} PCBWay-ready")


if __name__ == "__main__":
    main()

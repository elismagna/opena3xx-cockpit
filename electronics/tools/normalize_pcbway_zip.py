#!/usr/bin/env python3
"""Rewrite every Gerber.zip with PCBWay-standard layer filenames."""
from __future__ import annotations

import re
import zipfile
from pathlib import Path

ORDERS = Path(__file__).resolve().parents[1] / "pcbway-orders"

MAP = [
    (re.compile(r"topsilkscreen|\bgto\b", re.I), "Gerber_TopSilkscreenLayer.GTO"),
    (re.compile(r"bottomsilkscreen|\bgbo\b", re.I), "Gerber_BottomSilkscreenLayer.GBO"),
    (re.compile(r"topsoldermask|\bgts\b", re.I), "Gerber_TopSolderMaskLayer.GTS"),
    (re.compile(r"bottomsoldermask|\bgbs\b", re.I), "Gerber_BottomSolderMaskLayer.GBS"),
    (re.compile(r"toppastemask|\bgtp\b", re.I), "Gerber_TopPasteMaskLayer.GTP"),
    (re.compile(r"bottompastemask|\bgbp\b", re.I), "Gerber_BottomPasteMaskLayer.GBP"),
    (re.compile(r"toplayer|\bgtl\b", re.I), "Gerber_TopLayer.GTL"),
    (re.compile(r"bottomlayer|\bgbl\b", re.I), "Gerber_BottomLayer.GBL"),
    (re.compile(r"boardoutline|\bgko\b|\.gm1$", re.I), "Gerber_BoardOutlineLayer.GKO"),
    (re.compile(r"innerlayer1|\.g1$", re.I), "Gerber_InnerLayer1.G1"),
    (re.compile(r"innerlayer2|\.g2$", re.I), "Gerber_InnerLayer2.G2"),
    (re.compile(r"npth", re.I), "Drill_NPTH_Through.DRL"),
    (re.compile(r"pth|drill|\.drl$|\.xln$", re.I), "Drill_PTH_Through.DRL"),
]


def map_name(name: str) -> str | None:
    base = Path(name).name
    if re.search(r"how-to|board-size|readme|\.txt$", base, re.I) and not re.search(
        r"pth|npth|drill", base, re.I
    ):
        if base.lower() in ("pth.txt", "npth.txt"):
            pass
        else:
            return None
    for rx, out in MAP:
        if rx.search(base):
            if "npth" in base.lower():
                return "Drill_NPTH_Through.DRL"
            return out
    return None


def normalize_zip(zip_path: Path) -> None:
    with zipfile.ZipFile(zip_path, "r") as zin:
        items = []
        for info in zin.infolist():
            if info.is_dir():
                continue
            mapped = map_name(info.filename)
            if not mapped:
                continue
            items.append((mapped, zin.read(info.filename)))

    # de-dupe mapped names (keep first)
    seen: set[str] = set()
    unique = []
    for name, data in items:
        if name in seen:
            if name.startswith("Drill_"):
                # allow second drill with via suffix
                alt = name.replace(".DRL", "_Via.DRL")
                if alt not in seen:
                    unique.append((alt, data))
                    seen.add(alt)
            continue
        seen.add(name)
        unique.append((name, data))

    how_to = """PCBWay upload notes
- Upload this entire Gerber.zip
- Layers: Top/Bottom copper, solder mask, silkscreen, board outline, PTH/NPTH drill
- Suggested: 2-layer (unless InnerLayer files present), 1.6 mm, HASL or ENIG, qty 5
- Preview colored stackup in ../_previews/<folder>-top.svg before ordering
"""
    unique.append(("How-to-order-PCB.txt", how_to.encode("utf-8")))

    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zout:
        for name, data in unique:
            zout.writestr(name, data)
    print(f"normalized {zip_path.parent.name}: {len(unique)-1} layers")


def main() -> None:
    for folder in sorted(ORDERS.iterdir()):
        if not folder.is_dir() or folder.name.startswith("_"):
            continue
        z = folder / "Gerber.zip"
        if z.exists():
            normalize_zip(z)


if __name__ == "__main__":
    main()

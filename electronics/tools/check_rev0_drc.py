#!/usr/bin/env python3
"""Independent DRC + connectivity check for the Rev0 boards (16-30).

Reads only what PCBWay will read (Gerber.zip: copper, drills, outline) plus
PINOUT.csv, and checks:
  * copper-to-copper clearance between different nets  >= 0.15 mm
  * copper to NPTH hole edge                           >= 0.25 mm
  * copper to board edge                               >= 0.30 mm
  * no header pins of different nets are shorted together
  * both GND header pins are joined, every SW/LED pin reaches its button

Needs: shapely.   Usage: python electronics/tools/check_rev0_drc.py
"""
from __future__ import annotations

import csv
import re
import sys
import zipfile
from pathlib import Path

from shapely.geometry import LineString, Point, box
from shapely.strtree import STRtree

ORDERS = Path(__file__).resolve().parents[1] / "pcbway-orders"
MIN_CU = 0.15
MIN_HOLE = 0.25
MIN_EDGE = 0.30


def parse_gerber(text: str):
    scale = 10 ** int(re.search(r"%FSLAX\d(\d)", text).group(1))
    ap: dict[int, float] = {}
    cur = None
    shapes = []
    line: list[tuple[float, float]] = []
    width = 0.0
    tok = re.compile(r"%ADD(\d+)C,([\d.]+)\*%|^D(\d+)\*$|X(-?\d+)Y(-?\d+)D0([123])\*", re.M)
    for m in tok.finditer(text):
        if m.group(1):
            ap[int(m.group(1))] = float(m.group(2))
        elif m.group(3):
            if len(line) > 1:
                shapes.append(LineString(line).buffer(width / 2))
            line = []
            cur = int(m.group(3))
        else:
            x, y = int(m.group(4)) / scale, int(m.group(5)) / scale
            op = m.group(6)
            if op == "2":
                if len(line) > 1:
                    shapes.append(LineString(line).buffer(width / 2))
                line, width = [(x, y)], ap[cur]
            elif op == "1":
                line.append((x, y))
            else:
                shapes.append(Point(x, y).buffer(ap[cur] / 2))
    if len(line) > 1:
        shapes.append(LineString(line).buffer(width / 2))
    return shapes


def parse_drill(text: str):
    tools, cur, out = {}, None, []
    for ln in text.splitlines():
        m = re.match(r"T(\d+)C([\d.]+)", ln)
        if m:
            tools[m.group(1)] = float(m.group(2))
            continue
        m = re.match(r"T(\d+)$", ln)
        if m:
            cur = tools[m.group(1)]
            continue
        m = re.match(r"X(-?[\d.]+)Y(-?[\d.]+)", ln)
        if m:
            out.append((float(m.group(1)), float(m.group(2)), cur))
    return out


class DSU:
    def __init__(self, n):
        self.p = list(range(n))

    def find(self, a):
        while self.p[a] != a:
            self.p[a] = self.p[self.p[a]]
            a = self.p[a]
        return a

    def union(self, a, b):
        self.p[self.find(a)] = self.find(b)


def check(folder: Path) -> list[str]:
    z = zipfile.ZipFile(folder / "Gerber.zip")
    rd = lambda n: z.read(n).decode()
    layers = {L: parse_gerber(rd(f"Gerber_{n}.G{L[-2:]}")) for L, n in
              (("GTL", "TopLayer"), ("GBL", "BottomLayer"))}
    pth = parse_drill(rd("Drill_PTH_Through.DRL"))
    npth = parse_drill(rd("Drill_NPTH_Through.DRL"))
    edge = [p for p in parse_gerber(rd("Gerber_BoardOutlineLayer.GKO"))]
    minx, miny, maxx, maxy = edge[0].bounds if len(edge) == 1 else \
        (min(e.bounds[0] for e in edge), min(e.bounds[1] for e in edge),
         max(e.bounds[2] for e in edge), max(e.bounds[3] for e in edge))
    # outline is drawn with a 0.15 mm stroke: shrink back to the centreline
    board = box(minx + 0.075, miny + 0.075, maxx - 0.075, maxy - 0.075)
    errs: list[str] = []

    # global shape index: layer shapes + plated holes join layers
    shapes = [(L, g) for L in ("GTL", "GBL") for g in layers[L]]
    dsu = DSU(len(shapes))
    for L in ("GTL", "GBL"):
        idx = [k for k, (l, _g) in enumerate(shapes) if l == L]
        tree = STRtree([shapes[k][1] for k in idx])
        for a_local, k in enumerate(idx):
            for b_local in tree.query(shapes[k][1]):
                kb = idx[int(b_local)]
                if kb > k and shapes[k][1].intersects(shapes[kb][1]):
                    dsu.union(k, kb)
    for x, y, _d in pth:
        pt = Point(x, y)
        hits = [k for k, (_l, g) in enumerate(shapes) if g.contains(pt)]
        for a, b in zip(hits, hits[1:]):
            dsu.union(a, b)

    # clearance between different components, per layer
    for L in ("GTL", "GBL"):
        idx = [k for k, (l, _g) in enumerate(shapes) if l == L]
        geoms = [shapes[k][1] for k in idx]
        tree = STRtree(geoms)
        for a_local, k in enumerate(idx):
            g = geoms[a_local]
            for b_local in tree.query(g.buffer(MIN_CU)):
                kb = idx[int(b_local)]
                if kb <= k or dsu.find(k) == dsu.find(kb):
                    continue
                d = g.distance(geoms[int(b_local)])
                if d < MIN_CU - 1e-6:
                    c = g.centroid
                    errs.append(f"{L} clearance {d:.3f} mm near ({c.x:.1f},{c.y:.1f})")
        for x, y, d in npth:
            hole = Point(x, y).buffer(d / 2)
            for g in geoms:
                if g.distance(hole) < MIN_HOLE - 1e-6:
                    errs.append(f"{L} copper {g.distance(hole):.3f} mm from NPTH at ({x:.1f},{y:.1f})")
        for g in geoms:
            if not board.buffer(-MIN_EDGE + 1e-6).contains(g):
                c = g.centroid
                errs.append(f"{L} copper within {MIN_EDGE} mm of edge near ({c.x:.1f},{c.y:.1f})")

    # connectivity against PINOUT.csv (PINOUT y is SVG-down; Gerber y is up)
    H = maxy - 0.075
    rows = list(csv.DictReader(open(folder / "PINOUT.csv", encoding="utf-8")))
    comp_of_pin = []
    for r in rows:
        pt = Point(float(r["x_mm"]), H - float(r["y_mm"]))
        ks = [k for k, (l, g) in enumerate(shapes) if l == "GTL" and g.contains(pt)]
        comp_of_pin.append(dsu.find(ks[0]) if ks else None)
    by_comp: dict[int, set[str]] = {}
    for r, c in zip(rows, comp_of_pin):
        by_comp.setdefault(c, set()).add(r["net"])
    for c, nets in by_comp.items():
        if len(nets) > 1:
            errs.append(f"SHORT between header nets {sorted(nets)}")
    gnd = {c for r, c in zip(rows, comp_of_pin) if r["net"] == "GND"}
    if len(gnd) != 1:
        errs.append("GND header pins not joined")
    # each signal net must reach at least one 1.7 mm footprint pad besides the header
    pad_pts = [Point(x, y) for x, y, d in pth if abs(d - 0.9) < 1e-3]
    pad_comp = []
    for pt in pad_pts:
        ks = [k for k, (l, g) in enumerate(shapes) if l == "GTL" and g.contains(pt)]
        pad_comp.append(dsu.find(ks[0]) if ks else None)
    for r, c in zip(rows, comp_of_pin):
        reached = sum(1 for pc in pad_comp if pc == c)
        if r["net"] != "GND" and reached != 1:
            errs.append(f"{r['net']} reaches {reached} footprint pads (expected 1)")
    n_btn = sum(1 for r in rows if r["net"].startswith("SW"))
    gnd_pads = sum(1 for pc in pad_comp if pc in gnd)
    if gnd_pads != 2 * n_btn:
        errs.append(f"GND reaches {gnd_pads} footprint pads (expected {2 * n_btn})")
    return errs


def main() -> int:
    bad = 0
    for folder in sorted(ORDERS.glob("[123][0-9]-*")):
        if not (16 <= int(folder.name[:2]) <= 30):
            continue
        errs = check(folder)
        status = "OK " if not errs else "FAIL"
        print(f"{status} {folder.name}" + ("" if not errs else f"  ({len(errs)} issues)"))
        for e in errs[:8]:
            print("     ", e)
        bad += bool(errs)
    print("all clean" if not bad else f"{bad} board(s) failing")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())

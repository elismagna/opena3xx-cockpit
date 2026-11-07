from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

ELEC = Path(
    r"C:\Users\Elis\Downloads\Fenix v3 Installer\A320-panels\electronics\vendor\mobiflight-panels\aircraft\airbus-a32x\overhead\elec\a320-overhead-elec.svg"
)
HYD = Path(
    r"C:\Users\Elis\Downloads\Fenix v3 Installer\A320-panels\electronics\vendor\mobiflight-panels\aircraft\airbus-a32x\overhead\hyd-fuel\a320-overhead-hydfuel.svg"
)
FIRE = Path(
    r"C:\Users\Elis\Downloads\Fenix v3 Installer\A320-panels\electronics\vendor\mobiflight-panels\aircraft\airbus-a32x\overhead\fire\a320-overhead-fire.svg"
)


def circle_blocks(text: str) -> list[str]:
    return re.findall(r"<circle\b[^>]*?/?>", text, flags=re.I)


def summarize(name: str, path: Path) -> None:
    text = path.read_text(encoding="utf-8", errors="ignore")
    blocks = circle_blocks(text)
    print(f"\n=== {name} circles={len(blocks)} ===")
    by_stroke: Counter[str] = Counter()
    by_r_red: Counter[float] = Counter()
    by_r_all: Counter[float] = Counter()
    red_xy: list[tuple[float, float, float]] = []
    for b in blocks:
        rm = re.search(r'\br="([0-9.]+)"', b)
        if not rm:
            continue
        r = round(float(rm.group(1)), 2)
        by_r_all[r] += 1
        style = b
        sm = re.search(r'stroke:(#[0-9a-fA-F]+)', b)
        stroke = sm.group(1).lower() if sm else "?"
        if 'stroke="' in b and stroke == "?":
            sm2 = re.search(r'stroke="([^"]+)"', b)
            stroke = (sm2.group(1) if sm2 else "?").lower()
        by_stroke[stroke] += 1
        if stroke in ("#ff0000", "red"):
            by_r_red[r] += 1
            cx = float(re.search(r'\bcx="([-\d.]+)"', b).group(1))
            cy = float(re.search(r'\bcy="([-\d.]+)"', b).group(1))
            red_xy.append((cx, cy, r))
    print("stroke counts", by_stroke.most_common(8))
    print("all r top", by_r_all.most_common(8))
    print("red r", by_r_red.most_common(10), "n=", len(red_xy))
    if red_xy:
        xs = [c[0] for c in red_xy]
        ys = [c[1] for c in red_xy]
        print(f"red bbox x={min(xs):.1f}..{max(xs):.1f} y={min(ys):.1f}..{max(ys):.1f}")
        print("sample red", red_xy[:8])

    # layer labels
    labels = re.findall(r'inkscape:label="([^"]+)"', text)
    print("layers", labels[:20])

    # red path circles approximated: look for path with A arcs and red stroke nearby
    # Extract red-styled path elements more carefully
    red_elems = re.findall(
        r'<path[^>]*style="[^"]*stroke:#ff0000[^"]*"[^>]*>',
        text,
    )
    print("red path elems", len(red_elems))
    # also rect red
    print("red rect", len(re.findall(r'<rect[^>]*stroke:#ff0000', text)))
    # ellipses
    ell = re.findall(r"<ellipse\b[^>]*?/?>", text)
    print("ellipses", len(ell))
    for e in ell[:6]:
        print(" ", e[:180].replace("\n", " "))


for n, p in [("elec", ELEC), ("hyd", HYD), ("fire", FIRE)]:
    summarize(n, p)

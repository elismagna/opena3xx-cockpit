from __future__ import annotations

import re
from collections import Counter
from pathlib import Path
from xml.etree import ElementTree as ET

FILES = {
    "elec": Path(
        r"C:\Users\Elis\Downloads\Fenix v3 Installer\A320-panels\electronics\vendor\mobiflight-panels\aircraft\airbus-a32x\overhead\elec\a320-overhead-elec.svg"
    ),
    "hyd": Path(
        r"C:\Users\Elis\Downloads\Fenix v3 Installer\A320-panels\electronics\vendor\mobiflight-panels\aircraft\airbus-a32x\overhead\hyd-fuel\a320-overhead-hydfuel.svg"
    ),
    "fire": Path(
        r"C:\Users\Elis\Downloads\Fenix v3 Installer\A320-panels\electronics\vendor\mobiflight-panels\aircraft\airbus-a32x\overhead\fire\a320-overhead-fire.svg"
    ),
}


def local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def probe(name: str, path: Path) -> None:
    # stream-friendly: only scan for circle/ellipse/sodipodi arc attrs via regex on red-ish chunks
    text = path.read_text(encoding="utf-8", errors="ignore")
    print(f"\n=== {name} bytes={len(text)} ===")
    print("circle tags", text.count("<circle"))
    print("ellipse tags", text.count("<ellipse"))
    print("sodipodi:type=\"arc\"", text.count('sodipodi:type="arc"'))
    print("red strokes", text.count("stroke:#ff0000"))
    rs = Counter(float(m) for m in re.findall(r'\br="([0-9.]+)"', text))
    print("top r", rs.most_common(10))
    # sample a red path that looks circular (starts with m and has a)
    red_paths = re.findall(
        r'style="[^"]*stroke:#ff0000[^"]*"[^>]*\sd="([^"]{20,200})"',
        text,
    )
    print("red path samples", len(red_paths))
    for d in red_paths[:5]:
        print(" ", d[:120])
    arcs = re.findall(
        r'sodipodi:type="arc"[^>]*sodipodi:cx="([^"]+)"[^>]*sodipodi:cy="([^"]+)"[^>]*sodipodi:rx="([^"]+)"[^>]*sodipodi:ry="([^"]+)"',
        text,
    )
    if not arcs:
        arcs = re.findall(
            r'sodipodi:cx="([^"]+)"[^>]*sodipodi:cy="([^"]+)"[^>]*sodipodi:rx="([^"]+)"[^>]*sodipodi:ry="([^"]+)"',
            text,
        )
    print("sodipodi arcs", len(arcs))
    if arcs:
        rxs = Counter(round(float(a[2]), 1) for a in arcs)
        print("arc rx top", rxs.most_common(10))


for n, p in FILES.items():
    probe(n, p)

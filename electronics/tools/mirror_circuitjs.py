#!/usr/bin/env python3
"""Mirror Falstad CircuitJS compiled assets for same-origin embed."""
from __future__ import annotations

import re
import urllib.request
from pathlib import Path

BASE = "https://www.falstad.com/circuit/"
OUT = Path(__file__).resolve().parents[1] / "pcbway-orders" / "_previews" / "circuitjs"


def fetch(rel: str) -> bytes:
    url = BASE + rel.lstrip("/")
    dest = OUT / rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    print("GET", url)
    req = urllib.request.Request(url, headers={"User-Agent": "a320-panels-circuitjs-mirror"})
    data = urllib.request.urlopen(req, timeout=90).read()
    dest.write_bytes(data)
    return data


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for rel in ("circuitjs.html", "iframe.html", "lz-string.min.js"):
        try:
            fetch(rel)
        except Exception as e:
            print("fail", rel, e)

    nocache = fetch("circuitjs1/circuitjs1.nocache.js").decode("utf-8", "replace")
    files = set(re.findall(r"([A-Za-z0-9_.-]+\.(?:cache\.js|cache\.css|js|png|gif|css|wasm))", nocache))
    # GWT also references strong names without extension in some builds; pull .cache.js hex names
    for hx in re.findall(r'"([A-F0-9]{32})"', nocache, flags=re.I):
        files.add(f"{hx}.cache.js")
        files.add(f"{hx}.cache.css")
    print("candidates", len(files))
    for f in sorted(files):
        rel = f"circuitjs1/{f}"
        try:
            fetch(rel)
        except Exception as e:
            print("skip", rel, e)

    # common deferred chunks / clear.cache.gif
    for extra in (
        "circuitjs1/clear.cache.gif",
        "circuitjs1/hosted.html",
        "circuitjs1/compilation-mappings.txt",
    ):
        try:
            fetch(extra)
        except Exception as e:
            print("skip", extra, e)

    print("done ->", OUT)


if __name__ == "__main__":
    main()

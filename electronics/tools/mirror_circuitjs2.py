#!/usr/bin/env python3
from __future__ import annotations

import re
import urllib.request
from pathlib import Path

BASE = "https://www.falstad.com/circuit/"
OUT = Path(__file__).resolve().parents[1] / "pcbway-orders" / "_previews" / "circuitjs"


def fetch(rel: str) -> bytes:
    url = BASE + rel.lstrip("/")
    dest = OUT.joinpath(*rel.split("/"))
    dest.parent.mkdir(parents=True, exist_ok=True)
    print("GET", url)
    req = urllib.request.Request(url, headers={"User-Agent": "a320-panels"})
    data = urllib.request.urlopen(req, timeout=180).read()
    dest.write_bytes(data)
    print(" ", len(data), "bytes")
    return data


def main() -> None:
    for rel in [
        "circuitjs1/06BCBFAFF940A7BB694C63C1B9CBDB6B.cache.js",
        "circuitjs1/3667A141E95FDB21468CA0FDBC967657.cache.js",
        "circuitjs1/6B0FADC02E1AD650AD48EC3D6D7B4350.cache.js",
        "circuitjs1/58FFD0A4F3B1A704837D1DC7C1F6D961.cache.js",
        "circuitjs1/DCEA7872AA86481986B4A66D68AC33FE.cache.js",
        "circuitjs1/gwt/clean/clean.css",
        "circuitjs1/clear.cache.gif",
    ]:
        try:
            fetch(rel)
        except Exception as e:
            print("fail", rel, e)

    # Classic embed shell that loads GWT module (not the new Vite homepage)
    classic = """<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<title>CircuitJS embed</title>
<style>html,body,#circuitjsdiv{margin:0;height:100%;width:100%;overflow:hidden;background:#000}</style>
<script src="lz-string.min.js"></script>
</head>
<body>
<div id="circuitjsdiv"></div>
<script>
window.CircuitJSParams = {
  startCircuitText: '',
  mouseMode: false,
  hideMenu: true,
  hideSidebar: false
};
</script>
<script src="circuitjs1/circuitjs1.nocache.js"></script>
</body>
</html>
"""
    (OUT / "embed.html").write_text(classic, encoding="utf-8")

    # Also grab modern hashed assets for optional full UI
    html = fetch("circuitjs.html").decode("utf-8", "replace")
    for rel in re.findall(r"\./(circuitjs116/[^\"'\\s>]+)", html):
        try:
            fetch(rel)
        except Exception as e:
            print("fail", rel, e)

    print("done", OUT)


if __name__ == "__main__":
    main()

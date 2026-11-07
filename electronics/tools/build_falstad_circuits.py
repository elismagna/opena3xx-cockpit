#!/usr/bin/env python3
"""Generate Falstad/CircuitJS circuit dumps for panel boards (face I/O sim)."""
from __future__ import annotations

import json
from pathlib import Path

PREVIEWS = Path(__file__).resolve().parents[1] / "pcbway-orders" / "_previews"
CIRCUITS = PREVIEWS / "circuitjs" / "circuits"
CATALOG = PREVIEWS / "viewer-catalog.json"

# Prefer face legends from catalog; fallback names
DEFAULT_LABELS = [f"SW{i}" for i in range(1, 13)]


def header() -> str:
    # flags, timestep, ..., current speed, etc. — match ledflasher style
    return "$ 1 0.000005 10.20027730826997 50 5 50"


def rail(x: int, y: int, volts: float = 5.0) -> str:
    # Voltage rail (avoids voltage-source wire-loop detector issues)
    return f"R {x} {y} {x} {y - 16} 0 0 40 {volts} 0 0 0.5"


def ground(x: int, y: int) -> str:
    return f"g {x} {y} {x} {y + 16} 0"


def wire(x1: int, y1: int, x2: int, y2: int) -> str:
    return f"w {x1} {y1} {x2} {y2} 0"


def switch(x1: int, y: int, x2: int, closed: bool = False) -> str:
    # S x1 y1 x2 y2 flags position momentary  (0=open, 1=closed)
    pos = 1 if closed else 0
    return f"S {x1} {y} {x2} {y} 0 {pos} 0"


def led(x: int, y1: int, y2: int) -> str:
    # 162 LED — match ledflasher.txt dump (flags + 1.0 0.0 0.0)
    return f"162 {x} {y1} {x} {y2} 0 1.0 0.0 0.0"


def resistor(x1: int, y: int, x2: int, ohms: float = 330.0) -> str:
    return f"r {x1} {y} {x2} {y} 0 {ohms}"


def label(x: int, y: int, text: str) -> str:
    # Underscores survive URL/embed better than CircuitJS \s escapes
    safe = text.replace("/", "-").replace(" ", "_")[:18]
    return f"x {x} {y} {x + 40} {y} 0 12 {safe}"


def build_panel_circuit(title: str, names: list[str], closed: set[int] | None = None) -> str:
    """One column per control: +5V rail — SW — LED — R — GND."""
    closed = closed or set()
    lines = [header()]

    y_v = 48
    y_g = 320
    rail_x = 64
    lines.append(rail(rail_x, y_v, 5.0))
    lines.append(ground(rail_x, y_g))
    lines.append(wire(rail_x, y_v, 96, y_v))
    lines.append(wire(rail_x, y_g, 96, y_g))
    lines.append(label(96, 20, title[:18]))

    x0 = 120
    gap = 80
    for i, name in enumerate(names):
        x = x0 + i * gap
        if i == 0:
            lines.append(wire(96, y_v, x, y_v))
            lines.append(wire(96, y_g, x, y_g))
        else:
            prev = x0 + (i - 1) * gap
            lines.append(wire(prev, y_v, x, y_v))
            lines.append(wire(prev, y_g, x, y_g))

        y_sw = 112
        lines.append(wire(x, y_v, x, y_sw))
        x2 = x + 48
        lines.append(switch(x, y_sw, x2, closed=(i in closed)))
        lines.append(wire(x2, y_sw, x2, 152))
        lines.append(led(x2, 152, 216))
        lines.append(wire(x2, 216, x2, 248))
        lines.append(f"r {x2} 248 {x2} 296 0 330")
        lines.append(wire(x2, 296, x2, y_g))
        # 1M anode→gnd on same column (no floating stubs)
        lines.append(f"r {x2} 152 {x2} {y_g} 0 1000000")
        lines.append(label(x - 4, y_sw - 24, name))

    return "\n".join(lines) + "\n"


def board_names(board: dict) -> list[str]:
    names: list[str] = []
    for p in board.get("parts") or []:
        if p.get("kind") not in ("switch", "encoder"):
            continue
        if p.get("face") is False:
            continue
        # Prefer real face legends; skip anonymous Pushbutton N when better labels exist later
        names.append(str(p.get("label") or p.get("id")))
    out: list[str] = []
    for n in names:
        if n not in out:
            out.append(n)
        if len(out) >= 10:
            break
    return out or DEFAULT_LABELS[:6]


def main() -> None:
    CIRCUITS.mkdir(parents=True, exist_ok=True)
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    index = []
    for board in catalog["boards"]:
        if board.get("skip"):
            continue
        names = board_names(board)
        if not names:
            continue
        text = build_panel_circuit(board["title"], names)
        path = CIRCUITS / f"{board['id']}.txt"
        path.write_text(text, encoding="utf-8")
        index.append(
            {
                "id": board["id"],
                "title": board["title"],
                "file": f"circuits/{board['id']}.txt",
                "controls": names,
            }
        )
        print("wrote", path.name, "controls", len(names))

    (PREVIEWS / "circuitjs" / "circuits-index.json").write_text(
        json.dumps({"boards": index}, indent=2), encoding="utf-8"
    )
    print("index", len(index))


if __name__ == "__main__":
    main()

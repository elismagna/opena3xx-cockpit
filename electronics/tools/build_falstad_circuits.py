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
    # flags, timestep, sim speed, current speed, voltage range, power brightness
    return "$ 1 0.000005 10.20027730826997 50 5 50"


def label(x: int, y: int, text: str) -> str:
    safe = text.replace("/", "-").replace(" ", "_")[:16]
    return f"x {x} {y} {x + 40} {y} 0 12 {safe}"


COLS = 8          # controls per row
DX, DY = 128, 256  # column / row pitch (CircuitJS grid units, multiples of 16)


def build_panel_circuit(title: str, names: list[str]) -> str:
    """One self-contained column per control, as wired on the Rev0 PCB + Mega.

        +5V --20k pull-up-- PIN --switch-- GND      (MobiFlight input, active low)
                             |
                         MobiFlight
                     (input low -> output high, modelled by an inverter)
                             |
                           330R -- LED -- GND        (Korry lamp)

    Every connection meets at element endpoints (CircuitJS does not join a wire
    to the middle of another wire). Switches are ``s`` elements; position 1 =
    open, 0 = closed (sim.html writes the pressed state).
    """
    lines = [header(), label(32, 24, title)]
    for i, name in enumerate(names):
        x = 64 + (i % COLS) * DX
        y = 96 + (i // COLS) * DY
        pin = y + 64
        lines += [
            f"R {x} {y} {x} {y - 16} 0 0 40 5 0 0 0.5",
            f"r {x} {y} {x} {pin} 0 20000",
            f"s {x} {pin} {x} {pin + 64} 0 1 0",
            f"g {x} {pin + 64} {x} {pin + 80} 0",
            f"I {x} {pin} {x + 64} {pin} 0 0.5 5",
            f"r {x + 64} {pin} {x + 64} {pin + 48} 0 330",
            f"162 {x + 64} {pin + 48} {x + 64} {pin + 96} 0 1.0 0.0 0.0",
            f"g {x + 64} {pin + 96} {x + 64} {pin + 112} 0",
            label(x - 16, y - 40, name),
        ]
    return "\n".join(lines) + "\n"


def board_parts(board: dict) -> list[tuple[str, str]]:
    """(part id, display name) for every face switch/encoder, in catalog order.

    Upstream boards label parts by MPN (all 74 MCDU keys are "SKPMAPE010"), so
    repeated labels get a running number instead of being dropped.
    """
    parts = [p for p in board.get("parts") or []
             if p.get("kind") in ("switch", "encoder") and p.get("face") is not False]
    counts: dict[str, int] = {}
    for p in parts:
        lab = str(p.get("label") or p.get("id"))
        counts[lab] = counts.get(lab, 0) + 1
    seen: dict[str, int] = {}
    out = []
    for p in parts:
        lab = str(p.get("label") or p.get("id"))
        if counts[lab] > 1:
            seen[lab] = seen.get(lab, 0) + 1
            lab = f"{lab} {seen[lab]}"
        out.append((str(p.get("id")), lab))
    return out


def main() -> None:
    CIRCUITS.mkdir(parents=True, exist_ok=True)
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    index = []
    for board in catalog["boards"]:
        if board.get("skip"):
            continue
        parts = board_parts(board)
        if not parts:
            continue
        names = [n for _pid, n in parts]
        text = build_panel_circuit(board["title"], names)
        path = CIRCUITS / f"{board['id']}.txt"
        path.write_text(text, encoding="utf-8")
        index.append(
            {
                "id": board["id"],
                "title": board["title"],
                "file": f"circuits/{board['id']}.txt",
                "controls": names,
                "part_ids": [pid for pid, _n in parts],
            }
        )
        print("wrote", path.name, "controls", len(names))

    (PREVIEWS / "circuitjs" / "circuits-index.json").write_text(
        json.dumps({"boards": index}, indent=2), encoding="utf-8"
    )
    print("index", len(index))


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Human-readable catalog for the 3D PCB viewer (boards + face controls)."""
from __future__ import annotations

import json
from pathlib import Path

PREVIEWS = Path(__file__).resolve().parents[1] / "pcbway-orders" / "_previews"

TITLES = {
    "01-mcdu": ("MCDU", "Pedestal keyboard & display unit"),
    "02-overhead-lights": ("Overhead lights", "Dome / storm / annunciator lighting"),
    "03-engine-start": ("Engine start", "Pedestal engine start panel"),
    "04-fcu": ("FCU", "Autopilot flight control unit"),
    "05-efis-left": ("EFIS (captain)", "Captain display mode & range"),
    "06-efis-left-mini": ("EFIS mini", "Compact captain EFIS"),
    "07-efis-right": ("EFIS (FO)", "First officer EFIS"),
    "08-warning": ("Warning", "Master warn / caution glareshield"),
    "09-autobrake": ("Autobrake", "MIP autobrake & brake fans"),
    "10-chrono": ("Chronometer", "MIP clock / chrono"),
    "11-illumination": ("Illumination", "MIP panel brightness"),
    "12-mini-overhead": ("Mini overhead", "Compact overhead essentials"),
    "13-atc-tcas": ("ATC / TCAS", "Transponder & TCAS"),
    "14-ecam": ("ECAM control", "Pedestal ECAM page keys"),
    "15-mcdu-from-json": ("MCDU (skip)", "Use the official MCDU board instead"),
    "16-terr-on-nd": ("TERR ON ND", "Terrain on navigation display"),
    "17-flood-light": ("Flood light", "Pedestal flood lighting"),
    "18-flt-ctl-fo": ("Flight controls FO", "FO side flight-control panel"),
    "19-gndservices": ("Ground services", "External power / services"),
    "20-fire": ("Fire", "Engine / APU fire panel"),
    "21-adirs": ("ADIRS", "Air data / inertial reference"),
    "22-evac": ("Evacuation", "Cabin evacuate controls"),
    "23-audio": ("Audio", "ACP audio control panel"),
    "24-radio": ("Radio", "RMP radio management"),
    "25-cargo-heat": ("Cargo heat", "Cargo smoke / heat"),
    "26-emer-elec": ("Emer elec", "Emergency electrical"),
    "27-aircond": ("Air conditioning", "Bleed / packs / cabin temp"),
    "28-flt-ctl": ("Flight controls", "Captain flight-control panel"),
    "29-elec": ("Electrical", "Generators, buses, batteries"),
    "30-hyd-fuel": ("Hydraulics & fuel", "HYD + fuel pumps"),
}

KIND_LABEL = {
    "switch": "Pushbutton",
    "encoder": "Rotary knob",
    "led": "Indicator light",
    "connector": "Cable header",
    "mcu": "Controller board",
    "ic": "Driver chip",
    "passive": "Small part",
    "mount": "Mounting hole",
    "other": "Part",
}

KIND_HELP = {
    "switch": "Press-on control on the panel face.",
    "encoder": "Twist control (mode / value).",
    "led": "Status light / annunciator.",
    "connector": "Plug that goes to the controller box.",
    "mcu": "On-board controller (Arduino-class).",
    "ic": "Chip that drives lights or reads buttons.",
    "passive": "Tiny support part under the face.",
    "mount": "Screw into the printed shell.",
    "other": "Other hardware.",
}

# Prefer real panel legends when we know the face layout (order = face switches then knobs).
FACE_LEGENDS: dict[str, list[str]] = {
    "21-adirs": [
        "IR 1",
        "IR 2",
        "IR 3",
        "ADR 1",
        "ADR 2",
        "ADR 3",
        "ATT HDG",
        "ON BAT",
        "IR 1 fault / align",
        "IR 3 fault / align",
        "IR 1 mode",
        "IR 2 mode",
        "IR 3 mode",
    ],
    "12-mini-overhead": [
        "Anti-ice",
        "Battery",
        "External power",
        "Fuel pumps",
        "APU master",
        "APU start",
        "APU bleed",
    ],
    "04-fcu": [
        "SPD / MACH",
        "HDG / TRK",
        "ALT",
        "V/S / FPA",
        "AP 1",
        "AP 2",
        "A/THR",
        "LOC",
        "APPR",
        "EXPED",
        "METER / FEET",
        "FD",
    ],
}


def human_name(kind: str, name: str, idx: int) -> str:
    if kind == "switch":
        if name.lower().startswith("button"):
            return f"Pushbutton {idx}"
        return name if len(name) < 28 else f"Pushbutton {idx}"
    if kind == "encoder":
        if name.lower().startswith("knob"):
            return f"Knob {idx}"
        return name
    if kind == "led":
        return name if name and not name.lower().startswith("led") else f"Light {idx}"
    if kind == "connector":
        return "Cable header to controller"
    if kind == "mcu":
        return "Arduino / controller"
    if kind == "mount":
        return f"Screw mount {idx}"
    if kind == "ic":
        return name if name else f"Chip {idx}"
    return name or KIND_LABEL.get(kind, "Part")


def main() -> None:
    comps = json.loads((PREVIEWS / "components.json").read_text(encoding="utf-8"))
    ready = {b["id"]: b for b in json.loads((PREVIEWS / "pcbway-ready.json").read_text(encoding="utf-8"))["boards"]}

    boards = []
    for bid, pack in sorted(comps.items()):
        title, blurb = TITLES.get(bid, (bid, ""))
        r = ready.get(bid, {})
        kinds = pack.get("kinds") or {}
        face = {
            "pushbuttons": kinds.get("switch", 0),
            "knobs": kinds.get("encoder", 0),
            "lights": kinds.get("led", 0),
            "headers": kinds.get("connector", 0),
        }
        # Attach sim hints to face controls in order
        samples = (r.get("sim_bindings") or {}).get("sample") or []
        sim_labels = [s.get("description") for s in samples if s.get("description")]

        parts = []
        counters = {k: 0 for k in KIND_LABEL}
        legends = FACE_LEGENDS.get(bid, [])
        legend_i = 0
        for c in pack.get("components") or []:
            kind = c.get("kind") or "other"
            counters[kind] = counters.get(kind, 0) + 1
            n = counters[kind]
            label = human_name(kind, c.get("name") or "", n)
            role = None
            if kind in ("switch", "encoder") and legend_i < len(legends):
                label = legends[legend_i]
                legend_i += 1
            face_i = sum(1 for p in parts if p["kind"] in ("switch", "led", "encoder"))
            if kind in ("switch", "led", "encoder") and face_i < len(sim_labels):
                role = sim_labels[face_i]
            elif kind in ("switch", "encoder"):
                role = f"Control on the {title}"
            elif kind == "led":
                role = f"Light on the {title}"
            elif kind == "connector":
                role = "Ribbon / Dupont link to MobiFlight"
            parts.append(
                {
                    "id": c["id"],
                    "kind": kind,
                    "label": label,
                    "role": role,
                    "help": KIND_HELP.get(kind, ""),
                    "typeLabel": KIND_LABEL.get(kind, kind),
                    "x": c.get("x"),
                    "y": c.get("y"),
                    "approx": bool(c.get("approx")),
                    "face": kind in ("switch", "encoder", "led", "connector", "mcu"),
                }
            )

        summary_bits = []
        if face["pushbuttons"]:
            summary_bits.append(f"{face['pushbuttons']} buttons")
        if face["knobs"]:
            summary_bits.append(f"{face['knobs']} knobs")
        if face["lights"]:
            summary_bits.append(f"{face['lights']} lights")
        if face["headers"]:
            summary_bits.append("cable header")

        size = r.get("size_mm") or {}
        boards.append(
            {
                "id": bid,
                "title": title,
                "blurb": blurb,
                "summary": " · ".join(summary_bits) or f"{pack.get('component_count', 0)} parts",
                "ready": bool(r.get("pcbway_ready")),
                "skip": bid == "15-mcdu-from-json",
                "layers": r.get("copper_layers") or 2,
                "size": f"{size.get('w', '?')} × {size.get('h', '?')} mm" if size else "size TBD",
                "size_mm": size,
                "viewBox": pack.get("viewBox"),
                "orderNote": (
                    "Skip — order 01 MCDU instead"
                    if bid == "15-mcdu-from-json"
                    else ("4-layer board — select 4 layers on PCBWay" if (r.get("copper_layers") or 2) >= 4 else "2-layer board · ready to upload")
                ),
                "parts": parts,
            }
        )

    out = PREVIEWS / "viewer-catalog.json"
    out.write_text(json.dumps({"boards": boards}, indent=2), encoding="utf-8")
    print("wrote", out, "boards", len(boards))


if __name__ == "__main__":
    main()

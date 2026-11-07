# External PCB / panel references

Local copies under `electronics/vendor/`. Does **not** replace our `Gerber.zip` packs — use for dimensions and layout checks before PCBWay.

## Cloned repos

| Path | Source | Useful for PCBs? |
| --- | --- | --- |
| `vendor/mobiflight-panels/` | [MobiFlight/mobiflight-panels](https://github.com/MobiFlight/mobiflight-panels) | **Yes** — EasyEDA + Gerbers → our `01`–`14` |
| `vendor/A320-Home-Cockpit/` | [JA3297/A320-Home-Cockpit](https://github.com/JA3297/A320-Home-Cockpit) | **Panel DWG/DXF** (faces/dims), STLs — few/no copper Gerbers |
| `vendor/open-airbus-cockpit/` | [apoloval/open-airbus-cockpit](https://github.com/apoloval/open-airbus-cockpit) | Fritzing keypad / 8-bit expander (`.fzz`), FCU Arduino sketch — not full overhead Gerbers |

### JA3297 DWGs worth opening for hole alignment

- `A320-Home-Cockpit/00 General/A320 PANELES.dwg` (+ `A320 PANELES Print.dwg`)
- Pedestal: `50 Pedestal/**/**/*.dwg` / `.dxf` (RMP, ACP, lights, radar, XPDR, ECAM, MIP switches)

### open-airbus hardware

- `open-airbus-cockpit/boards/keypad/keypad.fzz`
- `open-airbus-cockpit/boards/8bits-expansion/8bits-expansion.fzz`
- `open-airbus-cockpit/fcu/` — sketch + Graffle blueprint

## Downloaded schematics (ops, not copper)

`vendor/reference/aviationhunt-schematics/` from  
[AviationHunt A320 debriefing schematics](https://www.aviationhunt.com/airbus-a320-debriefing-schematics/)  
(air-cond, elec, fire, flight controls, fuel, hyd, landing gear, braking). Educational systems diagrams — use to label controls, not to fab boards.

## Not cloned / no direct file URL

| Link | Status |
| --- | --- |
| [Okansacli A320 panel DWGs](https://www.okansacli.com/post/a320-cockpit-panel-drawings-in-dwg-format) | Blog post; DWG not exposed as a plain download link (Wix). JA3297 already has equivalent `A320 PANELES.dwg`. |
| [EasyEDA](https://www.easyeda.com) | Tooling — we already convert MF EasyEDA JSON → Gerber |
| [Aisler OSS thread](https://community.aisler.net/t/fully-open-source-airbus-a320-home-cockpit/5476) | Mentions `git.fly.building29.net/fly/A320-homecockpit` — clone failed earlier |

## Commercial (buy, don’t clone)

[HispaPanels A320 PCBs](https://hispapanels.com/) — kits for Mega; useful to see which MIP functions share one board.

## Our fab packs

Preview gallery: `pcbway-orders/_previews/` → http://127.0.0.1:8765/index.html  
3D + parts: `_previews/viewer3d.html`  
Panel sim (3D + local Falstad/CircuitJS face I/O): `_previews/sim.html?board=21-adirs`  
Circuit dumps: `_previews/circuitjs/circuits/` via `python electronics/tools/build_falstad_circuits.py`  
Order notes: `ORDER.md`  
Readiness JSON: `_previews/pcbway-ready.json` (layer count, size mm, BOM, MF/Fenix LVar samples)

## Direct comparison (next, after PCBWay)

Not “Fenix CB matrix → copper nets.” Path is:

1. Order / fab `Gerber.zip` packs (this folder).
2. Wire panels via MobiFlight using vendor `.mcc` (Fenix LVars like `I_OH_ELEC_BAT1_U` already in `MiniOverheadFenix.mcc`).
3. Compare live panel LEDs/switches to sim LVars (and later to AviationHunt / RE’d FS electrical maps) in one matrix.

Rebuild readiness: `python electronics/tools/build_pcbway_ready.py`

# A320 cockpit electronics

Print STLs: `../print/cockpit/`.  
**Read `STACK.md` first** — panel PCBs follow HispaPanels + MobiFlight, not a custom avionics MCU.

| Layer | Where | Job |
| --- | --- | --- |
| Panel PCBs | HispaPanels buy **or** MobiFlight → PCBWay | Buttons, LEDs, FCU 7-seg, EFIS, MCDU |
| Controller | Arduino Mega + Mobiflight shields | USB ↔ MSFS / Fenix / FBW |
| Law oracle (optional) | Host `firmware/src/lawOracle.ts` | ADIRU failure → law cues for training |
| Parked | `kicad/` STM32 hub Rev A | Only if you later need a sidestick/law brick |

Hobbyist sim only — not aircraft hardware.

## PCBWay order package (when Gerbers exist)

Upload one zip containing:

1. Gerbers (RS-274X) — copper, mask, silk, paste, edge cuts
2. Excellon drill + tool list
3. `pcbway/bom.csv` — MPN, qty, refdes, footprint
4. `pcbway/cpl.csv` — pick-and-place centroids (for SMT)
5. This README / `BOARD.md` as the fab note

Suggested first fab options:

- Size: **100 × 100 mm**
- Layers: **4**
- Thickness: **1.6 mm**
- Copper: **1 oz** outer / 0.5 oz inner
- Finish: **ENIG** (better for fine-pitch MCU)
- Colour: black solder mask, white silk
- Qty: **5** boards (prototype)
- Assembly: SMT top only, turnkey for Digi-Key / Mouser / LCSC common parts; leave HI-8596 and through-hole headers as DNP or hand-solder

## Repo layout

```
electronics/
  README.md              ← you are here
  BOARD.md               ← mechanical + connector map
  LAW_ORACLE.md          ← ADIRU → law state machine (sim)
  pcbway/
    bom.csv              ← assembly BOM
    cpl.csv              ← centroid template (fill after layout)
    fab-notes.txt        ← paste into PCBWay order comments
  firmware/              ← law tick + USB (next)
  kicad/                 ← KiCad project (next layout pass)
```

## Status

- [x] Architecture + PCBWay fab notes
- [x] Connector / net map for printed panels
- [x] BOM draft for Rev A
- [ ] KiCad schematic + PCB layout
- [ ] Gerber export + PCBWay quote
- [ ] Firmware `tick()` law oracle on MCU

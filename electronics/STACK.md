# Stack decision — HispaPanels + MobiFlight + PCBWay

Your printed Fenix STLs are the **shell**. Panel electronics should ride the **hobbyist A320 ecosystem**, not a custom avionics rack.

## References

| Source | Role |
| --- | --- |
| [HispaPanels A320 PCBs](https://hispapanels.com/tienda/en/107-a320-printed-circuit-boards) | Ready-made FCU / EFIS / MCDU / front-section PCBs (€10–25). SimIO or Arduino Mega. |
| [HispaPanels Mobiflight shields](https://hispapanels.com/tienda/en/105-mobiflight) | Arduino Mega shields + ribbon to their panel PCBs (A320 FCU / EFIS dedicated). |
| [MobiFlight/mobiflight-panels](https://github.com/MobiFlight/mobiflight-panels) | Open hardware (GPL-3.0). EasyEDA JSON → Gerbers → **PCBWay**. A320 under `aircraft/airbus-a32x/`. |
| This repo `print/cockpit/` | 1:1 mm STLs for physical cockpit. Mount PCBs behind panels on 10 mm spacers (MobiFlight convention). |

## How the pieces fit

```
Printed Fenix panels (your printer)
        │  10mm nylon spacers
        ▼
Panel PCB  ◄── buy HispaPanels  OR  fab MobiFlight EasyEDA on PCBWay
        │  ribbon
        ▼
Arduino Mega (+ Hispa Mobiflight shield if using their PCBs)
        │  USB
        ▼
MobiFlight Connector  →  MSFS / Fenix / FBW events
        │
        ▼
(optional) law-oracle host process  —  electronics/firmware/src/lawOracle.ts
           for training inject / ECAM cues; not required for basic panel I/O
```

## Buy vs PCBWay (practical)

**Buy from HispaPanels first (fastest path to lights/buttons):**

1. [A320 PCB for FCU](https://hispapanels.com/tienda/en/827-556-a320-pcb-for-fcu.html) + [Mobiflight FCU shield](https://hispapanels.com/tienda/en/851-mobiflight-pcb-for-a320-fcu.html)
2. [EFIS pilot](https://hispapanels.com/tienda/en/813-525-a320-pcb-for-efis-pilot.html) + [EFIS FO](https://hispapanels.com/tienda/en/814-527-a320-pcb-for-efis-copilot.html) + [Mobiflight EFIS shield](https://hispapanels.com/tienda/en/850-mobiflight-pcb-for-a320-efis.html)
3. [MCDU v1 PCB](https://hispapanels.com/tienda/en/808-523-a320-pcb-for-mcdu-v-1.html) and/or [front-section rest](https://hispapanels.com/tienda/en/853-a320-pcb-for-the-rest-of-front-section.html) (Arduino Mega direct)
4. Arduino Mega 2560 × N, ribbon cables, Korry LEDs/switches as per their BOM

**PCBWay when you want open designs / spares / mods:**

Ready-made Gerber zips already in the MobiFlight repo (upload as-is):

| Board | Path |
| --- | --- |
| MCDU SMD | `aircraft/airbus-a32x/pedestal/mcdu/Gerber_PCB_A320 MCDU SMD.zip` (+ BOM + pick-and-place CSVs) |
| Overhead lights | `aircraft/airbus-a32x/overhead/lights/Gerber_A320 OVHD Lights.zip` |
| Engine start | `aircraft/airbus-a32x/pedestal/engine-start/Gerber_PCB_Eng Start.zip` |

EasyEDA → Gerber for the rest (FCU / EFIS already proven upstream):

1. Clone [mobiflight-panels](https://github.com/MobiFlight/mobiflight-panels)
2. Open `PCB_*.json` in [EasyEDA](https://easyeda.com) → Document → Open → EasyEDA Source
3. Fabrication → Gerber → zip → PCBWay (2-layer OK)
4. First fab: **FCU** (`glareshield/fcu/PCB_A320 FCU.json`) — marked **v1.0.3 fabricated and tested**
5. Then EFIS L/R, warning, autobrake, chrono, ECAM, ATC-TCAS, mini-overhead

MobiFlight configs for **Fenix** exist (e.g. `Overhead Lights Fenix.mcc`, `MiniOverheadFenix.mcc`).

Do **not** clone HispaPanels artwork for PCBWay — commercial. Only fab MobiFlight (GPL-3.0) or your own layouts.

## What we deprioritized

The earlier custom `A320-SIM-FCS-HUB-REVA` (STM32 / ARINC footprints) is **parked**. It does not replace Hispa/MobiFlight panel boards. Revisit only if you need a dedicated law-oracle / sidestick ADC brick after panels work.

## PCBWay pack (generated)

See **`pcbway-orders/ORDER.md`**. Fifteen board folders are staged under `pcbway-orders/` (upstream Gerbers for MCDU / OVHD lights / engine start; EasyEDA→Gerber for FCU, EFIS, warning, MIP, ECAM, ATC, mini-overhead).

Regenerate converted boards:

```text
python electronics/tools/easyeda_to_gerber.py
```

## Next actions

1. Preview each `pcbway-orders/*/Gerber.zip` in PCBWay Online Gerber Viewer.
2. Order the recommended first cart from `ORDER.md`.
3. Align printed Fenix faces to MobiFlight hole patterns before final print.
4. Keep `LAW_ORACLE.md` + `firmware/src/lawOracle.ts` as the PC-side failure-training layer.

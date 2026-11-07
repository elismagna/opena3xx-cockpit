# Zero-cost electronics path (no PCBWay / HispaPanels)

Skip fabricated PCBs. Your printed faces + Arduino + MobiFlight still work.

## Stack

```
Printed Fenix / MobiFlight faceplates
        │
        ▼
Buttons / encoders / LEDs (hand-wired or protoboard)
        │ Dupont / ribbon
        ▼
Arduino Mega 2560 (or several)
        │ USB
        ▼
MobiFlight Connector → Fenix / MSFS
```

Gerbers in `pcbway-orders/` stay archived for later. You do **not** need them to fly.

## What you need that might already be free / on-hand

- Arduino Mega 2560 (or clone) — if you already own one, cost = €0
- Dupont wires, resistors (220–470 Ω for LEDs), momentary buttons, EC11 encoders
- Protoboard / stripboard scraps instead of custom PCBs
- 10 mm nylon standoffs (or print standoffs)

## Build order (no fab queue)

1. **One Mega + one panel** — e.g. FCU buttons only, or mini-overhead  
2. Load MobiFlight configs from vendor tree:  
   `vendor/mobiflight-panels/aircraft/airbus-a32x/**/*.mcc` (Fenix where named)  
3. Map pins in MobiFlight UI to your wired pins  
4. Grow panel-by-panel; never blocked on PCB shipping

## Using the open designs without ordering boards

| Asset | Free use |
| --- | --- |
| `*.svg` laser faces | Cut/engrave yourself, or skip and use your Fenix STLs |
| `*.stl` knobs / push-pull | Print on your printer |
| `*.mcc` / `*.mfmc` | Drop into MobiFlight — pin map is the valuable part |
| `Gerber.zip` / EasyEDA JSON | Ignore until you want boards someday |

## If you later want boards without “paying PCBWay”

- Home toner-transfer / CNC mill using the Gerbers (your time, not a fab invoice)  
- Friend/school fab lab  
- Coupons still count as paying — this path assumes **€0 fab**

## Parked paid stuff

- HispaPanels store  
- PCBWay uploads  
- Custom STM32 hub  

Law oracle on PC (`firmware/src/lawOracle.ts`) remains free software.

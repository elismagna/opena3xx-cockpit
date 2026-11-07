# Remaining panels — still need custom PCBs for PCBWay

Plan: design Gerbers → preview in `_previews/` → one PCBWay cart when the set looks good.  
Scope for now: **PCBs only** (shells / install later).

Existing packs `pcbway-orders/01`–`14` are already staged. These have face SVG only (no upstream EasyEDA board):

| # | Panel | Notes |
| --- | --- | --- |
| 16 | Overhead ADIRS | Buttons + ADIRS rotaries |
| 17 | Overhead aircond | Buttons + packs |
| 18 | Overhead audio | Dense pushbuttons |
| 19 | Overhead cargo-heat | |
| 20 | Overhead elec | Dense |
| 21 | Overhead emer-elec | |
| 22 | Overhead evac | |
| 23 | Overhead fire | Guarded + AGENT |
| 24 | Overhead flt-ctl | |
| 25 | Overhead flt-ctl-fo | |
| 26 | Overhead gndservices | |
| 27 | Overhead hyd-fuel | |
| 28 | Overhead radio | |
| 29 | MIP terr-on-nd | Small |
| 30 | Pedestal flood light | Rotary / switch |

**Not PCB-first (mech / servo — defer):** MIP gear lever (microswitches on lever), MIP brake-pressure (servos via Autobrake), pedestal parking-brake (handle transducer).

## Pipeline

1. Place footprints from face SVG hole centers (match existing MobiFlight button footprints where possible).
2. Route to IDC / pin header for Mega + MobiFlight. ✅ `tools/maze_router.py` — all 15 route with 0 unrouted nets, DRC clean (`tools/check_rev0_drc.py`).
3. Emit `Gerber.zip` + top-copper SVG preview under `pcbway-orders/`.
4. User reviews gallery → then order whole cart.

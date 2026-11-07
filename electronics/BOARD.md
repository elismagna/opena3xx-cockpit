# Rev A board map — A320 Sim FCS Hub

## Outline

- Board: **100.00 × 100.00 mm**, rectangle, 4 mounting holes **M3** at corners inset **3.5 mm** (centers at 3.5 / 96.5).
- Keep-out: 2 mm from board edge for PCBWay routing.
- Intended mount: behind pedestal / under glareshield shelf of the printed cockpit; standoffs into printed bosses (add bosses in a follow-up STL if missing).

## Stackup (PCBWay 4-layer default)

| Layer | Use |
| --- | --- |
| F.Cu | Signals + USB diff pair |
| In1.Cu | GND plane (solid) |
| In2.Cu | 3V3 power pour + quiet analog |
| B.Cu | Signals + LED matrix returns |

## Block diagram

```
 USB-C ──► ESD + CC ──► STM32H743VIT6 ──► USB CDC to host sim
                              │
              ┌───────────────┼───────────────┐
              ▼               ▼               ▼
         ADC: 2× stick   Matrix scan     Law status LEDs
         pitch/roll      J_PANEL_A/B     NORMAL/ALTN/DIRECT
         + priority      (overhead /     + fault LED
                         pedestal)
              │
              ▼
         Footprints only: HI-8596 ×2 (ARINC 429 TX/RX) — DNP Rev A
```

## Connectors (facing panel harnesses)

| Ref | Type | Function | Notes |
| --- | --- | --- | --- |
| J1 | USB-C 16P | Host data + 5 V in | Primary power for bench |
| J2 | Barrel 5.5/2.1 | 9–12 V panel lamp bus | Optional; feeds LED backlight rail via buck |
| J3 | 2×20 2.54 IDC | `PANEL_A` — overhead matrix | Rows/cols + 5 V LED anode bus |
| J4 | 2×20 2.54 IDC | `PANEL_B` — pedestal / glareshield | Same pinout as J3 |
| J5 | Molex MicroFit 3.0 8P | Captain sidestick | X, Y, 3V3ref, GND, PRIORITY, AP_DISC, spare×2 |
| J6 | Molex MicroFit 3.0 8P | FO sidestick | Mirror of J5 |
| J7 | JST GH 1.25 6P | Debug SWD | 3V3, GND, SWDIO, SWCLK, NRST, UART_TX |
| J8 | JST GH 1.25 4P | Spare UART / GPS time | Future |

### J3 / J4 IDC pinout (same both sides)

| Pin | Net | Pin | Net |
| --- | --- | --- | --- |
| 1 | ROW0 | 2 | ROW1 |
| 3 | ROW2 | 4 | ROW3 |
| 5 | ROW4 | 6 | ROW5 |
| 7 | ROW6 | 8 | ROW7 |
| 9 | COL0 | 10 | COL1 |
| 11 | COL2 | 12 | COL3 |
| 13 | COL4 | 14 | COL5 |
| 15 | COL6 | 16 | COL7 |
| 17 | LED_SDA (I2C1) | 18 | LED_SCL |
| 19 | +5V_LED | 20 | GND |
| 21–40 | GND / +5V_LED repeats | | Strain + return |

Matrix = up to 8×8 = 64 keys per connector. LED drivers sit on panel PCBs or IS31FL3731 breakouts hung on I2C — Rev A hub only provides the bus.

## Sidestick analog

- 0–3.3 V ratiometric, RC filter 100 Ω + 10 nF at MCU pin.
- Dual-sample average in firmware; stick-priority discrete active-low with 10 kΩ pull-up.

## Law status (board-local)

| LED | Colour | Meaning |
| --- | --- | --- |
| D_NORM | Green | Normal Law |
| D_ALTN | Amber | Alternate Law |
| D_DIR | Red | Direct Law |
| D_FAULT | White | Sensor disagree / oracle fault |

## Power tree

```
USB 5V ──► AP2112K-3.3 → 3V3_MCU / 3V3_ADC
Barrel 9–12V ──► MP1584 or AMS1117-5 → 5V_LED (panel bus)
```

USB and barrel diode-OR on 5V_SYS so either supply works.

## What Rev A deliberately skips

- Full Zynq / FPGA ELAC sandbox (cost + bring-up risk)
- Populated ARINC 429 (footprints only)
- Galvanic triple PMIC aircraft power (sim bench: USB + barrel)

Those stay on the REA roadmap after the printed cockpit + this hub talk to the sim flawlessly.

# Law oracle (sim) — ADIRU path

Runs on the hub MCU (and mirrored on host for HIL compare).
Tags: **[OBS]** public pilot docs · **[INF]** sim consolidation · **[UNK]** tuneable.

## States

`NORMAL` · `ALTN_RED` (reduced protection) · `ALTN_NOPROT` · `DIRECT` · `ABNORMAL`

## Inputs (each tick)

```ts
type AdiruHalf = {
  powered: boolean;
  selfFail: boolean;   // peripheral declared itself bad
  ageMs: number;       // time since last good frame
  ssmOk: boolean;
};

type TickIn = {
  adr: [AdiruHalf, AdiruHalf, AdiruHalf];
  ir:  [AdiruHalf, AdiruHalf, AdiruHalf];
  casKt: [number, number, number];     // only used if adr valid
  mach: [number, number, number];
  gearDown: boolean;
  apEngaged: boolean;
  bankDeg: number;
  pitchDeg: number;
  aoaDeg: number;
  iasKt: number;                       // voted IAS for abnormal envelope
  dtMs: number;
};
```

## Predicates

```text
fresh(x)     = x.powered && !x.selfFail && x.ssmOk && x.ageMs < T_fresh
adrCount     = count fresh(adr[i])
irCount      = count fresh(ir[i])

disagreeCas  = any pair of fresh ADRs with |CAS_a−CAS_b| > D_cas for N_persist ticks
rejectAllAdr = adrCount==0 OR (disagreeCas && !any selfFail on the disagreeing pair)  [INF]

[UNK] defaults for Rev A firmware:
  T_fresh   = 100 ms
  D_cas     = 20 kt
  N_persist = 5 ticks @ 50 Hz
```

## Transitions (priority order)

1. If envelope trip → `ABNORMAL`  
   Bank>125° OR pitch>50° OR pitch<−30° OR AOA absurd OR IAS absurd **[OBS]**
2. Else if `irCount == 0` → `DIRECT` **[OBS]**
3. Else if `adrCount == 0` → `ALTN_NOPROT` **[OBS]**
4. Else if `adrCount <= 1` OR `irCount <= 1` OR `rejectAllAdr` → `ALTN_RED` **[OBS]**  
   (single ADR/IR keep NORMAL — only dual+ degrade)
5. Else if current in `{ALTN_*}` AND `gearDown && !apEngaged` → `DIRECT` **[OBS]**
6. Else if was `ABNORMAL` and now inside envelope → `ALTN_RED` (stay degraded) **[OBS]**
7. Else if faults cleared → `NORMAL` **[OBS]** (recovery not always possible in real AC; sim allows when counts restore)

## Outputs

```ts
type TickOut = {
  law: 'NORMAL' | 'ALTN_RED' | 'ALTN_NOPROT' | 'DIRECT' | 'ABNORMAL';
  protections: {
    loadFactor: boolean;
    bankAngle: boolean;
    highAoA: boolean;
    highSpeed: boolean;
    pitchAttitude: boolean;
    speedStability: boolean;
    autoTrim: boolean;
  };
  ecam: string[];          // e.g. "F/CTL ALTN LAW (PROT LOST)"
  pfd: { amberX: boolean; useManPitchTrim: boolean };
  leds: { normal: boolean; altn: boolean; direct: boolean; fault: boolean };
};
```

### Protection matrix

| Law | loadFactor | bank | hiAoA | hiSpd | pitchAtt | speedStab | autoTrim |
| --- | --- | --- | --- | --- | --- | --- | --- |
| NORMAL | on | on | on | on | on | n/a | on |
| ALTN_RED | on | off | off | off | off | on | on |
| ALTN_NOPROT | on | off | off | off | off | off | on |
| DIRECT | off | off | off | off | off | off | off |
| ABNORMAL | off* | off | off | off | off | off | off |

\*Abnormal is recovery authority; after envelope restore → ALTN_RED.

## HIL inject API (USB CDC text)

```
INJECT ADR 1 FAIL SELF
INJECT ADR 2 FAIL DISAGREE
INJECT IR 1,2,3 FAIL
INJECT GEAR DOWN
INJECT CLEAR
LAW?
```

Firmware answers `LAW ALTN_RED` etc. Host tests must match `LAW_ORACLE.md` exactly.

/**
 * A320 hobbyist-sim flight-law oracle (ADIRU path).
 * Pure tick() — host golden model; port to C for the hub MCU.
 */

export type AdiruHalf = {
  powered: boolean;
  selfFail: boolean;
  ageMs: number;
  ssmOk: boolean;
};

export type Law =
  | "NORMAL"
  | "ALTN_RED"
  | "ALTN_NOPROT"
  | "DIRECT"
  | "ABNORMAL";

export type TickIn = {
  adr: [AdiruHalf, AdiruHalf, AdiruHalf];
  ir: [AdiruHalf, AdiruHalf, AdiruHalf];
  casKt: [number, number, number];
  gearDown: boolean;
  apEngaged: boolean;
  bankDeg: number;
  pitchDeg: number;
  aoaDeg: number;
  iasKt: number;
};

export type TickOut = {
  law: Law;
  protections: {
    loadFactor: boolean;
    bankAngle: boolean;
    highAoA: boolean;
    highSpeed: boolean;
    pitchAttitude: boolean;
    speedStability: boolean;
    autoTrim: boolean;
  };
  ecam: string[];
  pfd: { amberX: boolean; useManPitchTrim: boolean };
  leds: { normal: boolean; altn: boolean; direct: boolean; fault: boolean };
};

/** Tunables — [UNK] until matched against a chosen sim reference. */
export const DEFAULTS = {
  T_freshMs: 100,
  D_casKt: 20,
  disagreePersistTicks: 5,
  abnormal: {
    bankDeg: 125,
    pitchUpDeg: 50,
    pitchDownDeg: -30,
    aoaHiDeg: 35,
    aoaLoDeg: -10,
    iasLoKt: 75,
    iasHiKt: 440,
  },
};

export type OracleState = { law: Law; disagreePersist: number };

export function createState(): OracleState {
  return { law: "NORMAL", disagreePersist: 0 };
}

function fresh(x: AdiruHalf, tFresh: number): boolean {
  return x.powered && !x.selfFail && x.ssmOk && x.ageMs < tFresh;
}

function countFresh(xs: AdiruHalf[], tFresh: number): number {
  let n = 0;
  for (const x of xs) if (fresh(x, tFresh)) n++;
  return n;
}

function casDisagree(inp: TickIn, tFresh: number, dCas: number): boolean {
  const live: number[] = [];
  for (let i = 0; i < 3; i++) if (fresh(inp.adr[i], tFresh)) live.push(i);
  for (let a = 0; a < live.length; a++) {
    for (let b = a + 1; b < live.length; b++) {
      if (Math.abs(inp.casKt[live[a]] - inp.casKt[live[b]]) > dCas) return true;
    }
  }
  return false;
}

function envelopeTrip(inp: TickIn): boolean {
  const a = DEFAULTS.abnormal;
  return (
    Math.abs(inp.bankDeg) > a.bankDeg ||
    inp.pitchDeg > a.pitchUpDeg ||
    inp.pitchDeg < a.pitchDownDeg ||
    inp.aoaDeg > a.aoaHiDeg ||
    inp.aoaDeg < a.aoaLoDeg ||
    inp.iasKt < a.iasLoKt ||
    inp.iasKt > a.iasHiKt
  );
}

function protectionsFor(law: Law): TickOut["protections"] {
  switch (law) {
    case "NORMAL":
      return {
        loadFactor: true,
        bankAngle: true,
        highAoA: true,
        highSpeed: true,
        pitchAttitude: true,
        speedStability: false,
        autoTrim: true,
      };
    case "ALTN_RED":
      return {
        loadFactor: true,
        bankAngle: false,
        highAoA: false,
        highSpeed: false,
        pitchAttitude: false,
        speedStability: true,
        autoTrim: true,
      };
    case "ALTN_NOPROT":
      return {
        loadFactor: true,
        bankAngle: false,
        highAoA: false,
        highSpeed: false,
        pitchAttitude: false,
        speedStability: false,
        autoTrim: true,
      };
    case "DIRECT":
    case "ABNORMAL":
      return {
        loadFactor: false,
        bankAngle: false,
        highAoA: false,
        highSpeed: false,
        pitchAttitude: false,
        speedStability: false,
        autoTrim: false,
      };
  }
}

function nextLaw(
  prev: Law,
  adrCount: number,
  irCount: number,
  hardDisagree: boolean,
  inp: TickIn,
): Law {
  if (envelopeTrip(inp)) return "ABNORMAL";
  if (irCount === 0) return "DIRECT";
  if (adrCount === 0) return "ALTN_NOPROT";

  const sensorDegrade = adrCount < 2 || irCount < 2 || hardDisagree;

  if (sensorDegrade) {
    if (
      (prev === "ALTN_RED" || prev === "ALTN_NOPROT") &&
      inp.gearDown &&
      !inp.apEngaged
    ) {
      return "DIRECT";
    }
    return "ALTN_RED";
  }

  if (
    (prev === "ALTN_RED" || prev === "ALTN_NOPROT") &&
    inp.gearDown &&
    !inp.apEngaged
  ) {
    return "DIRECT";
  }

  if (prev === "ABNORMAL") return "ALTN_RED";

  return "NORMAL";
}

export function tick(
  state: OracleState,
  inp: TickIn,
  cfg = DEFAULTS,
): { state: OracleState; out: TickOut } {
  const adrCount = countFresh(inp.adr, cfg.T_freshMs);
  const irCount = countFresh(inp.ir, cfg.T_freshMs);
  const disagree = casDisagree(inp, cfg.T_freshMs, cfg.D_casKt);
  const disagreePersist = disagree ? state.disagreePersist + 1 : 0;
  const hardDisagree = disagreePersist >= cfg.disagreePersistTicks;

  const law = nextLaw(state.law, adrCount, irCount, hardDisagree, inp);

  const ecam: string[] = [];
  if (law === "ALTN_RED" || law === "ALTN_NOPROT") {
    ecam.push("F/CTL ALTN LAW (PROT LOST)");
  }
  if (law === "DIRECT") ecam.push("F/CTL DIRECT LAW");
  if (hardDisagree) ecam.push("NAV ADR DISAGREE");

  const out: TickOut = {
    law,
    protections: protectionsFor(law),
    ecam,
    pfd: {
      amberX: law !== "NORMAL",
      useManPitchTrim: law === "DIRECT",
    },
    leds: {
      normal: law === "NORMAL",
      altn: law === "ALTN_RED" || law === "ALTN_NOPROT" || law === "ABNORMAL",
      direct: law === "DIRECT",
      fault: hardDisagree || adrCount < 3 || irCount < 3,
    },
  };

  return { state: { law, disagreePersist }, out };
}

/** Healthy ADIRU half for tests / inject baseline. */
export function okHalf(): AdiruHalf {
  return { powered: true, selfFail: false, ageMs: 0, ssmOk: true };
}

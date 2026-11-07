import { createState, okHalf, tick, type TickIn } from "./lawOracle";

function base(): TickIn {
  return {
    adr: [okHalf(), okHalf(), okHalf()],
    ir: [okHalf(), okHalf(), okHalf()],
    casKt: [250, 250, 250],
    gearDown: false,
    apEngaged: true,
    bankDeg: 0,
    pitchDeg: 2,
    aoaDeg: 2,
    iasKt: 250,
  };
}

function assert(cond: boolean, msg: string) {
  if (!cond) throw new Error(msg);
}

let s = createState();
let r = tick(s, base());
assert(r.out.law === "NORMAL", "healthy → NORMAL");
s = r.state;

const dualAdr = base();
dualAdr.adr[0] = { ...okHalf(), selfFail: true };
dualAdr.adr[1] = { ...okHalf(), selfFail: true };
r = tick(s, dualAdr);
assert(r.out.law === "ALTN_RED", "dual ADR self-fail → ALTN_RED");
s = r.state;

const gear = { ...dualAdr, gearDown: true, apEngaged: false };
r = tick(s, gear);
assert(r.out.law === "DIRECT", "ALTN + gear + AP off → DIRECT");
assert(r.out.pfd.useManPitchTrim, "man pitch trim cue");

const tripleIr = base();
tripleIr.ir = [
  { ...okHalf(), selfFail: true },
  { ...okHalf(), selfFail: true },
  { ...okHalf(), selfFail: true },
];
r = tick(createState(), tripleIr);
assert(r.out.law === "DIRECT", "triple IR → DIRECT");

console.log("lawOracle tests OK");

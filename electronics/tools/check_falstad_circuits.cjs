#!/usr/bin/env node
/*
 * Load every circuits/<board>.txt into the vendored CircuitJS (headless
 * Chromium) and check that: there are no "unconnected" / undump warnings,
 * all LEDs are dark with every switch open, and pressing switch k lights
 * LED k only (even switches pressed, then odd).
 *
 *   cd electronics/pcbway-orders/_previews && python3 -m http.server 8765 &
 *   node electronics/tools/check_falstad_circuits.cjs
 * Needs: playwright (Chromium).
 */
const { chromium } = require("playwright");
const fs = require("fs");
const path = require("path");

const BASE = process.env.SIM_BASE || "http://127.0.0.1:8765/";
const dir = path.resolve(__dirname, "../pcbway-orders/_previews/circuitjs");
const index = JSON.parse(fs.readFileSync(path.join(dir, "circuits-index.json"), "utf8"));

function press(text, pick) {
  let k = 0;
  return text.split("\n").map((l) => {
    if (!l.startsWith("s ")) return l;
    const q = l.split(" ");
    q[6] = pick(k++) ? "0" : "1";
    return q.join(" ");
  }).join("\n");
}

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage();
  let warnings = [];
  page.on("console", (m) => {
    const t = m.text();
    if (/unconnected|undump|NoSuchElement|failed to create/i.test(t)) warnings.push(t);
  });
  await page.goto(BASE + "circuitjs/embed.html?cct=" + encodeURIComponent("$ 1 0.000005 10 50 5 50\n"));
  await page.waitForFunction(() => window.CircuitJS1 && window.CircuitJS1.importCircuit, null, { timeout: 60000 });
  warnings = []; // ignore CircuitJS's own startup noise
  let bad = 0;
  for (const b of index.boards) {
    const text = fs.readFileSync(path.join(dir, b.file), "utf8");
    const n = (text.match(/^s /gm) || []).length;
    const errs = [];
    if (n !== b.controls.length) errs.push(`${n} switches for ${b.controls.length} controls`);
    warnings = [];
    for (const [tag, pick] of [["open", () => false], ["even", (k) => k % 2 === 0], ["odd", (k) => k % 2 === 1]]) {
      const leds = await page.evaluate(async (t) => {
        const a = window.CircuitJS1;
        a.importCircuit(t, false);
        a.setSimRunning(true);
        await new Promise((r) => setTimeout(r, 1500));
        const els = a.getElements();
        const out = [];
        for (let i = 0; i < els.length; i++) if (els[i].getType() === "LEDElm") out.push(els[i].getCurrent() * 1000);
        return out;
      }, press(text, pick));
      if (leds.length !== n) errs.push(`${leds.length} LEDs for ${n} switches`);
      leds.forEach((mA, k) => {
        const want = pick(k);
        if (want && !(mA > 5 && mA < 20)) errs.push(`${tag}: LED ${k + 1} ${mA.toFixed(2)} mA, expected lit`);
        if (!want && Math.abs(mA) > 0.05) errs.push(`${tag}: LED ${k + 1} ${mA.toFixed(2)} mA, expected dark`);
      });
    }
    errs.push(...[...new Set(warnings)].map((w) => "CircuitJS: " + w.slice(0, 100)));
    console.log(`${errs.length ? "FAIL" : "OK  "} ${b.id.padEnd(20)} ${n} controls`);
    errs.slice(0, 5).forEach((e) => console.log("      " + e));
    bad += errs.length ? 1 : 0;
  }
  console.log(bad ? `${bad} circuit(s) failing` : "all circuits OK");
  await browser.close();
  process.exit(bad ? 1 : 0);
})();

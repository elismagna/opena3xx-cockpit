import fs from "fs";
import path from "path";
import { createWriteStream } from "fs";
import { pipeline } from "stream/promises";
import { createGunzip } from "zlib";
import { Readable } from "stream";
import gerberToSvg from "gerber-to-svg";
import AdmZip from "adm-zip";

const orders = path.resolve("../../pcbway-orders");
const outDir = path.join(orders, "_previews");
fs.mkdirSync(outDir, { recursive: true });

const folders = fs
  .readdirSync(orders, { withFileTypes: true })
  .filter((d) => d.isDirectory() && d.name !== "_previews")
  .map((d) => d.name)
  .sort();

function pickGerber(entries) {
  const names = entries.map((e) => e.entryName);
  const prefer = ["GTL.GTL", "GTL", ".gtl", "TopLayer", "Copper_Signal_Top"];
  for (const p of prefer) {
    const hit = names.find((n) => n.toLowerCase().includes(p.toLowerCase()) && !n.includes("/"));
    if (hit) return hit;
  }
  // upstream zips: any .gtl
  const gtl = names.find((n) => n.toLowerCase().endsWith(".gtl"));
  return gtl || names.find((n) => /\.(gtl|gbr|gbl)$/i.test(n));
}

for (const folder of folders) {
  const zipPath = path.join(orders, folder, "Gerber.zip");
  if (!fs.existsSync(zipPath)) {
    console.log("skip", folder);
    continue;
  }
  try {
    const zip = new AdmZip(zipPath);
    const entries = zip.getEntries();
    const name = pickGerber(entries);
    if (!name) {
      console.log("no copper layer", folder, entries.map((e) => e.entryName).slice(0, 8));
      continue;
    }
    const text = zip.readAsText(name);
    const svg = await new Promise((resolve, reject) => {
      gerberToSvg(text, { attributes: { width: "100%", height: "auto" } }, (err, result) => {
        if (err) reject(err);
        else resolve(result);
      });
    });
    const out = path.join(outDir, `${folder}.svg`);
    fs.writeFileSync(out, svg);
    console.log("ok", folder, "→", path.basename(out), `(from ${name})`);
  } catch (e) {
    console.log("fail", folder, e.message);
  }
}

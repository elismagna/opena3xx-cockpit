/**
 * Colored top/bottom PCB renders (tracespace stackup) for every Gerber.zip.
 * Output: pcbway-orders/_previews/<id>-top.svg, <id>-bottom.svg, manifest.json
 */
import fs from "fs";
import os from "os";
import path from "path";
import { fileURLToPath } from "url";
import AdmZip from "adm-zip";
import { read, plot, renderLayers, renderBoard, stringifySvg } from "@tracespace/core";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const orders = path.resolve(__dirname, "../../pcbway-orders");
const outDir = path.join(orders, "_previews");
fs.mkdirSync(outDir, { recursive: true });

/** Map zip entry names → PCBWay-style names (tracespace identifyLayers-safe). */
function canonicalName(entryName) {
  const base = path.basename(entryName).replace(/\\/g, "/");
  const lower = base.toLowerCase();
  // Prefer long PCBWay-style names first (upstream MCDU zips).
  if (lower.includes("topsilkscreen") || lower === "gto.gto" || /^gto\./.test(lower))
    return "Gerber_TopSilkscreenLayer.GTO";
  if (lower.includes("bottomsilkscreen") || lower === "gbo.gbo" || /^gbo\./.test(lower))
    return "Gerber_BottomSilkscreenLayer.GBO";
  if (lower.includes("topsoldermask") || lower === "gts.gts" || /^gts\./.test(lower))
    return "Gerber_TopSolderMaskLayer.GTS";
  if (lower.includes("bottomsoldermask") || lower === "gbs.gbs" || /^gbs\./.test(lower))
    return "Gerber_BottomSolderMaskLayer.GBS";
  if (lower.includes("toppastemask") || lower === "gtp.gtp" || /^gtp\./.test(lower))
    return "Gerber_TopPasteMaskLayer.GTP";
  if (lower.includes("bottompastemask") || lower === "gbp.gbp" || /^gbp\./.test(lower))
    return "Gerber_BottomPasteMaskLayer.GBP";
  if (lower.includes("toplayer") || lower === "gtl.gtl" || /^gtl\./.test(lower))
    return "Gerber_TopLayer.GTL";
  if (lower.includes("bottomlayer") || lower === "gbl.gbl" || /^gbl\./.test(lower))
    return "Gerber_BottomLayer.GBL";
  if (
    lower.includes("boardoutline") ||
    lower === "gko.gko" ||
    /^gko\./.test(lower) ||
    lower.endsWith(".gm1")
  )
    return "Gerber_BoardOutlineLayer.GKO";
  if (lower.includes("innerlayer1") || /\.g1$/.test(lower)) return "Gerber_InnerLayer1.G1";
  if (lower.includes("innerlayer2") || /\.g2$/.test(lower)) return "Gerber_InnerLayer2.G2";
  if (
    lower.includes("npth") ||
    (lower.includes("drill") && lower.includes("npth"))
  )
    return "Drill_NPTH_Through.DRL";
  if (
    lower.includes("pth") ||
    lower.includes("drill") ||
    lower.endsWith(".drl") ||
    lower.endsWith(".xln") ||
    lower === "pth.txt" ||
    lower === "npth.txt"
  ) {
    if (lower.includes("npth")) return "Drill_NPTH_Through.DRL";
    return "Drill_PTH_Through.DRL";
  }
  return null; // skip how-to / size notes
}

/** Give img tags a real intrinsic size + opaque backdrop (tracespace omits width/height). */
function prepareSvg(svg) {
  const m = svg.match(/viewBox="([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)"/);
  if (!m) return svg;
  const [, , , w, h] = m;
  let out = svg;
  // Do not treat stroke-width= as a size attribute.
  if (!/^<svg\b[^>]*\swidth="/.test(out)) {
    out = out.replace(
      /<svg\b([^>]*)>/,
      `<svg$1 width="${w}" height="${h}" style="background:#111">`
    );
  }
  // Avoid currentColor resolving to black when embedded as <img>.
  out = out.replace(/\sfill="currentColor"/g, ' fill="#c93"');
  out = out.replace(/\sstroke="currentColor"/g, ' stroke="#c93"');
  return out;
}

function extractMapped(zipPath, dest) {
  fs.mkdirSync(dest, { recursive: true });
  const zip = new AdmZip(zipPath);
  const written = [];
  for (const e of zip.getEntries()) {
    if (e.isDirectory) continue;
    const canon = canonicalName(e.entryName);
    if (!canon) continue;
    const out = path.join(dest, canon);
    // allow multiple drills — uniquify
    let final = out;
    let n = 2;
    while (fs.existsSync(final)) {
      const ext = path.extname(canon);
      const stem = path.basename(canon, ext);
      final = path.join(dest, `${stem}_${n}${ext}`);
      n++;
    }
    fs.writeFileSync(final, e.getData());
    written.push(final);
  }
  return written;
}

const folders = fs
  .readdirSync(orders, { withFileTypes: true })
  .filter((d) => d.isDirectory() && d.name !== "_previews")
  .map((d) => d.name)
  .sort();

const manifest = [];
const tmpRoot = fs.mkdtempSync(path.join(os.tmpdir(), "a320-gerber-"));

for (const folder of folders) {
  const zipPath = path.join(orders, folder, "Gerber.zip");
  if (!fs.existsSync(zipPath)) {
    console.log("skip", folder);
    continue;
  }
  const dest = path.join(tmpRoot, folder);
  try {
    const files = extractMapped(zipPath, dest);
    if (files.length < 2) {
      console.log("few files", folder, files.length);
      continue;
    }
    const readResult = await read(files);
    const plotResult = plot(readResult);
    const layersResult = renderLayers(plotResult);
    const board = renderBoard(layersResult);

    const topSvg = prepareSvg(stringifySvg(board.top));
    const botSvg = prepareSvg(stringifySvg(board.bottom));
    const topPath = path.join(outDir, `${folder}-top.svg`);
    const botPath = path.join(outDir, `${folder}-bottom.svg`);
    fs.writeFileSync(topPath, topSvg);
    fs.writeFileSync(botPath, botSvg);

    const layers = readResult.layers.map((l) => `${l.side}:${l.type}`).join(", ");
    const sizeMatch = topSvg.match(/viewBox="([^"]+)"/);
    manifest.push({
      id: folder,
      top: `${folder}-top.svg`,
      bottom: `${folder}-bottom.svg`,
      layers: readResult.layers.map((l) => ({
        filename: l.filename,
        side: l.side,
        type: l.type,
      })),
      viewBox: sizeMatch ? sizeMatch[1] : null,
      pcbwayZip: `../${folder}/Gerber.zip`,
    });
    console.log("ok", folder, "layers:", layers);
  } catch (err) {
    console.log("fail", folder, err.message);
  }
}

fs.writeFileSync(path.join(outDir, "manifest.json"), JSON.stringify(manifest, null, 2));
console.log("wrote", manifest.length, "boards →", outDir);

// cleanup
fs.rmSync(tmpRoot, { recursive: true, force: true });

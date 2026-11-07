import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";

const dir = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  "../../pcbway-orders/_previews"
);

let n = 0;
for (const f of fs.readdirSync(dir).filter((x) => x.endsWith(".svg"))) {
  const p = path.join(dir, f);
  let svg = fs.readFileSync(p, "utf8");
  const m = svg.match(/viewBox="([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)"/);
  if (!m) continue;
  const w = m[3];
  const h = m[4];
  // strip a prior broken patch that may have matched stroke-width
  svg = svg.replace(/\sstyle="background:#111"/g, "");
  svg = svg.replace(/^<svg\b([^>]*?)\swidth="[^"]*"\sheight="[^"]*"/, "<svg$1");
  svg = svg.replace(
    /<svg\b([^>]*)>/,
    `<svg$1 width="${w}" height="${h}" style="background:#111">`
  );
  svg = svg.replace(/\sfill="currentColor"/g, ' fill="#c93"');
  svg = svg.replace(/\sstroke="currentColor"/g, ' stroke="#c93"');
  fs.writeFileSync(p, svg);
  n++;
}
console.log("patched", n, "svgs in", dir);

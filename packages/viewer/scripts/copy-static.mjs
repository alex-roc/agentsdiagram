// Copies the built bundle where the Python package inlines it into the standalone HTML.
import { copyFileSync, mkdirSync } from "node:fs";
import { fileURLToPath } from "node:url";

const dist = fileURLToPath(new URL("../dist/", import.meta.url));
const dest = fileURLToPath(new URL("../../../src/agentsdiagram/_static/", import.meta.url));
mkdirSync(dest, { recursive: true });
for (const f of ["viewer.js", "viewer.css"]) copyFileSync(dist + f, dest + f);
console.log(`copied viewer.js, viewer.css -> ${dest}`);

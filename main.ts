import { copyFile, mkdir } from "node:fs/promises";
import { join } from "node:path";

const out = process.env.MAKEFUN_OUTPUT_DIR ?? "/output";
await mkdir(out, { recursive: true });
await copyFile(new URL("./entry.png", import.meta.url), join(out, "entry.png"));

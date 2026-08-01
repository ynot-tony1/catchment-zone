#!/usr/bin/env node
// Converts the YAML config files at the repo root (config/*.yml) into JSON
// modules under src/generated/. The web app statically imports the JSON
// output instead of reading YAML at request time, so the data is bundled
// correctly by Next.js for both local dev and serverless production builds
// (a runtime fs.readFileSync with a relative path breaks once the code is
// bundled into .next/server, because the bundle no longer lives next to the
// original source file).
//
// Runs automatically via the "prepare" lifecycle script after `pnpm
// install`, so it stays in sync with config/*.yml without needing to be
// wired into every individual build/test/typecheck command. Re-run manually
// with `pnpm --filter @schoolscope/shared sync-config` after editing a
// config file during local development.

import { readFileSync, writeFileSync, mkdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { load } from "js-yaml";

const __dirname = dirname(fileURLToPath(import.meta.url));
const repoRoot = join(__dirname, "..", "..", "..");
const configDir = join(repoRoot, "config");
const outDir = join(__dirname, "..", "src", "generated");

mkdirSync(outDir, { recursive: true });

const files = [
  ["metric-definitions.yml", "metric-definitions.json"],
  ["catchment-sources.yml", "catchment-sources.json"],
  ["statistics-sources.yml", "statistics-sources.json"],
];

for (const [source, target] of files) {
  const yamlText = readFileSync(join(configDir, source), "utf-8");
  const data = load(yamlText);
  writeFileSync(join(outDir, target), JSON.stringify(data, null, 2) + "\n", "utf-8");
  console.log(`[sync-config] ${source} -> src/generated/${target}`);
}

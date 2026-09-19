#!/usr/bin/env node
/**
 * Soft check: dollar figures outside the canonical pricing sources are drift risks.
 * Exits 0 with warnings by default; set PRICING_DRIFT_STRICT=1 to fail the build.
 *
 * Canonical sources:
 *   - frontend/src/lib/marketingCopy.js (PLANS) — frontend / marketing / crawlers
 *   - backend/plans.py — server entitlements (keep seats/prices aligned with PLANS)
 */
import { readFileSync, readdirSync, statSync } from "fs";
import { dirname, join, relative } from "path";
import { fileURLToPath } from "url";
import { loadMarketingPlans, formatPlanPrice } from "./loadMarketingPlans.mjs";

const __dirname = dirname(fileURLToPath(import.meta.url));
const repoRoot = join(__dirname, "../..");

const ALLOW_PATH_PREFIXES = [
  "frontend/src/lib/marketingCopy.js",
  "backend/plans.py",
  "frontend/public/llms.txt",
  "frontend/scripts/",
  "frontend/build/",
  "node_modules/",
  ".git/",
  ".agents/",
];

const SKIP_DIR_NAMES = new Set([
  "node_modules", ".git", "build", "coverage", ".agents", "__pycache__", ".pytest_cache",
]);

/** Stale / wrong figures we specifically want to catch. */
const FORBIDDEN = [
  { re: /\$8\s*\/\s*(mo|month|user)/i, label: "$8/mo (retired Helm Pro price)" },
  { re: /Helm Pro only/i, label: "Helm Pro only (retired single-tier claim)" },
];

function walk(dir, files = []) {
  for (const name of readdirSync(dir)) {
    if (SKIP_DIR_NAMES.has(name)) continue;
    const full = join(dir, name);
    let st;
    try {
      st = statSync(full);
    } catch {
      continue;
    }
    if (st.isDirectory()) walk(full, files);
    else if (/\.(md|js|jsx|mjs|ts|tsx|txt|json|py|html|yml|yaml)$/i.test(name)) files.push(full);
  }
  return files;
}

function isAllowed(rel) {
  return ALLOW_PATH_PREFIXES.some((p) => rel === p || rel.startsWith(p));
}

function main() {
  const { PLANS } = loadMarketingPlans();
  const expected = PLANS.map((p) => `${p.label} ${formatPlanPrice(p)}`).join(", ");
  console.log(`check-pricing-drift: canonical PLANS → ${expected}`);

  const hits = [];
  for (const file of walk(repoRoot)) {
    const rel = relative(repoRoot, file).replace(/\\/g, "/");
    if (isAllowed(rel)) continue;
    let text;
    try {
      text = readFileSync(file, "utf8");
    } catch {
      continue;
    }
    for (const { re, label } of FORBIDDEN) {
      if (re.test(text)) hits.push({ file: rel, label });
    }
  }

  if (hits.length) {
    console.warn("check-pricing-drift: possible stale pricing claims:");
    for (const h of hits) console.warn(`  - ${h.file}: ${h.label}`);
    console.warn("Update to match frontend/src/lib/marketingCopy.js PLANS, or allowlist if intentional.");
    if (process.env.PRICING_DRIFT_STRICT === "1") process.exit(1);
    process.exit(0);
  }
  console.log("check-pricing-drift: ok (no forbidden stale claims outside allowlist)");
}

main();

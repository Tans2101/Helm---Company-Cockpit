/**
 * Load PLANS (+ light metadata) from marketingCopy.js without bundling React.
 * marketingCopy.js is the canonical pricing source — keep this parser in sync
 * with the export shape there (plain array of plan objects).
 */
import { readFileSync } from "fs";
import { dirname, join } from "path";
import { fileURLToPath } from "url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const marketingCopyPath = join(__dirname, "../src/lib/marketingCopy.js");

function extractExport(src, name) {
  const re = new RegExp(`export const ${name} = ([\\s\\S]*?);\\n`);
  const m = src.match(re);
  if (!m) throw new Error(`loadMarketingPlans: export ${name} not found`);
  return Function(`"use strict"; return (${m[1]})`)();
}

export function loadMarketingPlans() {
  const src = readFileSync(marketingCopyPath, "utf8");
  const PLANS = extractExport(src, "PLANS");
  if (!Array.isArray(PLANS) || PLANS.length < 1) {
    throw new Error("loadMarketingPlans: PLANS empty or invalid");
  }
  const TAGLINE = extractExport(src, "TAGLINE");
  const CATEGORY = extractExport(src, "CATEGORY");
  const AUDIENCE = extractExport(src, "AUDIENCE");
  return { PLANS, TAGLINE, CATEGORY, AUDIENCE, marketingCopyPath };
}

export function formatPlanPrice(plan) {
  const n = Number(plan.price);
  if (!(n > 0)) return "$0";
  return `$${n}/mo`;
}

export function plansPlainLines(plans) {
  return plans.map((p) => {
    const seats = p.seats != null ? `${p.seats} seats` : "";
    const forWhom = p.for ? ` — ${p.for}` : "";
    return `- ${p.label}: ${formatPlanPrice(p)}${seats ? ` (${seats})` : ""}${forWhom}`;
  });
}

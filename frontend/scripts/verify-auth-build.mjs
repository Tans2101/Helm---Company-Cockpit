#!/usr/bin/env node
/**
 * Fail CI/build if auth fixes are missing from the production bundle.
 * Run after `yarn build` in frontend/.
 */
import { readFileSync, readdirSync } from "fs";
import { join } from "path";

const buildDir = join(process.cwd(), "build", "static", "js");
const files = readdirSync(buildDir).filter((f) => f.startsWith("main.") && f.endsWith(".js"));
if (!files.length) {
  console.error("verify-auth-build: no main.*.js in build/static/js");
  process.exit(1);
}

const bundle = readFileSync(join(buildDir, files[0]), "utf8");
const required = [
  "treatPendingAsSignedOut:!1",
  "auth/clerk/exchange",
  "Connecting your account",
  'path:"/login"',
];

const missing = required.filter((needle) => !bundle.includes(needle));
if (missing.length) {
  console.error("verify-auth-build: bundle missing required auth markers:", missing.join(", "));
  process.exit(1);
}

console.log(`verify-auth-build: ok (${files[0]})`);

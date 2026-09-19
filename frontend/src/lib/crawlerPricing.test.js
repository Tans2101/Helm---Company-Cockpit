/**
 * @jest-environment node
 */
import { execFileSync } from "child_process";
import { readFileSync } from "fs";
import { join } from "path";
import { PLANS } from "./marketingCopy";

const frontendRoot = join(__dirname, "../..");

describe("crawler pricing artifacts", () => {
  test("llms.txt lists every PLANS tier price", () => {
    execFileSync("node", ["scripts/sync-llms-txt.mjs"], { cwd: frontendRoot });
    const txt = readFileSync(join(frontendRoot, "public/llms.txt"), "utf8");
    for (const p of PLANS) {
      expect(txt).toContain(p.label);
      if (p.price > 0) expect(txt).toContain(`$${p.price}/mo`);
      else expect(txt).toMatch(/Free: \$0/);
    }
    expect(txt).toContain("https://www.trenston.com/pricing");
  });
});

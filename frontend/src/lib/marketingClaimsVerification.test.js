/**
 * Marketing claim verification (2026-09-18).
 * Source of truth for About / pricing FAQ accuracy vs shipped product.
 * Update this file when claims or product behavior change.
 */
describe("marketing claim verification log", () => {
  const { VALUES, CEO_DAY, PRICING_FAQ, FEATURE_MODULES } = require("./marketingCopy");

  test("About Honest synthesis claims remain present", () => {
    const honest = VALUES.find((v) => v.title === "Honest synthesis");
    expect(honest.body).toContain("Add data");
    expect(honest.body).toContain("Ask Helm");
    expect(honest.body).toContain("Decision Center");
  });

  test("pricing FAQ lists Google Gmail with Calendar and QuickBooks", () => {
    const integrations = PRICING_FAQ.find((q) => q.q.includes("integrations"));
    expect(integrations.a).toMatch(/Gmail/i);
    expect(integrations.a).toMatch(/Calendar/i);
    expect(integrations.a).toMatch(/QuickBooks/i);
  });

  test("homepage Briefing and FAQ both acknowledge Gmail draft replies", () => {
    const briefing = CEO_DAY.find((s) => s.title === "Briefing");
    expect(briefing.body).toMatch(/Gmail/i);
    expect(briefing.body).toMatch(/draft/i);
    const integrations = PRICING_FAQ.find((q) => q.q.includes("integrations"));
    expect(integrations.a).toMatch(/draft/i);
  });

  test("Decision Center module copy does not claim automated outcome-landed tracking", () => {
    const decisions = FEATURE_MODULES.find((m) => m.title === "Decision Center");
    expect(decisions.body.toLowerCase()).not.toContain("actually landed");
    expect(decisions.body.toLowerCase()).toMatch(/status and owner|do not disappear/);
  });
});

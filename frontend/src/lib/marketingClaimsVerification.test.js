/**
 * Marketing claim verification (2026-09-18).
 * Source of truth for About / pricing FAQ accuracy vs shipped product.
 * Update this file when claims or product behavior change.
 */
import {
  VALUES,
  CEO_DAY,
  PRICING_FAQ,
  FEATURE_MODULES,
  PLANS,
  paidPlanRenewalDisclosure,
  FOUNDER_NOTE,
  INTEGRATIONS_SHOWCASE,
  INTEGRATIONS_PUBLIC_BLURB,
} from "./marketingCopy";

describe("marketing claim verification log", () => {
  test("About Honest synthesis claims remain present", () => {
    const honest = VALUES.find((v) => v.title === "Honest synthesis");
    expect(honest.body).toContain("Add data");
    expect(honest.body).toContain("Ask Helm");
    expect(honest.body).toContain("Decision Center");
  });

  test("pricing FAQ and Features list the same shipped integrations including SAP B1", () => {
    const integrations = PRICING_FAQ.find((q) => q.q.includes("integrations"));
    expect(integrations.a).toMatch(/Gmail/i);
    expect(integrations.a).toMatch(/Calendar/i);
    expect(integrations.a).toMatch(/QuickBooks/i);
    expect(integrations.a).toMatch(/Xero/i);
    expect(integrations.a).toMatch(/SAP Business One/i);
    expect(integrations.a).toMatch(/HubSpot/i);
    const mod = FEATURE_MODULES.find((m) => m.title === "Integrations");
    expect(mod.body).toBe(INTEGRATIONS_PUBLIC_BLURB);
    expect(mod.body).toMatch(/SAP Business One/i);
    expect(INTEGRATIONS_SHOWCASE.map((i) => i.name)).toEqual([
      "Google",
      "QuickBooks",
      "Xero",
      "SAP Business One",
      "HubSpot",
    ]);
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

  test("paid plan CTAs have ARL renewal disclosure; Free does not", () => {
    expect(paidPlanRenewalDisclosure(PLANS.find((p) => p.id === "free"))).toBe("");
    for (const id of ["starter", "growth", "business"]) {
      const plan = PLANS.find((p) => p.id === id);
      const text = paidPlanRenewalDisclosure(plan);
      expect(text).toMatch(/7-day free trial/);
      expect(text).toContain(`$${plan.price}/mo`);
      expect(text).toMatch(/unless you cancel before it ends/i);
      expect(text).toMatch(/Paddle customer portal/i);
      expect(text).toMatch(/Billing/i);
    }
  });

  test("founder note stays factual and short (no new personal details)", () => {
    expect(FOUNDER_NOTE).toMatch(/built Helm himself/i);
    expect(FOUNDER_NOTE).toMatch(/no separate product team/i);
    expect(FOUNDER_NOTE.toLowerCase()).not.toMatch(/\b(age|student|family|linkedin|photo)\b/);
  });
});

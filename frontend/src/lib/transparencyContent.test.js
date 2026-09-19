/**
 * @jest-environment node
 */
import { CHANGELOG_ENTRIES, CHANGELOG_INTRO } from "./changelogEntries";
import { STATUS_DISCLAIMER, STATUS_TRACKING_STARTED, STATUS_INCIDENTS } from "./statusConfig";
import { PUBLIC_INTEGRATIONS_COMING_SOON } from "./marketingCopy";

describe("transparency content", () => {
  test("changelog lists real dated entries only", () => {
    expect(CHANGELOG_INTRO.toLowerCase()).toContain("not a roadmap");
    expect(CHANGELOG_ENTRIES.length).toBeGreaterThan(5);
    for (const e of CHANGELOG_ENTRIES) {
      expect(e.date).toMatch(/^\d{4}-\d{2}-\d{2}$/);
      expect(e.title.length).toBeGreaterThan(8);
      expect(e.body.length).toBeGreaterThan(20);
    }
  });

  test("status page does not invent historical uptime", () => {
    expect(STATUS_TRACKING_STARTED).toBe("2026-09-19");
    expect(STATUS_DISCLAIMER.toLowerCase()).toContain("do not publish historical uptime");
    expect(Array.isArray(STATUS_INCIDENTS)).toBe(true);
  });

  test("GitHub stays labeled coming soon on public marketing", () => {
    expect(PUBLIC_INTEGRATIONS_COMING_SOON.some((i) => i.id === "github")).toBe(true);
    expect(PUBLIC_INTEGRATIONS_COMING_SOON.every((i) => /not available|not shipped|planned/i.test(i.description))).toBe(true);
  });
});

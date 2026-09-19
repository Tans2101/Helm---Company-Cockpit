/** ⌘K site search must include every public marketing page. */
import { SITE_SEARCH_ACTIONS } from "./siteSearchActions";
import { SEO_PAGES } from "./seoPages";

describe("quick nav site search pages", () => {
  test("includes About, Features, and other public marketing routes", () => {
    const tos = SITE_SEARCH_ACTIONS.map((a) => a.to).sort();
    expect(tos).toEqual(
      ["/about", "/features", "/help", "/privacy", "/refunds", "/security", "/terms"].sort(),
    );
    expect(SITE_SEARCH_ACTIONS.find((a) => a.id === "about")?.label).toBe("About");
  });

  test("every SEO marketing page except home is searchable", () => {
    const searchable = new Set(SITE_SEARCH_ACTIONS.map((a) => a.to));
    for (const path of Object.keys(SEO_PAGES)) {
      if (path === "/") continue;
      expect(searchable.has(path)).toBe(true);
    }
  });
});

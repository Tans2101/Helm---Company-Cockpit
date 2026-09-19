/** Unit tests for marketing SEO path helpers. */
import { canonicalForPath, seoForPath, SEO_PAGES } from "./seoPages";

describe("seoPages", () => {
  test("about and features have distinct canonicals and titles", () => {
    expect(canonicalForPath("/about")).toBe("https://www.helmcontrol.online/about");
    expect(canonicalForPath("/features")).toBe("https://www.helmcontrol.online/features");
    expect(canonicalForPath("/")).toBe("https://www.helmcontrol.online/");
    expect(seoForPath("/about").title).not.toBe(seoForPath("/").title);
    expect(seoForPath("/features").ogTitle).not.toBe(seoForPath("/").ogTitle);
  });

  test("app routes canonicalize to homepage", () => {
    expect(canonicalForPath("/app/financials")).toBe("https://www.helmcontrol.online/");
  });

  test("all nine marketing routes are defined", () => {
    expect(Object.keys(SEO_PAGES).sort()).toEqual(
      ["/", "/about", "/features", "/help", "/integrations", "/privacy", "/refunds", "/security", "/terms"].sort(),
    );
  });
});

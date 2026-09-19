/** Unit tests for marketing SEO path helpers. */
import { canonicalForPath, seoForPath, SEO_PAGES } from "./seoPages";

describe("seoPages", () => {
  test("about and features have distinct canonicals and titles", () => {
    expect(canonicalForPath("/about")).toBe("https://www.trenston.com/about");
    expect(canonicalForPath("/features")).toBe("https://www.trenston.com/features");
    expect(canonicalForPath("/")).toBe("https://www.trenston.com/");
    expect(seoForPath("/about").title).not.toBe(seoForPath("/").title);
    expect(seoForPath("/features").ogTitle).not.toBe(seoForPath("/").ogTitle);
  });

  test("app routes canonicalize to homepage", () => {
    expect(canonicalForPath("/app/financials")).toBe("https://www.trenston.com/");
  });

  test("all twelve marketing routes are defined", () => {
    expect(Object.keys(SEO_PAGES).sort()).toEqual(
      [
        "/",
        "/about",
        "/changelog",
        "/features",
        "/help",
        "/integrations",
        "/pricing",
        "/privacy",
        "/refunds",
        "/security",
        "/status",
        "/terms",
      ].sort(),
    );
  });
});

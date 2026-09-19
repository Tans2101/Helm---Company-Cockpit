/** Guardrail: Trenston must not load fonts from Google's CDN (GDPR / privacy). */
const fs = require("fs");
const path = require("path");

const PUBLIC = path.join(__dirname, "../../public");
const INDEX = path.join(PUBLIC, "index.html");
const FONTS_CSS = path.join(PUBLIC, "fonts/fonts.css");
const FONTS_DIR = path.join(PUBLIC, "fonts");

const CDN_RE = /https?:\/\/fonts\.(googleapis|gstatic)\.com/i;

describe("self-hosted fonts", () => {
  test("index.html has no Google Fonts CDN links or preconnects", () => {
    const html = fs.readFileSync(INDEX, "utf8");
    expect(html).not.toMatch(CDN_RE);
    expect(html).toContain('href="/fonts/fonts.css"');
    expect(html).toContain('href="/fonts/dm-sans-latin.woff2"');
    expect(html).toContain('href="/fonts/dm-mono-400-latin.woff2"');
    expect(html).toContain('href="/fonts/hedvig-letters-sans-latin.woff2"');
  });

  test("fonts.css declares local faces with font-display swap", () => {
    const css = fs.readFileSync(FONTS_CSS, "utf8");
    expect(css).not.toMatch(CDN_RE);
    expect(css).toMatch(/font-family:\s*'DM Sans'/);
    expect(css).toMatch(/font-family:\s*'DM Mono'/);
    expect(css).toMatch(/font-family:\s*'Hedvig Letters Sans'/);
    expect(css).toMatch(/font-display:\s*swap/);
    expect(css).toMatch(/font-weight:\s*300 700/);
    expect(css).toContain("url('/fonts/dm-sans-latin.woff2')");
  });

  test("required woff2 files exist on disk", () => {
    const required = [
      "dm-sans-latin.woff2",
      "dm-sans-latin-ext.woff2",
      "dm-mono-400-latin.woff2",
      "dm-mono-400-latin-ext.woff2",
      "dm-mono-500-latin.woff2",
      "dm-mono-500-latin-ext.woff2",
      "hedvig-letters-sans-latin.woff2",
      "hedvig-letters-sans-latin-ext.woff2",
      "hedvig-letters-sans-math.woff2",
      "hedvig-letters-sans-symbols.woff2",
    ];
    for (const name of required) {
      const full = path.join(FONTS_DIR, name);
      expect(fs.existsSync(full)).toBe(true);
      expect(fs.statSync(full).size).toBeGreaterThan(1000);
    }
  });
});

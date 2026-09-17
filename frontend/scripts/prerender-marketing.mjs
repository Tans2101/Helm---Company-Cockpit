#!/usr/bin/env node
/**
 * Postbuild marketing prerender (CRA-compatible).
 *
 * Copies build/index.html into per-route static files with route-specific
 * <title>, description, canonical, and Open Graph / Twitter tags rewritten
 * in the head. No headless browser: marketing pages depend on Clerk/auth
 * bootstrap, so Puppeteer/react-snap would be brittle here; crawlers and
 * link-preview bots need correct head tags (the confirmed live bug).
 *
 * Output:
 *   build/index.html
 *   build/about/index.html
 *   build/features/index.html
 *   …
 *
 * Vercel serves these static files before the SPA rewrite catch-all.
 */
import { mkdirSync, readFileSync, writeFileSync, existsSync } from "fs";
import { dirname, join } from "path";
import { fileURLToPath } from "url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const frontendRoot = join(__dirname, "..");
const buildDir = join(frontendRoot, "build");
const indexPath = join(buildDir, "index.html");
const seoPath = join(frontendRoot, "src/lib/seoPages.json");

function upsertMeta(html, attr, key, content) {
  const re = new RegExp(`<meta\\s+[^>]*${attr}=["']${key}["'][^>]*>`, "i");
  const tag = `<meta ${attr}="${key}" content="${escapeAttr(content)}" />`;
  if (re.test(html)) return html.replace(re, tag);
  return html.replace(/<\/head>/i, `    ${tag}\n    </head>`);
}

function upsertLink(html, rel, href) {
  const re = new RegExp(`<link\\s+[^>]*rel=["']${rel}["'][^>]*>`, "i");
  const tag = `<link rel="${rel}" href="${escapeAttr(href)}" />`;
  if (re.test(html)) return html.replace(re, tag);
  return html.replace(/<\/head>/i, `    ${tag}\n    </head>`);
}

function upsertTitle(html, title) {
  if (/<title>[\s\S]*?<\/title>/i.test(html)) {
    return html.replace(/<title>[\s\S]*?<\/title>/i, `<title>${escapeHtml(title)}</title>`);
  }
  return html.replace(/<\/head>/i, `    <title>${escapeHtml(title)}</title>\n    </head>`);
}

function escapeAttr(s) {
  return String(s).replace(/&/g, "&amp;").replace(/"/g, "&quot;").replace(/</g, "&lt;");
}

function escapeHtml(s) {
  return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

function applySeo(html, { path, page, origin, ogImage }) {
  const canonical = path === "/" ? `${origin}/` : `${origin}${path}`;
  let out = html;
  out = upsertTitle(out, page.title);
  out = upsertMeta(out, "name", "description", page.description);
  out = upsertLink(out, "canonical", canonical);
  out = upsertMeta(out, "property", "og:url", canonical);
  out = upsertMeta(out, "property", "og:title", page.ogTitle || page.title);
  out = upsertMeta(out, "property", "og:description", page.ogDescription || page.description);
  out = upsertMeta(out, "property", "og:image", ogImage);
  out = upsertMeta(out, "name", "twitter:title", page.ogTitle || page.title);
  out = upsertMeta(out, "name", "twitter:description", page.ogDescription || page.description);
  out = upsertMeta(out, "name", "twitter:image", ogImage);
  return out;
}

function main() {
  if (!existsSync(indexPath)) {
    console.error("prerender-marketing: build/index.html missing — run build first");
    process.exit(1);
  }
  const { origin, ogImage, pages } = JSON.parse(readFileSync(seoPath, "utf8"));
  const shell = readFileSync(indexPath, "utf8");

  for (const [path, page] of Object.entries(pages)) {
    const html = applySeo(shell, { path, page, origin, ogImage });
    const outFile =
      path === "/"
        ? indexPath
        : join(buildDir, path.replace(/^\//, ""), "index.html");
    mkdirSync(dirname(outFile), { recursive: true });
    writeFileSync(outFile, html, "utf8");
    console.log(`prerender-marketing: wrote ${outFile.slice(frontendRoot.length + 1)}`);
  }
  console.log("prerender-marketing: ok");
}

main();

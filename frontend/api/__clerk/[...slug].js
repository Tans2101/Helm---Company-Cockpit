/**
 * Proxy Clerk Frontend API through www.helmcontrol.online (working TLS).
 * Register https://www.helmcontrol.online/__clerk in Clerk Dashboard → Domains → Proxy URL.
 */
const CLERK_FAPI = "https://frontend-api.clerk.services";

export const config = {
  api: { bodyParser: false },
};

export default async function handler(req, res) {
  const slug = req.query.slug;
  const parts = Array.isArray(slug) ? slug : slug ? [slug] : [];
  const path = parts.join("/");
  const qs = req.url?.includes("?") ? `?${req.url.split("?")[1]}` : "";
  const target = `${CLERK_FAPI}/${path}${qs}`;

  const host = req.headers["x-forwarded-host"] || req.headers.host || "www.helmcontrol.online";
  const proto = req.headers["x-forwarded-proto"] || "https";
  const proxyUrl = `${proto}://${host}/__clerk`;

  const forwardHeaders = {};
  const pass = [
    "authorization",
    "content-type",
    "accept",
    "accept-language",
    "user-agent",
    "origin",
    "referer",
    "cookie",
  ];
  for (const key of pass) {
    if (req.headers[key]) forwardHeaders[key] = req.headers[key];
  }
  forwardHeaders["Clerk-Proxy-Url"] = proxyUrl;
  forwardHeaders["X-Forwarded-For"] =
    req.headers["x-forwarded-for"] || req.socket?.remoteAddress || "";
  forwardHeaders.host = "frontend-api.clerk.services";

  let body;
  if (req.method !== "GET" && req.method !== "HEAD") {
    body = await new Promise((resolve, reject) => {
      const chunks = [];
      req.on("data", (c) => chunks.push(c));
      req.on("end", () => resolve(Buffer.concat(chunks)));
      req.on("error", reject);
    });
  }

  try {
    const upstream = await fetch(target, {
      method: req.method,
      headers: forwardHeaders,
      body: body?.length ? body : undefined,
    });

    res.status(upstream.status);
    upstream.headers.forEach((value, key) => {
      if (key.toLowerCase() === "transfer-encoding") return;
      res.setHeader(key, value);
    });
    const buf = Buffer.from(await upstream.arrayBuffer());
    res.send(buf);
  } catch (err) {
    console.error("clerk proxy error", err);
    res.status(502).json({ error: "Clerk proxy failed" });
  }
}

/**
 * Clerk Frontend API proxy (Vercel serverless).
 * Dashboard proxy URL: https://www.helmcontrol.online/__clerk
 * Requires CLERK_SECRET_KEY in Vercel project environment variables.
 */
const CLERK_FAPI = process.env.CLERK_FAPI_URL || "https://frontend-api.clerk.services";

export const config = {
  api: { bodyParser: false },
};

function readBody(req) {
  return new Promise((resolve, reject) => {
    const chunks = [];
    req.on("data", (chunk) => chunks.push(chunk));
    req.on("end", () => resolve(Buffer.concat(chunks)));
    req.on("error", reject);
  });
}

function clientIp(req) {
  const xff = req.headers["x-forwarded-for"];
  if (typeof xff === "string" && xff.trim()) {
    return xff.split(",")[0].trim();
  }
  const cf = req.headers["cf-connecting-ip"];
  if (typeof cf === "string" && cf.trim()) {
    return cf.trim();
  }
  return req.socket?.remoteAddress || "127.0.0.1";
}

export default async function handler(req, res) {
  const secret = process.env.CLERK_SECRET_KEY;
  if (!secret) {
    res.status(500).json({
      error: "CLERK_SECRET_KEY is not set on Vercel — add it in Project Settings → Environment Variables",
    });
    return;
  }

  const slug = req.query.slug;
  const parts = Array.isArray(slug) ? slug : slug ? [slug] : [];
  const path = parts.join("/");
  const qs = req.url?.includes("?") ? `?${req.url.split("?")[1]}` : "";
  const target = `${CLERK_FAPI}/${path}${qs}`;

  const host = req.headers["x-forwarded-host"] || req.headers.host || "www.helmcontrol.online";
  const proto = req.headers["x-forwarded-proto"] || "https";
  const proxyUrl = `${proto}://${host}/__clerk`;

  const forward = {
    "Clerk-Proxy-Url": proxyUrl,
    "Clerk-Secret-Key": secret,
    "X-Forwarded-For": clientIp(req),
  };
  for (const key of [
    "authorization",
    "content-type",
    "accept",
    "accept-language",
    "user-agent",
    "origin",
    "referer",
    "cookie",
  ]) {
    const val = req.headers[key];
    if (val) forward[key] = val;
  }

  try {
    const body =
      req.method !== "GET" && req.method !== "HEAD" ? await readBody(req) : undefined;
    const upstream = await fetch(target, {
      method: req.method,
      headers: forward,
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
    res.status(502).json({ error: "Clerk proxy failed", detail: err?.message || String(err) });
  }
}

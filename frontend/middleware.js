/**
 * Clerk FAPI edge proxy — Dashboard proxy URL: https://www.helmcontrol.online/__clerk
 * Proxies directly to frontend-api.clerk.services (Render cannot TLS to FAPI).
 * CLERK_SECRET_KEY: Vercel env, or fetched from Render bootstrap (CLERK_PROXY_BOOTSTRAP).
 */
const CLERK_FAPI = process.env.CLERK_FAPI_URL || "https://frontend-api.clerk.services";
const RENDER_API =
  process.env.RENDER_API_ORIGIN || "https://helm-company-cockpit.onrender.com";

let cachedSecret = process.env.CLERK_SECRET_KEY || null;
let secretFetchPromise = null;

export const config = {
  matcher: "/__clerk/:path*",
};

async function resolveClerkSecret() {
  if (cachedSecret) return cachedSecret;
  if (process.env.CLERK_SECRET_KEY) {
    cachedSecret = process.env.CLERK_SECRET_KEY;
    return cachedSecret;
  }
  const bootstrap = process.env.CLERK_PROXY_BOOTSTRAP;
  if (!bootstrap) return null;
  if (!secretFetchPromise) {
    secretFetchPromise = fetch(`${RENDER_API}/api/auth/clerk-edge-secret`, {
      headers: { "X-Clerk-Bootstrap": bootstrap },
    })
      .then(async (r) => {
        if (!r.ok) return null;
        const data = await r.json();
        return (data?.clerk_secret_key || "").trim() || null;
      })
      .catch(() => null);
  }
  cachedSecret = await secretFetchPromise;
  return cachedSecret;
}

export default async function middleware(request) {
  const secret = await resolveClerkSecret();
  if (!secret) {
    return new Response(
      JSON.stringify({
        error: "Clerk proxy not configured",
        hint: "Set CLERK_SECRET_KEY on Vercel or CLERK_PROXY_BOOTSTRAP + Render CLERK_PROXY_BOOTSTRAP",
      }),
      { status: 500, headers: { "content-type": "application/json" } },
    );
  }

  const url = new URL(request.url);
  const subpath = url.pathname.replace(/^\/__clerk\/?/, "");
  const target = `${CLERK_FAPI}/${subpath}${url.search}`;

  const proto = request.headers.get("x-forwarded-proto") || "https";
  // Clerk validates proxy URL on primary apex (must match Dashboard registration).
  const proxyUrl = "https://helmcontrol.online/__clerk";

  const xff = request.headers.get("x-forwarded-for");
  const clientIp = xff ? xff.split(",")[0].trim() : "127.0.0.1";

  const headers = new Headers();
  headers.set("Clerk-Proxy-Url", proxyUrl);
  headers.set("Clerk-Secret-Key", secret);
  headers.set("X-Forwarded-For", clientIp);
  headers.set("Origin", "https://helmcontrol.online");
  for (const key of ["authorization", "content-type", "accept", "accept-language", "user-agent", "cookie"]) {
    const val = request.headers.get(key);
    if (val) headers.set(key, val);
  }

  const body =
    request.method !== "GET" && request.method !== "HEAD" ? await request.arrayBuffer() : undefined;

  try {
    const upstream = await fetch(target, {
      method: request.method,
      headers,
      body: body?.byteLength ? body : undefined,
    });
    return new Response(upstream.body, {
      status: upstream.status,
      headers: upstream.headers,
    });
  } catch (err) {
    return new Response(
      JSON.stringify({ error: "Clerk proxy failed", detail: String(err?.message || err) }),
      { status: 502, headers: { "content-type": "application/json" } },
    );
  }
}

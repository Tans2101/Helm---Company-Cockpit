/**
 * Clerk FAPI edge proxy — routes /__clerk to Render (has CLERK_SECRET_KEY).
 * No Vercel secrets required. Dashboard proxy URL: https://www.helmcontrol.online/__clerk
 */
const RENDER_API =
  process.env.RENDER_API_ORIGIN || "https://helm-company-cockpit.onrender.com";

export const config = {
  matcher: "/__clerk/:path*",
};

export default async function middleware(request) {
  const url = new URL(request.url);
  const subpath = url.pathname.replace(/^\/__clerk\/?/, "");
  const target = `${RENDER_API}/api/clerk-proxy/${subpath}${url.search}`;

  const xff = request.headers.get("x-forwarded-for");
  const clientIp = xff ? xff.split(",")[0].trim() : "127.0.0.1";

  const headers = new Headers();
  for (const key of [
    "authorization", "content-type", "accept", "accept-language", "user-agent", "cookie",
  ]) {
    const val = request.headers.get(key);
    if (val) headers.set(key, val);
  }
  headers.set("x-forwarded-for", clientIp);
  headers.set("x-forwarded-host", request.headers.get("x-forwarded-host") || url.host);
  headers.set("x-forwarded-proto", request.headers.get("x-forwarded-proto") || "https");

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

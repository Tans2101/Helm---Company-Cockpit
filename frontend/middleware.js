/**
 * Clerk FAPI edge proxy — Dashboard proxy URL: https://www.helmcontrol.online/__clerk
 * Requires CLERK_SECRET_KEY in Vercel → Project Settings → Environment Variables.
 */
const CLERK_FAPI = process.env.CLERK_FAPI_URL || "https://frontend-api.clerk.services";

export const config = {
  matcher: "/__clerk/:path*",
};

export default async function middleware(request) {
  const secret = process.env.CLERK_SECRET_KEY;
  if (!secret) {
    return new Response(
      JSON.stringify({ error: "CLERK_SECRET_KEY missing on Vercel" }),
      { status: 500, headers: { "content-type": "application/json" } },
    );
  }

  const url = new URL(request.url);
  const subpath = url.pathname.replace(/^\/__clerk\/?/, "");
  const target = `${CLERK_FAPI}/${subpath}${url.search}`;

  const host = request.headers.get("x-forwarded-host") || url.host;
  const proto = request.headers.get("x-forwarded-proto") || "https";
  const proxyUrl = `${proto}://${host}/__clerk`;

  const xff = request.headers.get("x-forwarded-for");
  const clientIp = xff ? xff.split(",")[0].trim() : "127.0.0.1";

  const headers = new Headers();
  headers.set("Clerk-Proxy-Url", proxyUrl);
  headers.set("Clerk-Secret-Key", secret);
  headers.set("X-Forwarded-For", clientIp);
  headers.set("Origin", `${proto}://${host}`);
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

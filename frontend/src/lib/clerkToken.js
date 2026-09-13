const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

export function withTimeout(promise, ms, label = "timeout") {
  return Promise.race([
    promise,
    new Promise((_, reject) => {
      setTimeout(() => reject(new Error(label)), ms);
    }),
  ]);
}

function jwtExpMs(token) {
  try {
    const payload = JSON.parse(atob(token.split(".")[1].replace(/-/g, "+").replace(/_/g, "/")));
    return typeof payload.exp === "number" ? payload.exp * 1000 : 0;
  } catch {
    return 0;
  }
}

let cachedToken = null;
let cachedExpMs = 0;
let inflight = null;

/** Drop cached JWT (e.g. after sign-out). */
export function clearClerkTokenCache() {
  cachedToken = null;
  cachedExpMs = 0;
  inflight = null;
}

/**
 * Fast path for API calls: reuse Clerk JWT until ~60s before expiry.
 * Uses Clerk's own cache (skipCache: false) — never hammer Clerk on every click.
 */
export async function getCachedClerkToken(getToken, session, { tokenTimeoutMs = 1500 } = {}) {
  const now = Date.now();
  if (cachedToken && cachedExpMs - 60_000 > now) {
    return cachedToken;
  }
  if (inflight) return inflight;

  inflight = (async () => {
    try {
      // Single getToken call — Clerk caches internally; avoid double round-trips.
      const token = await withTimeout(getToken(), tokenTimeoutMs, "auth-token-timeout").catch(() => null);
      if (token && token.split(".").length === 3) {
        cachedToken = token;
        cachedExpMs = jwtExpMs(token) || now + 55_000;
        return token;
      }
      return null;
    } finally {
      inflight = null;
    }
  })();

  return inflight;
}

/**
 * Bootstrap / first-sign-in only: bounded retries.
 * Prefer Clerk cache; only skipCache on later attempts if the first fails.
 */
export async function resolveClerkToken(
  getToken,
  session,
  { attempts = 8, delayMs = 250, tokenTimeoutMs = 2000 } = {},
) {
  for (let i = 0; i < attempts; i += 1) {
    try {
      const skipCache = i > 0;
      const opts = skipCache ? { skipCache: true } : undefined;
      const fromSession = session
        ? await withTimeout(session.getToken(opts), tokenTimeoutMs, "session-token-timeout")
        : null;
      const fromAuth = await withTimeout(getToken(opts), tokenTimeoutMs, "auth-token-timeout");
      const token = fromSession || fromAuth;
      if (token && token.split(".").length === 3) {
        cachedToken = token;
        cachedExpMs = jwtExpMs(token) || Date.now() + 55_000;
        return token;
      }
    } catch {
      /* retry */
    }
    await sleep(delayMs);
  }
  return null;
}

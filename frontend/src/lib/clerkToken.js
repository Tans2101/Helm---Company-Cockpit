const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

export function withTimeout(promise, ms, label = "timeout") {
  return Promise.race([
    promise,
    new Promise((_, reject) => {
      setTimeout(() => reject(new Error(label)), ms);
    }),
  ]);
}

/** Resolve a Clerk session JWT with bounded wait (avoids hanging the whole app). */
export async function resolveClerkToken(getToken, session, { attempts = 20, delayMs = 400, tokenTimeoutMs = 2500 } = {}) {
  for (let i = 0; i < attempts; i += 1) {
    try {
      const fromSession = session
        ? await withTimeout(session.getToken({ skipCache: true }), tokenTimeoutMs, "session-token-timeout")
        : null;
      const fromAuth = await withTimeout(getToken({ skipCache: true }), tokenTimeoutMs, "auth-token-timeout");
      const token = fromSession || fromAuth;
      if (token && token.split(".").length === 3) return token;
    } catch {
      /* retry */
    }
    await sleep(delayMs);
  }
  return null;
}

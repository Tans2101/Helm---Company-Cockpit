// Loads Paddle.js v2 once. Initialize at most once; keep the event callback fresh
// for SPA re-checkouts in the same tab (Paddle only supports Initialize once).
let loaded;
let initialized = false;
let latestOnEvent = null;

export function loadPaddle() {
  if (window.Paddle) return Promise.resolve(window.Paddle);
  if (loaded) return loaded;
  loaded = new Promise((resolve, reject) => {
    const s = document.createElement("script");
    s.src = "https://cdn.paddle.com/paddle/v2/paddle.js";
    s.async = true;
    s.onload = () => resolve(window.Paddle);
    s.onerror = () => reject(new Error("Unable to load Paddle.js"));
    document.head.appendChild(s);
  });
  return loaded;
}

export async function initPaddle(token, environment, onEvent) {
  const P = await loadPaddle();
  latestOnEvent = onEvent || null;
  if (!initialized) {
    P.Environment.set(environment === "sandbox" ? "sandbox" : "production");
    P.Initialize({
      token,
      eventCallback: (event) => {
        if (typeof latestOnEvent === "function") latestOnEvent(event);
      },
    });
    initialized = true;
  }
  return P;
}

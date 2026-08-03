// Loads Paddle.js v2 once and initializes it a single time with the
// client token fetched from our backend (/billing/paddle/config).
let loaded;
let initialized = false;

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
  if (!initialized) {
    P.Environment.set(environment === "sandbox" ? "sandbox" : "production");
    P.Initialize({ token, eventCallback: onEvent });
    initialized = true;
  }
  return P;
}

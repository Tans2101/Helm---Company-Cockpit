const PADDLE_JS = "https://cdn.paddle.com/paddle/v2/paddle.js";

let loadingPromise = null;
let initializedToken = null;

function loadPaddleScript() {
  if (typeof window === "undefined") return Promise.reject(new Error("No window"));
  if (window.Paddle) return Promise.resolve(window.Paddle);
  if (loadingPromise) return loadingPromise;
  loadingPromise = new Promise((resolve, reject) => {
    const existing = document.querySelector(`script[src="${PADDLE_JS}"]`);
    if (existing) {
      existing.addEventListener("load", () => resolve(window.Paddle));
      existing.addEventListener("error", () => reject(new Error("Failed to load Paddle.js")));
      return;
    }
    const script = document.createElement("script");
    script.src = PADDLE_JS;
    script.async = true;
    script.onload = () => resolve(window.Paddle);
    script.onerror = () => reject(new Error("Failed to load Paddle.js"));
    document.head.appendChild(script);
  });
  return loadingPromise;
}

/**
 * Open Paddle overlay checkout for a backend-created transaction.
 * Falls back to hosted checkout_url when overlay cannot start.
 */
export async function openPaddleCheckout(checkout) {
  if (!checkout?.paddle_transaction_id && checkout?.checkout_url) {
    window.location.href = checkout.checkout_url;
    return { mode: "redirect" };
  }
  if (!checkout?.client_token || !checkout?.paddle_transaction_id) {
    if (checkout?.checkout_url) {
      window.location.href = checkout.checkout_url;
      return { mode: "redirect" };
    }
    throw new Error("Paddle checkout is missing transaction details");
  }

  const Paddle = await loadPaddleScript();
  if (!Paddle) throw new Error("Paddle.js unavailable");

  if (checkout.paddle_env === "sandbox" && typeof Paddle.Environment?.set === "function") {
    Paddle.Environment.set("sandbox");
  }

  if (initializedToken !== checkout.client_token) {
    Paddle.Initialize({ token: checkout.client_token });
    initializedToken = checkout.client_token;
  }

  try {
    Paddle.Checkout.open({
      transactionId: checkout.paddle_transaction_id,
      customer: checkout.customer_email ? { email: checkout.customer_email } : undefined,
      settings: {
        displayMode: "overlay",
        theme: "dark",
        successUrl: checkout.success_url,
      },
    });
    return { mode: "overlay" };
  } catch (e) {
    if (checkout.checkout_url) {
      window.location.href = checkout.checkout_url;
      return { mode: "redirect" };
    }
    throw e;
  }
}

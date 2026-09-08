const STORAGE_KEY = "helm_referral_code";
const CODE_RE = /^[A-Za-z0-9]{8,32}$/;

export function persistReferralFromSearch(search) {
  try {
    const params = new URLSearchParams(search || (typeof window !== "undefined" ? window.location.search : ""));
    const code = (params.get("ref") || "").trim();
    if (code && CODE_RE.test(code)) {
      localStorage.setItem(STORAGE_KEY, code);
    }
  } catch {
    /* ignore quota / private mode */
  }
}

export function peekReferralCode() {
  try {
    const code = (localStorage.getItem(STORAGE_KEY) || "").trim();
    return CODE_RE.test(code) ? code : "";
  } catch {
    return "";
  }
}

export function consumeReferralCode() {
  const code = peekReferralCode();
  try {
    localStorage.removeItem(STORAGE_KEY);
  } catch {
    /* ignore */
  }
  return code;
}

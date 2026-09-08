const STORAGE_KEY = "helm_referral_code";
const CODE_RE = /^[A-Fa-f0-9]{16}$/;

export function persistReferralFromSearch(search) {
  try {
    const params = new URLSearchParams(search || (typeof window !== "undefined" ? window.location.search : ""));
    const code = (params.get("ref") || "").trim().toLowerCase();
    if (CODE_RE.test(code)) {
      localStorage.setItem(STORAGE_KEY, code);
    }
  } catch {
    /* ignore quota / private mode */
  }
}

export function peekReferralCode() {
  try {
    const code = (localStorage.getItem(STORAGE_KEY) || "").trim().toLowerCase();
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

/** Include a pending ?ref= code on workspace create, then clear it after success. */
export function withReferralPayload(body) {
  const referral_code = peekReferralCode();
  return referral_code ? { ...body, referral_code } : body;
}

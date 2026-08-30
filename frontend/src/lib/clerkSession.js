/** True when Clerk has an active session (even if isSignedIn lags behind). */
export function clerkSessionActive({ isSignedIn, userId, sessionId, session }) {
  return Boolean(isSignedIn || userId || sessionId || session);
}

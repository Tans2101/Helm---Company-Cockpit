/** True when Clerk has an active session (including pending right after email verify). */
export function clerkSessionActive({
  isSignedIn,
  userId,
  sessionId,
  session,
  sessionStatus,
}) {
  return Boolean(
    isSignedIn
    || userId
    || sessionId
    || session
    || sessionStatus === "pending",
  );
}

/** True when Clerk session is ready for Helm JWT exchange (needs a concrete session). */
export function clerkSessionReadyForExchange({
  isSignedIn,
  userId,
  sessionId,
  session,
}) {
  return Boolean(isSignedIn || userId || sessionId || session);
}

/** Clerk useAuth options — pending sessions must count as signed in for Helm exchange. */
export const CLERK_AUTH_OPTS = { treatPendingAsSignedOut: false };

/**
 * Legacy full-app paywall. Free is now a real tier — everyone enters the cockpit.
 * Feature-level gates (Ask Trenston, AI upload, integrations, seats) handle upgrades via /app/billing.
 */
export default function SubscriptionGate({ children }) {
  return children;
}

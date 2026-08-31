export default function ClerkLoadError({ onRetry }) {
  return (
    <div className="min-h-screen flex flex-col items-center justify-center bg-[#09090b] p-8 text-center">
      <p className="text-lg text-white mb-2">Sign-in service is not responding</p>
      <p className="text-sm text-zinc-400 max-w-lg leading-relaxed">
        Clerk could not load. Helm uses a proxy at{" "}
        <span className="font-mono text-xs">/__clerk</span> while{" "}
        <span className="font-mono text-xs">clerk.helmcontrol.online</span> SSL is provisioning.
        Make sure <span className="text-zinc-300">CLERK_SECRET_KEY</span> is set in Vercel environment
        variables (same value as Render), redeploy, then run{" "}
        <span className="font-mono text-xs">POST /api/setup/clerk-sync</span> to register the proxy URL
        in Clerk Dashboard. If SSL is still pending, add apex CAA records in Namecheap for{" "}
        <span className="font-mono text-xs">pki.goog</span> and{" "}
        <span className="font-mono text-xs">digicert.com</span>.
      </p>
      <button
        type="button"
        className="mt-6 rounded-lg bg-gold text-black px-4 py-2 text-sm font-medium"
        onClick={onRetry || (() => window.location.reload())}
      >
        Retry
      </button>
    </div>
  );
}

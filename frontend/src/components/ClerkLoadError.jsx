export default function ClerkLoadError({ onRetry }) {
  return (
    <div className="min-h-screen flex flex-col items-center justify-center bg-[#09090b] p-8 text-center">
      <p className="text-lg text-white mb-2">Sign-in service is not responding</p>
      <p className="text-sm text-zinc-400 max-w-lg leading-relaxed">
        Clerk could not load. In Clerk Dashboard → <span className="text-zinc-300">Domains</span>, make sure{" "}
        <span className="font-mono text-xs">clerk.helmcontrol.online</span> shows a green checkmark (DNS verified, SSL issued).
        Do <strong>not</strong> use a proxy URL — use DNS only. If SSL is pending, add apex CAA records in Namecheap
        for <span className="font-mono text-xs">pki.goog</span> and <span className="font-mono text-xs">digicert.com</span>,
        then click Verify in Clerk and wait 5–30 minutes.
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

export default function ClerkLoadError({ onRetry }) {
  return (
    <div className="min-h-screen flex flex-col items-center justify-center bg-[#09090b] p-8 text-center">
      <p className="text-lg text-white mb-2">Sign-in service is not responding</p>
      <p className="text-sm text-zinc-400 max-w-lg leading-relaxed">
        Clerk could not load. This usually means the <span className="text-zinc-300">clerk.helmcontrol.online</span>{" "}
        SSL certificate is still provisioning. In Clerk Dashboard → Domains, set Proxy URL to{" "}
        <span className="font-mono text-xs">https://www.helmcontrol.online/__clerk</span>, verify the domain,
        and wait 5–30 minutes. If it persists, add apex CAA records for <span className="font-mono text-xs">pki.goog</span> and{" "}
        <span className="font-mono text-xs">digicert.com</span> in Namecheap DNS.
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

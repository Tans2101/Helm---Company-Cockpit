import { Link } from "react-router-dom";

export default function Terms() {
  return (
    <div className="min-h-screen bg-[#09090b] text-white grain">
      <div className="relative z-10 mx-auto max-w-3xl px-6 py-16 md:py-24">
        <Link to="/" className="inline-flex items-center gap-2 text-sm text-zinc-500 hover:text-white transition-colors mb-10">
          <span className="w-6 h-6 rounded bg-gold/15 border border-gold/30 flex items-center justify-center">
            <span className="font-mono text-gold text-xs">H</span>
          </span>
          Back to Helm
        </Link>

        <p className="font-mono text-xs uppercase tracking-[0.25em] text-gold mb-4">Legal</p>
        <h1 className="text-3xl md:text-4xl font-light tracking-tight text-white">Terms of Service</h1>
        <p className="text-zinc-500 text-sm mt-3">Last updated: August 2026 · Template for [COMPANY_NAME]</p>

        <div className="mt-10 space-y-8 text-[15px] text-zinc-300 leading-relaxed">
          <section>
            <h2 className="text-lg text-white font-normal tracking-tight mb-2">Agreement</h2>
            <p>
              By accessing Helm you agree to these Terms with [COMPANY_NAME]. If you use Helm on behalf of a company,
              you represent that you have authority to bind that company. Contact: [CONTACT_EMAIL] · [COMPANY_ADDRESS].
            </p>
          </section>

          <section>
            <h2 className="text-lg text-white font-normal tracking-tight mb-2">Account</h2>
            <p>
              You must sign in with a valid Google account and keep your credentials secure.
              You are responsible for activity under your account and for ensuring workspace members have appropriate access.
            </p>
          </section>

          <section>
            <h2 className="text-lg text-white font-normal tracking-tight mb-2">Acceptable use</h2>
            <p>
              You may not misuse Helm, attempt unauthorized access, disrupt the service, reverse engineer it except where
              permitted by law, or upload unlawful, infringing, or harmful content. You must only submit data you have the
              right to process, including when using AI features.
            </p>
          </section>

          <section>
            <h2 className="text-lg text-white font-normal tracking-tight mb-2">Subscriptions & billing</h2>
            <p>
              Paid plans are billed by Paddle as merchant of record. Pricing, taxes, invoices, refunds, and payment method
              handling follow Paddle’s checkout and customer terms. Plan features (including AI limits) may change with notice.
              Failure to pay may result in downgrade or suspension of paid features.
            </p>
          </section>

          <section>
            <h2 className="text-lg text-white font-normal tracking-tight mb-2">AI output disclaimer</h2>
            <p>
              Helm may generate summaries, recommendations, and answers using AI models (including Claude via Emergent).
              Outputs can be wrong, incomplete, or outdated. They are not legal, financial, tax, medical, or other professional
              advice. You must verify material decisions independently.
            </p>
          </section>

          <section>
            <h2 className="text-lg text-white font-normal tracking-tight mb-2">Limitation of liability</h2>
            <p>
              To the fullest extent permitted by law, [COMPANY_NAME] and its suppliers are not liable for indirect, incidental,
              special, consequential, or punitive damages, or for lost profits, data, or business opportunities arising from
              your use of Helm. Our aggregate liability for claims relating to the service is limited to the fees you paid us
              for Helm in the twelve months before the claim (or zero if you have not paid for Helm Pro).
            </p>
          </section>

          <section>
            <h2 className="text-lg text-white font-normal tracking-tight mb-2">Termination</h2>
            <p>
              You may stop using Helm and request account deletion at any time. We may suspend or terminate access if you
              breach these Terms, create risk for the service or other users, or as required by law. Provisions that by nature
              should survive (including disclaimers and liability limits) will survive termination.
            </p>
          </section>

          <section>
            <h2 className="text-lg text-white font-normal tracking-tight mb-2">Contact</h2>
            <p>
              Questions about these Terms: [CONTACT_EMAIL] · [COMPANY_NAME] · [COMPANY_ADDRESS].
            </p>
          </section>
        </div>

        <p className="mt-12 text-xs text-zinc-600 border-t border-white/5 pt-6">
          This page is a template and not legal advice. Replace placeholders and have counsel review before publishing.
        </p>
      </div>
    </div>
  );
}

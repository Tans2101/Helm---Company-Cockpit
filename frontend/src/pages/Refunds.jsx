import { Link } from "react-router-dom";

export default function Refunds() {
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
        <h1 className="text-3xl md:text-4xl font-light tracking-tight text-white">Refund &amp; Billing Policy</h1>
        <p className="text-zinc-500 text-sm mt-3">Last updated: September 3, 2026</p>

        <div className="mt-10 space-y-8 text-[15px] text-zinc-300 leading-relaxed">
          <section>
            <h2 className="text-lg text-white font-normal tracking-tight mb-2">Who this covers</h2>
            <p>
              This policy applies to paid Helm subscriptions sold by{" "}
              <span className="text-white">Helm Control</span> through{" "}
              <span className="text-white">Paddle</span> (merchant of record).
              Contact:{" "}
              <a href="mailto:tansherdhawan@gmail.com" className="text-gold hover:underline">tansherdhawan@gmail.com</a>
              {" "}· BGC, Taguig, Philippines.
            </p>
          </section>

          <section>
            <h2 className="text-lg text-white font-normal tracking-tight mb-2">Plans &amp; pricing</h2>
            <p>
              Helm offers tiered plans (including a free tier and paid plans). Features, member limits, and prices for
              your selected plan are shown on the{" "}
              <Link to="/app/billing" className="text-gold hover:underline">Billing</Link> page and marketing pricing.
              We may update plan pricing or inclusions with notice; changes apply to future billing periods.
            </p>
          </section>

          <section>
            <h2 className="text-lg text-white font-normal tracking-tight mb-2">7-day free trial</h2>
            <p>
              Paid plans include a <span className="text-white">7-day free trial</span>. During the trial you can explore
              paid features without being charged. If you cancel before the trial ends, you will not be billed for that
              plan. If you do not cancel, billing for your selected plan begins after the trial according to Paddle checkout.
            </p>
          </section>

          <section className="rounded-lg border border-white/10 bg-white/[0.02] p-5">
            <h2 className="text-lg text-white font-normal tracking-tight mb-2">No refunds after payment</h2>
            <p className="text-zinc-200">
              <span className="text-white font-medium">Once a payment is processed, it is non-refundable.</span>{" "}
              This includes the first charge after a trial and any subsequent renewal charges. Please use the free trial
              to evaluate Helm before your card is charged. If you believe a charge was made in error (for example a
              duplicate transaction), contact us at{" "}
              <a href="mailto:tansherdhawan@gmail.com" className="text-gold hover:underline">tansherdhawan@gmail.com</a>
              {" "}and we will work with Paddle to investigate.
            </p>
          </section>

          <section>
            <h2 className="text-lg text-white font-normal tracking-tight mb-2">Cancellation</h2>
            <p>
              You can cancel anytime through the Paddle customer portal (linked from{" "}
              <Link to="/app/billing" className="text-gold hover:underline">Billing</Link> when available).
              Cancellation takes effect at the end of the current billing period — you keep access until that period ends,
              and you will not be charged for the next period. Canceling does not entitle you to a refund for time already
              paid in the current period.
            </p>
          </section>

          <section>
            <h2 className="text-lg text-white font-normal tracking-tight mb-2">Payment processor</h2>
            <p>
              All payments are handled by Paddle as merchant of record. Invoices, taxes, payment methods, and customer
              billing records are managed through Paddle. Helm does not store full card numbers.
            </p>
          </section>

          <section>
            <h2 className="text-lg text-white font-normal tracking-tight mb-2">Non-payment</h2>
            <p>
              If a renewal payment fails, we may restrict paid features or suspend the workspace until payment is updated
              via the billing portal.
            </p>
          </section>

          <section>
            <h2 className="text-lg text-white font-normal tracking-tight mb-2">Related documents</h2>
            <p>
              See also our{" "}
              <Link to="/terms" className="text-gold hover:underline">Terms of Service</Link>
              {" "}and{" "}
              <Link to="/privacy" className="text-gold hover:underline">Privacy Policy</Link>.
            </p>
          </section>

          <section>
            <h2 className="text-lg text-white font-normal tracking-tight mb-2">Contact</h2>
            <p>
              Billing questions:{" "}
              <a href="mailto:tansherdhawan@gmail.com" className="text-gold hover:underline">tansherdhawan@gmail.com</a>
              {" "}· Helm Control · BGC, Taguig, Philippines.
            </p>
          </section>
        </div>

        <p className="mt-12 text-xs text-zinc-600 border-t border-white/5 pt-6">
          This policy will be reviewed by legal counsel as Helm grows; contact us with questions.
        </p>
      </div>
    </div>
  );
}

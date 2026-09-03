import { Link } from "react-router-dom";

/*
  NOTE (pre-publish): Google OAuth previously considered requesting gmail.readonly
  for future email-forward intake. The live scope list in backend/server.py
  (GOOGLE_SCOPES) currently requests calendar.readonly only — gmail is omitted.
  If Gmail is re-added before a real feature ships, update this Privacy Policy
  to describe the unused scope honestly before treating the policy as final.
*/

export default function Privacy() {
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
        <h1 className="text-3xl md:text-4xl font-light tracking-tight text-white">Privacy Policy</h1>
        <p className="text-zinc-500 text-sm mt-3">Last updated: September 3, 2026</p>

        <div className="mt-10 space-y-8 text-[15px] text-zinc-300 leading-relaxed">
          <section>
            <h2 className="text-lg text-white font-normal tracking-tight mb-2">Who we are</h2>
            <p>
              This Privacy Policy explains how <span className="text-white">Helm Control</span> (“we”, “us”)
              collects and uses information when you use <span className="text-white">Helm</span>, our company cockpit product.
              Contact:{" "}
              <a href="mailto:tansherdhawan@gmail.com" className="text-gold hover:underline">tansherdhawan@gmail.com</a>.
              Postal address: BGC, Taguig, Philippines.
            </p>
          </section>

          <section>
            <h2 className="text-lg text-white font-normal tracking-tight mb-2">Who can use Helm</h2>
            <p>
              Helm is open to individuals and businesses worldwide. There is no geographic restriction.
              We do not impose a hard minimum age gate. If you are under 18, you should only use Helm under a parent
              or guardian&apos;s supervision, at that guardian&apos;s discretion. Helm does not independently verify age
              or guardian consent.
            </p>
          </section>

          <section>
            <h2 className="text-lg text-white font-normal tracking-tight mb-2">Account &amp; profile data</h2>
            <p>
              When you sign up, we collect your name, email address, and company information needed to create your
              workspace. Authentication is handled by <span className="text-white">Clerk</span>; we receive basic
              identity details (such as name, email, and profile picture when provided) to create and secure your session.
              We do not ask for additional personal profile fields beyond what is required to run your account.
            </p>
          </section>

          <section>
            <h2 className="text-lg text-white font-normal tracking-tight mb-2">Financial &amp; business data</h2>
            <p>
              Helm stores the business data you enter or generate in the product — for example revenue and expense entries,
              categories, tasks, decisions, reports, team roster, pipeline deals, and related workspace content.
              Financial figures come from what you manually enter or from documents you upload.
            </p>
          </section>

          <section>
            <h2 className="text-lg text-white font-normal tracking-tight mb-2">Uploaded documents</h2>
            <p>
              Documents you upload (such as bills, receipts, or invoices) are stored in a private{" "}
              <span className="text-white">Cloudflare R2</span> bucket. Files are not publicly accessible.
              When you upload a document for extraction, it is sent to <span className="text-white">Anthropic&apos;s Claude API</span>{" "}
              for automated parsing. <span className="text-white">No human at Helm views your uploaded documents</span> —
              only the automated Claude process does, solely to extract suggested entries for your workspace.
            </p>
          </section>

          <section>
            <h2 className="text-lg text-white font-normal tracking-tight mb-2">Google data</h2>
            <p>
              If you connect Google from Integrations, Helm requests read-only access to your{" "}
              <span className="text-white">Google Calendar</span> events so we can show meetings in your cockpit.
              We do not request Gmail access today. Nothing from Google is accessed until you explicitly connect the integration.
            </p>
          </section>

          <section>
            <h2 className="text-lg text-white font-normal tracking-tight mb-2">QuickBooks data</h2>
            <p>
              QuickBooks (Intuit) data is pulled only if and when you explicitly connect your QuickBooks account via
              Integrations. Nothing is accessed before that connection.
            </p>
          </section>

          <section>
            <h2 className="text-lg text-white font-normal tracking-tight mb-2">Payments</h2>
            <p>
              Paid subscriptions are processed by <span className="text-white">Paddle</span> as merchant of record.
              Paddle collects billing details and may share limited transaction and customer identifiers with us so we can
              activate and manage your plan. We do not store full card numbers on Helm servers.
              See our{" "}
              <Link to="/refunds" className="text-gold hover:underline">Refund &amp; Billing Policy</Link>{" "}
              and the{" "}
              <Link to="/app/billing" className="text-gold hover:underline">Billing</Link> page for plan details.
            </p>
          </section>

          <section>
            <h2 className="text-lg text-white font-normal tracking-tight mb-2">Email</h2>
            <p>
              Transactional emails (for example invitations or notices) are sent through{" "}
              <span className="text-white">Resend</span>. Email addresses and message metadata needed to deliver those
              emails are processed accordingly.
            </p>
          </section>

          <section>
            <h2 className="text-lg text-white font-normal tracking-tight mb-2">AI processing</h2>
            <p>
              Features such as document extraction, Ask Helm chat, and AI briefings/summaries may send relevant workspace
              content you provide to <span className="text-white">Anthropic (Claude)</span>. That context is used only to
              generate responses and suggested entries for your workspace. Do not submit data you are not authorized to
              process with third-party AI providers.
            </p>
          </section>

          <section>
            <h2 className="text-lg text-white font-normal tracking-tight mb-2">Cookies &amp; session</h2>
            <p>
              We use a session/auth cookie to keep you logged in. We do not use tracking or advertising cookies.
              A small local preference may also record that you dismissed our cookie notice. You can clear cookies and
              site data in your browser.
            </p>
          </section>

          <section>
            <h2 className="text-lg text-white font-normal tracking-tight mb-2">Analytics &amp; tracking</h2>
            <p>
              Helm does not currently integrate Google Analytics or any other web analytics or tracking tool.
              We do not run session-recording or advertising trackers in the product today.
            </p>
          </section>

          <section>
            <h2 className="text-lg text-white font-normal tracking-tight mb-2">Where data is stored</h2>
            <ul className="list-disc pl-5 space-y-2 mt-2">
              <li><span className="text-white">MongoDB Atlas</span> — primary database for account and business data</li>
              <li><span className="text-white">Cloudflare R2</span> — uploaded document files (private bucket)</li>
              <li><span className="text-white">Clerk</span> — authentication and login/session data</li>
              <li><span className="text-white">Anthropic</span> — processes uploaded documents and Ask Helm messages</li>
              <li><span className="text-white">Paddle</span> — payment processing</li>
              <li><span className="text-white">Resend</span> — transactional email</li>
              <li><span className="text-white">QuickBooks (Intuit)</span> — only for users who connect it</li>
            </ul>
          </section>

          <section>
            <h2 className="text-lg text-white font-normal tracking-tight mb-2">Retention &amp; deletion</h2>
            <p>
              When you delete your account, your data is wiped immediately — there is no retention period after deletion.
              You can export your data and delete your account yourself from{" "}
              <Link to="/app/settings" className="text-gold hover:underline">Account Settings</Link>
              {" "}(<span className="font-mono text-xs text-zinc-400">/app/settings</span>).
            </p>
          </section>

          <section>
            <h2 className="text-lg text-white font-normal tracking-tight mb-2">Governing law</h2>
            <p>
              This policy is governed by the laws of the Philippines. This may change once the business entity is
              formally registered in another jurisdiction.
            </p>
          </section>

          <section>
            <h2 className="text-lg text-white font-normal tracking-tight mb-2">Contact</h2>
            <p>
              Privacy questions:{" "}
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

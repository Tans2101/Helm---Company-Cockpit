import { Link } from "react-router-dom";

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
        <p className="text-zinc-500 text-sm mt-3">Last updated: August 2026 · Template for [COMPANY_NAME]</p>

        <div className="mt-10 space-y-8 text-[15px] text-zinc-300 leading-relaxed">
          <section>
            <h2 className="text-lg text-white font-normal tracking-tight mb-2">Who we are</h2>
            <p>
              This policy describes how [COMPANY_NAME] (“we”, “us”) collects and uses information when you use Helm,
              the CEO Operating System. Contact: <span className="text-gold">[CONTACT_EMAIL]</span>. Postal address: [COMPANY_ADDRESS].
            </p>
          </section>

          <section>
            <h2 className="text-lg text-white font-normal tracking-tight mb-2">Authentication</h2>
            <p>
              Helm uses Google sign-in through Helm’s own OAuth integration with Google. When you sign in, we receive basic account
              details such as your name, email address, and profile picture to create and secure your session. The same Google
              account maps to the same Helm user on every login.
            </p>
          </section>

          <section>
            <h2 className="text-lg text-white font-normal tracking-tight mb-2">Data we store</h2>
            <p>
              Workspace and product data (company settings, tasks, decisions, financial inputs, team membership, and related
              content you enter or sync) is stored in MongoDB on our behalf. We process this data to operate Helm for your workspace.
            </p>
          </section>

          <section>
            <h2 className="text-lg text-white font-normal tracking-tight mb-2">Payments</h2>
            <p>
              Paid subscriptions are processed by Paddle as merchant of record. Paddle collects billing details and may share
              limited transaction and customer identifiers with us so we can activate and manage your plan. We do not store full
              card numbers on Helm servers.
            </p>
          </section>

          <section>
            <h2 className="text-lg text-white font-normal tracking-tight mb-2">Email</h2>
            <p>
              Transactional and product emails (for example invitations or notices) may be sent through Resend. Email addresses
              and message metadata needed to deliver those emails are processed accordingly.
            </p>
          </section>

          <section>
            <h2 className="text-lg text-white font-normal tracking-tight mb-2">AI / LLM processing</h2>
            <p>
              Features such as Ask Helm, briefings, and recommendations may send relevant company data you provide or sync
              to large language models (including Claude) via Emergent’s AI infrastructure. That context is used to generate
              responses for your workspace. Do not submit data you are not authorized to process with third-party AI providers.
            </p>
          </section>

          <section>
            <h2 className="text-lg text-white font-normal tracking-tight mb-2">Cookies & session</h2>
            <p>
              We use session cookies and similar technologies to keep you signed in and protect the service. A small local
              preference may also record that you dismissed our cookie notice. You can clear cookies and site data in your browser.
            </p>
          </section>

          <section>
            <h2 className="text-lg text-white font-normal tracking-tight mb-2">Retention</h2>
            <p>
              We retain account and workspace data while your account is active and for a reasonable period afterward as needed
              for backups, security, and legal obligations. You may request deletion as described below.
            </p>
          </section>

          <section>
            <h2 className="text-lg text-white font-normal tracking-tight mb-2">AI disclosure</h2>
            <p>
              AI-generated output can be incomplete or incorrect. Helm’s AI features are assistive tools, not legal, financial,
              or professional advice. You remain responsible for decisions made using the product.
            </p>
          </section>

          <section>
            <h2 className="text-lg text-white font-normal tracking-tight mb-2">Your rights</h2>
            <p>
              Depending on your location, you may have rights to access, export, correct, or delete personal data associated
              with your account. In Helm you can export your data and request account deletion from Account Settings
              (<span className="font-mono text-xs text-zinc-400">/app/settings</span>), or contact us at [CONTACT_EMAIL].
            </p>
          </section>

          <section>
            <h2 className="text-lg text-white font-normal tracking-tight mb-2">Contact</h2>
            <p>
              Privacy questions: [CONTACT_EMAIL] · [COMPANY_NAME] · [COMPANY_ADDRESS].
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

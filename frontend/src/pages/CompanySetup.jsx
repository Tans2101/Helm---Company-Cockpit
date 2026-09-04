import { useState } from "react";
import { toast } from "sonner";
import {
  Building2, Users, Target, ChevronRight, ChevronLeft, Check,
  Crown, Rocket, Handshake, Briefcase, Award,
} from "lucide-react";
import { api } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { GlassCard } from "@/components/kit";
import { cn } from "@/lib/utils";
import {
  FOUNDER_ROLES, COMPANY_STAGES, INDUSTRIES, TEAM_SIZES, SETUP_STEPS,
} from "@/lib/companySetupCopy";

const ROLE_ICONS = {
  CEO: Crown,
  Founder: Rocket,
  "Co-founder": Handshake,
  "Managing Director": Briefcase,
  President: Award,
};

const currentYear = new Date().getFullYear();

export default function CompanySetup({ company }) {
  const { user } = useAuth();
  const [step, setStep] = useState(0);
  const [busy, setBusy] = useState(false);
  const [form, setForm] = useState({
    founder_title: company?.founder_title || "CEO",
    name: company?.name || "",
    industry: company?.industry || "",
    stage: company?.stage && company.stage !== "Series A" ? company.stage : "",
    employees: company?.employees > 0 ? company.employees : null,
    founded: company?.founded && company.founded !== "2022" ? company.founded : String(currentYear - 2),
    mission: company?.mission || "",
  });

  const set = (key, value) => setForm((f) => ({ ...f, [key]: value }));

  const teamSizeLabel = () => {
    const match = TEAM_SIZES.find((t) => t.value === form.employees);
    return match?.label || `${form.employees} people`;
  };

  const canNext = () => {
    if (step === 0) return !!form.founder_title;
    if (step === 1) return form.name.trim().length >= 2 && form.industry && form.stage;
    if (step === 2) return form.employees && form.founded?.length === 4;
    return true;
  };

  const submit = async () => {
    if (!form.name.trim()) {
      toast.error("Company name is required");
      setStep(1);
      return;
    }
    setBusy(true);
    try {
      await api.patch("/company", {
        name: form.name.trim(),
        industry: form.industry,
        stage: form.stage,
        employees: form.employees,
        founded: form.founded,
        mission: form.mission.trim(),
        founder_title: form.founder_title,
        company_setup_done: true,
      });
      window.location.href = "/app";
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Could not save company profile");
      setBusy(false);
    }
  };

  const firstName = user?.name?.split(" ")[0] || "there";

  return (
    <div className="min-h-screen grain flex flex-col">
      <div className="flex-1 flex flex-col items-center justify-center px-5 py-10 md:py-14">
        <div className="w-full max-w-2xl">
          {/* Header */}
          <div className="flex items-center gap-2.5 mb-8">
            <div className="w-9 h-9 rounded-md bg-gold/15 border border-gold/30 flex items-center justify-center">
              <span className="font-mono text-gold font-medium">H</span>
            </div>
            <div>
              <p className="text-white font-semibold tracking-tight leading-none">Helm</p>
              <p className="text-[10px] font-mono uppercase tracking-[0.2em] text-zinc-600 mt-1">Set up your company</p>
            </div>
          </div>

          <p className="font-mono text-xs uppercase tracking-[0.25em] text-gold">Welcome, {firstName}</p>
          <h1 className="mt-3 text-3xl md:text-4xl font-light tracking-tight text-white">
            Let's set up your company.
          </h1>
          <p className="mt-3 text-zinc-500 text-sm leading-relaxed max-w-lg">
            A few details so Helm can tailor your briefing, decisions, and AI to how you actually run the business.
          </p>

          {/* Progress */}
          <div className="mt-8 flex items-center gap-2">
            {SETUP_STEPS.map((s, i) => (
              <div key={s.id} className="flex-1 flex items-center gap-2">
                <div
                  className={cn(
                    "h-1 flex-1 rounded-full transition-colors",
                    i <= step ? "bg-gold" : "bg-white/10",
                  )}
                />
              </div>
            ))}
          </div>
          <p className="mt-2 text-[10px] font-mono uppercase tracking-wider text-zinc-600">
            Step {step + 1} of {SETUP_STEPS.length} · {SETUP_STEPS[step].label}
          </p>

          <GlassCard className="mt-6 p-6 md:p-8 fade-up" glow>
            {/* Step 0: Role */}
            {step === 0 && (
              <div>
                <div className="flex items-center gap-3 mb-6">
                  <div className="w-10 h-10 rounded-xl bg-gold/10 border border-gold/25 flex items-center justify-center">
                    <Crown className="w-5 h-5 text-gold" />
                  </div>
                  <div>
                    <h2 className="text-lg text-white tracking-tight">What's your role?</h2>
                    <p className="text-xs text-zinc-500 mt-0.5">Helm is built for leaders who run the company.</p>
                  </div>
                </div>
                <div className="grid gap-2">
                  {FOUNDER_ROLES.map((role) => {
                    const Icon = ROLE_ICONS[role.id] || Crown;
                    const on = form.founder_title === role.id;
                    return (
                      <button
                        key={role.id}
                        type="button"
                        data-testid={`role-${role.id}`}
                        onClick={() => set("founder_title", role.id)}
                        className={cn(
                          "flex items-start gap-3 rounded-lg border px-4 py-3.5 text-left transition-colors",
                          on
                            ? "border-gold/40 bg-gold/[0.06]"
                            : "border-white/10 bg-white/[0.02] hover:border-white/20",
                        )}
                      >
                        <Icon className={cn("w-4 h-4 shrink-0 mt-0.5", on ? "text-gold" : "text-zinc-500")} />
                        <div className="min-w-0 flex-1">
                          <p className={cn("text-sm font-medium", on ? "text-white" : "text-zinc-300")}>{role.label}</p>
                          <p className="text-xs text-zinc-600 mt-0.5">{role.hint}</p>
                        </div>
                        {on && <Check className="w-4 h-4 text-gold shrink-0" />}
                      </button>
                    );
                  })}
                </div>
              </div>
            )}

            {/* Step 1: Company */}
            {step === 1 && (
              <div>
                <div className="flex items-center gap-3 mb-6">
                  <div className="w-10 h-10 rounded-xl bg-gold/10 border border-gold/25 flex items-center justify-center">
                    <Building2 className="w-5 h-5 text-gold" />
                  </div>
                  <div>
                    <h2 className="text-lg text-white tracking-tight">About your company</h2>
                    <p className="text-xs text-zinc-500 mt-0.5">Name, industry, and stage — the basics for your cockpit.</p>
                  </div>
                </div>
                <div className="space-y-5">
                  <label className="block text-xs text-zinc-500">
                    Company name
                    <input
                      data-testid="setup-company-name"
                      value={form.name}
                      onChange={(e) => set("name", e.target.value)}
                      placeholder="Acme Inc."
                      className="mt-1 w-full rounded-md border border-white/10 bg-[#141417] text-white text-sm px-3 py-2.5 focus:outline-none focus:border-gold/40"
                    />
                  </label>
                  <div>
                    <p className="text-xs text-zinc-500 mb-2">Industry</p>
                    <div className="flex flex-wrap gap-2">
                      {INDUSTRIES.map((ind) => (
                        <button
                          key={ind}
                          type="button"
                          data-testid={`industry-${ind}`}
                          onClick={() => set("industry", ind)}
                          className={cn(
                            "rounded-full px-3 py-1.5 text-xs transition-colors border",
                            form.industry === ind
                              ? "border-gold/40 bg-gold/10 text-gold"
                              : "border-white/10 text-zinc-500 hover:border-white/20 hover:text-zinc-300",
                          )}
                        >
                          {ind}
                        </button>
                      ))}
                    </div>
                  </div>
                  <div>
                    <p className="text-xs text-zinc-500 mb-2">Stage</p>
                    <div className="flex flex-wrap gap-2">
                      {COMPANY_STAGES.map((st) => (
                        <button
                          key={st}
                          type="button"
                          data-testid={`stage-${st}`}
                          onClick={() => set("stage", st)}
                          className={cn(
                            "rounded-full px-3 py-1.5 text-xs transition-colors border",
                            form.stage === st
                              ? "border-gold/40 bg-gold/10 text-gold"
                              : "border-white/10 text-zinc-500 hover:border-white/20 hover:text-zinc-300",
                          )}
                        >
                          {st}
                        </button>
                      ))}
                    </div>
                  </div>
                </div>
              </div>
            )}

            {/* Step 2: Team */}
            {step === 2 && (
              <div>
                <div className="flex items-center gap-3 mb-6">
                  <div className="w-10 h-10 rounded-xl bg-gold/10 border border-gold/25 flex items-center justify-center">
                    <Users className="w-5 h-5 text-gold" />
                  </div>
                  <div>
                    <h2 className="text-lg text-white tracking-tight">Team & context</h2>
                    <p className="text-xs text-zinc-500 mt-0.5">Helm calibrates runway views and planning defaults to your size.</p>
                  </div>
                </div>
                <div className="space-y-5">
                  <div>
                    <p className="text-xs text-zinc-500 mb-2">Team size</p>
                    <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
                      {TEAM_SIZES.map((t) => (
                        <button
                          key={t.label}
                          type="button"
                          data-testid={`team-${t.label}`}
                          onClick={() => set("employees", t.value)}
                          className={cn(
                            "rounded-lg border px-3 py-2.5 text-sm transition-colors",
                            form.employees === t.value
                              ? "border-gold/40 bg-gold/10 text-gold"
                              : "border-white/10 text-zinc-400 hover:border-white/20",
                          )}
                        >
                          {t.label}
                        </button>
                      ))}
                    </div>
                  </div>
                  <label className="block text-xs text-zinc-500">
                    Founded
                    <input
                      data-testid="setup-founded"
                      value={form.founded}
                      onChange={(e) => set("founded", e.target.value.replace(/\D/g, "").slice(0, 4))}
                      placeholder="2022"
                      className="mt-1 w-32 rounded-md border border-white/10 bg-[#141417] text-white text-sm px-3 py-2.5 font-mono focus:outline-none focus:border-gold/40"
                    />
                  </label>
                  <label className="block text-xs text-zinc-500">
                    Mission <span className="text-zinc-700">(optional)</span>
                    <textarea
                      data-testid="setup-mission"
                      value={form.mission}
                      onChange={(e) => set("mission", e.target.value)}
                      placeholder="What does your company do in one line?"
                      rows={2}
                      className="mt-1 w-full rounded-md border border-white/10 bg-[#141417] text-white text-sm px-3 py-2.5 resize-none focus:outline-none focus:border-gold/40"
                    />
                  </label>
                </div>
              </div>
            )}

            {/* Step 3: Review */}
            {step === 3 && (
              <div>
                <div className="flex items-center gap-3 mb-6">
                  <div className="w-10 h-10 rounded-xl bg-gold/10 border border-gold/25 flex items-center justify-center">
                    <Target className="w-5 h-5 text-gold" />
                  </div>
                  <div>
                    <h2 className="text-lg text-white tracking-tight">Ready to go</h2>
                    <p className="text-xs text-zinc-500 mt-0.5">Review your profile, then we'll set up your cockpit.</p>
                  </div>
                </div>
                <dl className="space-y-3 text-sm">
                  {[
                    ["Your role", form.founder_title],
                    ["Company", form.name],
                    ["Industry", form.industry],
                    ["Stage", form.stage],
                    ["Team size", teamSizeLabel()],
                    ["Founded", form.founded],
                    ...(form.mission ? [["Mission", form.mission]] : []),
                  ].map(([label, value]) => (
                    <div key={label} className="flex gap-4 py-2 border-b border-white/[0.04] last:border-0">
                      <dt className="w-28 shrink-0 text-zinc-600 text-xs font-mono uppercase tracking-wider pt-0.5">{label}</dt>
                      <dd className="text-zinc-200">{value}</dd>
                    </div>
                  ))}
                </dl>
                <p className="mt-5 text-xs text-zinc-600 leading-relaxed">
                  Next you'll choose whether to explore with sample data or start clean — then activate Helm when you're ready.
                </p>
              </div>
            )}

            {/* Navigation */}
            <div className="flex gap-2 mt-8 pt-6 border-t border-white/[0.06]">
              {step > 0 ? (
                <button
                  type="button"
                  onClick={() => setStep((s) => s - 1)}
                  className="inline-flex items-center gap-1.5 rounded-md border border-white/10 text-zinc-300 text-sm px-4 py-2.5 hover:bg-white/5 transition-colors"
                >
                  <ChevronLeft className="w-4 h-4" /> Back
                </button>
              ) : (
                <div />
              )}
              {step < SETUP_STEPS.length - 1 ? (
                <button
                  type="button"
                  data-testid="setup-next-btn"
                  onClick={() => canNext() && setStep((s) => s + 1)}
                  disabled={!canNext()}
                  className="flex-1 inline-flex items-center justify-center gap-1.5 rounded-md bg-gold text-black font-medium text-sm px-4 py-2.5 hover:bg-gold-hover transition-colors disabled:opacity-40"
                >
                  Continue <ChevronRight className="w-4 h-4" />
                </button>
              ) : (
                <button
                  type="button"
                  data-testid="setup-finish-btn"
                  onClick={submit}
                  disabled={busy}
                  className="flex-1 inline-flex items-center justify-center gap-1.5 rounded-md bg-gold text-black font-medium text-sm px-4 py-2.5 hover:bg-gold-hover transition-colors disabled:opacity-60"
                >
                  {busy ? "Saving…" : "Set up my cockpit"}
                </button>
              )}
            </div>
          </GlassCard>
        </div>
      </div>
    </div>
  );
}

/** Shared Clerk SignIn/SignUp appearance — Helm dark marketing (ink/cream/gold). */
import palette from "@/design/palette.json";

export const clerkAppearance = {
  variables: {
    colorBackground: palette.ink,
    colorInputBackground: palette.inkCard,
    colorInputText: palette.cream,
    colorText: palette.cream,
    colorTextSecondary: palette.slate,
    colorPrimary: palette.gold,
    colorDanger: palette.statusNegative,
    colorNeutral: palette.slate,
    colorShimmer: palette.inkCard,
    borderRadius: "0.5rem",
    fontFamily: "inherit",
  },
  elements: {
    rootBox: "w-full",
    card: "bg-transparent shadow-none border-0 p-0",
    headerTitle: "text-helm-cream font-normal tracking-tight",
    headerSubtitle: "text-helm-slate",
    socialButtonsBlockButton:
      "bg-helm-gold text-helm-navy font-medium border-0 hover:bg-helm-gold-hover",
    socialButtonsBlockButtonText: "text-helm-navy font-medium",
    formButtonPrimary: "bg-helm-gold text-helm-navy font-medium hover:bg-helm-gold-hover",
    footerActionLink: "text-helm-gold hover:text-helm-gold-hover",
    identityPreviewEditButton: "text-helm-gold",
    formFieldLabel: "text-helm-slate",
    formFieldInput:
      "bg-helm-ink-card border-helm-cream/15 text-helm-cream caret-helm-gold placeholder:text-helm-slate",
    formFieldInput__input:
      "bg-helm-ink-card border-helm-cream/15 text-helm-cream caret-helm-gold placeholder:text-helm-slate",
    formFieldInputShowPasswordButton: "text-helm-slate hover:text-helm-cream",
    otpCodeFieldInputs: "justify-center gap-2",
    otpCodeFieldInput:
      "bg-helm-ink-card border border-helm-cream/20 text-helm-cream text-lg font-mono caret-helm-gold",
    otpCodeFieldInput__input: "text-helm-cream bg-helm-ink-card",
    formResendCodeLink: "text-helm-gold hover:text-helm-gold-hover",
    dividerLine: "bg-helm-cream/10",
    dividerText: "text-helm-slate",
    alertText: "text-helm-cream",
    formFieldErrorText: "text-helm-status-negative",
  },
};

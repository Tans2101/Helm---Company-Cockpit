/** Shared Clerk SignIn/SignUp appearance — Helm dark + gold, readable inputs/OTP. */
export const clerkAppearance = {
  variables: {
    colorBackground: "#09090b",
    colorInputBackground: "#141417",
    colorInputText: "#ffffff",
    colorText: "#ffffff",
    colorTextSecondary: "#a1a1aa",
    colorPrimary: "#c9a962",
    colorDanger: "#f43f5e",
    colorNeutral: "#a1a1aa",
    colorShimmer: "#27272a",
    borderRadius: "0.5rem",
    fontFamily: "inherit",
  },
  elements: {
    rootBox: "w-full",
    card: "bg-transparent shadow-none border-0 p-0",
    headerTitle: "text-white font-normal tracking-tight",
    headerSubtitle: "text-zinc-500",
    socialButtonsBlockButton:
      "bg-gold text-black font-medium border-0 hover:bg-[#d4b56e]",
    socialButtonsBlockButtonText: "text-black font-medium",
    formButtonPrimary: "bg-gold text-black font-medium hover:bg-[#d4b56e]",
    footerActionLink: "text-gold hover:text-[#d4b56e]",
    identityPreviewEditButton: "text-gold",
    formFieldLabel: "text-zinc-400",
    formFieldInput:
      "bg-[#141417] border-white/15 text-white caret-[#c9a962] placeholder:text-zinc-500",
    formFieldInput__input:
      "bg-[#141417] border-white/15 text-white caret-[#c9a962] placeholder:text-zinc-500",
    formFieldInputShowPasswordButton: "text-zinc-400 hover:text-white",
    otpCodeFieldInputs: "justify-center gap-2",
    otpCodeFieldInput:
      "bg-[#141417] border border-white/20 text-white text-lg font-mono caret-[#c9a962] !text-white",
    otpCodeFieldInput__input: "text-white bg-[#141417]",
    formResendCodeLink: "text-gold hover:text-[#d4b56e]",
    dividerLine: "bg-white/10",
    dividerText: "text-zinc-500",
    alertText: "text-zinc-300",
    formFieldErrorText: "text-rose-400",
  },
};

/** Shared Clerk SignIn appearance — matches Helm dark + gold. */
export const clerkAppearance = {
  variables: {
    colorBackground: "#09090b",
    colorInputBackground: "#141417",
    colorText: "#ffffff",
    colorTextSecondary: "#a1a1aa",
    colorPrimary: "#c9a962",
    colorDanger: "#f43f5e",
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
    formFieldInput: "bg-[#141417] border-white/10 text-white",
    dividerLine: "bg-white/10",
    dividerText: "text-zinc-500",
  },
};

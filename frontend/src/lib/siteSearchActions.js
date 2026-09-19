/** Public marketing pages available from the ⌘K quick-nav search.

Omit /integrations — the in-app Settings → Integrations page already covers
connecting tools; the public marketing page stays in nav/footer only.
*/
export const SITE_SEARCH_ACTIONS = [
  {
    id: "about",
    label: "About",
    to: "/about",
    description: "Site",
    keywords: ["about helm", "company", "mission", "founder", "story"],
  },
  {
    id: "features",
    label: "Features",
    to: "/features",
    description: "Site",
    keywords: ["product", "modules", "cockpit", "what helm includes"],
  },
  {
    id: "help",
    label: "Help",
    to: "/help",
    description: "Site",
    keywords: ["docs", "how to", "guide", "faq"],
  },
  {
    id: "security-page",
    label: "Security",
    to: "/security",
    description: "Site",
    keywords: ["trust", "encryption", "privacy"],
  },
  {
    id: "terms",
    label: "Terms of Service",
    to: "/terms",
    description: "Site",
    keywords: ["tos", "legal", "terms"],
  },
  {
    id: "privacy",
    label: "Privacy Policy",
    to: "/privacy",
    description: "Site",
    keywords: ["legal", "data", "gdpr"],
  },
  {
    id: "refunds",
    label: "Refunds",
    to: "/refunds",
    description: "Site",
    keywords: ["billing", "cancel", "trial", "money back"],
  },
];

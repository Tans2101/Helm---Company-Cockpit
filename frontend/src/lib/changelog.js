/**
 * Public changelog loader.
 *
 * Source of truth: ./changelog.json — hand-edited only.
 * Do NOT generate, append, or sync this file from git history, CI, deploys,
 * webhooks, or cron. New entries are an explicit content edit (same as
 * marketingCopy.js), whenever Tansher chooses to publish one.
 */
import data from "./changelog.json";

export const CHANGELOG_INTRO = data.intro;

/** Newest first — by date string (YYYY-MM-DD), then original file order for ties. */
export function getChangelogEntries() {
  const entries = Array.isArray(data.entries) ? [...data.entries] : [];
  return entries.sort((a, b) => {
    const byDate = String(b.date || "").localeCompare(String(a.date || ""));
    if (byDate !== 0) return byDate;
    return 0;
  });
}

/** @deprecated Prefer getChangelogEntries() — kept for tests expecting a static array. */
export const CHANGELOG_ENTRIES = getChangelogEntries();

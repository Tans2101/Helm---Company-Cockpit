/**
 * Helm visual identity — named colors from palette.json.
 *
 * Brand (use these names in UI):
 *   helm-navy  — primary text, icons, line work, headings (foreground, never a page fill)
 *   helm-gold  — accent only (active states, small callouts, key borders)
 *   helm-slate — muted text, captions, borders
 *   helm-cream — primary light background
 *
 * FLAG — extra keys, not the four-color print palette:
 *   ink / inkCard — original near-black dark surfaces (#09090b / #121214)
 *   goldHover — derived gold for hover
 *   status* — meaning colors for deltas/errors, not brand
 */
const palette = require("./palette.json");

const HELM_PALETTE = {
  navy: palette.navy,
  gold: palette.gold,
  slate: palette.slate,
  cream: palette.cream,
};

const HELM_FLAGGED = {
  ink: palette.ink,
  inkCard: palette.inkCard,
  goldHover: palette.goldHover,
  statusPositive: palette.statusPositive,
  statusNegative: palette.statusNegative,
  statusWarning: palette.statusWarning,
};

module.exports = { HELM_PALETTE, HELM_FLAGGED, palette };

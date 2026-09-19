/**
 * Trenston visual identity — named colors from palette.json.
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
 *
 * Opacity conventions (Tailwind suffixes on helm-gold / helm-muted / helm-status-*):
 *   /12  — light background tint (badges, chips, highlighted rows): bg-helm-{token}/12
 *   /35  — border on a tinted element (or matching outline control): border-helm-{token}/35
 *   /10  — hover wash on outline controls only: hover:bg-helm-{token}/10
 *   /40  — focus ring on inputs only: focus:border-helm-gold/40
 *   (no suffix) — full-strength text and solid accents: text-helm-gold, bg-helm-gold
 *
 * Do not invent other opacities for those purposes — pick from this list so
 * department pages stay visually consistent. Meter fills (e.g. /70 progress)
 * and overlay scrims (e.g. bg-helm-ink/70) are separate concerns.
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

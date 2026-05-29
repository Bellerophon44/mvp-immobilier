# Cohérence — Web UI kit

A high-fidelity recreation of the Next.js single-page analyzer described in the brief.

## Surface

A single page. Three states:

1. **Idle / hero** — wordmark, single tagline, the input (URL or raw text), the *Analyser l'annonce* CTA, and a small "Comment ça marche" disclosure.
2. **Analyzing** — input collapses into a chip at the top, the score-ring placeholder draws an indeterminate sweep, and three pillar placeholders show a skeleton state.
3. **Result** — score-ring + verdict label, the two pillars (prix, sémantique), the "À vérifier" checklist, the comparables table, the "Leviers de négociation" pull-quotes, and the report-copy action.

## Components

- `Wordmark.jsx` — the logo
- `ScopeBadge.jsx` — the "Metz · Moselle" map-pin chip in the top bar
- `AnalyzerInput.jsx` — URL/text input + CTA, the centerpiece on idle
- `ScoreRing.jsx` — the iconic 132-px ring with the count-up numeral
- `VerdictHeader.jsx` — score ring + label + summary
- `PillarBar.jsx` — one pillar (prix or sémantique) with bar fill
- `ChecklistCard.jsx` — "à vérifier" / "questions" list
- `ComparablesTable.jsx` — retained comparables
- `LeversList.jsx` — "leviers de négociation" pull-quotes
- `Footer.jsx` — scope reminder + privacy line
- `App.jsx` — composes the page and owns the idle / analyzing / result state machine

`index.html` is the interactive prototype — paste-and-analyze with a deterministic mock response.

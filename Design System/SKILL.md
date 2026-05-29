---
name: coherence-design
description: Use this skill to generate well-branded interfaces and assets for Cohérence (the French real-estate listing-coherence analyzer, MVP Metz/Moselle), either for production or throwaway prototypes/mocks/etc. Contains essential design guidelines, colors, type, fonts, assets, and UI kit components for prototyping.
user-invocable: true
---

# Cohérence design skill

Read `README.md` for the full design system: brand voice, content fundamentals, visual foundations, iconography, and the file index. `CAVEATS.md` lists the open questions still owed to the product team — surface these any time you're about to make a major creative decision.

Then explore what's available:

- `colors_and_type.css` — every design token (color, type, spacing, motion, radii). Import it once at the root of any HTML page you build.
- `assets/` — logo wordmark, mark, favicon, and the seven brand icons (1.5 px stroke SVGs).
- `preview/` — Design System reference cards. Look here to understand how a token *should* be used in context.
- `ui_kits/web/` — the single-page Next.js analyzer recreated as a static prototype. Reusable JSX components: `Wordmark`, `ScopeBadge`, `AnalyzerInput`, `ScoreRing`, `VerdictHeader`, `PillarBar`, `ChecklistCard`, `ComparablesTable`, `LeversList`, `Footer`. Open `ui_kits/web/index.html` to see them composed.
- `ui_kits/api/` — the brand-styled API reference for `POST /analyze`. Components: `MethodPill`, `EndpointHeader`, `JsonBlock`, `SchemaTable`, `EnvList`, `RubricCard`.

## Working principles, short form

- **French, vouvoiement, never tu.** Numbers carry the argument; adjectives only frame.
- **Verdict words, not emoji.** No emoji *anywhere*. Use the brand diamond filled in the verdict color, or no glyph.
- **All numerics are monospaced and tabular** (`var(--font-mono)` + `font-variant-numeric: tabular-nums`).
- **One accent: brick.** No blue, no purple, no gradients, no pastels. Greens and ochres are reserved for verdict signals.
- **One elevation.** `var(--shadow-card)` = hairline border + 1 px lift. Nothing else.
- **One animation worth doing**: the score ring counting up from 0 to its value on result load.

## When invoked

If the user invokes this skill without other guidance, ask them what they want to build or design — typical asks include a marketing page, an embed widget, a "verdict card" social share, a deck slide, a printed PDF report, or an extension of the API kit. Ask a few short questions (audience, surface, length, whether French/vouvoiement strict, fidelity) before producing HTML.

For visual artefacts (slides, mocks, throwaway prototypes), copy assets out of `assets/` and produce a self-contained HTML file. For production-code handoff, lift the tokens from `colors_and_type.css` and the JSX components from `ui_kits/`.

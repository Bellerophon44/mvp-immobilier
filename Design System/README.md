# Cohérence — Design System

> *Ce prix et cette annonce sont-ils cohérents avec le marché local ?*

**Cohérence** is the working brand for an MVP real-estate listing-coherence analyzer aimed at private buyers in France (currently scoped to **Metz / Moselle**). A buyer pastes a listing (URL or raw text), and Cohérence returns a single coherence score (0–100), a verdict, three pillar breakdowns, and concrete next steps.

The product is a single-page tool, not a portal. The brand should feel like a **trusted, calm second opinion** — closer to a notary's letter than a property aggregator.

---

## Product context (from brief)

| Surface | Stack | Role |
|---|---|---|
| **Frontend** | Next.js App Router on Vercel | One page: text/URL field → "Analyser" → results |
| **Backend** | FastAPI + Docker on Railway, port `8000` | Single endpoint `POST /analyze` |
| **Storage** | SQLite `comparables.db` | Local comparables, Metz only |
| **LLM** | OpenAI `gpt-4.1-mini`, JSON mode, temp 0.2 | Semantic analysis, SHA-256 cache TTL 7d |

### `POST /analyze` flow

```
raw_text → run_full_analysis()
            ├─ analyze_semantic()          → verdict, summary, risk_level,
            │  (gpt-4.1-mini, JSON mode)     to_check, questions, levers
            ├─ compute_price_market_pillar()→ median_price_m2, position,
            │  (SQLite, ±20% surface,        confidence, q1, q3
            │   min 3 comparables)
            └─ compute_global_score()      → 0–100 + verdict
                                             (40 pts prix + 60 pts sémantique)
```

### Scoring rubric

**Pilier Prix — 40 pts**
- Aligné (±10 %) → 35
- Légèrement sur-positionné (+10–25 %) → 25
- Fortement sur-positionné (>+25 %) → 10
- Sous-positionné (<−10 %) → 30

**Pilier Sémantique — 60 pts** — combinaison `verdict` × `risk_level`.

**Verdict final**

| Score | Verdict |
|---|---|
| 75–100 | Favorable |
| 55–74 | À creuser |
| 35–54 | Prudence |
| 0–34 | Déconseillé |

### MVP constraints
- Geography: **Metz / Moselle only**.
- No price estimation, no DVF / notaires data.
- No automated tests; manual validation via Swagger `/docs`.
- LLM cache in-memory only; lost on restart.
- SQLite, no migrations.

---

## Sources provided

- A written product brief, pasted in chat. **No codebase, Figma, or visual artefacts were attached.** The brand identity in this system is therefore an original interpretation; treat every visual decision as a starting hypothesis to be revised once real product context exists.
- See [`/CAVEATS.md`](./CAVEATS.md) for a list of decisions that need confirmation.

---

## CONTENT FUNDAMENTALS

The product speaks **French**, in the register a notary or independent buyer's-agent would use with a client they respect. Calm, factual, never salesy.

### Voice principles

1. **Le vouvoiement, toujours.** This is a financial decision with real stakes — "vous", never "tu". The product addresses the buyer as an adult peer.
2. **Le produit ne donne pas d'ordre.** It surfaces what is *cohérent* or non; the buyer decides. Use *« à vérifier »*, *« à creuser »*, *« point d'attention »*, not *« mauvais »* or *« évitez »*.
3. **Chiffres avant adjectifs.** A median of 3 420 €/m² says more than "trop cher". Numbers carry the argument; adjectives only frame them.
4. **Phrases courtes, sujet en tête.** Short sentences. Subject-first. No marketing flourish.
5. **Pas de jargon non expliqué.** "Médiane", "comparable", "scope" — define on first use or replace.

### Casing & typography rules

- Verdict labels are **Title Case in French style**: *Favorable*, *À creuser*, *Prudence*, *Déconseillé*. The capital on the leading letter only.
- UI buttons: full lowercase French sentence-case — *Analyser l'annonce*, not *ANALYSER*.
- Section headings: sentence case — *Pilier prix*, *Pilier sémantique*, *Pilier global*.
- Numbers use **non-breaking spaces** as thousands separator and **a comma** as decimal: `3 420,50 €/m²`, `±20 %`. The `€` has a non-breaking space before it.
- Percentages: `+18 %`, `−7 %`. Use the real minus sign `−`, not a hyphen, in data displays.
- Quotation marks: French guillemets *« … »* with non-breaking spaces inside.

### Lexicon — preferred terms

| Use | Avoid |
|---|---|
| une annonce | une fiche, un listing |
| cohérent / cohérence | bon, mauvais, normal |
| à creuser, à vérifier | suspect, louche |
| comparables | similaires, équivalents |
| levier de négociation | argument, astuce |
| point d'attention | warning, alerte rouge |
| médiane locale | prix moyen |
| score de cohérence | note, rating |

### Tone examples

- ✅ « Ce bien se situe **18 % au-dessus** de la médiane locale pour cette surface. À creuser avant de visiter. »
- ❌ « ⚠️ Attention, ce bien est BEAUCOUP trop cher !! »
- ✅ « 4 comparables retenus dans un rayon de 1,5 km, surface ±20 %. »
- ❌ « On a trouvé 4 biens similaires près de là. »
- ✅ Button: *Analyser l'annonce* · *Voir les comparables* · *Copier le rapport*
- ❌ Button: *GO !* · *Découvrir* · *C'est parti*

### Emoji & ornament

**No emoji.** Anywhere. Not in copy, not in component states, not in error messages. The product needs to read as a quiet professional service — a `⚠️` warning glyph in a verdict would undo the entire tone.

For inline emphasis, use the dedicated icon set (see [Iconography](#iconography)). For typographic ornament, the only flourish allowed is the section rule (`────`) and the verdict diamond (`◆`) used in the Cohérence wordmark.

---

## VISUAL FOUNDATIONS

The visual language is **editorial-analytical**: it borrows from French print culture (newspapers, notarial documents, real-estate price-bulletins) more than from product-design tropes. Think *Le Monde*'s data pages, not a SaaS landing page.

### Palette

| Role | Token | Hex | Notes |
|---|---|---|---|
| Ink (primary text) | `--ink` | `#1A1814` | Warm near-black, never `#000`. |
| Parchment (base) | `--parchment` | `#F5F1EA` | The default page bg. Slight cream. |
| Paper (cards) | `--paper` | `#FBF8F2` | Slightly lighter than parchment, used for elevated surfaces. |
| Stone (borders, muted text) | `--stone` | `#8B8275` | The only neutral gray; warm. |
| Stone-line (hairlines) | `--stone-line` | `#D9D2C5` | 1px rules and dividers. |
| Brick (accent) | `--brick` | `#B5462F` | The single brand accent. Used for the wordmark diamond, the primary CTA, and the *Prudence* verdict. |
| Brick-deep | `--brick-deep` | `#6B2018` | *Déconseillé* verdict, hover state of brick CTAs. |
| Moss (positive) | `--moss` | `#2E6E4F` | *Favorable* verdict only. |
| Ochre (neutral signal) | `--ochre` | `#C28B3C` | *À creuser* verdict, "À vérifier" tags. |
| Jaumont (local seal) | `--jaumont` | `#C9A14A` | **Édition Metz only.** Or de la pierre de Jaumont — the honey-gold limestone Metz is actually built from. Reserved for the "contexte local" seal; **not** an action accent. |

There is **no blue, no purple, no gradient, no pastel**. The palette is intentionally earth-tone. The brick accent gives the brand its edge; the **Jaumont gold** is the authentic colour of Metz stone (« la ville jaune ») and carries the local seal of each *édition*. See [`/docs/brand/METZ-LOCAL.md`](../docs/brand/METZ-LOCAL.md) and [`/docs/brand/LOCAL-ANCHORING.md`](../docs/brand/LOCAL-ANCHORING.md).

### Typography

- **Display / serif:** *Instrument Serif* — used for the wordmark, the score numeral, and section openers. Italic variant for pull-quotes and the verdict label. *(Substitution flag: pulled from Google Fonts CDN. If a paid editorial serif is preferred, swap here.)*
- **UI / sans:** *Geist* — all body, labels, buttons, form text. 400 / 500 / 600 weights.
- **Numeric / mono:** *Geist Mono* — every price, percentage, m², median, and score. **All numeric data is monospaced** so columns of figures align without manual tabular tricks.

Type sizes follow a 1.25 modular scale anchored at 16 px body. See `colors_and_type.css` for the full ramp.

### Spacing & rhythm

- Base unit: **4 px**. Spacing scale: 4 / 8 / 12 / 16 / 24 / 32 / 48 / 64 / 96.
- Vertical rhythm: most surfaces sit on a 24 px baseline; data tables drop to 20 px.
- Page gutters: 24 px mobile, 64 px desktop.

### Backgrounds, borders, shadows

- **Backgrounds:** flat parchment. No imagery behind UI, no gradients, no patterns. The one exception is the marketing hero, which can carry a single full-bleed black-and-white architectural photograph (typical Metz limestone façade) with a parchment scrim at 70 % opacity over the bottom half.
- **Borders:** 1 px `--stone-line`. That is the only border weight. Cards either sit on a hairline border *or* on a 1 px `--paper` fill against parchment — never both.
- **Corner radii:** `--radius-sm: 2px` (inputs, chips), `--radius-md: 4px` (cards, buttons), `--radius-lg: 8px` (the result card, the score ring). Nothing rounder than 8 px. **No pill buttons.**
- **Shadows:** one elevation only — `--shadow-card: 0 1px 0 rgba(26,24,20,0.04), 0 0 0 1px var(--stone-line)`. It's a hairline + a 1-px lift. No drop shadows beyond that. Modals use a parchment scrim at 88 % opacity instead of a shadow.

### Motion

- **Default ease:** `cubic-bezier(0.32, 0.08, 0.24, 1)` — a calm, slow-out curve. Stored as `--ease-paper`.
- **Durations:** 120 ms for hover, 200 ms for state changes, 320 ms for the score-ring fill-in (the only "animated reveal" in the product), 480 ms for page transitions.
- **No bounces. No spring physics. No parallax.** The single deliberate animation is the score ring drawing itself from 0 to its value on result-load, eased linearly so the number feels *counted*, not *bounced*.

### States

- **Hover** on interactive elements: text turns from `--ink` to `--brick`; backgrounds darken by 4 % (use `color-mix(in oklab, var(--paper), var(--ink) 4%)`). Never an opacity change — opacity feels disabled.
- **Press:** the element scales to `0.99` and the background darkens an extra 2 %. Duration 80 ms.
- **Focus:** 2 px `--brick` outline, 2 px offset, never the browser's default blue.
- **Disabled:** 40 % opacity of the ink color, no border change. Cursor `not-allowed`.

### Transparency & blur

Used sparingly. The only allowed `backdrop-filter` is on the sticky top bar when the page scrolls — `backdrop-filter: blur(8px); background: color-mix(in oklab, var(--parchment), transparent 20%)`. No glassmorphism anywhere else.

### Imagery vibe

If photography is used, it is **black-and-white, slightly warm-toned, grainy**, depicting French stone architecture (Metz limestone, Mosellan ardoise rooftops). Never stock interiors with happy couples. Never drone shots. Photography is a frame, not a subject.

### Cards

A card is a `--paper` fill on a `--parchment` background, with a 1 px `--stone-line` border, 4 px radius, and 24 px padding. The card title is a small-caps sans label in `--stone`; the content is ink. **No card has an icon in its corner**; iconography lives inline with text.

### Layout rules

- The result page is a single column, max-width 720 px, centered. Even on a 1440 px monitor it stays narrow — the brand wants the user to read, not scan dashboards.
- The score ring is always top-left of the result card, the verdict label inline to its right. Always.
- Forms are full-width to their column. Inputs are never side-by-side.

---

## ICONOGRAPHY

The brand uses a **small, custom set of inline SVG marks**, not a general-purpose icon font. Icons are 1.5 px stroke, no fill, set in `--stone` by default and `--brick` when active. Sizes are 16 px (inline with body), 20 px (form fields), or 24 px (verdict markers).

The set is intentionally tiny because the product surface is small. Current set:

- **diamond** — the wordmark mark, used alone as a favicon, as the score-ring center dot, and as the inline bullet for verdict points. (`assets/icons/diamond.svg`)
- **arrow-right** — for "Analyser" CTA, and "Voir les comparables" links. (`assets/icons/arrow-right.svg`)
- **link** — to indicate the input accepts a URL. (`assets/icons/link.svg`)
- **map-pin** — for the Metz scope marker and comparables locations. (`assets/icons/map-pin.svg`)
- **scales** — the comparables / median icon. (`assets/icons/scales.svg`)
- **square-check** — "à vérifier" checklist items. (`assets/icons/square-check.svg`)
- **copy** — copy-rapport button. (`assets/icons/copy.svg`)

> **Substitution flag:** the seven icons in this system are originals drawn at 1.5 px stroke to match the brand's editorial register. If a CDN set is preferred for breadth, the closest match in tone and weight is [Lucide](https://lucide.dev) at `stroke-width: 1.5`. **Do not mix sets** — pick one.

**No emoji is ever used as iconography.** No unicode glyphs either (no ⚠ / ✓ / ★). The verdict states use either the wordmark **diamond** filled in `--moss` / `--ochre` / `--brick` / `--brick-deep`, or no icon at all — the verdict word does the work.

---

## Index — files in this design system

```
/
├── README.md                       ← this file
├── CAVEATS.md                      ← open questions for the user
├── SKILL.md                        ← skill manifest (cross-compatible with Agent Skills)
├── colors_and_type.css             ← tokens, type ramp, semantic vars
├── assets/
│   ├── logo-wordmark.svg
│   ├── logo-mark.svg
│   ├── favicon.svg
│   └── icons/                      ← the 7-icon brand set
├── preview/                        ← Design System tab cards
├── ui_kits/
│   ├── web/                        ← Next.js single-page analyzer recreation
│   │   ├── index.html              ← interactive prototype
│   │   ├── README.md
│   │   └── *.jsx                   ← components
│   └── api/                        ← API reference / Swagger surface
│       ├── index.html
│       ├── README.md
│       └── *.jsx
└── _check/                         ← screenshots used during build, ignore
```

The product is a single page on web and a single endpoint on the API, so the two UI kits are intentionally small and focused.

# Caveats & open questions

This design system was built from a **written product brief only**. No codebase, Figma, screenshots, or brand assets were provided. Every visual decision below is a working hypothesis — please confirm or redirect.

## Decisions that need confirmation

1. **Brand name.** The brief uses the working title *MVP Immobilier*. The system uses **Cohérence** (Cohérence Immo as full form) because *cohérence* is the product's core promise. → Confirm the actual product name, or instruct to rename.

2. **Visual register.** The system commits to an **editorial / French-print** aesthetic — parchment + ink + brick accent — meant to feel like a notary's letter, not a property aggregator. Alternatives we could pivot to: (a) **clean fintech** (white + navy + green chip), (b) **modern proptech** (off-white + electric green + Söhne-like sans), (c) **classified-ad utilitarian** (white + LeBonCoin-style orange). → Confirm direction.
   → **Résolu (juin 2026).** Direction éditoriale **confirmée et renforcée** par la
   refonte « D2 — L'Étude » (cf. [`/docs/strategy/REBRAND-2026.md`](../docs/strategy/REBRAND-2026.md)) :
   la modernité se signale par la **preuve chiffrée** et la sobriété (boussole
   Anthropic), pas par le SaaS bleu. Pas de pivot fintech/proptech.

3. **Fonts are CDN substitutions, not licensed files.**
   - Display: **Instrument Serif** (Google Fonts). Closest free match to a paid editorial serif (e.g. Sang Bleu, Romain).
   - UI: **Geist** (Google Fonts). Could be swapped for a paid grotesque (e.g. Söhne, GT America).
   - Mono: **Geist Mono**.
   → If real brand fonts exist, please attach `.woff2` files and we'll swap.

4. **Icon set.** The seven icons in `assets/icons/` were drawn fresh at 1.5 px stroke. If you'd prefer a CDN set, [Lucide](https://lucide.dev) at `stroke-width: 1.5` is the nearest match. → Confirm: keep custom set, or switch to Lucide?
   → **À jour (juin 2026).** Set custom conservé ; un mark de marque
   **`AlerionMark`** (alérion lorrain unique, trait 1,75 px, or Jaumont) a été
   ajouté et est en prod, à la place du cachet aux trois alérions (`LorraineSeal`).

5. **No imagery provided.** The visual-foundations doc allows for a single full-bleed B&W Metz architecture photo in the marketing hero, but no such image was supplied. The UI kit uses a placeholder slot. → Provide photography brief or actual images if marketing is in scope.
   → **Partiel (juin 2026).** Une image (`frontend/public/hero-metz.jpg`) est
   branchée, traitée N&B/grain en CSS et reléguée en **bande signature** en bas de
   home (`SignatureBand`). Reste à brancher une **vraie photo N&B libre de droits**
   (brief dans [`/docs/brand/LOCAL-ANCHORING.md`](../docs/brand/LOCAL-ANCHORING.md)).

6. **No slide template was provided**, so `slides/` was intentionally not created. If you'd like deck templates, attach a sample deck or describe the use case.

7. **API kit.** Since the backend is API-only (FastAPI on Railway), the "API kit" is a documentation/Swagger-style reference page. If there is a separate admin or operator UI that wasn't mentioned, flag it.

8. **Scoping.** The product is Metz/Moselle only at MVP. Copy and the map-pin icon currently lean on that. If geographic expansion is imminent, the brand voice will need a pass.
   → **Résolu (juin 2026).** Décision : marque géo-neutre **« Cohérence »** + système **« édition locale »** (édition Metz aujourd'hui, extension prévue). Ancrage local assumé via wording quartier + or Jaumont + cachet sobre. Détail : [`/docs/brand/LOCAL-ANCHORING.md`](../docs/brand/LOCAL-ANCHORING.md).

## Things we **did not** do

- We did not build automated tests, real auth flows, or backend integration — these are static prototypes.
- We did not create slide templates (no source provided).
- We did not draw photographic assets — placeholders only.

## What we'd love next

- One real listing's raw text + the expected analysis output, so we can pressure-test the result-card layout against realistic content lengths.
- A 2-paragraph description of how the founder talks about the product to a non-buyer friend — that's how we'll calibrate the marketing-page voice.
- Any logo or brand sketch you already have, even on paper.

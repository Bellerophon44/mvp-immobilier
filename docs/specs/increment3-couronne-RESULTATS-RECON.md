# increment3-couronne — RÉSULTATS RECON (axe B, agences locales de la couronne)

> Résultats du **recon read-only** décidé en GATE 1 (« recon avant code », cf.
> `docs/specs/increment3-couronne-ANALYSE.md` §4/§5). Mesuré en **CI** (egress
> ouvert) le **2026-06-20** via `diagnose-scrapers.yml` → `scrapers.diagnose
> --recon-all` sur `scrapers.recon.SITES`. Source de vérité = commentaire collant
> de la PR #113.
>
> Rappel : le recon est **inexploitable en local** dans l'environnement d'atelier
> (egress sur allowlist → tout sort en `403` proxy « Host not in allowlist »,
> verdict factice). Seul le runner CI donne un verdict réel.

---

## 0. Décisions GATE 1 (rappel)

- **Axe B (agences locales couronne) d'abord** ; axe A (dédup multi-mandat /
  matching photo) **différé et dégroupé**.
- **Recon avant code** côté agences (ne pas écrire un scraper qui rapporte 3 biens
  ou qui heurte un `robots.txt`).
- Axe A : **mesurer le gisement cross-source** avant tout pipeline image.

Candidates auscultées (agences LOCALES INDÉPENDANTES, pas des portails) :
Les Artisans de l'Immobilier (page *maisons* + page *ventes*), SOREC.

---

## 1. Verdicts (CI, 2026-06-20)

| Candidate | URL | robots.txt | HTTP | Prix en HTML serveur | Verdict |
|---|---|---|---|---|---|
| Artisans de l'Immobilier — *maisons* | `artisans-immobilier.com/maison-a-vendre-.htm` | **INTERDIT** | 200 | ✅ 17 prix / 41 surfaces | FAISABLE techniquement **mais robots interdit** |
| Artisans de l'Immobilier — *ventes* | `artisans-immobilier.com/immobilier-a-vendre-.htm` | **INTERDIT** | 200 | ✅ 33 prix / 74 surfaces | idem |
| SOREC | `sorec-immobilier.com/annonces/transaction/vente.html` | autorisé | 200 | ❌ 0 prix (196 Ko) | **JS-only probable** (pas de prix en HTML serveur) |

Détail Artisans (structure très propre, si jamais robots l'autorisait) : carte
`div.details` → prix `div.res_tbl_value[itemprop="price"] content="388500"`,
surface `div.loc_details > span.nobr`, lien détail `a.prod_details[href]`. Couvre
la couronne (Verny, Metz…) et des **maisons**.

---

## 2. Conclusion : 0 candidate retenue sur cette vague

- **Artisans** = le meilleur candidat technique du lot (HTML serveur propre,
  `itemprop=price`, maisons couronne) **mais son `robots.txt` interdit les pages
  de listing**. Règle projet non négociable : respecter `robots.txt`, ne jamais
  contourner (cf. `.claude/lessons.md`, anti-patterns CONTEXT §11). → **écartée**.
- **SOREC** = autorisé par robots mais **rend ses prix en JS** (0 € dans le HTML
  serveur). La stack scraping est volontairement **sans navigateur headless** (pas
  de Playwright). → **écartée**.

Le « recon avant code » a donc rempli son rôle : aucun scraper inutile ou non
conforme n'a été écrit.

---

## 3. Bonus mesuré dans le même rapport — gisement cross-source (intrant axe A)

(Section « Recouvrement inter-sources » + « Dédup exacte bienici » du diagnostic.)

- Parc total scrapé : **29 592** (`bienici` 29 241, `benedic` 239, `laveine_immo`
  74, `idemmo` 22, `immoheytienne` 16) ; parc agences hors bien'ici : **351**.
- Paires candidates **INTER-sources strictes** (±2 % surface ET ±2 % prix) :
  **688** (borne BASSE — un même bien chez deux agences n'a pas toujours des
  attributs identiques ; le matching photo en récupérerait davantage).
- Paires inter-sources **larges** (±10 % surface, prix libre) : 146 898 (dont
  146 752 impliquant bien'ici) — **borne haute bruitée**, similarité d'attributs ≠
  identité, **non significative** (mesure la densité du segment).
- **Dédup mandat exacte SANS photo** intra-bien'ici : **79 groupes de `reference`
  partagée** (198 annonces) ; `relatedAdsIds` présent sur 1/1000 (bien'ici relie
  déjà quelques annonces). Photos exploitables : `photos` présent 191/200.
- Verdict gisement : **réel mais à départager** (attributs proches ≠ même bien) →
  le **matching photo** reste le discriminant ; décision conditionnée à sa
  faisabilité (cf. `cross-agence-INCREMENT2B-ANALYSE.md`). À garder pour l'axe A.

---

## 4. Suites possibles (décision humaine, non tranchée)

1. **Vérifier le `robots.txt` réel d'Artisans** avant écart définitif : le verdict
   « INTERDIT » est conservateur ; si la directive `Disallow` ne vise pas ces
   chemins (ou cible un UA précis), Artisans redevient le meilleur candidat propre.
2. **2ᵉ vague de recon** : peupler `scrapers.recon.SITES` avec d'autres agences
   indépendantes de la couronne (Marly / Montigny / Woippy / Saint-Julien) et
   relancer `diagnose` (la CI repart sur push, voir note CI ci-dessous).
3. Si les vagues confirment le mur (robots ou JS partout) : **acter que l'axe B a
   un gisement scrapable maigre** et remonter le constat sans l'édulcorer (le vrai
   levier serait ailleurs, cf. `comparables-coverage-ANALYSE.md` §8).

---

## 5. Note CI (apprise dans la même session)

`diagnose-scrapers.yml` (event `pull_request`) tourne sur le commit de merge
`refs/pull/N/merge`. **Tant que la PR est en conflit (`mergeable_state: dirty`),
GitHub ne peut pas le fabriquer → aucun workflow `pull_request` ne se lance**, ni
sur push ni sur reopen. Diagnostic d'une CI muette : (1) barre de budget Actions
(si non pleine, ce n'est PAS le budget) ; (2) `mergeable_state` — si `dirty`,
**résoudre le conflit AVANT toute autre piste**. Détail : `.claude/lessons.md`
(entrée 2026-06-18).

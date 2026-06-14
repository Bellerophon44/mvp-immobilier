# Analyse pré-atelier — issue #100 « [pilote] Identification quartier Botanique »

> Statut : **analyse de triage / pré-GATE 1** (lecture seule du code, aucun
> changement de comportement). Produite avant l'arbitrage fondateur (`pret-atelier`)
> et avant tout `/feature`. Objectif : décomposer un retour pilote qui **agrège
> plusieurs constats**, ancrer chaque symptôme dans le code réel, séparer ce qui
> est **bug** de ce qui est **feature**, et remonter les **éléments structurants**
> que le fondateur pressent avoir touchés.
>
> Sources relues : `CONTEXT.md` (§1.4 « pas de fake precision », §2.1 ton, §11
> anti-patterns), `backend/CLAUDE.md`, `.claude/lessons.md`,
> `docs/pilotes/README.md`, `docs/brand/LOCAL-ANCHORING.md`,
> `docs/brand/METZ-LOCAL.md`, `docs/specs/photo-evidence-*`.

---

## 0. TL;DR pour le fondateur

L'issue #100 contient **cinq constats distincts** (elle déroge à « un constat =
une issue », ce qui est assumé : un seul passage produit). Trois sont des **bugs
de qualité** corrigeables ; deux sont des **demandes de capacité nouvelle**
(reconnaissance « secteur prisé » + « écoles à proximité ») qui touchent le
positionnement produit.

Le **fil rouge structurant** : tout part d'un **référentiel géographique trop
maigre et triplement dupliqué**, qui ne connaît pas « Sainte-Thérèse / Botanique »
et ne modélise pas la **réalité inter-communale** (le bien est sur la frange
Metz / Montigny-lès-Metz). Quand ce référentiel échoue, deux comportements
graves s'enchaînent :

1. l'app **n'identifie pas** le quartier pourtant nommé explicitement (perte de
   crédibilité — constat du pilote) ;
2. forcée à la main sur un quartier voisin (« Nouvelle Ville »), elle produit un
   **contexte local confiant mais faux** (« Quartier Impérial autour de la gare,
   architecture germanique ») — ce qui **viole l'anti-pattern « pas de fake
   precision » (CONTEXT §1.4)** et est, à mon sens, **plus grave** que le constat
   d'origine.

Recommandation : ne pas lancer un `/feature` « rustine » par symptôme. **Trancher
d'abord la question structurante du référentiel** (§4), puis dériver 2-3 chantiers.

---

## 1. Décomposition en constats

| # | Constat | Catégorie proposée | Gravité proposée | Bug / Feature |
|---|---|---|---|---|
| C1 | Le quartier « Sainte-Thérèse / Botanique », explicitement nommé, n'est pas auto-identifié ; choix manuel obligatoire | `ancrage-local` + `extraction-llm` | `bloquant-credibilite` | Bug |
| C2 | Le repli manuel sur « Nouvelle Ville » produit un contexte local **confiant et faux** | `ancrage-local` (+ `scoring`/`comparables`) | `bloquant-credibilite` | Bug |
| C3 | Allégation « au cœur du quartier Sainte-Thérèse / Botanique » classée « À vérifier » alors qu'une photo la démontre ; « quartier prisé » non reconnu | `ancrage-local` | `majeur` | Mixte (bug + capacité) |
| C4 | « Proximité des écoles » non vérifiable / non identifiée | `ancrage-local` | `mineur` → `majeur` | Feature (capacité absente) |
| C5 | Questions incohérentes : on demande le montant des charges que l'annonce donne (320 €/mois), et la dernière question **re-cite** ce montant (3840 €/an) | `extraction-llm` (+ `wording`) | `bloquant-credibilite` | Bug |

> Note process : conformément à `docs/pilotes/README.md` (« un constat = une
> issue »), ces cinq lignes devraient devenir **cinq issues filles** liées à
> #100, chacune labellisée séparément (le triage ne pose jamais `pret-atelier` —
> GATE fondateur). Proposition de découpage en §6.

---

## 2. Ancrage dans le code réel (cause racine par constat)

### C1 — Auto-identification du quartier en échec

Chaîne de résolution du quartier : `analysis._resolve_district`
(`backend/app/analysis.py:77-91`) :

```
district_override  →  extract_district(address)  →  listing["district"] (LLM)
                  →  extract_district(raw_text)  →  ""
```

- `extract_district` (`backend/scrapers/base.py:364-377`) fait un simple
  *substring match* contre `_KNOWN_LOCALITIES` (`base.py:329-361`). Cette liste
  **ne contient ni « sainte-thérèse » ni « botanique »**. Donc le repli texte
  échoue.
- Le LLM peut, lui, extraire `listing["district"] = "Sainte-Thérèse / Botanique"`.
  Mais en aval, `metz_local._resolve_key` (`metz_local.py:198-208`) et
  `market_stats.compute_market_stats` (`market_stats.py:177`) passent par
  `canonical_district` puis cherchent une **clé connue** dans `_PROFILES` /
  `_DIST_KM` / `_SECTORS_RAW`. « Sainte-Thérèse / Botanique » n'y est pas → pas
  de contexte local, pas de cascade quartier/secteur → l'analyse **reste au
  niveau ville** (« À l'échelle de Metz · 105 comparables », cf. le rapport).

**Cause racine** : le référentiel géographique est une **liste blanche de 16
quartiers officiels**, triplée et désynchronisable :
- `_KNOWN_LOCALITIES` (`scrapers/base.py:329`) — extraction texte ;
- `_PROFILES` + `_DIST_KM` + `_ALIASES` (`metz_local.py:64,168,189`) — contexte/allégations ;
- `_SECTORS_RAW` + `_METRO_CITIES_RAW` (`market_stats.py:36,58`) — cascade comparables ;
- `METZ_DISTRICTS` (`frontend/lib/districts.ts:7`) — sélecteur manuel.

« Sainte-Thérèse » est un **micro-quartier réel de Metz** (basilique
Sainte-Thérèse, frange sud Nouvelle-Ville / Sablon) absent de ce découpage ;
« Botanique » réfère au **Jardin botanique**, à cheval **Metz / Montigny-lès-Metz**.
Aucun des quatre référentiels ne le sait.

### C2 — Le repli manuel produit un contexte faux mais confiant

Le pilote, faute d'option « Sainte-Thérèse », choisit « Nouvelle Ville » dans le
sélecteur (`districts.ts`). Conséquence :
- `local_context("Nouvelle Ville")` (`metz_local.py:211-229`) renvoie le profil
  **Nouvelle-Ville** (`metz_local.py:77-82`) : *« Quartier Impérial autour de la
  gare, architecture germanique »*, gare « immédiate (~0,3 km) ». **Affirmé sans
  réserve** alors que le bien est ailleurs.
- `assess_claims` (`metz_local.py:296-322`) juge alors « 20 min à pied de la
  gare » **Cohérent** via le `_DIST_KM["Nouvelle-Ville"]["gare"] = 0.3`
  (`metz_local.py:171`) — *bon verdict pour une mauvaise raison* : la cohérence
  géographique n'est fiable que si la résolution du quartier l'est.
- Côté prix, le pilier bascule sur le secteur « Centre Ville »
  (`market_stats.py:49`, qui inclut Nouvelle Ville) → fourchette
  « 2005–2451 €/m² » d'un secteur qui n'est **pas** celui du bien.

**Cause racine** : le mode quartier **n'a aucun garde-fou d'incertitude**. Quand
le quartier saisi ne correspond pas au bien, le système ne le sait pas et **parle
avec autant d'assurance qu'en cas de match exact**. C'est exactement le
**fake precision** proscrit (`CONTEXT §1.4`, `LOCAL-ANCHORING.md` « la promesse ne
doit pas dépasser la maturité de la donnée »). À mes yeux, **C2 est le cœur du
problème de crédibilité**, plus encore que C1.

### C3 — Allégation de quartier classée « À vérifier » + « prisé » non reconnu

Deux mécanismes distincts, souvent confondus dans le constat :

1. **Contrôle de cohérence (couche B, sans photo).** L'allégation « au cœur du
   très recherché quartier Sainte-Thérèse / Botanique » est typée par le LLM
   (probablement `autre` ou `calme`/`quartier prisé`). `_assess_one`
   (`metz_local.py:254-293`) ne sait juger que `cathedrale`/`centre`/`gare`/`a31` ;
   tout le reste retombe sur **`A_VERIFIER` neutre** (`metz_local.py:291-293`).
   C'est **volontaire et prudent** (ne jamais valider par complaisance) — mais le
   pilote attend une **reconnaissance du quartier**, pas une validation
   d'allégation. Tant que le quartier n'est pas dans le référentiel, le système
   **ne peut pas** dire mieux que « à vérifier ».

2. **Preuve photo (couche photo-evidence).** `assess_claims_with_photos`
   (`backend/app/photo_evidence.py:121`) **ne tourne qu'en mode URL** : les
   `image_urls` viennent de `extract_image_urls` sur le HTML fetché
   (`main.py:595-597`). **En collage de texte (le cas du pilote), aucune image
   n'est transmise → aucune vérification photo.** Et même en mode URL : une
   identité de quartier (« au cœur du quartier X ») **n'est pas un repère visuel**
   confirmable sur une photo — le temple ou le jardin botanique le sont, le *nom
   du quartier* non. Donc « confirmé par la photo » ≠ « allégation de quartier
   confirmée ».

**Désaccord à expliciter** : le constat « une photo le démontre clairement »
mélange deux choses. La photo peut corroborer *un repère* (temple, jardin
botanique) ; elle ne peut pas, à elle seule, confirmer *l'appartenance au
quartier ni son caractère « prisé »*. Le vrai levier ici est la **connaissance du
quartier** (référentiel), pas la vision.

3. **« Quartier prisé ».** Aucune donnée de **réputation/désirabilité** par
   quartier n'existe dans le code. La qualifier toucherait directement le
   positionnement « factuel, neutre, jamais vendeur » (`CONTEXT §2.1`) — voir
   risque en §5.

### C4 — « Proximité des écoles »

Même mécanisme que C3-1 : type `ecoles` → `A_VERIFIER` neutre
(`metz_local.py:291`). Aucune base POI « écoles » n'existe. C'est une **capacité
absente**, donc une **feature**, pas un bug. Faisable techniquement (POI curatés
ou API publique type Annuaire de l'Éducation / Overpass), mais c'est un chantier
data, pas une correction.

### C5 — Questions incohérentes sur les charges

Deux questions se télescopent :
- **Question LLM** : « Quel est le montant annuel des charges de copropriété ? »
  — générée par le prompt `questions` (`llm_semantic.py:96`), alors que l'annonce
  dit « Charges mensuelles : 320 € ». Le prompt demande des « points à clarifier
  AVANT la visite » mais **n'interdit pas de poser une question dont la réponse
  est explicite dans l'annonce**.
- **Question déterministe** : `_amenity_actions` (`analysis.py:115-121`) ajoute
  « Que couvrent les charges de copropriété annoncées (**3840 €/an**)… » dès que
  `condo_fees` est extrait. Le LLM a annualisé 320 × 12 = 3840 → `condo_fees = 3840`.

Résultat : la **1ʳᵉ** question demande un montant que la **dernière** cite. Le
`_merge_unique` (`analysis.py:124-127`) ne déduplique que sur le texte quasi
identique, pas sur l'**intention** ou le **sujet**.

**Cause racine** : aucun **invariant de cohérence inter-champs** — « ne pas
demander ce que l'annonce (ou l'extraction) fournit déjà ». Le problème est
**généralisable** au-delà des charges (surface, DPE, étage, nb de pièces…).

---

## 3. Synthèse : ce qui est bug vs feature

- **Bugs (corrigeables sans changer le périmètre produit)** :
  - C5 — invariant « ne pas re-demander ce qui est donné » + cohérence
    questions LLM ↔ champs extraits. **Le plus net, le plus rapide, fort ROI
    crédibilité.** Candidat idéal pour un premier `/feature` + cas d'éval.
  - C2 — garde-fou d'incertitude sur le mode quartier (ne pas affirmer un profil
    de quartier quand la correspondance n'est pas sûre). Dépend en partie de §4.
- **Structurel (préalable)** :
  - C1 — enrichir/unifier le référentiel géographique (§4).
- **Features (décision produit)** :
  - C3 (volet « prisé ») et C4 (écoles) — nouvelles connaissances locales, à
    arbitrer contre le positionnement (§5) et la roadmap `LOCAL-ANCHORING.md`.

---

## 4. Élément structurant n°1 — le référentiel géographique

C'est le point que le fondateur pressent. Détail du problème et des options.

**Problème** : 4 listes codées en dur (§2-C1) qui doivent rester d'accord, au
grain « 16 quartiers officiels ». Elles ignorent (a) les **micro-quartiers**
(Sainte-Thérèse, Botanique, Bellecroix-haut, etc.) et (b) la **réalité
inter-communale** : « Botanique » est à cheval **Metz (57000) / Montigny-lès-Metz
(57950)**. Or les comparables filtrent sur `Comparable.city` **exact**
(`market_stats.py:131-134`) : un bien physiquement côté Montigny mais lu « Metz »
puise dans le mauvais pool (et inversement). Montigny est bien dans
`_METRO_CITIES` (`market_stats.py:58-71`) mais seulement comme **filet métropole**,
pas comme quartier de premier rang.

**Risque transverse déjà en base de leçons** : `lessons.md` (2026-06-14,
bienici-couronne) — *« une colonne filtrée dans un lookup par-ligne doit être
indexée »*. Toute extension du référentiel qui ajouterait des lookups par-ligne à
l'ingestion devra respecter cette leçon.

**Options (à arbitrer en GATE 1, non tranché ici)** :

- **(A) Étendre les listes à la main.** Ajouter « Sainte-Thérèse », « Botanique »
  (+ alias) aux 4 référentiels, avec profil/distances, et rattacher au bon
  secteur. *Pour* : rapide, dans la veine actuelle, 100 % curaté/vérifiable.
  *Contre* : ne règle pas la duplication ni l'inter-communal ; chaque micro-quartier
  est un nouveau quadruplet à maintenir. Ne scale pas (cf. système « édition
  locale », `METZ-LOCAL.md §5`).
- **(B) Unifier en une source unique** (un seul gazetteer quartiers→{aliases,
  centroïde, secteur, commune, code postal, profil}) dont dérivent les 4 usages.
  *Pour* : supprime la désynchronisation, prépare l'inter-communal et l'extension
  multi-villes. *Contre* : refactor transverse (back + front), à cadrer.
- **(C) Géocodage systématique** (couche C déjà présente, `geocode_address`) pour
  rattacher l'adresse à un quartier/commune réels plutôt qu'à un libellé.
  *Pour* : robuste aux libellés inconnus, gère l'inter-communal nativement.
  *Contre* : exige une **adresse** (souvent absente d'un texte collé), réseau,
  et un mapping coordonnées→quartier qu'on n'a pas encore (les `_POI` sont des
  points, pas des polygones). Distances « à vol d'oiseau » (limite déjà documentée
  `CLAUDE.md §11`).

Mon avis d'analyste : **(B)** comme cible (dette structurelle qui revient à chaque
retour pilote sur la géo), avec un **premier pas pragmatique (A)** pour débloquer
Sainte-Thérèse/Botanique **si** on en fait un cas d'éval — mais **seulement** une
fois C2 (garde-fou d'incertitude) en place, sinon on ne fait que déplacer le
risque de « confiant mais faux » vers le prochain quartier manquant.

---

## 5. Élément structurant n°2 — « prisé » / réputation : limite de positionnement

Reconnaître un « secteur prisé » (C3) ou affirmer la proximité d'écoles « réelles »
(C4) demande d'**injecter du jugement / de la donnée externe** dans un produit qui
se définit par : *factuel, neutre, jamais vendeur, pas de fake precision*
(`CONTEXT §1.4`, §2.1), *« héraldique-éditorial, jamais office de tourisme »*
(`METZ-LOCAL.md`). Risques :

- Qualifier un quartier de « prisé » = **reprendre l'argumentaire du vendeur**, à
  rebours du « second avis lucide » (§1.3). Si la source est une opinion, c'est
  du fake precision ; si c'est une donnée (prix médian du secteur, tension), il
  faut l'**objectiver** et la **sourcer**.
- Écoles : faisable **factuellement** (POI publics) sans jugement → plus sûr que
  « prisé ». Mais reste un chantier data + entretien.
- `LOCAL-ANCHORING.md` tranche déjà la philosophie : *« la preuve > la
  décoration »*, *« on promet quartier, jamais rue par rue tant que la donnée ne
  suit pas »*. Donc : **n'affirmer que ce qui est sourçable**, sinon rester sur
  « à vérifier » assumé.

Décision produit pour le fondateur (GATE 1) : **veut-on que Cohérence qualifie la
désirabilité d'un secteur**, et si oui sur **quelle donnée objective** ? Sans
réponse, C3-« prisé » et C4 restent hors atelier.

---

## 6. Recommandation de triage et de découpage

Découpage proposé en issues filles de #100 (chacune `retour-pilote` ; catégorie
+ gravité posées par le triage ; `pret-atelier` réservé au fondateur) :

1. **#100-a — Questions : ne pas re-demander une info donnée par l'annonce (charges)**
   `qualite/extraction-llm`, `qualite/wording` · `gravite/bloquant-credibilite` ·
   **bug, prêt techniquement** (cf. §2-C5). *Meilleur premier chantier.*
2. **#100-b — Mode quartier : garde-fou d'incertitude (ne pas affirmer un profil de quartier non sûr)**
   `qualite/ancrage-local` · `gravite/bloquant-credibilite` · bug, dépend de §4.
3. **#100-c — Référentiel géographique : intégrer Sainte-Thérèse/Botanique + inter-communal Metz/Montigny**
   `qualite/ancrage-local`, `qualite/comparables` · `gravite/majeur` · structurel (§4).
4. **#100-d — Reconnaissance « secteur prisé »** — `qualite/ancrage-local` ·
   `gravite/majeur` · **feature, bloquée GATE 1 produit** (§5).
5. **#100-e — Proximité écoles (POI)** — `qualite/ancrage-local` ·
   `gravite/mineur` · feature data (§5).

L'issue #100 mère : retirer `triage` une fois les filles créées, garder
`retour-pilote`, servir d'ombrelle.

---

## 7. Du retour pilote aux cas d'éval (anti-régression)

Conformément à `docs/pilotes/README.md` § « Du retour pilote au cas d'éval » et
`docs/specs/evals-harness-SPEC.md`, chaque finding validé `pret-atelier` doit
devenir un **cas synthétique** (`backend/evals/cases/issue_<n>.txt` +
`test_eval_issue_<n>.py`), **jamais l'extrait réel** (repo public, droit d'auteur,
CONTEXT §11.3). Cas pertinents :

- **C5** (le plus net) : annonce fictive en **copropriété** affichant des charges
  explicites (« Charges : 300 €/mois ») → assertion : **aucune** question ne
  demande le *montant* des charges (mot-clé), et pas de question qui à la fois
  ignore et cite le montant. Oracle partiellement déterministe possible côté
  `_amenity_actions` (suite gratuite `backend/tests/`) + volet LLM en `evals/`
  (`xfail` tant que non fixé, preuve XFAIL avant merge).
- **C1/C2** : annonce fictive nommant un quartier **hors référentiel** → assertion :
  le contexte local n'affirme pas un profil d'un *autre* quartier ; reste neutre.
- **C3/C4** : à n'écrire qu'**après** arbitrage produit (§5).

Leçon process candidate (`.claude/lessons.md`) si C5 part en atelier :
*« ne jamais générer une question dont la réponse est explicitement extraite dans
`listing` ; garde-fou par invariant testé, pas par confiance dans le prompt ».*

---

## 8. Questions structurantes (GATE 1, à trancher par le fondateur)

1. **Référentiel géo (§4)** : on vise (A) extension manuelle, (B) source unique
   unifiée, ou (C) géocodage→quartier ? (reco : B cible, A en 1ᵉʳ pas conditionné
   à C2).
2. **Garde-fou d'incertitude (C2)** : accepte-t-on que le mode quartier puisse
   dire « quartier non reconnu, analyse à l'échelle ville » plutôt que d'afficher
   un profil voisin ? (reco : oui — c'est la cohérence du positionnement).
3. **« Prisé » (§5)** : Cohérence qualifie-t-elle la désirabilité, et sur quelle
   donnée objective ? (sinon C3-prisé reste hors atelier).
4. **Écoles (C4)** : capacité voulue à court terme ? quelle source POI ?
5. **Process** : crée-t-on les 5 issues filles, ou traite-t-on #100 en bloc ?
6. **Priorité** : commence-t-on par **C5** (bug net, ROI immédiat) pendant que la
   question géo (§4) mûrit ?

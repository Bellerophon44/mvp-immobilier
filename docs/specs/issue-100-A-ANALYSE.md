# Analyse de faisabilité — issue #100, chantier A

> Palier 1 du référentiel géographique (intégrer « Sainte-Thérèse / Botanique »
> aux 4 référentiels) + garde-fou d'incertitude C2 (ne plus affirmer un profil de
> quartier « confiant mais faux »).
>
> Statut : analyse pré-GATE 1, lecture seule du code. S'appuie sur
> `docs/specs/issue-100-ANALYSE.md` (analyse-ombrelle actée) sans la réécrire.
> Périmètre strict (rappel) : in = (1) ajout référentiel Sainte-Thérèse/Botanique,
> (2) garde-fou C2. Hors = « secteur prisé » (fermé), écoles/POI (chantier C),
> unification en source unique (chantier B).
>
> Sources relues : `.claude/lessons.md` ; `docs/specs/issue-100-ANALYSE.md`
> (§0bis, §2, §4, §6, §8) ; code réel listé en regard de chaque assertion
> (`fichier:ligne`).

---

## 0. TL;DR analyste

- Le chantier A est **deux travaux distincts dans le même lot**, à ne pas
  confondre :
  - **(1) Ajout référentiel** : peupler les 4 listes pour que
    « Sainte-Thérèse / Botanique » soit RECONNU. C'est l'extension naturelle de
    l'existant, faisable, mais qui bute sur deux pièges réels du code :
    (a) le séparateur « / » du libellé pilote n'est PAS géré par
    `canonical_district` (qui split sur `" - "`, `base.py:309`) ; (b) le filtre
    comparables est sur `city` EXACT (`market_stats.py:134`), donc l'inter-communal
    Metz/Montigny n'est pas adressable par l'ajout de quartier seul.
  - **(2) Garde-fou C2** : empêcher le système, quand l'utilisateur force
    manuellement un quartier (`district_override`) qui ne correspond pas au bien,
    de débiter un profil curaté affirmé sans réserve. **C'est le vrai cœur
    crédibilité** (cf. §0bis-3 de l'ombrelle), orthogonal à (1) : ajouter
    Sainte-Thérèse ne corrige PAS C2, ça déplace juste le risque au prochain
    quartier absent.
- **Désaccord à remonter** (posture adversariale) : le garde-fou C2 tel que
  posé dans le retour pilote (« sélection manuelle Nouvelle-Ville pour un bien
  ailleurs ») n'est **pas détectable de façon fiable** dans le code actuel sans
  géocodage : `district_override` est, par conception (`analysis.py:85-91`,
  CLAUDE §10), la source la PLUS fiable et écrase l'extraction. Le système ne
  dispose d'aucun signal lui disant que le quartier choisi ≠ quartier réel du
  bien tant qu'on n'a pas d'adresse géocodée (chantier C). Le garde-fou C2 de
  palier A ne peut donc viser que ce qui est **atteignable sans géocodage** :
  voir options en §3 — il faut que l'humain tranche le périmètre exact de C2
  pour ne pas sur-promettre une détection qu'on n'a pas.

---

## 1. Cartographie du flux réel (où naît le « confiant mais faux »)

### 1.1 Chaîne de résolution du quartier

Point d'entrée : `run_full_analysis` (`analysis.py:166-203`). Deux usages du
quartier en parallèle, tous deux passant par `_resolve_district`
(`analysis.py:77-91`) :

```
district_override (sélecteur front)        # api.ts:62 -> main.py:76 -> analysis arg
  or extract_district(address)             # base.py:364 (si adresse saisie)
  or listing["district"]                   # extraction LLM (llm_semantic.py:71,332)
  or extract_district(raw_text)            # base.py:364 (repli substring)
  or ""
```

Ce `district` alimente DEUX branches indépendantes :

1. **Pilier prix** : `_price_pillar_from_listing` (`analysis.py:49`) →
   `compute_price_market_pillar` (`market_stats.py:423`) →
   `compute_market_stats` (`market_stats.py:160`). Le district est canonicalisé
   (`market_stats.py:177`), mappé à un secteur via `_DISTRICT_TO_SECTOR`
   (`market_stats.py:181`), et utilisé dans la cascade
   `quartier → secteur → ville → métropole` (`market_stats.py:193-224`). Le
   filtre SQL est `Comparable.district == district` ou `.in_(sector_districts)`
   et `Comparable.city == city` (exact, `market_stats.py:131-138`).

2. **Contexte local non-scoré** : `analysis.py:184-202`. Sans adresse géocodée :
   `local_context(district, city)` (`metz_local.py:211`) puis
   `assess_claims(district, claims, city)` (`metz_local.py:296`). Avec adresse
   géocodée (couche C, hors périmètre A) : `local_context_from_coords` +
   `claim_distances_from_coords`.

### 1.2 Où naît exactement le « confiant mais faux » (C2)

Quand l'utilisateur force `district_override = "Nouvelle Ville"` pour un bien qui
est en réalité à Sainte-Thérèse :

- `_resolve_district` (`analysis.py:85-91`) renvoie `"Nouvelle Ville"` (override
  prioritaire, écrase tout). **Le système n'a aucun moyen, à ce stade, de savoir
  que ce choix est faux.**
- `local_context("Nouvelle Ville")` (`metz_local.py:211-229`) → `_resolve_key`
  (`metz_local.py:198`) résout la clé `Nouvelle-Ville` et renvoie le profil
  `_PROFILES["Nouvelle-Ville"]` (`metz_local.py:77-82`) :
  *« Quartier Impérial autour de la gare, architecture germanique »*, gare
  « immédiate (~0,3 km) ». **Affirmé sans réserve** : c'est ici, `metz_local.py:218-228`
  (construction du dict `summary`/`facts` sans champ de confiance), que naît le
  « confiant mais faux ». Le bloc n'a pas de notion d'incertitude : `precision`
  vaut toujours `"quartier"` (`metz_local.py:228`) que la correspondance soit
  sûre ou non.
- `assess_claims("Nouvelle Ville", ...)` (`metz_local.py:296-322`) juge alors
  « 20 min à pied de la gare » via `_DIST_KM["Nouvelle-Ville"]["gare"]=0.3`
  (`metz_local.py:171`) → verdict COHERENT (`_assess_one`, `metz_local.py:280-286`)
  pour le mauvais quartier. Bon verdict, mauvaise raison.
- Côté prix : `compute_market_stats` mappe `Nouvelle-Ville → secteur "Centre Ville"`
  (`market_stats.py:49`, `_SECTORS_RAW`) → fourchette d'un secteur qui n'est pas
  celui du bien (`market_stats.py:261-263` libelle « Dans le secteur Centre Ville »).

**Conclusion cartographie** : le défaut C2 est concentré dans `metz_local.local_context`
/ `assess_claims` (le contexte non-scoré affirme un profil curaté sans réserve)
et il est PILOTÉ par `_resolve_district` qui suit l'override sans le challenger.
Le pilier prix, lui, est déjà « honnête » par construction (il dit le scope
réel — quartier/secteur/ville — `market_stats.py:257-270`), mais il hérite du
mauvais quartier en amont.

### 1.3 Distinction nette : ajout référentiel (1) vs garde-fou (2)

| Aspect | (1) Ajout référentiel | (2) Garde-fou C2 |
|---|---|---|
| But | Sainte-Thérèse RECONNU | Ne pas affirmer un profil non sûr |
| Déclencheur du bug | quartier absent → repli ville (perte de reconnaissance) | quartier présent mais FAUX (sélectionné à tort) → profil affirmé |
| Fichiers | `base.py`, `metz_local.py`, `market_stats.py`, `districts.ts` | `metz_local.local_context`/`assess_claims` + éventuellement `analysis._resolve_district` |
| Indépendance | n'enlève pas le risque C2 | ne dépend pas de la liste exacte des quartiers ajoutés |

C'est pourquoi l'ombrelle (§0bis-3) impose de livrer C2 dans le même lot que A :
sinon A déplace le « confiant mais faux » au prochain quartier inconnu.

---

## 2. Faisabilité & dépendances des 4 référentiels

Les 4 listes doivent rester cohérentes (cf. §2-C1 ombrelle). Pour chacune :
quoi ajouter, risque de désynchronisation.

### 2.1 `_KNOWN_LOCALITIES` (`backend/scrapers/base.py:329-361`)

- **Quoi** : ajouter les formes lower-case `"sainte-thérèse"`, `"sainte-therese"`,
  `"botanique"` (et selon l'arbitrage, `"saint-thérèse"`/variantes). Respecter la
  consigne du commentaire (`base.py:327`) : libellés longs avant courts.
- **Mécanique** : `extract_district` (`base.py:364-377`) fait un substring match
  et renvoie `locality.title()` → pour `"sainte-thérèse"` cela donne
  `"Sainte-Thérèse"`. OK.
- **Risque** : `extract_district` est utilisé sur `raw_text` ET sur `address`
  (`analysis.py:87,89`). Un faux positif sur « botanique » (le mot peut apparaître
  hors contexte adresse) reste faible mais existe. Acceptable au palier A.

### 2.2 `_PROFILES` + `_DIST_KM` + `_ALIASES` (`backend/app/metz_local.py:64-185,189-195`)

- **Quoi** : ajouter une clé canonique (ex. `"Sainte-Therese"`) dans `_PROFILES`
  (`metz_local.py:64`) avec `name`/`center`/`gare`/`caractere` curatés, et la même
  clé dans `_DIST_KM` (`metz_local.py:168`) avec `{center, gare}` approximatifs.
  Ajouter dans `_ALIASES` (`metz_local.py:189`) les variantes composées, dont
  **le libellé pilote complet** (voir piège séparateur ci-dessous).
- **Piège séparateur « / » (à signaler)** : la clé canonique est produite par
  `_resolve_key` → `canonical_district(district, city)` (`metz_local.py:203`).
  `canonical_district` (`base.py:297-315`) split UNIQUEMENT sur `" - "`, jamais
  sur « / ». Pour `"Sainte-Thérèse / Botanique"`, il appelle
  `canonical_city("Sainte-Thérèse / Botanique")` (`base.py:315`) qui split sur
  `r"[\s\-]+"` (`base.py:210`) — le « / » n'est ni espace ni tiret. Résultat
  approximatif : un segment `"/"` survit → clé du type `"Sainte-Therese-/-Botanique"`,
  qui ne matchera AUCUNE entrée `_PROFILES`. **Conséquence** : sans traitement
  explicite, le libellé exact extrait par le LLM (« Sainte-Thérèse / Botanique »,
  `local_claims` + `listing.district`) ne résoudra pas. Deux issues possibles, à
  trancher en conception (pas une question GATE 1, c'est de l'implémentation) :
  soit ajouter les libellés « / » comme entrées `_ALIASES` littérales, soit
  normaliser « / » comme séparateur. **Ne PAS rouvrir** `canonical_district` au
  sens large (risque de régression sur tous les libellés bien'ici) ; préférer
  l'alias littéral, plus sûr et 100 % curaté.
- **Risque de désynchronisation** : `_PROFILES` et `_DIST_KM` ont des clés
  dupliquées (deux dicts) — oublier l'un casse `assess_claims` (`metz_local.py:310`
  fait `_DIST_KM.get(key, {center:0,gare:0})` → distances 0 si la clé manque dans
  `_DIST_KM` mais existe dans `_PROFILES` → faux « cohérent »). À verrouiller par
  un test d'égalité des jeux de clés `_PROFILES`/`_DIST_KM`.

### 2.3 `_SECTORS_RAW` (`backend/app/market_stats.py:36-50`)

- **Quoi** : rattacher Sainte-Thérèse à un secteur existant (ou créer un secteur
  propre). C'est l'arbitrage structurant n°1 (§6). Le rattachement détermine quel
  pool de comparables est emprunté quand le quartier est creux (cascade
  `market_stats.py:198-201`).
- **Mécanique** : `_build_sector_maps` (`market_stats.py:74-90`) canonicalise les
  libellés au chargement. Ajouter `"Sainte-Thérèse"` dans la liste d'un secteur
  suffit pour que `_DISTRICT_TO_SECTOR` le connaisse.
- **Réalité du pool de comparables** : à vérifier — combien de comparables ont
  réellement `district == "Sainte-Therese"` en base ? S'il y en a ~0 (probable,
  vu que bien'ici n'utilise pas ce micro-quartier), la cascade tombera de toute
  façon au secteur puis à la ville. Le rattachement secteur n'a donc d'effet
  PRATIQUE sur le prix que marginal au palier A ; son enjeu est surtout la
  **cohérence du libellé affiché** (« Dans le secteur X », `market_stats.py:261`)
  et la préparation de B. À objectiver avant de sur-investir (posture MVP < 1 €/mois).

### 2.4 `METZ_DISTRICTS` (`frontend/lib/districts.ts:7-24`)

- **Quoi** : ajouter `"Sainte-Thérèse"` (libellé affiché) SI on décide d'exposer
  le quartier au sélecteur (arbitrage GATE 1 n°4). Le label est envoyé tel quel à
  `/analyze` (`api.ts:62`) et devient `district_override`.
- **Contrainte de cohérence** : le label front DOIT résoudre côté back (même piège
  « / » qu'en 2.2). Si on expose `"Sainte-Thérèse"` (sans « Botanique »), la
  résolution est simple (pas de « / »). Argument pour exposer le libellé SANS
  « / ».
- **Risque** : si on l'expose au sélecteur mais que le rattachement secteur/pool
  est vide, l'utilisateur choisit un quartier qui ne change rien au prix (repli
  ville) — acceptable, le contexte local reste lui enrichi.

### 2.5 Réalité inter-communale Metz (57000) / Montigny-lès-Metz (57950)

- **Fait** : « Botanique » (Jardin botanique) est à cheval Metz / Montigny-lès-Metz
  (cf. ombrelle §1-C1). Les comparables filtrent sur `Comparable.city` **EXACT**
  (`market_stats.py:134`). Montigny existe dans `_METRO_CITIES`
  (`market_stats.py:58-71`) mais seulement comme **filet métropole**
  (`market_stats.py:185,205-208`), mobilisé uniquement en dernier recours et
  jamais comme quartier de premier rang.
- **Impact concret** : un bien physiquement côté Montigny mais dont le LLM extrait
  `city = "Metz"` (parce que l'annonce dit « quartier Botanique, Metz ») puisera
  dans le pool Metz, pas Montigny — et inversement. Le quartier ne peut PAS
  réconcilier ça : le filtre `city` est en amont du filtre `district`
  (`market_stats.py:131-138`).
- **Limite de palier A (à acter)** : résoudre proprement l'inter-communal exige de
  rattacher une ADRESSE à une commune réelle = géocodage = **chantier C**
  (§4 ombrelle). Au palier A, le seul levier honnête est de **documenter la limite**
  et, au plus, de traiter « Botanique » comme un quartier rattaché à UNE commune
  par convention curatée (Metz OU Montigny), en assumant l'imprécision. Sur-promettre
  l'inter-communal en A serait rouvrir le chantier C. **Recommandation : ne pas le
  traiter en A, le documenter** (arbitrage GATE 1 n°2).

---

## 3. Conception du garde-fou C2

### 3.1 Contrainte de contrat (à ne pas casser)

Le bloc `local_context` est exposé tel quel (`main.py:90`
`Optional[Dict[str, Any]]`) et typé côté front (`api.ts:30-39` interface
`LocalContext` : `district`, `summary`, `facts`, `claims?`, `address?`,
`precision?`). **Tout nouveau champ doit être OPTIONNEL** pour rester
rétro-compatible (CLAUDE §10 : ne pas casser le schéma `/analyze`). Le champ
`precision ∈ {"quartier","adresse"}` (`api.ts:38`, `metz_local.py:228,361`)
existe déjà ; on peut s'appuyer dessus ou l'étendre, mais une valeur nouvelle
(ex. `"ville"`) impacte le front (union de types `api.ts:38`) → à coordonner.

### 3.2 Que peut-on réellement détecter au palier A (sans géocodage) ?

Rappel du désaccord (§0): sans adresse géocodée, **on ne peut pas savoir que le
quartier choisi manuellement est faux**. `district_override` est tenu pour la
vérité (`analysis.py:85`). Donc le garde-fou C2 ne peut PAS, au palier A,
« détecter une mauvaise sélection ». Il peut en revanche traiter les cas
atteignables :

- **Cas a — quartier saisi/extrait NON reconnu** (le cas pilote C1 + Sainte-Thérèse
  avant ajout) : `_resolve_key` renvoie None → `local_context` renvoie déjà None
  (`metz_local.py:216-217`) → aucun profil affiché, repli ville sur le prix. **Déjà
  honnête**. Le garde-fou ici = ne pas régresser ce comportement.
- **Cas b — divergence entre quartier extrait (LLM) et quartier forcé (override)** :
  détectable SANS géocodage. Si `listing["district"]` (extrait par le LLM du texte)
  résout à une clé DIFFÉRENTE de `district_override`, c'est un signal que la
  sélection manuelle contredit l'annonce → on peut poser une réserve. C'est le
  signal le plus proche du cas pilote réellement exploitable au palier A.
- **Cas c — incohérence claim/quartier déjà gérée** : `assess_claims` produit déjà
  `a_verifier`/`peu_plausible` (`metz_local.py:254-293`). Pas un nouveau garde-fou.

### 3.3 Options concrètes pour le repli/réserve

**Option 1 — Repli « quartier non reconnu → analyse à l'échelle ville » (déjà
le comportement par défaut).** Quand pas de clé résolue, `local_context = None`
et le prix part en ville/secteur. Coût : nul (existant). Limite : ne couvre PAS le
cas pilote où le quartier EST reconnu mais faux (override Nouvelle-Ville).
Insuffisant seul pour C2.

**Option 2 — Mention de réserve sur le profil curaté (champ de confiance).**
Ajouter au dict `local_context` un champ optionnel (ex. `"district_match"` ou
réutiliser/étendre `precision`) qui vaut « affirmé » quand le quartier est confirmé
par l'extraction LLM, et « à confirmer » quand il provient d'un override NON
corroboré par l'annonce (cas b). Le front affiche alors une réserve (« quartier
indiqué par vous, non confirmé par l'annonce »).
- Implications `local_context` (`metz_local.py:211-229`) : ajouter le champ ;
  signature de `local_context` doit recevoir un indicateur « override corroboré ou
  non » depuis `analysis.run_full_analysis` (qui seul connaît override vs extraction).
- Implications `assess_claims` (`metz_local.py:296`) : si réserve, ne PAS rendre
  un claim COHERENT pour un quartier non confirmé (rétrograder en `a_verifier`),
  pour ne pas « bien juger pour la mauvaise raison » (§1.2).
- Contrat : champ OPTIONNEL → rétro-compatible ; nécessite MAJ `api.ts`
  (`LocalContext`) + composant front (`LocalContextCard`). Coût modéré, front
  inclus.

**Option 3 — Suppression du profil curaté dès qu'il y a override non corroboré
(repli ville pur).** Si override ≠ extraction, on n'affiche PAS de profil de
quartier (`local_context = None`) et on reste au niveau ville. Coût : faible
(logique dans `analysis.py`, pas de nouveau champ contrat). Avantage : zéro
« confiant et faux » (on n'affirme rien). Inconvénient : perte de la valeur
ancrage local même quand l'utilisateur a raison (faux négatif) ; UX dégradée si
l'override est légitime (le LLM rate souvent le quartier).

**Recommandation analyste** : **Option 2** (réserve explicite) comme cœur de C2,
adossée à l'Option 1 (repli ville quand non reconnu, déjà acquis). Raison :
honnête (on n'affirme que ce qui est corroboré), conserve la valeur produit,
et le surcoût front est borné (un champ + un libellé). L'Option 3 est le repli si
le fondateur veut zéro risque au prix de la fonctionnalité. **Le seuil de
« correspondance sûre » se réduit alors à une règle binaire et déterministe**
(override corroboré par l'extraction LLM ou non), pas à un score flou — ce qui
évite le fake precision d'un « seuil de confiance » inventé.

### 3.4 Où poser le garde-fou sans casser le schéma

- Décision override-vs-extraction : dans `analysis.run_full_analysis`
  (`analysis.py:184`), qui a accès à `district_override`, `listing["district"]`
  ET `raw_text`. C'est le seul point qui distingue les sources.
- Construction du champ de réserve : passer le verdict (corroboré/non) à
  `local_context`/`assess_claims` (`metz_local.py:211,296`) en nouvel argument
  optionnel (défaut = comportement actuel, pour ne pas casser les appels
  existants ni les tests).
- Sérialisation : aucune contrainte côté `main.py` (`local_context` est un dict
  libre, `main.py:90`). Le seul vrai impact contrat est `frontend/lib/api.ts`
  (`LocalContext`) + le composant d'affichage.

---

## 4. Risques / anti-patterns (leçons + invariants)

- **Leçon index lookup par-ligne** (`lessons.md` 2026-06-14, bienici-couronne) :
  applicable SI le chantier A introduit un filtre/lookup par-ligne à l'INGESTION
  sur une colonne non indexée. **Au palier A tel que cadré, ce n'est PAS le cas** :
  on n'ajoute que des données curatées (listes en mémoire), pas de requête
  d'ingestion. À surveiller seulement si quelqu'un dérive vers un mapping en base.
  Le filtre `Comparable.district`/`city` de `market_stats` est en lecture
  (analyse), pas en ingestion par-ligne — risque non concerné.
- **Faux-vert / falsifiabilité** (`lessons.md` 2026-06-13 cross-agence-inc2b ;
  2026-06-09 9.10) : un test « le profil Sainte-Thérèse s'affiche » ne prouve PAS
  que la résolution « / » fonctionne si l'oracle passe le libellé déjà canonique.
  Tout test C2 doit prouver la FALSIFIABILITÉ : rouge si on retire l'alias / le
  garde-fou. Pour C2, asserter le comportement RÉEL (réserve présente quand
  override ≠ extraction), pas seulement « pas d'erreur 422 ».
- **Bornes/clés à tester aux valeurs exactes** (`lessons.md` 2026-06-04 [9.7]) :
  tester l'égalité des jeux de clés `_PROFILES` ⇄ `_DIST_KM` (sinon faux
  « cohérent » via le défaut `{center:0,gare:0}` `metz_local.py:310`).
- **État partagé / cache** (`lessons.md` photo-evidence, 9.9) : le cas d'éval C2
  passant par `analyze_semantic` doit respecter l'isolation des caches autouse
  déjà en place (conftest). Pas de nouveau cache introduit par A.
- **Invariants CONTEXT §11 / lessons préambule** : (a) ne JAMAIS estimer un prix —
  C2 ne touche pas au scoring ; (b) pas de redistribution d'annonces — le profil
  est curaté, pas re-publié ; (c) ne pas casser le schéma `/analyze` sans MAJ
  `api.ts` — tout champ C2 doit être optionnel + `api.ts` mis à jour
  simultanément ; (d) pas de fake precision (CONTEXT §1.4) — c'est l'objet MÊME de
  C2 : la réserve est la matérialisation de cet invariant.
- **Risque de sur-dimensionnement (posture MVP)** : le rattachement secteur de
  Sainte-Thérèse a un effet prix quasi nul si le pool de comparables du
  micro-quartier est vide ; ne pas créer un secteur propre « par principe ». De
  même, ne pas tenter de résoudre l'inter-communal en A (= chantier C déguisé).

---

## 5. Plan de cas d'éval anti-régression

Process pilote→éval (cf. ombrelle §7, `docs/pilotes/README.md`) : cas SYNTHÉTIQUE
fictif (jamais l'extrait réel, CONTEXT §11.3), harnais désormais multi-cas
(`test_eval_issue_<n>.py`, 1 appel `analyze_semantic` par module, leçon
2026-06-16 evals-harness).

- **C1 réglé (reconnaissance Sainte-Thérèse)** — volet déterministe (suite
  gratuite, sans coût LLM) : annonce fictive nommant « Sainte-Thérèse » →
  `_resolve_key` résout une clé connue → `local_context` non-None avec le bon
  `name`. + test du piège « / » : le libellé `"Sainte-Thérèse / Botanique"`
  résout bien (sinon rouge). + test d'égalité des clés `_PROFILES`/`_DIST_KM`.
- **C2 réglé (pas de confiant-faux)** — déterministe : appeler
  `run_full_analysis` avec `district_override="Nouvelle Ville"` sur un texte
  fictif qui nomme un AUTRE quartier → assertion : le `local_context` porte la
  réserve (Option 2) OU est None/ville (Option 3), et aucun claim n'est rendu
  COHERENT pour le quartier forcé non corroboré. Falsifiabilité : rouge si on
  retire le garde-fou.
- **Cas d'éval LLM** (payant, `evals/cases/`) : OPTIONNEL au palier A. Le volet C2
  est majoritairement déterministe (override vs extraction) → privilégier la suite
  gratuite. N'ajouter un cas LLM que si l'on veut verrouiller que le LLM extrait
  bien « Sainte-Thérèse » comme `listing.district`/`local_claims` (sinon coût pour
  peu de garantie).
- **Note process** (leçon 2026-06-16 evals-harness) : si un cas LLM est ajouté,
  respecter « 1 site `analyze_semantic` par module + 0 hors module » ; ne pas
  coder une cardinalité globale.

---

## 6. QUESTIONS GATE 1 (arbitrages réservés à l'humain)

1. **Rattachement secteur de Sainte-Thérèse.**
   Options réelles : (a) **Nouvelle-Ville** (frange sud, secteur « Centre Ville »
   `market_stats.py:49`) ; (b) **Sablon** (secteur « Sablon » `market_stats.py:44`,
   Sainte-Thérèse jouxte le Sablon au sud) ; (c) **secteur propre**.
   *Reco* : (b) **Sablon**. Argument factuel : la basilique Sainte-Thérèse et son
   quartier sont géographiquement au sud, contigus au Sablon, plus qu'au cœur
   Nouvelle-Ville/gare. Rattacher à « Centre Ville » reproduirait précisément le
   biais du repli pilote (gare/quartier impérial). Effet prix probablement faible
   (pool micro-quartier ~vide) ; l'enjeu est la cohérence du libellé et l'amorçage
   de B. NE PAS créer un secteur propre (sur-dimensionné pour le MVP).

2. **Gestion inter-communale Metz (57000) / Montigny-lès-Metz (57950) pour
   « Botanique ».**
   Options : (a) rattacher « Botanique » à **Metz** par convention curatée et
   documenter l'imprécision ; (b) le rattacher à **Montigny** ; (c) **ne pas
   traiter l'inter-communal en A** (le renvoyer au chantier C, géocodage).
   *Reco* : (c) + documentation explicite. Le filtre `city` exact
   (`market_stats.py:134`) rend toute réconciliation impossible sans adresse
   géocodée ; forcer une commune introduit un biais de pool dans l'autre sens.
   Au palier A, traiter « Sainte-Thérèse » (clairement Metz) et documenter que
   « Botanique » à cheval relève de C. Éviter de rouvrir le hors-périmètre.

3. **Formulation exacte du repli C2 et seuil de « correspondance sûre ».**
   Options : Option 1 (repli ville, existant) / **Option 2 (mention de réserve,
   champ optionnel)** / Option 3 (suppression du profil si override non corroboré).
   *Reco* : **Option 2**, seuil = règle binaire déterministe « override corroboré
   par l'extraction LLM du texte, ou non » (pas de score de confiance flou, qui
   serait lui-même du fake precision). Adosser l'Option 1 (déjà acquise) pour le
   quartier non reconnu. Si tolérance zéro souhaitée au prix de la fonctionnalité :
   Option 3. Important : aucune des options ne « détecte une mauvaise sélection »
   au sens absolu sans géocodage (cf. §0/§3.2) — l'humain doit valider qu'on vise
   bien la divergence override↔annonce, pas une détection géographique réelle.

4. **Exposer « Sainte-Thérèse » dans le sélecteur front (`districts.ts`) ?**
   Options : (a) oui, libellé `"Sainte-Thérèse"` (sans « / Botanique », pour
   éviter le piège séparateur) ; (b) non, le laisser uniquement en
   extraction/alias backend.
   *Reco* : (a) **oui, libellé sans « / »**. Cohérent avec l'intention « débloquer
   le cas pilote » (le pilote a justement cherché l'option dans le sélecteur et ne
   l'a pas trouvée). Condition : le label doit résoudre côté back (alias littéral,
   §2.2) et le rattachement secteur (Q1) doit être fait pour que le choix tombe sur
   le bon pool/contexte. Impact contrat : ajout d'une entrée liste front, sans
   changement de schéma `/analyze`.

5. **(Process, à confirmer) Périmètre des micro-quartiers du lot A.**
   L'ombrelle (§8) liste « liste exacte des micro-quartiers à ajouter au-delà de
   Sainte-Thérèse/Botanique ? » comme question ouverte.
   *Reco* : **s'en tenir STRICTEMENT à Sainte-Thérèse (+ Botanique documenté en
   limite)** pour ce lot. Ajouter d'autres micro-quartiers maintenant
   multiplierait les quadruplets à maintenir (dette que B doit résorber) sans
   nécessité pilote. Tout autre micro-quartier = nouveau lot ou attendre B.

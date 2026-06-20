# SPEC — issue #100, chantier A (palier 1 référentiel géo + garde-fou C2)

> Statut : pré-GATE 2. Spec implémentable issue de l'analyse approuvée
> (`docs/specs/issue-100-A-ANALYSE.md`) + arbitrages GATE 1 (actés par le
> fondateur, repris en §2). Sources relues avant rédaction : `.claude/lessons.md`,
> les deux analyses (#100 ombrelle §0bis/§4/§6 + #100-A), et le code réel
> (`backend/scrapers/base.py`, `backend/app/metz_local.py`,
> `backend/app/market_stats.py`, `backend/app/analysis.py`,
> `backend/app/llm_semantic.py`, `frontend/lib/districts.ts`,
> `frontend/lib/api.ts`).
>
> Le développeur ne code PAS d'après ce préambule : il code d'après les sections
> 3 (contrat technique) et 4 (critères d'acceptation).

---

## 1. Objectif et périmètre

### Objectif
Rendre le micro-quartier **Sainte-Thérèse** (commune Metz) reconnu par les
**quatre référentiels** géographiques, de façon cohérente (même clé canonique
partout) ; et empêcher le système d'**affirmer sans réserve** un profil de
quartier quand l'utilisateur a forcé un quartier (`district_override`) que
l'annonce ne corrobore pas (garde-fou C2, anti-« confiant mais faux »).

### Périmètre IN
1. **Ajout référentiel Sainte-Thérèse** dans les 4 listes :
   - `backend/scrapers/base.py` : `_KNOWN_LOCALITIES` (extraction texte/adresse).
   - `backend/app/metz_local.py` : `_PROFILES`, `_DIST_KM`, `_ALIASES`
     (profil curaté + distances + alias littéraux du libellé composé).
   - `backend/app/market_stats.py` : `_SECTORS_RAW` (secteur propre, cf. §2.1).
   - `frontend/lib/districts.ts` : `METZ_DISTRICTS` (sélecteur front).
2. **Garde-fou C2** : champ de réserve optionnel ajouté à `local_context`,
   posé quand le quartier vient d'un override NON corroboré par l'extraction
   (règle binaire déterministe, §2.3), avec rétrogradation des claims
   correspondants ; MAJ `frontend/lib/api.ts` + rendu front de la réserve.

### Périmètre OUT (hors-périmètre, non-objectifs — cf. §5)
- « Botanique » inter-communal (Metz/Montigny) → chantier C (géocodage) ;
  ici on n'intègre QUE « Sainte-Thérèse » et on documente la limite.
- Tout autre micro-quartier que Sainte-Thérèse.
- « Secteur prisé », écoles/POI (chantier C).
- Unification en source de vérité unique des 4 référentiels (chantier B).
- Géocodage / résolution d'adresse réelle.
- Toute réécriture de `canonical_district` / `canonical_city` (risque de
  régression large ; on contourne par alias littéraux).
- Toute modification du scoring (le contexte local reste non-scoré).

---

## 2. Décisions actées (GATE 1)

### 2.1 Rattachement secteur — SECTEUR PROPRE
Créer dans `_SECTORS_RAW` (`market_stats.py`) un secteur dédié à Sainte-Thérèse
contenant UNIQUEMENT Sainte-Thérèse. NE PAS la rattacher à Sablon ni à
« Centre Ville ».

Conséquence assumée et VOULUE : la cascade secteur (`compute_market_stats`,
`market_stats.py:198-201`) n'emprunte à aucun voisin. Pool quartier vide →
pool secteur identiquement vide → repli ville. C'est délibéré pour ne pas
reproduire le biais du repli pilote (gare/quartier impérial). Effet prix
pratique attendu : quasi nul (pool micro-quartier ~vide en base) ; l'enjeu est
la **cohérence du libellé affiché** et l'amorçage de B.

### 2.2 Inter-communal « Botanique » — NON traité en A
On intègre « Sainte-Thérèse » (clairement Metz). « Botanique » à cheval
Metz/Montigny relève du chantier C : le filtre `Comparable.city` EXACT
(`market_stats.py:134`) empêche toute réconciliation inter-communale sans
adresse géocodée. À DOCUMENTER dans le code (commentaire) et dans cette spec,
pas à implémenter.

### 2.3 Garde-fou C2 — RÉSERVE EXPLICITE (Option 2), règle binaire déterministe
- On vise la **divergence override↔annonce**, PAS une détection géographique
  réelle (impossible sans géocodage : `district_override` reste la source la
  plus fiable, `analysis.py:85-91`).
- Règle **binaire déterministe** : un quartier est *corroboré* ou *non
  corroboré*. PAS de score de confiance flou (ce serait du fake precision,
  CONTEXT §11 / CLAUDE §1).
- Champ **optionnel** ajouté à `local_context` → contrat `/analyze` non cassé
  (CLAUDE §10) ; `frontend/lib/api.ts` mis à jour simultanément.
- On CONSERVE l'Option 1 (repli ville quand quartier non reconnu) déjà acquise
  (`local_context` renvoie `None` si `_resolve_key` échoue).

### 2.4 Sélecteur front
Ajouter le libellé **`"Sainte-Thérèse"`** (SANS « / », pour éviter le piège
séparateur) à `METZ_DISTRICTS`. Ce label doit résoudre côté backend vers la
même clé canonique que les autres référentiels (§3.6).

### 2.5 Périmètre micro-quartiers
STRICTEMENT Sainte-Thérèse (+ « Botanique » documenté en limite). Aucun autre
micro-quartier.

---

## 3. Contrat technique (conception par fichier)

### 3.0 Clé canonique cible (invariant pivot)
La clé canonique de Sainte-Thérèse est **`"Sainte-Therese"`** (sans accent,
tiret unique, segments capitalisés), car `canonical_city("Sainte-Thérèse")`
(`base.py:206-211`) produit `"Sainte-Therese"`. Les 4 référentiels DOIVENT tous
résoudre vers cette même clé. C'est l'invariant central testé en AC10.

**Piège séparateur « / » (confirmé par lecture du code)** :
`canonical_district("Sainte-Thérèse / Botanique", "Metz")` ne split que sur
`" - "` (`base.py:309`) → un seul segment → `canonical_city(...)` split sur
`r"[\s\-]+"` (`base.py:210`), le « / » N'est NI espace NI tiret → il survit en
segment → clé `"Sainte-Therese-/-Botanique"`, qui ne matche aucune entrée
`_PROFILES`. Donc : NE PAS exposer le libellé « / » ; et si le LLM extrait un
libellé composé, prévoir un **alias littéral** (§3.2) pour qu'il résolve.
INTERDICTION de modifier `canonical_district` / `canonical_city` (hors
périmètre, §1 OUT).

### 3.1 `backend/scrapers/base.py` — `_KNOWN_LOCALITIES`
Ajouter les formes lower-case du quartier, en respectant la consigne du
commentaire (`base.py:327` : libellés longs AVANT libellés courts). Formes
minimales requises :
- `"sainte-thérèse"`
- `"sainte-therese"` (variante sans accent)

`extract_district` (`base.py:364-377`) fait un substring match et renvoie
`locality.title()` → `"sainte-thérèse"` devient `"Sainte-Thérèse"`, qui
canonicalise ensuite en `"Sainte-Therese"`. NE PAS ajouter `"botanique"`
(hors périmètre, §2.2 ; éviterait aussi un faux positif sur le mot « botanique »
hors contexte adresse).

Aucune modification de la signature `extract_district`.

### 3.2 `backend/app/metz_local.py` — `_PROFILES`, `_DIST_KM`, `_ALIASES`
- **`_PROFILES["Sainte-Therese"]`** : entrée curatée avec les clés du même
  schéma que l'existant (`name`, `center`, `gare`, `caractere`). `name` =
  libellé affiché `"Sainte-Thérèse"` (accent conservé). Distances exprimées en
  approximatif (« ~ ») — pas de fausse précision (CONTEXT §11). Valeurs
  géographiques curatées par le développeur (quartier sud de Metz, contigu au
  Sablon) ; le testeur n'oracle PAS les valeurs exactes de distance (curaté),
  il oracle la PRÉSENCE et le `name`.
- **`_DIST_KM["Sainte-Therese"]`** : `{"center": <km approx>, "gare": <km
  approx>}`. OBLIGATOIRE en même temps que `_PROFILES` : si la clé manque dans
  `_DIST_KM`, `assess_claims` (`metz_local.py:310`) retombe sur le défaut
  `{center:0, gare:0}` → faux « cohérent ». Verrouillé par AC9 (égalité des
  jeux de clés).
- **`_ALIASES`** : ajouter les alias littéraux des formes composées susceptibles
  d'être extraites par le LLM ou saisies, mappés vers `"Sainte-Therese"`. Au
  minimum la forme canonique du libellé composé piégé :
  - `"Sainte-Therese-/-Botanique"` → `"Sainte-Therese"` (clé produite par le
    piège « / », §3.0).
  Les alias sont des clés CANONIQUES (telles que produites par `_resolve_key`),
  pas des libellés bruts (cf. `_ALIASES` existant, `metz_local.py:189-195`).

### 3.3 `backend/app/market_stats.py` — `_SECTORS_RAW`
Ajouter un secteur propre :
```python
"Sainte-Thérèse": ["Sainte-Thérèse"],
```
(libellé brut ; `_build_sector_maps`, `market_stats.py:74-90`, le canonicalise au
chargement en `"Sainte-Therese"` via `canonical_district`). Effet : `_DISTRICT_TO_SECTOR["Sainte-Therese"] = "Sainte-Thérèse"` et
`_SECTOR_DISTRICTS["Sainte-Thérèse"] = ["Sainte-Therese"]`. La cascade secteur ne
contient donc que Sainte-Thérèse (aucun emprunt voisin, §2.1).

### 3.4 `frontend/lib/districts.ts` — `METZ_DISTRICTS`
Ajouter l'entrée `"Sainte-Thérèse"` (libellé sans « / »). Position libre dans la
liste. Le label est envoyé tel quel à `/analyze` (`api.ts:62`) comme `district`
→ `district_override`.

### 3.5 Garde-fou C2 — backend

#### 3.5.1 Décision corroboré / non corroboré (`analysis.py`)
Le seul point qui connaît à la fois l'override et l'extraction est
`run_full_analysis` (`analysis.py:166-203`). On y calcule un booléen
**déterministe** `district_corroborated` selon la règle binaire :

- Soit `K_used = _resolve_key(district_retenu, city)` où `district_retenu` est
  le quartier effectivement utilisé (= sortie de `_resolve_district`).
- La réserve C2 ne s'applique QUE lorsque le quartier retenu provient d'un
  **override** ET qu'un profil curaté est effectivement affiché (`local_ctx`
  non `None`). Si pas d'override, ou `local_ctx is None` (quartier non reconnu,
  Option 1 déjà honnête), aucune réserve.
- `district_corroborated` est **vrai** si la clé de l'override (`K_override =
  _resolve_key(district_override, city)`) est ÉGALE à la clé issue de
  l'extraction de l'annonce :
  `K_extracted = _resolve_key(listing.get("district") or extract_district(raw_text), city)`.
- Il est **faux** si `K_override` et `K_extracted` résolvent à des clés
  DIFFÉRENTES, OU si `K_extracted is None` (l'annonce ne fournit AUCUN quartier
  reconnu qui confirme l'override).

Note de sémantique (à respecter pour la falsifiabilité) : la réserve traduit
« quartier indiqué par vous, non confirmé par l'annonce ». L'absence de signal
d'annonce (`K_extracted is None`) est traitée comme **non corroborée** (on
n'invente pas une confirmation).

#### 3.5.2 Propagation à `metz_local`
Le verdict (`corroborated: bool`) est passé en **argument optionnel nouveau** à
`local_context` et `assess_claims`, avec une valeur par défaut qui PRÉSERVE le
comportement actuel (aucune réserve) pour ne casser ni les appels existants ni
les tests existants.

Signatures cibles (le nom exact de l'argument est laissé au développeur ;
proposition : `district_corroborated: Optional[bool] = None`) :
```python
def local_context(district, city="Metz", district_corroborated: Optional[bool] = None) -> Optional[Dict[str, Any]]: ...
def assess_claims(district, claims, city="Metz", dist_override=None, district_corroborated: Optional[bool] = None) -> List[Dict[str, str]]: ...
```
Sémantique de l'argument :
- `None` (défaut) ou `True` → aucune réserve ; comportement actuel inchangé.
- `False` → réserve : `local_context` ajoute le champ de réserve (§3.5.3) ;
  `assess_claims` rétrograde en `a_verifier` tout claim qui serait sinon rendu
  `coherent` (ne pas « bien juger pour la mauvaise raison », analyse §1.2).
  La rétrogradation NE concerne que les claims `coherent` → `a_verifier` ; les
  `peu_plausible` et `a_verifier` restent inchangés. La note du claim
  rétrogradé doit mentionner que le quartier n'est pas confirmé par l'annonce.

`run_full_analysis` ne passe `district_corroborated=False` que dans la branche
**sans géocodage** (`else`, `analysis.py:197-202`) et uniquement quand
l'override est non corroboré ET `local_ctx is not None`. La branche géocodée
(couche C) n'est PAS concernée par C2 au palier A (le géocodage est la source de
vérité ; hors périmètre).

#### 3.5.3 Contrat exact du champ de réserve (`local_context`)
- **Nom** : `district_caveat`.
- **Type** : `string` (ou absent).
- **Présent** uniquement quand la réserve s'applique (override non corroboré,
  profil affiché). **Absent** (clé non présente dans le dict) dans tous les
  autres cas : quartier corroboré, pas d'override, quartier non reconnu
  (`local_context is None`), ou branche géocodée.
- **Valeur** : un libellé court, déterministe et stable, p.ex. :
  `"Quartier indiqué par vous, non confirmé par l'annonce."`
  La valeur exacte est curatée ; l'AC teste la PRÉSENCE/ABSENCE de la clé, pas
  le wording mot à mot (sauf substring stable, cf. AC6).
- Champ OPTIONNEL → le schéma `/analyze` reste rétro-compatible : `main.py`
  expose `local_context` en `Optional[Dict[str, Any]]` (dict libre), aucune
  contrainte de sérialisation à modifier côté `main.py`.

### 3.6 Front — `frontend/lib/api.ts` + rendu
- Étendre l'interface `LocalContext` (`api.ts:30-39`) avec :
  ```ts
  district_caveat?: string;
  ```
  Optionnel → rétro-compatible avec les anciennes réponses.
- Rendu attendu (composant `LocalContextCard`) : quand `district_caveat` est
  présent, afficher une **mention de réserve** visible (texte d'avertissement)
  au niveau du bloc « Contexte local ». Quand absent, rendu inchangé. Pas
  d'emoji. (Le détail visuel est libre ; l'AC front porte sur la présence du
  champ dans le type et l'affichage conditionnel.)
- Pas d'autre changement de contrat : `actions`, `pillars`, `global_score`,
  etc. inchangés.

---

## 4. Critères d'acceptation (numérotés, testables)

> Convention : AC déterministes = suite gratuite `backend/tests/`. Placer les
> nouveaux tests dans un fichier dédié `backend/tests/test_issue_100_A.py`
> (évite la dépendance cachée à un oracle de harnais qui exécute un fichier
> existant en sous-processus, leçon 2026-06-12 fix-issue-80). Tests front :
> selon l'outillage front existant (au minimum, AC13 est statique sur le
> fichier). Isolation : s'appuyer sur les fixtures autouse du `conftest.py`
> (init_db session-scope, reset caches) ; ne PAS introduire de nouveau cache.

### Reconnaissance Sainte-Thérèse via les 4 chemins

**AC1 — Extraction texte (`base._KNOWN_LOCALITIES`).**
`extract_district("Bel appartement quartier Sainte-Thérèse à Metz")` retourne
une valeur non `None` dont `canonical_city(...)` (ou `canonical_district(..., "Metz")`)
égale `"Sainte-Therese"`.
Falsifiabilité : rouge si l'entrée est retirée de `_KNOWN_LOCALITIES`.

**AC2 — Extraction variante sans accent.**
`extract_district("appartement sainte-therese metz")` retourne une valeur
résolvant vers `"Sainte-Therese"`.

**AC3 — Profil curaté (`metz_local.local_context`).**
`local_context("Sainte-Thérèse", "Metz")` retourne un dict non `None` dont
`["district"] == "Sainte-Thérèse"`, `["summary"]` est non vide, `["facts"]` est
non vide, et `["precision"] == "quartier"`.
Falsifiabilité : rouge si l'entrée `_PROFILES["Sainte-Therese"]` est retirée.

**AC4 — Alias littéral du libellé composé « / ».**
`local_context("Sainte-Thérèse / Botanique", "Metz")` retourne le profil
Sainte-Thérèse (dict non `None`, `["district"] == "Sainte-Thérèse"`), prouvant
que l'alias littéral résout le piège séparateur.
Falsifiabilité : rouge si l'alias `"Sainte-Therese-/-Botanique"` est retiré de
`_ALIASES`. (Ce test échoue AUSSI si quelqu'un croit à tort que
`canonical_district` gère le « / » — c'est l'intention.)

**AC5 — Secteur propre (`market_stats`).**
Après chargement du module, `_DISTRICT_TO_SECTOR["Sainte-Therese"]` existe et
`_SECTOR_DISTRICTS[_DISTRICT_TO_SECTOR["Sainte-Therese"]] == ["Sainte-Therese"]`
(secteur ne contenant QUE Sainte-Thérèse, aucun voisin).
Falsifiabilité : rouge si l'entrée `_SECTORS_RAW` est retirée, OU si un autre
quartier est ajouté au même secteur.

### Garde-fou C2

**AC6 — Override NON corroboré → réserve présente + claims rétrogradés.**
Appel `run_full_analysis` (LLM mocké/façade pour fixer `listing.district` à un
quartier reconnu DIFFÉRENT de l'override, p.ex. `listing.district="Sainte-Thérèse"`),
avec `district_override="Nouvelle Ville"`, sans adresse. Assertions :
1. `result["local_context"]` est non `None` et contient la clé
   `district_caveat` (substring stable « non confirmé » présent dans la valeur) ;
2. `result["local_context"]["district"] == "Nouvelle Ville"` (l'override reste
   appliqué, on ne supprime pas le profil — Option 2, pas Option 3) ;
3. aucun claim de `result["local_context"]["claims"]` n'a `status == "coherent"`
   (tout claim sinon cohérent est rétrogradé `a_verifier`).
Falsifiabilité : rouge si le garde-fou C2 est retiré (le champ
`district_caveat` disparaît et/ou un claim redevient `coherent`).

**AC7 — Override corroboré → pas de réserve.**
Même appel mais `district_override` et `listing.district` résolvent à la MÊME
clé (p.ex. les deux à `"Sainte-Thérèse"` / `"Sainte-Therese"`). Assertions :
1. `result["local_context"]` est non `None` ;
2. la clé `district_caveat` est ABSENTE du dict.
Falsifiabilité : rouge si la réserve est posée inconditionnellement.

**AC8 — Pas d'override → pas de réserve (non-régression du défaut).**
`run_full_analysis` sans `district_override`, l'extraction fournissant un
quartier reconnu. `result["local_context"]` (si non `None`) NE contient PAS la
clé `district_caveat`. Le comportement par défaut de `local_context` /
`assess_claims` (arguments à `None`) est strictement inchangé.

### Cohérence inter-référentiels et non-régression

**AC9 — Égalité des jeux de clés `_PROFILES` ⇄ `_DIST_KM`.**
`set(_PROFILES.keys()) == set(_DIST_KM.keys())`.
Falsifiabilité : rouge si Sainte-Thérèse est ajoutée à `_PROFILES` mais oubliée
dans `_DIST_KM` (ou inversement). (Verrouille le faux « cohérent » via le défaut
`{center:0,gare:0}`, `metz_local.py:310`.)

**AC10 — Convergence des 4 référentiels vers la même clé.**
Pour le libellé front `"Sainte-Thérèse"` (`districts.ts`), la valeur extraite par
`extract_district`, et le libellé `_SECTORS_RAW`, tous résolvent vers la clé
canonique `"Sainte-Therese"` ; et cette clé est présente dans `_PROFILES`,
`_DIST_KM`, et `_DISTRICT_TO_SECTOR`. (Test backend ; le label front est
référencé par sa valeur littérale `"Sainte-Thérèse"`.)
Falsifiabilité : rouge si l'un des 4 référentiels résout vers une clé différente
(p.ex. accent/casse divergents).

**AC11 — Non-régression des autres quartiers (profils).**
Pour un échantillon de quartiers préexistants (au moins `"Nouvelle Ville"`,
`"Sablon"`, `"Centre-Ville"`), `local_context(q, "Metz")` retourne toujours le
profil attendu (dict non `None`, `["district"]` correct), inchangé par l'ajout.

**AC12 — Non-régression de la cascade secteur existante.**
Les secteurs préexistants de `_SECTORS_RAW` sont intacts : en particulier
`_DISTRICT_TO_SECTOR["Nouvelle-Ville"] == "Centre Ville"` (inchangé), et le
nombre de quartiers du secteur « Centre Ville » est inchangé (Sainte-Thérèse
n'y a PAS été ajoutée — vérifie l'arbitrage 2.1).

### Front

**AC13 — Sélecteur front contient le libellé sans « / ».**
`METZ_DISTRICTS` (`frontend/lib/districts.ts`) contient l'entrée exacte
`"Sainte-Thérèse"` et NE contient AUCUNE entrée comportant « / ».
(Test statique sur le fichier ; falsifiabilité : rouge si l'entrée manque ou si
une forme « Sainte-Thérèse / Botanique » est introduite.)

**AC14 — Type `LocalContext` porte le champ optionnel.**
`frontend/lib/api.ts` déclare `district_caveat?: string` dans l'interface
`LocalContext`, et l'affichage conditionne une mention de réserve à la présence
de ce champ. (Au minimum test statique de présence du champ dans le type ;
l'affichage est vérifié selon l'outillage front disponible.)

### Limite documentée (anti sur-promesse)

**AC15 — « Botanique » non intégré, limite documentée.**
`"botanique"` N'est PAS ajouté à `_KNOWN_LOCALITIES`, et un commentaire dans
le code (au choix `base.py` près de `_KNOWN_LOCALITIES` ou `metz_local.py`)
documente que l'inter-communal « Botanique » Metz/Montigny relève du chantier C.
(Test statique : substring « Botanique » absent de `_KNOWN_LOCALITIES` ;
présence d'un commentaire de renvoi au chantier C.)

### Cas d'éval LLM (suite payante `backend/evals/`)

**AC16 — Éval LLM : OPTIONNEL au palier A, conditionnel.**
Le volet C2 est majoritairement déterministe (override vs extraction) →
privilégier la suite gratuite (AC1-AC15). N'ajouter un cas LLM QUE si l'on veut
verrouiller que le LLM extrait bien « Sainte-Thérèse » comme `listing.district`
/ `local_claims` à partir d'un texte fictif.
SI un cas est ajouté :
- placement : un module dédié `backend/evals/test_eval_issue_100_A.py` (cas
  SYNTHÉTIQUE fictif, jamais l'extrait pilote réel — CONTEXT §11.3) ;
- politique : **exactement 1** site d'appel `analyze_semantic` PAR module (dans
  une fixture `scope="module"`), 0 hors module — NE PAS coder une cardinalité
  globale (leçon 2026-06-16 evals-harness) ;
- toute fixture consommée par un `xfail` doit l'être aussi par au moins un test
  bloquant de la même suite (leçon 2026-06-12 evals-harness) ;
- xfail `strict=False` pour un oracle LLM dont le passage n'est pas garanti.

---

## 5. Hors-périmètre / non-objectifs (rappel borné)

- Pas de résolution inter-communale « Botanique » (chantier C).
- Pas d'autre micro-quartier que Sainte-Thérèse.
- Pas de modification de `canonical_district` / `canonical_city`.
- Pas de modification du scoring ni des piliers (`local_context` reste
  non-scoré).
- Pas de score de confiance flou : la réserve C2 est binaire (présent/absent).
- Pas de détection géographique « vraie » : on ne détecte que la divergence
  override↔extraction.
- Pas de géocodage ; la branche couche C n'est pas modifiée.

---

## 6. Conformité (anti-patterns applicables)

- **Pas de fake precision (CONTEXT §11 / CLAUDE §1)** : la réserve C2 EST la
  matérialisation de cet invariant ; règle binaire, pas de seuil inventé. Les
  distances Sainte-Thérèse restent approximatives (« ~ »).
- **Pas d'estimation de prix** : C2 et l'ajout référentiel ne touchent pas au
  scoring ni au calcul des quartiles.
- **Pas de redistribution d'annonces brutes** : le profil est curaté, pas
  re-publié ; aucun champ d'annonce brute ajouté.
- **Contrat `/analyze` stable (CLAUDE §10)** : `district_caveat` est OPTIONNEL ;
  `frontend/lib/api.ts` est mis à jour dans le même lot. Aucune clé existante
  modifiée/supprimée.
- **Pas de secret en clair** : sans objet (pas de secret introduit).
- **Logging nommé, Python 3.12, pas de commentaire « what », pas d'emoji**
  (CLAUDE §12) : respecter dans tout code ajouté.

---

## 7. Points d'attention anti-régression (leçons)

- **Faux-vert / falsifiabilité** (leçons 2026-06-13, 2026-06-09 9.10) : chaque
  AC C2 et chaque AC référentiel DOIT être falsifiable (rouge si l'on retire
  l'alias / l'entrée / le garde-fou). En particulier AC4 prouve le piège « / »
  (l'oracle ne doit PAS passer un libellé déjà canonique), AC6 asserte le
  comportement RÉEL (réserve présente + claim rétrogradé), pas une simple
  absence d'erreur.
- **Clés dupliquées `_PROFILES`/`_DIST_KM`** (leçon 2026-06-04 9.7, bornes) :
  AC9 verrouille l'égalité des jeux de clés (sinon faux « cohérent » via défaut
  `{center:0,gare:0}`).
- **Index lookup par-ligne à l'ingestion** (leçon 2026-06-14) : NON applicable —
  le chantier A n'ajoute QUE des données curatées en mémoire (listes/dicts),
  aucune requête d'ingestion ni colonne filtrée par-ligne. Le filtre
  `Comparable.district`/`city` de `market_stats` est en LECTURE (analyse), pas
  en ingestion. À confirmer au review : aucun nouveau `filter`/`get` par-ligne
  à l'ingestion n'est introduit.
- **Isolation des tests** (leçons 9.7, 9.9, photo-evidence) : réutiliser les
  fixtures autouse du `conftest.py` (init_db session-scope, reset caches LLM/
  photo). NE PAS introduire de nouveau cache module-global. Les assertions de
  `run_full_analysis` filtrent sur des objets construits dans le test, pas sur
  des compteurs absolus.
- **Fichier de tests dédié** (leçon 2026-06-12 fix-issue-80) : placer les
  nouveaux tests déterministes dans `backend/tests/test_issue_100_A.py` pour ne
  pas heurter un oracle de harnais qui exécuterait un fichier existant en
  sous-processus.
- **Argument optionnel à défaut neutre** : le nouvel argument
  `district_corroborated` de `local_context`/`assess_claims` a un défaut
  (`None`) qui préserve EXACTEMENT le comportement actuel → les appels et tests
  existants (couche C géocodée incluse) ne changent pas (AC8, AC11).

---

## 8. Découpage des push

Tout tient dans un lot cohérent (peu de fichiers, suite gratuite uniquement sauf
AC16 optionnel). Découpage recommandé :

- **Push 1 — Référentiel (4 listes) + cohérence.**
  `base.py` (`_KNOWN_LOCALITIES` + commentaire AC15), `metz_local.py`
  (`_PROFILES`/`_DIST_KM`/`_ALIASES`), `market_stats.py` (`_SECTORS_RAW`),
  `frontend/lib/districts.ts`. Tests : AC1-AC5, AC9-AC13, AC15.
- **Push 2 — Garde-fou C2.**
  `analysis.py` (décision corroboré/non), `metz_local.py` (argument optionnel +
  champ `district_caveat` + rétrogradation claims), `frontend/lib/api.ts` +
  rendu. Tests : AC6-AC8, AC14.
- **Push 3 (conditionnel) — Éval LLM** si retenu (AC16) :
  `backend/evals/test_eval_issue_100_A.py`. Suite payante (`evals.yml`), à
  exécuter via la CI évals, jamais par la suite gratuite.

Règle de clôture (leçon 2026-06-12) : avant de clore une phase, diff du commit
confronté à la liste de contenu du push ci-dessus, suite par suite (les AC
répartis sur `tests/` gratuit ET `evals/` payant ne sont pas tous visibles
localement).

---

SPEC prête pour GATE 2 (approbation humaine).

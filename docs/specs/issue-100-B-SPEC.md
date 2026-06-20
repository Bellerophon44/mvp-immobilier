# SPEC — issue #100, chantier B (gazetteer unique des quartiers de Metz)

> Statut : pré-GATE 2. Spec implementable issue de l'analyse approuvee
> (`docs/specs/issue-100-B-ANALYSE.md`) + arbitrages GATE 1 (actes par le
> fondateur, repris en §2). Sources relues avant redaction : `.claude/lessons.md`,
> les analyses (#100 ombrelle §4/§6, #100-B), la SPEC A (`issue-100-A-SPEC.md` :
> cle pivot, piege « / », style des AC, fichier de tests dedie), et le code reel
> (`backend/scrapers/base.py`, `backend/app/metz_local.py`,
> `backend/app/market_stats.py`, `frontend/lib/districts.ts`,
> `backend/scrapers/sources/bienici.py`, `backend/tests/test_issue_100_A.py`).
>
> Le developpeur ne code PAS d'apres ce preambule : il code d'apres les sections
> 3 (contrat technique : schema + derivations) et 4 (criteres d'acceptation).
>
> B est un **refactor PUR** : comportement strictement identique. Toute valeur
> qui change un seul derive est un echec, sauf l'harmonisation explicite de la
> cle `_SECTORS_RAW` (§2 Q6) qui PRESERVE l'affichage.

---

## 1. Objectif et perimetre

### Objectif
Remplacer les quatre referentiels geographiques aujourd'hui dupliques et
desynchronisables (`_KNOWN_LOCALITIES`, `_PROFILES`/`_DIST_KM`/`_ALIASES`,
`_SECTORS_RAW`, `METZ_DISTRICTS`) par **une source unique backend** — un module
Python de donnees, le « gazetteer » des quartiers de Metz — dont **derivent**
les usages existants, sans aucun changement de comportement observable.

### Perimetre IN
1. Creer le module `backend/app/geo_gazetteer.py` : une entree typee par
   quartier (§3.2), source unique du vocabulaire ET des donnees curatees.
2. Faire **deriver** depuis le gazetteer, par fonctions pures calculees a
   l'import (comme `_build_sector_maps` aujourd'hui) :
   - `scrapers/base._KNOWN_LOCALITIES` (partie quartiers) ;
   - `metz_local._PROFILES`, `metz_local._DIST_KM`, `metz_local._ALIASES` ;
   - `market_stats._SECTORS_RAW` (et donc `_DISTRICT_TO_SECTOR` /
     `_SECTOR_DISTRICTS`).
3. **Harmoniser la cle `_SECTORS_RAW`** : separer `sector_key` (forme canonique)
   et `sector_display` (libelle affiche exact), en PRESERVANT a l'identique le
   `scope_name` expose au front (§2 Q6, §3.4).
4. **Verrouiller la coherence front** par un test statique backend :
   l'ensemble des libelles `in_selector` du gazetteer == `METZ_DISTRICTS` lu
   dans `frontend/lib/districts.ts` (Strategie C ; pas de build step, pas
   d'endpoint, §2 Q2). `districts.ts` reste maintenu en TS.
5. Garantir **par construction** que `_PROFILES` et `_DIST_KM` ont les memes
   cles (resout structurellement la classe de bug verrouillee par l'AC9 de A).
6. Migration **incrementale, referentiel par referentiel, derriere
   golden-tests** captures AVANT migration depuis l'ANCIEN code (§3.5, §6).

### Perimetre OUT (hors-perimetre, non-objectifs — cf. §5)
- Correction des **trous de couverture** detectes (Ancienne-Ville / Les-Iles
  absents de `_KNOWN_LOCALITIES`) : DOCUMENTES, PAS corriges (lot ulterieur ;
  les corriger changerait le comportement → ce ne serait plus un refactor pur).
- Geocodage reel / remplissage des centroides mesures (chantier C). Le champ
  `centroid` est PREVU dans le schema mais reste vide/nullable en B.
- Reconciliation inter-communale « Botanique » Metz/Montigny (chantier C).
- Toute reecriture de `canonical_district` / `canonical_city` : le gazetteer
  DERIVE ses formes via ces fonctions, il ne les remplace pas (cf. §2, risque
  MAJEUR : ces fonctions produisent la valeur stockee a l'ingestion).
- Toute modification du contrat `/analyze` ni de `frontend/lib/api.ts`.
- Absorption des **communes** de la couronne dans le gazetteer : le gazetteer =
  quartiers seuls (§2 Q5). La liste des communes de `_KNOWN_LOCALITIES` reste
  geree separement.
- Ajout de NOUVEAUX quartiers (B unifie l'existant tel quel).
- Build step de generation de `districts.ts` ou endpoint API `/districts`.

---

## 2. Decisions actees (GATE 1)

### Q1 — Format de la source : MODULE PYTHON DE DONNEES
Le gazetteer est un module Python typE (dict d'entrees + dataclasses/TypedDict),
PAS un JSON/YAML. Importable directement, teste sans parsing runtime, sans etape
de chargement/validation faillible sur le chemin `/analyze`. Les derives sont des
structures calculees a l'import (comme `_build_sector_maps`, `market_stats.py:96`).

### Q2 — Synchronisation du front : PROJECTION + TEST DE COHERENCE (Strategie C)
`frontend/lib/districts.ts` reste maintenu en TS. Un test backend statique sur
le fichier verifie qu'il derive EXACTEMENT du gazetteer : l'ensemble des libelles
`in_selector` du gazetteer == l'ensemble de `METZ_DISTRICTS`. PAS de build step,
PAS d'endpoint API. La « source unique » est assumee comme : backend unifie +
front projete et verrouille par test de coherence. Tout quartier `in_selector`
ajoute/retire au gazetteer sans MAJ de `districts.ts` fait rougir la CI.

### Q3 — Rythme : MIGRATION INCREMENTALE, REFERENTIEL PAR REFERENTIEL
Derriere des golden-tests captures AVANT migration depuis l'ANCIEN comportement
(valeurs figees dans le test, jamais regenerees depuis le gazetteer). Push
decoupes par referentiel migre (§6). Chaque bascule garde tous les goldens verts.

### Q4 — Ampleur : REFACTOR PUR
Comportement strictement identique : memes cles reconnues, memes profils, memes
distances, memes secteurs, meme selecteur, meme valeur stockee a l'ingestion. Les
trous de couverture (Ancienne-Ville / Les-Iles absents de `_KNOWN_LOCALITIES`)
sont HORS PERIMETRE : documentes (§5, AC), pas corriges.

### Q5 — Schema : QUARTIERS SEULS
Le gazetteer modelise les quartiers de Metz, PAS les communes de la couronne. La
presence des communes (`montigny-lès-metz`, `woippy`…) dans `_KNOWN_LOCALITIES`
est conservee separement (liste de communes maintenue a part, concatenee a la
derivation quartiers — §3.3.1). `_METRO_CITIES` (`market_stats.py:64-77`) n'est
PAS touche (deja une source unique propre).

### Q6 — Dette A : HARMONISER LA CLE `_SECTORS_RAW`
Separer `sector_key` (forme canonique) et `sector_display` (libelle affiche
exact). L'affichage actuel (`scope_name` expose au front via `_scope_context`,
`market_stats.py:263-276`) doit rester EXACTEMENT identique pour tous les
secteurs existants. Cela resout la lecon 2026-06-16 : la cle
`_SECTORS_RAW["Sainte-Therese"]` (forme canonique non-accentuee, `market_stats.py:50`)
est aujourd'hui incoherente avec les autres cles qui sont des libelles affiches
accentues (« Centre Ville », « Bellecroix - Vallieres »). Apres B, la cle de
dict secteur disparait au profit de `sector_key` + `sector_display` ; le
`scope_name` derive doit rester :
- pour Sainte-Therese : `sector_display` = **`"Sainte-Thérèse"`** (accentue),
  alors que la cle source actuelle est `"Sainte-Therese"` (non accentue). C'est
  le seul `scope_name` qui CHANGE de valeur source, mais il converge vers le
  libelle accentue attendu, jamais affiche aujourd'hui (secteur mono-quartier).
  Verrouille par AC8.
- pour tous les autres secteurs : `sector_display` strictement egal a l'actuelle
  cle de `_SECTORS_RAW` (« Centre Ville », « Bellecroix - Vallieres »,
  « Plantières-Queuleu », « Patrotte-Metz-Nord », « Devant-les-Ponts »,
  « Sablon », « Magny », « Borny »). Verrouille par AC4/AC7.

---

## 3. Contrat technique

### 3.0 Invariant pivot (rappel, identique a A)
La cle canonique de chaque quartier est la sortie de `canonical_city`
(`base.py:194-211`) appliquee a son libelle (ex. `"Sainte-Thérèse"` →
`"Sainte-Therese"` ; `"Nouvelle Ville"` → `"Nouvelle-Ville"`). Les profils
existants (`_PROFILES`, `metz_local.py:64-170`) sont deja dans cette forme. Le
gazetteer reprend ces cles canoniques comme cle primaire d'entree. INTERDICTION
de modifier `canonical_district` / `canonical_city` : le gazetteer les APPELLE
pour deriver, il ne les reimplemente pas (§5, risque MAJEUR ingestion).

Piege separateur « / » (confirme par le code, `metz_local.py:205-209`) : il
survit a la canonicalisation (« / » n'est ni espace ni tiret). Le gazetteer doit
conserver `aliases_canon` contenant la forme canonique piegee
`"Sainte-Therese-/-Botanique"` → `"Sainte-Therese"` (sinon AC4 de A regresse).

### 3.1 Nom de fichier et structure du module
Fichier : `backend/app/geo_gazetteer.py`.

Une **entree par quartier**, indexee par cle canonique. Champs :

| Champ | Type | Obligatoire | Derive vers / role |
|---|---|---|---|
| `canonical_key` | `str` | oui | cle pivot (= cle du dict). Cle de `_PROFILES`, `_DIST_KM`, `_DISTRICT_TO_SECTOR`. |
| `display_label` | `str` | oui | libelle affiche accentue. → `_PROFILES[k]["name"]`, libelle `_SECTORS_RAW`, projection front si `in_selector`. |
| `aliases_text` | `list[str]` | oui (peut etre `[]` minimal mais au moins la forme lower du label) | formes lower-case (accents conserves + variantes sans accent) → partie quartiers de `_KNOWN_LOCALITIES` (substring match). |
| `aliases_canon` | `list[str]` | oui (souvent `[]`) | cles canoniques de variantes/pieges (« / », libelles composes) → `_ALIASES`. |
| `sector_key` | `str` | oui | forme canonique du secteur de rattachement. Sert au regroupement (group-by) et a `_DISTRICT_TO_SECTOR` (valeur = `sector_display`). |
| `sector_display` | `str` | oui | libelle secteur affiche exact (`scope_name`). → cle de `_SECTOR_DISTRICTS` et valeur de `_DISTRICT_TO_SECTOR`. |
| `commune` | `str` | oui (`"Metz"` partout en B) | commune de rattachement (prepare l'inter-communal C). Non consomme en B au-dela d'etre present. |
| `postal_code` | `Optional[str]` | non (nullable) | informatif (prepare C). Non consomme en B. |
| `centroid` | `Optional[tuple[float, float]]` | non (nullable, **vide en B**) | PREVU pour C (geocodage). Doit etre `None` partout en B. |
| `profile` | dict `{center: str, gare: str, caractere: str}` | oui | → `_PROFILES[k]` (avec `name = display_label`). Valeurs curatees, reprises a l'identique de l'actuel `_PROFILES`. |
| `dist_km` | dict `{center: float, gare: float}` | oui | → `_DIST_KM[k]`. Reprises a l'identique de l'actuel `_DIST_KM`. |
| `in_selector` | `bool` | oui | expose ou non au selecteur front. `True` ssi le quartier est dans `METZ_DISTRICTS` aujourd'hui. → projection front (Q2). |

Representation au choix du developpeur : `@dataclass(frozen=True)` ou `TypedDict`.
Le dict racine `GAZETTEER: dict[str, GazetteerEntry]` est la source. Les valeurs
de `profile`, `dist_km`, `display_label`, `aliases_*`, `sector_*` doivent etre
copiees a l'identique de l'etat actuel (golden, §3.5).

Couplage garanti par construction : `profile` et `dist_km` etant deux champs de
LA MEME entree, `_PROFILES` et `_DIST_KM` derivent du meme jeu de cles → egalite
des cles structurelle (AC2).

### 3.2 Periode de couverture initiale du gazetteer (inventaire)
Les 17 quartiers actuellement dans `_PROFILES` (`metz_local.py:64-170`) :
`Centre-Ville`, `Ancienne-Ville`, `Nouvelle-Ville`, `Les-Iles`, `Outre-Seille`,
`Sablon`, `Sainte-Therese`, `Queuleu`, `Plantieres`, `Bellecroix`, `Borny`,
`Magny`, `Vallieres`, `Devant-Les-Ponts`, `La-Patrotte`, `Grange-Aux-Bois`,
`Technopole`. C'est l'ensemble exact des entrees du gazetteer en B (ni plus, ni
moins — refactor pur).

### 3.3 Fonctions de derivation (forme identique aux consommateurs actuels)

#### 3.3.1 `_KNOWN_LOCALITIES` (`scrapers/base.py`)
- Quartiers : concatenation des `aliases_text` de toutes les entrees du
  gazetteer, **triees par longueur decroissante** (consigne `base.py:327` :
  libelles longs avant courts ; un tri alphabetique naif casserait le substring
  match — risque MOYEN §5). Le gazetteer expose une fonction de derivation
  (ex. `known_localities_districts() -> list[str]`).
- Communes : la liste des communes de la couronne reste maintenue SEPAREMENT
  (Q5) — soit dans `base.py` (constante dediee `_KNOWN_COMMUNES`), soit dans le
  gazetteer comme structure distincte des quartiers. `_KNOWN_LOCALITIES` final =
  derive(quartiers) + communes, **avec le meme ordre effectif que l'actuel**
  (golden 1, §3.5). Le developpeur choisit l'agencement qui reproduit l'ordre ;
  l'oracle (AC1) compare l'ensemble ET le respect de l'ordre long-avant-court
  pour les formes derivees.
- Aucune modification de la signature de `extract_district`.

#### 3.3.2 `_PROFILES` / `_DIST_KM` (`metz_local.py`)
- `_PROFILES[k] = {"name": entry.display_label, **entry.profile}` pour chaque
  entree. `_DIST_KM[k] = dict(entry.dist_km)`.
- Memes cles par construction (§3.1, AC2).
- `local_context`, `assess_claims`, `_resolve_key` ne changent PAS de signature
  ni de comportement : ils continuent de lire `_PROFILES` / `_DIST_KM` /
  `_ALIASES` (qui sont desormais derives). L'argument `district_corroborated`
  ajoute par A reste intact.

#### 3.3.3 `_ALIASES` (`metz_local.py`)
- `_ALIASES` = union des `aliases_canon` de chaque entree, mappant chaque alias
  canonique → `canonical_key` de l'entree. Doit reproduire a l'identique
  l'actuel `_ALIASES` (golden 3) :
  `{"Centre": "Centre-Ville", "Plantieres-Queuleu": "Plantieres",
  "Queuleu-Plantieres": "Queuleu", "Iles": "Les-Iles", "Ile": "Les-Iles",
  "Sainte-Therese-/-Botanique": "Sainte-Therese"}`.

#### 3.3.4 `_SECTORS_RAW` / maps secteur (`market_stats.py`)
- Le gazetteer expose le secteur via `sector_key` + `sector_display`. La
  derivation reconstruit, par group-by sur `sector_key` :
  - `_DISTRICT_TO_SECTOR[canonical_key] = sector_display` (valeur = libelle
    affiche, comme aujourd'hui : `market_stats.py:91` met la cle de
    `_SECTORS_RAW` qui est le libelle affiche) ;
  - `_SECTOR_DISTRICTS[sector_display] = [canonical_key, ...]`.
- L'ordre des quartiers dans chaque secteur et l'ordre des secteurs doivent
  reproduire le resultat actuel de `_build_sector_maps` (golden 4). Le filtre SQL
  ne depend pas de l'ordre, mais le golden fige l'ensemble.
- Note refactor : aujourd'hui `_SECTORS_RAW` contient aussi des libelles bruts
  presents UNIQUEMENT pour matcher le stock (`"Vallières-lès-Bordes"`,
  `"Patrotte-Metz-Nord"`, formes composees `"Plantières - Queuleu"`). Ces formes
  se canonicalisent vers une cle DEJA presente (ex. `"Vallières-lès-Bordes"` →
  `"Vallieres-Les-Bordes"`, distinct de `"Vallieres"`). **Pour rester un
  refactor pur**, la derivation doit produire EXACTEMENT le meme
  `_DISTRICT_TO_SECTOR` / `_SECTOR_DISTRICTS` qu'aujourd'hui (golden 4), y compris
  ces formes de stock. Le developpeur modelise ces libelles de stock comme des
  `aliases_stock` rattaches au secteur (champ optionnel additionnel autorise si
  necessaire pour reproduire le golden), JAMAIS comme un quartier a part entiere
  du selecteur. Si le golden 4 revele une divergence, c'est la derivation qui est
  fausse, pas le golden.

#### 3.3.5 Projection front (`districts.ts`)
- Le gazetteer expose `selector_labels() -> list[str]` = `display_label` des
  entrees `in_selector == True`. Le test de coherence (AC6) compare l'ENSEMBLE
  (`set`) de cette projection a l'ensemble des entrees de `METZ_DISTRICTS` lu
  statiquement dans `frontend/lib/districts.ts`. (Ordre non contraint cote front ;
  seul l'ensemble compte. La SPEC A garantit deja que les libelles concordent.)

### 3.4 Harmonisation `_SECTORS_RAW` (Q6) — contrat exact
- Chaque entree porte `sector_key` (canonique) et `sector_display` (affiche).
- `_DISTRICT_TO_SECTOR` derive expose `sector_display` en valeur (inchange pour
  l'affichage). Pour TOUS les secteurs existants sauf Sainte-Therese, le
  `sector_display` est strictement egal a l'actuelle cle de `_SECTORS_RAW`.
- Sainte-Therese : `sector_key = "Sainte-Therese"`, `sector_display =
  "Sainte-Thérèse"` (accentue). C'est le seul changement de valeur source ; il
  est invisible a l'utilisateur (secteur mono-quartier dont le `scope_name` n'est
  atteignable que si un comparable y existe ; valeur convergee vers le libelle
  accentue attendu). Verrouille par AC8.

### 3.5 Goldens de non-regression (protocole anti-tautologie) — OBLIGATOIRE
Les goldens figent le comportement de l'ANCIEN code et doivent etre captures
AVANT migration. Protocole impose (lecons faux-vert 2026-06-09 9.10,
2026-06-13 ; analyse §3.3) :
- Les valeurs de reference sont **figees en litteral dans le fichier de tests**
  `backend/tests/test_issue_100_B.py` (ou dans un fichier de reference commite au
  commit pre-migration), capturees depuis l'etat actuel des modules AVANT toute
  derivation depuis le gazetteer.
- Il est INTERDIT de regenerer un golden depuis le gazetteer migre (un golden
  ainsi produit passerait toujours et ne prouverait rien). Un commentaire en tete
  de fichier doit rappeler ce protocole.
- Goldens a capturer (chacun verrouille par un AC, §4) :
  1. `sorted(_KNOWN_LOCALITIES)` ET la sous-sequence derivee des quartiers
     respectant l'ordre long-avant-court (golden 1 → AC1) ;
  2. `set(_PROFILES.keys())`, `_PROFILES` complet, `_DIST_KM` complet
     (golden 2/3 → AC2, AC3) ;
  3. `_ALIASES` complet (golden 3b → AC5) ;
  4. `_DISTRICT_TO_SECTOR` complet et `_SECTOR_DISTRICTS` complet (golden 4 →
     AC4) ;
  5. `_scope_context` pour un echantillon couvrant chaque secteur (verifie que
     le `scope_name` AFFICHE ne bouge pas — golden 4b → AC7) ;
  6. `canonical_district(raw, "Metz")` pour un echantillon de libelles bruts
     bien'ici (« Metz - Bellecroix », « Metz - Plantières - Queuleu », « Metz »)
     — verifie que la fonction d'ingestion N'EST PAS modifiee (golden 5 → AC9).

---

## 4. Criteres d'acceptation (numerotes, testables)

> Convention : AC deterministes = suite gratuite `backend/tests/`, dans un fichier
> DEDIE `backend/tests/test_issue_100_B.py` (lecon 2026-06-12 fix-issue-80 : ne
> pas heurter un oracle de harnais executant un fichier existant en sous-processus).
> Isolation : fixtures autouse du `conftest.py` (init_db session-scope, reset
> caches) ; aucun nouveau cache module-global. Le test de coherence front (AC6)
> est statique sur `frontend/lib/districts.ts`, cote backend. PAS d'eval LLM :
> B est un refactor pur sans appel modele (justification §4 in fine).

### Non-regression par referentiel (goldens captures avant migration)

**AC1 — `_KNOWN_LOCALITIES` derive == ancien, ordre preserve.**
Apres migration, `scrapers.base._KNOWN_LOCALITIES` est EGAL (meme ensemble) au
golden 1 fige avant migration. De plus, la sous-sequence des formes derivees de
quartiers respecte l'ordre **long-avant-court** : pour toute paire de formes ou
l'une est substring de l'autre, la plus longue apparait avant la plus courte
dans la liste.
Falsifiabilite : rouge si un libelle disparait, si l'ordre long-avant-court est
casse (tri alphabetique naif), ou si une commune est absorbee/perdue.

**AC2 — Couplage `_PROFILES` ⇄ `_DIST_KM` garanti par construction.**
`set(metz_local._PROFILES.keys()) == set(metz_local._DIST_KM.keys())`, et les
deux derivent du MEME jeu d'entrees du gazetteer (test : ajouter mentalement une
entree sans `dist_km` est impossible car `dist_km` est obligatoire dans le
schema → on prouve l'egalite + on asserte que chaque cle provient d'une entree
gazetteer unique).
Falsifiabilite : rouge si une entree avait un `profile` sans `dist_km` (le schema
l'interdit) ; rouge si les jeux de cles divergent.

**AC3 — `_PROFILES` / `_DIST_KM` derives == anciens (valeurs).**
`metz_local._PROFILES == golden_profiles` et `metz_local._DIST_KM ==
golden_dist_km` (goldens 2/3, figes avant migration), champ par champ y compris
`name`, `center`, `gare`, `caractere` et les distances numeriques.
Falsifiabilite : rouge si une distance ou un texte de profil change d'un seul
quartier.

**AC4 — Maps secteur derivees == anciennes.**
`market_stats._DISTRICT_TO_SECTOR == golden_district_to_sector` et
`market_stats._SECTOR_DISTRICTS == golden_sector_districts` (golden 4 fige avant
migration). En particulier `_DISTRICT_TO_SECTOR["Nouvelle-Ville"] == "Centre Ville"`
et `_SECTOR_DISTRICTS["Centre Ville"]` contient les 5 quartiers actuels.
Falsifiabilite : rouge si un quartier change de secteur, si un libelle affiche de
secteur change (hors Sainte-Therese, AC8), ou si une forme de stock
(`Vallieres-Les-Bordes`, `Patrotte-Metz-Nord`) disparait de sa map.

**AC5 — `_ALIASES` derive == ancien.**
`metz_local._ALIASES == golden_aliases` (golden 3b). Inclut imperativement
`_ALIASES["Sainte-Therese-/-Botanique"] == "Sainte-Therese"` (piege « / »
preserve, AC4 de A non regresse).
Falsifiabilite : rouge si un alias disparait ou pointe vers une autre cle.

### Coherence front (Strategie C)

**AC6 — `districts.ts` == projection du gazetteer (test statique).**
L'ensemble des `display_label` des entrees `in_selector == True` du gazetteer est
EGAL a l'ensemble des entrees de `METZ_DISTRICTS` parsees depuis
`frontend/lib/districts.ts`. Le parse est statique (lecture du fichier, extraction
des chaines de la liste), sans build front.
Falsifiabilite : rouge si un quartier `in_selector` est ajoute/retire du
gazetteer sans MAJ de `districts.ts` (et inversement).

### Harmonisation `_SECTORS_RAW` (Q6)

**AC7 — `sector_display` inchange pour tous les secteurs existants.**
Pour chaque secteur present avant B autre que Sainte-Therese, le `sector_display`
derive (et donc le `scope_name` rendu par `_scope_context`) est strictement egal
a l'ancien libelle affiche. Verifie sur l'echantillon golden 4b couvrant chaque
secteur (au minimum « Centre Ville », « Bellecroix - Vallières »,
« Plantières-Queuleu », « Patrotte-Metz-Nord », « Devant-les-Ponts »,
« Sablon », « Magny », « Borny »).
Falsifiabilite : rouge si un libelle de secteur affiche change (p.ex.
« Centre-Ville » au lieu de « Centre Ville »).

**AC8 — Cle canonique secteur correcte ET `sector_display` accentue pour
Sainte-Therese.**
L'entree Sainte-Therese du gazetteer a `sector_key == "Sainte-Therese"` et
`sector_display == "Sainte-Thérèse"` (accentue). La map derivee donne
`_DISTRICT_TO_SECTOR["Sainte-Therese"] == "Sainte-Thérèse"` et
`_SECTOR_DISTRICTS["Sainte-Thérèse"] == ["Sainte-Therese"]` (secteur ne contenant
QUE Sainte-Therese).
Falsifiabilite : rouge si la cle source reste non-accentuee non separee
(reproduit la dette lecon 2026-06-16), ou si un voisin est ajoute au secteur.
Note : cet AC asserte la forme DERIVEE (sortie de la fonction de normalisation),
JAMAIS l'identite d'une cle de dict source (lecon 2026-06-16 : ne pas forcer une
implementation via une cle brute).

### Invariance / non-regression globale

**AC9 — `canonical_district` / `canonical_city` NON modifies (caracterisation).**
1. Pour un echantillon de libelles bruts bien'ici, `canonical_district(raw, "Metz")`
   == golden 5 fige avant migration (« Metz - Bellecroix » → « Bellecroix » ;
   « Metz - Plantières - Queuleu » → « Plantieres-Queuleu » ; « Metz » → `None`).
2. Test statique : le diff de B ne modifie pas le corps de `canonical_district`
   ni `canonical_city` (asserter par hash/snapshot du source de ces fonctions, ou
   au minimum un golden de sortie sur un jeu de libelles couvrant accents,
   prefixe ville, separateurs).
Falsifiabilite : rouge si une de ces fonctions est touchee (divergence stock prod
↔ requete, ~17,7k comparables muets).

**AC10 — Invariance Sainte-Therese (chantier A) bout en bout.**
Apres migration : `extract_district("quartier Sainte-Thérèse à Metz")` resout
vers `"Sainte-Therese"` ; `local_context("Sainte-Thérèse", "Metz")` retourne le
profil (dict non `None`, `["district"] == "Sainte-Thérèse"`) ;
`local_context("Sainte-Thérèse / Botanique", "Metz")` retourne aussi ce profil
(alias « / » preserve) ; `_DISTRICT_TO_SECTOR["Sainte-Therese"]` existe. Tous les
acquis de A restent valides.
Falsifiabilite : rouge si un seul des quatre chemins de A regresse.

**AC11 — Invariance des autres quartiers (echantillon).**
Pour au moins `"Nouvelle Ville"`, `"Sablon"`, `"Centre-Ville"`, `"Borny"`,
`"Vallières"`, `local_context(q, "Metz")` retourne le meme dict
(`["district"]` correct, `["facts"]` identique) qu'avant B, et `_resolve_key(q)`
resout vers la meme cle.
Falsifiabilite : rouge si un profil derive differe de l'ancien.

**AC12 — Suite A intacte sans modification.**
`backend/tests/test_issue_100_A.py` reste VERT apres B sans aucune edition de ce
fichier (les AC de A sont des consommateurs des structures desormais derivees ;
si la derivation est correcte, ils passent inchanges).
Falsifiabilite : rouge si la derivation change une valeur observee par A.
Verification : le push qui migre un referentiel n'edite pas `test_issue_100_A.py`.

### Refactor pur — bornes documentees (anti sur-perimetre)

**AC13 — Trous de couverture documentes, PAS corriges.**
`extract_district("Ancienne Ville à Metz")` et `extract_district("Les Îles à
Metz")` retournent le MEME resultat qu'avant B (a savoir `None` pour le repli
texte, ces formes etant absentes de `_KNOWN_LOCALITIES`) — la couverture n'est
PAS etendue par B. Un commentaire dans le gazetteer (ou `base.py`) documente que
ces quartiers sont dans `_PROFILES`/`_SECTORS_RAW`/`METZ_DISTRICTS` mais pas dans
les `aliases_text` (lot de correction ulterieur, hors B).
Falsifiabilite : rouge si B etend silencieusement la reconnaissance (ce ne serait
plus un refactor pur) OU si le commentaire de renvoi manque.

**AC14 — `centroid` vide, commune presente.**
Toute entree du gazetteer a `centroid is None` (geocodage = chantier C) et
`commune == "Metz"`. Le champ `centroid` existe dans le schema (prepare C).
Falsifiabilite : rouge si un centroide est rempli en B (sur-perimetre C) ou si
`commune` est absent du schema.

### Pourquoi pas d'eval LLM
B est un refactor pur de structures de donnees deterministes : aucune sortie
modele n'est affectee, les AC sont tous deterministes (suite gratuite). Ajouter
un cas d'eval (`backend/evals/`, payant) n'apporterait aucune garantie
supplementaire et contredirait la frugalite (CONTEXT). Si une future correction
de couverture (hors B) changeait la reconnaissance, ELLE justifierait un cas
d'eval — pas B.

---

## 5. Hors-perimetre / non-objectifs (rappel borne)

- Pas de correction des trous de couverture (Ancienne-Ville / Les-Iles) : lot
  ulterieur, documente seulement (AC13).
- Pas de geocodage ni de remplissage des centroides (chantier C ; `centroid`
  reste `None`, AC14).
- Pas de reconciliation inter-communale « Botanique » (chantier C).
- Pas de modification de `canonical_district` / `canonical_city` (AC9).
- Pas de modification du contrat `/analyze` ni de `frontend/lib/api.ts`.
- Pas d'absorption des communes de la couronne dans le gazetteer (Q5).
- Pas d'ajout de nouveau quartier.
- Pas de build step de generation `districts.ts` ni d'endpoint API.
- Pas de nouveau lookup en base interroge par-ligne a l'ingestion (le gazetteer
  reste en memoire ; lecon 2026-06-14, §7).

---

## 6. Plan de migration incremental (ordre + golden + bascule)

Chaque etape est un push isole ; tous les goldens captures restent verts a
chaque etape. Si une etape casse un golden, on sait laquelle.

- **Push 0 — Goldens + gazetteer non branche.**
  - Capturer tous les goldens (§3.5) en litteral dans
    `backend/tests/test_issue_100_B.py`, DEPUIS l'ancien code (avant toute
    derivation). Ces tests passent contre l'etat actuel.
  - Creer `backend/app/geo_gazetteer.py` (entrees + fonctions de derivation),
    SANS le brancher dans les consommateurs.
  - Tests : chaque fonction de derivation du gazetteer produit une structure
    EGALE au golden correspondant (validation pure, gazetteer encore inerte).
  - AC couverts (en mode « derivation == golden », consommateurs encore
    anciens) : preparation de AC1-AC5 ; AC2, AC14 (schema) ; protocole anti-
    tautologie (§3.5) fige ici.

- **Push 1 — Brancher `metz_local` (`_PROFILES`/`_DIST_KM`/`_ALIASES`).**
  Le plus isole (aucun impact stock). Golden 2/3/3b verts.
  AC couverts : AC2, AC3, AC5, AC10 (partiel), AC11.

- **Push 2 — Brancher `market_stats._SECTORS_RAW` (+ maps + harmonisation Q6).**
  Point sensible : `scope_name` affiche. Golden 4/4b verts.
  AC couverts : AC4, AC7, AC8.

- **Push 3 — Brancher `scrapers.base._KNOWN_LOCALITIES` (quartiers) + liste
  communes separee.**
  Point sensible : ordre long-avant-court. Golden 1 vert. AC couverts : AC1,
  AC13.

- **Push 4 — Coherence front + invariants finaux.**
  Ajouter le test statique gazetteer ⇄ `districts.ts` (AC6) ; verifier AC9
  (caracterisation `canonical_*`), AC10 complet, AC12 (suite A intacte), AC14.
  `frontend/lib/districts.ts` n'est PAS modifie (deja coherent depuis A) sauf si
  AC6 revele une divergence — auquel cas elle est tranchee ici, pas masquee.

Regle de cloture (lecon 2026-06-12) : avant de clore chaque push, diff du commit
confronte a la liste de contenu ci-dessus, et `test_issue_100_A.py` confirme
inchange (AC12).

---

## 7. Points d'attention anti-regression (lecons applicables)

- **Faux-vert / goldens regeneres** (lecons 2026-06-09 9.10, 2026-06-13 ;
  analyse §3.3) : les goldens DOIVENT etre captures depuis l'ancien code AVANT
  migration et figes en litteral, JAMAIS regeneres depuis le gazetteer migre.
  Protocole impose §3.5 ; commentaire de rappel en tete du fichier de tests.
- **Oracle qui force une cle brute** (lecon 2026-06-16 issue-100-A) : AC8 asserte
  la forme DERIVEE (`_DISTRICT_TO_SECTOR[CANON]`), jamais l'identite d'une cle de
  dict source. L'harmonisation Q6 supprime justement la cle brute incoherente.
- **Couplage `_PROFILES` ⇄ `_DIST_KM`** : resolu par construction (deux champs de
  la meme entree, tous deux obligatoires) ; AC2 le prouve. Plus besoin d'un test
  d'egalite a maintenir a la main (AC9 de A devient structurel).
- **Index lookup par-ligne a l'ingestion** (lecon 2026-06-14) : NON applicable —
  le gazetteer reste en memoire, aucun nouveau `filter`/`get` par-ligne. A
  confirmer au review : aucune derivation ne tape la base. INTERDIT d'introduire
  un mapping gazetteer en table interroge par ligne a l'ingestion.
- **Couplage ingestion `canonical_*`** (analyse §4 risque MAJEUR) : ces fonctions
  produisent la valeur stockee (`bienici.py:285`). Le gazetteer les APPELLE pour
  deriver, ne les remplace pas. AC9 caracterise leur sortie inchangee.
- **Isolation des tests** (lecons 9.7, 9.9, photo-evidence) : reutiliser les
  fixtures autouse du `conftest.py` ; aucun nouveau cache module-global ; pas
  d'assertion sur compteur absolu.
- **Fichier de tests dedie** (lecon 2026-06-12) : nouveaux tests dans
  `backend/tests/test_issue_100_B.py` ; `test_issue_100_A.py` reste inchange
  (AC12).
- **Ordre long-avant-court `_KNOWN_LOCALITIES`** (analyse §4 risque MOYEN) :
  `extract_district` renvoie le PREMIER match ; la derivation trie par longueur
  decroissante, verrouille par AC1.

---

## 8. Conformite (anti-patterns applicables)

- **Pas de fake precision (CONTEXT §11 / CLAUDE §1)** : B ne geocode pas ;
  `centroid` reste `None` (honnete) ; distances inchangees (curatees,
  approximatives « ~ »). AC14.
- **Pas d'estimation de prix** : B ne touche ni au scoring ni au calcul des
  quartiles ; seules les structures de selection de pool sont refactorees a
  l'identique (golden 4).
- **Pas de redistribution d'annonces brutes** : le gazetteer ne contient que des
  donnees curatees (profils, alias, secteurs) ; aucun champ d'annonce brute.
- **Contrat `/analyze` stable (CLAUDE §10)** : refactor interne pur ; aucun champ
  de reponse modifie ; `frontend/lib/api.ts` non touche.
- **Pas de secret en clair** : sans objet.
- **Logging nomme, Python 3.12, pas de commentaire « what », pas d'emoji**
  (CLAUDE §12) : respecter dans tout code ajoute (le module `geo_gazetteer.py` et
  les fonctions de derivation).

---

## 9. Decoupage des push (recapitulatif par referentiel migre)

| Push | Contenu | Referentiel migre | Tests / AC |
|---|---|---|---|
| 0 | Goldens figes (avant migration) + `geo_gazetteer.py` non branche + fonctions de derivation | aucun (validation pure) | derivation==golden ; AC2/AC14 (schema) ; protocole §3.5 |
| 1 | Brancher `metz_local._PROFILES`/`_DIST_KM`/`_ALIASES` | profils + distances + alias | AC2, AC3, AC5, AC10 (partiel), AC11 |
| 2 | Brancher `market_stats._SECTORS_RAW` + maps + harmonisation Q6 | secteurs | AC4, AC7, AC8 |
| 3 | Brancher `scrapers.base._KNOWN_LOCALITIES` (quartiers) + liste communes separee | extraction texte | AC1, AC13 |
| 4 | Test coherence front + invariants finaux | front (projection testee) | AC6, AC9, AC10 (complet), AC12, AC14 |

Regle de cloture (lecon 2026-06-12) : a chaque push, diff confronte au contenu
ci-dessus ; `test_issue_100_A.py` verifie inchange (AC12) ; aucun golden regenere
depuis le gazetteer (§3.5, §7).

---

SPEC prête pour GATE 2 (approbation humaine).

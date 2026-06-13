# cross-agence — INCRÉMENT 2b, ÉTAPE 1 (capture URLs photo bienici + probe gisement) — SPEC (GATE 2)

> Rôle : SPEC-WRITER. Cahier des charges implémentable de la **seule ÉTAPE 1** de
> l'incrément 2b (rattachement cross-agence par PHOTO). GATE 1 actée (arbitrages §0,
> non rediscutables). Lecture du code au 2026-06-13. **Aucun code produit ici.**
> Réfs lues : `.claude/lessons.md`, `docs/specs/cross-agence-INCREMENT2B-ANALYSE.md`,
> `docs/specs/cross-agence-INCREMENT2A-SPEC.md`, `backend/CLAUDE.md` (§1/§7/§9/§12),
> `CONTEXT.md` §11. Code réel ancré : `scrapers/sources/bienici.py`,
> `scrapers/models.py`, `db/models.py`, `db/session.py`, `ingestion/save.py`,
> `jobs/push_comparables.py`, `app/main.py`.

---

## 0. Arbitrages GATE 1 actés (à implémenter, ne pas rediscuter)

1. **Séquençage en DEUX étapes.** Cette SPEC couvre **uniquement l'ÉTAPE 1** : le
   cheap/réversible (capture des URLs photo + probe read-only du gisement). L'ÉTAPE 2
   (download des bytes, hash dHash, table `photo_hashes`, matching cross-source,
   amendement doctrine download) sera spécifiée plus tard, calibrée sur les chiffres
   produits par l'étape 1. Frontière nette en §1.2/§7.
2. **Périmètre source = bienici uniquement.** Les photos sont déjà dans le JSON
   téléchargé (`realEstateAds.json`, clé `photos`, ~95,5 %, 3 URLs CDN, PREREQ0 §1).
   **0 fetch HTTP supplémentaire.** Les agences HTML (benedic, idemmo, immoheytienne,
   laveine_immo) sont **OUT** (étape 2 conditionnelle).
3. **`market_stats` / sélection comparables / score 40/30/30 / contrat `/analyze` /
   `AnalyzeResponse` / `frontend/lib/api.ts` : STRICTEMENT inchangés.**
4. **AUCUNE dépendance Python nouvelle** (`requirements.txt` inchangé). La capture
   d'URLs et la probe n'en exigent aucune. Pillow / dHash = étape 2.
5. **AUCUN download d'image, AUCUN hash** dans l'étape 1.

---

## 1. Objectif et périmètre

### 1.1 Objectif
Préparer la calibration de l'étape 2 (matching cross-agence par photo) sans engager
son coût ni son risque : (A) **capturer et persister les URLs photo bienici** (déjà
présentes dans le JSON collecté) comme métadonnée interne nullable, et (B) **mesurer
en read-only un ordre de grandeur du gisement de re-list cross-source** par un proxy
d'attributs, pour décider si l'étape 2 vaut son coût.

### 1.2 In (périmètre de l'étape 1)
- **Schéma** : colonne `photo_urls` nullable sur `comparables`, via micro-migration
  idempotente (`db/session.py::_ADD_COLUMNS` + `CREATE INDEX`/DDL re-run safe). §2.1.
- **Capture** : `scrapers/sources/bienici.py::_parse_listing` lit la clé JSON
  `photos`, helper nullable défensif cappé, propagation
  `PropertyListing` → `to_dict()` → `_is_valid` → `ComparableIn` → `save_comparables`.
  §2.2 / §2.3.
- **Probe** : un script read-only `backend/tools/probe_cross_source.py` produisant un
  rapport chiffré agrégé du gisement candidat cross-source (proxy d'attributs). §3.
- **Confidentialité** : `photo_urls` métadonnée interne, jamais exposée dans une
  réponse API. §4.

### 1.3 Out (étape 2 ou hors chantier — frontière nette)
- **Download des bytes d'image, calcul de hash (dHash/pHash), table `photo_hashes`,
  logique de matching cross-source, pose/fusion de `lineage_id` cross-source** :
  ÉTAPE 2.
- **Dépendances image (Pillow, imagehash, scipy)** : ÉTAPE 2.
- **Agences HTML** (download de pages détail, vignettes recadrées) : ÉTAPE 2
  conditionnelle.
- **Amendement de `CONTEXT.md` §11.3 sur le download transitoire d'images, vérif
  ToS/hotlink du CDN apimo.pro** : ÉTAPE 2.
- **Toute modification de `/analyze`, `AnalyzeResponse`, `frontend/lib/api.ts`,
  `market_stats.py`, `scoring.py`, sélection des comparables** : hors chantier
  (invariant permanent).
- **Dédoublonnage de `market_stats` via lignée** : interdit (doctrine, ANALYSE §7).

### 1.4 Frontière étape 1 vs étape 2 (rappel)
Étape 1 = capture URLs (métadonnée, réversible) + mesure (read-only). Aucun octet
d'image téléchargé, aucun hash, aucun rattachement cross-source posé. La probe est un
**intrant de décision**, elle n'écrit rien et ne modifie aucune lignée.

---

## 2. Schéma + capture

### 2.1 Colonne ajoutée à `comparables` (micro-migration idempotente)

Modèle `db/models.py` (classe `Comparable`) : ajouter

| Colonne | Type SQLAlchemy | Nullable | Index | Sémantique |
|---|---|---|---|---|
| `photo_urls` | `String` (TEXT SQLite), contenu = **liste d'URLs encodée JSON** (`json.dumps`) ou `None` | oui | non | URLs photo captées à la collecte (bienici clé JSON `photos`). Métadonnée technique **INTERNE** (usage futur étape 2 : hash). `None` si aucune photo ou hors bienici. |

Justification du type : le repo n'a pas de type JSON natif (SQLite/SQLAlchemy
`Column(String)`, cf. `dpe`/`reference`/`customer_id` toutes `String`). On reste sur
ce pattern : stockage d'une **chaîne JSON** (`json.dumps(list)`), `None` si vide. Pas
de nouvelle table (cohérent avec « pas de table dépendante à l'étape 1 », §6 ANALYSE).

Nullable côté schéma pour ne **pas** casser les ~17,7k lignes prod lors de l'`ALTER
TABLE`. Aucun index (la colonne n'est jamais un critère de filtre à l'étape 1).

Migration : étendre `_ADD_COLUMNS` de `db/session.py:35-56`. DDL attendu :

```
"photo_urls": "ALTER TABLE comparables ADD COLUMN photo_urls VARCHAR"
```

Le mécanisme `_migrate_comparables` (`db/session.py:59-72`) est déjà idempotent
(garde `if column not in existing`). Aucun nouvel index, donc aucun `CREATE INDEX` à
ajouter. Re-run de `init_db()` sans erreur exigé (AC).

### 2.2 Capture côté bienici (`scrapers/sources/bienici.py::_parse_listing`)

`_parse_listing` (`:199-252`) lit la clé JSON `photos` (confirmée PREREQ0 §1 / ANALYSE
2b §1.2 : liste de ~3 éléments, URLs CDN `media.apimo.pro/cache/..._1920-original.jpg`).

**Helper nullable défensif** `_extract_photo_urls(ad: dict) -> Optional[str]`, sur le
modèle de `_extract_postal`/`_as_str` (`:132-152`), avec ce contrat :
- lit `ad.get("photos")` ; si ce n'est pas une liste non vide ⇒ retourne `None` ;
- **la structure exacte d'un élément doit être vérifiée par le développeur sur un
  échantillon JSON réel** (le code actuel ne lit jamais `photos` ; l'ANALYSE indique
  « URLs CDN directes » mais ne fige pas si l'élément est une `str` ou un objet
  `{"url": ...}`/`{"src": ...}`). Le helper doit être **robuste aux deux formes** :
  - si l'élément est une `str` non vide après strip ⇒ c'est l'URL ;
  - si l'élément est un `dict` ⇒ lire la première clé d'URL présente parmi un jeu de
    candidats explicites (`"url"`, `"src"`, `"href"`) ; valeur `str` non vide après
    strip ;
  - tout autre type, ou URL vide ⇒ élément **ignoré** (jamais d'exception) ;
- **cap à 3 URLs** (`_PHOTO_URL_CAP = 3`, cohérent avec la discipline future étape 2 ;
  borne testée aux valeurs exactes) ; les URLs au-delà du cap sont ignorées ;
- déduplique en **préservant l'ordre** (la première occurrence est gardée) ;
- si après filtrage la liste est vide ⇒ retourne `None` ;
- sinon retourne `json.dumps(<liste d'URLs>)` (chaîne JSON, jamais une liste Python
  brute, pour rester homogène au type `String` de la colonne).

**Contrat impératif (défensif)** : une annonce bienici **sans** clé `photos`, avec
`photos` vide, ou avec une structure inattendue ⇒ `photo_urls = None`, **jamais**
d'échec de parsing ni de collecte (pas d'exception propagée, pas de 0 annonce). Le
helper est appelé dans le `try` de construction de `PropertyListing` (`:235-252`) et
renseigne `photo_urls=_extract_photo_urls(ad)`.

### 2.3 Propagation de la chaîne

- **`scrapers/models.py`** : `PropertyListing` += `photo_urls: Optional[str] = None`
  (champ optionnel ; `to_dict()`/`asdict` le propage automatiquement). Type `str`
  (chaîne JSON), cohérent avec la colonne. Note : le prompt évoquait
  `Optional[list]` ; on retient `Optional[str]` (JSON encodé) pour rester homogène au
  type `String` de la colonne et au pattern `reference`/`customer_id` — l'AC de
  contrat nullable (AC7) vérifie le défaut `None`.
- **`jobs/push_comparables.py::_is_valid`** : `photo_urls` **N'EST PAS** ajouté à
  `_REQUIRED_STR` (`:28`). Une annonce **sans** `photo_urls` reste valide et poussée.
  Aucun item ne doit être écarté pour absence de `photo_urls`.
- **`app/main.py::ComparableIn`** : ajouter `photo_urls: Optional[str] = None`
  (`:157-181`). `model_dump()` le transmet à `save_comparables`. Absence ⇒ pas de 422.
- **`ingestion/save.py::save_comparables`** : ajouter `photo_urls=ad.get("photo_urls")`
  au dict `fields` (`:182-208`), persisté de la même façon que `reference`/
  `customer_id` (créé via `db.add`, mis à jour via `setattr` à la re-observation).
  Aucune autre branche de `save_comparables` n'est touchée (logique de lignée 2a
  **inchangée**). Idempotence : à la re-observation d'un id connu, `photo_urls` est
  mis à jour comme les autres champs (re-observation = ré-affectation des `fields`).

---

## 3. Probe du gisement cross-source (read-only)

### 3.1 Objectif et nature
Estimer un **ordre de grandeur** du re-list cross-source (bien potentiellement
re-publié par une **autre** source) **par proxy d'attributs**, sans photo ni hash,
pour éclairer la décision d'engager l'étape 2. **Ce n'est PAS du rattachement** : la
probe n'écrit aucun `lineage_id`, ne crée/modifie/supprime aucune ligne, ne touche pas
`market_stats`. Le résultat est étiqueté « borne haute / candidats potentiels », pas
un compte de vrais matches.

### 3.2 Forme retenue : script read-only (pas d'endpoint)
**Script** `backend/tools/probe_cross_source.py`, lançable manuellement et en CI
(`python -m tools.probe_cross_source`), produisant un **rapport chiffré sur stdout**
(et, optionnellement, un fichier Markdown via `--out`). Aucune écriture en base
(connexion en lecture seule logique : que des `db.query`, aucun `db.add`/`commit`).

**Justification du choix script vs endpoint admin** : préférer le script évite
d'exposer une **nouvelle surface API** (pas de route à authentifier, à rate-limiter, à
tester pour fuite de données) pour une mesure ponctuelle d'aide à la décision. Le
pattern « outil dev hors prod » existe déjà (`scrapers/diag_bienici.py`,
`scrapers/diagnose.py`, `scrapers/recon.py`) et le script s'y range. Le rapport ne
contient **aucune** donnée personnelle, **aucune** URL, **aucun** identifiant : que des
**compteurs agrégés**.

### 3.3 Définition du proxy (conservateur, étiqueté borne haute)
Une **paire candidate** est un couple `(A, B)` de comparables tels que :
1. `A` et `B` ont des **sources différentes** : `A.source != B.source`.
2. `A` est **disparu** : `A.last_seen_at IS NOT NULL` et
   `(now_probe - A.last_seen_at).days > _PROBE_GAP_DAYS_RECENT` — c.-à-d. `A` n'a pas
   été revu dans les runs récents. (`now_probe` = `datetime.utcnow()` au lancement.)
3. `B` est **apparu après** la disparition de `A` :
   `B.first_seen_at IS NOT NULL` et `B.first_seen_at > A.last_seen_at`.
4. `B` apparaît **dans la fenêtre temporelle** suivant la disparition de `A` :
   `(B.first_seen_at - A.last_seen_at).days <= _PROBE_WINDOW_DAYS`. Borne **inclusive**
   (exactement `_PROBE_WINDOW_DAYS` jours révolus ⇒ retenu ;
   `_PROBE_WINDOW_DAYS + 1` ⇒ exclu).
5. **Corroboration d'attributs** (TOUS requis) :
   - `A.property_type == B.property_type` ;
   - `A.city == B.city` (villes déjà canoniques en base, `save.py:137`) ;
   - `A.postal_code == B.postal_code`, **les deux non nuls** (si l'un est `None` ⇒
     paire exclue : on ne devine pas) ;
   - **surface ±10 %** : `abs(A.surface_m2 - B.surface_m2) <= _PROBE_SURFACE_TOL *
     A.surface_m2`, avec `_PROBE_SURFACE_TOL = 0.10`. Borne **inclusive** (exactement
     10,00 % ⇒ retenu ; 10,01 % ⇒ exclu). **Ce seuil ±10 % de probe est distinct du
     ±2 % de rattachement 2a** (`LINEAGE_SURFACE_TOLERANCE = 0.02`) : la probe est une
     borne haute exploratoire, pas un rattachement.
6. **Aucune** contrainte de prix (l'écart de prix n'entre pas dans le proxy).

Constantes nommées en tête de module, valeurs proposées (calibrables, à acter par le
rapport lui-même) :
```
_PROBE_GAP_DAYS_RECENT = 7     # "disparu" = non revu depuis > 7 jours
_PROBE_WINDOW_DAYS     = 180   # B apparait dans les 180 j suivant la disparition de A
_PROBE_SURFACE_TOL     = 0.10  # tolerance de surface du proxy (distinct du 2a ±2%)
```

### 3.4 Sorties du rapport (compteurs agrégés uniquement)
- **Total de paires candidates** sur le corpus.
- **Ventilation par couple de sources** ordonné (ex. `bienici↔benedic`,
  `bienici↔idemmo`, …) : un compteur par couple non ordonné (`A.source`, `B.source`
  triés lexicographiquement pour ne pas compter deux fois le même couple).
- **% du corpus** : `nombre de comparables impliqués dans au moins une paire candidate`
  / `total comparables`, arrondi.
- **Compteurs de contexte** : total comparables, nombre de comparables disparus
  (critère 2), nombre par source.

Aucune ligne du rapport ne contient d'`id`, de `reference`, de `customer_id`, de
`photo_urls`, d'URL, de ville/quartier nominatif au-delà d'un compteur agrégé, ni
aucun extrait d'annonce.

### 3.5 Honnêteté statistique (étiquetage obligatoire dans le rapport)
Le rapport **doit** imprimer une section « Limites » étiquetant explicitement, au
minimum :
- **proxy d'attributs ≠ vrai match** : ces paires sont une **borne haute / candidats
  potentiels**, pas un compte de re-lists réels (le proxy ne distingue pas deux biens
  distincts de mêmes attributs d'un vrai re-list) ;
- **syndication bienici** : bienici ré-affiche des mandats de nos propres agences
  (PREREQ0 §2/§2bis) ⇒ le proxy peut **gonfler** (faux candidats syndiqués) ou
  **masquer** (déjà capté par 2a intra-`reference`) le vrai multi-mandat ;
- **données jeunes** : l'historique inc.1/2a est récent (déployé 2026-06-11) ⇒ peu de
  recul temporel, la fenêtre `_PROBE_WINDOW_DAYS` est partiellement non observée ;
- **conclusion** : le résultat est un **intrant de décision** pour dimensionner
  l'étape 2, **pas une vérité** sur le taux de re-list cross-source.

---

## 4. Confidentialité (anti-fuite `photo_urls`)

`photo_urls` est une **métadonnée technique INTERNE** au même titre que
`reference`/`customer_id`/`lineage_id` (SPEC 2a §6, CONTEXT §11.3 amendé) : stockée
pour usage interne futur (hash étape 2), **JAMAIS exposée** dans une réponse API.

Impératif (vérifié par AC anti-fuite) : `photo_urls` n'apparaît dans **aucune**
réponse de **aucun** endpoint — en particulier :
- `GET /admin/comparables/{listing_id}/history` (`app/main.py:224+`) : l'ensemble des
  clés de la réponse 200 reste **exactement** `{listing_id, source, first_seen_at,
  last_seen_at, weeks_on_market, price_first, price_last, price_change_pct,
  snapshots}` (SPEC 2a §4.1 AC27, inchangé), chaque snapshot ⊆ `{price_total,
  price_m2, observed_at}`. `photo_urls` n'y est pas ajouté.
- `GET /admin/comparables/stats` : inchangé (`{total, cities}`).
- `POST /admin/comparables` : réponse inchangée (`{received, saved, total_in_db}`).
- `POST /analyze` / `AnalyzeResponse` : aucune clé ajoutée.

Vérification à la couche qui **construit** le dict de réponse, pas seulement via
`response_model` (leçon 9.10 : un `response_model` masque une fuite à la sérialisation).

Note (non bloquante, §6) : stocker une URL en interne ≠ la redistribuer ; conforme à
§11.3 « stockage interne autorisé, redistribution interdite ».

---

## 5. Critères d'acceptation (testables)

Chaque AC est falsifiable et transformable 1:1 en pytest. Fichiers suggérés :
`backend/tests/test_cross_agence_increment2b_etape1.py` ; réutilisation de
`backend/tests/conftest.py` (base jetable, `init_db` session-scope, reset autouse
`comparables`/snapshots). Les tests de capture/persistance appellent **directement
`save_comparables`** sur la base jetable réelle (leçon 9.10), jamais un mock de
`db.get`/`setattr`. La probe est testée sur un **jeu synthétique contrôlé** inséré en
base avec `last_seen_at`/`first_seen_at` explicites.

### Schéma & migration
- **AC1** — Après `init_db()`, `PRAGMA table_info(comparables)` contient la colonne
  `photo_urls`.
- **AC2** — Idempotence : appeler `init_db()` **deux fois** ne lève aucune exception et
  ne duplique pas la colonne (`table_info` identique après le 2e appel).
- **AC3** — Migration sur stock prod simulé : sur une table `comparables`
  **préexistante sans** `photo_urls`, un `init_db()` ajoute la colonne ; un 2e
  `init_db()` ne lève pas et ne re-crée rien. Les lignes préexistantes (sans
  `photo_urls`) sont conservées intactes, `photo_urls IS NULL` pour elles.

### Capture (nominal / nullable / cap / dédup)
- **AC4** — Nominal : `_extract_photo_urls({"photos": [<3 URLs str valides>]})`
  retourne `json.dumps([u1, u2, u3])` (3 URLs, ordre préservé).
- **AC5** — Structure objet : `_extract_photo_urls({"photos": [{"url": u1},
  {"url": u2}]})` retourne `json.dumps([u1, u2])` (lecture de la clé d'URL d'un
  élément `dict`).
- **AC6** — Nullable défensif : `_extract_photo_urls(ad)` retourne `None` pour chacun
  de : `photos` absent ; `photos = []` ; `photos = None` ; `photos = "x"` (pas une
  liste) ; `photos = [{}]`, `photos = [{"foo": 1}]`, `photos = [""]`, `photos = [123]`
  (éléments sans URL exploitable). Aucune exception levée dans aucun cas.
- **AC7** — Cap exact à 3 : `_extract_photo_urls({"photos": [u1, u2, u3, u4, u5]})`
  (5 URLs distinctes) retourne une liste JSON de **3** URLs = `[u1, u2, u3]` (les
  2 au-delà du cap ignorées). Et `[u1, u2, u3]` (exactement 3) retourne les 3.
- **AC8** — Déduplication ordre-préservant : `_extract_photo_urls({"photos":
  [u1, u1, u2]})` retourne `json.dumps([u1, u2])`.
- **AC9** — Persistance bout-en-bout : `save_comparables([ad])` avec
  `ad["photo_urls"]=json.dumps([u1, u2])` persiste `photo_urls == json.dumps([u1, u2])`
  sur la ligne ; un `ad` **sans** `photo_urls` (clé absente ou `None`) persiste la
  ligne avec `photo_urls is None` (aucune exception, comparable bien créé).
- **AC10** — `PropertyListing` contrat nullable (sans réseau) : un `PropertyListing`
  construit sans `photo_urls` a `photo_urls is None` et
  `to_dict()["photo_urls"] is None`.
- **AC11** — `_is_valid` ne requiert pas `photo_urls` : `jobs.push_comparables._is_valid`
  renvoie `True` pour un item complet **sans** `photo_urls` (item poussé).
- **AC12** — `POST /admin/comparables` accepte `photo_urls` optionnel : un body sans
  `photo_urls` ne renvoie pas 422 ; un body avec `photo_urls` (chaîne) est accepté et
  la réponse conserve son contrat `{received, saved, total_in_db}`.

### Idempotence ingestion
- **AC13** — Re-observation : rejouer **deux fois** `save_comparables([ad])` (même id)
  avec `photo_urls` ne crée qu'**une** ligne ; `photo_urls` est mis à jour comme les
  autres champs (un 2e passage avec un `photo_urls` modifié écrase l'ancien sur la même
  ligne, pas de doublon de comparable ni de snapshot supplémentaire si le prix est
  inchangé).
- **AC14** — Re-run de lot : rejouer le même lot complet ne crée ni comparable
  supplémentaire ni snapshot supplémentaire ; les `photo_urls` restent stables.

### Anti-fuite (confidentialité)
- **AC15** — `/history` n'expose pas `photo_urls` : pour un comparable doté de
  `photo_urls` non nul, la réponse 200 de `GET /admin/comparables/{id}/history` ne
  contient **pas** la clé `photo_urls` ; l'ensemble des clés ⊆ `{listing_id, source,
  first_seen_at, last_seen_at, weeks_on_market, price_first, price_last,
  price_change_pct, snapshots}`. Vérifié sur le **dict construit** par la fonction
  d'endpoint (pas seulement via `response_model`).
- **AC16** — `/admin/comparables/stats` n'expose pas `photo_urls` (clés ⊆
  `{total, cities}`).
- **AC17** — `POST /admin/comparables` : la réponse ne contient pas `photo_urls`
  (clés = `{received, saved, total_in_db}`), même quand l'item importé en portait un.

### Non-régression (invariants)
- **AC18** — Contrat `/analyze` INCHANGÉ : `AnalyzeResponse` ne gagne aucune clé ; un
  appel `/analyze` renvoie le même jeu de clés
  (`global_score, verdict, confidence, pillars, actions, local_context`). Aucune modif
  de `frontend/lib/api.ts`.
- **AC19** — Score 40/30/30 et `market_stats` INCHANGÉS : un smoke de scoring/marché
  existant reste vert ; `photo_urls` n'entre ni dans la sélection des comparables ni
  dans le score (réutiliser un test smoke marché/score existant).
- **AC20** — Non-régression rattachement 2a : la présence de `photo_urls` ne modifie
  pas la logique de lignée — un re-list 2a nominal (même `reference`/`customer_id`/
  attributs) reste rattaché à l'identique, qu'`photo_urls` soit présent ou `None`
  (réutiliser/dériver un scénario de rattachement 2a, vérifier `lineage_id` inchangé).

### Probe (jeu synthétique contrôlé, bornes exactes)
- **AC21** — Comptage nominal : un jeu synthétique contenant exactement **1** paire
  candidate valide (A `source="benedic"` disparu, B `source="bienici"` apparu après,
  même `property_type`+`city`+`postal_code`, surface dans ±10 %, dans la fenêtre) est
  compté **1** ; la ventilation impute la paire au couple `bienici↔benedic`.
- **AC22** — Surface ±10 % incluse : A `surface_m2=100.0`, B `surface_m2=110.0`
  (10,00 %), sinon valides ⇒ **comptée** (1 paire).
- **AC23** — Surface ±10 % exclue : A `surface_m2=100.0`, B `surface_m2=110.01`
  (>10,00 %), sinon valides ⇒ **non comptée** (0 paire).
- **AC24** — Fenêtre `_PROBE_WINDOW_DAYS` incluse : `B.first_seen_at` =
  `A.last_seen_at + _PROBE_WINDOW_DAYS` jours, sinon valides ⇒ **comptée**.
- **AC25** — Fenêtre `_PROBE_WINDOW_DAYS` exclue : `B.first_seen_at` =
  `A.last_seen_at + (_PROBE_WINDOW_DAYS + 1)` jours, sinon valides ⇒ **non comptée**.
- **AC26** — Même source exclue : A et B de **même** `source` (sinon tous prédicats
  satisfaits) ⇒ **non comptée** (la probe ne cible que le cross-source).
- **AC27** — Code postal manquant exclu : A ou B avec `postal_code IS NULL` (sinon
  valides) ⇒ **non comptée** (on ne devine pas).
- **AC28** — `property_type` / `city` divergents exclus : une paire par ailleurs
  valide mais de `property_type` (ou `city`) différents ⇒ **non comptée**.
- **AC29** — B non apparu après A exclu : `B.first_seen_at <= A.last_seen_at` (sinon
  valides) ⇒ **non comptée** (critère 3 du proxy).
- **AC30** — Read-only : exécuter la probe sur un jeu de N comparables ne modifie
  **aucune** ligne (compte de comparables et de snapshots, et chaque `lineage_id`,
  identiques avant/après) — la probe n'écrit rien.
- **AC31** — Étiquetage des limites présent : la sortie du rapport contient une
  section « Limites » mentionnant explicitement les termes-clés « borne haute » (ou
  « candidats potentiels »), « syndication » et « intrant de décision » (assertions
  de présence de sous-chaînes). Le rapport ne contient aucune sous-chaîne d'`id`/URL
  des données synthétiques (anti-fuite : asserter l'absence d'un `id`/d'une URL témoin
  injectés dans le jeu).

### Isolation
- **AC32** — Aucun nouvel état mémoire de module : un test statique vérifie que
  l'étape 1 n'introduit aucun cache/compteur de module nécessitant un reset autouse
  au-delà de l'existant (`comparables`/snapshots déjà reset en `conftest.py`). La
  probe ne maintient pas d'état entre appels.

---

## 6. Note doctrine (`photo_urls` = métadonnée interne)

`photo_urls` (URLs des photos d'une annonce) est une **métadonnée technique interne**,
de même nature que `reference`/`customer_id`/`lineage_id` (SPEC 2a §6) : stockée pour
un usage interne futur (calcul de hash perceptuel à l'étape 2, aide au rattachement
cross-source), **jamais redistribuée ni exposée** dans une réponse API (§4). Conforme
à l'esprit de `CONTEXT.md` §11.3 amendé : « stockage interne par-annonce autorisé ;
redistribution du contenu interdite ». **Stocker une URL en interne ≠ la
redistribuer** ; on ne re-publie ni l'URL, ni l'image, ni l'annonce.

Recommandation **non bloquante** : ajouter une ligne à `CONTEXT.md` §11.3 (déjà amendé
pour `reference`/`customer_id`/`lineage_id`) et/ou `backend/CLAUDE.md` §7 mentionnant
explicitement `photo_urls` comme métadonnée technique interne non re-publiable, afin
qu'un agent ou reviewer futur ne re-détecte pas une fausse violation
RGPD/redistribution sur cette colonne. **Non bloquant pour l'étape 1.**

---

## 7. Ce que l'étape 1 NE fait PAS (renvoi explicite à l'étape 2)

L'étape 1 **ne** comporte **aucun** des éléments suivants, qui relèvent **tous** de
l'ÉTAPE 2 (à spécifier ultérieurement sur les chiffres de la probe §3) :
- **Download des bytes des images** (aucun fetch HTTP supplémentaire ; les URLs sont
  lues dans le JSON déjà collecté).
- **Calcul de hash perceptuel** (dHash/aHash/pHash), et toute **dépendance image**
  (Pillow, imagehash, PyWavelets, scipy). `requirements.txt` reste inchangé.
- **Table `photo_hashes`** (et donc aucun ré-audit des 4 chemins de purge `comparables`
  pour une table dépendante : à l'étape 1, `photo_urls` vit **sur** `comparables` et
  suit la même cascade que les autres colonnes — aucune nouvelle table).
- **Logique de matching cross-source** (distance de Hamming, vote k-sur-n,
  corroboration, pose/fusion de `lineage_id` cross-source).
- **Gestion du cas simultané** (deux annonces vivantes de sources différentes) et
  sémantique `/history` multi-membres cross-source.
- **Amendement de `CONTEXT.md` §11.3 sur le download transitoire d'images** aux fins
  de hash interne.
- **Vérification des ToS / hotlink-protection du CDN apimo.pro** (et des CDN agences).
- **Extension aux agences HTML** (pages détail, vignettes recadrées).

---

## 8. Risques résiduels assumés (étape 1)

1. **Structure exacte des éléments `photos` non figée par le code actuel** : le helper
   `_extract_photo_urls` est spécifié robuste aux deux formes (str / dict), et le
   développeur **doit** vérifier la structure réelle sur un échantillon JSON. Dégradé
   gracieux garanti : structure inattendue ⇒ `photo_urls = None`, jamais d'échec
   (AC6). Réversible (colonne nullable, droppable).
2. **Gisement de la probe non observable à pleine fenêtre** : historique inc.1/2a
   récent (déployé 2026-06-11) ⇒ peu de recul ; la probe est étiquetée « borne haute /
   intrant de décision » (§3.5, AC31). C'est précisément ce que l'étape 1 mesure pour
   décider de l'étape 2 — pas une vérité.
3. **Stock prod hérité sans `photo_urls`** : les ~17,7k lignes existantes auront
   `photo_urls = None` jusqu'au 1er passage de collecte post-déploiement. Documenté,
   non bloquant (on ne reconstruit pas un passé non capté). N'altère aucun chemin de
   lecture (la colonne n'est jamais exposée ni filtrée).
4. **Proxy d'attributs gonflé par la syndication bienici** : assumé et étiqueté ;
   l'étape 1 ne tranche pas le vrai taux de re-list, elle borne le candidat.

---

SPEC prête pour GATE 2 (approbation humaine).

# cross-agence — INCREMENT 1 — SPEC (GATE 2)

> Role : SPEC-WRITER. Cahier des charges implementable du **seul increment 1**
> du chantier cross-agence : tracking temporel mono-source par id stable.
> GATE 1 actee par l'humain (arbitrages 1/2/3 ci-dessous, non rediscutables).
> Lecture du code au 2026-06-10. Aucun code produit ici.
> Refs : `docs/specs/cross-agence-ANALYSE.md` (§2, §3, §6.3, §9.2),
> `.claude/lessons.md` (9.7/9.9/9.10), `backend/CLAUDE.md` (§1/§2/§5/§9/§12),
> `CONTEXT.md` §11.

---

## 1. Objectif & perimetre

### 1.1 Objectif
A chaque collecte hebdomadaire, **capturer et conserver** l'historique d'une
annonce identifiee par son `id` stable mono-source (`generate_stable_id`),
**sans rien ecraser** : date de premiere observation preservee, date de derniere
observation rafraichie, et un snapshot de prix ecrit uniquement quand le prix
change. Reparer au passage le defaut existant `ingestion/save.py:98-102`
(le `db.merge` ecrase prix + date a chaque run, detruisant l'historique).

### 1.2 In (perimetre de cet increment)
- Deux colonnes `first_seen_at` / `last_seen_at` sur `comparables` via
  micro-migration idempotente (pattern `db/session.py:51-61`).
- Une table de snapshots de prix `listing_price_snapshots` via
  `Base.metadata.create_all`.
- Logique de capture dans `ingestion/save.save_comparables` (lire la ligne
  existante avant d'ecrire ; ne plus se reposer sur `db.merge` seul).
- Un endpoint **admin** (`X-Admin-Token`) de consultation de l'historique d'une
  annonce par id, renvoyant des **metadonnees factuelles uniquement**.
- Une **purge de retention** a 24 mois apres `last_seen_at`.
- Amendement documentaire de `CONTEXT.md` §11.3 (wording §6 ci-dessous).

### 1.3 Out (explicitement increment 2+ ou hors chantier)
- **Aucune** image, **aucun** hash photo, **aucune** dependance Python nouvelle
  (pas de Pillow, pas d'imagehash, pas de scipy/PyWavelets). Le clustering photo
  cross-agence est l'**increment 2**, hors scope ici (ANALYSE §3.3, §9.2).
- **Aucune** exposition publique : ni dans `/analyze`, ni dans `AnalyzeResponse`,
  ni dans `frontend/lib/api.ts`. Ces fichiers ne sont **pas** touches
  (arbitrage GATE 1 n°3).
- **Aucun** matching cross-source ni cross-annonce (un id = une annonce d'une
  source ; pas de rapprochement entre ids). Increment 2.
- **Aucun** dedoublonnage des comparables dans `market_stats` : la selection de
  comparables et le score 40/30/30 restent **inchanges** (ANALYSE §5).
- **Aucune** nouvelle granularite : le pas reste hebdomadaire (collecte lundi
  04:00, ANALYSE §6.4).

### 1.4 Arbitrages GATE 1 actes (a implementer, ne pas rediscuter)
1. **Doctrine amendee** : stockage interne par-annonce + historique horodate
   AUTORISES. Exposition publique limitee aux metadonnees factuelles (source,
   anciennete, ecart %) ; JAMAIS de contenu re-publiable (texte, photos,
   adresse). Purge 24 mois apres `last_seen_at`. => amender `CONTEXT.md` §11.3
   (§6).
2. **Perimetre = increment 1 SEUL**, zero image, zero dep, mergeable prod.
3. **Exposition = admin/staging d'abord** : consultation par endpoint ADMIN,
   pas dans `/analyze`. Ne pas toucher `frontend/lib/api.ts` ni `AnalyzeResponse`.

---

## 2. Changements de schema

### 2.1 Colonnes ajoutees a `comparables` (micro-migration idempotente)
Modele `db/models.py` (classe `Comparable`) : ajouter

| Colonne | Type SQLAlchemy | Nullable | Defaut | Semantique |
|---|---|---|---|---|
| `first_seen_at` | `DateTime` | oui | (pose applicativement, cf. §3) | UTC de la 1re observation de cet `id`. JAMAIS reecrit. |
| `last_seen_at` | `DateTime` | oui | (pose applicativement) | UTC de la derniere observation. Rafraichi a chaque passage. |

Nullable=true cote schema pour ne pas casser les lignes prod existantes lors de
l'`ALTER TABLE` (les bases prod ont des lignes sans ces colonnes). La logique
applicative (§3) garantit qu'une ligne **ecrite par cet increment** porte
toujours les deux valeurs.

Migration : etendre le dict `_ADD_COLUMNS` de `db/session.py:35-48` (puis
`_migrate_comparables` les pose via `PRAGMA table_info` + `ALTER TABLE ADD
COLUMN`). DDL attendu :

```
"first_seen_at": "ALTER TABLE comparables ADD COLUMN first_seen_at DATETIME"
"last_seen_at":  "ALTER TABLE comparables ADD COLUMN last_seen_at DATETIME"
```

`collected_at` (`models.py:51`) est **conserve tel quel** (retro-compat ; il
continue d'etre rafraichi a chaque passage comme aujourd'hui ; il ne porte pas
l'historique, ce sont `first_seen_at`/`last_seen_at` qui le portent).

### 2.2 Nouvelle table `listing_price_snapshots` (via `create_all`)
Nouvelle classe dans `db/models.py`. Nom retenu : `listing_price_snapshots`
(suffixe `_snapshots` aligne sur le vocabulaire ANALYSE §6.3 « listing_snapshots » ;
prefixe `listing_price_` pour borner explicitement cet increment au prix, en
prevision d'autres snapshots en increment 2).

| Colonne | Type | Nullable | Contrainte | Semantique |
|---|---|---|---|---|
| `id` | `Integer` | non | PK, autoincrement | cle technique |
| `listing_id` | `String` | non | index | = `comparables.id` (id stable). **Pas** de FK formelle (SQLite/MVP ; coherence applicative). |
| `price_total` | `Float` | non | — | prix total observe a `observed_at` |
| `price_m2` | `Float` | non | — | prix/m2 observe (= price_total / surface) |
| `observed_at` | `DateTime` | non | — | UTC de l'observation ayant produit ce snapshot |

Index sur `listing_id` (lecture admin = serie d'un listing ; purge = jointure
logique sur les ids expires). Cree par `Base.metadata.create_all` (deja appele
`db/session.py:59`), aucune autre action requise pour une base neuve.

---

## 3. Comportement de `save_comparables` (pseudo-flux)

Cible : `ingestion/save.py`, fonction `save_comparables`. Les garde-fous
existants (`MIN_PRICE_M2`/`MAX_PRICE_M2` 800-12000, `OUT_OF_SCOPE_CITIES`,
`IN_SCOPE_DEPARTMENT` 57, surface/prix > 0) restent **inchanges et AVANT toute
ecriture** : une annonce rejetee ne cree NI comparable NI snapshot.

Pseudo-flux par annonce valide (apres garde-fous, dans la boucle `for ad`) :

```
now = datetime.utcnow()
existing = db.get(Comparable, ad["id"])        # lecture de la ligne existante

if existing is None:
    # 1re observation de cet id
    first_seen = now
    write_snapshot = True                        # snapshot initial
else:
    # re-observation : first_seen preserve, jamais reecrit
    first_seen = existing.first_seen_at or existing.collected_at or now
    write_snapshot = (existing.price_total != ad["price_total"])

upsert Comparable(
    ... champs metiers existants inchanges ...,
    first_seen_at = first_seen,
    last_seen_at  = now,
    collected_at  = now,                          # comportement actuel conserve
)

if write_snapshot:
    db.add(ListingPriceSnapshot(
        listing_id = ad["id"],
        price_total = ad["price_total"],
        price_m2    = price_m2,
        observed_at = now,
    ))
```

Regles imperatives :
- **`first_seen_at` immuable** : a la re-observation, on **relit** la valeur
  existante et on la repose telle quelle ; on ne la recalcule jamais a `now`.
  Repli `existing.collected_at` puis `now` pour les lignes prod heritees ou
  `first_seen_at` est `NULL` (post-migration, avant 1er passage de cet increment).
- **`last_seen_at` rafraichi a chaque passage**.
- **Snapshot conditionnel** : ecrit a la 1re observation, puis **uniquement si
  `price_total` differe** de la derniere valeur connue (= `existing.price_total`,
  qui est par construction le dernier prix puisque le comparable est upserte a
  chaque passage). Pas de snapshot si le prix est identique (anti-gonflement
  table, ANALYSE §6.3).
- **Definition de « change »** : egalite/inegalite **exacte** sur `price_total`
  (Python `!=` sur `float`). Argument : `price_total` provient d'un parsing prix
  deterministe (`normalize_price`, entiers en euros, pas de calcul flottant
  intermediaire cote prix total) ; introduire une tolerance (`abs(a-b) > eps`)
  serait de la **fausse precision** non justifiee et ouvrirait une borne floue a
  tester. On compare `price_total` (et non `price_m2`, derive de surface qui peut
  varier au reparsing) pour eviter des snapshots parasites a prix reellement
  constant.
- **Transaction** : un **seul `db.commit()` en fin** (comme aujourd'hui
  `save.py:109`), de sorte que comparable upserte et snapshot eventuel soient
  commits ensemble (coherence). En cas d'exception sur une annonce, le `except`
  existant (`save.py:105-107`) continue a la suivante ; aucune annonce
  partiellement ecrite ne doit subsister apres le commit final (le snapshot
  n'est `add` qu'apres l'upsert du comparable de la meme iteration).
- **Remplacer `db.merge` par une lecture explicite** : `db.merge` reconstruit un
  objet detache et **ecrase** `first_seen_at` ; il faut `db.get(Comparable, id)`
  (ou `query().get`) PUIS muter l'objet existant (ou en construire un neuf avec
  le `first_seen` relu) — voir leçon 9.10 : tester la **fonction** qui produit le
  defaut, pas un mock de merge.

Note isolation (leçon 9.7/9.9) : aucun nouvel etat **en memoire de module** n'est
introduit par cet increment (pas de cache). L'unique etat partage est la base
SQLite jetable, deja isolee par `conftest.py` (`DATABASE_PATH` suffixe pid,
`os.remove` en debut de session). Voir §3-AC pour le reset autouse de la nouvelle
table de tests.

---

## 4. Endpoint admin de consultation

### 4.1 Contrat
| Champ | Valeur |
|---|---|
| Methode / chemin | `GET /admin/comparables/{listing_id}/history` |
| Auth | header `X-Admin-Token`, via `_check_admin_token` (`main.py:182-187`) |
| Body | aucun |
| Codes | 200, 404 (id inconnu), 401 (token absent/mismatch), 503 (`ADMIN_TOKEN` non configure) |

Note codes auth : le pattern existant `_check_admin_token` renvoie **401** sur
token absent OU mismatch, et **503** si `ADMIN_TOKEN` n'est pas configure cote
serveur. Il n'y a **pas** de 403 dans ce codebase. La spec aligne donc l'AC sur
**401** (le brief mentionne « 401/403 » : ici c'est 401, on ne diverge pas du
pattern maison).

### 4.2 Reponse 200 (metadonnees factuelles UNIQUEMENT)
```json
{
  "listing_id": "<id stable>",
  "source": "bienici",
  "first_seen_at": "2026-01-06T04:00:00",
  "last_seen_at": "2026-06-08T04:00:00",
  "weeks_on_market": 22,
  "price_first": 250000,
  "price_last": 239000,
  "price_change_pct": -4.4,
  "snapshots": [
    {"price_total": 250000, "price_m2": 3125.0, "observed_at": "2026-01-06T04:00:00"},
    {"price_total": 239000, "price_m2": 2987.5, "observed_at": "2026-03-10T04:00:00"}
  ]
}
```

Regles de contenu (anti-redistribution, CONTEXT §11.3 amende, ANALYSE §7) :
- **Aucun** champ texte d'annonce, **aucune** adresse, **aucune** URL, **aucune**
  photo. Seuls `source`, dates, prix horodates et derives factuels.
- `weeks_on_market` = `floor((last_seen_at - first_seen_at).days / 7)`, entier.
- `price_change_pct` = `round((price_last - price_first) / price_first * 100, 1)`,
  derive du **premier et du dernier** snapshot. `null` si un seul snapshot (pas
  d'evolution) ou si `price_first == 0` (garde anti division par zero ;
  `price_first` > 0 par garde-fou d'ingestion, garde defensive seulement).
- `snapshots` : serie ordonnee par `observed_at` croissant.

### 4.3 404
Si aucun `Comparable` ne porte `listing_id` => 404 (`detail` generique, sans
echo du contenu). Un comparable sans aucun snapshot (cas heritage, ligne prod
pre-increment jamais re-observee) renvoie 200 avec `snapshots: []`,
`price_change_pct: null` et les dates disponibles (eventuellement `null`).

---

## 5. Retention / purge

### 5.1 Decision
Etendre l'endpoint **existant** `POST /admin/comparables/maintenance`
(`main.py:251-320`) plutot que d'en creer un nouveau : il est deja le point
unique d'assainissement de l'historique (CLAUDE §9), deja `dry_run=true` par
defaut, deja authentifie. Argument : coherence operationnelle (un seul endpoint
de maintenance), et le `dry_run` protege la purge de la meme facon que les purges
band/zone/dept existantes.

### 5.2 Comportement ajoute
- Nouvelle borne : **purge des `comparables` dont `last_seen_at` est strictement
  anterieur a `now - 24 mois`**, ET des `listing_price_snapshots` rattaches
  (memes `listing_id`). Compteur ajoute au resultat : `purged_retention`
  (comparables purges pour anciennete) et `purged_snapshots` (snapshots
  supprimes).
- Definition de « 24 mois » : seuil = `now - timedelta(days=730)`. Choix d'un
  delta en jours fixes (730) plutot qu'un decalage calendaire pour une **borne
  testable exacte** sans dependance a `dateutil` (zero dep, GATE 1 n°2).
- **Borne exacte** (leçon 9.7) : une ligne dont `last_seen_at == seuil`
  (exactement 730 jours) est **conservee** ; `last_seen_at < seuil` (731 jours)
  est **purgee**. Comparaison stricte `last_seen_at < seuil`.
- Une ligne dont `last_seen_at` est `NULL` (heritage non re-observe) n'est
  **pas** purgee par cette regle (on ne supprime que sur un last_seen connu et
  expire ; les autres regles band/zone/dept continuent de s'appliquer).
- `dry_run=true` (defaut) compte sans supprimer ; `dry_run=false` applique. Les
  snapshots d'un comparable purge sont supprimes dans la **meme transaction** que
  le comparable.

### 5.3 Reponse (extension du dict existant)
Le dict de reponse (`main.py:310-318`) gagne `purged_retention` et
`purged_snapshots` ; les cles existantes (`purged_band`, `purged_zone`,
`purged_dept`, `renamed`, `renamed_district`, `total_after`, `dry_run`) sont
**inchangees** (pas de regression du contrat maintenance).

---

## 6. Amendement doctrine `CONTEXT.md` §11.3 (wording propose)

Remplacer le point 3 (`CONTEXT.md:553`) par le texte suivant. Objectif : que les
agents futurs ne re-detectent pas une fausse violation alors que le stockage
par-annonce et l'historique horodate sont desormais doctrinairement autorises
(ANALYSE §1.3 constat 2, §10).

> 3. **Stockage interne par-annonce autorise ; redistribution du contenu
>    interdite.** La collecte stocke deja des annonces individuelles (table
>    `comparables`) et peut conserver leur **historique horodate** (dates de
>    premiere/derniere observation, snapshots de prix) a usage interne. Ce qui
>    reste interdit est la **redistribution du contenu** d'une annonce tierce :
>    ne jamais re-publier texte, photos, adresse exacte ou URL. L'**exposition
>    publique** se limite aux **agregats statistiques** (medianes, Q1/Q3) et aux
>    **metadonnees factuelles** non re-publiables (source, anciennete, ecart de
>    prix en %). **Retention** : purge des historiques 24 mois apres la derniere
>    observation (`last_seen_at`). Pas de DVF / notaires (point 4).

(Modification documentaire uniquement. Aucun autre point du §11 n'est touche.)

---

## 7. Criteres d'acceptation (testables)

Chaque AC est falsifiable et porte un test suggere (`fichier::nom_test`). Fichiers
proposes : `backend/tests/test_cross_agence_history.py` (logique save + lecture +
purge) et reutilisation de `backend/tests/conftest.py` pour l'isolation. Les tests
de la logique de capture appellent **directement `save_comparables`** sur la base
jetable reelle (leçon 9.10), pas un mock de `db.merge`.

### Schema & migration
- **AC1** — Apres `init_db()`, `PRAGMA table_info(comparables)` contient
  `first_seen_at` ET `last_seen_at`.
  `test_cross_agence_history.py::test_comparables_has_seen_columns`
- **AC2** — Apres `init_db()`, la table `listing_price_snapshots` existe avec les
  colonnes `id, listing_id, price_total, price_m2, observed_at` et un index sur
  `listing_id`.
  `::test_snapshots_table_and_index_exist`
- **AC3** — Idempotence : appeler `init_db()` **deux fois** de suite ne leve
  aucune exception et ne duplique aucune colonne (`table_info` identique apres le
  2e appel).
  `::test_init_db_idempotent_twice`

### Capture first_seen / last_seen
- **AC4** — Premiere observation d'un id : apres `save_comparables([ad])`, la
  ligne a `first_seen_at == last_seen_at` (= instant du run) et exactement **1**
  snapshot pour ce `listing_id`.
  `::test_first_observation_sets_first_and_last_and_initial_snapshot`
- **AC5** — `first_seen_at` JAMAIS ecrase : deux runs successifs du **meme id**
  (memes ou autres champs), avec `first_seen_at` du 2e run **strictement
  posterieur** force (instants distincts), laissent `first_seen_at` egal a la
  valeur du **1er** run.
  `::test_first_seen_never_overwritten_on_reobservation`
- **AC6** — `last_seen_at` rafraichi : au 2e run, `last_seen_at > first_seen_at`
  et reflete l'instant du 2e run.
  `::test_last_seen_refreshed_on_reobservation`

### Snapshots conditionnels
- **AC7** — Prix INCHANGE entre deux runs => **aucun** nouveau snapshot (compte
  reste 1).
  `::test_no_snapshot_when_price_unchanged`
- **AC8** — Prix CHANGE entre deux runs => **un** nouveau snapshot (compte passe
  a 2), `observed_at` du second = instant du 2e run, `price_total` = nouveau prix.
  `::test_new_snapshot_only_when_price_changes`
- **AC9** — Borne exacte « change » : un `price_total` strictement egal (meme
  valeur float) n'ecrit pas de snapshot ; une difference d'**1 euro** en ecrit un.
  `::test_price_change_boundary_exact_equality`
  `::test_price_change_boundary_one_euro_writes_snapshot`

### Garde-fous preserves
- **AC10** — Une annonce hors bande prix/m2 (`price_m2 < 800` ou `> 12000`) ou
  hors perimetre (`OUT_OF_SCOPE_CITIES` / code postal hors `57`) ne cree NI
  comparable NI snapshot.
  `::test_rejected_listing_creates_neither_comparable_nor_snapshot`

### Endpoint admin de lecture
- **AC11** — `GET /admin/comparables/{id}/history` sans `X-Admin-Token` (ou token
  errone) => **401**.
  `::test_history_requires_admin_token`
- **AC12** — id inconnu (aucun comparable) => **404**.
  `::test_history_unknown_id_returns_404`
- **AC13** — id connu avec 2 snapshots de prix differents => **200** avec
  `snapshots` (2 entrees ordonnees par `observed_at` croissant),
  `weeks_on_market` (entier), `price_first`, `price_last`,
  `price_change_pct` derive du premier/dernier (signe correct : baisse => negatif).
  `::test_history_returns_factual_metadata`
- **AC14** — La reponse ne contient **aucune** cle de contenu re-publiable :
  l'ensemble des cles est inclus dans
  `{listing_id, source, first_seen_at, last_seen_at, weeks_on_market, price_first,
  price_last, price_change_pct, snapshots}` ; aucune cle `address`, `url`, `text`,
  `title`, `description`, `photos`. Tester aussi qu'aucune valeur de `snapshots[]`
  ne porte d'autre cle que `{price_total, price_m2, observed_at}` (leçon 9.10 :
  prouver l'absence de fuite a la couche qui construit le dict, pas seulement via
  un response_model).
  `::test_history_exposes_no_republishable_content`

### Retention / purge (bornes exactes)
- **AC15** — Comparable dont `last_seen_at == now - 730j` (exactement 24 mois) est
  **conserve** par la maintenance (`dry_run=false`) ; ses snapshots subsistent.
  `::test_retention_boundary_exactly_730_days_kept`
- **AC16** — Comparable dont `last_seen_at == now - 731j` est **purge**
  (`dry_run=false`), et ses `listing_price_snapshots` sont supprimes ;
  `purged_retention` et `purged_snapshots` comptent ces suppressions.
  `::test_retention_boundary_731_days_purged_with_snapshots`
- **AC17** — `dry_run=true` (defaut) ne supprime rien : `purged_retention > 0`
  possible dans le compteur mais `total_after` et le contenu reel inchanges.
  `::test_retention_dry_run_counts_without_deleting`
- **AC18** — Une ligne `last_seen_at IS NULL` n'est pas purgee par la regle de
  retention.
  `::test_retention_does_not_purge_null_last_seen`

### Non-regression & contrat
- **AC19** — Le contrat `/analyze` est INCHANGE : `AnalyzeResponse` ne gagne
  aucune cle ; un appel `/analyze` renvoie le meme jeu de cles qu'avant
  (`global_score, verdict, confidence, pillars, actions, local_context`).
  `::test_analyze_contract_unchanged` (ou reutiliser le test smoke existant).
- **AC20** — `POST /admin/comparables` conserve son contrat
  (`{received, saved, total_in_db}`) ET capture desormais l'historique : apres un
  import d'un id neuf, ce meme id est consultable via
  `GET /admin/comparables/{id}/history` (200, 1 snapshot).
  `::test_admin_import_still_works_and_now_records_history`
- **AC21** — La suite complete existante (les ~220 tests) reste **verte** apres
  l'increment (aucune dependance a `db.merge` cassee, aucun etat qui fuit).
  Verifie par l'execution CI `test.yml` ; localement par `pytest backend/tests`.

### Isolation (leçon 9.7 / 9.9)
- **AC22** — La table `listing_price_snapshots` est **reinitialisee avant chaque
  test** par une fixture **autouse en `conftest.py`** (DELETE protege, sur le
  modele de `_reset_events_table`, `conftest.py:71-92`), jamais en fixture locale.
  Un test statique verifie la presence de cette fixture autouse ; un test
  dynamique prouve que deux runs successifs de `save_comparables` partent d'une
  table vierge (pas d'accumulation inter-tests).
  `::test_conftest_resets_snapshots_table`

---

## 8. Risques residuels / notes increment 2

- **`first_seen_at` NULL pour le stock prod existant** : les ~17,7k lignes deja
  en base n'auront `first_seen_at` qu'au premier passage de collecte post-deploy
  (repli `collected_at`). L'historique « depuis quand » n'est donc fiable qu'a
  partir du 1er run post-merge — assume (on ne peut pas reconstruire un passe
  non collecte). Documente, pas bloquant.
- **Pas de FK formelle** snapshot -> comparable (SQLite/MVP) : la coherence est
  applicative ; la purge supprime explicitement les snapshots des ids purges. Un
  snapshot orphelin ne peut apparaitre que par ecriture hors `save_comparables`
  (non prevu). A surveiller si increment 2 multiplie les ecrivains.
- **Volume** : mode delta (1 snapshot au 1er passage + 1 par changement de prix),
  ~20-50k lignes/an ≈ 5-10 Mo/an (ANALYSE §6.3) — confortable sur le volume 1 Go.
- **Increment 2 (hors scope)** : hashes photo + clustering cross-agence,
  dependant de la verification prerequis #0 (API bienici expose photos + agence),
  staging-first, job CI dedie, et de cet increment 1 (le cluster agrege des
  historiques). Aucune table/colonne de cet increment ne prejuge du schema
  photo de l'increment 2.
- **Egalite exacte sur `price_total`** : si une source se met a renvoyer un prix
  flottant non entier instable (ex. recalcul TTC), des snapshots parasites
  pourraient apparaitre. Non observe aujourd'hui (`normalize_price` produit des
  entiers euros) ; a reevaluer si une source change de format (le test AC9 fige
  la borne, un faux-vert serait detecte par un changement de comportement reel).

---

## 9. Recap des AC pour la GATE 2

- **Schema/migration** : AC1 (colonnes seen), AC2 (table snapshots + index),
  AC3 (init_db idempotent x2).
- **Capture** : AC4 (1re obs : first=last + snapshot initial), AC5 (first_seen
  jamais ecrase), AC6 (last_seen rafraichi).
- **Snapshots conditionnels** : AC7 (rien si prix egal), AC8 (1 si prix change),
  AC9 (borne exacte egalite / +1 euro).
- **Garde-fous** : AC10 (annonce rejetee => ni comparable ni snapshot).
- **Lecture admin** : AC11 (401 sans token), AC12 (404 id inconnu), AC13 (200 +
  metadonnees factuelles), AC14 (aucune cle re-publiable).
- **Retention** : AC15 (730j conserve), AC16 (731j purge + snapshots), AC17
  (dry_run ne supprime pas), AC18 (NULL non purge).
- **Non-regression** : AC19 (`/analyze` inchange), AC20 (`/admin/comparables`
  inchange + capture historique), AC21 (~220 tests verts).
- **Isolation** : AC22 (reset autouse en conftest de la table snapshots).

SPEC prête pour GATE 2 (approbation humaine).

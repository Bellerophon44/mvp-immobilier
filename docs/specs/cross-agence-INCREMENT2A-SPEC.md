# cross-agence — INCRÉMENT 2a (re-link « sans photo », même agence) — SPEC (GATE 2)

> Rôle : SPEC-WRITER. Cahier des charges implémentable du **seul incrément 2a** :
> re-lier les annonces successives d'un même bien re-publié par la **même agence**
> (nouvel `id` stable, même mandat) pour prolonger le suivi longitudinal de prix
> par-dessus la rupture d'`id`. GATE 1 actée (arbitrages §0, non rediscutables).
> Lecture du code au 2026-06-13. **Aucun code produit ici.**
> Réfs lues : `.claude/lessons.md`, `docs/specs/cross-agence-INCREMENT2A-ANALYSE.md`,
> `docs/specs/cross-agence-INCREMENT1-SPEC.md`, `backend/CLAUDE.md` (§2/§4/§5/§9/§12),
> `CONTEXT.md` §11. Code réel ancré : `ingestion/save.py`, `db/session.py`,
> `db/models.py`, `scrapers/sources/bienici.py`, `scrapers/models.py`,
> `jobs/push_comparables.py`, `app/main.py`.

---

## 0. Arbitrages GATE 1 actés (à implémenter, ne pas rediscuter)

1. **Séquençage** : capture ET logique de rattachement ET lecture, **d'un bloc**
   (Q1=b). Pas de découplage capture/logique.
2. **Modèle de lignée** : colonne `lineage_id` sur `comparables` (Q2=a), via
   micro-migration idempotente (pattern `db/session.py:53-63`). PAS de table de
   mapping, PAS de re-pointage de snapshots. En lecture, repli `lineage_id or id`
   pour les lignes héritées. `first_seen_at` de la lignée propagé sur le nouveau
   membre.
3. **Rattachement conservateur** : jamais de faux lien (Q3=a). Clé de base par §3.
   Doute (référence absente/triviale, plusieurs candidats, corroboration
   insuffisante) ⇒ NE PAS rattacher (nouvelle lignée).
4. **Périmètre** : bienici (clés JSON `reference`, `customerId`) + best-effort HTML
   agences pour `reference` (nullable) (Q4=b). `customerId` requis **uniquement**
   pour bienici ; pour une source mono-agence HTML il n'est pas requis (§3.3).
5. **Lignée en lecture/rétention** (Q5=a) : `/history` agrège la lignée ; la
   rétention 730j raisonne sur le `last_seen_at` MAX de la lignée ; cascade
   snapshots ré-auditée sur tous les chemins de purge. `reference`/`customer_id`/
   `lineage_id` restent **internes**, jamais exposés dans une réponse API.
6. **Doctrine** (Q6=a) : `reference`/`customerId` = identifiants techniques
   agence/mandat, pas de donnée perso, conformes à l'esprit §11.3 amendé (note §6).

---

## 1. Objectif et périmètre

### 1.1 Objectif
Prolonger l'historique de prix d'un **même bien physique** re-publié par la **même
agence** : quand un bien delisté réapparaît sous un nouvel `id` stable, le rattacher
à la lignée du bien disparu (mémoire de `first_seen_at` et continuité de l'historique
`listing_price_snapshots`) plutôt que de démarrer un historique neuf comme le fait
l'incrément 1 aujourd'hui (`ingestion/save.py:84-86`).

### 1.2 In (périmètre de cet incrément)
- **Capture** de `reference` (toutes sources, nullable) et `customer_id` (bienici,
  nullable) : `scrapers/sources/bienici.py::_parse_listing`, best-effort HTML pour
  les 4 agences, propagation `PropertyListing`/`to_dict()` (`scrapers/models.py`),
  `_is_valid` (`jobs/push_comparables.py`), `ComparableIn` (`app/main.py`),
  persistance (`ingestion/save.py`).
- **Schéma** : colonnes `reference`, `customer_id`, `lineage_id` sur `comparables`
  via micro-migration idempotente (`db/session.py::_ADD_COLUMNS`), index sur
  `lineage_id`.
- **Logique de rattachement** à l'ingestion (`ingestion/save.py`, branche
  `existing is None`) : recherche d'un candidat « récemment disparu » selon la clé
  par-source (§3), pose de `lineage_id` + propagation de `first_seen_at`.
- **Lecture** : `/admin/comparables/{id}/history` agrège la lignée (§4.1).
- **Rétention** : la borne 730j raisonne sur le `last_seen_at` MAX de la lignée
  (§4.2), cascade snapshots inchangée pour les 4 chemins de purge.

### 1.3 Out (explicitement 2b ou hors chantier)
- **Changement d'agence** (delisté A → relisté B : `reference` ET `customerId`
  changent). Relève de l'incrément **2b** (matching pHash). Hors scope 2a.
- **Aucune** image, **aucun** hash photo, **aucune** dépendance Python nouvelle.
- **Aucune** exposition publique : `/analyze`, `AnalyzeResponse`,
  `frontend/lib/api.ts` **non touchés** (même garantie qu'inc.1).
- **Aucun** dédoublonnage des comparables dans `market_stats` : sélection des
  comparables et score 40/30/30 **inchangés**. Une lignée n'est jamais un filtre
  de sélection.
- **Cas « même bien, deux annonces vivantes au même run »** (doublon simultané,
  non disparu) : NE PAS rattacher en 2a (§3.5). Relève du signal multi-mandat, 2b.

### 1.4 Frontière 2a vs 2b (rappel)
2a = re-publication **même agence**, sans photo, clé `reference`+`source`
(+`customerId` bienici)+attributs. 2b = **changement d'agence**, clé pHash photo.
2a ne préjuge d'aucun schéma photo de 2b.

---

## 2. Changements de schéma

### 2.1 Colonnes ajoutées à `comparables` (micro-migration idempotente)
Modèle `db/models.py` (classe `Comparable`) : ajouter

| Colonne | Type SQLAlchemy | Nullable | Index | Sémantique |
|---|---|---|---|---|
| `reference` | `String` | oui | non | Référence de mandat captée à la collecte (bienici clé JSON `reference` ; HTML agences best-effort). `None` si non extraite. Identifiant technique INTERNE. |
| `customer_id` | `String` | oui | non | Compte annonceur bienici (clé JSON `customerId`). `None` hors bienici ou absent. Identifiant technique INTERNE. |
| `lineage_id` | `String` | oui | **oui** | Identifiant de lignée du bien (survit au changement d'`id`). Posé applicativement à `id` (nouvelle lignée) ou au `lineage_id` du candidat rattaché. `None` pour les lignes héritées (repli `lineage_id or id` en lecture). |

Nullable côté schéma pour ne pas casser les ~17,7k lignes prod existantes lors de
l'`ALTER TABLE`. La logique applicative (§3) garantit qu'une ligne **écrite par cet
incrément** porte toujours un `lineage_id`.

Migration : étendre `_ADD_COLUMNS` de `db/session.py:35-50`. DDL attendu :

```
"reference":   "ALTER TABLE comparables ADD COLUMN reference VARCHAR"
"customer_id": "ALTER TABLE comparables ADD COLUMN customer_id VARCHAR"
"lineage_id":  "ALTER TABLE comparables ADD COLUMN lineage_id VARCHAR"
```

Index sur `lineage_id` : déclaré sur la colonne du modèle (`index=True`).
`Base.metadata.create_all` (déjà appelé `db/session.py:61`) crée l'index sur une
base **neuve** ; pour une base **prod existante** (table déjà créée, colonne ajoutée
par `ALTER`), l'index est créé par une instruction idempotente
`CREATE INDEX IF NOT EXISTS ix_comparables_lineage_id ON comparables (lineage_id)`
ajoutée à la migration (`_migrate_comparables`), exécutée **après** l'`ALTER`.
Re-run sans erreur exigé (AC).

`reference`/`customer_id` ne sont **pas** indexés : la recherche de candidat (§3)
filtre d'abord sur `source` + fenêtre temporelle (volume restreint), pas sur un
index `reference` (référence triviale = faible sélectivité). Index non requis au
volume MVP.

### 2.2 `listing_price_snapshots`
**Inchangée.** Aucune colonne ajoutée. Les snapshots restent rattachés à un
`listing_id` = `comparables.id` (id de membre), JAMAIS re-pointés vers un id de
lignée (interdiction de réécriture d'historique, leçon inc.1 2026-06-11). La lignée
se reconstitue en lecture par jointure logique (§4.1), pas par mutation des
snapshots.

### 2.3 Capture côté scrapers

**bienici** (`scrapers/sources/bienici.py::_parse_listing`, `:190-241`) : lire les
clés JSON directes `reference` et `customerId` (confirmées PREREQ0, remplissage
99,9 % / ~59 %), via des helpers nullable sur le modèle de `_extract_postal`
(`:132-143`). Valeur retenue : `str(...)` si présente et non vide après strip, sinon
`None`. Renseigner `reference=` et `customer_id=` dans `PropertyListing(...)`.

**HTML agences** (benedic, idemmo, immoheytienne, laveine_immo) : extraction
**best-effort** de `reference` (sélecteurs CSS laissés au developer). Contrat
impératif : si le sélecteur ne trouve rien → `reference=None`, **jamais** d'échec de
collecte (pas d'exception propagée, pas de 0 annonce). `customer_id` reste `None`
pour ces sources (mono-agence, `source` identifie l'agence).

**`scrapers/models.py`** : ajouter à `PropertyListing` deux champs optionnels
`reference: Optional[str] = None` et `customer_id: Optional[str] = None`. `to_dict()`
(`asdict`) les propage automatiquement.

**`jobs/push_comparables.py::_is_valid`** : `reference`/`customer_id` ne sont PAS
ajoutés à `_REQUIRED_STR` (un item sans référence reste valide et poussé ; il créera
simplement une nouvelle lignée). Aucun item ne doit être écarté pour absence de
`reference`/`customer_id`.

**`app/main.py::ComparableIn`** : ajouter `reference: Optional[str] = None` et
`customer_id: Optional[str] = None`. `model_dump()` les transmet à
`save_comparables`.

---

## 3. Logique de rattachement à l'ingestion (`ingestion/save.py`)

Cible : `save_comparables`, **branche `existing is None`** (aujourd'hui
`save.py:84-86`). Les garde-fous existants (prix/m² [800-12000],
`OUT_OF_SCOPE_CITIES`, `IN_SCOPE_DEPARTMENT` 57, surface/prix > 0) restent
**inchangés et AVANT toute écriture** (`save.py:58-75`) : une annonce rejetée ne
déclenche aucune recherche de lignée et ne crée NI comparable NI snapshot NI lignée.

### 3.1 Pseudo-flux (annonce valide, `existing is None`)

```
now = datetime.utcnow()
existing = db.get(Comparable, ad["id"])

if existing is None:
    candidate = _find_lineage_candidate(db, ad, now)   # §3.2 / §3.3 / §3.4
    if candidate is not None:
        lineage_id = candidate.lineage_id or candidate.id   # repli héritage
        first_seen = candidate.first_seen_at or candidate.collected_at or now
    else:
        lineage_id = ad["id"]            # nouvelle lignée (sur elle-même)
        first_seen = now
    write_snapshot = True                # 1re observation de cet id
else:
    # re-observation d'un id connu : comportement inc.1 STRICTEMENT inchangé
    lineage_id = existing.lineage_id or existing.id
    first_seen = existing.first_seen_at or existing.collected_at or now
    write_snapshot = (existing.price_total != price)
```

Le `lineage_id`, `reference`, `customer_id` sont ajoutés au dict `fields` upserté
(`save.py:97-120`). Le snapshot reste rattaché à `ad["id"]` (membre), jamais à
`lineage_id`.

Règles impératives :
- **`first_seen_at` immuable par membre** : à la re-observation d'un id connu, on
  relit la valeur existante (jamais recalculée). Au rattachement, le NOUVEAU membre
  reçoit le `first_seen_at` de la lignée du candidat (propagation, sous-option (i)
  ANALYSE §3.1). Les membres existants ne sont JAMAIS mutés par un rattachement.
- **Snapshots jamais touchés** : aucun re-pointage. La continuité se lit en §4.1.
- **`lineage_id` posé une seule fois** : un id déjà en base a déjà son `lineage_id`
  et ne repasse jamais par `_find_lineage_candidate` (idempotence, §3.6).

### 3.2 Définition d'un candidat « récemment disparu »
Un candidat est un `Comparable` en base tel que :
- `last_seen_at IS NOT NULL` ET `(now - last_seen_at).days <= 90` (fenêtre W = 90
  jours **révolus** ; exprimée en jours entiers, sens conservateur — leçon inc.1
  2026-06-11 « borne temporelle littérale intestable »). `.days == 90` ⇒ éligible ;
  `.days == 91` ⇒ exclu.
- `last_seen_at < now` n'est **pas** une condition supplémentaire requise (un
  candidat vu dans le même run aurait `last_seen_at == now` ; il est exclu par §3.5
  via la clé d'attributs seulement s'il n'est pas réellement disparu — voir §3.5
  pour le traitement explicite du « même run »).

`now` est l'instant de traitement de l'annonce courante (`datetime.utcnow()`),
cohérent avec la pose de `last_seen_at` (`save.py:77`).

### 3.3 Clé de rattachement (par-source, anti-faux-lien)
Tous les prédicats ci-dessous sont **cumulatifs** (TOUS requis) :

1. **`reference` égale** : `candidate.reference == ad["reference"]`, les deux non
   vides après strip. Si `ad["reference"]` est `None` ou vide ⇒ pas de recherche
   (nouvelle lignée).
2. **`source` égale** : `candidate.source == ad["source"]` (2a est intra-source).
3. **`property_type` égal** : `candidate.property_type == ad["property_type"]`.
4. **`city` canonique égale** : `candidate.city == canonical_city(ad["city"])`
   (la ville est déjà canonicalisée à l'ingestion, `save.py:67`).
5. **`surface_m2` à ±2 %** : `abs(candidate.surface_m2 - surface) <= 0.02 *
   candidate.surface_m2`. Borne **inclusive** (exactement 2,00 % ⇒ accepté ; 2,01 %
   ⇒ rejeté). Pas de contrainte de prix (l'écart de prix EST le signal).
6. **Garde temporel** : §3.2 (≤ 90 jours révolus).
7. **`customer_id` (règle PAR-SOURCE)** :
   - **Si `ad["source"] == "bienici"`** : `customer_id` **OBLIGATOIRE et égal**
     (`candidate.customer_id == ad["customer_id"]`, les deux non vides). bienici
     multiplexe plusieurs agences ⇒ une même `reference` peut collisionner entre
     agences ⇒ `customerId` lève l'ambiguïté. `customer_id` absent d'un des deux
     côtés ⇒ **pas de rattachement** (nouvelle lignée).
   - **Si `ad["source"]` est une source mono-agence** (benedic, idemmo,
     immoheytienne, laveine_immo) : `customer_id` **non requis** (`source` identifie
     déjà l'agence). `reference`+`source`+prédicats 3/4/5/6 suffisent. `customer_id`
     absent toléré.

### 3.4 Multi-candidats ⇒ abstention
`_find_lineage_candidate` recherche TOUS les candidats satisfaisant §3.2+§3.3 :
- **0 candidat** ⇒ nouvelle lignée (`lineage_id = ad["id"]`).
- **exactement 1 candidat** ⇒ rattachement à ce candidat.
- **≥ 2 candidats** ⇒ **abstention** (ambiguïté ⇒ nouvelle lignée, jamais de choix
  arbitraire). Verrouillé par un AC.

### 3.5 Cas « même run » (doublon simultané non disparu)
Si l'ancien membre est encore présent dans le run courant (ré-écrit avec
`last_seen_at = now` AVANT le traitement du nouvel id), il satisfait `.days == 0 <=
90`. Ce n'est PAS un re-list au sens 2a (les deux annonces coexistent ⇒ deux mandats
vivants, hors scope §1.3). Traitement retenu : **ne pas distinguer ce cas par un
prédicat temporel fragile** ; il est neutralisé en amont parce qu'un bien réellement
re-listé a son ancien `id` **absent du run** (donc `last_seen_at` figé à une date
antérieure). Le cas pathologique « deux annonces réellement distinctes, même
`reference`+`customerId`+attributs, même run » est :
- soit un faux doublon de la même agence (rare) ⇒ le rattachement les fusionne (coût
  faible : c'est bien le même mandat) ;
- soit ≥ 2 candidats ⇒ abstention par §3.4.

Aucun AC n'exige de fusionner deux annonces vivantes ; un AC vérifie que deux
annonces du **même run** (même `reference`) ne produisent pas de comportement
divergent du contrat inc.1 (pas de 500, pas de perte de batch ; cf. §3.6).

### 3.6 Ordre / idempotence dans les batchs de 1000
(`jobs/push_comparables.py:82`, session `autoflush=False`, `INCREMENT1-SPEC.md` §8.)
- `_find_lineage_candidate` lit la base (`db.query`), pas l'ordre du batch ⇒ robuste
  à l'ordre d'arrivée (surface croissante).
- **Idempotence** : re-rejouer le même lot ne re-crée NI lignée NI snapshot. Un id
  déjà en base passe par la branche `existing is not None` (jamais de re-détection).
  Un rattachement déjà fait a posé `lineage_id` sur le membre ; un re-run le relit
  tel quel.
- **Id dupliqué intra-batch** (préexistant inc.1) : 2a NE DOIT PAS l'aggraver.
  `_find_lineage_candidate` ne fait que des `db.query` en lecture et ne `db.add`
  rien ; il n'introduit aucun nouvel `add` non flushé susceptible de créer une
  collision PK supplémentaire. Comportement identique à inc.1 sur ce cas.

### 3.7 Aucun état mémoire de module
2a n'introduit aucun cache/compteur en mémoire de module (pas de fixture autouse
nouvelle requise au-delà du reset `comparables`/snapshots existant en `conftest.py`).

---

## 4. Lecture sur lignée + rétention sur lignée

### 4.1 `/admin/comparables/{id}/history` (agrégation de lignée)
Cible : `app/main.py:218-283`. Contrat HTTP **inchangé** (méthode, auth
`X-Admin-Token`, codes 200/401/404/503). Changement de **contenu** uniquement.

Résolution de lignée :
1. `row = db.get(Comparable, listing_id)` ; `None` ⇒ 404 (inchangé).
2. `lineage = row.lineage_id or row.id` (repli héritage).
3. Membres de la lignée :
   `members = db.query(Comparable).filter((Comparable.lineage_id == lineage) | (Comparable.id == lineage)).all()`
   (le `or row.id` couvre les membres hérités dont `lineage_id IS NULL` qui sont
   eux-mêmes la racine ; un membre rattaché porte toujours `lineage_id == lineage`).
4. `member_ids = {m.id for m in members}`.
5. Snapshots fusionnés :
   `snaps = db.query(ListingPriceSnapshot).filter(ListingPriceSnapshot.listing_id.in_(member_ids)).order_by(ListingPriceSnapshot.observed_at.asc()).all()`.

Dérivés (sur la lignée) :
- `first_seen_at` = **MIN** des `first_seen_at` non nuls des membres (repli
  `collected_at` puis `None`).
- `last_seen_at` = **MAX** des `last_seen_at` non nuls des membres.
- `weeks_on_market` = `(last_seen_at - first_seen_at).days // 7` (entier), `None`
  si une des deux dates manque.
- `price_first` = `price_total` du **premier** snapshot fusionné ; `price_last` =
  du **dernier** ; `None` si aucun snapshot.
- `price_change_pct` = `round((price_last - price_first) / price_first * 100, 1)`,
  `None` si < 2 snapshots OU `price_first` falsy.
- `source` = `row.source` (la source du membre interrogé ; 2a est intra-source ⇒
  identique sur toute la lignée).
- `listing_id` = `row.id` (l'id interrogé, continuité d'usage admin).

Interrogeable par **n'importe quel id membre** : `/history/{id_A}` et `/history/{id_B}`
d'une même lignée renvoient la **même** série fusionnée, le même `first_seen_at`
(MIN) et `last_seen_at` (MAX).

**Confidentialité (impératif)** : la réponse 200 ne contient **aucune** des clés
`reference`, `customer_id`, `lineage_id`, ni aucune clé de contenu re-publiable
(`address`, `url`, `text`, `title`, `description`, `photos`, `city`, `district`).
L'ensemble des clés de la réponse est inclus dans
`{listing_id, source, first_seen_at, last_seen_at, weeks_on_market, price_first,
price_last, price_change_pct, snapshots}` ; chaque entrée de `snapshots[]` ne porte
que `{price_total, price_m2, observed_at}`. Vérifié à la couche qui construit le
dict, pas seulement via response_model (leçon 9.10).

### 4.2 Rétention sur lignée (`POST /admin/comparables/maintenance`)
Cible : la branche rétention `app/main.py:391-399`. Décision : **ne jamais purger un
membre dont la LIGNÉE est encore vivante.**

Comportement ajouté : avant de purger un comparable `c` par la règle de rétention,
calculer le `last_seen_at` **MAX de sa lignée** :
- `lineage = c.lineage_id or c.id`.
- `lineage_max_last_seen` = MAX des `last_seen_at` non nuls de tous les membres de
  cette lignée (`Comparable.lineage_id == lineage OR Comparable.id == lineage`).
- Le membre `c` n'est purgé par rétention que si
  `lineage_max_last_seen is not None AND (maintenance_now - lineage_max_last_seen).days > 730`.
  La borne reste **730 jours révolus** (exactement 730 ⇒ conservé ; 731 ⇒ purgé),
  identique à inc.1.
- Une lignée dont MAX(`last_seen_at`) est `NULL` n'est jamais purgée par cette règle.

Conséquence testable : un ancien membre (`last_seen_at` du membre = 731j) dont la
lignée contient un membre récent (re-listé, `last_seen_at` récent) est **conservé**
(la lignée est vivante). Un membre dont TOUS les membres de la lignée sont expirés
(MAX > 730j) est purgé avec ses snapshots.

Les autres règles de purge (band, zone, dept) restent **inchangées** : elles
purgent un comparable hors-périmètre indépendamment de la lignée (un bien hors bande
prix/m² ou hors dépt 57 n'a rien à faire en base, lignée vivante ou non).

### 4.3 Cascade snapshots (ré-audit des 4 chemins)
`_purge_snapshots_of(c.id)` (`main.py:354-364`) reste appelé sur **chaque** chemin de
purge (band, zone, dept, rétention) — inchangé. Le balayage final d'orphelins
(`main.py:424-429`, compteur `purged_orphan_snapshots`) reste en place. 2a ne crée
aucun nouveau chemin de suppression de comparable ⇒ aucun nouveau point de cascade,
mais la spec **réaffirme** (leçon inc.1) que la cascade doit rester sur les 4 chemins
et qu'un membre purgé n'emporte que SES propres snapshots (jamais ceux des autres
membres de la lignée encore vivants). Vérifié par un AC.

Le dict de réponse maintenance est **inchangé** (mêmes clés
`purged_band/zone/dept/retention/snapshots/orphan_snapshots`, `renamed`,
`renamed_district`, `total_after`, `dry_run`). `dry_run=true` par défaut.

---

## 5. Critères d'acceptation (testables)

Chaque AC est falsifiable et transformable 1:1 en pytest. Fichiers suggérés :
`backend/tests/test_cross_agence_increment2a.py` (schéma, capture, rattachement,
lignée, rétention) ; réutilisation de `backend/tests/conftest.py` (isolation base
jetable, reset autouse `comparables`/snapshots). Les tests de capture et de
rattachement appellent **directement `save_comparables`** sur la base jetable réelle
(leçon 9.10), jamais un mock de `db.get`/`db.merge`. Toutes les bornes temporelles
sont posées en injectant `last_seen_at`/`first_seen_at` explicites en base.

### Schéma & migration
- **AC1** — Après `init_db()`, `PRAGMA table_info(comparables)` contient
  `reference`, `customer_id` ET `lineage_id`.
- **AC2** — Après `init_db()`, un index existe sur `comparables.lineage_id`
  (`PRAGMA index_list(comparables)` + `index_info` mentionne `lineage_id`).
- **AC3** — Idempotence : appeler `init_db()` **deux fois** ne lève aucune exception,
  ne duplique aucune colonne, ne duplique pas l'index (`table_info` et `index_list`
  identiques après le 2e appel).

### Capture
- **AC4** — `save_comparables([ad])` avec `ad["reference"]="ABC"` et
  `ad["customer_id"]="cust1"` persiste `reference == "ABC"` et
  `customer_id == "cust1"` sur la ligne.
- **AC5** — `save_comparables([ad])` sans `reference` ni `customer_id` (clés absentes
  ou `None`) persiste la ligne avec `reference is None` et `customer_id is None`
  (aucune exception, comparable bien créé).
- **AC6** — `jobs.push_comparables._is_valid` renvoie `True` pour un item complet
  **sans** `reference` ni `customer_id` (ces champs ne sont pas requis ; l'item est
  poussé).
- **AC7** — Contrat capture HTML best-effort : un `PropertyListing` construit sans
  `reference` a `reference is None` et `to_dict()["reference"] is None` ; le champ
  `customer_id` y est aussi `None` par défaut. (Vérifie le contrat nullable du
  modèle sans dépendre du réseau.)

### Lignée par défaut (rétro-compat)
- **AC8** — Première observation d'un id neuf SANS candidat : après
  `save_comparables([ad])`, la ligne a `lineage_id == ad["id"]`,
  `first_seen_at == last_seen_at` (instant du run) et exactement 1 snapshot.
- **AC9** — Repli héritage en lecture : une ligne préexistante avec
  `lineage_id IS NULL` est traitée par `/history` comme sa propre racine
  (`lineage = id`) ; la réponse agrège uniquement ses snapshots, sans erreur.

### Rattachement — cas nominal
- **AC10** — Re-list bienici nominal : un comparable disparu
  (`reference="R1"`, `customer_id="C1"`, `source="bienici"`, `last_seen_at` = now-30j,
  `lineage_id="L"`, `first_seen_at` = T0) ; à l'arrivée d'un id neuf de même
  `reference`/`customer_id`/`source`/`property_type`/`city`, `surface_m2` égale, prix
  **différent** ⇒ le nouveau membre reçoit `lineage_id == "L"` et
  `first_seen_at == T0` (propagé), et un snapshot du nouveau prix est écrit sur le
  nouvel id.
- **AC11** — Lignée racine = id : si le candidat a `lineage_id IS NULL` (héritage),
  le nouveau membre reçoit `lineage_id == candidate.id` (repli `lineage_id or id`).

### Rattachement — bornes exactes
- **AC12** — Fenêtre 90 jours **révolus**, borne incluse : candidat
  `last_seen_at` = now-90j ⇒ **rattaché** (`.days == 90 <= 90`).
- **AC13** — Fenêtre 90 jours, borne exclue : candidat `last_seen_at` = now-91j ⇒
  **non rattaché** (nouvelle lignée, `lineage_id == nouvel id`).
- **AC14** — Surface ±2 % incluse : candidat `surface_m2 = 100.0`, nouveau bien
  `surface_m2 = 102.0` (2,00 %) ⇒ **rattaché**.
- **AC15** — Surface ±2 % exclue : candidat `surface_m2 = 100.0`, nouveau bien
  `surface_m2 = 102.01` (>2,00 %) ⇒ **non rattaché**.
- **AC16** — Aucune contrainte de prix : un candidat éligible avec un prix
  **fortement différent** (ex. -20 %) est tout de même **rattaché** (le prix n'entre
  pas dans la clé).

### Rattachement — règle customer_id PAR-SOURCE
- **AC17** — bienici, `customer_id` égal requis : candidat et nouveau bien
  `source="bienici"`, même `reference`+attributs, **`customer_id` égal** ⇒ rattaché.
- **AC18** — bienici, `customer_id` divergent ⇒ **non rattaché** (nouvelle lignée),
  même si `reference`+attributs collent.
- **AC19** — bienici, `customer_id` absent (l'un OU l'autre `None`) ⇒ **non
  rattaché** (collision `reference` triviale sans `customerId` ⇒ pas de lien).
- **AC20** — Source mono-agence HTML (ex. `source="benedic"`), `customer_id` absent
  des deux côtés, même `reference`+`source`+`property_type`+`city`+surface ±2 % ⇒
  **rattaché** (`customer_id` non requis pour une source mono-agence).

### Rattachement — politique de doute
- **AC21** — `reference` absente/vide sur le nouveau bien ⇒ **aucune recherche**,
  nouvelle lignée (`lineage_id == nouvel id`), même si un candidat plausible existe
  par attributs.
- **AC22** — Multi-candidats ⇒ abstention : 2 comparables disparus distincts
  satisfaisant tous les prédicats (même `reference`+`customer_id`+attributs, fenêtre
  OK) ⇒ le nouveau bien crée une **nouvelle lignée** (`lineage_id == nouvel id`),
  n'est rattaché à aucun.
- **AC23** — `source` divergente ⇒ non rattaché : candidat `source="benedic"`,
  nouveau bien `source="bienici"`, mêmes `reference`/attributs ⇒ nouvelle lignée
  (2a est intra-source).
- **AC24** — `property_type` divergent ⇒ non rattaché (candidat `maison`, nouveau
  `appartement`, reste égal) ⇒ nouvelle lignée.

### Lecture `/history` sur lignée
- **AC25** — Agrégation : une lignée de 2 membres (member A : snapshots à T0/T1 ;
  member B rattaché : snapshot à T2 prix différent) interrogée via `/history/{B}`
  renvoie 200 avec `snapshots` = 3 entrées **ordonnées par `observed_at` croissant**,
  `first_seen_at` = MIN (T0), `last_seen_at` = MAX, `price_first` = prix de T0,
  `price_last` = prix de T2, `price_change_pct` cohérent (signe correct).
- **AC26** — Interrogeable par n'importe quel id membre : `/history/{A}` et
  `/history/{B}` de la même lignée renvoient la **même** série fusionnée et les mêmes
  `first_seen_at`/`last_seen_at`.
- **AC27** — Confidentialité : la réponse `/history` ne contient **aucune** clé
  `reference`, `customer_id`, `lineage_id`, ni `address/url/text/title/description/
  photos/city/district`. L'ensemble des clés ⊆ `{listing_id, source, first_seen_at,
  last_seen_at, weeks_on_market, price_first, price_last, price_change_pct,
  snapshots}` ; chaque snapshot ⊆ `{price_total, price_m2, observed_at}`. Vérifié sur
  le dict construit par la fonction (pas seulement via response_model).
- **AC28** — `/history` sans `X-Admin-Token` (ou token erroné) ⇒ **401** (contrat
  inchangé) ; id inconnu ⇒ **404**.

### Rétention sur lignée
- **AC29** — Lignée vivante non purgée : lignée à 2 membres, member ancien
  `last_seen_at` = now-731j, member récent `last_seen_at` = now-10j ; maintenance
  `dry_run=false` ⇒ AUCUN des deux membres n'est purgé par rétention (la lignée est
  vivante), leurs snapshots subsistent.
- **AC30** — Lignée entièrement expirée purgée : lignée à 2 membres, tous deux
  `last_seen_at` > 730j (MAX = now-731j) ; maintenance `dry_run=false` ⇒ les deux
  membres sont purgés par rétention, `purged_retention` les compte, leurs snapshots
  supprimés (`purged_snapshots`).
- **AC31** — Borne 730j sur la lignée, incluse : lignée mono-membre
  `last_seen_at` = now-730j ⇒ **conservée** (`.days == 730`, pas > 730).
- **AC32** — `dry_run=true` (défaut) sur une lignée expirée : `purged_retention` peut
  être > 0 dans le compteur mais `total_after` et le contenu réel sont **inchangés**
  (rien supprimé).
- **AC33** — Cascade par membre : la purge d'un membre n'emporte que SES propres
  snapshots (pas ceux d'un autre membre de la même lignée encore vivant). Sur une
  lignée vivante (AC29), aucun snapshot n'est supprimé.

### Idempotence / non-régression
- **AC34** — Idempotence du rattachement : rejouer **deux fois** le même
  `save_comparables([ad_new])` (re-list) ne crée qu'**une** lignée rattachée et ne
  duplique pas le snapshot (le 2e passage emprunte la branche `existing is not None`).
- **AC35** — Idempotence batch : rejouer le même lot complet ne crée ni lignée
  supplémentaire ni snapshot supplémentaire (compte de comparables et de snapshots
  stable après 2e run).
- **AC36** — Non-régression inc.1 (capture sans lignée) : tous les AC inc.1 figés
  (`first_seen` immuable, `last_seen` rafraîchi, snapshot delta à l'égalité exacte
  `price_total`, garde-fous prix/zone) restent verts ; un id ré-observé sans candidat
  conserve `lineage_id == son id` et son `first_seen_at` d'origine.
- **AC37** — Contrat `/analyze` INCHANGÉ : `AnalyzeResponse` ne gagne aucune clé ; un
  appel `/analyze` renvoie le même jeu de clés (`global_score, verdict, confidence,
  pillars, actions, local_context`). Aucune modif de `frontend/lib/api.ts`.
- **AC38** — Score 40/30/30 et sélection `market_stats` INCHANGÉS : un smoke de
  scoring/marché existant reste vert ; aucune lignée n'entre dans la sélection des
  comparables (pas de dédoublonnage). (Réutiliser un test smoke marché/score
  existant.)
- **AC39** — `POST /admin/comparables` conserve son contrat
  (`{received, saved, total_in_db}`) et accepte désormais `reference`/`customer_id`
  optionnels sans 422 quand absents.
- **AC40** — Id dupliqué intra-batch : 2a ne change PAS le comportement inc.1 sur ce
  cas (pas de `db.add` supplémentaire introduit par la recherche de candidat). Test
  de garde reprenant le scénario inc.1 (`INCREMENT1-SPEC.md` §8) reste cohérent.

### Migration idempotente / isolation
- **AC41** — La micro-migration est idempotente sur une base SIMULANT le stock prod
  (table `comparables` préexistante sans les 3 colonnes) : un `init_db()` ajoute les
  colonnes + l'index ; un 2e `init_db()` ne lève pas et ne re-crée rien.
- **AC42** — Isolation : les nouvelles écritures (lignées, `reference`,
  `customer_id`) s'appuient sur le reset autouse `comparables`/snapshots existant en
  `conftest.py` ; un test statique vérifie qu'aucun NOUVEL état mémoire de module
  n'est introduit par 2a (pas de cache à reset au-delà de l'existant).

---

## 6. Note doctrine (Q6=a)

`reference` (référence de mandat) et `customer_id` (compte annonceur bienici) sont
des **identifiants techniques d'agence/mandat**, pas des données personnelles d'un
vendeur particulier. Ils sont **internes** : stockés pour relier les annonces
successives d'un même bien (suivi longitudinal du prix), **jamais redistribués ni
exposés** dans une réponse API (§4.1 AC27). Cet usage est conforme à l'esprit de
`CONTEXT.md` §11.3 amendé (« stockage interne par-annonce autorisé ; redistribution
du contenu interdite »). Aucun amendement documentaire n'est **bloquant** pour 2a.

Recommandation **non bloquante** : ajouter une ligne à `CONTEXT.md` §11.3 et/ou
`backend/CLAUDE.md` §7 mentionnant explicitement `reference`/`customer_id`/
`lineage_id` comme métadonnées techniques internes non re-publiables, afin qu'un
agent futur (ou un reviewer) ne re-détecte pas une fausse violation RGPD/
redistribution sur ces colonnes.

---

## 7. Risques résiduels assumés

1. **Gisement non mesuré (taux de re-list)** : PREREQ0 §0/§3.4 — le taux de
   réapparition n'est pas encore calibré (inc.1 n'a que quelques jours d'historique
   au 2026-06-13). **Assumé sans danger** : le rattachement conservateur (§3) ne
   produit JAMAIS de faux lien ; en l'absence de re-list capté, 2a se comporte
   exactement comme l'inc.1 (chaque bien = sa propre lignée). Les valeurs W=90j et
   surface ±2 % sont des bornes prudentes, recalibrables plus tard sur une probe sans
   réécrire l'historique (les lignées passées restent valides).
2. **`reference`/`customer_id` NULL pour le stock prod existant** : les ~17,7k lignes
   héritées n'auront `reference`/`customer_id`/`lineage_id` qu'au 1er passage de
   collecte post-déploiement. Avant cela, repli `lineage_id or id` en lecture. Le
   re-link n'est effectif que sur les biens collectés post-merge. Documenté, non
   bloquant (on ne peut pas reconstruire un passé non capté).
3. **HTML agences best-effort** : `reference` peut rester `None` pour les 4 agences
   si les sélecteurs ne trouvent rien ⇒ ces biens ne sont jamais rattachés (nouvelle
   lignée). Dégradé gracieux identique à inc.1, jamais d'échec de collecte (§2.3).
4. **Référence réutilisée par l'agence pour un autre bien** dans la fenêtre 90j :
   atténué par la corroboration d'attributs (±2 % surface, type, ville) et, sur
   bienici, par `customer_id`. Cas résiduel ⇒ multi-candidats ⇒ abstention (§3.4).
5. **Id dupliqué intra-batch** (préexistant inc.1, `INCREMENT1-SPEC.md` §8) : 2a ne
   l'aggrave pas (`_find_lineage_candidate` est lecture seule). À durcir
   ultérieurement par déduplication du batch si une source émet des doublons.
6. **Fusion d'un faux doublon de la même agence** (même `reference`+`customer_id`+
   attributs, deux biens réellement distincts) : coût faible (même mandat), et ≥ 2
   candidats déclenchent l'abstention. Asymétrie de coût assumée en faveur du
   conservatisme (un raté < un faux lien).

---

SPEC prête pour GATE 2 (approbation humaine).

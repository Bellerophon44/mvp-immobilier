# cross-agence — INCRÉMENT 2a (re-link « sans photo ») — ANALYSE (GATE 1)

> Rôle : ANALYSTE. Cadre, challenge et chiffre l'incrément 2a ; ne tranche aucun
> arbitrage structurant (remontés en fin de document, GATE 1). Lecture du code au
> 2026-06-13. Environnement d'analyse SANS egress réseau : toute mesure exigeant
> une requête vers bienici est marquée [À VÉRIFIER] avec son protocole.
> Réfs lues : `.claude/lessons.md`, `CONTEXT.md` §0/§11, `backend/CLAUDE.md`
> §1/§2/§4/§5/§9/§12, `cross-agence-ANALYSE.md`, `cross-agence-INCREMENT1-SPEC.md`,
> `cross-agence-PREREQ0-RESULTATS.md`.

---

## 1. Objectif et périmètre

### 1.1 Reformulation
Suivre l'évolution du prix d'un **même bien physique** dans le temps. À l'instant
T, un bien n'est jamais que chez **une** agence ; le suivi longitudinal est
rompu quand le bien est **re-publié** (nouvelle annonce → nouvel `id` stable).
L'incrément 1 (en prod) suit par `id` stable PAR ANNONCE (`generate_stable_id`,
`scrapers/base.py:228` côté bienici) : au re-list, le bien reçoit un nouvel `id`,
l'inc.1 le voit comme neuf, pose `first_seen_at = now` et démarre un nouvel
historique de snapshots. La trajectoire de prix est cassée à la jointure.

2a doit **re-lier les annonces successives du même bien** (cas re-publication par
la **même** agence) pour prolonger `first_seen_at` et l'historique
`listing_price_snapshots` par-dessus la rupture d'`id`, en s'appuyant sur la
`reference` de mandat (+ corroboration) capturée à la collecte.

### 1.2 In (périmètre proposé, à confirmer GATE 1)
- **Capture** de `reference` (+ `customerId`) côté **bienici** (`_parse_listing`,
  `scrapers/sources/bienici.py:190`), propagée dans `PropertyListing`
  (`scrapers/models.py`), `to_dict()`, `_is_valid` (`jobs/push_comparables.py`),
  `ImportItem` (`app/main.py`) et la persistance (`ingestion/save.py`).
- **Schéma** : colonnes nouvelles sur `comparables` (micro-migration idempotente,
  pattern `db/session.py:35-63`) + un porteur de la « lignée de bien » (option à
  arbitrer, §3).
- **Logique de rattachement** à l'ingestion (`ingestion/save.py`) : à l'arrivée
  d'un `id` neuf, chercher un bien **récemment disparu** de même `reference`
  (+ corroboration) et rattacher à la même lignée, en **prolongeant**
  `first_seen_at` et l'historique de prix.
- **Lecture** : `/admin/comparables/{id}/history` (`app/main.py:218`) doit suivre
  la lignée (cf. §3.3).
- **Rétention** : la borne 24 mois (`app/main.py:391-399`) doit raisonner sur le
  `last_seen_at` de la **lignée**, pas de l'annonce isolée (cf. §3.4).

### 1.3 Out (explicitement 2b ou hors chantier)
- **Changement d'agence** (delisté de A → relisté par B) : `reference` ET
  `customerId` changent → seules les **photos (pHash)** relient. C'est
  l'**incrément 2b** (`PREREQ0-RESULTATS.md` §0, §3.3). Hors scope 2a.
- **Aucune** image, **aucun** hash photo, **aucune** dépendance Python nouvelle.
- **Aucune** exposition publique (`/analyze`, `AnalyzeResponse`,
  `frontend/lib/api.ts` non touchés) — comme l'inc.1.
- **Aucun** dédoublonnage des comparables dans `market_stats` : la sélection de
  comparables et le score 40/30/30 restent **inchangés** (cf. §4.6).
- **Signal « même bien, deux agences au même instant »** : hors scope (tombera de
  2b, `PREREQ0` §3.5).

### 1.4 Challenge du requirement (posture adversariale)
1. **Le gisement RÉEL de 2a n'est pas encore mesuré.** `PREREQ0` §0 et §3.4 sont
   explicites : le prérequis #0 a mesuré la **faisabilité** (`reference` rempli
   à 99,9 %, `customerId` ~59 %) sur un **snapshot unique**, mais **pas le taux de
   re-list**, qui est par nature temporel (disparition → réapparition). L'inc.1
   est en prod depuis le 2026-06-11 : il **commence tout juste** à accumuler
   `first_seen`/`last_seen` + snapshots. À ce jour (2026-06-13), **~2 jours**
   d'historique — soit 0 passage hebdo complet (collecte lundi 04:00). **On ne
   sait donc pas combien de biens sont effectivement re-listés**, ni quelle part
   est captable par `reference`. Construire la mécanique de rattachement avant
   d'avoir cette mesure, c'est risquer d'outiller un phénomène marginal.
   → **Question GATE 1 n°1 : séquencer une probe « taux de réapparition » avant
   le code 2a**, comme `PREREQ0` §3.4 le recommande explicitement.
2. **Découpler la CAPTURE de la LOGIQUE.** Capturer `reference`/`customerId` dès
   maintenant (colonnes nullables, 0 risque, 0 dépendance) est **rentable
   immédiatement** : ça alimente la probe du point 1 et c'est un prérequis de
   toute version de 2a et de 2b. La **logique de rattachement** (la partie
   risquée : faux liens) peut être livrée **après** la probe. Cette césure réduit
   le risque sans rien perdre.
3. **Sur-dimensionnement possible pour un MVP < 1 €/mois.** La valeur produit de
   2a est « depuis quand ce bien est en vente / a-t-il déjà baissé sous un autre
   mandat de la même agence » — et **rien n'est encore exposé** (`/analyze`
   intact depuis l'inc.1). Tant que l'exposition n'est pas décidée, 2a enrichit un
   historique **admin-only**. C'est défendable (prépare le terrain, coût quasi
   nul) mais il faut l'assumer : **2a ne produit aucune valeur utilisateur
   visible** tant que l'exposition (un futur incrément) n'est pas faite.
4. **Le risque dominant est le FAUX LIEN.** `PREREQ0` §2bis + §3 le documentent :
   `reference` courtes/non uniques (`67`, `1416179`) → collisions ; rattacher sur
   `reference` SEULE est dangereux. Un faux rattachement **fusionne deux biens
   distincts** → historique de prix corrompu (sauts aberrants), à l'opposé du
   positionnement « pas de fausse précision ». La politique doit être
   **conservatrice par construction** : dans le doute, NE PAS rattacher (créer une
   nouvelle lignée), jamais de faux lien — symétrique de la doctrine pHash de
   l'inc.2 (`cross-agence-ANALYSE.md` §5.2).

---

## 2. Cartographie d'impact (fichier:ligne)

### 2.1 Fonctionnement actuel (état réel vérifié)

**`ingestion/save.py` (upsert, first_seen immuable, snapshot delta)** — le point
névralgique de 2a.
- `save.py:46` `init_db()` ; `save.py:48` ouverture `SessionLocal()`.
- `save.py:53-75` garde-fous AVANT toute écriture : surface/prix > 0, bande
  prix/m² `[800-12000]` (`MIN_PRICE_M2`/`MAX_PRICE_M2`, `save.py:15-16`),
  `OUT_OF_SCOPE_CITIES` (`save.py:21-26`), `IN_SCOPE_DEPARTMENT="57"`
  (`save.py:32`). Une annonce rejetée ne crée NI comparable NI snapshot.
- `save.py:82` **lecture explicite** de la ligne existante
  `existing = db.get(Comparable, ad["id"])` (remplace l'ancien `db.merge`
  destructeur).
- `save.py:84-95` : si `existing is None` → `first_seen = now`,
  `write_snapshot = True` ; sinon `first_seen = existing.first_seen_at or
  existing.collected_at or now` (immuable, repli héritage),
  `write_snapshot = (existing.price_total != price)` (égalité **exacte**).
- `save.py:97-120` champs upsertés (`first_seen_at`, `last_seen_at`,
  `collected_at`) ; `save.py:122-126` add (neuf) ou setattr (existant).
- `save.py:128-134` snapshot conditionnel `ListingPriceSnapshot`.
- `save.py:142` **un seul `db.commit()` en fin** (comparable + snapshot de la même
  itération commités ensemble).
- **Point d'insertion 2a** : entre le garde-fou (`save.py:75`) et la branche
  `existing is None` (`save.py:84`). Quand `existing is None`, AVANT de poser
  `first_seen = now`, tenter un rattachement à une lignée existante (§3, §4).

**`db/models.py` (Comparable, ListingPriceSnapshot)**
- `Comparable` `models.py:8-58` : PK `id` (sha256), pas de FK. `first_seen_at`
  `models.py:57`, `last_seen_at` `models.py:58` (nullable, posés applicativement,
  jamais réécrits pour `first_seen_at`).
- `ListingPriceSnapshot` `models.py:61-76` : `id` PK auto, `listing_id` (indexé,
  = `comparables.id`, **pas de FK**), `price_total`, `price_m2`, `observed_at`.
  Cohérence applicative (commentaire `models.py:66-67`).
- **Ni `reference` ni `customerId` n'existent** dans le modèle (vérifié :
  `grep reference|customerId` ne matche que `diag_bienici.py` outil de diagnostic
  et `test_evals_harness.py`, jamais le code produit).

**Collecte hebdo (`collect.yml`, `jobs/push_comparables.py`)**
- `collect.yml` : `schedule cron "0 4 * * 1"` (lundi 04:00 UTC) +
  `workflow_dispatch` (CLAUDE §9). Timeout 15 min (`cross-agence-ANALYSE.md`
  §2.2). 2a n'ajoute pas de download → reste dans le timeout.
- `push_comparables.py:67-68` `load_all()` + `run_all()` ; `:73-74`
  `l.to_dict()` filtré par `_is_valid` (`:31-41`, exige `id/source/city/
  property_type` str non vides + surface/prix > 0) ; `:82-93` batches de 1000
  (`BATCH_SIZE`, `:24`) POST `/admin/comparables`, robuste aux batchs en échec
  (`:86-91`).
- **Ordre d'arrivée** : bienici est balayé par tranches de surface croissantes
  (`bienici.py:37-40`, `SURFACE_BUCKETS`), dédup intra-run par `id`
  (`bienici.py:254,272-273`). Les batchs arrivent donc dans un ordre **surface
  croissante**, pas chronologique de publication — sans incidence sur 2a (le
  rattachement lit la base, pas l'ordre du batch), SAUF le cas « id dupliqué
  intra-batch » déjà documenté (`INCREMENT1-SPEC.md` §8, autoflush=False).

**Endpoint maintenance / rétention (`app/main.py:320-448`)**
- `main.py:348` `maintenance_now = datetime.utcnow()`.
- `main.py:366-399` boucle de purge : band (`:367`), zone (`:374`), dept
  (`:384`), **rétention** (`:391-394` : `(maintenance_now - c.last_seen_at).days
  > 730`, NULL jamais purgé), renames (`:401-410`).
- `main.py:354-364` `_purge_snapshots_of` : cascade snapshots sur **toute** purge.
- `main.py:424-429` balayage final d'orphelins (`purged_orphan_snapshots`).
- `dry_run=true` par défaut (`main.py:316`).

**Endpoint `/history` (`app/main.py:218-283`)** — suit **un seul `listing_id`** :
`db.get(Comparable, listing_id)` (`:233`) + snapshots filtrés sur ce `listing_id`
(`:237-242`). `weeks_on_market`, `price_first/last`, `price_change_pct` dérivés des
snapshots de **ce seul id**. → à adapter pour suivre la lignée (§3.3).

### 2.2 Capture côté scraper bienici
- `bienici.py:190-241` `_parse_listing` lit `price`, `surfaceArea`,
  `propertyType`, `city`, `district`, `postalCode`, `dpe`, année, aménités —
  **mais ni `reference` ni `customerId`**. L'`id` API brut est `ad["id"]`
  (`bienici.py:228`), hashé par `generate_stable_id`.
- Pattern de capture nullable existant : `_extract_postal` (`:132-143`),
  `_extract_amenities` (`:174-187`) — gabarits directs pour `_extract_reference`
  / lecture de `customerId`. `reference` et `customerId` sont des **clés JSON
  directes** confirmées par `PREREQ0` §1/§2bis (remplissage 99,9 % / ~59 %).

### 2.3 Sources HTML agences (benedic, idemmo, immoheytienne, laveine_immo)
- Elles parsent des **cartes de listing**, pas de page détail
  (`cross-agence-ANALYSE.md` §2.1, §4.2). `reference`/`customerId` **ne sont pas
  garantis** dans le HTML des cartes (le « mandat » est rarement exposé en
  surface). `PREREQ0` est muet sur leur extraction côté HTML.
- **Découverte structurante** (`PREREQ0` §2, §2bis) : bienici **syndique nos
  propres agences** (ex. `cabinet-benedic-montigny-groupe-benedic` est un
  `customerId` bienici = notre scraper benedic). Beaucoup de biens d'agences sont
  donc **déjà présents dans bienici** avec leur `reference`. Implication : capter
  la `reference` **côté bienici seul** couvre probablement déjà une large part du
  parc agences, ce qui affaiblit la nécessité d'extraire la `reference` du HTML
  des petites agences pour 2a. → arg. pour **limiter 2a à bienici** (Question 4).

### 2.4 DB / migration / volume
- Micro-migration : `db/session.py:35-50` (`_ADD_COLUMNS`) + `_migrate_comparables`
  (`:53-57`, `PRAGMA table_info` + `ALTER TABLE ADD COLUMN`). Ajouter `reference`,
  `customer_id` (+ porteur de lignée selon §3) = quelques entrées.
- Volume : négligeable. Deux colonnes texte courtes × ~17,7k lignes ≈ < 1 Mo.
  Aucune nouvelle table de masse (sauf option 3.2b). Confortable sur 1 Go.

### 2.5 CI / non-régression
- `test.yml` (suite gratuite `backend/tests/`) doit rester verte (257 tests à
  l'inc.1, `INCREMENT1-SPEC.md` en-tête). Les tests inc.1
  (`test_cross_agence_increment1.py`, `test_cross_agence_history.py`) figent le
  comportement à **ne pas casser** : `first_seen` immuable, snapshot delta,
  rétention 730j, cascade orphelins.
- Pas de touche `/analyze` → pas d'impact `evals.yml`.

### 2.6 Ce que 2a NE touche pas
`/analyze`, `AnalyzeResponse`, `frontend/lib/api.ts`, `market_stats.py`,
`scoring.py`, `llm_semantic.py` : aucun. Même garantie que l'inc.1.

---

## 3. Modèle de « lignée de bien » — challenge des options

Le besoin : un identifiant stable QUI SURVIT au changement d'`id` d'annonce, sur
lequel `/history` et la rétention raisonnent. Trois options.

### 3.1 Option (a) — colonne `lineage_id` sur `comparables`
Chaque comparable porte un `lineage_id` (String, indexé). À la 1re observation
d'un `id` neuf, soit on trouve une lignée à rattacher → on reprend son
`lineage_id`, soit on en crée une (par défaut `lineage_id = id`, la lignée
démarre sur elle-même).
- **+** Minimal : une colonne + un index, micro-migration triviale
  (`db/session.py`). Rétro-compatible : les ~17,7k lignes héritées peuvent
  recevoir `lineage_id = id` au 1er passage (repli `lineage_id or id` en lecture,
  comme `first_seen_at or collected_at`). `/history` agrège sur `lineage_id`.
- **−** Re-lier deux lignées **déjà constituées** (A↔B observées séparément avant
  qu'on découvre le lien) impose un UPDATE de masse sur tous les membres d'une
  lignée. En pratique rare (le rattachement se fait à l'arrivée du nouvel id,
  avant qu'il ait sa propre lignée) ; gérable par « toujours adopter le
  `lineage_id` le plus ancien ».
- **Reste à trancher** : `first_seen_at` de la lignée. Deux sous-options :
  (i) propager `first_seen_at` du membre le plus ancien sur le nouveau membre
  (dénormalisé, simple en lecture) ; (ii) le recalculer en lecture par `MIN`. Reco
  (i) cohérent avec l'inc.1 (first_seen porté par la ligne).

### 3.2 Option (b) — table de mapping `lineage(lineage_id, listing_id, ...)`
Une table dédiée associant des `listing_id` à une lignée.
- **+** Normalisé ; trace l'historique des rattachements (qui a été lié à quoi,
  quand), auditável.
- **−** Sur-dimensionné pour le MVP : une jointure de plus à chaque `/history` et
  à la rétention, une table de plus à cascader (leçon inc.1 :
  `.claude/lessons.md` 2026-06-11 « nouvelle table dépendante : ré-auditer TOUS
  les chemins de suppression » — chaque purge devrait cascader cette table aussi).
  Plus de surface de bug pour une valeur d'audit faible au stade actuel.

### 3.3 Option (c) — re-pointer les snapshots (`listing_id` réécrit)
À la détection d'un re-list, **réécrire** le `listing_id` des snapshots de
l'ancien id vers le nouveau (ou vers un id de lignée).
- **−− À proscrire.** Viole frontalement la leçon inc.1 « ré-écriture
  d'historique » (`.claude/lessons.md` 2026-06-11, et `cross-agence-ANALYSE.md`
  §1.3 constat 1 : « le code actuel DÉTRUIT l'historique »). Un faux lien
  détecté plus tard serait **irréversible** (les snapshots ont perdu leur
  `listing_id` d'origine). Destructif et non auditável. Rejeté.

### 3.4 Impact sur `/history` et la rétention (commun aux options retenues)
- **`/history`** (`main.py:218-283`) : aujourd'hui filtre sur un seul
  `listing_id`. Avec une lignée, il doit agréger les snapshots de **tous les
  membres** de la lignée (ordonnés par `observed_at`), recalculer `first_seen_at`
  = MIN des membres, `last_seen_at` = MAX, `price_first/last` sur la série
  fusionnée. **Sous-question** : interroge-t-on `/history/{id}` avec n'importe
  quel id membre (il résout la lignée) ou expose-t-on un id de lignée ? Reco :
  n'importe quel id membre résout la lignée (continuité d'usage admin, pas de
  nouvel identifiant à connaître).
- **Rétention** (`main.py:391-399`) : la borne 730j doit raisonner sur le
  `last_seen_at` **de la lignée** (MAX des membres), sinon un ancien membre
  re-listé (donc le bien est toujours actif) verrait son segment purgé et ses
  snapshots perdus alors que la lignée est vivante. **Conséquence sur la cascade**
  (leçon inc.1 « ré-auditer TOUS les chemins de suppression ») : purger un membre
  ne doit pas casser la lignée des autres ; et le `_purge_snapshots_of`
  (`main.py:354-364`) doit rester cohérent avec le regroupement par lignée. Point
  de vigilance fort — toute nouvelle structure de lignée **multiplie les chemins**
  à auditer (cf. `.claude/lessons.md`).

### 3.5 Recommandation analyste
**Option (a) `lineage_id` sur `comparables`**, sous-option first_seen propagé (i).
Minimaliste, cohérent avec la culture du projet (colonnes nullables +
micro-migration, comme inc.1/chantiers B/C), rétro-compatible, et la rétention/
`/history` s'adaptent sans nouvelle table à cascader. (b) reste l'option si un
besoin d'audit fort des rattachements émerge plus tard. (c) rejeté.

---

## 4. Détection du re-list — règle de rattachement

### 4.1 « Récemment disparu » — la fenêtre temporelle
La collecte est **hebdo** (lundi 04:00). Un bien re-listé par la même agence peut
réapparaître :
- **le même lundi** que sa disparition (l'agence a republié dans la semaine, les
  deux annonces ne coexistent pas dans le même run) ;
- **un ou plusieurs lundis plus tard** (republication différée).

Le marqueur de « disparu » est `last_seen_at` qui **cesse d'être rafraîchi** : un
bien vu au run N puis absent au run N+1 garde `last_seen_at = date(N)`. À l'arrivée
d'un `id` neuf au run M, un candidat « récemment disparu » est un comparable de
même `reference` dont `last_seen_at < (run courant)` d'au moins un cycle ET de pas
plus de **W jours**.
- **Trop court (W = 1 semaine)** : rate les republications différées (vacance de
  quelques semaines entre deux mandats, fréquent).
- **Trop long (W = 6-12 mois)** : augmente le risque de **réutilisation de
  `reference`** par l'agence pour un AUTRE bien (collision temporelle).
- **Reco : W = 90 jours** (≈ 12 semaines), borné, conservateur. À calibrer sur la
  probe temporelle (§1.4 point 1) quand l'historique aura mûri. Borne exprimée en
  **jours révolus** (`(now - last_seen_at).days > W`), pas à la seconde (leçon
  inc.1 « borne temporelle littérale intestable », `.claude/lessons.md`
  2026-06-11).
- **Cas « même run »** (bien re-listé ET ancienne annonce encore présente le même
  lundi) : ce n'est PAS un re-list au sens 2a, c'est un **doublon simultané**
  (deux annonces vivantes du même bien) — cas marginal, à NE PAS rattacher en 2a
  (risque de fusionner deux annonces réellement distinctes) ; relève du signal
  « même bien deux mandats », hors scope (§1.3).

### 4.2 La clé et la corroboration (anti-faux-lien)
`PREREQ0` §3 est impératif : `reference` SEULE est dangereuse (collisions `67`,
`1416179`). Prédicats cumulés proposés (TOUS requis pour rattacher) :
1. **`reference` égale** (non vide, et idéalement « non triviale » — voir §4.3).
2. **`customerId` égal** (même compte annonceur = même agence). Dispo à ~59 %
   (`PREREQ0`). **Quand `customerId` est absent d'un des deux côtés** → exiger une
   corroboration d'attributs **renforcée** (point 4), ou ne pas rattacher (reco
   conservatrice).
3. **`source` égale** (`bienici` = `bienici`) : 2a est intra-source par
   construction (cas même-agence). Le cross-source est 2b.
4. **Attributs cohérents** : même `property_type`, même `city` canonique,
   `surface_m2` à **±2 %** (re-publication = même bien, la surface ne change pas ;
   `PREREQ0` §2bis cite les paires « strictes » à ±2 %). Idéalement même
   `postal_code` quand connu. **Pas** de contrainte de prix (l'écart de prix est
   précisément le signal qu'on veut capturer).
5. **Garde temporel** : candidat disparu depuis ≤ W jours (§4.1).

### 4.3 Référence « triviale » (garde-fou collision)
`PREREQ0` cite des `reference` courtes/numériques (`67`, `1416179`) à fort risque
de collision. Deux parades possibles (à arbitrer) :
- (a) **Exiger `customerId`** présent ET égal dès que `reference` est « courte »
  (heuristique : longueur < seuil, ou purement numérique courte). Sans
  `customerId`, ne pas rattacher.
- (b) **Toujours exiger `customerId` + attributs** (politique uniforme, plus
  simple à spécifier et tester, plus conservatrice). Reco **(b)** : une règle
  unique est plus testable (leçon : un garde-fou doit être verrouillé par un test ;
  une heuristique « courte » ajoute une borne floue à tester).

### 4.4 Politique en cas de doute
**Ne pas rattacher = créer une nouvelle lignée** (`lineage_id = id`). Jamais de
faux lien. Symétrique de la doctrine pHash (`cross-agence-ANALYSE.md` §5.2 :
« un faux ‘même bien' est pire qu'un raté »). Un raté = on perd la continuité de
prix d'un bien re-listé (dégradé gracieux : c'est l'état actuel inc.1). Un faux
lien = historique corrompu (sauts de prix aberrants entre deux biens distincts).
**Asymétrie de coût claire → conservatisme.**

### 4.5 Ambiguïté : plusieurs candidats
Si plusieurs comparables disparus matchent la clé (ex. une agence a 3 biens de
même `reference` triviale réutilisée), **ne pas rattacher** (ambiguïté =
nouvelle lignée). Un test de verrou doit figer « N candidats > 1 ⇒ pas de
rattachement ».

### 4.6 Non-impact sur `market_stats` / score
Les lignées **n'entrent jamais** dans `market_stats` : aucun dédoublonnage des
comparables, médianes/quartiles inchangés, score 40/30/30 intact (même garantie
qu'inc.1, `INCREMENT1-SPEC.md` §1.3). Une lignée est un regroupement **d'historique
admin**, pas un filtre de sélection. À verrouiller par un test de non-régression
du pilier prix (réutiliser un smoke existant).

---

## 5. Risques / anti-patterns

1. **Ré-écriture d'historique** (leçon inc.1, `.claude/lessons.md` 2026-06-11) :
   2a doit PROLONGER, jamais réécrire/écraser. `first_seen_at` immuable par
   membre ; les snapshots existants ne sont **jamais** modifiés ni re-pointés
   (option 3.3 rejetée). Un rattachement = pose d'un `lineage_id` + (éventuel)
   report de `first_seen_at` sur le NOUVEAU membre uniquement.
2. **Collisions `reference`** (`PREREQ0` §3) : traité par §4.2-4.5 (corroboration
   obligatoire, conservatisme, ambiguïté → pas de lien).
3. **Ordre d'ingestion / batchs de 1000** (`push_comparables.py:82`,
   `INCREMENT1-SPEC.md` §8) : le rattachement lit la base (`db.get`/`query`), pas
   l'ordre du batch — robuste à l'ordre. Vigilance sur le cas « id dupliqué
   intra-batch » (autoflush=False, déjà documenté inc.1) : 2a n'aggrave pas mais
   ne doit pas l'aggraver non plus (ne pas ajouter d'`add` pendant non flushé qui
   créerait une nouvelle collision).
4. **Idempotence (re-run de collecte)** : rejouer le même run ne doit pas
   re-créer de lignée ni dupliquer de rattachement. Le rattachement ne se déclenche
   qu'à `existing is None` (1re observation d'un id) ; un id déjà rattaché a déjà
   son `lineage_id` et ne re-passe pas par la détection. À verrouiller par un test
   « re-run idempotent ».
5. **Non-régression inc.1 + score 40/30/30** : toute la suite inc.1
   (`test_cross_agence_increment1.py`, `test_cross_agence_history.py`) doit rester
   verte ; `/analyze` inchangé. Risque concret : modifier `save.py` dans la branche
   `existing is None` peut casser la pose de `first_seen`/snapshot initial si mal
   séquencé. Tests de bornes inc.1 (first_seen immuable, snapshot delta) sont le
   filet.
6. **Isolation des tests (état SQLite partagé)** (leçons 9.7/9.9/inc.1) : les
   nouvelles colonnes/lignées s'écrivent dans la base jetable déjà isolée
   (`conftest.py`, `DATABASE_PATH` suffixe pid). Si une table de mapping est
   retenue (option 3.2b), prévoir un **reset autouse en `conftest.py`** (jamais
   local), comme `_reset_*` existants. Avec l'option `lineage_id` (3.1), pas de
   nouvelle table → réutilise le reset `comparables`/snapshots existant.
7. **RGPD / redistribution** : aucune donnée perso nouvelle. `reference` =
   référence de mandat (métadonnée commerciale, pas une personne) ; `customerId` =
   identifiant **technique** de compte annonceur (une **agence**, pas un
   particulier vendeur). Ils restent **internes** (jamais exposés dans `/history`
   ni `/analyze` — cf. `INCREMENT1-SPEC.md` §4.2 : la réponse `/history` n'expose
   que source/dates/prix). **À acter** : `reference`/`customerId` ne doivent PAS
   apparaître dans une réponse API (Question 5). Pas de nouveau vendor, pas de
   coût, pas d'estimation de prix.
8. **Rupture de contrat API** : aucune (`/analyze`, `AnalyzeResponse`,
   `frontend/lib/api.ts` non touchés). `/history` change son **contenu** (lignée)
   mais c'est un endpoint **admin** non contractuel côté front — à confirmer qu'il
   n'a pas de consommateur figé (revue : seul usage = consultation manuelle/
   staging, `CLAUDE.md` §5).

---

## 6. OPTIONS chiffrées (choix structurants)

### Option I — Séquençage : capture maintenant, logique après probe
| | Capture seule d'abord (reco) | Tout 2a d'un bloc |
|---|---|---|
| Risque faux lien | Nul (pas de logique) | Présent dès J1 |
| Mesure du gisement | **Alimentée** (probe sur reference réelle) | Aveugle |
| Valeur livrée immédiate | Données pour décider | Mécanique non mesurée |
| Effort | ~½ (2 colonnes + parse bienici) | Complet |
| Réversibilité | Totale (colonnes nullables) | Faible (logique en prod) |

**Reco : capture d'abord** (colonnes + parse bienici, 0 risque), **probe taux de
re-list**, PUIS logique de rattachement calibrée. Coût quasi nul, dérisque le pari.

### Option II — Modèle de lignée
Voir §3 : **(a) `lineage_id`** recommandé (minimal, rétro-compatible, pas de
nouvelle table à cascader) vs (b) table de mapping (audit, sur-dimensionné) vs
(c) re-pointage (rejeté, destructif).

### Option III — Périmètre sources
| | bienici seul (reco) | bienici + agences HTML |
|---|---|---|
| Fiabilité `reference`/`customerId` | 99,9 % / ~59 % (mesuré) | Inconnue côté HTML cartes |
| Couverture agences | Large (bienici **syndique** nos agences, `PREREQ0` §2bis) | Marginalement + |
| Effort | 1 source à instrumenter | 4 sources HTML, extraction incertaine |
| Risque | Faible | Parsing fragile, best-effort |

**Reco : bienici seul pour 2a.** La syndication (`PREREQ0` §2bis) fait que capter
la `reference` côté bienici couvre déjà l'essentiel du parc agences. Les colonnes
restent **nullables** : les sources HTML écrivent `None` sans casser, extension
ultérieure possible.

---

## 7. Frontière nette 2a vs 2b

| Aspect | 2a (ce chantier) | 2b (reporté) |
|---|---|---|
| Cas couvert | Re-publication **même agence** (nouvel id, même mandat) | **Changement d'agence** (delisté A → relisté B) |
| Clé de re-link | `reference` + `customerId` + attributs (sans photo) | **pHash photos** (reference/customerId changent) |
| Dépendances Python | Aucune | Pillow / imagehash (`cross-agence-ANALYSE.md` §2.6, Q6) |
| Job collecte | Inchangé (pas de download) | Job dédié download images (`ANALYSE` §6.1, §8) |
| Coût | Quasi nul | Bootstrap ~3 h CI + ~10-20 min/sem (`ANALYSE` §6.1) |
| Calibration | Probe temporelle reference | Seuils Hamming en staging (`ANALYSE` §5.2) |
| Signal « 2 agences même instant » | Hors scope | Tombe gratuitement (`PREREQ0` §3.5) |

**Explicitement reporté à 2b** : tout matching photo, toute dépendance image, tout
cas cross-agence, le signal multi-mandat simultané, l'exposition `/analyze` du
cross-agence. 2a ne fait que **prolonger l'historique de prix intra-agence
sans image**, admin-only.

---

## QUESTIONS POUR L'HUMAIN (GATE 1)

**Q1 — Séquençage : mesurer le gisement avant d'outiller la logique ?**
`PREREQ0` §0/§3.4 souligne que le **taux de re-list** n'est pas mesuré (snapshot
unique) et que l'inc.1 n'a accumulé que ~2 jours d'historique au 2026-06-13.
- (a) **Livrer d'abord la CAPTURE seule** (`reference`/`customerId` en colonnes
  nullables + parse bienici, 0 risque, 0 dépendance), lancer une **probe « taux de
  réapparition »** quand quelques semaines d'historique seront en base, PUIS
  spécifier la logique de rattachement calibrée.
- (b) Spécifier capture + logique de rattachement **d'un bloc** maintenant.
- **Reco : (a).** Dérisque le faux lien et le sur-dimensionnement sans rien perdre
  (la capture est de toute façon un prérequis commun à 2a et 2b).

**Q2 — Modèle de lignée retenu.**
- (a) **Colonne `lineage_id` sur `comparables`** (+ index, micro-migration), pas
  de nouvelle table.
- (b) Table de mapping `lineage(...)` (audit des rattachements, mais +1 table à
  cascader sur **chaque** purge — leçon inc.1).
- (c) Re-pointer les snapshots (réécriture d'historique — **rejeté**, leçon inc.1).
- **Reco : (a)**, `first_seen_at` propagé sur le nouveau membre, repli
  `lineage_id or id` en lecture (rétro-compat héritage).

**Q3 — Règle de rattachement (clé + corroboration + fenêtre + conservatisme).**
- Clé proposée : **`reference` égale ET `customerId` égal ET `source` égale ET
  même `property_type`/`city` canonique ET `surface_m2` ±2 %**, candidat disparu
  depuis **≤ 90 jours** (W, jours révolus), **pas** de contrainte de prix.
- Politique de doute : **`customerId` absent / référence ambiguë / plusieurs
  candidats ⇒ NE PAS rattacher** (nouvelle lignée). Jamais de faux lien.
- Options : (a) valider ce cadre (valeurs W/±% calibrables sur la probe Q1) ;
  (b) plus permissif (`reference` seule si attributs collent, `customerId`
  optionnel) — **rappel** : `PREREQ0` §3 alerte sur les collisions de `reference`.
- **Reco : (a)**, conservateur, valeurs affinées par la probe.

**Q4 — Périmètre sources de 2a.**
- (a) **bienici seul** (seule source à `reference`/`customerId` fiables, et qui
  **syndique** nos agences — `PREREQ0` §2bis) ; colonnes nullables, sources HTML →
  `None`.
- (b) bienici + extraction best-effort de `reference` dans le HTML des agences.
- **Reco : (a)** pour ce premier pas ; (b) ultérieurement si la probe montre du
  re-list non capté côté bienici.

**Q5 — `/history`, rétention et confidentialité sur une lignée.**
- `/history` : agréger les snapshots de **tous les membres** de la lignée
  (`first_seen` = MIN, `last_seen` = MAX, série fusionnée), interrogeable par
  n'importe quel id membre.
- Rétention : la borne 730j raisonne sur le `last_seen_at` **de la lignée** (MAX),
  pas du membre isolé (sinon purge d'un bien encore vivant). Cascade snapshots à
  ré-auditer pour tous les chemins (leçon inc.1).
- Confidentialité : `reference`/`customerId` restent **internes**, JAMAIS exposés
  dans une réponse API (ni `/history` ni `/analyze`).
- Options : (a) valider ce comportement ; (b) `/history` reste par-id (lignée non
  suivie en lecture) — déconseillé (la valeur de 2a serait invisible même en
  admin).
- **Reco : (a).**

**Q6 — Doctrine / documentation.**
La capture de `reference`/`customerId` (identifiant technique d'agence + mandat,
pas de donnée perso de vendeur) entre-t-elle dans la doctrine §11.3 amendée
(« stockage interne par-annonce autorisé ; jamais de redistribution de contenu ») ?
- (a) Confirmer : ce sont des métadonnées internes non re-publiables, dans
  l'esprit §11.3 ; pas d'amendement documentaire nécessaire au-delà d'une note.
- (b) Exiger une mise à jour explicite de `CONTEXT.md` §11.3 / `CLAUDE.md` §7
  mentionnant ces deux champs.
- **Reco : (a)** avec une courte note dans la future SPEC, pour qu'un agent futur
  ne re-détecte pas une fausse violation.

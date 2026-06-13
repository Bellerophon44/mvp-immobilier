# bienici-couronne — SPEC — Élargir la collecte bien'ici à la couronne de Metz

Rôle de ce document : cahier des charges implémentable (SPEC-WRITER). Fondé sur
le code réel (`backend/scrapers/sources/bienici.py`, `backend/scrapers/base.py`,
`backend/app/market_stats.py`, `backend/ingestion/save.py`, les workflows
`.github/workflows/collect.yml` et `coverage-probe.yml`), sur l'analyse
`docs/specs/comparables-coverage-ANALYSE.md` (§1.2, §3.1, §6, §8) et sur les
arbitrages GATE 1 (§8.2 : « mesurer PUIS élargir bien'ici »), confirmés par la
probe prod (run 27473882571). La SPEC ne code pas la solution ; elle fige le
contrat que le développeur, le testeur et le reviewer utiliseront.

---

## 1. Objectif et périmètre

### Objectif

Faire collecter bien'ici sur **toutes les communes de `_METRO_CITIES`** (Metz +
couronne) au lieu de la seule commune de Metz, afin de densifier la base de
comparables sur la couronne (Marly, Montigny-lès-Metz, Saint-Julien-lès-Metz,
etc.), maisons incluses, là où elle est aujourd'hui quasi vide côté bien'ici.

### Constat de cadrage (probe prod, run 27473882571)

Base = 17 840 comparables, dont Metz 17 591 (bien'ici 17 492). Couronne quasi
vide côté bien'ici : Marly 13 (bien'ici 0, 10 maisons via agences), Montigny 13
(bien'ici 0), Saint-Julien 7 (bien'ici 1), Le-Ban-Saint-Martin 7 (bien'ici 5),
Longeville 4 (bien'ici 0), Scy-Chazelles 2, Lessy 2, Plappeville 2, Augny 0,
Woippy 0. Le marché existe (les agences trouvent 10 maisons à Marly) → bien'ici
devrait densifier. Cause technique : `BieniciScraper.city = "Metz"` codé en dur
(`bienici.py:302`), `discover_zone_ids("Metz")` ne résout que le zoneId communal
de Metz, `zoneIdsByTypes` restreint donc au territoire de Metz intra-muros
(ANALYSE §1.2).

### Périmètre IN

- Étendre `BieniciScraper.scrape` pour itérer sur la liste des communes de
  `_METRO_CITIES` (au lieu de la seule ville `"Metz"`), en réutilisant
  `discover_zone_ids` par commune, puis la boucle existante zones ×
  `SURFACE_BUCKETS`.
- Garantir que la `city` stockée pour chaque comparable matche la forme
  canonique de `_METRO_CITIES` (via `canonical_city`, déjà appliqué dans
  `_parse_listing`).
- Robustesse : une commune qui ne résout pas de zoneId est **sautée avec un log**,
  sans interrompre la collecte des autres communes.
- Ajuster le budget temps du job `collect.yml` (`timeout-minutes`) pour absorber
  le facteur communes × buckets sans dépassement, en respectant `polite_sleep`
  et le retry/backoff 429 existants.
- Prévoir explicitement la **ré-exécution de la probe de couverture**
  (`coverage-probe.yml`) après le prochain passage de `collect.yml`, avec un
  critère de succès observable (bouclage « mesurer → agir → re-mesurer »).

### Périmètre OUT (non-objectifs)

- Toute modification du schéma de réponse `/analyze`, du scoring, des piliers ou
  du front (`frontend/lib/api.ts`). Ce chantier ne touche QUE le stock de
  comparables, jamais le contrat du pilier (ANALYSE §6, CLAUDE §11.9).
- La cascade `market_stats` (`quartier → secteur → ville → métropole`) :
  inchangée. On densifie le niveau `ville` de la couronne, la cascade en profite
  mécaniquement sans modification.
- Tout nouveau portail (seloger, leboncoin, ...), tout nouveau vendor, tout
  service anti-bot. On reste sur l'API JSON bien'ici déjà exploitée.
- Toute estimation de prix, tout usage DVF / PERVAL / bases notariales (NO-GO
  ferme, ANALYSE §8.1).
- Toute redistribution d'annonces brutes : agrégats internes seulement.
- L'intégration de nouvelles agences couronne et l'incrément 2 cross-agence
  (clustering photo) : chantiers distincts (ANALYSE §8.3), hors de cette SPEC.
- La dédup : déjà assurée par `generate_stable_id(source, ext_id)` + upsert
  (`save.py`). Aucun changement requis.

---

## 2. Décisions actées

### 2.1 Décision GATE 1 (acquise)

Élargir bien'ici à la couronne (Q2 de l'ANALYSE) après mesure (Q3). La probe a
été exécutée et confirme le diagnostic : la couronne est creuse côté bien'ici
alors que le marché existe. La porte est donc ouverte : on agit.

### 2.2 Choix technique tranché : variante (a) boucle sur les communes

L'ANALYSE §3.1 pose deux variantes :

- **(a)** boucler `discover_zone_ids` sur une liste de communes (réutiliser
  `_METRO_CITIES`), résoudre le zoneId de chacune, balayer ses `SURFACE_BUCKETS` ;
- **(b)** cibler un seul zoneId d'AGGLOMÉRATION (Metz Métropole) **si** l'endpoint
  suggest en expose un de type plus large que `city`.

**Décision : variante (a) retenue comme implémentation par défaut.**

Justification :

1. **Vérifiabilité.** `discover_zone_ids` (`bienici.py:63-99`) ne sélectionne
   aujourd'hui que les suggestions `type == "city"` (lignes 84 et 93). La
   variante (b) suppose que le suggest renvoie une entrée de type agglo
   (`epci` / `department` / autre) avec un `zoneIds` exploitable par
   `zoneIdsByTypes` — **non vérifiable depuis le repo sans appel réseau réel**
   (le doc `diag_bienici.py:4-7` ne documente qu'un type `city`). Spécifier (b)
   reviendrait à inventer un contrat d'API non observé.
2. **Simplicité et réutilisation.** La variante (a) réutilise tel quel
   `discover_zone_ids`, `_build_filters`, la boucle zones × `SURFACE_BUCKETS` et
   `_parse_listing`. Le seul changement structurel est l'itération externe sur
   une liste de communes. Effort faible, surface de régression minimale.
3. **Robustesse de couverture.** En (a), chaque commune est résolue
   indépendamment : l'échec de résolution d'une commune (suggest vide) n'empêche
   pas les autres. En (b), un seul point de résolution conditionne toute la
   collecte couronne.
4. **Granularité de la `city` stockée.** En (a), la `city` provient du champ
   `ad.city` de chaque annonce (canonicalisé) ; rien ne change. En (b), un pool
   agglo unique ne garantit pas que chaque annonce porte un `ad.city` distinct et
   propre — risque d'agrégat mal réparti à instruire.

**Piste d'optimisation (b) — notée, non retenue à ce stade.** Si une mesure
réseau ultérieure (via `diag-bienici.yml`) confirme qu'un zoneId agglo existe et
couvre exactement `_METRO_CITIES` sans débordement (pas de communes hors dépt 57,
pas de dilution), (b) pourra remplacer (a) en un seul `discover` + un seul
balayage de buckets (moins de requêtes suggest, moins de temps de job). C'est une
optimisation, pas un prérequis. Tout passage à (b) devra re-valider le périmètre
géographique et la répartition des `city`.

### 2.3 Conformité / coût

Aucun nouveau vendor, aucune donnée payante, coût d'infra nul (runner GitHub,
API gratuite). Risque ToS inchangé : même API bien'ici déjà exploitée, pas de
redistribution, agrégats seulement (ANALYSE §6). robots.txt / ToS non modifiés.

### 2.4 Point laissé ouvert (à ne pas inventer)

La SPEC ne fixe pas de chiffre attendu de comparables bien'ici par commune de
couronne : la probe a montré que le marché existe mais le volume réel par commune
n'est connaissable qu'après collecte. Le critère de succès post-déploiement (§5,
AC mesure) est donc formulé en **gain relatif observable** (bien'ici > 0 et total
en hausse sur les communes creuses ciblées), pas en valeur absolue.

---

## 3. Contrat technique

### 3.1 Fonctions et signatures touchées (`backend/scrapers/sources/bienici.py`)

| Élément | État actuel | Modification |
|---|---|---|
| `BieniciScraper.city: str = "Metz"` (l. 302) | une ville unique en dur | remplacée par une **liste de communes cibles** issue de `_METRO_CITIES` |
| `BieniciScraper.scrape` (l. 304-337) | `discover_zone_ids(self.city)` une fois, puis zones × buckets | itère sur la liste de communes : `discover_zone_ids(commune)` par commune, puis zones × buckets, agrège |
| `discover_zone_ids` (l. 63-99) | inchangée | réutilisée telle quelle, appelée une fois par commune |
| `_build_filters`, `_parse_listing`, `SURFACE_BUCKETS` | inchangés | réutilisés tels quels |

**Source de la liste de communes.** Réutiliser `_METRO_CITIES`
(`app/market_stats.py:71`, déjà la liste canonique triée Metz + couronne, dérivée
de `_METRO_CITIES_RAW`). L'import depuis le scraper est acceptable (même paquet
backend) ; à défaut d'import direct souhaité, dupliquer la liste **n'est pas
autorisé** (source unique de vérité : la liste DOIT correspondre à `_METRO_CITIES`,
cf. AC4). Le développeur choisit le mécanisme d'injection (attribut de classe
initialisé depuis `_METRO_CITIES`, ou paramètre) tant que l'AC4 est satisfait.

**Itération.** Pour chaque commune de la liste :
1. `zone_ids = discover_zone_ids(commune)` ;
2. si `not zone_ids` : **log warning + `continue`** (commune sautée, voir 3.2) ;
3. sinon, exécuter la boucle existante `SURFACE_BUCKETS × pages` avec ces
   `zone_ids`, en alimentant un **`seen` global** (dédup intra-run par
   `listing.id` déjà en place, l. 310/328) commun à toutes les communes pour ne
   pas ré-ajouter une même annonce vue via deux zones qui se recouvriraient.

**`city` stockée.** Inchangée : `_parse_listing` lit `ad.city` et applique
`canonical_city` (l. 267). Comme `_METRO_CITIES` est elle-même construite via
`canonical_city`, la `city` persistée matche la clé utilisée par la cascade
`market_stats`. Aucune réécriture forcée de la `city` à partir du nom de commune
demandé : on garde la ville réelle de l'annonce (une annonce limitrophe résolue
sous une commune voisine reste correctement attribuée).

### 3.2 Robustesse

- **Commune sans zoneId** : `discover_zone_ids` renvoie `[]` → `logger.warning`
  (déjà émis en interne l. 98) + `continue` sur la commune suivante. Ne JAMAIS
  lever ni interrompre la collecte des autres communes. (Le `try/except` de
  `run_all` couvre déjà un crash, mais on ne doit pas y recourir : l'échec d'une
  commune ne doit pas faire perdre les autres.)
- **Politesse réseau** : `discover_zone_ids` et `fetch_json` passent par
  `_session` / `fetch_json`, qui appliquent déjà `polite_sleep` et le
  retry/backoff sur 429/5xx (`base.py:40-43, 107-111`). Ne pas court-circuiter ni
  paralléliser de façon à marteler l'API. Aucun nouveau parallélisme requis.
- **Borne de requêtes** : le nombre de requêtes ADS est borné par
  `communes × len(SURFACE_BUCKETS) × MAX_PAGES` ; aucune boucle non bornée
  introduite. La dédup par `seen` ne crée pas de re-fetch.
- **Dédup persistée** : inchangée (`generate_stable_id` + upsert `save.py`).

### 3.3 Budget temps du job (`.github/workflows/collect.yml`)

Estimation d'ordre de grandeur (variante a) :

- 11 communes (`_METRO_CITIES`) × 1 appel suggest ≈ 11 requêtes suggest.
- Pour chaque commune ayant un zoneId : jusqu'à `9 buckets × pages`. En pratique,
  une commune de couronne épuise la plupart des buckets en 1 page (peu d'annonces)
  → l'ordre de grandeur réel est bien inférieur au plafond théorique.
- `polite_sleep` ≈ 1,5 s moyen entre requêtes (`base.py:32`).
- Metz reste la commune la plus volumineuse (~17,5k annonces, plusieurs pages par
  bucket) : c'est elle qui domine le temps de job, déjà absorbée aujourd'hui sous
  15 min. L'ajout de 10 communes creuses ajoute surtout des appels suggest + des
  buckets courts, pas un facteur 11 sur le volume réel.

**Décision** : porter `timeout-minutes` de `15` à **`30`** dans `collect.yml`
(marge de sécurité, coût nul — minutes GitHub Actions). Conserver l'ordre de
collecte tel quel (le `seen` global évite les doublons). Aucun parallélisme
ajouté. Si un run réel dépasse 30 min, l'optimisation (b) ou un ordre de collecte
« couronne d'abord, Metz ensuite » sera réinstruit (hors SPEC).

### 3.4 Schéma DB / migrations / variables d'env / contrat front

- **Schéma DB** : AUCUN changement. La table `comparables` et
  `listing_price_snapshots` sont inchangées. Aucune migration.
- **Variables d'env / secrets** : AUCUN ajout. `collect.yml` utilise déjà
  `BACKEND_URL` et `ADMIN_TOKEN`. Pas de secret en clair.
- **Contrat front (`frontend/lib/api.ts`)** : NON touché. `/analyze` inchangé.

---

## 4. Critères d'acceptation (testables, pytest, API bien'ici MOCKÉE)

Fichier de test attendu : **`backend/tests/test_bienici_couronne.py`**.

Contrainte transverse : **aucun appel réseau réel**. L'API bien'ici est mockée
(monkeypatch / fakes) au niveau de `scrapers.sources.bienici.discover_zone_ids`
et de `scrapers.sources.bienici.fetch_json` (ou des objets qu'ils utilisent), de
sorte que les tests soient déterministes et gratuits (cohérent avec la suite
`backend/tests/`, conftest autouse).

Chaque critère est falsifiable :

- **AC1 — La liste des communes ciblées correspond exactement à `_METRO_CITIES`.**
  L'ensemble des communes pour lesquelles le scraper tente une résolution de zone
  est égal à `set(app.market_stats._METRO_CITIES)` (inclut `"Metz"`). Test :
  capter les arguments des appels à `discover_zone_ids` et asserter
  `set(appels) == set(_METRO_CITIES)`. Falsifiable : rouge si la liste reste
  `["Metz"]` ou omet une commune de couronne.

- **AC2 — `discover_zone_ids` est appelé une fois pour chaque commune de la liste
  configurée.** Le nombre d'appels à `discover_zone_ids` == `len(_METRO_CITIES)`
  et chaque commune y figure une fois. Falsifiable : rouge si une seule commune
  est résolue, ou si une commune est appelée 0 ou plusieurs fois.

- **AC3 — Les comparables collectés portent la `city` canonique de chaque
  commune, pas seulement Metz.** Avec un mock retournant, pour au moins deux
  communes distinctes (ex. `"Marly"` et `"Montigny-lès-Metz"`), des annonces dont
  `ad.city` correspond, le résultat de `scrape()` contient des `PropertyListing`
  dont `city` couvre **au moins deux communes distinctes de la couronne**, sous
  forme canonique (`canonical_city`). Falsifiable : rouge si toutes les `city`
  sont `"Metz"` ou si la couronne est absente.

- **AC4 — La `city` stockée matche la forme de `_METRO_CITIES` (clé de cascade).**
  Pour une annonce mockée `ad.city == "MONTIGNY-LES-METZ"` (casse/variante), le
  `PropertyListing` produit a `city == canonical_city("Montigny-lès-Metz")` et
  cette valeur appartient à `_METRO_CITIES`. Falsifiable : rouge si la `city`
  n'est pas canonicalisée (ne matcherait pas la cascade `market_stats`).

- **AC5 — Une commune dont la résolution de zone échoue est sautée sans
  interrompre les autres.** Avec un mock où `discover_zone_ids` renvoie `[]` pour
  une commune donnée (ex. `"Augny"`) mais des zoneIds valides pour les autres :
  `scrape()` ne lève pas, et renvoie bien les comparables des communes valides
  (la collecte des autres communes n'est pas perdue). Falsifiable : rouge si une
  exception remonte, ou si le résultat est vide / tronqué à la première commune
  en échec.

- **AC6 — Le nombre de requêtes ADS est borné par communes × buckets × pages (pas
  de boucle infinie).** Avec un mock `fetch_json` comptant ses appels et
  retournant des pages finies, le nombre total d'appels ADS est
  `<= len(communes_resolues) * len(SURFACE_BUCKETS) * MAX_PAGES`. Falsifiable :
  rouge en cas de boucle non bornée ou de re-fetch incontrôlé.

- **AC7 — Dédup intra-run inter-communes.** Si deux communes résolvent des zones
  qui renvoient une annonce de même `id` bien'ici, `scrape()` ne la retourne
  qu'une fois (un seul `PropertyListing` pour cet `id`). Falsifiable : rouge si
  le `seen` n'est pas partagé entre communes (doublon).

> Note de conformité aux leçons (`.claude/lessons.md`) : ne pas se contenter
> d'un AC « ne lève pas » pour AC5 — asserter aussi la PRÉSENCE réelle des
> comparables des communes valides (oracle de transit, pas seulement d'absence
> d'erreur). De même, AC1/AC2 doivent capter les appels réels à
> `discover_zone_ids` (par mock instrumenté), pas seulement vérifier un attribut
> de classe.

---

## 5. Mesure de validation post-déploiement (bouclage « mesurer → agir → re-mesurer »)

Le chantier ne se clôt PAS au merge : la boucle GATE 1 (mesurer → agir →
re-mesurer) impose une vérification observable sur la base prod.

Procédure :

1. Une fois le code déployé en prod (merge `main` → auto-deploy Fly,
   `deploy-backend.yml`), déclencher (ou attendre le cron lundi 04:00 UTC) un
   passage de **`collect.yml`** avec le scraper élargi.
2. Après ce passage, ré-exécuter la probe de couverture **`coverage-probe.yml`**
   (déclenchement manuel `workflow_dispatch`), qui lit
   `GET /admin/comparables/coverage` (read-only, agrégats par commune × type ×
   source, conforme CONTEXT §11.3).
3. Comparer au point de référence (run 27473882571).

**AC-MESURE (critère de succès, hors pytest — vérification opérationnelle, à
consigner à la clôture) :** sur les communes creuses ciblées
(**Marly, Montigny-lès-Metz, Saint-Julien-lès-Metz** au minimum), après le
passage de collecte élargi :

- `by_source["bienici"] > 0` pour au moins ces trois communes (alors qu'il valait
  0 / 0 / 1 dans la probe de référence) ; ET
- le `total` par commune est **en hausse** vs la référence (17 591 / 13 / 13 / 7
  → strictement supérieur sur Marly, Montigny, Saint-Julien).

Lecture du résultat :

- **Succès** : bien'ici densifie réellement la couronne → levier confirmé
  (ANALYSE §3.1, gain potentiellement structurant). Clôture du chantier.
- **Échec / gain nul** : si bien'ici reste à 0 sur la couronne après élargissement,
  cela signifie que le marché communal est intrinsèquement étroit côté bien'ici
  (et non un défaut de balayage) → à remonter au porteur (ANALYSE §5 : seul un
  levier hors-MVP, partenariat agences, densifierait alors). Ne PAS sur-interpréter
  un échec comme un bug du scraper sans avoir vérifié les logs de résolution de
  zone par commune.

---

## 6. Conformité (anti-patterns applicables)

- **Pas d'estimation** (CONTEXT §11.1, lessons invariants) : ce chantier ne
  produit aucun prix prédit ; il alimente le stock de comparables observés.
- **Pas de redistribution brute** (CONTEXT §11.3) : on stocke des annonces en
  interne (déjà le cas) et on n'expose que des agrégats. La probe de validation
  (§5) ne lit que des compteurs et libellés.
- **Pas de nouveau vendor / coût** (ANALYSE §6) : même API bien'ici, runner
  GitHub gratuit, < 1 €/mois respecté. Aucun service anti-bot.
- **robots.txt / ToS inchangés** : on exploite l'API JSON bien'ici déjà utilisée,
  sans aggraver le périmètre ni la cadence (politesse `polite_sleep` + backoff
  conservés).
- **Pas de secret en clair** : `collect.yml` continue d'utiliser
  `secrets.ADMIN_TOKEN`. Aucune variable nouvelle.
- **Contrat `/analyze` stable** (CONTEXT §11.9, CLAUDE §10) : aucune modification
  du schéma de réponse ni de `frontend/lib/api.ts`. Le chantier est strictement
  côté collecte.
- **Conventions CLAUDE §12** : Python 3.12 ; logging via le logger nommé du module
  (`logger = logging.getLogger(__name__)`, déjà en place dans `bienici.py`) — un
  log par commune sautée, sans donnée sensible ; pas de commentaire « what »
  (commenter seulement le « why » non trivial, ex. le `seen` global partagé entre
  communes) ; pas d'emoji ; type hints cohérents avec l'existant.

---

SPEC prête pour GATE 2 (approbation humaine).

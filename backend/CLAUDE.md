# CLAUDE.md — backend mvp-immobilier

> Fichier de référence court à lire **avant toute modification du backend**.
> Pour le contexte stratégique, marketing, business et la roadmap, voir
> [`/CONTEXT.md`](../CONTEXT.md) à la racine du repo (source de vérité).
> Ce fichier-ci se concentre sur l'état technique courant du backend.
>
> **Dernière mise à jour :** 2026-06-18 (**screening photo réglé** : `MAX_IMAGES`
> 6 → **15** et `detail` `"low"` → **`"high"`** dans `app/photo_evidence.py`,
> PR #124 → `staging`, promotion #125 → `main`, deploy Fly prod OK. But : moins
> de faux `non_trouve` sur des repères pourtant visibles dans les photos — hors
> des premières images, ou en arrière-plan illisible à 512px. Bloc toujours
> **non-scoré**. Voir §6bis. Avant, même session : **refonte leviers de
> négociation** + section « Atouts du bien » (PR #121 → `main`), resync
> `main` → `staging`.)
>
> **Antérieurement (2026-06-18) :** « Contexte local v2 » **déployé en
> production**, PR #115 → `staging`, fix #117 → `staging`, promotion #116 →
> `main`, deploy Fly prod OK : **temps de trajet réels** via Google Routes API
> (Compute Route Matrix) + endpoint `POST /travel-times`, **re-géocodage** de
> l'adresse texte sans exposer/persister de lat/lon, **snapshot écoles** Metz +
> couronne (issue #100 sous-chantier C3). Intégration Google **inactive sans la
> clé** `GOOGLE_MAPS_API_KEY` → repli « à vol d'oiseau ». Spec :
> `docs/specs/contexte-local-v2-SPEC.md`. Reste TODO issue #100 : **C2**
> (quartier réel par polygones).
> Historique : cross-agence incrément 1 en prod depuis 2026-06-11 (tracking
> temporel par id stable, snapshots de prix, rétention 24 mois). Incrément 2
> (clustering photo) : à faire, staging-first.

---

## 1. Promesse produit (rappel court)

Analyseur de **cohérence d'annonces immobilières**, pas estimateur de prix.
Trois piliers : **prix vs marché local observable**, **transparence sémantique**,
**risques**. Score 0-100 explicable.

Anti-patterns à ne JAMAIS introduire :
- estimation de prix
- consultation DVF / bases notaires
- réagrégation / redistribution d'annonces brutes
- conseil juridique ou financier

---

## 2. Stack et infra réelles (vérifiées dans le code)

| Élément | Valeur |
|---|---|
| Plateforme backend | **Fly.io** (Docker explicite — pas de buildpacks) |
| App Fly | `backend-frosty-sound-441-docker` |
| Région | `cdg` |
| URL prod | https://backend-frosty-sound-441-docker.fly.dev |
| Image | `FROM python:3.12-slim` |
| Commande de démarrage | `uvicorn app.main:app --host 0.0.0.0 --port 8080` |
| Healthcheck Fly | `GET /health` toutes les 30 s, grace 10 s |
| Volume Fly | `comparables_data` (1 Go) monté sur `/data` |
| Persistence | SQLite, chemin via `DATABASE_PATH=/data/comparables.db` |
| Auto-stop / auto-start machines | `true` / `min_machines_running = 0` |
| Plateforme frontend | Vercel (Next.js **16.2.6** App Router) |
| CI | GitHub Actions : `test.yml` (pytest, suite gratuite `backend/tests/`), `evals.yml` (suite `backend/evals/`, **payante : vrais appels LLM**, PR touchant prompt/pipeline, secret `OPENAI_API_KEY` requis), `collect.yml`, `diagnose-scrapers.yml`, `diag-bienici.yml` |
| CD backend | `deploy-backend.yml` — **auto-deploy Fly** : push `main`→**prod** (`fly.toml`), push `staging`→**staging** (`fly.staging.toml`, app `coherence-staging`). `flyctl deploy --remote-only`, secret `FLY_API_TOKEN` (accès aux 2 apps), concurrency par env ; `workflow_dispatch` manuel |
| App Fly staging | `coherence-staging` (env de test isolé, base SQLite + volume dédiés ⇒ events 9.10 séparés de la prod). Voir `docs/specs/ENVIRONNEMENTS-ET-DOMAINE.md` |
| Domaine définitif | `coherence-metz.fr` (OVH) — **LIVRÉ 2026-06-11**, TLS actif : prod `coherence-metz.fr` / `api.coherence-metz.fr`, staging `staging.` / `api-staging.`. Détail : `docs/specs/ENVIRONNEMENTS-ET-DOMAINE.md` |

⚠️ **Pas de Railway.** Toute documentation interne qui mentionne encore Railway
ou le port 8000 est périmée et doit être ignorée.

---

## 3. Secrets et variables d'environnement

| Variable | Où | Usage |
|---|---|---|
| `OPENAI_API_KEY` | `fly secrets` | Appel `gpt-4.1-mini` |
| `OPENAI_MODEL` (optionnel) | `fly secrets` | Par défaut `gpt-4.1-mini` |
| `GOOGLE_MAPS_API_KEY` (optionnel) | `fly secrets` (prod **et** staging) | Active les **temps de trajet réels** (Google Routes API, header `X-Goog-Api-Key`). **Absente → repli « à vol d'oiseau »** (le routing ne lève jamais). Restreindre la clé à *Routes API* + poser un quota/jour (cap dur) côté Google Cloud. |
| `ADMIN_TOKEN` | `fly secrets` **et** GitHub repo secret | Authentifie `POST /admin/comparables` |
| `DATABASE_PATH` | `fly.toml [env]` | `/data/comparables.db` |
| `CORS_ORIGINS` (optionnel) | env Fly | Par défaut : localhost + `coherence-metz.fr`/`www.`/`staging.` + regex `*.vercel.app` (cf. `main.py`) |
| `NEXT_PUBLIC_API_URL` | Vercel | URL prod du backend |

---

## 4. Arborescence backend (état réel)

```
backend/
├── Dockerfile              # uvicorn :8080 + PYTHONUNBUFFERED
├── fly.toml                # 1 VM, volume /data, healthcheck /health, auto-stop
├── requirements.txt        # fastapi, uvicorn[standard], sqlalchemy, requests,
│                           # beautifulsoup4, openai>=1.50, numpy
├── app/
│   ├── main.py             # FastAPI, CORS, /health, /, /analyze, /travel-times, /admin/*
│   ├── analysis.py         # Orchestrateur run_full_analysis
│   ├── llm_semantic.py     # gpt-4.1-mini, cache mémoire SHA-256 TTL 7j
│   ├── market_stats.py     # SQL comparables, fallback district, stats Q1/médiane/Q3
│   ├── scoring.py          # Score global 0-100 (40+30+30)
│   ├── url_fetch.py        # GET URL annonce + extraction texte HTML + extract_image_urls, SSRF filter
│   ├── photo_evidence.py   # screening photo (NON-scoré) : appel vision gpt-4.1-mini
│   │                       # sur claims locaux éligibles, cap 15 images detail high,
│   │                       # cache mémoire TTL 7j, repli sûr non_trouve (cf. §6bis)
│   ├── rate_limit.py       # rate_limiter(limit, window) — dépendance FastAPI (9.9)
│   ├── geo_gazetteer.py    # référentiel géo unique (issue #100 B) : localités, alias
│   ├── geocode.py          # adresse → {lat, lon, score, label, city} via la BAN (couche C)
│   ├── metz_local.py       # profil quartier curaté + facts POI/écoles + contrôle cohérence
│   ├── routing.py          # client Google Routes (Compute Route Matrix), injectable/
│   │                       # mockable, repli silencieux, cache mémoire TTL 10 min
│   ├── schools.py          # k-NN Haversine sur le snapshot écoles (1 école/degré)
│   └── data/
│       └── schools_metz.json  # snapshot Annuaire Éducation Nationale (Licence Ouverte)
├── db/
│   ├── models.py           # SQLAlchemy Comparable, ListingPriceSnapshot
│   └── session.py          # SessionLocal, init_db, DATABASE_PATH
├── ingestion/
│   └── save.py             # save_comparables(list[dict]) → DB (lecture explicite
│                           # + upsert, first_seen immuable, snapshot si prix change)
│                           # + garde-fou central prix/m² [800-12000] (toutes sources)
├── scrapers/
│   ├── base.py             # session HTTP UA Chrome, retry, normalize_price/surface,
│   │                       # infer_property_type, extract_district (Grand Metz)
│   ├── models.py           # @dataclass PropertyListing
│   ├── protocol.py         # ScraperProtocol
│   ├── registry.py         # @register(name), run_all() — pattern registre
│   ├── recon.py            # outil dev : recon HTML d'agences locales
│   ├── diag_bienici.py     # outil dev : diagnostic API Bien'ici
│   ├── diagnose.py         # harnais : run sources + rapport Markdown / mode --recon
│   ├── site_local.py       # shim de rétrocompat — n'éditer plus, redirige vers sources/
│   └── sources/
│       ├── __init__.py     # load_all() — autoload de tous les modules du package
│       ├── bienici.py      # @register("bienici") — API JSON, zoneIdsByTypes
│       ├── benedic.py      # @register("benedic") — HTML benedicsa.com (data-card-maker)
│       ├── idemmo.py       # @register("idemmo") — HTML idemmo.fr (Essential Real Estate)
│       ├── immoheytienne.py# @register("immoheytienne") — HTML immoheytienne.fr
│       └── site_local.py   # @register("laveine_immo") — HTML laveine.immo
└── jobs/
    ├── collect_metz.py     # CLI local : python -m jobs.collect_metz
    └── push_comparables.py # CI : scrape + POST batches vers /admin/comparables
```

⚠️ `scrapers/site_local.py` (à la racine) est un **shim de rétrocompat** :

```python
from scrapers.sources.site_local import SiteLocalScraper
def scrape_site_local_metz() -> list: ...
```

Ne rien ajouter dedans. Toute nouvelle logique scraper va dans `scrapers/sources/`.

---

## 5. Endpoints HTTP exposés (état réel — `backend/app/main.py`)

| Méthode | Chemin | Auth | Rôle |
|---|---|---|---|
| GET | `/health` | aucune | `{"status":"ok"}` — pour Fly healthcheck |
| GET | `/` | aucune | `{"service":"mvp-immobilier","docs":"/docs"}` |
| GET | `/docs` | aucune | Swagger UI FastAPI |
| POST | `/analyze` | aucune | Analyse cohérence d'une annonce |
| POST | `/travel-times` | aucune (rate-limit 30/60s) | Temps de trajet à la demande depuis une adresse texte (re-géocodée), par mode |
| GET | `/admin/comparables/stats` | `X-Admin-Token` | `{"total": n, "cities": [...]}` |
| GET | `/admin/comparables/cross-source-probe` | `X-Admin-Token` | Probe read-only du gisement de re-list cross-source (compteurs agrégés de `tools.probe_cross_source`, voir ci-dessous) |
| GET | `/admin/comparables/{listing_id}/history` | `X-Admin-Token` | Historique temporel d'une annonce (métadonnées factuelles uniquement, voir ci-dessous) |
| POST | `/admin/comparables` | `X-Admin-Token` | Import batch (max 10000) |
| POST | `/admin/comparables/maintenance` | `X-Admin-Token` | Assainit l'historique + rétention 24 mois (voir §9) |

### `POST /analyze`
Body (au moins l'un des deux) :
```json
{"raw_text": "Appartement T3 à Metz...", "url": null}
```
ou
```json
{"raw_text": null, "url": "https://..."}
```

Quand `url` est fourni seul, le backend télécharge la page via `app/url_fetch.py`
(UA Chrome, anti-SSRF basique, extraction du `<main>`/`<article>`, plafond
8000 chars) puis passe le texte au LLM.

Réponse :
```json
{
  "global_score": 0-100,
  "verdict": "Cohérence forte" | "À creuser" | "Risque élevé" | "Cohérence faible",
  "confidence": "Élevée" | "Moyenne" | "Faible",
  "pillars": [
    {"label": "Prix vs marché local", "verdict": "...", "explanation": "..."},
    {"label": "Transparence de l'annonce", "verdict": "...", "explanation": "..."},
    {"label": "Risques et incertitudes", "verdict": "...", "explanation": "..."}
  ],
  "actions": {"check": [...], "questions": [...], "negotiation": [...]}
}
```

Codes d'erreur : 400 (aucun input), 422 (URL fournie mais inaccessible),
500 (erreur interne, loguée).

### `POST /travel-times`
Calcul de **temps de trajet réels** à la demande (onglets « à pied / à vélo /
en voiture / en transports » du front), via Google Routes API. Sans LLM ni DB.
Rate-limit 30 requêtes / 60 s (`rate_limiter`).

Body : `{"address": "12 Rue des Parmentiers 57000 Metz", "mode": "WALK"}`
(modes `WALK` / `BICYCLE` / `DRIVE` / `TRANSIT`).

RGPD : l'adresse texte est **re-géocodée côté serveur** (BAN) à la volée ;
**aucune coordonnée n'est exposée au client ni persistée**. Si
`GOOGLE_MAPS_API_KEY` est absente / le routing échoue / l'adresse n'est pas
géocodable → **repli silencieux** sur la distance Haversine « à vol d'oiseau »
(jamais de minutes sur une distance, jamais « à vol d'oiseau » sur un temps
routé — étiquetage honnête).

### `POST /admin/comparables`
Authentification : header `X-Admin-Token` comparé en temps constant à
`os.getenv("ADMIN_TOKEN")`. 503 si la variable n'est pas configurée, 401 si
mismatch, 413 au-delà de 10000 items.

Body :
```json
{"items": [{"id": "...", "source": "...", "city": "...", "property_type": "appartement",
            "surface_m2": 80, "price_total": 250000, "district": null}, ...]}
```

Délègue à `ingestion/save.save_comparables`, recalcule `price_m2`.

### `GET /admin/comparables/{listing_id}/history`
Historique temporel d'une annonce par id stable (chantier cross-agence,
incrément 1). Renvoie des **métadonnées factuelles uniquement** (CONTEXT §11.3) :

```json
{
  "listing_id": "...", "source": "bienici",
  "first_seen_at": "...", "last_seen_at": "...",
  "weeks_on_market": 22,
  "price_first": 250000, "price_last": 239000, "price_change_pct": -4.4,
  "snapshots": [{"price_total": 250000, "price_m2": 3125.0, "observed_at": "..."}]
}
```

Jamais de contenu re-publiable (texte, adresse, URL, photo, ni city/district).
`weeks_on_market` = floor des jours/7 (null si dates manquantes) ;
`price_change_pct` = round 1 décimale entre premier et dernier snapshot (null si
<2 snapshots). 401 token absent/mismatch, 503 `ADMIN_TOKEN` non configuré,
404 id inconnu.

---

## 6. Pipeline d'analyse (état réel)

```
POST /analyze
  └── run_full_analysis(raw_text)               ← app/analysis.py
        ├── analyze_semantic()                  ← app/llm_semantic.py → OpenAI gpt-4.1-mini
        │     retourne :
        │     - transparency_score (int 0-100)
        │     - verdict, summary, risk_level, risk_summary
        │     - questions[], highlights[], negotiation_levers[]
        │     - listing: {city, district, property_type, surface_m2, price_total}
        │
        ├── _price_pillar_from_listing(listing)
        │     └── compute_price_market_pillar()  ← app/market_stats.py
        │            └── compute_market_stats()
        │                   1) requête DB avec district si fourni
        │                   2) si <3 résultats : retry sans district (fallback)
        │                   → médiane, Q1, Q3, dispersion, confiance
        │            └── interpret_price_positioning() → verdict ("Plutôt aligné",
        │                  "Légèrement sur-positionné", "Fortement sur-positionné",
        │                  "Sous-positionné", "Indéterminé")
        │
        └── compute_global_score()               ← app/scoring.py
              pondération : 40 pts prix + 30 pts transparence + 30 pts risques
              verdict global selon score :
                ≥80 "Cohérence forte" | ≥60 "À creuser"
                ≥40 "Risque élevé"    | <40 "Cohérence faible"
```

⚠️ Le **pilier prix renvoie "Indéterminé"** si :
- le LLM n'a pas extrait city/surface/price_total ;
- ou la DB renvoie <3 comparables même après fallback sans district.

Voir §11 pour les pistes de tuning du `scoring.py` (déséquilibre actuel
quand seul le prix est défavorable).

---

## 6bis. Screening photo des allégations locales (`app/photo_evidence.py`)

Bloc **NON-scoré** (n'entre jamais dans le 40/30/30) branché en **mode URL** dans
`run_full_analysis(..., image_urls=...)`. Objectif : confronter aux photos de
l'annonce les seules allégations locales **visuellement vérifiables** et poser un
`photo_status` informatif sur chaque claim de `local_context.claims`.

Flux :
1. `url_fetch.extract_image_urls(html, base_url)` extrait les URLs d'images (ordre
   de priorité `og:image`/`twitter:image` → JSON-LD `image` → `<img>`, dédup).
2. `assess_claims_with_photos(claims, image_urls)` :
   - **gating par TYPE** : seuls les claims de type `cathedrale` / `nature` /
     `autre` (`ELIGIBLE_TYPES`) sont éligibles ; jamais par le texte.
   - **court-circuit** : 0 claim éligible OU 0 image → aucun appel LLM.
   - **cap** : `MAX_IMAGES = 15` premières images, transmises en
     `IMAGE_DETAIL = "high"` (réglage 2026-06-18 : avant 6 / `"low"` ; `high` est
     nécessaire pour lire les repères en arrière-plan que 512px rendait illisibles).
   - **un seul** appel multimodal `gpt-4.1-mini` (`temperature=0.2`,
     `response_format=json_object`), prompt système strict anti-complaisance.
   - statut par claim ∈ `{confirme, non_trouve, non_applicable}` ; **repli sûr
     `non_trouve`** à la moindre incertitude/erreur (jamais `confirme` par défaut).
   - **cache mémoire** SHA-256 (clé = images + claims normalisés), TTL 7j.
3. `analysis._merge_photo_status` fusionne le statut dans chaque claim éligible.

Garanties : RGPD (URLs d'images **jamais loggées**, transit sans stockage, pas de
re-fetch serveur), score inchangé. Coût : `detail:"high"` × 15 ≈ 3-4k tokens
d'entrée par analyse non cachée (`gpt-4.1-mini`), amorti par le cache.
Spec : `docs/specs/photo-evidence-SPEC.md`. Tests :
`tests/test_photo_evidence*.py` (bornes du cap recâblées sur `MAX_IMAGES`).

---

## 7. Modèle de données

`db/models.py` — table `comparables` :

```python
class Comparable(Base):
    id            = Column(String, primary_key=True)  # sha256(source:external_id)
    source        = Column(String, nullable=False)    # ex "bienici"
    city          = Column(String, nullable=False)    # normalisé (Casse-Titre)
    district      = Column(String, nullable=True)
    postal_code   = Column(String, nullable=True)      # code postal 5 chiffres (filtre dépt 57)
    property_type = Column(String, nullable=False)    # "appartement" | "maison"
    surface_m2    = Column(Float, nullable=False)
    price_total   = Column(Float, nullable=False)
    price_m2      = Column(Float, nullable=False)
    dpe                = Column(String, nullable=True)   # lettre A-G (chantier B)
    construction_year  = Column(Integer, nullable=True)  # (chantier B)
    floor / has_elevator / has_terrace / has_balcony / is_condo /
    condo_fees / has_cellar / parking / bedrooms         # critères affinés (chantier C)
    collected_at  = Column(DateTime, default=datetime.utcnow)
    first_seen_at = Column(DateTime, nullable=True)   # 1re observation, JAMAIS réécrit
    last_seen_at  = Column(DateTime, nullable=True)   # rafraîchi à chaque passage
```

`db/models.py` — table `listing_price_snapshots` (cross-agence incrément 1) :
une ligne à la 1re observation d'un id puis une par **changement** de
`price_total` (mode delta). Colonnes `id` (PK), `listing_id` (indexé, =
`comparables.id`, pas de FK formelle), `price_total`, `price_m2`, `observed_at`.
La logique de capture est dans `ingestion/save.py` : lecture explicite de la
ligne existante (plus de `db.merge`, qui écrasait l'historique), `first_seen_at`
immuable (repli `collected_at` pour les lignes prod héritées), `last_seen_at` et
`collected_at` rafraîchis, snapshot conditionnel à l'égalité exacte sur
`price_total`. Rétention : purge 24 mois après `last_seen_at` (voir §9).

> **Chantier B (critères affinés)** : `dpe` + `construction_year` ajoutés (nullable,
> remplissage variable : bien'ici ~82% DPE / ~33% année ; agences best-effort).
> `db/session.init_db` fait une **micro-migration** idempotente (`ALTER TABLE ADD
> COLUMN`) pour les bases prod existantes. L'**époque** (neuf/récent/ancien) est
> *dérivée* (`scrapers.base.construction_epoch`), pas stockée.
>
> **B2 — usage hybride (`market_stats`)** : la sélection des comparables suit une
> **cascade** retenant le périmètre le plus précis encore peuplé (≥10) :
> `quartier+bandeDPE → quartier → secteur+bandeDPE → secteur → ville+bandeDPE →
> ville → métropole+bandeDPE → métropole` (bandes DPE larges A-B / C-D / E-G, cf.
> `dpe_band` ; niveau **secteur** = chantier #6 ; niveau **métropole** = communes
> limitrophes, cf. §11 « Secteur Metz métropole »). En plus, un **signal explicatif** (couche 2,
> non-estimatif) situe le DPE/époque du bien vs le profil du pool, ajouté à
> l'explication — **verdict et score inchangés**.
>
> **B3 — extraction LLM** : `llm_semantic` extrait aussi `dpe` + `construction_year`
> de l'annonce analysée (sinon `null`).
>
> **Chantier C (critères de confort)** : `floor`, `has_elevator`, `has_terrace`,
> `has_balcony`, `is_condo`, `condo_fees`, `has_cellar`, `parking`, `bedrooms`
> (nullable, micro-migration idempotente). Captés par bien'ici (`_extract_amenities`,
> noms de champs confirmés par `field_audit_md` : `floor` 82 %, `hasElevator` 78 %,
> `hasTerrace`/`terracesQuantity`, `isInCondominium`, `annualCondominiumFees`...) ;
> sources HTML → `None`. Surfacés **des deux façons**, sans estimation :
> 1) **signal factuel** ajouté à l'explication du pilier prix (`_amenity_phrases` :
>    « 4e étage sans ascenseur, avec terrasse... ») — verdict/score inchangés ;
> 2) **actions déterministes** (`analysis._amenity_actions`) fusionnées (dédup) aux
>    listes du LLM : étage élevé sans ascenseur → vérification + levier de négo,
>    charges de copropriété → à intégrer au budget. `llm_semantic` extrait ces
>    champs de l'annonce analysée.
>
> **Chantier #6 (cascade secteurs)** : niveau intermédiaire `quartier → secteur →
> ville` dans `market_stats` pour qu'un quartier creux emprunte aux quartiers
> voisins (100 % comparables observés). `_SECTORS_RAW` (carte validée des secteurs
> messins : Centre Ville, Sablon, Plantières-Queuleu, Devant-les-Ponts,
> Patrotte-Metz-Nord, Borny [+Technopôle/Grange], Bellecroix-Vallières, Magny) est
> **normalisée via `canonical_district` au chargement** → matche les libellés
> stockés, formes composées bien'ici incluses. Le front (sélecteur de quartier)
> envoie `district` à `/analyze` (override prioritaire) ; le pilier prix expose
> `scope`/`scope_name`/`dpe_band`/`n_comparables`/`refinable` → chip dynamique.
> *Limite connue* : quelques formes composées rares (`Grange-Aux-Bois-Grigy-Technopole`,
> `Metz-Devant-Les-Ponts`) pas encore mappées à un secteur (sans impact : niveau
> quartier ou repli ville).

État : **5 sources** actives (bienici, benedic, laveine_immo, idemmo,
immoheytienne). Depuis le **balayage par tranches de surface** de bien'ici (juin
2026, cf. §8), un run collecte **~17,4k annonces bien'ici** (toutes tailles, dont
~2,6k maisons) + ~350 des agences → base prod **~17,7k comparables** (vs ~1,1k
avant). Couverture des 12-16 quartiers messins largement au-dessus du seuil
d'affinage pour toutes les tailles. La ville est stockée sous forme canonique
(`canonical_city`) ; un garde-fou prix/m² [800-12000] est appliqué à l'ingestion
(`ingestion/save.py`) à toutes les sources. `jobs/push_comparables` **filtre les
items invalides** (ville manquante…) et **ne s'arrête plus sur un batch en échec**
(robustesse collecte, juin 2026).

Seuils dans `market_stats.py` :
- Fenêtre surface : ±20%
- Minimum 3 comparables sinon `None` (verdict "Indéterminé")
- Confiance "Élevée" si ≥10 comparables ET dispersion <800 €/m²
- Confiance "Moyenne" si ≥4 ; sinon "Faible"

Seuils de verdict prix (vs médiane locale) :
- ≤ ±10 % → "Plutôt aligné"
- +10 à +25 % → "Légèrement sur-positionné"
- > +25 % → "Fortement sur-positionné"
- < -10 % → "Sous-positionné"

---

## 8. Architecture scrapers (pattern registre)

### Registre
`scrapers/registry.py` expose `@register("nom")` et `run_all()`. Chaque module
dans `scrapers/sources/` enregistre sa classe ; `run_all()` les exécute toutes
et agrège des `PropertyListing`.

### Source 1 : `bienici` (principale)
`scrapers/sources/bienici.py` — **API JSON pas HTML**, donc immunisé aux
protections anti-bot des frontaux.

- **Collecte sur toute la couronne** (juin 2026) : le scraper **itère sur les
  communes de `app.market_stats._METRO_CITIES`** (Metz + couronne : Montigny,
  Woippy, Marly, Le Ban-Saint-Martin, Longeville, Saint-Julien, Scy-Chazelles,
  Plappeville, Lessy, Augny) — source unique de vérité importée, pas dupliquée —
  au lieu de la seule commune de Metz codée en dur. Une commune dont la zone ne
  se résout pas est sautée (log) sans interrompre les autres ; un `seen` global
  partagé dédoublonne intra-run les annonces vues via deux communes limitrophes.
  La `city` stockée reste celle de l'annonce, canonicalisée (`canonical_city`).
- Découverte dynamique de l'identifiant de zone via
  `https://res.bienici.com/suggest.json?q=<ville>` → renvoie `zoneIds`
  (ex. Metz = `["-450381"]`). C'est l'ID interne Bien'ici, **pas** l'INSEE.
- Endpoint annonces : `https://www.bienici.com/realEstateAds.json`
  avec `filterType=buy` + `zoneIdsByTypes.zoneIds`
- **Collecte par tranches de surface** (juin 2026) : l'API trie par **petites
  surfaces d'abord** et **plafonne la pagination à ~2500 résultats** (offset 2500)
  alors que le total dépasse 27k. Lire les 1000 premières annonces ne ramenait que
  des studios (aucun appartement > 70 m² en base → pilier prix faussé). On **balaie
  donc par tranches de surface** (`SURFACE_BUCKETS`, `minArea`/`maxArea`), chaque
  tranche paginée jusqu'à épuisement, dédup par id → couverture de **toutes les
  tailles** + gros volume (~17,4k). Diagnostiquer via `scrapers.diagnose`
  (histogramme surfaces, profondeur quartier/secteur) ; sonde de pagination
  ponctuelle disponible dans `diag_bienici.deep_pagination_probe_md`.
- **Pagination historique** : 50/page (avant le balayage par tranches)
- **Filtres qualité** dans `_parse_listing` :
  - `adType == "buy"` uniquement (rejette `lifeAnnuitySale` viagers et `rent`)
  - Type résidentiel uniquement (flat/studio/loft/duplex/house/villa/castle/townhouse/manor)
  - `price` et `surfaceArea` doivent être des nombres simples (rejette les
    fourchettes `[min, max]` des programmes neufs)
  - Bande de plausibilité prix/m² : **800-12000 €/m²** (éjecte parkings,
    erreurs de saisie, biens hors marché)
  - Normalisation casse ville via `_normalize_city`
- Renvoie ~830 comparables propres pour Metz par run

### Source 2 : `laveine_immo` (complément)
`scrapers/sources/site_local.py` — scraper HTML de https://www.laveine.immo
avec sélecteurs CSS spécifiques (`article.item`, `.item__price`,
`.item__block--title`, `.item__block--city`). Apporte des biens en exclusivité
agence, notamment quelques maisons dans les communes limitrophes.

### Sources 3-5 : agences locales HTML (ajoutées via le harnais de diagnostic)
- `benedic` — `scrapers/sources/benedic.py` : benedicsa.com. Cartes
  `div[data-card-maker]` (id stable), prix dans `p.text-2xl`, ville dans
  `p.uppercase` (segment après ` - `), surface depuis le bloc méta / titre.
  Pagination `?page=N` avec arrêt dès qu'aucune annonce nouvelle. ~240 annonces,
  couverture Moselle large (Forbach, Thionville, Saint-Avold...).
- `idemmo` — `scrapers/sources/idemmo.py` : idemmo.fr (plugin Essential Real
  Estate). Cartes `.js-es-listing`, prix `.es-price`, ville/surface dans les
  méta structurées (`li.es_property_address` / `li.es_property_area`),
  pagination via lien « next ».
- `immoheytienne` — `scrapers/sources/immoheytienne.py` : immoheytienne.fr.
  Cartes `a[href*='/property/']`, prix `.price-badge`, ville `.locality-badge`,
  **surface habitable** depuis le span picto (évite les pièges du titre :
  surface de jardin, année de construction). Majoritairement des maisons.

Agences écartées au recon : herbeth, agencevalentin (robots.txt interdit +
HTTP 403), century21, orpi (rendu JS-only, pas de prix dans le HTML serveur).

### Bases utilitaires partagées
`scrapers/base.py` :
- `requests.Session` réutilisée + UA Chrome 121 réaliste
- `fetch_page` et `fetch_json` avec retry/backoff sur 429/5xx
- `polite_sleep` avec jitter
- `generate_stable_id(source, ext_id)` → sha256
- `normalize_price` / `normalize_surface` (regex, gèrent points de milliers,
  virgules décimales, "à partir de", "FAI", "nbsp")
- `infer_property_type` (maison/villa/pavillon... sinon appartement)
- `extract_district` (~30 localités du Grand Metz reconnues, renvoie `None`
  si inconnu — pas de placeholder)
- `canonical_city` : forme canonique partagée par **toutes les sources** ET par
  `market_stats` (requête d'analyse). Supprime les accents, unifie espaces/tirets,
  capitalise par segment → 'Montigny-lès-Metz', 'Montigny Les Metz' et
  'MONTIGNY-LES-METZ' deviennent tous 'Montigny-Les-Metz'. Indispensable pour que
  les comparables d'une même commune issus d'agences différentes s'agrègent.
- `canonical_district` : idem pour les quartiers. Retire le préfixe ville des
  libellés Bien'ici ('Metz - Bellecroix' -> 'Bellecroix', 'Metz' seul -> None) et
  normalise. Appliqué côté stock (Bien'ici) ET requête (`market_stats`) pour
  comparer un bien aux comparables du **même quartier**. Les quartiers composés
  ('Plantières - Queuleu') ne matchent pas un mono-quartier extrait du texte
  ('Queuleu') -> repli ville (limite connue).

### Outils dev (pas en prod)
- `scrapers/recon.py` : exécution locale pour ausculter une URL d'agence
  (statut, présence prix dans le HTML, classes CSS candidates, dump local
  dans `recon_dumps/`)
- `scrapers/diag_bienici.py` : suite de tests sur l'API Bien'ici (suggest
  endpoints, variantes de filtres) — exécutable via GitHub Action
  `diag-bienici.yml`
- `scrapers/diagnose.py` : **harnais de diagnostic générique**. Lance les
  sources enregistrées et produit un rapport Markdown (comptage, villes,
  types, distribution prix/m², hors-bande, échantillon). `--recon <url>`
  ausculte le HTML brut (statut, signaux prix, classes CSS candidates).
  Écrit `diag_report.md` et l'affiche sur stdout. Code de sortie non nul si
  une source renvoie 0 annonce. Sans accès réseau en local, c'est le runner
  CI qui l'exécute (voir `diagnose-scrapers.yml`, §9).

---

## 9. Pipeline d'ingestion (CI + manuel)

### En CI (production)
1. `.github/workflows/collect.yml` se déclenche :
   - manuellement (`workflow_dispatch`)
   - **chaque lundi 04:00 UTC** (`schedule: cron "0 4 * * 1"`)
2. Le runner GitHub installe Python 3.12 + `requirements.txt`
3. Exécute `python -m jobs.push_comparables` avec
   `BACKEND_URL=https://...fly.dev` et `ADMIN_TOKEN=<secret>`
4. Le job :
   - appelle `scrapers.sources.load_all()` qui importe automatiquement tous
     les modules de `scrapers/sources/` (déclenche leurs `@register`). Une
     nouvelle agence = un fichier déposé, sans édition du job.
   - appelle `run_all()` (collecte sur les runners GitHub, pas anti-bot)
   - batch de 1000 max et POST vers `/admin/comparables`
5. Le backend reçoit, appelle `ingestion/save.save_comparables` → garde-fou
   prix/m² [800-12000] (rejet des loyers/parkings/erreurs, toutes sources) puis
   écriture sur le volume `/data`

### Diagnostic des scrapers en CI (`diagnose-scrapers.yml`)
Boucle de développement automatisable des nouveaux scrapers :
1. Se déclenche sur **`pull_request`** touchant `backend/scrapers/**` ou
   `backend/jobs/**` (et `workflow_dispatch`).
2. Installe les deps, exécute `python -m scrapers.diagnose --out diag_report.md`.
3. **Poste le rapport en commentaire de PR** (commentaire collant, mis à jour
   à chaque push via `actions/github-script`). C'est le canal de retour : pas
   besoin de lire les logs Actions bruts.
4. Le job passe au rouge si une source renvoie 0 annonce.

Boucle type pour intégrer une agence : déposer `sources/<agence>.py` sur une
branche → ouvrir une PR → lire le commentaire de diagnostic → corriger les
sélecteurs → repousser → relire → merge quand vert.

### Maintenance de l'historique (`POST /admin/comparables/maintenance`)
Le garde-fou prix/m² et le filtre zone à l'ingestion ne nettoient que les
*nouvelles* écritures ; les lignes anciennes (outliers d'avant le filtre, villes
en ancien format) persistent. Cet endpoint les assainit en base :
- **purge** les lignes hors bande `[800-12000]` (`purged_band`) ;
- **purge** les communes hors périmètre (`OUT_OF_SCOPE_CITIES`, dépt 54 /
  agglo nancéienne — `purged_zone`) ; `extra_out_of_scope: [...]` ajoute des
  villes ponctuelles ;
- **ré-applique `canonical_city`** aux villes existantes (`renamed`) et
  `canonical_district` aux quartiers existants (`renamed_district`) ;
- **purge de rétention** (cross-agence incrément 1) : comparables dont
  `last_seen_at` date de **plus de 730 jours révolus** (24 mois ; exactement
  730 jours = conservé) — compteur `purged_retention`. Une ligne
  `last_seen_at` NULL n'est jamais purgée par cette règle.

**Cascade snapshots** : TOUTE purge d'un comparable (band, zone, dept ou
rétention) supprime aussi ses `listing_price_snapshots` dans la même
transaction — compteur `purged_snapshots`. Un **balayage final d'orphelins**
supprime en plus les snapshots dont le `listing_id` n'existe plus dans
`comparables` (rattrape les orphelins laissés par d'anciennes purges sans
cascade ou par tout chemin de suppression futur oublié) — compteur dédié
`purged_orphan_snapshots` (un orphelin signale une anomalie passée, pas une
cascade attendue).

`dry_run` est **true par défaut** (simulation, ne supprime rien) ; passer
`{"dry_run": false}` pour appliquer. Renvoie les compteurs + `total_after`.

### En local (manuel, alternatif)
```bash
python -m jobs.collect_metz
```
Écrit directement dans `comparables.db` local (ne touche pas la prod).

---

## 10. Frontend en bref (pour comprendre le contrat API)

Le frontend a été repris depuis une autre conversation Claude (design
system "Cohérence"). Côté contrat API :

- `frontend/lib/api.ts` expose
  `analyzeListing(input: string, mode: "url" | "text"): Promise<ApiResult>`
  → envoie `{url}` ou `{raw_text}` selon le mode choisi par l'utilisateur
  (onglets explicites dans `components/design/AnalyzerInput.tsx`, plus de
  détection regex côté client).
- Polices Google Fonts (`Instrument Serif`, `Geist`, `Geist Mono`).
- Tokens de design dans `app/globals.css` (palette ink/parchment/brick/
  moss/ochre, échelle typo 12-88 px, espacements 4 px).
- Next.js **16.2.6** App Router, déployé sur Vercel.
- Composants présentation : `VerdictHeader`, `PillarBar`, `ScoreRing`,
  `ChecklistCard`, `LeversList`, `Wordmark`, `ScopeBadge`, `Footer`, `Icons`
  (tous sous `components/design/`).
- Les anciens composants à la racine (`components/Actions.tsx`,
  `Pillars.tsx`, `ScoreResult.tsx`) sont conservés mais **plus utilisés**
  par la page principale.

**Côté backend, retenir** : la réponse `/analyze` doit garder ce schéma
(`global_score`, `verdict`, `confidence`, `pillars[]`, `actions{highlights,
questions, negotiation}`, `local_context` optionnel). Le frontend code en dur l'ordre des
piliers `[prix, transparence, risques]`. Chaque pilier porte `points`/`max`
(prix /40, transparence /30, risque /30) : **le score global est exactement la
somme des `points`** (cf. §11, scoring 40/30/30). Depuis le chantier A, `actions`
a fusionné `to_check` dans `questions`. Depuis la refonte des leviers
(chantier negotiation-levers-review) `actions` porte **trois** listes :
`highlights` (atouts factuels du bien, objective sa valeur — LLM), `questions`,
et `negotiation` recentré **côté acheteur** (éléments factuels qui pèsent à la
baisse : prix sur-positionné [dérivé du pilier prix], DPE F/G, allégation locale
peu plausible, étage élevé sans ascenseur, points faibles extraits par le LLM ;
liste vide plutôt que des atouts si rien de défavorable). `highlights` est
optionnel dans le contrat (rétro-compatible). Le bloc
`local_context` (non-scoré) porte le profil de quartier (couche A), la liste
`claims` (couche B : `{text, type, status, note}`), `address` (si saisie) et
`precision` ∈ `{"quartier","adresse"}` (couche C : `"adresse"` = distances
exactes géocodées, `"quartier"` = repli profil). `AnalyzeRequest` accepte
`district` et `address` (tous deux optionnels).

---

## 11. Limitations connues et dette technique

### Côté produit / scoring
- **Pondération du score 40 / 30 / 30** (prix / transparence / risque = 100) :
  `compute_global_score` renvoie un `breakdown` par pilier et le score global est
  **exactement la somme** prix(/40)+transparence(/30)+risque(/30). Le front
  affiche ces `points` (pilier prix /40 + pilier sémantique /60 = global), il ne
  recalcule plus de barres divergentes. *(Corrigé 2026-06-04 : avant, transparence
  et risque plafonnaient à 25 → max 90, et le front recomputait les barres depuis
  les verdicts → `52 ≠ 10+48`.)* Reste discutable : un bien transparent et peu
  risqué mais fortement sur-positionné plafonne vers 72/100 — sévérité du pilier
  prix à rediscuter avec la charte produit, mais désormais cohérente à la lecture.
- **Couverture maisons** : Bien'ici ne renvoie ~1% de maisons pour Metz
  intra-muros. Les sources HTML d'agences ajoutées (benedic, idemmo,
  immoheytienne) apportent une part bien plus élevée de maisons et de communes
  limitrophes — à confirmer dans la durée (volume par commune encore faible
  hors Metz).

### Ancrage local — limitations connues à optimiser
- **Temps de trajet réels — LIVRÉ EN PROD (2026-06-18).** En **mode adresse**, les
  facts POI (cathédrale / gare / Pompidou en `WALK`, échangeur A31 en `DRIVE`)
  affichent un **temps routé** via Google Routes API (`app/routing.py`,
  Compute Route Matrix) ; l'endpoint `POST /travel-times` couvre les modes à la
  demande (à pied / vélo / voiture / transports). Étiquetage honnête : jamais
  « à vol d'oiseau » sur un temps routé, jamais de minutes sur une distance.
  Limites restantes : (a) **sans `GOOGLE_MAPS_API_KEY` / sur échec réseau**, repli
  Haversine « à vol d'oiseau » par POI (le routing ne lève jamais) ; (b) le **mode
  quartier** (sans adresse) reste en distances approximatives ; (c) les **écoles**
  (volet D) restent en distance Haversine *par choix* (pas de minutes — anti fausse
  précision) ; (d) cache routing **mémoire seulement** (TTL 10 min, perdu au restart
  VM). Coût maîtrisé par le quota/jour Google (cap dur) + budget d'alerte.
- **POI échangeur A31 approximatif** : `_POI["a31"]` est un point unique approché ;
  un vrai calcul prendrait l'**accès autoroutier le plus proche** parmi plusieurs
  échangeurs (Metz-Nord, Metz-Centre, Metz-Sud), idéalement via routing.
- **Géocodage : cache mémoire seulement** (perdu au restart VM Fly), comme le LLM —
  à migrer vers SQLite/Redis. Et **dépendance à un service externe** (BAN) : si
  l'egress est bloqué, on reste en repli quartier sans le signaler à l'utilisateur
  (choix assumé : ne pas inquiéter ; à reconsidérer si la BAN tombe souvent).
- **Profils de quartier figés en dur** (`_PROFILES`, `_DIST_KM`) : distances au
  centroïde saisies à la main. À terme, dériver les distances de centroïdes
  géocodés plutôt que de valeurs manuelles.

### Côté technique
- `@app.on_event("startup")` est **déprécié** (FastAPI lifespan moderne).
  Fonctionne encore, à migrer.
- **Cache LLM en mémoire seulement** (perdu au restart de la VM Fly).
  Pas critique mais non optimal. Migrer vers Redis ou table SQLite.
- **Tests pytest** sous `backend/tests/` (feedback, scoring, smoke, llm_fallback,
  photo_evidence), exécutés en CI par `test.yml`. Isolation via `conftest.py`
  (base SQLite jetable, `OPENAI_API_KEY` factice, `init_db` session-scope, reset
  des caches mémoire). Couverture encore partielle — à étendre.
- **Évals LLM** sous `backend/evals/` (harnais anti-régression des corrections
  de prompt, spec `docs/specs/evals-harness-SPEC.md`) : suite **séparée et
  payante** (vrais appels OpenAI, ~0,01 €/run), jamais collectée par la suite
  gratuite (`backend/pytest.ini`, `testpaths = tests`). Invocation explicite :
  `python -m pytest evals -q -rxX` avec une vraie clé ; en CI via `evals.yml`
  (PR touchant `llm_semantic`/`analysis`/`market_stats`/`scoring`/`evals/`).
  Cas issue #80 : fix livré (2026-06-12, chantier fix-issue-80), tests de
  régression bloquants (plus aucun xfail) ; process d'ajout de cas :
  `docs/pilotes/README.md`.
- **Pas de monitoring** d'erreurs (pas de Sentry).
- **Filtre SSRF dans `url_fetch.py`** : volontairement minimal (refuse
  localhost / IP privées RFC1918 / scheme non http(s)). Ne résout pas le
  DNS pour valider l'IP réelle, donc partiellement contournable.

### Pistes d'optimisation / automatisation
- **Filtre zone par code postal** — *implémenté*. `postal_code` (5 chiffres) est
  capté à la collecte (`PropertyListing` + colonne `Comparable` + micro-migration)
  par bien'ici (`_extract_postal`, clés candidates + repli district) et laveine
  (le "(57530)" du libellé ville). À l'ingestion (`ingestion/save.py`,
  `IN_SCOPE_DEPARTMENT = "57"`) et en maintenance (`purged_dept`), un bien dont le
  code postal est **connu et hors dépt 57** est écarté ; un bien **sans** code
  postal est conservé (repli sur la blocklist de noms `OUT_OF_SCOPE_CITIES`).
  Étendre la capture aux agences HTML (benedic/idemmo/immoheytienne) au besoin ;
  ouvre la voie à un filtrage par secteur/agglo plus fin.

---

## 11bis. Prochaine session — roadmap produit (proposé, non implémenté)

Décidé en fin de session du 2026-06-04 après validation du pilier prix affiné.
Deux chantiers prioritaires, dans l'esprit « cohérence vs observable, pas
d'estimation » :

### A) Fusionner les sections d'actions (questions > affirmations) — FAIT (2026-06-04)
Anciennement 3 listes (`to_check`, `questions`, `negotiation_levers`) dont
`to_check`/`questions` redondants. Désormais **2 listes** :
- **« Questions à poser (vendeur / agent) »** = fusion `to_check`+`questions`,
  formulées en **questions**, dédupées (`_merge_unique`).
- **« Leviers de négociation »** = inchangé (intention distincte).
- Réalisé : `llm_semantic` (prompt → une seule liste `questions` + `negotiation`,
  `to_check` retiré du format/fallback/sortie), `analysis._amenity_actions`
  (items reformulés en questions ; renvoie `{questions, negotiation}`),
  `app/main.py` (schéma inchangé, `actions` reste `Dict[str, list]`), front
  (`page.tsx` : carte « À vérifier » supprimée, libellé questions mis à jour,
  `handleCopy`), `lib/api.ts`.

### B) Section « Ancrage local » — le différenciateur (pas de livre foncier)
Toute la valeur de l'app est le **positionnement local** ; faute de livre foncier,
la cohérence des **allégations locales** EST le produit. Trois couches :
- **Couche A — profil local de quartier (curaté, déterministe, factuel)** — FAIT
  (2026-06-04) : `app/metz_local.py` = dict quartier (clé canonique) → profil
  {distance approx. centre/cathédrale, gare Metz-Ville + Centre Pompidou-Metz
  (accolés), axe A31 + Luxembourg (attrait **frontalier**), caractère}. Exposé via
  `local_context(district, city)` (canonicalisation + aliases composés type
  `Plantieres-Queuleu`), branché dans `run_full_analysis` → champ `local_context`
  de la réponse, rendu en carte « Contexte local » **non-scorée** côté front
  (`LocalContextCard`). Distances volontairement approximatives (« ~ ») : pas de
  fausse précision. *Shippé sans géocodage.*
- **Couche B — allégations locales (LLM) + contrôle de cohérence** — FAIT
  (2026-06-04) : `llm_semantic` extrait `local_claims[]` (`{text, type}`, type ∈
  centre/cathedrale/gare/transport/commerces/nature/ecoles/calme/a31/autre) ;
  `metz_local.assess_claims()` les **confronte au profil du quartier** (distances
  numériques `_DIST_KM` + seuils déterministes) → statut `coherent` /
  `a_verifier` / `peu_plausible` + note (ex. « 'vue cathédrale' peu plausible
  depuis Borny, ~4,5 km du centre »). Branché dans `run_full_analysis` →
  `local_context.claims`, rendu sous la carte « Contexte local » (pastilles de
  statut). Cœur du positionnement : transformer le marketing en affirmations
  vérifiables. Prudence : on ne contredit que le géographiquement douteux ; le
  non-vérifiable reste « à vérifier », jamais « cohérent » par complaisance.
  Pour l'instant **non-scoré** (n'alimente pas encore risque/négo).
- **Champ adresse (alternative manuelle à la couche C)** — FAIT (2026-06-04) :
  `AnalyzeRequest.address` (optionnel). À défaut de géocodage, l'utilisateur peut
  saisir l'adresse (champ texte « Préciser », même esprit que le sélecteur de
  quartier). Effet : `_resolve_district` en tire le quartier (priorité juste
  après le sélecteur), ce qui débloque/affine contexte local + cohérence ;
  l'adresse est affichée (`local_context.address`). Hook pour la vraie couche C.
- **Couche C — géocodage adresse → distances exactes** — FAIT (2026-06-04) :
  `app/geocode.py` interroge la **Base Adresse Nationale** (api-adresse.data.gouv.fr,
  gratuite, sans clé) : adresse → `{lat, lon, score, label}`, avec cache mémoire,
  seuil de score (0.4), garde-fou département 57, et **repli silencieux** (None) sur
  erreur réseau / score faible / hors périmètre. `metz_local` calcule alors les
  distances exactes (Haversine) du bien aux POI curatés `_POI` (cathédrale,
  Pompidou, gare, échangeur A31) → `local_context_from_coords` (facts précis,
  `precision="adresse"`) et `claim_distances_from_coords` pour un contrôle de
  cohérence (couche B) au bien près. Sans adresse / si géocodage échoue → on retombe
  sur le profil de quartier (`precision="quartier"`). Front : note de bas de carte
  adaptée ("distances à vol d'oiseau depuis l'adresse").
  - **Prérequis infra** : la politique réseau de l'environnement doit autoriser
    l'**egress HTTPS vers `api-adresse.data.gouv.fr`** (sinon 403/timeout → repli
    quartier en continu). À vérifier sur Fly et sur Claude Code on the web.
- UI : section **non-scorée** (comme la carte prix), pas un 4e pilier
  (garde le score 40/30/30 stable + « pas de fausse précision »).

### Secteur « Metz métropole » — FAIT (2026-06-04)
Niveau **au-dessus de la ville** dans la cascade `market_stats` : `_METRO_CITIES`
(Metz + communes limitrophes : Montigny, Woippy, Marly, Le Ban-Saint-Martin,
Longeville, Saint-Julien, Scy-Chazelles, Plappeville, Lessy, Augny). La cascade
devient `quartier → secteur → ville → métropole` (× bande DPE). `_fetch_comparables`
accepte un ensemble de communes (`cities`). Règles : la **ville reste préférée dès
`MIN_COMPARABLES` (5)** — on n'élargit à la métropole que si la commune est trop
creuse (pas de dilution d'un pool communal exploitable) ; la métropole n'est
mobilisée que si le bien est **dans** le périmètre (sinon pas d'élargissement à des
communes étrangères, ex. Thionville → None). Scope `"metropole"` exposé au front
(badge), `refinable` gardé à Metz uniquement. Vérifié sur DB temporaire.

### Contexte local v2 — LIVRÉ EN PROD (2026-06-18)
Lot poussé en prod (PR #115 → `staging`, fix #117, promotion #116 → `main`).
Spec : `docs/specs/contexte-local-v2-SPEC.md`. Quatre volets, section toujours
**non-scorée** (40/30/30 intact) :
- **A** — retrait du fact générique « Axe A31 · Luxembourg » en **mode quartier**
  (aucune donnée propre à l'annonce ; le quartier passe de 3 à 2 facts).
- **B** — **Centre Pompidou-Metz** en fact distinct en mode adresse (4 facts POI :
  cathédrale, gare, Pompidou, échangeur A31 ; fin de la fusion `min(gare, pompidou)`).
- **C** — **temps de trajet réels** Google Routes (`app/routing.py` + endpoint
  `POST /travel-times`) — voir §3 (secret), §5 (endpoint) et §11 (limites). C'est
  l'« optimisation routing isochrone » jusqu'ici en dette.
- **D** — **distance aux écoles** les plus proches en mode adresse (`app/schools.py`
  + snapshot `app/data/schools_metz.json`, Annuaire Éducation Nationale, k-NN
  Haversine, 1 école/degré). = sous-chantier **C3** de l'issue #100. Facts factuels
  sans jugement de valeur ; le claim `ecoles` reste `A_VERIFIER`.
  - *Dette connue* : **régénération du snapshot écoles à automatiser** (aujourd'hui
    curaté/figé) ; egress vers `data.education.gouv.fr` requis pour le régénérer.

### Référentiel géographique (issue #100) — A / B / C1 / C3 FAIT, C2 TODO
Feuille de route actée le 2026-06-16 (analyse-chapeau
`docs/specs/issue-100-ANALYSE.md` §4/§8). Les paliers A, B, C1 et **C3** sont en
production ; le palier C a été **sous-découpé** en trois sous-chantiers. **Seul
C2 reste à faire** (ne pas l'oublier) :

- **A — extension manuelle du référentiel** (Sainte-Thérèse/Botanique + alias +
  garde-fou d'incertitude). ✅ EN PRODUCTION.
- **B — gazetteer unique** (`app/geo_gazetteer.py`, source unique dérivant
  `_KNOWN_LOCALITIES`, profils, secteurs, alias). ✅ EN PRODUCTION.
- **C1 — inter-communal & commune réelle.** ✅ EN PRODUCTION (2026-06-16, PR #110
  → `staging`, PR #111 → `main`). Un quartier à cheval (Botanique = Metz /
  Montigny-lès-Metz) réunit les comparables de ses deux communes au niveau
  quartier via une table curatée `intercommunal_districts()` ; `geocode_address`
  expose en plus `city`/`citycode` de la BAN. Aucun changement de contrat
  `/analyze`. Spec : `docs/specs/issue-100-C-SPEC.md`.
- **✅ C3 — POI écoles. EN PRODUCTION (2026-06-18)** via le lot « Contexte local
  v2 » (volet D ci-dessus) : snapshot **Annuaire de l'Éducation** versionné
  (`app/data/schools_metz.json`) + `app/schools.py` (k-NN Haversine, 1 école par
  degré), `facts[]` écoles en mode adresse, distance bien→école. Donnée factuelle
  sourçable, sans jugement « prisé ». Dette : régénération du snapshot à automatiser.
- **⬜ C2 — quartier réel par coordonnées (TODO, reporté).** Rattacher l'adresse
  géocodée à un quartier **réel** par point-in-polygon, remplir les `centroid` du
  gazetteer, alimenter `_resolve_district` depuis le géocode. Prérequis : mapping
  coordonnées→quartier (polygones), décision licence/source, garde-fou
  anti-fake-precision aux frontières. Borne dans `docs/specs/issue-100-C-SPEC.md` §1 OUT.

> Avis ROI consigné (2026-06-16, amendé 2026-06-18) : **C3 livré** ; **C2** reste
> **non prioritaire** pour le MVP (n'aide que les biens avec adresse saisie ;
> coût/risque polygones > gain immédiat). À relancer en atelier sur décision
> explicite du fondateur (GATE 1 ; questions ouvertes en `issue-100-ANALYSE.md` §8).

### Autres chantiers en attente
- Mapper les formes composées rares à un secteur (`_SECTORS_RAW`).
- Rééquilibrage `scoring.py` (sévérité pilier prix, cf. §11) ; migration
  `on_event`→lifespan ; cache LLM persistant ; tests pytest.

---

## 12. Conventions de code

- **Python 3.12** uniquement
- **Logging** structuré via `logging.getLogger(<module>)`. Niveau INFO par
  défaut (forcé dans `app/main.py` avec `basicConfig(level=INFO, force=True)`).
  Loggers nommés en prod : `mvp`, `analysis`, `market_stats`, `llm_semantic`,
  `url_fetch`, `scrapers.base`, `push_comparables`, `rate_limit` (9.9 ; n'émet
  jamais l'IP, message 429 agrégé sur `limit` seulement), `events` (9.10 ;
  n'émet jamais une valeur de dimension potentiellement sensible — au plus le
  `name` et des booléens de présence, jamais `referrer_domain`/`path`/IP).
- **Pas de commentaires "what"** dans le code. Commenter uniquement le "why"
  non-trivial (workaround, invariant caché, choix non-évident).
- **Pas d'emoji** dans le code, commits ou prompts LLM système, sauf demande
  explicite utilisateur.
- **Type hints** : on en ajoute volontiers dans les nouveaux modules (`db/`,
  `app/`, `scrapers/sources/`). On reste cohérent avec le style existant.

---

## 13. Commandes utiles

### Ops Fly (PowerShell)
Le deploy prod est **automatique** sur merge `main` touchant `backend/**`
(`deploy-backend.yml`). `fly deploy` ci-dessous n'est qu'un **override manuel**
(hotfix sans merge, rollback).
```powershell
fly status --app backend-frosty-sound-441-docker
fly logs --app backend-frosty-sound-441-docker
fly secrets list --app backend-frosty-sound-441-docker
fly deploy --app backend-frosty-sound-441-docker   # override manuel (sinon auto sur merge main)
fly volumes list --app backend-frosty-sound-441-docker
```

### Test direct du backend (PowerShell)
```powershell
# stats de la DB
Invoke-WebRequest `
  -Uri "https://backend-frosty-sound-441-docker.fly.dev/admin/comparables/stats" `
  -Headers @{"X-Admin-Token"="<token>"}

# analyse
$body = '{"url":"https://idemmo.fr/bien-immobilier/..."}'
Invoke-WebRequest -Uri "https://backend-frosty-sound-441-docker.fly.dev/analyze" `
  -Method POST -ContentType "application/json" -Body $body
```

### Collecte manuelle (local)
```bash
cd backend
python -m jobs.collect_metz
```

### Diagnostic Bien'ici
GitHub → Actions → "Diagnose Bien'ici scraper" → Run workflow

### Collecte prod (manuelle)
GitHub → Actions → "Collect comparables (Metz)" → Run workflow
(sinon, déclenchement auto chaque lundi 04:00 UTC)

---

## 14. Si tu touches au backend, lire d'abord

1. **Ce fichier** (CLAUDE.md) pour la cartographie technique courante
2. **`/CONTEXT.md`** à la racine pour le contexte stratégique et la roadmap
3. Les fichiers que tu vas modifier, **avant** de modifier (l'état réel
   change vite : ce CLAUDE.md est une carte, pas le terrain)

Ne jamais réintroduire les anti-patterns listés au §1.
Ne jamais commiter de secret en clair.

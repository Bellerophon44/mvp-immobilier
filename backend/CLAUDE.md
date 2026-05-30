# CLAUDE.md — backend mvp-immobilier

> Fichier de référence court à lire **avant toute modification du backend**.
> Pour le contexte stratégique, marketing, business et la roadmap, voir
> [`/CONTEXT.md`](../CONTEXT.md) à la racine du repo (source de vérité).
> Ce fichier-ci se concentre sur l'état technique courant du backend.
>
> **Dernière mise à jour :** 2026-06-02 (post-activation cron Bien'ici)

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
| CI | GitHub Actions (2 workflows, voir §9) |

⚠️ **Pas de Railway.** Toute documentation interne qui mentionne encore Railway
ou le port 8000 est périmée et doit être ignorée.

---

## 3. Secrets et variables d'environnement

| Variable | Où | Usage |
|---|---|---|
| `OPENAI_API_KEY` | `fly secrets` | Appel `gpt-4.1-mini` |
| `OPENAI_MODEL` (optionnel) | `fly secrets` | Par défaut `gpt-4.1-mini` |
| `ADMIN_TOKEN` | `fly secrets` **et** GitHub repo secret | Authentifie `POST /admin/comparables` |
| `DATABASE_PATH` | `fly.toml [env]` | `/data/comparables.db` |
| `CORS_ORIGINS` (optionnel) | env Fly | Par défaut : localhost + regex `*.vercel.app` |
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
│   ├── main.py             # FastAPI, CORS, /health, /, /analyze, /admin/comparables
│   ├── analysis.py         # Orchestrateur run_full_analysis
│   ├── llm_semantic.py     # gpt-4.1-mini, cache mémoire SHA-256 TTL 7j
│   ├── market_stats.py     # SQL comparables, fallback district, stats Q1/médiane/Q3
│   ├── scoring.py          # Score global 0-100 (40+30+30)
│   └── url_fetch.py        # GET URL annonce + extraction texte HTML, SSRF filter
├── db/
│   ├── models.py           # SQLAlchemy Comparable
│   └── session.py          # SessionLocal, init_db, DATABASE_PATH
├── ingestion/
│   └── save.py             # save_comparables(list[dict]) → DB (merge)
├── scrapers/
│   ├── base.py             # session HTTP UA Chrome, retry, normalize_price/surface,
│   │                       # infer_property_type, extract_district (Grand Metz)
│   ├── models.py           # @dataclass PropertyListing
│   ├── protocol.py         # ScraperProtocol
│   ├── registry.py         # @register(name), run_all() — pattern registre
│   ├── recon.py            # outil dev : recon HTML d'agences locales
│   ├── diag_bienici.py     # outil dev : diagnostic API Bien'ici
│   ├── site_local.py       # shim de rétrocompat — n'éditer plus, redirige vers sources/
│   └── sources/
│       ├── __init__.py
│       ├── bienici.py      # @register("bienici") — API JSON, zoneIdsByTypes
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
| GET | `/admin/comparables/stats` | `X-Admin-Token` | `{"total": n, "cities": [...]}` |
| POST | `/admin/comparables` | `X-Admin-Token` | Import batch (max 10000) |

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

---

## 6. Pipeline d'analyse (état réel)

```
POST /analyze
  └── run_full_analysis(raw_text)               ← app/analysis.py
        ├── analyze_semantic()                  ← app/llm_semantic.py → OpenAI gpt-4.1-mini
        │     retourne :
        │     - transparency_score (int 0-100)
        │     - verdict, summary, risk_level, risk_summary
        │     - to_check[], questions[], negotiation_levers[]
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

## 7. Modèle de données

`db/models.py` — table `comparables` :

```python
class Comparable(Base):
    id            = Column(String, primary_key=True)  # sha256(source:external_id)
    source        = Column(String, nullable=False)    # ex "bienici"
    city          = Column(String, nullable=False)    # normalisé (Casse-Titre)
    district      = Column(String, nullable=True)
    property_type = Column(String, nullable=False)    # "appartement" | "maison"
    surface_m2    = Column(Float, nullable=False)
    price_total   = Column(Float, nullable=False)
    price_m2      = Column(Float, nullable=False)
    collected_at  = Column(DateTime, default=datetime.utcnow)
```

État actuel en prod : **~900 comparables**, couverture Grand Metz (Metz +
~20 communes limitrophes), 98% appartements (Bien'ici intra-muros).

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

- Découverte dynamique de l'identifiant de zone via
  `https://res.bienici.com/suggest.json?q=<ville>` → renvoie `zoneIds`
  (ex. Metz = `["-450381"]`). C'est l'ID interne Bien'ici, **pas** l'INSEE.
- Endpoint annonces : `https://www.bienici.com/realEstateAds.json`
  avec `filterType=buy` + `zoneIdsByTypes.zoneIds`
- **Pagination** : 50/page, jusqu'à 20 pages = 1000 annonces brutes / run
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

### Outils dev (pas en prod)
- `scrapers/recon.py` : exécution locale pour ausculter une URL d'agence
  (statut, présence prix dans le HTML, classes CSS candidates, dump local
  dans `recon_dumps/`)
- `scrapers/diag_bienici.py` : suite de tests sur l'API Bien'ici (suggest
  endpoints, variantes de filtres) — exécutable via GitHub Action
  `diag-bienici.yml`

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
   - importe `scrapers.sources.bienici` et `scrapers.sources.site_local`
     pour déclencher leurs `@register`
   - appelle `run_all()` (collecte sur les runners GitHub, pas anti-bot)
   - batch de 1000 max et POST vers `/admin/comparables`
5. Le backend reçoit, appelle `ingestion/save.save_comparables` → écriture
   atomique sur le volume `/data`

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
exact (`global_score`, `verdict`, `confidence`, `pillars[]`, `actions{check,
questions, negotiation}`). Le frontend code en dur l'ordre des piliers
`[prix, transparence, risques]`.

---

## 11. Limitations connues et dette technique

### Côté produit / scoring
- **Pondération du score** : `scoring.py` donne 40 pts au pilier prix.
  Quand un bien est transparent, à faible risque, mais nettement sur-positionné,
  le score peut descendre jusqu'à 50/100 → verdict "Risque élevé", ce qui
  est trop sévère sémantiquement. À reprendre avec la charte produit.
- **Couverture maisons** : Bien'ici ne renvoie ~1% de maisons pour Metz
  intra-muros, donc le pilier prix sort souvent "Indéterminé" pour une
  maison. À élargir via ajout de zones (banlieue dortoir) ou source HTML
  dédiée.

### Côté technique
- `@app.on_event("startup")` est **déprécié** (FastAPI lifespan moderne).
  Fonctionne encore, à migrer.
- **Cache LLM en mémoire seulement** (perdu au restart de la VM Fly).
  Pas critique mais non optimal. Migrer vers Redis ou table SQLite.
- **Pas de tests automatisés** (pas de pytest). Vérification manuelle via
  Swagger.
- **Pas de monitoring** d'erreurs (pas de Sentry).
- **Filtre SSRF dans `url_fetch.py`** : volontairement minimal (refuse
  localhost / IP privées RFC1918 / scheme non http(s)). Ne résout pas le
  DNS pour valider l'IP réelle, donc partiellement contournable.

---

## 12. Conventions de code

- **Python 3.12** uniquement
- **Logging** structuré via `logging.getLogger(<module>)`. Niveau INFO par
  défaut (forcé dans `app/main.py` avec `basicConfig(level=INFO, force=True)`).
  Loggers nommés en prod : `mvp`, `analysis`, `market_stats`, `llm_semantic`,
  `url_fetch`, `scrapers.base`, `push_comparables`.
- **Pas de commentaires "what"** dans le code. Commenter uniquement le "why"
  non-trivial (workaround, invariant caché, choix non-évident).
- **Pas d'emoji** dans le code, commits ou prompts LLM système, sauf demande
  explicite utilisateur.
- **Type hints** : on en ajoute volontiers dans les nouveaux modules (`db/`,
  `app/`, `scrapers/sources/`). On reste cohérent avec le style existant.

---

## 13. Commandes utiles

### Ops Fly (PowerShell)
```powershell
fly status --app backend-frosty-sound-441-docker
fly logs --app backend-frosty-sound-441-docker
fly secrets list --app backend-frosty-sound-441-docker
fly deploy --app backend-frosty-sound-441-docker
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

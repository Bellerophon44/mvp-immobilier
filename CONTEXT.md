# Contexte — MVP Immobilier

Document de passation rassemblant le contexte produit, le diagnostic technique
et l'état réel du projet à la date du 2026-05-19.

---

## 1. Vision produit

MVP d'aide à l'**analyse de cohérence** d'annonces immobilières pour acheteurs particuliers.

Positionnement explicite :
- ❌ Pas d'estimation de prix
- ❌ Pas de DVF / notaires
- ❌ Pas de prédiction opaque
- ✅ Analyse de cohérence
- ✅ Appui sur données observables
- ✅ Résultats explicables, juridiquement prudents

Question à laquelle le produit répond :
> « Ce prix et cette annonce sont-ils cohérents avec ce que j'observe réellement
> sur le marché local, et quels points dois-je vérifier avant d'acheter ? »

---

## 2. Architecture cible

### Backend (`backend/`)
- **FastAPI**, endpoint unique `POST /analyze`
- Trois piliers d'analyse :
  1. **Sémantique IA** (`app/llm_semantic.py`) — transparence, risques, questions à poser, leviers de négociation, **extraction structurée** (ville, surface, prix)
  2. **Prix vs marché local** (`app/market_stats.py`) — médiane, Q1/Q3, dispersion, verdict relatif
  3. **Agrégation explicable** (`app/scoring.py`) — score 0–100 + verdict + niveau de confiance
- Orchestrateur : `app/analysis.py`
- **SQLite** (`db/`) pour cache des comparables, modèle `Comparable`
- **Scraping ciblé Metz/Moselle** (`scrapers/`, `jobs/collect_metz.py`)

### Frontend (`frontend/`)
- Next.js App Router déployé sur **Vercel**
- Une page : champ texte/URL → bouton « Analyser » → score + piliers + actions
- Appelle l'API via `NEXT_PUBLIC_API_URL`

### Infra
- Backend déployé sur **Fly.io** (région `cdg`), image Docker explicite
- App name : `backend-frosty-sound-441-docker`
- Volume Fly `comparables_data` monté sur `/data` pour la persistence SQLite

---

## 3. Historique du blocage initial

D'après le résumé Copilot reçu en entrée :
- Le déploiement Fly.io bouclait : machines créées puis redémarrées en boucle,
  app en statut `suspended`.
- Logs : `Preparing to run: /app/.venv/bin/fastapi run` + `Could not find a default file to run`.
- Copilot avait identifié comme cause racine les **buildpacks Paketo FastAPI**
  imposant `fastapi run` malgré `Procfile` / `fly.toml` / `FASTAPI_APP`.
- Solution préconisée par Copilot : **forcer un Dockerfile explicite** et
  recréer l'app Fly. Pas encore appliqué quand la conversation a démarré.

---

## 4. Diagnostic réel (Claude Code, 2026-05-19)

Le diagnostic initial de Copilot ciblait uniquement l'infra. **Plusieurs bugs
runtime cumulés** ont été trouvés en plus :

### 4.1 Infra / Fly.io
- **Port mismatch** : `Dockerfile` lançait uvicorn sur `8000`, `fly.toml`
  routait vers `internal_port = 8080` → healthcheck TCP échouait à chaque boot
  → boucle de redémarrage → suspension. C'était la cause directe persistante
  même *après* le passage en Dockerfile.
- `build = { }` vide dans `fly.toml` — inutile, supprimé.
- **Pas de healthcheck HTTP** dans `fly.toml`.
- **SQLite sur filesystem éphémère** : avec `auto_stop_machines = true`,
  la base était perdue à chaque arrêt de machine. Pas de volume monté.

### 4.2 Bugs runtime backend
- `app/analysis.py:16` appelait `compute_price_market_pillar(raw_text)` —
  mais la fonction attend 5 kwargs (`city`, `district`, `property_type`,
  `surface_m2`, `listing_price_m2`). **`TypeError` à chaque requête**.
  Il manquait toute la couche d'**extraction structurée** entre le texte
  brut et le pilier prix.
- `app/llm_semantic.py:122` faisait `USER_PROMPT_TEMPLATE.format(raw_text=...)`
  sur un template contenant des accolades JSON `{ "transparency_score": ... }`
  non échappées → `KeyError` systématique → chaque appel partait dans le
  `except` et retournait le fallback générique. L'IA n'était jamais vraiment
  appelée.
- `client.responses.create(...)` mélangeait la nouvelle Responses API et le
  paramètre `response_format` de l'ancienne Chat Completions API.
  `response.output_parsed` n'existe que pour `responses.parse()`, pas
  `responses.create()`. Double échec.

### 4.3 Manques côté API
- `init_db()` jamais appelé au démarrage → première requête sur table
  inexistante.
- **Pas de `CORSMiddleware`** → le front Vercel bloqué par le navigateur.
- Pas de route `/health` ni `/` — healthchecks Fly impossibles.

### 4.4 Hygiène
- Pas de `.dockerignore` (le `COPY . .` embarquait `.git`, venvs, etc.).
- `requirements.txt` sans versions, `uvicorn` redondant avec `fastapi[standard]`.

---

## 5. Correctifs appliqués

Branche : `claude/analyze-mvp-immobilier-vtne5`
Commits poussés sur le remote :

| SHA | Message |
|---|---|
| `d214b5d` | Fix backend runtime bugs and Fly.io deployment |
| `2b3fb6d` | Expand .gitignore to exclude __pycache__, venvs, env files, local DBs |

### Détail des modifications

| Fichier | Nature | Correctif |
|---|---|---|
| `backend/Dockerfile` | modifié | uvicorn sur **8080** (aligné fly.toml), `PYTHONUNBUFFERED=1`, `EXPOSE 8080` |
| `backend/fly.toml` | modifié | suppression `build = {}`, ajout `[[http_service.checks]]` sur `/health`, **volume `/data`**, env `DATABASE_PATH` |
| `backend/.dockerignore` | **nouveau** | exclut `.git`, venv, `__pycache__`, `*.db`, `.claude` |
| `backend/requirements.txt` | modifié | `uvicorn[standard]`, `openai>=1.50` |
| `backend/db/session.py` | modifié | chemin DB via `DATABASE_PATH` (env var), création auto du dossier parent |
| `backend/app/main.py` | modifié | `CORSMiddleware` (regex `*.vercel.app`), routes `/health` et `/`, `init_db()` au `startup` |
| `backend/app/llm_semantic.py` | modifié | accolades JSON échappées, passage à `chat.completions.create` + `json.loads`, **extraction structurée `listing` (city/district/property_type/surface_m2/price_total)**, coercion de types, fallback enrichi |
| `backend/app/analysis.py` | modifié | nouvel adaptateur `_price_pillar_from_listing` qui appelle `compute_price_market_pillar` avec les bons kwargs ; "Indéterminé" si extraction insuffisante |
| `.gitignore` | modifié | exclut `__pycache__/`, venvs, env files, `*.db` |

### Vérifications faites
- Syntaxe Python OK sur les 11 fichiers du backend.
- `from app.main import app` charge sans erreur, expose `/health`, `/`, `/analyze`, `/docs`.
- `init_db()` crée la table `comparables` à la cible `DATABASE_PATH`.
- Pipeline `run_full_analysis` testée bout-en-bout en mockant le LLM : score
  cohérent, pilier prix bascule en "Indéterminé" tant que la DB est vide
  (comportement attendu).

---

## 6. État actuel

| Élément | État |
|---|---|
| Conception produit | ✅ aboutie |
| Backend (logique) | ✅ corrigé et testé en local |
| Frontend | ✅ déployé sur Vercel (état hérité) |
| Bugs runtime backend | ✅ corrigés |
| Conflit buildpacks Fly | ✅ contourné par Dockerfile explicite |
| Push branche corrective | ✅ `claude/analyze-mvp-immobilier-vtne5` à jour sur le remote |
| Déploiement Fly.io | ⏳ à relancer avec la branche corrigée |
| Volume Fly | ⏳ à créer (`comparables_data`) |
| Secret `OPENAI_API_KEY` | ⏳ à définir sur Fly |
| Collecte comparables Metz | ⏳ jamais exécutée (DB vide en prod) |
| Tests bout-en-bout sur annonces réelles | ⏳ à faire après déploiement |

---

## 7. Checklist post-correctifs

### Priorité 1 — Déploiement
```bash
cd backend
# Côté Fly, une fois sur la branche claude/analyze-mvp-immobilier-vtne5
fly volumes create comparables_data --size 1 --region cdg
fly secrets set OPENAI_API_KEY=sk-...
fly deploy
curl https://backend-frosty-sound-441-docker.fly.dev/health  # doit renvoyer {"status":"ok"}
```

### Priorité 2 — Données
- Lancer `python -m jobs.collect_metz` (depuis `backend/`) une première fois
  pour peupler la base de comparables.
- ⚠️ Vérifier d'abord les sélecteurs CSS dans `scrapers/site_local.py:72`
  (`.property-card`, `.price`, `.surface`) — ils sont marqués "à adapter" et
  ne correspondent probablement pas au DOM réel du site cible (`laveine.immo`).
- Décider du modèle d'alimentation continue : cron Fly ? GitHub Action ?

### Priorité 3 — Frontend
- Mettre à jour `NEXT_PUBLIC_API_URL` sur Vercel vers la nouvelle URL Fly.
- Tester l'appel `POST /analyze` end-to-end depuis le front.

### Priorité 4 — Produit
- Tester 5–10 annonces réelles pour valider la qualité de l'extraction LLM
  (les champs `listing.city/surface_m2/price_total` doivent être fiables).
- Ajuster wording UX et textes légaux.
- Décider : continuer scraping ou passer à une API payante de données marché.

---

## 8. Points d'attention / dette technique

- **Cache LLM en mémoire uniquement** (`_CACHE` dict) — perdu à chaque restart
  de machine Fly. Pour un MVP c'est OK, mais à migrer vers Redis/disque si
  trafic récurrent.
- **`@app.on_event("startup")` est déprécié** dans les FastAPI récents au
  profit du `lifespan` context manager. Fonctionne encore mais émet un warning.
- **`CORS_ORIGINS` par défaut** autorise tout `*.vercel.app` via regex —
  à restreindre au domaine de prod du front une fois connu.
- **Scrapers** : sélecteurs CSS placeholders, à valider sur le vrai DOM.
  Aussi, respecter robots.txt et fréquence raisonnable.
- **Pas de tests automatisés** dans le repo — seules des vérifications
  manuelles ont été faites. À ajouter (pytest, au minimum pour `analysis.py`
  et `scoring.py`).

---

## 9. Référentiel fichiers

```
backend/
├── Dockerfile              # corrigé
├── fly.toml                # corrigé (volume, healthcheck, port 8080)
├── .dockerignore           # nouveau
├── requirements.txt        # ajusté
├── app/
│   ├── __init__.py
│   ├── main.py             # CORS + /health + startup init_db
│   ├── analysis.py         # adaptateur listing → pilier prix
│   ├── llm_semantic.py     # OpenAI correct + extraction structurée
│   ├── market_stats.py     # inchangé
│   └── scoring.py          # inchangé
├── db/
│   ├── models.py           # inchangé
│   └── session.py          # DATABASE_PATH configurable
├── ingestion/
│   └── save.py             # inchangé
├── scrapers/
│   ├── base.py             # inchangé
│   └── site_local.py       # ⚠️ sélecteurs à valider
└── jobs/
    └── collect_metz.py     # inchangé
```

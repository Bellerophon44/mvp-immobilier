# CLAUDE.md — mvp-immobilier

> Fichier de référence pour Claude Code. Lit ce fichier en entier avant de toucher au code.

---

## 1. Vision produit — ce que c'est et ce que ce n'est PAS

Ce projet est un **analyseur de cohérence d'annonces immobilières** à destination d'acheteurs particuliers.

| Ce que le produit fait ✅ | Ce que le produit ne fait PAS ❌ |
|---|---|
| Analyse sémantique du texte de l'annonce | Estimation de prix |
| Compare le prix au marché local **observable** | Consultation DVF / bases notaires |
| Produit un score explicable (0–100) | Prédiction opaque ou scoring "boîte noire" |
| Pose des questions utiles à l'acheteur | Distribution ou réagrégation d'annonces |
| Identifie des leviers de négociation | Avis juridique ou financier |

**Promesse utilisateur :** *"Ce prix et cette annonce sont-ils cohérents avec ce que j'observe réellement sur le marché local, et quels points dois-je vérifier avant d'acheter ?"*

---

## 2. Architecture générale

### Backend (ce repo)

```
POST /analyze
    └── run_full_analysis(raw_text)           ← app/analysis.py
            ├── analyze_semantic()            ← app/llm_semantic.py  → OpenAI gpt-4.1-mini
            ├── compute_price_market_pillar() ← app/market_stats.py  → SQLite comparables.db
            └── compute_global_score()        ← app/scoring.py
```

**Flux de collecte de données (batch, indépendant de l'API) :**

```
jobs/collect_metz.py
    └── scrape_site_local_metz()   ← scrapers/site_local.py
            └── fetch_page()       ← scrapers/base.py  → requests HTTP
    └── save_comparables()         ← ingestion/save.py → SQLAlchemy → comparables.db
```

### Frontend (repo séparé, Vercel)

Next.js App Router, une seule page :
- Champ texte (texte brut de l'annonce ou URL)
- Bouton "Analyser"
- Affichage du score + 3 piliers + actions concrètes

La communication avec le backend se fait via `NEXT_PUBLIC_API_URL` pointant vers l'URL Railway.

---

## 3. Infrastructure de déploiement

| Élément | Valeur |
|---|---|
| Plateforme backend | **Railway** (Docker explicite) |
| Image Docker | `FROM python:3.12-slim` |
| Commande de démarrage | `uvicorn app.main:app --host 0.0.0.0 --port 8000` |
| Variable d'env requise | `OPENAI_API_KEY` |
| Base de données | SQLite locale `comparables.db` (créée automatiquement au démarrage via `init_db()`) |
| Plateforme frontend | Vercel (Next.js) |

> ⚠️ Un fichier `fly.toml` est présent dans le repo — c'est un **vestige d'une tentative Fly.io avortée**. Il ne doit pas être utilisé et peut être ignoré ou supprimé.

Le `Dockerfile` est la seule source de vérité pour le déploiement. Ne jamais revenir à un buildpack ou à `fastapi run`.

---

## 4. État exact de chaque fichier

### ✅ Fichiers complets et fonctionnels

| Fichier | Rôle |
|---|---|
| `app/main.py` | FastAPI entry point, route `POST /analyze`, CORS |
| `app/analysis.py` | Orchestrateur — appelle les 3 piliers et assemble la réponse |
| `app/llm_semantic.py` | Analyse IA via OpenAI, cache mémoire SHA-256 TTL 7j |
| `db/models.py` | Modèle SQLAlchemy `Comparable` |
| `db/session.py` | Engine SQLite, `SessionLocal`, `init_db()` |
| `scrapers/site_local.py` | Scraper Metz ciblé (laveine.immo) |
| `ingestion/save.py` | Upsert SQLAlchemy des comparables |
| `jobs/collect_metz.py` | Script batch de collecte — à lancer manuellement |

### ⚠️ Fichiers tronqués — À COMPLÉTER EN PRIORITÉ

#### `app/market_stats.py`
- **Présent :** requête SQLite, calcul Q1/médiane/Q3, verdicts de positionnement, indice de confiance
- **Manquant :** la fonction `compute_price_market_pillar(raw_text)` — c'est cette fonction qu'`analysis.py` appelle. Elle doit :
  1. Parser le texte brut de l'annonce (regex) pour en extraire : prix, surface, ville, quartier (optionnel), type de bien
  2. Appeler les fonctions de calcul statistique déjà présentes dans le fichier
  3. Retourner un dict avec au minimum : `median_price_m2`, `position_verdict`, `confidence`, `comparables_count`, `q1`, `q3`
  4. Retourner `None` ou un dict avec `insufficient_data: True` si moins de 3 comparables

#### `app/scoring.py`
- **Présent :** scoring du pilier prix (40 pts max) : aligné→35, modéré→25, fort→10, sous-positionné→30
- **Manquant :**
  - Scoring du pilier sémantique (60 pts max) basé sur `verdict` (BON/MOYEN/MAUVAIS) et `risk_level` (FAIBLE/MODÉRÉ/ÉLEVÉ) retournés par `llm_semantic.py`
  - Calcul du verdict final (`Favorable`, `À creuser`, `Prudence`, `Déconseillé`)
  - `return {"score": ..., "verdict": ..., "confidence": ...}`

#### `scrapers/base.py`
- **Présent :** `fetch_page(url)` — GET avec User-Agent custom, timeout 10s
- **Manquant :**
  - Corps de `generate_stable_id(source, external_id)` : doit retourner `hashlib.sha256(f"{source}:{external_id}".encode()).hexdigest()`
  - `normalize_price(raw)` : extrait le float d'une chaîne type `"250 000 €"` ou `"250000€"`
  - `normalize_surface(raw)` : extrait le float d'une chaîne type `"68 m²"` ou `"68m2"`

---

## 5. Détails des modules — comportement attendu

### `app/llm_semantic.py`

- Modèle : `gpt-4.1-mini`, temperature 0.2, `response_format: {"type": "json_object"}`
- Cache mémoire en dict Python, clé = SHA-256 du texte normalisé (strip + lowercase), TTL = 7 jours
- **Retourne un dict avec ces clés exactes** (utilisées par `scoring.py` et `analysis.py`) :
  ```python
  {
    "verdict": "BON" | "MOYEN" | "MAUVAIS",
    "summary": str,
    "risk_level": "FAIBLE" | "MODÉRÉ" | "ÉLEVÉ",
    "risk_summary": str,
    "to_check": [str, ...],       # points à vérifier avant achat
    "questions": [str, ...],      # questions à poser au vendeur/agent
    "negotiation_levers": [str, ...]
  }
  ```

### `app/market_stats.py`

- Scope géographique MVP : **Metz / Moselle uniquement**
- Requête SQLite : biens de même `city`, même `property_type`, surface dans un intervalle ±20%
- Seuil minimum : **3 comparables** pour produire un résultat
- Verdicts de positionnement (basés sur écart entre prix annoncé et médiane) :
  - `"Plutôt aligné"` : écart ≤ ±10%
  - `"Légèrement sur-positionné"` : +10% à +25%
  - `"Fortement sur-positionné"` : >+25%
  - `"Sous-positionné"` : <-10%
- Indice de confiance :
  - `"Élevée"` : ≥10 comparables ET dispersion <800€/m²
  - `"Moyenne"` : ≥4 comparables
  - `"Faible"` : 3 comparables ou dispersion élevée

### `app/scoring.py`

Score total sur 100, deux piliers :

| Pilier | Poids | Critères |
|---|---|---|
| Prix vs marché | 40 pts | aligné→35, légèrement sur→25, fortement sur→10, sous→30 |
| Sémantique IA | 60 pts | combinaison verdict × risk_level (grille à définir) |

Verdict final suggéré (à adapter selon les seuils retenus) :
- 75–100 → `"Favorable"`
- 55–74 → `"À creuser"`
- 35–54 → `"Prudence"`
- 0–34 → `"Déconseillé"`

---

## 6. Corrections déjà appliquées (ne pas revenir en arrière)

Ces bugs ont été corrigés lors d'une session précédente avec Claude Code :

1. **`app/main.py`** — backticks `` ` `` parasites ligne 68 → `SyntaxError` → **supprimés**
2. **`app/analysis.py`** — backticks `` ` `` parasites ligne 58 → `SyntaxError` → **supprimés**
3. **`app/llm_semantic.py`** — fichier tronqué à la ligne 45 → `IndentationError` → **fichier complété intégralement**

Ces trois corrections permettent au serveur de **démarrer**. Mais le premier appel à `POST /analyze` échouera encore en runtime car `compute_price_market_pillar` et le `return` de `compute_global_score` sont manquants.

---

## 7. Ordre des priorités pour la prochaine session

### Priorité 1 — Compléter le backend (blocage runtime)

1. **Compléter `app/market_stats.py`** — écrire `compute_price_market_pillar(raw_text)` :
   - Parser prix, surface, ville, quartier, type avec regex
   - Appeler les fonctions statistiques déjà présentes
   - Gérer le cas `None` (données insuffisantes)

2. **Compléter `app/scoring.py`** — écrire le scoring sémantique + le `return` final de `compute_global_score()`

3. **Compléter `scrapers/base.py`** — corps de `generate_stable_id`, `normalize_price`, `normalize_surface`

4. **Tester l'endpoint end-to-end** avec un texte d'annonce réel (voir exemple ci-dessous)

### Priorité 2 — Peupler la base de données

5. **Lancer `jobs/collect_metz.py`** pour peupler `comparables.db` — sans cela, `compute_price_market_pillar` retournera systématiquement "données insuffisantes"

### Priorité 3 — Produit (après backend opérationnel)

6. Tester 5–10 annonces réelles, ajuster les seuils de scoring
7. Ajouter le wording légal dans le frontend
8. Décider : scraping continu vs API payante pour les données marché

---

## 8. Exemple de texte d'annonce pour les tests

```
Appartement T3 de 68m² à Metz-Sablon, 3ème étage sans ascenseur.
Séjour 25m², 2 chambres, cuisine équipée, cave. Chauffage collectif gaz.
DPE D. Prix : 189 000 € FAI. Libre de suite. Copropriété de 24 lots,
charges 180€/mois. Pas de travaux votés.
```

Ce texte doit permettre de tester le parsing regex dans `compute_price_market_pillar` :
- Prix : 189 000 €
- Surface : 68 m²
- Ville : Metz
- Quartier : Sablon
- Type : appartement

---

## 9. Conventions du projet

- **Python 3.12**
- **Pas de type hints stricts** dans les fichiers existants — rester cohérent avec le style présent
- **Logging** : utiliser `print()` ou `logging` simple, pas de framework de logs complexe
- **Pas de migrations** : SQLite est recréé via `init_db()` au démarrage si absent
- **Pas de tests automatisés** actuellement — valider manuellement via `/docs` (Swagger) et curl
- **Pas de `.env`** en local : la variable `OPENAI_API_KEY` est injectée par Railway en production
- **`fly.toml` présent** dans le repo : ignorer, ne pas modifier, peut être supprimé proprement

---

## 10. Variables d'environnement requises

| Variable | Où | Usage |
|---|---|---|
| `OPENAI_API_KEY` | Railway (backend) | Appels GPT-4.1-mini dans `llm_semantic.py` |
| `NEXT_PUBLIC_API_URL` | Vercel (frontend) | URL Railway du backend, ex: `https://mvp-immobilier.up.railway.app` |

---

## 11. Rappel — ce qui a été validé par simulation

Une simulation complète bout-en-bout a été réalisée sur une vraie annonce Leboncoin avec les résultats suivants, qui définissent le comportement cible du produit :

- **Score** : ~65/100
- **Verdict** : "À creuser"
- **Positionnement prix** : "Légèrement sur-positionné"
- **Transparence** : "Bonne"
- **Risques** : "Modérés"
- **Questions générées** : pertinentes et actionnables

Ces valeurs servent de référence pour valider que les fonctions manquantes une fois écrites produisent des résultats dans le bon ordre de grandeur.

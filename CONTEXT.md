# Contexte projet — MVP Immobilier

> Document de contexte exhaustif destiné à être lu par une IA (Claude Code,
> agents, workflows) avant toute action sur le projet. Couvre la stratégie,
> le produit, la technique, l'opérationnel et les opportunités d'automatisation.
>
> **Dernière mise à jour :** 2026-06-04 — pilier prix affiné + collecte bien'ici
> repensée. **⚠️ Les sections 4 à 7 et 10 ci-dessous sont partiellement
> historiques** (rédigées en mai) ; l'état réel à jour est résumé en **§0** et,
> côté technique fin, dans [`backend/CLAUDE.md`](backend/CLAUDE.md) (source de
> vérité technique). La vision (§1-3) et les anti-patterns (§11) restent valides.

---

## 0. État actuel (2026-06-04) — snapshot de vérité

### Stack réelle
- **Backend** : Python 3.12, FastAPI sur **Fly.io** (`backend-frosty-sound-441-docker`,
  région cdg, Docker explicite, volume SQLite `/data`, auto-stop). **Pas de Railway.**
- **Frontend** : **Next.js 16** App Router sur Vercel, design system « Cohérence »
  (palette ink/parchment/brick/moss/ochre, fonts Instrument Serif/Geist), composants
  sous `frontend/components/design/`. **Pas l'UI bleue de transition décrite en §2.3.**
- **CI** : 3 GitHub Actions — `collect.yml` (collecte hebdo lundi 04:00 + manuel),
  `diagnose-scrapers.yml` (sur PR touchant les scrapers → commentaire de diagnostic),
  `deploy-backend.yml` (deploy Fly sur merge `main`).
- **Branche de dev courante** : `claude/clever-gates-xXqfp` (l'ancienne
  `claude/analyze-mvp-immobilier-vtne5` est périmée).

### Données & pilier prix (le gros du travail récent)
- **5 scrapers** réels et actifs : `bienici` (API JSON, **balayage par tranches de
  surface**), `benedic`, `idemmo`, `immoheytienne`, `laveine_immo` (HTML).
- Base prod **~17,7k comparables** (vs « DB vide » en §4.3, désormais faux), toutes
  tailles, ~2,6k maisons. DPE ~82 % / année ~37 % / étage-ascenseur ~60 % / code
  postal ~100 % (bien'ici).
- Le **pilier « Prix vs marché »** fonctionne : cascade
  `quartier → secteur → ville` (×bande DPE), fenêtre surface ±20 %, quartiles,
  filtre périmètre par **code postal (dépt 57)**, signal explicatif non-estimatif
  (DPE/époque/étage/terrasse…). Front : **sélecteur de quartier** + **chip de
  périmètre dynamique**.
- Chantiers livrés cette session : époque resserrée, périmètre structuré + badge,
  filtre code postal, sélecteur de quartier, **critères de confort** (étage,
  ascenseur, terrasse, copro, charges, cave, parking, chambres), **cascade
  secteurs**, correctif UX d'affinage, **collecte bien'ici par tranches de surface**
  (cause racine d'un pool biaisé petites surfaces) + robustesse collecte.

### Roadmap (détaillée dans `backend/CLAUDE.md` §11bis)
1. **Fusionner les actions** — FAIT : une liste de **questions** (vendeur/agent) +
   leviers de négo.
2. **Section « Ancrage local »** (différenciateur, faute de livre foncier) — FAIT :
   profil local curaté par quartier (gare, A31/Luxembourg frontaliers, cathédrale,
   Pompidou) ; extraction des **allégations locales** de l'annonce + **contrôle de
   cohérence** géographique (couche B) ; **géocodage de l'adresse** (BAN) pour des
   distances exactes au bien, avec repli quartier (couche C). Section non-scorée.
   - *Limite à optimiser* : distances **à vol d'oiseau**, pas un temps de trajet
     réel (« 3 min à vol d'oiseau » ≠ « 7 min à pied » de la cathédrale ou « 12 min
     en voiture » de l'A31). Brancher un routing isochrone plus tard.
3. **Prochaines étapes** : faire peser la cohérence (couche B) sur le pilier risques ;
   routing temps de trajet ; secteur « Metz métropole » (communes limitrophes) ;
   rééquilibrage scoring ; dette (lifespan, cache LLM/géocodage persistant, tests).

---

## 1. Vision et objectifs stratégiques

### 1.1 Promesse produit
> *« Ce prix et cette annonce sont-ils cohérents avec ce que j'observe réellement
> sur le marché local, et quels points dois-je vérifier avant d'acheter ? »*

### 1.2 Positionnement (contre-positionné face aux acteurs existants)

| Ce que le produit fait | Ce qu'il refuse explicitement de faire |
|---|---|
| Analyser la **cohérence** d'une annonce | Estimer un prix de vente |
| S'appuyer sur des **données observables** | Utiliser DVF ou bases notariales |
| Fournir des résultats **explicables** | Faire de la prédiction opaque |
| Rester **juridiquement prudent** | Donner du conseil juridique |

### 1.3 Cible utilisateur
- **Acheteur particulier**, première transaction ou peu expérimenté
- Se sent perdu face à la complexité du marché et à l'asymétrie d'information vendeur/acheteur
- Veut un **second avis lucide**, pas un robot qui dit "c'est cher / pas cher"

### 1.4 Différenciation
- **Explicabilité maximale** : aucune réponse sans justification sourcée
- **Tone factuel et rassurant**, pas commercial
- **Pas de fake precision** : le pilier "Prix vs marché" répond "Indéterminé" plutôt que d'inventer un chiffre quand les données manquent
- **MVP volontairement étroit** géographiquement (Metz/Moselle au démarrage)

---

## 2. Stratégie marketing et UX

### 2.1 Tonalité de communication
- Pédagogique sans être condescendant
- Prudent et neutre, jamais alarmiste ni vendeur
- Vocabulaire concret ("annonce", "vendeur", "visite") plutôt que jargon
- Toujours dire ce qu'on ne sait pas plutôt que d'inventer

### 2.2 Wording de référence (en prod actuellement)
- **Titre hero** : *« Avant d'acheter, faites lire l'annonce par un œil neuf. »*
- **Sous-titre** : *« Une analyse en clair de ce que l'annonce dit, de ce qu'elle ne dit pas, et des bonnes questions à poser au vendeur. »*
- **CTA principal** : *« Analyser cette annonce »*
- **Disclaimer** (bas de page) : *« Cette analyse est un outil d'aide à la décision. Elle ne remplace pas l'avis d'un professionnel et ne constitue pas une estimation de prix. »*
- **Groupes d'actions** : "À vérifier avant de visiter" / "Questions à poser au vendeur" / "Arguments pour négocier"

### 2.3 Identité visuelle (état actuel = palette de transition pour tests)
- Background neutre chaud `#faf9f7`
- Accent `#2563eb` (bleu de confiance, sobre)
- Système de fonts natif (`-apple-system, BlinkMacSystemFont, "Segoe UI"...`)
- Coins arrondis 12-20px
- Score visualisé en anneau conique CSS, couleur dépendant du score band
- ⚠️ **La charte graphique définitive est à concevoir avec un agent Claude design.** L'UI actuelle est une étape test, pas finale.

### 2.4 Hypothèses d'acquisition (non validées, à tester)
- Bouche-à-oreille initial (cercles immédiats)
- SEO long tail sur questions d'acheteur ("comment savoir si une annonce est honnête", "questions à poser à un vendeur immobilier")
- Partenariats locaux (notaires, courtiers, associations de consommateurs) en B2B2C
- Contenu utile en marque blanche (template de checklist, etc.)

---

## 3. Modèle économique

### 3.1 État actuel
- **MVP gratuit**, phase de test utilisateurs
- Aucune monétisation activée
- Coûts opérationnels couverts en personnel par le founder

### 3.2 Structure de coûts unitaires

| Poste | Coût mesuré / estimé | Notes |
|---|---|---|
| Fly.io (1 VM 1Go RAM, cdg, auto-stop) | ~0-5 €/mois | Auto-stop quand idle, payé à la consommation |
| Vercel (Next.js front) | 0 € | Free tier, suffisant pour MVP |
| OpenAI `gpt-4.1-mini` | ~0,001 € / analyse | Cache LLM (in-memory) réduit les coûts en cas de tests répétés |
| Fly volume SQLite (1 Go) | ~0,15 €/mois | |
| Domaine custom | non acquis | Fly fournit `*.fly.dev`, Vercel `*.vercel.app` |
| **Coût marginal d'une analyse** | **~0,001 €** | Tient sur du `gpt-4.1-mini` |
| **Coût fixe mensuel actuel** | **< 1 €** | Sans usage récurrent |

### 3.3 Sécurités financières en place
- ⚠️ **Recommandation** : configurer un **usage limit OpenAI mensuel** (5-10 €) sur `platform.openai.com → Settings → Limits` pour éviter une surprise si l'app prend du trafic ou subit du scraping malveillant.
- Fly auto-stop = pas de facture qui dérape.

### 3.4 Pistes de monétisation à explorer (post-tests)

| Modèle | Cible | Hypothèse de prix | Maturité |
|---|---|---|---|
| **Freemium** : N analyses/mois gratuites, illimité payant | Acheteurs sérieux | 5-10 €/mois | À tester après validation produit |
| **B2B agences** : white-label de l'outil pour leurs prospects | Agences locales | 50-200 €/mois | À explorer après preuve d'usage |
| **B2B courtiers/banques** : intégration dans le parcours prêt | Pros du financement | API métier facturée | Plus long terme |
| **B2B notaires / consommateurs** : marque blanche associative | Associations de défense des acheteurs | Sponsoring / forfait | À explorer |
| **Premium fonctionnel** : alertes / dossier d'achat / suivi | Acheteurs actifs | 10-20 € one-shot | Modèle simple, testable rapidement |

---

## 4. Périmètre fonctionnel actuel (état exact)

### 4.1 Parcours utilisateur en production
1. L'utilisateur arrive sur l'URL Vercel
2. Colle dans un textarea soit le texte d'une annonce, soit son URL
3. Clique "Analyser cette annonce"
4. Si URL : le backend la fetch et extrait le texte ; si texte : utilisé directement
5. Le texte est envoyé à OpenAI (`gpt-4.1-mini`) qui retourne en JSON structuré :
   - Score de transparence (0-100)
   - Verdict transparence + risques
   - Listes : à vérifier, questions, leviers de négociation
   - Extraction structurée : `city`, `district`, `property_type`, `surface_m2`, `price_total`
6. Si l'extraction permet de calculer un `price_m2`, on cherche en DB des comparables → pilier "Prix vs marché"
7. Le score global est calculé par `scoring.py` (40 pts prix + 30 pts transparence + 30 pts risques)
8. Le frontend affiche : score (anneau coloré) + 3 cartes piliers + 3 listes d'actions + bouton "Analyser une autre annonce"

### 4.2 Endpoints backend (Fly.io)
- **`GET /health`** → `{"status":"ok"}` — utilisé par Fly healthcheck
- **`GET /`** → `{"service":"mvp-immobilier","docs":"/docs"}`
- **`GET /docs`** → Swagger UI (FastAPI)
- **`POST /analyze`** → body `{"raw_text"?: str, "url"?: str}` → réponse `AnalyzeResponse`
  - 200 : `global_score`, `verdict`, `confidence`, `pillars[]`, `actions{check,questions,negotiation}`
  - 400 : ni `raw_text` ni `url` fournis
  - 422 : URL fournie mais site inaccessible / contenu vide
  - 500 : erreur inattendue (loguée)

### 4.3 Limitations connues
- **Anti-bot des grands portails** : Leboncoin, SeLoger, Bien'ici renvoient des pages JS-only ou bloquent les requêtes non-navigateur. Les "petits sites" (idemmo.fr, agences locales) marchent bien (testé OK sur idemmo.fr → 200 OK + 202 Ko HTML → 2280 chars extraits).
- **DB comparables vide** : le pilier "Prix vs marché local" répond systématiquement "Indéterminé". Le scraper Metz a des sélecteurs CSS placeholders à adapter.
- **Cache LLM en mémoire** (perdu au restart machine Fly).
- **`@app.on_event("startup")`** déprécié, à migrer vers lifespan ultérieurement.
- **Pas de tests automatisés**.
- **Pas de monitoring** d'erreurs (Sentry / Logflare) ni d'analytics utilisateur.

---

## 5. Architecture technique

### 5.1 Stack
- **Backend** : Python 3.12, FastAPI, uvicorn, SQLAlchemy + SQLite, BeautifulSoup 4, OpenAI SDK
- **Frontend** : Next.js 14 (App Router), React 18, TypeScript, CSS vanilla (pas de Tailwind ni lib UI)
- **Infra** : Fly.io (Docker explicite), Vercel (frontend)
- **CI/CD** : `deploy-backend.yml` redéploie **automatiquement** Fly sur tout merge `main` touchant `backend/**` (+ `workflow_dispatch` manuel) ; Vercel auto-deploy le frontend sur merge `main`. `fly deploy` reste un override manuel.

### 5.2 Repo
- GitHub : `Bellerophon44/mvp-immobilier`
- Branche de dev : `claude/analyze-mvp-immobilier-vtne5` → mergée régulièrement dans `main`
- Branche prod : `main` (déclenche les redeploys Vercel)

### 5.3 Arborescence
```
.
├── CONTEXT.md                  # ce fichier
├── backend/
│   ├── Dockerfile              # uvicorn sur :8080
│   ├── fly.toml                # 1 machine, volume /data, healthcheck /health
│   ├── .dockerignore
│   ├── requirements.txt
│   ├── app/
│   │   ├── main.py             # FastAPI app, CORS, /analyze, lifecycle
│   │   ├── analysis.py         # orchestrateur run_full_analysis
│   │   ├── llm_semantic.py     # appel OpenAI, prompt, cache, fallback
│   │   ├── url_fetch.py        # fetch HTTP + extraction texte HTML
│   │   ├── market_stats.py     # stats marché local sur Comparable
│   │   └── scoring.py          # score global 0-100 + verdict + confiance
│   ├── db/
│   │   ├── models.py           # SQLAlchemy Comparable
│   │   └── session.py          # engine SQLite, DATABASE_PATH=/data/...
│   ├── ingestion/
│   │   └── save.py             # save_comparables(list) → DB
│   ├── scrapers/
│   │   ├── base.py             # fetch_page, normalize_price/surface, ID stable
│   │   └── site_local.py       # ⚠️ sélecteurs CSS à adapter (placeholder)
│   └── jobs/
│       └── collect_metz.py     # entry point cron-friendly
└── frontend/
    ├── app/
    │   ├── globals.css         # design tokens, layout
    │   ├── layout.tsx
    │   └── page.tsx            # hero + textarea + résultat
    ├── components/
    │   ├── ScoreResult.tsx
    │   ├── Pillars.tsx
    │   └── Actions.tsx
    ├── lib/
    │   └── api.ts              # analyzeListing(input) → POST /analyze
    ├── next.config.js
    └── package.json
```

### 5.4 Variables d'environnement et secrets

**Côté Fly (backend) — gérés via `fly secrets set`**
| Nom | Source | Usage |
|---|---|---|
| `OPENAI_API_KEY` | platform.openai.com | Appel LLM |
| `OPENAI_MODEL` (optionnel) | par défaut `gpt-4.1-mini` | Pour basculer sur `gpt-4o-mini` ou autre |
| `DATABASE_PATH` | fly.toml `[env]` | Chemin SQLite, par défaut `/data/comparables.db` |
| `CORS_ORIGINS` (optionnel) | env Fly | Liste séparée par virgules ; par défaut couvre `*.vercel.app` |

**Côté Vercel (frontend)**
| Nom | Valeur attendue |
|---|---|
| `NEXT_PUBLIC_API_URL` | `https://backend-frosty-sound-441-docker.fly.dev` |

### 5.5 Conventions de code

- **Logging** : `logging.getLogger("<module>")`, niveaux INFO sur actions clés, `logger.exception` pour les erreurs récupérables. `logging.basicConfig(level=INFO, force=True)` est fait dans `app/main.py`.
- **Loggers nommés** présents : `mvp` (entrée requêtes), `url_fetch` (fetch URL), `llm_semantic` (appels OpenAI).
- **Fallbacks LLM** : toute erreur OpenAI tombe sur un dict `_FALLBACK` constant pour ne pas exposer l'erreur à l'utilisateur (et est loguée).
- **Pas de comments inutiles** dans le code (pratique imposée).
- **Pas d'emoji** dans le code ni les commits, sauf demande utilisateur explicite.

---

## 6. Modèle de données

### 6.1 Table `comparables` (SQLite, schéma SQLAlchemy)

```python
class Comparable(Base):
    id            = Column(String, primary_key=True)  # sha256(source:external_id)
    source        = Column(String, nullable=False)    # ex "site_local_metz"
    city          = Column(String, nullable=False)    # ex "Metz"
    district      = Column(String, nullable=True)     # ex "Sablon"
    property_type = Column(String, nullable=False)    # "appartement" / "maison"
    surface_m2    = Column(Float, nullable=False)
    price_total   = Column(Float, nullable=False)
    price_m2      = Column(Float, nullable=False)
    collected_at  = Column(DateTime, default=datetime.utcnow)
```

### 6.2 Stats marché (`market_stats.py`)
- Minimum **3 comparables** dans une fenêtre `surface_m2 ± 20%` pour produire un résultat.
- Calcule médiane, Q1, Q3, dispersion (Q3-Q1).
- Verdict prix selon écart à la médiane : `±10% = Plutôt aligné`, `+10-25% = Légèrement sur-positionné`, `+25%+ = Fortement sur-positionné`, négatif = `Sous-positionné`.
- Confiance : ≥10 comparables ET dispersion < 800 = "Élevée", ≥4 = "Moyenne", sinon "Faible".

---

## 7. Workflow de déploiement actuel

### 7.1 Backend (automatique sur merge `main`)
1. Mergé `claude/...` → `main` via PR GitHub
2. Le workflow `deploy-backend.yml` se déclenche sur tout push `main` touchant
   `backend/**` (ou `.github/workflows/deploy-backend.yml`) et lance
   `flyctl deploy --remote-only` (concurrence : un seul deploy à la fois, le plus
   récent annule l'en-cours). Nécessite le secret repo `FLY_API_TOKEN`.
3. `fly logs --app backend-frosty-sound-441-docker` pour vérifier
4. **Override manuel** si besoin (hotfix sans merge, rollback) :
   `cd backend ; fly deploy --app backend-frosty-sound-441-docker`, ou
   `workflow_dispatch` sur le workflow.

### 7.2 Frontend (automatique)
- Toute PR mergée sur `main` déclenche un déploiement Vercel
- Variables d'env doivent être définies AVANT le build (les `NEXT_PUBLIC_*` sont inlinées dans le bundle)

### 7.3 Pièges connus
- **Browser cache** : après un deploy frontend, ouvrir en navigation privée OU hard reload (Ctrl+Shift+R)
- **Volume Fly** : 1 machine = 1 volume. Si on scale à 2, il faut créer un 2e volume.
- **App fantôme** : `fly launch` au lieu de `fly deploy` crée des apps parasites. Toujours utiliser `fly deploy --app <nom>` explicite.

---

## 8. À faire (backlog) — priorisé

### Backlog produit (mémorisé par le user — "to-do MVP")

| Item | Priorité | Effort | Statut |
|---|---|---|---|
| Peupler la DB de comparables Metz (adapter scrapers + lancer job) | 🟠 moyenne (débloque pilier prix) | 2-4h dev | À faire |
| Tester 5-10 vraies annonces (qualité IA, robustesse fetch) | 🟠 moyenne (validation produit) | 30 min | En cours |
| Mention légale / disclaimer dans l'UI | ✅ déjà présent (bas de page) | — | Fait |
| Limite de dépense OpenAI sur platform.openai.com | 🟡 basse (sécurité financière) | 5 min | À faire |
| Améliorer le wording UX (texte d'aide, exemples) | 🟡 basse | 1h | Partiellement fait avec UI refresh |

### Dette technique / observabilité

- Tests pytest sur `analysis.py`, `scoring.py`, `url_fetch.py` (au moins golden path)
- Migration `@app.on_event` → `lifespan`
- Monitoring : Sentry pour erreurs, Logflare/Axiom pour logs structurés
- **Automatisations 9.x (9.3 monitoring IA, 9.5 SEO, 9.6 watchlist, 9.8 A/B) —
  différées** : statut, findings, risques et workarounds détaillés en **§9**
  (source canonique) ; analyses complètes dans `docs/specs/9.X-ANALYSE.md`.
- Cache LLM persistant (Redis Fly ou table SQLite)
- Rate limiting sur `/analyze` (anti-abus)
- Robots.txt côté frontend
- Sitemap pour SEO

---

## 9. Opportunités d'automatisation (input pour agents et workflows)

> **Mise à jour 2026-06-05.** Les requirements 9.2→9.8 ont été passés un par un
> dans l'**atelier d'agents** (`.claude/`, voir `.claude/atelier/README.md`) :
> analyse → spec → tests → dev → revue adversariale, avec gates humaines. Chaque
> requirement porte ci-dessous : un **statut**, la **version complète (cible)**
> conservée pour reprise ultérieure, les **findings / challenges / risques** de
> l'analyse, et le **workaround léger** réellement retenu. Le détail complet de
> chaque analyse est versionné dans `docs/specs/9.X-ANALYSE.md` (et `-SPEC.md`
> quand un livrable a été produit).
>
> **Légende statut** : ✅ Fait · ⚠️ Partiel (workaround livré, version complète
> différée) · ⏸️ Différé · ⬜ À faire (hors atelier).
>
> **Fil rouge des analyses** : à **trafic quasi nul** (MVP en phase de test) et
> **sans domaine email** ni **auth** ni **rate-limit**, plusieurs requirements
> sont **prématurés ou bloqués par des prérequis externes**. La stratégie retenue
> a été de livrer à chaque fois la **version la plus légère qui apporte de la
> valeur sans dette**, et de documenter la version lourde pour plus tard.

### 9.1 [agent ingestion] Alimenter la base des comparables — ✅ Fait
**Statut : ✅ Fait.** 5 scrapers actifs (bienici, benedic, idemmo, immoheytienne,
laveine_immo), base prod **~17,7k comparables**, collecte CI hebdo (`collect.yml`)
+ harnais de diagnostic en PR (`diagnose-scrapers.yml`). Voir `backend/CLAUDE.md`
§8-9. Le pilier « Prix vs marché » est passé de « Indéterminé » à opérationnel.
- **Version cible** (rappel) : cron + modules `scrapers/sources/<site>.py` à
  sélecteurs CSS, ingestion via `ingestion/save.py`, agrégats seulement (pas de
  redistribution brute).
- **Reste possible** : ajouter d'autres agences accessibles (registre + harnais
  déjà en place : déposer un fichier `sources/<agence>.py`, lire le diagnostic PR).

### 9.2 [workflow] Email récapitulatif après une analyse — ⚠️ Partiel
**Statut : ⚠️ Partiel.** Livré : **export client `.md`** du rapport (bouton
« Télécharger (.md) », PR #54). **Email différé** (prérequis externes manquants).
Specs : `docs/specs/9.2-ANALYSE.md`, `docs/specs/9.2-SPEC.md`.

- **Version complète (cible, conservée)** : à la fin d'un `/analyze` réussi, si
  l'utilisateur fournit un email + consentement, lui envoyer le récap (score,
  verdict, piliers, actions) par mail. Conception cible arbitrée : endpoint
  **séparé** `POST /send-report` recevant le résultat déjà calculé (zéro coût
  LLM, contrat `/analyze` intact, pattern `/feedback`) ; **ne rien stocker** (D1,
  minimisation) ; Resend via `requests` (zéro dépendance) ; template HTML inline +
  texte ; **pas d'envoi sur fallback LLM** ; consentement explicite (case non
  pré-cochée) ; mention « vos données ne sont pas réutilisées ». Fichier cible :
  `backend/app/email.py`.
- **Prérequis EXTERNES bloquants (action humaine)** : (1) **acquérir un domaine**
  expéditeur (le projet n'en a pas, §3.2), (2) compte Resend + **vérification DNS
  SPF/DKIM**, (3) secret `RESEND_API_KEY` (`fly secrets`).
- **Challenges / risques** : **relais de spam ouvert** (endpoint d'envoi sans
  rate-limit — dette §8 — peut cramer la réputation d'un domaine neuf) ; **RGPD**
  (email = donnée perso) ; valeur engagement **non validée** (§2.4) ; ne pas
  redistribuer l'annonce brute (§11.3) ; ne pas envoyer le fallback LLM.
- **Workaround léger retenu** : export client (le bouton « Copier » existait déjà ;
  ajout d'un téléchargement `.md` qui réutilise `buildReportText`) — couvre ~80 %
  du besoin « garder mon analyse », **0 backend / 0 RGPD / 0 vendor / 0 domaine**.

### 9.3 [agent qualité] Monitoring qualité IA — ⚠️ Partiel
**Statut : ⚠️ Partiel.** Livré : **test de régression** verrouillant le marqueur
de dégradation (PR #55). **Alerte complète différée.** Specs :
`docs/specs/9.3-ANALYSE.md`, `docs/specs/9.3-SPEC.md`.

- **Finding clé** : le fallback LLM est émis en **un seul point**
  (`backend/app/llm_semantic.py:236-242`) — le « log warning » et le « retour
  `_FALLBACK` » du requirement sont le **même événement**. Le seul signal loggable
  est la chaîne **`LLM call failed`** (ERROR, logger `llm_semantic`) ; la variable
  `_FALLBACK` n'apparaît jamais dans les logs.
- **Version complète (cible, conservée)** : détection **persistée** en SQLite
  (table `LlmFailure`, modèle `Feedback` à imiter) → taux/heure fiable **malgré
  l'auto-stop Fly** (un compteur en mémoire est remis à zéro à chaque réveil) ;
  endpoint `GET /admin/health/llm` (protégé `X-Admin-Token`, agrégats seulement) ;
  cron GitHub Actions (modèle `collect.yml`) qui alerte au-delà d'un seuil
  (proposition : ≥ 3 fallbacks ET > 50 % sur 60 min) via **issue GitHub** (zéro
  secret externe) ou **webhook Slack**.
- **Challenges / risques** : **prématuré au trafic quasi nul** (un fallback n'est
  observable que si quelqu'un analyse pendant une panne OpenAI) ; **email écarté**
  (pas de domaine, cf. 9.2) ; **vendor Better Stack sur-dimensionné** ; le
  **polling réveille la VM** (contre l'auto-stop / sécurité financière §3.3) ; le
  **cache LLM peut masquer** une panne (annonces déjà en cache servies sans appel).
- **Workaround léger retenu** : test `backend/tests/test_llm_fallback.py` qui
  garantit que le marqueur `LLM call failed` reste émis et explicite — tout
  monitoring futur s'appuiera dessus. Coût nul, aucun changement de comportement.

### 9.4 [workflow] Alertes coût OpenAI — ⬜ À faire (hors atelier)
**Statut : ⬜ À faire.** Volontairement **hors atelier** (pure config UI, pas de
code → le pipeline à 5 rôles ne se justifie pas, cf. règle right-sizing
`.claude/commands/feature.md`).
- **Action** : sur `platform.openai.com → Settings → Limits`, poser un **usage
  limit hard** (ex. 20 €) + alerte douce à 80 %. ~5 min, aucune dépendance.

### 9.5 [agent contenu] Génération SEO long-tail — ⏸️ Différé
**Statut : ⏸️ Différé.** Spec : `docs/specs/9.5-ANALYSE.md`.
- **Version complète (cible, conservée)** : socle SEO **0-dépendance**
  (`app/sitemap.ts` + `app/robots.ts` + `metadataBase`/OpenGraph + `generateMetadata`
  par article) ; **scaffold blog en composants `.tsx` statiques** (server
  components, **pas de MDX**) sous `frontend/app/blog/` ; agent qui propose
  **sujets + plans**, **rédaction relue humainement** ; cadence 1 article/semaine
  via PR de brouillon (jamais d'auto-merge sur du contenu).
- **Findings** : pas de route blog, **MDX absent** (l'activer = 3 deps + config,
  à rebours du minimalisme), **aucun socle SEO** (ni robots, ni sitemap, ni
  `metadataBase`), `page.tsx` est `"use client"` (un article doit rester statique).
- **Challenges / risques** : « MDX = SEO » est un **faux ami** ; **acquisition SEO
  = hypothèse non validée** (§2.4) et **lente** (mois) ; **rédaction automatisée =
  risque éditorial/légal majeur** vu le positionnement (juridiquement prudent, pas
  d'estimation) → revue humaine obligatoire. Prérequis : `NEXT_PUBLIC_SITE_URL`
  (URL Vercel prod) pour canonicals/sitemap.
- **Workaround léger identifié (non encore livré)** : socle SEO seul (sitemap +
  robots + metadata) répare la dette §8 sans pari éditorial ; ou 1 article pilote
  `.tsx` relu, automatisation différée.

### 9.6 [workflow] Watchlist d'annonces avec re-analyse — ⏸️ Différé
**Statut : ⏸️ Différé.** Le chantier **le plus lourd** (cumule deux bloqueurs).
Spec : `docs/specs/9.6-ANALYSE.md`.
- **Version complète (cible, conservée)** : (1) l'utilisateur enregistre une
  annonce (lien) ; (2) cron quotidien : `url_fetch` chaque annonce, compare le
  **hash de contenu** ; (3) si baisse de prix → email « Cette annonce a baissé de
  X € ». Stack : table `Watchlist(id, user_email, url, last_hash, last_price,
  created_at)`, reuse `url_fetch.py`, cron type `collect.yml`.
- **Prérequis EXTERNES bloquants (cumulés)** : (1) **AUTH utilisateur** —
  inexistante (seul `X-Admin-Token` machine-à-machine existe) ; un **magic link**
  est un **chantier entier** (envoi d'email + tokens + session + rate-limit +
  parcours front) ; (2) **EMAIL** — bloqué par l'absence de domaine, **comme 9.2**.
  9.6 hérite donc du blocage email **deux fois** (magic link **et** notification).
- **Challenges / risques** : **saut de posture RGPD majeur** (stockage nominatif
  durable + profilage + envoi récurrent ⇒ consentement, désinscription, rétention,
  registre — à l'opposé de la minimisation assumée de `Feedback`) ; **coût** —
  distinguer un **hash** (cheap) d'une **re-analyse LLM** (chère, ×annonces×jours,
  peut dépasser le < 1 €/mois) ; **promesse intenable** sur les grands portails
  (Leboncoin/SeLoger non-fetchables, anti-bot §4.3) ; **détection « baisse de
  prix » non fiable** (le hash voit *un* changement, pas le prix — il n'y a pas de
  scraper dédié par site arbitraire) ; **relais de spam** (pas de rate-limit).
- **Workaround léger identifié (non livré)** : version **sans compte ni email** —
  l'utilisateur garde ses annonces analysées en **localStorage** (« Mes
  annonces ») + bouton **« re-analyser »** qui rejoue `/analyze` sur un lien
  sauvegardé. Donne « garder + re-vérifier » sans auth/email/RGPD, mais **pas
  d'alerte proactive** de baisse de prix.

### 9.7 [agent analytics] Collecte de feedback utilisateur — ✅ Fait
**Statut : ✅ Fait.** Pilote de l'atelier (PR #53). Specs :
`docs/specs/9.7-ANALYSE.md`, `docs/specs/9.7-SPEC.md`.
- **Livré** : table `feedback` (rating 1-5, comment ≤ 1000, `analysis_id`,
  `global_score`, `verdict`, `prompt_variant` nullable [pré-câblage 9.8],
  `created_at`) — **aucune IP ni identifiant** ; endpoint **`POST /feedback`**
  public (201) ; validation Pydantic (422) ; logger `feedback` qui **ne journalise
  jamais le commentaire** ; `FeedbackForm` côté front ; `analysis_id` généré
  client (`crypto.randomUUID`) → **contrat `/analyze` intact** ; footer corrigé
  (« Aucune donnée conservée » retiré) + micro-mention RGPD.
- **Décisions** : stockage **SQLite** (pas de Supabase), modèle **D2** (sans
  extrait d'annonce), anti-abus **léger** (validation, pas de slowapi), RGPD a+c.
- **Suites notées** : politique de **rétention/purge** des feedbacks ; **rapports
  d'exploitation** (corrélation note ↔ score/verdict, lecture commentaires).

### 9.8 [workflow] A/B testing de prompts — ⏸️ Différé
**Statut : ⏸️ Différé.** Backend **pré-câblé** par 9.7. Spec :
`docs/specs/9.8-ANALYSE.md`.
- **Version complète (cible, conservée)** : 2 versions de `SYSTEM_PROMPT` en
  parallèle, split (≈50/50), enregistrement de la satisfaction (note 9.7) par
  variante, bascule vers la variante gagnante.
- **Acquis (pré-câblage 9.7)** : `Feedback.prompt_variant` (nullable) +
  `FeedbackIn.prompt_variant` persisté + test de verrou. **Maillon manquant** :
  le front n'envoie pas encore `prompt_variant` (`FeedbackPayload` +
  `handleFeedback`).
- **Nœud de conception** : la variante est choisie au backend à `/analyze`, mais
  `analysis_id` est **généré côté client** et n'arrive qu'avec le feedback.
  Options : (a) `/analyze` **renvoie** la variante → change `AnalyzeResponse`
  (anti-pattern §11.9, MAJ `lib/api.ts`), corrélation **exacte** [reco si on
  accepte le changement de contrat] ; (b) **dérivation déterministe** (hash de
  `analysis_id`) → zéro changement de contrat, split « par contenu » imparfait ;
  (c) table serveur → **bloquée** (analysis_id est client) ; (d) cookie/session →
  **RGPD** + contredit la minimisation.
- **Challenges / risques** : **prématuré** (jamais significatif au trafic quasi
  nul, même constat que 9.3) ; **rolling refresh auto = sur-apprentissage du
  bruit** ; le **cache LLM ignore le prompt** dans sa clé → re-sert sans repasser
  par la sélection (fausse l'attribution) ; inclure la variante dans la clé corrige
  mais peut **doubler les appels OpenAI** ; une variante B doit respecter les
  **mêmes anti-patterns** (pas d'estimation, pas de conseil juridique).
- **Workaround léger identifié (1re étape à la reprise)** : **fermer la chaîne
  front `prompt_variant`** (no-risk), puis infra de variante **OFF par défaut**
  (prod = 1 seul prompt), bascule **manuelle** quand le trafic le justifiera.

---

## 10. Données de référence — URLs et identifiants

| Item | Valeur |
|---|---|
| Repo GitHub | `Bellerophon44/mvp-immobilier` |
| Branche dev | `claude/analyze-mvp-immobilier-vtne5` |
| App Fly backend | `backend-frosty-sound-441-docker` |
| URL backend | `https://backend-frosty-sound-441-docker.fly.dev` |
| URL Swagger | `https://backend-frosty-sound-441-docker.fly.dev/docs` |
| URL healthcheck | `https://backend-frosty-sound-441-docker.fly.dev/health` |
| Région Fly | `cdg` (Paris) |
| Volume Fly | `comparables_data` (1 Go, monté sur `/data`) |
| Modèle LLM par défaut | `gpt-4.1-mini` |
| URL frontend Vercel | (à compléter — pas exposée dans la conversation) |
| URL test de référence | `https://idemmo.fr/bien-immobilier/magnifique-maison-individuelle-saint-julien-les-metz-saint-julien-les-metz-86901328/` |

---

## 11. Anti-patterns à éviter

Listés ici pour qu'un agent IA n'y retombe pas :

1. **Ne pas estimer un prix.** Toute réponse qui ressemble à "ce bien vaut X €" est hors périmètre produit.
2. **Ne pas inventer de données.** Si le LLM ne sait pas, il doit dire "non précisé dans l'annonce".
3. **Stockage interne par-annonce autorisé ; redistribution du contenu interdite.** La collecte stocke déjà des annonces individuelles (table `comparables`) et peut conserver leur **historique horodaté** (dates de première/dernière observation, snapshots de prix) à usage interne. Ce qui reste interdit est la **redistribution du contenu** d'une annonce tierce : ne jamais re-publier texte, photos, adresse exacte ou URL. L'**exposition publique** se limite aux **agrégats statistiques** (médianes, Q1/Q3) et aux **métadonnées factuelles** non re-publiables (source, ancienneté, écart de prix en %). **Rétention** : purge des historiques 24 mois après la dernière observation (`last_seen_at`). Pas de DVF / notaires (point 4).
4. **Ne pas faire de DVF / notaires.** Cassé le positionnement.
5. **Ne pas ajouter Tailwind / Material UI** sans validation explicite (le projet est volontairement sans dépendance UI).
6. **Ne pas merger directement sur `main` sans PR.** Toujours passer par `claude/analyze-mvp-immobilier-vtne5` → PR → merge.
7. **Ne pas créer une seconde app Fly.** Toujours utiliser `--app backend-frosty-sound-441-docker`.
8. **Ne pas exposer la clé OpenAI** dans le repo (utiliser `fly secrets`).
9. **Ne pas changer la signature de `/analyze`** sans aussi mettre à jour `frontend/lib/api.ts`.
10. **Ne pas commit le contenu du cache LLM ou la DB SQLite** (`.gitignore` les couvre).

---

## 12. Historique des décisions techniques

Pour comprendre pourquoi certains choix ont été faits :

| Décision | Pourquoi |
|---|---|
| Dockerfile explicite (pas buildpacks Paketo) | Les buildpacks Fly forçaient `fastapi run` qui ne trouvait pas l'app → boucle de restart |
| Volume Fly monté sur `/data` | Filesystem Fly éphémère + auto-stop = DB perdue à chaque arrêt sinon |
| Port 8080 (pas 8000) | Conventions Fly + alignement avec `internal_port` de `fly.toml` |
| OpenAI via `chat.completions.create` + `response_format: json_object` | Plus stable et mieux documenté que `responses.create` pour du JSON strict |
| Extraction structurée `listing` dans le LLM | Pas besoin d'un parser séparé : le LLM est déjà bon pour extraire ville/surface/prix |
| Pas de Tailwind | Quick-win UI, dette technique minimale, refresh facile |
| URL fetching côté serveur (pas CORS-proxy client) | Sécurité (anti-SSRF maîtrisé) + uniformité du parcours utilisateur |
| Cache LLM par hash de texte normalisé, 7 jours | Réduit drastiquement le coût lors des tests répétitifs |
| `auto_stop_machines = true` + 1 machine | Coût minimal en idle (~0 €/mois) + SQLite mono-writer |

---

## Annexe — Commandes utiles

### Déploiement backend
```powershell
fly deploy --app backend-frosty-sound-441-docker
fly logs --app backend-frosty-sound-441-docker
fly secrets list --app backend-frosty-sound-441-docker
fly secrets set OPENAI_API_KEY=sk-... --app backend-frosty-sound-441-docker
fly status --app backend-frosty-sound-441-docker
fly machine start <ID> --app backend-frosty-sound-441-docker
```

### Volume Fly
```powershell
fly volumes list --app backend-frosty-sound-441-docker
fly volumes create comparables_data --size 1 --region cdg --app backend-frosty-sound-441-docker --yes
```

### Test direct du backend (PowerShell)
```powershell
$body = '{"url":"https://idemmo.fr/bien-immobilier/..."}'
Invoke-WebRequest -Uri "https://backend-frosty-sound-441-docker.fly.dev/analyze" `
  -Method POST -ContentType "application/json" -Body $body | `
  Select-Object -ExpandProperty Content
```

### Job d'ingestion (manuel)
```powershell
fly ssh console --app backend-frosty-sound-441-docker --command "python -m jobs.collect_metz"
```

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
- **CI/CD** : aucun, déploiement manuel via `fly deploy` et auto-deploy Vercel sur merge `main`

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

### 7.1 Backend (manuel)
1. Mergé `claude/...` → `main` via PR GitHub
2. `git pull origin main` en local
3. `cd backend ; fly deploy --app backend-frosty-sound-441-docker`
4. `fly logs --app backend-frosty-sound-441-docker` pour vérifier

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
- Cache LLM persistant (Redis Fly ou table SQLite)
- Rate limiting sur `/analyze` (anti-abus)
- Robots.txt côté frontend
- Sitemap pour SEO

---

## 9. Opportunités d'automatisation (input pour agents et workflows)

Les automatisations ci-dessous sont des candidats logiques pour des agents
Claude Code ou workflows planifiés. Chacune est décrite avec son trigger, ses
inputs/outputs, ses dépendances, et son effort estimé.

### 9.1 [agent ingestion] Alimenter la base des comparables
- **Objectif** : faire passer le pilier "Prix vs marché" de "Indéterminé" à un verdict réel
- **Trigger** : cron quotidien ou hebdomadaire (ex. 4h du matin)
- **Étapes** :
  1. Identifier les sites cibles accessibles (sans anti-bot) — idemmo.fr testé OK ; en ajouter 2-3 (orpi-metz, century21-metz, agences locales)
  2. Pour chaque site : implémenter un module `scrapers/<site>.py` avec sélecteurs CSS spécifiques (analyser le DOM, écrire les sélecteurs)
  3. Lancer le job ; ingérer via `ingestion/save.py` (utilise `merge` pour update sans doublon)
  4. Loguer le nombre d'annonces récupérées / sauvegardées
- **Dépendances** : aucune nouvelle clé API, juste des respects de fréquence raisonnable (1 req/s max conseillé)
- **Légalité** : vérifier robots.txt de chaque site, ne pas redistribuer le contenu brut (seulement les agrégats statistiques)
- **Effort agent** : moyen (analyse de DOM + écriture de sélecteurs résilients)
- **Trigger possible** : GitHub Action cron, ou `fly machine run` schedulé
- **Fichiers à créer/modifier** : `backend/scrapers/<site>.py`, `backend/jobs/collect_<region>.py`, possiblement un module `scrapers/registry.py` pour orchestrer

### 9.2 [workflow] Envoyer un email récapitulatif après une analyse
- **Objectif** : engagement / rétention / création d'asset propre à l'utilisateur
- **Trigger** : `POST /analyze` réussi
- **Étapes** :
  1. Ajouter un champ `email` optionnel dans `AnalyzeRequest`
  2. Côté frontend : checkbox "Recevez-moi cette analyse par mail" + champ email
  3. Côté backend : à la fin de `/analyze`, si email présent, déclencher l'envoi async
  4. Format mail : HTML simple avec score, verdict, 3 piliers, 3 listes d'actions
- **Dépendances** : 
  - Provider d'envoi : Resend (recommandé, free tier 100 mails/jour), ou Postmark, ou Brevo
  - Secret Fly : `RESEND_API_KEY` (ou équivalent)
  - Domaine vérifié pour expéditeur (ex. `noreply@mvp-immobilier.fr`)
- **Conformité RGPD** : checkbox de consentement explicite, mention "vos données ne sont pas réutilisées"
- **Effort** : 2-3h (backend send + template HTML + frontend champ + tests)
- **Fichiers à créer** : `backend/app/email.py` (client Resend), template HTML inline ou via Jinja2

### 9.3 [agent qualité] Monitoring qualité IA
- **Objectif** : détecter automatiquement quand l'IA donne des réponses fallback (signal de dégradation)
- **Trigger** : log warning détecté ("LLM call failed" ou retour `_FALLBACK`)
- **Étapes** : tail des logs Fly → si seuil de fallbacks/heure dépassé → notification Slack/email
- **Dépendances** : Better Stack (anciennement Logtail), ou intégration Fly logs → webhook
- **Effort** : 1-2h

### 9.4 [workflow] Alertes coût OpenAI
- **Objectif** : éviter une facture surprise
- **Trigger** : webhook OpenAI Usage Alerts (configurable sur platform.openai.com)
- **Étapes** : mettre un usage limit hard (ex. 20 €) + alerte douce à 80%
- **Effort** : 5 min de config UI sur platform.openai.com (pas de code)

### 9.5 [agent contenu] Génération SEO long-tail
- **Objectif** : créer du contenu pédagogique qui ramène du trafic ("Comment savoir si une annonce immobilière est honnête ?")
- **Trigger** : manuel ou hebdomadaire
- **Étapes** : agent Claude → liste de 20 questions d'acheteurs → 1 article par semaine → publication sur Vercel (pages MDX dans `frontend/app/blog/`)
- **Effort** : moyen (squelette MDX à créer côté Next.js + agent de génération)

### 9.6 [workflow] Watchlist d'annonces avec re-analyse
- **Objectif** : pousser à l'engagement régulier ; capter l'intention d'achat dans la durée
- **Mécanique** :
  1. L'utilisateur enregistre une annonce (lien)
  2. Cron quotidien : fetch chaque annonce, comparer le hash du contenu
  3. Si modifié (notamment baisse de prix) : email "Cette annonce a baissé de X €"
- **Stack** : nouvelle table `Watchlist(id, user_email, url, last_hash, last_price, created_at)` ; reuse de `url_fetch.py`
- **Effort** : 4-6h
- **Pré-requis** : auth utilisateur (au moins email magic link)

### 9.7 [agent analytics] Collecte de feedback utilisateur post-analyse
- **Objectif** : améliorer le prompt LLM et le wording UX
- **Mécanique** : à la fin du résultat, micro-form "Cette analyse vous a-t-elle aidée ? 1-5", + champ libre. Stockage SQLite/Supabase.
- **Effort** : 2h

### 9.8 [workflow] A/B testing de prompts
- **Objectif** : optimiser progressivement la qualité d'analyse
- **Mécanique** : 2 versions de `SYSTEM_PROMPT` actives en parallèle, split 50/50 par cookie/session ID, enregistrement de la satisfaction ; rolling refresh par variante gagnante
- **Effort** : 3-4h, nécessite analytics et feedback en place (cf 9.7)

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
3. **Ne pas redistribuer des annonces brutes** (droits d'auteur). Stocker uniquement les agrégats statistiques (médianes, Q1/Q3).
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

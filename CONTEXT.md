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

> **MàJ données 2026-06-21** — chiffres rafraîchis depuis la base **prod** via
> `GET /admin/comparables/stats` + `GET /admin/comparables/coverage` (la prochaine
> session part de CES chiffres, pas du « ~17,7k » de juin, périmé) :
> - **Total : 29 682 comparables** (~29,7k).
> - **Couverture par commune ≥ 198 comparables = la couronne (`_METRO_CITIES`, 11
>   communes)** : Metz 17 906 · Montigny-lès-Metz 4 439 · Marly 1 731 ·
>   Woippy 1 422 · Longeville-lès-Metz 1 055 · Saint-Julien-lès-Metz 905 ·
>   Le Ban-Saint-Martin 805 · Scy-Chazelles 461 · Augny 280 · Plappeville 263 ·
>   Lessy 198. (Metz seul ≈ 60 % de la base : 15 118 appart / 2 788 maisons.)
> - **Seuil ≥ 10 comparables : 14 communes** = les 11 de couronne + Forbach 16,
>   Saint-Avold 11, Thionville 12 (ces 3 hors couronne sont minces, une **seule**
>   agence benedic). **Seuil ≥ 20 : exactement les 11 de couronne.** ~90 communes
>   au total figurent en base, la plupart avec 1 à 8 biens (Moselle dispersée).
> - **Quartiers de Metz : 17** (= longueur de `frontend/lib/districts.ts`). Le
>   « 16 » cité dans plusieurs docs est **périmé** : Sainte-Thérèse a été ajoutée
>   (issue #100 A). Liste : Centre-Ville, Ancienne Ville, Nouvelle Ville, Les Îles,
>   Sablon, Sainte-Thérèse, Queuleu, Plantières, Bellecroix, Borny, Magny,
>   Vallières, Devant-les-Ponts, La Patrotte, Outre-Seille, Grange-aux-Bois,
>   Technopôle.
> - **Bandeau de preuve de la home** (`frontend/app/page.tsx`, `PROOF_POINTS`) mis
>   à jour en conséquence : **« 29 000+ comparables » · « 17 quartiers de Metz » ·
>   « 11 — Metz et ses 10 communes de couronne »** (ce 3ᵉ chiffre remplace l'ancien
>   « 7 j / collecte hebdomadaire »). Livré PR #131 → `staging` puis #132 → `main`.
> - *Hygiène data à assainir en maintenance* : doublons de normalisation repérés
>   dans `coverage` (Le-Ban-Saint-Martin / Le-Ban-St-Martin / Ban-Saint-Martin ;
>   Metz-Vallieres ; Marly-Frescaty ; Montoy-Flanville / Ogy-Montoy-Flanville).

### Stack réelle
- **Backend** : Python 3.12, FastAPI sur **Fly.io** (`backend-frosty-sound-441-docker`,
  région cdg, Docker explicite, volume SQLite `/data`, auto-stop). **Pas de Railway.**
- **Frontend** : **Next.js 16** App Router sur Vercel, design system « Cohérence »
  (palette ink/parchment/brick/moss/ochre, fonts Instrument Serif/Geist), composants
  sous `frontend/components/design/`. **Pas l'UI bleue de transition décrite en §2.3.**
- **CI** : GitHub Actions — `collect.yml` (collecte hebdo lundi 04:00 + manuel,
  **cible `prod`/`staging`**), `coverage-probe.yml` + `cross-source-probe.yml`
  (probes admin **read-only** paramétrables `prod`/`staging`), `diagnose-scrapers.yml`
  (sur PR touchant les scrapers → commentaire de diagnostic + recon), `test.yml`,
  `evals.yml`, `deploy-backend.yml` (deploy Fly : `main`→prod, `staging`→staging).
  Secret `ADMIN_TOKEN_STAGING` requis pour cibler staging (détail `backend/CLAUDE.md` §3).
  ⚠️ Un workflow `pull_request` ne démarre **pas** si la PR est en conflit (`dirty`) — §7.3.
- **Branche de dev courante** : `claude/clever-gates-xXqfp` (l'ancienne
  `claude/analyze-mvp-immobilier-vtne5` est périmée).

### Données & pilier prix (le gros du travail récent)
- **5 scrapers** réels et actifs : `bienici` (API JSON, **balayage par tranches de
  surface**), `benedic`, `idemmo`, `immoheytienne`, `laveine_immo` (HTML).
- Base prod **~29,7k comparables** (29 682 au 2026-06-21, vérifié via
  `/admin/comparables/stats` ; vs « DB vide » en §4.3, désormais faux), toutes
  tailles. DPE ~82 % / année ~37 % / étage-ascenseur ~60 % / code postal ~100 %
  (bien'ici). Répartition par commune : voir l'entrée datée **2026-06-21** en tête de §0.
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
   - *Optimisation livrée (2026-06-18)* : **temps de trajet réels** (Google Routes
     API) en mode adresse + onglets par mode (à pied / vélo / voiture / transports),
     avec repli « à vol d'oiseau » si la clé est absente. Voir « Contexte local v2 »
     en fin de section.
3. **Prochaines étapes** : faire peser la cohérence (couche B) sur le pilier risques ;
   secteur « Metz métropole » (communes limitrophes, **livré**) ; rééquilibrage
   scoring ; dette (lifespan, cache LLM/géocodage/routing persistant, tests).

### Livré depuis le snapshot (post-2026-06-04)
- **Cross-agence — incrément 1 : ✅ EN PRODUCTION (2026-06-11).** Tracking
  temporel mono-source par id stable : `first_seen_at`/`last_seen_at`, table
  `listing_price_snapshots`, capture sans écrasement (`ingestion/save.py`),
  endpoint admin `GET /admin/comparables/{id}/history`, purge de rétention
  24 mois + cascade snapshots. **Aucune** exposition `/analyze`, score 40/30/30
  intact (doctrine §11.3 amendée). Parcours staging-first (PR #71 → `staging`,
  PR #72 → `main`). Specs : `docs/specs/cross-agence-ANALYSE.md`,
  `docs/specs/cross-agence-INCREMENT1-SPEC.md`.
  - **Suite : incrément 2 (clustering photo) ⬜ à faire**, staging-first — voir
    « versus prod » en §11.3 / ANALYSE §8.
- **Harnais d'évals qualité (`backend/evals/`) — livré (2026-06-11).** Filet
  anti-régression des corrections de prompt : cas synthétiques rejoués avec de
  vrais appels LLM par `.github/workflows/evals.yml` sur toute PR touchant
  prompt/pipeline ; suite gratuite isolée (`backend/pytest.ini`). Premier cas :
  issue #80 — **fix livré (2026-06-12, chantier fix-issue-80)** : les
  régressions A/B sont des cas bloquants, plus aucun xfail. Prérequis
  humain : clé OpenAI **dédiée CI** en secret repo `OPENAI_API_KEY` +
  **usage limit** mensuel côté OpenAI (item 9.4 acté pour cette clé, garde-fou
  financier du harnais) — sans secret, le
  workflow échoue explicitement, jamais de faux vert. Spec :
  `docs/specs/evals-harness-SPEC.md`.
- **Issue #100 (retour pilote « quartier Botanique ») — référentiel géo, paliers
  A / B / C1 / C3 ✅ EN PRODUCTION.** C5 (questions non redondantes), A
  (Sainte-Thérèse/Botanique + garde-fou d'incertitude), B (gazetteer unique
  `app/geo_gazetteer.py`) puis **C1** (inter-communal & commune réelle, PR #110 →
  `staging`, PR #111 → `main`) livrés le 2026-06-16 ; **C3** (POI écoles : snapshot
  Annuaire Éducation + distance bien→école) livré le **2026-06-18** dans le lot
  « Contexte local v2 ». Reste **C2 (quartier réel par polygones) en TODO, reporté**
  — détail et prérequis dans `backend/CLAUDE.md` §11bis (backlog canonique) et
  `docs/specs/issue-100-ANALYSE.md` §6/§8. Specs C : `docs/specs/issue-100-C-*.md`.
- **« Contexte local v2 » — ✅ EN PRODUCTION (2026-06-18).** Temps de trajet réels
  (Google Routes API, endpoint `POST /travel-times`), re-géocodage de l'adresse
  texte sans exposer ni persister de lat/lon, Centre Pompidou-Metz en fact distinct,
  retrait du fact A31 générique en mode quartier, distance aux écoles (= C3).
  Intégration Google **inactive sans la clé** `GOOGLE_MAPS_API_KEY` (repli « à vol
  d'oiseau »). Parcours staging-first (PR #115 → `staging`, fix #117, promotion
  #116 → `main`). Spec : `docs/specs/contexte-local-v2-SPEC.md`.
- **Refonte des leviers de négociation + « Atouts du bien » — ✅ EN PRODUCTION
  (2026-06-18, PR #121 → `main`).** Les leviers reprenaient les points forts du
  bien (favorables au vendeur) ; désormais deux intentions distinctes :
  `actions.highlights` (atouts factuels, objective la valeur) et
  `actions.negotiation` recentré **côté acheteur** (éléments factuels qui pèsent
  à la baisse : prix sur-positionné, DPE F/G, allégation locale peu plausible,
  étage élevé sans ascenseur ; liste vide plutôt que du remplissage). Contrat
  `actions` rétro-compatible. Cas d'éval pilote #122.
- **Screening photo — réglage cap/résolution ✅ EN PRODUCTION (2026-06-18).** La
  vérification visuelle des allégations locales (`app/photo_evidence.py`, bloc
  **non-scoré** : un appel `gpt-4.1-mini` multimodal confronte aux photos de
  l'annonce les claims locaux éligibles `cathedrale`/`nature`/`autre` → statut
  `confirme`/`non_trouve`/`non_applicable`, repli sûr `non_trouve`) ratait trop
  de repères pourtant présents. Deux causes corrigées : le **cap d'images passe
  de 6 à 15** et le **détail de `"low"` à `"high"`** (un repère en arrière-plan
  était illisible à 512px). Garanties inchangées (score 40/30/30 intact, RGPD :
  URLs jamais loggées, cache mémoire TTL 7j). Coût `detail:"high"` × 15 ≈ 3-4k
  tokens/analyse non cachée — garde-fou recommandé : usage limit OpenAI. Parcours
  staging-first (PR #124 → `staging`, promotion #125 → `main`), resync préalable
  `main` → `staging`. Spec : `docs/specs/photo-evidence-SPEC.md` ; carto technique :
  `backend/CLAUDE.md` §6bis.
- **Collecte & probes paramétrables `prod`/`staging` — ✅ EN PRODUCTION
  (2026-06-20, PR #99 → `main`).** `collect.yml` et `coverage-probe.yml` exposent
  un input `workflow_dispatch target: prod|staging` (le cron de collecte vise
  toujours la prod) ; URL + token résolus par expression. **Principe : staging =
  mêmes capacités que prod** (peupler/sonder sa base isolée à la demande). Geste
  ops requis : secret GitHub `ADMIN_TOKEN_STAGING`. Leçon : `.claude/lessons.md`.
- **Incrément 3 « couronne » — PRÉPA GATE 1 (PR #113, ouverte, NON mergée).**
  Axe B (agences locales couronne) d'abord ; axe A (dédup multi-mandat) différé.
  Outillage : endpoint read-only `GET /admin/comparables/cross-source-probe` +
  `cross-source-probe.yml`. **Recon 1ʳᵉ vague (2026-06-20) : 0 candidate retenue**
  (Artisans = `robots.txt` interdit ; SOREC = JS-only). Décision humaine en
  attente. Détail : `docs/specs/increment3-couronne-{ANALYSE,RESULTATS-RECON}.md`,
  `backend/CLAUDE.md` §11bis.
- **App mobile — Phase 1 (câblage backend) ✅ EN PRODUCTION (2026-06-23).**
  `POST /analyze` accepte un champ optionnel `image_urls: list[str]` routé vers
  le screening photo existant (`run_full_analysis(..., image_urls=...)`) y compris
  en mode `raw_text`, pour qu'un client mobile fournisse ses propres URLs de photos
  (extraction on-device) sans dépendre de l'extraction HTML serveur. Additif,
  rétro-compatible, **non-scoré** ; sûreté : filtrage `_is_safe_url` (whitelist
  http/https + rejet localhost/IP privées), cap d'entrée 50 distinct du cap aval
  `MAX_IMAGES=15`, ordre figé (nettoyage → dédup → filtrage → troncature) ; RGPD :
  URLs jamais loggées (compteur seul). Parcours staging-first (PR #141 → `staging`,
  promotion #142 → `main`). Specs : `docs/specs/mobile-phase1-image-urls-{ANALYSE,SPEC}.md`.
- **App mobile — Phase 2 (l'app elle-même) ⬜ DÉCIDÉE, NON DÉMARRÉE (GATE 1 du
  2026-06-23).** Décision actée d'en faire le prochain grand chantier (auparavant
  absente de cette doc, d'où ce report). Arbitrages humains GATE 1 :
  - **Périmètre Tier 1 uniquement** (parcours `/analyze` raw_text + `image_urls`,
    partage natif depuis les apps immo, OCR, géoloc). **Le backend est déjà prêt
    (Phase 1) : 0 backend nouveau pour Tier 1.**
  - **Spike on-device ✅ FAIT (2026-06-23) — risque technique n°1 LEVÉ.** Niveau 1
    (navigateur) + Niveau 2 (WebView in-app, Expo Go sur iPhone réel) : la WebView
    charge LBC **sans captcha** (accueil + annonce), l'injection JS marche, et la
    galerie est récupérée (`rule=ad-large` > 0). Findings pour la spec : filtrer
    `ad-large` (exclure `ad-image`=annonces similaires, `bo-*`=logos, `pp-small`) ;
    le share intent fournit texte+URL → extraire la 1ʳᵉ URL ; auto-scroller pour le
    lazy-load. Protocole + verdict : `docs/specs/mobile-phase2-spike-PROTOCOLE.md`
    §9-10. Harnais jetable : `spikes/lbc-extraction/`.
  - **Techno tranchée par le spike** : **React Native + Expo** (cohérence TS,
    WebView qui débloque LBC, durable sur stores). Flutter écarté.
  - **Push notifications = Phase 3 DISTINCTE**, jamais fondue dans le jour 1 : seul
    lot qui casse les invariants « anonyme / sans état » (auth, PII, persistance,
    pHash) — cap d'architecture + RGPD majeur, mêmes bloqueurs que §9.6.
  - **Garde-fou coût déjà en place** : l'usage limit OpenAI hard existe déjà
    (§9.4) — pas un bloqueur, juste à re-vérifier (montant) avant un lancement à
    plus fort trafic.
  - Analyse complète + questions : `docs/specs/mobile-phase2-app-ANALYSE.md`.

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
│   │   ├── url_fetch.py        # fetch HTTP + extraction texte HTML + images
│   │   ├── photo_evidence.py   # screening photo non-scoré (vision, cap 15/detail high)
│   │   ├── market_stats.py     # stats marché local sur Comparable
│   │   ├── scoring.py          # score global 0-100 + verdict + confiance
│   │   └── (carto complète des modules : backend/CLAUDE.md §4)
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
| `ADMIN_TOKEN` | `fly secrets` **et** GitHub repo secret | Endpoints admin (`/admin/comparables`, probes). Le secret repo = celui de la prod |
| `ADMIN_TOKEN_STAGING` | GitHub repo secret | = `ADMIN_TOKEN` de `coherence-staging` ; requis pour `target=staging` (collecte/probes). Voir `backend/CLAUDE.md` §3 |
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
- **CI muette sur une PR** : un workflow `pull_request` (test, diagnose-scrapers…) tourne sur le commit de merge `refs/pull/N/merge` ; si la PR est en **conflit** (`mergeable_state: dirty`), GitHub ne peut pas le fabriquer → **aucun run ne démarre** (ni sur push ni sur reopen), seul Vercel continue. Diagnostic : (1) barre budget Actions (si non pleine, ce n'est pas le budget) ; (2) `mergeable_state` → si `dirty`, **résoudre le conflit d'abord**. (Vécu 2026-06-20 ; `.claude/lessons.md`.)

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
laveine_immo), base prod **~29,7k comparables** (29 682 au 2026-06-21, cf. §0),
collecte CI hebdo (`collect.yml`)
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

### 9.4 [workflow] Alertes coût OpenAI — ✅ En place (hors atelier)
**Statut : ✅ Fait (en place de longue date, documenté tardivement ici).**
Volontairement **hors atelier** (pure config UI, pas de code → le pipeline à
5 rôles ne se justifie pas, cf. règle right-sizing `.claude/commands/feature.md`).
- **En place** : sur `platform.openai.com → Settings → Limits`, un **usage limit
  hard** + alerte douce sont configurés (garde-fou financier §3.3). Couvre aussi la
  clé CI dédiée (item référencé en §0 « Harnais d'évals »).
- **Note GATE 1 mobile (2026-06-23)** : ce garde-fou étant déjà actif, il ne
  constitue **pas** un bloqueur pour la publication store de l'app mobile (§0
  Phase 2) — simplement à re-vérifier (montant adapté au trafic) le moment venu.

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
3. **Stockage interne par-annonce autorisé ; redistribution du contenu interdite.** La collecte stocke déjà des annonces individuelles (table `comparables`) et peut conserver leur **historique horodaté** (dates de première/dernière observation, snapshots de prix) à usage interne. Ce qui reste interdit est la **redistribution du contenu** d'une annonce tierce : ne jamais re-publier texte, photos, adresse exacte ou URL. L'**exposition publique** se limite aux **agrégats statistiques** (médianes, Q1/Q3) et aux **métadonnées factuelles** non re-publiables (source, ancienneté, écart de prix en %). **Rétention** : purge des historiques 24 mois après la dernière observation (`last_seen_at`). Les identifiants techniques de collecte (`reference` de mandat, `customer_id` de compte agence, `lineage_id` de bien, `photo_urls` d'annonce) sont des **métadonnées internes** au même titre : conservés pour le suivi longitudinal (et, pour `photo_urls`, le futur rattachement par empreinte d'image), **jamais exposés** dans une réponse API ni re-publiés. Pas de DVF / notaires (point 4).
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

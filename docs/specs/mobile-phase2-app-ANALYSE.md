# Analyse — Mobile PHASE 2 : l'application qui consomme le contrat Phase 1

> Rôle : ANALYSTE (GATE 1, lecture seule sauf ce document). Cadrage et challenge,
> PAS de spec ni de solution d'implémentation. Les décisions structurantes sont
> remontées en §6 pour arbitrage humain.
>
> Sources relues (état réel du code, pas seulement la doc) :
> - `backend/app/main.py` : `AnalyzeRequest` (l.74-86, `image_urls` DÉCLARÉ),
>   `_sanitize_client_image_urls` (l.599-618), endpoint `/analyze` (l.621-685,
>   rate-limit `limit=10, window=60` l.624, log d'entrée l.626-644), CORS
>   (l.47-66), absence totale d'auth utilisateur.
> - `frontend/lib/api.ts` : `AnalyzeRequestBody` (l.88-94, `image_urls?: string[]`
>   documenté, NON émis), `analyzeListing` (l.96-129), `fetchTravelTimes`,
>   `sendFeedback`, `sendEvent`.
> - `docs/specs/mobile-phase1-image-urls-SPEC.md` (contrat Phase 1 livré),
>   `docs/specs/mobile-phase1-image-urls-ANALYSE.md`, `docs/specs/mobile-app-ANALYSE.md`
>   (cadrage stratégique global du portage mobile, spike LBC tranché).
> - `CONTEXT.md` (§0, §3 coûts, §9 fil rouge auth/email, §11 anti-patterns),
>   `backend/CLAUDE.md` (§1, §5, §6bis, §10), `.claude/lessons.md`,
>   `.claude/atelier/README.md`.
> - Arborescence : `Glob {mobile,app,android,ios,expo,react-native}/**` → AUCUN
>   fichier. Il n'existe PAS de code d'app mobile dans le repo (seul `frontend/`
>   = web Next.js).
>
> Branche de dev : `claude/cohérence-mobile-app-effort-tuu74e` (PR #141, Phase 1).

---

## 0. Avertissement liminaire — le besoin Phase 2 n'est PAS cadré dans CONTEXT.md

C'est la première chose à signaler honnêtement, et c'est une question
structurante majeure (cf. §6, Q0).

- **CONTEXT.md ne mentionne nulle part une « app mobile » ni une « Phase 2 ».**
  Recherche faite : aucune occurrence de `mobile`, `on-device`, `Phase 2`,
  `WebView`, `push`, `LeBonCoin` dans `CONTEXT.md`. Le mot « mobile » n'y apparaît
  que dans `docs/strategy/REBRAND-2026.md` au sens « affichage responsive du site
  web », pas au sens « application native ».
- La **seule source de cadrage du chantier mobile** est `docs/specs/mobile-app-ANALYSE.md`
  (un document d'analyse issu d'un fil avec le fondateur le 2026-06-21), qui n'a
  PAS été reporté dans `CONTEXT.md` (ni §0, ni §8 backlog, ni §9 automatisations,
  ni §11bis roadmap). Le chantier mobile est donc, à ce jour, **hors roadmap
  officielle versionnée**.
- La **roadmap réelle de CONTEXT.md** (§0, §11bis) pointe ailleurs : issue #100 C2
  (quartiers par polygones), incrément 2 (clustering photo), incrément 3 couronne,
  rééquilibrage scoring, dette technique. Et le **fil rouge des analyses 9.x**
  (CONTEXT §9) insiste : à trafic quasi nul, sans auth, sans domaine email, les
  chantiers lourds sont prématurés.

**Conséquence** : « PHASE 2 = l'app mobile » est une hypothèse de travail héritée
de `mobile-app-ANALYSE.md`, pas un requirement écrit. Avant de spécifier quoi que
ce soit, il faut que l'humain (1) confirme que l'app mobile est bien le prochain
chantier, et (2) reporte la décision dans `CONTEXT.md` pour qu'elle cesse d'être
orpheline. Sinon on construit un produit que la doc de vérité ignore.

---

## 1. Reformulation du besoin Phase 2 (tel qu'il ressort de `mobile-app-ANALYSE.md`)

Faute de cadrage dans `CONTEXT.md`, je reformule depuis la seule source existante.

### 1.1 Ce que Phase 1 a livré (le socle backend)
Phase 1 (PR #141, spec `mobile-phase1-image-urls-SPEC.md`) a rendu `POST /analyze`
capable de recevoir `image_urls: list[str]` optionnel, routé vers le screening
photo y compris en mode `raw_text`. Vérifié dans le code :
- `AnalyzeRequest.image_urls: Optional[list[str]] = None` (`main.py:86`).
- `_sanitize_client_image_urls` (`main.py:599-618`) : nettoyage → dédup ordre
  préservé → filtrage `_is_safe_url` → troncature `MAX_INPUT_IMAGE_URLS = 50`.
- Câblage : mode `raw_text` → `image_urls = client_image_urls or None`
  (`main.py:651`) ; mode `url` → remplacement si client fournit (`main.py:668-672`).
- `frontend/lib/api.ts` : `AnalyzeRequestBody.image_urls?: string[]` documenté mais
  NON émis par le web (`api.ts:88-94`).

Phase 1 est donc **un changement de contrat backend uniquement**. Aucune ligne
d'app mobile n'a été écrite. Le « consommateur » de ce contrat reste à construire.

### 1.2 Ce que Phase 2 désigne (interprétation)
Le côté **application mobile** qui consomme ce contrat. D'après
`mobile-app-ANALYSE.md` §2-§5, le scénario type est :
1. l'utilisateur partage / saisit une annonce dans l'app (depuis Bien'ici, SeLoger,
   LeBonCoin, ou une vitrine d'agence) ;
2. l'app **extrait on-device** le texte de l'annonce (et les URLs des photos de la
   galerie), parce que le fetch serveur est bloqué par les murs anti-bot (DataDome
   sur LeBonCoin) — `mobile-app-ANALYSE.md` §4 ;
3. l'app appelle `POST /analyze` en `raw_text` + `image_urls` ;
4. l'app affiche le rapport (`ApiResult`) avec le même rendu que le web.

`mobile-app-ANALYSE.md` propose un découpage en tiers de valeur (§3) :
- **Tier 1** (justifie l'app, peu coûteux, branche sur l'API existante) : partage
  natif depuis les apps immo, scan/OCR d'annonce papier, géoloc « je suis devant
  le bien ».
- **Tier 2** : notifications push (re-list / baisse de prix), capture photo en
  visite vs allégations.
- **Tier 3** : dossier hors-ligne, export natif.

Le **chantier 4 (push)** est explicitement signalé comme celui qui « met fin à
trois invariants » (zéro auth, zéro stockage de photos, analyse stateless) —
`mobile-app-ANALYSE.md` §6.

### 1.3 Périmètre IN / OUT proposé pour la Phase 2 (à arbitrer en §6)
> Ce découpage est une **proposition** de l'analyste pour réduire le risque, pas
> une décision. La vraie question est Q1 (périmètre) en §6.

- **IN (proposé, jour 1)** : greenfield d'une app mobile minimale qui (a) appelle
  `/analyze` en `raw_text` (+ `image_urls` quand l'extraction on-device les
  fournit), (b) affiche le rapport, (c) intègre AU MOINS une fonction native
  réelle (partage/OCR/géoloc) pour passer la review Apple 4.2.
- **OUT (proposé, hors jour 1)** : notifications push, persistance d'analyses,
  identité de bien par pHash, auth utilisateur, upload d'octets d'images
  (Option 2 du spike). Tout ce qui touche au « cap d'architecture » de
  `mobile-app-ANALYSE.md` §6.

---

## 2. État des lieux du contrat backend disponible (ce que Phase 1 permet, ce qui manque)

### 2.1 Ce que le backend permet DÉJÀ pour une app mobile
- **`POST /analyze` accepte `raw_text` + `image_urls`** (vérifié, §1.1). Le cœur
  du parcours mobile « texte extrait on-device + galerie » est servi tel quel.
- **`POST /travel-times`** (`main.py`, rate-limit 30/60s) : temps de trajet à la
  demande depuis une adresse texte. Réutilisable par l'app pour la fonction
  Tier 1 « géoloc je suis devant le bien ».
- **`POST /feedback`** et **`POST /events`** : collecte de feedback et funnel
  anonyme. `sendEvent` (`api.ts:214`) montre que l'instrumentation produit existe
  déjà ; l'app mobile peut émettre les mêmes events (utile pour mesurer l'usage
  mobile réel — cf. `mobile-app-ANALYSE.md` §2 « valider l'appétit mobile »).
- **API publique, stateless, sans auth utilisateur** : aucun OAuth/login à recoder
  côté app pour le parcours d'analyse. C'est le scénario le plus favorable
  (`mobile-app-ANALYSE.md` §1).
- **Rate-limit présent** sur `/analyze` (`limit=10, window=60s`, `main.py:624`),
  `/travel-times` (30/60), `/feedback` et `/events`. Anti-abus de base en place.

### 2.2 Ce qui MANQUE côté backend pour servir une app mobile (par fonction)
| Fonction visée | Manque backend | Bloquant ? |
|---|---|---|
| Analyse `raw_text` + `image_urls` (cœur Tier 1) | **Rien.** Contrat Phase 1 suffit. | Non |
| Partage natif / OCR / géoloc (Tier 1) | **Rien** (tout est on-device + API existante). | Non |
| CORS pour l'app | **Sans objet** : une app native (RN/Flutter) n'est pas soumise au CORS navigateur. Une **PWA / wrapper WebView** servie depuis un domaine custom devrait être ajoutée à `CORS_ORIGINS` (`main.py:50-57`). | Selon techno (Q2) |
| Endpoint d'upload d'octets (Option 2 spike) | Endpoint inexistant. **Tranché inutile pour LBC** (spike A : CDN `img.leboncoin.fr` ouvert, OpenAI fetche les URLs) — `mobile-app-ANALYSE.md` §5. Repli conditionnel par source seulement. | Non (jour 1) |
| Notifications push (Tier 2, chantier 4) | **Tout** : table biens suivis, token APNs/FCM, persistance d'analyses, couche pHash, cron de re-check. + le cap d'architecture (auth/PII). | Oui (mais OUT jour 1) |
| Auth / compte utilisateur | Inexistante (seul `X-Admin-Token` machine-à-machine). Même bloqueur que CONTEXT §9.6 (watchlist différée). | Oui pour push ; inutile sinon |

**Synthèse** : pour un périmètre Tier 1 (le parcours d'analyse + une fonction
native), **le backend est prêt, rien ne manque**. Tout le reste du manque
backend concerne les notifications push (Tier 2), qui est hors jour 1 et porte un
cap d'architecture lourd.

### 2.3 Vérification CORS (point technique précis)
`main.py:50-66` : `allow_origins` = localhost + `coherence-metz.fr` /`www.`
/`staging.` ; `allow_origin_regex = https://.*\.vercel\.app` ; `allow_credentials
= True`. Implications Phase 2 :
- **App native (RN/Flutter/Capacitor natif)** : n'envoie pas d'`Origin` soumis à
  la politique CORS navigateur → fonctionne sans changement.
- **PWA / wrapper WebView** servie depuis un nouveau domaine → il faudrait ajouter
  ce domaine à `CORS_ORIGINS`. Geste ops mineur (env Fly), pas de code.
- ⚠️ `allow_credentials = True` combiné à `allow_methods/headers = ["*"]` est une
  config permissive ; comme l'API est publique sans cookie de session, l'impact
  est faible aujourd'hui, mais à re-challenger si une auth (push) est introduite.

---

## 3. Faisabilité & options de techno mobile (greenfield — SANS trancher)

`mobile-app-ANALYSE.md` §2 a déjà chiffré quatre méthodes. Je les reprends en les
challengeant sous l'angle « extraction on-device des URLs photo », qui est le vrai
point dur du parcours (le reste de l'app est ~2 écrans).

> Rappel du point dur (vérifié `mobile-app-ANALYSE.md` §4-5) : LeBonCoin bloque le
> fetch serveur (DataDome). La solution est d'extraire le texte ET les URLs
> d'images **on-device** (vrai navigateur de l'utilisateur, déjà au-delà du mur),
> puis d'envoyer `raw_text + image_urls`. La capacité à exécuter une **WebView +
> injection JS** pour lire `document.body.innerText` et les `<img src>` de la
> galerie est donc le critère technique discriminant.

### Option A — React Native + Expo
- **Cohérence stack** : réutilise React/TypeScript (le `frontend/` web est déjà
  React/Next 16). Le rendu du rapport (`ApiResult`) peut largement réutiliser la
  logique de présentation existante.
- **Extraction on-device** : `react-native-webview` permet `injectedJavaScript` +
  `onMessage` → lecture de `innerText` et des `<img src>`/`data-src`/`srcset` de
  la galerie. Faisable et documenté. Déroulé du lazy-load = effort supplémentaire
  (scroll programmatique avant lecture).
- **Partage natif** : Share Extension iOS / intent-filter Android faisables via
  modules natifs (Expo dev build, pas Expo Go).
- **Stores** : les deux. EAS Build simplifie la CI/signature.
- **Effort** (`mobile-app-ANALYSE.md`) : ~4-8 sem dev solo.
- **Risques** : modules natifs (share extension) sortent d'Expo « managed pur » →
  dev build. Nouveau pipeline CI/CD mobile à maintenir.

### Option B — Wrapper web (Capacitor / PWABuilder)
- **Cohérence stack** : réutilise directement le web existant (1 codebase).
- **Extraction on-device** : Capacitor `@capacitor/browser` ou WebView interne +
  plugin → faisable mais l'injection JS cross-origin dans une page tierce (LBC)
  est plus contrainte qu'avec `react-native-webview` (sandbox WebView, CSP de la
  page cible). À tester avant de s'engager.
- **Stores** : Play facile ; **App Store risqué** (règle Apple 4.2 « minimum
  functionality » recale les simples wrappers de site). Il FAUT une vraie fonction
  native (partage/OCR) pour passer — ce qui annule une partie de l'avantage
  « 0 code natif ».
- **Effort** : ~1-2 sem. Le moins cher.
- **Risques** : ping-pong de rejet Apple ; injection JS cross-origin plus fragile.

### Option C — Flutter
- **Cohérence stack** : **3e langage** (Dart) à maintenir en plus de Python +
  TypeScript. Réécriture complète de la présentation. Difficile à justifier pour
  un MVP solo à < 1 €/mois.
- **Extraction on-device** : `webview_flutter` + JS channel → faisable, équivalent
  RN.
- **Effort** : ~6-10 sem. Le plus cher.
- **Recommandation** : à écarter sauf raison externe (équipe Flutter existante).

### Option D — PWA seule (pas de store)
- **Cohérence stack** : ajout d'un manifest + service worker au `frontend/` web.
- **Extraction on-device** : ⚠️ **limite majeure** — une PWA dans un navigateur
  mobile **ne peut PAS** ouvrir une page tierce (LBC) et y injecter du JS
  cross-origin (same-origin policy stricte, pas de WebView contrôlée). Le Web Share
  Target API reçoit l'URL ou du texte partagé, mais ne peut pas « scraper »
  on-device la page d'un autre domaine. Donc **la PWA ne débloque PAS LeBonCoin**
  par WebView ; elle reste tributaire du partage de texte (souvent juste l'URL
  depuis l'app LBC).
- **Stores** : non.
- **Effort** : ~1-2 j.
- **Intérêt réel** : **tester l'appétit mobile** à coût quasi nul avant d'investir
  dans le natif. NE résout PAS le point dur on-device.

### Recommandation (À ARBITRER — Q2)
**React Native + Expo** est le meilleur rapport effort/résultat *si* l'objectif est
une app store durable qui débloque LeBonCoin : cohérence avec le stack TS, WebView
contrôlée pour l'extraction on-device, fonctions natives pour passer Apple 4.2.
**Mais** je challenge l'engagement immédiat : commencer par une **PWA (Option D)
+ instrumentation** pour *mesurer* la part d'usage mobile et l'appétit, avant de
financer 4-8 semaines de natif, est plus aligné avec la discipline « valider avant
d'investir » du fil rouge CONTEXT §9. La PWA ne débloque pas LBC, mais elle valide
l'hypothèse d'usage à coût marginal. **Décision structurante, remontée en Q2.**

---

## 4. Dépendances, ordre et risques

### 4.1 Dépendances et ordre
- **Phase 1 → Phase 2** : Phase 1 (contrat `image_urls`) est un **prérequis
  satisfait** du parcours « conserver les photos en raw_text ». Aucun prérequis
  backend manquant pour un périmètre Tier 1.
- **Spike LBC photo** : TRANCHÉ (Option 1, `mobile-app-ANALYSE.md` §5, 2026-06-23).
  Pas de blocage.
- **Spike WebView / injection JS on-device** : **NON FAIT.** La faisabilité réelle
  de l'extraction texte + galerie depuis LBC dans une WebView (challenge cookies,
  CSP, lazy-load) n'a PAS été prouvée par un essai. C'est le **risque technique
  n°1 non levé** de la Phase 2. À acter comme spike préalable (cf. Q3).
- **Push (Tier 2) dépend de** : auth/identité d'appareil + persistance d'analyses
  + couche pHash. Cumule les mêmes bloqueurs que CONTEXT §9.6 (watchlist différée :
  auth inexistante + pas de domaine email). **OUT jour 1.**
- **Comptes développeur stores** : Apple 99 $/an, Google 25 $ one-shot
  (`mobile-app-ANALYSE.md` §2). Geste humain / coût externe, prérequis de toute
  publication.

### 4.2 Risques d'anti-pattern (CONTEXT §11 / CLAUDE §1)
1. **RGPD — photos et données personnelles.** Le parcours `image_urls` reste
   conforme tant qu'on respecte l'invariant Phase 1 : URLs en transit, jamais
   loggées, jamais stockées, jamais re-fetchées serveur (`_sanitize_client_image_urls`
   ne logge qu'un compteur, `main.py:644`). ⚠️ L'app mobile NE DOIT PAS introduire
   de stockage de photos/URLs côté appareil persistant et synchronisé sans
   consentement. Le **chantier push** (pHash, token APNs/FCM, persistance
   d'analyses) est un **saut de posture RGPD majeur** identique à §9.6 (stockage
   nominatif durable, profilage, notif récurrente ⇒ consentement, désinscription,
   rétention, registre). À garder OUT jour 1 et à traiter comme décision produit
   distincte (`mobile-app-ANALYSE.md` §6).
2. **Redistribution d'annonce (anti-pattern §11.3).** L'app extrait UNE annonce,
   sur l'appareil de l'utilisateur, à sa demande, non stockée ni redistribuée →
   aligné §11.3 (c'est le copier-coller que l'utilisateur peut déjà faire). Le
   `mobile-app-ANALYSE.md` §4 le pose explicitement. Garde-fou : ne jamais
   constituer côté serveur une base d'annonces LBC/tierces à partir des analyses
   mobiles (ce serait de la réagrégation).
3. **Scraping on-device — légalité / ToS.** Risque modéré et borné : WebView dans
   la session du navigateur de l'utilisateur, action initiée par lui, une annonce.
   L'option D (« durcir le fetch serveur » via proxies résidentiels / solveur
   anti-bot) est **à déconseiller** (course à l'armement, zone grise juridique, LBC
   a un historique contentieux scraping) — déjà écartée `mobile-app-ANALYSE.md` §4.
4. **Pas d'estimation de prix / pas de DVF / pas de conseil juridique.** L'app ne
   fait que présenter `ApiResult` (déjà conforme côté backend). Vigilance : une UI
   mobile ne doit pas ré-introduire un « ce bien vaut X € » dans une fonction
   native (ex. comparateur de visite). À verrouiller dans la future spec UI.
5. **Coût.** Plus d'usage mobile = plus d'appels OpenAI (analyse) + Google Routes
   (travel-times). Cohérent avec MVP < 1 €/mois tant que le trafic reste faible ;
   le rate-limit `/analyze` (10/60s) et le cache LLM/photo bornent l'abus.
   Recommandation déjà notée CONTEXT §9.4 / §3.3 : poser un **usage limit OpenAI
   hard** AVANT toute campagne de publication store (un succès de lancement pourrait
   faire déraper la facture).
6. **Nouveaux vendors.** Expo/EAS (build/CI mobile) = nouvelle dépendance d'outil,
   pas un vendor backend. Push (APNs/FCM) = nouveau vendor + token persistant
   (OUT jour 1). Stores = comptes développeur payants. À acter en Q1/Q2.
7. **Pas de secret en clair.** L'app mobile embarque `NEXT_PUBLIC_API_URL`
   (publique). Aucune clé OpenAI/Google côté app (tout passe par le backend) —
   invariant à maintenir : l'app ne doit JAMAIS porter de secret backend.

### 4.3 Taille du chantier — à découper
La Phase 2 « app mobile » est, contrairement à la Phase 1 (~10 lignes backend),
un **chantier greenfield potentiellement très gros et pluri-disciplinaire**
(mobile + natif + stores + éventuellement backend push). Il NE doit pas être traité
comme un requirement atomique de l'atelier. Découpage proposé (à arbitrer Q1) :
- **Phase 2a** — Spike on-device (prouver WebView + injection JS extrait texte +
  galerie sur LBC). Petit, lève le risque n°1.
- **Phase 2b** — App minimale (1 techno) : parcours `/analyze` `raw_text`+
  `image_urls` + 1 fonction native (partage). Branche sur l'API existante.
- **Phase 2c** — Fonctions natives complémentaires (OCR, géoloc).
- **Phase 3 (séparée)** — Push / re-check / pHash + cap d'architecture (auth/PII).
  À traiter comme un chantier produit distinct, pas un sous-lot de l'app.

---

## 5. Challenge du requirement (posture adversariale)

- **Le requirement « Phase 2 = app mobile » n'est pas écrit dans CONTEXT.md
  (§0).** Avant tout, faire confirmer et reporter la décision dans la doc de
  vérité. Construire une app que la roadmap officielle ignore est un risque de
  pilotage.
- **Sur-dimensionnement probable pour un MVP < 1 €/mois sans usage validé.** Le
  fil rouge CONTEXT §9 a justement *différé* watchlist (9.6), email (9.2), A/B
  (9.8), monitoring (9.3) au motif « prématuré à trafic quasi nul, sans auth, sans
  domaine ». Une app native (4-8 sem + comptes store + CI mobile + reviews) est un
  investissement bien plus lourd que ces chantiers différés. **Cohérence
  exigée** : si 9.6 est différé faute de signal d'usage, sur quelle base
  finance-t-on une app native ? La réponse honnête est probablement « valider
  l'appétit mobile d'abord » (PWA + events), pas « écrire RN tout de suite ».
- **Y a-t-il plus simple ?** Oui : (1) une **PWA** répare la dette responsive et
  teste l'usage mobile à ~1-2 j ; (2) la fonction qui apporte le plus de valeur
  immédiate (partage natif depuis les apps immo) peut être un **wrapper minimal**
  si l'on accepte le risque Apple. Le natif complet n'est justifié que si les
  events montrent un usage mobile réel ET que le déblocage LBC on-device est prouvé
  (spike 2a).
- **Le vrai point dur n'est pas la techno, c'est le spike on-device non fait.**
  Choisir RN vs Flutter vs wrapper avant d'avoir prouvé qu'on peut extraire texte +
  galerie LBC dans une WebView, c'est mettre la charrue avant les bœufs.

---

## 6. QUESTIONS POUR L'HUMAIN (GATE 1)

Numérotées, chacune avec options et recommandation. Aucune n'est tranchée par
l'analyste. **Q0 et Q1 sont bloquantes** : tout le reste en dépend.

### Q0 (BLOQUANTE) — « Phase 2 = app mobile » est-il bien le requirement ?
Le chantier mobile n'est cadré que dans `mobile-app-ANALYSE.md`, **pas dans
CONTEXT.md** (§0). La roadmap officielle pointe ailleurs (issue #100 C2, incrément 2
clustering photo, scoring, dette).
- (a) Oui, l'app mobile est le prochain chantier → **reporter la décision dans
  CONTEXT.md** (§0 + §8/§11bis) avant de spécifier, pour qu'elle ne soit plus
  orpheline.
- (b) Non / pas encore → traiter d'abord la roadmap CONTEXT, garder
  `mobile-app-ANALYSE.md` comme étude.
- **Reco** : trancher (a) ou (b) explicitement. Si (a), exiger le report dans
  CONTEXT.md (sinon dérive doc/code, à rebours de la discipline de l'atelier).

### Q1 (BLOQUANTE) — Périmètre exact de la Phase 2 (c'est greenfield et gros)
- (a) **Tier 1 seul** (parcours `/analyze` raw_text+image_urls + partage natif +
  OCR + géoloc), push EXCLU. Branche sur l'API existante, **0 backend nouveau**.
- (b) Tier 1 **+ Tier 2 push** dès le départ → ouvre le cap d'architecture
  (auth/PII, persistance d'analyses, pHash) = chantier × plusieurs.
- (c) **Spike + PWA d'abord** (valider l'appétit mobile et le déblocage on-device)
  AVANT de choisir le périmètre natif.
- **Reco** : **(a) pour le natif jour 1, précédé de (c) si l'usage mobile n'est pas
  encore mesuré.** Garder push (Tier 2) comme **Phase 3 distincte** : c'est le seul
  lot qui détruit les invariants « anonyme / sans état » (mêmes bloqueurs que
  CONTEXT §9.6, RGPD majeur). Ne jamais le fondre dans « l'app jour 1 ».

### Q2 — Choix de la techno mobile
- (a) **React Native + Expo** — cohérence TS, WebView contrôlée (débloque LBC),
  stores OK, ~4-8 sem.
- (b) **Wrapper web (Capacitor)** — 1 codebase, ~1-2 sem, **Apple 4.2 risqué**,
  injection JS cross-origin plus fragile.
- (c) **Flutter** — 3e langage, réécriture, ~6-10 sem → à écarter sauf raison
  externe.
- (d) **PWA seule** — ~1-2 j, **ne débloque PAS LBC** (pas de WebView cross-origin),
  mais teste l'appétit mobile à coût quasi nul.
- **Reco** : **RN/Expo** si l'objectif est une app store durable qui débloque LBC ;
  **PWA (d) en préalable** si l'usage mobile n'est pas encore validé (mesurer avant
  d'investir, aligné CONTEXT §9). Flutter écarté.

### Q3 — Spike on-device préalable (lever le risque technique n°1)
La faisabilité d'extraire texte + galerie LBC via WebView + injection JS n'est PAS
prouvée (le spike LBC photo, lui, est tranché côté CDN d'images).
- (a) Faire un **spike on-device** (WebView, lecture `innerText` + `<img>`/`srcset`,
  déroulé lazy-load) sur 3-5 annonces LBC réelles AVANT de choisir/figer la techno.
- (b) Présumer que ça marche et engager directement le développement.
- **Reco** : **(a).** Petit, isole le risque dominant, et son résultat conditionne
  Q2 (si l'injection JS cross-origin est trop contrainte en wrapper, RN devient
  obligatoire). Effet de bord : WebView + partage + OCR sont précisément les
  fonctions natives qui crédibilisent l'app face à Apple 4.2.

### Q4 — Comptes développeur stores et usage limit OpenAI (prérequis externes)
- Comptes : Apple 99 $/an + Google 25 $ one-shot (geste humain, coût externe).
- **Usage limit OpenAI hard** (CONTEXT §9.4 / §3.3) : non encore posé. Un succès de
  lancement store pourrait faire déraper la facture (analyse + travel-times).
- **Reco** : **poser l'usage limit OpenAI AVANT toute publication store**
  (5 min, sécurité financière), et n'acquérir les comptes développeur que si Q1 ⇒
  publication réelle (pas pour une PWA).

### Q5 — Réutilisation de la présentation web vs réécriture
- (a) Réutiliser la logique de rendu `ApiResult` du `frontend/` (composants
  `components/design/`) dans l'app (favorisé par RN/TS, partiel).
- (b) Réécrire la présentation mobile from scratch (Flutter impose ; RN permet une
  réutilisation partielle de la logique, pas des composants Next/DOM).
- **Reco** : dépend de Q2. Si RN, **réutiliser la logique TS et le design system
  comme référence**, sans réutiliser littéralement les composants Next (DOM ≠ RN).
  À détailler en spec, pas bloquant pour GATE 1.

---

## DÉCISIONS À PRENDRE PAR L'HUMAIN (synthèse)

1. **Q0 (bloquante)** — Confirmer que l'app mobile est le requirement Phase 2 et la
   **reporter dans CONTEXT.md** (aujourd'hui absente de la doc de vérité).
2. **Q1 (bloquante)** — Fixer le périmètre : Tier 1 seul (reco) vs Tier 1+push.
   Garder le push (Tier 2/3) comme chantier distinct (cap d'architecture, RGPD).
3. **Q2** — Choisir la techno : RN/Expo (reco si app store durable) vs wrapper vs
   PWA d'abord (reco si l'appétit mobile n'est pas validé). Flutter écarté.
4. **Q3** — Lancer un **spike on-device** (WebView + injection JS sur LBC) avant de
   figer la techno : c'est le risque technique non levé n°1.
5. **Q4** — Poser l'**usage limit OpenAI hard** avant publication ; n'acquérir les
   comptes store que si publication réelle décidée.

## Estimation grossière de l'effort par option (ordres de grandeur, pas fausse précision)

> Reprend `mobile-app-ANALYSE.md` §2, augmenté du spike on-device et du périmètre
> Tier 1. Dev solo. Hors temps de review store (1-7 j + itérations de rejet).

| Option / lot | Effort | Backend nouveau | Débloque LBC | Sur les stores |
|---|---|---|---|---|
| Spike on-device (Q3) | ~1-3 j | non | (prouve / infirme) | n/a |
| PWA seule (Q2-d) | ~1-2 j | non (CORS si domaine) | **non** | non |
| Wrapper Capacitor + 1 fct native (Q2-b) | ~1-2 sem | non | partiel (à prouver) | Play oui / Apple risqué |
| RN + Expo, Tier 1 (Q2-a + Q1-a) | ~4-8 sem | **non** (API Phase 1 suffit) | oui (WebView) | oui (les deux) |
| Flutter, Tier 1 (Q2-c) | ~6-10 sem | non | oui (WebView) | oui (les deux) |
| **+ Tier 2 push (Phase 3 distincte)** | **+plusieurs sem** | **OUI lourd** (auth/PII, persistance, pHash, cron) | n/a | n/a |

Lecture : pour un périmètre Tier 1, **le backend est prêt** (effort backend nul,
grâce à Phase 1). Le coût est entièrement côté app + stores. Le seul lot qui
rouvre un gros chantier backend (et un cap RGPD) est le push, à isoler.

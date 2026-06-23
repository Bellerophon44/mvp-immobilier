# SPEC — Mobile PHASE 2, Tranche 1 : la boucle minimale partage -> extraction -> /analyze -> résultat

> Rôle : SPEC-WRITER (GATE 2). Transforme l'analyse approuvée
> (`mobile-phase2-app-ANALYSE.md`), les arbitrages GATE 1 (`CONTEXT.md` §0 « App
> mobile — Phase 2 ») et le verdict du spike (`mobile-phase2-spike-PROTOCOLE.md`
> §9-10) en cahier des charges implémentable avec critères d'acceptation
> testables. Lecture seule sauf ce fichier. **N'implémente rien.**
>
> Sources relues (état réel, pas seulement la doc) :
> - `docs/specs/mobile-phase2-app-ANALYSE.md` (analyse, GATE 1 tranché).
> - `docs/specs/mobile-phase2-spike-PROTOCOLE.md` §9 (résultats) + §10 (verdict +
>   inputs pour la spec : `document.body.innerText`, `rule=ad-large` + dédup par
>   chemin, `firstUrl`, auto-scroll lazy-load, POST `raw_text` + `image_urls`).
> - `spikes/lbc-extraction/App.js` (code du spike qui marche : `firstUrl`,
>   `buildExtractor`, filtrage `rule=ad-large`, dédup par chemin, `postMessage`).
> - `frontend/lib/api.ts` (`AnalyzeRequestBody` avec `image_urls?`, `analyzeListing`,
>   forme de `ApiResult`).
> - `backend/app/main.py` (endpoint `/analyze`, mode `raw_text`,
>   `_sanitize_client_image_urls` : dédup -> `_is_safe_url` -> cap 50).
> - `backend/CLAUDE.md` §5/§10 (contrat `/analyze`, champs de `ApiResult` rendus
>   par le web), `CONTEXT.md` §0/§1.2/§11.
> - `.claude/lessons.md` (anti-faux-vert ; en particulier : prouver le transit
>   réel et pas « absence d'erreur » ; bornes aux valeurs exactes ; tester le
>   chemin réel pas la façade ; pour une inertie observer la dépendance terminale).

---

## 1. Objectif et périmètre

### 1.1 Objectif (1-2 phrases)
Livrer la **première tranche verticale et fonctionnelle** de l'app mobile RN/Expo :
recevoir une annonce LeBonCoin (partage natif ou collage manuel), en extraire
on-device le texte + les URLs de la galerie via WebView + injection JS, POSTer
`raw_text` + `image_urls` à `/analyze` (backend Phase 1, inchangé), et afficher le
rapport de cohérence dans un écran lisible.

### 1.2 Périmètre IN (cette tranche)
1. Réception d'une annonce : **collage manuel d'URL ou de texte** dans un champ
   (`firstUrl` extrait la 1ʳᵉ URL http(s) du payload). [GATE 2 : le share intent
   natif est SORTI de cette tranche → sous-incrément suivant, cf. §2.2.]
2. Chargement de l'URL dans une **WebView** ; **auto-scroll** de la galerie pour
   déclencher le lazy-load ; **injection JS** d'extraction (`document.body.innerText`
   pour le texte ; URLs de galerie filtrées `rule=ad-large`, dédupliquées par
   chemin, exclusion `ad-image` / `bo-*` / `pp-small`).
3. **POST `/analyze`** avec `raw_text` (texte) + `image_urls` (galerie) vers le
   backend Phase 1. **Rien à changer côté serveur.**
4. **Écran de résultat** affichant au minimum `global_score`, `verdict`,
   `confidence`, les 3 `pillars`, et `actions` (cf. §4.4 pour la liste exacte).

### 1.3 Périmètre OUT (explicite, pour borner le dev — pour plus tard)
- OCR de captures d'écran (Tier 1 ultérieur).
- Géoloc « je suis devant le bien » / appel `POST /travel-times` (Tier 1 ultérieur).
- Multi-portails autres que LBC (SeLoger, Bien'ici…) : architecture extensible mais
  **un seul host CDN câblé** (`img.leboncoin.fr`).
- Notifications push, re-list, baisse de prix, pHash, persistance d'analyses (=
  **Phase 3 distincte**, cap d'architecture auth/PII — `CONTEXT.md` §0).
- Design abouti / parité pixel avec le web (MVP lisible suffit).
- Comptes développeur stores / publication App Store / Play Store.
- Gestion d'historique d'analyses, comptes utilisateur, auth.
- Upload d'octets d'images (Option 2 du spike — tranché inutile pour LBC).
- Émission d'`events` / instrumentation funnel mobile (peut être un sous-incrément
  suivant ; non requis pour livrer la boucle).

---

## 2. Décisions actées (GATE 1) et points à flaguer

### 2.1 Décisions actées (reprises de GATE 1 / spike)
| Décision | Valeur actée | Source |
|---|---|---|
| Périmètre | **Tier 1, tranche 1 = la boucle minimale** ; push = Phase 3 | `CONTEXT.md` §0 |
| Techno | **React Native + Expo, SDK 54** (compat Expo Go validée au spike), `react-native-webview`, **TypeScript** | spike §10, GATE 1 |
| Backend | **0 backend nouveau** : `/analyze` Phase 1 suffit (`raw_text` + `image_urls`) | analyse §2.2 |
| Extraction texte | `document.body.innerText` | spike §10.1 |
| Extraction galerie | garder `rule=ad-large`, dédup par **chemin** (`origin+pathname`), exclure `ad-image` / `bo-*` / `pp-small` | spike §9, §10.2 |
| Partage | extraire la **1ʳᵉ URL http(s)** du payload partagé (`firstUrl`) | spike §9 (finding), §10.3 |
| Lazy-load | **auto-scroller** la galerie avant collecte | spike §10.4 |
| RGPD | extraction sur la **seule** annonce ouverte ; aucun stockage texte/photos ; URLs jamais persistées/loggées (garanti serveur) | spike §10.6, analyse §4.2 |

### 2.2 Décisions de cette spec (par défaut, non bloquantes mais flaguées si structurantes)
- **D-EMPLACEMENT (À FLAGUER — décision humaine, structurante).** Défaut proposé :
  dossier **`mobile/`** dans le monorepo (proximité du contrat `/analyze`,
  réutilisation des types de `frontend/lib/api.ts`, une seule CI). Alternative :
  **repo séparé** (isole le pipeline EAS Build mobile, évite d'alourdir la CI web).
  Recommandation : `mobile/` pour cette tranche (réutilisation de types > isolation
  CI à ce stade). **Ne pas trancher sans l'humain** : impacte la CI, le tooling et
  la suite des tranches.
- **D-BACKEND-URL.** L'URL backend est **configurable** (prod / staging / local),
  jamais hardcodée, jamais un secret. Mécanisme proposé : variable d'environnement
  Expo publique `EXPO_PUBLIC_API_URL` (équivalent du `NEXT_PUBLIC_API_URL` web),
  lue à la construction du body. Défaut de dev : staging. Aucune clé OpenAI/Google
  côté app (tout passe par le backend) — invariant.
- **D-PARTAGE-INCREMENT (À FLAGUER si jugé trop lourd).** Le share intent natif iOS
  (Share Extension) / Android (intent-filter `SEND`/`SEND text`) sort de l'Expo Go
  « managed pur » et exige un **dev build** (`expo-share-intent` ou config plugin +
  prebuild). Si l'intégration du share intent natif est trop lourde pour garder
  cette tranche **fine**, la décision proposée est : **livrer d'abord le fallback
  « coller l'URL/texte » (couvert intégralement par les AC famille A, testable sans
  device), et traiter le share intent natif comme le sous-incrément immédiatement
  suivant** (AC famille B, vérifié sur device). La logique `firstUrl` est commune
  aux deux chemins, donc le share intent ne fait que **brancher une nouvelle source
  d'entrée** sur une logique déjà testée. **Décision à confirmer par l'humain** : si
  le share intent doit être DANS cette tranche, le dire (sinon il bascule en
  sous-incrément).
- **D-RENDU.** MVP lisible, **pas** la parité pixel du web. Champs minimaux affichés
  fixés en §4.4. Pas de réutilisation littérale des composants Next/DOM (DOM ≠ RN) ;
  réutilisation de la **logique TS** et des **types** (`ApiResult`) seulement.
- **D-IMAGE-HOSTS.** Liste des hosts CDN d'images en constante (`['img.leboncoin.fr']`),
  extensible, mais **un seul** câblé pour cette tranche (LBC).

### 2.3 Points laissés ouverts (ne pas inventer — remontés en §8)
- Choix `mobile/` vs repo séparé (D-EMPLACEMENT).
- Share intent natif DANS la tranche vs sous-incrément suivant (D-PARTAGE-INCREMENT).
- Robustesse à terme : sélection scopée au **conteneur DOM de la galerie** plutôt
  qu'au nom de `rule` (le spike §9 le note ; **hors tranche 1**, on garde `rule`
  en dur conformément au code qui marche).

---

## 3. Architecture cible

### 3.1 Arborescence proposée (`mobile/`, sous réserve D-EMPLACEMENT)
```
mobile/
├── app.json / app.config.ts   # config Expo SDK 54 (name, slug, scheme, plugins)
├── package.json               # expo, react-native, react-native-webview, typescript, jest
├── tsconfig.json              # TypeScript strict (cohérence repo)
├── babel.config.js
├── jest.config.js             # preset jest-expo + react-native-testing-library
├── App.tsx                    # racine : navigation minimale (saisie -> webview -> résultat)
├── src/
│   ├── extract/
│   │   ├── firstUrl.ts        # extraction 1ere URL http(s) d'un payload de partage/collage
│   │   ├── gallery.ts         # filtrage/dédup des URLs d'images (rule=ad-large, exclusions)
│   │   └── injectedScript.ts  # build du JS injecté dans la WebView (texte + images)
│   ├── api/
│   │   ├── types.ts           # ApiResult & co. (copie/symlink du contrat frontend/lib/api.ts)
│   │   └── analyze.ts         # buildAnalyzeBody() + analyzeListing() (POST /analyze)
│   ├── screens/
│   │   ├── InputScreen.tsx    # champ collage + (sous-incrément) entrée share intent
│   │   ├── WebViewScreen.tsx  # WebView + auto-scroll + injection + onMessage
│   │   └── ResultScreen.tsx   # rendu ApiResult (score + piliers + actions)
│   └── config.ts              # lecture EXPO_PUBLIC_API_URL (jamais hardcodée)
└── __tests__/                 # tests Jest des modules purs (famille A)
    ├── firstUrl.test.ts
    ├── gallery.test.ts
    └── analyzeBody.test.ts
```

### 3.2 Dépendances
- `expo` (SDK 54), `react`, `react-native`, `react-native-webview`.
- `typescript`, `@types/react`.
- Dev/test : `jest`, `jest-expo`, `@testing-library/react-native`, `@testing-library/jest-native`.
- Sous-incrément share intent (si retenu) : `expo-share-intent` (ou config plugin
  natif) + **dev build** (hors Expo Go).
- **Aucune** dépendance portant un secret ; aucune clé tierce embarquée.

### 3.3 Configuration backend
- `EXPO_PUBLIC_API_URL` (env publique Expo) : URL racine du backend. Le code POST
  cible `${EXPO_PUBLIC_API_URL}/analyze`.
- Valeurs documentées (README de `mobile/`) : prod
  `https://api.coherence-metz.fr` (ou `https://backend-frosty-sound-441-docker.fly.dev`),
  staging `https://coherence-staging.fly.dev`, local `http://<ip-lan>:8080`.
- **App native (RN)** : pas soumise au CORS navigateur → aucun changement
  `CORS_ORIGINS` requis (analyse §2.3).
- Rate-limit `/analyze` = 10 req / 60 s (existant) : l'app ne doit pas spammer (un
  POST par action utilisateur explicite).

### 3.4 Contrat technique consommé (rappel — aucune modification)
- Endpoint : `POST /analyze`, body JSON.
- Body émis par cette tranche (sous-ensemble de `AnalyzeRequestBody`) :
  ```json
  {"raw_text": "<innerText de l'annonce>", "image_urls": ["https://img.leboncoin.fr/api/v1/.../image.jpg?rule=ad-large", ...]}
  ```
  - `raw_text` : string non vide.
  - `image_urls` : `string[]` (peut être omis ou vide ; le serveur traite `[]`
    comme « pas d'images », cf. `_sanitize_client_image_urls`).
  - **Ne JAMAIS** émettre `url` dans cette tranche (on POSTe le texte extrait
    on-device, pas l'URL à re-fetcher serveur — le serveur serait bloqué par
    DataDome ; c'est tout l'intérêt de l'extraction on-device).
  - Champs `district` / `address` : non émis dans cette tranche (OUT).
- Réponse : `ApiResult` (cf. `frontend/lib/api.ts` l.69-82). Codes : 400 (aucun
  input), 422 (URL inaccessible — non atteint ici car on n'envoie pas `url`), 500
  (erreur interne). L'app gère 4xx/5xx en affichant le `detail` renvoyé.

---

## 4. Spécification fonctionnelle de la boucle

### 4.1 Entrée (saisie / partage)
- L'utilisateur fournit un payload : soit le texte de partage natif (« Voici une
  annonce … sur leboncoin: https://… »), soit un collage manuel (URL nue ou texte
  contenant une URL).
- `firstUrl(payload)` renvoie la **1ʳᵉ** sous-chaîne `https?://...` (jusqu'au
  premier espace), ou `null` si aucune. Si `null` : message d'erreur lisible
  (« Aucune URL http(s) trouvée »), pas de navigation WebView. Reprend exactement
  la regex du spike : `/https?:\/\/[^\s]+/i`.

### 4.2 Chargement WebView + lazy-load + injection
- La WebView charge `firstUrl(payload)` avec un User-Agent mobile réaliste (cf.
  spike : iOS Safari / Android Chrome) pour que la page se comporte comme pour un
  humain (DataDome ne se déclenche pas sur un vrai appareil — spike §9 Niveau 2).
- L'utilisateur ferme la bannière cookies et fait défiler la galerie ; l'app
  **auto-scrolle** (`window.scrollTo(0, document.body.scrollHeight)` dans le script
  injecté) puis attend (~1500 ms, cf. spike) avant collecte, pour déclencher le
  lazy-load.
- Le script injecté (`injectedScript.ts`, repris de `buildExtractor`) :
  - lit `document.body.innerText` -> `text` ;
  - parcourt les `<img>`, prend la plus grande candidate de `srcset` sinon `src` ;
  - filtre au(x) host(s) CDN (`img.leboncoin.fr`) ;
  - ne garde que `rule=ad-large`, dédup par `origin+pathname`, reconstruit l'URL en
    `origin+pathname+'?rule=ad-large'` ;
  - renvoie au natif via `window.ReactNativeWebView.postMessage(JSON.stringify({ ok, text, image_urls }))`.
- Le natif (`onMessage`) parse le message ; sur `ok=false` ou message illisible :
  message d'erreur lisible, pas de POST.

### 4.3 Appel `/analyze`
- `buildAnalyzeBody(text, imageUrls)` construit `{ raw_text: text, image_urls: imageUrls }`
  (omet `image_urls` si vide n'est pas requis — le serveur tolère `[]` ; voir AC9
  pour la forme exacte attendue).
- `analyzeListing` POST le body à `${EXPO_PUBLIC_API_URL}/analyze`, header
  `Content-Type: application/json`. Sur réponse non-ok : lit `detail` et lève/affiche.

### 4.4 Rendu du résultat (champs minimaux — D-RENDU)
L'écran de résultat affiche **au minimum**, depuis `ApiResult` :
1. `global_score` (0-100) et `verdict` (ex. « Cohérence forte »).
2. `confidence` (« Élevée » / « Moyenne » / « Faible »).
3. Les **3** `pillars` dans l'ordre du contrat `[prix, transparence, risques]`,
   chacun : `label`, `verdict`, `explanation` (et `points`/`max` si présents).
4. `actions.questions` (liste) et `actions.negotiation` (liste). `actions.highlights`
   affiché s'il est présent (optionnel, rétro-compatible).
5. `local_context` : optionnel ; si présent, afficher au moins `district` + `summary`
   (le détail facts/claims est un bonus, **non requis** pour cette tranche).
- **Anti-pattern produit** : l'écran ne doit afficher AUCUNE estimation de prix
  « ce bien vaut X € ». Il rend tel quel ce que le backend renvoie (déjà conforme).
  Reprendre le disclaimer `CONTEXT.md` §2.2 (« …ne constitue pas une estimation de
  prix »).

---

## 5. Critères d'acceptation

> Deux familles SÉPARÉES car l'environnement de test diffère. Famille A = logique
> pure, **automatisable** (Jest / React Native Testing Library), falsifiable, porte
> sur le **résultat/transit réel** (pas « ne plante pas »). Famille B = comportement
> device / bout-en-bout, **non automatisable en sandbox** (pas de device, egress LBC
> bloqué) -> **checklist manuelle** sur device, chaque item avec critère de
> réussite/échec.
>
> Leçon anti-faux-vert appliquée (`.claude/lessons.md`) : un AC qui ne peut pas
> échouer n'a aucune valeur ; pour prouver qu'on envoie bien `image_urls`, asserter
> la **liste EXACTE** transmise, pas « la requête part ». Bornes aux valeurs exactes.

### 5.A Famille A — logique pure, testable en automatique (Jest)

#### AC1 — `firstUrl` : texte + URL -> extrait l'URL exacte
`firstUrl("Voici une annonce sur leboncoin: https://www.leboncoin.fr/ad/ventes_immobilieres/123 super")`
**renvoie exactement** `"https://www.leboncoin.fr/ad/ventes_immobilieres/123"`.
(Falsifiable : échoue si la regex capte l'espace suivant ou rate le préfixe texte.)

#### AC2 — `firstUrl` : URL nue -> la renvoie telle quelle
`firstUrl("https://www.leboncoin.fr/ad/ventes_immobilieres/456")` renvoie
exactement la même chaîne. Variante `http://` acceptée (insensible à la casse :
`HTTPS://...` capté).

#### AC3 — `firstUrl` : plusieurs URLs -> la 1ʳᵉ
`firstUrl("a https://un.example/x b https://deux.example/y")` renvoie exactement
`"https://un.example/x"` (jamais la 2ᵉ, jamais une concaténation).

#### AC4 — `firstUrl` : aucune URL -> erreur gérée (renvoie `null`)
`firstUrl("juste du texte sans lien")` renvoie `null`. `firstUrl("")` renvoie
`null`. `firstUrl(undefined)` / `firstUrl(null)` renvoient `null` (pas
d'exception). (Falsifiable : échoue si la fonction lève ou renvoie `""`/`undefined`.)

#### AC5 — Galerie : garde `ad-large`, exclut `ad-image` / `bo-*` / `pp-small`
La fonction de filtrage, sur l'entrée :
| URL d'entrée | rule | attendu |
|---|---|---|
| `https://img.leboncoin.fr/api/v1/img/A.jpg?rule=ad-large` | ad-large | **gardée** |
| `https://img.leboncoin.fr/api/v1/img/B.jpg?rule=ad-image` | ad-image | exclue |
| `https://img.leboncoin.fr/api/v1/img/C.jpg?rule=bo-thumb` | bo-thumb | exclue |
| `https://img.leboncoin.fr/api/v1/img/D.jpg?rule=pp-small` | pp-small | exclue |
| `https://img.leboncoin.fr/api/v1/img/E.jpg?rule=ad-thumb` | ad-thumb | exclue |
| `https://img.leboncoin.fr/api/v1/img/F.jpg` (sans rule) | (aucune) | exclue |
Sortie attendue (ordre préservé) : **exactement** `["https://img.leboncoin.fr/api/v1/img/A.jpg?rule=ad-large"]`.
(Falsifiable : échoue si une exclusion fuit ou si l'ordre/contenu diffère.)

#### AC6 — Galerie : exclut les hosts non-CDN
Une URL hors `img.leboncoin.fr` (ex. `https://www.googletagmanager.com/x.png?rule=ad-large`)
est **exclue** même si `rule=ad-large`. Sur une entrée ne contenant que des hosts
hors CDN : sortie = `[]`. (Falsifiable : échoue si le filtre host est absent.)

#### AC7 — Galerie : dédup par chemin + normalisation `ad-large`
Entrée contenant la **même image** sous plusieurs tailles/formes :
| URL d'entrée | rule |
|---|---|
| `https://img.leboncoin.fr/api/v1/img/P.jpg?rule=ad-large` | ad-large |
| `https://img.leboncoin.fr/api/v1/img/P.jpg?rule=ad-thumb` | ad-thumb |
| `https://img.leboncoin.fr/api/v1/img/P.jpg?rule=ad-large&w=800` | ad-large (variante query) |
| `https://img.leboncoin.fr/api/v1/img/Q.jpg?rule=ad-large` | ad-large |
Sortie attendue **exacte** (dédup par `origin+pathname`, normalisée
`origin+pathname+'?rule=ad-large'`, ordre de 1ʳᵉ apparition) :
`["https://img.leboncoin.fr/api/v1/img/P.jpg?rule=ad-large", "https://img.leboncoin.fr/api/v1/img/Q.jpg?rule=ad-large"]`.
(2 URLs, pas 1, pas 4. Falsifiable : échoue si la dédup compte la query string,
ou si elle écrase Q.)

#### AC8 — Galerie : cap éventuel et galerie vide
- Sur une entrée de **N > 50** images `ad-large` distinctes (chemins distincts), la
  sortie est tronquée à **exactement 50** (cohérent avec `MAX_INPUT_IMAGE_URLS=50`
  côté serveur ; on cappe aussi côté app pour ne pas envoyer inutilement). Les 50
  premières dans l'ordre de 1ʳᵉ apparition sont conservées (la 51ᵉ exclue).
- Sur une entrée **sans aucune** `ad-large` (page d'accueil LBC, cf. spike Niveau 2),
  la sortie est `[]`. (Falsifiable aux bornes : 50 conservées, 51 -> 50 ; off-by-one
  détecté.)

#### AC9 — `buildAnalyzeBody` : forme exacte du corps `/analyze`
- `buildAnalyzeBody("Appartement T3 ...", ["https://img.leboncoin.fr/x.jpg?rule=ad-large"])`
  renvoie **exactement** l'objet
  `{ raw_text: "Appartement T3 ...", image_urls: ["https://img.leboncoin.fr/x.jpg?rule=ad-large"] }`.
- Le corps **ne contient JAMAIS** la clé `url` (assertion explicite : `"url" in body === false`).
- Avec une galerie vide : le corps a `raw_text` et soit pas de clé `image_urls`,
  soit `image_urls: []` — fixer **une** des deux formes et l'asserter exactement
  (recommandé : omettre la clé quand vide). (Falsifiable : échoue si une clé
  parasite apparaît, si `url` fuit, ou si `image_urls` n'est pas la liste exacte.)

#### AC10 — Transit réel vers `/analyze` : la liste EXACTE est postée
Avec `fetch` mocké (capture du body), appeler `analyzeListing(text, imageUrls)`
puis asserter que le **body JSON réellement envoyé** (`JSON.parse(fetch.mock.calls[0][1].body)`)
est **strictement égal** à `{ raw_text: text, image_urls: imageUrls }` (mêmes
valeurs, même liste d'URLs, dans le même ordre), que l'URL appelée est
`${EXPO_PUBLIC_API_URL}/analyze`, la méthode `POST`, et l'en-tête
`Content-Type: application/json`.
(Leçon `mobile-phase1-image-urls` / cross-agence-inc2b : on asserte la liste
**exacte transmise**, pas « la requête part ». Falsifiable : échoue si l'app
filtre/réordonne les URLs avant l'envoi, ou omet `image_urls`.)

#### AC11 — `/analyze` non-ok : erreur remontée, pas de faux succès
Avec `fetch` mocké renvoyant `{ ok: false, status: 422, json: () => ({ detail: "msg backend" }) }`,
`analyzeListing(...)` **rejette** avec un message contenant `"msg backend"` (et ne
renvoie pas un `ApiResult` vide/factice). (Falsifiable : échoue si l'erreur est
avalée silencieusement.)

#### AC12 — `EXPO_PUBLIC_API_URL` : aucune URL backend hardcodée, aucun secret
Test statique/structurel : le code de construction de l'appel lit la config depuis
`EXPO_PUBLIC_API_URL` (via `config.ts`) et **ne contient pas** d'URL backend en dur
ni de chaîne ressemblant à une clé API (`sk-`, `AIza`, token). (Falsifiable : un
grep/test échoue si une URL `fly.dev`/`coherence-metz.fr` est codée en dur dans la
couche API, ou si une clé est présente.)

### 5.B Famille B — device / bout-en-bout : CHECKLIST MANUELLE sur device

> Non automatisable en sandbox (pas de device ; egress LBC hors allowlist). Chaque
> item est une étape vérifiable sur un appareil réel (Expo Go SDK 54 ou dev build),
> sur le réseau de l'utilisateur. Renseigner pour chaque item : annonce testée,
> observation, **PASS/FAIL**. Reprend la trame du spike §9 (déjà concluant), ici
> appliquée à l'app de la tranche, pas au harnais jetable.

#### AC-B1 — La WebView charge une annonce LBC sans captcha
Étape : coller/partager l'URL d'une **vraie annonce LBC** ; la WebView l'affiche.
- **Réussite** : la page d'annonce s'affiche (titre, prix, galerie) **sans mur
  DataDome / captcha** sur ≥ 4/5 annonces réelles testées.
- **Échec** : captcha, mur de login, ou page blanche -> remonter (peut rouvrir la
  stratégie ; cf. spike §5 signaux d'alerte).

#### AC-B2 — Après auto-scroll + extraction : `image_urls` non vide et toutes `ad-large`
Étape : sur une annonce avec galerie (≥ 4 photos), faire défiler puis « Extraire ».
- **Réussite** : le natif reçoit `image_urls` **non vide**, **toutes** en
  `?rule=ad-large`, et leur **nombre correspond au compteur de galerie affiché**
  (« 1/N ») à ± tolérance dédup, sur ≥ 4/5 annonces. ≥ 80 % des photos visibles
  captées (critère du spike §5).
- **Échec** : `image_urls` vide sur une annonce qui a des photos ; présence d'URLs
  `ad-image` (photos d'AUTRES annonces -> `photo_status` faux) ; photos en
  `blob:`/`data:` non réutilisables.

#### AC-B3 — Le texte extrait contient titre + description
Étape : vérifier le `raw_text` extrait (longueur + échantillon).
- **Réussite** : `raw_text` contient le titre, le prix et la description (cf. spike :
  ~5700 caractères sur une annonce réelle), sur ≥ 4/5 annonces.
- **Échec** : texte vide, tronqué au seul titre, ou contenu d'overlay cookies
  uniquement.

#### AC-B4 — Le POST `/analyze` renvoie un résultat exploitable
Étape : l'app POST `raw_text` + `image_urls` vers le backend configuré (staging),
et reçoit la réponse.
- **Réussite** : HTTP 200 + `ApiResult` avec `global_score` numérique [0-100],
  `verdict` non vide, 3 `pillars`. Quand `image_urls` non vide et claim local
  éligible, les `local_context.claims` portent un `photo_status` renseigné (preuve
  de bout en bout du transit des URLs — cf. spike §4.7).
- **Échec** : 4xx/5xx non géré, ou `global_score` absent.

#### AC-B5 — L'écran de résultat affiche score + sections
Étape : après réponse, l'écran de résultat s'affiche.
- **Réussite** : `global_score`, `verdict`, `confidence`, les **3** piliers (label
  + verdict + explanation) et les listes `questions` / `negotiation` sont **toutes
  visibles et lisibles** ; **aucune** mention « ce bien vaut X € » (anti-estimation).
- **Échec** : un pilier manquant, score absent, écran illisible, ou apparition
  d'une estimation de prix.

#### AC-B6 — Fallback collage = parité du chemin partage
Étape : refaire AC-B1..AC-B5 en **collant** l'URL (au lieu du partage natif).
- **Réussite** : comportement identique au chemin partage (même `firstUrl`, même
  extraction, même résultat).
- **Échec** : divergence de comportement entre collage et partage.

---

## 6. Contraintes RGPD et anti-patterns (rappel applicable)

- **RGPD — extraction sur la SEULE annonce ouverte par l'utilisateur.** Pas de
  crawl, pas de collecte de masse. L'app n'ouvre QUE l'URL fournie/partagée par
  l'utilisateur (spike §7, analyse §4.2).
- **Aucun stockage** du texte ni des photos/URLs côté app au-delà de la requête.
  Pas de persistance locale, pas de cache disque, pas de synchro. Les `image_urls`
  transitent vers le backend et ne sont **jamais loggées/persistées** (garanti
  serveur : `_sanitize_client_image_urls` ne logge qu'un compteur, `main.py:644`).
- **Pas de redistribution d'annonce** (`CONTEXT.md` §11.3) : l'app analyse une
  annonce à la demande de l'utilisateur, ne la republie pas, ne constitue aucune
  base d'annonces côté serveur à partir des analyses mobiles.
- **Pas d'estimation de prix maison** (`CONTEXT.md` §1.2 / §11) : l'écran rend
  `ApiResult` tel quel (cohérence, pas estimation) ; aucune UI mobile ne réintroduit
  un « ce bien vaut X € ». Disclaimer §2.2 repris.
- **Pas de DVF / bases notariales, pas de conseil juridique ou financier**
  (`backend/CLAUDE.md` §1) : aucun de ces éléments n'est ajouté côté app.
- **Pas de secret en clair** (`.claude/lessons.md` invariants) : l'app n'embarque
  AUCUNE clé OpenAI/Google/admin ; seule `EXPO_PUBLIC_API_URL` (publique) est
  configurée. Tout appel tiers passe par le backend.
- **Contrat `/analyze` stable** : cette tranche **consomme** le contrat Phase 1
  sans le modifier ; aucun changement backend, aucune MAJ de schéma. Si un besoin
  de modification du contrat apparaît, il est HORS tranche et doit repasser GATE.
- **Pas de contournement d'authentification ni de crawl** : on lit le DOM **rendu
  pour l'utilisateur lui-même** dans sa propre session de navigation (spike §7) ;
  on ne contourne aucun login, on ne durcit pas le fetch serveur (option proxies/
  solveur anti-bot explicitement écartée — analyse §4.2.3).

---

## 7. Plan d'implémentation par petits pas (machine de l'utilisateur, hors sandbox)

> Le sandbox de l'atelier ne peut pas faire tourner ce code (pas de device, egress
> LBC bloqué). Ces pas s'exécutent sur la machine de l'utilisateur. Les pas 1-5
> sont vérifiables par Jest (famille A) ; les pas 6-8 par la checklist device
> (famille B).

1. **Scaffold `mobile/`** (sous réserve D-EMPLACEMENT) : `npx create-expo-app`
   (SDK 54, template TypeScript), ajouter `react-native-webview`, configurer Jest
   (`jest-expo` + `@testing-library/react-native`). Aucune logique métier encore.
2. **`src/extract/firstUrl.ts`** + tests AC1-AC4 (rouge -> vert). Port direct de
   `firstUrl` du spike, typé.
3. **`src/extract/gallery.ts`** (filtrage/dédup/cap) + tests AC5-AC8. Port de la
   logique `byRule`/`seen`/`gallery` de `buildExtractor`, extraite en fonction pure
   testable hors WebView.
4. **`src/extract/injectedScript.ts`** : build du JS injecté (auto-scroll + collecte
   + `postMessage`), réutilisant la même logique de filtrage que le pas 3 (source
   unique de vérité du filtrage côté page). Pas de test Jest (s'exécute dans la
   WebView) ; vérifié en famille B.
5. **`src/config.ts` + `src/api/{types,analyze}.ts`** : lecture
   `EXPO_PUBLIC_API_URL`, `buildAnalyzeBody`, `analyzeListing` + tests AC9-AC12
   (`fetch` mocké). Copier les types `ApiResult` depuis `frontend/lib/api.ts`.
6. **`src/screens/InputScreen.tsx` + `WebViewScreen.tsx`** : champ collage,
   WebView (UA mobile), bouton « Extraire », `onMessage` -> POST. Vérif device
   AC-B1..AC-B4, AC-B6.
7. **`src/screens/ResultScreen.tsx`** : rendu `ApiResult` (§4.4). Vérif device
   AC-B5.
8. **(Sous-incrément, si D-PARTAGE-INCREMENT le place ici)** : brancher le share
   intent natif (dev build, `expo-share-intent`) sur la même logique `firstUrl`.
   Vérif device AC-B1..AC-B6 par le chemin partage.

À chaque pas Jest : prouver la **falsifiabilité** (le test échoue si on casse la
logique), conformément aux leçons anti-faux-vert.

---

## 8. Risques résiduels et questions ouvertes pour l'humain

- **R1 — Fragilité des noms de `rule`** : `ad-large` vient du site desktop ; le spike
  confirme qu'il tient sur mobile, mais un changement LBC casserait l'extraction.
  Mitigation à terme (HORS tranche 1) : scoper au conteneur DOM de la galerie
  (spike §9, §10.2). Pour cette tranche, on garde `rule` en dur (code qui marche).
- **R2 — Lazy-load incomplet** : si l'utilisateur n'a pas fait défiler toute la
  galerie, des photos manquent dans le DOM. Mitigation : auto-scroll + délai ; la
  perte est partielle, pas bloquante (≥ 80 % visé, AC-B2).
- **R3 — Share intent natif = dev build** : sort d'Expo Go managed pur, alourdit le
  build/CI. D'où D-PARTAGE-INCREMENT (le sortir de la tranche fine si trop lourd).
- **R4 — Multi-portails** : un seul host CDN câblé ; SeLoger/Bien'ici exigeraient
  d'autres hosts/règles (OUT, à mesurer plus tard).
- **R5 — Rate-limit `/analyze` (10/60s)** : si l'app déclenche plusieurs analyses
  rapprochées (re-extraction), risque de 429. Mitigation : un POST par action
  explicite ; gérer le 429 comme une erreur lisible.

### GATE 2 — DÉCISIONS ACTÉES (humain, 2026-06-23)
1. **D-EMPLACEMENT → `mobile/` dans le monorepo.** Réutilisation des types du
   contrat `/analyze`, un seul tooling, plus simple pour une tranche fine.
2. **D-PARTAGE-INCREMENT → collage d'URL d'abord ; share intent natif en
   sous-incrément suivant.** La tranche reste fine et 100 % testable sans device.
3. **Body galerie vide → OMETTRE la clé `image_urls`** (le serveur tolère les deux ;
   AC9 asserte l'omission).
4. **Cap côté app → 50** (aligné `MAX_INPUT_IMAGE_URLS` serveur ; AC8 teste 50/51).

Spec APPROUVÉE pour implémentation. Les points ci-dessous sont conservés pour
traçabilité de la décision.

### POINTS À ARBITRER (GATE 2)
1. **D-EMPLACEMENT** : `mobile/` dans le monorepo (défaut proposé) **ou** repo
   séparé ? Structurant (CI, tooling, réutilisation de types).
2. **D-PARTAGE-INCREMENT** : le **share intent natif** est-il DANS cette tranche, ou
   bascule-t-il en **sous-incrément immédiatement suivant** (livrer d'abord le
   fallback collage, déjà couvert par les AC famille A) ? Recommandation : sous-
   incrément, pour garder la tranche fine et 100 % testable sans device au pas 5.
3. **Forme du body quand galerie vide** (AC9) : omettre la clé `image_urls` (reco)
   **ou** envoyer `image_urls: []` ? Fixer l'un, l'AC asserte ce choix.
4. **Cap côté app** (AC8) : confirmer le cap à **50** (aligné `MAX_INPUT_IMAGE_URLS`
   serveur) ou laisser le serveur seul cappeur (on transmettrait tout) ?
   Recommandation : capper à 50 côté app (économie réseau, borne testable).

SPEC prête pour GATE 2 (approbation humaine).

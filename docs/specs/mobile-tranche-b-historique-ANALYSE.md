# ANALYSE — Mobile, Tranche B : « Historique d'analyses local (sur l'appareil) »

> Rôle : ANALYSTE (GATE 1). Cadre le problème, challenge la faisabilité contre le
> code RÉEL, lève les arbitrages structurants. N'implémente rien, ne spécifie pas
> la solution. Lecture seule sur le code ; seul ce fichier est écrit.
>
> Sources relues (état réel, pas seulement la doc) :
> - `mobile/App.tsx` (machine à états `input | webview | result`, pas de
>   react-navigation), `mobile/package.json` (dépendances réelles).
> - `mobile/src/lib/types.ts` (`ApiResult`), `mobile/src/lib/analyzeApi.ts`,
>   `mobile/src/lib/analyzeBody.ts`, `mobile/src/lib/config.ts`.
> - `mobile/src/screens/{Input,WebView,Result}Screen.tsx`, `mobile/src/theme.ts`.
> - `docs/specs/mobile-phase2-tranche1-SPEC.md` (conventions, GATE 2, RGPD §6).
> - `CONTEXT.md` §0 (état mobile + §11.3 redistribution), §11 anti-patterns ;
>   `.claude/lessons.md` (faux-verts, source unique de vérité `src/lib`).

---

## 1. Reformulation de l'objectif et périmètre

### 1.1 Objectif
Donner une **mémoire locale** à l'app : aujourd'hui une analyse est éphémère
(`result` est un `useState` dans `App.tsx`, perdu à la fermeture). On veut qu'un
acheteur retrouve ses analyses passées pour comparer plusieurs biens, **100 % sur
l'appareil**, sans serveur, sans compte, sans email.

### 1.2 Périmètre IN (proposé)
1. **Sauvegarde locale** d'une analyse terminée : le `ApiResult` (global_score,
   verdict, confidence, pillars, actions, local_context) + métadonnées minimales
   (un libellé/titre, une date, et — à arbitrer — l'URL de l'annonce).
2. **Écran « Mes analyses »** : liste triée par date (récent d'abord), chaque
   entrée = date + titre + petit donut de score + couleur de verdict (réutilise
   `ScoreDonut` + `verdictColorFromLabel`).
3. **Rouvrir** : réafficher `ResultScreen` à partir des données stockées, **sans
   nouvel appel LLM** (gratuit, instantané).
4. **Suppression** : effacer une entrée ; « tout effacer ».
5. **Plafond** : conserver les N dernières (défaut proposé 50).
6. Logique de persistance/plafond/dédup dans un **module pur `src/lib`** testé
   Jest (source unique de vérité), conformément à la leçon
   `mobile-phase2-tranche1` (`filterGallery`/`firstUrl`).

### 1.3 Périmètre OUT (proposé, à confirmer)
- **« Re-analyser » qui rejoue `/analyze` sur l'URL** : techniquement faisable
  MAIS il y a un nœud (cf. §2.3 et Q3) — proposé OUT de la tranche B initiale, ou
  conditionné à l'arbitrage Q1/Q3. À trancher.
- Stockage du **texte brut** (`raw_text`) ou des **photos** de l'annonce :
  **INTERDIT** (contenu tiers, §11.3). Non négociable, hors périmètre par principe.
- Synchronisation multi-appareils, sauvegarde cloud, compte, export chiffré : OUT
  (re-introduirait auth/PII/RGPD, à l'opposé de la minimisation).
- Partage natif d'une entrée d'historique vers d'autres apps : OUT (peut
  redistribuer du contenu tiers selon ce qu'on partage — hors tranche).
- Recherche/tri/filtre avancés, tags, notes personnelles : OUT (polish ultérieur).

---

## 2. Faisabilité vs code réel

### 2.1 Verdict global : FAISABLE, et bien aligné sur l'architecture existante
Rien dans le code n'empêche cette tranche. Elle se greffe proprement :
- **Machine à états** : `App.tsx:27` définit `type Screen = 'input' | 'webview' |
  'result'`. Ajouter un état `'history'` est trivial (un `setScreen('history')`
  depuis `InputScreen`, un rendu conditionnel de plus dans le `return` `App.tsx:58-90`).
  Pas de react-navigation requis — conforme à la contrainte.
- **Point de sauvegarde auto** : le seul endroit où une analyse « se termine » est
  `WebViewScreen.tsx:77` (`onResult(result)` après `analyzeListing`). `App.tsx:70-77`
  reçoit le `result` et bascule en `'result'`. C'est l'unique chemin de succès, donc
  l'unique hook de persistance (1 seul point à instrumenter). NB : la PWA et le web
  ne passent pas par là — la tranche B est **mobile-only** (cohérent, AsyncStorage
  est natif).
- **Donut de liste** : `ScoreDonut` (`src/components/ScoreDonut.tsx`) +
  `verdictColorFromLabel` / `verdictMeta` (`theme.ts:85-107`) existent déjà et
  prennent `score` + `color` — réutilisables tels quels pour la vignette de liste.
- **Réouverture** : `ResultScreen` (`ResultScreen.tsx:30`) prend `{ result, onBack }`
  et est **purement présentiel** (aucun appel réseau dans le composant). Lui passer
  un `ApiResult` rechargé depuis le stockage le réaffiche à l'identique, **sans
  aucun appel LLM**. La fonctionnalité « rouvrir gratis » est donc acquise par
  construction.

### 2.2 Dépendance de stockage : AsyncStorage est ABSENT — à ajouter
Vérifié dans `mobile/package.json` (l.27-40) : **ni
`@react-native-async-storage/async-storage`, ni `expo-sqlite`, ni `expo-secure-store`**
ne sont présents. Dépendances actuelles : expo SDK 54, react-native 0.81.5,
react-native-webview, react-native-svg, expo-font/-updates/-status-bar/-dev-client,
@expo-google-fonts/*. Il faut **ajouter une brique de persistance** (cf. Options §5
et Q1). Les deux candidats (`@react-native-async-storage/async-storage` et
`expo-sqlite`) sont des modules **du SDK Expo 54**, compatibles Expo Go ET dev
build, pur JS côté API — donc testables sur les deux plateformes (iPhone Expo Go +
APK Android), sans dépendre du compte Apple (cf. §6).

### 2.3 Le nœud central : `raw_text` est du CONTENU TIERS, et l'URL ne circule pas jusqu'à l'analyse
C'est le point le plus structurant et il faut le poser net :
- Dans `WebViewScreen.tsx:74-77`, on appelle `analyzeListing(data.text, gallery)`
  où `data.text` = `document.body.innerText` de l'annonce LBC = **le texte intégral
  de l'annonce tierce** (titre, description, prix…). `buildAnalyzeBody`
  (`analyzeBody.ts:13`) le met dans `raw_text`.
- **Stocker `raw_text` = stocker du contenu d'annonce tierce → INTERDIT** par
  l'invariant §11.3 (« ne jamais re-publier texte, photos, adresse exacte »).
  Même si le stockage est local, c'est une constitution d'une copie persistante de
  contenu tiers : à proscrire, et c'est explicitement listé dans le brief.
- **Conséquence directe pour « re-analyser »** : `analyzeListing` ne prend PAS
  d'URL ; il poste `raw_text`. Re-jouer une analyse **sans avoir le raw_text**
  imposerait de **ré-ouvrir la WebView sur l'URL et de ré-extraire** le DOM (puis
  re-POST). Donc « re-analyser » n'est PAS « rappeler `/analyze` avec un texte
  stocké » : c'est **relancer toute la boucle webview→extraction→analyze** à partir
  de l'**URL**. Cela suppose (a) qu'on ait stocké l'URL, et (b) que l'annonce soit
  toujours en ligne et toujours extractible (DataDome, lazy-load, etc.).
- **L'URL elle-même** : est-ce du contenu tiers à ne pas stocker ? Lecture de
  §11.3 : l'interdiction de redistribution vise « texte, photos, adresse exacte ou
  URL » au sens **exposition publique / re-publication**. Ici on ne re-publie rien :
  l'URL reste **strictement locale sur l'appareil de l'utilisateur**, pour son seul
  usage (rouvrir l'annonce, re-analyser). C'est analogue à un historique de
  navigateur. Lecture proposée : **stocker l'URL en local est acceptable** (ce
  n'est ni une base d'annonces côté serveur, ni une redistribution), MAIS c'est un
  arbitrage à valider (Q3) car le brief le pose comme question ouverte.

### 2.4 Ce qu'on PEUT stocker sans risque (minimisation)
Le `ApiResult` (`types.ts:46-57`) est **le produit d'analyse de Coherence**, pas le
contenu de l'annonce : global_score, verdict, confidence, pillars
(label/verdict/explanation/points/max), actions (highlights/questions/negotiation),
local_context (district/summary/facts/claims). C'est **notre** sortie dérivée.
Le stocker localement est conforme (c'est exactement « le résultat d'analyse » que
le brief autorise). Nuance à surveiller : `local_context.summary`/`claims[].text`
peuvent **citer des bribes** de l'annonce (allégations extraites) ; cela reste un
agrégat d'analyse, pas la republication de l'annonce — acceptable, mais à noter.

### 2.5 Le « titre » : d'où vient-il ?
Le brief demande un titre dans la liste. Or **`ApiResult` ne contient pas de
champ titre** (vérifié `types.ts`). Sources possibles :
- (a) Dériver du `raw_text` (1ʳᵉ ligne de l'`innerText`, souvent le titre LBC) —
  MAIS on a décidé de **ne pas stocker `raw_text`** ; on pourrait extraire le titre
  **au moment de l'analyse** (avant de jeter le raw_text) et ne persister QUE ce
  court libellé. Question : un titre d'annonce extrait est-il du contenu tiers ? Un
  libellé court à usage local = métadonnée d'identification, défendable (analogue à
  un titre de favori navigateur), mais à acter (Q4).
- (b) Utiliser l'**URL** (ou son chemin/slug) comme libellé — neutre, mais peu
  lisible (« .../ventes_immobilieres/123456 »).
- (c) `local_context.district` + score comme libellé synthétique (« Sablon —
  72/100 ») — 100 % dérivé de notre analyse, zéro contenu tiers, mais peu
  distinctif si plusieurs biens dans le même quartier.
- (d) Laisser l'**utilisateur saisir** un libellé à la sauvegarde — zéro contenu
  tiers extrait, mais ajoute une friction (et un champ de saisie).

### 2.6 Faisabilité des tests (source unique de vérité)
Tout le cœur (sérialisation d'une entrée, ajout, plafond, dédup, suppression,
tri) doit vivre dans un module pur `src/lib` (ex. `history.ts`) **sans dépendance
RN** : les fonctions prennent/retournent des structures, l'I/O AsyncStorage est
injecté/mocké. Le pattern Jest existe déjà (`analyzeApi.test.ts` mocke `fetch` ;
ici on mocke l'adaptateur de stockage). Falsifiabilité : asserter la **liste exacte**
après plafond (N gardées, N+1 → la plus ancienne évincée — borne exacte, leçon
9.7 sur les bornes), la dédup (même clé → 1 entrée mise à jour, pas 2), l'ordre.

---

## 3. Dépendances et ordre

### 3.1 Prérequis techniques
- **P1 — Brique de persistance à ajouter** (Q1) : `@react-native-async-storage/async-storage`
  OU `expo-sqlite`. Bloquant pour toute la tranche. `npx expo install` gère la
  compat SDK 54.
- **P2 — Décision « quoi stocker »** (Q2/Q3/Q4) : forme de l'entrée persistée
  (ApiResult + métadonnées). Doit précéder l'écriture du module `src/lib/history.ts`
  (son type = contrat de stockage).
- **P3 — Schéma de l'entrée + clé de dédup** (Q5) : conditionne `history.ts` et la
  migration future (versionner le schéma stocké dès le départ — un champ `version`).

### 3.2 Ordre d'implémentation conseillé
1. Trancher Q1→Q6 (GATE 1).
2. `src/lib/history.ts` (pur, testé Jest) : types + add/list/remove/clear + plafond
   + dédup, I/O storage injecté. **Indépendant de l'UI**, livrable et vert seul.
3. Câblage persistance au point de succès (`WebViewScreen.onResult` →
   `App.tsx`) : sauvegarde auto OU bouton (Q6).
4. Écran `'history'` + entrée depuis `InputScreen` + réouverture (`ResultScreen`
   piloté par une donnée stockée).
5. (Optionnel/conditionnel) « Re-analyser » (dépend de Q3 : URL stockée).

### 3.3 Dépendances inter-tranches
- **Ne dépend PAS** du compte Apple (cf. §6) ni du share intent (sous-incrément
  séparé) ni d'aucun nouveau backend (`/analyze` Phase 1 inchangé). Aucun prérequis
  manquant bloquant hors P1 (dépendance npm à installer).
- **Interaction avec la tranche share intent** (future) : si un jour l'entrée se
  fait par partage natif, le point de sauvegarde reste le même (`onResult`) — pas
  de couplage. RAS.

---

## 4. Risques et anti-patterns

### 4.1 Anti-pattern §11.3 — stockage de contenu tiers (RISQUE PRINCIPAL)
- **Ne JAMAIS persister `raw_text` ni les `image_urls`/photos.** C'est l'écueil n°1.
  Garde-fou recommandé : un **test statique/structurel** prouvant que la forme
  d'entrée stockée n'a **aucun champ** `raw_text`/`text`/`image_urls`/`photos`
  (asserter les clés autorisées en whitelist, comme la leçon 9.10 sur les corps
  d'endpoint et la leçon « whitelist positive » 9.10). Falsifiable : rouge si on
  ajoute un champ contenu tiers.
- Vigilance sur le **titre dérivé** (§2.5) : si on extrait un titre du raw_text,
  garder un **libellé court** (pas la description), et l'acter (Q4).

### 4.2 RGPD / minimisation
- Données **100 % locales**, jamais transmises (aucun appel réseau dans le flux
  historique), **effaçables** (suppression unitaire + « tout effacer »). Conforme.
- **Pas de PII** : on ne stocke ni email, ni compte, ni identifiant utilisateur
  (cohérent avec l'invariant « anonyme/sans état »). Un historique local n'est pas
  un traitement de données personnelles côté éditeur (rien ne quitte l'appareil).
- **Rétention** : le plafond N (Q5) + « tout effacer » tiennent lieu de politique
  de rétention. Pas de purge temporelle nécessaire au MVP (mais possible).

### 4.3 Coût / estimation de prix / vendor
- **Coût** : « rouvrir » = 0 € (aucun LLM). Seul « re-analyser » rappelle `/analyze`
  (~0,001 €) — borné par action utilisateur explicite + rate-limit serveur (10/60s,
  SPEC tranche1 §3.3). Pas de dérive. Conforme au cap « < 1 €/mois ».
- **Estimation de prix** : aucune réintroduite ; on réaffiche `ApiResult` tel quel
  (ResultScreen porte déjà le disclaimer anti-estimation, `ResultScreen.tsx:106-109`).
- **Nouveau vendor** : AsyncStorage/expo-sqlite sont **first-party Expo**, pas un
  service tiers, pas de secret, pas de réseau. Pas de saut de posture vendor.

### 4.4 Risques techniques de persistance
- **Corruption / format invalide** au chargement (JSON cassé, schéma ancien) :
  prévoir un **parse défensif** (entrée illisible ignorée, pas de crash) + un champ
  `version` de schéma dès v1 (migration future). Garde-fou : test « entrée corrompue
  → liste filtrée, pas d'exception ».
- **Course / écritures concurrentes** : AsyncStorage est asynchrone ; deux écritures
  rapprochées (ex. sauvegarde auto + plafond) doivent passer par une **lecture →
  mutation → réécriture** atomique côté logique pure (sérialiser les écritures).
  Risque faible au MVP (un POST par action), mais à tester (ajout puis ajout →
  pas de perte). NB : la leçon « état partagé de module » (9.7/9.9) s'applique en
  Jest — réinitialiser le mock storage entre tests (fixture autouse / `beforeEach`).
- **Volume** : 50 entrées × un `ApiResult` (quelques Ko chacune) = négligeable
  (centaines de Ko). AsyncStorage gère ; pas de souci de quota au plafond proposé.

### 4.5 Anti-pattern « re-analyser » silencieusement cassé
Si on expose « re-analyser » mais que l'annonce est **hors ligne** ou que LBC
**bloque** (DataDome, captcha — cf. spike), l'action échoue de façon non
déterministe → promesse fragile (parente de la critique 9.6 « promesse intenable
sur les grands portails »). Il faut que l'échec soit **lisible** (message clair),
et que l'entrée d'historique existante **reste intacte** (ne pas écraser une bonne
analyse par un échec). D'où l'importance de Q3 et du comportement de re-analyse.

### 4.6 Conventions atelier
- **Source unique de vérité** : toute la logique (plafond/dédup/tri/sérialisation)
  dans `src/lib/history.ts`, jamais dupliquée dans les écrans (leçon
  mobile-phase2-tranche1). L'écran ne fait que rendre.
- **Pas d'emoji**, pas de secret, TypeScript strict (cohérent repo).
- **Versionner le schéma stocké** dès v1 (éviter une migration douloureuse plus tard).

---

## 5. OPTIONS chiffrées (choix structurants)

### OPTION A — Brique de persistance (Q1)

| Critère | A1. AsyncStorage (`@react-native-async-storage/async-storage`) | A2. `expo-sqlite` |
|---|---|---|
| Modèle | clé→valeur (un blob JSON de toutes les entrées, ou 1 clé/entrée) | base SQL embarquée (table `history`) |
| Volume cible (≤ 50 entrées) | largement suffisant | sur-dimensionné |
| Complexité d'implémentation | minimale (get/set string) | plus lourde (schéma, requêtes, migrations SQL) |
| Requêtes (tri/filtre) | en mémoire JS (50 entrées = trivial) | SQL natif (inutile à cette échelle) |
| Compat Expo Go SDK 54 / Android | oui, pur JS API | oui, mais module natif (OK Expo Go SDK 54) |
| Testabilité Jest (logique pure) | excellente (mock d'un get/set) | bonne mais I/O plus verbeux à mocker |
| Risque migration future | versionner le blob JSON | migrations SQL (plus rituel) |
| Coût | 0 € (first-party) | 0 € (first-party) |

**Recommandation : A1 (AsyncStorage).** À 50 entrées d'agrégats, le tri/filtre se
fait en mémoire ; SQLite n'apporte rien et alourdit (schéma + migrations). A1 est
le minimum viable sans dette, aligné « MVP < 1 €/mois » et droit au but. SQLite ne
se justifierait que si l'historique devenait gros et requêtable (recherche
plein-texte, milliers d'entrées) — non, le plafond est 50.

### OPTION B — Sauvegarde automatique vs bouton explicite (Q6)

| Critère | B1. Auto (à `onResult`) | B2. Bouton « Enregistrer » |
|---|---|---|
| Friction utilisateur | nulle (mémoire transparente) | un tap de plus |
| Conformité « consentement RGPD » | non requis (local, pas de PII, pas d'éditeur) | n/a |
| Risque d'historique « pollué » | analyses ratées/test s'y retrouvent | l'utilisateur choisit |
| Cohérence avec le besoin (« aucune trace aujourd'hui ») | répond pleinement | partiel |
| Complexité | minimale | + un état/affordance UI |

**Recommandation : B1 (auto), avec dédup** (Q5) pour ne pas empiler 10 fois le même
bien ré-analysé. La mémoire doit être transparente (« je n'ai rien à gérer »).
Comme tout est local et effaçable + plafonné, le risque d'« historique pollué »
est faible et réversible (suppression unitaire). Si l'humain préfère le contrôle,
B2 reste simple.

### OPTION C — « Re-analyser » (Q3, conditionne aussi le stockage de l'URL)

| Critère | C1. Stocker l'URL → re-analyser via la boucle webview | C2. Pas d'URL → pas de re-analyse (rouvrir seulement) |
|---|---|---|
| Valeur produit | « re-vérifier un bien plus tard » (acheteur comparant) | « consulter mes analyses passées » seulement |
| Contenu tiers stocké | URL locale uniquement (pas de raw_text) | rien d'identifiant d'annonce |
| Fiabilité | dépend de l'annonce en ligne + LBC non bloquant (fragile) | 100 % fiable (lecture locale) |
| Complexité | + ré-ouverture WebView pré-remplie + gestion échec/écrasement | minimale |
| Risque promesse fragile (cf. 9.6) | réel (annonce retirée / DataDome) | nul |

**Recommandation : C1 mais en SOUS-INCRÉMENT** (après la tranche B « mémoire +
relecture » livrée et stable). La tranche B v1 = sauvegarde auto + liste + rouvrir
gratis + suppression + plafond (valeur immédiate, zéro fragilité). « Re-analyser »
ajoute la dépendance « annonce toujours extractible » et mérite son propre cycle
(gestion d'échec, écrasement vs nouvelle entrée — Q3b). Stocker l'**URL** dès la v1
(elle est gratuite et locale) **prépare** C1 sans le livrer, **si** Q3 valide que
l'URL locale est acceptable.

---

## 6. Ce qui est faisable sans le compte Apple (testable maintenant)

**Tout le cœur de la tranche B est testable maintenant, sans compte Apple :**
- `@react-native-async-storage/async-storage` et `expo-sqlite` sont **pur JS côté
  API** et fonctionnent en **Expo Go (iOS)** ET via **APK Android** (déjà validé en
  prod, CONTEXT §0). Aucune capacité native iOS payante requise (pas de
  `NSUsageDescription`, pas de credential Apple).
- La **logique pure** `src/lib/history.ts` (plafond/dédup/tri/sérialisation) est
  testable **en Jest dans le sandbox de l'atelier** (famille A), sans device —
  comme `analyzeApi`/`gallery`/`firstUrl` aujourd'hui (73 tests verts).
- Les **écrans** (liste, réouverture) = famille B (vérif device), validables sur
  **iPhone Expo Go** et **Android APK** sans rien payer.
- **Aucun** maillon de la tranche B n'attend l'inscription Apple Developer (qui ne
  bloque que la **publication App Store / TestFlight iOS natif**, pas le
  développement ni le test en Expo Go).

Conclusion §6 : la tranche B est un **bon candidat pour avancer pendant que le
compte Apple est bloqué** — elle apporte de la valeur, n'a aucune dépendance
payante, et est testable des deux côtés.

---

## 7. QUESTIONS POUR L'HUMAIN (GATE 1)

> Numérotées, chacune avec options et recommandation argumentée. Aucune décision
> structurante prise ici.

### Q1 — Brique de persistance : AsyncStorage ou expo-sqlite ?
- Options : (A1) `@react-native-async-storage/async-storage` clé→valeur JSON ;
  (A2) `expo-sqlite` table SQL.
- **Reco : A1 (AsyncStorage).** À 50 entrées d'agrégats, le tri/filtre se fait en
  mémoire ; SQLite est sur-dimensionné et ajoute schéma + migrations. Minimum viable
  sans dette, first-party Expo, 0 €, testable Expo Go + Android. (Détail §5 Option A.)

### Q2 — Quoi stocker exactement (forme de l'entrée) ?
- Acquis non négociable : **ApiResult complet** (notre sortie d'analyse) +
  métadonnées (date, score/verdict déjà dans ApiResult). **JAMAIS** `raw_text` ni
  photos/`image_urls` (contenu tiers, §11.3).
- Options sur les métadonnées : stocker en plus (a) l'URL, (b) un titre, (c) rien
  d'autre. Voir Q3 (URL) et Q4 (titre).
- **Reco** : entrée = `{ version, id, savedAt, result: ApiResult, url?, title? }`,
  avec un **garde-fou statique** interdisant tout champ de contenu tiers. (Détail
  §2.4, §4.1.)

### Q3 — Stocker l'URL de l'annonce en local ? (et donc activer « re-analyser » ?)
- Le brief pose explicitement : l'URL est-elle du contenu tiers à NE PAS stocker ?
- Lecture (§2.3) : §11.3 interdit la **redistribution/exposition** d'URL ; un
  stockage **strictement local** (jamais transmis, jamais publié, usage perso =
  comme un favori navigateur) n'est pas une redistribution.
- Options : (a) stocker l'URL en local (permet « rouvrir l'annonce » et prépare
  « re-analyser ») ; (b) ne pas stocker d'URL (relecture seule, jamais de
  re-analyse).
- **Reco : (a) stocker l'URL en local**, MAIS « re-analyser » en **sous-incrément**
  séparé (C1, §5 Option C) — la fragilité (annonce retirée, DataDome) mérite son
  propre cycle. Si l'humain juge le stockage d'URL trop limite vis-à-vis de §11.3,
  basculer en (b) (relecture pure, qui couvre déjà l'essentiel du besoin).

### Q3b — (si Q3=a et re-analyser activé) Re-analyser : remplace l'entrée ou en crée une nouvelle ?
- Options : (a) **mettre à jour** l'entrée existante (même URL → même bien, on suit
  son évolution) ; (b) **créer une nouvelle entrée** (garder l'historique des deux
  analyses) ; (c) ne pas écraser si la re-analyse **échoue** (garde-fou).
- **Reco : (a) mise à jour de l'entrée existante** (cohérent avec la dédup par URL,
  Q5) **+ (c)** : ne jamais écraser une bonne analyse par un échec de re-analyse
  (l'entrée reste intacte, message d'erreur lisible). (Détail §4.5.) À ne trancher
  que si Q3=a et le sous-incrément re-analyse est lancé.

### Q4 — D'où vient le « titre » affiché dans la liste ?
- `ApiResult` n'a pas de champ titre (§2.5).
- Options : (a) extraire un **titre court** du raw_text **au moment de l'analyse**
  (avant de jeter le raw_text), n'en persister que le libellé ; (b) dériver de
  l'URL (slug) ; (c) libellé synthétique « district — score » (100 % notre analyse,
  zéro contenu tiers) ; (d) saisie utilisateur à la sauvegarde.
- **Reco : (c) en défaut** (« Sablon — 72/100 », ou « score + date » si pas de
  district), **avec (a)** comme amélioration si jugé trop pauvre — un **libellé court**
  extrait reste défendable (métadonnée d'identification locale, pas une republication),
  à acter explicitement. (d) évite tout contenu tiers mais ajoute de la friction
  (à éviter avec la sauvegarde auto Q6). Éviter (b) seul (peu lisible).

### Q5 — Plafond N et clé de dédup ?
- Options plafond : **50** (proposé), 30, 100.
- Options dédup : (a) par **URL** (même annonce ré-analysée → 1 entrée mise à
  jour) ; (b) par **id d'analyse** (chaque analyse = une entrée distincte, pas de
  dédup) ; (c) pas de dédup.
- **Reco : plafond 50** (aligné sur le brief et sur le `MAX_INPUT_IMAGE_URLS=50`
  serveur — chiffre familier ; volume négligeable) **+ dédup par URL** si Q3=a
  (évite d'empiler le même bien), sinon **pas de dédup** (chaque analyse = une
  entrée). Borne à tester aux valeurs exactes (50 gardées, 51 → éviction de la plus
  ancienne — leçon 9.7). (Détail §2.6, §4.4.)

### Q6 — Sauvegarde automatique ou bouton « Enregistrer » explicite ?
- Options : (B1) auto à la fin de chaque analyse réussie (`onResult`) ; (B2) bouton
  explicite.
- **Reco : B1 (auto) + dédup** (Q5). Mémoire transparente, répond pleinement au
  besoin (« aucune trace aujourd'hui »), réversible (suppression + « tout effacer »
  + plafond). (Détail §5 Option B.)

### Q7 — Périmètre de la tranche B v1 : relecture seule, ou relecture + re-analyse ?
- Options : (a) **v1 = mémoire + liste + rouvrir gratis + suppression + plafond**
  (zéro fragilité, 100 % testable) ; (b) v1 inclut aussi « re-analyser ».
- **Reco : (a)**. Livrer d'abord la valeur sûre et instantanée ; « re-analyser »
  (dépendant de l'annonce en ligne + LBC non bloquant) en **sous-incrément**
  immédiatement suivant. Évite de coupler une promesse fragile à une fonctionnalité
  robuste. (Détail §5 Option C, §4.5.)

---

## 8. Synthèse de cadrage (pour GATE 1)

- **Faisabilité : OUI, élevée.** L'architecture (machine à états `App.tsx`,
  `ResultScreen` purement présentiel, logique pure `src/lib` testée) accueille la
  tranche sans friction. Une seule dépendance à ajouter (P1).
- **Sans compte Apple : OUI**, tout est développable et testable (Expo Go iOS +
  APK Android + Jest sandbox). Bon chantier pendant le blocage Apple.
- **Risque n°1 : §11.3.** Ne jamais persister `raw_text`/photos ; garde-fou
  statique (whitelist de champs) recommandé. Le `ApiResult` (notre sortie) est OK.
- **Nœud de conception** : `raw_text` = contenu tiers + l'URL ne circule pas
  jusqu'à `analyzeListing` → « re-analyser » n'est PAS un simple re-POST, c'est
  relancer la boucle webview/extraction depuis l'URL → d'où Q3/Q3b/Q7.
- **Décisions structurantes à trancher : Q1→Q7** (cf. §7). Aucune prise ici.

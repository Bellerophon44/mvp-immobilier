# SPEC — Mobile, Tranche B : « Historique d'analyses local (sur l'appareil) »

> Rôle : SPEC-WRITER (GATE 2). Transforme l'analyse approuvée
> (`mobile-tranche-b-historique-ANALYSE.md`) et les arbitrages humains GATE 1 en
> cahier des charges implémentable avec critères d'acceptation testables. Lecture
> seule sur le code ; seul ce fichier est écrit. **N'implémente rien.**
>
> Sources relues (état réel, pas seulement la doc) :
> - `mobile/App.tsx` (machine à états `'input' | 'webview' | 'result'`, pas de
>   react-navigation ; `onResult` est l'unique point de fin d'analyse).
> - `mobile/src/lib/types.ts` (`ApiResult`, `ApiPillar`, `LocalContext`…),
>   `mobile/src/lib/analyzeApi.ts` (dépendance réseau terminale = `fetch`),
>   `mobile/src/lib/gallery.ts` (modèle « source unique de vérité » à imiter).
> - `mobile/src/screens/{Input,WebView,Result}Screen.tsx`,
>   `mobile/src/webview/injectedScript.ts`, `mobile/src/theme.ts`
>   (`verdictColorFromLabel`, `verdictMeta`), `mobile/src/components/ScoreDonut.tsx`.
> - `mobile/package.json` (aucune brique de persistance présente aujourd'hui).
> - `docs/specs/mobile-phase2-tranche1-SPEC.md` (conventions, familles A/B,
>   anti-faux-vert, RGPD §6).
> - `CONTEXT.md` §11 (anti-patterns ; §11.3 relu : interdit la **redistribution /
>   exposition publique** de contenu tiers, PAS le stockage strictement local).
> - `.claude/lessons.md` (faux-verts, bornes exactes 9.7, inertie observée sur la
>   dépendance terminale + test de contraste, isolation d'état entre tests,
>   `rejects.toThrow()` nu, source unique de vérité `src/lib`).

---

## 1. Objectif et périmètre

### 1.1 Objectif (1-2 phrases)
Donner à l'app une **mémoire locale** : à la fin de chaque analyse réussie,
sauvegarder automatiquement le résultat sur l'appareil pour qu'un acheteur
retrouve ses analyses passées (écran « Mes analyses »), les **rouvre sans aucun
appel réseau**, et les supprime. **100 % local** : aucune donnée d'historique ne
quitte jamais l'appareil.

### 1.2 Périmètre IN (cette tranche, v1)
1. **Sauvegarde automatique** d'une analyse terminée au seul point de fin
   d'analyse (`App.onResult`, alimenté par `WebViewScreen`).
2. **Écran « Mes analyses »** (nouvel état `'history'` de `App.tsx`), accessible
   depuis `InputScreen`, listant les entrées **triées plus récent d'abord**, avec
   pour chaque entrée : date, titre court, vignette `ScoreDonut` colorée via
   `verdictColorFromLabel`.
3. **Rouvrir une analyse** : réafficher `ResultScreen` à partir de l'`ApiResult`
   stocké, **sans aucun appel `/analyze` ni LLM** (gratuit, instantané, hors ligne).
4. **Suppression** : effacer une entrée ; « tout effacer ».
5. **Plafond 50** entrées (éviction de la plus ancienne au-delà) et **dédup par
   URL** (ré-analyser la même URL met à jour l'entrée et la remonte en tête).
6. **Stockage de l'URL** de l'annonce en local (préparation du futur
   « re-analyser », hors v1) — strictement sur l'appareil, jamais transmis.
7. Toute la **logique pure** (dédup, plafond, tri, sérialisation/désérialisation,
   validation + whitelist des champs) dans un module `src/lib` testé Jest,
   opérant contre une **interface de store injectable** (port).

### 1.3 Périmètre OUT (explicite, pour borner le dev)
- **« Re-analyser » qui rejoue la boucle webview→extraction→`/analyze` sur l'URL
  stockée** : **HORS v1** (sous-incrément suivant). L'URL est stockée dès
  maintenant pour le préparer, mais aucune action de re-analyse n'est livrée.
- **Stockage du `raw_text`, du texte d'annonce, des photos / `image_urls`** :
  **INTERDIT** (contenu tiers, §11.3). Non négociable, hors périmètre par principe.
- Synchronisation multi-appareils, sauvegarde cloud, compte, auth, export chiffré,
  partage natif d'une entrée d'historique : OUT (réintroduiraient auth/PII/RGPD).
- Recherche, filtres avancés, tags, notes personnelles, purge temporelle : OUT
  (le plafond 50 + « tout effacer » tiennent lieu de politique de rétention).
- Émission d'`events` / instrumentation funnel : OUT.

---

## 2. Décisions actées (GATE 1) et points flagués

### 2.1 Décisions actées (humain, GATE 1)
| # | Décision | Valeur actée |
|---|---|---|
| D1 | Périmètre v1 | mémoire locale : sauvegarde auto à la fin d'analyse, écran « Mes analyses », rouvrir sans LLM, supprimer + tout effacer, plafond 50, dédup par URL, **URL stockée** |
| D2 | « Re-analyser » | **HORS v1** (sous-incrément suivant), mais l'URL est stockée dès la v1 |
| D3 | Titre | libellé court **extrait de l'annonce**, **borné à 80 caractères** (cf. §5.3 pour la justification) |
| D4 | Stockage | **`expo-sqlite`** (à ajouter à `package.json` ; first-party Expo SDK 54) |
| D5 | §11.3 | le stockage **strictement local** d'URL + titre court + `ApiResult` est conforme ; l'interdiction porte sur la **redistribution / exposition publique**. Invariant testable : l'historique ne quitte jamais l'appareil |
| D6 | Architecture | port/adapter : logique pure dans `src/lib` contre une **interface de store injectable** ; l'adaptateur `expo-sqlite` est la partie famille B |
| D7 | Déclencheur de sauvegarde | **automatique** à `App.onResult` (cohérent avec le besoin « aucune trace aujourd'hui »), avec dédup par URL |

### 2.2 Décisions de cette spec (par défaut, non bloquantes ; flaguées en §10 si structurantes)
- **D-TITRE-SOURCE.** Le titre court est extrait **au moment de l'analyse**, dans
  `WebViewScreen.onMessage`, à partir du `data.text` (DOM) **avant** que ce texte
  ne soit jeté (il n'est jamais persisté). On dérive un libellé via une fonction
  pure `deriveTitle(rawText)` (`src/lib/history.ts`), **bornée à 80 caractères**.
  Seul ce libellé court est passé à la sauvegarde ; le `raw_text` ne l'est jamais.
  Repli déterministe si le texte ne donne rien d'exploitable : voir §5.3.
- **D-DEDUP-CLE.** Clé de dédup = **URL normalisée** (cf. §5.2 pour la
  normalisation exacte — décision testable). L'URL provient de `App.tsx` (`url`
  d'entrée), déjà disponible au moment de `onResult`.
- **D-RESET-STORE-TEST.** Le port de store de test (in-memory) est réinitialisé
  **avant chaque test** (leçon isolation d'état 9.7/9.9). Aucun état partagé de
  module ne fuit entre tests.
- **D-SCHEMA-VERSION.** Chaque enregistrement porte un champ `schemaVersion`
  entier (v1 = `1`) pour préparer une migration future sans douleur.

### 2.3 Points laissés ouverts (ne pas inventer — remontés en §10)
- Aucun point structurant n'est laissé ambigu : GATE 1 a tranché stockage, titre,
  périmètre et l'invariant §11.3. Les seuls choix résiduels (forme exacte de la
  normalisation d'URL, repli de titre) sont **tranchés dans cette spec** de façon
  testable (§5.2, §5.3) et listés en §10 pour confirmation.

---

## 3. Architecture cible (port / adapter)

### 3.1 Arborescence des fichiers touchés / créés

```
mobile/
├── package.json                       # MODIFIÉ : + "expo-sqlite" (dépendance)
├── App.tsx                            # MODIFIÉ : état 'history' + sauvegarde auto à onResult + réouverture
├── src/
│   ├── lib/
│   │   ├── history.ts                 # CRÉÉ : logique PURE (port + add/list/remove/clear, dédup, plafond, tri, sérialisation, whitelist, deriveTitle) — testée Jest (famille A)
│   │   ├── history.test.ts            # CRÉÉ : tests Jest de history.ts (AC1..AC10, AC14)
│   │   └── historyStoreSqlite.ts      # CRÉÉ : ADAPTATEUR concret du port (expo-sqlite) — famille B (device), pas de Jest
│   ├── screens/
│   │   ├── HistoryScreen.tsx          # CRÉÉ : écran « Mes analyses » (liste, rouvrir, supprimer, tout effacer) — famille B
│   │   └── InputScreen.tsx            # MODIFIÉ : affordance « Mes analyses » -> onOpenHistory — famille B
│   └── (existant inchangé : ResultScreen.tsx réutilisé tel quel pour la réouverture)
```

Note d'alignement (leçon 2026-06-23, écart d'arbo) : le cœur logique mobile vit
**à plat sous `mobile/src/lib/`** avec des tests homonymes `*.test.ts` à côté
(`testMatch` `src/**/*.test.ts`). On s'y conforme : `history.ts` + `history.test.ts`
sous `src/lib/`. L'adaptateur sqlite est dans `src/lib/historyStoreSqlite.ts`
(même dossier, mais **non testé Jest** car il dépend du module natif `expo-sqlite`).

### 3.2 Le port (interface de store injectable)

`history.ts` définit et exporte une interface de store **agnostique du moteur**.
La logique pure n'importe JAMAIS `expo-sqlite` ni aucun module réseau : elle reçoit
le store en paramètre.

```ts
export interface HistoryStore {
  read(): Promise<HistoryRecord[]>;          // lit tous les enregistrements bruts
  write(records: HistoryRecord[]): Promise<void>;  // remplace l'ensemble
}
```

Forme retenue (read/write de l'ensemble) : à 50 entrées d'agrégats, lire+muter+
réécrire en mémoire est trivial et rend la logique pure (dédup/plafond/tri) 100 %
testable contre un store in-memory. L'adaptateur sqlite (`historyStoreSqlite.ts`)
implémente `HistoryStore` sur une table `history` (sérialise `result` en JSON dans
une colonne TEXT). Cf. §4 pour le schéma.

### 3.3 Signatures du module pur `src/lib/history.ts` (contrat)

```ts
export const HISTORY_SCHEMA_VERSION = 1;
export const HISTORY_CAP = 50;
export const TITLE_MAX_LENGTH = 80;

export interface HistoryRecord {
  schemaVersion: number;   // === HISTORY_SCHEMA_VERSION (1 en v1)
  id: string;              // identifiant interne stable (cf. §4.2)
  url: string;             // URL de l'annonce, STRICTEMENT locale
  title: string;           // libellé court, borné à TITLE_MAX_LENGTH
  savedAt: number;         // timestamp epoch ms de la sauvegarde
  result: ApiResult;       // notre sortie d'analyse (jamais le raw_text/photos)
}

// Champs autorisés dans un enregistrement (whitelist stricte). Tout champ hors
// de cet ensemble est rejeté à la validation (cf. AC2).
export const ALLOWED_RECORD_KEYS: readonly string[];

// Dérive un titre court (<= TITLE_MAX_LENGTH) depuis le texte d'annonce, SANS
// stocker ce texte. Repli déterministe si vide (cf. §5.3).
export function deriveTitle(rawText: string | null | undefined): string;

// Normalise une URL pour la clé de dédup (cf. §5.2).
export function normalizeUrlKey(url: string): string;

// Construit un enregistrement valide à partir des données de sauvegarde.
// Valide la whitelist : lève une erreur NOMMÉE si result porte un champ interdit
// (raw_text/text/image_urls/photos) — cf. AC2.
export function buildRecord(input: {
  url: string;
  title: string;
  result: ApiResult;
  savedAt: number;
}): HistoryRecord;

// Pipeline pur : insère/met à jour un enregistrement dans une liste existante,
// applique dédup par URL (remonte en tête), plafond, tri récent-d'abord.
export function upsertRecord(
  existing: HistoryRecord[],
  record: HistoryRecord,
): HistoryRecord[];

// Désérialise + valide une liste brute (entrée corrompue ignorée, pas d'exception).
export function parseRecords(raw: unknown): HistoryRecord[];

// Façade injectée par le store (port) :
export async function saveAnalysis(
  store: HistoryStore,
  input: { url: string; title: string; result: ApiResult; savedAt: number },
): Promise<HistoryRecord[]>;
export async function listAnalyses(store: HistoryStore): Promise<HistoryRecord[]>;
export async function removeAnalysis(store: HistoryStore, id: string): Promise<HistoryRecord[]>;
export async function clearAnalyses(store: HistoryStore): Promise<void>;
```

`history.ts` **n'importe** ni `expo-sqlite`, ni `fetch`/`analyzeApi`, ni aucun
module réseau (garde-fou §6, AC12).

---

## 4. Modèle d'enregistrement et schéma DB

### 4.1 Whitelist stricte (champ par champ)
Un enregistrement d'historique ne contient **QUE** les clés de `ALLOWED_RECORD_KEYS` :

| Clé | Type | Nullable | Description |
|---|---|---|---|
| `schemaVersion` | `number` | non | `1` en v1 (D-SCHEMA-VERSION) |
| `id` | `string` | non | identifiant interne stable (§4.2) |
| `url` | `string` | non | URL de l'annonce, **strictement locale** |
| `title` | `string` | non | libellé court, longueur ≤ 80 (§5.3) |
| `savedAt` | `number` | non | epoch ms |
| `result` | `ApiResult` | non | notre sortie d'analyse (`types.ts`) |

**Interdits absolus** (jamais présents, à aucun niveau de l'enregistrement) :
`raw_text`, `text`, `image_urls`, `photos`, `body`, toute copie du DOM ou du texte
d'annonce. Le `result` est l'`ApiResult` de `types.ts` : il ne contient PAS de
`raw_text` ni d'`image_urls` (vérifié dans `types.ts`). `local_context.summary` et
`local_context.claims[].text` peuvent citer des bribes d'allégations extraites :
c'est notre agrégat d'analyse, pas la republication de l'annonce — conservé tel
quel (déjà affiché par `ResultScreen` aujourd'hui).

### 4.2 Identifiant interne `id`
`id` = chaîne dérivée déterministe de `normalizeUrlKey(url)` (la dédup étant par
URL, l'`id` est fonction de l'URL normalisée). Forme exacte (testable, AC4) : `id`
est **égal** pour deux enregistrements de même URL normalisée, et **distinct** pour
deux URLs normalisées différentes. Implémentation libre (ex. l'URL normalisée
elle-même, ou un hash stable), tant que cette propriété tient.

### 4.3 Schéma DB exact (adaptateur `expo-sqlite`, famille B)
Table `history`, créée idempotemment (`CREATE TABLE IF NOT EXISTS`) :

| Colonne | Type SQLite | Nullable | Contenu |
|---|---|---|---|
| `id` | `TEXT PRIMARY KEY` | non | `HistoryRecord.id` |
| `url` | `TEXT NOT NULL` | non | `HistoryRecord.url` |
| `title` | `TEXT NOT NULL` | non | `HistoryRecord.title` |
| `saved_at` | `INTEGER NOT NULL` | non | `HistoryRecord.savedAt` (epoch ms) |
| `schema_version` | `INTEGER NOT NULL` | non | `HistoryRecord.schemaVersion` |
| `result_json` | `TEXT NOT NULL` | non | `JSON.stringify(HistoryRecord.result)` |

L'adaptateur **ne crée aucune colonne** pour le texte d'annonce ou les photos. Au
`read()`, il reconstruit chaque `HistoryRecord` (parse `result_json`) puis délègue
à `parseRecords` (validation + whitelist) côté logique pure. Au `write()`, il
sérialise l'ensemble. La base est ouverte via `expo-sqlite` (`openDatabaseAsync`)
sur un fichier local de l'app ; aucun chemin réseau, aucun secret.

### 4.4 Dépendances à ajouter
- `expo-sqlite` (à installer via `npx expo install expo-sqlite`, compat SDK 54,
  first-party Expo, pur côté API, fonctionne en Expo Go iOS + APK Android).
- **Aucune** dépendance portant un secret ; aucun module réseau ajouté.

### 4.5 Variables d'env / secrets
**Aucune.** L'historique est 100 % local ; il ne lit ni n'écrit aucune variable
d'environnement, aucun secret, aucune URL backend. `EXPO_PUBLIC_API_URL` (tranche
1) reste l'unique config, **non utilisée** par le chemin historique.

### 4.6 Contrat front / backend
**Aucun changement de contrat.** `/analyze` (`frontend/lib/api.ts`,
`backend/app/main.py`) est inchangé : la tranche B ne touche ni l'endpoint, ni
`ApiResult`, ni `analyzeApi.ts`. La réouverture réaffiche un `ApiResult` stocké
sans appel réseau. Contrat `/analyze` stable (anti-pattern §11.9).

---

## 5. Décisions de conception testables

### 5.1 Tri
`listAnalyses` et `upsertRecord` renvoient les enregistrements triés par `savedAt`
**décroissant** (plus récent d'abord). À `savedAt` égal, l'ordre est stable (l'entrée
qui vient d'être upsertée passe en tête).

### 5.2 Normalisation d'URL pour la dédup (`normalizeUrlKey`)
Décision testable : `normalizeUrlKey(url)` renvoie `origin + pathname` de l'URL
parsée (schéma + host + chemin), **sans** query string ni fragment, host en
minuscules. Deux URLs ne différant que par leur query (`?utm=…`) ou leur fragment
(`#x`) ont la **même** clé → même bien → une seule entrée. Si l'URL est
non-parsable, la clé est l'URL d'entrée telle quelle (repli conservateur, pas
d'exception). (Falsifiable : échoue si la query est comptée dans la clé.)

### 5.3 Titre court (`deriveTitle`) — borne 80 caractères (justification D3)
- Source : `deriveTitle(rawText)` prend la **première ligne non vide** du texte
  (sur LBC, c'est le titre de l'annonce), espaces de bord retirés.
- **Borne : 80 caractères.** Justification : un titre d'annonce LBC tient
  largement sous 80 caractères ; 80 garde une ligne lisible dans une vignette de
  liste mobile sans rognage agressif, tout en évitant de stocker une description
  entière (un titre > 80 serait une description, pas un titre — borne qui distingue
  « libellé d'identification » de « contenu d'annonce »). Troncature : si la ligne
  dépasse 80, on garde **exactement les 80 premiers caractères** (pas d'ellipse
  ajoutée qui ferait 81 ; l'UI peut afficher une ellipse via style, hors logique).
- Repli déterministe si le texte est vide / sans ligne exploitable : libellé
  `"Analyse sans titre"` (constante). Jamais d'exception, jamais de chaîne vide.

### 5.4 Plafond et éviction (D1)
`HISTORY_CAP = 50`. Après `upsertRecord`, si la liste dépasse 50, **l'entrée la
plus ancienne** (plus petit `savedAt`) est évincée jusqu'à revenir à 50. La dédup
s'applique **avant** le plafond (un upsert d'URL existante ne crée pas de 51ᵉ).

---

## 6. Invariant « strictement local » et anti-patterns (rappel applicable)

- **Invariant §11.3 — l'historique ne quitte JAMAIS l'appareil.** Aucune donnée
  d'historique n'est transmise à un serveur, exposée publiquement, ni
  re-publiée. Le module `history.ts` **n'importe aucun module réseau** (`fetch`,
  `analyzeApi`, `config`) et **n'alimente jamais** `analyzeListing`/`POST /analyze`.
  Garde-fous : statique (AC12) + dynamique (AC13).
- **Anti-pattern §11.3 — pas de contenu tiers persisté.** `raw_text`, texte
  d'annonce, photos et `image_urls` ne sont **jamais** stockés (whitelist stricte,
  garde-fou statique + dynamique AC2 — un test qui ROUGIT si un champ interdit
  apparaît, leçon cross-agence-inc2b « absence de 422 ≠ transit réel »).
- **RGPD / minimisation.** Données 100 % locales, sans PII (ni email, ni compte,
  ni identifiant utilisateur), effaçables (suppression unitaire + tout effacer).
  Pas de consentement requis (rien ne quitte l'appareil, pas de traitement côté
  éditeur).
- **Pas d'estimation de prix.** La réouverture réaffiche `ApiResult` via
  `ResultScreen` (qui porte déjà le disclaimer anti-estimation) ; aucune nouvelle
  UI ne réintroduit « ce bien vaut X € ».
- **Pas de DVF / notaires, pas de conseil juridique** : aucun de ces éléments n'est
  ajouté.
- **Pas de secret en clair** : l'historique n'embarque aucune clé ; aucune variable
  d'env requise.
- **Contrat `/analyze` stable** : tranche B ne modifie ni l'endpoint, ni
  `ApiResult`, ni `frontend/lib/api.ts`.
- **Source unique de vérité** : toute la logique (dédup/plafond/tri/sérialisation/
  whitelist/titre) vit dans `src/lib/history.ts`, jamais dupliquée dans les écrans
  (leçon mobile-phase2-tranche1). Les écrans ne font que rendre et déléguer.
- **Pas d'emoji**, TypeScript strict, logging via logger nommé si logging il y a
  (cohérent repo), pas de commentaire « what ».

---

## 7. Critères d'acceptation

> Deux familles SÉPARÉES (cf. tranche 1). **Famille A = logique pure**,
> automatisable en Jest (`history.ts`), falsifiable, porte sur le résultat/transit
> réel. **Famille B = device / bout-en-bout** (adaptateur sqlite, écrans, machine
> à états), non automatisable en sandbox → checklist sur device.
>
> Leçons appliquées : un AC qui ne peut pas échouer n'a aucune valeur ; bornes aux
> valeurs exactes (50 ET 51) ; pour une inertie, observer la dépendance terminale
> réelle + test de contraste ; un test d'erreur asserte la NATURE de l'erreur, pas
> un throw nu ; isolation d'état entre tests.

### 7.A Famille A — logique pure (Jest, `history.test.ts`)

**Isolation (préalable à tous les AC-A).** Un store de test in-memory implémentant
`HistoryStore` est **réinitialisé avant chaque test** (`beforeEach`), sans état
partagé de module (leçon 9.7/9.9). Un test dédié vérifie que deux tests successifs
ne se voient pas (AC14).

#### AC1 — Persistance via la façade : `saveAnalysis` ajoute un enregistrement complet
Avec un store in-memory vide, `saveAnalysis(store, { url, title, result, savedAt })`
puis `listAnalyses(store)` renvoie **exactement 1** enregistrement dont
`url`/`title`/`savedAt` sont ceux fournis, `schemaVersion === 1`, et `result` est
**strictement égal** (deep-equal) à l'`ApiResult` fourni. (Falsifiable : échoue si
un champ est perdu ou altéré.) **[Jest]**

#### AC2 — Whitelist stricte : un champ interdit fait ROUGIR le test (garde-fou statique + dynamique)
- **Statique** : `ALLOWED_RECORD_KEYS` est **exactement**
  `{schemaVersion, id, url, title, savedAt, result}` et ne contient **aucun** de
  `raw_text`, `text`, `image_urls`, `photos`, `body`. Un enregistrement produit par
  `buildRecord` n'a **aucune** clé hors de `ALLOWED_RECORD_KEYS`
  (`Object.keys(record)` ⊆ whitelist, asserté en stricte égalité d'ensemble).
- **Dynamique** : si `buildRecord` reçoit un `result` qui porte un champ interdit
  (ex. `result` augmenté de `raw_text` ou `image_urls`), il **lève une erreur
  NOMMÉE** (message contenant le nom du champ interdit, pas un throw nu), OU
  produit un enregistrement dont la sérialisation ne contient à aucune profondeur
  les clés `raw_text`/`image_urls`/`photos`/`text` (choisir l'un et l'asserter).
- **Falsifiabilité (obligatoire)** : un test qui ajoute un champ interdit à l'objet
  stocké et asserte que `JSON.stringify(record)` **ne matche pas**
  `/"(raw_text|image_urls|photos|text)"/` → ce test **rougit** si la whitelist est
  retirée (leçon cross-agence-inc2b : on prouve l'absence par un test qui détecte
  réellement la présence). **[Jest]**

#### AC3 — Dédup par URL : même URL → mise à jour + remontée en tête (pas de doublon)
Partant d'une liste de 3 entrées d'URLs distinctes, `saveAnalysis` d'une analyse
dont l'URL **normalisée** égale celle d'une entrée existante (ex. même URL avec une
query différente, cf. §5.2) :
- la liste résultante a **toujours le même nombre d'entrées** (pas de 4ᵉ) ;
- l'entrée correspondante est **mise à jour** (`result`/`title`/`savedAt` = ceux du
  nouveau) ;
- elle est **en tête** de la liste (index 0).
(Falsifiable : échoue si un doublon est créé, ou si l'ancienne entrée reste en place.)
**[Jest]**

#### AC4 — `normalizeUrlKey` / `id` : égalité par URL, distinction par URL
- `normalizeUrlKey("https://lbc.fr/ad/123?utm=x")` **===**
  `normalizeUrlKey("https://lbc.fr/ad/123#photo")` (query/fragment ignorés).
- `normalizeUrlKey("https://lbc.fr/ad/123")` **!==** `normalizeUrlKey("https://lbc.fr/ad/999")`.
- Deux `buildRecord` de même URL normalisée ont le **même** `id` ; de URLs
  différentes, des `id` **distincts**. (Falsifiable : échoue si la query est
  comptée dans la clé.) **[Jest]**

#### AC5 — Plafond aux valeurs EXACTES : 50 gardées, 51ᵉ → éviction de la plus ancienne
- En insérant 50 entrées d'URLs distinctes (`savedAt` croissants), `listAnalyses`
  renvoie **exactement 50** entrées, et la plus ancienne est **présente**.
- En insérant une **51ᵉ** entrée (URL distincte, `savedAt` le plus récent),
  `listAnalyses` renvoie **exactement 50** entrées, la **plus ancienne (1ʳᵉ
  insérée) est ABSENTE**, et la 51ᵉ est **présente en tête**.
- (Bornes exactes, leçon 9.7 : tester 50 ET 51, off-by-one détecté.) **[Jest]**

#### AC6 — Tri : plus récent d'abord
Après insertion dans un ordre `savedAt` mélangé, `listAnalyses` renvoie les entrées
par `savedAt` **strictement décroissant** (asserter la séquence exacte des
`savedAt`). (Falsifiable : échoue si l'ordre d'insertion ou un tri croissant fuit.)
**[Jest]**

#### AC7 — Titre borné : troncature exacte à 80 et repli
- `deriveTitle` d'un texte dont la 1ʳᵉ ligne fait **81 caractères** renvoie une
  chaîne de **longueur exactement 80** (les 80 premiers caractères de la ligne).
- `deriveTitle` d'une 1ʳᵉ ligne de **80 caractères** renvoie cette ligne inchangée
  (longueur 80). `deriveTitle` d'une 1ʳᵉ ligne de **79** renvoie 79.
- `deriveTitle("")`, `deriveTitle(null)`, `deriveTitle(undefined)`,
  `deriveTitle("\n\n")` renvoient la constante de repli (`"Analyse sans titre"`),
  jamais une chaîne vide ni une exception.
- (Bornes exactes 79/80/81, leçon 9.7. Falsifiable : off-by-one ou repli vide.)
  **[Jest]**

#### AC8 — Suppression unitaire
Avec 3 entrées, `removeAnalysis(store, id2)` puis `listAnalyses` renvoie **2**
entrées, **sans** celle d'`id2`, les deux autres intactes et toujours triées.
`removeAnalysis` d'un `id` inexistant ne lève pas et laisse la liste inchangée.
(Falsifiable : échoue si la mauvaise entrée est retirée ou si tout est effacé.)
**[Jest]**

#### AC9 — Tout effacer
Avec N entrées, `clearAnalyses(store)` puis `listAnalyses` renvoie `[]` (liste
vide). (Falsifiable : échoue si une entrée subsiste.) **[Jest]**

#### AC10 — Parse défensif : entrée corrompue ignorée, pas de crash
`parseRecords` sur une entrée brute corrompue (JSON cassé, champ obligatoire
manquant, `schemaVersion` inconnu, clé interdite présente) **ignore** l'entrée
invalide et renvoie les entrées valides restantes, **sans lever d'exception**. Sur
une entrée totalement illisible : renvoie `[]`. (Falsifiable : échoue si une entrée
corrompue plante le chargement ou si une entrée à clé interdite est acceptée.)
**[Jest]**

#### AC11 — Erreur de store en lecture/écriture : nature de l'erreur, pas un throw nu
- Avec un store dont `read()` **rejette** (ex. `new Error('SQLITE_READ_FAILED')`),
  `listAnalyses` **rejette** avec une erreur dont le message **identifie** l'échec
  de lecture (pattern asserté, ex. `/read|store|sqlite/i`), **jamais** un message
  de stub générique. Idem pour `write()` rejetant lors de `saveAnalysis`
  (message identifiant l'écriture).
- Test de contraste : avec un store sain, `listAnalyses`/`saveAnalysis`
  **n'émettent aucune erreur** (l'erreur n'apparaît que quand le store échoue).
- (Leçon `rejects.toThrow()` nu + « asserter la NATURE de l'erreur » : interdire le
  throw nu. Falsifiable : échoue si l'erreur est avalée ou si tout throw passe.)
  **[Jest]**

#### AC12 — Invariant « strictement local » : aucun import réseau dans `history.ts` (statique)
Test statique/structurel : le source de `src/lib/history.ts` **n'importe pas**
`fetch`, `./analyzeApi`, `./config`, ni aucun module réseau ; il **ne référence
jamais** `analyzeListing` ni `/analyze`. (Falsifiable : un grep/test échoue si un
import réseau ou une référence à l'endpoint apparaît dans le module historique.)
**[Jest]**

#### AC13 — Inertie réseau prouvée sur la dépendance terminale + contraste
Pour prouver que sauvegarder/lister/rouvrir **ne déclenche aucun appel réseau** :
- `global.fetch` est mocké (compteur). `saveAnalysis`, `listAnalyses`,
  `removeAnalysis`, `clearAnalyses` exécutés via un store in-memory → `fetch`
  **`call_count === 0`** (dépendance terminale réelle observée, pas une façade).
- **Test de contraste causal** : le même `fetch` mocké, appelé par `analyzeListing`
  (chemin d'analyse réel, tranche 1), **incrémente** le compteur — prouvant que le
  garde-fou détecterait un appel s'il survenait. (Leçon mobile-phase1 : une inertie
  n'a de valeur que si un contraste prouve que l'effet serait vu.) **[Jest]**

#### AC14 — Isolation d'état entre tests
Un test insère une entrée ; le test suivant (store réinitialisé en `beforeEach`)
démarre sur une liste **vide** (`listAnalyses` renvoie `[]`). Un test dédié
asserte qu'aucun état du store de test ne fuit d'un test à l'autre. (Leçon 9.7/9.9 :
état partagé réinitialisé, pas d'ordre-dépendance.) **[Jest]**

### 7.B Famille B — device / bout-en-bout : CHECKLIST MANUELLE

> Non automatisable en sandbox (pas de device, `expo-sqlite` natif). Chaque item :
> appareil testé (Expo Go iOS / APK Android), observation, **PASS/FAIL**.

#### AC-B1 — Sauvegarde auto à la fin d'une analyse
Étape : faire une analyse complète (collage URL → WebView → extraction → résultat).
- **Réussite** : sans action supplémentaire, l'analyse apparaît dans « Mes
  analyses » (titre court de l'annonce, date, donut de score coloré).
- **Échec** : rien n'est sauvegardé, ou doublon créé pour une même analyse.

#### AC-B2 — Adaptateur sqlite : persistance entre lancements
Étape : faire 2 analyses, **fermer puis rouvrir l'app**.
- **Réussite** : les 2 entrées sont toujours présentes après redémarrage (table
  `history` persistée). Aucune colonne de texte/photos d'annonce dans la base.
- **Échec** : historique vidé au redémarrage, ou présence de `raw_text`/photos.

#### AC-B3 — Écran « Mes analyses » accessible depuis InputScreen
Étape : depuis l'écran de saisie, ouvrir « Mes analyses » (état `'history'`).
- **Réussite** : l'écran liste les entrées, triées plus récent d'abord, chaque
  vignette réutilisant `ScoreDonut` + couleur `verdictColorFromLabel(verdict)`.
- **Échec** : pas d'accès, liste non triée, couleur incohérente avec le verdict.

#### AC-B4 — Rouvrir une analyse SANS appel réseau
Étape : passer l'appareil en **mode avion**, ouvrir une entrée d'historique.
- **Réussite** : `ResultScreen` s'affiche à l'identique (score, piliers, actions,
  contexte local), **instantanément, hors ligne** (preuve qu'aucun `/analyze` n'est
  rappelé).
- **Échec** : erreur réseau, écran vide, ou tentative d'appel `/analyze`.

#### AC-B5 — Dédup par URL sur device
Étape : ré-analyser **la même** annonce (même URL).
- **Réussite** : une **seule** entrée pour ce bien, mise à jour et remontée en
  tête (pas de doublon).
- **Échec** : deux entrées pour la même URL.

#### AC-B6 — Suppression unitaire + tout effacer
Étape : supprimer une entrée ; puis « tout effacer ».
- **Réussite** : l'entrée disparaît (les autres restent) ; « tout effacer » vide la
  liste ; après redémarrage, l'état effacé persiste.
- **Échec** : mauvaise entrée supprimée, ou réapparition au redémarrage.

#### AC-B7 — Plafond 50 sur device
Étape (si praticable) : dépasser 50 analyses, ou vérifier via un jeu de données
injecté en dev.
- **Réussite** : au plus 50 entrées affichées ; la plus ancienne évincée.
- **Échec** : croissance illimitée.

#### AC-B8 — Robustesse store : échec sqlite ne crashe pas l'app
Étape : simuler/forcer un échec d'ouverture/lecture sqlite (dev).
- **Réussite** : l'app **ne crashe pas** ; l'écran « Mes analyses » affiche un état
  d'erreur lisible ou une liste vide ; l'analyse normale reste possible.
- **Échec** : crash de l'app sur erreur de store.

---

## 8. Plan de tests (synthèse)

- **Famille A (Jest, `src/lib/history.test.ts`)** : AC1–AC14. Store in-memory
  injecté, réinitialisé en `beforeEach`. Pour chaque AC, prouver la falsifiabilité
  (le test rougit si la logique est cassée). Garde-fous critiques : AC2 (whitelist
  statique + dynamique falsifiable), AC5 (bornes 50/51), AC7 (bornes 79/80/81),
  AC11 (nature de l'erreur, pas throw nu), AC12 (statique : pas d'import réseau),
  AC13 (inertie terminale + contraste), AC14 (isolation).
- **Famille B (device)** : AC-B1–AC-B8, sur Expo Go iOS + APK Android. Renseigner
  appareil, observation, PASS/FAIL par item.
- **Adaptateur sqlite (`historyStoreSqlite.ts`)** : non couvert Jest (module natif).
  Vérifié par AC-B2 (persistance), AC-B7 (plafond bout-en-bout), AC-B8 (robustesse).

---

## 9. Plan d'implémentation par petits pas (machine utilisateur, hors sandbox)

> Pas 1–4 vérifiables par Jest (famille A) ; pas 5–7 par la checklist device
> (famille B). Le sandbox ne peut pas exécuter `expo-sqlite` ni un device.

1. **`npx expo install expo-sqlite`** (ajout dépendance, `package.json`).
2. **`src/lib/history.ts`** : types + port `HistoryStore` + `deriveTitle` +
   `normalizeUrlKey` + `buildRecord` (whitelist) + `upsertRecord` (dédup/plafond/
   tri) + `parseRecords` + façade `saveAnalysis/listAnalyses/removeAnalysis/
   clearAnalyses`. **Aucun import réseau ni sqlite.**
3. **`src/lib/history.test.ts`** : AC1–AC14 (rouge → vert), store in-memory,
   `beforeEach` reset, falsifiabilité prouvée.
4. **`src/lib/historyStoreSqlite.ts`** : adaptateur concret du port (table
   `history`, schéma §4.3, `CREATE TABLE IF NOT EXISTS`, parse défensif délégué à
   `parseRecords`). Pas de Jest.
5. **`App.tsx`** : état `'history'` ; à `onResult`, dériver le titre depuis le texte
   extrait (dans `WebViewScreen.onMessage`, transmis à `onResult` ou à App) et
   appeler `saveAnalysis(sqliteStore, { url, title, result, savedAt: Date.now() })`
   **sans bloquer** l'affichage du résultat (best-effort ; un échec de store
   n'empêche pas d'afficher le résultat). Réouverture : `setResult(stored.result)`
   + `setScreen('result')`. Vérif device AC-B1, AC-B2, AC-B4, AC-B5.
6. **`src/screens/HistoryScreen.tsx`** : liste triée, vignette `ScoreDonut` +
   `verdictColorFromLabel`, actions rouvrir / supprimer / tout effacer, état
   d'erreur store lisible. Vérif device AC-B3, AC-B6, AC-B7, AC-B8.
7. **`src/screens/InputScreen.tsx`** : affordance « Mes analyses » → `onOpenHistory`
   (nouvelle prop, câblée dans `App.tsx`). Vérif device AC-B3.

À chaque pas Jest : prouver la falsifiabilité (le test échoue si on casse la
logique), conformément aux leçons anti-faux-vert.

---

## 10. Points à confirmer par l'humain (GATE 2)

> Aucun de ces points n'est laissé ambigu dans la spec : ils sont **tranchés de
> façon testable** ci-dessus et listés ici pour validation explicite.
1. **Titre = 1ʳᵉ ligne non vide du texte, bornée à 80 caractères**, repli
   `"Analyse sans titre"` (§5.3). Confirmer la borne 80 et le libellé de repli.
2. **Normalisation d'URL pour la dédup = `origin + pathname`** (query/fragment
   ignorés, §5.2). Confirmer (impacte AC3/AC4).
3. **Sauvegarde auto best-effort** : un échec de store ne bloque pas l'affichage du
   résultat (§9 pas 5, AC-B8). Confirmer ce comportement de dégradation.
4. **Forme du port = read/write de l'ensemble** (§3.2). Confirmer (alternative :
   port granulaire insert/delete — non retenu, plus de surface pour 50 entrées).

---

SPEC prête pour GATE 2 (approbation humaine).

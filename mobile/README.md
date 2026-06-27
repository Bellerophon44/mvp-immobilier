# Coherence — app mobile (Phase 2, tranche 1)

App React Native / Expo (SDK 54) qui realise la boucle minimale :
collage d'une URL d'annonce LeBonCoin -> chargement WebView + extraction
on-device (texte + galerie) -> `POST /analyze` (backend Phase 1, inchange) ->
ecran de resultat de coherence.

La logique pure (extraction d'URL, filtrage de galerie, appel `/analyze`) vit
sous `src/lib/` et est couverte par les tests Jest. Les ecrans RN
(`src/screens/`) et le script injecte dans la WebView (`src/webview/`)
reutilisent cette logique comme source unique de verite.

## Prerequis

- Node 18+ et npm.
- L'app mobile **Expo Go (SDK 54)** sur un appareil iOS/Android, sur le meme
  reseau que la machine de dev (ou un dev build).

## Installation

```bash
cd mobile
npm install
```

## Configuration du backend (EXPO_PUBLIC_API_URL)

L'URL du backend n'est JAMAIS codee en dur : elle est lue depuis la variable
d'environnement publique Expo `EXPO_PUBLIC_API_URL` (`src/lib/config.ts`).
Sans elle, l'appel `/analyze` echoue (URL vide).

1. Copier l'exemple : `cp .env.example .env`
2. Renseigner l'URL racine du backend dans `.env`, par exemple :
   - prod : `EXPO_PUBLIC_API_URL=https://backend-frosty-sound-441-docker.fly.dev`
   - staging : `EXPO_PUBLIC_API_URL=https://coherence-staging.fly.dev`
   - local : `EXPO_PUBLIC_API_URL=http://<ip-lan>:8080`

L'app appelle alors `POST ${EXPO_PUBLIC_API_URL}/analyze`.

> `.env` est gitignore : ne committez jamais d'URL/secret reels. Le prefixe
> `EXPO_PUBLIC_` embarque la valeur dans le bundle, donc n'y mettez AUCUN secret
> (aucune cle OpenAI/Google/admin cote app : tout appel tiers passe par le
> backend).

## Lancer l'app

```bash
cd mobile
npm start          # ou: npx expo start
```

Scanner le QR code affiche avec Expo Go (SDK 54). L'app s'ouvre sur l'ecran de
saisie ; collez l'URL d'une annonce, lancez l'analyse, fermez la banniere
cookies et faites defiler la galerie dans la WebView, puis « Extraire et
analyser ».

## Tests et verifications

```bash
cd mobile
npm test           # Jest : logique pure (src/lib), 73 tests
npm run typecheck  # tsc --noEmit
```

Les ecrans (`.tsx`) ne sont pas couverts par Jest (verifies manuellement sur
device, cf. SPEC §5.B).

## Identite visuelle

Le theme (`src/theme.ts`) reprend a l'identique les tokens du design system web
(`frontend/app/globals.css`) : palette Metz (encre, parchemin, brique, or de
Jaumont), echelle typo, polices **Instrument Serif** (titres) / **Geist** (corps)
/ **Geist Mono** (chiffres) chargees via `@expo-google-fonts`. Composants de marque
portes en `react-native-svg` : `Wordmark` (losange brique) et `ScoreDonut`. Regle :
l'or de Jaumont est **reserve au cachet « contexte local »** ; la brique est le seul
accent d'action. La couleur du verdict derive du **libelle renvoye par le backend**
(`verdictColorFromLabel`), pas du score (sinon mot et couleur divergent aux seuils).

## Distribution (EAS)

Projet Expo : `@coherence44/coherence` (projectId dans `app.json`). Profils dans
`eas.json` (`development` / `preview` / `production`) ; `EXPO_PUBLIC_API_URL` (prod)
est injectee **au build** via `eas.json` (donc un build n'a PAS besoin de `.env`).

- **Apercu en Expo Go (sans serveur de dev)** — `eas update` publie un bundle
  ouvrable dans Expo Go (runtime `exposdk:54.0.0`, `runtimeVersion.policy =
  sdkVersion`).

  **Chemin fiable (recommande) — env cote serveur Expo.** Contrairement a
  `eas build`, **`eas update` n'utilise PAS le `env` de `eas.json`** : il lit le
  `.env` / l'environnement **au moment de l'export**. Pour ne plus dependre d'un
  `.env` local (cause du « Network request failed », cf. `.claude/lessons.md`
  2026-06-25), declarer la variable **une seule fois** sur le serveur Expo, puis
  publier avec `--environment` (le script npm `update:preview` le fait) :
  ```bash
  eas login
  # one-shot : enregistre EXPO_PUBLIC_API_URL cote serveur pour l'env "preview"
  eas env:create --environment preview \
    --name EXPO_PUBLIC_API_URL \
    --value https://backend-frosty-sound-441-docker.fly.dev \
    --visibility plaintext
  eas env:list --environment preview        # verifier
  # ensuite, a chaque apercu :
  npm run update:preview                     # = eas update --branch preview --environment preview
  ```
  Le log d'export doit afficher `Loading environment variables from EAS` et la
  valeur `EXPO_PUBLIC_API_URL`. Plus besoin de `.env` pour `eas update`.

  **Repli local (si pas d'env serveur)** : avoir un `.env` (ou exporter la variable)
  AVANT `eas update --branch preview` ; sans `EXPO_PUBLIC_API_URL` a cet instant le
  bundle appelle une URL vide → « Network request failed ».
- **Build Android (APK autonome, gratuit, sans compte)** :
  ```bash
  eas build -p android --profile preview
  ```
  Donne un `.apk` a telecharger/installer (vraie icone, sans Expo Go). ✅ Construit
  et valide sur device.
- **Build iOS (app sur iPhone)** : necessite un **compte Apple Developer (99 $/an)**
  — il n'existe pas de build iOS cloud gratuit (le « 7 jours » d'Apple est local via
  Xcode/Mac). Procedure complete : voir **Runbook iOS / TestFlight** ci-dessous.
  **Statut : en attente** de l'inscription Apple (bloquee a la verif d'identite —
  en France, fournir **passeport** (ou CNI) plutot que le permis ; permis « pas
  valide pour la region »).
- **Sans Git installe sur la machine** (ex. Windows + GitHub Desktop) : EAS exige
  un VCS ; lancer les commandes EAS avec `EAS_NO_VCS=1` (`setx EAS_NO_VCS 1` pour le
  rendre permanent).

## Runbook iOS / TestFlight

> A derouler **une fois le compte Apple Developer actif**. Le repo est deja pret
> cote code (bundleId `fr.coherencemetz.app`, `projectId` lie, profils EAS iOS,
> icone/splash, `ios.config.usesNonExemptEncryption=false` pour l'export
> compliance). Aucune permission iOS (camera/photos/geoloc) n'est requise : la
> boucle actuelle = coller URL → WebView → extraction DOM → `/analyze`, donc aucun
> `NSUsageDescription` a declarer.

### 1. Enregistrer l'iPhone + build ad-hoc (install directe)
```bash
cd mobile
eas login                       # Apple ID rattache au compte developpeur
eas device:create               # enregistre l'UDID de l'iPhone (suivre le lien/QR)
npm run build:ios:preview       # = eas build -p ios --profile preview
```
EAS genere automatiquement **certificat + provisioning profile** via l'Apple ID
(repondre « yes » a la creation). A la fin, installer le `.ipa` sur l'iPhone
enregistre via le lien/QR. Pas de Mac requis.

### 2. TestFlight (test interne propre)
```bash
npm run build:ios:prod          # = eas build -p ios --profile production (app-store)
npm run submit:ios              # = eas submit -p ios --latest  → App Store Connect
```
`eas submit` demande, la 1re fois, 3 identifiants **specifiques au compte** (a
recuperer une fois le compte actif) ; pour les figer et ne plus etre invite,
completer `eas.json` :
```jsonc
// eas.json → "submit": { "production": { ... } }
"ios": {
  "appleId": "<email Apple ID developpeur>",
  "ascAppId": "<App ID numerique, App Store Connect → ton app → General → App Information → Apple ID>",
  "appleTeamId": "<Team ID, developer.apple.com → Membership details>"
}
```
- L'app doit exister cote **App Store Connect** (creee a la 1re soumission ou
  manuellement) ; `ascAppId` = son identifiant numerique.
- Export compliance : deja gere par `usesNonExemptEncryption=false` (pas de
  question a chaque build). L'app n'utilise que HTTPS standard.
- `appVersionSource: remote` + `autoIncrement` (profil production) → le numero de
  build s'incremente tout seul a chaque upload (exigence TestFlight).
- Apres upload, ajouter les testeurs internes dans App Store Connect → TestFlight.

## PWA (alternative web, iPhone 0 €)

Le site web `coherence-metz.fr` est installable (« Sur l'ecran d'accueil ») via le
manifeste `frontend/app/manifest.ts` + icones + meta iOS. C'est le moyen **gratuit,
sans Apple** d'avoir Coherence sur iPhone. Limite : un PWA **ne peut pas** faire
l'extraction WebView de LBC (cross-origin) ni le partage natif — son flux est
« coller URL/texte → backend ». L'extraction in-app reste le differenciateur de
l'app native.

## Limites & pieges connus

- **`eas update` + `EXPO_PUBLIC_*`** : fiabilise via les **variables d'env cote
  serveur Expo** (`eas env:create` + `npm run update:preview` qui passe
  `--environment preview`) — voir « Distribution ». Le repli `.env` local reste
  valable si l'env serveur n'est pas configure.
- **Cache Expo Go** : apres un nouveau `eas update`, Expo Go peut servir l'ancien
  bundle. Tuer l'app et rouvrir le **groupe d'update precis** ; en dernier recours,
  reinstaller Expo Go.
- **iOS** : aucune installation sur iPhone reel sans compte Apple Developer paye.

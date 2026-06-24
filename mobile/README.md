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

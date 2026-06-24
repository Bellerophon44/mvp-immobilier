# Spike on-device — extraction texte + photos LeBonCoin

Mini-app **jetable** pour le niveau 2 du spike Phase 2 mobile. Elle ouvre une
annonce dans une fenêtre intégrée (WebView), comme le ferait l'app finale, et
vérifie qu'on peut en extraire **sur l'appareil** le texte + les URLs des photos.

Protocole complet et critères de réussite : `../../docs/specs/mobile-phase2-spike-PROTOCOLE.md`.
Rappel : la fetchabilité des URLs par OpenAI est **déjà tranchée** (Spike A) — ce
spike ne teste QUE l'extraction.

## Pré-requis (une fois)

- **Node.js** installé sur ton ordinateur (https://nodejs.org).
- L'app **Expo Go** sur ton téléphone (gratuite, App Store / Google Play).
- Ton téléphone et ton ordinateur sur le **même réseau Wi-Fi**.

## Lancer (≈ 4 commandes)

`App.js` ci-joint est le seul fichier « maison ». On le dépose dans un projet
Expo neuf (qui apporte automatiquement les bonnes versions, compatibles avec ton
Expo Go) :

```bash
# 1. Créer un projet Expo vierge (réponds au nom proposé)
npx create-expo-app@latest lbc-spike --template blank

cd lbc-spike

# 2. Ajouter la WebView (version choisie automatiquement par Expo)
npx expo install react-native-webview

# 3. Remplacer le App.js généré par celui de ce dossier
#    (copie spikes/lbc-extraction/App.js par-dessus lbc-spike/App.js)

# 4. Démarrer
npx expo start
```

Un **QR code** s'affiche dans le terminal : scanne-le avec **Expo Go** (Android)
ou l'appareil photo (iOS). L'app se lance sur ton téléphone.

## Ce que tu fais dans l'app

1. Colle l'URL d'une **vraie annonce LeBonCoin** dans le champ, tape **Charger**.
2. Dans la fenêtre intégrée : **ferme la bannière cookies**, puis **fais défiler
   toute la galerie de photos** (sinon LBC ne les charge pas toutes).
3. Tape **Extraire le contenu**.
4. En bas s'affichent : la **longueur du texte** + un extrait, et la **liste des
   URLs de photos** trouvées.

Refais-le sur **3-5 annonces** variées (beaucoup de photos / peu de photos /
maison / appartement).

## Comment lire le résultat

**Réussite** (≥ 4/5 annonces) :
- le texte contient bien titre + description ;
- le nombre de photos correspond ~à la galerie affichée, les URLs commencent par
  `https://img.leboncoin.fr/...` ;
→ l'extraction on-device est viable, on peut spécifier l'app Tier 1 (React Native).

**Échec / à remonter** :
- la page est bloquée (mur anti-bot / captcha) même dans la WebView ;
- 0 photo trouvée alors que la galerie est pleine (photos en `blob:`/`canvas`,
  ou hôte d'images différent — voir `IMAGE_HOSTS` dans `App.js`) ;
- le texte est vide ou tronqué.
→ remonter le cas : peut imposer React Native obligatoire, ou rouvrir l'analyse
  (si photos non récupérables en URL, la Phase 1 ne suffit plus pour ce portail).

## Tester un autre portail

Dans `App.js`, ajouter l'hôte d'images du portail à la liste `IMAGE_HOSTS`.

## Niveau 1 (rappel, sans rien installer)

Avant même ce projet : sur ordinateur, ouvre une annonce LBC, **F12 → Console**,
colle le petit script fourni dans la conversation. Si le texte + les photos
sortent dans un navigateur normal, c'est déjà bon signe pour le niveau 2.

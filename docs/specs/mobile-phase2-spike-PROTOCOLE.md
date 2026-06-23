# Spike on-device — extraction texte + galerie photo via WebView (Phase 2 mobile)

> Statut : PROTOCOLE prêt à exécuter — NON exécuté. Décidé en GATE 1 (2026-06-23,
> cf. `CONTEXT.md` §0 « App mobile — Phase 2 »). Ce spike lève le **risque
> technique n°1** et **conditionne le choix de techno** (Q2 de
> `mobile-phase2-app-ANALYSE.md`). Il ne peut PAS tourner dans le sandbox de
> l'atelier (pas de device, egress LBC hors allowlist) : c'est un geste
> humain/device.

## 0. Ce qui est DÉJÀ tranché — ne pas re-tester

**Spike A (« Probe images LBC », `.github/workflows/probe-lbc-images.yml`,
exécuté le 2026-06-23) a déjà répondu à la moitié AVAL du problème** : une fois
qu'on dispose des URLs d'images, **OpenAI les fetche** (4/4 vraies photos, CDN
`img.leboncoin.fr` ouvert, URLs non signées, pas de verrou Referer). Conclusion
actée : **Option 1 (envoyer les URLs) suffit**, l'upload d'octets (Option 2) est
inutile pour LBC. C'est sur ce résultat qu'a été bâtie la Phase 1 (`image_urls`).
Enseignement clé : **le mur anti-bot DataDome est sur la PAGE d'annonce, pas sur
le CDN d'images.**

**Ce spike-ci porte donc UNIQUEMENT sur la moitié AMONT, non testée** : l'app
peut-elle, sur l'appareil, **récupérer automatiquement** le texte + les URLs de
la galerie depuis la page d'annonce (qui, elle, est derrière DataDome) ? Le probe,
lui, recevait des URLs **copiées à la main** depuis un navigateur — il n'a jamais
testé l'extraction automatique. Ne pas refaire le test de fetchabilité OpenAI
(le POST `/analyze` en fin de procédure n'est qu'une confirmation de bout en bout,
pas le cœur du spike).

## 1. Objectif

Prouver — ou infirmer — qu'une app mobile peut, **on-device**, extraire d'une
annonce immobilière ouverte par l'utilisateur :
1. le **texte** de l'annonce (titre + description) ;
2. les **URLs des photos** de la galerie (http(s) publiques),

afin de les POSTer à `/analyze` en mode `raw_text` + `image_urls` (contrat livré
en Phase 1). Le backend est déjà prêt ; tout le risque est côté extraction
client.

## 2. Hypothèse à valider

Dans une **WebView contrôlée** chargeant l'URL d'annonce, une **injection JS**
peut lire `document` (texte via `innerText`, images via `<img>`/`srcset`) et
renvoyer le résultat à la couche native, malgré les protections du portail
(lazy-load, anti-bot, overlays consentement, cross-origin).

## 3. Corpus de test

3 à 5 annonces **réelles** LeBonCoin (cible principale), variées :
- une avec **beaucoup de photos** (>15, pour tester le cap d'entrée 50 et le
  lazy-load) ;
- une avec **peu de photos** (1-3) ;
- une **maison** et un **appartement** (layouts/DOM différents) ;
- si possible une annonce d'un **second portail** (SeLoger ou Bien'ici) pour
  juger la généralité de l'approche.

Conserver les URLs testées et un comptage manuel des photos réellement affichées
(vérité terrain).

## 4. Procédure

1. Monter un harnais minimal avec **`react-native-webview`** (Expo) — c'est aussi
   l'option techno favorite, donc le spike sert de preuve ET de socle. Optionnel :
   répliquer en **Capacitor** pour comparer la robustesse de l'injection.
2. Charger l'URL d'annonce dans la WebView.
3. Gérer le **consentement/cookies** (détecter et cliquer l'overlay si présent).
4. Déclencher le **lazy-load** : scroller programmatiquement jusqu'en bas (ou
   itérer sur le carrousel de photos) avant de collecter.
5. Injecter le JS de collecte (`injectedJavaScript` + `window.ReactNativeWebView.postMessage`) :
   - texte : `document.querySelector(<sélecteur description>)?.innerText` avec
     repli sur `document.body.innerText` ;
   - images : parcourir `<img>`, extraire `src` + la plus grande candidate de
     `srcset`, **filtrer** au domaine CDN d'images du portail, **dédupliquer** en
     préservant l'ordre.
6. Renvoyer `{ text, image_urls[] }` au natif via `onMessage`.
7. POSTer à `/analyze` (`raw_text` + `image_urls`) sur un backend de test et
   vérifier que `photo_status` est bien renseigné (preuve de bout en bout).

## 5. Critères de réussite / échec (falsifiables)

**Réussite** (le natif RN/Expo Tier 1 est viable, Q2 = RN/Expo) si, sur **≥ 4/5**
annonces :
- le **texte** récupéré contient titre + description complète ;
- les **image_urls** récupérées correspondent à la galerie affichée (±, après
  dédup), sont des **http(s) publiques** (donc compatibles `_is_safe_url` et le
  fetch vision OpenAI), et ≥ 80 % des photos visibles sont captées ;
- l'aller-retour `/analyze` renvoie un `photo_status` cohérent.

**Échec / signal d'alerte** (à remonter, peut imposer RN obligatoire ou rouvrir
la stratégie) :
- l'injection JS est **bloquée cross-origin** ou par anti-bot / mur de login ;
- les photos sont servies en **`blob:`/`data:`/canvas** (pas d'URL http(s)
  réutilisable) → l'approche `image_urls` ne marche pas, il faudrait uploader des
  octets (autre contrat backend, hors Phase 1) ;
- le lazy-load ne se déclenche pas sans gestes utilisateur réels ;
- comportement **divergent entre portails** rendant l'approche non générale.

## 6. Ce que le résultat décide

- **Si réussite en wrapper (Capacitor)** : un wrapper peut suffire (moins cher),
  mais arbitrer le risque Apple 4.2 (cf. analyse Q2-b).
- **Si réussite seulement en RN** : RN/Expo devient obligatoire (Q2-a).
- **Si échec image_urls (blob/canvas)** : la Phase 1 ne suffit pas pour ce
  portail ; rouvrir l'analyse (upload d'octets = nouveau contrat backend, nouveau
  chantier — ne PAS l'improviser).

## 7. Garde-fous (RGPD / anti-patterns CONTEXT §11)

- Extraction **uniquement** sur l'annonce que l'utilisateur a explicitement
  ouverte/partagée — **pas de crawl**, pas de collecte de masse.
- **Aucun stockage** des photos ni du texte côté app au-delà de la requête ;
  image_urls transmises au backend, jamais loggées (déjà garanti côté serveur).
- **Pas de redistribution** d'annonce (anti-pattern §11) : on analyse, on ne
  republie pas.
- Respecter `robots.txt` / CGU dans l'esprit ; le spike lit le DOM rendu pour
  l'utilisateur lui-même, ne contourne pas une authentification.

## 8. Hors périmètre du spike

Construire l'app complète, le partage natif (share extension), l'OCR, la géoloc,
le design. Le spike prouve **uniquement** la faisabilité de l'extraction
texte + image_urls on-device.

## 9. Résultats

### Niveau 1 — navigateur desktop (2026-06-23) : ✅ CONCLUANT
Annonce LBC réelle (appartement, Metz Sablon), script console :
- **Texte** : 5741 caractères, complet (titre, prix 212 000 €, 93 m², prix/m²,
  quartier, agence) → extraction texte triviale via `document.body.innerText`.
- **Photos** : toutes sur `img.leboncoin.fr`, **non signées** (`?rule=ad-large`),
  conformes au constat Spike A.
- **Finding** : LBC sert la **même photo sous plusieurs tailles** (`ad-thumb`/
  `ad-large`/`ad-image`) → 25 URLs brutes pour ~9 photos réelles ; présence d'un
  asset `?rule=bo-*` = **logo agence** (à exclure). D'où la règle de nettoyage
  retenue (et appliquée dans `spikes/lbc-extraction/App.js`) : **dédupliquer par
  chemin d'image, normaliser en `ad-large`, exclure les rules `bo-`**. Cette règle
  devra être reprise dans la spec de l'app (et éventuellement validée côté backend,
  mais le cap d'entrée 50 + dédup y absorbent déjà les doublons).
- La page s'est chargée **sans captcha** dans un navigateur normal (cohérent : le
  mur DataDome cible les bots, pas un vrai navigateur).

**Finding majeur — filtrer par hôte SUR-collecte.** 2ᵉ annonce : 28 images
distinctes sur `img.leboncoin.fr` alors que la galerie en comptait bien moins. Le
détail par `rule` le démasque :

| `rule` | annonce 1 | annonce 2 | nature |
|---|---|---|---|
| `ad-large` | 9 | 6 | **galerie réelle** (varie avec l'annonce) |
| `ad-image` | 14 | 14 | **annonces similaires** (bloc reco, taille constante) |
| `ad-thumb` | 1 | 1 | vignette de couverture |
| `bo-thumb` | 1 | 1 | logo agence |

`ad-image` constant à 14 = carrousel de recommandations → ce ne sont PAS les
photos du bien. **Règle retenue : ne garder que `rule=ad-large`** (galerie), dédup
par chemin. Enjeu de **justesse**, pas que de coût : sans ce filtre on enverrait à
OpenAI des photos d'AUTRES annonces → `photo_status` faux.
**Confirmé sur 2 annonces** : `ad-large` = 9 (page « 1/9 ») puis 6 (page « 1/6 »),
soit exactement le compteur de galerie affiché. Niveau 1 clos.
⚠️ Réserve : ces noms de `rule` viennent du site **desktop**. Le site **mobile**
(dans la WebView, Niveau 2) peut les nommer autrement → la mini-app affiche
désormais le détail par `rule` pour le constater de visu. À terme (spec app), une
sélection **scopée au conteneur DOM de la galerie** sera plus robuste qu'un nom de
`rule` en dur.

➡️ La moitié amont (extraction) est **prouvée en navigateur**. Reste à confirmer
le **même comportement dans la WebView in-app** (Niveau 2) — seul contexte où
l'injection est cross-origin et où DataDome / les noms de `rule` pourraient
différer.

### Niveau 2 — WebView in-app (Expo) : ⬜ à exécuter sur device.

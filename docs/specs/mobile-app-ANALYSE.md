# Analyse — Portage de Cohérence en application mobile (iOS / Android)

> Rôle : ANALYSE de faisabilité / cadrage stratégique. Document de réflexion, pas
> une spec : il ne tranche rien de structurant et n'engage aucun code. Issu d'un
> fil d'échange avec le fondateur (2026-06-21).
>
> Sources relues : `backend/CLAUDE.md` (§1 anti-patterns, §2 stack, §5 endpoints,
> §6bis screening photo, §7 modèle de données, §8 scrapers, §9 collecte, §10
> contrat, §11/§11bis roadmap) ; `CONTEXT.md` ; le code réel
> (`app/url_fetch.py`, `app/photo_evidence.py`, `app/analysis.py`, `db/models.py`,
> `frontend/lib/api.ts`).
>
> Branche de dev : `claude/cohérence-mobile-app-effort-tuu74e`.

---

## 0. Objet et résumé

Évaluer l'effort et l'architecture d'un portage de Cohérence en **application
mobile native publiable sur l'App Store et le Play Store**, et instruire les
points durs identifiés dans le fil :
1. méthodes de portage et effort comparé ;
2. fonctionnalités natives qui *justifient* une app (vs un simple marque-page) ;
3. le blocage **LeBonCoin** sur l'analyse d'URL, et comment le contourner
   proprement sur mobile ;
4. la **conservation des photos** (allégations visuelles) quand on bascule sur
   `raw_text` ;
5. le chantier **notifications push de re-list / baisse de prix** — le plus
   ambitieux, qui casse plusieurs invariants de l'architecture actuelle.

**Conclusion courte.** Le portage UI est *petit* (architecture déjà découplée,
API REST publique sans auth, ~2 écrans). Le travail réel n'est pas le portage :
c'est (a) sécuriser l'ingestion d'annonces malgré les murs anti-bot, et (b)
décider si l'on franchit le cap « outil anonyme et sans état → produit à
utilisateurs identifiés et avec état » qu'impose la rétention par notification.

---

## 1. Point de départ technique (état réel)

Architecture **déjà découplée** :
- **Backend** FastAPI sur Fly.io, expose une API REST JSON **publique, sans
  authentification utilisateur** (`/analyze`, `/travel-times`, `/feedback`,
  `/events` ; admin par `X-Admin-Token`). SQLite sur volume Fly.
- **Frontend** Next.js 16 / React 18 (SPA, ~2 700 lignes TS), déployé sur Vercel,
  consomme l'API. **2 écrans réels** : l'analyseur (home) + `/méthode`. Design
  system maison, pas de lib UI. Aucune brique mobile (pas de RN/Flutter/Capacitor,
  pas de PWA).

Conséquences majeures pour un portage :
- **Le backend ne bouge pas** quelle que soit la méthode : réutilisable tel quel.
- L'UI à porter est **minuscule** ; pas d'OAuth/login à recoder ; pas de
  cookies/sessions/stockage complexe ; chaque `/analyze` est **stateless**.
- C'est le scénario le plus favorable possible. Tout l'effort est côté
  présentation + capacités natives.

---

## 2. Méthodes de portage et effort comparé

Estimations en mode dev solo, à prendre comme ordres de grandeur (pas de fausse
précision). L'effort « code » est faible partout ; le risque dominant est la
**validation App Store** (règle Apple 4.2 « minimum functionality », qui recale
les simples wrappers de site web).

| # | Méthode | Effort | Sur les stores ? | Note |
|---|---|---|---|---|
| 1 | **PWA** (manifest + service worker) | ~1–2 j | ❌ Non | Préalable aux autres, mais hors périmètre stores |
| 2 | **Wrapper web** (Capacitor / PWABuilder) | ~1–2 sem | ✅ (Play facile, **App Store risqué**) | 1 codebase. Recalé Apple si 0 fonction native |
| 3 | **React Native + Expo** | ~4–8 sem | ✅ Les deux | Réutilise la logique React/TS, recode la présentation |
| 4 | **Flutter** | ~6–10 sem | ✅ Les deux | Réécriture complète, 3e langage à maintenir → difficile à justifier ici |

Coûts indépendants de la méthode : comptes développeur (Apple 99 $/an, Google
25 $ une fois) ; cycle de review (1–7 j + itérations de rejet) ; conformité
(politique de confidentialité, privacy labels Apple, RGPD) ; assets (icônes,
splash, captures store, ASO) ; CI/CD mobile (signature ; EAS Build simplifie) ;
**coût backend récurrent** (chaque analyse = appel OpenAI + Google Routes, latence
2–5 s → plus d'usage mobile = plus de coûts API).

**Recommandation.** Vu la petite UI déjà en React et le risque de ping-pong de
rejet Apple sur un wrapper, **Expo / React Native** est le meilleur rapport
effort/résultat pour une app durable. Le wrapper (méthode 2) reste l'option
« présence store rapide, budget zéro » si l'on accepte le risque Apple. Et
**valider d'abord l'appétit mobile** (les events de funnel donnent déjà la part
de trafic mobile) avant d'investir dans le natif — une PWA peut suffire à tester.

---

## 3. Fonctionnalités natives qui justifient l'app

Filtre : *qu'est-ce que le téléphone permet que le web ne permet pas, et qui colle
au moment d'usage de Cohérence* (en visite, devant une vitrine d'agence, en
scrollant les apps immo) ?

### Tier 1 — justifient l'app et peu coûteuses (branchent sur l'API existante)
1. **Partage natif depuis les apps immo** *(le « killer feature »)* — Share
   Extension iOS / intent-filter Android : depuis Bien'ici/SeLoger/Leboncoin →
   « Analyser avec Cohérence ». Supprime le friction copier-coller d'URL.
   Bonus : c'est *exactement* la fonction native qui fait passer la validation
   Apple 4.2.
2. **Scan / OCR de l'annonce papier** — vitrine d'agence le dimanche, fiche
   papier : photo → OCR sur l'appareil (Vision iOS / ML Kit Android) → `raw_text`.
   L'API accepte déjà `raw_text` : zéro changement backend.
3. **Géolocalisation « je suis devant le bien »** — pré-remplit adresse/quartier
   sans saisie. Toute la machinerie existe (BAN, `precision`, Google Routes).

### Tier 2 — différenciation plus profonde
4. **Notifications push** (baisse de prix / réapparition) — meilleur levier de
   rétention, infaisable sur web. **Seul chantier à backend nouveau lourd**
   (voir §6).
5. **Capture photo en visite vs allégations de l'annonce** — extension mobile de
   `photo_evidence.py` (l'appareil photo confronte tes photos aux promesses).

### Tier 3 — utile mais à surveiller (gadget / coût)
6. Dossier de visite hors-ligne (shortlist comparée, SQLite local).
7. Export/partage natif du rapport (déjà PDF web).

**Combinaison retenue** : trio **1 + 2 + 3** (peu coûteux, branche sur l'API,
crédibilise l'app face à Apple), puis **4** comme moteur de rétention dans un
second temps. Pré-requis stratégique : confirmer que l'usage est réellement
mobile et pas majoritairement desktop (copier-coller d'URL assis).

---

## 4. Le blocage LeBonCoin et le partage natif (cascade texte)

### Cause racine
`url_fetch.py` fait `requests.get(url)` **depuis l'IP datacenter Fly.io**.
LeBonCoin (anti-bot type DataDome) rejette ça (403 / page-challenge JS) → le texte
extrait passe sous `MIN_TEXT_LENGTH` → échec. **Le blocage n'est pas lié à l'URL,
mais à *qui* fait le fetch.** Sur mobile, le contenu est déjà rendu sur l'appareil
de l'utilisateur — vrai navigateur, souvent connecté, ayant déjà franchi le mur.
La solution est de **déplacer l'extraction du serveur vers l'appareil** et
d'envoyer `{raw_text}` plutôt que `{url}`. **Le contrat `raw_text` existe déjà.**

### Options de partage natif
- **A — Partager l'URL → fetch serveur** *(piège pour LBC)* : `/analyze {url}` →
  même 403. Valable seulement pour les sites non protégés (agences, idemmo…). À
  garder comme défaut, **inopérant sur LeBonCoin**.
- **B — Récupérer le texte rendu sur l'appareil → `raw_text`** *(le déblocage)* :
  - **B1 — iOS Share Extension + pré-traitement JS** (`NSExtensionJavaScript­Preprocessing­File`) lit `document.body.innerText` dans le contexte de la page.
    ⚠️ Marche depuis **Safari** ; depuis l'app native LBC le payload est en
    général *juste l'URL*.
  - **B2 — Android `ACTION_SEND` texte** : moins de contrôle ; l'app LBC ne donne
    souvent que l'URL.
  - **B3 — WebView embarquée** *(le plus robuste, recommandé)* : Cohérence reçoit
    l'URL, ouvre la page dans sa propre WebView (vrai navigateur on-device :
    exécute le JS, porte les cookies, franchit/affiche le challenge), puis
    **injecte un script** qui extrait le texte. Marche quelle que soit l'app
    source et que le partage donne du texte ou juste l'URL. Coût UX : la page se
    charge un instant (parfois bandeau cookies / captcha à résoudre par l'user).
- **C — Screenshot → OCR → `raw_text`** : immunisé par construction (rien n'est
  fetché). Lossy/partiel. Bon **filet de sécurité** si la WebView bute sur un
  captcha persistant.
- **D — Durcir le fetch serveur** (proxies résidentiels / headless / solveur
  anti-bot) : **à déconseiller** — course à l'armement fragile, coût récurrent,
  **zone grise juridique** (LBC a un historique contentieux scraping en France).

### Posture juridique / ToS
B3 et C automatisent le **copier-coller que l'utilisateur peut déjà faire** :
session de **son** navigateur, **action initiée par lui**, **une seule annonce**,
**non stockée ni redistribuée** → aligné avec l'anti-pattern §1 (« pas de
réagrégation/redistribution d'annonces brutes »). L'option D, elle, est du
scraping serveur à notre nom — ce que la jurisprudence vise.

### Cascade recommandée (texte)
1. **A** par défaut (sites non protégés). 2. **B3 (WebView + injection JS)** dès
qu'un domaine est connu pour bloquer (LBC). 3. **C (screenshot/OCR)** en filet.
Effet de bord : extension de partage + WebView + caméra/OCR sont **précisément**
les fonctions natives qui crédibilisent l'app face à Apple 4.2. *Contourner LBC
et justifier l'app native, c'est le même travail.*

---

## 5. Conserver les photos en mode `raw_text` (cascade photo)

### Le mécanisme actuel (vérifié dans le code)
`photo_evidence.assess_claims_with_photos(claims, image_urls)` construit des
parts `{"type":"image_url","image_url":{"url":url,"detail":"high"}}` → **ce sont
les serveurs d'OpenAI qui vont chercher les images, le backend ne télécharge
jamais les octets**. Les URLs viennent de `url_fetch.extract_image_urls(html)`,
qui **exige le HTML**. En mode `raw_text` : pas de HTML → pas d'URLs →
`_merge_photo_status` court-circuite. C'est là que les photos se perdent.

### Distinction essentielle : deux flux, un seul concerné
- **Flux « analyse » (app mobile)** → appelle `/analyze`, utilise
  `photo_evidence`, se heurte à LBC. Photos = **validation d'allégations**
  (cathédrale, Moselle…).
- **Flux « collecte » (base de comparables → historique de prix cross-agence)** →
  pipeline **serveur** (GitHub Actions, API Bien'ici + HTML d'agences),
  indépendant de l'app et de LBC (qui n'est pas une source collectée). Le
  « matching photo cross-source » est l'**incrément 2, différé**, côté serveur.

➡️ **Le suivi de prix cross-agence n'est PAS impacté par le repli `raw_text`** :
il ne passe jamais par le flux mobile. Le seul vrai problème ici = la validation
photo des allégations.

### Options pour garder les photos
La WebView (B3) a déjà chargé la page : lire les `<img>` de la galerie y est quasi
gratuit. La même extraction rend `{texte, urls_images}`.

- **Option 1 — Extraire les URLs d'images sur l'appareil, OpenAI les fetche**
  *(le moins coûteux)* : envoyer `{raw_text, image_urls}`. **Petit changement de
  contrat** : `/analyze` accepte `image_urls` optionnel et le route vers
  `_merge_photo_status` (aujourd'hui « mode URL seulement »). Marche **SI** les
  URLs sont fetchables par OpenAI — plausible car les images LBC vivent sur un
  **CDN séparé** (`img.leboncoin.fr`…), généralement moins protégé que la page.
  RGPD inchangé (URLs en transit, jamais loggées). Détail : galeries en
  *lazy-load* → lire `data-src`/`srcset`, parfois dérouler la galerie.
- **Option 2 — Téléverser les octets depuis l'appareil** *(robuste, plus lourd)* :
  si les URLs sont signées/expirantes/verrouillées par `Referer`, l'appareil
  télécharge les octets (session autorisée) et le backend les passe à OpenAI en
  **base64** (`data:image/...`, pas de fetch distant). Implique : `/analyze`
  accepte des images inline, **downscale + cap à 15 (`MAX_IMAGES`) sur
  l'appareil**. ⚠️ **Glissement RGPD** : les octets transitent par le serveur
  (toujours « transit sans stockage », mais la garantie passe de « URLs
  seulement » à « le client téléverse, le serveur relaie ») → à acter dans la
  politique de confidentialité.
- **Option 3 — Screenshot/OCR** : bon pour le **texte**, **faible pour les
  photos** (ne capture pas la galerie). Ne pas compter dessus pour l'ID de
  monuments.

### Test qui débloque la décision
Prendre 4–5 annonces LBC réelles, récupérer les `src` de leurs photos, vérifier si
OpenAI (ou un `curl` sans cookie/referer) arrive à les télécharger. **Oui →
option 1 suffit** (coût faible). **Non → prévoir l'upload d'octets (option 2)**
dès le départ.

---

## 6. Chantier notifications push : re-list / baisse de prix

Scène de référence : un user voit un bien sur **LeBonCoin**, analyse depuis là ;
2 semaines plus tard le bien réapparaît **10 000 € moins cher chez Herbeth**, avec
une description réécrite. Pour notifier, il faut (a) persister l'historique
d'analyse de ce user pour ce bien, (b) identifier le bien pour le matcher malgré
une description différente → **sur base des photos**.

La scène contient **deux problèmes distincts** ; résoudre l'identité photo ne
suffit pas.

### Problème 1 — l'identité du bien *(soluble proprement)*
On ne stocke pas les photos, on stocke leur **empreinte perceptuelle**.
- **Perceptual hashing (pHash/dHash)** : chaque photo → empreinte 64 bits,
  robuste recompression/resize/petit recadrage. Calcul **sur l'appareil**, on ne
  persiste que le **jeu d'empreintes** (non réversible, non re-publiable →
  compatible anti-pattern §1 et RGPD : un pHash n'est pas du contenu).
- **Matching** : distance de Hamming (seuil ~≤10/64 par paire) + **corroboration**
  (≥2 photos, OU 1 photo + signaux structurés : surface ±5 %, pièces, secteur,
  delta de prix plausible).
- **Biais vers la précision, pas le rappel** : une fausse notif « réapparu moins
  cher ! » détruit la confiance. Mieux vaut rater un re-list qu'en inventer un.
  pHash matche quand l'agence **réutilise les photos** (fréquent) ; rate un
  **nouveau shooting** (accepté). C'est l'incrément 2 (clustering photo) tiré côté
  utilisateur.

### Problème 2 — la surface d'observation *(le vrai mur)*
Pour notifier, **l'annonce ré-apparue doit entrer dans le champ de vision**. Or
**Herbeth** (robots.txt interdit) et **LeBonCoin** ne sont pas collectés →
l'annonce « moins chère chez Herbeth » n'existe nulle part dans le système tant que
personne ne l'y amène. Le meilleur matching photo ne sert à rien sans rien contre
quoi matcher. Trois réponses, par ordre de faisabilité :

- **A — Re-check de la *même* annonce** *(facile, gros de la valeur)* : surveiller
  l'URL d'origine. Si source collectée → côté serveur (`ListingPriceSnapshot` fait
  déjà le delta) ; si LBC/Herbeth → **re-check on-device** (le téléphone ré-ouvre
  l'URL en WebView en tâche de fond, compare le prix). **Pas besoin de photo** :
  même bien, même URL. → **80 % de la valeur de rétention, atteignable.**
- **B — Réapparition sur une source *collectée*** *(moyen)* : matching pHash côté
  serveur. Couvre bienici/agences scrapées, **pas** Herbeth/LBC.
- **C — Radar crowdsourcé** *(la vraie réponse à la scène, mais ∝ échelle)* :
  chaque analyse de n'importe quel user verse ses empreintes (fingerprints only)
  dans un **index partagé** ; quand user B analyse l'annonce Herbeth, on matche
  contre le bien suivi par user A → notif A. Élégant, propre, mais sa puissance
  croît avec le nombre d'utilisateurs. À petite échelle, déclenche rarement.

➡️ **La scène exacte (LBC → Herbeth, deux sources interdites, un seul user) tombe
dans le trou** : ni A ni B collectables, et sans volume C ne déclenche pas. À
assumer : **la réapparition cross-source sur sources interdites n'est pas garantie
à l'échelle MVP.** Périmètre *fiable* = A (toujours) + B (sources collectées).

### Le coût caché : cette feature met fin à trois invariants
1. **Zéro auth / zéro PII → fini** : un **token push (APNs/FCM)** persistant par
   appareil devient nécessaire.
2. **« On ne stocke pas les photos » → « on stocke des empreintes »** (mitigé :
   pHash ≠ image, mais nouveau type de donnée persistée).
3. **Analyse stateless → fini** : il faut **persister les analyses** liées à un
   appareil (table « biens suivis » = {token, jeu d'empreintes, features
   structurées, prix de référence, url d'origine}).

C'est le seul chantier qui transforme Cohérence d'un **outil anonyme et sans
état** en un **produit à utilisateurs identifiés et avec état**. Défendable, mais
c'est un cap — décision produit, pas qu'un chiffrage.

### Recommandation chantier 4
- **Livrer A** (re-check même annonce, incl. on-device pour LBC/Herbeth) : haute
  valeur, atteignable, sans photo ni identité complexe.
- **Construire la couche d'empreintes pHash** (fingerprints, pas d'images) : utile
  aussi pour l'incrément 2.
- **Câbler B** (matching sur sources collectées) une fois pHash en place.
- **Présenter C (radar crowdsourcé) comme la cible**, honnête sur sa dépendance à
  l'échelle — pas une garantie jour 1.

---

## 7. Synthèse des décisions à remonter (GATE)

1. **Méthode de portage** : Expo/RN (recommandé) vs wrapper rapide vs PWA d'abord
   pour tester l'appétit mobile. → arbitrage fondateur.
2. **Périmètre fonctionnel jour 1** : trio partage natif + scan/OCR + géoloc
   (Tier 1) ; push (chantier 4) en phase 2.
3. **Cascade texte** : valider A→B3→C ; confirmer l'acceptabilité UX de la WebView
   (chargement + captcha éventuel).
4. **Cascade photo** : lancer le **test de fetch des URLs d'images LBC par OpenAI**
   → décide option 1 (URLs) vs option 2 (octets). Acter le glissement RGPD si
   option 2.
5. **Chantier 4 — cap d'architecture** : accepter ou non la fin des invariants
   (auth/PII, stockage d'empreintes, persistance d'analyses). Si oui, livrer A
   d'abord, pHash ensuite, B puis C.

> Aucune de ces options n'enfreint l'anti-pattern §1 tant qu'on reste sur : une
> annonce, sur l'appareil de l'utilisateur, à sa demande, non redistribuée ; et
> qu'on stocke des **empreintes**, pas du contenu.

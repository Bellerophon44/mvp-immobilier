# cross-agence — ANALYSE (GATE 1)

> Rôle : ANALYSTE. Chantier « cross-agence » : identification d'un même bien à
> travers plusieurs annonces/agences (photos comme empreinte) + historique de
> prix. Ce document cadre, challenge et chiffre ; il ne tranche aucun arbitrage
> structurant (remontés en fin de document). Lecture du code au 2026-06-10.
> Environnement d'analyse SANS egress réseau : tout ce qui exige une requête
> vers bienici/agences est marqué [A VERIFIER] avec son protocole de
> vérification (§4.4).

---

## 1. Objectif et périmètre

### 1.1 Reformulation
Un même bien physique est souvent publié via plusieurs annonces (mandats
simples : plusieurs agences ; republications : même agence, nouvelle annonce).
Objectif produit, en deux valeurs distinctes :
1. **Historique d'un bien en vente** : depuis quand il est sur le marché,
   évolution du prix, republications.
2. **Signal acheteur dans `/analyze`** : « ce bien semble aussi publié chez X
   (depuis N semaines, prix -Y %) » — levier de transparence/négociation.

Moyen technique pressenti (à challenger, §5-§6) : hash perceptuel des photos
au moment de la collecte, matching par distance de Hamming avec vote
multi-photos + corroboration d'attributs, tables `listings` /
`listing_snapshots` / `photo_hashes`, clusters = « biens ».

### 1.2 In / Out proposés
- **In** : persistance d'un historique par annonce (au minimum
  first_seen/last_seen/prix horodatés), éventuel pipeline pHash, matching,
  exposition d'un signal non-scoré.
- **Out** : estimation de prix (anti-pattern #1) ; redistribution du contenu
  d'une annonce tierce (texte, photos, URL re-publiée comme une annonce —
  anti-pattern #3) ; embeddings/CLIP (écartés a priori, sur-dimensionnés) ;
  toute pesée du signal dans le score 40/30/30 (cohérent avec `local_context`
  et `photo_status`, non-scorés).

### 1.3 Challenge du requirement lui-même
Trois constats durs issus du code :

1. **Le code actuel DÉTRUIT l'historique qu'on cherche à construire.**
   `ingestion/save.py:98` pose `collected_at=datetime.utcnow()` puis
   `db.merge(comparable)` (`save.py:102`) : à chaque run hebdo, une annonce
   déjà connue voit son prix ET sa date écrasés. Impossible de savoir « depuis
   quand » ni « combien avant ». Et une annonce disparue n'est jamais marquée
   (aucune purge/flag : les lignes périmées restent des comparables).
   **Corriger cela (first_seen préservé + snapshot de prix au changement) est
   trivial, sans image, sans dépendance, et livre déjà la valeur n°1** pour le
   tracking par id stable (`generate_stable_id`, `scrapers/base.py`).

2. **La « doctrine agrégats seulement » est déjà, de fait, du stockage
   par-annonce.** La table `comparables` (`db/models.py:8-51`) stocke ~17,7k
   lignes individuelles : prix, surface, ville, quartier, DPE, étage, charges…
   par annonce, par source. L'anti-pattern #3 (CONTEXT §11) dit « ne pas
   redistribuer » et « stocker uniquement les agrégats » — la pratique réelle
   est : *stockage interne par-annonce, exposition agrégée*. Le chantier ne
   crée donc pas la rupture qu'on croit ; il ajoute (a) la dimension
   **temporelle** (snapshots), (b) des **hashes de photos**, (c) une
   **exposition par-annonce** dans `/analyze` (le vrai point neuf, §7).
   À re-confirmer explicitement en GATE 1 (Question 1) — c'est demandé, et
   c'est sain : la doctrine écrite et la doctrine pratiquée divergent déjà.

3. **« Cross-agence » au sein de NOS 5 sources a une valeur incertaine ;
   « cross-annonces » au sein de bienici est probablement le vrai gisement.**
   Bienici est un portail agrégateur : un bien en mandat simple y apparaît
   plusieurs fois (une annonce par agence, ids différents). Le matching photo
   paie donc d'abord **intra-bienici** (17,4k annonces, photos en JSON
   [A VERIFIER]), et pour le bien analysé par l'utilisateur (URL arbitraire)
   **contre** ce corpus. Le recouvrement entre nos 4 petites agences HTML
   (~350 annonces, zones partiellement disjointes : benedic = Moselle large,
   immoheytienne = maisons, laveine = communes limitrophes) est invérifiable
   sans mesure et probablement faible (§9.1 propose une mesure à coût nul).

---

## 2. Cartographie d'impact (fichier:ligne)

### 2.1 Collecte / scrapers
- `scrapers/models.py:5-29` — `PropertyListing` : **aucun champ photo**
  (confirmé ; le seul hit grep « photo » des scrapers est un commentaire,
  `scrapers/sources/benedic.py:64` : le premier nombre des cartes est « le
  compteur de photos », preuve indirecte que les cartes benedic portent des
  vignettes). Ajouter un champ `photo_hashes: list[str]` (ou `photo_urls`
  transitoire) = micro-migration du dataclass, sans impact DB comparables.
- `scrapers/sources/bienici.py:190-241` — `_parse_listing` ne lit ni photos ni
  nom d'agence. L'API renvoie-t-elle `photos[]` et un identifiant
  d'agence/annonceur ? [A VERIFIER §4.4] — le harnais existe déjà :
  `scrapers/diag_bienici.py:235-293` (`field_audit_md` liste TOUS les champs
  avec taux de remplissage ; un run de `diag-bienici.yml` répond à la
  question sans écrire une ligne de code).
- 4 sources HTML (`benedic.py`, `idemmo.py`, `immoheytienne.py`,
  `site_local.py`) : parsing de **cartes de listing**, jamais de page détail.
  Vignettes probables dans les cartes mais résolution/recadrage inconnus
  [A VERIFIER] ; sinon, fetch des pages détail = ~350 GET supplémentaires
  (politesse `polite_sleep` ~1,5 s : `scrapers/base.py:32,40-43` → ~9-12 min).

### 2.2 Pipeline d'ingestion
- `jobs/push_comparables.py:60-97` — runner GitHub → POST batches 1000 vers
  `/admin/comparables`. `collect.yml:12` : **timeout 15 minutes** — tout
  téléchargement d'images de masse est incompatible avec CE job ; il faut un
  job dédié (§8).
- `ingestion/save.py:98-102` — le merge écrase prix + `collected_at` (perte
  d'historique, cf. §1.3). Point d'insertion naturel des snapshots.
- `app/main.py:217-241` — `POST /admin/comparables` (X-Admin-Token, max
  10000). Un endpoint frère (`/admin/photo-hashes` ou extension du payload)
  suivrait le même pattern.

### 2.3 DB
- `db/models.py` : 3 tables (`comparables`, `feedback`, `events`).
- `db/session.py:35-61` : pattern micro-migration idempotente
  (`PRAGMA table_info` + `ALTER TABLE ADD COLUMN`) — réutilisable pour
  ajouter `first_seen_at`/`last_seen_at` à `comparables` ; les tables
  nouvelles (`listing_snapshots`, `photo_hashes`) passent par
  `Base.metadata.create_all` (déjà appelé, `session.py:59`).
- Volume Fly 1 Go : la base actuelle pèse de l'ordre de 10 Mo
  (17,7k lignes × ~300 o + index). Volumétrie nouvelle chiffrée en §6.3 :
  négligeable en mode delta, dangereuse en snapshot hebdo intégral.

### 2.4 `/analyze`
- `app/main.py:323-377` — handler ; rate-limit 10 req/min/IP
  (`main.py:326`, 9.9). En mode URL, les images sont DÉJÀ extraites
  (`main.py:364`, `extract_image_urls`) et passées à `run_full_analysis`
  (`app/analysis.py:153-156`) pour le screening photo (transient,
  `app/photo_evidence.py` — qui n'a **pas** de téléchargement : il passe les
  URLs à OpenAI, `photo_evidence.py:99,149-157`). Calculer un pHash du bien
  analysé exigerait au contraire de **télécharger les bytes sur la VM Fly**
  (3-6 images ≈ 1-3 s de latence, cap de taille + réutilisation du filtre
  `_is_safe_url` de `url_fetch.py:29-47` obligatoires).
- `AnalyzeResponse` (`main.py:79-87`) : ajouter un bloc optionnel (type
  `listing_history`) est rétro-compatible côté Pydantic, mais impose la MAJ
  de `frontend/lib/api.ts` (anti-pattern #9). Le précédent `local_context`
  (bloc non-scoré, `analysis.py:244`) est le gabarit à suivre.
- `EventIn` (`main.py:106-116`) : enum fermée — tracer l'exposition du signal
  (ex. `cross_listing_shown`) = ajout d'un littéral, anodin.
- `scoring.py` ne lit que les piliers prix/sémantique : un bloc non-scoré ne
  touche pas le 40/30/30 (même garantie que pour photo-evidence).

### 2.5 CI / staging
- `collect.yml` (hebdo lundi 04:00, timeout 15 min), `diagnose-scrapers.yml`
  (rapport en PR), `diag-bienici.yml`, `test.yml`, `deploy-backend.yml`
  (prod + staging). Staging `coherence-staging` : base et volume dédiés,
  amorçables d'un snapshot prod (`docs/specs/ENVIRONNEMENTS-ET-DOMAINE.md`
  §2) — terrain d'essai idéal pour la première collecte avec hashes et la
  mesure de précision du matching avant toute exposition utilisateur.

### 2.6 Dépendances Python
- `requirements.txt:1-7` : `numpy` déjà présent, **Pillow absent,
  imagehash absent**.
- `imagehash` tire `Pillow` + `PyWavelets` + `scipy` (pour pHash DCT) :
  +~70-100 Mo installés dans l'image `python:3.12-slim` (wheels manylinux
  disponibles, pas de paquet apt requis). Alternative : `Pillow` seul
  (+~12 Mo) avec un dHash/aHash maison (~20 lignes, Pillow + numpy déjà là).
  Arbitrage en Question 6. Impact : image Docker Fly, install CI
  (`collect.yml`, `test.yml`), et — si on choisit le calcul côté backend —
  uniquement là où on hash réellement (on peut isoler la dep dans le job CI
  et ne PAS l'embarquer dans l'image Fly si le backend ne hash jamais).

---

## 3. Dépendances et ordre

1. **Prérequis #0 (vérification, 0 code)** : confirmer que l'API bienici
   expose photos (+ nom d'agence pour « publié chez X ») via
   `diag-bienici.yml` ; confirmer la nature des vignettes des cartes agences
   via `diagnose-scrapers.yml --recon`. **Point de faisabilité dur** : sans
   photos bienici en JSON, le pivot du matching s'effondre (il faudrait
   fetcher 17,4k pages HTML bienici — bloquées anti-bot, CONTEXT §4.3 →
   infaisable).
2. **Incrément 1 — historique mono-source par id stable** (aucune image) :
   `first_seen_at`/`last_seen_at` + snapshots de prix au changement dans
   `ingestion/save.py`. Ne dépend de rien. Débloque « depuis quand / -Y % ».
3. **Incrément 2 — hashes photo + clustering** : dépend de #0, des nouvelles
   tables, du job de collecte d'images dédié, et de l'incrément 1 (le cluster
   agrège des historiques ; sans #2.1 il n'y a rien à agréger).
4. **Incrément 3 — exposition `/analyze`** : dépend de #2 (corpus de hashes)
   + hash transient du bien analysé (download d'images sur la VM) + MAJ
   `frontend/lib/api.ts`. C'est le seul incrément qui touche le chemin
   critique.
5. Pas de prérequis d'auth ni d'email. Pas de nouveau vendor. Prérequis
   egress : les runners GitHub sortent librement ; la VM Fly devra atteindre
   les CDN d'images des agences si l'incrément 3 est retenu (même nature que
   la dépendance BAN, `backend/CLAUDE.md` §11bis).

Découplage (point challengé n°5) : **oui, vérifié faisable**. Tables neuves,
job CI neuf, endpoint admin neuf → zéro contact avec `/analyze` ni avec
`collect.yml` jusqu'à l'incrément 3. Seul l'incrément 1 touche
`ingestion/save.py` (chemin de collecte, pas d'analyse) — modification locale
de quelques lignes, testable, et qui répare au passage un défaut existant
(écrasement d'historique).

---

## 4. Faisabilité « images à la collecte » — le point dur

### 4.1 bienici (pivot pressenti)
- L'API JSON (`realEstateAds.json`) renvoie très vraisemblablement un tableau
  de photos par annonce (les portails l'exposent pour leurs frontaux), mais
  **rien dans le repo ne le prouve** : `_parse_listing` n'en lit aucun, et
  aucun rapport d'audit committé ne liste un champ photo. [A VERIFIER]
- Même réserve pour le **nom d'agence** par annonce — indispensable au
  wording « publié chez X ». [A VERIFIER]
- Si confirmé : 0 fetch HTML, on a les URLs CDN directement dans le JSON déjà
  téléchargé. Le surcoût est alors uniquement le download des images.

### 4.2 Agences HTML (4 sources)
- Les cartes portent des vignettes (indice : compteur de photos benedic,
  `benedic.py:64`) mais une vignette est souvent **recadrée au ratio de la
  carte** et lazy-loadée (`data-src`) : un pHash de vignette recadrée matche
  mal le même cliché non recadré publié ailleurs. Pour des hashes fiables il
  faut probablement la **page détail** : +1 GET par annonce, ~350 GET × ~2 s
  (politesse) ≈ 10-12 min — acceptable dans un job dédié, pas dans
  `collect.yml` (timeout 15 min déjà consommé par la collecte).
- `extract_image_urls` (`app/url_fetch.py:135-182`) est directement
  réutilisable sur ces pages détail (og:image, JSON-LD, img/data-src).

### 4.3 Résolution minimale
Un pHash/dHash se calcule sur une réduction 32×32 ou 9×8 : une vignette
300-600 px suffit **en valeur absolue**. Le risque n'est pas la résolution
mais le **recadrage** (vignette vs original) et le **watermark** (§5).

### 4.4 Protocole de vérification (env sans réseau — à exécuter avant GATE 2)
1. Étendre `diag_bienici.field_audit_md` (ou simplement lire son rapport
   existant : il liste déjà tous les champs) via le workflow
   `diag-bienici.yml` → noter les clés contenant photo/image/agency/contact
   et leur taux de remplissage.
2. PR touchant `backend/scrapers/**` avec `scrapers/diagnose.py --recon` sur
   une carte et une page détail de chaque agence → le commentaire de PR
   (`diagnose-scrapers.yml`) révèle les balises img, leurs dimensions
   d'URL CDN, le lazy-load.
3. Sur un échantillon de ~20 annonces : télécharger les photos, hasher,
   mesurer les distances intra-bien (même photo, deux sources) et inter-biens
   (photos d'appartements différents du même immeuble) → calibrer les seuils
   (§5) sur données réelles, pas sur des constantes de littérature.

---

## 5. Robustesse pHash et politique de décision (point challengé n°2)

### 5.1 Ce qui résiste / ce qui casse
| Transformation | pHash (DCT) | dHash maison |
|---|---|---|
| Recompression JPEG, redimensionnement | robuste | robuste |
| Retouche lumière/contraste modérée | robuste | moyen |
| Watermark d'angle discret | souvent robuste | souvent robuste |
| Bandeau/watermark central, gros logo | dégradé | dégradé |
| **Recadrage** (vignette, ratio carte) | **casse** | **casse** |
| Rotation 90° (verticale vs horizontale) | casse (hash des 2 orientations possible) | casse |
| Miroir (parfois appliqué par les agences) | casse (hashable en double) | casse |

Parade peu coûteuse : stocker 2-4 variantes de hash par photo (original +
miroir, éventuellement ±90°) — multiplie le stockage par 2-4 mais reste
négligeable (§6.3).

### 5.2 Le faux positif réaliste : même immeuble, biens différents
Deux appartements du même immeuble partagent hall, façade, cage d'escalier,
vue. Un vote k=1 photo est donc interdit. Politique **conservatrice**
proposée (positionnement « pas de fausse précision » ; un faux « même bien »
est pire qu'un raté) :
- match photo = distance de Hamming ≤ 6/64 (à calibrer en staging, §4.4.3) ;
- vote : **≥ 2 photos distinctes** appariées (k-sur-n) ;
- corroboration d'attributs obligatoire : même `property_type`, même
  `city` canonique (idéalement même `postal_code`), surface à **±10 %**
  (les agences arrondissent différemment ; ±5 % serait trop strict avec du
  Carrez vs utile) ;
- prix : AUCUNE contrainte (l'écart de prix est précisément le signal) ;
- wording toujours hedgé : « **semble** aussi publié chez X », jamais « est
  le même bien » ;
- les clusters n'entrent **jamais** dans `market_stats` (pas de
  dédoublonnage automatique des comparables en incrément 1-3 : un faux
  cluster y fausserait les médianes — dette explicitement hors périmètre) ;
- verrouiller par tests : un test « jamais de match avec k=1 », un test
  « jamais de match sans corroboration attributs » (leçon : un garde-fou sans
  test est oublié, `.claude/lessons.md`).

---

## 6. Volumétrie et budgets chiffrés (point challengé n°4)

### 6.1 Téléchargement d'images — options
Hypothèses : ~120 Ko/photo (CDN redimensionné), ~5 img/s soutenus avec
parallélisme poli sur CDN, runner GitHub (egress gratuit, repo privé =
quota 2000 min/mois d'Actions).

| Option | Volume/run | Durée | Verdict |
|---|---|---|---|
| A. bienici intégral, 10 photos × 17,4k | ~174k img, ~20 Go | ~10 h | Infaisable (impoli, hors quota, hors timeout) |
| B. bienici **3 premières photos, nouvelles annonces seulement** (delta vs hashes connus) | bootstrap ~52k img (~6 Go, ~3 h, one-shot) puis ~3-6k img/sem (5-8 % de churn) | ~10-20 min/sem | Faisable en job dédié |
| C. **Agences locales seules** (~350 annonces, pages détail + ~3-5 photos) | ~350 GET + ~1,2-1,8k img (~200 Mo) | ~15-25 min/sem | Faisable, mais sans pivot bienici la proba de match est faible |
| D. C + B (agences en continu, bienici en pivot delta) | cumul B+C | ~30-45 min/sem après bootstrap | Cible raisonnable de l'incrément 2 |

Budget Actions : bootstrap 180 min one-shot + ~120-180 min/mois en rythme —
dans le quota gratuit, à surveiller.

### 6.2 Où calculer les hashes — CI vs Fly
| Critère | Runner CI (reco) | VM Fly |
|---|---|---|
| Egress images | Gratuit, illimité de fait | Payant (~0,02 $/Go, négligeable) mais VM occupée des heures |
| CPU | 2 vCPU dédiés au job | shared-cpu, concurrence avec `/analyze` |
| Auto-stop (sécurité financière §3.3) | Sans impact | Contredit l'auto-stop (machine réveillée longtemps) |
| Dépendances | Pillow/imagehash seulement dans le job CI possible | Alourdit l'image Docker prod |
| Transport | POST hashes (quelques Mo) vers endpoint admin | — |

Reco : **calcul en CI**, le backend ne reçoit que des hashes (pattern
`push_comparables` à l'identique). Exception : l'incrément 3 exige un hash
transient côté Fly pour le bien analysé (3-6 images, ~1-3 s, borné).

### 6.3 Stockage SQLite (volume 1 Go)
| Table | Mode | Volumétrie |
|---|---|---|
| `listings` (annonce par source : id, source, agence, city, type, surface, first_seen, last_seen) | — | 17,7k lignes ≈ 5 Mo ; ×2-3 avec churn annuel ≈ 15 Mo |
| `listing_snapshots` | **delta** (1 ligne au 1er passage + 1 par changement de prix, ~2-5 %/sem) | ~20-50k lignes/an ≈ 5-10 Mo/an |
| `listing_snapshots` | hebdo intégral | ~920k lignes/an ≈ 100-150 Mo/an — à proscrire |
| `photo_hashes` (listing_id, position, hash 16 hex, variantes ×2-4) | — | 52k photos × 2 variantes ≈ 100k lignes ≈ 10 Mo |

Total mode delta ≈ 30-40 Mo la première année : confortable sur 1 Go.
Prévoir une **purge** (lignes dont `last_seen_at` > 12 mois) — politique de
rétention à acter (Question 1).

### 6.4 Granularité hebdo
Collecte lundi 04:00 → historique au pas de la semaine. Pour de
l'immobilier (les baisses de prix se comptent en semaines/mois), c'est
suffisant pour le MVP ; « depuis N semaines » est même le bon grain de
wording. Signalé comme choix produit : passer à un pas quotidien
multiplierait le budget §6.1 par 7 pour un gain marginal. Reco : rester
hebdo.

---

## 7. Droit / RGPD (point challengé n°3)

- **Hash perceptuel ≠ photo** : non reconstructible, ce n'est pas une
  reproduction de l'œuvre. Stocker un hash est de même nature qu'une
  empreinte ; défendable.
- **Prix horodaté = fait** : un fait n'est pas protégé par le droit
  d'auteur. Le risque juridique pertinent est le **droit sui generis des
  bases de données** (extraction substantielle du portail). Or l'extraction
  par-annonce existe déjà (table `comparables`, hebdo, 17,4k lignes
  bienici) : conserver l'historique de ce qu'on extrait déjà n'ajoute pas
  d'extraction nouvelle — risque incrémental faible. Le download d'images
  (incrément 2) EST en revanche une extraction nouvelle (les bytes des
  photos), même si on ne conserve que le hash : transit seulement, jamais de
  stockage d'image, jamais de log d'URL d'image (même posture que
  photo-evidence, `main.py:362-364`).
- **Ce qui serait une redistribution (interdit, anti-pattern #3)** :
  re-publier le tuple complet (texte + photos + prix + lien) d'une annonce
  tierce. Le signal proposé n'expose que des **métadonnées factuelles**
  (nom de la source, ancienneté, écart de prix en %) — pas le contenu de
  l'annonce. Ne pas inclure l'URL de l'annonce tierce dans la réponse au
  MVP (option conservatrice ; un lien est juridiquement défendable mais
  rapproche visuellement de la redistribution — remonté en Question 5).
- **RGPD** : pas de donnée personnelle directe (aucune adresse stockée dans
  les tables proposées ; `comparables` n'en a pas non plus). Risque indirect :
  l'historique de prix d'un bien singulier peut, recoupé avec l'annonce
  publique, pointer un vendeur. Mitigations : pas d'adresse, pas d'URL
  stockée côté cluster exposé, granularité quartier/ville, rétention bornée
  (purge §6.3), exposition hedgée. Le cluster reste un profil d'un **bien**,
  pas d'une personne ; posture défendable si la rétention est définie.
- **ToS portail** : inchangé par rapport à la collecte actuelle pour le JSON ;
  le download d'images ajoute de la charge CDN — cap à 3 photos + delta +
  politesse = profil de trafic d'un petit cache d'images, raisonnable.

---

## 8. Stratégie de rollout (staging-first)

> **Légende statut** : ✅ Livré en prod · 🚧 En cours · ⬜ À faire.

1. **[✅ LIVRÉ EN PROD le 2026-06-11]** Incrément 1 (historique mono-source) :
   mergeable prod directement — il ne change aucune réponse API, n'ajoute aucune
   dep, répare l'écrasement. Parcours staging-first respecté (PR #71 → `staging`,
   PR #72 → `main`). Détail et verrous : `cross-agence-INCREMENT1-SPEC.md`.
2. **[⬜ À faire]** Incrément 2 : **staging d'abord** (`coherence-staging`, base
   dédiée) — le job d'images pousse vers l'URL staging, on mesure précision/rappel
   du matching sur le corpus réel (protocole §4.4.3 industrialisé), on calibre
   les seuils, PUIS on pointe la prod.
3. **[⬜ À faire]** Incrément 3 : derrière la validation staging de la précision ;
   events 9.10 pour mesurer l'exposition ; rate-limit 9.9 inchangé (le hash
   transient s'ajoute au coût d'un appel déjà limité à 10/min/IP).

---

## 9. Valeur incrémentale — challenge fort (point n°6)

### 9.1 Mesurer avant d'investir
Le recouvrement réel entre sources est inconnu. Deux mesures à coût ~nul,
AVANT d'écrire le pipeline image :
- **Probe attributs** (diagnostic, pas du matching produit) : compter les
  paires inter-sources (ville, type, surface ±2 %, prix ±2 %) dans la base
  actuelle — borne basse du multi-mandat visible chez nous. Un script
  `diagnose`-style en CI suffit.
- **Field audit bienici** (§4.4.1) : photos + agence disponibles ? Combien
  d'annonces bienici partagent (surface, quartier) exacts — indice de
  doublons intra-portail.

Si la probe montre < 1 % de recouvrement inter-sources ET que bienici
n'expose pas les photos, l'incrément 2 tel que pressenti perd l'essentiel de
sa valeur → repli sur l'incrément 1 seul + alternative attributs (v0 sans
photos), réévaluation.

### 9.2 Ordre de valeur proposé
1. **Incrément 1 — tracking temporel par id stable** : trivial (l'id stable
   existe, `generate_stable_id`), zéro image, zéro dep, répare un bug de
   facto. Livre « depuis quand + évolution prix + republication » par
   source. C'est, de l'avis de l'analyste, **la vraie Phase 1** — le
   requirement tel que formulé (photos d'abord) est sur-dimensionné comme
   premier pas.
2. **Incrément 2 — clustering photo** (intra-bienici + agences→bienici),
   staging-first, si #0/§9.1 confirment le gisement.
3. **Incrément 3 — signal `/analyze`** : matcher le bien analysé (URL
   utilisateur, n'importe quelle agence fetchable) contre le corpus — c'est
   là que le cross-agence paie pour l'acheteur, y compris pour des agences
   que nous ne scrapons pas.

---

## 10. Synthèse adversariale

- Le besoin est réel et aligné produit (transparence, négociation, pas
  d'estimation). Mais la formulation « photos comme empreinte » présuppose
  l'infrastructure la plus chère du chantier alors que 1) l'historique
  mono-source est quasi gratuit et débloque la moitié de la valeur, 2) la
  faisabilité photos (API bienici, vignettes agences) n'est PAS établie,
  3) le recouvrement inter-sources n'est pas mesuré.
- Le code actuel écrase l'historique chaque lundi (`save.py:98-102`) : toute
  semaine sans l'incrément 1 est de l'historique perdu — argument pour le
  livrer vite, indépendamment du reste.
- La « rupture doctrinale » du stockage par-annonce est en réalité une mise
  en cohérence : la pratique stocke déjà par-annonce ; la vraie ligne rouge
  est l'**exposition** (métadonnées factuelles oui, contenu non) et la
  **rétention** (à acter).
- Le risque produit dominant n'est pas technique : c'est le faux « même
  bien » (deux appartements du même immeuble) qui détruirait le
  positionnement « pas de fausse précision ». Politique conservatrice + tests
  de verrou + validation staging non négociables.

---

## QUESTIONS POUR L'HUMAIN (GATE 1)

1. **Doctrine de stockage par-annonce — re-confirmation explicite.**
   Constat : `comparables` stocke déjà 17,7k annonces individuelles ; le
   chantier ajoute l'historique horodaté + hashes photo, et la doctrine
   écrite (« agrégats seulement », CONTEXT §11.3) doit être amendée ou le
   chantier refusé.
   - Options : (a) confirmer la doctrine réelle « stockage interne
     par-annonce autorisé ; exposition publique limitée aux agrégats et aux
     métadonnées factuelles (source, ancienneté, écart %) ; jamais de
     contenu d'annonce (texte/photos/adresse) re-publiable » + politique de
     rétention (proposition : purge 12 mois après `last_seen_at`) + MAJ du
     texte de CONTEXT §11.3 ; (b) refuser → le chantier entier est
     infaisable (un historique est par nature par-annonce).
   - **Reco : (a)**, avec la MAJ documentaire pour que les agents futurs ne
     re-détectent pas une fausse violation.

2. **Périmètre de l'incrément 1 : tracking temporel mono-source d'abord ?**
   - Options : (a) incrément 1 seul d'abord (first_seen/last_seen + snapshots
     de prix delta dans `ingestion/save.py`, zéro image, zéro dep, mergeable
     prod), photos en incrément 2 conditionné aux vérifications §4.4/§9.1 ;
     (b) tout le chantier photo d'un bloc.
   - **Reco : (a)** — chaque semaine d'attente détruit de l'historique
     (écrasement actuel), et (b) parie sur une faisabilité non vérifiée.

3. **Budget collecte d'images (incrément 2).**
   - Options (§6.1) : A intégral (infaisable, écarté) ; B bienici 3 photos
     delta (bootstrap ~3 h one-shot puis ~10-20 min/sem) ; C agences locales
     seules (~15-25 min/sem, faible proba de match) ; D = B+C (~30-45
     min/sem).
   - **Reco : B d'abord** (le pivot intra-bienici est le gisement probable),
     extension D si les agences locales montrent du recouvrement (§9.1).
     Conditionné à la confirmation photos/agence dans le JSON bienici
     (prérequis #0). Calcul des hashes **en CI**, backend récepteur de
     hashes seulement (§6.2).

4. **Politique de matching conservatrice — validation des seuils.**
   - Proposition : Hamming ≤ 6/64, vote ≥ 2 photos distinctes, corroboration
     même type + même ville (postal) + surface ±10 %, wording « semble »,
     jamais d'impact score, jamais de dédoublonnage des comparables, seuils
     recalibrés sur corpus staging avant prod, tests de verrou (k=1 interdit,
     corroboration obligatoire).
   - Options : (a) valider cette politique comme cadre (les valeurs exactes
     restant calibrables en staging) ; (b) plus strict (k ≥ 3, surface ±5 %)
     au prix d'un rappel très faible.
   - **Reco : (a)** — (b) risque de ne presque jamais matcher (beaucoup
     d'annonces n'ont que 3 photos communes exploitables).

5. **Exposition du signal : où et quand ?**
   - Options : (a) d'abord **aucune exposition publique** — clusters
     consultables via endpoint admin/staging, validation précision, puis
     décision ; (b) bloc non-scoré dans `/analyze` (gabarit `local_context`,
     MAJ `frontend/lib/api.ts`) avec métadonnées seules (source, N semaines,
     -Y %), sans URL tierce ; (c) page dédiée « historique du bien »
     (chantier front entier).
   - **Reco : (a) puis (b)** — (c) est prématuré au trafic actuel. Sous-choix
     dans (b) : inclure ou non le lien vers l'annonce tierce — reco : non au
     MVP (prudence redistribution, §7).

6. **Dépendance image : Pillow seul ou imagehash ?**
   - Options : (a) `Pillow` seul (+~12 Mo) + dHash/aHash maison (~20 lignes,
     numpy déjà présent), variantes miroir/rotation stockées ; (b)
     `imagehash` (pHash DCT, plus robuste aux retouches) au prix de scipy +
     PyWavelets (+~70-100 Mo, 3 deps nouvelles).
   - **Reco : (a) en première intention** (culture minimaliste du projet,
     dep isolable dans le job CI), bascule (b) si la précision mesurée en
     staging (§4.4.3) est insuffisante — le format de stockage (64 bits hex)
     est identique, la migration est un re-hash du corpus (~3 h CI).

7. **Granularité et rétention.**
   - Options granularité : (a) hebdo (collecte actuelle, « depuis N
     semaines ») ; (b) quotidien (×7 sur tous les budgets).
   - Options rétention : purge des listings/snapshots/hashes à (a) 12 mois
     après `last_seen_at` ; (b) 24 mois ; (c) jamais (déconseillé : volume +
     posture juridique).
   - **Reco : hebdo + purge 12 mois.**

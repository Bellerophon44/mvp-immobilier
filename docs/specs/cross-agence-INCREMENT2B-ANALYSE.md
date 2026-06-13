# cross-agence — INCRÉMENT 2b (re-link par PHOTO, agence DIFFÉRENTE) — ANALYSE (GATE 1)

> Rôle : ANALYSTE (Phase 1, lecture seule). Cadre, challenge et chiffre l'incrément
> 2b CONTRE LE CODE RÉEL ; ne tranche aucun arbitrage structurant (remontés en fin
> de document, GATE 1). Lecture du code au 2026-06-13.
> Environnement d'analyse SANS egress réseau : toute mesure exigeant une requête
> vers bienici / un CDN d'images est marquée [À VÉRIFIER] avec son protocole.
> Réfs lues : `.claude/lessons.md`, `CONTEXT.md` §0/§3/§11, `backend/CLAUDE.md`
> §1/§2/§4/§5/§7/§9/§12, `docs/specs/cross-agence-ANALYSE.md`,
> `docs/specs/cross-agence-PREREQ0-RESULTATS.md`,
> `docs/specs/cross-agence-INCREMENT1-SPEC.md`,
> `docs/specs/cross-agence-INCREMENT2A-ANALYSE.md`,
> `docs/specs/cross-agence-INCREMENT2A-SPEC.md`. Code ancré : `scrapers/sources/*`,
> `scrapers/models.py`, `scrapers/diag_bienici.py`, `ingestion/save.py`,
> `db/models.py`, `db/session.py`, `app/main.py`, `requirements.txt`.

---

## 0. Objectif et périmètre

### 0.1 Reformulation
2a (livré, en prod) re-lie les annonces successives d'un même bien re-publié par
la **même** agence : il s'appuie sur des identifiants techniques communs
(`reference` de mandat + `customer_id` bienici + attributs), capturés à la collecte,
et pose un `lineage_id` à l'ingestion (`ingestion/save.py:49-102`,
`_find_lineage_candidate`). Sa garantie : jamais de faux lien (abstention au moindre
doute).

2b vise le cas que 2a ne sait **pas** traiter : un bien re-publié par une agence
**différente**. Source différente, nouvelle `reference`, `customer_id`
différent/absent, texte réécrit ⇒ **aucun identifiant technique commun**. La seule
corroboration forte restante est la **photo** : les mêmes clichés sur deux annonces
de sources différentes ⇒ très probablement le même bien physique. 2b doit étendre le
mécanisme de `lineage_id` à un rattachement **cross-source** par similarité d'image
(hash perceptuel / pHash), corroboré par attributs (surface, type, ville, géo), en
restant fidèle à la doctrine conservatrice « jamais de faux lien ».

### 0.2 In (périmètre candidat, à confirmer GATE 1)
- **Capture des photos** à la collecte : URLs photo dans `PropertyListing`
  (`scrapers/models.py`) côté bienici (champ JSON `photos`, déjà identifié par la
  probe PREREQ0) et, si retenu, côté agences HTML.
- **Calcul d'un pHash** par photo (où ? CI vs ingestion vs job dédié — §2) et son
  **stockage** (nouvelle colonne ou nouvelle table).
- **Logique de rattachement cross-source** par distance de Hamming + vote
  multi-photos + corroboration d'attributs, posant/fusionnant des `lineage_id`.
- **Réutilisation ou extension** de `lineage_id` / `/history` / rétention (§6).

### 0.3 Out (hors 2b, à confirmer)
- **Aucune exposition publique** : `/analyze`, `AnalyzeResponse`,
  `frontend/lib/api.ts`, `market_stats.py`, `scoring.py` non touchés (même garantie
  que inc.1 et 2a). 2b reste **admin-only** comme 2a.
- **Aucune estimation de prix**, aucun DVF/notaires (anti-patterns CONTEXT §11).
- **Pas de redistribution de contenu** : ni image, ni URL d'image, ni adresse
  re-publiées (le hash n'est pas la photo — voir §3).
- Le matching photo du **bien analysé par l'utilisateur** contre le corpus (hash
  transient côté Fly à `/analyze`) relève de l'« incrément 3 / exposition »
  (`cross-agence-ANALYSE.md` §3 pt 4) — **hors 2b**.

### 0.4 Challenge du requirement lui-même (posture adversariale)
Quatre constats durs, à confronter à GATE 1.

1. **Le gisement RÉEL de 2b est le plus étroit des trois incréments, et il n'est
   toujours pas mesuré.** PREREQ0 §2 et §2bis sont explicites : la redondance
   inter-sources observée est en grande partie de la **syndication** (bienici
   ré-affiche les mandats de nos propres agences — `cabinet-benedic-montigny` est un
   `customerId` bienici = notre scraper benedic), **pas** du vrai multi-mandat entre
   agences indépendantes. Les 519 paires « strictes » sont « en grande partie la
   même annonce des deux côtés » (PREREQ0 §2). Le vrai cas 2b — « delisté chez A,
   relisté plus tard chez B **différente** » — est par nature **temporel** et **n'a
   jamais été mesuré** (snapshot unique, PREREQ0 §0/§3.4). On ne sait pas s'il
   représente 5 %, 1 % ou 0,1 % du parc. **Construire le pipeline image le plus
   coûteux du chantier pour un phénomène non quantifié est le risque n°1.**

2. **2b est, de loin, le plus cher en infra ET le seul à exiger des dépendances
   Python nouvelles** (Pillow ± imagehash). Tous les incréments précédents (1, 2a)
   ont tenu l'anti-pattern « zéro dépendance nouvelle, zéro download de masse ». 2b
   le rompt frontalement. C'est une **tension majeure** à arbitrer (§4, Q1).

3. **2b n'apporte AUCUNE valeur utilisateur visible tant que l'exposition n'est pas
   faite.** Comme 2a, il enrichit un historique admin-only. Or l'exposition
   (incrément 3) n'est pas décidée. 2b prépare un terrain dont on ne sait pas s'il
   sera exploité — à assumer explicitement.

4. **2a couvre peut-être déjà l'essentiel du gisement captable.** Si la syndication
   bienici fait que la plupart des re-lists « cross-source » sont en réalité le même
   mandat ré-affiché (même `reference`, capté par 2a côté bienici), alors le delta
   de valeur de 2b sur 2a est faible. **À mesurer avant d'investir** (probe §1.4 de
   l'ANALYSE 2a, jamais faite).

→ **Recommandation analyste forte** : 2b ne doit PAS être lancé d'un bloc. Il faut
d'abord **mesurer le gisement temporel cross-source réel** (probe sur l'historique
inc.1/2a qui mûrit) ET **découpler la capture photo (cheap, réversible) de la
logique de matching (chère, risquée)** — voir §1 et §6 de la SPEC 2a comme modèle de
césure. Détail en QUESTIONS GATE 1.

---

## 1. Disponibilité des photos à la collecte (cartographie source par source)

### 1.1 État réel : AUCUNE source ne capture de photo aujourd'hui
Vérifié exhaustivement :
- `scrapers/models.py:5-35` — `PropertyListing` ne porte **aucun** champ photo
  (champs : id, source, city, type, surface, prix, district, postal, dpe, année,
  aménités, `reference`, `customer_id`). `grep -i photo|image|img` sur
  `scrapers/` ne renvoie que des **commentaires** et l'outil de diagnostic, jamais
  un champ de données produit.
- `scrapers/sources/bienici.py:199-252` — `_parse_listing` ne lit ni `photos` ni
  vignette. L'`id` brut est `ad["id"]` (`:237`).
- `scrapers/sources/benedic.py:71-110` — parse une **carte** (`[data-card-maker]`) ;
  un commentaire (`:80`) note même que « le premier nombre est le **compteur de
  photos** » ⇒ les cartes portent des vignettes, mais aucune URL n'est extraite.
- `scrapers/sources/idemmo.py:56-94`, `immoheytienne.py:61-90`, `site_local.py`
  (laveine) — idem : parsing de cartes de listing, aucune photo extraite.

⇒ **Effort de capture : non nul, à créer dans chaque source visée**, mais déjà
gabarité par les helpers nullable existants (`_extract_postal`, `_extract_amenities`
côté bienici ; sélecteurs CSS côté HTML).

### 1.2 bienici — photos confirmées dans le JSON (mesuré, PREREQ0)
**C'est le point fort de la faisabilité.** La probe PREREQ0 §1 (run réel sur 200
annonces via `diag_bienici.field_audit_md`, instrumentée
`scrapers/diag_bienici.py:271-315`) a mesuré :

| Champ JSON | Remplissage | Nature |
|---|---|---|
| `photos` | **191/200 (95,5 %)**, liste de **3** | URLs CDN **directes** (`media.apimo.pro/cache/…_1920-original.jpg`) |
| `photoWatermarkAlias` | 22/200 (11 %) | watermark présent sur une minorité |

⇒ **0 fetch HTML pour obtenir les URLs** côté bienici : elles sont dans le JSON
**déjà téléchargé** par la collecte actuelle (`realEstateAds.json`). La capture des
**URLs** y est donc triviale (un helper de plus dans `_parse_listing`). Reste le
**download des bytes** des images (3/annonce) pour calculer le hash — autre sujet
(§2, §8). Accès image : CDN direct (`media.apimo.pro`), pas d'auth apparente
[À VÉRIFIER : hotlink-protection / referer / rate-limit du CDN — protocole : un job
CI télécharge ~20 images et journalise les codes HTTP].

### 1.3 Agences HTML (benedic, idemmo, immoheytienne, laveine) — non mesuré
- Les 4 sources parsent des **cartes**, pas des pages détail. Les vignettes de carte
  sont souvent **recadrées au ratio de la carte** et **lazy-loadées** (`data-src`) —
  un pHash de vignette recadrée matche mal le même cliché non recadré publié
  ailleurs (`cross-agence-ANALYSE.md` §4.2, §5.1 : « **recadrage casse** »). Pour des
  hashes fiables, il faut probablement la **page détail** ⇒ **+1 GET par annonce**
  (~350 GET × politesse `polite_sleep` ~1,5-2 s ≈ 10-12 min, hors timeout 15 min de
  `collect.yml`). [À VÉRIFIER : nature/résolution des vignettes — protocole :
  `diagnose.py --recon` sur une carte ET une page détail de chaque agence, lecture du
  commentaire de PR].
- **Tension avec la posture de politesse** des scrapers existants (`scrapers/base.py`
  UA Chrome + retry + `polite_sleep`) : un download d'images de masse alourdit le
  trafic vers des CDN tiers.

### 1.4 Implication périmètre
La capture côté **bienici seul** est de loin la moins coûteuse et la mieux mesurée.
**Mais** : c'est aussi la source la plus **syndiquée** (PREREQ0 §2bis). Le vrai cas
cross-agence (B ≠ A) suppose souvent une **agence HTML** d'un côté — ce qui rouvre la
question des vignettes recadrées. Cette tension (bienici = fiable mais syndiqué ;
agences = pertinentes mais photos incertaines) est structurante (Q5).

---

## 2. Où calculer le pHash : moment, coût, stockage

Trois moments possibles. La logique de calcul est **lecture seule** vis-à-vis du
contenu (on jette les bytes, on garde le hash).

### 2.1 Au scrape (CI runner) — recommandé par l'ANALYSE chantier
`cross-agence-ANALYSE.md` §6.2 conclut **calcul en CI** : le runner télécharge les
images (egress GitHub gratuit), calcule le hash, et le backend ne reçoit que des
hashes (pattern `jobs/push_comparables.py` à l'identique). Avantages : la dépendance
image (Pillow/imagehash) reste **dans le job CI**, **jamais dans l'image Docker
Fly** ; le CPU est dédié ; pas de réveil de la VM Fly (sécurité financière CONTEXT
§3.3). Inconvénient : le job de collecte actuel (`collect.yml`, timeout 15 min) ne
peut pas absorber un download de masse ⇒ **job dédié** séparé (`cross-agence-ANALYSE`
§8, §6.1 option B/D).

### 2.2 À l'ingestion (VM Fly) — déconseillé
Calculer le hash dans `ingestion/save.py` exigerait de télécharger les bytes sur la
VM Fly (shared-cpu, concurrence avec `/analyze`), d'embarquer Pillow dans l'image
prod, et de **réveiller la VM longtemps** (contre l'auto-stop). Rejeté par
`cross-agence-ANALYSE.md` §6.2 sauf pour le hash **transient** du bien analysé
(incrément 3, hors 2b).

### 2.3 Job séparé périodique — variante de 2.1
Un workflow distinct du `collect.yml`, post-collecte, qui lit les URLs nouvellement
capturées et calcule/pousse les hashes. Permet de **découpler capture (collect.yml,
inchangé) et hashing (job neuf)**. C'est la forme concrète de 2.1.

### 2.4 Stockage du hash
Deux options (à arbitrer, §6) :
- **Colonne(s) sur `comparables`** : simple, mais une annonce a N photos ⇒ il
  faudrait soit N colonnes fixes (rigide), soit une chaîne concaténée (anti-SQL).
  Peu adapté à N photos × variantes (miroir/rotation, `cross-agence-ANALYSE.md` §5.1).
- **Table dédiée `photo_hashes(listing_id, position, hash, …)`**
  (`cross-agence-ANALYSE.md` §6.3) : normalisé, adapté au multi-photos.
  **Conséquence (leçon inc.1, `.claude/lessons.md` 2026-06-11)** : toute nouvelle
  table dépendante impose de ré-auditer **TOUS** les chemins de suppression du parent
  (`comparables`) — band/zone/dept/rétention dans `app/main.py` — pour cascader la
  purge, plus un reset autouse en `conftest.py` (leçon photo-evidence). C'est le coût
  caché d'une table de masse.

### 2.5 Volume / coût récurrent (ordre de grandeur, non chiffré sans source)
Intrants factuels pour le strategist :
- Parc : **~17,7k annonces** (CONTEXT §0), dont ~17,4k bienici.
- Photos bienici exposées : **3/annonce** (PREREQ0). ⇒ borne haute capture URLs : ~52k URLs.
- Download bootstrap (one-shot) : ~52k images ; rythme hebdo : seulement les
  **nouvelles** annonces (delta de churn). `cross-agence-ANALYSE.md` §6.1 estime
  l'option B (bienici 3 photos delta) à **bootstrap ~6 Go / ~3 h one-shot**, puis
  **~10-20 min/sem**. Stockage hashes (table) : ~52k photos × variantes ≈
  négligeable (~10 Mo, §6.3 ANALYSE) sur le volume Fly 1 Go.
- Ces chiffres sont des **estimations de l'ANALYSE chantier**, à valider par le job
  de mesure réel (taille moyenne des images apimo, débit CDN) — **non re-chiffrés
  ici faute d'egress**.

---

## 3. Doctrine RGPD / ToS — POINT CRITIQUE (la photo est le contenu le plus sensible)

### 3.1 Ce qui est clairement permis (par analogie avec l'existant)
- **Stocker un pHash** = stocker une **empreinte non réversible** (on ne peut pas
  reconstruire l'image depuis un hash 64 bits). `cross-agence-ANALYSE.md` §7 :
  « hash perceptuel ≠ photo, non reconstructible, ce n'est pas une reproduction de
  l'œuvre ». C'est de même nature que les `reference`/`customer_id`/`lineage_id`
  déjà actés comme **métadonnées internes** (CONTEXT §11.3 amendé, note ajoutée sur
  les identifiants techniques internes ; SPEC 2a §6). Posture défendable : **stockage
  interne autorisé**, à condition de ne **jamais exposer ni l'image, ni son URL, ni
  le hash** dans une réponse API (cf. confidentialité `/history`, SPEC 2a §4.1 AC27).
- **Ne jamais stocker l'image elle-même** ni journaliser l'URL d'image (même posture
  que `photo_evidence`, `cross-agence-ANALYSE.md` §7) : transit seulement.

### 3.2 Ce qui relève d'un ARBITRAGE HUMAIN explicite (je ne tranche pas)
- **Le download massif d'images tierces est une extraction NOUVELLE.**
  `cross-agence-ANALYSE.md` §7 le dit clairement : conserver l'historique de ce qu'on
  extrait **déjà** (le JSON) n'ajoute pas d'extraction ; mais **télécharger les bytes
  des photos** (même pour ne garder que le hash) **EST** une extraction nouvelle au
  regard du **droit sui generis des bases de données** et de la **charge CDN**. 2a
  n'a jamais franchi cette ligne (zéro download). 2b la franchit. ⇒ **arbitrage
  humain requis** : accepte-t-on de télécharger ~52k images tierces (bootstrap) puis
  un delta hebdo, sous discipline de politesse (cap 3 photos, delta, throttle) ?
- **Watermarks d'agence** (22/200, PREREQ0) : une photo watermarkée est le contenu
  d'un tiers nominativement marqué. On n'en stocke que le hash (pas l'image), mais le
  fait de re-hasher un contenu watermarké d'un concurrent mérite d'être acté.
- **ToS / hotlink** du CDN apimo.pro : [À VÉRIFIER] le CDN peut interdire le
  hotlinking ou throttler. Risque opérationnel + ToS, à mesurer avant tout
  engagement.

### 3.3 Ce qui resterait interdit (anti-pattern, non négociable)
- Re-publier l'image, son URL, l'adresse exacte, le texte ou re-afficher l'annonce
  tierce (CONTEXT §11.3 ; anti-pattern #3). 2b reste sous la même contrainte que
  2a : exposition limitée aux **agrégats / métadonnées factuelles** (source,
  ancienneté, écart de prix %), jamais le contenu.

**Synthèse RGPD/ToS** : le **stockage du hash** est dans l'esprit de la doctrine
amendée (permis, interne). Le **téléchargement de masse des images** est le point qui
**sort** du périmètre déjà acté et **exige une décision humaine** (Q3). Ne pas
trancher ici.

---

## 4. Dépendances Python nouvelles — TENSION MAJEURE (GATE 1)

### 4.1 État réel
`requirements.txt` (7 lignes) : `fastapi, uvicorn[standard], sqlalchemy, requests,
beautifulsoup4, openai>=1.50, numpy`. **Ni Pillow, ni imagehash, ni scipy.**

### 4.2 Ce qu'exige le pHash
`cross-agence-ANALYSE.md` §2.6 a chiffré :
- **`imagehash`** (pHash DCT, robuste aux retouches) tire **Pillow + PyWavelets +
  scipy** ⇒ **+~70-100 Mo** installés, **3 deps nouvelles**.
- **Alternative `Pillow` seul** (+~12 Mo) + un **dHash/aHash maison** (~20 lignes,
  `numpy` déjà présent). Une dépendance, isolable.

### 4.3 Impact CI / Docker Fly
- Si le calcul est **en CI** (§2.1, reco), la dépendance vit **uniquement dans le
  job CI** (le nouveau workflow d'images), **pas dans l'image Docker Fly** ni dans
  `test.yml`/`deploy-backend.yml`. C'est le point clé qui **désamorce** en grande
  partie l'anti-pattern « zéro dep » : l'image prod reste inchangée, le coût de build
  Fly aussi.
- Si un jour le hash **transient** du bien analysé est calculé côté Fly (incrément 3,
  hors 2b), alors Pillow entrerait dans l'image prod — décision à reporter à
  l'incrément 3, **pas** à 2b.

### 4.4 Arbitrage
La tension « anti-pattern zéro dep » vs « 2b a besoin d'une lib image » se résout
**si et seulement si** la dépendance reste **confinée au job CI**. À acter
explicitement (Q1) : (a) Pillow seul + dHash maison (minimaliste, culture projet) ;
(b) imagehash + scipy (plus robuste, 3 deps). Le format de stockage (64 bits hex)
étant identique, une bascule (a)→(b) est un re-hash du corpus (~3 h CI,
`cross-agence-ANALYSE.md` §6.6/Q6) — donc **commencer minimaliste est réversible**.

---

## 5. Risque de faux positifs (le risque produit dominant)

### 5.1 Pourquoi les pHash collisionnent
`cross-agence-ANALYSE.md` §5.1/§5.2 documente les cas réels :
- **Même immeuble, biens différents** : deux appartements partagent hall, façade,
  cage d'escalier, vue ⇒ un vote **k=1 photo est interdit**.
- **Photos de stock / plans / photos d'immeuble** réutilisées pour des lots
  différents.
- **Watermarks** d'agence (22/200) : un watermark central dégrade le hash ; un
  watermark d'angle est souvent robuste.
- **Recadrage** (vignette vs original) : **casse** le hash (§1.3) — d'où la
  préférence pour les photos pleine résolution (JSON bienici) sur les vignettes HTML.

### 5.2 Politique conservatrice proposée par l'ANALYSE chantier (à valider)
`cross-agence-ANALYSE.md` §5.2 (cadre, valeurs calibrables) :
- match photo = **distance de Hamming ≤ 6/64** (à calibrer en staging) ;
- vote **≥ 2 photos distinctes** appariées (k-sur-n, jamais k=1) ;
- corroboration d'attributs **obligatoire** : même `property_type`, même `city`
  canonique (idéalement même `postal_code`), surface à **±10 %** (les agences
  arrondissent ; Carrez vs utile — noter la différence avec le **±2 %** de 2a, plus
  strict car intra-source) ;
- **aucune** contrainte de prix (l'écart de prix est le signal) ;
- jamais d'entrée dans `market_stats`, jamais de pesée du score ;
- **tests de verrou** : « jamais de match k=1 », « jamais de match sans corroboration
  attributs » (leçon : un garde-fou sans test est oublié, `.claude/lessons.md`).

### 5.3 Symétrie avec 2a
2a a posé la même asymétrie de coût (SPEC 2a §3.4, ANALYSE 2a §4.4) : **un raté
(continuité manquée, dégradé gracieux = état actuel) est moins grave qu'un faux lien
(historique corrompu, sauts de prix aberrants entre deux biens distincts)**. 2b doit
hériter de ce conservatisme — voire être **plus strict**, car cross-source est
intrinsèquement plus ambigu (pas de `customer_id` pour lever l'ambiguïté).

### 5.4 Ce qui n'est PAS mesuré (honnêteté)
- **Le taux de collision réel** des pHash sur le parc messin (même immeuble, stock,
  watermarks) n'est **pas** mesuré. PREREQ0 a mesuré la **disponibilité** des photos,
  **pas** la séparabilité intra-bien vs inter-bien. Les seuils (Hamming, ±%) sont des
  **constantes de littérature**, pas calibrées sur données réelles
  (`cross-agence-ANALYSE.md` §4.4.3 prévoit la calibration staging — **non faite**).
- **Le taux de re-list cross-source réel** n'est pas mesuré (PREREQ0 §3.4, ANALYSE 2a
  §1.4) : c'est le **même trou** que pour 2a, aggravé par le fait que la syndication
  bienici masque le vrai multi-mandat. ⇒ on outillerait un phénomène dont on ignore
  l'ampleur ET la séparabilité.

---

## 6. Réutilisation de l'acquis 2a — modèle de lignée cross-source

### 6.1 L'acquis réutilisable tel quel
- **`lineage_id`** (colonne indexée, `db/models.py:68`, migration
  `db/session.py:55-72`) : sémantiquement « lignée d'un bien physique » — **ne
  présuppose pas la source**. Un rattachement cross-source peut, en principe, poser
  le même `lineage_id` sur deux membres de sources différentes.
- **`/history`** agrège déjà les snapshots de **tous les membres** d'une lignée (SPEC
  2a §4.1, `app/main.py` /history) — fonctionne indépendamment de la source des
  membres.
- **Rétention sur lignée** (MAX `last_seen_at`, SPEC 2a §4.2) — idem.
- La **branche d'ingestion** `existing is None` (`ingestion/save.py:154-168`) est le
  point d'insertion naturel d'un second rattacheur (photo) **après** l'échec du
  rattacheur 2a.

### 6.2 Ce que 2b casse dans les invariants implicites de 2a
Trois ruptures structurantes que 2b introduit et que 2a évitait **par construction** :

1. **2a est SÉQUENTIEL (un bien chez une agence à la fois) ; 2b peut être
   SIMULTANÉ.** Un même bien physique peut être **vivant chez 2 agences en même
   temps** (mandat simple multi-agences) ⇒ 2 annonces de sources différentes,
   **toutes deux non disparues**, dans le même run. 2a a explicitement **exclu** ce
   cas (SPEC 2a §3.5 « doublon simultané, hors scope »). 2b, par nature, le rencontre.
   **Question non triviale** : deux annonces vivantes simultanées du même bien
   forment-elles **une** lignée unique ? Si oui, `/history` fusionnerait deux séries
   de prix **concurrentes** (pas séquentielles) — la sémantique de
   `price_first`/`price_last`/`price_change_pct` (SPEC 2a §4.1) devient ambiguë (quel
   prix « courant » quand deux annonces vivantes affichent des prix différents ?).

2. **La fenêtre temporelle de 2a (« récemment DISPARU », 90j) ne s'applique pas
   telle quelle.** Le rattachement cross-source simultané se ferait entre deux
   annonces **actives**, pas entre une disparue et une neuve. Le marqueur «
   `last_seen_at` figé » (SPEC 2a §3.2) ne discrimine plus. ⇒ 2b a besoin d'un autre
   prédicat temporel (ou d'aucun).

3. **Double-comptage dans `market_stats` — risque NOUVEAU révélé par 2b.** 2a était
   intra-source et séquentiel : un bien re-listé n'était jamais compté deux fois
   **au même instant** dans `market_stats` (l'ancien membre est disparu). 2b
   identifie qu'un même bien physique est présent **simultanément** via 2 annonces de
   2 sources ⇒ il **est déjà compté deux fois aujourd'hui** dans `market_stats`
   (deux lignes `comparables` distinctes). 2a ne dédoublonnait pas (SPEC 2a §1.3,
   §4.6) ; 2b **révèle** explicitement ce double-comptage. **Attention** : il serait
   tentant de « corriger » en dédoublonnant via `lineage_id` — mais
   `cross-agence-ANALYSE.md` §5.2 l'interdit (« les clusters n'entrent **jamais** dans
   `market_stats` ; un faux cluster y fausserait les médianes »). ⇒ 2b doit
   **laisser `market_stats` strictement inchangé** et **assumer/documenter** le
   double-comptage préexistant comme un risque connu, **pas** le résoudre via un
   matching photo faillible. Ce point doit être tranché (Q4).

### 6.3 Conclusion réutilisation
Le **schéma** `lineage_id` est réutilisable. La **logique** ne l'est pas : 2b exige
un nouveau prédicat (photo + Hamming + vote), une nouvelle gestion du cas simultané,
et la décision explicite de **ne pas** toucher `market_stats`. La frontière nette :

| Aspect | 2a (livré) | 2b (ce chantier) |
|---|---|---|
| Cas | re-list même agence, **séquentiel** | re-list agence différente, **possiblement simultané** |
| Clé | `reference`+`customer_id`+attributs | **pHash photos** + attributs (±10 % surface) |
| Identifiants communs | oui | **non** (tout change) |
| Dépendances Python | aucune | **Pillow ± imagehash** (confinées CI) |
| Download | aucun | **~52k images bootstrap** + delta |
| Fenêtre temporelle | « disparu ≤ 90j » | inadaptée (annonces simultanées) |
| Double-comptage market_stats | évité par construction | **révélé**, à assumer (pas corriger) |
| Calibration | bornes prudentes | **seuils Hamming à calibrer en staging (non fait)** |

---

## 7. Impact sur les invariants (score, contrat, market_stats)

- **Score 40/30/30** (`scoring.py`) : doit rester **strictement intact**. 2b est
  admin-only, non-scoré (comme 2a, inc.1, `local_context`, `photo_status`).
- **Contrat `/analyze` / `AnalyzeResponse` / `frontend/lib/api.ts`** : **non
  touchés**. Aucune clé ajoutée. (Anti-pattern #9.) Verrou : un AC type AC37 de 2a.
- **`market_stats` / sélection des comparables** : **inchangés**. **Ne PAS
  dédoublonner** par `lineage_id` (cf. §6.2 pt 3 et `cross-agence-ANALYSE.md` §5.2).
- **Double-comptage** : 2b ne le crée pas (il préexiste pour les biens syndiqués),
  mais il le **rend visible**. Choix conservateur : documenter comme risque connu,
  laisser `market_stats` intact. Un faux cluster photo qui dédoublonnerait à tort
  serait **pire** que le double-comptage actuel. À acter (Q4).
- **`/history` / rétention** : extensibles à des membres cross-source, **mais** la
  sémantique « prix courant » devient ambiguë en cas de membres simultanés (§6.2
  pt 1) — à spécifier.

---

## 8. Coût infra & forecast (intrant strategist, ordre de grandeur)

Quantification d'ordre de grandeur (sources : CONTEXT §0, PREREQ0 §1,
`cross-agence-ANALYSE.md` §6.1) — **non re-chiffré faute d'egress** :
- **Volume** : ~17,7k annonces × 3 photos bienici = **~52k images** (borne haute
  bootstrap). Rythme hebdo = **delta de churn** (annonces nouvelles seulement),
  estimé ~3-6k images/sem (`cross-agence-ANALYSE.md` §6.1 option B).
- **Download bootstrap** : ~6 Go / ~3 h CI one-shot ; **hebdo** : ~10-20 min CI
  (option B). Quota GitHub Actions (repo privé, 2000 min/mois) : bootstrap 180 min +
  ~120-180 min/mois — **dans le quota, à surveiller** (`cross-agence-ANALYSE.md`
  §6.1).
- **CPU/bande passante récurrents** : portés par le **runner CI**, **pas** par la VM
  Fly (préserve l'auto-stop, CONTEXT §3.3) — à condition de calculer en CI (§2.1).
- **Stockage** : table de hashes ~10 Mo, négligeable sur 1 Go.
- **CDN tiers** : charge récurrente sur apimo.pro (bienici) et les CDN agences —
  **coût ToS/politesse**, pas un coût € pour nous, mais un risque relationnel/blocage
  [À VÉRIFIER].
- **Coût € direct pour le projet** : ~0 (egress CI gratuit, pas de LLM, pas de
  vendor). Le coût réel est **en temps de build/quota CI** et en **risque ToS**, pas
  en facture. Cohérent avec le MVP < 1 €/mois **si** confiné CI.

---

## QUESTIONS POUR L'HUMAIN (GATE 1)

> Distinction tranchable-par-défaut-conservateur vs décision-humaine indiquée pour
> chaque question.

**Q1 — Dépendance image : laquelle, et où la confiner ? [décision humaine — tension
anti-pattern]**
2b rompt l'anti-pattern « zéro dépendance nouvelle » présent dans tous les incréments
précédents. La tension se désamorce **si** la dep reste **dans le job CI** (image
Docker Fly inchangée, §4.3).
- (a) **Pillow seul (+~12 Mo) + dHash/aHash maison** (~20 lignes, `numpy` déjà là),
  confiné au nouveau job CI ; image Fly intacte. Bascule vers (b) = re-hash du corpus
  (~3 h CI), réversible.
- (b) **imagehash + Pillow + PyWavelets + scipy** (+~70-100 Mo, 3 deps), pHash DCT
  plus robuste aux retouches, confiné CI.
- **Reco : (a)** en première intention (culture minimaliste, réversible), bascule (b)
  si la précision mesurée en staging est insuffisante. **À confirmer explicitement**
  que la dep ne touche **jamais** l'image prod en 2b.

**Q2 — Moment et stockage du hash. [tranchable par défaut conservateur, mais le
choix table est structurant]**
- Moment : (a) **calcul en CI**, backend récepteur de hashes (reco
  `cross-agence-ANALYSE.md` §6.2 ; préserve l'auto-stop) ; (b) à l'ingestion Fly
  (déconseillé) ; (c) job dédié post-collecte (= forme de (a)).
- Stockage : (a) **table `photo_hashes`** (normalisé, multi-photos) — **impose** de
  ré-auditer les 4 chemins de purge `comparables` + cascade + reset autouse conftest
  (leçon inc.1) ; (b) colonne(s) sur `comparables` (rigide pour N photos).
- **Reco : calcul CI + table `photo_hashes`**, en assumant explicitement le coût «
  nouvelle table dépendante » (cascade sur band/zone/dept/rétention).

**Q3 — Téléchargement de masse des images tierces : doctrine RGPD/ToS. [décision
humaine — point critique, NE PAS trancher par défaut]**
Stocker un **hash** est dans l'esprit de §11.3 amendé (empreinte non réversible,
métadonnée interne, jamais exposée). **Mais télécharger ~52k images tierces**
(bootstrap) puis un delta hebdo est une **extraction nouvelle** que ni inc.1 ni 2a
n'ont franchie (`cross-agence-ANALYSE.md` §7 : droit sui generis + charge CDN).
- (a) Autoriser le download sous **discipline stricte** (cap 3 photos/annonce, delta
  seulement, throttle/politesse, jamais de stockage d'image ni de log d'URL, hash
  seul conservé) — et **amender CONTEXT §11.3** pour acter que le download transitoire
  d'images aux seules fins de hash interne est permis.
- (b) Refuser le download de masse ⇒ 2b infaisable tel que pressenti (pas de hash
  sans bytes).
- **Reco : remonter tel quel, ne pas trancher.** Prérequis avant tout code :
  [À VÉRIFIER] ToS/hotlink du CDN apimo.pro et des CDN agences.

**Q4 — Double-comptage `market_stats` révélé par 2b. [décision humaine]**
2b identifie qu'un même bien physique vivant via 2 sources est **déjà compté deux
fois** dans `market_stats` (préexistant). Tentation : dédoublonner via `lineage_id`.
- (a) **Laisser `market_stats` strictement inchangé**, ne PAS dédoublonner, documenter
  le double-comptage comme risque connu (un faux cluster photo fausserait les médianes
  — `cross-agence-ANALYSE.md` §5.2 l'interdit explicitement).
- (b) Dédoublonner via `lineage_id` cross-source — **déconseillé** (introduit le
  risque de faux cluster dans le cœur statistique, contre la doctrine).
- **Reco : (a)**, conservateur. C'est le défaut sûr, mais il doit être **acté** car
  2b rend le double-comptage visible.

**Q5 — Périmètre sources de 2b. [tranchable par défaut conservateur]**
- (a) **bienici uniquement** (photos en JSON, 95,5 %, 3 URLs, 0 fetch HTML) — mais
  c'est la source la plus **syndiquée** (le vrai cross-agence y est rare).
- (b) bienici + agences HTML (pages détail, +~350 GET/sem hors timeout `collect.yml`,
  vignettes recadrées au risque de hash — [À VÉRIFIER]).
- **Reco : (a) pour un premier pas mesurable**, extension (b) **seulement si** la
  probe de gisement (Q6) montre du re-list cross-source non capté côté bienici. (b)
  rouvre la question des vignettes recadrées (§1.3).

**Q6 — Séquençage : mesurer AVANT de coder, et découpler capture/logique. [décision
humaine — recommandation forte de l'analyste]**
Le gisement cross-source réel **n'est pas mesuré** (syndication masque le vrai
multi-mandat ; taux de re-list temporel jamais mesuré, PREREQ0 §3.4). Le taux de
collision pHash n'est pas mesuré non plus (§5.4).
- (a) **Probe d'abord** : (i) mesurer sur l'historique inc.1/2a qui mûrit le taux de
  re-list cross-source réel (biens disparus d'une source → réapparus dans une autre,
  non captés par 2a) ; (ii) capturer les **URLs photo** (cheap, réversible, colonne
  nullable) ; (iii) calibrer Hamming/seuils sur un corpus staging (protocole
  `cross-agence-ANALYSE.md` §4.4.3) ; **PUIS** spécifier la logique de matching.
- (b) Spécifier capture + download + hashing + matching **d'un bloc**.
- **Reco : (a) fortement.** Découple le cheap/réversible (capture URLs, probe) du
  cher/risqué (download de masse, matching faillible), comme 2a a découplé capture et
  logique. Évite d'outiller un phénomène non quantifié avec une infra à 3 deps et 52k
  downloads.

**Q7 — Politique de matching conservatrice (cas simultané + seuils). [tranchable par
défaut conservateur, à valider]**
Cadre proposé (`cross-agence-ANALYSE.md` §5.2 + adaptation cross-source) :
- Hamming ≤ 6/64, **≥ 2 photos distinctes** (jamais k=1), corroboration obligatoire
  (même type + ville/postal + surface **±10 %**), aucune contrainte de prix, wording
  hedgé, jamais d'impact score/market_stats, tests de verrou (k=1 interdit,
  corroboration obligatoire), seuils **recalibrés en staging avant prod**.
- **Cas simultané** (deux membres vivants de sources différentes, §6.2 pt 1) : (a)
  les regrouper en une lignée unique en assumant une sémantique « prix courant »
  ambiguë à spécifier ; (b) **ne PAS les fusionner au MVP** (rester aussi
  conservateur que 2a, qui exclut le doublon simultané — SPEC 2a §3.5) et ne traiter
  que le cas séquentiel cross-source (disparu d'une source → réapparu dans une autre).
- **Reco : (a) pour les seuils** (valeurs calibrables staging) ; **(b) pour le cas
  simultané** (conservatisme : ne pas fusionner deux annonces vivantes tant que la
  sémantique `/history` du multi-membre simultané n'est pas tranchée).

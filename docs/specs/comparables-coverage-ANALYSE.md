# comparables-coverage — ANALYSE — Densifier et fiabiliser la base de comparables sur la couronne de Metz

Rôle de ce document : cadrage et challenge (ANALYSTE). Aucune décision
structurante n'est prise ici ; les arbitrages (en particulier DVF) sont remontés
en GATE 1. Analyse fondée sur le code réel (`backend/scrapers/`,
`backend/ingestion/save.py`, `backend/app/market_stats.py`, `backend/jobs/`,
`.github/workflows/`) qui prime sur la doc, et sur les indices documentaires
(CONTEXT §11, CLAUDE §7/§11) quand le volume réel n'est pas mesurable depuis le
repo.

Problème porteur : la base est trop mince et peu fiable sur les communes
recherchées de la couronne messine (Marly, Saint-Julien-lès-Metz, Scy-Chazelles,
Plappeville, Le Ban-Saint-Martin, Montigny-lès-Metz, Longeville-lès-Metz, Augny,
Lessy...), surtout pour les MAISONS. Symptôme vu en issue #87 : un bien à Marly
retombe sur des comparables agglo (faux-signal). Crainte existentielle : « sans
base plus étoffée et fiable, le projet est vain ».

---

## 0. Avertissement de mesurabilité (à lire avant tout chiffre)

**Le volume par commune n'est PAS mesurable depuis ce repo.** La base prod
(~17,7k comparables, ~2,6k maisons selon CLAUDE §7) vit sur le volume Fly
`/data/comparables.db`, absente du dépôt (`.gitignore`, CONTEXT §11.10). Aucun
décompte par commune ni par couple (commune × maison) n'est donc vérifiable ici.
Tout ce qui suit raisonne à partir de :
- la **nature des sources** (lisible dans le code : quelle source ratisse quel
  territoire) ;
- les **indices documentaires** : CLAUDE §7 « couverture des 12-16 quartiers
  messins largement au-dessus du seuil » mais §11 « volume par commune encore
  faible hors Metz » ; issue #87 confirmant qu'à Marly le pool maisons dans la
  fenêtre surface est tombé sous le plancher.

Aucun chiffre par commune n'est fabriqué dans ce document. Là où une mesure est
nécessaire à la décision, elle est listée comme **prérequis de mesure** (cf. §9).

---

## 1. Diagnostic de couverture réel (par source)

### 1.1 Ce que chaque source ratisse réellement (lu dans le code)

| Source | Type | Périmètre géographique réel | Maisons couronne ? |
|---|---|---|---|
| `bienici` | API JSON | **Zone de la VILLE de Metz uniquement** | Quasi nul (voir 1.2) |
| `benedic` | HTML | Moselle large (Forbach, Thionville, Saint-Avold...) | Diffus, dilué hors couronne |
| `idemmo` | HTML | Moselle (agence messine) | Oui mais volume faible |
| `immoheytienne` | HTML | Secteur messin, « majoritairement des maisons » | Oui, mais une seule agence |
| `laveine_immo` | HTML | La Veine immo, « quelques maisons communes limitrophes » | Marginal |

### 1.2 Le point technique central : bien'ici ne collecte QUE la commune de Metz

`backend/scrapers/sources/bienici.py:302` fixe `city = "Metz"` en dur, et
`discover_zone_ids("Metz")` (`bienici.py:63-99`) résout le **zoneId de la
commune de Metz** (`-450381`, cf. `diag_bienici.py:4-7`), pas un zoneId
d'agglomération ni les communes de la couronne. Le filtre `zoneIdsByTypes`
(`bienici.py:102-116`) restreint donc la collecte au **territoire communal de
Metz intra-muros**.

Conséquence directe et structurante : **la source de loin la plus volumineuse
(~17,4k des ~17,7k comparables, CLAUDE §7) n'alimente PAS la couronne.** Marly,
Saint-Julien, Scy-Chazelles, Plappeville, etc. ne reçoivent de bien'ici que les
rares annonces dont le libellé ville déborde de la zone Metz — quantité
négligeable. Les communes limitrophes ne sont alimentées que par les **4 agences
HTML**, dont une seule (`immoheytienne`) est orientée maisons, et dont le volume
total est de l'ordre de ~350 annonces toutes communes confondues (CLAUDE §7).

C'est l'explication mécanique du faux-signal #87 : pour une maison à Marly dans
la fenêtre surface ±20 %, le pool communal tombe sous le plancher
(`MIN_COMPARABLES`, `market_stats.py:26`) → la cascade remonte à `metropole`
(`market_stats.py:205-208`) → verdict calculé contre la moyenne d'agglo.

### 1.3 Spécificité MAISONS

Double peine sur les maisons de la couronne :
1. bien'ici ne ramène « ~1 % de maisons pour Metz » (CLAUDE §11) — et de toute
   façon pour Metz, pas pour la couronne ;
2. les communes de la couronne (où la maison est justement le bien-type) ne sont
   alimentées que par les agences HTML, à faible volume.

Donc le segment le plus demandé par l'utilisateur cible (maison en couronne) est
**exactement** le moins couvert. Le diagnostic du porteur est correct.

### 1.4 Ce que la cascade fait déjà pour compenser (et ses limites)

`market_stats.py:160-250` tente le grain commune EN PREMIER (`city ==`,
ligne 134), puis élargit : `quartier → secteur → ville → métropole`. Pour une
commune de couronne, quartier/secteur sont sautés (`_SECTORS_RAW` ne couvre que
Metz, `market_stats.py:36-50`), donc ville → métropole. La cascade est une
**béquille de couverture**, pas une densification : elle ne crée pas de données
communales, elle emprunte à l'agglo. Issue #87 a déjà fait poser un
**avertissement textuel** sur ce repli (`_scope_warning`, `market_stats.py:273`)
— honnêteté, pas densité.

---

## 2. VOLUME ≠ FIABILITÉ (les deux axes du problème)

Densifier (plus de lignes) et fiabiliser (lignes plus dignes de confiance) sont
deux problèmes distincts. Un afflux de volume mal qualifié peut *dégrader* la
fiabilité.

### 2.1 Axes de fiabilité, état actuel

- **Fraîcheur.** Collecte hebdomadaire (lundi 04:00, `collect.yml:7`). Acceptable.
  Rétention 24 mois (`save.py` + maintenance, CLAUDE §9). Pas de signal d'annonce
  périmée au-delà du `last_seen_at`.
- **Dédup intra-source.** `generate_stable_id(source, ext_id)` (`base.py:132`) +
  upsert (`save.py:152`). Solide.
- **Dédup INTER-agences (cross-agence).** Incrément 1 livré (tracking temporel
  mono-source : `first_seen/last_seen`, snapshots de prix). Incrément 2a livré
  (re-link même agence par `reference`+attributs). **Ce qui est livré ne fait PAS
  encore de dédup d'un même bien listé par DEUX agences différentes** : le
  re-link exige `source` identique (`save.py:77`). Un bien en multi-mandat
  (fréquent en couronne : un pavillon chez 3 agences + sur bien'ici) compte donc
  comme 3-4 comparables distincts → **sur-représentation** d'un même bien réel.
  L'incrément 2 (clustering photo, `photo_urls` déjà capté `bienici.py:191`) vise
  ce cas mais n'est pas livré.
- **Correspondance surface/DPE/type.** DPE ~82 % et année ~37 % sur bien'ici, mais
  best-effort et souvent vides sur les agences HTML (CLAUDE §7). Donc pour la
  couronne (alimentée par les agences HTML), le filtre par bande DPE
  (`market_stats.py:194-208`) est rarement activable → moins de finesse là où on
  en aurait le plus besoin. Le type est inféré par mots-clés
  (`infer_property_type`, `base.py:318`) — robuste mais grossier.
- **Biais annonces vs transactions.** **Point de fiabilité majeur et structurel.**
  La base ne contient QUE des **prix affichés d'annonces en cours**, jamais des
  prix de transaction réels. Or :
  - un prix affiché est un prix *demandé* par le vendeur, souvent au-dessus du
    prix de vente effectif (marge de négo) ;
  - les biens qui se vendent vite (souvent les mieux prix) **sortent** de la base
    avant d'être bien observés ; les biens sur-cotés **stagnent** et sont
    sur-représentés dans le stock à un instant t → biais de survie qui **gonfle
    structurellement** la médiane observée.
  Aucun levier d'acquisition d'annonces ne corrige ce biais : c'est exactement ce
  que DVF (transactions réelles) corrigerait (cf. §4). À garder en tête : la base
  mesure « ce qui est demandé sur le marché », pas « ce qui se vend ». Le
  positionnement produit (« cohérence avec ce que j'observe sur le marché »,
  CONTEXT §1.1) est cohérent avec ce biais ASSUMÉ — mais le porteur doit savoir
  que « fiable » a une borne haute tant qu'on reste sur des annonces.
- **Accumulation temporelle.** Les snapshots (incrément 1) capturent l'historique
  de prix d'une annonce. En laissant tourner la collecte, on accumule le **flux**
  d'annonces (biens qui apparaissent/disparaissent), ce qui densifie le stock
  communal au fil des mois SANS nouveau levier — levier le moins cher (cf. §3.4).

### 2.2 Implication

Pour la couronne, le déficit est d'abord un **déficit de volume communal**
(bien'ici ne la couvre pas), et secondairement un **plafond de fiabilité**
(annonces ≠ transactions, multi-mandat non dédupliqué). Les leviers §3 traitent
le volume ; seul DVF (§4) traite le plafond de fiabilité « transactions ».

---

## 3. LEVIERS d'acquisition (effort / coût / risque juridique-ToS / gain couronne)

Tous chiffrés en ordre de grandeur. Coût cible MVP < 1 €/mois (CONTEXT §3.2).

### 3.1 Élargir le balayage bien'ici aux communes de la couronne — LEVIER LE PLUS RENTABLE

C'est le levier à plus fort effet de levier, parce que bien'ici est une **API
JSON immunisée à l'anti-bot** (CLAUDE §8) et que le code ne lui demande
aujourd'hui que la ville de Metz (§1.2). Deux variantes :

- **(a) Boucler `discover_zone_ids` sur une liste de communes** (réutiliser
  `_METRO_CITIES_RAW`, `market_stats.py:58-70`) : pour chaque commune, résoudre
  son zoneId et balayer ses tranches de surface. Effort : faible (~0,5-1 j ;
  `BieniciScraper.scrape` itère déjà les `SURFACE_BUCKETS`, il suffit d'itérer en
  plus sur une liste de zones). Dédup déjà géré par id stable.
- **(b) Cibler le zoneId de l'AGGLOMÉRATION** (Metz Métropole) si l'endpoint
  suggest en expose un de type plus large que `city`. Effort : faible mais à
  vérifier (le suggest ne sélectionne aujourd'hui que `type == "city"`,
  `bienici.py:84,93` ; il faut diagnostiquer ce que renvoie le suggest pour
  « Metz Métropole »).

- **Coût** : nul (runner GitHub, API gratuite). Attention au **temps de job** :
  `collect.yml` a `timeout-minutes: 15` (`collect.yml:12`) et `polite_sleep`
  ~1,5 s entre requêtes (`base.py:32`). Multiplier les communes × tranches de
  surface peut faire dépasser 15 min → relever le timeout et/ou paralléliser
  prudemment. Pas de quota tarifaire bien'ici connu, mais risque de throttling si
  on accélère trop (le code a déjà retry/backoff sur 429, `base.py:107`).
- **Risque ToS** : identique à l'existant (on scrape déjà bien'ici via son API
  JSON non documentée — c'est déjà le pari assumé du projet). N'aggrave pas le
  risque juridique : pas de redistribution, agrégats seulement (§11.3). On reste
  dans le périmètre déjà accepté.
- **Gain couronne** : **potentiellement décisif.** Si bien'ici couvre la couronne
  comme il couvre Metz, ce seul levier peut faire passer Marly/Saint-Julien/etc.
  de « creux » à « exploitable » pour beaucoup de biens, maisons incluses.
- **Risque de mesure** : à confirmer que bien'ici a un volume réel sur ces
  communes (une petite commune a mécaniquement peu d'annonces — élargir le
  périmètre n'invente pas de stock là où le marché est étroit).

**Reco analyste : levier prioritaire n°1, à instruire en premier** (faible
effort, coût nul, pas de nouveau risque, gain potentiellement structurant).

### 3.2 Étendre les scrapers d'agences locales de la couronne

Ajouter des agences qui **listent réellement** en couronne. Le harnais existe
déjà (`diagnose-scrapers.yml`, déposer `sources/<agence>.py` → lire le
diagnostic PR, CLAUDE §9). Cibles plausibles : réseaux nationaux à agences
messines/couronne (selon ce que le recon trouve fetchable) et agences de
proximité de Marly/Montigny/etc.

- **Effort** : ~0,5-1 j par agence intégrée (recon → sélecteurs → diagnostic →
  merge). Variable selon que le site rend le prix en HTML serveur ou en JS.
- **Coût** : nul.
- **Risque ToS** : à vérifier au cas par cas. Le recon a déjà **écarté** herbeth,
  agencevalentin (robots.txt + 403), century21, orpi (JS-only) (CLAUDE §8). Donc
  le gisement d'agences facilement scrapables est en partie déjà épuisé ; les
  grosses enseignes sont soit bloquées, soit JS-only. **Respecter robots.txt est
  une règle, pas une option.**
- **Gain couronne** : réel mais **incrémental et fragile** (chaque agence = peu
  de biens, sélecteurs cassables à tout redesign). Un mandat exclusif chez une
  agence de Marly n'apparaît que là — utile, mais on additionne des petits.

**Reco : levier n°2, en parallèle de 3.1, sans en attendre un effet volume
massif.** Plutôt un complément qualité (biens exclusifs absents de bien'ici).

### 3.3 Ajouter des portails nationaux (seloger, leboncoin, logic-immo, paruvendu, ouestfrance-immo, figaro immo)

- **Faisabilité technique** : **faible à très faible** pour la plupart.
  CONTEXT §4.3 acte que Leboncoin, SeLoger et Bien'ici (frontal) « renvoient des
  pages JS-only ou bloquent les requêtes non-navigateur ». Le projet n'a PAS de
  navigateur headless (pas de Playwright/Selenium dans `requirements.txt`, CLAUDE
  §4) et c'est un choix de minimalisme. Bien'ici n'est exploité QUE parce qu'il
  expose une API JSON ; les autres portails n'offrent pas cette porte.
- **Coût** : nul en infra, mais **coût d'effort élevé et récurrent** (anti-bot,
  CAPTCHA, rotation d'IP → on entre dans une course aux armements). Un service
  d'anti-blocage tiers serait un **nouveau vendor payant** (anti-pattern coût + < 1 €/mois).
- **Risque ToS / juridique** : **élevé.** Ces portails interdisent en général le
  scraping dans leurs CGU et ont des protections actives. Contourner un anti-bot
  est un risque juridique et réputationnel disproportionné pour un MVP. Leboncoin
  notamment est connu pour être agressif sur ce point.
- **Gain couronne** : potentiellement élevé (gros volume) MAIS inatteignable
  proprement à coût/risque MVP.

**Reco : écarter** pour le MVP (sauf si l'un d'eux expose une API JSON
analogue à bien'ici — à vérifier ponctuellement, mais ne pas en faire un pari).

### 3.4 Accumulation longitudinale (laisser tourner la collecte 6-12 mois)

Le flux d'annonces de la couronne, capté chaque semaine, s'**accumule** dans le
stock (rétention 24 mois). Une commune qui a peu d'annonces *à l'instant t* en
aura davantage *cumulées sur 6-12 mois*.

- **Effort** : nul (déjà en place). **Combiné à 3.1, l'accumulation porte sur un
  périmètre élargi → effet multiplicatif.**
- **Coût** : nul.
- **Risque** : aucun, sauf que les annonces anciennes vieillissent (prix de
  marché glissant) — la rétention 24 mois et la fraîcheur des snapshots limitent
  ce biais ; à surveiller si on veut pondérer par ancienneté plus tard.
- **Gain couronne** : réel mais **lent** (mois) et **plafonné** par l'étroitesse
  du marché communal. N'aide pas un bien atypique (#87 : maison 257 m²) pour
  lequel il n'y aura jamais de comparable strict.

**Reco : levier n°3, gratuit, à activer immédiatement EN COMBINAISON de 3.1.**
Seul, il ne résout pas la couronne assez vite pour lever la crainte « projet
vain ».

### 3.5 Partenariats agences locales (fourniture de données / mandats) — piste B2B

CONTEXT §2.4 / §3.4 évoque déjà le B2B agences. Une agence partenaire pourrait
fournir ses mandats (données structurées, fiables, fraîches) en échange de
visibilité / d'usage de l'outil.

- **Effort** : non technique (commercial, contractuel) — hors atelier d'agents.
- **Coût** : nul en infra.
- **Risque** : RGPD limité (données de biens, pas de personnes, si pas de
  coordonnées vendeur) ; dépendance commerciale ; ne change pas le biais
  annonce ≠ transaction (une agence fournit ses mandats, pas ses actes notariés).
- **Gain couronne** : potentiellement bon et fiable, mais **non actionnable par
  l'atelier** et incertain (dépend d'un accord humain).

**Reco : piste stratégique à instruire par le porteur/strategist, hors du
chantier technique immédiat.**

---

## 4. LE point d'arbitrage central — DVF (challenge adversarial)

DVF (Demande de Valeurs Foncières, open data Etalab / data.gouv.fr) est
**gratuit, légal (open data sous licence ouverte), et donne les PRIX DE
TRANSACTION RÉELS commune par commune** — soit précisément les deux choses qui
manquent : du volume communal ET la correction du biais annonce ≠ transaction
(§2.1). Or DVF est **interdit explicitement** : CONTEXT §1.2 (« S'appuyer sur des
données observables » vs « Utiliser DVF ou bases notariales »), §11.3-4 (« Pas de
DVF / notaires »), §11.4 (« Cassé le positionnement »), CLAUDE §1, et
`.claude/lessons.md` (invariant permanent). Challenge honnête, en quatre temps.

### 4.1 Pourquoi cet interdit existe (raison reconstruite)

La doc dit « casse le positionnement » sans détailler. En recoupant CONTEXT §1.1-1.4 :

1. **Différenciation produit.** Le produit est contre-positionné face aux
   estimateurs (MeilleursAgents, SeLoger estimation, etc.) qui exploitent DVF. Se
   définir par « cohérence sur données **observables d'annonces** » est ce qui le
   distingue ; mobiliser DVF le rapprocherait du peloton des estimateurs.
2. **Refus de l'estimation.** DVF est le carburant classique des modèles
   d'estimation de prix (« ce bien vaut X € »). L'interdit DVF est un **garde-fou
   par construction** contre la dérive vers l'estimation (CONTEXT §1.2, anti-pattern §11.1).
3. **Prudence juridique / éditoriale.** Le positionnement « juridiquement prudent »
   (CONTEXT §1.2) ; afficher un prix de transaction réel d'une adresse identifiable
   touche à la vie privée et au foncier nominatif — sensible.

L'interdit est donc d'abord un interdit de **POSITIONNEMENT** (ne pas devenir un
estimateur), renforcé par un garde-fou anti-dérive. Ce n'est pas un interdit
technique ni un interdit de licence (DVF est librement réutilisable).

### 4.2 « Comparables » (référence agrégée) ≠ « estimation » : y a-t-il une lecture compatible ?

Distinction clé que le porteur soulève à juste titre : le produit utilise DÉJÀ
des transactions/annonces individuelles en interne pour produire des **agrégats**
(médiane/Q1/Q3 d'un pool), et expose ces agrégats SANS estimer le bien analysé
(`market_stats.py` ne sort jamais un prix prédit, seulement un positionnement vs
distribution observée). Le pilier prix est déjà un comparateur agrégé, pas un
estimateur.

Sur ce plan strictement fonctionnel, **rien ne distingue une médiane calculée sur
des annonces bien'ici d'une médiane calculée sur des transactions DVF** : dans les
deux cas on produit un agrégat statistique, jamais une estimation du bien. Une
lecture existe donc où **DVF alimente la base de référence (agrégats communaux)
sans faire d'estimation ni de redistribution brute** :
- on ne re-publie pas les lignes DVF (pas de redistribution — conforme §11.3 qui
  autorise déjà le stockage interne par-annonce et n'expose que des agrégats) ;
- on ne prédit pas le prix du bien (pas d'estimation — §11.1) ;
- on s'en sert pour densifier les quartiles communaux, surtout en couronne.

**Donc l'incompatibilité n'est PAS technique ni statistique : elle est de
positionnement et de doctrine.** C'est tout l'enjeu de l'arbitrage. Trois nuances
qui empêchent l'analyste de trancher :

- DVF reste « bases notariales/foncières » au sens littéral de l'anti-pattern,
  même utilisé en agrégat. Lever l'interdit, même encadré, est un **changement de
  doctrine** qui dépasse l'analyste.
- Mélanger transactions (DVF) et annonces (scraping) dans un même pool de
  quartiles serait méthodologiquement douteux (deux natures de prix). Il faudrait
  soit des pools séparés, soit un usage de DVF en **contrôle/calage** plutôt qu'en
  mélange — décision de conception à instruire.
- La promesse marketing actuelle (« ce que j'observe sur le marché », hero
  CONTEXT §2.2) devrait être réécrite si DVF entre dans la référence.

### 4.3 Limites factuelles de DVF (ce n'est pas une solution magique)

- **Délai de publication ~6 mois** (semestriel) : DVF ne donne pas le marché
  *actuel*, il donne le marché *passé*. Pour de la « cohérence avec ce qu'on
  observe », c'est un décalage à assumer.
- **Pas de surface habitable fiable ni de DPE** : DVF donne surface bâtie/terrain
  cadastrale, pas la surface Carrez habitable ; le prix/m² DVF n'est donc pas
  directement comparable au prix/m² des annonces (qui se base sur l'habitable).
  Recoupement non trivial.
- **Pas de descriptif, pas de critères de confort** : aucun étage, terrasse, état
  — donc DVF ne nourrit QUE le grain prix communal, pas l'ancrage local ni la
  finesse confort (chantier C).
- **Granularité parcelle / adresse** : données par mutation rattachée à une
  parcelle ; agréger proprement à la commune et filtrer les ventes atypiques
  (multi-lots, dépendances) demande du nettoyage non trivial.
- **Volume** : un atout réel en couronne (toutes les ventes, pas seulement les
  annonces en cours), mais pour un bien atypique (#87) DVF ne fera pas de miracle
  non plus.

DVF corrige le biais annonce ≠ transaction et densifie la couronne, mais
introduit un biais de **fraîcheur** et un problème de **comparabilité prix/m²**.

### 4.4 Conclusion DVF (l'analyste ne tranche pas)

C'est une **décision de POSITIONNEMENT produit** qui dépasse l'analyste :
maintenir l'interdit strict (et accepter que la couronne reste faible sur les
seuls leviers §3), ou l'assouplir de façon encadrée (DVF en référence agrégée
communale, jamais en estimation ni redistribution) au prix d'une révision de
doctrine et de marketing. À remonter en GATE 1 comme **LA question structurante**,
à instruire ensuite par le strategist si l'humain ouvre la porte. Voir Q1.

---

## 5. OPTIONS chiffrées (combinaisons de leviers)

### Option 1 — Court terme, coût nul, sans toucher à la doctrine (RECO 1re intention)
Combine les leviers gratuits et sans nouveau risque :
- **3.1(a)** : boucler bien'ici sur les communes de `_METRO_CITIES` (≈0,5-1 j, +
  relever `timeout-minutes` de `collect.yml`) ;
- **3.4** : laisser accumuler (déjà actif), désormais sur périmètre élargi ;
- **3.2** : 1-2 scrapers d'agences couronne fetchables, si le recon en trouve.
- **Effort total** : ~1,5-3 j dev. **Coût** : nul. **Risque** : aucun nouveau
  (on reste dans le périmètre de scraping déjà accepté). **Gain couronne** :
  potentiellement structurant SI bien'ici a du volume réel en couronne (à
  mesurer — prérequis §9). Ne corrige PAS le biais annonce ≠ transaction.
- **Limite honnête** : si la mesure montre que bien'ici lui-même est creux en
  couronne (marché étroit), cette option ne suffit pas et l'on bute sur le mur DVF.

### Option 2 — Rupture encadrée : assouplir l'interdit DVF (DÉCISION HUMAINE)
DVF en **référence agrégée communale** (pools séparés ou calage), jamais en
estimation ni redistribution, marketing révisé.
- **Effort** : moyen-élevé (ingestion DVF, nettoyage, recomparabilité prix/m²,
  réécriture doctrine + UI). **Coût** : nul (open data). **Risque** : changement
  de positionnement, risque éditorial/juridique à border, dérive vers
  l'estimation à empêcher par garde-fous. **Gain couronne** : le plus fort et le
  seul qui corrige le biais transaction — c'est la réponse de fond à la crainte
  « projet vain ».
- **Ne PAS lancer sans arbitrage GATE 1.**

### Option 3 — Fiabilité d'abord (compléments aux deux)
Indépendant de la source : livrer l'**incrément 2 cross-agence** (clustering
photo) pour dédupliquer le multi-mandat (§2.1) — réduit la sur-représentation,
améliore la fiabilité des quartiles couronne (où le multi-mandat est fréquent)
sans nouvelle donnée. Effort moyen (déjà cadré, staging-first, CONTEXT §0).

### Recommandation séquencée (honnête)
1. **D'abord mesurer** (prérequis §9) : sans le volume réel par commune, on
   pilote à l'aveugle.
2. **Option 1 immédiatement** (gratuit, sans risque) — c'est le maximum
   atteignable à coût quasi-nul, et il peut suffire si bien'ici couvre la couronne.
3. **Remonter l'arbitrage DVF (Option 2) en GATE 1** en parallèle : c'est le seul
   levier qui adresse le **plafond de fiabilité** (transactions) et le seul qui
   garantit du volume communal si bien'ici s'avère creux en couronne.
4. Option 3 en complément de fiabilité quand la priorité passe de « plus » à
   « plus sûr ».

**Confrontation directe de la crainte « projet vain » (posture demandée) :** à
coût strictement MVP et SANS toucher à l'interdit DVF, **on ne peut PAS garantir**
que la couronne deviendra fiable. Le meilleur scénario gratuit (Option 1) dépend
entièrement du fait que bien'ici ait du volume réel sur ces communes — non
vérifié à ce jour. Si cette mesure est décevante, **aucun levier gratuit ne
densifiera un marché communal étroit**, et le biais annonce ≠ transaction restera
non corrigé quoi qu'il arrive. Dans ce cas, la seule réponse de fond est DVF (ou
un partenariat agences), c'est-à-dire un **choix de positionnement**, pas un
chantier technique. La crainte du porteur est donc légitime et ne doit pas être
édulcorée : la viabilité « couronne fiable » bute, à terme, sur l'arbitrage DVF.

---

## 6. Risques et anti-patterns (transverses)

- **Estimation déguisée** (§11.1) : aucun levier ne doit produire un prix prédit.
  Tous restent en agrégats. Vigilance si DVF entre (garde-fous explicites requis).
- **Redistribution** (§11.3) : ne jamais re-publier d'annonces ni de lignes DVF
  brutes ; agrégats seulement. Le stockage interne par-annonce reste autorisé.
- **Nouveau vendor / coût** (§3.2 CONTEXT) : écarter tout service anti-bot payant
  (portails §3.3). Rester < 1 €/mois.
- **ToS / robots.txt** : respecter les exclusions (déjà fait : herbeth,
  agencevalentin écartés). Ne pas contourner d'anti-bot (portails §3.3).
- **Rupture contrat API** (§11.9) : les leviers de COLLECTE ne touchent pas
  `/analyze` ; ils n'impactent que le stock. Pas de MAJ `lib/api.ts` requise tant
  qu'on ne change pas le schéma du pilier.
- **Robustesse job** : multiplier les communes/sources allonge `collect.yml`
  (timeout 15 min) → ajuster ; `push_comparables` ne s'arrête déjà plus sur un
  batch en échec (`push_comparables.py:82-91`).
- **Biais de mélange de natures de prix** (si DVF) : ne pas mélanger transactions
  et annonces dans un même pool de quartiles sans méthode.

---

## 7. QUESTIONS POUR L'HUMAIN (GATE 1)

1. **[STRUCTURANTE] DVF — maintien strict / assouplissement encadré / statu quo + autres leviers.**
   - (a) **Maintien strict** de l'interdit DVF : on se limite aux leviers §3
     (gratuits, sans risque), en assumant que la couronne reste plafonnée et que
     le biais annonce ≠ transaction n'est jamais corrigé.
   - (b) **Assouplissement encadré** : autoriser DVF UNIQUEMENT en référence
     agrégée communale (jamais estimation, jamais redistribution), avec révision
     de doctrine/marketing — à instruire par le strategist avant tout code.
   - (c) **Statu quo + autres leviers** : (a) + ouvrir la piste partenariat
     agences (§3.5, hors atelier).
   *Reco analyste : ne pas trancher ici, mais NE PAS lancer (a) seule sans avoir
   d'abord mesuré (Q3) — sinon on risque de constater trop tard que le gratuit ne
   suffit pas. Personnellement je remonte (b) comme la seule réponse de fond au
   « projet vain », à condition de l'encadrer strictement.*

2. **Élargissement bien'ici à la couronne (levier n°1).** Autorisez-vous à
   boucler le scraper bien'ici sur les communes de `_METRO_CITIES`
   (Marly, Saint-Julien, Scy-Chazelles, etc.) plutôt que la seule ville de Metz ?
   Et acceptez-vous d'ajuster `collect.yml` (timeout) en conséquence ?
   *Reco : oui — effort faible, coût nul, aucun nouveau risque, gain potentiellement
   structurant. À faire en premier.*

3. **[PRÉREQUIS] Mesure de couverture par commune.** Avant tout chantier,
   acceptez-vous une **probe read-only** (sur la base prod ou staging) comptant
   les comparables par (commune × type) sur la couronne, afin de savoir si le
   problème est « bien'ici ne ratisse pas la couronne » (réparable gratuitement,
   §3.1) ou « le marché communal est intrinsèquement étroit » (→ seul DVF/partenariat
   aide) ? Sans cette mesure, on pilote à l'aveugle.
   *Reco : oui, c'est le prérequis n°1. Probe simple, sans coût, sans exposition API.*

4. **Portails nationaux (seloger/leboncoin/...).** Confirmez-vous qu'on les
   ÉCARTE pour le MVP (JS-only / anti-bot / risque ToS / vendor payant), sauf si
   l'un expose une API JSON analogue à bien'ici (à vérifier ponctuellement) ?
   *Reco : oui, écarter ; ne pas engager d'effort de contournement anti-bot.*

5. **Nouvelles agences couronne (levier n°2).** Souhaitez-vous qu'on tente
   l'intégration de 1-2 agences supplémentaires listant en couronne (via le
   harnais `diagnose-scrapers.yml`), en sachant que le gisement facilement
   scrapable est en partie épuisé (gros réseaux bloqués/JS-only) ?
   *Reco : oui en parallèle, sans en attendre un effet volume massif (complément
   qualité : biens exclusifs).*

6. **Fiabilité : prioriser l'incrément 2 cross-agence (clustering photo) ?**
   Le multi-mandat (un bien chez plusieurs agences) sur-représente certains biens
   en couronne. Faut-il avancer l'incrément 2 pour dédupliquer, ou rester sur la
   priorité « volume » d'abord ?
   *Reco : volume d'abord (Q2/Q3), incrément 2 ensuite comme passe de fiabilité.*

7. **Partenariat agences (§3.5).** Souhaitez-vous instruire la piste B2B
   « fourniture de mandats » comme source de données couronne fiable et fraîche,
   sachant qu'elle est hors atelier (commerciale/contractuelle) ?
   *Reco : à porter par le porteur/strategist ; ne corrige pas le biais
   transaction mais densifie proprement la couronne.*

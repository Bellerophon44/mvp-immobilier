# cross-agence — PRÉREQUIS #0 (incrément 2) — RÉSULTATS & GO/NO-GO

> Mesure exécutée le **2026-06-11** sur un runner GitHub Actions (le sandbox de
> dev n'a pas d'egress), via `diagnose-scrapers.yml` (PR diagnostique #76, draft,
> non destinée au merge). Instruments : `scrapers/diagnose.py::cross_source_overlap_md`
> (gisement) et `scrapers/diag_bienici.py::field_audit_md` (faisabilité photos/agence).
> Réfs : `cross-agence-ANALYSE.md` §3 (#0), §4.4, §9.1.

---

## 0. Cadrage produit (clarifié 2026-06-11) — but réel = suivi LONGITUDINAL du prix

Le but de l'incrément 2 n'est **pas** « ce bien est simultanément chez deux agences
concurrentes » (cas concurrent, instant T — info marginale, utile surtout en cas de
prix différents). Le but est de **suivre l'évolution du prix d'un même bien physique
dans le temps**, alors qu'à un instant T il n'est jamais que chez **une seule agence** :

- **(1) Même agence, re-publication** (nouvelle annonce, nouveau prix) ;
- **(2) Changement d'agence** (delisté de A → relisté par B, nouveau prix).

**Pourquoi l'incrément 1 ne suffit pas** : il suit par **id stable PAR ANNONCE**. Un
bien re-listé reçoit un **nouvel id** → l'incrément 1 le voit comme neuf et **rompt la
continuité de prix**. L'incrément 2 doit **re-lier les annonces successives du même
bien** pour reconstruire la trajectoire.

**Où chaque signal est pertinent** (re-cartographie des mesures ci-dessous) :

| Cas | Continuité d'id (inc.1) | `reference` mandat | Photos |
|---|---|---|---|
| Même annonce, prix change | ✅ déjà couvert | — | — |
| (1) Même agence, re-list | ❌ rompue (nouvel id) | **souvent stable → dédup sans photo (inc.2a)** | renfort |
| (2) Changement d'agence | ❌ rompue | ❌ change (autre agence) | **✅ discriminant requis (inc.2b)** |

**Lecture importante** : les paires *concurrentes* mesurées en §2 (et la « découverte
structurante » bienici-agrégateur) sont **tangentielles** à ce but. Le signal réellement
pertinent est **temporel** (disparition → réapparition d'un même bien), que l'historique
de l'incrément 1 **commence justement à accumuler** — une mesure propre du taux de
re-list sera possible quand quelques semaines d'historique seront en base (probe à venir
sur snapshots successifs, pas sur un snapshot unique).

---

## 1. Partie B — Faisabilité du pivot photo (le « point dur » §3)

**VERDICT : ✅ FAISABLE — gate dur franchi.**

Audit sur 200 annonces bienici (`realEstateAds.json`, déjà téléchargé par la collecte) :

| Champ | Remplissage | Lecture |
|---|---|---|
| `photos` | **191/200 (95,5 %)**, **liste de 3** | URLs CDN directes (`media.apimo.pro/cache/…_1920-original.jpg`). **0 fetch HTML** : le pivot du matching est dans le JSON. |
| `photoWatermarkAlias` | 22/200 | Watermark présent sur une minorité (à anticiper, §5 robustesse pHash). |
| `accountType` | 200/200 = `agency` | Toujours su que c'est un mandat d'agence. |
| `accountDisplayName` | **22/200 (11 %)** | Nom d'agence lisible — **rare** : le wording « publié chez X » nommément ne couvrirait qu'~11 % (sinon repli « chez une autre agence »). |
| `reference` | 200/200 | Référence mandat — **signal de dédup quasi gratuit** (cf. §3). |
| `relatedAdsIds` | présent (rare) | bienici expose parfois des ids d'annonces liées. |
| `customerId` | 126/200 (63 %) | Identifiant compte annonceur (dédup intra-portail). |

**Conséquence** : l'effondrement redouté en §3/§4.1 (« sans photos en JSON → fetcher
17,4k pages HTML bloquées anti-bot → infaisable ») **n'a pas lieu**. Le surcoût de
l'incrément 2 se réduit au **download des images** (3/annonce) dans un job dédié,
pas à un scraping HTML de masse.

---

## 2. Partie A — Gisement (recouvrement inter-sources)

Scrape live des 5 sources (≈ contenu base) : **17 789 annonces**
(bienici 17 440 · benedic 238 · laveine_immo 71 · idemmo 23 · immoheytienne 17).

| Métrique | Valeur | Interprétation |
|---|---|---|
| Paires INTER-sources **strictes** (±2 % surface ET prix) | **519** | Signal honnête : quasi-jumeaux entre sources. ~149 % du parc agences (349) ⇒ chaque mandat agence a souvent un jumeau bienici. |
| Paires LARGES (±10 % surface, prix libre) | 141 184 | **Bruit** : densité du segment, PAS identité. À ignorer. |
| Annonces avec ≥1 candidat large | 92,6 % | Non significatif (même raison). |
| Doublons INTRA-bienici (type/quartier/surface±0.5 m²) | 13 550 dans 1 324 grappes | **Coarse, surévalue** : deux 70 m² au Sablon ≠ même bien. |

### Découverte structurante
bienici porte `accountType=agency` **et** des noms d'agences (`accountDisplayName`,
ex. « CENTURY 21 Atout Immobilier ») : **bienici est lui-même un agrégateur qui
syndique les mandats d'agences**. Les 519 paires strictes bienici↔agence sont donc
en grande partie **la même annonce des deux côtés** (mandat syndiqué), pas du
multi-mandat entre agences indépendantes.

### Ce que ça implique
- Les attributs seuls **ne peuvent pas** établir l'identité d'un bien (13 550 faux
  « doublons » coarse le prouvent) → **c'est exactement la justification des
  photos** comme discriminant (§5.2).
- Mais le « gisement cross-agence » au sens du produit (« aussi publié chez une
  agence **différente** ») est **plus étroit** qu'espéré : l'essentiel de la
  redondance est *bienici ↔ site propre de la même agence* (syndication) et
  *republications intra-bienici*, pas du vrai multi-mandat concurrent.

---

## 2bis. Partie C — Dédup EXACTE sans photo (probe #0bis)

Échantillon 1 000 annonces bienici (`dedup_signals_md`, 20 pages) :

| Identifiant | Mesure | Lecture |
|---|---|---|
| `reference` | 999/1000 rempli · **79 groupes partagés = 198 annonces (~20 %)** | Dédup mandat **sans photo** : capte ~10-20 % d'overlap intra-bienici. Sous-ensemble à prix identique (`FR344950 ×2` 33000, `FR327103 ×2` 10000) = fiable ; refs courtes (`67`, `1416179`) = bruit possible (collisions). |
| `customerId` | 588/1000 · **43 comptes distincts** | Top : `pericles-dumur` 87, `icr-57` 81, **`cabinet-benedic-montigny-groupe-benedic` 53** (= notre scraper benedic !), `immosky` 45. Confirme que **bienici syndique nos propres agences**. |
| `relatedAdsIds` | **1/1000** | Inexploitable (trop rare). |

**Conséquence** : une couche de dédup `reference` (+ `customerId` pour scoper),
**zéro image**, capterait déjà une part de la valeur « republication / depuis quand »
(prolongement direct de l'incrément 1). Les `customerId` montrent aussi que les
« matches » benedic↔bienici sont en grande partie **la même annonce syndiquée**,
pas du multi-mandat concurrent — ce qui réduit d'autant le gisement spécifique au
matching photo.

---

## 3. Recommandation GO/NO-GO (cadrée « suivi longitudinal du prix », §0)

**GO conditionnel, décomposé en 2a (sans photo) puis 2b (photo).**

1. **Faisabilité photo : GO.** Photos en JSON (95,5 %, 3 URLs CDN) → pipeline image
   réaliste, sans scraping HTML de masse. Le gate dur du chantier est levé — mais
   les photos ne servent que le cas (2) ci-dessous, pas tout l'incrément.

2. **Incrément 2a — re-link SANS photo (à livrer d'abord).** Cible le cas (1)
   « même agence, re-list » du §0. Mécanique :
   - À l'ingestion, quand un nouvel id apparaît, chercher un bien **récemment
     disparu** (absent du dernier passage) de **même `reference` + même
     `customerId`** (et attributs cohérents) → rattacher le nouvel id à la même
     **lignée de bien** et **prolonger la trajectoire de prix** par-dessus la
     rupture d'id.
   - Coût quasi nul, zéro image, zéro dépendance. Prolonge directement l'inc.1.
   - Mesuré : `reference` rempli à 99,9 %, `customerId` à ~59 % — clés exploitables.
   - **Garde-fou** : `reference` courtes/non uniques (`67`, `1416179`) → exiger
     `reference` + `customerId` (ou + attributs) pour éviter les collisions ;
     `relatedAdsIds` (1/1000) écarté.

3. **Incrément 2b — re-link PAR PHOTO (le seul cas où les photos paient).** Cible
   le cas (2) « changement d'agence » du §0 : nouvelle agence ⇒ `reference`
   différente ⇒ seules les **photos** (pHash) relient l'ancienne et la nouvelle
   annonce du même bien. Staging-first non négociable (§8), politique conservatrice
   §5.2 (Hamming ≤ 6/64, ≥ 2 photos distinctes, corroboration attributs, wording
   hedgé), seuils calibrés sur corpus réel (§4.4.3). Watermarks présents (22/200) à
   anticiper.

4. **Mesure du gisement RÉEL (temporel) à faire quand l'historique aura mûri.** Le
   prérequis #0 a été mesuré sur un **snapshot unique** : il prouve la faisabilité
   (photos, reference) mais **pas** le taux de re-list, qui est par nature temporel
   (disparition → réapparition). Dès que l'inc.1 aura accumulé quelques semaines de
   `first_seen`/`last_seen` + snapshots, ajouter une probe « taux de réapparition »
   (biens disparus puis revus sous un nouvel id, % via `reference` vs via attributs)
   pour dimensionner 2a et 2b sur du réel.

5. **Note marché (non bloquante)** : le cas « même bien, deux agences au même
   instant, prix différents » existe et a de la valeur, mais reste **secondaire**
   vs le suivi longitudinal ; il tombe gratuitement de 2b sans le viser.

**Prochaine étape proposée** : spécifier l'**incrément 2a** (re-link `reference`/
`customerId` à l'ingestion, prolongement de l'inc.1, zéro image) — c'est le pas le
plus rentable et le moins risqué, et il réduit le périmètre que 2b devra justifier.

---

## 4. Traçabilité
- Run : `diagnose-scrapers.yml` sur `claude/cool-mccarthy-WlDhm`, commentaire de la
  PR #76 (draft, `[NE PAS MERGER]`).
- Instruments : commit ajoutant `cross_source_overlap_md` (`diagnose.py`) et les
  sections Photos/Agence (`diag_bienici.field_audit_md`).
- Lecture seule, aucune écriture base, aucune dépendance nouvelle.

# cross-agence — PRÉREQUIS #0 (incrément 2) — RÉSULTATS & GO/NO-GO

> Mesure exécutée le **2026-06-11** sur un runner GitHub Actions (le sandbox de
> dev n'a pas d'egress), via `diagnose-scrapers.yml` (PR diagnostique #76, draft,
> non destinée au merge). Instruments : `scrapers/diagnose.py::cross_source_overlap_md`
> (gisement) et `scrapers/diag_bienici.py::field_audit_md` (faisabilité photos/agence).
> Réfs : `cross-agence-ANALYSE.md` §3 (#0), §4.4, §9.1.

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

## 3. Recommandation GO/NO-GO

**GO conditionnel, avec recadrage de la valeur de l'incrément 2.**

1. **Faisabilité : GO.** Photos en JSON (95,5 %, 3 URLs CDN) → le pipeline image
   est réaliste, sans scraping HTML de masse. Le gate dur du chantier est levé.
2. **Recadrage de la valeur (important).** La cible la plus rentable n'est pas
   « même bien chez deux agences concurrentes » (gisement étroit car bienici
   agrège déjà), mais :
   - **(a) dédup / republication** : relier les annonces du même bien dans le
     temps et entre bienici et le site propre de l'agence — pour fiabiliser
     « depuis quand sur le marché » et l'évolution de prix (prolonge directement
     l'incrément 1, déjà en prod) ;
   - **(b) détection de multi-mandat réel** quand il existe (deux agences
     distinctes) — bonus, volume probablement faible.
3. **Mesuré (Partie C) : la dédup sans photo capte déjà une part de (a).**
   `reference` (99,9 % rempli) donne ~20 % d'annonces en groupes partagés ;
   `customerId` scope par compte. `relatedAdsIds` est inexploitable (1/1000).
   → **Livrer d'abord une couche de dédup `reference`/`customerId` (zéro image)**
   comme incrément 2a : elle prolonge l'incrément 1 (republication, « depuis
   quand », évolution de prix) à coût quasi nul, et **réduit le périmètre** que le
   pipeline photo (incrément 2b) devrait justifier — désormais cantonné au
   multi-mandat à références différentes et au même-bien-référence-différente.
4. **Si l'on garde le pipeline photo** : staging-first non négociable (§8),
   politique conservatrice §5.2 (Hamming ≤ 6/64, ≥ 2 photos, corroboration
   attributs, wording hedgé), calibration des seuils sur corpus réel (§4.4.3).
5. **Wording « publié chez X »** : nom d'agence dispo à ~11 % seulement → prévoir
   le repli neutre « semble aussi publié ailleurs » par défaut (incrément 3).

**Prochaine étape proposée** : ajouter une probe `reference`/`customerId`/`relatedAdsIds`
(dédup exacte, 0 image) pour chiffrer la part de (a) captable sans photos, AVANT
d'arbitrer le pipeline image. C'est le complément naturel de ce prérequis #0.

---

## 4. Traçabilité
- Run : `diagnose-scrapers.yml` sur `claude/cool-mccarthy-WlDhm`, commentaire de la
  PR #76 (draft, `[NE PAS MERGER]`).
- Instruments : commit ajoutant `cross_source_overlap_md` (`diagnose.py`) et les
  sections Photos/Agence (`diag_bienici.field_audit_md`).
- Lecture seule, aucune écriture base, aucune dépendance nouvelle.

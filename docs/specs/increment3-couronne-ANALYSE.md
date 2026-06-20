# increment3-couronne — ANALYSE comparative (LECTURE SEULE) — Quel axe attaquer en premier ?

> Rôle : ANALYSTE (phase 1, lecture seule). Ce document cadre et challenge DEUX
> axes candidats pour l'incrément suivant du programme couronne, et recommande
> lequel attaquer en premier (ratio impact / effort / risque) AVANT la gate
> humaine. Aucune décision structurante n'est prise ici ; les arbitrages sont
> remontés en GATE 1.
>
> État du code lu au 2026-06-16. Réfs : `CONTEXT.md` §0/§9/§11, `backend/CLAUDE.md`
> §1/§5/§7/§8/§9/§12, `.claude/lessons.md`, `docs/specs/comparables-coverage-ANALYSE.md`,
> `docs/specs/bienici-couronne-SPEC.md`, `docs/specs/cross-agence-PREREQ0-RESULTATS.md`,
> `docs/specs/cross-agence-INCREMENT2B-ANALYSE.md`. Code ancré : `backend/scrapers/*`,
> `backend/ingestion/save.py`, `backend/db/models.py`, `backend/app/market_stats.py`,
> `backend/app/main.py`, `backend/tools/probe_cross_source.py`.
>
> Environnement d'analyse SANS egress réseau ni accès au volume Fly `/data` : tout
> chiffre par commune / par couple de sources est NON mesurable depuis ce repo et
> repris des probes documentées (probe couverture run 27473882571, PREREQ0
> 2026-06-11). Toute mesure manquante est listée en prérequis.

---

## 0. Mise à jour de l'état réel (ce qui a changé depuis comparables-coverage-ANALYSE)

Point d'attention fort : **`comparables-coverage-ANALYSE.md` §1.2 est désormais
PÉRIMÉ**. Il affirme que bien'ici ne collecte que la commune de Metz
(`city = "Metz"` en dur). Ce n'est plus vrai : le programme « bien'ici couronne »
est livré et en prod.

- `backend/scrapers/sources/bienici.py:306` : `communes: list[str] = _METRO_CITIES`
  (importé de `app.market_stats`, `bienici.py:16`). Le scraper itère désormais sur
  les 11 communes de la couronne (`bienici.py:308-348`), avec un `seen` global de
  dédup intra-run (`bienici.py:313`) et saut silencieux d'une commune non résolue
  (`bienici.py:316-319`).
- Index `ix_comparables_reference` + retry d'ingestion + collecte/probe
  paramétrables prod|staging : livrés (CLAUDE §8, `.claude/lessons.md` 2026-06-14).
- Probe de couverture opérationnelle : `GET /admin/comparables/coverage`
  (`backend/app/main.py:228`), workflow `coverage-probe.yml`.

Conséquence pour le présent arbitrage : le levier « élargir bien'ici » de l'ancienne
analyse (§3.1) est **consommé**. L'incrément suivant n'est donc plus « faire ratisser
la couronne par bien'ici » mais bien le choix entre **Axe A (dédup multi-mandat)** et
**Axe B (agences locales)** — les deux compléments restants de l'arbitrage GATE 1
précédent (`comparables-coverage-ANALYSE.md` §8.3).

---

## 1. AXE A — Dédoublonnage multi-mandat (re-link cross-source)

### 1.1 Ce qui existe DÉJÀ (fichiers:lignes)

Le suivi longitudinal d'un bien et le re-link ont été construits par paliers, tous
en prod sauf le dernier :

- **Incrément 1 (tracking temporel mono-source, EN PROD)** : id stable par annonce,
  `first_seen_at` / `last_seen_at` (`db/models.py:57-58`), table
  `listing_price_snapshots` (`db/models.py:81-96`), capture sans écrasement
  (`ingestion/save.py:147-231`), endpoint admin `/history`, rétention 24 mois +
  cascade snapshots (CLAUDE §9). Aucune exposition `/analyze`.
- **Incrément 2a (re-link MÊME agence par `reference`, EN PROD)** :
  `_find_lineage_candidate` (`ingestion/save.py:49-102`) rattache une annonce neuve
  à une lignée disparue de **même source** (`save.py:77`), même `reference`
  (`save.py:76`, indexée `db/models.py:70`), même `property_type`/`city`, surface
  ±2 % (`LINEAGE_SURFACE_TOLERANCE`, `save.py:38`), fenêtre 90 j (`save.py:37`).
  Pour bien'ici, `customer_id` requis et égal pour lever l'ambiguïté de référence
  (`save.py:68-71, 93-96`). Doctrine conservatrice : tout doute (≥2 candidats,
  référence triviale) → abstention, nouvelle lignée (`save.py:99-102`). `lineage_id`
  posé à l'ingestion (`save.py:159-166, 205`).
- **Incrément 2b étape 1 (capture des photos, EN PROD)** : `photo_urls` capté côté
  bien'ici (`bienici.py:192-225, 294`), porté par `PropertyListing`
  (`scrapers/models.py:33-36`), persisté (`db/models.py:78`, `save.py:204`).
  Métadonnée interne, jamais exposée.
- **Probe de gisement cross-source (read-only, livrée)** :
  `backend/tools/probe_cross_source.py` — estime par proxy d'attributs (surface
  ±10 %, même type/ville/postal, A disparu > 7 j → B apparu dans 180 j) un ordre de
  grandeur du re-list cross-source, **sans rien écrire**.

### 1.2 Le trou réel

Le trou est précis et déjà nommé dans `cross-agence-INCREMENT2B-ANALYSE.md` : un même
bien physique re-publié par une agence **différente** (source ≠, `reference` ≠,
`customer_id` ≠/absent, texte réécrit) n'a **aucun identifiant technique commun**. 2a
exige `source` identique (`save.py:77`) → il ne traite pas ce cas. La seule
corroboration forte restante est la **photo** (pHash), corroborée par attributs.

Sous-distinction importante (PREREQ0 §0) : deux cas se cachent derrière
« multi-mandat ».
- **Cas simultané** (un bien chez 2 agences en même temps) : gonfle le stock à un
  instant t → double-comptage dans `market_stats`.
- **Cas séquentiel** (delisté chez A, relisté plus tard chez B) : rompt la continuité
  de prix dans `/history`.

### 1.3 Impact attendu sur le produit

Deux effets distincts, à ne pas confondre :

- **Qualité des stats de prix (pilier prix /40)** : un bien en multi-mandat
  *simultané* est compté plusieurs fois dans les quartiles communaux
  (`market_stats._fetch_comparables`, `market_stats.py:109-143`). En couronne, où le
  pool est mince, quelques doublons pèsent davantage qu'à Metz. MAIS — point dur —
  `cross-agence-INCREMENT2B-ANALYSE.md` §6.2 pt 3 et §7 **interdisent explicitement**
  de dédoublonner `market_stats` via `lineage_id` : un faux cluster photo y
  fausserait les médianes, ce qui serait pire que le double-comptage actuel. **Donc
  Axe A, tel que doctriné, N'AMÉLIORE PAS les stats de prix** : il enrichit un
  historique admin-only (`/history`) et **révèle** le double-comptage sans le
  corriger. C'est le challenge central de cet axe (cf. §1.6 Q-A2).
- **Suivi longitudinal du prix (admin-only, non exposé)** : reconstruit la
  trajectoire de prix d'un bien qui change d'agence. Valeur réelle mais **invisible
  pour l'utilisateur** tant que l'exposition (incrément 3 / `/analyze`) n'est pas
  décidée — et elle ne l'est pas.

### 1.4 Effort estimé : **L** (large)

- Capture photo : déjà faite côté bien'ici (étape 1, prod). **Acquis.**
- Reste : download des bytes des images (~52k bootstrap, PREREQ0 §1 / INC2B §8),
  calcul pHash, stockage (table `photo_hashes` recommandée → ré-audit des 4 chemins
  de purge + cascade + reset conftest, leçon inc.1 2026-06-11), logique de matching
  (Hamming + vote ≥2 photos + corroboration attributs), gestion du cas simultané,
  calibration des seuils en staging (non faite).
- Dépendance Python nouvelle (Pillow ± imagehash) — rompt l'anti-pattern « zéro dep »,
  ne se désamorce que si confinée au job CI (INC2B §4).

C'est, de l'aveu même de l'analyse 2b (§0.4), **le plus cher et le plus risqué des
trois incréments cross-agence**.

### 1.5 Risques et anti-patterns

- **Faux positifs (risque produit dominant, INC2B §5)** : même immeuble (hall,
  façade, vue), photos de stock/plans, watermarks (22/200), recadrage qui casse le
  hash. Un faux cluster fusionne deux biens distincts → historique corrompu, sauts de
  prix aberrants. Doctrine : Hamming ≤ 6/64, ≥2 photos (jamais k=1), corroboration
  attributs obligatoire, seuils calibrés staging.
- **Download de masse d'images tierces (RGPD/ToS, INC2B §3.2)** : extraction NOUVELLE
  que ni inc.1 ni 2a n'ont franchie (droit sui generis des bases + charge CDN
  apimo.pro, ToS/hotlink [À VÉRIFIER]). Stocker le **hash** est dans l'esprit de
  CONTEXT §11.3 (empreinte non réversible, métadonnée interne) ; **télécharger les
  bytes** exige une décision humaine et un amendement de doctrine.
- **Anti-pattern « zéro dépendance »** (`requirements.txt` 7 lignes) — cf. effort.
- **Gisement non mesuré** : le taux de re-list cross-source *temporel* réel n'a
  **jamais** été mesuré (PREREQ0 §3.4, INC2B §0.4 pt 1). La syndication bien'ici (il
  ré-affiche nos propres mandats agences — `cabinet-benedic-montigny` est un
  `customerId` bien'ici, PREREQ0 §2bis) **masque** le vrai multi-mandat et est en
  partie déjà captée par 2a. On ne sait pas si le phénomène pèse 5 %, 1 % ou 0,1 %.
  **Construire le pipeline image le plus coûteux pour un phénomène non quantifié est
  le risque n°1.**

### 1.6 Dépendances

- Étape 1 (capture photo bien'ici) : **acquise** (prod).
- Prérequis avant tout code lourd : (a) **probe de gisement temporel** sur
  l'historique inc.1/2a qui mûrit (`tools/probe_cross_source.py` existe déjà, à faire
  tourner sur la prod après quelques semaines de recul) ; (b) calibration Hamming sur
  corpus staging ; (c) arbitrage humain RGPD/ToS download (INC2B Q3).

---

## 2. AXE B — Agences locales de la couronne (nouveaux scrapers HTML)

### 2.1 Ce qui existe DÉJÀ (fichiers:lignes)

Architecture scraper en **pattern registre**, conçue précisément pour ajouter une
source à faible coût :

- **Registre** : `scrapers/registry.py` — `@register("nom")` (`registry.py:12-17`) +
  `run_all()` (`registry.py:20-32`) qui exécute chaque source et **isole les pannes**
  (`try/except`, `registry.py:29-30` : une source qui crash n'arrête pas les autres).
- **Autoload** : `scrapers/sources/__init__.py::load_all()` importe tous les modules
  du package → une nouvelle agence = un fichier déposé, **sans éditer le job**
  (CLAUDE §9).
- **5 sources actives** : `bienici` (API JSON), `benedic`, `idemmo`, `immoheytienne`,
  `laveine_immo` (`scrapers/sources/site_local.py`) — toutes HTML sauf bien'ici.
- **Helpers partagés mutualisés** (`scrapers/base.py`) : `fetch_page`/`fetch_json`
  (retry/backoff 429/5xx), `polite_sleep`, `generate_stable_id`, `normalize_price`/
  `normalize_surface`, `infer_property_type`, `extract_district`, `canonical_city`/
  `canonical_district`, `extract_dpe`/`extract_construction_year`,
  `normalize_postal_code`. Un nouveau scraper HTML ne réécrit aucune normalisation.
- **Garde-fous d'ingestion centralisés** (`ingestion/save.py`) : bande prix/m²
  [800-12000] (`save.py:15-16, 133`), filtre dépt 57 (`save.py:32, 142-145`),
  blocklist hors-périmètre (`save.py:21-26, 138`). Toute nouvelle agence est protégée
  sans y penser.
- **Harnais de diagnostic en PR** : `diagnose-scrapers.yml` (sur PR touchant
  `scrapers/**`) → poste un rapport Markdown collant en commentaire de PR (comptage,
  villes, types, distribution prix/m², échantillon), rouge si une source renvoie 0
  (CLAUDE §9). Outil de recon : `scrapers/recon.py` (ausculte une URL : statut,
  présence prix HTML, classes CSS candidates).

Le gabarit type est court : un scraper HTML d'agence ≈ 90-125 lignes (cf.
`immoheytienne.py`, 125 lignes : sélecteurs CSS, pagination avec arrêt « plus de
nouvelle annonce », parsing défensif `try/except` → `None`).

### 2.2 Le trou réel

bien'ici, même élargi à la couronne, sous-représente structurellement les **maisons**
(~1 % pour Metz intra-muros, CLAUDE §11) et **les mandats exclusifs d'agence** (un
mandat exclusif chez une agence de Marly n'apparaît que sur le site de cette agence).
La couronne est précisément le territoire où la maison est le bien-type et où les
agences de proximité tiennent des exclusivités. Les agences déjà intégrées qui
ramènent des maisons sont peu nombreuses : `immoheytienne` (majoritairement maisons),
`laveine_immo` (quelques maisons limitrophes). Le trou est le **volume maisons
couronne via agences exclusives non encore scrapées**.

### 2.3 Impact attendu sur le produit

- **Couverture maisons couronne** : effet direct sur le segment le plus demandé par
  la cible et le moins couvert (`comparables-coverage-ANALYSE.md` §1.3). Contrairement
  à l'Axe A, l'Axe B **alimente réellement `market_stats`** (nouvelles lignes
  `comparables` dans le pool communal) → améliore le pilier prix /40 sur la couronne,
  réduit le recours au repli « métropole » (`_scope_warning`, `market_stats.py:273`,
  cause du faux-signal #87). C'est de la **densité utile et visible**.
- **Limite honnête** : gain **incrémental** — chaque agence = peu de biens (les
  agences déjà intégrées font ~17 à ~240 annonces chacune, PREREQ0 §2). On additionne
  des petits ; on ne reproduit pas l'effet de levier de bien'ici.

### 2.4 Effort estimé : **S à M par agence** (S si le prix est en HTML serveur,
M si pagination/JS partiel)

~0,5-1 j par agence : recon (`recon.py`/`diagnose.py --recon`) → écrire les sélecteurs
CSS → ouvrir la PR → lire le commentaire de diagnostic → corriger → merge quand vert.
Pas de dépendance nouvelle, pas de schéma DB, pas de migration. Boucle automatisée et
déjà rodée (4 agences HTML intégrées par ce chemin). Effort **fractionnable** : on
peut s'arrêter après 1 agence et avoir livré de la valeur.

### 2.5 Risques et anti-patterns

- **Fragilité des scrapers HTML** : un redesign du site casse les sélecteurs. Atténué
  par le harnais `diagnose-scrapers.yml` (rouge si 0 annonce) et le `try/except` de
  `run_all` (une source cassée n'abat pas la collecte), mais c'est une **dette de
  maintenance récurrente** qui croît linéairement avec le nombre d'agences.
- **Gisement facilement scrapable en partie épuisé** : le recon a déjà écarté herbeth,
  agencevalentin (robots.txt + HTTP 403), century21, orpi (JS-only) (CLAUDE §8). Les
  grosses enseignes sont bloquées ou JS-only (pas de Playwright, choix de minimalisme).
  Reste les agences de proximité, à fetchabilité variable.
- **robots.txt / ToS** : à vérifier au cas par cas — **règle, pas option** (respecter
  les exclusions, ne jamais contourner un anti-bot).
- **Périmètre & doublons** : géré par les garde-fous existants (dépt 57, prix/m²,
  `canonical_city`, id stable). Une agence couronne dont les biens sont aussi sur
  bien'ici crée du multi-mandat — ce qui **renvoie à l'Axe A** (les deux axes
  interagissent : plus d'agences = plus de multi-mandat potentiel).
- **Anti-patterns produit** : aucun risque d'estimation/DVF/redistribution (collecte
  d'agrégats, stockage interne) ; pas de nouveau vendor ni coût (runner GitHub) ;
  contrat `/analyze` non touché.

### 2.6 Dépendances

- Aucune dépendance bloquante. Le harnais, les helpers et l'ingestion sont en place.
- Prérequis léger : un **recon** des agences couronne candidates (lesquelles listent
  réellement des maisons à Marly/Montigny/Saint-Julien, et sont fetchables en HTML
  serveur) pour ne pas écrire un scraper qui rapporte 3 biens.

---

## 3. Comparaison synthétique

| Critère | Axe A — dédup multi-mandat | Axe B — agences couronne |
|---|---|---|
| Impact pilier prix /40 | **Nul** (doctrine interdit de dédoublonner `market_stats`) | **Direct et positif** (densité communale, maisons) |
| Impact couverture maisons | Nul (ne crée pas de données) | **Direct** (cœur du trou) |
| Valeur utilisateur visible | Aucune (admin-only, exposition non décidée) | Visible (meilleur pilier prix couronne) |
| Effort | **L** (download masse, pHash, table, calibration) | **S-M par agence**, fractionnable |
| Dépendances nouvelles | Pillow ± imagehash (rompt « zéro dep ») | Aucune |
| Risque dominant | Faux positifs + RGPD/ToS download + gisement non mesuré | Fragilité HTML + gisement scrapable partiellement épuisé |
| Prérequis bloquant | Probe gisement temporel + calibration + arbitrage RGPD | Recon des agences candidates (léger) |
| Réversibilité | Faible (infra lourde) | Forte (1 fichier par agence) |

---

## 4. RECOMMANDATION (argumentée)

**Attaquer l'AXE B (agences locales de la couronne) en premier.**

Raisons, par ordre de poids :

1. **Seul l'Axe B améliore le produit visible.** Le programme couronne vise à lever
   le faux-signal #87 (maison de couronne retombant sur la métropole). L'Axe B
   alimente directement `market_stats` sur la couronne, maisons comprises ; l'Axe A,
   par doctrine (`INCREMENT2B-ANALYSE` §6.2/§7), **n'a pas le droit** de toucher
   `market_stats` et reste admin-only sans exposition décidée.
2. **Ratio effort/risque très favorable.** L'Axe B est S-M, fractionnable, zéro
   dépendance, infra déjà rodée, réversible. L'Axe A est L, rompt « zéro dep »,
   franchit une ligne RGPD/ToS nouvelle, et **outillerait un phénomène non quantifié**
   (taux de re-list cross-source temporel jamais mesuré).
3. **Prérequis de l'Axe A non satisfaits.** L'Axe A ne devrait de toute façon pas être
   lancé d'un bloc : il exige d'abord une probe de gisement temporel (sur l'historique
   inc.1/2a qui mûrit), une calibration de seuils en staging, et un arbitrage humain
   sur le download de masse. Tant que ces prérequis ne sont pas levés, l'Axe A n'est
   pas « prêt à coder ».

**Nuance / posture adversariale honnête.** L'Axe B est lui aussi un gain
*incrémental* (on additionne des petites agences, gisement scrapable en partie
épuisé). Il ne « sauve » pas la couronne à lui seul — mais c'est le meilleur pas
disponible à coût MVP, et il faut le **subordonner à un recon préalable** (ne pas
écrire des scrapers qui rapportent 3 biens). Si le recon montre qu'aucune agence
couronne fetchable n'apporte de volume maisons significatif, alors le vrai mur est
ailleurs (densité de marché, biais annonces ≠ transactions non corrigeable à coût MVP
faute de DVF sur le 57, `comparables-coverage-ANALYSE.md` §8.1) — à remonter au
porteur sans l'édulcorer.

**Sur l'Axe A** : ne pas l'abandonner, le **séquencer après** et le **dégrouper**.
Première sous-étape cheap et sans risque dès maintenant : faire tourner
`tools/probe_cross_source.py` sur la prod pour mesurer le gisement réel, ce qui
décidera s'il vaut un jour l'infra image. Tant que ce chiffre est inconnu, engager le
pipeline pHash est prématuré.

---

## 5. QUESTIONS POUR L'HUMAIN (GATE 1)

1. **[STRUCTURANTE] Ordre des deux axes.**
   - (a) Axe B (agences couronne) d'abord, Axe A (dédup photo) différé et dégroupé.
   - (b) Axe A d'abord.
   - (c) Les deux en parallèle.
   *Reco : (a). Seul B améliore le produit visible, à effort/risque bien moindre ; A
   a des prérequis non levés (mesure, calibration, arbitrage RGPD).*

2. **[PRÉREQUIS B] Recon des agences candidates avant d'écrire du code.**
   Autorisez-vous un recon read-only (via `recon.py` / `diagnose-scrapers.yml`) des
   agences de proximité couronne (Marly/Montigny/Saint-Julien...) pour ne retenir que
   celles qui (i) listent réellement des maisons, (ii) sont fetchables en HTML serveur,
   (iii) ont un robots.txt permissif ?
   *Reco : oui. C'est le prérequis n°1 de B, coût quasi nul, évite d'écrire un scraper
   à 3 biens ou de heurter un robots.txt.*

3. **Combien d'agences viser pour ce premier incrément B (1-2 ou plus) ?**
   *Reco : viser 1-2 agences à fort signal maisons, livrables une par une via le
   harnais, sans promettre un effet volume massif (complément qualité).*

4. **[STRUCTURANTE — Axe A] Mesurer le gisement cross-source AVANT tout pipeline image.**
   Acceptez-vous que la première (et seule, à ce stade) action sur l'Axe A soit de
   faire tourner `tools/probe_cross_source.py` sur la prod (historique inc.1/2a qui a
   mûri), read-only, pour décider si le phénomène justifie un jour l'infra pHash ?
   *Reco : oui. Le taux de re-list temporel n'a jamais été mesuré ; sans lui, le
   pipeline image est un pari.*

5. **[DÉCISION HUMAINE — différée] Download de masse d'images tierces (Axe A).**
   Le calcul de pHash exige de télécharger les bytes de ~52k images (bootstrap) puis un
   delta hebdo — extraction nouvelle (droit sui generis + charge CDN apimo.pro) que ni
   inc.1 ni 2a n'ont franchie. Acceptez-vous d'instruire cet arbitrage (et l'amendement
   de doctrine CONTEXT §11.3 associé) seulement SI la probe Q4 montre un gisement réel ?
   *Reco : ne pas trancher maintenant ; conditionner à Q4. Stocker le hash est permis ;
   télécharger les bytes est la ligne nouvelle à arbitrer.*

6. **[Axe A] Double-comptage `market_stats` rendu visible par la dédup.**
   Confirmez-vous que, même si l'Axe A est mené, `market_stats` reste STRICTEMENT
   inchangé (pas de dédoublonnage par `lineage_id`), le double-comptage simultané étant
   documenté comme risque connu plutôt que corrigé par un matching photo faillible
   (`INCREMENT2B-ANALYSE` §7) ?
   *Reco : oui, conservateur. Un faux cluster dans le cœur statistique serait pire que
   le double-comptage actuel.*

7. **Interaction des deux axes.** Plus d'agences couronne (B) = plus de multi-mandat
   potentiel (bien aussi sur bien'ici) = plus de matière pour A. Acceptez-vous ce
   couplage assumé (B d'abord densifie, A plus tard nettoie si le gisement le justifie) ?
   *Reco : oui — c'est cohérent avec le séquencement (a) de Q1.*

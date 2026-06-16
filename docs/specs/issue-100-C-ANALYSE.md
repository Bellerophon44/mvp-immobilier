# Analyse de faisabilite — issue #100, chantier C (geocodage -> quartier reel, inter-communal, POI ecoles)

> Palier 3 (le dernier) du referentiel geographique : passer d'un rattachement
> par LIBELLE texte a un rattachement par COORDONNEES reelles, gerer nativement
> l'inter-communal (« Botanique » a cheval Metz / Montigny-les-Metz), et brancher
> les POI ecoles (C4, decision §0bis/§5 de l'analyse mere : retenu, factuel).
>
> Statut : analyse pre-GATE 1, LECTURE SEULE du code (ce document est le seul
> livrable ecrit ; aucun changement de comportement). Ne decide rien de
> structurant : remonte les arbitrages a l'humain.
>
> Sources relues avant redaction : `.claude/lessons.md` (toutes les entrees, dont
> index lookup par-ligne 2026-06-14, refactor pur / ordre / cycle d'import du
> chantier B) ; `docs/specs/issue-100-ANALYSE.md` (§4 palier 3, §6 #100-d, §8.4) ;
> `docs/specs/issue-100-B-ANALYSE.md` + `-B-SPEC.md` (gazetteer livre) ;
> `backend/CLAUDE.md` (§7, §10 contrat /analyze, §11 limitations ancrage local,
> §11bis roadmap A/B/C) ; `CONTEXT.md` (§1.4, §11) ;
> `docs/brand/LOCAL-ANCHORING.md`. Code reel cite en `fichier:ligne` (l'etat du
> code prime sur la doc).

---

## 0. TL;DR analyste — verdict de faisabilite

- **La couche de geocodage est DEJA en place et fonctionne.** `app/geocode.py`
  (BAN, cache, seuil score 0.4, garde-fou dept 57, repli silencieux),
  `metz_local.precise_distances_km` / `local_context_from_coords`
  (`metz_local.py:239-279`), branchement `analysis.py:189-197`, contrat front
  `precision in {quartier, adresse}` (`api.ts:38`, `page.tsx:565`). **Ce que C
  doit ajouter n'est PAS le geocodage** (fait depuis 2026-06-04, cf. CLAUDE
  §11bis) mais **la traduction coordonnees -> quartier/commune REELS** : ce
  maillon n'existe nulle part. Aujourd'hui, meme avec une adresse geocodee, le
  quartier reste celui resolu par TEXTE (`_resolve_district`, `analysis.py:78-92`)
  ; le geocodage ne sert qu'a calculer des distances aux 4 POI, jamais a
  identifier le quartier.

- **Le perimetre du brief est trop large pour un seul atelier.** Le palier 3 tel
  qu'enonce melange trois chantiers de natures et de risques tres differents :
  (C-geo) un mapping coordonnees->quartier (probleme de DONNEE : ou trouver des
  polygones de quartier, sous quelle licence) ; (C-inter) la reconciliation
  inter-communale (probleme de REQUETE : `Comparable.city` filtre en EXACT,
  `market_stats.py:108`) ; (C4-ecoles) une nouvelle source POI (probleme de
  DONNEE + entretien). **Recommandation forte : sous-decouper en au moins deux
  sous-paliers** (C-geo+inter d'abord, C4-ecoles ensuite), voire trois. Detail §6.

- **Le point le plus genant pour la credibilite : C n'apporte presque RIEN au cas
  pilote d'origine.** Le pilote n'avait PAS d'adresse, seulement « Sainte-Therese
  / Botanique » en texte colle. Or tout C repose sur une adresse geocodable
  (`analysis.py:189` : `geocode_address(addr, city) if addr else None`). Sans
  adresse -> branche `else` -> repli sur le profil de quartier, c'est-a-dire
  exactement ce que A (Sainte-Therese ajoutee) et B (gazetteer) ont DEJA livre.
  **C est un chantier pour les biens AVEC adresse, pas pour le cas pilote.** Il
  faut le dire au fondateur sans detour (analyse §5 ci-dessous).

- **Plusieurs anti-patterns en embuscade** : fake precision (un quartier devine
  par polygone affiche avec assurance ; distance vol d'oiseau != temps trajet,
  deja documente CLAUDE §11) ; dependance reseau a un 2e vendor (Overpass/IGN
  pour les ecoles, en plus de la BAN) ; licence des donnees (polygones quartier,
  ecoles) = decision humaine ; cout/latence sur le chemin `/analyze` ; RGPD si on
  stockait l'adresse (aujourd'hui non stockee — ne pas regresser).

- **Posture adversariale.** Le requirement est sain sur le fond (rattacher a un
  quartier reel est la bonne maniere de fiabiliser durablement), mais
  sur-dimensionne pour un MVP < 1 EUR/mois et mal cible sur le cas qui a declenche
  l'issue. La version a plus fort ROI/risque le plus faible : (a) **inter-communal
  Botanique** via un assouplissement cible du filtre `city` (petit, vrai gain
  data, le seul vrai « bug » de pool) ; (b) **rattachement coordonnees->commune**
  (gratuit : la BAN renvoie deja `city`/`citycode`/`postcode`, on ne l'exploite
  pas) AVANT d'investir dans des polygones de quartier intra-Metz. Les polygones
  de quartier et les ecoles sont les morceaux chers/risques : a isoler et a
  arbitrer separement.

---

## 1. Reformulation de l'objectif et perimetre (in / out)

### Objectif (palier 3, analyse mere §4)
Rattacher un bien a un quartier/commune **reels** a partir de coordonnees
geocodees (et non d'un libelle texte), pour : (1) robustesse aux libelles inconnus
; (2) gestion native de l'inter-communal ; (3) ouverture aux POI factuels
(ecoles). C s'appuie sur le geocodage existant et sur le gazetteer unifie par B.

### Les 4 sous-objectifs du brief, reformules avec leur nature reelle

| Sous-objectif | Nature du probleme | Ce qui manque aujourd'hui |
|---|---|---|
| 1. Geocodage -> quartier reel | DONNEE (polygones) + integration | aucun mapping coord->quartier ; `_POI` sont des POINTS (`metz_local.py:32-37`), pas des polygones |
| 2. Inter-communal Botanique | REQUETE (filtre city) | `_fetch_comparables` filtre `Comparable.city ==` EXACT (`market_stats.py:108`) ; pas de notion « quartier a cheval » |
| 3. Mapping coord->quartier | DONNEE (source + licence) | prerequis du 1 ; source a trancher (GATE 1) |
| 4. POI ecoles (C4) | DONNEE (2e vendor) + entretien | aucune base POI ecoles ; `_assess_one` type `ecoles` -> `A_VERIFIER` neutre (`metz_local.py:193-195`) |

### Perimetre IN (propose, a confirmer par GATE 1 et le decoupage §6)
- Exploiter la sortie geocodee pour determiner un **quartier/commune reels**
  (pas seulement des distances aux 4 POI).
- Reconcilier l'inter-communal au niveau du pool de comparables (Botanique).
- Eventuellement (sous-palier separe) brancher la proximite ecoles, factuelle.

### Perimetre OUT (a maintenir hors C, sauf decision contraire)
- Reecriture de `canonical_district` / `canonical_city` (valeur STOCKEE a
  l'ingestion, `bienici.py` ; risque MAJEUR herite de B, cf. B-ANALYSE §4).
- Stockage de l'adresse saisie (RGPD ; aujourd'hui non stockee — ne pas
  introduire de persistance nominative, §4).
- Routing isochrone / temps de trajet reel (deja note CLAUDE §11 comme
  optimisation distincte ; C reste sur du « a vol d'oiseau » etiquete).
- Estimation de prix, redistribution d'annonces, qualification « prise »
  (CONTEXT §11 ; « prise » deja FERME, analyse mere §0bis-2).
- Ajout de nouveaux quartiers au gazetteer (releve de A/B).
- Multi-villes / generalisation hors Metz (METZ-LOCAL §5, hors C).

---

## 2. Cartographie de l'impact reel dans le code

### 2.1 Ce qui EXISTE deja (et qu'on ne refait pas)

- **Geocodage** : `geocode_address(address, city_hint)` (`geocode.py:49-104`)
  renvoie `{lat, lon, score, label}` ou `None`. Cache memoire TTL 30j
  (`geocode.py:30-31`), seuil `_MIN_SCORE = 0.4` (`geocode.py:27`), garde-fou
  `_IN_SCOPE_DEPARTMENT = "57"` sur le `postcode` BAN (`geocode.py:28,85`), repli
  silencieux sur erreur reseau (`geocode.py:98-101`).
- **Distances exactes** : `precise_distances_km` (Haversine sur `_POI`,
  `metz_local.py:239-241`), `local_context_from_coords` (`metz_local.py:251-279`,
  pose `precision="adresse"`), `claim_distances_from_coords`
  (`metz_local.py:244-248`).
- **Branchement** : `analysis.py:189-197` — seul point d'appel du geocodage dans
  tout le backend (verifie par grep : `analysis.py:189` est l'unique site).
- **Contrat front** : `precision in {quartier, adresse}` (`api.ts:38`), champ
  adresse (`page.tsx:1105`), note « Distances a vol d'oiseau depuis l'adresse »
  (`page.tsx:565-566`), `AnalyzeRequest.address` accepte (CLAUDE §10).

### 2.2 Sous-objectif 1 & 3 — geocodage -> quartier reel : OU s'inserer

Le geocodage renvoie un point ; il faut le rattacher a un polygone de quartier.
Insertion naturelle : entre `geocode_address` (sortie lat/lon) et la resolution
du quartier.

- Aujourd'hui, le quartier est resolu par TEXTE dans `_resolve_district`
  (`analysis.py:78-92`), AVANT et INDEPENDAMMENT du geocodage. Le geocodage
  (`analysis.py:189`) ne fait qu'ajouter des distances ; il ne corrige jamais le
  quartier. **C doit inserer une etape `point_to_district(lat, lon)`** dont le
  resultat alimenterait `_resolve_district` avec une priorite a definir (GATE 1 :
  le geocode prime-t-il sur le selecteur manuel ? sur l'extraction LLM ?).
- `local_context_from_coords` (`metz_local.py:251-263`) prend deja un `district`
  en argument mais le recoit du resolveur texte (`analysis.py:192`) ; il
  faudrait lui passer le quartier DERIVE des coordonnees.
- **Le maillon manquant est une donnee** : `_POI` sont 4 points
  (`metz_local.py:32-37`), il n'existe aucun polygone de quartier. Soit on importe
  des polygones (GeoJSON quartiers IRIS/INSEE ou OSM) + un test point-in-polygon,
  soit on approxime par « quartier au centroide le plus proche » (les centroides
  sont justement le champ `centroid` PREVU mais VIDE du gazetteer,
  `geo_gazetteer.py:68`, `GazetteerEntry.centroid = None`).

### 2.3 Sous-objectif 2 — inter-communal Botanique : OU ca casse

- Le filtre est EXACT : `_fetch_comparables` fait
  `query.filter(Comparable.city == city)` (`market_stats.py:108`) quand `cities`
  n'est pas fourni. Un bien « Botanique » lu cote Metz (57000) ne verra jamais
  les comparables stockes cote Montigny-les-Metz (57950), et inversement.
- Montigny EST dans `_METRO_CITIES` (`market_stats.py:36-49`) mais seulement comme
  **filet metropole** (dernier niveau de cascade, `market_stats.py:179-182`),
  jamais comme « meme quartier que le bien ». La cascade
  quartier->secteur->ville->metropole (`market_stats.py:167-182`) ne modelise pas
  « quartier inter-communal ».
- Le commentaire `base.py:330-333` acte deja explicitement que Botanique N'EST
  PAS dans le referentiel curate et que « sa reconciliation cross-commune exige
  une adresse geocodee [...] : elle releve du chantier C ». **C'est donc le coeur
  ecrit du palier 3.** Techniquement, une fois le point geocode, on connait la
  commune REELLE (via BAN `city`/`citycode`) ; il faut alors autoriser
  `_fetch_comparables` a puiser dans un ENSEMBLE de communes pour un quartier
  inter-communal (le parametre `cities` existe deja, `market_stats.py:91,105-106`
  — l'infrastructure de requete multi-communes est en place, il manque la
  decision « quand l'activer »).

### 2.4 Sous-objectif 4 — POI ecoles : OU brancher

- `_assess_one` (`metz_local.py:156-195`) ne sait juger que
  `cathedrale/centre/gare/a31` ; tout le reste (dont `ecoles`) tombe sur
  `A_VERIFIER` neutre (`metz_local.py:193-195`). Le type `ecoles` est deja extrait
  par le LLM (`local_claims[].type`, CLAUDE §11bis couche B).
- Brancher les ecoles signifie : (a) une base POI ecoles avec coordonnees ; (b)
  un calcul de distance (Haversine, reutilisable) bien->ecole la plus proche ; (c)
  un rendu factuel (« ecole elementaire X a ~350 m ») SANS jugement « bien
  desservi/prise ». L'insertion suit le pattern `precise_distances_km` mais sur un
  jeu de POI bien plus grand (toutes les ecoles, pas 4 points) -> question de
  perf/structure (k-NN simple sur quelques centaines de points = trivial en
  memoire ; pas de lookup base par-ligne -> lecon index NON applicable si on
  reste en memoire).
- **Depend du geocodage** : sans coordonnees du bien, « ecole a 350 m » est
  impossible (au niveau quartier, on ne peut dire que « il y a N ecoles dans le
  quartier », ce qui est deja moins parlant). Donc C4 herite de la meme limite que
  C-geo : utile surtout AVEC adresse.

### 2.5 Schema `/analyze` et front

- Le contrat `precision in {quartier, adresse}` existe deja (`api.ts:38`). Si C
  ajoute un quartier DERIVE des coordonnees, deux options : (a) ne rien changer au
  schema (le quartier derive alimente `local_context.district`, deja present) ;
  (b) ajouter un marqueur de provenance (« quartier confirme par geocodage ») ->
  changement de contrat (MAJ `api.ts` obligatoire, leeson invariant §lessons).
- Ecoles : un nouveau `fact` dans `local_context.facts[]` (deja une liste libre
  `{label, value}`, `metz_local.py:266-270`) NE casse PAS le schema (structure
  generique). Un nouveau champ dedie (ex. `local_context.schools[]`) casserait le
  contrat -> MAJ front. Recommandation : passer par `facts[]` pour eviter une
  rupture de contrat.

### 2.6 DB / ingestion / CI

- **Aucune migration DB requise** pour C-geo et C-inter si on reste en memoire
  (polygones/centroides charges a l'import comme le gazetteer). `Comparable` a
  deja `city`, `district`, `postal_code` (CLAUDE §7).
- **Attention leeson index (2026-06-14)** : si une implementation faisait un
  lookup point-in-polygon ou un filtre nouveau PAR-LIGNE a l'ingestion
  (`ingestion/save.py`), il faudrait indexer/borner le cout. **A proscrire** : C
  doit rester une operation a l'ANALYSE (par requete utilisateur), pas a
  l'ingestion (par ligne x volume). Le geocodage est deja cote analyse uniquement
  (`analysis.py`), pas dans la collecte — preserver ce choix.
- **CI** : si C4 ajoute un vendor (Overpass/IGN), prevoir l'egress reseau (cf.
  §4) et eventuellement un cas d'eval ou un test de repli reseau.

---

## 3. Dependances et ordre

- **C depend de B (livre).** Le gazetteer (`geo_gazetteer.py`) porte deja les
  champs reserves a C : `centroid: Optional[Tuple[float,float]]` et `postal_code`
  (`geo_gazetteer.py:67-68`), VIDES (decision B : remplis en C). C est donc le
  consommateur prevu de ces champs. **Prerequis : remplir les centroides** (au
  minimum) si l'on choisit l'approche « commune au centroide le plus proche »
  plutot que des polygones.
- **C-inter (Botanique) ne depend PAS de polygones de quartier.** Il depend
  d'une chose plus simple : connaitre la COMMUNE reelle du point (la BAN la
  renvoie deja : `city`, `citycode`, `postcode` — aujourd'hui on ne lit que
  `postcode` pour le garde-fou dept, `geocode.py:84`). On peut donc livrer
  l'inter-communal AVANT le mapping quartier complet. **Ceci est un argument fort
  pour le sous-decoupage** (§6).
- **C4 (ecoles) depend du geocodage** (coordonnees du bien) mais PAS du mapping
  quartier ni de l'inter-communal. C'est un module orthogonal : il peut etre fait
  avant ou apres C-geo. Vu son cout (2e vendor, entretien), le mettre EN DERNIER.
- **Prerequis externe (deja note CLAUDE §11bis)** : l'egress HTTPS vers la BAN
  doit etre autorise en prod (Fly) ET en CI/atelier. Si C4 ajoute Overpass/IGN, un
  2e domaine d'egress a autoriser. **Signaler : a verifier avant de coder** (sinon
  repli silencieux permanent = feature invisible, faux-vert possible en eval).

Ordre recommande : **C-inter (Botanique + commune reelle) -> C-geo (quartier reel
intra-Metz) -> C4 (ecoles)**. Justification : valeur data decroissante, risque et
cout croissants ; le premier est presque gratuit (exploiter une donnee BAN deja
recue), le dernier introduit un vendor.

---

## 4. Risques et anti-patterns

1. **[MAJEUR] Fake precision sur le quartier derive (CONTEXT §1.4).** Un point
   geocode pres d'une frontiere de quartier, rattache par « centroide le plus
   proche » ou par un polygone imparfait, peut afficher un quartier FAUX avec
   l'assurance du « adresse geocodee » (`precision="adresse"`). C'est exactement le
   defaut C2 (« confiant mais faux ») que A a du corriger par un garde-fou. Le
   garde-fou C2 (`metz_local.py:96-99,229-234`) ne couvre PAS ce cas (il ne traite
   que l'override manuel non corrobore, branche sans geocodage). **Mitigation a
   specifier** : ne rattacher a un quartier que si le point est franchement a
   l'interieur (marge) ; sinon rester « commune » sans quartier. A trancher.

2. **[MAJEUR] Distance vol d'oiseau != temps de trajet (CLAUDE §11).** Deja
   documente et etiquete cote front (`page.tsx:566`). C4 (ecoles) AGGRAVE le
   risque : « ecole a 350 m » suggere « 4 min a pied » alors qu'une riviere/voie
   ferree peut imposer un detour. **Mitigation** : garder l'etiquette « a vol
   d'oiseau », ne jamais convertir en minutes sans routing.

3. **[MAJEUR] Licence des donnees = decision humaine (GATE 1).**
   - Polygones de quartier : OSM (ODbL, share-alike — contraintes d'attribution
     et de partage), IRIS/INSEE (licence ouverte, mais les IRIS != quartiers
     « grand public »), ou trace manuel (cout, mais 100% maitrise). C'est un choix
     vendor/licence a remonter.
   - Ecoles : Annuaire de l'Education Nationale (data.gouv, Licence Ouverte —
     plutot sain) vs Overpass/OSM (ODbL). Decision humaine.

4. **[MOYEN] Nouveau vendor / dependance reseau (CONTEXT anti-patterns).** Tout
   appel runtime a Overpass/IGN ajoute une dependance externe sur le chemin
   `/analyze` (latence + point de panne). **Mitigation** : preferer une donnee
   IMPORTEE A FROID (snapshot d'ecoles commite/charge a l'import, comme le
   gazetteer) plutot qu'un appel live. Idem polygones : un GeoJSON local, pas un
   service de tuiles runtime.

5. **[MOYEN] Cout / latence sur `/analyze` (MVP < 1 EUR/mois).** Le geocodage BAN
   est gratuit et cache. Un appel POI live ne le serait pas forcement (quota
   Overpass). Le point-in-polygon en memoire est negligeable. **Eviter tout appel
   reseau supplementaire synchrone** dans `/analyze` au-dela de la BAN deja
   presente.

6. **[MOYEN] RGPD — ne pas regresser.** Aujourd'hui l'adresse saisie n'est PAS
   stockee (elle transite, sert au geocodage, est affichee, point ; aucune table
   ne la persiste — verifie : pas d'ecriture d'adresse). Le geocodage BAN envoie
   l'adresse a un service public francais (data.gouv) ; acceptable mais a garder a
   l'esprit. **Garde-fou** : C ne doit creer AUCUNE persistance d'adresse ni de
   coordonnees nominatives (le cache geocode est en memoire, par adresse
   normalisee, perdu au restart — OK). Si un jour on cache en SQLite (suite notee
   CLAUDE §11), re-evaluer.

7. **[MOYEN] Rupture de contrat API.** Ajouter un champ dedie (quartier confirme,
   `schools[]`) casse le schema `/analyze` -> MAJ `frontend/lib/api.ts`
   obligatoire (invariant lessons.md « jamais casser le schema sans MAJ api.ts »).
   **Mitigation** : passer par les structures generiques existantes
   (`local_context.facts[]`, `local_context.district`) tant que possible.

8. **[FAIBLE] Leeson index lookup par-ligne (2026-06-14).** NON applicable si C
   reste en memoire et a l'analyse. DEVIENT applicable si quelqu'un ajoute un
   filtre/lookup geographique PAR-LIGNE a l'ingestion -> a proscrire explicitement
   dans la future spec.

9. **[FAIBLE] Refactor pur vs changement de comportement.** Contrairement a B
   (refactor pur), C est un CHANGEMENT DE COMPORTEMENT (le quartier resolu peut
   changer pour un bien avec adresse ; le pool de comparables peut changer pour
   Botanique). Donc : goldens de NON-regression sur les cas SANS adresse (le
   comportement A/B doit rester identique), + nouveaux cas pour les cas AVEC
   adresse. Eval LLM pertinente ici (contrairement a B).

10. **[FAIBLE] Cycle d'import (leeson 2026-06-16 chantier B).** Si une nouvelle
    structure (polygones, ecoles) est derivee au top-level et importe
    `scrapers.base`/`geo_gazetteer`, re-verifier que chaque module s'importe en
    premier sans cycle (`python -c "import <module>"`).

---

## 5. Point critique : que vaut C pour le cas pilote (qui n'a PAS d'adresse) ?

C'est le point que le brief demande d'analyser sans complaisance.

- **Le cas pilote n'avait pas d'adresse** : seulement « Sainte-Therese /
  Botanique » en texte colle. Le flux est : `analysis.py:187` `addr = ""`
  -> `analysis.py:189` `geo = None` -> branche `else` (`analysis.py:198-219`) ->
  `local_context(district, ...)` au niveau quartier. **Tout C-geo et C4 sont
  inertes sans adresse.**
- **Ce que A/B ont DEJA livre pour ce cas** : Sainte-Therese est dans le gazetteer
  (`geo_gazetteer.py:107-124`), avec profil, distances, secteur propre, alias
  « / » (`Sainte-Therese-/-Botanique`, `geo_gazetteer.py:112`). Donc « Sainte-
  Therese / Botanique » en texte est DEJA reconnu (via `_resolve_key` ->
  `_ALIASES`) et produit un contexte local correct. **Le constat #100 d'origine
  est leve par A, pas par C.**
- **Donc qu'apporte C au cas pilote ? Quasi rien en l'absence d'adresse.** Le seul
  apport theorique : si l'utilisateur SAISIT une adresse (champ « Preciser »,
  `page.tsx:1105`), alors C-geo confirmerait/corrigerait le quartier et C-inter
  irait chercher les comparables des deux communes pour Botanique. Mais ce n'est
  plus le « cas pilote » (texte sans adresse) : c'est un usage enrichi.
- **Conclusion adversariale.** C ne doit PAS etre justifie par le retour pilote
  #100 (deja traite). Il se justifie par : (1) le **bug de pool inter-communal**
  (reel, mesurable, independant du pilote — Botanique et toute frange communale) ;
  (2) la **robustesse generale** aux libelles inconnus quand une adresse existe.
  Si le fondateur attend que C « finisse de regler le cas Botanique du pilote »,
  il faut clarifier : **sans adresse, C n'ajoute rien que A/B n'aient deja fait** ;
  avec adresse, C ajoute le bon pool de comparables. Le sous-palier le plus
  defendable est donc **C-inter** (corrige un vrai biais de donnee), pas le
  mapping quartier complet ni les ecoles.

---

## 6. Decoupage recommande (posture MVP)

Le palier 3 monolithique (« geocodage->quartier + inter-communal + polygones +
ecoles ») est trop lourd et melange donnee/requete/vendor. Decoupage propose, du
meilleur ROI/risque au plus cher :

- **Sous-palier C1 — Inter-communal & commune reelle (recommande EN PREMIER).**
  Exploiter `city`/`citycode`/`postcode` deja renvoyes par la BAN (aujourd'hui
  seul `postcode` est lu, `geocode.py:84`) pour : (a) connaitre la commune REELLE
  du bien ; (b) autoriser `_fetch_comparables(cities=...)` (parametre existant,
  `market_stats.py:91`) a couvrir un quartier inter-communal (Botanique
  Metz+Montigny). Petit, pas de nouveau vendor, vrai gain data. Changement de
  comportement -> goldens + cas de test. C'EST le coeur ecrit du palier 3
  (`base.py:330-333`).

- **Sous-palier C2 — Quartier reel intra-Metz par coordonnees.** Remplir les
  `centroid` du gazetteer (`geo_gazetteer.py:68`) et/ou importer des polygones de
  quartier ; rattacher le point au quartier ; alimenter `_resolve_district`. Plus
  cher (donnee + licence + risque fake precision). A faire seulement si le gain
  est juge superieur au risque (GATE 1). Requiert le garde-fou anti-fake-precision
  (§4-1).

- **Sous-palier C3 — POI ecoles (C4 du brief).** 2e source de donnee (Annuaire de
  l'Education recommande, licence ouverte), snapshot importe a froid (pas d'appel
  live), rendu factuel via `facts[]`. EN DERNIER : utile surtout avec adresse,
  cout d'entretien, pas lie au pilote.

Chaque sous-palier = une spec, un lot de tests, un GATE. Cela evite l'atelier
monolithique et permet d'arreter apres C1 si le ROI des suivants est juge
insuffisant pour un MVP.

---

## 7. OPTIONS chiffrees (choix structurants)

### Option A — Source du mapping coordonnees -> quartier (sous-palier C2)
- **A1. Centroides + plus proche voisin.** Remplir `centroid` dans le gazetteer
  (17 points), rattacher le bien au quartier au centroide le plus proche.
  *Avantages* : trivial, pas de donnee externe, pas de licence, en memoire.
  *Inconvenients* : faux pres des frontieres (fake precision), ignore la forme
  reelle des quartiers, mauvais pour les quartiers etendus/concaves.
- **A2. Polygones GeoJSON (OSM ODbL ou IRIS/INSEE Licence Ouverte).**
  point-in-polygon en memoire. *Avantages* : rattachement correct, gere les
  formes reelles, base de C-inter (un polygone peut chevaucher 2 communes).
  *Inconvenients* : donnee + licence (ODbL share-alike pour OSM ; IRIS != decoupage
  grand public), entretien, mapping IRIS<->quartiers gazetteer a etablir.
- **Reco** : si C2 est retenu, **A2 avec IRIS/INSEE (Licence Ouverte)** pour
  eviter le share-alike d'OSM, OU A1 comme approximation HONNETE assortie d'une
  marge (ne rattacher que si nettement a l'interieur, sinon « commune » sans
  quartier). A1 est moins risque pour un MVP si on accepte de ne pas rattacher les
  cas-frontiere. Decision humaine.

### Option B — Source POI ecoles (sous-palier C3)
- **B1. Annuaire de l'Education Nationale (data.gouv, Licence Ouverte).**
  Snapshot importe a froid. *Avantages* : officiel, factuel, licence ouverte
  (pas de share-alike), pas d'appel live. *Inconvenients* : a rafraichir
  periodiquement (peu frequent).
- **B2. Overpass / OSM (ODbL).** *Avantages* : riche, requetable. *Inconvenients*
  : ODbL share-alike, appel live (latence/quota) ou snapshot a maintenir, 2e
  vendor reseau.
- **Reco** : **B1 (Annuaire EN), snapshot importe a froid.** Licence saine, pas de
  dependance reseau runtime, factuel.

### Option C — Activation de l'inter-communal (sous-palier C1)
- **C1a. Table de quartiers inter-communaux curatee.** Declarer dans le gazetteer
  qu'un quartier (Botanique) couvre {Metz, Montigny} -> `_fetch_comparables`
  utilise `cities` pour ce quartier. *Avantages* : maitrise, explicite, petit.
  *Inconvenients* : curation manuelle (mais 1-2 cas connus seulement).
- **C1b. Generique par geocodage** : si le point est a < X m d'une frontiere
  communale, inclure les deux communes. *Avantages* : automatique.
  *Inconvenients* : fake precision inverse (inclure une commune a tort dilue le
  pool), seuil arbitraire.
- **Reco** : **C1a (curation, quelques cas)** — fidele a la philosophie « 100%
  curate/verifiable » du referentiel, faible surface, pas d'arbitraire.

---

## 8. Synthese

- **Faisable techniquement** : l'infrastructure (geocodage, Haversine, parametre
  `cities` multi-communes, champs `centroid`/`postal_code` reserves) est deja en
  place. Le manquant est de la DONNEE (polygones, ecoles) et des DECISIONS
  (licence, vendor, priorite de resolution, garde-fou fake precision).
- **Mal cible sur le pilote** : sans adresse, C n'ajoute rien que A/B n'aient
  livre (§5). Le justifier par le bug de pool inter-communal (reel) et la
  robustesse, pas par le retour #100.
- **Sur-dimensionne en un seul atelier** : sous-decouper en C1 (inter-communal,
  presque gratuit), C2 (quartier reel, cher/risque), C3 (ecoles, vendor) — §6.
- **Anti-patterns en embuscade** : fake precision (quartier devine, distance vol
  d'oiseau), 2e vendor/egress, licence donnees, rupture de contrat API, RGPD (ne
  pas persister d'adresse). Aucun bloquant si on reste en memoire, a froid, a
  l'analyse, via les structures de contrat existantes.

---

## QUESTIONS GATE 1 (arbitrages reserves au fondateur)

**Q1 — Decoupage : un seul atelier ou sous-paliers ?**
Options : (a) chantier C monolithique (geo+quartier+inter-communal+ecoles) ;
(b) sous-decoupe en C1 inter-communal -> C2 quartier reel -> C3 ecoles, chacun
sa spec/son GATE (§6).
*Reco* : **(b)**. C melange donnee/requete/vendor de risques tres differents ;
le monolithe maximise la surface et le risque pour un MVP < 1 EUR/mois.

**Q2 — Perimetre minimal credible : s'arreter ou ?**
Options : (a) livrer seulement C1 (inter-communal Botanique + commune reelle),
juger le ROI des suivants apres ; (b) livrer C1 + C2 (quartier reel) ;
(c) tout (C1+C2+C3).
*Reco* : **(a) C1 d'abord**. C'est le seul vrai bug de DONNEE (pool inter-communal),
quasi gratuit (exploiter `city`/`citycode` deja renvoyes par la BAN,
`geocode.py:84`), et c'est le coeur ecrit du palier (`base.py:330-333`). C2/C3
sont des ameliorations cheres a arbitrer ensuite.

**Q3 — Cas pilote sans adresse : assume-t-on que C n'y change rien ?**
Le cas pilote (texte « Sainte-Therese / Botanique », sans adresse) est DEJA traite
par A/B (§5). C n'apporte de valeur qu'AVEC une adresse saisie.
Options : (a) assumer C comme un chantier « biens avec adresse » + bug de pool,
deconnecte du pilote ; (b) chercher a ameliorer le cas sans adresse (mais sans
geocodage, il n'y a pas de levier nouveau cote C).
*Reco* : **(a)**. Acter que le pilote est clos par A ; C se justifie par le pool
inter-communal et la robustesse, pas par #100.

**Q4 — Source du mapping coordonnees -> quartier (si C2 retenu).**
Options : (A1) centroides + plus proche voisin (en memoire, pas de licence, mais
fake precision aux frontieres) ; (A2) polygones GeoJSON IRIS/INSEE (Licence
Ouverte) ou OSM (ODbL share-alike), point-in-polygon (§7-A).
*Reco* : **A2 avec IRIS/INSEE (Licence Ouverte)** si C2 est retenu, OU A1 comme
approximation HONNETE qui ne rattache PAS les cas-frontiere (reste « commune »).
Eviter OSM (share-alike) si possible. Decision licence = humaine.

**Q5 — Source POI ecoles (si C3 retenu) + mode d'acces.**
Options : (B1) Annuaire de l'Education Nationale (data.gouv, Licence Ouverte),
snapshot importe a froid ; (B2) Overpass/OSM (ODbL), live ou snapshot (§7-B).
*Reco* : **B1, snapshot importe a froid** (licence saine, zero dependance reseau
runtime, factuel). Pas d'appel live sur `/analyze`.

**Q6 — Activation de l'inter-communal (C1).**
Options : (C1a) table curatee de quartiers inter-communaux dans le gazetteer
(Botanique = {Metz, Montigny}) ; (C1b) regle generique « point a < X m d'une
frontiere -> deux communes » (§7-C).
*Reco* : **C1a (curation)** — fidele au « 100% curate/verifiable », faible surface,
pas de seuil arbitraire (1-2 cas connus).

**Q7 — Comportement quand le geocodage echoue / pas d'adresse (repli).**
Aujourd'hui : repli silencieux sur le profil de quartier, sans signalement
(`analysis.py:198`, choix assume CLAUDE §11). C ajoute des chemins (commune reelle,
quartier derive) qui peuvent aussi echouer.
Options : (a) garder le repli SILENCIEUX (ne pas inquieter) ; (b) signaler
discretement « localisation approximative (quartier) » quand on n'a pas pu
geocoder.
*Reco* : **(a) silencieux**, coherent avec l'existant et « pas de fake precision »
(on ne sur-promet pas), MAIS verrouiller par test que l'absence d'adresse/echec
geocode = comportement A/B identique (non-regression).

**Q8 — Garde-fou fake precision sur le quartier derive par coordonnees (si C2).**
Un point pres d'une frontiere peut etre rattache a un quartier FAUX affiche avec
assurance (`precision="adresse"`). Le garde-fou C2 actuel
(`metz_local.py:229-234`) ne couvre PAS ce cas.
Options : (a) ne rattacher a un quartier que si le point est nettement a
l'interieur (marge), sinon rester « commune » ; (b) rattacher toujours au plus
proche (risque fake precision).
*Reco* : **(a) marge / abstention pres des frontieres**. Coherent avec « la
promesse ne depasse pas la maturite de la donnee » (LOCAL-ANCHORING).

**Q9 — Prerequis egress reseau (a verifier AVANT de coder).**
La BAN doit etre joignable en prod (Fly) et en atelier (sinon repli permanent =
feature invisible). Si C3 ajoute un 2e vendor live, idem.
Options : (a) confirmer l'egress BAN + tout 2e vendor avant la spec ; (b) coder
puis decouvrir le blocage.
*Reco* : **(a)**. Verifier l'egress avant l'atelier ; preferer des donnees
importees a froid (Q5) pour eliminer la dependance runtime des ecoles.

# Analyse — Contexte local v2 (Ancrage local, qualite d'info) — volets A+B+C+D

> Role : ANALYSTE (cadrage + challenge). Lecture seule du code, ecriture de ce
> seul document. Sources relues avant redaction : `.claude/lessons.md` (toutes
> les entrees, dont cycle d'import 2026-06-16 issue-100-B, faux-vert 9.10,
> caches globaux 9.7 / photo-evidence, isolation DB 9.7, BAN/egress CLAUDE
> §11bis) ; `backend/CLAUDE.md` (§1 anti-patterns, §5 endpoints, §7 donnees, §10
> contrat, §11/§11bis) ; `CONTEXT.md` (§0, §3 couts, §11 anti-patterns) ;
> `docs/specs/issue-100-C-SPEC.md` et `docs/specs/issue-100-C-ANALYSE.md`
> (§2.4, §6, Option B) ; et le code reel (`app/metz_local.py`, `app/analysis.py`,
> `app/geocode.py`, `app/geo_gazetteer.py`, `app/main.py`, `app/rate_limit.py`,
> `frontend/lib/api.ts`, `frontend/app/page.tsx`).
>
> Branche de dev : `claude/trusting-gauss-boi5lr`. Perimetre decide avec le
> fondateur : COMPLET (A+B+C+D), livre en un lot. Cette analyse cadre, decoupe et
> remonte les decisions ; elle ne specifie pas la solution et ne tranche rien de
> structurant.

---

## 0. Reformulation de l'objectif et perimetre

### Objectif
Ameliorer la **qualite d'information** de la section non-scoree « Contexte local »
sur quatre fronts :
- **A** : retirer une ligne generique sans valeur propre en mode quartier
  (l'« Axe A31 / Luxembourg » identique pour toutes les annonces) ;
- **B** : separer le Centre Pompidou-Metz de la gare pour obtenir 4 facts
  distincts (cathedrale, gare, Pompidou, A31/echangeur) ;
- **C** : remplacer/completer la distance « a vol d'oiseau » par des **temps de
  trajet reels** (Google Routes API, Compute Route Matrix) en mode adresse, avec
  un calcul paresseux (un mode par defaut a l'analyse, modes alternatifs a la
  demande), etiquetage honnete et repli silencieux sur Haversine ;
- **D** : afficher la **distance aux ecoles les plus proches** (sous-chantier C3
  deja analyse), via un snapshot Annuaire Education Nationale importe a froid,
  k-NN en memoire, rendu factuel sans jugement de valeur, mode adresse seulement.

### Perimetre IN
- Modification du rendu des `facts[]` du Contexte local (A, B).
- Nouveau module de routing Google + aiguillage defaut/a-la-demande (C).
- Snapshot ecoles + chargement a froid + k-NN + branchement `facts[]` et couche B
  (D).
- Extension RETRO-COMPATIBLE du contrat `LocalContext` (champs optionnels) et du
  rendu `LocalContextCard`.
- Prerequis infra a signaler (secret Google, egress `routes.googleapis.com`).

### Perimetre OUT (a ne pas deriver de cette analyse)
- C2 (quartier reel par polygones / point-in-polygon) : reste TODO, hors lot.
- Estimation de prix, DVF, conseil, redistribution d'annonces (anti-patterns
  permanents CONTEXT §11 / CLAUDE §1).
- Persistance de l'adresse ou des coordonnees (RGPD : non regresser).
- Cache routing PERSISTANT (interdit par les CGU Google — voir §6).
- Generalisation hors Metz Metropole.
- Scoring : la section reste NON-scoree (40/30/30 inchange).

### Challenge de cadrage (posture adversariale)
1. **A, B sont triviaux et a faible risque** (cosmetique de `facts[]`, en memoire,
   pas de reseau). **C est le gros morceau** (nouveau vendor, nouvel endpoint
   probable, egress, latence, CGU cache). **D est moyen** (snapshot a maintenir,
   pas de reseau runtime). Livrer A+B+C+D « en un lot » melange des risques tres
   heterogenes. Recommandation de decoupage en sous-lots/push internes en §5 —
   sans rouvrir la decision « livrable unique » du fondateur, mais en sequencant
   pour que A/B/D restent shippables si C bloque sur l'egress.
2. **C et D n'ont de valeur qu'en mode ADRESSE** (depend du geocodage BAN). En
   mode quartier, ils n'apportent rien (l'analyse C de #100 §5/§8 l'a deja acte).
   Or la proportion d'analyses avec adresse saisie n'est pas mesuree. A trafic
   quasi nul, **C ajoute un vendor et de la latence pour une fraction des
   analyses** : c'est defendable (qualite d'info = coeur produit) mais le ROI
   reel reste a surveiller. Ce n'est pas un argument pour ne pas faire, c'est un
   argument pour ne pas sur-investir (cache simple, modes a la demande — ce que le
   design lazy fait deja bien).
3. **Le free tier Google (10k Essentials / 5k Pro par mois) couvre largement le
   volume MVP** (cf. §6). Le risque cout est quasi nul tant que le trafic l'est ;
   le vrai risque est operationnel (cle, egress, CGU cache), pas financier.

---

## 1. Cartographie du code actuel touche, par volet

### Etat commun
La section est produite par `app/analysis.py::run_full_analysis`
(`analysis.py:167-221`), avec deux branches :
- mode ADRESSE (geocodage reussi) : `local_context_from_coords`
  (`metz_local.py:251-279`), `precision="adresse"`, distances Haversine ;
- mode QUARTIER (pas d'adresse / geocodage echoue) : `local_context`
  (`metz_local.py:102-131`), `precision="quartier"`, distances curatees figees.

Les distances/profils viennent du gazetteer unique `app/geo_gazetteer.py`. Les
POI geocodes sont `metz_local._POI` (`metz_local.py:32-37`). Le rendu est
`frontend/app/page.tsx::LocalContextCard` (`page.tsx:381-571`), le contrat TS
`frontend/lib/api.ts::LocalContext` (`api.ts:30-43`). La couche B est
`metz_local.assess_claims` / `_assess_one` (`metz_local.py:156-236`).

### Volet A — supprimer la ligne generique « Axe A31 / Luxembourg » en mode quartier
- Constante `metz_local._A31_LUXEMBOURG` (`metz_local.py:22-25`).
- Ajoutee en mode QUARTIER en `metz_local.py:121` (3e fact, identique pour toutes
  les annonces : aucune donnee propre, valeur informative nulle, perte de
  credibilite — diagnostic fondateur correct).
- En mode ADRESSE, la meme constante est portee par un fact qui a une DISTANCE
  reelle (`metz_local.py:269` : `Echangeur A31 le plus proche` + texte
  frontalier). La decision fondateur (retirer la ligne generique en mode quartier,
  la garder en mode adresse) ne touche donc QUE `local_context` (mode quartier).
- **Impact** : retirer le 3e element de la liste `facts` en `metz_local.py:118-122`
  (mode quartier). Decision a confirmer (Q1) : suppression seche, OU verser
  l'attrait frontalier dans le `summary` (`metz_local.py:124`/`p["caractere"]`).
  Le `summary` vient du gazetteer (`profile.caractere`), donc « verser dans le
  summary » impliquerait soit de concatener un texte fixe a l'affichage, soit de
  modifier les profils du gazetteer (plus invasif, touche un refactor-pur). Reco :
  suppression seche du fact en mode quartier (le plus simple, le moins de surface).
- **Tests touches** : tout test qui asserte la presence des 3 facts en mode
  quartier devra etre mis a jour. A reperer en phase tests.

### Volet B — sortir le Centre Pompidou-Metz comme fact distinct (4 facts)
- Aujourd'hui mode ADRESSE : Pompidou et gare sont FUSIONNES par
  `min(d["gare"], d["pompidou"])` (`metz_local.py:265`), affiches sous un seul
  fact « Gare Metz-Ville · Centre Pompidou-Metz » (`metz_local.py:268`).
- `_POI` contient deja `pompidou` (`metz_local.py:34`) ET `a31`
  (`metz_local.py:36`) : en mode ADRESSE, **les 4 distances existent deja**, il
  suffit de ne plus fusionner et d'ajouter une 4e ligne. Faible cout en mode
  adresse.
- Mode QUARTIER : le gazetteer ne porte que `center` et `gare` dans `dist_km` et
  `profile` (`geo_gazetteer.py` : chaque entree a `dist_km={"center":..,
  "gare":..}` et `profile` avec `center`/`gare`/`caractere`). **Aucune distance
  Pompidou par quartier**. Pour 4 facts en mode quartier, il faudrait soit (i)
  ajouter une distance `pompidou` curatee a chaque entree du gazetteer (17
  entrees), soit (ii) n'afficher Pompidou qu'en mode adresse (ou il est mesure).
- **Recommandation** : option (ii) — n'afficher Pompidou comme fact distinct
  qu'en mode ADRESSE. Justification : (a) en mode quartier, Pompidou est
  geographiquement quasi colle a la gare (cf. `_POI` : gare 49.1097,6.1773 /
  Pompidou 49.1095,6.1825) ; une distance « au centroide du quartier » serait
  quasi identique a celle de la gare et apporterait une fausse granularite ; (b)
  ajouter une 17e×N valeur curatee a la main est de la dette (CLAUDE §11 « profils
  figes en dur, distances saisies a la main »). Decision a remonter (Q2).
- **Impact mode adresse** : remplacer `metz_local.py:265-270` pour produire 4
  facts (`cathedrale`, `gare`, `pompidou`, `a31`). Le `_A31_LUXEMBOURG` reste sur
  le fact A31 (volet A ne touche pas l'adresse).
- **Couche B inchangee** : `_assess_one` ne juge que `cathedrale/centre/gare/a31`
  ; pas de claim « pompidou » a ce stade (non demande).

### Volet C — temps de trajet reels (Google Routes API, Compute Route Matrix)
- **Aucun code de routing aujourd'hui.** Tout passe par Haversine
  (`metz_local.haversine_km`, `precise_distances_km` `metz_local.py:239-241`).
- Le front etiquette deja explicitement « a vol d'oiseau » et annonce « temps de
  trajet reel a venir » (`page.tsx:565-566`). C remplace cette etiquette par un
  mode honnete quand un temps reel est obtenu.
- **Le calcul n'a lieu qu'a `/analyze`** aujourd'hui : `run_full_analysis` est le
  seul producteur du Contexte local. Le design lazy (un mode par defaut a
  l'analyse + modes alternatifs a la demande) impose un point d'entree
  SUPPLEMENTAIRE pour le « a la demande » (clic utilisateur). Voir §2.
- Fichiers impactes : nouveau `app/routing.py` (a creer) ; `analysis.py`
  (aiguillage du mode par defaut a l'analyse, autour de
  `local_context_from_coords` `analysis.py:190-197`) ; `app/main.py` (nouvel
  endpoint si retenu) ; `metz_local.py` (structure des facts enrichie par mode) ;
  contrat `api.ts` + `page.tsx` (affichage des modes + onglets a la demande).
- Secret + egress : `GOOGLE_MAPS_API_KEY` (`fly secrets`) + egress HTTPS vers
  `routes.googleapis.com` autorise en prod (Fly) ET dans l'environnement Claude
  Code web (leçon BAN/egress CLAUDE §11bis : sinon repli permanent = feature
  invisible / faux-vert en test).

### Volet D — distance aux ecoles les plus proches (= C3, deja analyse)
- `_assess_one` route le type `ecoles` vers `A_VERIFIER` neutre
  (`metz_local.py:193-195`) : « non verifiable depuis le profil de quartier ».
- Le type `ecoles` est deja extrait par le LLM (`local_claims[].type`, CLAUDE
  §11bis couche B).
- Aucune base POI ecoles aujourd'hui. Le calcul de distance reutilise
  `haversine_km` (`metz_local.py:40-50`) sur un jeu de points bien plus grand
  (k-NN en memoire).
- Source recommandee (analyse #100 §7 Option B, reco B1) : **Annuaire de
  l'Education Nationale** (data.education.gouv.fr / data.gouv, Licence Ouverte),
  snapshot importe A FROID, pas d'appel live. Mode ADRESSE uniquement (depend du
  geocodage). Rendu factuel via `facts[]` (« ecole elementaire X a ~350 m ») SANS
  jugement (« prise »/« bien desservi » interdits).
- Fichiers impactes : nouveau snapshot de donnees + nouveau module de chargement
  (`app/schools.py` ou similaire) ; `analysis.py` / `metz_local.py`
  (`local_context_from_coords` enrichi de facts ecoles) ; eventuellement
  `_assess_one` pour le type `ecoles` (passer de A_VERIFIER neutre a une note
  factuelle quand on a des coordonnees). Contrat `api.ts` inchange si on passe par
  `facts[]` (structure generique `{label, value}`).

---

## 2. Volet C — design technique (a cadrer, decisions remontees)

### 2.1 Ou brancher le routing
- Nouveau module `app/routing.py` isolant le client Google (pattern « un seul
  point d'appel », comme `geocode.py`). Signature pressentie (a fixer en spec, pas
  ici) du style :
  `compute_travel_times(origin: tuple[float,float], destinations: dict[str, tuple], mode: str) -> dict[str, dict]`
  renvoyant par POI `{mode, duration_s, distance_m}` ou un repli/None par element.
- Repli SILENCIEUX : si cle absente, egress bloque, HTTP non-2xx, timeout, ou
  element sans route -> retomber sur Haversine (« a vol d'oiseau »), exactement
  comme `geocode.py` retombe sur None (`geocode.py:101-104`). Aucun signalement
  inquietant a l'utilisateur (choix assume, coherent avec l'existant).
- Le mode par defaut PAR POI (decide fondateur) : pieton pour
  cathedrale/gare/Pompidou, voiture pour l'echangeur A31. A l'analyse, un SEUL
  appel Compute Route Matrix (1 origine × 4 destinations = 4 elements) suffit si
  l'on accepte un mode mixte dans une meme requete — OR le route matrix prend UN
  `travelMode` par requete. Donc « un mode par defaut par POI » = potentiellement
  2 requetes (1 WALK pour 3 POI + 1 DRIVE pour 1 POI), soit 4 elements au total.
  A trancher : 2 requetes (honnete par POI) vs 1 requete tout-pieton (plus simple,
  moins fidele pour l'A31). Voir Q4.

### 2.2 Aiguillage defaut (analyse) vs a-la-demande (clic) — nouvel endpoint ?
- A l'analyse : `run_full_analysis` appelle le routing pour le mode par defaut et
  remplit les facts (mode + duree + etiquette). Si echec -> Haversine.
- A la demande : l'utilisateur clique un mode alternatif (pieton/velo/voiture/
  transports) sur un POI -> 1 requete a la volee. `run_full_analysis` ne s'execute
  qu'a `/analyze` ; il faut donc un POINT D'ENTREE separe. Deux options :
  - (a) **Nouvel endpoint** `POST /travel-times` (body : coordonnees origine +
    POI + mode), pattern `/feedback` / `/events` (sans LLM, sans DB), protege par
    `rate_limiter` (`app/rate_limit.py:53`, signature `(limit, window_seconds)`).
    Avantage : pas de re-analyse, pas de cout LLM, contrat `/analyze` intact.
    Inconvenient : nouvelle surface API + RGPD (les coordonnees transitent dans le
    body — voir §2.3).
  - (b) **Recalcul** via `/analyze` avec un parametre de mode : couteux (re-appel
    LLM ou cache), melange les responsabilites, change le contrat `/analyze`. A
    eviter.
- **Recommandation** : (a) nouvel endpoint dedie `POST /travel-times`. Voir Q3.

### 2.3 Conserver les coordonnees entre l'analyse et le clic SANS les persister (RGPD)
- Contrainte : l'adresse/les coordonnees ne sont JAMAIS stockees (RGPD non
  regresse — CONTEXT §11, CLAUDE §11bis, analyse #100 §4-6).
- Aujourd'hui la reponse `/analyze` n'expose PAS lat/lon (seulement `label`/
  `address` textuel et des distances formatees). Pour qu'un clic a-la-demande
  recalcule un mode, le client doit pouvoir fournir l'origine et la destination.
  Trois pistes (a trancher Q5) :
  - (i) **Le front renvoie les coordonnees** dans le body de `POST /travel-times`.
    Implique d'EXPOSER lat/lon du bien dans la reponse `/analyze` (nouveau champ).
    Sensible : exposer les coordonnees du bien augmente la surface (meme si pas de
    persistance). A challenger : est-ce une regression de minimisation ?
  - (ii) **Le client renvoie l'ADRESSE texte** (deja exposee via
    `local_context.address`) ; l'endpoint re-geocode (cache memoire BAN) puis
    route. Pas de nouvelle exposition de coordonnees ; 1 geocodage de plus (cache).
  - (iii) Coordonnees des POI = constantes serveur (`_POI`), donc seules les
    coordonnees du BIEN doivent circuler ; (ii) evite de les exposer.
  - **Recommandation** : (ii) — l'endpoint a-la-demande prend l'adresse (deja
    cote client) + l'id du POI + le mode, re-geocode (cache) et route. Zero
    nouvelle exposition de coordonnees, zero persistance. Cout : un hit de cache
    geocode. Voir Q5.
- Cache de session/court (CGU) : un cache MEMOIRE court (TTL court, par
  process) est acceptable ; un cache PERSISTANT (SQLite/Redis) des temps de trajet
  est INTERDIT par les CGU Google. Le repli sur le cache memoire existant est
  coherent avec la pratique geocode/LLM (perdu au restart). A documenter en spec.

### 2.4 Structure de la donnee renvoyee (par POI)
- Par fact/POI, exposer (forme exacte a fixer en spec) :
  `{label, value, mode, duration_min, distance, estimated: bool}` ou
  `value` reste le texte affiche (« ~7 min a pied ») et `mode`/`estimated`
  permettent l'etiquetage honnete + le repli. Quand repli Haversine : `value` =
  « ~420 m a vol d'oiseau », `estimated`/mode absent ou `"vol_oiseau"`.
- **Contrainte de retro-compatibilite** : ajouter des cles OPTIONNELLES a chaque
  element de `facts[]` ne casse pas le contrat (le front lit `f.label`/`f.value`,
  `page.tsx:447-468`). Les nouvelles cles sont ignorees par les anciens clients.
- Etiquetage honnete (decision fondateur) : « a pied » / « en voiture » / « en
  transports » quand temps reel ; NE PLUS afficher « a vol d'oiseau » dans ce cas
  ; « a vol d'oiseau » UNIQUEMENT en repli Haversine reel (pas de fausse
  precision, CONTEXT §1.4).

---

## 3. Volet D — design technique (a cadrer)

### 3.1 Snapshot ecoles
- **Source** : Annuaire de l'Education Nationale (data.gouv, Licence Ouverte).
  Champs utiles : nom, type (maternelle/elementaire/college/lycee), lat, lon,
  commune, code commune. Filtrer au perimetre (voir Q6 : Metz + couronne
  `_METRO_CITIES` ? departement 57 entier ?).
- **Format** : module Python de donnees (comme `geo_gazetteer.py`) OU fichier
  data (CSV/JSON) charge a l'import. L'analyse #100 §2.6/§4-4 recommande IMPORT A
  FROID (pas d'appel live) pour eliminer la dependance reseau runtime. Reco :
  fichier data versionne (CSV compact) + module de chargement, plutot qu'un gros
  litteral Python.
- **Volume** : a estimer selon le perimetre. Metz + couronne ~ quelques dizaines a
  ~150 ecoles ; departement 57 entier ~ plusieurs milliers. k-NN lineaire en
  memoire reste trivial (<10k points). Reco : perimetre Metz Metropole (couronne)
  pour limiter le volume et rester pertinent (mode adresse = bien messin).
- **Ou stocker** : sous `backend/app/data/` (nouveau) ou `backend/data/`. A fixer
  Q7. Le `.gitignore` couvre la DB SQLite et le cache, pas un snapshot data
  versionne : OK a committer (donnee publique Licence Ouverte, pas un secret, pas
  une annonce).

### 3.2 Chargement a froid + robustesse import (leçon 2026-06-16)
- **Leçon cycle d'import (issue-100-B)** : une structure derivee au TOP-LEVEL d'un
  module qui depend d'un module qui depend en retour cree un cycle latent. Si le
  snapshot ecoles est charge au top-level de `app/schools.py`, verifier
  `python -c "import app.schools"` ET les modules qui l'importent CHACUN en premier
  (process separes). Pas d'import croise top-level avec `metz_local`/`analysis`.
- Charger le snapshot une fois a l'import (lecture fichier data), pas par requete
  ; pas de lookup base par-ligne a l'ingestion (la donnee ecole n'a rien a voir
  avec la collecte de comparables — ne PAS la brancher dans `ingestion/save.py`,
  leçon index 2026-06-14 NON applicable mais a ne pas y porter).

### 3.3 k-NN et rendu
- k-NN : pour les coordonnees geocodees du bien, trouver la/les ecole(s) les plus
  proches par type (1 elementaire + 1 maternelle + 1 college, par ex.). Haversine
  reutilise (`metz_local.haversine_km`). Trivial en memoire.
- Rendu : ajouter des `facts[]` (« Ecole elementaire X · ~350 m a vol d'oiseau »)
  en mode ADRESSE uniquement, dans `local_context_from_coords`. SANS jugement de
  valeur. Etiqueter « a vol d'oiseau » (meme contrainte que C : pas de conversion
  en minutes sans routing ; analyse #100 §4-2 : « ecole a 350 m » suggere « 4 min
  a pied » alors qu'une riviere/voie ferree impose un detour).
- Interaction routing (C) : on POURRAIT calculer un temps pieton vers l'ecole la
  plus proche via Google (coherent avec C). A challenger : cela multiplie les
  elements factures et la latence. Reco : en lot 1, ecoles en distance vol
  d'oiseau (factuel, honnete) ; routing ecoles = optionnel/ulterieur. Voir Q8.

### 3.4 Couche B (claims « ecoles »)
- Aujourd'hui : claim type `ecoles` -> A_VERIFIER neutre (`metz_local.py:193-195`).
- Avec un snapshot + coordonnees, on peut produire une note FACTUELLE (« ecole
  elementaire la plus proche a ~350 m ») au lieu du neutre, MAIS sans statut
  « coherent » de complaisance (regle de prudence `metz_local.py:160-162`). Reco :
  garder `A_VERIFIER` comme statut (on ne « valide » pas une allegation
  marketing), enrichir la NOTE avec le fait mesure quand on a des coordonnees.
  Voir Q8.

---

## 4. Impact sur le contrat `LocalContext` (`api.ts`) et `LocalContextCard`

### Contrat backend
- `AnalyzeResponse.local_context` est un `Optional[Dict[str, Any]]`
  (`main.py:90`) : cote backend, ajouter des cles ne declenche aucune validation
  Pydantic (dict libre). Le verrou est cote FRONT (`api.ts`).

### Contrat front (`api.ts:30-43`)
- `facts: { label: string; value: string }[]` (`api.ts:33`). Pour C, enrichir
  chaque fact de cles OPTIONNELLES (`mode?`, `duration_min?`, `estimated?`) reste
  RETRO-COMPATIBLE (anciens clients lisent label/value). Pour D, un fact ecole
  passe par la meme structure `{label, value}` -> aucun changement de type requis.
- Modes a la demande (C) : pour permettre les onglets pieton/velo/voiture/
  transports cote front, il faut soit (i) exposer par fact la liste des modes
  disponibles + un identifiant de POI (`poi_id`) pour rappeler `/travel-times`,
  soit (ii) ne proposer les alternatives que sur clic et porter `poi_id`/origine
  cote client. Cela AJOUTE des champs optionnels au contrat -> MAJ `api.ts`
  OBLIGATOIRE (leçon permanente : ne pas casser le schema sans MAJ `api.ts`). Ces
  ajouts etant OPTIONNELS, ils sont retro-compatibles, mais `api.ts` DOIT etre
  mis a jour dans le meme lot.
- Si un nouveau champ structure (ex. `schools[]` dedie ou `travel_modes[]`) etait
  prefere a `facts[]`, ce serait une rupture de structure -> MAJ front obligatoire.
  Reco : rester sur `facts[]` enrichi (generique) pour D ; pour C, le minimum de
  champs optionnels (mode/etiquette + de quoi declencher l'appel a-la-demande).

### Rendu `LocalContextCard` (`page.tsx:381-571`)
- Volet A : 1 fact de moins en mode quartier (le `.map` `page.tsx:447` s'adapte
  tout seul).
- Volet B : 1 fact de plus en mode adresse (idem, le `.map` s'adapte). 4 facts.
- Volet C : afficher le mode/etiquette par fact ; UI d'onglets de modes a la
  demande (nouveau composant ou enrichissement). Adapter la note de bas de carte
  (`page.tsx:565-567`) : ne plus dire « temps de trajet reel a venir » quand on a
  un temps reel ; dire « a vol d'oiseau » seulement en repli.
- Volet D : facts ecoles affiches comme les autres.
- `buildReportText` (`page.tsx:695-725`) liste deja `lc.facts` : les ecoles et les
  temps de trajet apparaitront automatiquement dans l'export `.md` (verifier le
  wording).

---

## 5. Decoupage en push / sous-lots (ordre, dependances, testabilite)

Le fondateur veut un LIVRABLE unique (A+B+C+D). Decoupage INTERNE recommande
(push successifs sur la branche, pas 4 PR) pour borner le risque et garder du
testable sans reseau :

| Push | Contenu | Depend de | Testable sans reseau ? |
|---|---|---|---|
| 1 | **A** (retrait fact A31 en mode quartier) + **B** (4 facts en mode adresse, Pompidou demixe) | rien | Oui (en memoire, distances Haversine deja la) |
| 2 | **D** (snapshot ecoles importe a froid + k-NN + facts ecoles mode adresse + couche B note) | geocodage (existant) | Oui (snapshot local, pas de reseau ; patcher geocode) |
| 3 | **C** (`app/routing.py` + mode par defaut a l'analyse + repli Haversine + contrat enrichi) | secret Google + egress | Oui via MOCK du client Google ; le repli Haversine est testable sans reseau |
| 4 | **C a la demande** (`POST /travel-times` + onglets front + `api.ts`) | push 3 | Oui via mock |

- **Dependances** : C (push 4) depend de C (push 3). D est independant de C. A et B
  sont independants de tout. Donc si l'egress Google bloque, A/B/D restent
  livrables et C peut rester en repli Haversine (feature degradee mais honnete).
- **Testabilite sans reseau (critique, leçon BAN/egress)** : MOCKER le client
  Google (`app/routing.py`) et patcher `geocode_address` (deja la pratique des
  tests #100, spec C §3.6). Le snapshot ecoles est local -> testable hors ligne.
  NE PAS dependre d'appels Google/BAN reels en CI (sinon faux-vert / repli
  permanent invisible).
- **Caches globaux (leçons 9.7 / photo-evidence)** : tout cache module-global
  ajoute (cache routing memoire, cache geocode, snapshot ecoles charge une fois)
  doit etre reinitialise par une fixture AUTOUSE en `conftest.py` si un test
  asserte un compteur d'appels. A signaler au spec-writer/testeur.

---

## 6. Risques (par gravite), anti-patterns, prerequis externes, RGPD/CGU

### Bloquants / prerequis externes (a verifier AVANT de coder C)
1. **[BLOQUANT C] Egress `routes.googleapis.com`** non autorise en prod (Fly) ou
   dans l'environnement Claude Code web. Consequence : repli permanent = feature
   invisible + faux-vert en test (leçon BAN/egress CLAUDE §11bis). A confirmer
   avant l'atelier (Q9).
2. **[BLOQUANT C] Secret `GOOGLE_MAPS_API_KEY`** absent : repli permanent. Doit
   etre pose via `fly secrets` (prod + staging, leçon « staging = memes capacites
   que prod » 2026-06-14) et dispo en CI/atelier si on veut un test d'integration
   reel (sinon mock only). Ne JAMAIS committer la cle (CONTEXT §11.8).

### Majeurs
3. **[MAJEUR] CGU Google — cache persistant interdit.** On ne peut PAS persister
   les temps de trajet (SQLite/Redis). Seul un cache memoire court est admis. Un
   futur chantier « cache persistant » (note CLAUDE §11 pour LLM/geocode) NE doit
   PAS embarquer les temps Google. A inscrire comme garde-fou.
4. **[MAJEUR] Fausse precision (CONTEXT §1.4).** Ne jamais convertir une distance
   vol d'oiseau en minutes sans routing reel ; etiqueter le mode ; « a vol
   d'oiseau » seulement quand c'est vraiment Haversine. Vaut pour C (repli) ET D
   (ecoles : ne pas suggerer un temps a pied). Verrouiller par tests d'etiquetage.
5. **[MAJEUR] Repli silencieux mal verrouille = faux-vert.** Si l'egress est
   bloque en CI/atelier, les tests qui « passent » peuvent ne tester que le repli.
   Verrouiller le CHEMIN REEL par mock (faire « repondre » le client Google mocke,
   et faire « lever » le mock pour tester le repli) — pattern leçons 9.10 (tester
   le fallback par le chemin reel, pas via monkeypatch de la facade).
6. **[MAJEUR] RGPD — ne pas exposer/persister les coordonnees.** L'adresse n'est
   pas stockee aujourd'hui ; les coordonnees non plus. Le design a-la-demande ne
   doit ni persister ni (idealement) exposer lat/lon (preferer re-geocoder
   l'adresse texte cote endpoint, §2.3 option (ii)). Verrouiller par test « aucune
   ecriture d'adresse/coordonnees ».

### Moyens
7. **[MOYEN] Nouveau vendor (Google).** Decide, pas a rouvrir. Mais ajoute une
   dependance externe + un point de panne sur un chemin produit. Mitigation : repli
   Haversine systematique, endpoint isole, timeout court.
8. **[MOYEN] Latence ajoutee.** L'appel Google a l'analyse (mode par defaut)
   ajoute un aller-retour reseau sur `/analyze` (en plus du LLM et de la BAN). A
   borner par un timeout court + repli. Le « a la demande » deplace le reste de la
   latence hors du chemin critique d'analyse (bon design).
9. **[MOYEN] Cout.** Compute Route Matrix facture par element (origines ×
   destinations). Mode par defaut a l'analyse = ~4 elements/analyse (Essentials) ;
   transit = Pro (~0,01 $/element), plafond 100 elements/requete. Free tier
   mensuel par SKU (10k Essentials / 5k Pro). A volume MVP, cout ~nul (decide, ne
   pas rouvrir). Garde-fou recommande : poser une LIMITE de depense / quota cote
   Google Cloud (analogue a l'usage limit OpenAI, CONTEXT 9.4) — a remonter.
10. **[MOYEN] Snapshot ecoles a maintenir.** Donnee a rafraichir periodiquement
    (peu frequent). Pas de fraicheur runtime. Definir une politique (Q7) :
    rafraichissement manuel a la main, versionne. Documenter la date du snapshot.
11. **[MOYEN] Volet B mode quartier = dette si on remplit le gazetteer.** Ajouter
    une distance Pompidou curatee par quartier = 17 valeurs a la main (fake
    granularite + dette). D'ou la reco « Pompidou en mode adresse seulement »
    (Q2).

### Faibles
12. **[FAIBLE] Contrat `/analyze`.** Les ajouts sont des cles OPTIONNELLES
    (retro-compatibles) mais `api.ts` DOIT etre mis a jour dans le lot (leçon
    permanente). Pas une rupture si bien fait.
13. **[FAIBLE] Section non-scoree.** Aucun de ces volets ne doit toucher le
    40/30/30 (CONTEXT §11.3). Verrouiller par test que le score est inchange.
14. **[FAIBLE] Anti-patterns produit.** Pas d'estimation, pas de DVF, pas de
    redistribution, pas de conseil. Les ecoles et temps de trajet sont des FAITS
    sourçables (Annuaire EN / Google), pas des jugements. Interdits explicites :
    « quartier prise », « bien desservi », conversion distance->minutes sans
    routing.

---

## 7. QUESTIONS POUR L'HUMAIN (GATE 1)

> Vendor C deja tranche = Google (ne pas rouvrir). Tarification deja arbitree (ne
> pas rouvrir). Perimetre = A+B+C+D en un lot (ne pas rouvrir). Les questions
> ci-dessous sont les seuls arbitrages restants qui relevent vraiment de l'humain.

**Q1 — Volet A : suppression seche ou report dans le `summary` ?**
Options : (a) retirer purement le fact « Axe A31 · Luxembourg » en mode quartier ;
(b) verser l'attrait frontalier dans le `summary` (implique de concatener un texte
ou de modifier les profils du gazetteer — plus invasif).
*Reco* : **(a) suppression seche.** Le moins de surface, pas de modification du
gazetteer (refactor-pur preserve). L'attrait frontalier reste visible en mode
adresse (porte par une distance reelle).

**Q2 — Volet B : Pompidou comme 4e fact en mode quartier aussi, ou mode adresse
seulement ?**
Options : (a) afficher Pompidou comme fact distinct UNIQUEMENT en mode adresse
(ou la distance est mesuree) ; (b) ajouter aussi une distance Pompidou curatee a
chacune des 17 entrees du gazetteer pour l'afficher en mode quartier.
*Reco* : **(a) mode adresse seulement.** En mode quartier, Pompidou est quasi
colle a la gare (centroide quasi identique) : (b) serait de la fausse granularite
+ 17 valeurs a la main (dette). « 4 facts distincts » est donc tenu en mode
adresse ; en mode quartier on garde cathedrale + gare (+ A31 retire par A).

**Q3 — Volet C : nouvel endpoint `POST /travel-times` ou recalcul via `/analyze` ?**
Options : (a) nouvel endpoint dedie (sans LLM, sans DB, rate-limite, pattern
`/feedback`/`/events`) pour le « a la demande » ; (b) re-passer par `/analyze` avec
un parametre de mode.
*Reco* : **(a) nouvel endpoint.** Zero cout LLM, contrat `/analyze` intact, latence
hors chemin d'analyse. (b) melange les responsabilites et touche `/analyze`.

**Q4 — Volet C : mode par defaut a l'analyse = 1 requete (tout pieton) ou 2
requetes (pieton pour cathedrale/gare/Pompidou + voiture pour A31) ?**
Options : (a) 1 requete WALK (4 elements) — plus simple/moins cher, mais l'A31 en
« a pied » n'a pas de sens (on l'etiquetterait alors « a vol d'oiseau » ou on
ometterait le temps) ; (b) 2 requetes (WALK ×3 + DRIVE ×1) — fidele a la decision
« voiture pour l'echangeur », ~4 elements quand meme, 2 appels reseau.
*Reco* : **(b) 2 requetes.** Coherent avec la decision fondateur (voiture pour
l'A31), cout/element identique, free tier large. La latence des 2 appels est
acceptable (et peut etre parallelisee). Si on veut minimiser les appels, (a) avec
A31 laisse en « a vol d'oiseau ».

**Q5 — Volet C a la demande : comment l'origine circule sans exposer/persister les
coordonnees (RGPD) ?**
Options : (i) exposer lat/lon du bien dans la reponse `/analyze` et les renvoyer au
endpoint ; (ii) l'endpoint prend l'ADRESSE texte (deja exposee) + l'id du POI + le
mode, et re-geocode (cache memoire) ; (iii) autre.
*Reco* : **(ii) re-geocoder l'adresse texte.** Pas de nouvelle exposition de
coordonnees, pas de persistance, cout = un hit de cache geocode. Verrouiller par
test « aucune ecriture d'adresse/coordonnees ».

**Q6 — Volet D : perimetre geographique du snapshot ecoles ?**
Options : (a) Metz + couronne (`_METRO_CITIES`) ; (b) departement 57 entier ;
(c) Metz intra-muros seulement.
*Reco* : **(a) Metz + couronne.** Coherent avec le perimetre marche
(`_METRO_CITIES`), volume modere (~dizaines a ~150 ecoles, k-NN trivial),
pertinent car le mode adresse cible des biens de l'agglo. (b) gonfle le snapshot
sans gain (biens hors agglo non cibles).

**Q7 — Volet D : ou heberger le snapshot, format, et politique de fraicheur ?**
Options format : (a) fichier data versionne (CSV/JSON) sous `backend/app/data/`
charge a l'import ; (b) gros litteral Python dans un module. Fraicheur : (a)
rafraichissement manuel versionne (date inscrite) ; (b) job CI periodique.
*Reco* : **fichier data versionne + chargement a froid + rafraichissement manuel
documente (date du snapshot).** Pas d'appel live (analyse #100 §4-4). Un job CI de
rafraichissement est sur-dimensionne pour un MVP (la liste des ecoles bouge peu).

**Q8 — Volet D : temps de trajet vers l'ecole (routing C) ou distance vol d'oiseau
seulement ? Et statut couche B ?**
Options : (a) ecoles en distance vol d'oiseau (factuel, etiquete), routing ecoles
ulterieur ; (b) router aussi le temps pieton vers l'ecole la plus proche (plus
d'elements factures + latence). Couche B : garder `A_VERIFIER` (ne pas « valider »
une allegation marketing) en enrichissant la note, ou introduire un statut
factuel.
*Reco* : **(a) distance vol d'oiseau pour les ecoles au lot 1** + note couche B
enrichie en gardant le statut `A_VERIFIER` (pas de validation de complaisance).
Routing ecoles = optionnel/ulterieur si le ROI le justifie.

**Q9 — Prerequis egress/secret : confirmer AVANT l'atelier que l'egress
`routes.googleapis.com` est ouvert (prod Fly + Claude Code web) et que
`GOOGLE_MAPS_API_KEY` est pose (prod + staging) ?**
Options : (a) confirmer/poser l'egress + la cle avant de coder C ; (b) coder puis
decouvrir le blocage (repli permanent = feature invisible, faux-vert).
*Reco* : **(a) confirmer avant l'atelier.** Sinon C est invisible et les tests
verts ne prouvent que le repli. Idem garde-fou cout : poser une limite de depense /
quota cote Google Cloud (analogue a l'usage limit OpenAI, CONTEXT 9.4).

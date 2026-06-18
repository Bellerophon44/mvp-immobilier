# SPEC — Contexte local v2 (Ancrage local, qualité d'info) — volets A+B+C+D

> Rôle : SPEC-WRITER. Lecture seule du code, écriture de ce seul document.
> Sources relues avant rédaction : `.claude/lessons.md` (toutes les entrées, dont
> cycle d'import issue-100-B, faux-vert 9.10, caches globaux 9.7 / photo-evidence,
> isolation DB 9.7, bornes 9.7) ; `backend/CLAUDE.md` (§1, §5, §10, §11, §11bis,
> §12) ; `docs/specs/contexte-local-v2-ANALYSE.md` (analyse + arbitrages GATE 1) ;
> et le code réel : `app/metz_local.py`, `app/analysis.py`, `app/geocode.py`,
> `app/rate_limit.py`, `app/main.py`, `app/market_stats.py`,
> `frontend/lib/api.ts`, `frontend/app/page.tsx`, `backend/tests/conftest.py`.
>
> Branche : `claude/trusting-gauss-boi5lr`. Périmètre : COMPLET A+B+C+D, livrable
> unique, découpé en 4 push internes (§5). Les décisions GATE 1 sont **actées et
> non rouvrables** ; cette spec les traduit en contrat technique testable. Le
> testeur écrira les pytest À PARTIR des critères d'acceptation (§4).

---

## 1. Objectif et périmètre

### Objectif
Améliorer la qualité d'information de la section **non-scorée** « Contexte local »
sur quatre fronts : (A) retirer une ligne générique sans valeur en mode quartier ;
(B) séparer le Centre Pompidou-Metz de la gare en mode adresse (4 facts) ;
(C) afficher des temps de trajet réels (Google Routes API) en mode adresse, avec
repli silencieux sur Haversine et étiquetage honnête ; (D) afficher la distance
aux écoles les plus proches (snapshot Annuaire Éducation Nationale, k-NN en
mémoire) en mode adresse.

### Périmètre IN
- Rendu des `facts[]` du Contexte local (A, B).
- Nouveau module `app/routing.py` (client Google Route Matrix, injectable/mockable)
  + aiguillage du mode par défaut à l'analyse (C-défaut).
- Nouvel endpoint `POST /travel-times` (C-à-la-demande), sans LLM ni DB, rate-limité.
- Snapshot écoles versionné + module de chargement à froid + k-NN + facts écoles
  + enrichissement de la note couche B (D).
- Extension **rétro-compatible** du contrat `LocalContext` (champs optionnels) +
  MAJ `frontend/lib/api.ts` et `frontend/app/page.tsx` (`LocalContextCard`,
  `buildReportText`).

### Périmètre OUT (non-objectifs — §5 OUT de l'analyse, à ne pas dériver)
- C2 (quartier réel par point-in-polygon) : reste TODO, hors lot.
- Pompidou comme fact distinct **en mode quartier** : NON (décision B, voir §3.B).
- Routing des écoles (temps de trajet vers l'école) : NON au lot 1 ; distance à vol
  d'oiseau uniquement (décision D).
- Bascule du claim `ecoles` en `coherent` : INTERDITE (décision D / couche B).
- Cache **persistant** des temps de trajet (interdit par les CGU Google).
- Persistance ou exposition de l'adresse / des coordonnées (RGPD : ne pas régresser).
- Estimation de prix, DVF, redistribution d'annonces, conseil (anti-patterns §1).
- Modification du score 40/30/30 (la section reste non-scorée).
- Généralisation hors Metz Métropole.

---

## 2. Décisions actées (GATE 1, non rouvrables)

| Réf | Décision |
|---|---|
| A | Suppression **sèche** du fact générique « Axe A31 · Luxembourg » en mode QUARTIER (`local_context`). En mode ADRESSE il reste (porte une distance réelle). |
| B | Pompidou = fact distinct en mode ADRESSE **uniquement** (4 facts adresse). En mode QUARTIER : cathédrale + gare seulement (A31 retiré par A). Suppression de la fusion `min(gare, pompidou)`. |
| C | Temps de trajet réels via Google Route Matrix, **mode adresse uniquement**. Module `app/routing.py` ; clé via `GOOGLE_MAPS_API_KEY` ; repli silencieux None partout si clé absente / réseau KO / réponse invalide ; cache mémoire court (pas de persistance). Défaut analyse = 2 requêtes (WALK cathédrale+gare+Pompidou, DRIVE échangeur A31). À la demande = `POST /travel-times` (re-géocode l'adresse texte, pas de lat/lon exposé). Étiquetage honnête. |
| D | Snapshot Annuaire Éducation Nationale (Licence Ouverte) versionné dans le repo, chargé à froid en mémoire ; k-NN Haversine sur Metz + couronne (`_METRO_CITIES`) ; mode adresse uniquement ; facts factuels sans jugement ; claim `ecoles` reste `A_VERIFIER`, note enrichie. |

### Arbitrages techniques fins (résolus par le spec-writer dans le cadre acté)
Ces points ne rouvrent aucune décision GATE 1 ; ils précisent les bornes laissées
ouvertes par le brief. Ils sont signalés comme tels et restent ajustables par le
testeur sans toucher au code produit.

- **C — bornes rate-limit `POST /travel-times`** : `limit=30, window_seconds=60`
  par IP (cohérent avec l'échelle `/analyze`=10, `/feedback`=60, `/events`=120 ;
  un utilisateur peut cliquer plusieurs modes × plusieurs POI sur une analyse).
- **C — TTL cache mémoire routing** : 10 minutes (CGU Google : court, par process,
  jamais persisté). Clé = `(origine_arrondie, poi_id, mode)`.
- **C — timeout client Google** : 4 s (sous le timeout BAN de 6 s ; le routing est
  best-effort, on ne veut pas allonger `/analyze`).
- **C — arrondi de l'origine pour la clé de cache** : coordonnées arrondies à 5
  décimales (≈ 1 m) — déterministe, évite les quasi-doublons.
- **D — nombre d'écoles affichées** : **la plus proche par degré** parmi
  {maternelle, élémentaire, collège, lycée} présents dans le snapshot au périmètre,
  soit **au plus 4 facts écoles**, omettant les degrés sans école dans le snapshot.
  Justification : un fact par degré est lisible, factuel, et évite de noyer la carte
  (vs « les N plus proches » qui mélangerait les degrés sans information de choix).
- **D — chemin du snapshot** : `backend/app/data/schools_metz.json` (JSON compact,
  versionné, public Licence Ouverte). Module de chargement : `app/schools.py`.

---

## 3. Spécification par volet

### Volet A — retrait du fact générique « Axe A31 · Luxembourg » en mode quartier

**Fichier** : `app/metz_local.py::local_context` (lignes 118-122).

- Retirer le 3e élément `{"label": "Axe A31 · Luxembourg", "value": _A31_LUXEMBOURG}`
  de la liste `facts` construite en mode quartier. La liste passe de 3 à **2 facts**
  (`Centre / Cathédrale St-Étienne`, `Gare Metz-Ville · Centre Pompidou-Metz`).
- Ne **pas** verser `_A31_LUXEMBOURG` dans le `summary` (suppression sèche, décision A).
- La constante `_A31_LUXEMBOURG` reste définie (utilisée par le mode adresse).
- `local_context_from_coords` (mode adresse) n'est PAS touché par A : le fact A31 y
  reste (volet B en redéfinit la liste, mais conserve le fact A31, voir §3.B).

### Volet B — Pompidou comme 4e fact distinct en mode adresse

**Fichier** : `app/metz_local.py::local_context_from_coords` (lignes 264-270).

- Supprimer la fusion `gare_pompidou = min(d["gare"], d["pompidou"])` (ligne 265).
- Produire **4 facts** dans cet ordre exact (mode adresse) :
  1. `{"label": "Centre / Cathédrale St-Étienne", "value": <cathedrale>}`
  2. `{"label": "Gare Metz-Ville", "value": <gare>}`
  3. `{"label": "Centre Pompidou-Metz", "value": <pompidou>}`
  4. `{"label": "Échangeur A31 le plus proche", "value": <a31> + " · " + _A31_LUXEMBOURG}`
- En mode QUARTIER : aucun fact Pompidou (le gazetteer ne porte pas de distance
  Pompidou par quartier ; en fabriquer une serait de la fausse précision — OUT).
- La couche B (`_assess_one`) n'est PAS étendue à un claim `pompidou` (non demandé).

> Note : les labels « Gare Metz-Ville · Centre Pompidou-Metz » (mode quartier
> existant, ligne 120) et le label fusionné mode adresse (ligne 268) sont remplacés.
> En mode quartier, le label gare reste **inchangé** (`Gare Metz-Ville · Centre
> Pompidou-Metz`) car le gazetteer agrège toujours les deux au niveau quartier ;
> seul le mode adresse les sépare. C'est volontaire (le mode quartier ne mesure pas).

### Volet C — temps de trajet réels (Google Route Matrix)

#### C.1 — Module `app/routing.py`

Nouveau module, logger `logging.getLogger("routing")`, type hints obligatoires
(§12). Point d'appel unique du client Google Route Matrix.

Signature publique :

```python
def compute_travel_times(
    origin: tuple[float, float],
    destinations: dict[str, tuple[float, float]],
    mode: str,
    client: RoutesClient | None = None,
) -> dict[str, dict | None]:
    """Pour chaque POI de `destinations` ({poi_id: (lat, lon)}), renvoie
    {poi_id: {"mode": <mode>, "distance_m": int, "duration_s": int}} ou
    {poi_id: None} si pas de route / réponse invalide pour ce POI.
    Repli SILENCIEUX : renvoie {poi_id: None} pour TOUS les POI si la clé est
    absente, le réseau échoue, ou la réponse est invalide. Ne lève jamais."""
```

- `mode` ∈ `{"WALK", "DRIVE", "BICYCLE", "TRANSIT"}` (mappé sur `travelMode` de
  l'API Route Matrix ; un seul `travelMode` par requête).
- **Client injectable** (`client` paramètre) : un objet `RoutesClient` interne
  encapsule l'appel HTTPS `POST https://routes.googleapis.com/distanceMatrix/v2:computeRouteMatrix`
  avec header `X-Goog-Api-Key`. En production `client=None` → le module construit
  son client à partir de `os.getenv("GOOGLE_MAPS_API_KEY")`. Les **tests injectent
  un client mocké** (jamais de réseau réel, leçon BAN/egress). Le repli silencieux
  est testé en faisant **lever** le client mocké (leçon 9.10 : tester le chemin réel
  du fallback, pas la façade).
- Si `GOOGLE_MAPS_API_KEY` est absente ET `client is None` → repli immédiat
  (`{poi_id: None}` pour tous), aucun appel réseau, aucune exception, log INFO.
- Cache mémoire `_CACHE: dict[tuple, tuple[float, dict | None]]`, TTL 10 min, clé
  `(round(lat,5), round(lon,5), poi_id, mode)`. `reset_routing_cache()` exposé pour
  l'isolation des tests (leçon 9.7/9.9, voir §7). **Jamais de persistance disque/DB**
  (CGU Google).
- `distance_m` et `duration_s` sont des entiers issus de la réponse Google ; aucune
  valeur n'est inventée. Un élément de réponse sans route (status non-OK, condition
  `ROUTE_NOT_FOUND`, etc.) → `None` pour ce POI.

#### C.2 — Aiguillage du mode par défaut à l'analyse

**Fichier** : `app/analysis.py::run_full_analysis` (branche géocodage réussi,
lignes 190-197) et `app/metz_local.py::local_context_from_coords`.

- En mode adresse, après géocodage, calculer le mode par défaut **par POI** via
  **2 requêtes** Route Matrix :
  1. `compute_travel_times(origin, {cathedrale, gare, pompidou}, "WALK")`
  2. `compute_travel_times(origin, {a31}, "DRIVE")`
- Pour chaque POI où un temps réel est obtenu, le fact affiche un **temps de trajet
  étiqueté** (« à pied » / « en voiture ») ; sinon le fact retombe sur la **distance
  Haversine** étiquetée « à vol d'oiseau » (repli par POI, indépendant).
- L'appel routing est **best-effort** : si `app/routing` n'est pas disponible /
  lève / clé absente, **tous** les facts retombent sur Haversine (comportement
  identique à l'actuel). `/analyze` ne renvoie jamais 500 à cause du routing.
- Le format texte des `value` :
  - temps réel : `"~{minutes} min {label_mode}"` où `minutes = round(duration_s/60)`
    et `label_mode ∈ {"à pied", "en voiture", "à vélo", "en transports"}`.
  - repli Haversine : format actuel `_fmt_dist(km)` + `" à vol d'oiseau"` (le suffixe
    « à vol d'oiseau » est ajouté au `value`, voir contrat §4 / AC d'étiquetage).

#### C.3 — Endpoint `POST /travel-times` (à la demande)

**Fichier** : `app/main.py`. Pattern `/feedback` / `/events` : sans LLM, sans DB,
rate-limité par `rate_limiter`. Logger `mvp` ou logger dédié `routing`
(jamais d'adresse/coordonnée journalisée).

Request (Pydantic) :

```python
class TravelTimesIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    address: str = Field(min_length=1, max_length=300)
    mode: Literal["WALK", "DRIVE", "BICYCLE", "TRANSIT"]
    city_hint: Optional[str] = "Metz"
```

Comportement :
1. Re-géocode `address` via `geocode.geocode_address(address, city_hint)` (cache
   mémoire). Si `None` → réponse `{"status": "indisponible", "reason": "adresse"}`
   (HTTP 200, pas 500).
2. Sinon, `compute_travel_times((lat, lon), <POI pertinents>, mode)`. Les POI sont
   les constantes serveur `metz_local._POI` (cathédrale, gare, pompidou, a31). Les
   coordonnées **ne transitent pas** dans le body (RGPD) ; seule l'adresse texte
   (déjà exposée côté front via `local_context.address`) circule.
3. Pour chaque POI : si temps réel → `{poi_id, mode, label_mode, value, duration_s,
   distance_m, estimated: false}` ; si repli → `{poi_id, mode: "vol_oiseau", value:
   "<haversine> à vol d'oiseau", estimated: true}`.

Response (succès) :

```json
{
  "status": "ok",
  "mode": "WALK",
  "results": [
    {"poi_id": "cathedrale", "label": "Centre / Cathédrale St-Étienne",
     "value": "~8 min à pied", "label_mode": "à pied",
     "duration_s": 480, "distance_m": 620, "estimated": false},
    {"poi_id": "a31", "label": "Échangeur A31 le plus proche",
     "value": "~1,3 km à vol d'oiseau", "estimated": true}
  ]
}
```

Response (indisponible) : `{"status": "indisponible", "reason": "adresse" | "routing"}`,
HTTP 200. `reason="adresse"` = géocodage échoué ; `reason="routing"` = géocodage OK
mais routing indisponible pour **tous** les POI ET aucun repli (cas théorique : la
réponse fournit toujours au moins le repli Haversine, donc en pratique `status="ok"`
avec `estimated: true` partout — `reason="routing"` reste défini pour robustesse).
**Aucune coordonnée (lat/lon) n'apparaît dans la réponse.**

- Rate-limit : `Depends(rate_limiter(limit=30, window_seconds=60))`.
- 422 si `mode` invalide ou `address` vide (validation Pydantic).

### Volet D — distance aux écoles les plus proches

#### D.1 — Snapshot et module de chargement

**Fichiers** : `backend/app/data/schools_metz.json` (versionné), `app/schools.py`.

- Source : Annuaire de l'Éducation Nationale (data.gouv, Licence Ouverte). Snapshot
  importé À FROID, **pas d'appel live, pas de job CI**. Rafraîchissement manuel
  documenté en tête de `app/schools.py` (date du snapshot + procédure).
- Périmètre géographique : communes de `market_stats._METRO_CITIES` (Metz + couronne).
- Format JSON compact, liste d'objets `{"name": str, "degre": str, "commune": str,
  "lat": float, "lon": float}`. `degre` ∈ `{"maternelle", "elementaire", "college",
  "lycee"}`.
- Chargement à l'import dans `app/schools.py` (lecture du fichier data une fois,
  pas par requête). Logger `logging.getLogger("schools")`, type hints (§12).
- **Robustesse import (leçon issue-100-B)** : `python -c "import app.schools"` doit
  réussir en tout premier import (process séparé). PAS d'import croisé top-level avec
  `metz_local` / `analysis` (importer `haversine_km` paresseusement dans la fonction,
  ou ne dépendre que de la stdlib pour le k-NN). NE PAS brancher dans `ingestion/save.py`.

Signature publique :

```python
def nearest_schools(lat: float, lon: float) -> list[dict]:
    """Pour chaque degré présent dans le snapshot, l'école la plus proche (Haversine).
    Renvoie une liste d'au plus 4 dicts {name, degre, commune, distance_km},
    triés par degré dans l'ordre {maternelle, elementaire, college, lycee}.
    Liste vide si le snapshot est vide."""
```

#### D.2 — Rendu `facts[]` (mode adresse uniquement)

**Fichier** : `app/metz_local.py::local_context_from_coords`.

- Après les 4 facts A/B/C, ajouter **un fact par école retournée** par
  `nearest_schools`, format :
  `{"label": "<Degré lisible> <Nom>", "value": "~{dist} à vol d'oiseau"}`
  où `<dist>` est `_fmt_dist(distance_km)` et `<Degré lisible>` mappe `degre` vers
  `{"maternelle": "École maternelle", "elementaire": "École élémentaire",
  "college": "Collège", "lycee": "Lycée"}`.
- **Aucun jugement de valeur** : les mots « prisé », « bien desservi », « recherché »
  sont INTERDITS dans le label/value des facts écoles.
- Distance à **vol d'oiseau** uniquement (pas de conversion en minutes — leçon
  fausse précision). Routing écoles = OUT (lot ultérieur).
- Mode quartier : aucun fact école (dépend du géocodage).

#### D.3 — Couche B (claim `ecoles`)

**Fichier** : `app/metz_local.py::_assess_one`.

- Le claim de type `ecoles` reste `A_VERIFIER` (jamais `coherent` — pas de
  validation de complaisance d'une allégation marketing).
- La **note** peut être enrichie d'un fait mesuré **quand des écoles sont
  disponibles** : ex. « École élémentaire la plus proche à ~350 m à vol d'oiseau —
  proximité à confirmer sur place. » Sans jugement.
- L'enrichissement ne s'applique qu'en présence de coordonnées (mode adresse) ; en
  mode quartier la note neutre actuelle est conservée.

---

## 4. Contrat API

### 4.1 — Forme exacte des nouveaux champs `LocalContext` (rétro-compatible)

Côté backend, `local_context` est un `dict` libre (`Optional[Dict[str, Any]]`,
`main.py:90`) — pas de validation Pydantic. Le verrou est côté front (`api.ts`).

Chaque élément de `facts[]` reste un objet `{label: string, value: string}` et gagne
des clés **optionnelles** (anciens clients lisent `label`/`value`, ignorent le reste) :

```ts
export interface LocalFact {
  label: string;
  value: string;
  // Mode de trajet réel quand un temps routé est disponible (volet C). Absent en
  // repli Haversine. "vol_oiseau" non utilisé ici : l'absence de `mode` signifie
  // distance à vol d'oiseau.
  mode?: "WALK" | "DRIVE" | "BICYCLE" | "TRANSIT";
  duration_s?: number;
  distance_m?: number;
  // true => `value` est une distance Haversine ("à vol d'oiseau"), pas un temps réel.
  estimated?: boolean;
  // Identifiant de POI permettant de redemander un autre mode via POST /travel-times.
  // Présent sur les facts de POI routables (cathedrale/gare/pompidou/a31), absent
  // sur les facts écoles (non routables au lot 1).
  poi_id?: string;
}
```

`LocalContext.facts` devient `LocalFact[]`. Tous les nouveaux champs sont optionnels
→ **rétro-compatible** : une réponse `/analyze` sans ces champs reste valide.

### 4.2 — Schéma `POST /travel-times` (nouveau, à déclarer dans `api.ts`)

```ts
export interface TravelTimesRequest {
  address: string;
  mode: "WALK" | "DRIVE" | "BICYCLE" | "TRANSIT";
  city_hint?: string;
}
export interface TravelTimeResult {
  poi_id: string;
  label: string;
  value: string;
  label_mode?: string;   // "à pied" | "en voiture" | "à vélo" | "en transports"
  duration_s?: number;
  distance_m?: number;
  estimated?: boolean;   // true => repli vol d'oiseau
  mode?: string;         // "vol_oiseau" en repli
}
export interface TravelTimesResponse {
  status: "ok" | "indisponible";
  mode?: string;
  reason?: "adresse" | "routing";
  results?: TravelTimeResult[];
}
```

### 4.3 — Changements front attendus (`api.ts` + `page.tsx`)

- `api.ts` : ajouter `LocalFact` (remplace le type inline de `facts`), `TravelTimes*`
  + une fonction `fetchTravelTimes(address, mode, cityHint?)` (POST `/travel-times`).
  MAJ obligatoire dans le lot (leçon permanente : pas de schéma `/analyze` modifié
  sans MAJ `api.ts`), même si les champs sont optionnels.
- `page.tsx::LocalContextCard` :
  - A : 1 fact de moins en mode quartier (le `.map` ligne 447 s'adapte seul).
  - B : 4 facts en mode adresse (idem).
  - C : afficher `value` tel quel (déjà étiqueté côté serveur) ; pour les facts avec
    `poi_id`, proposer des **onglets/boutons de modes** (à pied / vélo / voiture /
    transports) qui appellent `fetchTravelTimes` et remplacent le `value` du fact.
    Adapter la note de bas de carte (ligne 565-567) : ne plus afficher « temps de
    trajet réel à venir » ; afficher « à vol d'oiseau » seulement pour les facts
    `estimated`.
  - D : facts écoles affichés comme les autres (génériques).
  - `buildReportText` (ligne 714) liste déjà `lc.facts` → écoles et temps de trajet
    apparaissent automatiquement dans l'export `.md` (vérifier le wording).

---

## 5. Critères d'acceptation (numérotés, testables)

> Le testeur écrit les pytest à partir d'ici. Chaque AC est falsifiable. Les tests
> backend ne dépendent JAMAIS du réseau (client Google injecté/mocké, `geocode`
> patché). Sauf mention contraire, « mode adresse » = `geocode_address` patché pour
> renvoyer un `{lat, lon, label, ...}` connu ; « mode quartier » = pas d'adresse.

### Volet A
- **AC1** — En mode QUARTIER, `local_context("Sablon")["facts"]` contient
  **exactement 2** facts, dont les labels sont `Centre / Cathédrale St-Étienne` et
  `Gare Metz-Ville · Centre Pompidou-Metz` ; **aucun** fact dont le label contient
  « A31 » ou « Luxembourg ».
- **AC2** — En mode QUARTIER, aucune `value` de fact ni le `summary` ne contient la
  chaîne `_A31_LUXEMBOURG` (« Axe A31 vers le sillon lorrain ») — la suppression est
  sèche, pas reportée dans le summary.
- **AC3** — En mode ADRESSE (géocodage patché), le fact « Échangeur A31 le plus
  proche » est **toujours présent** et son `value` contient « Luxembourg »
  (A ne touche pas le mode adresse).

### Volet B
- **AC4** — En mode ADRESSE, `local_context_from_coords(lat, lon)["facts"]` contient
  **4 facts de POI** dans l'ordre : labels `Centre / Cathédrale St-Étienne`,
  `Gare Metz-Ville`, `Centre Pompidou-Metz`, `Échangeur A31 le plus proche` (avant
  d'éventuels facts écoles).
- **AC5** — Les `value` des facts gare et Pompidou sont **distincts** quand les
  distances Haversine `d["gare"]` et `d["pompidou"]` diffèrent (sonde : coordonnées
  choisies pour que les deux distances diffèrent d'au moins 200 m → deux `value`
  formatés différents). Prouve que la fusion `min(gare, pompidou)` est supprimée.
- **AC6** — Aucun label de fact ne contient à la fois « Gare » et « Pompidou » en
  mode ADRESSE (la fusion par label est supprimée). (Le mode quartier conserve son
  label fusionné — AC1.)

### Volet C — module routing
- **AC7** — `compute_travel_times` avec un client mocké renvoyant des routes valides
  produit, par POI, `{"mode": <mode>, "distance_m": int, "duration_s": int}` (types
  entiers, valeurs = celles renvoyées par le mock, non inventées).
- **AC8** (repli clé absente) — Avec `GOOGLE_MAPS_API_KEY` non défini et `client=None`,
  `compute_travel_times` renvoie `{poi_id: None}` pour **tous** les POI, **sans lever**
  et **sans appel réseau** (aucun appel HTTP émis — sonde : pas de client construit).
- **AC9** (repli réseau KO, chemin réel) — Avec un client mocké dont la méthode
  d'appel **lève** une exception, `compute_travel_times` renvoie `{poi_id: None}`
  pour tous les POI, sans propager l'exception (leçon 9.10 : faire lever la vraie
  dépendance, pas la façade).
- **AC10** (réponse invalide) — Avec un client mocké renvoyant une réponse malformée
  (champ manquant, `status` non-OK pour un POI), le POI concerné est `None` et les
  autres POI restent corrects (repli par élément, pas global).
- **AC11** (cache mémoire) — Deux appels successifs `compute_travel_times` avec la
  même origine/poi/mode ne déclenchent qu'**un seul** appel client (cache hit au 2e).
  Après `reset_routing_cache()`, un nouvel appel re-déclenche le client.
- **AC12** (pas de persistance) — Aucune écriture disque/DB n'est faite par
  `app/routing` (sonde : `_CACHE` est un dict module ; aucune table créée, aucun
  fichier écrit ; le cache est vidé par `reset_routing_cache`).

### Volet C — analyse (mode par défaut)
- **AC13** — En mode ADRESSE avec routing mocké renvoyant des temps WALK pour
  cathédrale/gare/pompidou et DRIVE pour a31, les `value` des facts correspondants
  sont des **temps** (`~{min} min à pied` / `~{min} min en voiture`), portent
  `mode`, `duration_s`, `distance_m`, `estimated=false` et `poi_id`.
- **AC14** (2 requêtes par mode) — Le routing par défaut émet exactement **2 appels**
  `compute_travel_times` : un en `WALK` sur {cathedrale, gare, pompidou}, un en
  `DRIVE` sur {a31} (sonde sur les arguments d'appel — vérifier le mode ET l'ensemble
  des poi_id de chaque appel, pas seulement le nombre).
- **AC15** (repli par POI) — Si le routing mocké renvoie un temps pour cathédrale mais
  `None` pour gare, le fact cathédrale affiche un temps (`estimated=false`) et le fact
  gare retombe sur Haversine (`estimated=true`, `value` se terminant par « à vol
  d'oiseau »). Repli **indépendant** par POI.
- **AC16** (routing indisponible global) — Si `compute_travel_times` renvoie `None`
  partout (clé absente), les 4 facts adresse sont en Haversine étiqueté « à vol
  d'oiseau » et `/analyze` renvoie 200 (pas de 500). Comportement identique à
  l'actuel sans routing.
- **AC17** (`/analyze` robuste au routing qui lève) — En faisant **lever**
  `compute_travel_times` (monkeypatch qui raise), `run_full_analysis` en mode adresse
  retourne un contexte local valide en Haversine et `/analyze` renvoie 200.

### Volet C — endpoint `POST /travel-times`
- **AC18** (succès) — `POST /travel-times` avec `geocode` patché (coords connues) et
  routing mocké renvoie `status="ok"`, `results[]` non vide, chaque résultat porte
  `poi_id` ∈ {cathedrale, gare, pompidou, a31}.
- **AC19** (indisponible adresse) — `geocode_address` patché pour renvoyer `None` →
  réponse HTTP **200** `{"status": "indisponible", "reason": "adresse"}` (pas de 500).
- **AC20** (validation) — `POST /travel-times` sans `address` (ou `address=""`) →
  **422** ; `mode` hors enum → **422** ; champ extra → **422** (`extra="forbid"`).
- **AC21** (rate-limit) — La 31e requête `POST /travel-times` dans la fenêtre de 60 s
  pour une même IP renvoie **429** avec en-tête `Retry-After` ; la 30e passe.
- **AC22** (sans LLM ni DB) — Le handler `/travel-times` n'appelle ni `analyze_semantic`
  ni n'ouvre de session DB (sonde statique : pas de `SessionLocal`/`analyze_semantic`
  dans le corps de l'endpoint).

### Volet C — étiquetage honnête (anti fausse précision)
- **AC23** — Aucun fact ni résultat `/travel-times` avec `estimated=true` (repli
  Haversine) n'affiche un temps en minutes : son `value` ne matche pas
  `~\d+ min` et se termine par « à vol d'oiseau ».
- **AC24** — Aucun fact ni résultat avec un temps réel (`estimated=false`, `mode`
  routé) n'affiche « à vol d'oiseau » dans son `value` ; le `label_mode` est l'un de
  {à pied, en voiture, à vélo, en transports} et JAMAIS « à vol d'oiseau ».
- **AC25** — Le `value` d'un temps réel est dérivé de `duration_s` (`round(duration_s/60)`
  minutes), jamais d'une distance Haversine convertie (sonde : `value` cohérent avec
  `duration_s`, indépendant de `distance_m` Haversine).

### Volet C — RGPD
- **AC26** — La réponse `/analyze` (mode adresse) ne contient **aucune** clé `lat`,
  `lon`, `latitude`, `longitude`, ni dans `local_context` ni dans aucun fact (sonde
  récursive sur le dict de réponse).
- **AC27** — La réponse `POST /travel-times` ne contient **aucune** coordonnée
  (lat/lon) ; seuls `poi_id`, labels, valeurs textuelles, durées/distances entières.
- **AC28** — `POST /travel-times` n'écrit **aucune** ligne en base (sonde :
  `count()` de toutes les tables inchangé avant/après l'appel) et ne persiste aucune
  adresse/coordonnée. (Couvre la non-régression RGPD du chemin à-la-demande.)

### Volet C — rétro-compat contrat
- **AC29** — Tous les nouveaux champs de fact (`mode`, `duration_s`, `distance_m`,
  `estimated`, `poi_id`) sont **optionnels** : une réponse `/analyze` en mode quartier
  (sans ces champs) reste un `LocalContext` valide (les facts n'ont que `label`/`value`).
- **AC30** — `frontend/lib/api.ts` déclare `LocalFact` (avec les champs optionnels)
  et les types `TravelTimes*` (sonde statique sur le fichier : présence des champs et
  de la fonction `fetchTravelTimes`). Garde-fou « pas de schéma sans MAJ `api.ts` ».

### Volet D — écoles
- **AC31** (import sans cycle) — `python -c "import app.schools"` réussit en process
  séparé, en **tout premier** import ; et `python -c "import app.metz_local"` réussit
  aussi en premier (leçon issue-100-B : pas de cycle top-level). Sonde par
  sous-processus.
- **AC32** (k-NN correct) — Sur un snapshot de test connu (jeu d'écoles aux coords
  fixées), `nearest_schools(lat, lon)` renvoie pour chaque degré l'école dont la
  distance Haversine est minimale (vérifier l'identité exacte de l'école la plus
  proche, pas seulement la distance) — falsifiable en déplaçant une école.
- **AC33** (au plus 4 facts, 1 par degré) — `nearest_schools` renvoie au plus 4
  entrées, une par degré présent, triées dans l'ordre {maternelle, elementaire,
  college, lycee} ; un degré absent du snapshot est omis (pas de fact vide).
- **AC34** (périmètre Metz + couronne) — Toutes les écoles du snapshot
  `schools_metz.json` ont une `commune` ∈ `market_stats._METRO_CITIES` (forme
  canonique). Sonde sur le fichier data chargé. Falsifiable en injectant une commune
  hors périmètre.
- **AC35** (facts écoles mode adresse) — En mode ADRESSE, `local_context_from_coords`
  ajoute après les 4 facts POI un fact par école, label commençant par un degré
  lisible (`École maternelle`/`École élémentaire`/`Collège`/`Lycée`) et `value`
  finissant par « à vol d'oiseau ».
- **AC36** (pas de jugement) — Aucun label/value de fact école ne contient
  « prisé », « recherché », « bien desservi » (liste de mots interdits asserter).
- **AC37** (pas d'école en mode quartier) — En mode QUARTIER, aucun fact école n'est
  produit (`local_context` n'appelle pas `nearest_schools`).
- **AC38** (distance vol d'oiseau, pas de minutes) — Aucun fact école n'affiche un
  temps en minutes (`value` ne matche pas `~\d+ min`).

### Volet D — couche B (non-régression)
- **AC39** — Un claim `{type: "ecoles"}` reste de statut `A_VERIFIER` après
  l'enrichissement (jamais `coherent`), en mode adresse comme en mode quartier.
  Falsifiable : un test rougirait si le code basculait en `coherent`.
- **AC40** — En mode ADRESSE, la note du claim `ecoles` peut mentionner une distance
  factuelle (« ~\d+ m » ou « ~\d+,\d km » + « à vol d'oiseau ») sans aucun mot de
  jugement ; en mode quartier la note neutre actuelle est conservée.

### Invariants transverses
- **AC41** (section non-scorée) — `global_score` et le `breakdown` 40/30/30 sont
  **inchangés** que le routing/écoles soient présents ou non (comparer deux analyses
  identiques avec et sans routing mocké : score identique).
- **AC42** (anti-patterns produit) — Aucun fact/claim ajouté ne contient
  d'estimation de prix, de référence DVF, ni de redistribution d'annonce (sonde de
  régression légère : pas de « €/m² estimé », pas de « valeur estimée »).

---

## 6. Découpage en push

> Livrable unique côté fondateur ; découpage interne en 4 push successifs sur la
> branche pour borner le risque et garder du testable sans réseau. Ordre imposé :
> push1 → push2 → push3 → push4. **Tout est testable sans réseau** (mocks/patch).

| Push | Contenu | Dépend de | AC couverts | Testable sans réseau ? |
|---|---|---|---|---|
| 1 | **A** (retrait fact A31 mode quartier) + **B** (4 facts adresse, Pompidou démixé) + MAJ `api.ts` `LocalFact` | rien | AC1-AC6, AC29-AC30 (partie facts) | Oui (en mémoire, Haversine déjà là) |
| 2 | **D** (snapshot `schools_metz.json` + `app/schools.py` + k-NN + facts écoles + note couche B) | géocodage (existant, patché) | AC31-AC40 | Oui (snapshot local, geocode patché) |
| 3 | **C-défaut** (`app/routing.py` + 2 requêtes par défaut à l'analyse + repli Haversine + facts enrichis) | secret Google + egress (mock en test) | AC7-AC17, AC23-AC26, AC29, AC41-AC42 | Oui (client Google mocké ; repli Haversine sans réseau) |
| 4 | **C-à-la-demande** (`POST /travel-times` + `fetchTravelTimes` + onglets front + complément `api.ts`) | push 3 | AC18-AC22, AC27-AC28, AC30 | Oui (geocode patché + client mocké) |

- Dépendances : push4 dépend de push3 (`compute_travel_times`). D (push2) est
  indépendant de C. A/B (push1) indépendants de tout. Si l'egress Google bloque en
  réel, A/B/D restent livrables et C reste en repli Haversine (feature dégradée mais
  honnête).
- Contenu testable sans réseau de **chaque** push : voir colonne ci-dessus. Le testeur
  doit MOCKER le client Google (`app/routing`, client injecté) et PATCHER
  `geocode_address` — jamais d'appel Google/BAN réel en CI (leçon BAN/egress : sinon
  faux-vert / repli permanent invisible).

---

## 7. Prérequis, risques, notes d'isolation de tests

### Prérequis & risques externes
- **[BLOQUANT pour la validation réelle de C, NON bloquant pour le code/tests]**
  Egress HTTPS vers `routes.googleapis.com` autorisé en **prod (Fly)** ET dans
  l'environnement **Claude Code web** ; secret `GOOGLE_MAPS_API_KEY` posé (prod +
  staging, leçon « staging = mêmes capacités que prod »). Le fondateur confirme
  egress + clé AVANT que C soit considéré validé en réel. Le **code doit être SÛR
  sans clé** (repli permanent silencieux, AC8/AC16) et les **tests ne dépendent pas
  du réseau** (client injecté/mocké, AC7-AC11).
- **[MAJEUR] CGU Google — cache persistant interdit.** Les temps de trajet ne sont
  JAMAIS persistés (SQLite/Redis). Seul un cache mémoire court (TTL 10 min, par
  process) est admis (AC11/AC12). Un futur chantier « cache persistant LLM/geocode »
  NE doit PAS embarquer les temps Google (garde-fou à inscrire).
- **[MAJEUR] Fausse précision.** Jamais de distance Haversine convertie en minutes ;
  étiquetage honnête « à vol d'oiseau » réservé au repli réel (AC23-AC25, AC38).
  Vaut pour C (repli) et D (écoles : distance seulement).
- **[MAJEUR] Faux-vert du repli silencieux.** Si l'egress est bloqué en CI, les tests
  « verts » ne testeraient que le repli. Verrouiller le chemin réel par client mocké
  qui RÉPOND (AC7/AC13) ET qui LÈVE (AC9/AC17) — leçon 9.10.
- **[MAJEUR] RGPD.** Ne pas exposer/persister adresse ni coordonnées (AC26-AC28).
  L'endpoint à-la-demande re-géocode l'adresse texte (déjà côté client) ; aucune
  lat/lon ne circule ni n'est stockée.
- **[MOYEN] Plafond de dépense Google Cloud.** Poser une limite de dépense / quota
  côté Google Cloud (analogue à l'usage limit OpenAI). À volume MVP, coût ≈ nul
  (free tier 10k Essentials / 5k Pro / mois). NON bloquant code/tests.
- **[MOYEN] Maintenance snapshot écoles.** Rafraîchissement manuel, versionné, date
  inscrite en tête de `app/schools.py`. Pas de fraîcheur runtime, pas de job CI.
- **[MOYEN] Latence ajoutée à `/analyze`** (2 appels Google au défaut, timeout 4 s,
  best-effort). Le à-la-demande déplace le reste de la latence hors du chemin
  d'analyse (bon design).
- **[FAIBLE] Contrat `/analyze`** : ajouts optionnels (rétro-compatibles) mais
  `api.ts` MAJ obligatoire dans le lot (AC30).
- **[FAIBLE] Section non-scorée** : aucun volet ne touche le 40/30/30 (AC41).

### Notes d'isolation de tests (conftest)
- **Caches de module à reset en `autouse` conftest** (leçons 9.7 / 9.9 /
  photo-evidence — JAMAIS en fixture locale) :
  - `app.routing._CACHE` via `reset_routing_cache()` (ajouter une fixture autouse
    `_reset_routing_cache` dans `backend/tests/conftest.py`, import protégé sur le
    modèle de `_reset_photo_cache`). Indispensable pour les AC qui assertent un
    compteur d'appels client (AC11, AC14).
  - Le snapshot écoles (`app.schools`) est chargé **une fois** à l'import (lecture
    seule, immuable au runtime) → pas de reset nécessaire **sauf** si un test
    monkeypatch le snapshot ; dans ce cas, restaurer en `autouse` ou via fixture
    locale qui restore. Recommandation : exposer `_load_schools()` testable + une
    constante module ; les tests k-NN passent un snapshot **explicite** (paramètre)
    plutôt que de muter l'état global, pour rester sans état partagé.
- **Pas de dépendance réseau** : `compute_travel_times` reçoit un `client` mocké ;
  `geocode_address` est patché (pattern des tests issue-100). Jamais d'appel Google
  ou BAN réel en CI.
- **Schéma DB pré-créé** : déjà géré par `conftest._init_db_schema` (autouse session).
  `/travel-times` n'écrit pas en DB (AC28) ; les autres tables sont reset par les
  fixtures autouse existantes (`_reset_events_table`, `_reset_snapshots_table`).
- **Bornes exactes** (leçon 9.7 bornes) : tester le rate-limit `/travel-times` AUX
  valeurs exactes (30e passe, 31e → 429), pas seulement hors borne.
- **Tester la couche qui produit, pas seulement le sérialiseur** (leçon 9.10) : pour
  AC26 (pas de lat/lon), asserter sur le dict retourné par `run_full_analysis`
  directement (hors `response_model` qui filtre), pas seulement sur le corps HTTP.

---

SPEC prête pour GATE 2 (approbation humaine).

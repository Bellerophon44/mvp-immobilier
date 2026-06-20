# SPEC — issue #100, chantier C, sous-palier C1 (inter-communal & commune reelle)

> **MAJ statut (2026-06-18) :** C1 est EN PRODUCTION (PR #110/#111, 2026-06-16).
> Le sous-palier **C3 (POI ecoles)**, marque OUT dans cette spec C1 (§1 OUT),
> a depuis ete **livre en prod** (2026-06-18) dans le lot « Contexte local v2 »
> — voir `docs/specs/contexte-local-v2-SPEC.md` et `backend/CLAUDE.md` §11bis.
> Reste **C2** (quartier reel par polygones) en TODO. Le corps ci-dessous decrit
> le perimetre C1 d'origine et reste valable comme spec de C1.

> Statut : pre-GATE 2. Spec implementable issue de l'analyse approuvee
> (`docs/specs/issue-100-C-ANALYSE.md`) + arbitrages GATE 1 (actes par le
> fondateur, repris en §2, non negociables). Sources relues avant redaction :
> `.claude/lessons.md` (toutes les entrees, dont index lookup par-ligne
> 2026-06-14, refactor pur / ordre / cycle d'import du chantier B) ;
> `docs/specs/issue-100-C-ANALYSE.md` (§6 sous-palier C1, §7 option C, questions
> GATE 1) ; `docs/specs/issue-100-B-SPEC.md` (modele de rigueur et de format) ;
> `backend/CLAUDE.md` (§7, §10 contrat /analyze, §11/§11bis) ; `CONTEXT.md`
> (§1.4 fake precision, §11 anti-patterns) ; et le code reel
> (`backend/app/geocode.py`, `geo_gazetteer.py`, `market_stats.py`,
> `analysis.py`, `metz_local.py`).
>
> Le developpeur ne code PAS d'apres ce preambule : il code d'apres les sections
> 3 (contrat technique) et 4 (criteres d'acceptation).
>
> C1 est un **changement de comportement BORNE** : il n'agit QUE pour un quartier
> explicitement declare inter-communal (et, pour la commune reelle, QUE lorsqu'une
> adresse est geocodee). Toute autre situation doit rester strictement identique
> a l'etat A/B (non-regression verrouillee, AC NR).

---

## 1. Objectif et perimetre

### Objectif
Corriger le seul vrai biais de DONNEE du palier 3 : le pool de comparables d'un
quartier **a cheval sur deux communes** (Botanique = Metz + Montigny-les-Metz)
est aujourd'hui ampute parce que `_fetch_comparables` filtre la commune en EXACT
(`market_stats.py:108`). C1 (a) exploite la commune REELLE deja renvoyee par la
BAN quand une adresse est geocodee, et (b) modelise dans le gazetteer, par une
table CURATEE, qu'un quartier couvre plusieurs communes, pour que son pool puise
dans l'ensemble de ses communes via le parametre `cities` (deja existant,
`market_stats.py:91`).

### Perimetre IN
1. **Lire la commune reelle de la BAN.** `geocode_address` expose en plus de
   `{lat, lon, score, label}` les champs `city` et `citycode` (et conserve
   `postcode`) issus des `properties` BAN, lorsqu'ils sont presents (§3.1).
   Aucun nouvel appel reseau : on lit la reponse deja obtenue.
2. **Table curatee d'inter-communalite dans le gazetteer.** Un champ
   `communes: Tuple[str, ...]` sur `GazetteerEntry` (defaut `()` derive en
   `(commune,)`), et une entree curatee pour le quartier inter-communal
   Botanique rattache a Sainte-Therese (alias `"Sainte-Therese-/-Botanique"`,
   chantier B). Une fonction de derivation pure expose la table
   `{canonical_key: tuple(communes)}` (§3.2, §3.3).
3. **Activation conditionnelle de `_fetch_comparables(cities=...)`.** Quand le
   quartier resolu pour l'analyse est declare inter-communal, le niveau
   `quartier` de la cascade `compute_market_stats` puise dans l'ENSEMBLE de ses
   communes au lieu de la seule commune du bien (§3.4). L'activation est
   binaire et explicite (table curatee), jamais derivee d'une distance a la
   frontiere.
4. **Repli silencieux + non-regression.** Sans adresse, sans quartier
   inter-communal, ou si le geocodage echoue, le comportement (pool ET sortie
   `/analyze`) reste strictement identique a A/B. Verrouille par AC NR1/NR2/NR3.

### Perimetre OUT (hors C1, reportes — NE PAS specifier ni coder)
- **C2** : rattachement quartier-reel par coordonnees (polygones / centroides /
  point-in-polygon), remplissage des `centroid`, alimentation de
  `_resolve_district` par le geocode. Le champ `centroid` reste `None`.
- **C3** : POI ecoles (2e vendor / snapshot), `facts[]` ecoles, calcul de
  distance bien->ecole.
- Reecriture de `canonical_district` / `canonical_city` (valeur stockee a
  l'ingestion — risque MAJEUR herite de B).
- Ajout de nouveaux quartiers au gazetteer ; multi-villes / generalisation hors
  Metz Metropole.
- Persistance de l'adresse ou des coordonnees nominatives (RGPD : l'adresse
  n'est jamais stockee aujourd'hui — ne pas regresser).
- Routing isochrone / temps de trajet ; conversion des distances vol-d'oiseau en
  minutes.
- Tout nouveau champ de reponse `/analyze` ou de `frontend/lib/api.ts` (C1
  passe par les structures existantes ; §3.5).
- Tout filtre / lookup geographique nouveau a l'INGESTION (`ingestion/save.py`,
  `scrapers/`). C1 agit uniquement a l'ANALYSE, en memoire (§5, lecon index
  2026-06-14).

---

## 2. Decisions actees (GATE 1) — non negociables

### D1 — Perimetre = C1 SEUL
IN = commune reelle BAN + table curatee d'inter-communalite + activation
`cities`. OUT = C2/C3 et tout le reste (cf. §1 OUT). Tout point hors de ce
perimetre qui apparaitrait necessaire est REMONTE a l'humain, pas invente.

### D2 — Activation inter-communale = TABLE CURATEE (option C1a de l'analyse §7)
On declare explicitement dans le gazetteer qu'un quartier couvre plusieurs
communes. **Pas** de regle generique « point a < X m d'une frontiere » (C1b
rejetee : seuil arbitraire, fake precision inverse qui diluerait le pool).
Consequence importante actee : cette table aide le pool **meme SANS adresse**,
des que le quartier inter-communal est resolu — y compris depuis le TEXTE via
l'alias `Botanique -> Sainte-Therese` (chantier B). La « commune reelle via
BAN » (D3) exige, elle, une adresse geocodee ; les deux mecanismes sont
complementaires et independants.

### D3 — Commune reelle = lecture de la sortie BAN deja obtenue
`geocode_address` lit deja `properties.postcode` (`geocode.py:84`) pour le
garde-fou departement. On lit EN PLUS `properties.city` et `properties.citycode`
de la MEME reponse, sans 2e appel reseau, sans 2e vendor. Cette commune reelle
sert (en C1) a determiner la commune du bien quand une adresse est fournie
(utile notamment quand le bien est cote Montigny d'un quartier a cheval).

### D4 — Repli SILENCIEUX + non-regression stricte
Sans adresse / geocodage en echec / quartier non inter-communal : comportement
identique a A/B, aucun nouveau signalement UI. Aucune fake precision : on
n'elargit le pool a une 2e commune QUE pour un quartier explicitement declare
inter-communal. Verrouille par AC NR1/NR2/NR3.

### D5 — Pas de rupture du contrat `/analyze`
On privilegie les structures existantes (`local_context`, `precision`, le pool
deja expose via `scope`/`scope_name`). Aucun champ de reponse ajoute/modifie,
donc `frontend/lib/api.ts` non touche (§3.5). Si un champ devait changer, il
faudrait l'expliciter et remonter l'impact front : ce n'est PAS le cas ici.

---

## 3. Contrat technique

### 3.0 Invariants de structure (rappel B, applicables a C1)
- Cle canonique de quartier = sortie de `canonical_city` appliquee au libelle
  (pivot B §3.0). C1 reutilise ces cles, n'en cree aucune.
- `canonical_district` / `canonical_city` ne sont PAS modifiees (elles
  produisent la valeur stockee a l'ingestion). La derivation les APPELLE.
- `GazetteerEntry` est une `@dataclass(frozen=True)` ; la derivation est pure,
  calculee a l'import, sans I/O ni lookup base (style `geo_gazetteer.py`).
- Robustesse a l'ordre d'import (lecon 2026-06-16 cycle d'import) : aucun nouvel
  import top-level de `scrapers.base` dans `geo_gazetteer.py` ; toute fonction
  nouvelle reste cote derivation pure (pas d'appel a `canonical_*` au top-level).

### 3.1 Commune reelle BAN — `backend/app/geocode.py`
Dans la branche succes de `geocode_address` (`geocode.py:86-93`), enrichir le
dict `result` avec la commune reelle issue des memes `properties` deja lues :

```
result = {
    "lat": float(lat),
    "lon": float(lon),
    "score": float(score),
    "label": props.get("label") or query,
    "city": props.get("city") or None,          # commune reelle BAN
    "citycode": props.get("citycode") or None,  # code INSEE BAN
    "postcode": postcode or None,               # deja lu (garde-fou dept 57)
}
```

Contraintes :
- Aucun nouvel appel reseau, aucun nouveau vendor, aucune nouvelle variable
  d'env / secret. On lit `feat["properties"]` deja desierialisee.
- Les trois champs sont **optionnels** : `None` si absents de la reponse BAN
  (robustesse). Le garde-fou departement 57 (`geocode.py:85`) et le seuil de
  score (`_MIN_SCORE`) sont INCHANGES.
- Le cache memoire existant (`_CACHE`) stocke desormais le dict enrichi ; aucune
  migration (cache en memoire, perdu au restart). Pas de persistance.
- Signature de `geocode_address` inchangee.

### 3.2 Schema gazetteer — champ inter-communal sur `GazetteerEntry`
Ajouter a `GazetteerEntry` (`geo_gazetteer.py:41-68`) un champ :

| Champ | Type | Defaut | Role |
|---|---|---|---|
| `communes` | `Tuple[str, ...]` | `()` | Ensemble ORDONNE des communes couvertes par le quartier (formes brutes, canonicalisees a la derivation via `canonical_city`). `()` = quartier mono-commune (= `(commune,)`). |

Regles :
- `communes` reste vide `()` pour toutes les entrees existantes (mono-commune
  Metz) : leur table derivee vaut `(canonical_city(commune),)` (= `("Metz",)`),
  donc aucun elargissement. Refactor pur pour ces entrees.
- Seules les entrees explicitement inter-communales declarent `communes` avec au
  moins deux communes. En C1 : l'entree **Sainte-Therese** (qui porte l'alias
  `"Sainte-Therese-/-Botanique"`, `geo_gazetteer.py:112`) declare
  `communes=("Metz", "Montigny-lès-Metz")`.
- Les formes brutes saisies passent par `canonical_city` a la derivation pour
  matcher les communes stockees (`Comparable.city` est canonicalisee a
  l'ingestion, CLAUDE §7). `"Montigny-lès-Metz"` -> `"Montigny-Les-Metz"`.
- Les communes declarees DOIVENT appartenir a `_METRO_CITIES`
  (`market_stats.py:49`) : on n'autorise pas un quartier a puiser dans une
  commune hors perimetre Metz Metropole. Verrouille par AC2.

> Pourquoi Sainte-Therese et pas une nouvelle entree « Botanique » : Botanique
> n'est PAS un quartier du selecteur ni une entree du gazetteer (B §1 OUT) ;
> il est resolu vers Sainte-Therese par l'alias « / » (B). Declarer
> l'inter-communalite sur Sainte-Therese fait beneficier le bien resolu vers
> cette cle, que la resolution vienne du texte (alias) ou d'une adresse. Ajouter
> une entree « Botanique » serait un nouveau quartier (hors C1, cf. §1 OUT).

### 3.3 Derivation pure — table des communes par quartier
Ajouter a `geo_gazetteer.py` une fonction de derivation pure, du meme style que
`profiles()` / `aliases()` :

```
def intercommunal_districts() -> Dict[str, Tuple[str, ...]]:
    """{canonical_key: tuple(communes canonicalisees)} pour les SEULS quartiers
    declares inter-communaux (>= 2 communes). Les quartiers mono-commune sont
    ABSENTS de la table (pas d'elargissement par defaut)."""
```

Contrat :
- La cle est `canonical_key` de l'entree.
- La valeur est le tuple des `canonical_city(c)` pour chaque `c` de `communes`,
  dedoublonne en preservant l'ordre, **uniquement si la cardinalite finale est
  >= 2**. Une entree dont `communes` est vide ou se reduit a une seule commune
  apres canonicalisation N'APPARAIT PAS dans la table (pas de `(commune,)`
  redondant).
- Derivation pure : `canonical_city` est deja importe au top-level de
  `geo_gazetteer`? Non — il ne l'est pas (cf. note `geo_gazetteer.py:34-38`).
  Pour eviter le cycle d'import (lecon 2026-06-16), `canonical_city` est importe
  **paresseusement** dans `intercommunal_districts` (comme `canonical_district`
  l'est dans `build_sector_maps`, `geo_gazetteer.py:425`), JAMAIS au top-level.
- `python -c "import app.geo_gazetteer"` ET `python -c "import scrapers.base"`
  doivent reussir chacun en premier import (process separes). Verifie au review.

### 3.4 Activation cote `market_stats` — niveau quartier inter-communal
Dans `compute_market_stats` (`market_stats.py:134-224`), au moment de construire
les candidats de cascade, determiner les communes du quartier resolu :

```
from app import geo_gazetteer as gazetteer
_INTERCOMMUNAL = gazetteer.intercommunal_districts()  # derive a l'import
...
district_cities = _INTERCOMMUNAL.get(district) if district else None
```

Regles d'activation (binaires, explicites) :
- Les candidats de **niveau quartier** (`market_stats.py:168-171`) passent
  `cities=district_cities` a `_fetch_comparables` au lieu de filtrer la seule
  `city` quand `district_cities` est non vide. Concretement, pour le niveau
  quartier, `_fetch_comparables` recoit `district=<quartier>` ET
  `cities=district_cities` : le filtre devient « ce quartier, dans cet ensemble
  de communes » (`Comparable.district == district AND Comparable.city IN
  district_cities`).
- Quand `district_cities` est `None` (quartier non inter-communal ou pas de
  quartier), les candidats quartier sont INCHANGES (`cities=None`, filtre
  `Comparable.city == city`) : refactor pur, aucune regression.
- Les niveaux **secteur**, **ville**, **metropole** sont INCHANGES. En
  particulier la regle « la ville reste preferee des `MIN_COMPARABLES` »
  (`market_stats.py:195`) et le filet metropole ne sont pas touches.
- `district_cities` est restreint a des communes de `_METRO_CITIES` par
  construction (§3.2 / AC2) ; on n'elargit jamais a une commune etrangere.

Effet attendu (Botanique) : un bien resolu vers `Sainte-Therese` voit, au niveau
quartier, les comparables `district == "Sainte-Therese"` des communes
`{"Metz", "Montigny-Les-Metz"}` reunies, au lieu de la seule commune du bien.
Les niveaux superieurs de la cascade sont inchanges.

> Note d'implementation (a la main du developpeur) : `_fetch_comparables`
> accepte deja `cities` (`market_stats.py:91, 105-106`). Si `cities` est fourni,
> le filtre `Comparable.city == city` est remplace par `Comparable.city.in_(cities)`
> (deja code). Aucune modification de `_fetch_comparables` n'est requise ; seul
> l'APPEL du niveau quartier dans la cascade change pour passer `cities`.

### 3.5 Contrat `/analyze` et front — INCHANGE
- Aucun champ de reponse ajoute/retire/renomme. Le pool elargi se reflete
  uniquement dans les valeurs deja exposees (`scope="quartier"`, `scope_name`,
  `n_comparables`, fourchette de prix) : meme structure, valeurs potentiellement
  differentes pour les seuls biens inter-communaux. `frontend/lib/api.ts` non
  touche. Verrouille par AC C5.
- `precision` (`local_context`) est INCHANGE : C1 ne touche pas a la resolution
  du quartier ni au geocodage de distances (C2). La commune reelle BAN (§3.1)
  est lue mais n'altere PAS `precision` ni les `facts[]` en C1.
- Le scoring 40/30/30 est inchange (le pool n'affecte que le pilier prix via les
  comparables observes, jamais une estimation).

### 3.6 Fichier de tests dedie
Tous les AC deterministes vont dans un fichier DEDIE
`backend/tests/test_issue_100_C.py` (lecon 2026-06-12 : ne pas heurter un oracle
de harnais executant un fichier existant en sous-processus ; ne pas editer
`test_issue_100_A.py` / `_B.py`). Isolation via les fixtures autouse du
`conftest.py` (init_db session-scope, reset caches) ; aucun nouveau cache
module-global. Le cache geocode (`geocode._CACHE`) est en memoire : les tests qui
geocodent doivent le reinitialiser ou patcher `geocode_address` (ne pas dependre
du reseau ; voir AC1).

---

## 4. Criteres d'acceptation (numerotes, testables)

> Chaque AC est observable et oraclable par pytest dans
> `backend/tests/test_issue_100_C.py`. Les AC de pool s'appuient sur une DB de
> test peuplee (fixtures `Comparable`), pas sur la prod. Les AC geocode patchent
> la couche reseau (pas d'appel BAN reel en CI).

### Commune reelle BAN (§3.1)

**AC1 — `geocode_address` expose city/citycode/postcode depuis la reponse BAN.**
En patchant `requests.get` pour renvoyer une feature BAN avec
`properties = {score: 0.9, postcode: "57000", city: "Metz", citycode: "57463",
label: "..."}` et `geometry.coordinates = [lon, lat]`, le dict renvoye contient
`result["city"] == "Metz"`, `result["citycode"] == "57463"`,
`result["postcode"] == "57000"`, en plus de `lat`/`lon`/`score`/`label`.
Falsifiabilite : rouge si l'un des trois champs est absent du dict.

**AC1b — champs manquants -> None, garde-fous inchanges.**
(a) Si la reponse BAN n'a ni `city` ni `citycode`, le dict renvoye porte
`city is None` et `citycode is None` (pas de KeyError, pas d'exception).
(b) Une feature dont `postcode` commence par `"54"` (hors dept 57) renvoie
toujours `None` (garde-fou inchange) ; un score `< 0.4` renvoie toujours `None`.
Falsifiabilite : rouge si l'enrichissement casse le repli/garde-fou existant ou
leve sur champ absent.

### Table curatee d'inter-communalite (§3.2, §3.3)

**AC2 — Schema + derivation de la table inter-communale.**
1. `GazetteerEntry` possede un champ `communes: Tuple[str, ...]` de defaut `()`.
2. `gazetteer.intercommunal_districts()` renvoie un dict contenant
   `"Sainte-Therese": ("Metz", "Montigny-Les-Metz")` (communes canonicalisees,
   ordre preserve, dedoublonne).
3. Toute commune presente dans une valeur de la table appartient a
   `market_stats._METRO_CITIES` (aucune commune hors perimetre).
Falsifiabilite : rouge si le champ manque, si Botanique/Sainte-Therese n'est pas
dans la table, ou si une commune declaree sort de `_METRO_CITIES`.

**AC3 — Quartiers mono-commune ABSENTS de la table (pas d'elargissement par defaut).**
Pour chaque entree dont `communes` est `()` (toutes les entrees historiques), la
cle correspondante est ABSENTE de `intercommunal_districts()` (la table ne
contient QUE des quartiers >= 2 communes). En particulier `"Sablon"`,
`"Borny"`, `"Centre-Ville"` ne sont pas des cles de la table.
Falsifiabilite : rouge si la table contient un `(commune,)` singleton redondant
ou un quartier mono-commune.

### Activation cote market_stats (§3.4)

**AC4 — Pool inter-communal au niveau quartier (cas Botanique, DB de test).**
DB de test peuplee de comparables `appartement` de surface comparable :
N1 a `city="Metz", district="Sainte-Therese"` et N2 a
`city="Montigny-Les-Metz", district="Sainte-Therese"`, avec N1+N2 >=
`MIN_REFINED_COMPARABLES` mais N1 seul < `MIN_REFINED_COMPARABLES`.
`compute_market_stats(city="Metz", district="Sainte-Thérèse", ...)` retourne
`scope == "quartier"` et `count == N1 + N2` (les deux communes reunies au niveau
quartier).
Falsifiabilite : rouge si le pool reste limite a `Metz` seul (count == N1) ou si
le scope retombe sur secteur/ville faute d'avoir reuni les communes.

**AC5 — `_fetch_comparables` recoit bien `cities` pour le niveau quartier
inter-communal (sonde de l'appel).**
En espionnant `_fetch_comparables` (ou via un comparable temoin), pour un bien
resolu vers `Sainte-Therese`, l'appel du niveau quartier passe
`cities == ("Metz", "Montigny-Les-Metz")` (ou ensemble equivalent) ET
`district == "Sainte-Therese"`. Pour un bien resolu vers un quartier
mono-commune (ex. `Sablon`), l'appel du niveau quartier passe `cities is None`.
Falsifiabilite : rouge si `cities` n'est pas transmis pour l'inter-communal, ou
s'il est transmis a tort pour un quartier mono-commune.

### Non-regression / repli silencieux (D4) — CONTRAT CENTRAL

**AC NR1 — Sans adresse : pool ET sortie identiques a A/B.**
Pour un meme `raw_text` (sans adresse) et une meme DB, `run_full_analysis(...)`
sans adresse produit un resultat dont le pilier prix (`scope`, `scope_name`,
`n_comparables`, `verdict`, `explanation`) et le `local_context` sont identiques
a un golden capture sur le comportement AVANT C1 pour un quartier
**mono-commune** (ex. Sablon). Aucun champ nouveau dans la reponse.
Falsifiabilite : rouge si C1 modifie le pool ou la sortie d'un bien mono-commune
sans adresse.

**AC NR2 — Quartier inter-communal SANS adresse : la table agit quand meme
(comportement voulu, pas une regression).**
Pour `Sainte-Therese` resolu depuis le TEXTE (sans adresse, via l'alias
`"Sainte-Thérèse / Botanique"`), `compute_market_stats` reunit deja les deux
communes au niveau quartier (meme assertion qu'AC4). Ceci documente que la table
(D2) aide MEME sans adresse, contrairement a la commune reelle BAN (D3) qui
exige une adresse.
Falsifiabilite : rouge si l'elargissement ne s'active que via une adresse
(confusion D2/D3).

**AC NR3 — Geocodage en echec : repli identique a A/B.**
En patchant `geocode_address` pour renvoyer `None` (reseau indisponible / score
faible / hors dept), `run_full_analysis(..., address="...")` produit exactement
le meme `local_context` (`precision == "quartier"`) et le meme pilier prix que
sans adresse — aucun nouveau signalement, aucun champ ajoute (branche `else`
inchangee, `analysis.py:198-219`).
Falsifiabilite : rouge si l'echec de geocodage change la sortie ou introduit un
signalement.

### Invariants (D5, conformite)

**AC C5 — Contrat `/analyze` et `api.ts` inchanges.**
1. Le `set` des cles de la reponse `/analyze` (et de chaque pilier, et de
   `local_context`) est identique a l'etat pre-C1 (aucune cle ajoutee/retiree).
2. Test statique : `frontend/lib/api.ts` n'est pas modifie par C1 (aucun champ
   `local_context`/pilier ajoute).
Falsifiabilite : rouge si une cle de reponse apparait/disparait, ou si `api.ts`
doit changer.

**AC C6 — Pas de fake precision (elargissement borne).**
La table inter-communale ne contient que des quartiers explicitement declares.
Test : aucun quartier mono-commune ne declenche `cities` non vide (= AC3 + AC5
volet mono-commune) ; il n'existe AUCUN code activant `cities` au niveau quartier
sur un critere de distance/frontiere (revue : seul `intercommunal_districts()`
alimente l'elargissement quartier).
Falsifiabilite : rouge si un chemin elargit le pool quartier hors table curatee.

**AC C7 — Pas de persistance d'adresse / coordonnees (RGPD non regresse).**
Test statique/comportemental : C1 n'ajoute aucune ecriture en base d'adresse, de
`city`/`citycode` BAN ou de coordonnees nominatives. Le cache geocode reste en
memoire (`geocode._CACHE`), aucun nouveau modele/colonne.
Falsifiabilite : rouge si un champ adresse/coordonnees est persiste.

**AC C8 — `centroid` toujours None, pas de nouveau quartier (borne C2).**
Toute entree du gazetteer conserve `centroid is None` ; le nombre d'entrees du
gazetteer est inchange vs B (C1 n'ajoute aucun quartier ; il ajoute seulement le
champ `communes` et le declare sur Sainte-Therese).
Falsifiabilite : rouge si un centroide est rempli (sur-perimetre C2) ou si une
entree est ajoutee.

**AC C9 — Robustesse a l'ordre d'import (cycle).**
`python -c "import app.geo_gazetteer"` et `python -c "import scrapers.base"`
reussissent chacun en premier import (process separes). La fonction
`intercommunal_districts` n'importe `canonical_city` que paresseusement.
Falsifiabilite : rouge si un import top-level recree un cycle (lecon 2026-06-16).

**AC C10 — `canonical_district` / `canonical_city` non modifiees.**
Caracterisation inchangee sur un echantillon de libelles bruts (« Montigny-lès-Metz »
-> « Montigny-Les-Metz », « Metz - Sainte-Thérèse » -> « Sainte-Therese »). C1
appelle ces fonctions, ne les reecrit pas.
Falsifiabilite : rouge si une de ces fonctions change de sortie.

### Pas d'eval LLM (justification)
C1 ne touche ni le prompt ni la sortie LLM : commune reelle = lecture d'une
reponse HTTP deja recue ; table inter-communale = donnee curatee deterministe ;
activation `cities` = selection SQL deterministe. Tous les AC sont
deterministes (suite gratuite `backend/tests/`). Un cas d'eval payant
n'apporterait aucune garantie supplementaire (CONTEXT frugalite). Si une
correction future touchait l'extraction LLM du quartier inter-communal, ELLE
justifierait un cas d'eval — pas C1.

---

## 5. Hors-perimetre / non-objectifs (rappel borne, pour cadrer dev et testeur)

- **C2** (quartier reel par coordonnees) : aucun point-in-polygon, aucun
  centroide rempli, aucune alimentation de `_resolve_district` par le geocode.
  La commune reelle BAN est LUE (§3.1) mais n'altere ni `precision` ni le
  quartier resolu en C1.
- **C3** (POI ecoles) : aucun vendor, aucun snapshot, aucun `fact` ecole.
- Pas de regle generique de frontiere (C1b rejetee) ; activation 100% curatee.
- Pas de modification de `canonical_district` / `canonical_city` (AC C10).
- Pas de modification du contrat `/analyze` ni de `frontend/lib/api.ts` (AC C5).
- Pas d'ajout de quartier ; pas de generalisation hors Metz Metropole.
- Pas de persistance d'adresse/coordonnees (AC C7).
- Pas de nouveau lookup en base par-ligne a l'ingestion : C1 agit a l'ANALYSE,
  en memoire. La table inter-communale est derivee a l'import (lecon index
  2026-06-14 : NON applicable car C1 est hors du chemin d'ecriture ; INTERDIT de
  l'y porter).

---

## 6. Risques / points d'attention (developpeur & testeur)

1. **[MAJEUR] Fake precision / dilution du pool.** N'elargir le niveau quartier
   QU'aux communes de la table curatee. Le testeur verrouille qu'un quartier
   mono-commune ne recoit JAMAIS `cities` non vide (AC3, AC5, AC6). Risque
   symetrique : declarer trop de communes sur Botanique diluerait le pool — la
   table se limite a `{Metz, Montigny-Les-Metz}`, communes effectivement a
   cheval, toutes deux dans `_METRO_CITIES`.

2. **[MAJEUR] Faux-vert de non-regression.** Le coeur de C1 est « ne rien
   changer hors inter-communal ». Le golden NR1 doit etre capture sur le
   comportement AVANT branchement (litteral fige dans le fichier de tests, pas
   regenere apres coup — lecons faux-vert 2026-06-09 9.10 / 2026-06-13). Capturer
   pilier prix + `local_context` complets pour un bien mono-commune.

3. **[MOYEN] Canonicalisation des communes.** Les communes de la table sont
   saisies en forme brute (« Montigny-lès-Metz ») et doivent etre canonicalisees
   (« Montigny-Les-Metz ») pour matcher `Comparable.city` (canonicalisee a
   l'ingestion). Une commune declaree dans une forme qui ne canonicalise pas vers
   une entree de `_METRO_CITIES` ne ramenerait aucun comparable (filet vide) :
   AC2 verrouille l'appartenance a `_METRO_CITIES` apres canonicalisation.

4. **[MOYEN] Cycle d'import.** `intercommunal_districts` doit importer
   `canonical_city` paresseusement (comme `build_sector_maps`), jamais au
   top-level de `geo_gazetteer`. Verifier `python -c "import ..."` dans les deux
   sens (AC C9, lecon 2026-06-16).

5. **[MOYEN] Cache geocode en memoire pollue les tests.** `geocode._CACHE` (TTL
   30j) survit entre tests d'une meme session. Tout test geocode doit patcher la
   couche reseau ET/OU reinitialiser `_CACHE` en entree (lecons cache global
   9.7 / photo-evidence). Ne jamais dependre d'un appel BAN reel en CI.

6. **[FAIBLE] Dependance a `_METRO_CITIES`.** La contrainte AC2 (« communes de la
   table ⊆ `_METRO_CITIES` ») couple le gazetteer a `market_stats`. C'est voulu
   (on n'elargit jamais hors metropole) ; verifier l'absence de cycle d'import
   induit (lire `_METRO_CITIES` cote test, pas en top-level du gazetteer).

7. **[FAIBLE] Egress BAN.** C1 n'ajoute aucun appel reseau ; il lit la reponse
   deja obtenue. Si l'egress BAN est bloque (prod/CI), `geo` reste `None` -> repli
   AC NR3, sans regression. La commune reelle (D3) est alors simplement absente,
   mais la table inter-communale (D2) continue d'agir depuis le texte.

8. **[FAIBLE] Ordre testeur -> reviewer.** Phase B : figer le fichier de tests
   (testeur) AVANT la review (lecon 2026-06-09 atelier).

---

## 7. Conformite (anti-patterns applicables)

- **Pas de fake precision (CONTEXT §1.4)** : elargissement du pool 100% borne a
  une table curatee ; jamais de seuil de distance arbitraire (AC C6).
- **Pas d'estimation de prix / pas de DVF** : C1 ne touche ni scoring ni
  quartiles ; il ne fait qu'elargir le pool de comparables OBSERVES (AC4).
- **Pas de redistribution d'annonces brutes** : aucun champ d'annonce brute
  ajoute ; seuls des agregats statistiques sortent (inchange).
- **Contrat `/analyze` stable (CLAUDE §10)** : aucun champ de reponse modifie ;
  `frontend/lib/api.ts` non touche (AC C5).
- **Pas de secret en clair / pas de nouveau vendor / pas de nouvel egress** : on
  reutilise la reponse BAN deja obtenue (D3).
- **RGPD** : aucune persistance d'adresse / commune reelle / coordonnees ; cache
  geocode en memoire uniquement (AC C7).
- **Logging nomme, Python 3.12, pas de commentaire « what », pas d'emoji**
  (CLAUDE §12) : respecter dans tout code ajoute (`geocode.py`,
  `geo_gazetteer.py`, `market_stats.py`).

---

## 8. Decoupage des push (recapitulatif)

| Push | Contenu | Tests / AC |
|---|---|---|
| 0 | Golden NR1 fige (comportement pre-C1, mono-commune) + champ `communes` au schema + `intercommunal_districts()` non branche | AC2, AC3, AC C8, AC C9 ; capture golden NR1 |
| 1 | Enrichir `geocode_address` (city/citycode/postcode) | AC1, AC1b, AC C7 (volet geocode) |
| 2 | Brancher l'activation `cities` au niveau quartier dans `compute_market_stats` | AC4, AC5, AC NR1, AC NR2, AC C6 |
| 3 | Invariants finaux | AC NR3, AC C5, AC C10, AC C7 (complet) |

Regle de cloture (lecon 2026-06-12) : a chaque push, diff du commit confronte au
contenu ci-dessus ; `test_issue_100_A.py` / `_B.py` verifies inchanges ; aucun
golden NR1 regenere depuis le code C1.

---

SPEC prête pour GATE 2 (approbation humaine).

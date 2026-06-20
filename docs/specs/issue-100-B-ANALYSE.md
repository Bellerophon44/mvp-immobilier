# Analyse de faisabilité — issue #100, chantier B (gazetteer unique)

> Palier 2 du référentiel géographique : unifier les **4 référentiels
> aujourd'hui dupliqués** en **une source de vérité unique** (gazetteer) dont
> DÉRIVENT les 4 usages, avec migration SANS régression.
>
> Statut : analyse pré-GATE 1, LECTURE SEULE du code (ce document est le seul
> livrable écrit). Ne décide rien de structurant : remonte les arbitrages.
> S'appuie sur : `docs/specs/issue-100-ANALYSE.md` (§4 chantier B, §8-3),
> `docs/specs/issue-100-A-ANALYSE.md` + `-A-SPEC.md` (acquis du palier A),
> `.claude/lessons.md`, `backend/CLAUDE.md` (§1, §7, §10, §11, §12), `CONTEXT.md`
> §11. Code réel relu et cité en `fichier:ligne` (l'état du code prime).
>
> Périmètre rappel (ombrelle §4) : in = unifier les 4 listes en un gazetteer ;
> out = géocodage réel / centroïdes mesurés / inter-communal Botanique (= chantier
> C). Le gazetteer peut PRÉVOIR un champ centroïde mais B ne géocode pas.

---

## 0. TL;DR analyste — verdict de faisabilité

- **Faisable, mais c'est le chantier le plus à risque de la feuille de route**,
  parce qu'il touche **un invariant déjà en production** : `canonical_district`
  et `canonical_city` ne servent PAS que l'analyse — ils produisent la valeur
  `Comparable.district` / `Comparable.city` **STOCKÉE en base** à l'ingestion
  (`bienici.py:268,285`). Le « référentiel » réel n'est donc pas 4 listes en
  mémoire : c'est **4 listes + une fonction de normalisation + ~17,7k lignes de
  stock déjà canonicalisées avec**. Toute la cohérence stock⇄requête repose sur
  le fait que la même fonction normalise les deux côtés. Le gazetteer ne doit
  PAS casser ce contrat.

- **La vraie source de duplication n'est pas « 4 listes de quartiers » mais
  deux choses distinctes mélangées** : (a) un **vocabulaire** (quels libellés/alias
  désignent quel quartier, et quelle est sa clé canonique) ; (b) des **données
  curatées par quartier** (profil, distances, secteur, commune). Le palier A a
  bien montré que le coût n'est pas les données mais la **désynchronisation du
  vocabulaire** (clés canoniques divergentes, séparateur « / », alias). Le
  gazetteer doit d'abord unifier le vocabulaire ; les données suivent.

- **Le point dur est la frontière back/front.** `frontend/lib/districts.ts` est
  un artefact TypeScript consommé au build Vercel (`page.tsx:15,1029`),
  totalement découplé du Python. Il n'existe AUCUN mécanisme de génération
  back→front aujourd'hui. Unifier « pour de vrai » exige soit un build step
  (génération de `districts.ts`), soit un endpoint API, soit on assume que le
  front reste une **projection** synchronisée par un **test de cohérence**. La
  3ᵉ voie est la moins risquée pour un MVP < 1 €/mois (voir Q2).

- **Posture adversariale — le requirement est-il sur-dimensionné ?** Partiellement.
  L'objectif « une source unique dont dérivent les 4 usages » est sain pour la
  dette, MAIS : (1) le pilote n'attend rien de B (A a déjà débloqué le cas) ;
  (2) « big-bang des 4 référentiels + génération front » est un gros refactor
  transverse pour un gain invisible à l'utilisateur. **Recommandation : réduire B
  à son cœur de valeur** = unifier le **vocabulaire backend** (un gazetteer
  Python d'où dérivent `_KNOWN_LOCALITIES`, `_ALIASES`, et les clés de
  `_PROFILES`/`_DIST_KM`/`_SECTORS_RAW`), front laissé en projection testée. Ne
  PAS investir dans un build step de génération front tant que multi-villes
  (`METZ-LOCAL.md §5`) n'est pas réellement lancé. Détail en §6 et Q3/Q4.

---

## 1. Cartographie de l'existant — les 4 référentiels et leurs clés

Le tableau ci-dessous est le cœur du diagnostic : **chaque référentiel a une
forme de clé différente**, et c'est cette hétérogénéité que B doit réconcilier.

| Référentiel | Fichier:ligne | Forme de la clé / entrée | Rôle | Canonicalisation |
|---|---|---|---|---|
| `_KNOWN_LOCALITIES` | `scrapers/base.py:333-367` | **liste** de chaînes lower-case, accents conservés (`"sainte-thérèse"`, `"montigny-lès-metz"`) + variantes sans accent | reconnaissance par substring dans un texte (`extract_district`, `base.py:370`) | aucune au stockage ; `extract_district` renvoie `locality.title()` |
| `_PROFILES` | `metz_local.py:64-170` | **dict**, clé = forme **canonique** (`canonical_city`), sans accent, tiret unique, segments capitalisés (`"Sainte-Therese"`, `"Nouvelle-Ville"`) ; valeur a un champ `name` accentué affiché | profil curaté (caractère, distances texte) | clé déjà canonique à la main |
| `_DIST_KM` | `metz_local.py:177-195` | **dict**, MÊMES clés canoniques que `_PROFILES` (duplication imposée, AC9) | distances numériques pour cohérence (couche B) | idem |
| `_ALIASES` | `metz_local.py:199-210` | **dict**, clé = forme canonique d'un libellé composé/variante → valeur = clé canonique d'un profil | remappe variantes/pièges (« / ») | clés et valeurs canoniques |
| `_SECTORS_RAW` | `market_stats.py:36-56` | **dict**, clé = **libellé secteur** (mixte : « Centre Ville » accentué affiché, MAIS « Sainte-Therese » canonique — incohérence léguée par A, cf. leçon 2026-06-16) ; valeur = liste de **libellés bruts** quartiers | cascade comparables | les libellés bruts sont canonicalisés au chargement (`_build_sector_maps`, `market_stats.py:80-93`) |
| `METZ_DISTRICTS` | `frontend/lib/districts.ts:7-25` | **liste TS** de **libellés affichés** accentués, espace (`"Nouvelle Ville"`, `"Sainte-Thérèse"`) | sélecteur front → `district_override` | aucune ; le label part tel quel à `/analyze` (`page.tsx:1030`, `api.ts`), canonicalisé côté back |

### 1.1 Le pivot réel : `canonical_district` / `canonical_city`

Toutes les formes ci-dessus convergent (ou doivent converger) via
`canonical_city` (`base.py:194-211`) et `canonical_district` (`base.py:297-315`).
C'est la VRAIE source unique fonctionnelle aujourd'hui : la clé canonique
(`canonical_city` du libellé). Le gazetteer doit s'articuler AUTOUR de cette
fonction, pas la remplacer (la réécrire est explicitement hors périmètre A et
serait un risque de régression sur le stock — voir §4).

**Divergences de représentation actuelles (sources d'incohérence)** :
- `_KNOWN_LOCALITIES` est lower-case accentué ; `_PROFILES` est canonique sans
  accent. Deux orthographes du même quartier, jamais reliées formellement —
  reliées seulement parce que `extract_district().title()` puis `canonical_city`
  retombent sur la même clé. Fragile mais fonctionnel.
- `_SECTORS_RAW` mélange clés affichées (« Centre Ville ») et clés canoniques
  (« Sainte-Therese ») depuis A (leçon 2026-06-16 : un oracle a forcé la clé
  canonique pour ce seul quartier). **B est l'occasion d'harmoniser, mais c'est
  un piège** : la clé `_SECTORS_RAW` est le `scope_name` AFFICHÉ au front
  (`market_stats.py:265`, « Dans le secteur X »). La rendre canonique partout
  changerait l'affichage (« Centre-Ville » au lieu de « Centre Ville »).

### 1.2 Incohérences de COUVERTURE entre les 4 (quartiers présents ici, absents là)

Comparaison effective des inventaires (après livraison de A) :

| Quartier (clé pivot) | `_KNOWN_LOCALITIES` | `_PROFILES`/`_DIST_KM` | `_SECTORS_RAW` (un quartier d'un secteur) | `METZ_DISTRICTS` |
|---|---|---|---|---|
| Centre-Ville | oui (`centre-ville`, `centre`) | oui | oui | oui |
| Ancienne-Ville | **NON** | oui | oui | oui (« Ancienne Ville ») |
| Nouvelle-Ville | oui (`nouvelle ville`) | oui | oui | oui |
| Les-Iles | **NON** | oui | oui | oui (« Les Îles ») |
| Outre-Seille | oui | oui | oui | oui |
| Sablon | oui | oui | oui | oui |
| Sainte-Therese | oui | oui | oui (secteur propre) | oui |
| Queuleu | oui | oui | oui | oui |
| Plantieres | oui | oui | oui | oui |
| Bellecroix | oui | oui | oui | oui |
| Borny | oui | oui | oui | oui |
| Magny | oui | oui | oui | oui |
| Vallieres | oui | oui | oui (+ « Vallières-lès-Bordes ») | oui |
| Devant-Les-Ponts | oui | oui | oui | oui |
| La-Patrotte | oui (`la patrotte`) | oui | oui (« Patrotte-Metz-Nord ») | oui |
| Grange-Aux-Bois | oui | oui | oui | oui |
| Technopole | oui | oui | oui | oui |
| Communes couronne (Montigny, Woippy…) | oui (`_KNOWN_LOCALITIES`) | **NON** (pas des quartiers) | non (sont dans `_METRO_CITIES`) | **NON** (exclu volontairement, `districts.ts:5`) |

**Incohérences avérées** (le gazetteer doit les exposer et les trancher) :
1. **« Ancienne-Ville » et « Les-Iles » sont dans `_PROFILES`/`_SECTORS_RAW`/
   `METZ_DISTRICTS` mais ABSENTS de `_KNOWN_LOCALITIES`** (`base.py:333-367`).
   Conséquence réelle : un texte d'annonce qui mentionne « Les Îles » ou
   « Ancienne Ville » SANS que le LLM extraie `listing.district` ne sera PAS
   reconnu par le repli `extract_district(raw_text)` (`analysis.py:90`). Bug
   latent de couverture, déjà présent, qu'un gazetteer corrigerait
   automatiquement (la source unique alimenterait les 4 usages).
2. **`_SECTORS_RAW` contient des libellés (« Vallières-lès-Bordes »,
   « Patrotte-Metz-Nord ») absents des autres référentiels** : ce sont des formes
   stockées en base par bien'ici, mises là pour matcher le stock, pas des
   quartiers du sélecteur. Le gazetteer doit modéliser « alias de stock » comme
   un type d'alias à part entière.
3. **`_KNOWN_LOCALITIES` contient les communes de la couronne** (Montigny, Woippy,
   Marly…) qui ne sont PAS des quartiers de Metz : `extract_district` sert aussi
   à reconnaître une commune limitrophe dans un texte. Le gazetteer « quartiers »
   ne couvre donc pas tout l'usage de `_KNOWN_LOCALITIES` (qui mêle quartiers ET
   communes). Point à trancher (Q5).

**Conclusion cartographie** : les 4 « référentiels » ne sont pas 4 vues du même
ensemble. Ils ont des **frontières différentes** (quartiers vs communes,
formes-de-stock vs formes-d'affichage) et des **clés de natures différentes**
(lower-case / canonique / affichée). C'est ce désalignement, plus que la
duplication ligne-à-ligne, qui rend l'ajout d'un quartier coûteux (palier A : 4
éditions + alias « / » + AC de convergence). Le gazetteer doit modéliser ces
distinctions explicitement, sinon il les masque sans les résoudre.

---

## 2. Faisabilité du gazetteer unique

### 2.1 Schéma commun pouvant dériver les 4 usages SANS perte d'information

Une entrée de gazetteer par quartier, clé = forme canonique pivot
(`canonical_city` du libellé, ex. `"Sainte-Therese"`). Schéma minimal couvrant
TOUS les champs réellement consommés aujourd'hui :

```
"Sainte-Therese": {
  display: "Sainte-Thérèse",          # name de _PROFILES + label METZ_DISTRICTS + scope display
  aliases_text: ["sainte-thérèse", "sainte-therese"],   # -> _KNOWN_LOCALITIES (substring lower-case)
  aliases_canon: ["Sainte-Therese-/-Botanique"],        # -> _ALIASES (clés canoniques, pièges « / »)
  aliases_stock: [],                  # formes brutes stockées en base (ex. "Vallières-lès-Bordes")
  sector: "Sainte-Therese",           # -> _SECTORS_RAW (clé secteur) ; secteurs multi-quartiers = champ partagé
  commune: "Metz",                    # commune de rattachement (prépare inter-communal C, mais B ne géocode pas)
  postal_code: "57000",               # informatif (déjà capté en base ; B le centralise)
  centroid: null,                     # PRÉVU mais non rempli en B (géocodage = chantier C)
  profile: {center, gare, caractere}, # -> _PROFILES (texte)
  dist_km: {center, gare},            # -> _DIST_KM (numérique cohérence)
  in_selector: true,                  # expose ou non au sélecteur front
}
```

Faisabilité de la dérivation des 4 usages :
- `_KNOWN_LOCALITIES` : concat de `aliases_text` de toutes les entrées (+ une
  liste séparée de communes couronne, Q5). Ordre « long avant court » (`base.py:327`)
  à reproduire par tri sur la longueur — **point d'attention** (le substring
  match dépend de l'ordre).
- `_PROFILES` / `_DIST_KM` : projection directe (`profile` / `dist_km`), clés =
  clés du gazetteer → **égalité des jeux de clés GARANTIE par construction**
  (résout structurellement l'AC9 du palier A, plus besoin d'un test d'égalité :
  une seule source).
- `_ALIASES` : concat de `aliases_canon` → `display`-clé.
- `_SECTORS_RAW` / `_DISTRICT_TO_SECTOR` : agrégation par champ `sector`. Le
  secteur multi-quartiers (« Centre Ville » = 5 quartiers) se reconstruit par
  group-by. **Attention** : le `scope_name` affiché (`market_stats.py:265`) =
  clé secteur ; il faut conserver le libellé secteur affiché (« Centre Ville »),
  donc le gazetteer a besoin d'une table secteurs séparée `{sector_key: display}`
  OU le champ `sector` porte directement le display. Modélisable, mais c'est le
  point le plus délicat (la cascade `market_stats` filtre sur les quartiers
  canoniques du secteur — `_SECTOR_DISTRICTS` — ET affiche le secteur).
- `METZ_DISTRICTS` : liste des `display` où `in_selector == true`. **Mais c'est
  du TypeScript** → voir §2.2.

**Verdict schéma** : aucun champ consommé aujourd'hui n'est perdu ; au contraire
le gazetteer rend explicites des distinctions aujourd'hui implicites (alias de
stock, commune, in_selector). Faisable côté backend.

### 2.2 Le point dur : la frontière back/front (`districts.ts`)

`districts.ts` est un module TS pur (`frontend/lib/districts.ts`), importé par
`page.tsx:15` et rendu en `<option>` (`page.tsx:1029-1031`), buildé par Vercel.
Aucun pont avec le Python n'existe. Trois stratégies, honnêtement chiffrées :

**Stratégie A — Build step de génération.** Un script (Python ou Node) lit le
gazetteer et RÉGÉNÈRE `districts.ts` (fichier commité, ou généré en CI/au build
Vercel). *Avantage* : source unique réelle, front toujours d'accord. *Coût* :
nouveau maillon de build, dépendance back→front dans le pipeline Vercel (le
build front devrait lire un artefact backend — couplage cross-stack non trivial),
risque de fichier généré désynchronisé du commit. **Sur-dimensionné pour un MVP**
tant qu'il n'y a qu'une ville et un déploiement manuel des quartiers.

**Stratégie B — Endpoint API `/districts`.** Le front fetche la liste au runtime
depuis le backend (qui dérive du gazetteer). *Avantage* : zéro duplication, vraie
source unique au runtime. *Coût* : nouvel endpoint, appel réseau supplémentaire
au chargement de la page, gestion du cas backend froid (Fly auto-stop,
`CLAUDE.md §2` `min_machines_running=0` → cold start), et le sélecteur devient
dépendant d'un fetch (dégradation si l'API est lente/down). Change le contrat
front. **Coût/bénéfice défavorable** pour une liste de 17 entrées qui bouge 1×
par chantier.

**Stratégie C — `districts.ts` reste une projection manuelle, verrouillée par un
TEST DE COHÉRENCE.** Le gazetteer backend reste la source de vérité ; `districts.ts`
en est une copie. Un test (déjà partiellement là : AC13 statique) vérifie que
**l'ensemble des labels `in_selector` du gazetteer == l'ensemble de
`METZ_DISTRICTS`**. *Avantage* : zéro nouveau maillon de build/runtime, coût
quasi nul, le test EMPÊCHE la dérive (un quartier ajouté au gazetteer sans MAJ du
front fait rougir la CI). *Inconvénient* : édition manuelle de 2 endroits à
l'ajout (mais 2 au lieu de 4, et le test garantit la cohérence). C'est
exactement le pattern « source de vérité + projection testée » que la leçon
2026-06-11 (cascade snapshots : « tout chemin doit respecter l'invariant, figé
par test ») valide.

**Recommandation analyste : Stratégie C** (voir Q2). Elle réduit honnêtement la
portée de « source unique » à « source unique côté backend + front projeté et
testé », ce qui est le bon niveau pour un MVP mono-ville. Stratégie A/B à
reconsidérer SI/QUAND multi-villes (`METZ-LOCAL.md §5`) est lancé — pas avant.

### 2.3 Format de la source : module Python vs fichier de données

- **Module Python de données** (`gazetteer.py` = un gros dict + fonctions de
  dérivation). *Avantage* : aucun parsing, typage, testable trivialement, import
  direct par `metz_local`/`market_stats`/`base`, cohérent avec l'existant (tout
  est déjà des dicts Python). Les dérivations (`_KNOWN_LOCALITIES`, etc.) sont
  des compréhensions calculées à l'import (comme `_build_sector_maps` aujourd'hui,
  `market_stats.py:96`). *Inconvénient* : pas éditable par un non-dev, pas
  multi-langage (mais on n'en a pas besoin).
- **Fichier de données (JSON/YAML/TOML)** chargé au démarrage. *Avantage* :
  éditable hors code, partageable potentiellement avec le front (lecture du même
  JSON). *Inconvénient* : ajoute un parsing + validation de schéma (sinon erreurs
  silencieuses à l'exécution — un YAML mal formé casse l'analyse en prod), perd
  le typage, YAML/TOML ajoutent une dépendance. Le « partage front » est illusoire
  sans le build step (Stratégie A) qu'on écarte.

**Recommandation analyste : module Python de données** (voir Q1). Le seul argument
fort pour JSON (partage front) tombe avec le choix Stratégie C. Le module Python
est le plus simple à migrer (on déplace des dicts existants) et à tester, et
évite d'introduire une étape de chargement/validation faillible sur le chemin
`/analyze`.

---

## 3. Plan de migration SANS régression

L'invariant à préserver : **comportement strictement identique après migration**
(mêmes clés reconnues, mêmes profils, mêmes secteurs, même sélecteur, même valeur
`Comparable.district` stockée à l'ingestion). La migration B est un **refactor
pur** (aucun changement fonctionnel attendu) — donc la stratégie est golden-master.

### 3.1 Tests de caractérisation (golden) à capturer AVANT migration

Avant de toucher quoi que ce soit, figer le comportement actuel par des tests
qui ne dépendent PAS de l'implémentation (ils passent avant ET après) :

1. **Golden des dérivés** : sérialiser et figer
   `sorted(_KNOWN_LOCALITIES)`, `sorted(_PROFILES.keys())`, `_PROFILES` complet,
   `_DIST_KM` complet, `_ALIASES` complet, `_DISTRICT_TO_SECTOR`,
   `_SECTOR_DISTRICTS`, et `METZ_DISTRICTS` (lu depuis le `.ts`). Après migration,
   les structures dérivées du gazetteer doivent être ÉGALES à ces goldens.
   *C'est le filet n°1 : si une seule entrée change, rouge.*
2. **Golden de résolution** : pour chaque libellé de `METZ_DISTRICTS` + chaque
   forme de `_KNOWN_LOCALITIES`, figer `_resolve_key(label, "Metz")` et
   `canonical_district(label, "Metz")`. Après migration : identiques.
3. **Golden de `local_context`** : pour chaque quartier, figer le dict retourné
   par `local_context(label, "Metz")` (sans C2). Après migration : identique
   champ par champ.
4. **Golden de la cascade secteur** : `_DISTRICT_TO_SECTOR` et
   `_SECTOR_DISTRICTS` complets, + pour un échantillon, le `scope_name` affiché
   (`_scope_context`, `market_stats.py:263`) — vérifie que l'AFFICHAGE secteur
   ne bouge pas.
5. **Golden ingestion** : pour un échantillon de libellés bruts bien'ici
   (« Metz - Bellecroix », « Metz - Plantières - Queuleu », « Metz »),
   `canonical_district(raw, city)` inchangé — **car cette valeur est stockée**
   (`bienici.py:285`) et doit rester cohérente avec le stock prod existant.
   **CRITIQUE** : si B modifiait `canonical_district`, le stock prod (canonicalisé
   avec l'ancienne version) divergerait du nouveau code → comparables muets. B ne
   doit PAS toucher `canonical_district`/`canonical_city` (comme A, §1 OUT).

### 3.2 Ordre de migration : référentiel par référentiel, derrière le golden

1. Créer `gazetteer.py` avec les entrées + fonctions de dérivation, SANS encore
   le brancher. Tester que chaque dérivé == golden (étape de validation pure).
2. Brancher `metz_local._PROFILES`/`_DIST_KM`/`_ALIASES` sur les dérivés du
   gazetteer (le plus isolé, pas d'impact stock). Golden 1/2/3 verts.
3. Brancher `market_stats._SECTORS_RAW` (donc `_DISTRICT_TO_SECTOR`/
   `_SECTOR_DISTRICTS`) sur le gazetteer. Golden 4 vert. **Point sensible** :
   le `scope_name` affiché — garder les libellés secteurs exacts.
4. Brancher `scrapers.base._KNOWN_LOCALITIES` sur le gazetteer (+ table communes).
   Golden 1/2 verts. **Point sensible** : l'ordre long-avant-court du substring
   match (`base.py:327`).
5. Front : aligner `METZ_DISTRICTS` (inchangé si déjà cohérent) + ajouter le
   test de cohérence gazetteer⇄`districts.ts` (Stratégie C).

Chaque étape est un commit/PR isolé, golden vert à chaque fois. Si une étape
casse un golden, on sait exactement laquelle. C'est le « migration incrémentale
référentiel par référentiel » de Q3.

### 3.3 Falsifiabilité (leçons faux-vert)

Le risque d'un refactor « tout vert » est le **faux-vert tautologique** (leçons
2026-06-09 9.10, 2026-06-13) : un golden généré DEPUIS le gazetteer migré
passerait toujours. **Les goldens doivent être capturés AVANT migration, depuis
l'ANCIEN code** (snapshot figé en littéral dans le test, ou fichier de référence
commité au commit pré-migration), pas régénérés. Sinon le test ne prouve rien.

---

## 4. Risques & pièges

1. **[MAJEUR] Couplage ingestion : `canonical_district` produit la valeur
   STOCKÉE.** `bienici.py:285` stocke `canonical_district(district_name, city)`
   dans `Comparable.district` ; `market_stats.py:183` re-canonicalise le district
   de requête. La cohérence stock⇄requête tient UNIQUEMENT parce que c'est la
   même fonction des deux côtés. Si B « unifie » en passant par le gazetteer pour
   normaliser à l'ingestion mais que le gazetteer ne connaît pas une forme brute
   non listée, la valeur stockée changerait → divergence avec ~17,7k lignes
   existantes. **Mitigation** : B ne touche PAS `canonical_*` ni le chemin
   d'ingestion ; le gazetteer dérive les LISTES, pas la fonction de
   normalisation. Golden ingestion (§3.1-5) en garde-fou.

2. **[MAJEUR] Frontière back/front non automatisable sans coût.** Voir §2.2.
   Risque de sur-ingénierie (build step/endpoint) pour un gain MVP nul.
   Mitigation : Stratégie C (projection + test).

3. **[MOYEN] Le `scope_name` secteur est un libellé d'affichage.** Harmoniser
   les clés `_SECTORS_RAW` (incohérence léguée par A : « Centre Ville » affiché vs
   « Sainte-Therese » canonique) risque de changer ce qui s'affiche au front
   (`market_stats.py:265`). Mitigation : golden 4 sur `_scope_context` ; le
   gazetteer sépare `sector_key` (canonique) et `sector_display` (affiché).

4. **[MOYEN] Ordre du substring match `_KNOWN_LOCALITIES`.** `extract_district`
   renvoie le PREMIER match (`base.py:380-382`) ; l'ordre long-avant-court évite
   qu'un libellé court masque un long (`base.py:327`). Une dérivation naïve qui
   trie alphabétiquement casserait des extractions. Mitigation : tri explicite par
   longueur décroissante dans la dérivation + golden 2.

5. **[MOYEN] Piège séparateur « / » et alias canoniques (héritage A).** Les alias
   sont des clés CANONIQUES, pas des libellés bruts (`metz_local.py:199`,
   `Sainte-Therese-/-Botanique`). Le gazetteer doit conserver `aliases_canon`
   comme des clés canoniques produites par le piège, sinon AC4 du palier A
   régresse. Mitigation : golden `_ALIASES`.

6. **[FAIBLE] Frontières quartier vs commune dans `_KNOWN_LOCALITIES`.** La liste
   mêle quartiers (gazetteer) et communes couronne (relèvent de `_METRO_CITIES`,
   `market_stats.py:64`). Le gazetteer « quartiers » ne couvre pas tout — il faut
   une table communes (ou laisser `_KNOWN_LOCALITIES` concaténer gazetteer +
   liste communes). Q5.

7. **[FAIBLE] Leçon index lookup par-ligne (2026-06-14).** NON applicable : B
   ajoute/déplace des structures EN MÉMOIRE, aucun nouveau `filter`/`get` par
   ligne à l'ingestion. À confirmer au review : aucun lookup gazetteer en base.
   (Si quelqu'un dérivait vers un mapping en table interrogé par ligne à
   l'ingestion, la leçon s'appliquerait — à proscrire en B.)

8. **[FAIBLE] Anti-patterns CONTEXT §11 / CLAUDE §1.** Respectés par construction :
   pas d'estimation (B ne touche pas le scoring), pas de redistribution (profils
   curatés), pas de fake precision (centroïdes restent `null`/non géocodés en B —
   le champ est PRÉVU mais vide, c'est honnête), contrat `/analyze` inchangé (B
   est un refactor interne, `local_context` garde son schéma), pas de secret.

9. **[PROCESS] Faux-vert de migration.** Voir §3.3 : goldens capturés depuis
   l'ancien code, jamais régénérés depuis le neuf.

---

## 5. Périmètre — ce qui est dans B vs ce qui relève de C

**IN (chantier B)** :
- Un gazetteer backend = source unique du **vocabulaire** (clés, alias, secteur,
  commune de rattachement, in_selector) + des **données curatées** (profil,
  distances) par quartier.
- Dérivation des usages backend (`_KNOWN_LOCALITIES`, `_PROFILES`, `_DIST_KM`,
  `_ALIASES`, `_SECTORS_RAW`/maps) depuis le gazetteer.
- Cohérence front via test de projection (Stratégie C recommandée).
- Champ `centroid` et `commune`/`postal_code` PRÉVUS dans le schéma (préparent C)
  mais `centroid` reste vide en B (pas de géocodage).

**OUT (chantier C, ne pas absorber)** :
- Géocodage réel / remplissage des centroïdes mesurés (`metz_local._POI` est
  déjà la couche C, hors B).
- Réconciliation inter-communale « Botanique » Metz/Montigny (filtre `city`
  exact, `market_stats.py:140` ; relève de C, déjà documenté A §2.5).
- Mapping coordonnées→quartier (polygones), POI écoles (C4).
- Toute réécriture de `canonical_district`/`canonical_city`.
- Ajout de NOUVEAUX quartiers (B unifie l'existant ; ajouter = palier A pour un
  nouveau quartier, ou attendre B fait pour l'ajouter une seule fois).

**Ce que B peut OPPORTUNÉMENT corriger** (à valider, Q4) : les incohérences de
COUVERTURE relevées en §1.2 (Ancienne-Ville/Les-Îles absents de
`_KNOWN_LOCALITIES`). Le gazetteer les corrige « gratuitement » (une source →
tous les usages). MAIS cela change le comportement (un texte « Les Îles » devient
reconnu par le repli) → ce n'est plus un refactor pur, c'est un changement
fonctionnel. À acter explicitement (corriger maintenant vs préserver à
l'identique puis corriger en lot séparé).

---

## 6. Recommandation de découpage le moins risqué

Vu la posture MVP et le risque stock/front, le découpage le moins risqué :

- **B se limite au backend.** Source unique = module Python `gazetteer.py`.
  Front = projection testée (Stratégie C), PAS de build step ni d'endpoint.
- **Migration incrémentale référentiel par référentiel**, derrière des goldens
  capturés AVANT (refactor pur, comportement identique). PR par étape (§3.2).
- **Migrer TOUS les quartiers existants d'un coup** (l'inventaire est petit, ~17
  entrées ; un gazetteer partiel laisserait deux sources de vérité = pire que le
  statu quo). Mais NE PAS ajouter de nouveau quartier dans B.
- **Ne PAS corriger les incohérences de couverture (§1.2) dans le même lot** que
  le refactor pur, OU les acter comme un changement fonctionnel séparé avec son
  propre cas de test (sinon le golden de non-régression devient contradictoire).
- Reporter Stratégie A/B (génération/endpoint front) à un éventuel chantier
  multi-villes ultérieur.

C'est un B « dégonflé » par rapport à la lettre du requirement (« source unique
dont dérivent les 4 usages », front inclus). Le gain de dette est réel (1 source
backend au lieu de 4, AC9 structurellement garanti, incohérences §1.2 visibles),
le risque est borné, le coût front quasi nul. Si le fondateur veut la version
« front généré », c'est un sur-coût à assumer explicitement (Q2).

---

## 7. QUESTIONS GATE 1 (arbitrages réservés à l'humain)

**Q1 — Format de la source unique.**
Options : (a) **module Python de données** (`gazetteer.py`, dicts + dérivations
à l'import) ; (b) fichier JSON/YAML/TOML chargé au démarrage.
*Reco* : **(a) module Python**. Le seul avantage fort de JSON (partage avec le
front) tombe avec le choix Stratégie C de Q2. Le module Python est le plus simple
à migrer (déplacement de dicts existants), typé, testable, sans étape de
chargement/validation faillible sur le chemin `/analyze`. Choisir (b) seulement
si une édition par un non-développeur est un objectif explicite.

**Q2 — Stratégie de synchronisation du front (`districts.ts`).**
Options : (A) build step qui GÉNÈRE `districts.ts` depuis le gazetteer ;
(B) endpoint API `/districts` fetché au runtime ; (C) `districts.ts` reste une
projection manuelle, verrouillée par un TEST de cohérence gazetteer⇄front.
*Reco* : **(C)**. Coût quasi nul, empêche la dérive, adapté au MVP mono-ville
(la liste bouge ~1×/chantier). (A) couple le build Vercel à un artefact backend ;
(B) ajoute un endpoint + appel réseau + cold-start Fly pour 17 entrées statiques.
Reconsidérer (A)/(B) UNIQUEMENT si multi-villes (`METZ-LOCAL.md §5`) est lancé.
*Conséquence* : « source unique » est assumée comme « unique côté backend, front
projeté et testé » — à valider par l'humain (c'est une réduction de portée du
requirement).

**Q3 — Périmètre de migration (rythme).**
Options : (a) big-bang des 4 référentiels en un lot ; (b) migration
incrémentale référentiel par référentiel derrière des goldens.
*Reco* : **(b) incrémentale**. Refactor transverse touchant un invariant de prod
(canonicalisation stock⇄requête) : isoler chaque bascule permet de localiser une
régression au commit près. Big-bang maximise le risque de faux-vert et la
difficulté de bissection.

**Q4 — Ampleur : refactor pur vs correction des incohérences de couverture.**
Options : (a) B = refactor PUR, comportement strictement identique (les
incohérences §1.2 — Ancienne-Ville/Les-Îles absents de `_KNOWN_LOCALITIES` —
restent, corrigées plus tard) ; (b) B unifie ET corrige ces incohérences au
passage (la source unique alimente les 4 usages → reconnaissance étendue).
*Reco* : **(a) refactor pur d'abord, correction en lot séparé ensuite** (avec son
propre cas de test). Mélanger refactor et changement fonctionnel rend le golden
de non-régression contradictoire et brouille la falsifiabilité. La correction
§1.2 a de la valeur (bug de couverture réel) mais doit être un changement assumé,
testé, pas un effet de bord du refactor.

**Q5 — Frontière du gazetteer : quartiers seuls, ou quartiers + communes ?**
(question révélée par le code, non listée dans le brief)
`_KNOWN_LOCALITIES` (`base.py:333`) mêle quartiers de Metz ET communes de la
couronne (Montigny, Woippy…), ces dernières vivant par ailleurs dans
`_METRO_CITIES` (`market_stats.py:64`). Options : (a) gazetteer = quartiers
seuls, et `_KNOWN_LOCALITIES` = dérivé(gazetteer) + liste communes maintenue à
part ; (b) gazetteer modélise aussi les communes (type « commune ») comme source
unique de `_METRO_CITIES` ET de la partie communes de `_KNOWN_LOCALITIES`.
*Reco* : **(a)** pour B (périmètre borné : unifier les QUARTIERS, qui est le sujet
du retour pilote). Unifier aussi les communes est un sur-périmètre ; `_METRO_CITIES`
est déjà une source unique propre (`market_stats.py:64-77`, importée par
`bienici.py` selon CLAUDE §8). Laisser la liste communes là où elle est et
seulement la concaténer.

**Q6 — Harmoniser la clé `_SECTORS_RAW` (dette léguée par A) ?**
(question révélée par le code)
La clé `_SECTORS_RAW` est tantôt un libellé affiché (« Centre Ville »), tantôt
canonique (« Sainte-Therese », forcé par un oracle, leçon 2026-06-16). Options :
(a) ne rien harmoniser, dériver tel quel (golden préserve l'affichage) ;
(b) le gazetteer sépare proprement `sector_key` (canonique) et `sector_display`
(affiché) et régularise tout. *Reco* : **(b)**, MAIS en préservant les libellés
AFFICHÉS exacts (golden 4 sur `_scope_context`) — c'est l'occasion propre de
solder cette dette sans changer l'affichage. Si le fondateur préfère zéro risque
d'affichage, (a).

---

## 8. Synthèse

- **Verdict** : faisable côté backend, à risque modéré-élevé à cause du couplage
  ingestion (stock prod canonicalisé) et de la frontière back/front non
  automatisable sans coût. Recommandation : un B « backend-only » (module Python,
  front projeté + testé), migration incrémentale derrière goldens, refactor pur.
  Le requirement « source unique dont dérivent les 4 usages, front inclus » est
  légèrement sur-dimensionné pour un MVP mono-ville : réduire la portée front est
  l'arbitrage central (Q2).
- **Risques majeurs** : (1) `canonical_district`/`canonical_city` produisent la
  valeur STOCKÉE à l'ingestion — ne pas y toucher, sinon divergence avec ~17,7k
  comparables ; (2) frontière `districts.ts` (TS pur, aucun pont Python) — pas de
  vraie « source unique » front sans build step coûteux ; (3) faux-vert de
  refactor — les goldens doivent être capturés depuis l'ANCIEN code.
- **Questions GATE 1** : Q1 format (reco module Python) ; Q2 stratégie front (reco
  projection + test de cohérence) ; Q3 rythme (reco incrémental) ; Q4 ampleur
  (reco refactor pur, correction de couverture en lot séparé) ; Q5 frontière
  quartiers/communes (reco quartiers seuls) ; Q6 dette clé `_SECTORS_RAW` (reco
  séparer key/display en préservant l'affichage).

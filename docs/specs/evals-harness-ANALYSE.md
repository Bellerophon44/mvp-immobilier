# ANALYSE — Harnais d'évaluation qualité de l'analyse (`backend/evals/`)

> Rôle : ANALYSTE (atelier). Date : 2026-06-11. Statut : pré-GATE 1.
> Référence produit : `docs/pilotes/README.md` (suite prévue n°1, lignes 64-71).
> Premier cas : issue #80 (`retour-pilote`, `gravite/bloquant-credibilite`).

---

## 1. Contexte et reformulation du besoin

### 1.1 Objectif
Transformer chaque retour pilote validé (issue GitHub `pret-atelier`) en **cas
d'évaluation versionné et rejouable avec de vrais appels LLM**, exécuté en CI
sur toute PR touchant le prompt ou le pipeline d'analyse. C'est le filet
anti-régression des corrections de prompt : une correction de prompt est
**globale** (elle modifie le comportement sur toutes les annonces), donc chaque
fix issu d'un pilote peut en casser un autre silencieusement. Sans harnais, la
boucle pilotes décrite dans `docs/pilotes/README.md` est ouverte à son dernier
maillon (« le constat devient un cas d'évaluation versionné »).

### 1.2 Périmètre IN
- Structure `backend/evals/` : format des cas, runner, helpers.
- Workflow CI dédié (pattern `diagnose-scrapers.yml` : déclenchement ciblé par
  paths, secrets, rapport en commentaire de PR).
- Le **premier cas** (issue #80), livré **rouge de façon attendue** (régression
  connue, fix non livré) sans bloquer les autres PR.
- Documentation du process « issue validée → cas d'éval » dans
  `docs/pilotes/README.md`.
- Création du secret GitHub `OPENAI_API_KEY` (action humaine, voir GATE).

### 1.3 Périmètre OUT
- Le **fix** de l'issue #80 (second chantier, qui retirera le marqueur de
  régression connue).
- L'agent de triage asynchrone (suite prévue n°2 du README pilotes).
- Toute modification du prompt, du pipeline, du schéma `/analyze`, de la DB
  prod. Ce chantier n'a **aucun effet en production** : il n'ajoute que des
  tests, un workflow et de la doc.
- Évaluation de la qualité photo (`photo_evidence`) et de l'ancrage local
  géocodé : hors v1 (extensibles plus tard avec le même format).

### 1.4 Challenge du requirement
Le requirement est bien posé et le moment est le bon : la boucle pilotes
produit déjà des findings, et la prochaine étape (corriger le prompt) est
exactement l'opération la plus risquée sans filet. Trois réserves :

1. **Une partie du besoin ne nécessite PAS le harnais payant.** Le symptôme 1
   de #80 (rendu « rez-de-chaussée ») est dans une couche **déterministe**
   (`market_stats._amenity_phrases`) testable en pytest classique, gratuit,
   dans la suite existante. Mettre cette assertion dans le harnais LLM serait
   payer (et accepter du non-déterminisme) pour tester du code déterministe.
   Le harnais LLM doit se concentrer sur ce que seul un appel réel peut
   vérifier : l'extraction structurée et les textes générés par le LLM.
2. **Risque de sur-ingénierie du format de cas.** Avec 1 cas au départ, un DSL
   déclaratif (YAML + moteur d'assertions) est prématuré. Des tests pytest avec
   une convention légère suffisent et offrent un contrôle d'oracle maximal
   (leçons : faux-verts tautologiques, mocks de façade).
3. **La valeur réelle dépend de la discipline d'alimentation** : un harnais à
   1 cas est surtout une infrastructure. Acceptable car le coût est faible et
   le flux pilotes est l'alimentation prévue — mais il faut que le process
   d'ajout soit trivial (sinon il ne sera pas suivi).

---

## 2. État du code concerné (vérifié, fichier:ligne)

### 2.1 Cause racine de l'issue #80 — qui produit quoi

Les deux symptômes viennent de **trois couches distinctes**. Le harnais doit
pouvoir les détecter indépendamment.

**Symptôme 1 — « rez-de-chaussée » sur une maison de plain-pied** (nuance du
pilier prix). Deux couches conjuguées :

- **(a) Extraction LLM** : la règle de prompt `backend/app/llm_semantic.py:101`
  dit « `floor` : numéro d'étage (entier ; rez-de-chaussée = 0) si mentionné,
  sinon null ». Pour une villa « de plain-pied », le LLM peut légitimement
  poser `floor=0`. La coercition `_coerce_int_opt`
  (`backend/app/llm_semantic.py:204-212`) conserve explicitement 0 (« 0 reste
  valide (rdc) »). Cette couche n'est observable qu'avec un **appel LLM réel**
  — c'est exactement ce que le harnais mesure.
- **(b) Rendu déterministe** : `backend/app/market_stats.py:319-343`
  (`_amenity_phrases`) rend `floor == 0` en « rez-de-chaussée »
  (`market_stats.py:328`) **sans conditionner au type de bien**. Aggravation
  structurelle : le générateur ne **peut pas** conditionner aujourd'hui, car
  `analysis._amenity_attrs` (`backend/app/analysis.py:63-70`, `_AMENITY_KEYS`)
  ne transmet pas `property_type`. La phrase finale « À pondérer : ... » est
  assemblée par `_criteria_signal` (`market_stats.py:346-375`, littéral ligne
  375) et concaténée à l'explication du pilier prix en
  `market_stats.py:433`.
- **Condition d'apparition importante pour le harnais** : le signal
  « À pondérer » n'est émis **que si** `compute_market_stats` renvoie un pool
  (≥ 3 comparables) ; base vide → pilier « Indéterminé » sans signal
  (`market_stats.py:416-429`). En CI (DB SQLite jetable vide, cf.
  `backend/tests/conftest.py:12-15`), le symptôme 1 est **invisible au niveau
  pipeline** sans seeding de comparables. La couche (b) se teste donc
  directement sur `_criteria_signal`/`_amenity_phrases` (déterministe, gratuit).

**Symptôme 2 — question « copropriété » sur une maison individuelle** :

- **Couche génération LLM** : la règle des `questions` du prompt
  (`backend/app/llm_semantic.py:95`) cite explicitement « copropriété » parmi
  les sujets d'exemple (« étage/ascenseur, charges, travaux, exposition,
  parking, nuisances, copropriété, etc. ») **sans condition sur le type de
  bien** ; le `SYSTEM_PROMPT` (`llm_semantic.py:47-53`) ne cadre pas non plus.
  Le seul générateur déterministe touchant la copropriété est
  `_amenity_actions` (`backend/app/analysis.py:103-107`), déclenché uniquement
  si `condo_fees` est non nul — pour une maison individuelle sans charges
  extraites, la question incriminée vient **du LLM**. Détectable uniquement par
  appel réel + assertion de mots-clés interdits sur la liste `questions`.

**Synthèse des couches et du mode de détection** :

| Couche | Fichier | Symptôme | Détection |
|---|---|---|---|
| Extraction LLM (`floor` depuis « plain-pied », `property_type`) | `llm_semantic.py:101`, `:215-265` | 1(a) | Appel réel, assertion sur champs structurés |
| Rendu déterministe des nuances prix | `market_stats.py:319-343`, `:375`, `:433` + `analysis.py:63-70` | 1(b) | pytest classique, sans LLM |
| Génération LLM des `questions` | `llm_semantic.py:95` | 2 | Appel réel, assertion mots-clés sur liste |

### 2.2 Infrastructure CI existante (vérifiée)

- **Aucun secret `OPENAI_API_KEY` n'existe en GitHub Actions.** `test.yml`
  (`.github/workflows/test.yml:33-34`) injecte une valeur **factice**
  (`test-key-not-real`) ; les seuls vrais secrets référencés sont
  `ADMIN_TOKEN` (`collect.yml:32`), `STAGING_ADMIN_TOKEN`
  (`collect-staging.yml:41`) et `FLY_API_TOKEN` (`deploy-backend.yml:43`).
  **Créer le secret repo `OPENAI_API_KEY` est une action humaine préalable.**
- **Pattern de référence** : `.github/workflows/diagnose-scrapers.yml` —
  déclenchement `pull_request` ciblé par `paths` (lignes 6-12), rapport posté
  en **commentaire de PR collant** via `actions/github-script` (lignes 48-70),
  job rouge sur échec (lignes 72-77).
- **Suite pytest existante** : `test.yml` lance `python -m pytest -q` depuis
  `backend/` (ligne 35). **Pas de `pytest.ini`/`pyproject.toml`** dans
  `backend/` : la collecte ramasse tout `test_*.py` sous `backend/`, donc un
  futur `backend/evals/test_*.py` serait exécuté par `test.yml` **avec la clé
  factice** → appels OpenAI en échec → fallback → cas rouges dans la suite
  gratuite. L'isolation de la collecte est un point de spec obligatoire.
- **Isolation des tests** : `backend/tests/conftest.py` force une DB SQLite
  jetable (lignes 12-15) et une clé factice (`setdefault`, ligne 16). Le
  harnais d'évals devra avoir son **propre `conftest.py`** (clé réelle exigée,
  pas de `setdefault` masquant, DB jetable propre, reset du cache LLM).
- **Cache LLM en mémoire** : `backend/app/llm_semantic.py:20-21`, `:215-219`,
  `:279`. Process CI frais → cache vide au départ ; mais si un cas est rejoué
  k fois pour la stabilité, les rejeux **frapperaient le cache** (même texte →
  même clé) et ne mesureraient rien. Leçon photo-evidence applicable : reset
  de `_CACHE` entre rejeux.
- **Coût et config LLM** : modèle `gpt-4.1-mini` (`llm_semantic.py:16`),
  température 0.2 (`:17`). 1 cas (mode `raw_text`) = **1 appel**
  `chat.completions.create` (~0,001-0,002 € l'appel, cf. CONTEXT §3.2).

### 2.3 Impact fichiers (création / modification)

| Fichier | Nature |
|---|---|
| `backend/evals/` (nouveau) : `conftest.py`, `cases/` (textes d'annonce), `test_eval_*.py`, helpers | Création |
| `.github/workflows/evals.yml` (nouveau) | Création |
| `backend/pytest.ini` (ou équivalent) : `testpaths = tests` pour exclure `evals/` de la suite gratuite | Création — **risque : vérifier que `test.yml` collecte exactement la même suite avant/après** |
| `backend/tests/test_*.py` : assertions déterministes (couche 1(b)) — peut aussi relever du chantier fix | Modification légère ou différé au chantier fix |
| `docs/pilotes/README.md` : process « issue → cas d'éval » | Modification |
| `backend/CLAUDE.md`, `CONTEXT.md` §0 | Mise à jour doc |

Aucun impact : schéma `/analyze`, `frontend/`, DB prod, prompt, scoring.

---

## 3. Options d'architecture

### 3.1 Format des cas et runner

- **Option A1 — déclaratif (YAML/JSON par cas + moteur d'assertions
  générique).** Avantages : ajout d'un cas = 1 fichier données, lisible par un
  non-dev. Inconvénients : nouvelle dépendance (PyYAML) ou JSON verbeux ; il
  faut concevoir et maintenir un mini-DSL d'assertions (champs attendus,
  mots-clés interdits, conditions) — sur-ingénierie à 1 cas ; un DSL pauvre
  pousse à des assertions molles (risque de faux-vert).
- **Option A2 — pytest : un module `test_eval_<issue>.py` par cas + texte
  d'annonce dans `evals/cases/<issue>.txt` + helpers partagés
  (`run_extraction(case)`, `assert_no_keyword(liste, mots)`).** Avantages :
  zéro dépendance, `xfail` natif, contrôle d'oracle maximal (leçons
  faux-verts), l'auteur des cas est l'atelier (pas le pilote) donc Python
  n'est pas une barrière. Inconvénients : un cas = un peu de code ; convention
  à documenter pour rester homogène.

**Recommandation : A2.** Si le volume de cas dépasse ~15-20 et que les
assertions se répètent, factoriser alors vers un déclaratif léger (paramétrage
pytest), pas avant.

### 3.2 Niveaux d'assertion (design du cas #80)

Trois niveaux, séparés pour détecter chaque couche indépendamment :

- **N1 — extraction structurée (LLM réel)** : appel direct à
  `analyze_semantic(texte)` ; assertions sur `listing` (`property_type ==
  "maison"`, `surface_m2`, `dpe == "C"`, comportement de `floor` face à
  « plain-pied »). Robuste au non-déterminisme (champs, pas texte libre).
- **N2 — textes générés (LLM réel)** : assertions par **mots-clés
  interdits/requis** sur les listes (`questions` ne contient ni « copropriété »
  ni « syndic » pour une maison individuelle), jamais d'égalité de texte.
- **N3 — rendu déterministe (sans LLM, gratuit)** : `_criteria_signal(...,
  attrs={"floor": 0, ...})` ne doit pas produire « rez-de-chaussée » pour une
  maison ; testable dans `backend/tests/` (suite gratuite). À noter : tant que
  `property_type` n'est pas transmis au générateur (`analysis.py:63-70`), ce
  test est structurellement rouge — il appartient au cas #80 (xfail) et son
  oracle survivra au fix.

Piège d'oracle : le **choix du comportement cible** (extraire `floor=null`
pour « plain-pied » vs garder `floor=0` et conditionner le rendu) est une
décision du chantier **fix**, pas du harnais. Pour que le cas #80 reste
valable quel que soit le fix retenu, ses assertions principales portent sur
les **invariants visibles par l'utilisateur** : (i) pour une maison,
l'explication du pilier prix ne contient jamais « rez-de-chaussée » ; (ii)
pour une maison individuelle, aucune question ne mentionne la copropriété.
Les assertions de couche (N1/N3) restent utiles en diagnostic mais ne doivent
pas figer prématurément le design du fix.

### 3.3 Pipeline complet vs extraction seule (v1)

Reproduire le symptôme 1 **au niveau pipeline** (`run_full_analysis`) exige de
seeder la DB d'éval avec ≥ 3 comparables maisons « Marly » synthétiques (sinon
pilier « Indéterminé », pas de « À pondérer », cf. §2.1). Options :

- **Option B1 — v1 = N1 + N2 (LLM) + N3 (déterministe), sans seeding.** Couvre
  les deux symptômes au plus près de leur couche fautive. Simple, suffisant
  pour #80.
- **Option B2 — v1 inclut un mode pipeline avec fixtures de comparables
  synthétiques.** Plus fidèle de bout en bout, mais ajoute la maintenance de
  fixtures DB et le risque d'assertions dépendantes des seuils de
  `market_stats` (cascade, bandes DPE). À réserver aux futurs cas
  `qualite/comparables`.

**Recommandation : B1** en v1, B2 quand un retour pilote portera réellement
sur le pilier prix.

### 3.4 Déclenchement CI

- **Paths proposés** (déclencheurs `pull_request`) :
  `backend/app/llm_semantic.py` (prompt + extraction),
  `backend/app/analysis.py`, `backend/app/market_stats.py`,
  `backend/app/scoring.py`, `backend/evals/**`,
  `.github/workflows/evals.yml`. Ne PAS mettre `backend/**` (brûlerait du
  budget sur chaque PR scraper/infra).
- **Anti-gaspillage** : `concurrency` avec `cancel-in-progress` par PR (un
  push annule le run précédent — pattern `deploy-backend.yml`) ;
  `workflow_dispatch` pour rejouer à la main. À ce coût (~0,01-0,05 €/run,
  §4), un déclenchement par label « run-evals » serait de la friction inutile.
- **Forks** : l'événement `pull_request` ne fournit pas les secrets aux PR de
  forks (comportement GitHub par défaut) → le job échouerait sur un fork.
  Repo mono-contributeur : risque accepté, et surtout **ne pas** passer à
  `pull_request_target` (exfiltration de secret par code de PR).
- **Rapport** : commentaire de PR collant (tableau cas / statut / assertions
  échouées / extraits des sorties LLM), pattern exact
  `diagnose-scrapers.yml:48-70`.

### 3.5 Bloquant vs informatif

- **Option C1 — informatif seulement** (le job ne fait jamais échouer la PR).
  Pas de filet réel : un rouge ignoré est un faux-vert organisationnel.
- **Option C2 — bloquant strict** (tout cas rouge bloque). Incompatible avec
  le premier cas volontairement rouge et avec le non-déterminisme LLM
  résiduel.
- **Option C3 — bloquant sur les cas attendus-verts, régressions connues en
  `xfail`.** Le job échoue si un cas attendu-vert casse ; les cas liés à un
  fix non livré sont marqués `pytest.mark.xfail(reason="issue #80, fix non
  livré")` et apparaissent dans le rapport sans bloquer.

**Recommandation : C3.** Nuance sur `strict` : pour les cas **déterministes**
(N3), `xfail(strict=True)` — le jour du fix, le XPASS force à retirer le
marqueur (mémoire exécutable, cf. leçon « fix non oraclé »). Pour les cas
**LLM** (N1/N2), `strict=False` au départ : un LLM non déterministe qui ne
reproduit pas le bug à un run donné produirait un XPASS intermittent → rouge
aléatoire. Le retrait du xfail LLM fait partie de la checklist du chantier
fix (documenté dans le process).

### 3.6 Non-déterminisme LLM

- **Température : celle de la prod (0.2, `llm_semantic.py:17`).** Forcer 0
  pour l'éval testerait un système qui n'est pas celui déployé (variante du
  « mock de façade » : on évalue la config réelle ou rien).
- **Assertions robustes** : champs structurés et mots-clés, jamais de texte
  exact (cf. §3.2).
- **Rejeux** : v1 = 1 run par cas. Si du flaky apparaît, passer à k=3 avec
  majorité **en vidant `llm_semantic._CACHE` entre rejeux** (sinon les rejeux
  frappent le cache et mesurent 3 fois le même appel — leçon photo-evidence).
  Le flaky non traité est le principal mode de mort du harnais (les devs
  re-runnent jusqu'au vert et le filet devient décoratif).
- **Retries transport** : laisser le SDK OpenAI gérer (retries réseau ≠
  rejeux de non-déterminisme).

### 3.7 Contenu d'annonce dans un repo PUBLIC (point challengé sérieusement)

`docs/pilotes/README.md` (règles de capture) tolère « un extrait court à
usage interne de qualification » dans une **issue**. Un cas versionné dans
`backend/evals/cases/` d'un **repo public** n'est plus un usage interne :
c'est une **re-publication durable** du texte d'une annonce tierce — en
tension directe avec CONTEXT §11.3 (« ne jamais re-publier texte, photos,
adresse exacte ou URL ») et avec le droit d'auteur du rédacteur de l'annonce.
L'anonymisation (retrait d'adresse) traite le volet données perso, pas le
volet redistribution/PI.

- **Option D1 — annonce synthétique** : réécrire entièrement le texte en
  conservant les **caractéristiques déclenchantes** (villa, « de plain-pied »,
  maison individuelle, ~280 m², secteur type Marly, DPE C, terrasse,
  parking...). Conforme §11.3 par construction, zéro risque PI, repo public
  sans réserve. Risque : le cas synthétique peut ne pas reproduire le bug →
  **étape de process obligatoire : vérifier (run local/CI) que le cas
  reproduit le symptôme AVANT de le committer** ; sinon reformuler en se
  rapprochant des tournures d'origine.
- **Option D2 — extrait réel court anonymisé** (< ~300 caractères). Fidélité
  maximale, mais zone grise PI dans un repo public, et contradiction de
  principe avec §11.3 que le projet s'impose ailleurs (l'endpoint `/history`
  a été conçu pour ne jamais exposer de contenu re-publiable).
- **Option D3 — stockage privé** (repo privé, gist secret, artifact chiffré).
  Résout PI mais casse la versionnabilité/relecture en PR et complexifie la
  CI — disproportionné.

**Recommandation : D1**, avec la règle de process « un cas n'est mergeable que
s'il reproduit le symptôme constaté » inscrite dans `docs/pilotes/README.md`.
Pour #80, le déclencheur est du vocabulaire générique (« de plain-pied »,
« villa », « maison individuelle ») : un texte synthétique a toutes les
chances de reproduire les deux symptômes.

---

## 4. Coût (chiffrage)

| Poste | Valeur |
|---|---|
| 1 cas, mode `raw_text` | 1 appel `gpt-4.1-mini` ≈ 0,001-0,002 € |
| Run v1 (1 cas, 1 run) | < 0,01 € |
| Projection 10 cas × 3 rejeux | ~0,05 €/run de PR |
| PR « prompt/pipeline » estimées | quelques-unes/mois → **< 0,5 €/mois** |

Compatible avec le budget MVP < 1 €/mois **à condition** que les paths de
déclenchement restent ciblés (pas `backend/**`) et que l'usage limit OpenAI
(item 9.4, toujours « à faire » d'après CONTEXT §8/§9.4) soit posé : mettre
une clé OpenAI en secret CI **augmente la surface d'usage** de la clé — 9.4
passe de « recommandé » à « prérequis fortement conseillé ».

---

## 5. Dépendances et ordre

1. **GATE 1 (humain)** : décisions §7 + création du secret repo
   `OPENAI_API_KEY` (Settings → Secrets and variables → Actions). Idéalement
   une clé dédiée projet avec usage limit (9.4). **Bloquant** : sans secret,
   le workflow ne peut pas exister utilement.
2. **Ce chantier** : `backend/evals/` + `evals.yml` + isolation de collecte
   (`pytest.ini` `testpaths = tests`, avec oracle de non-régression sur la
   collecte de `test.yml`) + cas #80 (synthétique, xfail) + doc process.
3. **Chantier fix #80** (second, dépend de celui-ci) : corrige les couches
   identifiées en §2.1, retire les xfail (strict=True déterministes le
   forcent ; xfail LLM retirés par checklist).
4. Chaque future correction de prompt issue des pilotes **dépend du harnais**
   (c'est sa raison d'être).

Aucune dépendance vers auth, email, domaine, ni vers les 9.x différés.

## 6. Risques et anti-patterns

- **Faux-verts (leçons 9.10)** : interdire tout mock du LLM dans `evals/`
  (un eval mocké est un mock de façade par définition) ; interdire les
  assertions tautologiques (ex. asserter un champ que la coercition force de
  toute façon). La revue de chaque cas doit vérifier que l'assertion échoue
  bien sur le comportement fautif (le cas #80 DOIT être rouge avant fix —
  c'est son oracle de naissance).
- **Fuite des évals dans la suite gratuite** : sans `testpaths`, `test.yml`
  collecterait `backend/evals/test_*.py` avec la clé factice → échecs OpenAI
  → fallback → rouges parasites. À verrouiller par config + test statique si
  besoin.
- **État partagé** (leçons 9.7/9.9/photo) : conftest d'évals dédié, DB
  jetable, reset `_CACHE` autouse ; ne pas réutiliser `backend/tests/conftest.py`
  tel quel (son `setdefault` de clé factice masquerait l'absence du secret).
- **Flakiness → filet décoratif** : voir §3.6 ; tout cas flaky est traité
  (assertion élargie ou k-runs), jamais ignoré.
- **Secret en CI** : jamais de `pull_request_target` ; pas d'echo de la clé ;
  rapport de PR sans données sensibles (les sorties LLM sur annonces
  synthétiques sont publiables).
- **Redistribution (§11.3)** : traité en §3.7 (annonces synthétiques).
- **RGPD** : aucun stockage de donnée personnelle (annonces synthétiques,
  pas d'utilisateur impliqué).
- **Dérive de périmètre** : le harnais évalue, il ne corrige pas. Aucune
  modification de `llm_semantic.py`/`analysis.py`/`market_stats.py` dans ce
  chantier (hors éventuel `pytest.ini`).

## 7. Effort estimé

- Harnais (structure, conftest, helpers, workflow, isolation collecte) : ~0,5 j.
- Cas #80 (annonce synthétique reproduisant les 2 symptômes + assertions
  N1/N2/N3 + vérification de reproduction) : ~0,25 j.
- Doc process (`docs/pilotes/README.md`) + MAJ `CLAUDE.md`/`CONTEXT.md` : ~0,25 j.
- **Total : ~1 jour atelier** (S/M). Coût récurrent : < 0,5 €/mois.

---

## QUESTIONS (GATE 1)

1. **Secret `OPENAI_API_KEY` en GitHub Actions (action humaine + argent).**
   Il n'existe pas aujourd'hui (vérifié : `test.yml` utilise une clé factice).
   Options : (a) réutiliser la clé prod ; (b) créer une **clé OpenAI dédiée
   CI** sur le même compte, et poser l'usage limit mensuel (item 9.4, jamais
   fait). **Reco : (b)** — révocable indépendamment de la prod, et 9.4 devient
   le garde-fou financier du harnais. Acceptes-tu de créer le secret et de
   poser la limite ?

2. **Contenu des annonces versionnées dans le repo public (légal / §11.3).**
   Options : (a) **annonce synthétique** réécrite conservant les déclencheurs,
   avec obligation de prouver la reproduction du symptôme avant merge ; (b)
   extrait réel court anonymisé (zone grise PI, repo public) ; (c) stockage
   privé (complexité disproportionnée). **Reco : (a)** — seule option
   pleinement conforme à la doctrine §11.3 que le projet s'impose partout
   ailleurs. Valides-tu, y compris le léger risque de moindre fidélité ?

3. **Statut CI : bloquant ou informatif ?** Options : (a) informatif
   (commentaire de PR seulement) ; (b) bloquant strict ; (c) **bloquant sur
   les cas attendus-verts, régressions connues en xfail** (premier cas #80
   rouge attendu, ne bloque pas). **Reco : (c)** — (a) n'est pas un filet,
   (b) est incompatible avec un premier cas volontairement rouge.

4. **Budget / fréquence de run.** Déclenchement par paths ciblés
   (`llm_semantic.py`, `analysis.py`, `market_stats.py`, `scoring.py`,
   `evals/**`) + annulation des runs obsolètes ; coût projeté < 0,5 €/mois à
   10 cas. Options : (a) ce déclenchement automatique ciblé ; (b) déclenchement
   manuel/label uniquement (moins cher, mais filet optionnel = filet oublié).
   **Reco : (a)**. Confirmes-tu le budget ?

5. **Périmètre v1 du harnais.** Options : (a) **extraction + textes LLM (N1/N2)
   avec assertions déterministes N3 dans la suite gratuite** ; (b) ajouter dès
   la v1 un mode pipeline complet avec comparables synthétiques seedés en DB
   (utile aux futurs cas pilier prix, mais maintenance de fixtures et
   assertions couplées aux seuils `market_stats`). **Reco : (a)**, (b) au
   premier retour pilote `qualite/comparables` qui l'exigera.

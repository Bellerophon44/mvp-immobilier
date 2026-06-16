# SPEC — Harnais d'évaluation qualité de l'analyse (`backend/evals/`)

> Rôle : SPEC-WRITER (atelier). Date : 2026-06-11. Statut : pré-GATE 2.
> Source : `docs/specs/evals-harness-ANALYSE.md` + arbitrages humains GATE 1
> (tous tranchés). Premier cas : issue #80 (`retour-pilote`,
> `gravite/bloquant-credibilite`).

---

## 1. Objectif et périmètre

### 1.1 Objectif

Mettre en place le filet anti-régression des corrections de prompt : chaque
retour pilote validé devient un cas d'évaluation versionné, rejoué avec de
VRAIS appels LLM par un workflow CI dédié sur toute PR touchant le prompt ou
le pipeline d'analyse. Premier cas livré : issue #80, en régression connue
(xfail), avec preuve de reproduction avant merge.

### 1.2 Périmètre IN

- `backend/evals/` : conftest dédié, cas synthétique #80, module de test,
  convention d'ajout de cas.
- `backend/pytest.ini` : isolation de la collecte (la suite gratuite ne
  collecte JAMAIS `evals/`).
- Tests déterministes gratuits (couche rendu + générateur de questions) dans
  `backend/tests/`, dont la régression connue « rez-de-chaussée » en
  `xfail(strict=True)`.
- `.github/workflows/evals.yml` : workflow CI bloquant, paths ciblés,
  commentaire de PR collant, échec explicite si secret absent.
- Documentation du process « issue validée -> cas d'éval » dans
  `docs/pilotes/README.md` ; mises à jour `backend/CLAUDE.md` et `CONTEXT.md`.

### 1.3 Périmètre OUT (non-objectifs)

- Le FIX de l'issue #80 (chantier suivant ; il retirera les marqueurs xfail).
- L'agent de triage asynchrone (suite n°2 du README pilotes).
- Toute modification de `llm_semantic.py`, `analysis.py`, `market_stats.py`,
  `scoring.py`, du schéma `/analyze`, du front, de la DB prod. Ce chantier
  n'a AUCUN effet en production.
- Pipeline complet seedé en DB (mode B2 de l'analyse) : différé au premier
  retour pilote `qualite/comparables` qui l'exigera.
- Évals photo (`photo_evidence`) et ancrage local géocodé.
- Rejeux k-runs / vote majoritaire (v1 = 1 run par cas ; à introduire
  seulement si du flaky apparaît, avec reset de `_CACHE` entre rejeux).
- Création du secret OpenAI et pose de l'usage limit : action HUMAINE
  (prérequis §3.1), pas du code.
- Required status check en branch protection (voir point remonté §8).

---

## 2. Décisions actées (GATE 1)

1. **Annonce SYNTHÉTIQUE uniquement.** Jamais d'extrait réel d'annonce
   versionné (repo public, CONTEXT §11.3, droit d'auteur). Le cas #80 est une
   réécriture fictive reproduisant les pièges : villa contemporaine de
   plain-pied ~282 m², maison individuelle avec jardin/terrasse/garage, DPE C,
   construite en 2006, suite parentale + 4 chambres. **Preuve de reproduction
   obligatoire avant merge** : le run de PR doit montrer que le cas déclenche
   les symptômes (statut XFAIL, pas XPASS — §5.4).
2. **Secret CI : `OPENAI_API_KEY` dédié CI avec usage limit côté OpenAI**,
   créé MANUELLEMENT par l'humain (hors périmètre du code). Le workflow
   échoue explicitement si le secret est absent — jamais de faux vert.
3. **CI bloquante, régressions connues en xfail**, déclenchement auto sur
   paths ciblés, pattern `diagnose-scrapers.yml` (concurrency
   cancel-in-progress, commentaire de PR collant). Les deux assertions du cas
   #80 sont des régressions CONNUES non fixées : `xfail(strict=False)` pour
   ce qui dépend du LLM non déterministe, `xfail(strict=True)` pour le
   déterministe.
4. **Périmètre v1 : extraction + textes LLM uniquement** (vrais appels). Le
   rendu déterministe (`_amenity_phrases`/`_criteria_signal`) et le
   générateur de questions déterministe (`_amenity_actions`) se testent SANS
   LLM dans `backend/tests/` (suite gratuite).

Aucun point GATE 1 ne reste ambigu. Un point d'exécution est remonté en §8
(mécanique GitHub du « bloquant »), sans remettre en cause l'arbitrage.

---

## 3. Contrat technique

### 3.1 Prérequis humain (avant merge du workflow)

| Action | Qui | Détail |
|---|---|---|
| Créer une clé OpenAI dédiée CI | Fondateur | Clé distincte de la prod, révocable indépendamment |
| Poser l'usage limit mensuel OpenAI | Fondateur | Item 9.4 — garde-fou financier du harnais |
| Créer le secret repo `OPENAI_API_KEY` | Fondateur | GitHub Settings -> Secrets and variables -> Actions |

Le code ne dépend de ce prérequis qu'à l'exécution CI : tant que le secret
n'existe pas, le workflow échoue avec un message explicite (AC18), il ne
passe jamais au vert.

### 3.2 Fichiers créés / modifiés

```
backend/
├── pytest.ini                          # CRÉÉ — [pytest] testpaths = tests
├── evals/
│   ├── conftest.py                     # CRÉÉ — garde env, DB jetable, reset cache, fixture load_case
│   ├── cases/
│   │   └── issue_80.txt                # CRÉÉ — annonce synthétique (§4)
│   └── test_eval_issue_80.py           # CRÉÉ — 1 appel LLM réel, assertions §5
└── tests/
    ├── test_issue_80_deterministic.py  # CRÉÉ — couche rendu/questions sans LLM (§6)
    └── test_evals_isolation.py         # CRÉÉ — oracle de séparation des suites (§7)

.github/workflows/evals.yml             # CRÉÉ — workflow CI (§7.2)
docs/pilotes/README.md                  # MODIFIÉ — process « issue -> cas » (§9)
backend/CLAUDE.md                       # MODIFIÉ — CI + cartographie tests/evals
CONTEXT.md                              # MODIFIÉ — §0 état courant (mention du harnais)
```

Aucun endpoint, aucune colonne DB, aucune migration, aucun changement de
`frontend/lib/api.ts`. `.github/workflows/test.yml` n'est PAS modifié.

### 3.3 Variables d'environnement et secrets

| Variable | Contexte | Comportement spécifié |
|---|---|---|
| `OPENAI_API_KEY` | Secret GitHub Actions, injecté dans le job `evals` | Obligatoire et réelle. Absente/vide/placeholder -> échec explicite (workflow ET conftest) |
| `DATABASE_PATH` | Forcée par `evals/conftest.py` | Fichier SQLite jetable suffixé pid (jamais `setdefault`, leçon 9.7 durcie) |

Valeurs de clé REFUSÉES par le conftest d'évals : non définie, chaîne vide,
`test-key-not-real` (placeholder de `test.yml`), `test-key-not-used`
(placeholder de `backend/tests/conftest.py`).

### 3.4 Invariants d'exécution du harnais

- **Aucun mock du LLM dans `evals/`** : pas de `unittest.mock`, `MagicMock`,
  `monkeypatch` sur `openai`, `client` ou `analyze_semantic`. Un eval mocké
  est un mock de façade par définition (leçons 9.10).
- **Config LLM = config prod** : les évals appellent `analyze_semantic` tel
  quel ; interdiction de réassigner `llm_semantic.TEMPERATURE`,
  `llm_semantic.MODEL_NAME` ou d'instancier un client OpenAI dans `evals/`.
- **Coût borné : 1 appel LLM par cas et par run.** Mécanisme : chaque module
  de cas porte UNE fixture `scope="module"` qui appelle `analyze_semantic`
  une seule fois ; toutes les assertions du cas consomment son résultat.
  `analyze_semantic` n'apparaît nulle part ailleurs dans `evals/` (ni dans un
  autre module hors sa propre fixture de cas, ni dans `conftest`/helpers).
- **Reset du cache module** : `llm_semantic._CACHE.clear()` en fixture
  autouse `scope="session"` au démarrage (un rejeu dans la même session
  mesurerait le cache, pas le modèle — leçon photo-evidence). Pas de clear
  par test en v1 (il forcerait un 2e appel payant pour le même cas).
- **Pas d'import de conftest sous un second nom de module** dans les tests
  (leçon cross-agence-inc1) : les helpers (`load_case`) sont exposés en
  fixtures, jamais importés depuis `conftest`.
- **DB** : v1 n'utilise pas TestClient ni la DB ; le conftest force quand
  même `DATABASE_PATH` jetable AVANT tout import `app.*` (la chaîne d'import
  de `analysis.py` touche `db/`). Si un futur cas utilise TestClient, il
  réutilisera le pattern d'isolation de `backend/tests/conftest.py`
  (init_db session-scope, resets autouse), à répliquer dans
  `evals/conftest.py` à ce moment-là.

---

## 4. Le cas synthétique `issue_80.txt`

### 4.1 Contenu requis

Texte d'annonce ENTIÈREMENT fictif, rédigé pour ce repo, longueur 400 à
1500 caractères, en français, qui DOIT contenir les déclencheurs suivants
(sous-chaînes exactes, insensibles à la casse pour la vérification) :

- `villa`
- `plain-pied`
- `maison individuelle`
- `282 m²` (surface habitable, sans « environ »)
- `DPE C` (ou `DPE : C` — la lettre C explicitement associée au DPE)
- `2006` (année de construction explicite, ex. « construite en 2006 »)
- `suite parentale` et `4 chambres`
- jardin, terrasse, garage (mentions textuelles)
- un prix exact : `565 000 €`
- une commune réelle du périmètre, sans adresse : `Marly`

### 4.2 Contenu interdit

- Toute sous-chaîne parmi : `copropriété`, `coproprietaire`, `syndic`,
  `charges` (le symptôme 2 doit venir du LLM, pas d'une mention légitime du
  texte).
- `http`, `www.`, `@` (pas d'URL, pas d'email).
- Adresse postale (numéro + rue), numéro de téléphone, nom d'agence ou de
  personne réels.
- Toute phrase recopiée d'une annonce réelle (le texte est une création).

### 4.3 Provenance

Le docstring de `test_eval_issue_80.py` référence l'issue #80 et rappelle
que le texte est synthétique (règle §11.3). Le fichier `.txt` ne contient
que le texte de l'annonce (pas de métadonnées).

---

## 5. Module d'éval `test_eval_issue_80.py`

### 5.1 Fixture d'appel unique

```python
@pytest.fixture(scope="module")
def semantic_issue_80(load_case):
    return analyze_semantic(load_case("issue_80"))
```

(Signature indicative ; `load_case` est une fixture de `evals/conftest.py`
qui lit `evals/cases/<nom>.txt`.) C'est le SEUL point d'appel du LLM.

### 5.2 Assertions bloquantes (attendues vertes — sanity d'extraction)

Sur `semantic_issue_80["listing"]` et les listes, SANS marqueur xfail :

- `property_type == "maison"`
- `surface_m2 == 282.0`
- `dpe == "C"`
- `construction_year == 2006`
- `price_total == 565000.0`
- `len(questions) >= 1` (garantit que l'assertion de régression B n'est pas
  vide par vacuité)

Ces assertions sont le pouvoir bloquant du harnais dès le jour 1 : une PR de
prompt qui casse l'extraction de ces champs met le job au rouge. Elles sont
volontairement limitées aux champs non ambigus du texte (pas d'assertion sur
`bedrooms` — « suite parentale + 4 chambres » est ambigu 4/5 ; pas
d'assertion d'égalité sur `city` ; pas de comparaison de texte libre).

### 5.3 Assertions de régression connue (xfail, non bloquantes)

Marquées `@pytest.mark.xfail(strict=False, reason="issue #80, fix non livre")` :

- **Régression A — « rez-de-chaussée » sur une maison de plain-pied**
  (invariant visible utilisateur, agnostique du fix retenu) : à partir de
  l'extraction RÉELLE, composer le rendu déterministe et asserter l'absence
  du défaut :

  ```python
  attrs = _amenity_attrs(semantic_issue_80["listing"])
  signal = _criteria_signal(listing["dpe"], construction_epoch(listing["construction_year"]), {}, attrs)
  assert "rez-de-chaussée" not in signal
  ```

  Aucune assertion sur la valeur de `floor` extraite (le choix
  `floor=null` vs rendu conditionné est une décision du chantier fix).
  Cette assertion ne consomme pas d'appel LLM supplémentaire.
- **Régression B — question copropriété sur maison individuelle** : aucune
  entrée de `semantic_issue_80["questions"]` ne contient (insensible à la
  casse) `copropriété`, `copropriete` ou `syndic`.

`strict=False` parce que le LLM est non déterministe : un run où le bug ne
se manifeste pas produit un XPASS qui ne doit PAS mettre la CI au rouge. Le
retrait de ces marqueurs appartient à la checklist du chantier fix (§9).

### 5.4 Preuve de reproduction (condition de merge du cas)

Le workflow lance pytest avec `-rxX` : les XFAIL/XPASS apparaissent
nominativement dans le rapport et le commentaire de PR. Règle de process
(inscrite au README pilotes, vérifiée par le reviewer de la PR qui introduit
le cas) : **un cas n'est mergeable que si le run de sa PR montre le statut
XFAIL (pas XPASS) sur ses assertions de régression connue**, c'est-à-dire
que l'annonce synthétique déclenche bien les symptômes. Sinon, reformuler le
texte en se rapprochant des tournures déclenchantes et repousser.

---

## 6. Tests déterministes gratuits (`backend/tests/test_issue_80_deterministic.py`)

Sans LLM, sans réseau, collectés par la suite normale (`test.yml`, clé
factice) :

- **Régression connue, `xfail(strict=True, reason="issue #80, fix non
  livre")`** : pour des `attrs` issus de `_amenity_attrs` sur un listing
  maison avec `floor=0` (et `property_type="maison"` disponible dans le
  listing source), le signal rendu (`_criteria_signal(None, None, {},
  attrs)`) ne contient pas `rez-de-chaussée`. Aujourd'hui structurellement
  rouge (`analysis._AMENITY_KEYS` ne transmet pas `property_type`,
  `market_stats.py:328` rend `floor == 0` inconditionnellement) -> XFAIL.
  `strict=True` : le jour du fix, le XPASS casse la suite et force le
  retrait du marqueur (mémoire exécutable, leçon « fix non oraclé »).
- **Garde passante (verte aujourd'hui, verrouille l'existant)** :
  `analysis._amenity_actions` sur un listing maison sans `condo_fees`
  (`condo_fees=None`) ne produit aucune question contenant `copropriété` ni
  `syndic` — fige le fait que le symptôme 2 de #80 vient du LLM, pas du
  générateur déterministe.

Note pour le chantier fix : si le fix change la signature de
`_criteria_signal`/`_amenity_phrases` (ex. ajout de `property_type`), il met
à jour ces tests ET l'assertion A de §5.3 dans le même mini-cycle.

---

## 7. Séparation des suites et workflow CI

### 7.1 Isolation de la collecte

- `backend/pytest.ini` :

  ```ini
  [pytest]
  testpaths = tests
  ```

- Effet : `python -m pytest -q` depuis `backend/` (commande inchangée de
  `test.yml`) ne collecte QUE `backend/tests/`. `backend/evals/` n'est
  collecté que par invocation explicite (`python -m pytest evals ...`), les
  arguments positionnels primant sur `testpaths`.
- Oracle dynamique (`backend/tests/test_evals_isolation.py`) : un test
  inspecte les items collectés de la session courante
  (`request.session.items`) et asserte qu'aucun chemin ne contient le
  segment `evals` — il échoue si `pytest.ini` disparaît ou si `testpaths`
  est élargi. Un second test statique lit `backend/pytest.ini` et asserte
  `testpaths = tests`.
- Non-régression de collecte : la liste de fichiers de
  `python -m pytest --collect-only -q` (défaut) est identique à celle de
  `python -m pytest --collect-only -q tests` — vérification à la revue de
  la PR (commande documentée dans la description de PR).

### 7.2 Workflow `.github/workflows/evals.yml`

Pattern `diagnose-scrapers.yml`, spécification exhaustive :

- **Déclencheurs** : `pull_request` avec `paths` EXACTEMENT :
  - `backend/app/llm_semantic.py`
  - `backend/app/analysis.py`
  - `backend/app/market_stats.py`
  - `backend/app/scoring.py`
  - `backend/evals/**`
  - `.github/workflows/evals.yml`

  plus `workflow_dispatch`. JAMAIS `backend/**` (budget), JAMAIS
  `pull_request_target` (exfiltration de secret).
- **Permissions** : `contents: read`, `pull-requests: write` (commentaire).
- **Concurrency** : `group: evals-${{ github.ref }}`,
  `cancel-in-progress: true` (pattern `deploy-backend.yml`).
- **Timeout** : `timeout-minutes: 10`.
- **Étape garde du secret** (AVANT pytest) : si
  `secrets.OPENAI_API_KEY` est vide, le step écrit un message explicite
  (ex. « Secret OPENAI_API_KEY absent : creer la cle CI dediee avec usage
  limit, cf. docs/specs/evals-harness-SPEC.md §3.1 ») et `exit 1`. La clé
  n'est JAMAIS affichée (pas d'echo de sa valeur, seulement de sa présence).
  Conséquence assumée : les PR de forks (secrets non fournis par GitHub sur
  `pull_request`) échouent explicitement — repo mono-contributeur.
- **Exécution** : `working-directory: backend`,
  `python -m pytest evals -q -rxX --tb=short` avec
  `OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}`, sortie capturée
  (`tee eval_report.txt`) et `continue-on-error: true` + `id` pour pouvoir
  poster le rapport avant de faire échouer le job.
- **Commentaire de PR collant** : `if: always() && github.event_name ==
  'pull_request'`, via `actions/github-script`, marqueur `<!-- evals -->`,
  create-or-update (même mécanique que `diagnose-scrapers.yml:48-70`),
  corps = sortie pytest (XFAIL/XPASS visibles grâce à `-rxX`), tronquée par
  la fin à 60000 caractères si nécessaire. Contenu publiable par
  construction (annonces synthétiques uniquement).
- **Statut bloquant** : step final qui `exit 1` si l'outcome du step pytest
  est `failure`. Régressions connues (xfail) n'échouent pas ; toute
  assertion bloquante (§5.2) qui casse met la PR au rouge.

### 7.3 `test.yml` inchangé

`test.yml` garde `python -m pytest -q` et sa clé factice
`test-key-not-real` : la séparation est portée par `pytest.ini`, pas par une
modification de la commande (zéro risque de dérive de la suite gratuite).

---

## 8. Point remonté (exécution, n'invalide pas GATE 1)

**« Bloquant » = job rouge sur la PR, pas required status check.** Un check
GitHub « required » en branch protection est incompatible avec un workflow
filtré par `paths` : sur les PR hors périmètre, le check attendu ne serait
jamais reporté et bloquerait le merge indéfiniment (il faudrait un workflow
compagnon « skip » qui poste un statut vert factice). V1 : le job échoue au
rouge sur la PR (même niveau de garantie que `diagnose-scrapers.yml` et
conforme à la pratique du repo mono-contributeur). Si le fondateur veut un
required check formel, c'est un mini-chantier séparé (workflow compagnon) —
décision à prendre hors de cette spec.

---

## 9. Documentation et process

### 9.1 `docs/pilotes/README.md` — section « Du retour pilote au cas d'éval »

Nouvelle section décrivant le process, avec AU MINIMUM ces règles :

1. Entrée : issue `retour-pilote` validée `pret-atelier` (GATE fondateur).
2. **Annonce synthétique obligatoire** : réécrire un texte fictif conservant
   les caractéristiques déclenchantes ; jamais d'extrait réel versionné
   (repo public, CONTEXT §11.3 + droit d'auteur). L'extrait réel reste dans
   l'issue (usage interne), pas dans le repo.
3. Convention de fichiers : `backend/evals/cases/issue_<n>.txt` +
   `backend/evals/test_eval_issue_<n>.py` ; une fixture module-scoped = un
   appel LLM par cas ; assertions sur champs structurés et mots-clés, jamais
   d'égalité de texte libre ; aucun mock du LLM.
4. Politique xfail : comportement fautif connu non fixé ->
   `xfail(reason="issue #<n>, fix non livre")`, `strict=False` si l'oracle
   dépend du LLM, `strict=True` si déterministe (ces derniers vivent dans
   `backend/tests/`).
5. **Preuve de reproduction avant merge** : le run de la PR introduisant le
   cas doit montrer XFAIL (pas XPASS) sur ses assertions de régression
   connue ; sinon reformuler le texte synthétique.
6. Checklist du chantier fix : retirer les xfail LLM (`strict=False`) à la
   main ; les xfail `strict=True` se signalent seuls par XPASS ; mettre à
   jour les tests si les signatures internes changent.
7. Tout cas flaky est traité (assertion élargie ou rejeux k=3 avec reset de
   `llm_semantic._CACHE` entre rejeux), jamais re-run jusqu'au vert.

La section « Suites prévues » est mise à jour : l'item 1 (harnais) passe à
l'état livré avec renvoi vers `backend/evals/` et cette spec.

### 9.2 Autres docs

- `backend/CLAUDE.md` : ligne CI du §2 (ajout `evals.yml`), §11 « Tests
  pytest » (mention de `backend/evals/`, séparation des suites, coût).
- `CONTEXT.md` §0 : mention du harnais livré et du prérequis secret/usage
  limit (item 9.4 acté pour la clé CI).

---

## 10. Critères d'acceptation

Chaque AC est vérifiable par un test automatisé (T) ou une inspection
statique précise (I — fichier/commande indiqués).

### Structure et séparation des suites

- **AC1 (I)** — `backend/pytest.ini` existe et contient une section
  `[pytest]` avec `testpaths = tests`.
- **AC2 (T)** — Depuis `backend/`, `python -m pytest --collect-only -q`
  (sans argument) ne liste aucun item dont le chemin contient `evals/`,
  alors que `backend/evals/test_eval_issue_80.py` existe.
- **AC3 (T)** — `backend/tests/test_evals_isolation.py` contient un test qui
  asserte, via les items de la session pytest courante, qu'aucun item
  collecté n'a un chemin contenant le segment `evals` ; ce test échoue si
  `pytest.ini` est supprimé ou si `testpaths` inclut `evals`.
- **AC4 (I)** — La liste de fichiers produite par
  `python -m pytest --collect-only -q` est identique à celle de
  `python -m pytest --collect-only -q tests` (non-régression de la suite
  gratuite ; commande et sortie jointes à la PR).
- **AC5 (T)** — Depuis `backend/` avec une clé valide,
  `python -m pytest evals --collect-only -q` ne collecte que des items sous
  `evals/` (aucun item de `tests/`).
- **AC6 (I)** — `.github/workflows/test.yml` est strictement identique à son
  état avant chantier (`git diff` vide sur ce fichier).

### Conftest d'évals (environnement)

- **AC7 (T)** — Avec `OPENAI_API_KEY` non définie, `python -m pytest evals`
  se termine avec un code retour non nul et la sortie contient
  `OPENAI_API_KEY` (échec explicite, pas de faux vert ni d'appel réseau).
- **AC8 (T)** — Même comportement qu'AC7 avec `OPENAI_API_KEY` valant
  `test-key-not-real`, `test-key-not-used` ou la chaîne vide.
- **AC9 (I)** — `backend/evals/conftest.py` force
  `os.environ["DATABASE_PATH"]` (affectation directe, pas `setdefault`) vers
  un fichier jetable suffixé par le pid, AVANT tout import de modules `app.*`
  ou `db.*`, et la garde de clé (AC7/AC8) s'exécute AVANT l'import de
  `app.llm_semantic` (qui instancie le client OpenAI à l'import).
- **AC10 (I)** — `backend/evals/conftest.py` définit une fixture autouse
  `scope="session"` qui exécute `llm_semantic._CACHE.clear()` au démarrage
  de la session.
- **AC11 (I)** — `grep -rn` sur `backend/evals/` ne retourne aucune
  occurrence de `unittest.mock`, `MagicMock`, `monkeypatch`, `OpenAI(`, ni
  d'affectation à `TEMPERATURE` ou `MODEL_NAME` (pas de mock de façade, pas
  d'override de la config prod).

### Cas #80 — annonce synthétique

- **AC12 (T)** — `backend/evals/cases/issue_80.txt` existe, fait entre 400
  et 1500 caractères, et contient (insensible à la casse) chacune des
  sous-chaînes : `villa`, `plain-pied`, `maison individuelle`, `282 m²`,
  `DPE`, `2006`, `suite parentale`, `4 chambres`, `565 000 €`, `Marly`.
  (Vérifiable par un test statique dans le module d'éval, collecté donc
  uniquement par la suite évals, ou par inspection.)
- **AC13 (T)** — Le même fichier ne contient aucune des sous-chaînes
  (insensible à la casse) : `copropriété`, `copropriete`, `syndic`,
  `charges`, `http`, `www.`, `@`.
- **AC14 (I)** — `analyze_semantic` n'est appelé qu'à UN seul endroit **par
  module de cas** : sa fixture `scope="module"` (1 appel LLM réel par cas et
  par run ; toutes les assertions du cas consomment son résultat). Il
  n'apparaît **nulle part ailleurs** dans `backend/evals/` (conftest, helpers).
  *Généralisé multi-cas (issue #100) : l'oracle vérifie « exactement 1 site par
  module + 0 hors module », au lieu de « 1 site global » (formulation mono-cas
  d'origine). Le total de sites = le nombre de cas.*

### Cas #80 — assertions

- **AC15 (T)** — Les assertions bloquantes du §5.2 existent et ne portent
  AUCUN marqueur xfail : `property_type == "maison"`,
  `surface_m2 == 282.0`, `dpe == "C"`, `construction_year == 2006`,
  `price_total == 565000.0`, `len(questions) >= 1`. Si l'une échoue,
  `python -m pytest evals` retourne un code non nul.
- **AC16 (I)** — L'assertion de régression A (le rendu composé
  `_criteria_signal(..., _amenity_attrs(listing))` sur l'extraction réelle
  ne contient pas `rez-de-chaussée`) est marquée
  `xfail(strict=False, reason="issue #80, fix non livre")` et n'effectue
  aucun appel LLM supplémentaire (réutilise la fixture). Elle n'asserte PAS
  la valeur de `floor` (design du fix non figé).
- **AC17 (I)** — L'assertion de régression B (aucun élément de `questions`
  ne contient, insensible à la casse, `copropriété`, `copropriete` ou
  `syndic`) est marquée `xfail(strict=False, reason="issue #80, fix non
  livre")`.
- **AC18 (I)** — Preuve de reproduction : le rapport pytest (`-rxX`) du run
  CI de la PR introduisant le cas montre le statut XFAIL (pas XPASS) pour
  les deux assertions AC16/AC17 (capture ou lien du run joint à la PR ;
  condition de merge inscrite au README, cf. AC27).

### Tests déterministes gratuits

- **AC19 (T)** — `backend/tests/test_issue_80_deterministic.py` contient un
  test marqué `xfail(strict=True, reason="issue #80, fix non livre")` qui
  asserte que le signal rendu pour des attrs de maison avec `floor=0` ne
  contient pas `rez-de-chaussée` ; sur le code actuel, ce test est en statut
  XFAIL (il échoue réellement) et la suite `python -m pytest -q` reste
  verte.
- **AC20 (T)** — Le même fichier contient un test PASSANT (sans xfail)
  assertant que `analysis._amenity_actions` sur un listing maison avec
  `condo_fees=None` ne renvoie aucune question contenant `copropriété` ni
  `syndic`.
- **AC21 (T)** — Ces deux tests s'exécutent sans réseau et sans clé OpenAI
  réelle (aucun import déclenchant un appel ; ils passent sous la clé
  factice de `test.yml`).

### Workflow CI

- **AC22 (I)** — `.github/workflows/evals.yml` se déclenche sur
  `pull_request` avec `paths` exactement :
  `backend/app/llm_semantic.py`, `backend/app/analysis.py`,
  `backend/app/market_stats.py`, `backend/app/scoring.py`,
  `backend/evals/**`, `.github/workflows/evals.yml` — plus
  `workflow_dispatch`. Aucune occurrence de `pull_request_target` ni d'un
  path `backend/**`.
- **AC23 (I)** — Le workflow déclare `permissions: contents: read` +
  `pull-requests: write`, un bloc `concurrency` groupé par ref avec
  `cancel-in-progress: true`, et `timeout-minutes: 10`.
- **AC24 (I)** — Un step antérieur à pytest échoue (`exit 1`) avec un
  message mentionnant `OPENAI_API_KEY` quand le secret est vide ; aucun step
  n'imprime la valeur du secret (seulement sa présence/absence).
- **AC25 (I)** — Le step pytest s'exécute en `working-directory: backend`
  avec la commande `python -m pytest evals -q -rxX --tb=short` (sortie
  capturée pour le rapport), et un step final met le job au rouge si
  l'outcome pytest est `failure` (statut bloquant : assertions §5.2 cassées
  => PR rouge ; xfail => pas d'échec).
- **AC26 (I)** — Un step `if: always()` poste/met à jour un commentaire de
  PR collant (marqueur HTML `<!-- evals -->`, create-or-update via
  `actions/github-script`) contenant la sortie pytest (XFAIL/XPASS
  visibles), tronquée à 60000 caractères maximum.

### Documentation et process

- **AC27 (I)** — `docs/pilotes/README.md` contient une section « issue ->
  cas d'éval » énonçant explicitement : annonce synthétique obligatoire
  (jamais d'extrait réel versionné), convention de nommage
  `cases/issue_<n>.txt` + `test_eval_issue_<n>.py`, 1 appel LLM par cas,
  politique xfail (strict=False LLM / strict=True déterministe dans
  `backend/tests/`), preuve de reproduction XFAIL exigée avant merge,
  checklist de retrait des xfail au chantier fix, traitement obligatoire du
  flaky. L'item 1 de « Suites prévues » est marqué livré.
- **AC28 (I)** — `backend/CLAUDE.md` mentionne `evals.yml` (table CI §2) et
  la séparation `tests/` (gratuite) vs `evals/` (payante, vrais appels) ;
  `CONTEXT.md` §0 mentionne le harnais et le prérequis clé CI dédiée +
  usage limit.

---

## 11. Conformité (anti-patterns applicables)

- **Pas de redistribution d'annonces brutes (CONTEXT §11.3)** : annonces
  synthétiques uniquement, vérifié par AC12/AC13 et la règle de process AC27.
- **RGPD** : aucune donnée personnelle (texte fictif, aucun utilisateur,
  aucune adresse/téléphone — AC13).
- **Pas d'estimation de prix** : le harnais évalue l'existant, n'introduit
  aucune logique d'estimation ; aucune modification de `app/`.
- **Pas de secret en clair** : clé uniquement via secret GitHub Actions,
  jamais loggée (AC24), jamais `pull_request_target` (AC22) ; le prérequis
  usage limit borne le risque financier.
- **Contrat `/analyze` stable** : aucun fichier de `app/`, `db/`,
  `frontend/` modifié (AC6 + périmètre §1.3) ; `frontend/lib/api.ts`
  intouché.
- **Pas de mock de façade / pas de faux vert tautologique (leçons 9.10)** :
  vrais appels LLM (AC11), régression A testée sur la couche qui compose le
  défaut (rendu réel sur extraction réelle), preuve de naissance rouge du
  cas (AC18), xfail strict=True comme mémoire exécutable (AC19).
- **État partagé (leçons 9.7/9.9/photo-evidence)** : DB jetable forcée
  (AC9), reset `_CACHE` en autouse session (AC10), pas d'import de conftest
  sous un second nom (§3.4).
- **Conventions CLAUDE §12** : Python 3.12, loggers nommés si besoin, pas de
  commentaires « what », pas d'emoji (commentaires de workflow et code sans
  accents si le style du fichier voisin l'impose).

SPEC prête pour GATE 2 (approbation humaine).

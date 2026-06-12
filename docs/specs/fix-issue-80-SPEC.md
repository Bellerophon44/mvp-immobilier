# SPEC — Fix de l'issue #80 (régressions qualité d'analyse LLM)

> Rôle : SPEC-WRITER (atelier). Date : 2026-06-12. Statut : pré-GATE 2.
> Sources : `docs/specs/fix-issue-80-ANALYSE.md` (approuvée) + arbitrages
> humains GATE 1 (tous tranchés, repris en §2) + code réel vérifié
> (`llm_semantic.py`, `analysis.py`, `market_stats.py`,
> `test_evals_harness.py`, `test_issue_80_deterministic.py`,
> `test_eval_issue_80.py`).
> Règle absolue (repo public, CONTEXT §11.3) : aucun extrait réel d'annonce
> pilote dans ce chantier — cas synthétique `backend/evals/cases/issue_80.txt`
> uniquement, qui n'est PAS modifié.

---

## 1. Objectif et périmètre

### 1.1 Objectif

Corriger les deux défauts de l'issue #80 (signal « rez-de-chaussée » pour une
maison ; question copropriété sur une maison individuelle), prouver le passage
XFAIL -> XPASS des évals, puis rendre les tests de régression bloquants
(retrait des marqueurs xfail + bascule des oracles du harnais).

### 1.2 Périmètre IN (fichiers)

| Fichier | Nature | Push |
|---|---|---|
| `backend/app/llm_semantic.py` | Champ `single_storey` (prompt, `_FALLBACK`, coercition) ; règle questions conditionnée ; filtre déterministe copropriété dans `analyze_semantic` | 1 |
| `backend/app/analysis.py` | `_AMENITY_KEYS` += `property_type`, `single_storey` ; `_amenity_actions` neutralisé pour les maisons | 1 |
| `backend/app/market_stats.py` | `_amenity_phrases` conditionné au type de bien + rendu « de plain-pied » | 1 |
| `backend/tests/test_issue_80_deterministic.py` | Nouveaux tests rendu/actions (push 1) ; retrait du xfail strict=True (push 2) | 1+2 |
| `backend/tests/test_issue_80_semantic_filter.py` | CRÉÉ — tests du filtre B et de `single_storey` (client OpenAI réel mocké, jamais la façade) | 1 |
| `backend/tests/conftest.py` | Reset autouse de `llm_semantic._CACHE` | 1 |
| `backend/evals/test_eval_issue_80.py` | Sanity bloquante `single_storey` (push 1) ; retrait des 2 xfail strict=False (push 2) | 1+2 |
| `backend/tests/test_evals_harness.py` | Bascule des 5 oracles vers l'état post-fix | 2 |
| `docs/pilotes/README.md` | Checklist fix complétée (oracles du harnais) | 2 |
| `CONTEXT.md` §0, `backend/CLAUDE.md` §11 | « régressions connues en xfail » -> cas bloquants, fix livré | 2 |

### 1.3 Périmètre OUT (non-objectifs)

- Aucun changement du schéma de réponse `/analyze` ni de
  `frontend/lib/api.ts` (le contenu des listes change, pas le contrat ; le
  champ `single_storey` est interne au pipeline, jamais exposé).
- Aucune colonne ajoutée à `Comparable` ni à aucune table : `single_storey`
  est un champ d'ANALYSE de l'annonce soumise, pas un critère de collecte.
  Aucune migration, aucune variable d'env, aucun secret.
- `backend/app/scoring.py` intouché : le signal « À pondérer » est la couche 2
  explicative — verdict et score inchangés.
- `backend/evals/cases/issue_80.txt` intouché (AC12/AC13 du harnais restent
  valides tels quels).
- Pas de nouveau cas d'éval (le cas « appartement témoin » est une suite
  identifiée, hors périmètre), pas d'extension du harnais (k-runs).
- Pas de refonte du prompt : modifications minimales et ciblées.
- Pas de question copropriété GÉNÉRÉE pour les maisons réellement en
  copropriété au-delà de l'existant (le générateur déterministe `condo_fees`
  suffit) — on ne fait que retirer le faux positif.

---

## 2. Décisions actées (GATE 1 — à la lettre)

1. **Wording « de plain-pied » avec garde-fou sémantique.** `floor == 0`
   signifie « l'annonce mentionne un rez-de-chaussée » (ex. suite parentale au
   rez-de-chaussée d'une maison à étage), PAS « bien de plain-pied ». La
   mention « de plain-pied » n'est rendue que sur PREUVE EXPLICITE : nouveau
   champ d'extraction `single_storey: boolean | null`, true UNIQUEMENT si
   l'annonce affirme explicitement le plain-pied, sinon null, jamais supposé
   (même convention que `has_elevator`). Une maison `floor == 0` sans cette
   preuve -> AUCUNE mention d'étage. Jamais « de plain-pied » pour une maison
   à étage.
2. **Portée** : pour `property_type == "maison"`, neutraliser TOUT le bloc
   étage/ascenseur — phrases de `_amenity_phrases` ET question/levier de
   `_amenity_actions`. Invariant générique, pas un patch du seul `floor == 0`.
3. **Régression B** : prompt conditionné par type de bien ET filtre
   déterministe dans `analyze_semantic` (avant la mise en cache), limité au
   cas « maison + texte sans mention copropriété/syndic + `condo_fees` null ».
4. **Séquencement** : une PR, deux pushes. Push 1 = fix (+ nouveaux tests),
   marqueurs xfail INTACTS, preuve XFAIL -> XPASS dans le rapport `evals.yml`,
   rouge `test.yml` ASSUMÉ et documenté. Push 2 = retrait des 3 marqueurs +
   bascule des oracles de `test_evals_harness.py` + docs.

Nuance de design actée par l'analyse (§5.4), reprise ici : tout
conditionnement porte sur `property_type == "maison"` EXPLICITE ; un
`property_type` null conserve le comportement actuel (conservateur — on ne
supprime pas d'information quand on ne sait pas).

Aucun point GATE 1 ne reste ambigu.

---

## 3. Contrat technique

### 3.1 Nouveau champ d'extraction `single_storey` (`llm_semantic.py`)

Champ INTERNE au pipeline (jamais dans la réponse `/analyze`, jamais en DB).

- **`USER_PROMPT_TEMPLATE`** : le format JSON du bloc `listing` gagne la ligne
  `"single_storey": boolean | null` ; une règle est ajoutée :
  `single_storey` vaut true UNIQUEMENT si l'annonce affirme explicitement que
  le bien est de plain-pied ; ne JAMAIS le déduire de la mention d'un
  rez-de-chaussée ou d'une pièce au rez-de-chaussée ; sinon null (ne pas
  supposer).
- **`_FALLBACK["listing"]`** : ajoute `"single_storey": None`.
- **Coercition** : dans le dict `listing` de `analyze_semantic`,
  `"single_storey": _coerce_bool(raw_listing.get("single_storey"))` (true /
  false / null ; toute autre valeur -> None).
- **Cache** : aucune mécanique nouvelle. `_CACHE` est en mémoire (perdu au
  restart) ; la clé reste le hash du texte ; les valeurs mises en cache
  portent désormais le champ. Aucune entrée pré-fix ne survit à un déploiement
  (pas de migration de cache). Les lectures aval passent par `.get()` (repli
  None).
- **DB** : la colonne n'existe PAS dans `Comparable` et ne doit pas y être
  ajoutée (champ d'analyse, pas de collecte ; `is_condo` côté comparables est
  sans rapport).

### 3.2 Régression A — rendu déterministe (option A1, signatures inchangées)

- **`analysis._AMENITY_KEYS`** : ajoute `"property_type"` et
  `"single_storey"`. `_amenity_attrs` les transporte donc sans changement de
  signature de `_criteria_signal` / `_amenity_phrases` (les tests existants —
  éval A et déterministe — passent au vert sans réécriture de leur corps).
- **`market_stats._amenity_phrases(attrs)`**, comportement spécifié :
  - Si `attrs.get("property_type") == "maison"` :
    - le bloc étage/ascenseur est entièrement neutralisé : aucune phrase
      « rez-de-chaussée », « Ne étage », « sans ascenseur », quelles que
      soient les valeurs de `floor` et `has_elevator` ;
    - si `attrs.get("single_storey") is True` ET que `floor` n'est pas un
      entier >= 1, la phrase `de plain-pied` est ajoutée (à la place du bloc
      étage). Garde-fou : si `floor` est un entier >= 1 (extraction
      contradictoire avec le plain-pied affirmé), AUCUNE mention n'est rendue
      — ni plain-pied, ni étage (prudence, jamais « de plain-pied » pour une
      maison à étage) ;
    - les autres phrases (terrasse, balcon, cave, parking) sont inchangées.
  - Sinon (`"appartement"` ou null) : comportement strictement identique à
    l'actuel ; `single_storey` n'a AUCUN effet (la mention « de plain-pied »
    est réservée aux maisons explicites).
- **`analysis._amenity_actions(listing)`** : si
  `listing.get("property_type") == "maison"`, la question et le levier
  « étage élevé sans ascenseur » ne sont JAMAIS produits (même invariant que
  le rendu). La question `condo_fees` est inchangée pour tous les types : un
  `condo_fees` non nul est une preuve de copropriété (horizontale comprise) —
  la question reste légitime pour une maison.

### 3.3 Régression B — prompt conditionné + filtre déterministe (option B3)

- **Prompt** (`USER_PROMPT_TEMPLATE`, règle `questions`) : conditionner les
  sujets de copropriété au type de bien — les questions copropriété / syndic /
  charges de copropriété ne s'appliquent qu'aux biens en copropriété, jamais à
  une maison individuelle. NE PAS retirer « copropriété » de la liste
  d'exemples (les appartements en ont besoin ; aucun éval appartement
  n'existe pour détecter une dégradation). `SYSTEM_PROMPT` inchangé.
- **Filtre déterministe** dans `analyze_semantic`, appliqué sur
  `semantic_output` APRÈS sa construction et AVANT `_set_cache` (le point où
  l'oracle d'éval observe ; la valeur mise en cache est la valeur filtrée).
  Conditions CUMULATIVES de déclenchement :
  1. `listing["property_type"] == "maison"` (valeur post-coercition ; null ne
     filtre pas) ;
  2. le texte d'annonce ne mentionne pas lui-même la copropriété :
     `"copropri" not in raw_text.casefold()` ET
     `"syndic" not in raw_text.casefold()` ;
  3. `listing["condo_fees"] is None`.

  Effet : retirer de `questions` ET de `negotiation_levers` tout item dont
  `str(item).casefold()` contient `copropri` ou `syndic` (couvre copropriété,
  copropriete, copropriétaire, syndic, casse incluse). L'ordre relatif des
  items conservés est préservé. Aucun autre champ n'est modifié. Le chemin
  fallback n'est pas concerné (listes vides).

### 3.4 Tests — suite gratuite (sans LLM, sans réseau)

- **`backend/tests/test_issue_80_deterministic.py`** : conserve les 2 tests
  existants (le xfail strict=True passe en XPASS au push 1, marqueur retiré au
  push 2) ; gagne les tests des AC1 à AC13 (§5).
- **`backend/tests/test_issue_80_semantic_filter.py`** (CRÉÉ) : tests du
  filtre B, de la coercition `single_storey` et du fallback. Règle absolue
  (leçon 9.10) : mocker `llm_semantic.client.chat.completions.create` (la
  vraie dépendance, qui renvoie un JSON contrôlé ou lève), JAMAIS
  monkeypatcher `analyze_semantic` ni recopier le filtre dans le test.
- **`backend/tests/conftest.py`** : fixture autouse qui exécute
  `llm_semantic._CACHE.clear()` avant chaque test (leçon photo-evidence :
  tout test assertant un compteur d'appels sur un module à cache global
  réinitialise ce cache en autouse conftest, jamais en fixture locale).
- **`backend/tests/test_evals_harness.py`** (push 2) — bascule des 5 oracles
  qui figent l'état pré-fix, état final exact :

  | Oracle | État final (push 2) |
  |---|---|
  | `test_ac16_regression_a_rendu_rez_de_chaussee_xfail` | Exige le test de régression A SANS aucun marqueur xfail (bloquant), composant toujours `_criteria_signal(_amenity_attrs(listing))` et assertant l'absence de `rez-de-chaussée`, toujours sans appel `analyze_semantic(` supplémentaire dans son corps. Échoue si un xfail est réintroduit. |
  | `test_ac17_regression_b_questions_copropriete_xfail` | Exige le test de régression B (questions + copropri + syndic) SANS marqueur xfail. |
  | `test_phase_b_fixtures_des_xfail_partagees_avec_un_test_bloquant` | Devient CONDITIONNEL : `assert tests_xfail` est supprimé ; la propriété « toute fixture d'un test xfail est partagée avec un test bloquant » reste vérifiée pour tout test xfail présent (vraie pour les futurs cas) ; `assert tests_bloquants` est conservé. |
  | `test_ac19_statique_xfail_strict_true_rez_de_chaussee` | Exige le test déterministe `rez-de-chaussée` (floor=0, maison, `_criteria_signal`) SANS marqueur xfail. |
  | `test_ac19_ac20_ac21_statuts_reels_xfail_et_passants` | Exécution réelle du fichier déterministe sous clé factice : returncode 0, au moins 1 `passed`, `xfailed` ABSENT de la sortie, `xpassed` absent, aucun `failed`. |

  Les noms de ces tests sont renommés en cohérence (ex. suffixe `_bloquant` à
  la place de `_xfail`) — les docstrings expliquent l'état post-fix.

### 3.5 Évals (payantes, `backend/evals/test_eval_issue_80.py`)

- **Push 1** : ajout d'UNE assertion de sanity bloquante (sans xfail)
  `semantic_issue_80["listing"]["single_storey"] is True` — le texte
  synthétique contient littéralement « plain-pied » (même classe de fiabilité
  que `property_type`). Consomme la fixture module existante : toujours un
  seul appel LLM par run (AC14 du harnais préservé). Les 2 marqueurs xfail
  restent INTACTS au push 1.
- **Push 2** : retrait MANUEL des 2 marqueurs `xfail(strict=False)` (un XPASS
  strict=False est silencieux — c'est la checklist, pas la CI, qui l'impose).
  Les corps des tests A et B sont inchangés.

### 3.6 Documentation (push 2)

- `docs/pilotes/README.md`, étape 6 de la checklist fix : ajouter « basculer
  les oracles de `backend/tests/test_evals_harness.py` qui figent les
  marqueurs xfail (état pré-fix) dans la même PR » (lacune identifiée par
  l'analyse §4.2, risque n°1 du chantier).
- `CONTEXT.md` §0 (~ligne 76) et `backend/CLAUDE.md` §11 (~ligne 602) :
  « régressions connues en xfail » -> cas #80 bloquants, fix livré.

---

## 4. Invariants de comportement (table de vérité du rendu)

`_amenity_phrases` — mention étage/plain-pied selon
(`property_type`, `floor`, `has_elevator`, `single_storey`) :

| property_type | floor | has_elevator | single_storey | Mention rendue |
|---|---|---|---|---|
| maison | 0 | * | None/False | (aucune) |
| maison | None | * | True | `de plain-pied` |
| maison | 0 | * | True | `de plain-pied` |
| maison | >= 1 | * | True | (aucune — contradiction, prudence) |
| maison | >= 1 | False | None | (aucune) |
| maison | None | False | None | (aucune) |
| appartement | 0 | * | * | `rez-de-chaussée` (inchangé) |
| appartement | 4 | False | * | `4e étage sans ascenseur` (inchangé) |
| null | 0 | * | * | `rez-de-chaussée` (inchangé, conservateur) |
| null | * | * | True | comportement actuel, jamais `plain-pied` |

`_amenity_actions` : question/levier étage-ascenseur jamais produits si
maison ; inchangés sinon ; question `condo_fees` inchangée pour tous.

Filtre B : actif ssi (maison explicite) ET (texte sans `copropri`/`syndic`,
casefold) ET (`condo_fees` null). Retire des deux listes les items contenant
`copropri` ou `syndic` (casefold), ordre préservé, avant mise en cache.

---

## 5. Critères d'acceptation

Chaque AC est falsifiable. (T) = test automatisé ; (I) = inspection statique
précise. Sauf mention contraire, les AC « suite gratuite » s'exécutent sous la
clé factice de `test.yml`, sans réseau.

### 5.1 Suite gratuite — rendu déterministe (`test_issue_80_deterministic.py`)

Tous via `_criteria_signal(None, None, {}, _amenity_attrs(listing))` (corps
des phrases) sauf mention :

- **AC1 (T)** — Maison, `floor=0`, sans clé `single_storey` dans le listing :
  le signal ne contient pas `rez-de-chaussée` (test xfail existant, dont le
  corps est inchangé ; XPASS au push 1, bloquant au push 2).
- **AC2 (T)** — Maison, `floor=0`, `single_storey=None`, `has_terrace=True` :
  le signal ne contient ni `rez-de-chaussée`, ni `étage`, ni `ascenseur`, ni
  `plain-pied`, ET contient `avec terrasse` (les autres phrases survivent).
- **AC3 (T)** — Maison, `floor=None`, `single_storey=True` : le signal
  contient `de plain-pied` et ne contient ni `étage`, ni `rez-de-chaussée`,
  ni `ascenseur`.
- **AC4 (T)** — Maison, `floor=0`, `single_storey=True` : le signal contient
  `de plain-pied`.
- **AC5 (T)** — Maison, `floor=2`, `single_storey=True` : le signal ne
  contient ni `plain-pied`, ni `2e étage`, ni `ascenseur` (contradiction ->
  omission).
- **AC6 (T)** — Maison, `floor=3`, `has_elevator=False`,
  `single_storey=None` : le signal ne contient ni `3e étage` ni
  `sans ascenseur` (neutralisation du bloc complet, pas du seul floor=0).
- **AC7 (T)** — Appartement, `floor=0` : le signal contient `rez-de-chaussée`
  (non-régression). Appartement, `floor=4`, `has_elevator=False` : le signal
  contient `4e étage sans ascenseur` (non-régression).
- **AC8 (T)** — Appartement, `single_storey=True` : le signal ne contient pas
  `plain-pied`.
- **AC9 (T)** — `property_type=None`, `floor=0` : le signal contient
  `rez-de-chaussée` (comportement actuel conservé, conservateur §2).

### 5.2 Suite gratuite — actions déterministes (`test_issue_80_deterministic.py`)

- **AC10 (T)** — `_amenity_actions` sur une maison `floor=5`,
  `has_elevator=False` : aucune question ni levier ne contient `étage` ou
  `ascenseur`.
- **AC11 (T)** — `_amenity_actions` sur un appartement `floor=5`,
  `has_elevator=False` : la question et le levier étage/ascenseur sont
  présents (non-régression).
- **AC12 (T)** — `_amenity_actions` sur une maison avec `condo_fees=1200` :
  la question sur les charges de copropriété est présente (copropriété
  horizontale prouvée par `condo_fees` — pas de sur-filtrage).
- **AC13 (T)** — `_AMENITY_KEYS` contient `property_type` et `single_storey`,
  et `_amenity_attrs({"property_type": "maison", "single_storey": True})` les
  restitue.

### 5.3 Suite gratuite — extraction et filtre B (`test_issue_80_semantic_filter.py`, client réel mocké)

- **AC14 (T)** — Le client mocké renvoie `"single_storey": true` ->
  `analyze_semantic(...)["listing"]["single_storey"] is True` ; renvoie
  `"oui"` (str) -> `None` ; clé absente -> `None`.
- **AC15 (T)** — Le client mocké LÈVE (chemin réel du fallback, leçon 9.10) :
  la sortie porte `listing["single_storey"] is None` et le contrat fallback
  existant (marqueur `_fallback`, listes vides) est intact.
- **AC16 (T)** — Maison, `raw_text` sans `copropri`/`syndic`,
  `condo_fees=None`, le client mocké renvoie
  `questions = ["Quel est le montant des charges de copropriété ?",
  "Y a-t-il un syndic ?", "Quelle est l'exposition ?"]` et
  `negotiation_levers = ["Copropriété sans travaux votés", "DPE C"]` ->
  la sortie vaut `questions == ["Quelle est l'exposition ?"]` et
  `negotiation_levers == ["DPE C"]` (items copropri/syndic retirés des DEUX
  listes, ordre préservé).
- **AC17 (T)** — Le filtrage est insensible à la casse : `"COPROPRIÉTÉ"` et
  `"Syndic"` sont retirés.
- **AC18 (T)** — La valeur mise en cache est la valeur FILTRÉE : un second
  appel `analyze_semantic` sur le même texte renvoie le résultat filtré avec
  `mock.call_count == 1` (cache hit, pas de re-filtrage requis).
- **AC19 (T)** — Appartement (mêmes questions mockées) : aucune question ni
  levier retiré.
- **AC20 (T)** — Maison mais `raw_text` contenant `copropriété` : aucun item
  retiré (copropriété horizontale mentionnée -> question légitime).
- **AC21 (T)** — Maison mais `condo_fees` non null dans la réponse mockée :
  aucun item retiré.
- **AC22 (T)** — `property_type` null dans la réponse mockée : aucun item
  retiré (conservateur).

### 5.4 Suite gratuite — prompt, fallback, isolation

- **AC23 (T/I)** — `USER_PROMPT_TEMPLATE` contient `"single_storey"` dans le
  format `listing` et une règle énonçant : true UNIQUEMENT si le plain-pied
  est explicitement affirmé, jamais déduit d'une mention de rez-de-chaussée,
  sinon null. `_FALLBACK["listing"]` contient `single_storey: None`.
- **AC24 (I)** — La règle `questions` du prompt conditionne les sujets
  copropriété/syndic au type de bien (jamais pour une maison individuelle) et
  `copropriété` reste présent dans la liste d'exemples. `SYSTEM_PROMPT`
  inchangé (`git diff` ne le touche pas).
- **AC25 (T)** — `backend/tests/conftest.py` définit une fixture AUTOUSE qui
  vide `llm_semantic._CACHE` avant chaque test (vérifiable statiquement ou
  par un test qui pré-remplit `_CACHE` et constate l'isolation).

### 5.5 Suite gratuite — état final des marqueurs et oracles (push 2)

- **AC26 (T/I)** — `backend/tests/test_issue_80_deterministic.py` ne contient
  plus AUCUN marqueur xfail ; `python -m pytest
  tests/test_issue_80_deterministic.py -q -rxX` retourne 0 avec uniquement
  des `passed` (ni `xfailed`, ni `xpassed`, ni `failed`).
- **AC27 (I)** — `backend/evals/test_eval_issue_80.py` ne contient plus aucun
  marqueur xfail ; les corps des tests de régression A et B sont inchangés.
- **AC28 (T)** — Oracle AC16 du harnais basculé : il exige le test de
  régression A SANS xfail (toujours `_criteria_signal` + `_amenity_attrs` +
  absence de `rez-de-chaussée`, toujours aucun `analyze_semantic(` dans le
  corps) et ÉCHOUE si un marqueur xfail y est réintroduit.
- **AC29 (T)** — Oracle AC17 du harnais basculé : test de régression B
  (questions + copropri + syndic) exigé SANS xfail.
- **AC30 (T)** — Oracle phase B basculé : plus d'exigence d'existence de
  tests xfail (`assert tests_xfail` supprimé) ; la propriété « fixtures des
  xfail partagées avec un test bloquant » reste vérifiée pour tout test xfail
  présent ; l'exigence d'au moins un test bloquant est conservée.
- **AC31 (T)** — Oracle AC19 statique basculé : test déterministe
  `rez-de-chaussée` (floor=0, maison, `_criteria_signal`) exigé SANS xfail.
- **AC32 (T)** — Oracle dynamique basculé : l'exécution réelle du fichier
  déterministe sous clé factice doit donner returncode 0, au moins 1
  `passed`, AUCUN `xfailed`, aucun `xpassed`, aucun `failed`.
- **AC33 (T)** — Au push 2, la suite gratuite complète
  (`python -m pytest -q` depuis `backend/`) est verte (les ~296 tests
  existants + les nouveaux), sans warning de collecte nouveau.

### 5.6 Suite gratuite — documentation (push 2)

- **AC34 (I)** — `docs/pilotes/README.md`, checklist du chantier fix
  (étape 6), mentionne explicitement la bascule des oracles de
  `backend/tests/test_evals_harness.py` qui figent les marqueurs xfail.
- **AC35 (I)** — `CONTEXT.md` §0 et `backend/CLAUDE.md` §11 ne décrivent plus
  le cas #80 comme « régressions connues en xfail » : ils indiquent le fix
  livré et les cas devenus bloquants.

### 5.7 Évals payantes (vrais appels LLM, `evals.yml`)

- **AC36 (T)** — Les 6 assertions de sanity existantes restent vertes
  (property_type, surface, dpe, construction_year, price_total, questions non
  vides) — aucune dérive d'extraction due au changement de prompt.
- **AC37 (T)** — Nouvelle sanity bloquante (sans xfail) :
  `listing["single_storey"] is True` sur le cas #80 (le texte contient
  littéralement « plain-pied »). Elle consomme la fixture module existante
  (toujours UN seul `analyze_semantic(` dans `evals/`, AC14 du harnais).
- **AC38 (I)** — Preuve push 1 : le rapport `-rxX` du run `evals.yml` du
  push 1 montre nominativement le statut XPASS des deux tests de régression A
  et B (marqueurs encore en place) ; le lien du run est collé dans la
  description de PR (le commentaire collant sera écrasé au push 2).
- **AC39 (T)** — Push 2 : `python -m pytest evals -q -rxX` (clé réelle) est
  vert, les ex-xfail A et B passent en BLOQUANT (un futur run où le LLM
  glisse une question copropriété mettrait la PR au rouge — impossible par
  construction du filtre déterministe au point observé par l'oracle).

---

## 6. Séquencement (une PR, deux pushes)

### Push 1 — fix + nouveaux tests, marqueurs intacts

Contenu : §3.1, §3.2, §3.3 (code) ; nouveaux tests §5.1-§5.4 ; sanity éval
AC37. AUCUN marqueur xfail retiré, `test_evals_harness.py` intouché.

État CI attendu et ASSUMÉ :
- `evals.yml` : VERT (xfail strict=False -> XPASS silencieux) ; le rapport
  `-rxX` montre les 2 XPASS nominatifs = preuve de la définition de done
  (AC38).
- `test.yml` : ROUGE, exactement par deux causes attendues : le XPASS du
  xfail strict=True de `test_issue_80_deterministic.py`, et l'échec des
  oracles du harnais qui figent l'état pré-fix
  (`test_ac19_ac20_ac21_statuts_reels...`, qui interdit `xpassed`). Toute
  AUTRE cause de rouge est un défaut à corriger avant push 2.
- Description de PR : documente le rouge attendu + lien du run `evals.yml`
  du push 1.

### Push 2 — retrait des marqueurs + bascule + docs

Contenu : retrait des 3 marqueurs xfail (2 évals strict=False à la main, 1
déterministe strict=True signalé par le XPASS) ; bascule des 5 oracles
(§3.4) ; docs (§3.6).

État CI attendu : `test.yml` VERT, `evals.yml` VERT. Condition de merge
(GATE 3) : les deux verts + AC38 vérifiable via le lien du run push 1.

Pas de variante « deux PR » : un merge intermédiaire laisserait `main` rouge
(strict=True), exclu.

---

## 7. Non-régression (récapitulatif vérifiable)

1. Suite gratuite : les ~296 tests existants verts au push 2 (AC33) ; seuls
   `test_issue_80_deterministic.py` et `test_evals_harness.py` touchent les
   couches modifiées (vérifié par l'analyse).
2. Évals : les 6 sanity passantes restent vertes (AC36).
3. Schéma `/analyze` strictement inchangé (mêmes clés, mêmes types) ;
   `frontend/lib/api.ts` intouché ; `git diff` vide sur `frontend/`.
4. `scoring.py`, `compute_market_stats`, cascade de sélection des
   comparables, `db/`, workflows CI : intouchés (`git diff` vide ;
   `evals.yml` se déclenche par ses paths existants).
5. Verdict et score du pilier prix inchangés à attrs égaux : seul le texte du
   signal « À pondérer » change (couche 2 explicative).
6. `backend/evals/cases/issue_80.txt` intouché (AC12/AC13 du harnais).

---

## 8. Conformité (anti-patterns applicables)

- **Pas d'extrait réel d'annonce** (CONTEXT §11.3, repo public) : aucun
  nouveau texte d'annonce ; le cas synthétique existant n'est pas modifié ;
  les exemples de tests (AC16) sont des chaînes génériques inventées. À
  re-vérifier sur les messages de commit en revue.
- **Pas d'estimation de prix** : « de plain-pied » est un fait observable
  affirmé par l'annonce, pas une évaluation ; aucun calcul de valeur ajouté.
- **Pas de redistribution brute** : aucune donnée d'annonce nouvelle stockée
  ni exposée ; `single_storey` reste interne.
- **Contrat `/analyze` stable** : aucune clé ajoutée/retirée à la réponse ;
  pas de MAJ front requise (vérifié : `single_storey` n'atteint jamais
  `AnalyzeResponse`).
- **Pas de secret en clair** : aucun secret touché ; les tests gratuits
  tournent sous clé factice ; les évals via le secret CI existant.
- **RGPD** : aucune donnée personnelle.
- **Leçons** : pas de mock de la façade (AC14-AC22 mockent
  `client.chat.completions.create`), pas de test tautologique (le filtre est
  testé sur la couche qui le produit, avant cache), reset de cache global en
  autouse conftest (AC25), fix oraclé dans le même mini-cycle (AC1-AC12
  verrouillent chaque branche du conditionnement).
- **Conventions CLAUDE §12** : Python 3.12, loggers nommés existants, pas de
  commentaire « what », pas d'emoji (code, commits, prompt).

SPEC prête pour GATE 2 (approbation humaine).

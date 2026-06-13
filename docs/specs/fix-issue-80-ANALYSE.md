# ANALYSE — Fix de l'issue #80 (régressions qualité d'analyse LLM)

> Rôle : ANALYSTE (atelier). Date : 2026-06-12. Statut : pré-GATE 1.
> Référence : issue GitHub #80 (`retour-pilote`, `qualite/extraction-llm`,
> `gravite/bloquant-credibilite`) ; harnais livré le 2026-06-11
> (`docs/specs/evals-harness-ANALYSE.md`, `docs/specs/evals-harness-SPEC.md`).
> Règle absolue (repo public, CONTEXT §11.3) : ce document et le chantier ne
> contiennent AUCUN extrait réel d'annonce — seules références : l'issue #80
> et le cas synthétique `backend/evals/cases/issue_80.txt`.

---

## 1. Objectif et périmètre

### 1.1 Reformulation

Corriger les deux défauts constatés par un pilote sur l'analyse d'une maison
individuelle de plain-pied, encodés en régressions connues (xfail) dans
`backend/evals/test_eval_issue_80.py` :

- **Régression A** — le signal « À pondérer » du pilier prix rend « rez-de-
  chaussée » (connoté appartement, tire vers le négatif) pour une maison de
  plain-pied (qui est un atout).
- **Régression B** — la liste « Questions à poser » mentionne la copropriété
  / le syndic pour une maison individuelle.

**Définition de done** : les deux tests d'éval passent de XFAIL à XPASS sur la
PR du fix, puis les marqueurs xfail sont retirés pour les rendre bloquants.
S'y ajoute, par construction de la suite gratuite, le test déterministe
`backend/tests/test_issue_80_deterministic.py::test_signal_maison_plain_pied_sans_rez_de_chaussee`
(`xfail(strict=True)`) : le jour du fix, son XPASS met `test.yml` au rouge et
force le retrait du marqueur dans la même PR (mémoire exécutable voulue par la
spec du harnais §6).

### 1.2 Périmètre IN

- Correction de la couche rendu déterministe (régression A) :
  `backend/app/market_stats.py` (+ `backend/app/analysis.py` selon l'option).
- Correction de la génération des questions (régression B) :
  `backend/app/llm_semantic.py` (prompt et/ou post-traitement déterministe).
- Retrait des trois marqueurs xfail (2 LLM strict=False, 1 déterministe
  strict=True) et mise à jour des oracles du harnais qui encodent l'état
  pré-fix (`backend/tests/test_evals_harness.py`, voir §4 — point critique).
- Mises à jour doc : `CONTEXT.md` §0, `backend/CLAUDE.md` §11,
  `docs/pilotes/README.md` (checklist du chantier fix, à compléter).

### 1.3 Périmètre OUT

- Aucun changement du schéma `/analyze` ni de `frontend/lib/api.ts` (le
  contenu des listes change, pas le contrat ; CONTEXT §11.9 respecté).
- Aucun changement de scoring : le signal « À pondérer » est la couche 2
  explicative (« verdict et score inchangés », CLAUDE §7) ; `scoring.py`
  n'est **pas impliqué** (il ne consomme que verdicts/score, vérifié).
- Pas de nouveau cas d'éval, pas d'extension du harnais (k-runs etc.).
- Pas de re-publication d'extrait réel d'annonce (CONTEXT §11.3).
- Pas de refonte générale du prompt : modifications minimales et ciblées.

### 1.4 Challenge du requirement

Le requirement est bien posé et correctement séquencé : le harnais (chantier
précédent) a précisément été construit pour rendre ce fix sûr, et les causes
racines sont déjà cartographiées dans `evals-harness-ANALYSE.md` §2.1 (j'ai
re-vérifié chaque ligne dans le code, elles sont exactes, cf. §2). Deux
challenges :

1. **Le « fix prompt seul » est insuffisant par construction.** Le test
   déterministe `xfail(strict=True)` construit `floor=0` directement (sans
   LLM) : tant que la couche rendu n'est pas conditionnée au type de bien,
   il reste rouge. Le chantier impose donc un fix déterministe pour A ; la
   question prompt-vs-déterministe ne se pose réellement que pour B.
2. **Risque de sur-ajustement au cas unique** : corriger « floor==0 +
   maison » au plus étroit laisserait absurdes les rendus voisins
   (« 3e étage » ou « sans ascenseur » pour une maison). Le fix doit traiter
   l'invariant générique (les notions d'étage/ascenseur sont des notions
   d'appartement), pas la seule combinaison du pilote — voir Q2.

---

## 2. Causes racines localisées (vérifiées fichier:ligne)

### 2.1 Régression A — « rez-de-chaussée » dans « À pondérer »

Chaîne complète, trois maillons :

1. **Extraction LLM** : `backend/app/llm_semantic.py:101` — règle de prompt
   « `floor` : numéro d'étage (entier ; rez-de-chaussée = 0) si mentionné,
   sinon null ». Face à « plain-pied », le LLM pose légitimement `floor=0` ;
   `_coerce_int_opt` (`llm_semantic.py:204-212`) conserve 0 (« 0 reste valide
   (rdc) »). Ce maillon n'est pas fautif en soi : `floor=0` est une
   information correcte. Le défaut est en aval.
2. **Information type de bien non transmise au rendu** :
   `backend/app/analysis.py:63-66` — `_AMENITY_KEYS` ne contient pas
   `property_type` ; `_amenity_attrs` (`analysis.py:69-70`) ne le transmet
   donc pas. Pourtant `property_type` est disponible à chaque étage :
   `analysis.py:35` (avec repli `"appartement"` si null — attention, cf.
   §5.4) et comme paramètre de `compute_price_market_pillar`
   (`market_stats.py:400`) qui ne le forwarde pas à `_criteria_signal`
   (`market_stats.py:433`).
3. **Rendu inconditionnel** : `backend/app/market_stats.py:328` —
   `_amenity_phrases` rend `floor == 0` en « rez-de-chaussée » (et
   `floor >= 1` en « Ne étage », `has_elevator is False` en « sans
   ascenseur ») sans connaître le type de bien. La phrase « À pondérer :
   ... » est assemblée par `_criteria_signal` (`market_stats.py:346-375`,
   littéral ligne 375) et concaténée à l'explication du pilier prix ligne
   433. C'est **le seul point du code** qui produit « rez-de-chaussée » dans
   une sortie utilisateur.

Le signal n'est émis que si `compute_market_stats` renvoie un pool (≥ 3
comparables) ; c'est pourquoi l'éval compose le rendu directement
(`test_eval_issue_80.py:73-81`) au lieu de passer par `run_full_analysis` sur
DB vide — l'oracle survit à tout design de fix qui supprime « rez-de-
chaussée » du rendu pour une maison.

### 2.2 Régression B — question copropriété sur maison individuelle

- **Générateur fautif : le LLM.** La règle des `questions` du prompt
  (`llm_semantic.py:95`) cite « copropriété » dans la liste d'exemples de
  sujets (« étage/ascenseur, charges, travaux, exposition, parking,
  nuisances, copropriété, etc. ») **sans condition sur le type de bien**, et
  le `SYSTEM_PROMPT` (`llm_semantic.py:47-53`) ne cadre rien à ce sujet.
- **Le générateur déterministe est hors de cause** : `_amenity_actions`
  (`analysis.py:90-108`) ne produit la question charges de copropriété que
  si `condo_fees` est non nul (ligne 103-107) — verrouillé par la garde
  passante
  `tests/test_issue_80_deterministic.py::test_amenity_actions_maison_sans_condo_fees_sans_question_copropriete`.
- **Point d'observation de l'oracle** : le test d'éval B
  (`test_eval_issue_80.py:84-94`) asserte sur
  `analyze_semantic(...)["questions"]`, c'est-à-dire la **sortie de
  `llm_semantic`**, pas la liste fusionnée de `run_full_analysis`
  (`analysis.py:232-235`). Conséquence structurante : un éventuel filtre
  déterministe doit vivre **dans `analyze_semantic`** (assemblage
  `semantic_output`, `llm_semantic.py:267-277`, avant la mise en cache ligne
  279) — un filtre placé dans `analysis.py` ne serait pas vu par l'oracle et
  le test resterait rouge.

### 2.3 Non impliqués

`backend/app/scoring.py` (consomme verdicts/score, aucun texte concerné) ;
`market_stats.compute_market_stats` et la cascade (aucun changement de
sélection de comparables) ; le front (schéma inchangé).

---

## 3. Options de fix

### 3.1 Régression A — rendu déterministe (obligatoire)

- **Option A1 — transporter `property_type` dans les attrs** : ajouter
  `"property_type"` à `_AMENITY_KEYS` (`analysis.py:63`) et conditionner
  `_amenity_phrases` (`market_stats.py:319-343`). **Aucun changement de
  signature** : les deux tests xfail existants (déterministe et éval A)
  construisent déjà leurs attrs via `_amenity_attrs(listing)` avec un
  listing portant `property_type` — ils passent au vert **sans réécriture**
  (seul le retrait des marqueurs reste à faire). Churn minimal.
- **Option A2 — paramètre explicite `property_type` de `_criteria_signal`** :
  plus propre sémantiquement (le type de bien n'est pas une « amenity »),
  déjà disponible dans `compute_price_market_pillar` (`market_stats.py:400`).
  Mais changement de signature ⇒ réécrire le test déterministe ET
  l'assertion A de l'éval ET l'oracle statique AC16 du harnais dans le même
  mini-cycle (la spec du harnais §6 l'anticipe explicitement). Plus de churn
  pour le même invariant.
- **Option A3 — prompt seul** (`floor=null` pour une maison) : **rejetée** —
  le test déterministe `strict=True` construit `floor=0` sans LLM et
  resterait rouge ; et un futur `floor=0` venu d'une autre source
  re-produirait le défaut.

**Recommandation : A1.** Deux sous-décisions remontées en GATE 1 :
le **wording** de remplacement pour une maison `floor==0` (omettre la mention
vs rendre « de plain-pied », Q1) et la **portée** du conditionnement
(seulement `floor==0` vs tout le bloc étage/ascenseur pour une maison, Q2).
Sur la portée, position de l'analyste : pour une maison, « 2e étage » et
« sans ascenseur » sont tout aussi absurdes que « rez-de-chaussée » —
neutraliser tout le bloc est la correction de l'invariant, pas un
élargissement de périmètre. Par cohérence, la question déterministe
« étage élevé sans ascenseur » de `_amenity_actions` (`analysis.py:96-101`)
devrait suivre la même condition (coût marginal nul, même invariant).

### 3.2 Régression B — questions copropriété

- **Option B1 — prompt seul** : ajouter à la règle `questions`
  (`llm_semantic.py:95`) une condition du type « adaptées au type de bien :
  jamais de copropriété/syndic pour une maison individuelle » (sans retirer
  « copropriété » des exemples, qui reste pertinent pour les appartements).
  Avantage : corrige à la source, améliore le texte. Inconvénient majeur :
  fix **probabiliste** — une fois le xfail retiré, le test d'éval devient
  bloquant et un run où le LLM glisse quand même une question copropriété
  met une future PR au rouge (flaky = mort du harnais, leçon §3.6 de
  l'analyse harnais).
- **Option B2 — filtre déterministe dans `analyze_semantic`**
  (`llm_semantic.py:267-277`, avant le cache) : si
  `listing["property_type"] == "maison"`, retirer de `questions` (et par
  cohérence de `negotiation_levers`) les items contenant `copropri` ou
  `syndic`. Garantit l'invariant au point exact où l'oracle l'observe.
  Risque métier : une maison **peut** être en copropriété horizontale
  (lotissement) — une question légitime serait supprimée. Mitigation : ne
  filtrer que si le texte d'annonce (`raw_text`, disponible dans
  `analyze_semantic`) ne mentionne pas lui-même `copropri`/`syndic` et que
  `condo_fees` est null. Le cas synthétique #80 interdit ces tokens (AC13),
  donc l'oracle reste valide.
- **Option B3 — B1 + B2** : le prompt réduit l'occurrence (qualité du texte
  vu par l'utilisateur, y compris pour des formulations que le filtre à
  tokens ne capte pas), le filtre garantit l'invariant rendu bloquant.

**Recommandation : B3**, avec le filtre conditionné comme en B2. Si l'humain
veut le minimum de churn prompt, B2 seul suffit à la définition de done ;
B1 seul est refusé (test bloquant flaky).

### 3.3 Risque de régression sur l'existant

- **Suite gratuite (~296 items)** : seuls `test_issue_80_deterministic.py`
  et `test_evals_harness.py` touchent ces couches (grep vérifié). Le premier
  passe au vert (retrait du marqueur), le second doit être mis à jour (§4).
  Aucun autre test n'asserte sur « À pondérer », le rendu d'étage ou les
  questions.
- **Évals payantes (6 assertions sanity passantes)** : elles re-tournent sur
  la PR (les paths d'`evals.yml` couvrent `llm_semantic.py`,
  `market_stats.py`, `analysis.py`, `evals/**`) et verrouillent l'extraction
  (`property_type`, `surface_m2`, `dpe`, `construction_year`, `price_total`,
  `questions` non vide). Toute dérive d'extraction due au changement de
  prompt y est détectée. Angle mort assumé : aucune éval ne couvre un
  **appartement** — une dégradation des questions copropriété côté
  appartement ne serait pas détectée ; d'où la reco de ne PAS retirer
  « copropriété » des exemples du prompt, seulement conditionner.
- **Sur-ajustement** : le filtre B2 et le conditionnement A1 portent sur
  l'invariant générique maison/appartement, pas sur les valeurs du cas #80
  (282 m², Marly...) — pas de sur-ajustement structurel si Q2 est tranchée
  vers la généralisation.

---

## 4. Mécanique de sortie de xfail — état exact et conflit à anticiper

### 4.1 Ce que disent la config et la spec

- `backend/pytest.ini` ne pose **pas** de `xfail_strict` global : seuls les
  marqueurs explicites comptent.
- Évals (`test_eval_issue_80.py:66` et `:84`) : `xfail(strict=False)` — un
  XPASS post-fix est **silencieux** (exit 0). Le retrait est donc **manuel**,
  prescrit par la checklist `docs/pilotes/README.md` (étape 6 : « retirer à
  la main les xfail LLM (strict=False) ; les xfail strict=True se signalent
  seuls par XPASS »).
- Déterministe (`tests/test_issue_80_deterministic.py:21`) :
  `xfail(strict=True)` — le XPASS post-fix met `test.yml` au **rouge** et
  force le retrait dans la même PR. C'est voulu (spec harnais §6, leçon
  « fix non oraclé »).
- Spec harnais §5.4 : la preuve de reproduction (XFAIL, pas XPASS) était la
  condition de merge du **cas** ; pour le **fix**, la preuve attendue est
  l'inverse — un run montrant XPASS via `-rxX` (le workflow et le
  commentaire de PR collant les rendent nominatifs).

### 4.2 Conflit certain : `backend/tests/test_evals_harness.py` encode l'état pré-fix

Point que la checklist du README **ne mentionne pas** et qui mettra la suite
gratuite au rouge si on l'oublie. Quatre oracles du chantier harnais figent
la présence des marqueurs xfail :

| Oracle | Lignes | Effet post-fix si non mis à jour |
|---|---|---|
| `test_ac16_regression_a_rendu_rez_de_chaussee_xfail` | 488-517 | FAIL (exige le xfail strict=False sur la régression A) |
| `test_ac17_regression_b_questions_copropriete_xfail` | 519-537 | FAIL (idem régression B) |
| `test_phase_b_fixtures_des_xfail_partagees_avec_un_test_bloquant` | 539-571 | FAIL (`assert tests_xfail` exige au moins un test xfail dans le module d'éval) |
| `test_ac19_statique_xfail_strict_true_rez_de_chaussee` + `test_ac19_ac20_ac21_statuts_reels_xfail_et_passants` | 578-608, 633-661 | FAIL (exigent le marqueur strict=True ET un statut « xfailed » réel, « xpassed » interdit) |

Le fix doit donc **basculer ces oracles vers l'état post-fix** dans la même
PR : AC16/AC17/AC19 deviennent « les tests de régression existent SANS
marqueur xfail (bloquants) », le test dynamique attend « passed » sans
« xfailed », et la règle phase B (fixtures des xfail partagées) devient
conditionnelle (elle ne s'applique que s'il existe des tests xfail — la
propriété reste vraie pour les futurs cas). Mettre aussi à jour la checklist
du README pilotes (ajouter : « mettre à jour les oracles de
`test_evals_harness.py` qui figent les marqueurs ») pour le prochain cycle.

### 4.3 Séquencement XFAIL -> XPASS -> retrait (même PR ou deux temps)

Contrainte : si un push contient le fix **en gardant** les marqueurs, le
xfail `strict=True` produit un XPASS qui met `test.yml` au rouge (et
`test_ac19_ac20_ac21...` échoue aussi). Il n'existe donc **pas** d'état
intermédiaire entièrement vert « fix + marqueurs ». Deux séquencements
possibles, remontés en Q4 :

- **(a) Une PR, deux pushes** : push 1 = fix seul (rapport `evals.yml`
  montre nominativement les 2 XPASS via `-rxX` — preuve de la définition de
  done ; `test.yml` rouge **attendu et documenté** dans la description de PR,
  précisément parce que le strict=True signale le fix) ; push 2 = retrait des
  3 marqueurs + bascule des oracles `test_evals_harness.py` ⇒ tout vert,
  mergeable. Le commentaire de PR collant est écrasé au push 2 : lier le run
  Actions du push 1 dans la description de PR.
- **(b) Un seul push, marqueurs retirés d'emblée** : la preuve devient « les
  tests ex-xfail passent en bloquant sur le run de PR ». Plus simple, mais
  on ne voit jamais le statut XPASS littéral exigé par la définition de done,
  et pour la régression B (dépendante du LLM si B1 entre en jeu) un unique
  run vert est une preuve faible.

Recommandation : **(a)** — colle à la lettre de la définition de done et à la
checklist README ; le rouge intermédiaire est l'effet désiré du strict=True.
Pas de seconde PR : un fix mergé avec ses marqueurs encore en place (variante
« deux PR ») laisserait `main` rouge entre les deux merges (strict=True), ce
qui est exclu.

### 4.4 Stabilité post-retrait (test B bloquant et LLM)

Une fois bloquant, le test B dépend d'un appel LLM réel. Avec le filtre B2,
l'invariant est garanti déterministiquement au point observé : le risque de
flaky est nul par construction. Sans B2 (option B1 seule), prévoir des
re-runs `workflow_dispatch` (k≥3) avant merge et accepter un risque de rouge
aléatoire futur — argument supplémentaire pour B2/B3. Rappel process (README
pilotes, étape 7) : tout flaky est traité, jamais re-run jusqu'au vert.

---

## 5. Risques, anti-patterns, dépendances

### 5.1 Anti-patterns (CONTEXT §11 / CLAUDE §1)

- **Pas d'estimation de prix** : le fix ne touche que des formulations
  factuelles (« de plain-pied » est observable, pas évaluatif) — conforme.
- **Pas de redistribution / extrait réel** : contrainte absolue respectée —
  ni l'analyse, ni les tests, ni les commits ne citent l'annonce pilote ;
  seul le cas synthétique existant est utilisé. À re-vérifier en revue de PR
  (messages de commit inclus).
- **Contrat `/analyze`** : inchangé (mêmes clés, mêmes types) — pas de MAJ
  `frontend/lib/api.ts`.
- **Pas d'emoji dans le prompt**, modifications de prompt sobres et neutres.
- **Secrets / vendor / RGPD / coût** : aucun nouveau vendor, aucune donnée
  perso, coût = quelques runs `evals.yml` (~0,01 €/run, paths ciblés déjà en
  place) — négligeable vs budget < 1 €/mois.

### 5.2 Dépendances et ordre

1. **Prérequis satisfaits** : harnais livré (2026-06-11), secret CI
   `OPENAI_API_KEY` + usage limit actés (CONTEXT §0). Rien de bloquant.
2. Ce chantier. Aucune dépendance vers les 9.x différés.
3. Aval : le retrait des xfail clôt la boucle pilote de l'issue #80 (les cas
   deviennent le filet bloquant permanent pour toute future PR de prompt).

### 5.3 Risques spécifiques

- **Oublier `test_evals_harness.py`** (§4.2) : suite gratuite rouge à coup
  sûr. C'est le risque n°1 du chantier, désormais documenté ici.
- **Filtre B2 trop large** : suppression d'une question légitime pour une
  maison réellement en copropriété — mitigé par la condition « le texte ne
  mentionne pas copro/syndic et `condo_fees` null ».
- **Prompt B1 dégradant les appartements** : aucun éval appartement
  n'existe ; mitigation = conditionner sans retirer l'exemple. Noter en
  passant que le besoin d'un cas d'éval « appartement témoin » est une suite
  naturelle (hors périmètre).
- **Cache LLM** : `analyze_semantic` met en cache la sortie **filtrée**
  (clé = texte, `llm_semantic.py:279`) — cohérent ; le conftest d'évals
  vide `_CACHE` en début de session, pas d'interférence.

### 5.4 Nuance de design à trancher au chantier (pas GATE 1)

`analysis.py:35` replie `property_type` null sur `"appartement"` pour la
sélection des comparables. Pour le **rendu** et le **filtre**, ne conditionner
que sur `property_type == "maison"` explicite (un null garde le comportement
actuel — conservateur : on ne supprime pas d'information quand on ne sait
pas). À écrire tel quel dans la spec.

---

## 6. Impacts fichiers (récapitulatif)

| Fichier | Nature |
|---|---|
| `backend/app/market_stats.py` (`_amenity_phrases:319-343`) | Modif — conditionnement au type de bien (A1) |
| `backend/app/analysis.py` (`_AMENITY_KEYS:63`, option `_amenity_actions:96-101`) | Modif légère (A1, portée Q2) |
| `backend/app/llm_semantic.py` (`:95` prompt si B1/B3 ; `:267-277` filtre si B2/B3) | Modif |
| `backend/evals/test_eval_issue_80.py` (`:66`, `:84`) | Retrait des 2 xfail strict=False |
| `backend/tests/test_issue_80_deterministic.py` (`:21`) | Retrait du xfail strict=True |
| `backend/tests/test_evals_harness.py` (`:488-517`, `:519-537`, `:539-571`, `:578-608`, `:633-661`) | Bascule des oracles vers l'état post-fix |
| `docs/pilotes/README.md` (checklist fix, `:93-95`) | Compléter (oracles harnais) |
| `CONTEXT.md` §0 (~`:80`), `backend/CLAUDE.md` §11 (~`:602`) | « régressions en xfail » -> « cas bloquants » |

CI : `evals.yml` se déclenche (paths couverts), `test.yml` inchangé. Aucun
impact DB, schéma `/analyze`, front. Effort estimé : ~0,5 jour atelier
(fix ~0,25 ; bascule des oracles + docs + séquencement ~0,25). Coût LLM :
< 0,05 € (quelques runs d'évals).

---

## QUESTIONS POUR L'HUMAIN (GATE 1)

1. **Wording du rendu pour une maison de plain-pied (visible utilisateur).**
   Quand `property_type == "maison"` et `floor == 0`, le signal « À
   pondérer » doit : (a) **omettre** toute mention (zéro risque d'inférence,
   mais l'atout disparaît) ; (b) rendre **« de plain-pied »** (restitue
   l'atout factuel que le pilote reprochait de voir transformé en négatif ;
   légère inférence : `floor=0` extrait d'une maison signifie en pratique
   plain-pied). **Reco : (b).**

2. **Portée du conditionnement déterministe (anti-sur-ajustement).**
   (a) Conditionner uniquement le cas `floor == 0` (strict minimum du cas
   #80) ; (b) **neutraliser tout le bloc étage/ascenseur pour une maison**
   (« 2e étage », « sans ascenseur » y sont tout aussi absurdes), y compris
   la question déterministe « étage élevé sans ascenseur » de
   `_amenity_actions`. **Reco : (b)** — c'est l'invariant générique, pas un
   élargissement ; (a) garantit une issue pilote future sur le cas voisin.

3. **Stratégie pour la régression B (questions copropriété).**
   (a) Filtre déterministe seul dans `analyze_semantic` (garantie totale,
   prompt intouché, churn minimal) ; (b) prompt seul (REJET recommandé :
   test bloquant flaky) ; (c) **prompt conditionné + filtre déterministe**
   (qualité du texte + garantie), filtre limité au cas « le texte d'annonce
   ne mentionne pas copro/syndic et `condo_fees` null » pour préserver les
   maisons réellement en copropriété horizontale. **Reco : (c)** ; à défaut
   (a).

4. **Séquencement de la preuve XFAIL -> XPASS (process de PR).**
   (a) **Une PR, deux pushes** : push 1 = fix seul (preuve XPASS nominative
   dans le rapport `evals.yml` ; `test.yml` rouge ATTENDU via le strict=True
   — documenté en description de PR avec lien vers le run) ; push 2 =
   retrait des 3 marqueurs + bascule des oracles `test_evals_harness.py` ;
   (b) un seul push avec marqueurs retirés d'emblée (plus simple, mais pas
   de statut XPASS littéral et preuve plus faible pour la partie LLM).
   **Reco : (a)** — colle à la définition de done ; valides-tu le rouge
   intermédiaire assumé sur le push 1 ?

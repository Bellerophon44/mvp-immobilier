# Leçons de l'atelier — registre « ne plus reproduire »

> Relu par CHAQUE rôle au démarrage. Un LLM n'apprend pas entre deux runs :
> ce fichier (+ les tests de régression) EST la mémoire. Une leçon sans
> garde-fou (test ou règle) est une leçon qui sera oubliée.
>
> Format d'une entrée :
> - **[date] [requirement] Titre**
>   - Symptôme : ce qui a cassé / mal tourné
>   - Cause racine : pourquoi
>   - Garde-fou : test ajouté (`chemin::test`) ou règle (où elle est inscrite)

---

## Invariants permanents (rappel, source = CONTEXT §11 / CLAUDE §1)

- Ne jamais estimer un prix de vente ni utiliser DVF / bases notariales.
- Ne jamais redistribuer d'annonces brutes (seulement des agrégats statistiques).
- Ne jamais casser le schéma de réponse `/analyze` sans MAJ `frontend/lib/api.ts`.
- Ne jamais committer de secret ; secrets via env / `fly secrets`.
- Ne jamais merger directement sur `main` (toujours branche -> PR).
- Pas d'emoji dans code, commits ou prompts système.
- Données perso : consentement explicite avant stockage (RGPD).

---

## Entrées

- **[2026-06-18] [increment3-couronne] CI `pull_request` muette : suspecter d'abord le CONFLIT de merge (PR `dirty`), pas le budget**
  - Symptôme : sur #113 aucun workflow `pull_request` ne démarre (ni `test.yml` malgré `backend/**`, ni `diagnose-scrapers` censé poster les verdicts recon), ni sur push, ni après un reopen humain. Seul Vercel tourne. ERREUR répétée : j'ai d'abord accusé le « budget Actions à 0 $ » alors que la capture Billing montrait Actions 5 $ / 0 $ dépensé (barre NON pleine) — le budget n'était pas le sujet.
  - Cause racine (suspect n°1, à confirmer par l'observation post-résolution) : la PR est `mergeable_state: dirty` (conflit, ici `staging` a avancé). Un workflow `pull_request` tourne sur le commit de merge `refs/pull/N/merge` ; tant que la PR est en conflit, GitHub ne peut pas le fabriquer → AUCUN run `pull_request` n'est créé, quel que soit l'auteur du push ou un reopen. Cohérent avec le fait que les runs récents marchaient sur des branches NON conflictuelles (`staging`, autres). (Hypothèse secondaire envisagée puis dépriorisée : events générés par le token de l'intégration ne déclencheraient pas Actions — non tranché.)
  - Garde-fou (règle, diagnostic) : CI `pull_request` muette → (1) vérifier la barre budget Actions ; si NON pleine, écarter le budget DÉFINITIVEMENT ; (2) vérifier `mergeable_state` de la PR — si `dirty`, RÉSOUDRE le conflit (merge/rebase de la base dans la branche) AVANT toute autre piste, c'est très probablement le blocage. Levier de secours indépendant du commit de merge : `workflow_dispatch` (« Run workflow » UI) — mais l'étape de commentaire de `diagnose-scrapers` est gardée `if github.event_name == 'pull_request'`, donc un dispatch ne posterait pas le commentaire. NB : recon impossible en local ici (egress sur allowlist : `Host not in allowlist` → 403 proxy, pas un vrai verdict site).

- **[2026-06-16] [issue-100 / C1] Une cascade avec PLUSIEURS candidats d'un même niveau : l'oracle doit vérifier l'activation conditionnelle sur CHAQUE candidat, pas sur le plus simple**
  - Symptôme : l'inter-communalité (passer `cities=` au niveau quartier de `compute_market_stats` pour réunir Metz + Montigny sur le quartier Sainte-Thérèse/Botanique) était correctement câblée par le développeur sur les DEUX candidats de niveau quartier (`quartier+bande DPE` ET `quartier seul`), mais la phase A des tests ne couvrait QUE le candidat sans bande DPE. Un futur refactor aurait pu retirer `cities` du candidat `quartier+DPE` sans qu'aucun test ne rougisse → élargissement silencieusement partiel (pool DPE limité à Metz).
  - Cause racine : l'oracle a testé un candidat « représentatif » d'un niveau qui en compte plusieurs. Même classe de faux-vert que la leçon « golden d'ordre capturé mais non asserté » : on verrouille une instance, pas chaque artefact.
  - Garde-fou : tests adversariaux `tests/test_issue_100_C_adversarial.py::test_adv_intercommunal_with_dpe_band_unites_two_communes` et `::test_adv_intercommunal_dpe_candidate_receives_cities` (sonde d'appel sur le candidat `quartier+DPE`), falsifiabilité prouvée en cassant `market_stats.py:178`. Règle : quand une activation conditionnelle s'applique à un NIVEAU de cascade qui a plusieurs candidats (avec/sans filtre DPE, etc.), asserter l'activation sur CHAQUE candidat du niveau.

- **[2026-06-16] [issue-100 / C5] Ne jamais poser une question dont la réponse est déjà extraite dans `listing` — garde-fou déterministe, pas confiance au prompt**
  - Symptôme : pour un appartement dont l'annonce donne les charges (« Charges mensuelles : 320 € »), l'analyse posait « Quel est le montant des charges de copropriété ? » (question LLM) PENDANT que la question déterministe (`analysis._amenity_actions`) citait ce même montant (« …charges annoncées (3840 €/an)… ») : on demande une info qu'on affiche par ailleurs → incohérence visible, perte de crédibilité (retour pilote, `gravite/bloquant-credibilite`).
  - Cause racine : aucun invariant « ne pas redemander ce que l'annonce/extraction fournit déjà ». Le prompt demandait des « points à clarifier » sans interdire de clarifier un point déjà clair ; et `_merge_unique` (analysis.py) ne déduplique que sur le texte quasi identique, pas sur l'intention/le sujet → les deux questions coexistaient.
  - Garde-fou : filtre déterministe `llm_semantic._filter_redundant_fee_question` (retire les questions LLM sur le MONTANT des charges — « charge » + montant/combien/coût — quand `condo_fees is not None`), appliqué AVANT le cache comme `_filter_condo_for_house` ; + règle de prompt générale (ne pas redemander une info explicite : charges, surface, DPE, étage, pièces). Tests `tests/test_issue_100_questions.py` (filtre + conservatisme condo_fees None + items non-str + cache porte la valeur filtrée + règle de prompt statique). Note d'interaction : un exemple de question copro servant à tester le filtre MAISON (issue #80, `_QUESTIONS_AC16`) ne doit pas être une demande de montant, sinon C5 le retire et mêle les deux filtres (corrigé : exemple « règlement de copropriété »).
  - Suivi : ✅ FAIT (2026-06-16) — cas d'éval LLM `evals/cases/issue_100.txt` + `test_eval_issue_100.py` ajouté, et **harnais d'évals généralisé multi-cas**.

- **[2026-06-16] [evals-harness] Un oracle écrit pour UN cas peut coder en dur la cardinalité « 1 » et bloquer l'ajout d'un 2e cas — généraliser « par module », pas « globalement »**
  - Symptôme : ajouter un 2e cas d'éval (`issue_100`) cassait `test_evals_harness.py::test_ac14_un_seul_point_appel_analyze_semantic`, qui assertait **exactement 1** site d'appel `analyze_semantic` dans TOUT `evals/`. Or l'intention de la spec (§3.4) est « 1 appel par CAS et par run » (coût borné), pas « 1 appel dans tout le harnais ».
  - Cause racine : l'oracle mono-cas a sur-implémenté l'invariant de coût en cardinalité globale ; la formulation spec « n'apparaît nulle part ailleurs dans evals/ » visait « hors de la fixture de cas de chaque module », pas « une seule fois au total ».
  - Garde-fou : AC14 généralisé — « exactement 1 site `analyze_semantic` PAR module `test_eval_issue_*.py` (dans une fixture `scope=module`) ET 0 hors module ». Provenance docstring (#<n> + synthétique) itérée sur tous les modules via `_eval_modules()`. Oracles `issue_100` ajoutés (tokens, sanity bloquantes, régression C5). Règle : tout oracle de harnais destiné à accueillir N artefacts doit itérer sur la collection (`rglob` des modules de cas) et asserter une propriété PAR artefact, jamais une cardinalité globale figée au 1er cas. Spec mise à jour (AC14).

- **[2026-06-14] [bienici-couronne] Ne JAMAIS coder en dur l'environnement prod dans une feature : staging doit avoir les mêmes capacités que prod**
  - Symptôme : après collecte de la couronne, un test utilisateur sur STAGING (maison à Marly) retombait sur le repli « Metz métropole » alors que la prod fonctionnait. Cause immédiate : `collect.yml` poussait les comparables vers une URL prod **codée en dur** → seule la base prod était peuplée ; staging (env isolé, base dédiée) restait vide, donc inutilisable pour tester la feature.
  - Cause racine : un job de pipeline (collecte, probe) ciblait la prod en dur, ce qui prive staging de la capacité qu'il est censé fournir (tester comme en prod, sans toucher la prod). Anti-pattern : staging traité comme un demi-environnement.
  - Garde-fou (règle, process) : tout workflow agissant sur un backend (collecte, probe, maintenance…) doit **paramétrer la cible** (`workflow_dispatch` input `target: prod|staging`, le cron/automatique visant la prod par défaut), avec URL + secret résolus par expression. Appliqué : `collect.yml` et `coverage-probe.yml` (input `target`, secret `ADMIN_TOKEN_STAGING` pour l'app `coherence-staging`). Principe : staging = mêmes capacités que prod (cf. `docs/specs/ENVIRONNEMENTS-ET-DOMAINE.md`).

- **[2026-06-14] [bienici-couronne] Une colonne filtrée dans un lookup PAR-LIGNE à l'ingestion DOIT être indexée — sinon O(n×m) qui n'explose qu'à l'échelle**
  - Symptôme : après l'élargissement de la collecte bien'ici à la couronne (~17,7k → ~30k poussés), la collecte prod a échoué à l'ingestion (batch en read-timeout puis HTTP 500 sur les suivants, 4 batchs perdus, job rouge). Le scraping était nickel ; l'échec était purement côté écriture.
  - Cause racine : `ingestion/save._find_lineage_candidate` (re-link cross-agence inc.2a) lance `db.query(Comparable).filter(reference==…, source, property_type, city)` pour CHAQUE annonce neuve, sur une colonne `reference` NON indexée → balayage de table par insertion. Invisible à ~17,7k, explose au doublement du volume (worker Fly bloqué sur SQLite → 500 en cascade).
  - Garde-fou : index `ix_comparables_reference` (`db/models.py` `index=True` + `CREATE INDEX IF NOT EXISTS` idempotent dans `db/session._migrate_comparables`, comme `ix_comparables_lineage_id`). Tests `backend/tests/test_ingestion_scale_index.py` (présence d'index après `init_db`, idempotence migration). Règle : toute colonne utilisée dans un `filter`/`get` exécuté par-ligne pendant l'ingestion doit avoir un index ; vérifier le coût d'une lecture par-ligne à l'échelle prod, pas seulement sur la suite de tests.

- **[2026-06-14] [bienici-couronne] Défense en profondeur ingestion : ne pas perdre des communes entières de la queue sur un 500/timeout transitoire**
  - Symptôme : un seul batch transitoirement en échec (timeout serveur sous charge) faisait perdre TOUTES les données de ce batch (communes de fin de collecte), même si la cause sous-jacente était passagère.
  - Cause racine : `jobs/push_comparables` postait chaque batch en un seul essai ; sur exception, il loguait et continuait (ne stoppait pas tout, bien), mais sans réessai → perte définitive du batch.
  - Garde-fou : `_post_batch_with_retry` (backoff exponentiel, `MAX_RETRIES`) + timeout 60→120. Tests `test_ingestion_scale_index.py` (retry récupère / abandonne après N, exit codes de `main`). Règle : un envoi réseau idempotent (upsert par id stable) dans un job de collecte doit réessayer avant d'abandonner un lot.

- **[2026-06-14] [bienici-couronne] Branche longue + squash-merges : recaler sur la base AVANT la PR suivante**
  - Symptôme : en ouvrant une nouvelle PR depuis la même branche après deux squash-merges (#88, #90), la PR ressortait `mergeable_state: dirty` (conflit) et un diff gonflé (14 fichiers / +3541) alors que le vrai changement faisait 5 fichiers.
  - Cause racine : le squash-merge écrit un nouveau commit sur la base et n'amène PAS l'historique de la branche ; la base commune (merge-base) reste ancienne, donc le three-dot diff ré-affiche tout le travail déjà mergé, et des fichiers ajoutés des deux côtés deviennent des conflits add/add.
  - Garde-fou (règle, process) : après un squash-merge, AVANT de continuer sur la même branche, la recaler sur la base (`git reset --hard origin/<base>` puis force-with-lease, ou rebase) pour repartir d'un merge-base propre. Sinon, brancher à neuf depuis la base. Vécu sur #92 (résolu par merge de `staging` dans la branche) puis évité sur #94 (reset préalable).

- **[2026-06-14] [bienici-couronne] Budget GitHub Actions à 0 $ avec « stop usage » coupe SILENCIEUSEMENT la CI dès le quota gratuit épuisé**
  - Symptôme : en milieu de session, plus aucun workflow (`test.yml`, `evals.yml`, `deploy`) ne se déclenchait sur les pushes/PR ; seul Vercel (externe) tournait. githubstatus.com vert. Aucune erreur visible côté PR.
  - Cause racine : budget Actions plafonné à 0 $ avec arrêt automatique (Billing → Budgets and alerts) ; tant que le quota mensuel gratuit suffit ça passe, mais une fois épuisé (beaucoup de jobs ce jour-là) toute minute facturable est bloquée → workflows non planifiés. À NE PAS confondre avec un filtre de chemins ou une permission `actions:write` manquante (l'intégration ne PEUT PAS déclencher via l'API : `run_workflow`/`rerun` → 403 ; seul un `git push` ou un « Run workflow » UI humain déclenche).
  - Garde-fou (règle ops) : si la CI ne se déclenche plus sans cause de code, vérifier Billing → Budgets and alerts (limite Actions > 0, sinon supprimer le budget) AVANT de soupçonner le code. Repli pour déclencher : push (auto) ou « Run workflow » manuel depuis l'UI Actions.

- **[2026-06-13] [cross-agence-inc2b-etape1] Un AC « le body avec champ optionnel ne renvoie pas 422 » est un FAUX-VERT pour prouver qu'un champ est DÉCLARÉ dans un modèle Pydantic à `model_config` vide**
  - Symptôme : l'AC d'acceptation de `POST /admin/comparables` (accepte
    `photo_urls` sans 422 + contrat de réponse intact) restait vert MÊME si
    `ComparableIn` ne déclarait pas le champ `photo_urls` — Pydantic ignore par
    défaut les champs extra (`extra="ignore"`). Sans déclaration, `model_dump()`
    ne transmet pas la valeur à `save_comparables` → colonne jamais persistée,
    sans qu'aucun AC ne le voie (l'AC de persistance testait l'appel DIRECT à
    `save_comparables`, pas le chemin endpoint).
  - Cause racine : confusion entre assertion d'ACCEPTATION (absence de 422) et
    assertion de DÉCLARATION/transit du champ ; le chemin endpoint → save n'était
    jamais oraclé pour le nouveau champ. Trou de couverture entre « accepte » et
    « persiste ».
  - Garde-fou : test de persistance bout-en-bout via l'endpoint admin vérifiant
    la valeur RÉELLE en base (`tests/test_cross_agence_increment2b_etape1.py::test_hardening_b_admin_import_actually_persists_photo_urls`,
    falsifiabilité prouvée : rouge si le champ est retiré de `ComparableIn`).
    Règle : pour prouver qu'un champ optionnel d'un modèle Pydantic
    (`model_config` sans `extra="forbid"`) est bien pris en compte, asserter sa
    PERSISTANCE/transit réel via le chemin endpoint complet, jamais seulement
    l'absence de 422. Trouvé par le testeur phase B (sonde de falsifiabilité des
    AC « passe-déjà »).

- **[2026-06-13] [cross-agence-inc2b-etape1] Probe de mesure read-only en O(n²) : tolérable comme outil dev, à pré-filtrer avant tout usage récurrent**
  - Symptôme : `tools/probe_cross_source.py::compute_probe` évalue les paires
    candidates via `itertools.combinations` sur tout le corpus (~157 M paires sur
    ~17,7k comparables prod). Justesse verrouillée par tests (~80 comparables),
    mais coût d'exécution réel élevé.
  - Cause racine : produit cartésien sans pré-filtrage, acceptable car le script
    est un outil de mesure ponctuel, read-only, HORS chemin prod (jamais importé
    par l'app, pas de surface API, pas dans un job de collecte).
  - Garde-fou / dette : NON bloquant à l'étape 1 (documenté). Pour l'ÉTAPE 2, si
    la probe doit tourner régulièrement / en CI sur le stock prod, pré-filtrer par
    bucket `(city, postal_code, property_type)` (égalité stricte requise → group-by
    ramène à des sous-corpus de quelques unités) avant le `combinations`. À porter
    dans la spec étape 2.

- **[2026-06-13] [cross-agence-inc2a] Sous `autoflush=False`, relire par PK un objet ajouté dans la MÊME session exige un `db.flush()` préalable**
  - Symptôme : un id présent deux fois dans le même batch (`save_comparables`)
    n'était pas vu par le `db.get(Comparable, id)` du second passage (session
    `SessionLocal(autoflush=False)`), provoquant un SECOND `db.add` du même PK →
    `IntegrityError` au commit → **tout le batch perdu**. Le re-link 2a, qui relit
    la base avant d'écrire, exposait ce cas (inc.1 ne le déclenchait pas).
  - Cause racine : avec `autoflush=False`, un objet `add`é mais non flushé n'est
    PAS dans l'identity map interrogée par `db.get` (qui renvoie `None`). Le
    doublon échappe donc à la branche `existing is not None`.
  - Garde-fou : `db.flush()` après le `db.add` d'un nouveau comparable (rend l'id
    visible → le doublon intra-batch emprunte la branche de re-observation, 1
    comparable / 1 snapshot). Verrouillé par
    `tests/test_cross_agence_increment2a.py` (AC40 + `test_hardening_batch_mixed_*`
    : lot mêlant valides et invalides, batch jamais perdu). Règle : tout code qui
    relit par PK un objet ajouté dans la même session sous `autoflush=False` doit
    `flush()` d'abord ; et placer toute voie de rejet (`continue`) AVANT le
    `db.add` pour ne pas poisonner la session.

- **[2026-06-13] [cross-agence-inc2a] Une lignée longitudinale se fragmente si le re-list survient pendant que l'ancien membre est encore dans la fenêtre de rattachement**
  - Symptôme : une lignée ne s'étend à 3+ membres que si les membres précédents
    SORTENT de la fenêtre 90j avant le re-list suivant. Un bien re-publié à
    cadence < 90j voit ≥ 2 candidats au 3e passage et **s'abstient** (§3.4) →
    nouvelle lignée → historique de prix fragmenté en lignées de 2 membres.
  - Cause racine : conséquence DIRECTE et VOULUE de l'invariant « jamais de faux
    lien » (Q3 conservateur) combiné à « les membres existants ne sont jamais
    mutés par un rattachement » (l'ancien membre garde son `last_seen_at`, donc
    reste candidat tant qu'il est dans les 90j). Ce n'est PAS un bug.
  - Garde-fou : test de régression
    `tests/test_cross_agence_increment2a.py::test_hardening_idempotence_replay_then_third_member_one_lineage`
    (chaîne A→B→C avec A hors fenêtre = lignée longue valide). Risque résiduel
    consigné spec §7. Règle : à la calibration future du taux de re-list, mesurer
    la part de chaînes fragmentées avant d'élargir la fenêtre (élargir augmente le
    risque de faux lien — arbitrage, pas réglage libre).

- **[2026-06-13] [cross-agence-inc2a / atelier] Le développeur ne possède pas l'oracle ; une incohérence INTERNE du fichier de tests se tranche en phase B**
  - Symptôme : le développeur a dû modifier une donnée du fichier de tests
    (`_build_lineage_two_members`, `t2` à 123j d'écart alors que la fenêtre est de
    90j) pour atteindre le vert — l'oracle phase A était mathématiquement
    insatisfiable (aucune fenêtre ne peut exclure 91j via AC13 ET inclure 123j via
    AC25). Un développeur qui édite l'oracle est un risque de complaisance.
  - Cause racine : (a) côté testeur, des bornes temporelles d'un scénario
    MULTI-membres posées sans recalculer les écarts inter-membres contre la
    fenêtre de rattachement → oracle faux ; (b) côté process, la correction a été
    faite par le développeur, pas par le propriétaire de l'oracle.
  - Garde-fou (règles atelier) : (1) tout test d'une chaîne de re-list explicite,
    par membre, l'écart au candidat visé ET aux autres candidats potentiels
    (abstention §3.4), pas seulement l'écart now→membre ; (2) si le développeur
    détecte une incohérence interne de l'oracle, il la SIGNALE (commentaire +
    rapport) sans l'« optimiser », et c'est le TESTEUR phase B qui statue et
    reprend la propriété — fait ici (modif validée légitime, aucune assertion
    affaiblie).

- **[2026-06-12] [fix-issue-80] Livrable de push réparti sur plusieurs suites (tests/ gratuits + evals/ payants) partiellement livré sans détection locale**
  - Symptôme : l'AC37 (sanity bloquante `single_storey` dans `evals/`) faisait
    partie du contenu du push 1 selon la spec §6, mais le commit du fix ne
    touchait pas `evals/` — aucune suite exécutée localement ne pouvait le
    voir (les évals ne tournent qu'en CI). Aggravé par une consigne
    d'orchestration trop large (« interdit de toucher evals/ ») qui
    contredisait la spec.
  - Cause racine : le « done » a été vérifié contre les tests verts, pas
    contre la liste de contenu du push prescrite par la spec ; et une
    interdiction d'orchestrateur a primé silencieusement sur la spec.
  - Garde-fou : règle orchestrateur — avant de clore une phase dev, diff du
    commit confronté à la liste de contenu du push (spec §6), suite par
    suite ; toute interdiction donnée à un rôle doit citer ses exceptions
    prévues par la spec. Détecté ici par le testeur phase B (audit de
    livrable, pas seulement de code).

- **[2026-06-12] [fix-issue-80] Conditionnement par égalité stricte sur une valeur d'enum extraite du LLM**
  - Symptôme : tout le conditionnement maison (`property_type == "maison"`)
    repose sur la discipline du prompt ; une variante de casse (« Maison »)
    ferait resurgir le comportement pré-fix (rendu « rez-de-chaussée »,
    question copropriété).
  - Cause racine : `property_type` n'est jamais normalisé dans
    `analyze_semantic` ; l'enum n'est garanti que par le prompt.
  - Garde-fou : limite actée par la spec (égalité stricte, comportement
    conservateur) et figée par deux tests dédiés
    (`tests/test_issue_80_deterministic.py::test_b_property_type_casse_variante_comportement_conservateur` (replié au push 2 depuis le fichier dédié de phase A),
    `tests/test_issue_80_semantic_filter.py::test_b_property_type_casse_variante_maison_aucun_filtrage`).
    Si un cas réel de casse variante apparaît dans les évals : normaliser à
    la coercition (un seul endroit), jamais élargir chaque comparaison.

- **[2026-06-12] [fix-issue-80] Un oracle qui exécute un fichier de tests en sous-processus rend ce fichier inextensible en tests-first**
  - Symptôme : la spec prescrivait d'ajouter les tests AC1-AC13 à
    `tests/test_issue_80_deterministic.py`, mais l'oracle du harnais
    (`test_evals_harness.py::test_ac19_ac20_ac21_statuts_reels_xfail_et_passants`)
    exécute ce fichier en sous-processus et exige returncode 0 : tout rouge
    légitime de phase A y devient un échec hors spec.
  - Cause racine : dépendance cachée entre un fichier de tests et un oracle
    de harnais qui l'observe, non anticipée au moment de la spec.
  - Garde-fou : règle spec-writer/testeur — quand un fichier de tests est
    observé par un oracle en sous-processus, la spec doit prévoir soit un
    fichier dédié pour les nouveaux tests, soit la bascule simultanée de
    l'oracle ; tout écart de placement se documente en tête de fichier (fait
    ici) et s'acte explicitement au push suivant.

- **[2026-06-12] [evals-harness] Une erreur de setup de fixture sur un test xfail devient un XFAIL silencieux (exit 0), pas un ERROR**
  - Symptôme : prouvé par sonde en phase B — sous pytest, si la fixture d'un
    test marqué `xfail(strict=False)` lève pendant le setup, le test est
    rapporté XFAIL et la session sort en exit 0. Un harnais dont les seuls
    consommateurs d'une fixture seraient des tests xfail peut donc casser
    entièrement (fixture en panne = aucun appel LLM) sans jamais mettre la CI
    au rouge.
  - Cause racine : sémantique pytest — le marqueur xfail couvre aussi les
    échecs de setup, pas seulement les assertions du test.
  - Garde-fou : règle structurelle — toute fixture consommée par un test xfail
    doit aussi être consommée par au moins un test bloquant (sans xfail) de la
    même suite, dont l'ERROR de setup met le job au rouge. Verrouillé par
    `backend/tests/test_evals_harness.py::test_phase_b_fixtures_des_xfail_partagees_avec_un_test_bloquant`.

- **[2026-06-11] [cross-agence-inc1] Bootstrap destructif en top-level de conftest ré-exécuté par un double-import**
  - Symptôme : `OperationalError: attempt to write a readonly database` non
    déterministe sur des tests d'écriture collectés APRÈS le fichier
    cross-agence, en run combiné d'un seul processus. Diagnostiqué d'abord à
    tort comme « artefact sandbox lié au volume d'écritures ».
  - Cause racine : le test statique AC22 faisait `import tests.conftest as
    conftest_mod` ; pytest ayant déjà chargé conftest sous le nom `conftest`,
    l'import sous un SECOND nom de module ré-exécutait son top-level, donc le
    `os.remove(_tmp_db)` du bootstrap — **sous le moteur SQLAlchemy déjà
    connecté** → toute écriture suivante échouait. Déterministe, pas un effet
    de volume.
  - Garde-fou : bootstrap rendu idempotent par sentinelle d'env
    (`MVP_TEST_DB_BOOTSTRAPPED == DATABASE_PATH`, suffixe pid pour re-bootstrap
    d'une nouvelle session). Test de régression :
    `tests/test_cross_agence_increment1.py::test_conftest_reimport_under_second_name_keeps_db_writable`
    (double-import volontaire + écriture réelle). Règle : tout effet de bord
    destructif en top-level de conftest doit être idempotent au double import.
    Et : ne pas conclure « artefact sandbox » sur un `readonly database` sans
    avoir cherché un ré-import/réinit de la base sous moteur ouvert.

- **[2026-06-11] [cross-agence-inc1] Borne temporelle littérale `x < now - delta` intestable à l'exactitude**
  - Symptôme : implémenter la rétention au mot près (`last_seen < now -
    timedelta(days=730)`) faisait échouer l'AC de borne : le test insère
    `last_seen = now_test - 730j`, l'endpoint recalcule son `now` quelques ms
    plus tard → la ligne « exactement 730 jours » est déjà sous le seuil
    sub-seconde et purgée à tort.
  - Cause racine : une borne à la seconde près n'est pas spécifiable ni
    testable de façon stable (latence entre l'insert du test et le `now` du
    code).
  - Garde-fou : spécifier les bornes de rétention en **jours révolus**
    (`(now - last_seen).days > 730`), sens conservateur (jamais de purge
    prématurée), et figer la zone intermédiaire par un test fin :
    `tests/test_cross_agence_increment1.py::test_retention_day_granularity_730_days_plus_hours_kept`.

- **[2026-06-11] [cross-agence-inc1] Nouvelle table dépendante : ré-auditer TOUS les chemins de suppression du parent**
  - Symptôme : l'ajout de `listing_price_snapshots` n'a cascadé la suppression
    que sur le NOUVEAU chemin de purge (rétention) ; les purges préexistantes
    (band/zone/dept) supprimaient le comparable sans ses snapshots → orphelins
    que la rétention (qui ne scanne que `comparables`) ne rattrapait jamais.
    Livré sans oracle : aucun test n'aurait détecté l'absence de cascade.
  - Cause racine : sans FK formelle (SQLite/MVP), la cohérence est applicative ;
    on n'a traité que le chemin sous les yeux, pas l'invariant « tout chemin de
    suppression du parent supprime ses dépendances ».
  - Garde-fou : cascade généralisée aux 4 chemins + balayage d'orphelins en
    maintenance (compteur dédié `purged_orphan_snapshots`). 5 oracles :
    `tests/test_cross_agence_increment1.py::test_cascade_band_zone_dept_purges_delete_snapshots_real_run`
    (+ dry_run, orphelin préexistant, non-double-comptage, idempotence).
    Règles : (1) toute table dépendante sans FK impose de ré-auditer TOUS les
    chemins de suppression du parent existants, pas seulement le nouveau ;
    (2) un correctif de fin de cycle (post-verdict) doit être verrouillé par un
    test dans le même mini-cycle — un fix non oraclé est réversible
    silencieusement par n'importe quel refactor.

- **[2026-06-11] [cross-agence-inc1] Justifier un invariant transactionnel par le mécanisme RÉEL, pas un mécanisme désactivé**
  - Symptôme : un commentaire justifiait l'absence de double comptage du
    balayage d'orphelins par « l'autoflush du count() a déjà appliqué les
    suppressions » — alors que `SessionLocal` est créé `autoflush=False`. Code
    correct, justification fausse : piège pour un futur agent qui raisonnerait
    dessus.
  - Cause racine : l'invariant tient en réalité par le DML immédiat de
    `Query.delete` (indépendant du flush), pas par l'autoflush.
  - Garde-fou : commentaire corrigé (cite `Query.delete` + note que les
    `db.delete` pendants ne sont PAS flushés → un orphelin d'un futur chemin
    sans cascade ne serait rattrapé qu'au run suivant). Règle : toute
    justification d'invariant transactionnel doit citer le mécanisme réel et
    être vérifiable contre la config de session (`autoflush`/`autocommit`).

- **[2026-06-04] [9.7] Isolation des tests par fichier SQLite partagé**
  - Symptôme : les feedbacks persistés s'accumulent dans le même fichier
    `DATABASE_PATH` ; un `.one()` filtré sur un `analysis_id` réutilisé entre
    deux runs lèverait `MultipleResultsFound` (faux rouge non lié au code).
  - Cause racine : pas de transaction rollback par test ; la table `feedback`
    n'est pas vidée entre les tests d'une même session, et le fichier survit
    entre sessions.
  - Garde-fou : `conftest.py` supprime le `.db` jetable en début de session
    (`os.remove` si présent) AVANT l'import de l'app ; les assertions de
    persistance filtrent sur un `analysis_id` unique par test (jamais `count()`
    absolu) — voir `tests/test_feedback.py::test_feedback_persisted` et
    `::test_feedback_absent_comment_persisted_as_none`.
  - Durcissement (challenge phase B) : `setdefault("DATABASE_PATH", ...)` était
    dangereux — si l'env définit déjà `DATABASE_PATH` (dev local, conteneur prod
    `/data/comparables.db`), le `os.remove` aurait effacé la **vraie** base.
    Corrigé : `conftest.py` **force** désormais `os.environ["DATABASE_PATH"]`
    vers un fichier jetable dédié suffixé par le pid
    (`mvp_test_feedback_<pid>.db`), jamais `setdefault`. Ne jamais combiner
    `setdefault` sur un chemin de base avec une suppression de fichier.

- **[2026-06-04] [9.7] Bornes de validation à tester aux valeurs exactes**
  - Symptôme : risque qu'une borne soit codée `gt`/`lt` au lieu de `ge`/`le`
    (ou max_length off-by-one) sans qu'un test ne le détecte.
  - Cause racine : tests-first ne couvrait que 6/0/1001 (hors bornes), pas
    1/5/1000 inclus ni le float non entier (3.5 -> 422 attendu, pas 500).
  - Garde-fou : `tests/test_feedback.py::test_feedback_rating_lower_bound_included`,
    `::test_feedback_rating_upper_bound_included`,
    `::test_feedback_comment_exactly_1000_accepted`,
    `::test_feedback_rating_float_rejected`, `::test_feedback_rating_negative_rejected`.

- **[2026-06-09] [9.9] État partagé de module réinitialisé en conftest autouse, pas en fixture locale**
  - Symptôme : le reset du rate-limit (`reset_rate_limit_state`) a été livré en
    fixture **locale** à `test_9_9_rate_limit.py`. La suite était verte par chance
    (les autres fichiers tapent peu de requêtes par IP-testclient, donc sous le
    seuil), mais le compteur en mémoire de module de `app.rate_limit` fuit entre
    fichiers → dépendance implicite à l'ordre des tests (re-violation de la
    leçon 9.7 sur l'état partagé).
  - Cause racine : « tests verts » confondu avec « critère couvert ». Le garde-fou
    d'isolation était au mauvais endroit (fichier local au lieu du conftest global).
  - Garde-fou : fixture **autouse** `_reset_rate_limit_state` dans
    `backend/tests/conftest.py` (reset avant chaque test, import protégé) +
    `tests/test_9_9_rate_limit.py::test_conftest_provides_global_rate_limit_reset`
    (statique) et `::test_prod_app_state_leaks_without_conftest_reset` (dynamique).
    Règle : tout état partagé de module (compteur, cache) se réinitialise par une
    fixture **autouse en conftest.py**, jamais locale à un seul fichier.

- **[2026-06-09] [9.9 / atelier] Phase B : séquencer testeur → reviewer, jamais en parallèle sur le même fichier**
  - Symptôme : l'orchestrateur a lancé le testeur (phase B, qui **édite** les
    tests) ET le reviewer (read-only) **en parallèle** sur `test_9_9_rate_limit.py`.
    Le reviewer a relu une cible mouvante : il a vu rouge un test (`NameError`) que
    le testeur était justement en train de corriger, et a fondé une partie de son
    FAIL dessus.
  - Cause racine : deux agents écrivant/lisant le même fichier simultanément (course).
  - Garde-fou (règle orchestrateur) : en phase B, **lancer d'abord le testeur**
    (il fige le fichier de tests), **puis** le reviewer sur l'état stabilisé. Les
    deux verdicts restent indépendants (contextes isolés), mais plus de course.

- **[2026-06-09] [9.9] Risques résiduels assumés du rate-limit (documentés, non bloquants)**
  - NB1 — croissance mémoire non bornée des clés `(scope, ip)` : une deque vidée
    laisse sa clé dans `_buckets`. Atténué : mono-instance Fly, état perdu au
    restart/auto-stop, volume MVP négligeable. À durcir (évincer la clé quand la
    deque devient vide, ou cap de taille) si le trafic monte (suivi 9.10/infra).
  - NB2 — `X-Forwarded-For` spoofable : n'est qu'un **repli** ; derrière Fly,
    `Fly-Client-IP` (posé par le proxy) fait foi et est lu en priorité. Risque
    assumé pour le modèle de menace (rafale), pas pour l'abus distribué.

- **[2026-06-09] [9.10] Faux-vert tautologique sur un corps d'endpoint à `response_model`**
  - Symptôme : `test_ac8b` assertait `set(reponse.keys()) <= autorisees` sur le
    corps de `POST /analyze`. Or FastAPI **filtre déjà** les clés hors
    `AnalyzeResponse` (response_model) : l'assertion serait verte même si le code
    laissait fuiter le marqueur interne `_fallback`. Garde-fou inopérant.
  - Cause racine : tester un invariant « pas de fuite » à un niveau (endpoint) où
    une couche tierce (Pydantic) masque le défaut → vert de complaisance.
  - Garde-fou : tester aussi la **fonction sous-jacente** hors response_model —
    `tests/test_events_hardening.py::test_run_full_analysis_does_not_return_fallback_marker`
    appelle `run_full_analysis` directement et asserte l'absence de `_fallback`.
    Règle : pour prouver qu'un champ interne ne fuit pas, tester la couche qui le
    produit, pas seulement celle qui le sérialise.

- **[2026-06-09] [9.10] Tester le fallback LLM par le CHEMIN RÉEL, pas via monkeypatch de la façade**
  - Symptôme : le test officiel du fallback monkeypatchait `analyze_semantic` pour
    renvoyer `dict(_FALLBACK) + {_fallback:True}`. Il court-circuitait le `except`
    de `llm_semantic` où le marqueur est **réellement** posé → un bug dans la pose
    du marqueur passerait inaperçu.
  - Garde-fou : `tests/test_events_hardening.py::test_real_fallback_path_persists_event_and_keeps_contract`
    mocke `client.chat.completions.create` pour qu'il **lève**, et vérifie de bout
    en bout (event `llm_fallback` persisté + contrat `/analyze` intact). Règle :
    pour un comportement déclenché par une exception, faire lever la **vraie**
    dépendance, pas la façade qui l'enrobe.

- **[2026-06-09] [9.10] Validation conforme « à la lettre » mais en deçà de l'intention ; ressource best-effort hors `try`**
  - Symptôme (a) : le validator `referrer_domain` (`main.py::_hostname_only`)
    couvrait l'AC (« pas de `/` ni `?` ») mais, écrit en **blacklist** de 2
    caractères, laissait passer `user:secret@host` (credential), `host#fragment`
    et un saut de ligne (log-injection) — en deçà de « hostname seul » (§3.1).
    Symptôme (b) : `_record_llm_fallback_event` ouvrait `db = SessionLocal()`
    **hors** du `try` best-effort → une panne à l'ouverture aurait remonté un 500
    sur `/analyze`.
  - Cause racine : borne exprimée comme interdiction ponctuelle au lieu d'une
    **whitelist positive** ; acquisition de ressource hors du bloc censé l'avaler.
  - Garde-fou : validator passé en whitelist `re.fullmatch(r"[A-Za-z0-9.-]+", v)` ;
    `SessionLocal()` déplacé **dans** le `try` (`db=None` + `if db is not None`).
    Tests de régression (xfail convertis en passants) :
    `tests/test_events_hardening.py::test_ac10_referrer_non_hostname_residual_risk`
    et `::test_record_llm_fallback_event_swallows_session_open_error`.
    Règle : exprimer une borne de validation en **whitelist positive**, jamais en
    blacklist de quelques caractères ; placer toute acquisition de ressource
    best-effort à l'intérieur du `try/except` qui doit l'avaler.

- **[2026-06-07] [photo-evidence] Schéma DB absent pour les appels directs au pipeline**
  - Symptôme : un test appelant `run_full_analysis` SANS instancier `TestClient`
    levait `sqlite3.OperationalError: no such table: comparables` selon l'ordre de
    collecte ; la suite ne passait que par chance (un test `TestClient` antérieur
    déclenchait le `@app.on_event("startup")` → `init_db`, créant le schéma à temps).
  - Cause racine : `init_db()` n'est câblé qu'au startup FastAPI ; pour un appel
    direct au pipeline en début de session, la table `comparables` n'existe pas encore.
  - Garde-fou : `conftest.py::_init_db_schema` (autouse, `scope="session"`) appelle
    `db.session.init_db()` avant tout test → suite robuste à l'ordre. Oracle de
    régression : `tests/test_photo_evidence_hardening.py::test_gating_uses_type_not_text_full_analysis`
    (et tout test photo frappant `run_full_analysis` directement) échouerait si le
    schéma n'était pas pré-créé.

- **[2026-06-07] [photo-evidence] Cache module global fait fuiter un cache-hit entre tests**
  - Symptôme : `test_cap_six_images` (10 URLs capées à `cdn.x/0..5`) puis
    `test_exactly_six_images_all_transmitted` (URLs `0..5`) se réduisent au même
    couple (images capées, claims éligibles) → même clé de cache. Le 2e test
    obtenait un cache hit, n'appelait jamais son mock, et `mock.calls[0]` levait
    `IndexError` (faux rouge non lié au code produit).
  - Cause racine : `app.photo_evidence._CACHE` est un état module global (TTL 7j,
    pattern `llm_semantic`) qui survit entre tests d'une même session ; une
    assertion sur `mock.call_count`/`mock.calls` du test suivant est faussée par
    le hit légitime du précédent.
  - Garde-fou : `conftest.py::_reset_photo_cache` (autouse) vide `_CACHE` avant
    chaque test — isolation sans affaiblir la spec (cache pleinement actif
    intra-test). Règle générale : tout test assertant un compteur d'appels sur un
    module à cache global doit réinitialiser ce cache en `autouse`. Verrouillé par
    `tests/test_photo_evidence_hardening.py` (tests de cache hit/miss dédiés :
    discrimination de la clé sur claims ET images, marqueur `_CACHE == {}` en entrée).

- **[2026-06-16] [issue-100-A] Un oracle qui asserte une clé brute force une implémentation contre-conventionnelle**
  - Symptôme : AC10 (convergence des référentiels) testait `CANON in _SECTORS_RAW`
    puis `_SECTORS_RAW[CANON]` avec `CANON="Sainte-Therese"` (forme canonique sans
    accent). Cela a forcé le développeur à poser la **clé** de secteur en forme
    canonique, alors que toutes les autres clés de `_SECTORS_RAW` sont des libellés
    humains accentués (« Centre Ville », « Plantières-Queuleu ») servant de
    `scope_name` exposé au front. La spec §3.3 prescrivait pourtant la clé accentuée
    `"Sainte-Thérèse"` avec dérivation canonique au chargement (`_build_sector_maps`).
  - Cause racine : l'oracle a verrouillé la convergence canonique en assertant
    l'**identité de la clé source** d'un dict dont les clés ont un rôle d'affichage,
    au lieu d'asserter la **valeur canonicalisée dérivée** par la fonction de
    chargement. Risque fonctionnel ici nul (secteur ne contenant que le quartier →
    libellé inatteignable en affichage), mais incohérence de convention.
  - Garde-fou (règle) : pour verrouiller la convergence canonique d'un nouveau
    référentiel, l'oracle asserte la **forme dérivée** (sortie de la fonction de
    normalisation, p.ex. `_DISTRICT_TO_SECTOR[CANON]` / `canonical_district`), JAMAIS
    l'identité d'une clé source dont les clés portent un rôle d'affichage. Parenté
    avec la leçon 2026-06-13 (oracle qui force une implémentation au lieu d'oracler
    une propriété). Si harmonisation souhaitée : assouplir AC10
    (`backend/tests/test_issue_100_A.py`) au niveau du tester, pas du développeur.

- **[2026-06-16] [issue-100-B] Un golden d'ORDRE capturé mais non asserté est un faux-vert (refactor d'un matcher « premier match »)**
  - Symptôme : la migration des 4 référentiels vers le gazetteer unique a fait passer
    tous les goldens ET la review, mais le challenge adversarial a trouvé une
    régression réelle : `geo_gazetteer.known_localities_districts()` appliquait un tri
    GLOBAL `forms.sort(key=len, reverse=True)` qui détruisait l'ordre curaté
    historique de `scrapers.base._KNOWN_LOCALITIES`. Comme `extract_district` renvoie
    le PREMIER match par substring, l'ordre détermine quel quartier gagne sur un texte
    multi-localités : 78 textes (ex. « Vallières proche Technopôle » → ancien
    `Vallieres`, nouveau `Technopôle`) changeaient de résolution → refactor NON pur.
  - Cause racine : l'oracle d'origine (AC1) figeait bien le golden d'ordre exact mais
    n'assertait QUE `set()` + l'invariant partiel long-avant-court (paires en relation
    de substring). L'ordre relatif des formes DISJOINTES n'était pas verrouillé, et un
    tri (longueur ou alpha) ne reproduit jamais un ordre curaté arbitraire.
  - Garde-fou (tests de régression, `backend/tests/test_issue_100_B.py`) :
    `test_b_regression_known_localities_ordre_exact_egal_golden` (`list(...) == golden`,
    ordre exact), `test_b_regression_extract_district_multi_localite_inchange` et
    `test_b_regression_extract_district_balayage_exhaustif_paires` (toutes les paires
    ordonnées de localités, sortie identique à l'état pré-migration `7d03053`).
    Règle : quand une liste ORDONNÉE pilote un « premier match » (type
    `_KNOWN_LOCALITIES`/`extract_district`), l'oracle de non-régression asserte
    l'ORDRE EXACT contre le golden, pas seulement l'ensemble + une propriété partielle,
    et teste la fonction consommatrice sur des entrées multi-tokens. L'ordre curaté
    fait partie du contrat comportemental : ne jamais le re-trier lors d'une
    unification de référentiels.

- **[2026-06-16] [issue-100-B] Dérivation exécutée au top-level d'un module source crée un import circulaire latent dépendant de l'ordre d'import**
  - Symptôme : `scrapers.base` appelait `_build_known_localities()` à son top-level, qui
    importe `app.geo_gazetteer`, lequel importait `scrapers.base` à SON top-level
    (`from scrapers.base import canonical_district`). `python -c "import app.geo_gazetteer"`
    en TOUT PREMIER plantait (`AttributeError: partially initialized module`). Le chemin
    prod (`app.main`) et pytest ne déclenchaient pas le bug (ils chargeaient
    `scrapers.base` d'abord) → fragilité invisible en suite verte.
  - Cause racine : cycle d'import A↔B dont une branche s'exécute au top-level ; il ne
    casse que selon l'ordre d'import, donc passe inaperçu tant qu'un consommateur
    impose le bon ordre.
  - Garde-fou (règle + vérif) : une dérivation à l'import qui dépend d'un module qui
    dépend en retour du module courant doit être robuste à l'ordre — import paresseux
    d'un côté (ici `canonical_district` importé dans `build_sector_maps`, pas au
    top-level de `geo_gazetteer`). Vérifier que `python -c "import <A>"` ET
    `python -c "import <B>"` réussissent CHACUN en premier import (process séparés).

- **[2026-06-18] [contexte-local-v2 / C] Un libellé statique embarquant un faux temps chiffré (« ~45 min ») collisionne avec un invariant anti-fausse-précision testé par regex `~\d+ min`**
  - Symptôme : la constante `metz_local._A31_LUXEMBOURG` contenait « (~45 min hors trafic) ». Apposée au `value` du fact A31 (qui doit contenir « Luxembourg », AC3), elle faisait matcher la regex `~\d+ min` de l'invariant d'étiquetage honnête (AC23) sur un fact en repli Haversine `estimated=true` (qui ne doit afficher AUCUNE minute) → AC3 et AC23 mutuellement insatisfiables.
  - Cause racine : un libellé qualitatif d'ancrage local portait une durée chiffrée non sourcée, alors que le produit interdit la fausse précision (distance vol d'oiseau ≠ temps). Détecté par le développeur (signalé sans contourner un test), tranché en phase B.
  - Garde-fou : « ~45 min » retiré de `_A31_LUXEMBOURG` ; mention A31 placée en PRÉFIXE du value (« à vol d'oiseau » reste en fin). Verrouillé par `tests/test_contexte_local_v2_hardening.py::test_h1_*` (assert : `_A31_LUXEMBOURG` ne matche pas `~\d+ min` + fact a31 réel en repli conforme AC3∧AC23 ; falsifiable en réintroduisant la durée). Règle : ne jamais embarquer de durée chiffrée dans un libellé statique d'ancrage local ; les regex d'étiquetage honnête scannent tout le `value`, suffixe inclus.

- **[2026-06-18] [contexte-local-v2 / C] Un invariant d'étiquetage testé seulement sur les modes du chemin par DÉFAUT laisse non couverts les modes atteignables uniquement à-la-demande**
  - Symptôme : l'étiquetage honnête (AC23/AC24 : jamais « à vol d'oiseau » sur un temps réel, jamais `~\d+ min` sur un repli) n'était exercé que sur WALK/DRIVE (modes du calcul par défaut à l'analyse). Les modes TRANSIT/BICYCLE, accessibles UNIQUEMENT via `POST /travel-times`, n'étaient jamais vérifiés : un `_MODE_LABELS` amputé d'une entrée ou un repli endpoint affichant des minutes serait passé inaperçu (comportement pourtant correct dans le code, mais non verrouillé).
  - Cause racine : oracle d'invariant écrit sur le sous-ensemble de valeurs du chemin nominal, pas sur l'ensemble des valeurs atteignables par une surface publique. Parenté avec la leçon issue-100/C1 (« activation conditionnelle sur CHAQUE candidat »).
  - Garde-fou : `tests/test_contexte_local_v2_hardening.py::test_h4_endpoint_transit_bicycle_label_mode_honest` (paramétré TRANSIT+BICYCLE) et `::test_h5_endpoint_fallback_no_minutes` (falsifiables). Règle : un invariant d'étiquetage qui s'applique à un ENSEMBLE de modes/valeurs doit être asserté sur CHAQUE mode/valeur atteignable par une surface publique, pas seulement le chemin par défaut.

- **[2026-06-18] [contexte-local-v2 / D] Un AC de périmètre sur une donnée curatée ne contrôle pas la plausibilité géométrique des coordonnées qu'elle porte**
  - Symptôme : AC34 vérifiait commune ∈ `_METRO_CITIES` + degré valide sur `schools_metz.json`, mais pas les coordonnées. Une inversion lat/lon, un (0,0) ou une coord hors zone resterait verte alors que la donnée factuelle (exigence produit) serait fausse et fausserait silencieusement le k-NN écoles.
  - Cause racine : oracle de périmètre verrouillant les attributs catégoriels d'une donnée curatée, pas la géométrie exploitée par un calcul aval.
  - Garde-fou : `tests/test_contexte_local_v2_hardening.py::test_h2_real_snapshot_coords_in_metz_bbox` (bbox Metz élargie + anti-inversion lat/lon, falsifiable). Règle : quand une donnée curatée porte des coordonnées exploitées par un calcul, l'oracle de périmètre doit aussi verrouiller une bbox plausible et l'orientation lat/lon, pas seulement les champs catégoriels.

- **[2026-06-18] [contexte-local-v2 / D] DETTE — snapshot écoles curaté à la main (egress bloqué) + communes non canonicalisées à l'écriture**
  - Symptôme : l'egress vers `data.education.gouv.fr` étant bloqué en environnement de dev (`403 Host not in allowlist`), `backend/app/data/schools_metz.json` est un snapshot INITIAL curaté à la main (24 écoles réelles de Metz + couronne, 4 degrés) au lieu d'un export officiel vérifié. De plus les `commune` y sont stockées en forme non canonique (« Montigny-lès-Metz »), alors que la spec §3 D.1 prescrivait la canonicalisation à l'écriture (impact fonctionnel NUL : `commune` n'est ni exposée ni utilisée comme filtre, et AC34 re-canonicalise à la volée).
  - Cause racine : indisponibilité réseau du vendor en dev + oracle de périmètre testant l'intention (re-canonicalisation à la volée) plutôt que la forme stockée brute.
  - Garde-fou / dette : en-tête de `app/schools.py` documente source/date/Licence Ouverte + procédure de rafraîchissement (régénérer via l'API quand l'egress est ouvert, ce qui canonicalisera les communes). Garde-fou RECOMMANDÉ pour ce rafraîchissement (non ajouté ce cycle, à porter par le testeur lors de la régénération) : un test assertant la forme STOCKÉE brute (`s["commune"] in _METRO_CITIES` SANS re-canonicaliser). Règle : pour une donnée versionnée dont la spec impose une forme normalisée à l'écriture, asserter la forme stockée brute en plus de l'intention, sinon le format du fichier source peut dériver silencieusement.

- **[2026-06-23] [mobile-phase1-image-urls] Prouver une INERTIE (zéro effet) en observant la dépendance terminale RÉELLE, pas une façade qu'on a soi-même neutralisée**
  - Symptôme : en phase A, AC9 (« toutes les URLs filtrées → pas d'images ») et AC13 (« inertie sans claim éligible ») « passaient déjà » sans implémentation. AC9 mockait `assess_claims_with_photos` et assertait `image_urls == []` : il prouvait seulement que la sonde *recevait* `[]`, pas qu'aucun appel vision ne se produisait. La sonde de remplacement court-circuitait justement le point observé (`_merge_photo_status` n'appelle l'assess que si `image_urls` est truthy ; le gate `ELIGIBLE_TYPES` court-circuite DANS l'assess) → faux-vert structurel.
  - Cause racine : observer un invariant « rien ne se passe » à une couche qu'on a soi-même neutralisée par le mock. Même classe que 9.10 (tester la façade au lieu du chemin réel) et cross-agence-inc2b (« absence de 422 » ≠ transit réel).
  - Garde-fou : pour prouver une inertie, (1) observer la dépendance TERMINALE non court-circuitée (`app.photo_evidence.client.chat.completions.create` → `call_count == 0`), (2) asserter que la couche intermédiaire n'est pas invoquée du tout (`assess_claims_with_photos` `call_count == 0`, pas « appelée avec [] »), (3) ajouter un test de CONTRASTE causal : même entrée, une seule variable change → l'effet APPARAÎT (`test_b_eligible_claim_triggers_vision_same_images` : type de claim `gare`→`nature` → vision appelée). Verrouillé dans `backend/tests/test_mobile_phase1_image_urls.py` (`test_b_all_unsafe_urls_assess_not_invoked`, `test_b_eligible_claim_triggers_vision_same_images`). Règle : un AC d'inertie n'a de valeur que s'il observe l'effet terminal réel ET qu'un test de contraste prouve que l'effet serait détecté s'il survenait.

- **[2026-06-23] [mobile-phase2-tranche1] Un test de rejet `rejects.toThrow()` SANS pattern est un FAUX-VERT tant que le stub throw lui-même**
  - Symptôme : en phase A (TDD), les cas AC11 « réponse non-ok sans `detail` exploitable » écrits en `await expect(analyzeListing(...)).rejects.toThrow()` NU passaient déjà contre le stub `throw new Error('NOT_IMPLEMENTED')` — le matcher est satisfait par N'IMPORTE quel throw, donc le test ne prouvait pas le traitement du non-ok (il aurait été vert sans aucune implémentation, et le serait resté si l'impl avalait l'erreur autrement).
  - Cause racine : un assert « ça throw » ne distingue pas le throw du stub de celui de la vraie logique. Même classe que cross-agence-inc2b (« absence de 422 » ≠ transit) et 9.10 (avaler une erreur).
  - Garde-fou : contraindre le MESSAGE du rejet à une preuve du chemin réel (statut HTTP `/500/`, `/502/`, ou `detail` backend `/msg backend/`) ET interdire explicitement le message du stub (`not.toThrow(/NOT_IMPLEMENTED/)`). Ainsi le test est rouge en phase A pour la BONNE raison et falsifiable face à une erreur avalée. Verrouillé dans `mobile/src/lib/analyzeApi.test.ts`. Règle générale (TS/Jest comme Python) : un test d'erreur doit asserter la NATURE de l'erreur attendue, jamais « quelque chose a été levé ».

- **[2026-06-23] [atelier / process] Acter explicitement tout écart d'arborescence spec↔code, sinon dérive silencieuse entre tranches**
  - Symptôme : la spec tranche 1 §3.1 prévoyait `src/extract/*.ts` + `src/api/*.ts` ; le code a tout mis à plat sous `src/lib/*.ts` (`extractUrl.ts` au lieu de `firstUrl.ts`). Sans impact sur les AC (le test statique scanne `__dirname`), mais les tranches suivantes (`injectedScript.ts`, écrans RN) risquent de pointer vers une arbo fantôme.
  - Garde-fou : quand le dev réorganise l'arbo proposée, l'acter au commit ET dans la spec (note d'alignement), pour que le code embarqué à venir s'y réfère. Corollaire spécifique mobile : le futur `injectedScript` (extraction DOM dans la WebView, famille B) DOIT réutiliser `filterGallery`/`firstUrl` de `src/lib` comme SOURCE UNIQUE DE VÉRITÉ — sinon le durcissement testé ici (host-match par égalité stricte, vs `indexOf` permissif du spike) ne protégerait pas le code réellement exécuté sur device.

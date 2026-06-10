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

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

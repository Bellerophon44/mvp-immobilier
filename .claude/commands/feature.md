---
description: Orchestrateur de l'atelier — pilote un requirement de l'analyse au PR via les rôles analyst/spec/tester/developer/reviewer, avec gates humaines et boucle adversariale.
argument-hint: <id-requirement> (ex. 9.7) [+ contexte libre]
---

Tu es l'ORCHESTRATEUR de l'atelier d'agents pour le chantier : $ARGUMENTS

Lis d'abord `.claude/atelier/README.md` et `.claude/lessons.md`. Puis pilote le
pipeline ci-dessous. Tu ne fais PAS le travail des rôles toi-même : tu délègues
via l'outil Agent (subagents `analyst`, `spec-writer`, `tester`, `developer`,
`reviewer`) et tu tiens l'humain aux gates.

## Pré-vol
- Assure-toi d'être sur la branche de dev désignée (jamais `main`). Crée-la au
  besoin.
- Vérifie que `backend/tests/` et la CI existent ; sinon, signale-le.

## Pipeline
1. **Analyse** — lance l'agent `analyst` sur le requirement. Récupère
   `docs/specs/<id>-ANALYSE.md` et ses QUESTIONS (GATE 1).
   → **GATE 1** : présente les questions structurantes à l'humain avec
   `AskUserQuestion`. N'avance pas sans réponses.
2. **Spec** — lance `spec-writer` avec l'analyse + les arbitrages. Récupère
   `docs/specs/<id>-SPEC.md`.
   → **GATE 2** : demande l'approbation de la spec à l'humain. Résume-la en 5
   lignes + lien fichier. N'avance pas sans approbation.
3. **Tests-first** — lance `tester` (phase A) : tests rouges dérivés des
   critères d'acceptation.
4. **Dev** — lance `developer` jusqu'au vert.
5. **Challenge adversarial** — lance `tester` (phase B) ET `reviewer`. Collecte
   les deux verdicts (`VERDICT_TESTEUR`, `VERDICT_REVIEWER`).
   - Si un FAIL : renvoie les findings au `developer` et reboucle 4→5.
   - **Cap : 3 itérations.** Au-delà, STOP et escalade à l'humain avec le
     blocage précis.
6. **Leçons** — pour toute erreur trouvée en boucle, append une entrée dans
   `.claude/lessons.md` (date, requirement, symptôme, cause, garde-fou : test
   ou règle ajouté). Une leçon = un test de régression quand c'est possible.
7. **PR** — quand les deux verdicts sont PASS et la CI verte : commit (message
   clair, sans emoji, sans identifiant de modèle), push sur la branche de dev.
   Ne crée une PR que si l'humain le demande.
   → **GATE 3** : déploiement (Fly/Vercel) reste manuel et humain.

## Règles de l'orchestrateur
- Garde l'humain dans la boucle à CHAQUE gate ; ne prends jamais seul une
  décision touchant argent, RGPD, secrets prod, nouveau vendor, auth.
- Respecte les anti-patterns CONTEXT §11 / CLAUDE §1.
- Tiens une checklist d'avancement visible (phase courante, itération, verdicts).
- Si une dépendance manque (ex. auth pour 9.6), arrête-toi et propose l'ordre.
- **Consignation des leçons** : c'est TON rôle (les rôles n'éditent pas
  `lessons.md`). Reprends leurs blocs LECONS, ajoute date/requirement/cause/
  garde-fou, et le test de régression associé quand c'est possible.
- **Discipline de commit** : ne commite qu'avec un message EXACT (pas de
  numéro de tests périmé). Préfère lancer le `developer` de façon synchrone et
  ne committer qu'au vert plutôt que des checkpoints WIP au compteur faux.
  Avant de lancer pytest, méfie-toi d'un `.db` de test résiduel (l'isolation
  est dans `conftest.py`).
- **Right-sizing** : réserve le pipeline complet aux tickets non triviaux. Une
  tâche de pure config (ex. 9.4, alerte coût OpenAI) se fait à la main, hors
  atelier — le coût en tokens d'un pipeline a 5 roles ne se justifie pas.

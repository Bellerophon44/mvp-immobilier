# Atelier d'agents — fabrique logicielle à rôles

> Asset réutilisable. Construit pour automatiser les requirements §9 du
> `CONTEXT.md`, puis tout autre chantier (roadmap §0, backlog §8). Approche
> retenue : **subagents Claude Code à rôles spécialisés** pilotés par un
> orchestrateur, avec revue adversariale et gates humaines.

## Principe

Un chantier traverse un pipeline de rôles. Chaque rôle est un subagent
(`.claude/agents/*.md`) avec son propre contexte, donc la revue est
réellement adversariale : le testeur et le reviewer ne voient que la spec et
le diff, jamais la justification du développeur.

```
[Analyste] --GATE 1--> [Spec] --GATE 2--> [Testeur (tests-first)]
   |                                              |
   |                                              v
   +<---- boucle (cap 3) ----[Reviewer/Testeur]<--[Développeur]
                                   | PASS
                                   v
                              [Leçons] --> PR + CI --GATE 3--> merge/deploy
```

## Rôles

| Rôle | Fichier | Mission | Sort |
|---|---|---|---|
| Analyste | `agents/analyst.md` | Challenge la faisabilité vs CONTEXT/CLAUDE, lève les questions structurantes | `docs/specs/<id>-ANALYSE.md` + questions |
| Spec | `agents/spec-writer.md` | Cahier des charges + critères d'acceptation testables | `docs/specs/<id>-SPEC.md` |
| Testeur | `agents/tester.md` | Écrit les pytest AVANT le code, puis challenge | `backend/tests/test_<id>*.py` |
| Développeur | `agents/developer.md` | Implémente jusqu'à tests verts | diff |
| Reviewer | `agents/reviewer.md` | Verdict PASS/FAIL vs spec + anti-patterns §11 | verdict + findings |

## Orchestrateur

`/feature <id-requirement>` (`.claude/commands/feature.md`) enchaîne les
phases, gère les 3 gates humaines et le cap d'itérations.

## Gates humaines (jamais déléguées)

1. **GATE 1** — réponses aux questions structurantes (vendor, RGPD, stockage,
   auth, argent, secrets prod).
2. **GATE 2** — approbation de la spec.
3. **GATE 3** — review du diff + merge + déploiement.

## Mémoire — « ne plus reproduire »

Un LLM n'apprend pas entre deux runs. La connaissance acquise est
**externalisée** :
- `.claude/lessons.md` — registre relu par chaque rôle au démarrage.
- `backend/tests/` — chaque bug trouvé en boucle devient un test de régression.
- `CONTEXT.md` §11 + `backend/CLAUDE.md` §1 — anti-patterns produit.

Une leçon sans test ou sans règle = leçon oubliée.

## Invariants non négociables (rappel)

- Pas d'estimation de prix, pas de DVF/notaires, pas de redistribution
  d'annonces brutes, pas de conseil juridique (CONTEXT §11, CLAUDE §1).
- Pas d'emoji dans code/commits/prompts. Pas de secret en clair.
- Jamais de merge direct sur `main` : branche -> PR.
- Ne pas casser le schéma `/analyze` sans mettre à jour `frontend/lib/api.ts`.

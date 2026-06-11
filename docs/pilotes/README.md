# Programme pilotes — capture et exploitation des retours

> Boucle qualité de la phase pilote : chaque constat d'un utilisateur pilote
> devient une issue GitHub structurée, qui alimente le triage, l'arbitrage
> humain, puis l'atelier de dev. Objectif : faire progresser la **qualité de
> l'analyse** (pas le périmètre fonctionnel), sans régression.

## La boucle

```
Pilote constate un défaut sur une analyse réelle
  → issue « Retour pilote » (template, labels retour-pilote + triage)
  → triage : dédup, catégorie qualite/*, gravité gravite/* [automatisable]
  → synthèse périodique : findings groupés par cause racine
  → gate humaine : le fondateur retient ce qui part en dev (label pret-atelier)
  → atelier (/feature) : analyse → spec → tests AVANT code → dev → revue
  → le constat devient un cas d'évaluation versionné (anti-régression)
```

Le label `pret-atelier` est posé **uniquement** par le fondateur : c'est la
GATE 1 de l'atelier. Le triage (humain ou agent) ne décide jamais d'un
changement de comportement de l'analyse.

## Règles de capture

- **Un constat = une issue.** Trois défauts sur la même annonce = trois issues
  (elles peuvent se référencer).
- **Extraits, pas liens.** Coller les passages pertinents du texte de
  l'annonce : les liens meurent et les grands portails ne sont pas
  re-fetchables. Le lien reste optionnel en complément.
- **Anonymisation avant collage** : retirer l'adresse exacte et toute donnée
  personnelle (CONTEXT.md §11.3 — pas de redistribution de contenu d'annonce ;
  un extrait court à usage interne de qualification est acceptable, une annonce
  complète non).
- Le fondateur peut ouvrir l'issue **au nom** d'un pilote qui a remonté le
  constat oralement — mêmes règles.

## Taxonomie des labels (source : `.github/labels.json`)

| Label | Rôle |
|---|---|
| `retour-pilote` | Origine : constat pilote (posé par le template) |
| `triage` | À qualifier — retiré une fois catégorie + gravité posées |
| `pret-atelier` | Validé en gate humaine, prêt pour `/feature` |
| `qualite/extraction-llm` | Le LLM a mal lu/compris l'annonce (ex. plain-pied ≠ rez-de-chaussée) |
| `qualite/scoring` | Score ou verdict incohérent avec les constats |
| `qualite/comparables` | Pilier prix : périmètre, cascade ou valeurs douteux |
| `qualite/ancrage-local` | Contexte local, distances, allégations |
| `qualite/wording` | Formulation, ton, jargon |
| `ux` | Parcours, affichage, performance perçue |
| `gravite/bloquant-credibilite` | Fait douter de tout l'outil — priorité absolue |
| `gravite/majeur` | Conseil erroné ou inversé |
| `gravite/mineur` | Perfectible, pas trompeur |

Les menus déroulants du template (catégorie, gravité) ne posent **pas** les
labels automatiquement — c'est le rôle du triage. Le template ne pose que
`retour-pilote` + `triage`.

La synchronisation des labels est assurée par `.github/workflows/sync-labels.yml`
(idempotent : crée/met à jour depuis `labels.json` ; ne supprime jamais).
Premier déclenchement : automatique au merge sur `main`, ou manuel via
Actions → « Sync labels » → Run workflow.

## Du retour pilote au cas d'éval

Process d'alimentation du harnais `backend/evals/` (spec :
`docs/specs/evals-harness-SPEC.md`). Chaque issue `retour-pilote` validée
`pret-atelier` (GATE fondateur) devient un cas d'évaluation versionné, rejoué
avec de vrais appels LLM par `.github/workflows/evals.yml` sur toute PR
touchant le prompt ou le pipeline d'analyse.

1. **Entrée** : issue `retour-pilote` validée `pret-atelier`.
2. **Annonce synthétique obligatoire** : réécrire un texte entièrement fictif
   conservant les caractéristiques déclenchantes. **Jamais d'extrait réel
   versionné** dans le repo (public — CONTEXT §11.3 + droit d'auteur du
   rédacteur de l'annonce). L'extrait réel reste dans l'issue (usage interne
   de qualification), pas dans le repo.
3. **Convention de fichiers** : `backend/evals/cases/issue_<n>.txt` (texte de
   l'annonce seul) + `backend/evals/test_eval_issue_<n>.py`. Une fixture
   module-scoped = **un seul appel** LLM par cas et par run ; toutes les
   assertions consomment son résultat. Assertions sur champs structurés et
   mots-clés, jamais d'égalité de texte libre ; **aucun mock du LLM** (un
   eval mocké est un mock de façade par définition).
4. **Politique xfail** : comportement fautif connu non fixé →
   `xfail(reason="issue #<n>, fix non livre")`. `strict=False` si l'oracle
   dépend du LLM (non déterministe) ; `strict=True` si l'oracle est
   déterministe — ces derniers vivent dans `backend/tests/` (suite gratuite).
5. **Preuve de reproduction avant merge** : le run CI de la PR introduisant le
   cas doit montrer le statut **XFAIL** (pas XPASS) sur ses assertions de
   régression connue — c'est la preuve que l'annonce synthétique déclenche
   bien les symptômes. Sinon, reformuler le texte en se rapprochant des
   tournures déclenchantes et repousser.
6. **Checklist du chantier fix** : retirer à la main les xfail LLM
   (`strict=False`) ; les xfail `strict=True` se signalent seuls par XPASS ;
   mettre à jour les tests si les signatures internes changent.
7. **Flaky** : tout cas flaky est traité (assertion élargie, ou rejeux k=3
   avec vote majoritaire et reset de `llm_semantic._CACHE` entre rejeux),
   **jamais** re-run jusqu'au vert.

## Suites prévues

1. **Harnais d'évaluation** (`backend/evals/`) — **livré** (2026-06-11, spec
   `docs/specs/evals-harness-SPEC.md`) : chaque finding validé devient un cas
   synthétique rejoué avec de vrais appels LLM par `evals.yml` sur toute PR
   touchant le prompt — voir la section « Du retour pilote au cas d'éval »
   ci-dessus. Premier cas : issue #80.
2. **Agent de triage asynchrone** (non livré) : classement, dédup, questions
   de clarification en commentaire, synthèse hebdomadaire. Il prépare la gate
   humaine, il ne la remplace pas.

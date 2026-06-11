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

## Suites prévues (non livrées ici)

1. **Harnais d'évaluation** (`backend/evals/`) : chaque finding validé devient
   un cas (annonce anonymisée + assertions attendues), rejoué avec de vrais
   appels LLM par un workflow CI sur toute PR touchant le prompt — pattern
   `diagnose-scrapers.yml`. C'est le filet anti-régression sans lequel les
   corrections de prompt se cannibalisent.
2. **Agent de triage asynchrone** : classement, dédup, questions de
   clarification en commentaire, synthèse hebdomadaire. Il prépare la gate
   humaine, il ne la remplace pas.

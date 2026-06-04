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

(aucune pour l'instant — la première boucle adversariale alimentera cette section)

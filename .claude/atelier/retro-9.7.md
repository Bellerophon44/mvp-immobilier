# Rétro atelier — pilote 9.7 (feedback utilisateur)

> Rétrospective de process (distincte de `lessons.md`, qui consigne les bugs
> produit/technique). À relire avant de lancer un nouveau chantier.

## Verdict global
Le pilote a livré 9.7 de bout en bout (29/29 tests verts, 2 verdicts PASS) en
respectant les gates humaines. L'atelier est validé sur un cas réel.

## Ce qui a marché
- **Revue adversariale rentable** : le testeur (phase B) a trouvé un bug
  destructeur (`conftest` supprimait potentiellement une vraie base) invisible
  pour le dev ET le reviewer, et l'a converti en correctif + test + leçon.
- **Analyste = filet produit/légal** : a détecté la contradiction du footer
  « Aucune donnée conservée » vs stockage RGPD, pas seulement du code.
- **Mémoire externalisée effective** : leçons adossées à des tests de
  régression, pas de la prose seule.
- **Gates humaines tenues** : aucune décision structurante prise sans l'humain.

## Frictions et correctifs appliqués
1. Outils ↔ instructions incohérents : l'analyste devait écrire un fichier sans
   outil Write ; le testeur a été refusé sur `lessons.md`.
   -> **Corrigé** : `analyst` a désormais Write ; `tester`/`reviewer` remontent
   les leçons dans leur bloc LECONS, l'orchestrateur les consigne.
2. Course du commit WIP (dev en arrière-plan + stop-hook) -> message « 18/19 »
   inexact (en réalité un `.db` résiduel).
   -> **Corrigé** : règle de discipline de commit dans `feature.md` (commit au
   vert, message exact, méfiance du `.db` résiduel ; préférer le dev synchrone).
3. Frontière de rôle floue (le dev a corrigé le harnais du testeur).
   -> **Documenté** (règle souple) : le harnais appartient au testeur ; le dev
   peut le débloquer mais doit le signaler pour revue en phase B. A bien
   fonctionné en pratique (le testeur a re-durci ensuite).
4. Coût : ~290k tokens de subagents pour un ticket ~2h.
   -> **Règle right-sizing** dans `feature.md` : pipeline complet réservé aux
   tickets non triviaux ; la config pure (9.4) se fait à la main.

## À surveiller au prochain chantier
- Les requirements à prérequis externes (9.2 email : Resend + domaine ; 9.6 :
  auth) stalleront au GATE 1 tant que l'humain n'a pas fourni les accès.
- 9.8 dépend de 9.7 (la colonne `prompt_variant` est déjà pré-câblée).
- Mettre à jour `CONTEXT.md` §5 (doc périmée signalée par l'analyste) quand on
  touchera à nouveau le backend.

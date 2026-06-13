# 87 — ANALYSE — [pilote] Comparer les prix au niveau de la commune (Marly) et non de l'agglo

Issue GitHub #87 (retour-pilote). Catégorie : comparables — pilier prix.
Gravité signalée : bloquant-crédibilité.
Rôle de ce document : cadrage et challenge (ANALYSTE). Aucune décision
structurante prise ici ; les choix sont remontés en GATE 1.

Bien concerné : MAISON À VENDRE À MARLY — 257 m², 1 095 000 €, 8 pièces,
DPE C, terrain ~2300 m², dépendances (appartement indépendant, garage 5
véhicules, piscine couverte). Marly est une commune limitrophe de Metz,
réputée recherchée. Prix au m² affiché du bien : 1 095 000 / 257 ≈ 4 261 €/m².

Texte de l'outil incriminé : « À l'échelle de Metz Métropole (communes
voisines) (DPE C-D), le prix au m² dépasse nettement les niveaux observés
(au-delà de 2863 €/m²) pour des biens similaires. À pondérer : DPE C,
construction ancienne, 4 places de parking. »

---

## 0. Diagnostic technique préalable (état réel du code)

La sélection des comparables est une **cascade** dans
`backend/app/market_stats.py:160` (`compute_market_stats`), du périmètre le
plus précis au plus large :

> quartier+DPE → quartier → secteur+DPE → secteur → ville+DPE → ville →
> métropole+DPE → métropole

Construction des candidats : `market_stats.py:193-208`. Choix du niveau
retenu : `market_stats.py:212-224`.

Points établis par lecture du code (pas la doc) :

1. **Le grain "commune" EXISTE déjà.** Le filtre se fait sur
   `Comparable.city` (nom de commune canonique), pas sur l'agglo :
   `market_stats.py:131-134`. Pour un bien à Marly, `city = "Marly"` et le
   niveau "ville" de la cascade interroge bien **les seules transactions de
   Marly**. Le problème n'est donc PAS l'absence de niveau commune.

2. **Marly n'a pas de quartier ni de secteur.** `_SECTORS_RAW`
   (`market_stats.py:36-50`) ne couvre que les quartiers de Metz intra-muros.
   Pour Marly, `district = None`, `sector = None` : les 4 premiers candidats
   de la cascade (quartier/secteur) sont **sautés**. Restent : ville+DPE,
   ville, métropole+DPE, métropole.

3. **Le bien tombe à l'échelle métropole** parce que le niveau "ville" (Marly)
   est trop creux. La règle `ville_usable` (`market_stats.py:221`) ne retient
   le niveau ville **sans DPE** que s'il atteint `MIN_COMPARABLES = 3`
   (`market_stats.py:26`) ; le niveau ville+DPE exige `MIN_REFINED_COMPARABLES
   = 10` (`market_stats.py:25,222`). Le texte affiché dit « Metz Métropole
   (communes voisines) (DPE C-D) » : c'est le candidat
   `("metropole", _METRO_NAME, ..., band="C-D", metro_cities)`
   (`market_stats.py:205-206`), donc l'outil n'a trouvé **ni 10 maisons
   206-308 m² à Marly DPE C-D, ni 3 maisons 206-308 m² à Marly toutes DPE
   confondues**, et a élargi à l'agglo. Marly est dans `_METRO_CITIES`
   (`market_stats.py:58-71`), donc l'élargissement métropole est autorisé.

4. **La fenêtre surface est ±20 %** (`market_stats.py:187-188`) : pour 257 m²,
   206-308 m². Une maison de 257 m² avec dépendances est un bien rare ; le
   pool communal de Marly dans cette tranche est presque certainement < 3.

5. **Le périmètre EST déjà annoncé à l'utilisateur.** Le verdict textuel
   préfixe « À l'échelle de Metz Métropole (communes voisines) »
   (`_scope_context`, `market_stats.py:257-270`), et le front affiche le
   `scope_name` + `n_comparables` dans un libellé dédié (`scopeLabel`,
   `frontend/app/page.tsx:42-51`, rendu lignes 906-922). L'info de périmètre
   n'est donc PAS cachée — mais elle est présentée comme une référence valide,
   sans avertir que comparer Marly à l'agglo aplatit l'effet-commune.

6. **`refinable` n'aide pas ici.** Il n'est vrai que pour un bien à Metz
   (`market_stats.py:458-461`) ; le sélecteur de quartier front ne propose que
   des quartiers de Metz. Un utilisateur à Marly n'a aucun moyen de resserrer.

**Conclusion du diagnostic :** ce n'est pas un défaut de *grain* (la commune
est disponible et tentée en premier), c'est un **défaut de robustesse
statistique sur petit échantillon** (la commune recherchée est trop creuse →
fallback agglo) **combiné à un défaut d'explicitation** (le fallback est
nommé mais pas présenté comme une approximation à valeur réduite). Le pilote a
raison sur le ressenti (« cette comparaison n'a pas de valeur ») mais la cause
n'est pas celle qu'il suppose (« les comparables devraient être au niveau de
Marly » — ils le sont déjà tentés, il n'y en a juste pas assez).

---

## 1. Objectif et périmètre

### Objectif reformulé
Quand le pilier prix élargit le périmètre au-dessus de la commune du bien
(fallback métropole, voire ville pour un bien hors agglo), l'utilisateur doit
**comprendre que la référence affichée n'est pas un comparatif de la commune**
et que l'effet-commune (Marly chère vs moyenne agglo) **biaise le verdict** —
voire le verdict doit être **dégradé / requalifié** au lieu d'être asséné.

### Qualification : "change" plus que "bug"
Confirmé. Le code fait ce qu'il a été spécifié pour faire (cascade,
élargissement documenté §11bis « Secteur Metz métropole »). Le pilote conteste
un **choix produit** (présenter un fallback agglo comme une référence ferme),
pas une régression. C'est une évolution de comportement, pas une correction de
défaut.

### IN
- Comportement du pilier prix lorsque le périmètre retenu est plus large que
  la commune du bien (au minimum : métropole pour un bien d'agglo).
- Honnêteté de l'explication et du verdict dans ce cas (wording, et/ou
  dégradation du verdict, et/ou de la confiance).
- Éventuellement : seuil de déclenchement du fallback métropole.

### OUT (sauf décision explicite en GATE 1)
- Toute estimation de prix « corrigée de l'effet-commune » (anti-pattern §11.1
  / CLAUDE §1 : interdit d'estimer). On ne fabrique pas un prix Marly.
- Importer DVF / notaires pour densifier Marly (anti-pattern §11.4).
- Pondération géostatistique (indice de prix par commune, modèle hédonique) :
  hors MVP, et frôle l'estimation.
- Refonte du sélecteur de quartier en sélecteur de commune (possible mais
  lourd front ; à arbitrer).
- Le cas des biens atypiques (257 m² + piscine + dépendances) en tant que tel :
  aucun outil statistique n'aura de comparable strict pour ce bien ; c'est une
  limite structurelle à assumer, pas à résoudre.

---

## 2. Cartographie d'impact

| Zone | Fichier:ligne | Nature de l'impact |
|---|---|---|
| Cascade / seuils | `backend/app/market_stats.py:25-26,193-224` | Cœur : seuil de fallback métropole, ordre des candidats |
| Wording verdict | `backend/app/market_stats.py:257-316` (`_scope_context`, `interpret_price_positioning`) | Texte affiché ; lieu d'un avertissement explicite |
| Verdict/confiance | `backend/app/market_stats.py:392-462` (`compute_confidence`, `compute_price_market_pillar`) | Lieu d'une dégradation de verdict/confiance sur fallback élargi |
| Exposition API | `backend/app/analysis.py:215-228` (`pillars[0]`) | `scope`/`scope_name`/`n_comparables`/`refinable` déjà exposés. Ajouter un champ ? → impacte le contrat |
| Schéma `/analyze` | `backend/app/main.py` (modèle `AnalyzeResponse`, pilier) | Si on ajoute un champ au pilier (ex. `scope_is_fallback`), MAJ obligatoire + `frontend/lib/api.ts` (anti-pattern §11.9) |
| Front contrat | `frontend/lib/api.ts:10-14` | `scope`, `scope_name`, `refinable` déjà typés ; ajout de champ à répercuter |
| Front rendu | `frontend/app/page.tsx:42-51,906-936` | `scopeLabel` + bloc périmètre ; lieu d'un bandeau « hors commune » |
| Données géo | `backend/db/models.py:25` (`postal_code`), `Comparable.city` | Grain commune = `city`. `postal_code` ne sert qu'au filtre dépt à l'ingestion, pas à la sélection. Pas de code INSEE stocké |
| DB | — | **Aucune migration nécessaire** pour les options légères (le grain commune existe). Migration seulement si on stocke un drapeau ou un indice par commune (déconseillé) |
| CI / tests | `backend/tests/` (pas de test market_stats cascade aujourd'hui — à vérifier), evals | Tout changement de wording/seuil doit être verrouillé par un test ; risque de casser des evals de prompt si le wording prix change |

Note : aucun test dédié à la cascade `market_stats` n'a été trouvé dans
`backend/tests/` lors du survol ; à confirmer par le spec-writer. Le pilier
prix est en revanche touché par les evals (`market_stats` est dans le
déclencheur `evals.yml`, CLAUDE §11).

---

## 3. Faisabilité données (la question structurante)

### Volume au niveau commune
- Base prod ~17,7k comparables, ~2,6k maisons, mais **dominées par Metz
  intra-muros** ; CLAUDE §11 acte explicitement « volume par commune encore
  faible hors Metz ». Les communes limitrophes sont alimentées surtout par les
  agences HTML (benedic, idemmo, immoheytienne, laveine_immo), faible volume.
- Pour Marly spécifiquement, maisons dans 206-308 m² : très probablement < 3
  (sinon le fallback métropole ne se serait pas déclenché). Même en élargissant
  la fenêtre surface, le stock de grandes maisons à Marly reste faible.

### Conséquence
Une stratégie « commune stricte » renverrait **« Indéterminé »** pour la
quasi-totalité des biens hors Metz et pour les biens atypiques. C'est honnête
mais réduit fortement la couverture du pilier (le différenciateur principal).

### Fallback : c'est LA question
Le fallback existe déjà (métropole). Le débat n'est pas « faut-il un
fallback » mais « **un fallback agglo doit-il produire un verdict ferme
("Fortement sur-positionné") ou un verdict atténué / un simple repère** ».
Comparer Marly (commune prisée) à la moyenne d'agglo produit mécaniquement un
« sur-positionné » qui dit surtout « Marly > moyenne agglo », pas « ce bien est
cher pour Marly ». C'est le faux-signal que le pilote dénonce.

---

## 4. Risques et anti-patterns

- **Estimation déguisée (§11.1, CLAUDE §1)** : toute « correction
  d'effet-commune » (coefficient Marly/agglo, indice de prix communal) est une
  forme d'estimation. À proscrire. On peut requalifier/avertir, jamais
  recalculer un prix de référence pour Marly.
- **DVF / notaires (§11.4)** : densifier Marly par DVF est interdit et casserait
  le positionnement. Exclu.
- **Robustesse petit échantillon** : abaisser les seuils pour « forcer » un
  verdict communal sur 1-2 transactions produirait des quartiles ininterprétables
  (leçon récurrente : un sous-échantillon trop fin a des quartiles trompeurs,
  commentaire `market_stats.py:21-24`). Anti-pattern statistique.
- **Coût** : nul. Aucune des options n'ajoute d'appel LLM ni de vendor. Tient
  dans le MVP < 1 €/mois.
- **RGPD** : aucun. On manipule des agrégats internes, pas de donnée perso.
- **Contrat API (§11.9)** : ajouter un champ au pilier impose la MAJ
  synchronisée `main.py` + `lib/api.ts`. Une option « wording seul » évite ce
  risque.
- **Evals de prompt** : changer le wording du pilier prix peut faire bouger des
  assertions d'evals — à vérifier avant merge.

---

## 5. OPTIONS (choix structurant : que faire du fallback hors-commune)

Toutes les options partent du constat que **le grain commune existe déjà** et
qu'il est **déjà tenté en premier**. Elles diffèrent sur le traitement du cas
« commune trop creuse ».

### Option A — Wording d'avertissement seul (le plus léger)
Quand `scope` ∈ {metropole} (ou plus large que la commune du bien), ajouter
une phrase explicite du type : « Faute d'assez de transactions comparables à
Marly, cette fourchette reflète l'ensemble de Metz Métropole ; une commune
recherchée peut se situer durablement au-dessus. À interpréter comme un repère,
pas comme une référence locale. »
- **Effort** : ~1/2 j. Wording dans `_scope_context` / `interpret_price_positioning`.
- **Contrat** : inchangé si on n'ajoute pas de champ (texte seul). Zéro
  `lib/api.ts`.
- **+** : répond directement au grief du pilote (honnêteté) ; zéro risque
  produit ; zéro estimation ; couverture inchangée.
- **−** : le **verdict** reste « Fortement sur-positionné » (la pastille/le
  score prix restent sévères). Un lecteur pressé voit le verdict, pas le texte.

### Option B — Dégrader verdict ET confiance sur fallback hors-commune
En plus du wording (A), quand le périmètre retenu est plus large que la commune
du bien : forcer la confiance à « Faible » et **plafonner le verdict** (ex. ne
jamais conclure « Fortement sur-positionné » sur un pool agglo pour un bien de
commune prisée — au plus « à confirmer localement »), donc neutraliser une
partie du poids prix dans le score.
- **Effort** : ~1-1,5 j. Touche `compute_price_market_pillar` + `compute_confidence`
  + scoring indirectement.
- **Contrat** : un champ `scope_is_fallback: bool` au pilier serait propre →
  MAJ `main.py` + `lib/api.ts` (§11.9). Sinon dérivable côté front depuis
  `scope` + ville, mais moins net.
- **+** : corrige le faux-signal au niveau verdict ET score, pas seulement
  texte ; aligne sévérité et fiabilité réelle.
- **−** : touche le scoring (40 pts prix) → effet de bord sur le score global,
  à valider contre la charte produit (CLAUDE §11 : sévérité prix déjà en débat) ;
  change le contrat ; plus de tests.

### Option C — Périmètre adaptatif par rayon / communes voisines pondérées
Remplacer le saut binaire commune→agglo par un élargissement progressif
(communes limitrophes une à une, ou rayon), éventuellement pondéré.
- **Effort** : élevé (plusieurs jours), nécessite une carte d'adjacence
  communale et/ou des coords ; la pondération frôle l'estimation.
- **+** : périmètre plus « juste » géographiquement.
- **−** : sur-dimensionné pour le MVP ; complexité ; risque anti-pattern
  (pondération = quasi-estimation) ; gain marginal tant que le stock communal
  hors Metz est faible (on retomberait vite sur l'agglo de toute façon).
- **Reco** : **écarter** pour ce requirement.

### Option D — Commune stricte + "Indéterminé" assumé (pas de fallback agglo)
Ne jamais élargir au-dessus de la commune du bien hors Metz : si la commune est
creuse → « Indéterminé ».
- **Effort** : faible (désactiver le candidat métropole hors Metz).
- **+** : zéro faux-signal ; parfaitement honnête.
- **−** : **régression de couverture majeure** — le pilier prix devient muet
  pour la plupart des biens hors Metz, alors qu'il est le différenciateur.
  Contredit l'intention §11bis (fallback métropole délibérément ajouté).
- **Reco** : **écarter** seul, mais c'est l'option de repli si on refuse tout
  affichage de fallback.

### Recommandation de l'analyste
**Option A en première intention** (livraison rapide, zéro risque, répond au
grief central qui est un grief d'honnêteté/d'explication), avec une **brique de
l'Option B limitée à la confiance** (forcer « Faible » sur fallback
hors-commune) si on l'estime peu risquée. Garder le plafonnement de verdict et
la touche au scoring (B complet) pour un second temps, car ils ouvrent le débat
scoring (CLAUDE §11) et changent le contrat. Écarter C et D.

Justification : le diagnostic §0 montre que le défaut est d'abord
d'**explicitation** (le pool commune est déjà tenté, il est juste trop creux).
Le pilote interprète mal la cause ; corriger d'abord ce que l'on affirme à
l'utilisateur règle le « bloquant-crédibilité » sans toucher au moteur
statistique ni au scoring.

---

## 6. Challenge du requirement (posture adversariale)

1. **Le requirement présuppose une mauvaise cause.** « Les comparables
   devraient être au niveau de Marly » — ils le sont déjà tentés
   (`market_stats.py:131-134,203-204`). Le vrai problème est l'absence de
   transactions Marly comparables et la présentation du repli. Cadrer le fix
   sur le grain serait traiter le mauvais levier.
2. **Un comparateur par commune robuste est-il à la portée d'un MVP < 1 €/mois ?**
   Non, pas avec le stock actuel hors Metz (CLAUDE §11). Sans DVF (interdit) ni
   collecte massive multi-communes, le volume communal restera faible. D'où la
   reco « expliquer/atténuer », pas « densifier ».
3. **Plus simple que tout fix moteur :** Option A (wording). Elle restaure la
   crédibilité (le grief est « cette comparaison n'a pas de valeur » → on le dit
   nous-mêmes) sans risque ni changement de contrat.
4. **Attention au sur-correctif :** plafonner le verdict (B) peut masquer un
   bien réellement trop cher même pour sa commune. Le wording prudent informe
   sans cacher. À trancher avec la charte produit.

---

## 7. QUESTIONS POUR L'HUMAIN (GATE 1)

1. **Niveau d'intervention.** Vu que le grain commune est déjà tenté en premier
   et que le défaut est surtout un défaut d'explicitation d'un fallback agglo,
   on retient :
   - (a) Option A seule — wording d'avertissement quand le périmètre est plus
     large que la commune du bien [reco, le plus rapide, zéro risque] ;
   - (b) Option A + forcer la confiance « Faible » sur ce fallback ;
   - (c) Option A + B complet (plafonner le verdict + impact scoring) — change
     le contrat et ouvre le débat scoring.
   *Reco : (a), avec (b) si jugé peu risqué ; différer (c).*

2. **Verdict sur fallback agglo : informer ou neutraliser ?** Doit-on continuer
   d'afficher un verdict ferme (« Fortement sur-positionné ») accompagné d'un
   avertissement (option A), ou empêcher tout verdict « sur-positionné » quand
   la référence est l'agglo et non la commune (option B) ?
   *Reco : informer (A). Neutraliser le verdict risque de masquer un vrai
   sur-prix ; le wording prudent suffit au grief de crédibilité.*

3. **Seuil de fallback.** Faut-il relever le seuil de bascule vers la métropole
   (ex. n'élargir que si la commune a < N maisons, avec N plus exigeant) ou le
   laisser tel quel (ville usable dès 3) ? Cela ne changera rien pour Marly
   (creux quel que soit le seuil) mais clarifie la doctrine.
   *Reco : laisser tel quel ; l'effort utile est sur l'explication, pas le seuil.*

4. **Champ de contrat.** Acceptez-vous d'ajouter un champ booléen au pilier
   (ex. `scope_is_fallback`) — ce qui impose MAJ `main.py` + `frontend/lib/api.ts`
   (anti-pattern §11.9, géré) — ou préférez-vous rester en **wording pur** (texte
   dans l'explication, zéro changement de contrat) ?
   *Reco : wording pur pour A ; champ seulement si on va jusqu'à B.*

5. **Sélecteur de commune front (hors périmètre proposé).** Faut-il, à terme,
   permettre à l'utilisateur de choisir/préciser la commune comme il précise le
   quartier de Metz (`refinable`) ? Aujourd'hui `refinable` est réservé à Metz
   (`market_stats.py:458-461`). Hors scope de ce fix, mais à acter pour la suite.
   *Reco : noter en backlog, ne pas inclure ici.*

6. **Évals.** Confirmez-vous qu'un changement de wording du pilier prix doit
   être validé contre `evals/` (vrais appels LLM, payant) avant merge, et qu'un
   test unitaire dédié à la cascade `market_stats` (absent aujourd'hui) doit
   être créé pour verrouiller le nouveau comportement ?
   *Reco : oui aux deux ; le spec-writer prévoit le test de régression.*

---

## 8. ARBITRAGES HUMAINS (GATE 1 — tranché le 2026-06-13)

Décisions de l'humain, à charge pour le spec-writer de les traduire en
critères d'acceptation testables.

1. **Niveau d'intervention → Option A (wording seul).** Ajouter un
   avertissement quand le périmètre retenu est plus large que la commune du
   bien (au minimum : fallback métropole). Le verdict et le score prix restent
   inchangés. Pas de plafonnement de verdict, pas de forçage de confiance
   (options B écartées pour ce fix).

2. **Contrat API → wording pur.** Aucun champ ajouté au pilier ; texte intégré
   dans l'explication (`_scope_context` / `interpret_price_positioning`).
   Aucune MAJ de `main.py` ni `frontend/lib/api.ts`. (Conséquence : si le front
   doit styliser l'avertissement, il le dérive de `scope` + ville déjà exposés,
   sans nouveau champ.)

3. **Seuil de fallback → relever le seuil.** Décision divergente de la reco
   analyste. Doctrine retenue : un verdict commune sur trop peu de transactions
   est statistiquement fragile (quartiles trompeurs, cf. `market_stats.py:21-24`),
   donc on durcit le seuil de rétention du niveau ville. Le spec-writer fixe la
   nouvelle valeur de `MIN_COMPARABLES` (actuellement 3, `market_stats.py:26`) —
   et vérifie l'effet sur `MIN_REFINED_COMPARABLES` (10) et sur la couverture
   globale (un seuil trop haut élargit les replis agglo et rend le pilier muet).
   À chiffrer et justifier dans la spec ; ce changement de comportement doit
   être couvert par un test de cascade.

### Points non bloquants (recos analyste retenues par défaut)

4. **Sélecteur de commune front** (Q5) : hors périmètre, noté en backlog.
   `refinable` reste réservé à Metz pour ce fix.
5. **Évals + test de régression** (Q6) : oui aux deux. Le changement de wording
   du pilier prix est validé contre `evals/` avant merge ; un test unitaire
   dédié à la cascade `market_stats` (absent aujourd'hui) est créé pour
   verrouiller le nouveau comportement (wording + nouveau seuil).

### Périmètre net pour la spec
- IN : avertissement textuel sur fallback hors-commune ; relèvement du seuil
  `MIN_COMPARABLES` (valeur à fixer + justification) ; test de cascade ; passage
  evals.
- OUT : plafonnement de verdict, forçage de confiance, champ de contrat,
  scoring, sélecteur de commune, toute densification de données (DVF).

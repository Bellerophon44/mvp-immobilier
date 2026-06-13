# 87 — SPEC — Avertissement de périmètre hors-commune sur le pilier prix

Issue GitHub #87 (retour-pilote, bloquant-crédibilité). Rôle de ce document :
cahier des charges implémentable. Source : `docs/specs/87-ANALYSE.md`
(diagnostic §0, cartographie §2, options §5, ARBITRAGES HUMAINS §8) et lecture
du code réel (`backend/app/market_stats.py`, `backend/app/analysis.py`,
`backend/app/main.py`, `frontend/lib/api.ts`, `frontend/app/page.tsx`).

Les arbitrages GATE 1 (§8 de l'analyse) sont actés et non négociables ; cette
spec les traduit en critères testables.

---

## 1. Objectif et périmètre

### Objectif
Quand le pilier prix retient un périmètre de comparables **plus large que la
commune du bien** (typiquement le repli métropole), l'explication doit avertir
explicitement, en nommant la commune du bien et le périmètre réellement
utilisé, que la fourchette affichée est un **repère** et non une référence
locale de la commune. En complément, durcir le seuil de rétention du niveau
ville (`MIN_COMPARABLES`) pour ne pas asseoir un verdict communal sur un
sous-échantillon statistiquement fragile.

Le verdict de positionnement, le score prix et le contrat `/analyze` restent
strictement inchangés : la valeur du verdict ne change pas, seul le **texte**
de l'explication s'enrichit.

### IN
- Avertissement textuel (wording) intégré à l'explication du pilier prix
  lorsque le `scope` retenu est plus large que la commune du bien (au minimum :
  `scope == "metropole"`).
- Relèvement de la constante `MIN_COMPARABLES` (valeur fixée et justifiée en
  §3.3), appliquée dans la cascade de `compute_market_stats`.
- Création d'un test pytest dédié à la cascade `market_stats` (absent
  aujourd'hui) verrouillant le wording et le nouveau seuil.
- Passage de la suite `evals/` avant merge (point de vigilance CI, §6).

### OUT (non-objectifs, bornage du dev)
- Plafonnement / requalification du verdict de positionnement (Option B :
  écartée).
- Forçage de la confiance (`compute_confidence` inchangée).
- Tout nouveau champ de contrat sur le pilier (ex. `scope_is_fallback`) :
  interdit. `main.py` (`AnalyzeResponse`) et `frontend/lib/api.ts` ne sont pas
  touchés.
- Toute modification du scoring (`scoring.py`, pondération 40/30/30).
- Sélecteur de commune front ; `refinable` reste réservé à Metz.
- Toute densification de données (DVF, notaires) ou correction d'effet-commune
  (= estimation déguisée, interdit).

---

## 2. Décisions actées (GATE 1, §8 de l'analyse)

1. **Option A — wording seul.** On ajoute un avertissement textuel quand le
   périmètre des comparables retenu est plus large que la commune du bien
   (au minimum : repli métropole). Le verdict (positionnement) et le score prix
   restent INCHANGÉS. Pas de plafonnement de verdict, pas de forçage de
   confiance.

2. **Contrat API — wording pur.** AUCUN champ ajouté au pilier. Le texte est
   intégré dans l'explication existante produite par `_scope_context` /
   `interpret_price_positioning`. AUCUNE MAJ de `main.py` (`AnalyzeResponse`)
   ni de `frontend/lib/api.ts`. Invariant verrouillé par un critère
   d'acceptation (clés de réponse `/analyze` et clés du pilier figées).

3. **Relèvement de `MIN_COMPARABLES`.** Changement de comportement assumé par
   l'humain, divergent de la reco analyste. Doctrine : un verdict communal sur
   trop peu de transactions est statistiquement fragile (quartiles trompeurs,
   cf. `market_stats.py:21-24`). Nouvelle valeur fixée en §3.3 avec
   justification et examen de l'effet sur `MIN_REFINED_COMPARABLES` (10) et sur
   la couverture.

---

## 3. Contrat technique

### 3.1 Détection « périmètre plus large que la commune »

Le signal de déclenchement de l'avertissement se calcule à partir des données
DÉJÀ disponibles dans le dict `market_stats` (aucun champ ajouté au contrat) :

- `market_stats["scope"]` ∈ `{"quartier", "secteur", "ville", "metropole"}`.
- La commune du bien est `canonical_city(city)` (déjà calculée dans
  `compute_market_stats`, `market_stats.py:176`).

Règle : l'avertissement s'affiche si et seulement si le périmètre retenu n'est
PAS rattaché à la commune du bien. Dans l'état actuel du code, cela se réduit à :

> **avertissement actif ⇔ `scope == "metropole"`**

car `"quartier"`, `"secteur"` et `"ville"` ciblent tous la commune du bien
(quartier/secteur n'existent que pour Metz et restent dans `city`, et `"ville"`
filtre sur `Comparable.city == city`). Le scope `"metropole"` est le seul qui
élargit à `_METRO_CITIES` (`market_stats.py:205-208`). Le cas `market_stats is
None` (verdict « Indéterminé ») n'affiche pas d'avertissement (pas de
fourchette à qualifier).

Implémentation attendue : le wording est ajouté dans la couche d'explication du
pilier, à partir du `scope` et du nom de commune. Deux emplacements possibles,
au choix du développeur, tant que le résultat est observable sur l'explication
finale du pilier :

- soit dans `_scope_context` (`market_stats.py:257-270`), qui connaît déjà le
  `scope` et le `scope_name` ;
- soit dans `interpret_price_positioning` (`market_stats.py:273-316`), qui
  construit l'`explanation`.

Contrainte : le nom de la commune du bien (`canonical_city(city)`) doit être
accessible à l'endroit retenu. `_scope_context` et `interpret_price_positioning`
ne reçoivent aujourd'hui que `market_stats` (qui ne porte pas la commune
d'origine, seulement `scope_name` = `_METRO_NAME` quand le scope est
métropole). Le développeur doit donc faire transiter la commune du bien
jusqu'au point de génération du wording. Pistes acceptables (sans toucher au
contrat) :

- ajouter la commune du bien dans le dict interne `market_stats` retourné par
  `compute_market_stats` sous une clé interne (ex. `"property_city"`) — ce dict
  est INTERNE au backend et n'est PAS le pilier exposé ; il n'est jamais
  sérialisé tel quel dans `/analyze` (seules les clés listées en
  `compute_price_market_pillar` le sont) ;
- ou passer la commune en argument explicite aux fonctions de wording.

Quelle que soit la piste, un critère d'acceptation (§4, AC-CONTRAT) prouve
qu'aucune clé nouvelle ne fuit dans la réponse `/analyze` ni dans le dict du
pilier exposé.

### 3.2 Gabarit du wording d'avertissement

Le texte doit :
- nommer la **commune du bien** (`canonical_city(city)`, ex. « Marly ») ;
- nommer le **périmètre réellement utilisé** (`scope_name`, ex.
  « Metz Métropole ») ;
- exprimer la tonalité « repère, pas référence locale » sans estimer ni
  recalculer un prix communal.

Gabarit de référence (le wording exact est figé par le développeur ; les tests
asserteront sur des invariants robustes, voir §4, pas sur la phrase au
caractère près) :

> « Faute d'assez de transactions comparables à {commune}, cette fourchette
> reflète {scope_name} (communes voisines), pas {commune} seule : une commune
> recherchée peut s'en écarter durablement. À interpréter comme un repère, pas
> comme une référence locale. »

Contraintes vérifiables par test (oracle robuste) :
- la chaîne contient le nom de la commune du bien ;
- la chaîne contient le nom du périmètre élargi (`scope_name`, ex.
  « Metz Métropole ») ;
- la chaîne contient un marqueur de tonalité « repère » (le mot « repère »).

Le wording s'ajoute APRÈS la phrase de positionnement existante, dans la même
`explanation`. Il ne remplace pas, ne modifie pas et ne réordonne pas le texte
de verdict produit par `interpret_price_positioning` ni le signal `_criteria_signal`
(« À pondérer : … »). Conventions CLAUDE §12 : pas d'emoji, pas de commentaire
« what », logging via le logger nommé `market_stats` existant si un log est
ajouté (non requis).

### 3.3 Nouveau seuil `MIN_COMPARABLES`

État actuel (`market_stats.py:25-26`) :
- `MIN_REFINED_COMPARABLES = 10` (niveaux affinés : quartier, secteur,
  ville+DPE, métropole+DPE) ;
- `MIN_COMPARABLES = 3` (plancher absolu, condition `ville_usable`
  `market_stats.py:221`, et garde-fou final `market_stats.py:232`).

Décision : **`MIN_COMPARABLES = 5`.**

Justification :
- 3 transactions ne permettent pas des quartiles (Q1/Q3) interprétables
  (commentaire `market_stats.py:21-24`) ; 5 reste un plancher modeste mais
  écarte les pools communaux les plus creux. C'est un relèvement prudent (+2),
  pas un saut vers 10 qui viderait massivement le niveau ville hors Metz.
- `MIN_COMPARABLES` est utilisé à DEUX endroits ; les deux doivent rester
  cohérents avec la nouvelle valeur :
  1. `ville_usable` (`market_stats.py:221`) : le niveau ville (sans DPE) n'est
     retenu qu'à partir de 5 comparables au lieu de 3 ; en-dessous, la cascade
     bascule au candidat suivant (métropole+DPE puis métropole) ;
  2. garde-fou final (`market_stats.py:232`) : `if len(comparables) <
     MIN_COMPARABLES: return None`. Conséquence à acter : un dernier candidat
     (filet) retenu avec 3 ou 4 comparables renverra désormais `None`
     (« Indéterminé ») au lieu d'une fourchette. C'est cohérent avec la
     doctrine (pas de fourchette sur < 5 transactions), mais c'est une
     **diminution de couverture** sur les biens dont même le filet le plus
     large reste entre 3 et 4 comparables.

- `MIN_REFINED_COMPARABLES` (10) reste **inchangé** : il borne les niveaux
  affinés (DPE, quartier, secteur). Le relever davantage durcirait l'affinage
  sans rapport avec le grief #87 (qui porte sur le repli commune→agglo). On
  garde l'invariant `MIN_COMPARABLES (5) < MIN_REFINED_COMPARABLES (10)` :
  un niveau affiné reste plus exigeant qu'un niveau large, et la zone
  intermédiaire [5,10[ continue de privilégier le niveau ville sans DPE sur un
  affinage DPE creux.

Effet sur la couverture (impact métropole / pilier muet) :
- Pour un bien d'agglo (commune ∈ `_METRO_CITIES`) dont la commune a entre 3 et
  4 comparables dans la fenêtre surface : on **ne retient plus le niveau ville**
  et on bascule au repli métropole — donc **le wording §3.2 se déclenche** sur
  exactement ces cas (effet voulu, cohérent : on dit à l'utilisateur que la
  référence n'est plus sa commune).
- Pour un bien **hors** `_METRO_CITIES` (pas de candidat métropole) dont la
  commune a entre 3 et 4 comparables : le dernier candidat est `("ville", …)`
  avec < 5 comparables → garde-fou final → `None` → « Indéterminé ». C'est une
  régression de couverture assumée par l'arbitrage GATE 1 (doctrine
  statistique).

Chiffrage fin (risque résiduel documenté) : le volume réel de comparables par
commune dans la fenêtre surface ±20 % n'est **pas mesurable depuis le code ni
depuis des fixtures** (la base prod ~17,7k comparables n'est pas accessible
dans le repo de test ; CLAUDE §11 indique seulement « volume par commune encore
faible hors Metz »). On retient donc une valeur **prudente (+2 → 5)** plutôt
qu'un seuil agressif, et on **documente en risque résiduel** que la part exacte
de biens basculant ville→métropole ou ville→« Indéterminé » n'est pas chiffrée.
Si une mesure prod ultérieure montrait un assèchement notable du pilier hors
Metz, réviser cette valeur (à la baisse) plutôt que de relâcher les autres
garde-fous.

### 3.4 Contrat `/analyze` — invariant verrouillé

- `AnalyzeResponse` (`backend/app/main.py:80-88`) : inchangé. `pillars` y est
  typé `list` (pas un modèle Pydantic strict), donc **FastAPI ne filtre PAS les
  clés du pilier** : l'invariant « pas de nouveau champ exposé » ne tient que
  par le code de `analysis.py` (`pillars[0]`, lignes 215-228) et par
  `compute_price_market_pillar` (`market_stats.py:445-462`). Le test contrat
  (§4, AC-CONTRAT) doit donc asserter sur les clés RÉELLES du pilier produit,
  pas seulement sur l'absence de 422 ni sur le filtrage response_model (leçon
  9.10 : faux-vert tautologique sur response_model).
- Clés autorisées du pilier prix exposé (`analysis.py:215-228`), figées :
  `label`, `verdict`, `explanation`, `points`, `max`, `scope`, `scope_name`,
  `dpe_band`, `n_comparables`, `refinable`. Aucune clé supplémentaire.
- `frontend/lib/api.ts` (`ApiPillar`) : inchangé.

---

## 4. Critères d'acceptation (numérotés, testables en pytest)

Tous les AC ci-dessous s'asserent au niveau des fonctions sous-jacentes
(`compute_market_stats`, `interpret_price_positioning` /
`compute_price_market_pillar`) ET, pour le contrat, via le chemin endpoint
réel, jamais seulement via le filtrage Pydantic (leçon 9.10). Les seuils sont
testés aux valeurs EXACTES de bord (leçon 9.7).

**AC1 — Le wording APPARAÎT sur repli métropole.**
Pour un bien d'une commune d'agglo dont la commune est trop creuse (pool
communal < 5 dans la fenêtre surface) mais où la métropole fournit ≥ 5
comparables, `compute_price_market_pillar` retourne un pilier dont
`scope == "metropole"` ET `explanation` contient : le nom de la commune du bien,
le nom du périmètre élargi (`scope_name`), et le marqueur de tonalité « repère ».

**AC2 — Le wording N'APPARAÎT PAS quand le scope est la commune.**
Pour un bien dont le scope retenu est `"ville"` (pool communal ≥ 5), le pilier a
`scope == "ville"` et son `explanation` ne contient PAS le marqueur de
tonalité « repère » ni de mention « communes voisines ». Même garantie pour
`scope == "quartier"` et `scope == "secteur"` (bien messin) : pas de wording
d'avertissement.

**AC3 — Le verdict de positionnement est identique avant/après.**
À fourchette (Q1/Q3) et prix donnés, le `verdict` retourné par
`interpret_price_positioning` (et propagé dans le pilier) est strictement le
même qu'avant l'ajout du wording : pour un même jeu de comparables et un même
`listing_price_m2`, le champ `verdict` du pilier vaut la valeur attendue
(« Sous‑positionné » / « Plutôt aligné » / « Légèrement sur‑positionné » /
« Fortement sur‑positionné ») indépendamment de la présence du wording. Le
wording n'altère que `explanation`.

**AC4 — Le score prix est inchangé.**
Pour un même bien et un même pool de comparables, `n_comparables`, `points`
(part prix du score, /40) et `confidence` du pilier sont identiques avec et
sans le wording (le wording ne touche ni `compute_confidence` ni le scoring).
Testable en comparant le pilier sur un cas à scope métropole : `points` est
fonction du seul `verdict` (via `scoring.py`), qui est inchangé (AC3).

**AC-CONTRAT — Contrat `/analyze` figé, prouvé hors response_model.**
(a) Via le chemin endpoint `POST /analyze` (TestClient) : les clés du corps de
réponse sont exactement `{global_score, verdict, confidence, pillars, actions,
local_context}` (et pas davantage), et chaque pilier ne porte que les clés
listées en §3.4.
(b) Via la fonction sous-jacente `compute_price_market_pillar` appelée
directement (hors Pydantic) : l'ensemble des clés du dict retourné est
exactement `{verdict, explanation, confidence, scope, scope_name, dpe_band,
n_comparables, refinable}` — aucune clé nouvelle (ex. pas de
`scope_is_fallback`). Cet AC est falsifiable : il vire au rouge si le
développeur ajoute un champ au pilier.

**AC5 — Le nouveau seuil `MIN_COMPARABLES = 5` est appliqué dans la cascade
(valeurs de bord).**
- (a) Un bien d'agglo dont la commune a exactement **4** comparables (entre
  l'ancien seuil 3 et le nouveau 5) dans la fenêtre surface, et dont la
  métropole a ≥ 5 comparables : le scope retenu n'est PLUS `"ville"` mais
  `"metropole"`, et le wording d'avertissement (AC1) se déclenche.
- (b) Un bien dont la commune a exactement **5** comparables : le scope retenu
  EST `"ville"` (borne `>= MIN_COMPARABLES` incluse) et le wording NE se
  déclenche PAS (AC2).
- (c) Un bien **hors** `_METRO_CITIES` dont la commune a exactement **4**
  comparables (pas de candidat métropole) : `compute_market_stats` retourne
  `None` et le pilier vaut `verdict == "Indéterminé"` (garde-fou final
  `len < MIN_COMPARABLES`).
- (d) `MIN_COMPARABLES == 5` et `MIN_REFINED_COMPARABLES == 10` (assertion
  statique sur les constantes, pour figer la doctrine et l'invariant
  `MIN_COMPARABLES < MIN_REFINED_COMPARABLES`).

---

## 5. Test de cascade dédié (exigence GATE 1 Q6)

Aucun test ne couvre aujourd'hui la cascade `market_stats` (vérifié :
`grep` de `compute_market_stats` / `MIN_COMPARABLES` / `_scope_context` dans
`backend/tests/` → aucun résultat). C'est le garde-fou demandé en GATE 1.

**Fichier attendu :** `backend/tests/test_issue_87_scope_warning.py`.

**Contraintes de mise en place :**
- Le schéma DB doit être créé avant les appels directs au pipeline ; il l'est
  déjà via la fixture autouse session-scope `conftest.py::_init_db_schema`
  (leçon photo-evidence). Insérer les comparables de test via le modèle
  `Comparable` dans la base jetable (`SessionLocal`), avec un `property_type`,
  une `surface_m2` dans la fenêtre ±20 % du bien testé, un `price_m2` calculé,
  et une `city` canonique. Filtrer les assertions de comptage sur des données
  isolées par test (ne jamais s'appuyer sur un `count()` absolu, leçon 9.7) :
  utiliser une commune/surface dédiée par scénario, ou nettoyer la table en
  début de test.
- Choisir des `price_m2` qui placent le bien dans un verdict déterminé et
  STABLE pour AC3 (ex. un prix dans la fourchette Q1–Q3 → « Plutôt aligné »),
  afin que l'oracle de verdict soit robuste au pool injecté.

**Scénarios à couvrir (mapping AC) :**
1. Commune d'agglo creuse (4 comparables ville) + métropole fournie (≥ 5) →
   `scope == "metropole"`, wording présent (AC1, AC5a).
2. Commune d'agglo fournie (≥ 5 comparables ville) → `scope == "ville"`, pas de
   wording (AC2, AC5b borne incluse à 5).
3. Bien messin avec quartier/secteur peuplé → `scope` ∈ {quartier, secteur},
   pas de wording (AC2).
4. Verdict identique avec/sans wording sur un même pool et prix (AC3) ; score
   prix `points` et `confidence` inchangés (AC4).
5. Bien hors `_METRO_CITIES` avec 4 comparables ville → `Indéterminé` (AC5c).
6. Assertions statiques `MIN_COMPARABLES == 5`, `MIN_REFINED_COMPARABLES == 10`,
   `MIN_COMPARABLES < MIN_REFINED_COMPARABLES` (AC5d).
7. Contrat : clés du pilier via `compute_price_market_pillar` direct ET clés du
   corps `/analyze` via TestClient (AC-CONTRAT a et b). Pour le chemin endpoint,
   `analyze_semantic` est mocké pour renvoyer un `listing` déterministe (city
   d'agglo creuse, surface, prix) sans appel LLM réel.

---

## 6. Conformité (anti-patterns applicables)

- **Pas d'estimation de prix** (CLAUDE §1, anti-pattern §11.1) : on n'invente
  aucun prix « corrigé de l'effet-commune ». Le wording informe, ne recalcule
  rien.
- **Pas de DVF / notaires** (§11.4) : aucune densification de données.
- **Pas de redistribution d'annonces brutes** : on ne manipule que des agrégats
  statistiques internes.
- **Pas de secret en clair** : aucun secret introduit.
- **Contrat `/analyze` stable** : invariant central de ce fix, prouvé par
  AC-CONTRAT (clés figées, testées hors response_model car `pillars` est typé
  `list`, leçon 9.10). Aucune MAJ `frontend/lib/api.ts`.
- **Bornes testées aux valeurs exactes** (leçon 9.7) : AC5 teste 4 (exclu) et 5
  (inclus) sur `MIN_COMPARABLES`, et l'égalité `>= MIN_COMPARABLES`.
- **Pas de faux-vert tautologique** (leçon 9.10) : le wording et le contrat sont
  asserés sur les fonctions productrices (`compute_market_stats`,
  `compute_price_market_pillar`, `interpret_price_positioning`), pas seulement
  sur le filtrage Pydantic.
- **Conventions CLAUDE §12** : Python 3.12, logger nommé `market_stats`, pas de
  commentaire « what », pas d'emoji.
- **Évals (point de vigilance CI, non couvert par pytest)** : tout changement de
  wording du pilier prix peut faire bouger des assertions de la suite payante
  `evals/` (déclenchée par `evals.yml` sur PR touchant `market_stats`). Cette
  suite (vrais appels LLM, ~0,01 €/run) doit passer AVANT merge. C'est une
  exigence d'orchestration/CI, pas un test `tests/`. Vigilance leçon
  fix-issue-80 : vérifier que le contenu poussé inclut bien le passage evals si
  une assertion d'eval référence le texte du pilier prix.

---

## 7. Risques résiduels documentés

- **Chiffrage couverture non mesurable depuis le repo** : la part exacte de
  biens basculant ville→métropole (wording) ou ville→« Indéterminé » suite au
  passage `MIN_COMPARABLES` 3→5 n'est pas quantifiable sans la base prod. Valeur
  prudente (+2) retenue ; à réviser à la baisse si une mesure prod montre un
  assèchement du pilier hors Metz.
- **Détection « hors commune » liée à la topologie de la cascade** : la règle
  `scope == "metropole"` couvre tous les cas actuels (quartier/secteur/ville
  restent dans la commune du bien). Si un futur niveau « agglo voisine non
  rattachée à la commune » était ajouté à la cascade, la règle de déclenchement
  du wording devrait être réauditée (documenté pour éviter un wording muet sur
  un futur scope élargi).

SPEC prête pour GATE 2 (approbation humaine).

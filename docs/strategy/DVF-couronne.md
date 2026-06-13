# DVF-couronne — Instruction stratégique de l'assouplissement encadré DVF (GATE 1, Q1b)

> **Nature de ce document.** Modèle que le porteur possède et édite, pas une opinion ni
> une décision. Chaque chiffre porte `[source: …]` (donnée publique vérifiée) ou
> `[HYPOTHÈSE — à valider]`. Les formules de sizing sont posées en clair : change une
> entrée, le résultat suit. Aucun chiffre nu.
>
> **Mandat.** Le porteur a tranché en GATE 1 (`docs/specs/comparables-coverage-ANALYSE.md`
> §8.1) : ASSOUPLISSEMENT ENCADRÉ de l'interdit DVF — DVF autorisé en RÉFÉRENCE AGRÉGÉE
> communale uniquement (jamais estimation du bien, jamais redistribution de lignes brutes).
> Ma mission : instruire ce choix AVANT tout code, sur les 6 questions du brief.
>
> **Périmètre.** Metz / Moselle (dépt 57). Communes cibles : Marly, Saint-Julien-lès-Metz,
> Scy-Chazelles, Plappeville, Le Ban-Saint-Martin, Montigny-lès-Metz, Longeville-lès-Metz,
> Augny, Lessy. Segment d'intérêt prioritaire : MAISONS. App gratuite, trafic quasi nul,
> coût marginal ≈ 0,001 €/analyse, MVP < 1 €/mois [source: CONTEXT.md §3.2].
>
> **Dernière mise à jour du modèle** : 2026-06-13.

---

## 0. RÉSULTAT DOMINANT (à lire avant tout le reste)

**DVF ne couvre PAS la Moselle. Le département 57 est exclu de la base DVF / Demandes de
Valeurs Foncières en open data.** [source: data.gouv.fr / app.dvf.etalab.gouv.fr, confirmé
par deux recherches indépendantes — voir §8 Sources]

Raison : la Moselle (57), comme le Bas-Rhin (67) et le Haut-Rhin (68), relève du **droit
local d'Alsace-Moselle**. Les mutations immobilières y sont enregistrées au **Livre Foncier**
(régime hérité du droit local), et non au fichier de la DGFiP qui alimente DVF. La DGFiP
**ne dispose donc pas** des mutations de ces départements, et les données du Livre Foncier
**ne sont pas ouvertes** aujourd'hui. [source: data.gouv.fr, sogefi-sig.com, FAQ DVF Etalab —
voir §8]

**Conséquence directe et structurante pour ce mandat :**

| Question d'origine | Réponse |
|---|---|
| Combien de transactions DVF/an sur la couronne messine ? | **ZÉRO** ligne DVF exploitable. Le gisement DVF sur la couronne est nul, par exclusion légale du territoire — pas par étroitesse de marché. [source: exclusion Alsace-Moselle] |
| DVF densifie-t-il la couronne au point d'atteindre MIN_COMPARABLES=5 / MIN_REFINED=10 ? | **Non, par construction.** Il n'y a aucune donnée DVF à ingérer pour le 57. |
| L'assouplissement encadré GATE 1 est-il instruisable tel quel ? | **Non.** La prémisse de la GATE 1 (« DVF = transactions réelles communales gratuites ») **ne tient pas sur le périmètre du projet.** Le porteur a tranché Q1b sur une hypothèse factuellement fausse pour la Moselle. |

L'analyse `comparables-coverage-ANALYSE.md` (§4) a raisonné sur DVF comme s'il couvrait la
couronne (« gratuit, légal, donne les prix de transaction réels commune par commune »). Cette
prémisse est **inexacte pour le 57**. L'analyste n'avait pas vérifié la couverture
géographique réelle de DVF — c'est précisément le rôle de cette instruction stratégique
(« sizing du gisement réel AVANT tout code », §8.1 de l'analyse).

**Ce document instruit donc les 6 questions sous cet éclairage**, et reformule la décision :
la vraie question n'est plus « DVF oui/non », c'est « **existe-t-il une source de
transactions réelles exploitable sur la Moselle, et à quel prix de doctrine / d'argent ?** »
(§7 reformule l'arbitrage). Tout ce qui suit garde les formules de sizing **génériques**
pour rester utile si le porteur explore une source de transactions alternative (Livre
Foncier, PERVAL notaires, partenariat agences).

> ATTENTION DE FRAÎCHEUR DE CETTE INFO. L'exclusion Alsace-Moselle est stable depuis
> l'ouverture de DVF (2019). Une **ouverture future** du Livre Foncier en open data est
> possible mais non annoncée à ma connaissance [date de connaissance : 2026-06]. Ligne « à
> vérifier » §10 : reconfirmer l'absence de jeu DVF/Livre Foncier 57 sur data.gouv.fr au
> moment d'un éventuel chantier.

---

## 1. Sizing — gisement de transactions sur la couronne (formule générique, entrée DVF = 0)

Le sizing DVF demandé est **vide** (§0). Mais le porteur a besoin de savoir **combien de
transactions réelles existent** sur ces communes pour juger si une source ALTERNATIVE
vaudrait l'effort. Je pose donc le modèle de sizing **du marché de la transaction**, que
toute source (Livre Foncier ouvert un jour, PERVAL, agences) viendrait remplir.

### 1.1 Formule de sizing (éditable)

```
mutations_maisons_par_an(commune)
  = parc_maisons(commune)  ×  taux_rotation_annuel

mutations_maisons_cumulables(commune)
  = mutations_maisons_par_an(commune)  ×  fenetre_annees  ×  part_dans_fenetre_surface
```

- `parc_maisons` : nombre de maisons (résidences principales + secondaires) de la commune
  [source visée : INSEE, base Logement — à extraire commune par commune, §10].
- `taux_rotation_annuel` : part du parc qui mute (se vend) chaque année. Ordre de grandeur
  national du résidentiel : 3-4 %/an [HYPOTHÈSE — à valider sur le 57]. Prudent 2,5 % /
  base 3,5 % / ambitieux 4,5 %.
- `fenetre_annees` : profondeur de données conservée. DVF expose 5 ans glissants [source :
  data.gouv.fr] ; pour une source alternative, à caler.
- `part_dans_fenetre_surface` : fraction des mutations qui tombe dans la fenêtre surface
  ±20 % d'un bien donné. Pour un bien « médian » d'une commune, ordre de grandeur 25-40 %
  des maisons de la commune [HYPOTHÈSE — à valider]. C'est le facteur qui détermine si on
  atteint MIN_COMPARABLES par requête.

### 1.2 Entrées de population (input INSEE, ordre de grandeur)

Population légale (proxy de la taille de commune, PAS le parc de maisons) :

| Commune | Population (≈2023) | Source |
|---|---|---|
| Montigny-lès-Metz | ~21 700 | [source: INSEE / web] |
| Marly | ~10 300 | [source: INSEE / web] |
| Saint-Julien-lès-Metz | ~3 550 | [source: INSEE / web] |
| Scy-Chazelles | ~2 750 | [source: INSEE / web] |
| Plappeville | ~2 000 | [HYPOTHÈSE — à valider INSEE] |
| Le Ban-Saint-Martin | ~4 000 | [HYPOTHÈSE — à valider INSEE] |
| Longeville-lès-Metz | ~3 800 | [HYPOTHÈSE — à valider INSEE] |
| Augny | ~2 300 | [HYPOTHÈSE — à valider INSEE] |
| Lessy | ~1 200 | [HYPOTHÈSE — à valider INSEE] |

> Le parc de MAISONS par commune n'a pas pu être extrait dans cette session (les snippets
> INSEE Logement ne sont pas remontés). Ligne « à vérifier » §10. **Ne pas fabriquer un
> chiffre de parc crédible** : sans lui, le sizing reste paramétrique.

### 1.3 Exemple chiffré (illustratif, à recalculer une fois le parc connu)

Pour une petite commune type (Scy-Chazelles, Plappeville, Lessy) — hypothèse de travail
parc_maisons ≈ 600-900 [HYPOTHÈSE — à valider] :

```
mutations_maisons_par_an  ≈ 700 × 3,5 %  ≈ 25/an              [base]
sur fenêtre 5 ans          ≈ 25 × 5      ≈ 125 mutations
dans fenêtre surface ±20 % ≈ 125 × 30 %  ≈ 37 comparables potentiels par requête médiane
```

Lecture : **même AVEC une source de transactions, une petite commune ne fournit qu'un pool
serré.** 37 comparables sur 5 ans pour un bien médian dépasse MIN_REFINED=10, mais pour un
bien atypique (issue #87 : maison 257 m²) la fenêtre surface vide le pool — le mur reste.
Pour les grosses communes (Montigny, Marly), le pool serait confortable ; pour les petites,
marginal. **Cette structure (gros OK / petits creux) est indépendante de la source.**

> Tant que `parc_maisons` réel n'est pas saisi, ce calcul est une **démonstration de
> formule**, pas un résultat. Voir §10.

---

## 2. Recomparabilité prix/m² — transactions vs annonces (vaut pour toute source de transaction)

La question vaut pour DVF ET pour toute alternative (Livre Foncier, PERVAL). DVF étant
absent, je traite l'écart **structurel** entre un prix/m² de transaction et un prix/m²
d'annonce, car il conditionne la conception quelle que soit la source.

### 2.1 Sources d'écart modélisées

| Écart | Sens | Ordre de grandeur | Étiquette |
|---|---|---|---|
| Surface cadastrale/bâtie vs surface Carrez habitable | prix/m² transaction **gonflé** (dénominateur plus petit si Carrez < bâtie) ou **dilué** selon le cas | 5-15 % de divergence sur la surface | [HYPOTHÈSE — à valider] |
| Prix demandé (annonce) vs prix acté (transaction) | annonce **au-dessus** de la transaction | 3-8 % de marge de négociation moyenne | [HYPOTHÈSE — à valider] |
| Absence DPE/descriptif côté transaction | impossible de filtrer par bande DPE / confort | qualitatif | [source: analyse §4.3] |
| Multi-lots / dépendances (transaction) | prix/m² **faussé** si vente groupée | à filtrer au nettoyage | [HYPOTHÈSE — à valider] |

Le solde net (gonflement Carrez × décote négociation) peut **partiellement se compenser**,
mais dans un sens **non déterministe par bien** : on ne peut pas appliquer un facteur de
conversion fiable ligne à ligne. C'est l'argument central contre le mélange.

### 2.2 Options de conception (sans coder)

| Option | Description | Implication |
|---|---|---|
| **A — Pools séparés** | Quartiles « annonces » et quartiles « transactions » calculés indépendamment, jamais fusionnés dans un même tableau de comparables. | Méthodologiquement propre. Double l'affichage (deux distributions). Charge cognitive accrue. Exige un volume suffisant DANS CHAQUE pool. |
| **B — Transactions en CALAGE/contrôle** | Le pool reste les annonces (positionnement « observable »). Les transactions servent de **repère de contrôle** affiché à part (« le marché demandé est à X ; les ventes actées récentes étaient à Y »), jamais mélangé aux quartiles scorés. | Préserve le positionnement « ce que j'observe ». N'altère pas le score 40/30/30. Pédagogiquement fort (montre l'écart demandé/acté). Reco si une source de transaction existe un jour. |
| **C — Mélange dans un pool unique** | Annonces + transactions dans les mêmes quartiles. | **À écarter.** Mélange deux natures de prix sans facteur de conversion fiable (§2.1) → fausse précision, exactement l'anti-pattern produit (CONTEXT §1.4, §11.2). |

**Reco de conception (conditionnelle à l'existence d'une source) : Option B (calage), à
défaut A (pools séparés). Jamais C.** Cette reco est valable quelle que soit la source de
transaction ; elle protège le positionnement même si la source devient disponible.

---

## 3. Biais corrigé vs biais introduit (solde)

Modèle du solde, pour décider si une source de transaction (si elle existait) vaudrait son
biais propre.

```
gain_fiabilite = correction_biais_demande_vs_acte  +  correction_biais_de_survie
perte_fiabilite = biais_de_fraicheur (délai de publication)  +  perte_de_comparabilite_m2 (§2)
solde = gain_fiabilite − perte_fiabilite
```

| Terme | Effet | Ordre de grandeur | Étiquette |
|---|---|---|---|
| Correction biais demandé vs acté | + (la transaction dit le vrai prix de vente) | 3-8 % | [HYPOTHÈSE — à valider] |
| Correction biais de survie (les sur-cotés stagnent et polluent le stock d'annonces) | + (la transaction ne garde que ce qui s'est vendu) | qualitatif, potentiellement significatif | [source: analyse §2.1] |
| Biais de fraîcheur (délai de publication) | − | DVF ≈ 6 mois ; **PERVAL ≈ 6 semaines** [source: adnov.fr/journaldelagence] | [source] |
| Perte de comparabilité m² (§2) | − | non déterministe par bien | [HYPOTHÈSE] |

**Lecture du solde :** sur le principe, le gain « transaction » l'emporte sur la perte de
fraîcheur pour un usage en **calage** (Option B) — on ne cherche pas le prix du jour, on
cherche un repère acté fiable. La fraîcheur de 6 mois est acceptable pour un repère de
contrôle, pas pour un prix scoré au jour le jour. **Mais ce solde est purement théorique
pour la Moselle : il n'y a aucune source de transaction ouverte à mettre dans la balance.**
Pour une source comme PERVAL (notaires, 6 semaines de délai), le biais de fraîcheur serait
quasi nul — mais PERVAL est payant (§7).

---

## 4. Repositionnement produit et marketing

La question « faut-il réécrire le hero si DVF entre en référence ? » devient **sans objet
pour DVF** (DVF n'entrera pas, §0). Je traite le risque générique « source de transaction →
glissement vers l'estimateur », utile si une alternative est un jour adoptée.

### 4.1 Le risque de glissement (réel quelle que soit la source)

Toute source de transactions réelles rapproche le produit du carburant des estimateurs
(MeilleursAgents, SeLoger estimation, Patrim). Le risque n'est pas la donnée, c'est la
**promesse** : si l'UI affiche « les ventes récentes étaient à X €/m² », l'utilisateur
entend « mon bien vaut X » même sans qu'on l'ait dit. C'est le glissement vers le peloton
des estimateurs que l'interdit visait (analyse §4.1).

### 4.2 Formulations de positionnement compatibles « pas d'estimation »

Trois pistes, si une source de transaction était adoptée en Option B :

1. *« On vous montre l'écart entre ce qui est demandé et ce qui s'est vendu — à vous d'en
   tirer vos questions. »* (registre : révéler l'asymétrie, pas trancher le prix.)
2. *« Repère de cohérence, pas estimation : on situe l'annonce dans le marché observé, on ne
   chiffre pas votre bien. »* (registre : continuité avec le hero actuel.)
3. *« Les annonces disent un prix demandé. Les actes disent un prix payé. On vous donne les
   deux, sans conclure à votre place. »* (registre : pédagogie de l'écart.)

### 4.3 Hero actuel

Le hero en prod (« Avant d'acheter, faites lire l'annonce par un œil neuf », CONTEXT §2.2)
**n'a PAS besoin d'être réécrit** dans l'immédiat, puisque DVF n'entre pas. S'il fallait un
jour intégrer une source de transaction, **ne pas toucher le hero principal** ; ajouter
plutôt une mention de second rang dans la carte prix (Option B). Garder « observable » dans
le hero : c'est le contre-positionnement (analyse §4.1).

---

## 5. Garde-fous anti-dérive (invariants testables pour le futur spec-writer)

Ces invariants valent pour **toute** source de transaction (DVF, Livre Foncier, PERVAL,
agences) si elle entre un jour. Formulés pour être repris tels quels en spec et en tests.

| # | Invariant | Test (forme attendue) |
|---|---|---|
| G1 | **Aucun prix prédit du bien.** Aucune réponse `/analyze` ne contient un champ ni une phrase chiffrant la valeur du bien analysé. | Assert : la réponse ne contient pas de motif « ce bien vaut / estimé à / valeur estimée X € ». Déjà l'esprit du produit (CONTEXT §11.1). |
| G2 | **Agrégats seulement.** Une source de transaction ne sort que médiane/Q1/Q3/dispersion/effectif, jamais une ligne de mutation individuelle. | Assert : la couche d'exposition ne renvoie aucune ligne brute (prix unitaire + localisation parcellaire). |
| G3 | **Pas de redistribution de lignes.** Aucune mutation individuelle (prix, date, parcelle, adresse) n'est exposée par API ni re-publiée. | Assert : `/analyze` et endpoints publics ne renvoient ni `parcelle`, ni `adresse_mutation`, ni `prix_mutation` unitaire. Aligné CONTEXT §11.3. |
| G4 | **Seuil d'anonymisation par agrégat.** Un agrégat (médiane communale, etc.) n'est exposé que si l'effectif sous-jacent ≥ k. Proposition k=5 (cohérent avec MIN_COMPARABLES). Empêche de ré-identifier une vente unique dans une petite commune. | Assert : aucun agrégat affiché si `n < k`. Verrouille le risque « DVF/Livre Foncier nominatif » (analyse §4.1). |
| G5 | **Pas de mélange de natures de prix.** Transactions et annonces ne sont jamais dans le même pool de quartiles (Option C interdite, §2.2). | Assert : la fonction de quartiles reçoit un pool homogène (un seul `price_nature`). |
| G6 | **Calage non-scoré.** Si une source de transaction sert de repère (Option B), elle n'altère pas le score 40/30/30. | Assert : `global_score` inchangé que le repère transaction soit présent ou absent (comme l'ancrage local, CONTEXT §11bis). |
| G7 | **Traçabilité de source.** Toute ligne stockée porte sa nature (`annonce` / `transaction`) et sa source, pour audit et pour G5. | Assert : schéma impose `price_nature` non-null. |

Ces 7 invariants sont la condition non négociable d'un éventuel chantier. Ils transforment
« assouplissement encadré » en garde-fous mécaniques, pas en intention.

---

## 6. Coût / effort / SLO (sous l'hypothèse contrefactuelle d'une source disponible)

DVF étant absent (§0), il n'y a **rien à ingérer** : coût et effort DVF = **0 €, 0 j** (le
chantier n'existe pas). Pour border la décision si une source alternative était retenue :

| Source hypothétique | Coût infra | Effort build (ordre de grandeur) | Impact SQLite | Fraîcheur | < 1 €/mois ? |
|---|---|---|---|---|---|
| **DVF (si 57 ouvrait un jour)** | nul (open data, download CSV) | 2-4 j (download, nettoyage cadastral, agrégation commune, recomparabilité m²) | +1 table agrégats communaux ; volume faible (agrégats, pas lignes) ; pas de pression sur SQLite | semestriel (~6 mois) | oui |
| **Livre Foncier 57** | inconnu (non ouvert) | non chiffrable | — | — | bloqué (pas open data) |
| **PERVAL (notaires)** | **payant** (abonnement pro) | moyen (intégration API/export) | idem agrégats | ~6 semaines [source] | **non — nouveau vendor payant, anti-pattern coût** |
| **Partenariat agences (mandats)** | nul en infra | non technique (commercial) | idem agrégats | variable | oui en infra, mais ≠ transactions (mandats = prix demandé, ne corrige pas le biais) |

Ingestion d'agrégats communaux = quelques lignes par commune rafraîchies en batch
(semestriel suffirait pour DVF, hebdo n'apporte rien sur du transactionnel). **Pas de
pression sur SQLite** (agrégats = volume négligeable vs les ~17,7k annonces actuelles).
**SLO de dispo inchangé** : la donnée est pré-agrégée et lue, pas calculée à chaud ; pas de
nouvel appel réseau dans le chemin `/analyze`. On reste **< 1 €/mois** pour toute source
gratuite ; PERVAL ferait basculer (abonnement) et est donc écarté au titre de la sécurité
financière (CONTEXT §3.2-3.3).

---

## 7. REFORMULATION DE L'ARBITRAGE (ce que le porteur doit re-trancher)

La GATE 1 a tranché « DVF en référence agrégée » sur une prémisse fausse pour la Moselle.
Le porteur doit re-trancher entre :

| Voie | Description | Coût doctrine | Coût argent | Gain couronne |
|---|---|---|---|---|
| **V0 — Renoncer à la transaction** | Rester sur les annonces (positionnement actuel intact), accepter le plafond de fiabilité « annonce ≠ transaction » non corrigé. Concentrer l'effort sur les leviers gratuits (élargir bien'ici à la couronne, accumulation longitudinale — analyse §3.1/§3.4). | nul (statu quo) | nul | densification annonces, **pas** de correction du biais transaction |
| **V1 — Attendre l'ouverture du Livre Foncier 57** | Surveiller data.gouv.fr ; câbler DVF-like le jour où le 57 ouvre. | nul tant qu'inactif | nul | nul aujourd'hui, conditionnel |
| **V2 — PERVAL (notaires)** | Source de transactions couvrant l'Alsace-Moselle, fraîche (~6 sem). | révision doctrine (anti-pattern « bases notariales », CONTEXT §1.2/§11.4) | **payant** → casse < 1 €/mois | fort et fiable, MAIS coût récurrent |
| **V3 — Partenariat agences (mandats)** | Données fraîches et structurées, mais = prix DEMANDÉ, pas acté. | révision marketing modérée | nul en infra | densifie la couronne, **ne corrige pas** le biais transaction |

**Le « assouplissement encadré DVF » voté en GATE 1 n'est réalisable par AUCUNE voie
gratuite couvrant la Moselle.** La seule source de transactions couvrant le 57 est payante
(PERVAL) ou fermée (Livre Foncier). C'est l'arbitrage réel à re-soumettre.

---

## 8. RECOMMANDATION GO / NO-GO (conditionnelle)

### NO-GO ferme — chantier d'ingestion DVF
**NO-GO. Il n'y a rien à ingérer : DVF exclut la Moselle (§0).** Aucune ligne de code
d'ingestion DVF ne se justifie pour le périmètre Metz/Moselle. Démarrer un chantier DVF
serait un effort à fond perdu. C'est un NO-GO factuel, pas d'opinion.

### Conditions sous lesquelles un chantier « transaction » se justifierait
Un chantier d'intégration d'une source de transactions se justifie **si et seulement si** :
1. une source couvrant le 57 devient disponible **gratuitement** (ouverture Livre Foncier —
   à surveiller, §10), OU le porteur accepte explicitement le coût récurrent de PERVAL en
   dérogeant à la cible < 1 €/mois (décision financière + doctrine, hors atelier) ; ET
2. le sizing §1 (une fois `parc_maisons` réel saisi) montre qu'au moins les **grosses
   communes** (Montigny, Marly) atteindraient MIN_REFINED=10 par requête médiane ; ET
3. les invariants G1-G7 (§5) sont inscrits en spec AVANT tout code ; ET
4. la conception retient l'Option B (calage) ou A (pools séparés), jamais C (§2.2).

### Conditions sous lesquelles il ne se justifie PAS
- Tant qu'aucune source gratuite ne couvre le 57 ET que le porteur tient la cible
  < 1 €/mois → **NO-GO** (PERVAL exclu par le coût).
- Si le sizing montre que même les grosses communes restent creuses → le jeu n'en vaut pas
  la chandelle (l'effort de nettoyage cadastral ne sert que quelques requêtes).

### Recommandation de séquencement (sans rien décider à la place du porteur)
1. **Acter le NO-GO DVF** et corriger l'analyse §4/§8 qui présume DVF disponible.
2. **Prioriser la voie V0** (gratuite, déjà votée en §8.2 de l'analyse) : élargir bien'ici à
   la couronne + accumulation. C'est le maximum atteignable à coût nul, indépendant de DVF.
3. **Mettre V1 en veille** (surveiller l'ouverture du Livre Foncier, coût nul).
4. **Re-soumettre V2/V3 au porteur** comme décisions de doctrine + budget (hors atelier),
   en sachant que seul PERVAL corrige réellement le biais transaction mais à coût récurrent.

---

## 9. REGISTRE D'HYPOTHÈSES

| # | Hypothèse | Valeur retenue | Impact si fausse | Comment valider |
|---|---|---|---|---|
| H1 | DVF exclut la Moselle (57) — droit local Alsace-Moselle / Livre Foncier | VRAI [source vérifiée ×2] | Tout le document s'inverse | Reconfirmer sur data.gouv.fr au moment d'un chantier (§10) |
| H2 | Le Livre Foncier 57 n'est pas en open data aujourd'hui | VRAI [source] | Ouvrirait la voie V1 gratuite | Veille data.gouv.fr |
| H3 | PERVAL couvre l'Alsace-Moselle et est payant | VRAI [source: adnov/journaldelagence] | Change l'arbitrage V2 | Devis PERVAL/ADNOV |
| H4 | Taux de rotation annuel du parc ≈ 3,5 % (base) | [HYPOTHÈSE] | Sur/sous-estime le sizing §1 | Statistiques notariales locales / INSEE |
| H5 | Parc de maisons par commune (Scy ~700, etc.) | [HYPOTHÈSE] | Sizing §1 non chiffrable | INSEE base Logement, commune par commune |
| H6 | Part des mutations dans la fenêtre surface ±20 % ≈ 30 % | [HYPOTHÈSE] | Détermine l'atteinte de MIN_COMPARABLES | Distribution surfaces réelle (source transaction) |
| H7 | Marge négociation demandé→acté ≈ 3-8 % | [HYPOTHÈSE] | Calibrage du repère de calage (Option B) | Études notariales nationales/locales |
| H8 | Écart surface Carrez vs cadastrale ≈ 5-15 % | [HYPOTHÈSE] | Recomparabilité m² §2 | Échantillon croisé annonces/cadastre |
| H9 | Populations communales (≈2023) | [source: INSEE/web, ordres de grandeur] | Faible (proxy de taille seulement) | Pages INSEE par commune |

---

## 10. LISTE « À VÉRIFIER » (ordonnée par impact)

1. **[IMPACT MAXIMAL] Reconfirmer l'exclusion DVF/Livre Foncier du 57** au moment où un
   chantier transaction est envisagé (data.gouv.fr, FAQ Etalab). Toute la décision en
   dépend. Surveiller une éventuelle ouverture du Livre Foncier d'Alsace-Moselle. [H1, H2]
2. **[FORT] Parc de maisons par commune** (INSEE base Logement, 9 communes cibles). Sans
   lui, le sizing §1 reste paramétrique et le GO/NO-GO conditionnel ne peut pas être tranché
   quantitativement. [H5]
3. **[FORT] Décision de doctrine + budget sur PERVAL** : le porteur accepte-t-il un vendor
   payant (dérogation < 1 €/mois) pour une source de transaction couvrant le 57 ? C'est la
   seule voie ouverte aujourd'hui qui corrige le biais transaction. [H3, §7 V2]
4. **[MOYEN] Taux de rotation et part en fenêtre surface** sur le marché local 57 (stats
   notariales). Affine le sizing §1. [H4, H6]
5. **[MOYEN] Corriger l'analyse `comparables-coverage-ANALYSE.md` §4/§8** qui présume DVF
   disponible sur la couronne — la GATE 1 Q1b a été tranchée sur une prémisse fausse.
6. **[FAIBLE] Marge négociation et écart Carrez/cadastrale** locaux : ne servent qu'au
   calibrage fin d'un éventuel repère de calage (Option B). [H7, H8]
7. **[FAIBLE] Populations INSEE manquantes** (Plappeville, Ban-Saint-Martin, Longeville,
   Augny, Lessy) : confort de complétude, faible impact (proxy de taille). [H9]

---

## 11. Sources

- [Demandes de valeurs foncières — data.gouv.fr](https://www.data.gouv.fr/datasets/demandes-de-valeurs-foncieres)
- [Base « Demande de valeurs foncières » — cadastre.data.gouv.fr](https://cadastre.data.gouv.fr/dvf)
- [Donnée DVF — exclusion Alsace-Moselle — SOGEFI](https://www.sogefi-sig.com/donnee-dvf-demande-de-valeurs-foncieres/)
- [FAQ DVF Etalab](https://app.dvf.etalab.gouv.fr/faq.html) (page renvoyant 403 à la récupération automatique ; couverture confirmée par les sources ci-dessus)
- [PERVAL — base notariale, couverture Alsace-Moselle, ~6 semaines — ADNOV](https://www.adnov.fr/solutions/perval-base-de-donnees-marche-immobilier/)
- [PERVAL — Journal de l'Agence](https://www.journaldelagence.com/1408031-perval-loutil-incontournable-pour-des-estimations-immobilieres-fiables-et-incontestables)
- [Populations légales — Montigny-lès-Metz (INSEE)](https://www.insee.fr/fr/statistiques/7725600?geo=COM-57480)
- [Dossier complet — Saint-Julien-lès-Metz (INSEE)](https://www.insee.fr/fr/statistiques/2011101?geo=COM-57616)

> Fin du modèle. Le porteur valide à une gate dédiée. Aucune décision n'est prise ici :
> ce document établit que la décision GATE 1 (assouplissement DVF) repose sur une prémisse
> factuellement fausse pour la Moselle, et reformule l'arbitrage réel (§7) sous garde-fous
> testables (§5).

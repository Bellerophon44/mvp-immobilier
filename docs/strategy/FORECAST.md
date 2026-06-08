# FORECAST — Cohérence (Metz / Moselle)

> **Nature de ce document.** Ceci est un **modèle que tu possèdes et édites**, pas une
> prédiction. Chaque chiffre porte une étiquette `[source: …]` (donnée publique vérifiée)
> ou `[HYPOTHÈSE — à valider]`. Les nombres nus sont interdits. Les formules sont posées
> en clair : change une entrée, le reste suit.
>
> **Rappel produit.** Cohérence = *analyseur de cohérence* d'annonces immobilières (PAS
> estimateur de prix), périmètre **Metz / Moselle**, registre « second avis local de
> confiance ». Coût marginal mesuré ≈ **0,001 €/analyse** (`gpt-4.1-mini`) [source: CONTEXT.md §3.2].
> App gratuite, sans analytics, à trafic quasi nul aujourd'hui [source: CONTEXT.md §3.1].
>
> **Horizon.** 6 et 12 mois. **Critère de succès retenu par le fondateur** : adoption (usage)
> + apprentissage/validation du problème d'asymétrie d'info — **PAS encore du revenu**.
>
> **Dernière mise à jour du modèle** : 2026-06-08.
> **Statut des données** : voir §9 (registre d'hypothèses) et §10 (à vérifier, ordonné par impact).

---

## 0. Comment lire / éditer ce modèle

- Les **entrées** (ce que tu peux changer) sont dans des tables marquées `ENTRÉE`.
- Les **formules** sont écrites en toutes lettres juste au-dessus du résultat.
- Trois scénarios partout : **Prudent** / **Base** / **Ambitieux**. Ce ne sont pas des
  probabilités, ce sont trois jeux d'hypothèses cohérents entre eux.
- Quand une donnée publique n'a pas pu être atteinte ou n'existe pas proprement, la ligne
  est marquée `[HYPOTHÈSE — à valider]` et reportée en §10.

---

## 1. Sizing du marché — TAM → SAM → SOM (Metz / Moselle)

### 1.1 Population (socle, sourcé)

| Périmètre | Population | Étiquette |
|---|---|---|
| Ville de Metz | ~123 000 hab. (estim. 2026 ~123 600 ; rec. 2023 +0,7 %/an) | [source: INSEE dossier commune Metz 57463 ; Gazette Moselle 2024] |
| Metz Métropole (EPCI, ~44 communes) | ~220 000 hab. | [source: INSEE comparateur EPCI Metz Métropole 200039865 ; arrondi presse] |
| Département Moselle (57) | ~1 051 000 hab. (rec. 2023) | [source: INSEE populations légales 1ᵉʳ janv. 2026 = recensement 2023, dep57.pdf] |

### 1.2 Volume annuel de transactions immobilières (le vrai TAM d'usage)

Le produit s'adresse à **un acheteur, sur une annonce, à un moment d'achat**. L'unité de
marché pertinente n'est donc pas « habitants » mais **transactions/an** (et, en amont,
**annonces actives** + **visites**).

**Données sourcées (Moselle) :**
- T2 2023 : **~3 500 transactions** sur le trimestre (point bas sur 5 ans)
  [source: Chambre des notaires Moselle, via France Bleu / Gazette Moselle 2023].
- Moyenne mars 2023 : **~4 000 transactions/trimestre**, pic T3 2022 à ~4 700
  [source: Chambre des notaires Moselle, via Affiches-Moniteur / France Bleu].

**Dérivation du volume annuel Moselle** (formule explicite) :
```
Transactions/an Moselle ≈ (transactions/trimestre moyen) × 4
```

| Scénario d'année | Trim. moyen retenu | Transactions/an Moselle | Étiquette |
|---|---|---|---|
| Année basse (type 2023, marché ralenti) | ~3 500 | **~14 000** | [dérivé de source notaires Moselle ; ×4] |
| Année normale (type 2022) | ~4 200 | **~16 800** | [dérivé de source notaires Moselle ; ×4] |
| Année haute (pic 2021-22) | ~4 700 | **~18 800** | [dérivé du pic T3 2022 ; ×4] |

> **Fourchette de travail Moselle : ~14 000 à ~19 000 transactions/an.** On retient
> **~16 000/an** comme valeur base [HYPOTHÈSE — milieu de fourchette dérivée].
>
> **Garde-fou de cohérence (cross-check national).** France ancien : ~935 000 trans.
> en 2023, ~750-780 000 en 2024 [source: Notaires de France, via Immomatin / Dalloz /
> Extencia]. Moselle = ~1,05 M hab. / ~68 M hab. France ≈ **1,5 %** de la population →
> 1,5 % × 800-935 000 ≈ **12 000-14 000**. Cohérent (légèrement sous notre dérivation
> notaires, l'écart vient du neuf + de la sur-représentation transfrontalière). On garde
> **14 000-19 000** comme fourchette, **16 000 base**.

**Part Metz Métropole dans la Moselle** (formule) :
```
Trans/an Metz Métropole ≈ Trans/an Moselle × (part métropole)
```
La part de population de Metz Métropole dans la Moselle = 220 000 / 1 051 000 ≈ **21 %**
[source: ratio des deux chiffres INSEE ci-dessus]. Le marché y est plus actif (urbain,
locatif, transfrontalier) → on prend une part **transactions** un peu supérieure à la part
**population**.

| | Part transactions retenue | Trans/an Metz Métropole (base 16 000) | Étiquette |
|---|---|---|---|
| Prudent | 21 % (= part pop.) | ~3 400 | [HYPOTHÈSE — part = poids démographique] |
| Base | 25 % | ~4 000 | [HYPOTHÈSE — léger sur-poids urbain] |
| Ambitieux | 28 % | ~4 500 | [HYPOTHÈSE — sur-poids marché actif] |

> **Note attention.** Une donnée presse « 192 maisons + 459 apparts vendus à Metz **2018-2022** »
> [source: Orpi Accueil 57] est **un échantillon d'agence, pas le marché** : ~130 ventes/an
> serait absurde pour une ville de 123 000 hab. **À ne PAS utiliser comme volume marché.**
> Reportée en §10 comme « à ne pas confondre ».

### 1.3 Du marché à la demande adressable : annonces, visites, acheteurs

Le produit est consommé surtout **avant l'achat**, par des **acheteurs en recherche**, sur
des **annonces actives** — un volume bien plus grand que les transactions abouties.

Chaînage (formules) :
```
Annonces actives à un instant T  ≈ Trans/an × (durée de vie moyenne d'une annonce en années)
Acheteurs actifs en recherche /an ≈ Trans/an × (nb d'acheteurs sérieux par bien vendu)
Visites /an                       ≈ Trans/an × (nb de visites pour vendre un bien)
```

| Coefficient | Prudent | Base | Ambitieux | Étiquette |
|---|---|---|---|---|
| Visites pour vendre un bien | 5 | 8 | 12 | [source: SeLoger / Guy-Hoquet / agences : « 8-12 », « 5-10 »] |
| Acheteurs sérieux par bien vendu (≈ visiteurs distincts) | 4 | 6 | 9 | [HYPOTHÈSE — visites < visiteurs car re-visites] |
| Durée de vie moyenne d'une annonce (mois) | 2 | 3 | 4 | [HYPOTHÈSE — ~90 j de délai de vente cité] |

**TAM d'usage « actes d'analyse potentiels / an » (Metz Métropole, base) :**
```
≈ Trans/an Metz Métropole × visites pour vendre
≈ 4 000 × 8 ≈ 32 000 « moments où un acheteur regarde sérieusement une annonce » /an
```
Fourchette Metz Métropole : **~17 000 (prud.) → ~32 000 (base) → ~54 000 (amb.)** moments/an
[dérivé des lignes ci-dessus].

**À l'échelle Moselle (base) :** 16 000 × 8 ≈ **~128 000 moments d'analyse potentiels/an**
[dérivé]. C'est le **plafond théorique d'usage** si chaque acheteur analysait chaque annonce
sérieusement considérée. Personne ne capte ça ; voir SOM.

### 1.4 TAM / SAM / SOM (synthèse)

| Niveau | Définition retenue | Valeur (base) | Étiquette |
|---|---|---|---|
| **TAM** (usage) | Moments d'analyse d'annonce/an, **Moselle** | ~100 000-130 000 | [dérivé §1.3] |
| **SAM** | Idem restreint à **Metz Métropole** (cœur de couverture data, ~17,7k comparables, quartiers peuplés) | ~17 000-54 000 ; base ~32 000 | [dérivé §1.3 ; couverture data source: CONTEXT.md §0] |
| **SOM 12 mois** | Part réellement capturée par un MVP gratuit, non monétisé, ~0 budget, sans SEO mûr | **prud. ~0,5 % → base ~2 % → amb. ~6 %** du SAM | [HYPOTHÈSE — voir funnel §2] |

**SOM 12 mois en actes d'analyse (Metz Métropole, base) :**
```
SOM = SAM × part captée = 32 000 × 2 % ≈ 640 analyses/an  (base)
```
Fourchette : **~85 (prud.) → ~640 (base) → ~3 200 (amb.)** analyses sur 12 mois.
> Ces chiffres SOM sont **petits**, et c'est attendu : MVP local, gratuit, sans acquisition
> financée, en phase d'apprentissage. **L'enjeu n'est pas le volume brut mais la pente
> d'adoption et la qualité du signal** (cf. §7). Le funnel §2 reconstruit ces ordres de
> grandeur par le haut (visiteurs → analyses) pour que tu puisses bouger chaque taux.

---

## 2. Funnel d'acquisition → usage (le cœur éditable)

### 2.1 Étapes et formules

```
Visiteurs uniques /mois
  → × taux_lancement_analyse        = Analyses lancées /mois
  → × (1 − taux_échec_technique)    = Analyses abouties (rapports affichés) /mois
  → × taux_export_ou_partage        = Rapports « emportés » (PDF/.md/copie) /mois
  → × taux_inscription*             = Inscrits /mois     (*nécessite une feature compte, cf. §6)
  → × taux_conversion_payant        = Payants /mois      (si monétisation activée, cf. §3)
```

> `taux_inscription` et `taux_conversion_payant` sont **à zéro aujourd'hui** : il n'y a ni
> compte ni paiement (auth inexistante [source: CONTEXT.md §9.6]). Ils n'ont de sens qu'une
> fois les features §6 livrées. On les modélise pour préparer la décision, pas pour prétendre
> qu'ils tournent déjà.

### 2.2 Taux retenus (ENTRÉE — modifie ici)

| Taux | Prudent | Base | Ambitieux | Étiquette |
|---|---|---|---|---|
| `taux_lancement_analyse` (visiteur → lance ≥1 analyse) | 15 % | 30 % | 45 % | [HYPOTHÈSE — intention forte, outil mono-tâche] |
| `taux_échec_technique` (URL grands portails non-fetchables, fallback LLM) | 25 % | 15 % | 8 % | [HYPOTHÈSE — anti-bot Leboncoin/SeLoger source: CONTEXT.md §4.3] |
| `taux_export_ou_partage` (.md / copie / futur PDF) | 10 % | 20 % | 35 % | [HYPOTHÈSE — export .md existe source: §9.2] |
| `taux_inscription` (si compte proposé) | 3 % | 8 % | 15 % | [HYPOTHÈSE — friction email, valeur à prouver] |
| `taux_conversion_payant` (inscrit → payant, B2C) | 1 % | 3 % | 6 % | [HYPOTHÈSE — freemium grand public typique] |

### 2.3 Trois scénarios de trafic (ENTRÉE — le vrai levier d'incertitude)

Le trafic est l'inconnue dominante (aucune analytics installée → **on ne sait pas** le
trafic réel actuel, cf. §10 item #1). On pose trois trajectoires de **visiteurs uniques/mois**.

| Visiteurs uniques/mois | Mois 0 (aujourd'hui) | Mois 6 | Mois 12 | Hypothèse de moteur |
|---|---|---|---|---|
| **Prudent** | ~30 | ~80 | ~150 | bouche-à-oreille seul, 0 budget |
| **Base** | ~50 | ~300 | ~700 | BàO + SEO local naissant + 1-2 partenariats |
| **Ambitieux** | ~80 | ~1 200 | ~3 000 | + presse/radio locale + paid ciblé + partenariats actifs |

> Mois 0 est lui-même `[HYPOTHÈSE — à valider]` : sans analytics on ignore le trafic réel.
> **Premier impératif de mesure** (§7) = instrumenter pour remplacer ces hypothèses par des
> faits dès le mois 1.

### 2.4 Résultats du funnel (analyses abouties /mois)

```
Analyses abouties/mois = Visiteurs × taux_lancement × (1 − taux_échec)
```

| | Mois 6 | Mois 12 | Cumul ~12 mois (ordre de grandeur) |
|---|---|---|---|
| **Prudent** | 80 × 15 % × 75 % ≈ **9** | 150 × 15 % × 75 % ≈ **17** | ~100-150 analyses |
| **Base** | 300 × 30 % × 85 % ≈ **76** | 700 × 30 % × 85 % ≈ **178** | ~900-1 200 analyses |
| **Ambitieux** | 1 200 × 45 % × 92 % ≈ **497** | 3 000 × 45 % × 92 % ≈ **1 242** | ~6 000-8 000 analyses |

**Inscrits/mois (si feature compte livrée, scénario Base)** :
```
≈ analyses abouties × taux_export × taux_inscription
≈ 178 × 20 % × 8 % ≈ 3 inscrits/mois à M12 (Base)
```
> Lecture honnête : **même en Base, l'inscription au goutte-à-goutte**. C'est cohérent avec
> un outil « second avis ponctuel » (on ne revient pas chaque semaine). **Conséquence
> stratégique forte** : la rétention récurrente B2C est *intrinsèquement faible* → cela
> pèse lourd dans l'arbitrage B2C vs B2B (§3).

### 2.5 Une ligne par scénario (résumé)

- **Prudent** — bouche-à-oreille seul, 0 budget : ~10-20 analyses/mois à M12, ~100-150 sur l'année, apprentissage qualitatif possible mais signal statistique faible.
- **Base** — BàO + SEO local + 1-2 partenariats : ~150-180 analyses/mois à M12, ~1 000 sur l'année, premier signal d'adoption exploitable.
- **Ambitieux** — + presse/radio/paid/partenariats actifs : ~1 200 analyses/mois à M12, ~6 000-8 000 sur l'année, volume suffisant pour A/B et décision de monétisation.

---

## 3. Monétisation — B2C freemium vs B2B (comparées, décision laissée au fondateur)

> **Décision NON tranchée par le fondateur.** Ce qui suit met les deux modèles côte à côte
> sur les mêmes critères. **Aucune décision n'est prise ici** — c'est une aide au choix.

### 3.1 Tableau comparatif

| Critère | **B2C freemium** (acheteurs) | **B2B white-label** (agences / courtiers / mandataires) |
|---|---|---|
| Cible | Acheteur particulier, 1ʳᵉ transaction | Agence locale, courtier, réseau de mandataires |
| Prix hypothèse | 5-10 €/mois ou 10-20 € one-shot [source: CONTEXT.md §3.4] | 50-200 €/mois par pro [source: CONTEXT.md §3.4] |
| Volume clients pour 1 000 €/mois | ~150-200 abonnés payants | ~5-20 comptes pros |
| Fréquence d'usage | **Faible** (1 achat tous les ~7-10 ans) → rétention structurellement basse | **Récurrente** (le pro analyse des biens en continu) → rétention élevée |
| CAC attendu | Moyen-élevé (acquérir des inconnus 1 par 1) | Élevé à l'entrée (cycle de vente B2B) mais **amorti** sur la durée de vie |
| Crédibilité / positionnement | **Fort** : « second avis neutre pour l'acheteur » ; payer côté pro pourrait sembler un conflit d'intérêt à l'acheteur | **Risque de posture** : un outil « anti-survente » vendu au vendeur/agent peut paraître contradictoire → à cadrer (outil de *transparence* / *confiance client*, pas d'aide à survendre) |
| Effort produit | Auth + comptes + quotas + paiement (Stripe) — chantier moyen (§6) | Multi-tenant + marque blanche + facturation + éventuelle API — chantier **lourd** |
| Risque principal | Rétention faible → churn → CAC jamais amorti | Cycle de vente long, peu de comptes = **concentration** (perdre 1 client = -X %) |
| Asymétrie d'info (mission produit) | Sert **directement** l'acheteur lésé par l'asymétrie | Sert l'acheteur **via** le pro ; aligné si l'agence l'utilise comme gage de transparence |
| Conformité / RGPD | Données acheteurs (email, paiement) | Contrats B2B, moins de données perso de masse |

### 3.2 Lecture pour la décision

- **Le talon d'Achille du B2C est la fréquence** : un acheteur n'a besoin de l'outil que
  pendant ~quelques semaines de recherche, tous les ~10 ans. Un abonnement mensuel récurrent
  est mal adapté ; un **one-shot 10-20 € « dossier d'achat »** (§3.4 CONTEXT) colle mieux à
  l'usage, mais plafonne le LTV.
- **Le B2B a la récurrence et le LTV**, mais un **risque de positionnement** (vendre au
  vendeur un outil qui sert l'acheteur) et un **coût de build** nettement supérieur
  (multi-tenant, marque blanche).
- **Cohérence avec l'objectif 6-12 mois** (adoption + apprentissage, pas revenu) : aucun des
  deux ne doit être *construit* maintenant. Mais **l'instrumentation §7 doit déjà récolter les
  signaux qui trancheront** : qui revient ? qui exporte ? d'où viennent les analyses (un même
  pro qui analyse 30 biens = signal B2B fort) ?

**Recommandation argumentée (le fondateur tranche) :**

> 1. **Ne rien monétiser avant la fin de la fenêtre d'apprentissage.** Activer un paiement
>    maintenant détruirait le signal d'adoption (le seul KPI qui compte à 6-12 mois).
> 2. **Préparer en priorité l'option B2B**, parce que c'est celle dont les signaux sont les
>    plus discriminants tôt (un utilisateur qui lance 20+ analyses/mois sur des biens variés
>    = quasi certainement un pro) et dont l'économie (récurrence, LTV) résiste à la faible
>    fréquence du B2C. Le **risque de posture** se neutralise en vendant la *transparence*
>    (« montrez à vos acheteurs que vos annonces tiennent la route »), pas la survente.
> 3. **Garder le B2C en one-shot** (« dossier d'achat » 10-20 €) comme **option de
>    monétisation légère et tardive**, pas comme pilier de revenu récurrent.
> 4. **Critère de bascule** : si, dans les events §7, on voit **≥ X % des analyses venant
>    d'utilisateurs récurrents à fort volume** (proxy pro), prioriser un pilote B2B avec 2-3
>    agences partenaires AVANT d'investir dans le paiement B2C. `X` `[HYPOTHÈSE — à fixer,
>    suggestion 15-20 %]`.

> Détail possible dans un futur `docs/strategy/MONETISATION.md` si tu veux dérouler les
> mécaniques de prix et le pilote B2B. Non créé ici pour rester focalisé sur le forecast.

---

## 4. Budget = levier de sortie (CAC × budget → portée → inscrits)

> Le budget est traité comme un **levier** : « quel retour pour quel budget », pas une
> contrainte imposée. Formules :
```
Portée (visiteurs apportés) = budget_mensuel / coût_par_visiteur_du_canal
Inscrits apportés           = Portée × taux_lancement × (1 − taux_échec) × taux_export × taux_inscription
Coût par inscrit (CAC)      = budget_mensuel / inscrits_apportés
```

### 4.1 Canaux adaptés à une ville comme Metz (coûts indicatifs)

| Canal | Coût/visiteur indicatif | Délai d'effet | Plafond local | Étiquette |
|---|---|---|---|---|
| Bouche-à-oreille (cercles, forums locaux) | ~0 € | immédiat | très bas | [HYPOTHÈSE] |
| Groupes Facebook locaux (« Acheter à Metz », quartiers) | ~0 € (temps) à ~0,3 € | jours | moyen | [HYPOTHÈSE] |
| SEO local long-tail (contenu, §9.5 différé) | ~0 € marginal, coût = temps de rédaction | **mois** | élevé | [HYPOTHÈSE ; SEO non validé source: CONTEXT.md §2.4/§9.5] |
| Partenariats (agences transparentes, courtiers, notaires, assos consommateurs) | ~0 € direct, coût = relationnel | semaines | moyen-élevé | [HYPOTHÈSE — B2B2C source: CONTEXT.md §2.4] |
| Presse / radio locale (Républicain Lorrain, France Bleu, Gazette) | encart ~quelques 100 €→pic ponctuel | jours | élevé mais one-shot | [HYPOTHÈSE — à devis] |
| Paid (Google Ads « avis annonce immobilière Metz », Meta) | ~0,5-2 € / visiteur | immédiat | élevé tant qu'on paie | [HYPOTHÈSE — fourchette FR petites villes] |

### 4.2 Table budget → portée → inscrits → coût/inscrit

Hypothèses de calcul : taux **Base** (§2.2 : lancement 30 %, échec 15 %, export 20 %,
inscription 8 % → **taux global visiteur→inscrit ≈ 30 % × 85 % × 20 % × 8 % ≈ 0,4 %**).
Coût/visiteur **mixte** dépendant du palier (les premiers euros vont au gratuit/organique,
les suivants au paid).

| Budget mensuel | Canaux dominants | Coût/visiteur mixte | Portée (visiteurs/mois) | Inscrits/mois (≈0,4 %) | Coût/inscrit |
|---|---|---|---|---|---|
| **0 €** | BàO + groupes FB + SEO (temps) | ~0 € (temps non valorisé) | ~50-300 (= scénarios trafic organique) | ~0,2-1,2 | n/a (coût = temps) |
| **< 100 €** | + 1 partenariat + micro-paid test | ~0,8 € | +~100 payants → ~150-400 total | +~0,4 ; total ~1-2 | ~50-250 €/inscrit |
| **100-500 €** | paid structuré + presse one-shot | ~1,0 € | +~300-500 → ~500-900 total | +~1,5-2 ; total ~2-4 | ~70-180 €/inscrit |
| **500-2 000 €** | paid soutenu + radio/presse + partenariats | ~1,2 € | +~450-1 700 → ~1 200-3 000 total | +~2-7 ; total ~5-12 | ~120-300 €/inscrit |

> **Lecture brutale.** Au funnel actuel (inscription rare car peu d'utilité à s'inscrire
> aujourd'hui, et conversion payante nulle), **le coût par inscrit du paid est élevé
> (~50-300 €)** et **ne se justifie PAS tant qu'il n'y a ni feature compte ni preuve de
> rétention**. Acheter du trafic pour le verser dans un seau percé est le pire usage du budget.

### 4.3 Quel budget justifie quel retour ?

| Budget | Ce qu'il achète **réellement et utilement** maintenant | Verdict |
|---|---|---|
| **0 €** | Validation d'adoption organique + apprentissage. **Suffisant pour l'objectif 6-12 mois.** | **Recommandé par défaut** |
| **< 100 €/mois** | 1-2 mini-tests de canaux (1 partenariat outillé, 1 campagne paid de 50 € pour *mesurer* un CAC réel, pas pour scaler) | **Justifié pour apprendre le CAC**, pas pour la croissance |
| **100-500 €/mois** | Croissance modeste **seulement si** §7 montre déjà rétention/usage répété | Justifié **après** preuve d'usage |
| **500-2 000 €/mois** | Scaling | **Prématuré** : à réserver au post-validation + monétisation amorçable |

> **Le budget que je juge justifié aujourd'hui : 0 € à < 100 €/mois**, ce dernier *uniquement*
> pour **mesurer un CAC réel** sur 1-2 canaux (50 € de paid = un chiffre de CAC vaut plus que
> 500 € de trafic non instrumenté). Le retour visé n'est pas des inscrits mais **un CAC
> chiffré + un signal de rétention** qui débloqueront la décision d'investir plus.

---

## 5. Courbe de coût infra + robustesse, par palier de trafic

### 5.1 Coût dominé par le LLM (formule)

```
Coût LLM mensuel ≈ analyses_abouties/mois × coût_par_analyse × (1 − taux_cache_hit)
coût_par_analyse ≈ 0,001 €  [source: CONTEXT.md §3.2, gpt-4.1-mini]
```
Coûts fixes : Fly ~0-5 €/mois (auto-stop), Vercel 0 €, volume SQLite ~0,15 €/mois
[source: CONTEXT.md §3.2]. **Coût fixe actuel < 1 €/mois.**

### 5.2 Table par palier

| Palier (analyses abouties/mois) | Coût LLM/mois (cache ~30 %) | Coût fixe | **Total €/mois** | Correspond à |
|---|---|---|---|---|
| ~20 (prudent M12) | 20 × 0,001 × 0,7 ≈ **0,01 €** | < 1 € | **< 1 €** | scénario Prudent |
| ~180 (base M12) | ≈ **0,13 €** | ~1-2 € | **~2 €** | scénario Base |
| ~1 250 (ambitieux M12) | ≈ **0,9 €** | ~2-5 € | **~3-6 €** | scénario Ambitieux |
| ~10 000 (hypothétique succès) | ≈ **7 €** | ~5-10 € | **~12-17 €** | au-delà du SOM 12 mois |

> **Conclusion coût : l'infra n'est PAS une contrainte avant longtemps.** Même le scénario
> ambitieux tient **sous ~6 €/mois**. Le risque financier n'est pas le coût récurrent mais
> un **emballement** (scraping malveillant de `/analyze`, pas de rate-limit) → d'où la
> recommandation persistante : **usage limit OpenAI hard** (§9.4 CONTEXT) + rate-limit
> (dette §8). Ces deux items valent plus que toute optimisation de coût.

### 5.3 Points de bascule techniques (robustesse = crédibilité)

| Déclencheur | Bascule recommandée | Étiquette |
|---|---|---|
| Écritures concurrentes / 2ᵉ machine Fly nécessaire | **SQLite → Postgres** (SQLite est mono-writer ; auto-stop + 1 volume = 1 machine) | [source: CONTEXT.md §12, §7.3 ; backend/CLAUDE.md] |
| Seuil indicatif de bascule Postgres | quand trafic soutenu **> ~quelques req/s** OU besoin de scale horizontal OU lectures analytiques lourdes sur comparables | [HYPOTHÈSE — SQLite tient très loin en lecture seule] |
| Cache LLM perdu à chaque restart (in-memory) | **cache LLM persistant** (table SQLite ou Redis Fly) — dès que le trafic répété rend le cache rentable, ou pour lisser le coût | [source: dette CONTEXT.md §8, backend/CLAUDE.md §11] |
| Cache géocodage (BAN) perdu au restart | idem persistance | [source: backend/CLAUDE.md §11 ancrage local] |
| Dépendance egress externe (OpenAI, BAN) | surveiller : si bloqué → fallback LLM / repli quartier silencieux | [source: backend/CLAUDE.md §11] |

### 5.4 SLO de disponibilité (la crédibilité = l'uptime)

| | Prudent | Base | Ambitieux | Note |
|---|---|---|---|---|
| Cible uptime `/analyze` | « best effort » | **99,0 %** | **99,5 %** | [HYPOTHÈSE — cible à choisir] |
| Conséquence | auto-stop = **cold start** acceptable (1ʳᵉ requête lente) | cold start à masquer (warmup / message UX) | envisager min 1 machine chaude (coût ↑) | auto-stop source: CONTEXT.md §12 |
| Monitoring d'erreurs | aucun (état actuel) | **Sentry/Logflare** (dette §8) | + alerte fallback LLM (§9.3 différé) | source: CONTEXT.md §4.3/§8 |

> **Tension assumée** : `auto_stop_machines = true` minimise le coût (~0 € idle) mais
> introduit un **cold start** sur la 1ʳᵉ requête après inactivité — frottement de crédibilité
> si un partenaire/journaliste teste « à froid ». Décision à prendre **seulement** si le
> trafic le justifie (Base+).

---

## 6. Backlog features → impact forecast

> Coûts de build **estimés** en s'appuyant sur l'atelier existant et les analyses 9.x déjà
> versionnées (`docs/specs/9.X-ANALYSE.md`). « j-h » = jours-homme `[HYPOTHÈSE]`.

| Feature | État (source) | Coût build estimé | Levier funnel visé | Trafic/rétention attendus | Priorité forecast |
|---|---|---|---|---|---|
| **Analytics / events** (§7) | absent [source: §4.3] | ~1-3 j-h | **mesure de TOUT le funnel** | nul direct, **débloque toutes les décisions** | **#1 — prérequis** |
| **Rate-limit `/analyze`** | dette [§8] | ~0,5-1 j-h | protège coût + uptime | nul direct, **protège crédibilité/budget** | **#2 — garde-fou** |
| **Socle SEO** (sitemap/robots/metadata) | différé [§9.5] | ~1-2 j-h | `visiteurs` (organique) | **+trafic à 3-6 mois**, durable | **#3 — levier acquisition** |
| **Export PDF du rapport** | .md existe [§9.2] | ~1-2 j-h | `taux_export_ou_partage` | **+partage/viralité**, +crédibilité | moyen |
| **localStorage « Mes annonces » + re-analyser** | identifié non livré [§9.6] | ~2-3 j-h | rétention **sans auth/RGPD** | +retours sans email | moyen-élevé |
| **Auth (magic link) + comptes** | inexistant [§9.6] | **lourd** ~5-10 j-h (email+tokens+session+rate-limit+front) | débloque `taux_inscription` | base de tout B2C récurrent ; **mais email bloqué (pas de domaine)** | **différer** tant que pas de domaine + preuve d'usage |
| **Email récap / alertes** | différé, bloqué [§9.2/§9.6] | moyen ~2-4 j-h **+ prérequis externes** (domaine, Resend, DNS) | engagement/rétention | **non validé** | bloqué (prérequis externes) |
| **Dashboards/rapports sauvegardés** | non commencé | dépend de l'auth | rétention pro (signal B2B) | clé pour B2B | après auth |
| **A/B prompts** | pré-câblé, différé [§9.8] | faible pour fermer la chaîne front | qualité (proxy `taux_lancement`) | **prématuré** au trafic bas | après volume Base+ |

### 6.1 Les 3 features à plus fort levier (synthèse)

1. **Analytics / instrumentation d'events (§7)** — sans elle, *tout le reste est aveugle* :
   on ne peut ni valider le funnel, ni mesurer un CAC, ni trancher B2C/B2B. **Plus haut levier
   absolu** car elle conditionne chaque décision suivante. Coût faible.
2. **Socle SEO local** (sitemap + robots + metadata, déjà cadré en §9.5) — seul levier
   d'acquisition **durable et ~0 €** adapté à Metz ; répare aussi de la dette. Effet lent
   (mois) donc à lancer **tôt**.
3. **Rétention sans compte (« Mes annonces » localStorage + re-analyser)** — augmente les
   retours **sans** ouvrir le chantier auth/email/RGPD (bloqué par l'absence de domaine).
   Meilleur ratio rétention / coût / risque à ce stade.

> **Note coût/levier** : l'auth complète (le plus gros chantier) est **volontairement
> repoussée** — elle est bloquée par un prérequis externe (domaine email) et son levier
> (`taux_inscription`) reste faible tant que la fréquence d'usage B2C est basse (§2.4).

---

## 7. Mesure — events à instrumenter, métriques d'adoption, critères d'apprentissage

> **C'est le livrable le plus actionnable.** Aujourd'hui : **aucune analytics** [source:
> CONTEXT.md §4.3]. Tant que ce n'est pas posé, le forecast reste 100 % hypothèses. Cible :
> events **anonymes, agrégés, RGPD-minimaux** (même esprit que `Feedback` : pas d'IP, pas
> de PII — source: CONTEXT.md §9.7).

### 7.1 Liste EXACTE d'events à instrumenter

| Event | Propriétés | Pourquoi (quel taux du funnel il alimente) |
|---|---|---|
| `page_view` | `path`, `referrer` (domaine seul) | base de `visiteurs uniques/mois` |
| `analysis_started` | `mode` ∈ {url, text} | numérateur de `taux_lancement_analyse` + **split url/texte** (demandé) |
| `analysis_succeeded` | `global_score` (band), `confidence`, `pillar_price_status` ∈ {indéterminé/aligné/sur-positionné…} | `taux_échec_technique` (inverse), qualité produit |
| `analysis_failed` | `reason` ∈ {url_unreachable, llm_fallback, no_input} | mesure réelle de l'échec (anti-bot vs fallback LLM) |
| `report_export` | `format` ∈ {md, copy, pdf(futur)} | `taux_export_ou_partage` + **impressions/exports PDF** (demandé) |
| `district_refine` | `from_scope` → `to_scope` (ville→quartier…) | **affinage quartier** (demandé) : utilité du sélecteur |
| `address_entered` | bool (pas l'adresse !) | usage couche C géocodage, sans stocker de PII |
| `methode_view` | — | **vues /methode** (demandé) : besoin de réassurance/pédagogie |
| `feedback_submitted` | `rating`, `prompt_variant` (déjà câblé §9.7) | satisfaction ↔ score, base A/B futur |
| `repeat_session` | `sessions_count` (cookie 1ʳᵉ partie ou empreinte douce non-PII) | **proxy rétention** + **proxy pro/B2B** (forte récurrence) |
| `analysis_volume_per_session` | compteur d'analyses dans la session | **signal B2B** (1 user, 20 analyses = pro) |

> **Garde-fous mesure** : ne **jamais** logguer l'URL/texte d'annonce brut ni l'adresse
> (PII + droits d'auteur, anti-pattern §11.3 CONTEXT) ; agrégats et bands seulement ;
> outil léger respectant l'auto-stop (pas de polling qui réveille la VM — leçon §9.3).
> Choix d'outil **à décider** (Plausible/Umami self-host, ou table SQLite `events` maison
> dans l'esprit `Feedback`) — `[HYPOTHÈSE — à trancher]`, hors périmètre de ce modèle.

### 7.2 Métriques d'adoption (le tableau de bord 6-12 mois)

| Métrique | Formule | Cible apprentissage (Base) |
|---|---|---|
| Analyses abouties/mois | `analysis_succeeded` count | courbe **croissante** mois après mois |
| Taux d'aboutissement | `succeeded / started` | **> 80 %** (sinon problème fetch/LLM) |
| Taux d'export | `report_export / succeeded` | **> 15 %** = le rapport a de la valeur perçue |
| Taux d'affinage quartier | `district_refine / succeeded` | **> 10 %** = le différenciateur local est utilisé |
| Part url vs texte | `mode=url / total` | informe l'effort anti-bot |
| Satisfaction | moyenne `rating` (≥ 4/5) | **≥ 3,8/5** |
| Taux de retour (proxy rétention) | `repeat_session / total sessions` | **> 5 %** |
| Part « gros volumes » (proxy pro) | sessions avec ≥ N analyses | **discrimine B2C/B2B** |

### 7.3 Critères d'apprentissage : go / no-go / pivot

> Le succès = **adoption + validation du problème d'asymétrie d'info**. Voici les seuils
> qui transforment le forecast en décision. Seuils `[HYPOTHÈSE — à fixer avec le fondateur]`.

- **GO (continuer / investir plus)** si à M6-M12 :
  - tendance analyses/mois **croissante** ET ≥ niveau **Base** (≥ ~75/mois à M6) ;
  - **taux d'export > 15 %** ET **satisfaction ≥ 3,8/5** (le rapport est jugé utile) ;
  - **signal d'asymétrie validé** : les utilisateurs reviennent / exportent / affinent →
    preuve que « lire l'annonce d'un œil neuf » répond à un vrai manque.
- **NO-GO partiel / itérer le produit** si :
  - trafic croît mais **taux d'export < 5 %** ou **satisfaction < 3/5** → le rapport ne
    convainc pas (problème de valeur perçue, pas d'acquisition) → itérer le contenu du rapport.
- **Signaux de PIVOT** :
  - **vers B2B** si une part notable des analyses vient d'**utilisateurs à fort volume**
    (proxy pro) → tester un pilote agences avant tout paiement B2C ;
  - **vers SEO/contenu** si l'organique long-tail surperforme tout le reste en CAC ;
  - **abandon/redéfinition** si, malgré du trafic, **aucun** signal d'utilité (export, retour,
    affinage tous bas) ne se manifeste sur 2-3 mois → le problème d'asymétrie ne « mérite »
    peut-être pas ce produit sous cette forme (l'apprentissage négatif est un résultat valide).

---

## 8. Synthèse exécutive (à garder en tête)

- **Marché (sourcé)** : Moselle ~14-19k transactions/an ; Metz Métropole ~3,4-4,5k/an ;
  TAM d'usage (Moselle) ~100-130k « moments d'analyse »/an ; SAM (Metz Métropole) ~17-54k/an.
- **SOM 12 mois (hypothèse)** : ~85 (prud.) → ~640 (base) → ~3 200 (amb.) analyses.
- **Funnel** : le goulot n'est pas le coût ni la tech, c'est **le trafic** (inconnu, non
  mesuré) et **la faible fréquence d'usage B2C** (rétention structurellement basse).
- **Infra** : non contraignante (< ~6 €/mois même en ambitieux). Vrais risques = abus
  `/analyze` (→ rate-limit + usage limit OpenAI) et cold-start (crédibilité).
- **Décision clé déléguée** : B2C vs B2B — préparer le **signal B2B** dès maintenant via
  l'instrumentation, ne monétiser qu'après la fenêtre d'apprentissage.

---

## 9. Registre d'hypothèses

| # | Hypothèse | Valeur(s) retenue(s) | Impact si fausse | Comment la tester |
|---|---|---|---|---|
| H1 | Transactions/an Moselle ≈ trim. moyen × 4 | 14-19k, base 16k | déplace tout le sizing | bilan annuel Chambre des notaires Moselle (PDF) |
| H2 | Part Metz Métropole = 21-28 % des transactions | base 25 % | déplace SAM | données notaires par EPCI / DVF agrégé |
| H3 | Visites pour vendre = 5-12 | base 8 | déplace TAM d'usage | sourcé (fourchette agences) — affiner local |
| H4 | Acheteurs sérieux/bien = 4-9 | base 6 | déplace TAM d'usage | observatoire / entretiens agents |
| H5 | Trafic M0 ≈ 30-80 visiteurs/mois | inconnu | **fonde tout le funnel** | **installer analytics (urgent)** |
| H6 | `taux_lancement` 15-45 % | base 30 % | déplace analyses | mesurer `analysis_started/page_view` |
| H7 | `taux_échec` 8-25 % | base 15 % | déplace analyses abouties | mesurer `analysis_failed` |
| H8 | `taux_inscription` 3-15 % | base 8 % | conditionne B2C | nécessite feature compte d'abord |
| H9 | `taux_conversion_payant` 1-6 % | base 3 % | conditionne revenu B2C | nécessite paiement d'abord |
| H10 | Coût/analyse 0,001 € | fixe | faible (infra non contraignante) | sourcé CONTEXT ; re-mesurer si modèle change |
| H11 | Cache hit ≈ 30 % | 30 % | faible sur coût total | mesurer ratio cache |
| H12 | Prix B2C 5-20 € / B2B 50-200 €/mois | sourcé CONTEXT §3.4 | déplace l'éco de monétisation | tests de prix (post-validation) |
| H13 | CAC paid 0,5-2 €/visiteur | base ~1 € | déplace table budget §4 | **50 € de paid pour mesurer un vrai CAC** |
| H14 | Bascule SQLite→Postgres « lointaine » | > quelques req/s | faible court terme | charge réelle |

---

## 10. À vérifier — ordonné par impact (du plus structurant au moins)

1. **[CRITIQUE] Trafic réel actuel** — aucune analytics installée → M0 est une pure hypothèse
   (H5). **Tout le funnel en dépend.** → *Installer l'instrumentation §7 (event #1).* Bloque
   la quasi-totalité des décisions.
2. **[FORT] Volume annuel de transactions Metz Métropole / Moselle** — dérivé de chiffres
   trimestriels notaires (H1, H2). Vérifier sur le **bilan annuel de la Chambre des notaires
   de la Moselle** et/ou **DVF open data (data.gouv.fr)** agrégé par EPCI (utilisable comme
   *input forecast* même si DVF est exclu comme *source produit*). *Tentative web : chiffres
   trimestriels obtenus via presse citant les notaires ; le total annuel propre par EPCI n'a
   pas été trouvé en accès libre dans cette session.*
3. **[FORT] Choix de monétisation B2C vs B2B** — non tranché (par design). Les signaux §7
   (récurrence, volume/session = proxy pro) doivent être collectés avant de trancher.
4. **[MOYEN] Coefficients de demande** : visites/vente (H3, partiellement sourcé), acheteurs
   sérieux/bien (H4), durée de vie d'annonce — affiner via observatoire local / entretiens.
5. **[MOYEN] CAC réel par canal** (H13) — inconnu tant qu'aucune campagne n'a tourné.
   *Recommandé : 50 € de paid pour mesurer, pas pour scaler.*
6. **[MOYEN] Faisabilité partenariats locaux** (agences transparentes, courtiers, notaires,
   assos) — canal le plus aligné mission, coût ~0 €, mais effort relationnel non chiffré.
7. **[FAIBLE] Prérequis externes auth/email** : acquisition d'un **domaine** (bloque email,
   magic link, watchlist — §9.2/§9.6 CONTEXT). Décision humaine, pas technique.
8. **[À NE PAS CONFONDRE] « 192 maisons + 459 apparts 2018-2022 à Metz » [source: Orpi]** =
   échantillon d'agence, **PAS** le volume marché. Ne jamais l'utiliser comme TAM.

---

## Annexe — Sources publiques consultées (session 2026-06-08)

- INSEE — Dossier/comparateur commune Metz (57463), EPCI Metz Métropole (200039865),
  département Moselle (57) ; populations légales au 1ᵉʳ janv. 2026 (rec. 2023).
- Chambre des notaires de la Moselle — transactions trimestrielles 2022-2023 (via France
  Bleu, Gazette Moselle, Affiches-Moniteur).
- Notaires de France — volumes nationaux ancien 2023-2024 (via Immomatin, Dalloz, Extencia).
- Agences (SeLoger, Guy-Hoquet, Optimhome…) — nombre de visites pour vendre (5-12).
- Orpi Accueil 57 — répartition ventes Metz (échantillon, **non utilisé comme volume**).

> **Accès web** : les recherches publiques ont abouti pour la population (INSEE) et les
> ordres de grandeur de transactions (notaires/presse). **Le total annuel de transactions
> propre par EPCI et les exports DVF agrégés n'ont pas été récupérés en accès direct dans
> cette session** ; les lignes concernées sont dérivées et marquées, et reportées en §10
> (item 2) « à vérifier ». Aucun chiffre n'a été fabriqué.

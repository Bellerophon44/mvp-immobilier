# BUSINESS-CASE — Cohérence (multi-éditions Alsace-Moselle, puis France)

> **Nature de ce document.** Business case multi-scénarios que le fondateur possède et
> édite, pas une prédiction ni une décision. Il EXTEND `docs/strategy/FORECAST.md` (Metz)
> à l'échelle multi-éditions : il réutilise ses formules et ses chiffres de funnel/infra,
> et ne les contredit pas sans le dire. Chaque chiffre porte `[source: …]` (donnée publique
> vérifiée) ou `[HYPOTHÈSE — à valider]`. Aucun nombre nu. Trois scénarios partout :
> **Prudent / Base / Ambitieux** (trois jeux d'hypothèses cohérents, pas des probabilités).
> Les formules sont posées en clair : change une entrée, le reste suit.
>
> **Statut produit (rappel, ne pas l'oublier en lisant les revenus).** App gratuite,
> **trafic quasi nul**, **aucune analytics installée** → tout repère de trafic/conversion
> est une **hypothèse à instrumenter** (FORECAST §7, §10 item #1). Coût marginal mesuré
> ≈ **0,001 €/analyse** (`gpt-4.1-mini`) [source: CONTEXT.md §3.2]. Coût fixe actuel
> **< 1 €/mois** [source: CONTEXT.md §3.2].
>
> **Question centrale (le mandat).** *Cette app peut-elle faire de l'argent, à quelle
> échéance, sous quel format, avec quel scope ?*
>
> **Dernière mise à jour du modèle** : 2026-06-23.

---

## 0. Cadrage : question, horizon, ce qui repose sur des hypothèses

### 0.1 La question, décomposée

« Faire de l'argent » se décompose en quatre sous-questions, traitées dans ce document :
- **À quelle échéance ?** → §5 (break-even par scénario sur 12 / 24 / 36 mois).
- **Sous quel format ?** → §3 (B2C one-shot / freemium / B2B white-label / API ; + cookies
  et pub comme leviers optionnels chiffrés).
- **Avec quel scope ?** → §1-§2 (quelles éditions géo, quelles vagues produit, gates de
  passage) et §6 (le pari « reste de la France »).

### 0.2 Horizon retenu

Le FORECAST raisonnait à **6-12 mois** (objectif = adoption + apprentissage, **pas** revenu).
Un business case « faire de l'argent » est un horizon **plus long**. On retient **12 / 24 /
36 mois**, en cohérence avec le séquencement rollout (§2). À 12 mois on ne juge pas la
rentabilité : on juge si l'adoption autorise à *investir* dans la monétisation.

### 0.3 Ce qui est solide vs ce qui est hypothèse (à garder en tête)

| Solide (sourcé) | Hypothèse (à instrumenter / valider) |
|---|---|
| Populations des bassins (INSEE) | Trafic réel actuel (aucune analytics — FORECAST §10 #1) |
| Volume national de transactions (notaires) | Volume de transactions par bassin local (dérivé) |
| Coût/analyse et coût infra (mesurés) | Tous les taux de conversion (funnel) et prix de vente |
| Exclusion DVF Alsace-Moselle (vérifiée ×2) | Coût RH et coût par édition (estimés) |

> **Conséquence de méthode.** Les chiffres de **revenu** de ce document sont **dérivés
> d'hypothèses empilées** (trafic × taux × prix), eux-mêmes non encore mesurés. Ils donnent
> des **ordres de grandeur et des points de bascule**, pas une prévision. Le premier
> livrable qui transforme ce business case en décision reste l'**instrumentation** (FORECAST
> §7), sans laquelle le numérateur de tout calcul de revenu est inconnu.

---

## 1. Sizing multi-éditions (TAM → SAM → SOM consolidé)

### 1.1 Méthode (identique au FORECAST, appliquée par bassin)

On réutilise la chaîne du FORECAST §1, en quatre temps :
```
(1) Population du bassin                                  [source INSEE]
(2) Transactions/an du bassin   ≈ population × (trans_nationales / population_nationale)
                                  [cross-check national ; à confirmer par notaires locaux]
(3) Moments d'analyse/an (TAM)  ≈ transactions/an × visites_pour_vendre   (base = 8)
(4) SOM/an                       = SAM × part_captée   (funnel §3 / FORECAST §2)
```
- L'étape (2) est le **cross-check national** que le FORECAST a validé pour la Moselle
  (Moselle ≈ 1,6 % de la pop FR → ≈ 1,6 % des transactions). On l'étend ici aux autres
  bassins **faute de volume notaires local par bassin** (cf. §8 « à vérifier »). C'est un
  **proxy**, pas une mesure : flaggé partout.
- Référence nationale : **~945 000 transactions/12 mois fin 2025** ; **~958 000 à fin fév.
  2026** (ancien, hors Mayotte) [source: Notaires de France / CSN, bilan 2025 + Immo Matin,
  fév. 2026]. On retient **~950 000** comme base nationale [dérivé des deux points].
- `visites_pour_vendre` = **5 / 8 / 12** (prudent/base/ambitieux), sourcé agences au FORECAST
  §1.3 [source: SeLoger / Guy-Hoquet]. On garde **base 8**.

### 1.2 Populations des bassins (socle sourcé)

| Bassin (périmètre rollout) | Population (≈2023) | Étiquette |
|---|---|---|
| **Metz Métropole** (Phase 1, l'existant) | ~220 000 | [source: INSEE EPCI Metz Métropole, via FORECAST §1.1] |
| Département **Moselle (57)** | ~1 051 000 | [source: INSEE pop. légales 2023, FORECAST §1.1] |
| **Thionville** (commune) | ~42 700 | [source: INSEE commune 57672 / web 2026] |
| **Agglo Thionville-Fensch** (Sillon Nord) | ~155 000 | [source: web 2026 ; INSEE EPCI — à reconfirmer périmètre exact] |
| **Strasbourg Eurométropole** (Phase 3a) | ~522 600 | [source: INSEE EPCI Eurométropole 246700488 / web 2026] |
| Département **Bas-Rhin (67)** | ~1 164 000 | [source: INSEE pop. 2023 / web] |
| Département **Haut-Rhin (68)** | ~771 000 | [source: INSEE pop. 2023 / web] |
| **Total cœur Alsace-Moselle (57+67+68)** | **~2 986 000** | [dérivé : somme des trois départements] |
| **France entière** | ~66 000 000 | [source: ordre de grandeur INSEE, FORECAST §1.2] |

> **Note périmètre Phase 2.** Le « Sillon Lorrain Nord » (Metz→Thionville→frontière, Luxembourg
> exclu) recoupe la Moselle déjà comptée. Pour éviter le double comptage, on raisonne en
> **incrément** : Phase 2 ajoute surtout l'**axe Thionville-Fensch (~155k)** et la dynamique
> **frontalière** (travailleurs du Luxembourg) comme spécificité locale, pas un nouveau
> département. La Moselle hors Metz Métropole (~830k hab.) est le réservoir d'extension
> intra-57.

### 1.3 Transactions/an par bassin (cross-check national, proxy)

Formule : `transactions/an ≈ population × (950 000 / 66 000 000) = population × 1,44 %`
[dérivé du ratio national]. Le FORECAST a montré que ce proxy tombe **un peu sous** la
dérivation notaires Moselle ; on garde donc une fourchette ±15 % autour du proxy.

| Bassin | Pop. | Transactions/an (proxy ±15 %) | Étiquette |
|---|---|---|---|
| Metz Métropole | ~220 000 | ~2 700 – ~3 600 ; base **~3 200** | [dérivé proxy ; FORECAST retient ~3,4-4,5k via sur-poids urbain] |
| Moselle (57) | ~1 051 000 | ~12 800 – ~17 400 ; base **~15 000** | [cohérent FORECAST §1.2 base ~15k] |
| Agglo Thionville-Fensch | ~155 000 | ~1 900 – ~2 600 ; base **~2 200** | [dérivé proxy] |
| Strasbourg Eurométropole | ~522 600 | ~6 400 – ~8 700 ; base **~7 500** | [dérivé proxy] |
| Bas-Rhin (67) | ~1 164 000 | ~14 300 – ~19 300 ; base **~16 800** | [dérivé proxy] |
| Haut-Rhin (68) | ~771 000 | ~9 500 – ~12 800 ; base **~11 100** | [dérivé proxy] |
| **Cœur Alsace-Moselle (57+67+68)** | ~2 986 000 | ~36 600 – ~49 500 ; base **~43 000** | [dérivé proxy ; somme] |
| France entière | ~66 000 000 | **~950 000** | [source: notaires 2025-2026] |

> **Garde-fou de fraîcheur.** Les volumes Alsace-Moselle sont **en repli marqué** sur
> 2023-2024 : **-34 % Bas-Rhin, -20 % Haut-Rhin en 2023**, retour aux niveaux 2015-2016
> [source: Chambre des notaires Bas-Rhin / Haut-Rhin, via France Bleu + cir-colmar-metz 2024].
> Le proxy ci-dessus est calé sur le **national en reprise** (+11 %/an fin 2025) : il
> **sur-estime probablement** l'Alsace-Moselle sur la période basse. Lire les bases comme
> un **haut de fourchette** tant que le volume notaires local par bassin n'est pas obtenu
> (§8). **Aucun volume notaires local absolu n'a pu être récupéré dans cette session** —
> seulement des taux d'évolution ; le volume absolu est marqué « à vérifier ».

### 1.4 TAM d'usage par bassin (moments d'analyse/an)

`TAM_usage = transactions/an × visites_pour_vendre (base 8)` [FORECAST §1.3].

| Bassin | TAM d'usage/an (base ×8) | Étiquette |
|---|---|---|
| Metz Métropole (existant) | ~3 200 × 8 ≈ **~26 000** | [dérivé ; FORECAST donne ~17-54k, base ~32k] |
| Agglo Thionville-Fensch | ~2 200 × 8 ≈ **~18 000** | [dérivé] |
| Strasbourg Eurométropole | ~7 500 × 8 ≈ **~60 000** | [dérivé] |
| Bas-Rhin (67) entier | ~16 800 × 8 ≈ **~134 000** | [dérivé] |
| Haut-Rhin (68) entier | ~11 100 × 8 ≈ **~89 000** | [dérivé] |
| **Cœur Alsace-Moselle (57+67+68)** | ~43 000 × 8 ≈ **~344 000** | [dérivé ; TAM consolidé hors-DVF] |
| France entière | ~950 000 × 8 ≈ **~7 600 000** | [dérivé] |

### 1.5 Synthèse TAM / SAM / SOM consolidée

| Niveau | Définition retenue | Valeur (base) | Étiquette |
|---|---|---|---|
| **TAM hors-DVF** | Moments d'analyse/an, cœur **Alsace-Moselle (57+67+68)** | **~280 000 – 410 000 ; base ~344 000** | [dérivé §1.4] |
| **TAM France** | Moments d'analyse/an, France entière | **~6,5 – 8,5 M ; base ~7,6 M** | [dérivé §1.4] |
| **SAM (rollout réaliste)** | Bassins effectivement couverts par une **édition mûre** (data densifiée + marque locale) à un horizon donné ; à 36 mois Base = Metz Métropole + Thionville-Fensch + Strasbourg Eurométropole | **~104 000** (= 26k + 18k + 60k) | [dérivé §1.4 ; gating §2] |
| **SOM 36 mois** | Part réellement captée, gratuit→monétisé partiel | prud. ~1 % → base ~3 % → amb. ~7 % du SAM | [HYPOTHÈSE — funnel §3 / FORECAST §2] |

**SOM 36 mois en actes d'analyse (Base, SAM ~104k) :**
```
SOM = SAM × part captée = 104 000 × 3 % ≈ 3 100 analyses/an  (base, à 36 mois)
```
Fourchette : **~1 000 (prud.) → ~3 100 (base) → ~7 300 (amb.)** analyses/an à 36 mois,
**toutes éditions confondues**.

> **Lecture honnête du sizing.** Le TAM hors-DVF (~344k moments/an) est **~3,5× le SAM
> Metz seul** du FORECAST : l'extension géo multiplie réellement le plafond. Mais le SOM
> reste **petit en absolu** parce que le goulot n'est ni le marché ni l'infra : c'est le
> **trafic** (inconnu) et la **faible fréquence B2C** (FORECAST §2.4). Ouvrir 3 éditions ne
> résout pas le goulot — ça le **réplique 3 fois**. Le sizing dit « le plafond existe » ;
> il ne dit pas « le revenu suit ». C'est §3-§5 qui tranchent.

---

## 2. Phasage rollout (produit × géo) + gates de passage

### 2.1 Deux axes séquencés

- **Axe produit** : **Vague A — Desktop/Web** (l'existant, mûr) → **Vague B — Mobile**
  (Expo/RN ~4-8 sem puis natif ; cf. `mobile-app-ANALYSE.md` §2). La mobile n'est pas un
  remplacement : elle débloque le **partage natif** (contourne LeBonCoin), l'**OCR vitrine**,
  la **géoloc terrain** et — plus tard — le **push** (rétention). C'est aussi elle qui porte
  le pari « reste de la France » (valeur terrain, §6).
- **Axe géo (éditions locales)** : Metz (labo) → Sillon Nord/Thionville → Strasbourg/Alsace
  → (instruction) reste de la France. Chaque édition exige une **empreinte locale
  authentique** (contrainte marque impérative, §4 du brief) — c'est un **coût récurrent par
  édition** chiffré en §4.

### 2.2 Frise de séquencement (indicative, scénario Base)

```
        0-6 mois      6-12 mois     12-24 mois          24-36 mois
GÉO   | Metz (mûr) | Metz + instrum.| Thionville/Nord  | Strasbourg + Alsace
      |            | + 1 pilote B2B | (Sillon frontalier)| (67 puis 68)
PROD  | Web mûr    | Web + analytics| Mobile Expo (B)  | Mobile natif + push
      |            | + SEO socle    | partage/OCR/géoloc| (cap auth/PII)
MONÉT.| 0 €        | 0 € (apprend.) | B2C one-shot +    | + B2B white-label
      |            |                | 1er pilote B2B    | (signal pro confirmé)
```

> La Vague B (mobile) est placée en **Phase 2 (12-24 mois)** : elle vaut surtout combinée
> à l'extension géo (un acheteur Thionville/Strasbourg en visite = usage terrain) et après
> que l'instrumentation a **confirmé un appétit mobile** (mobile-app-ANALYSE §2 : « valider
> d'abord l'appétit mobile »). L'avancer sans ce signal = construire à l'aveugle.

### 2.3 Gates de passage (conditions de bascule — ne pas ouvrir l'édition n+1 avant)

Chaque ouverture d'édition coûte (data + marque + maintenance, §4). On n'ouvre **pas** sur
l'enthousiasme : on ouvre sur **preuve d'adoption/rétention** dans l'édition précédente.

| Gate | Avant d'ouvrir… | Condition (proxy mesurable, seuils `[HYPOTHÈSE — à fixer]`) |
|---|---|---|
| **G0** | Toute monétisation | Analytics installée + funnel mesuré ≥ 1 trimestre (FORECAST §7) |
| **G1** | Thionville / Sillon Nord | Metz atteint ≥ niveau **Base** (≥ ~75 analyses abouties/mois) ET taux d'export > 15 % ET satisfaction ≥ 3,8/5 (= GO du FORECAST §7.3) |
| **G2** | Mobile (Vague B) | Part de trafic **mobile** mesurée ≥ X % (suggestion 40 %) ET ≥ 1 fonction native validée utile (partage/OCR) |
| **G3** | Strasbourg / Alsace | Thionville réplique le funnel Metz **sans** ré-investissement marketing proportionnel (= preuve que le playbook édition est reproductible) ET 1er revenu B2C/B2B observé |
| **G4** | Reste de la France | Strasbourg/Alsace rentables OU pari terrain mobile prouvé (§6) ; sinon **NO-GO** (le moat data disparaît hors zone, §6) |

> **Principe directeur.** La valeur de ce phasage n'est pas la frise, c'est la **discipline
> des gates** : chaque édition est un **pari coûteux** (§4) qui ne doit être pris qu'après
> preuve reproductible. Sans gates, l'extension géo transforme un coût marginal nul en un
> coût fixe (humain + édition) qui tue la rentabilité (§5).

---

## 3. Scénarios de revenu (Prudent / Base / Ambitieux)

### 3.1 Formules de conversion (reprises du FORECAST §2)

```
Analyses abouties/mois = Visiteurs/mois × taux_lancement × (1 − taux_échec)
Payants B2C one-shot/mois = Analyses abouties/mois × taux_achat_dossier
Abonnés B2C premium       = base installée × taux_conversion_premium
Comptes B2B               = f(démarchage) — PAS dérivé du funnel grand public
MRR = (abonnés B2C × prix_abo) + (comptes B2B × prix_B2B) ; one-shot = revenu non récurrent
```
Taux funnel **base** (FORECAST §2.2) : lancement 30 %, échec 15 %, export 20 %.
**Nouveaux taux de monétisation** posés ici (tous `[HYPOTHÈSE — à valider]`) :

| Taux de monétisation | Prudent | Base | Ambitieux | Étiquette |
|---|---|---|---|---|
| `taux_achat_dossier` (analyse aboutie → achat one-shot 10-20 €) | 0,5 % | 2 % | 5 % | [HYPOTHÈSE — micro-paiement ponctuel] |
| `taux_conversion_premium` (utilisateur actif → abonné) | 0,5 % | 1,5 % | 3 % | [HYPOTHÈSE — freemium B2C, fréquence basse FORECAST §2.4] |
| Prix one-shot « dossier d'achat » | 10 € | 15 € | 20 € | [source: CONTEXT §3.4 ; FORECAST §3] |
| Prix abo B2C premium | 5 €/mois | 7 €/mois | 10 €/mois | [source: CONTEXT §3.4] |
| Prix B2B white-label | 50 €/mois | 100 €/mois | 200 €/mois | [source: CONTEXT §3.4 ; FORECAST §3] |

### 3.2 Volume d'analyses par scénario (consolidé toutes éditions, à 36 mois)

On part du SOM §1.5 (analyses/an) ramené au mois :

| Scénario | Analyses/an (36 mois) | Analyses/mois (≈) |
|---|---|---|
| Prudent | ~1 000 | ~85 |
| Base | ~3 100 | ~260 |
| Ambitieux | ~7 300 | ~610 |

> Ces volumes consolidés (3 éditions) restent **du même ordre** que le seul Metz ambitieux
> du FORECAST (~1 250 analyses/mois à M12). C'est cohérent : l'extension géo **élargit le
> plafond** mais le trafic réel par édition démarre bas à chaque ouverture (re-amorçage).

### 3.3 Trajectoire de revenu (B2C one-shot, le format le plus tôt activable)

`Revenu one-shot/mois = analyses/mois × taux_achat_dossier × prix_one-shot`

| Scénario (36 mois) | Calcul | Revenu one-shot/mois | Revenu one-shot/an |
|---|---|---|---|
| Prudent | 85 × 0,5 % × 10 € | **~4 €** | ~50 € |
| Base | 260 × 2 % × 15 € | **~78 €** | ~940 € |
| Ambitieux | 610 × 5 % × 20 € | **~610 €** | ~7 300 € |

### 3.4 Trajectoire de revenu (B2B white-label, le format à plus fort LTV)

Le B2B **ne se dérive pas du funnel grand public** : il dépend du démarchage et du signal
pro (FORECAST §3). On le modélise en **nombre de comptes pros** acquis.

| Scénario (36 mois) | Comptes B2B | Prix/mois | **MRR B2B** | ARR B2B |
|---|---|---|---|---|
| Prudent | 1 | 50 € | **~50 €** | ~600 € |
| Base | 5 | 100 € | **~500 €** | ~6 000 € |
| Ambitieux | 20 | 150 € | **~3 000 €** | ~36 000 € |

> **Comparaison des deux formats (réutilise FORECAST §3.1).** Pour atteindre ~1 000 €/mois :
> il faut **~5-20 comptes B2B** OU **~150-200 abonnés B2C** OU **des milliers d'analyses
> one-shot/mois**. Au trafic projeté (centaines d'analyses/mois consolidées), **le B2C seul
> n'atteint jamais 1 000 €/mois** ; le **B2B est le seul format qui peut**, parce que son
> revenu ne dépend pas du faible trafic grand public. C'est le résultat dominant du §3.

### 3.5 Format dominant recommandé par phase

| Phase | Format dominant recommandé | Pourquoi |
|---|---|---|
| 0-12 mois | **Aucun (gratuit)** | Monétiser détruit le signal d'adoption, seul KPI utile (FORECAST §3.2) |
| 12-24 mois | **B2C one-shot « dossier d'achat »** | Le plus simple à brancher (Stripe + un export enrichi), colle à l'usage ponctuel, ne suppose ni auth lourde ni récurrence ; **plafond de revenu bas mais risque bas** |
| 12-24 mois (parallèle) | **1er pilote B2B** dès signal pro | Le seul format au LTV qui résiste à la faible fréquence ; à amorcer dès que les events montrent des utilisateurs à fort volume (proxy pro, FORECAST §7) |
| 24-36 mois | **B2B white-label + premium mobile au moment push** | Le push (rétention) débloque un premium mobile défendable ; le B2B monte en compte |

### 3.6 Leviers optionnels : cookies et publicité (chiffrés et tranchés)

**Cookies (analytics fine, retargeting, A/B, rétention).**

| Ce que ça débloque | Coût de posture | Ordre de grandeur de gain |
|---|---|---|
| Attribution multi-touch, retargeting, A/B fiable, mesure de rétention cookie | Bandeau de consentement (friction + perte de ~20-50 % du signal des refus) [HYPOTHÈSE], conformité RGPD/registre, **tension directe avec la marque « sobre et honnête »** (REBRAND : « tu peux être le seul de ton marché à ne pas mentir ») | Indirect : améliore le **taux de conversion** des leviers existants de quelques points [HYPOTHÈSE], **n'apporte aucun revenu direct** |

> **Reco cookies (le fondateur tranche).** **NE PAS** introduire de cookies tiers/retargeting
> tant que le funnel n'est pas mesuré par l'instrumentation **anonyme RGPD-minimale déjà
> cadrée** (FORECAST §7, esprit `Feedback` : pas d'IP, pas de PII). Cette instrumentation
> couvre ~80 % du besoin de mesure **sans** bandeau ni coût de marque. Les cookies de
> retargeting ne se justifient **qu'après** preuve qu'on a un produit à retargeter ET un
> budget paid à optimiser (§5) — c'est-à-dire **pas avant 24 mois** dans le scénario Base.
> Le coût de marque est réel : la sobriété est le différenciateur (REBRAND §3-§7).

**Publicité (display / sponsoring d'agences locales).**

| Option | Revenu réaliste à ce trafic | Conflit de posture |
|---|---|---|
| Display programmatique | À ~3 000-7 000 analyses/an (36 mois Base/amb.), à un RPM de ~1-5 € [HYPOTHÈSE], le revenu pub ≈ **quelques dizaines à ~150 €/an** — **négligeable** | **Élevé** : un « second avis neutre pour l'acheteur » couvert de bannières détruit la crédibilité |
| Sponsoring d'agences locales « transparentes » | Variable, potentiellement > display | **Critique** : un outil anti-survente financé par les agences = conflit d'intérêt frontal, exactement ce que le produit dénonce |

> **Reco pub (tranchée).** **NON.** Le revenu pub réaliste à ce trafic est **négligeable**
> (dizaines d'euros/an) et le coût de marque est **disproportionné** : il attaque le cœur du
> positionnement (neutralité acheteur). Le sponsoring agences est encore pire (conflit
> d'intérêt structurel). **Le revenu pub ne vaut pas le coût de marque.** Si un jour un
> partenariat agence existe, ce doit être un **canal B2B de transparence** (l'agence paie
> pour *prouver* que ses annonces tiennent la route — FORECAST §3.1), jamais de la pub
> display à l'acheteur.

---

## 4. Scénarios de coût (Prudent / Base / Ambitieux)

### 4.1 Le driver de coût n'est plus l'infra

Le FORECAST §5 le démontre : même en ambitieux, l'**infra tient sous ~6 €/mois**. C'est
toujours vrai ici. On confirme par palier, puis on ajoute les **deux vrais drivers** :
**coût par édition** et **coût RH**.

**Infra par palier (étend FORECAST §5.2) :**

| Palier d'usage consolidé | Coût LLM/mois | Coût fixe | **Total infra/mois** | Étiquette |
|---|---|---|---|---|
| ~260 analyses/mois (Base 36 mois) | ~0,2 € | ~2 € | **~2-3 €** | [dérivé FORECAST §5.1] |
| ~610 analyses/mois (Amb. 36 mois) | ~0,4 € | ~3-5 € | **~4-6 €** | [dérivé FORECAST §5.1] |
| Infra « state-of-the-art ambitieuse » (cf. brief §6 : Postgres + Redis + machine chaude + Sentry + CDN) | LLM idem | ~30-80 €/mois (Postgres managé + Redis + 1 VM toujours chaude + monitoring) | **~30-90 €/mois** | [HYPOTHÈSE — paliers vendors managés] |
| LLM **state-of-the-art** (modèles plus capables + vision lourde pHash/screening) | si on quitte gpt-4.1-mini pour du modèle premium : coût/analyse ×5 à ×20 → ~0,005-0,02 € | — | reste **< quelques €/mois** au volume projeté | [HYPOTHÈSE — pricing modèles premium] |

> **Conclusion infra (inchangée et structurante).** Même en empilant Postgres, Redis, machine
> chaude, Sentry, CDN et un LLM premium, l'infra reste **à deux chiffres d'euros/mois** au
> volume projeté. **L'infra n'est jamais le frein à la rentabilité.** Le risque financier
> infra reste l'**emballement** (abus `/analyze` sans rate-limit) → garde-fou usage-limit
> OpenAI + rate-limit (FORECAST §5.2, CONTEXT §9.4). Les comptes stores (Apple 99 $/an,
> Google 25 $ une fois) et EAS Build sont **marginaux** [source: mobile-app-ANALYSE §2].

### 4.2 Coût par édition (le poste récurrent imposé par la marque)

Contrainte marque impérative (brief §4) : chaque édition porte une **empreinte locale
authentique** (héraldique/pierre/POI/dynamiques locales). Ce n'est pas cosmétique →
**coût de build + coût récurrent par édition**.

| Poste par édition | Coût build estimé (j-h) | Récurrent | Étiquette |
|---|---|---|---|
| Gazetteer local (communes/quartiers/secteurs) | ~3-6 j-h | maintenance légère | [HYPOTHÈSE ; modèle = `geo_gazetteer.py` Metz, CONTEXT §0] |
| POI/écoles/transports (snapshot + distances) | ~2-4 j-h | rafraîchissement annuel | [HYPOTHÈSE ; modèle = C3 Annuaire Éducation, CONTEXT §0] |
| Scrapers d'agences locales (densifier les comparables) | ~3-8 j-h **par lot d'agences** | maintenance anti-casse (sélecteurs) | [HYPOTHÈSE ; recon couronne = 0 candidate retenue, CONTEXT §0 incrément 3] |
| Assets de marque + wording local (empreinte authentique) | ~2-4 j-h + éventuel graphiste | refresh ponctuel | [HYPOTHÈSE ; cf. LOCAL-ANCHORING : ~80 % de l'effet = wording] |
| **Total par édition** | **~10-22 j-h** + vérif données | **maintenance scrapers récurrente** | [dérivé] |

> **Avertissement coût caché (issu de la recon Metz).** La densification des comparables par
> scraping d'agences locales est le poste **le plus risqué et le plus récurrent** : la recon
> couronne messine a retenu **0 candidate sur la 1ʳᵉ vague** (robots.txt interdit, sites
> JS-only) [source: CONTEXT.md §0, incrément 3]. **Rien ne garantit qu'une nouvelle édition
> trouve des sources scrapables** ; sans elles, le pilier prix retombe sur « Indéterminé »
> et l'empreinte locale est creuse. C'est un **risque de faisabilité par édition**, pas un
> simple coût. Le gisement DVF qui aiderait ailleurs est **nul sur tout le cœur Alsace-Moselle**
> [source: DVF-couronne.md §0].

### 4.3 Coût de build mobile (reprend mobile-app-ANALYSE §2)

| Poste | Coût | Étiquette |
|---|---|---|
| Portage Expo/RN (UI minuscule, backend inchangé) | ~4-8 semaines dev solo | [source: mobile-app-ANALYSE §2] |
| Trio natif jour 1 (partage / OCR / géoloc) | inclus dans le portage (branche sur l'API) | [source: mobile-app-ANALYSE §3] |
| Chantier push (re-list / baisse de prix) | **lourd** : casse 3 invariants (auth/PII, stockage pHash, persistance analyses) | [source: mobile-app-ANALYSE §6] |
| Comptes stores + EAS + CI/CD mobile | Apple 99 $/an, Google 25 $, EAS ~free→payant | [source: mobile-app-ANALYSE §2] |

> Le portage UI est **petit** ; le coût réel mobile est (a) la **fiabilisation de
> l'ingestion** malgré l'anti-bot (WebView on-device) et (b) le **cap d'architecture** du
> push (passage « outil anonyme sans état » → « produit identifié avec état »). Ce cap est
> une **décision produit**, pas qu'un chiffrage (mobile-app-ANALYSE §6-§7).

### 4.4 Courbe RH (le vrai driver quand l'ambition l'exige)

Le brief le pose : le vrai driver de coût, c'est le passage **fondateur solo → petite
équipe**. Modèle des déclencheurs d'embauche (ordres de grandeur France, chargé) :

| Palier | Composition | Coût RH/mois (chargé) | Déclencheur d'embauche |
|---|---|---|---|
| **Solo** (aujourd'hui → ~12-18 mois) | Fondateur | ~0 € (non valorisé) ou coût d'opportunité | défaut |
| **+1** (build mobile OU 2ᵉ-3ᵉ édition) | + 1 dev / 1 freelance | ~4 000-7 000 €/mois | quand le backlog édition + mobile dépasse la capacité solo (G2/G3) |
| **+2-3** (rollout Alsace + B2B) | + commercial/ops B2B + data/scraping | ~10 000-18 000 €/mois | quand le **revenu B2B** justifie un cycle de vente dédié (G3 franchi) |

> **Résultat dominant des coûts.** L'infra est **bruit de fond** (€/mois à deux chiffres au
> pire). Le coût par édition est **modéré mais récurrent et risqué** (scrapers). **Dès qu'on
> embauche, le RH écrase tout le reste de 2-3 ordres de grandeur.** La question de
> rentabilité (§5) n'est donc PAS « le revenu couvre-t-il l'infra ? » (trivialement oui dès
> les premiers euros) mais « **le revenu couvre-t-il l'humain qu'exige l'ambition ?** » —
> et là, c'est tendu (§5).

---

## 5. P&L / trajectoire de rentabilité — la réponse à la question centrale

### 5.1 Confrontation revenu vs coût par scénario

On distingue **deux régimes** car ils donnent deux réponses opposées :

**Régime A — Fondateur solo, RH non valorisé** (statu quo, coût = infra + édition amortie) :

| Scénario | Revenu/mois (36 mois : one-shot + MRR B2B) | Coût/mois (infra + édition amortie) | Solde/mois |
|---|---|---|---|
| Prudent | ~4 € + ~50 € ≈ **~54 €** | ~5-20 € | **positif (~+35 à +50 €)** |
| Base | ~78 € + ~500 € ≈ **~580 €** | ~20-60 € | **positif (~+520 €)** |
| Ambitieux | ~610 € + ~3 000 € ≈ **~3 610 €** | ~60-120 € | **positif (~+3 500 €)** |

**Régime B — Avec équipe (RH valorisé), ambition mobile + multi-édition + B2B** :

| Scénario | Revenu/mois (36 mois) | Coût/mois (infra + édition + **RH**) | Solde/mois |
|---|---|---|---|
| Prudent | ~54 € | ~5 000 € (solo+1 partiel) | **lourdement négatif** |
| Base | ~580 € | ~7 000-12 000 € (+1 à +2) | **lourdement négatif** |
| Ambitieux | ~3 610 € | ~12 000-18 000 € (+2-3) | **négatif (revenu couvre ~20-30 % du RH)** |

### 5.2 Break-even : à quelle échéance, sous quel format, avec quel scope ?

**Réponse directe, en deux temps :**

1. **En régime solo (RH non valorisé), le break-even est déjà atteint** ou trivial : dès
   les premiers euros de B2C/B2B, le revenu couvre l'infra (€/mois à deux chiffres). **Le
   projet est "viable" comme side-project rentable** dans tous les scénarios, **format
   dominant = B2B** (le seul qui dépasse quelques centaines d'€/mois). Échéance : **dès
   l'activation de la monétisation (~12-24 mois)**, scope **Metz + 1-2 éditions**.

2. **En régime équipe (le sens "entreprise" de la question), le break-even N'est PAS atteint
   à 36 mois dans aucun scénario** de ce modèle. Même l'Ambitieux (~3 600 €/mois) ne couvre
   qu'**une fraction** d'un seul salaire chargé + édition. **Pour qu'une équipe soit
   soutenable, il faut un revenu B2B d'un ordre de grandeur supérieur** :
   ```
   Comptes B2B pour couvrir 1 ETP (~6 000 €/mois) ≈ 6 000 / prix_B2B
     = 120 comptes à 50 € | 60 à 100 € | 30 à 200 €
   ```
   Atteindre **~30-60 comptes B2B** (vs 5-20 en Ambitieux) suppose une **traction B2B
   structurée** (commercial dédié, plusieurs éditions actives) — non démontrée par ce modèle
   à 36 mois. **Échéance break-even équipe : au-delà de 36 mois**, conditionnée à une montée
   B2B forte, scope **≥ 3 éditions Alsace-Moselle**.

| Question centrale | Réponse (fourchette, pas un point) |
|---|---|
| **Peut-elle faire de l'argent ?** | **Oui, mais peu en absolu.** B2B = quelques centaines à ~3 000 €/mois à 36 mois (Base→Amb.). B2C seul = négligeable. Pub/cookies = à écarter. |
| **À quelle échéance ?** | **Rentable solo : ~12-24 mois** (dès monétisation). **Rentable avec équipe : > 36 mois**, non garanti. |
| **Sous quel format ?** | **B2B white-label** (le seul à fort LTV) ; B2C one-shot en appoint ; premium mobile au moment du push. |
| **Avec quel scope ?** | **Side-project rentable** dès Metz + 1 édition. **Entreprise** : exige ≥ 3 éditions + montée B2B forte, au-delà de l'horizon modélisé. |

> **Le résultat le plus important du business case.** Le projet est **structurellement un
> excellent side-project** (coûts quasi nuls, marge sur chaque euro encaissé) et un
> **pari d'entreprise difficile** (le revenu plafonne loin sous le coût d'une équipe). La
> bascule solo→équipe est le **vrai point de décision financier**, pas la monétisation
> elle-même. **Ne pas embaucher avant que le revenu B2B prouve une pente vers ~30+ comptes.**

---

## 6. Le pari « reste de la France » (Phase 4 — à instruire, pas à acter)

### 6.1 Pourquoi c'est un pari de nature DIFFÉRENTE

Tout le cœur d'expansion (Metz → Thionville → Strasbourg → Alsace) est en **zone hors-DVF**
[source: DVF-couronne.md §0]. Conséquence stratégique majeure (insight dominant du brief) :

| | **Cœur Alsace-Moselle (hors-DVF)** | **Reste de la France (DVF public)** |
|---|---|---|
| Accès concurrents aux transactions | **Aucun** (DVF exclut 57/67/68 ; Livre Foncier fermé) | **Oui** (MeilleursAgents, SeLoger, Patrim ont DVF) |
| Origine de la doctrine produit | **Native et authentique** : « pas de DVF, données observables » est née de la contrainte | **Importée** : la contrainte n'existe pas → la doctrine devient un choix, pas une nécessité |
| Différenciateur | « **on reconstruit ce que personne ne voit** » — difficilement attaquable | « **on n'estime pas, on vérifie une cohérence + usage terrain** » — attaquable |
| Nature du moat | **Data + doctrine** | **UX / terrain / anti-estimation** uniquement |

> Le moat data **disparaît** hors zone : tout le monde a DVF. Ce qui reste défendable, c'est
> le **pari UX/terrain** que le fondateur défend : (a) même là où DVF/Livre Foncier existe,
> **tout le monde ne le consulte pas** ; (b) l'**usage mobile/terrain** (en visite, devant
> une vitrine) a une valeur propre, indépendante de la donnée de transaction. Le « reste de
> la France » est donc un **pari produit (UX/terrain)**, pas une réplication du moat.

### 6.2 GO / NO-GO conditionnel

**NO-GO par défaut** comme **réplication du moat data** (il n'existe pas hors zone).

**GO conditionnel** comme **pari terrain mobile**, si et seulement si, AVANT d'ouvrir :
1. la **Vague B (mobile)** est livrée et l'usage **terrain** est mesuré comme significatif
   (events : géoloc, OCR vitrine, partage natif) — pas un usage desktop copier-coller ;
2. au moins **une édition Alsace-Moselle est rentable** (preuve que le playbook tient même
   là où le moat data existait) — Gate G4 ;
3. on accepte que, hors zone, le produit se positionne en **« vérificateur de cohérence +
   compagnon de visite »**, pas en « révélateur d'un marché invisible » (le hero ne ment
   pas : DVF-couronne.md §4 prévient le glissement vers l'estimateur) ;
4. le coût par édition (gazetteer + scrapers + marque, §4.2) est **soutenable à l'échelle
   de centaines de bassins** — ce qui est douteux en l'état (le scraping par bassin ne
   scale pas manuellement ; cf. §7).

### 6.3 Ce qu'il faudrait prouver d'abord

- Que l'**usage terrain mobile** crée de la valeur *là où DVF existe* (test : une édition
  pilote hors zone, par ex. un bassin frontalier comparable, mesurée sur l'usage natif).
- Que le **coût par édition s'industrialise** (gazetteer + POI semi-automatisés, sinon le
  modèle ne passe pas à l'échelle France).
- Que le **différenciateur anti-estimation** résiste face à des acteurs qui *ont* la donnée
  et peuvent ajouter une couche « cohérence » par-dessus DVF.

> **Tranché honnêtement.** Le « reste de la France » est le **scope le plus large et le plus
> incertain**. Il ne doit **pas** être acté maintenant. C'est un **pari produit (terrain)**
> à instruire **après** preuve de rentabilité Alsace-Moselle, et il change la nature du
> produit (de « moat data » à « moat UX »). Le sizing dit que le TAM y est ~20× plus grand
> (~7,6 M moments/an) ; mais le TAM n'est pas le moat, et c'est le moat qui paie.

---

## 7. Risques structurants

| # | Risque | Gravité | Mitigation / lecture |
|---|---|---|---|
| R1 | **Anti-bot LBC/portails** : l'ingestion d'URL grands portails échoue (FORECAST `taux_échec`) | Élevée | WebView on-device en mobile (mobile-app-ANALYSE §4) ; sur web, rester sur sites non protégés |
| R2 | **Faible fréquence B2C** : un acheteur tous les ~7-10 ans → rétention structurellement basse (FORECAST §2.4) | Élevée | Privilégier B2B (récurrence) ; B2C en one-shot, jamais en pilier récurrent |
| R3 | **Dépendance scraping pour densifier chaque édition** : recon Metz = 0 candidate (CONTEXT §0) ; DVF nul sur tout le cœur (DVF-couronne §0) | **Critique** | Risque de **faisabilité par édition** : sans sources scrapables, le pilier prix retombe sur « Indéterminé ». À tester AVANT chaque ouverture (intègre la gate) |
| R4 | **Cap d'architecture push/auth** : passage outil anonyme → produit avec état (PII, pHash, persistance) | Élevée | Décision produit assumée (mobile-app-ANALYSE §6-§7) ; livrer A (re-check même annonce) avant C (radar crowdsourcé) |
| R5 | **Tension marque vs pub/cookies** : la sobriété/neutralité est le différenciateur (REBRAND §3-§7) | Élevée | Écarter pub et cookies retargeting (§3.6) ; B2B = transparence, pas survente |
| R6 | **Exécution solo** : multi-édition + mobile + B2B dépasse la capacité d'un fondateur seul | Élevée | C'est le déclencheur RH (§4.4) ; mais embaucher casse la rentabilité (§5) → tension centrale du projet |
| R7 | **Volume local sur-estimé** : proxy national appliqué à une Alsace-Moselle en repli -20/-34 % (§1.3) | Moyenne | Lire les bassins en haut de fourchette ; obtenir le volume notaires local (§8) |
| R8 | **Glissement vers l'estimateur** hors zone DVF (§6) | Moyenne | Garde-fous G1-G7 de DVF-couronne §5 ; ne pas réécrire le hero « observable » |

---

## 8. Synthèse exécutive + registre d'hypothèses + à vérifier

### 8.1 Synthèse exécutive

- **Peut-elle faire de l'argent ?** Oui, mais **modestement en absolu**. Le seul format qui
  dépasse quelques centaines d'€/mois est le **B2B white-label** ; le B2C (one-shot ou
  freemium) reste un appoint à cause de la faible fréquence d'usage ; **pub et cookies sont
  à écarter** (revenu négligeable, coût de marque disproportionné).
- **À quelle échéance ?** **Rentable en régime solo : ~12-24 mois** (l'infra est négligeable,
  chaque euro encaissé est marge). **Rentable en régime équipe : au-delà de 36 mois et non
  garanti** — le revenu plafonne loin sous le coût d'un seul salaire.
- **Avec quel scope ?** **Side-project rentable** dès Metz + 1 édition ; **entreprise**
  seulement avec ≥ 3 éditions Alsace-Moselle ET une montée B2B forte (~30-60 comptes).
- **Le moat est géographique** : il vit dans la zone hors-DVF (57/67/68) où personne n'a la
  donnée. Hors de cette zone, le « reste de la France » est un **pari UX/terrain différent**,
  à instruire plus tard, pas le même produit.

### 8.2 Les 3 paris les plus structurants

1. **Le pari B2B** : que des agences/courtiers paient 50-200 €/mois un outil de
   *transparence* (et que le risque de posture « vendre au vendeur un outil pro-acheteur »
   se neutralise). C'est le seul chemin vers un revenu non négligeable.
2. **Le pari "édition reproductible"** : qu'on puisse répliquer Metz à Thionville/Strasbourg
   **sans** ré-investir un effort marketing/data complet à chaque fois — et surtout **en
   trouvant des sources scrapables** par bassin (le point le plus fragile : recon Metz = 0).
3. **Le pari solo→équipe** : que la traction B2B prouve une pente vers ~30+ comptes **avant**
   d'embaucher. Embaucher trop tôt transforme un side-project rentable en entreprise
   déficitaire (§5).

### 8.3 Les 3 données manquantes les plus bloquantes

1. **[CRITIQUE] Trafic réel actuel** (aucune analytics — FORECAST §10 #1). Tout numérateur
   de revenu en dépend. **Bloque tout.** → installer l'instrumentation (FORECAST §7).
2. **[FORT] Volume de transactions par bassin** (Thionville, Strasbourg Eurométropole, 67,
   68) : seuls des **taux d'évolution** ont été trouvés (repli -20/-34 %), **aucun volume
   absolu local**. Le sizing §1 repose sur un proxy national qui sur-estime probablement une
   Alsace-Moselle en repli. → bilans Chambres des notaires Bas-Rhin/Haut-Rhin/Moselle.
3. **[FORT] Faisabilité scraping par édition** : existe-t-il, dans chaque nouveau bassin, des
   agences scrapables pour densifier les comparables (le pilier prix) ? La recon couronne
   messine a retenu **0 candidate** et DVF est **nul** sur tout le cœur Alsace-Moselle. Sans
   réponse, le coût par édition (§4.2) et la faisabilité même d'une édition (R3) sont
   indéterminés. → recon source par bassin avant chaque gate.

### 8.4 Registre d'hypothèses (en plus de celles héritées du FORECAST)

| # | Hypothèse | Valeur retenue | Impact si fausse | Comment tester |
|---|---|---|---|---|
| B1 | Proxy national applicable aux bassins (trans ≈ pop × 1,44 %) | base | déplace tout le sizing §1 | volume notaires local par bassin |
| B2 | Alsace-Moselle en repli → base = haut de fourchette | -20/-34 % en 2023 [source] | sur/sous-estime SAM | volume notaires local récent |
| B3 | `taux_achat_dossier` 0,5-5 % | base 2 % | déplace revenu B2C one-shot | test de prix après monétisation |
| B4 | Comptes B2B 1-20 à 36 mois | base 5 | déplace MRR (format dominant) | pilote B2B réel |
| B5 | Coût par édition ~10-22 j-h + scrapers récurrents | [HYPOTHÈSE] | déplace le P&L régime solo | 1 édition réelle (Thionville) |
| B6 | RH chargé ~6 000 €/mois/ETP | [HYPOTHÈSE FR] | déplace le break-even équipe | devis/recrutement réel |
| B7 | Revenu pub négligeable à ce trafic (RPM 1-5 €) | [HYPOTHÈSE] | si faux, pub reconsidérable (peu probable) | régie display test |
| B8 | Usage terrain mobile a une valeur hors zone DVF | [HYPOTHÈSE — pari §6] | conditionne le GO Phase 4 | édition pilote hors zone mesurée |
| B9 | Appétit mobile (part trafic mobile ≥ 40 %) | [HYPOTHÈSE — gate G2] | conditionne la Vague B | analytics (part mobile) |

### 8.5 À vérifier — ordonné par impact

1. **[CRITIQUE] Installer l'instrumentation** (FORECAST §7) → trafic et funnel réels.
   Bloque tout calcul de revenu. [B-trafic, héritée FORECAST §10 #1]
2. **[FORT] Volume de transactions par bassin** (notaires 67/68/57, EPCI). Resserre §1. [B1, B2]
3. **[FORT] Faisabilité scraping/densification par édition** (recon source par bassin). Sans
   elle, le coût et la faisabilité par édition sont indéterminés. [B5, R3]
4. **[FORT] Signal B2B** (utilisateurs à fort volume = proxy pro, FORECAST §7) → valide le
   format dominant et le pari R1/B4. [B4]
5. **[MOYEN] Appétit mobile** (part de trafic mobile) avant d'investir la Vague B. [B9, gate G2]
6. **[MOYEN] Coût RH réel** et seuil d'embauche soutenable (lien direct au break-even équipe). [B6]
7. **[MOYEN] Périmètre exact EPCI Thionville/Sillon Nord** (éviter double comptage avec Moselle). [§1.2]
8. **[FAIBLE→PARI] Valeur terrain hors zone DVF** — à n'instruire qu'après rentabilité
   Alsace-Moselle (édition pilote mesurée). [B8, §6]

---

> Fin du modèle. Le fondateur valide à une gate dédiée. **Aucune décision n'est prise ici** :
> ce business case met côte à côte les scénarios, pose les formules et les gates, et tranche
> seulement là où c'est utile (pub/cookies écartés, B2B comme seul format à fort revenu,
> break-even solo vs équipe). Le fondateur décide du scope, du format et du moment d'embauche.

---

## Sources web consultées (session 2026-06-23)

- [INSEE — Comparateur EPCI Portes de France-Thionville (245701362)](https://www.insee.fr/fr/statistiques/1405599?geo=EPCI-245701362) ; [Dossier commune Thionville (57672)](https://www.insee.fr/fr/statistiques/2011101?geo=COM-57672)
- [INSEE — Eurométropole de Strasbourg (246700488)](https://www.insee.fr/fr/statistiques/2011101?geo=EPCI-246700488) ; [Eurométropole — Wikipédia](https://fr.wikipedia.org/wiki/D%C3%A9mographie_de_Strasbourg)
- [INSEE — Département Bas-Rhin (67)](https://www.insee.fr/fr/statistiques/2011101?geo=DEP-67) ; [Haut-Rhin (68)](https://www.insee.fr/fr/statistiques/2011101?geo=DEP-68)
- [Notaires de France — Bilan immobilier 2025 / tendances 2026](https://www.notaires.fr/fr/bilan_immobilier_annuel) ; [Immo Matin — 945 000 transactions 2025 / 958 000 fin fév. 2026](https://www.immomatin.com/evaluation/services-evaluer/notaires-de-france-958-000-transactions-11-transactions-sur-un-an-une-reprise-sans-exces.html)
- [Chambre des notaires Bas-Rhin — statistiques](https://chambre-bas-rhin.notaires.fr/statistiques-analyses) ; [France Bleu — bilan notaires Alsace-Moselle 2023-2024 (-20/-34 %)](https://www.francebleu.fr/emissions/l-eco-d-ici-de-france-bleu-lorraine-nord/les-notaires-d-alsace-et-de-moselle-dressent-le-bilan-du-secteur-immobilier-pour-2023-2024-7225791) ; [cir-colmar-metz — état des lieux 2023-2024](https://cir-colmar-metz.notaires.fr/actualite/marches-immobiliers-etat-des-lieux-2023-2024)

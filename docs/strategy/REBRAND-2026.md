# Rebrand 2026 — concilier autorité notariale locale et crédibilité « tech robuste »

> Mémo stratégique pour le fondateur (Mathieu). Draft à valider — je ne tranche
> rien à ta place, je propose et je vote. Périmètre : surface d'entrée (home,
> logo, hero, wording, motion). Ne touche pas au produit (score 40/30/30,
> anti-fausse-précision, anti-fausse-preuve-sociale).
>
> Note de méthode sur les sources : l'environnement bloque le fetch direct de
> `anthropic.com`, `openai.com`, `netflix.com`, `meta.com`, `aws.amazon.com`
> (403 / anti-bot) et plusieurs articles (403). Les affirmations sur ces sites
> sont donc soit `[source: …]` (vérifiées en recherche web), soit
> `[CONNAISSANCE — cutoff jan. 2026, à revérifier en live]`. Aucune n'est un
> chiffre nu inventé. Tout ce qui touche notre propre repo est `[repo]`.

---

## 1. Diagnostic de la home actuelle — ce qui dit « garage » vs « robuste »

Lecture du code réel (`frontend/app/page.tsx`, `components/design/Footer.tsx`,
`Design System/README.md`).

### Signaux « local crédible » — à conserver (c'est le capital)

- **Micro-géographie nommée** : H1 et sous-titre citent Sablon, Queuleu,
  Devant-les-Ponts, Outre-Seille `[repo: page.tsx L742-762]`. C'est l'ancrage le
  plus fort et le plus sobre qui existe — un national ne peut pas l'imiter.
- **L'aveu du livre foncier** (« le livre foncier n'est pas public… »)
  `[repo: page.tsx L756]` : pose un problème réel, signale une expertise de
  terrain. À garder.
- **Registre éditorial-notarial** : Instrument Serif, parchemin, encre, brick,
  pas d'emoji, vouvoiement. C'est cohérent et distinctif. À garder.
- **Bloc « local > national »** `[repo: page.tsx L258-307]` : argument de
  positionnement honnête (ville vs quartier). Bon.

### Signaux « garage » — à corriger

1. **La photo prend tout l'espace mobile.** `PhotoBand` fait
   `clamp(200px, 32vh, 360px)` AVANT tout texte `[repo: page.tsx L153]` : sur un
   écran de 700 px, ~1/3 du premier viewport est une image d'ambiance muette,
   avant même le H1. C'est le point que tu cites, et il est réel.
2. **Le hero est en réalité un placeholder qui s'avoue.** `HERO_IMAGE` pointe
   `/hero-metz.jpg` mais `HERO_CREDIT = "Illustration"` `[repo: page.tsx L133-137]`.
   Afficher le mot « Illustration » en bas d'un hero = dire « ce n'est pas une
   vraie photo ». Aucun grand acteur n'avoue son placeholder. Signal garage net.
3. **Le sceau aux 3 alérions ne se lit pas.** `LorraineSeal` size 88 en
   letterhead `[repo: page.tsx L728]`, et la doc reconnaît elle-même qu'à 20 px
   « ailes/corps se confondent » et que l'alérion est « peu connu du grand
   public » `[repo: LOCAL-ANCHORING.md L37-41, METZ-LOCAL.md L36]`. Un logo que
   l'auteur doit expliquer n'est pas un logo : c'est un blason privé.
4. **Le footer affiche le mot « MVP ».** « MVP · Metz / Moselle uniquement »
   `[repo: Footer.tsx L20]`. « MVP » dit littéralement « produit minimum,
   inachevé, garage ». À retirer de la surface publique (le garder en interne).
5. **Contradiction de promesse de fiabilité.** Le footer dit « Analyses non
   conservées » `[repo: Footer.tsx L26]` alors que la home instrumente
   `page_view`, `analysis_started`, etc. `[repo: page.tsx L543-569]`. Ce n'est
   pas un mensonge (les events sont anonymisés, pas l'analyse), mais c'est
   ambigu et fragilise la crédibilité « sérieux ».
6. **Aucune preuve de robustesse n'est visible.** Pas un chiffre sur la
   profondeur de données (la base fait pourtant ~17,7k comparables
   `[repo: CONTEXT.md §0]`), pas de mention de méthode au-dessus de la ligne de
   flottaison, pas de signal de disponibilité. Le travail d'infra sérieux
   (5 scrapers, CI, évals, staging-first `[repo: CONTEXT.md §0]`) est totalement
   invisible côté entrée.

**Synthèse du diagnostic :** le « garage » ne vient PAS du style éditorial (qui
est un atout). Il vient de quatre détails qui s'excusent (« Illustration »,
« MVP », sceau illisible, photo muette qui mange le mobile) et de l'**absence de
preuve chiffrée** au-dessus de la ligne de flottaison. On peut tout corriger
sans renier la charte.

---

## 2. Benchmark — comment les grands signalent échelle / modernité / fiabilité

Pour chaque acteur : ce qu'il fait sur sa surface d'entrée, puis **1-2
mécanismes transférables** à Cohérence (transposés, pas copiés — on reste
éditorial).

### Anthropic
- **État 2026** : pas de refonte majeure de la home identifiée ; le mouvement
  produit notable est le lancement de **Claude Design** (17 avril 2026), sur
  Claude Opus 4.7 `[source: buildfastwithai / digital4design, 2026]`. Registre
  de marque connu : palette chaude (off-white / « clay » / coral), serif
  éditorial (Styrene/Tiempos-like), beaucoup de blanc, peu de motion, sobriété
  assumée `[CONNAISSANCE — cutoff jan. 2026, à revérifier en live]`.
- **Mécanisme transférable n°1 — la sobriété chaude EST le signal de sérieux.**
  Anthropic prouve qu'on peut être à la frontière tech tout en refusant le
  néon/gradient/dark-mode SaaS. C'est exactement notre pari : notre parchemin +
  serif n'est pas un handicap « old », c'est le même registre « adulte, calme,
  sûr de lui » qu'Anthropic. **Conclusion forte : ne pas moderniser en allant
  vers le SaaS bleu — moderniser en allant vers Anthropic.**
- **Mécanisme n°2 — le wording pose une posture, pas un bénéfice.** Pas de
  « boostez », mais des phrases déclaratives calmes. On a déjà ce ton ; il faut
  juste le rendre plus affirmé (cf. §5).

### OpenAI
- **État 2026** : leurs guidelines de pages de marque (publiées via
  developers.openai.com) disent que **le hero doit être edge-to-edge sans
  gouttières héritées**, que **le nom de marque doit être un signal de niveau
  hero**, et que **« si le premier viewport pouvait appartenir à une autre marque
  une fois la nav retirée, le branding est trop faible »**
  `[source: WebSearch — OpenAI showcase / developers.openai.com, 2026]`.
- **Mécanisme transférable n°1 — le test du « viewport anonyme ».** Applique-le à
  notre home : retire la nav, reste-t-il quelque chose qui ne pourrait être que
  Cohérence-édition-Metz ? Aujourd'hui : à moitié (les quartiers oui, le sceau
  non). À renforcer.
- **Mécanisme n°2 — hero pleine largeur structurant.** Notre `PhotoBand` est
  edge-to-edge, c'est bon ; le problème n'est pas la largeur mais qu'elle soit
  *muette* et *avant le texte* sur mobile (cf. §6).

### Netflix
- **État 2026** : home = **hero full-bleed** (visuel d'un titre tendance) +
  header logo/sign-in + un **unique champ email « Get Started »** répété, FAQ,
  features `[source: Raw.Studio, babich.biz — analyses UX 2026]`.
- **Mécanisme transférable n°1 — une seule action, répétée.** Netflix ne propose
  qu'UNE chose à faire : entrer son email. Nous : une seule chose, **analyser une
  annonce**. Le champ `AnalyzerInput` doit être le héros incontestable du premier
  viewport, pas la photo. Sur mobile surtout.
- **Mécanisme n°2 — le visuel sert l'action, il ne la précède pas.** Chez
  Netflix l'image EST le produit. Chez nous l'image n'est PAS le produit (le
  produit est l'analyse) → elle doit donc reculer, pas dominer.

### Meta
- **État 2026** : wordmark sans-serif custom à terminaisons douces, introduit en
  2019, pensé « du plus petit usage in-app jusqu'au métavers »
  `[source: design.facebook.com / designatmeta, Medium]`. Logo = **wordmark
  lisible**, pas un blason abstrait.
- **Mécanisme transférable n°1 — un wordmark se lit, un emblème s'explique.**
  Meta a abandonné l'idée d'un symbole cryptique au profit d'un mot lisible.
  Notre logo doit faire pareil : « Cohérence » en mots, l'alérion devient un
  *détail de signature*, jamais le porteur d'identité (cf. ton problème de sceau).
- **Mécanisme n°2 — un système qui scale (in-app → grand format).** Meta a conçu
  son identité pour fonctionner à toutes les tailles. C'est exactement notre
  besoin « édition Metz → Nancy → Luxembourg » : un système, pas un blason figé.

### Amazon / AWS
- **État 2026** : la crédibilité enterprise d'AWS repose sur l'empilement de
  **signaux de confiance au-dessus de la ligne de flottaison** : logos clients
  reconnaissables, badges de conformité (SOC 2, GDPR), notes G2/Capterra, métrique
  de ROI. Best practice citée : **exactement trois signaux above-the-fold (un
  badge sécurité, une note, un logo reconnu)** pour créer la confiance sans
  encombrer `[source: saashero.net, webstacks.com, site123 — 2026]`.
- **Mécanisme transférable n°1 — trois preuves, pas trente.** On n'a pas de logos
  clients (et on n'en inventera pas, cf. §4). Mais on a des **chiffres réels** :
  nombre de comparables, nombre de quartiers couverts, fréquence de collecte. Une
  bande de **trois faits chiffrés** sous le hero = le mécanisme AWS, version
  honnête.
- **Mécanisme n°2 — la fiabilité se signale par la conformité affichée.** Notre
  équivalent : une ligne « données collectées chaque semaine · périmètre dépt 57 ·
  méthode publique » — la transparence comme badge de sérieux.

**Fil rouge du benchmark :** les grands ne signalent pas « moderne » par des
gradients ou de l'animation. Ils le signalent par (a) **une action unique et
dominante**, (b) **un nom/logo lisible**, (c) **trois preuves chiffrées
above-the-fold**, (d) **une sobriété assumée**. Tout cela est compatible avec
notre charte. Aucun n'exige d'abandonner le serif ni le parchemin.

---

## 3. Recommandation de positionnement — la phrase-pivot

La tension « artisanal local vs tech moderne » est **fausse**. Le bon antonyme
de « notarial » n'est pas « moderne », c'est « bâclé ». Le bon antonyme de
« tech robuste » n'est pas « local », c'est « bricolé ». Les deux registres
convergent vers le **même** axe : *le sérieux*. Un notaire ET une infra fiable
disent la même chose — « vous pouvez vous reposer là-dessus ».

> **Phrase-pivot : « La rigueur d'une étude notariale, servie comme une
> infrastructure moderne. »**
>
> Autrement dit : on ne choisit pas entre l'autorité du papier et la fiabilité
> de la machine — la modernité, chez nous, c'est de rendre la rigueur
> *systématique, transparente et toujours disponible*, pas de la rendre clinquante.

Conséquence opérationnelle : on module la modernité par la **précision, la
preuve et la disponibilité**, jamais par l'effet visuel. Anthropic est la
boussole, pas Netflix. (Netflix nous sert pour la *structure d'action*, pas pour
le *style*.)

---

## 4. Leviers de crédibilité activables SANS fabriquer de preuve

Garde-fou repo : la promesse ne dépasse jamais la maturité de la donnée
`[repo: LOCAL-ANCHORING.md L21-23]` ; pas de fausse précision
`[repo: CONTEXT.md §1.4]`.

### Activables tout de suite (preuve réelle)
- **Chiffres de profondeur de données**, above-the-fold : « ~17 700 comparables
  messins » / « 16 quartiers » / « collecte hebdomadaire »
  `[repo: CONTEXT.md §0]`. Chiffres avant adjectifs — c'est déjà ta doctrine.
  *À valider : afficher un chiffre rond « 17 000+ » et le brancher sur une vraie
  source (endpoint count) pour qu'il ne se périme pas.* `[HYPOTHÈSE — à valider]`
- **Preuve de méthode** : remonter le lien « Notre méthode locale » de tout en
  bas vers le premier écran. La transparence de la méthode EST le badge de
  sérieux (mécanisme AWS transposé).
- **Transparence de périmètre** : « Metz & Moselle, dépt 57 » assumé comme une
  *spécialisation*, pas une limite. Reformuler « uniquement » (qui s'excuse) en
  « édition Metz » (qui revendique).
- **Signal de méthode anti-bullshit** : « Nous n'estimons pas un prix. Nous
  vérifions une cohérence. » — cette retenue est un signal de sérieux rare dans
  l'immo. À mettre en avant, pas en disclaimer de bas de page.

### Activables avec un peu de travail
- **SLO de disponibilité visible** (page statut, ou simple « disponible 24/7 »)
  — crédible seulement si l'uptime suit. Attention : Fly auto-stop = cold start
  `[repo: CONTEXT.md §0]`. Ne pas promettre d'instantanéité tant que le réveil
  de VM est lent. `[HYPOTHÈSE — à valider : mesurer le p95 de cold start]`

### À NE PAS faire (fabriquerait de la fausse preuve — interdit)
- **Logos clients / « Ils nous font confiance »** : on n'a pas de clients
  payants `[repo: CONTEXT.md §3.1]`. Mettre des logos = mensonge. **Proscrit.**
- **« Noté 4,8/5 par X utilisateurs »** : le feedback existe `[repo: 9.7]` mais
  le volume est quasi nul. Pas de note publique tant que N n'est pas significatif.
- **« Utilisé par des milliers d'acheteurs »** : trafic quasi nul
  `[repo: CONTEXT.md §9]`. **Proscrit.**
- **Témoignages** : aucun réel disponible → ne pas en inventer.
- **Badges de conformité (SOC 2…)** : non certifié. Ne pas afficher.

Règle simple : on peut afficher tout ce qui décrit **notre méthode et notre
donnée** (vrai, vérifiable) ; on n'affiche rien qui décrive **notre traction**
(faux à ce stade).

---

## 5. Direction wording — H1 / eyebrow / sous-titre alternatifs

Contraintes respectées : vouvoiement, chiffres avant adjectifs, pas d'emoji, pas
de « GO !/Découvrir », registre notarial. Trois propositions, plus affirmées que
l'actuel (« Ce prix… sont-ils cohérents… ? »).

### Proposition A — « l'expertise locale chiffrée » (sobre-évolutive)
- **Eyebrow** : `Édition Metz · Moselle`
- **H1** : « Le marché immobilier messin, lu *quartier par quartier*. »
- **Sous-titre** : « Collez une annonce. Nous la confrontons à ~17 000
  comparables réels — du Sablon à Queuleu — et vous disons ce qui est cohérent,
  ce qui est à creuser, et les questions à poser avant la visite. »
- *Force* : affirmatif, chiffré, ancré. *Risque* : faible.

### Proposition B — « le second avis, scellé » (autorité notariale)
- **Eyebrow** : `Analyse de cohérence · Metz & Moselle`
- **H1** : « Avant de signer, un *second avis* sur l'annonce. »
- **Sous-titre** : « Une lecture méthodique de ce que l'annonce dit, de ce
  qu'elle tait, et de son prix face au marché du quartier. Sans estimation
  hasardeuse : nous vérifions la cohérence, nous ne devinons pas un prix. »
- *Force* : assume le positionnement « notaire » + l'anti-fausse-précision comme
  argument. *Risque* : « second avis » déjà connu, moins neuf.

### Proposition C — « l'asymétrie corrigée » (audacieuse-moderne)
- **Eyebrow** : `Metz · données du marché réel`
- **H1** : « Le vendeur connaît le marché. *Désormais, vous aussi.* »
- **Sous-titre** : « Le livre foncier n'est pas public. Nous reconstituons le
  marché messin à partir des annonces réelles, quartier par quartier, et plaçons
  la vôtre dans ce contexte — score de cohérence, trois piliers, points à
  vérifier. »
- *Force* : tension narrative (asymétrie d'information), très moderne sans emoji.
  *Risque* : le plus « marketing » des trois — surveiller qu'il ne glisse pas
  vers le combatif (la charte veut du calme).

**Mon vote wording : A en H1, avec le sous-titre de C.** A donne l'autorité
chiffrée, le sous-titre de C donne la raison d'être (asymétrie + livre foncier)
sans le ton combatif du H1 de C.

---

## 6. Directions créatives — 3 pistes nommées pour previews

Chacune décrite par : logo, hero/mobile, palette/motion, wording. Toutes
respectent la charte (pas de bleu, pas de gradient SaaS, pas d'emoji, serif +
mono pour les chiffres).

### Direction 1 — « Le Cadastre » (sobre-évolutive, faible risque)
*L'évolution propre de l'existant, sans rupture.*
- **Logo** : wordmark « Cohérence » en Instrument Serif + un **point/losange
  brick** comme seule marque (on retire l'alérion de l'identité primaire ; il
  survit en filigrane sur le PDF/print uniquement). Lisible à 16 px.
- **Hero / mobile** : on **inverse l'ordre** — H1 + champ d'analyse d'abord,
  photo réduite à une **bande fine signature** (~120 px) OU déplacée plus bas. Sur
  mobile, zéro image avant le premier H1. La photo devient un **filet
  horizontal** N&B, pas un bloc de 32vh.
- **Palette / motion** : palette actuelle inchangée. Motion : on garde
  uniquement le remplissage de l'anneau de score. Ajout discret : une **ligne de
  règle qui se trace** sous le H1 au chargement (cohérent « éditorial »).
- **Wording** : Proposition A.
- *Pour qui* : si tu veux livrer vite et sans risque de casser l'acquis.

### Direction 2 — « L'Étude » (équilibre, mon vote)
*Notarial assumé + preuve chiffrée à la AWS + structure d'action à la Netflix.*
- **Logo** : wordmark « Cohérence » + sous-marque « édition Metz » en mono. Le
  **sceau alérion** est requalifié : il n'est plus un logo, il devient un
  **cachet de validation** posé sur le rapport/PDF (là où un sceau a un sens) et
  sur le favicon grand format. Jamais comme porteur d'identité dans le header.
- **Hero / mobile** : structure en **trois étages** above-the-fold —
  (1) eyebrow + H1 + sous-titre, (2) **le champ d'analyse, dominant** (héros
  réel, façon Netflix « une seule action »), (3) **bande de 3 preuves chiffrées**
  (« ~17 000 comparables · 16 quartiers · collecte hebdomadaire »). La photo N&B
  passe en **arrière-plan très atténué d'une seule section** ou en filet, jamais
  en bloc plein avant le texte. Mobile : H1 → champ → 3 chiffres, aucune image
  bloquante.
- **Palette / motion** : parchemin/ink/brick conservés ; le **Jaumont** monte en
  grade comme couleur des chiffres-preuve (le doré = la valeur/la donnée).
  Motion : anneau de score + apparition séquentielle calme des 3 chiffres
  (fade + 8px de translation, ease-paper, pas de spring). Rien de plus.
- **Wording** : H1 = Prop. A, sous-titre = Prop. C, plus la ligne de méthode
  « Nous vérifions une cohérence, nous n'estimons pas un prix. »
- *Pour qui* : c'est la réconciliation directe de la phrase-pivot (§3). Sérieux
  notarial + preuve d'infra, zéro mensonge, zéro folklore, mobile réparé.

### Direction 3 — « La Frontière » (audacieuse-moderne, risque sur l'autorité)
*Le pari « grand et moderne » poussé le plus loin compatible avec la charte.*
- **Logo** : wordmark serif + traitement **éditorial fort** (gros corps, contraste
  ink/parchemin, type comme image). Pas de symbole du tout.
- **Hero / mobile** : **type-as-hero** — un très grand H1 serif occupe le premier
  écran (façon manchette de quotidien), le champ d'analyse juste dessous, **aucune
  photo above-the-fold**. La photo N&B devient une respiration éditoriale en
  milieu de page. Mobile : naturellement excellent (le texte scale, pas d'image).
- **Palette / motion** : parchemin + brick, plus de contraste, plus d'échelle
  typographique. Motion un cran au-dessus : compteur de score qui « compte »,
  règles qui se tracent, chiffres-preuve qui s'incrémentent une fois au scroll.
  Toujours dans `ease-paper`, jamais de bounce.
- **Wording** : H1 = Prop. C.
- *Risque que je signale franchement* : pousser l'échelle et le mouvement
  rapproche du registre « média/agence créative » et peut **diluer l'autorité
  notariale calme** que la charte protège. Le H1 « le vendeur connaît le marché,
  désormais vous aussi » est puissant mais flirte avec le combatif. À tester, à ne
  pas adopter sans voir une preview.

### Mon vote : **Direction 2 — « L'Étude ».**
Motivation : elle résout *littéralement* ta tension (notarial + robuste) via la
phrase-pivot, sans abandonner un seul atout de la charte. Elle corrige les
quatre signaux « garage » du §1 (photo mobile, « Illustration », sceau
illisible, « MVP ») et ajoute la seule chose qui manque vraiment — **la preuve
chiffrée above-the-fold** — en n'utilisant que des chiffres vrais. La D1 est le
repli sûr si le budget/temps manque ; la D3 est le test à faire en preview mais
risquée pour l'autorité.

---

## 7. Avertissements honnêtes (opinions tranchées)

- **« Plus de modernité » ≠ « plus d'animation/gradients ».** Si tu vas vers le
  SaaS bleu animé, tu *perds* la crédibilité, tu ne la gagnes pas : tu ressembles
  alors à 10 000 startups, et l'autorité notariale (ton vrai différenciateur)
  s'évapore. La modernité crédible ici = Anthropic, pas Linear/Vercel néon.
- **Le sceau alérion est un attachement personnel à challenger.** Il est beau et
  documenté, mais ta propre doc admet qu'il ne se lit pas et que le public n'y
  voit rien `[repo: METZ-LOCAL.md L36, LOCAL-ANCHORING.md L37-41]`. Un logo qui
  doit être expliqué travaille contre « robuste/fiable ». Le sauver comme *cachet
  de rapport* (où le sceau a un sens fonctionnel) plutôt que comme logo primaire.
- **Ne fabrique aucune traction.** C'est le garde-fou n°1. Tout chiffre de
  *méthode/donnée* est permis et puissant ; tout chiffre d'*adoption* est interdit
  tant qu'il est faux. C'est aussi ce qui te distingue : tu peux être le seul de
  ton marché à ne pas mentir.
- **Répare le mobile en priorité n°1**, indépendamment de la direction retenue :
  c'est un bug d'UX concret (`PhotoBand` 32vh avant le H1) qui coûte
  immédiatement, alors que le rebrand complet est un chantier.

---

## 8. Registre d'hypothèses

| # | Hypothèse | Statut | Impact si fausse |
|---|---|---|---|
| H1 | La base fait ~17 700 comparables aujourd'hui et le restera (croissant) | `[repo: CONTEXT.md §0]` daté 2026-06-04 — à rafraîchir | Chiffre-preuve faux = perte de crédibilité (l'inverse du but) |
| H2 | 16 quartiers Metz couverts | `[repo: districts.ts]` non recompté ici | Chiffre above-the-fold erroné |
| H3 | La collecte hebdo tourne réellement chaque lundi | `[repo: CONTEXT.md §0 collect.yml]` | « collecte hebdomadaire » deviendrait un mensonge |
| H4 | Cold start Fly acceptable pour promettre une dispo | `[HYPOTHÈSE — à valider]` | Promesse de fiabilité contredite par l'expérience |
| H5 | La photo N&B libre de droits sera bien branchée (pas « Illustration ») | `[repo: page.tsx L137]` non résolu | Reste un signal garage tant que non fait |
| H6 | Le public ne lit pas l'alérion comme un sceau notarial | `[repo: doc auto-admise]` + intuition fondateur | Si faux, on pourrait garder l'alérion en logo |
| H7 | « Anthropic = boussole moderne sobre » | `[CONNAISSANCE jan. 2026]` non revérifiée en live | Direction visuelle à réajuster |

---

## 9. À vérifier — ordonné par impact

1. **Rafraîchir et fiabiliser les 3 chiffres-preuve** (comparables / quartiers /
   fréquence) et idéalement les brancher sur une source vivante (endpoint count)
   avant de les afficher. *Bloquant pour D2/D3.* `[H1, H2, H3]`
2. **Mesurer le p95 de cold start Fly** avant toute promesse de disponibilité.
   `[H4]`
3. **Brancher une vraie photo héro N&B libre de droits** et supprimer le crédit
   « Illustration » (ou retirer la photo above-the-fold). `[H5]`
4. **Revérifier en live** les surfaces d'entrée d'Anthropic / OpenAI / Netflix /
   Meta / AWS (l'environnement bloquait le fetch ici) avant de figer les
   mécanismes transposés. `[H7]`
5. **Décider du sort du sceau alérion** (logo primaire vs cachet de rapport) —
   décision fondateur, idéalement après un test 5 personnes « que voyez-vous ? ».
   `[H6]`
6. **Retirer « MVP » de la surface publique** (footer) — trivial, fort impact
   perception, à faire quelle que soit la direction.
7. **Clarifier la ligne RGPD du footer** (« Analyses non conservées » vs events
   instrumentés) pour qu'elle soit exacte ET rassurante.

---

*Draft. Aucune décision prise à ta place : tu valides la direction (1/2/3), le
wording (A/B/C) et le sort du sceau ; je transforme ensuite la direction retenue
en previews. Mon vote : Direction 2 « L'Étude », H1 = A + sous-titre = C.*

Sources web consultées :
- [buildfastwithai — Claude Design guide 2026](https://www.buildfastwithai.com/blogs/claude-design-anthropic-guide-2026)
- [digital4design — What is Claude Design](https://www.digital4design.com/blog/what-is-claude-design-anthropic/)
- [OpenAI showcase — landing page guidelines](https://developers.openai.com/showcase/coffee-house-landing-page)
- [Raw.Studio — Netflix welcome page UX](https://raw.studio/blog/the-hidden-ux-genius-of-netflixs-new-welcome-page/)
- [babich.biz — Netflix first-time UX review](https://babich.biz/blog/netflix-ux-review/)
- [Design at Meta — designing the Meta brand](https://design.facebook.com/blog/designing-our-new-company-brand-meta/)
- [saashero — landing page trust signals](https://www.saashero.net/design/landing-page-design-trust-signals/)
- [webstacks — trust signals](https://www.webstacks.com/blog/trust-signals)

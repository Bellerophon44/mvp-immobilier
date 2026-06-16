# Metz & Moselle — base de connaissance pour l'ancrage de marque

> Source d'expertise pour toute décision d'ancrage local de **Cohérence**
> (wording, palette, iconographie, photo). À lire avant de toucher à la charte.
> Les faits notoires sont donnés sans réserve ; les points à confirmer sont
> marqués **[à vérifier]**.

L'ancrage local n'est pas une décoration : la donnée de Cohérence est
Metz/Moselle uniquement. Assumer le local, c'est dire la vérité du produit. La
règle d'or est de rester **« héraldique-éditorial »** (sobre, noble, gravé) et
**jamais** « office de tourisme » (mascotte, vitrail coloré, silhouette
cliché). Le design existant a été bâti *contre* le folklore — on le respecte.

---

## 1. La pierre — l'ancrage le plus authentique

- **Pierre de Jaumont.** Calcaire ferrugineux à l'oolithe, d'un **jaune-miel
  doré** caractéristique, extrait au sud de Metz (carrières de Jaumont,
  Malancourt-la-Montagne). C'est la pierre de la **cathédrale Saint-Étienne**
  et de la quasi-totalité de la vieille ville. Metz est surnommée **« la ville
  jaune »** à cause d'elle. *C'est la signature chromatique réelle de Metz.*
- **Conséquence de marque.** La couleur-héros actuelle (`--brick #B5462F`,
  rouge brique) est justifiée dans la charte par « le grès lorrain », mais ce
  n'est pas la couleur de Metz. La couleur juste est l'**or Jaumont**, déjà
  proche de `--ochre`. → token `--jaumont #C9A14A` ajouté à la charte, réservé
  au **cachet « contexte local »**. Le brick reste l'unique accent d'action.
- Nuancier indicatif Jaumont : du miel clair `#D8B468` au doré profond
  `#B98A38` selon l'exposition et la patine. `#C9A14A` est un milieu lisible.

## 2. Héraldique — le registre noble, sans cliché

- **Les alérions de Lorraine.** Armes du duché : *« D'or à la bande de gueules
  chargée de trois alérions d'argent »*. L'**alérion** est un aiglon héraldique
  **sans bec ni pattes**, ailes déployées. Élégant, abstrait, **peu connu du
  grand public** → distinctif sans tomber dans le cliché. Anagramme bien connue :
  *Alérion* ↔ *Loreina/Lorraine* (jeu attribué à la légende ducale).
- **Armes de la ville de Metz.** *« Parti d'argent et de sable »* — écu coupé
  verticalement **blanc et noir**. Les couleurs municipales de Metz sont donc
  le **noir & blanc**… ce qui colle parfaitement au registre encre/parchemin
  déjà en place. La photo héro N&B est, de ce point de vue, *doublement* messine.
- **Croix de Lorraine.** Très reconnaissable mais **connotée** (France Libre,
  WWII, parfois récupérations politiques). → à éviter en grand / en logo.

## 3. Symboles à manier avec prudence (folklore)

- **Le Graoully.** Dragon légendaire de Metz, terrassé par saint Clément.
  Symbole fort et affectif, mais **figuratif et folklorique** → proscrit en
  logo/UI (déclasse le positionnement « second avis sérieux »). Acceptable
  éventuellement en clin d'œil éditorial *textuel* très mesuré, jamais en image.
- **Cathédrale Saint-Étienne** (« la Lanterne du Bon Dieu », l'une des plus
  hautes nefs gothiques, vitraux dont Chagall). Magnifique **en photo N&B**,
  mais **jamais en silhouette-logo ni en vitrail coloré** (couleurs vives + bleu,
  proscrits par la charte).
- **Centre Pompidou-Metz** (toiture en chapeau chinois) : moderne et iconique,
  mais peu raccord avec le registre éditorial/patrimonial. À écarter.
- **Mirabelle de Lorraine** (prune AOC, doré), **grenat du FC Metz** : couleurs
  locales mobilisables comme *accents* éventuels, pas comme symboles centraux.

## 4. Repères géographiques mobilisables (wording)

- **Quartiers de Metz** (déjà dans `frontend/lib/districts.ts`) : Centre-Ville,
  Ancienne Ville, Nouvelle Ville, Les Îles, Sablon, Queuleu, Plantières,
  Bellecroix, Borny, Magny, Vallières, Devant-les-Ponts, La Patrotte,
  Outre-Seille, Grange-aux-Bois, Technopôle.
- **Citer les vrais quartiers est l'arme d'ancrage la plus efficace et la plus
  sobre** : la spécificité micro-géographique signale une connaissance locale
  authentique, sans aucun folklore, et reste dans le registre.
- Lieux photogéniques et reconnaissables : **Porte des Allemands** (le plus
  identifiable et le mieux cadré), cathédrale Saint-Étienne, quartier impérial
  / gare de Metz (néo-roman rhénan), Temple Neuf et le plan d'eau, façades
  Jaumont de la rue Serpenoise / place Saint-Louis (arcades médiévales).

## 5. Le système « édition locale » (décision actée)

Marque **« Cohérence »** géo-neutre et scalable ; chaque marché est une
**« édition »** locale avec son accent dérivé de la pierre locale, sa photo, son
lexique de quartiers. *Édition Metz* aujourd'hui ; demain Nancy (grès rose des
Vosges), Thionville, Luxembourg. Cela permet d'aller à 100 % messin maintenant
sans bloquer l'extension. → cf. `LOCAL-ANCHORING.md`.

## 6. DO / DON'T (mémo rapide)

| ✅ DO | ❌ DON'T |
|---|---|
| Or Jaumont en cachet discret | Rouge brique « vendu » comme couleur de Metz |
| Citer les vrais quartiers | Promettre « rue par rue » (la donnée ne suit pas) |
| Photo N&B chaude, granuleuse (cathédrale, Porte des Allemands) | Silhouette de cathédrale en logo |
| Alérion gravé, trait fin, en cachet | Graoully / dragon figuratif |
| Croix de Lorraine : éviter | Vitrail coloré, dégradés, bleu |
| Noir & blanc = couleurs réelles de Metz | Énergie « fête / terroir / souvenir » |

## 7. Brief pour le graphiste — l'alérion-cachet (évolution prévue)

Le code livre aujourd'hui un **cachet** sobre (anneau de sceau + losange de
marque embossé, en or Jaumont — `Seal` dans `components/design/Icons.tsx`).
**Évolution souhaitée**, à confier à un graphiste : remplacer le losange central
par un **alérion lorrain** stylisé.

Contraintes impératives (registre de la marque) :
- Trait **1,5 px**, sans remplissage, monochrome (s'encre via `currentColor`),
  cohérent avec le set d'icônes existant (`viewBox="0 0 24 24"`).
- Alérion **abstrait et géométrique**, ailes déployées, sans bec ni pattes
  (fidèle à la définition héraldique) ; lisibilité parfaite à 20 px.
- Rendu « gravure de cachet », pas illustration. Aucune couleur héraldique
  pleine (pas d'or/gueules remplis) : c'est un *trait*, encré en `--jaumont`.
- Livrable : un `<path>` propre intégrable dans le composant `Seal`, + le SVG
  source dans `Design System/assets/icons/`.

> **Mise à jour (juin 2026) — réalisé.** L'évolution a été tranchée et livrée en
> prod : la marque primaire n'est plus le cachet, mais un **alérion lorrain
> unique** au trait (`AlerionMark`, source `mark-alerion-single.svg`), encré or
> Jaumont — décision fondateur (« l'alérion donne un sentiment de direction +
> rappel local »). Le cachet aux *trois* alérions (`LorraineSeal`) est retiré de
> l'UI. En parallèle, une piste **« clef de voûte »** (la pierre qui tient l'arc =
> cohérence + robustesse, ancrage messin sans cathédrale) a été explorée en 6
> variantes (`Design System/preview/brand-keystone-clear.html`, vote v2 arc brisé
> gothique) et reste ouverte comme alternative au logo de test.

---

*Faits notoires (pierre de Jaumont, alérions de Lorraine, armes de Metz parti
d'argent et de sable, Graoully, surnom « ville jaune ») ; détails de carrières
et nuanciers exacts **[à vérifier]** avant impression / supports print.*

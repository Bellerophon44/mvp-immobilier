# Ancrage local — décisions & roadmap

Décisions arrêtées avec le fondateur (juin 2026) sur la façon de refléter
l'ancrage messin de **Cohérence**. Base d'expertise : [`METZ-LOCAL.md`](./METZ-LOCAL.md).

## Arbitrages

| Question | Décision |
|---|---|
| Horizon d'expansion | **Metz d'abord, extension prévue** → système « édition locale », marque géo-neutre. |
| Intensité visuelle | **Éditorial-local** (le milieu) : wording + nudge palette Jaumont + photo N&B + cachet sobre. Pas d'identité folklorique. |
| Authenticité | Ancrage **humain assumé dans le copy** ; pas encore de photo → brief photo ci-dessous. |

## Principe directeur

À fond sur le local, mais en **héraldique-éditorial**, jamais « office de
tourisme ». Le levier à plus fort ROI est le **wording** (≈ 80 % de l'effet, coût
et risque quasi nuls) ; le graphisme reste un nudge sobre.

**Garde-fou (important) :** la promesse marketing ne doit pas dépasser la
maturité de la donnée. L'affinage par quartier retombe souvent sur « trop peu de
comparables » (cf. `frontend/app/page.tsx`). → On promet **« quartier »**, jamais
**« rue par rue »**, tant que la donnée n'est pas plus dense.

## Refonte visuelle « D2 — L'Étude » — livré en prod (16 juin 2026)

Évolution du look & feel décidée avec le fondateur (mémo complet :
[`/docs/strategy/REBRAND-2026.md`](../strategy/REBRAND-2026.md)). Objectif : garder
l'autorité notariale et l'ancrage messin, mais signaler « app robuste et moderne »
(pas « projet de garage ») et réparer le mobile. Livré sur `main` :

- **Mobile réparé** : la photo plein cadre (Porte des Allemands) qui occupait le
  premier écran *avant* le titre est retirée ; elle devient une **bande signature
  encadrée, en bas de page** (`SignatureBand` dans `frontend/app/page.tsx`). Le H1
  est responsive (`clamp(34px, 8vw, 56px)`) au lieu de `56px` fixe.
- **Wording affirmé** : H1 « Le marché immobilier messin, lu *quartier par
  quartier*. » + sous-titre attaquant l'asymétrie du livre foncier (du Sablon à
  Queuleu…).
- **Preuve chiffrée above-the-fold** en or Jaumont (`ProofBand`) : *29 000+
  comparables · 17 quartiers · Metz et ses 10 communes de couronne* (rafraîchi
  2026-06-21 ; auparavant « 17 000+ · 16 quartiers · collecte hebdomadaire »),
  + la ligne de méthode
  « Nous vérifions une cohérence. Nous n'estimons pas un prix. ». **Que des chiffres
  de méthode/donnée, jamais de traction** (pas de logos clients, pas de note, pas
  de « milliers d'acheteurs »). → l'**or Jaumont** monte en grade : couleur de la
  *donnée*, plus seulement du cachet.
- **Logo** : l'**alérion lorrain unique** (`AlerionMark` — aiglon ailes déployées,
  sans bec ni pattes, encré or Jaumont) remplace le cachet aux **trois** alérions
  (`LorraineSeal`), illisible et non lu par le grand public. En letterhead de la
  home + en-tête du rapport PDF.
- **Signaux « garage » retirés** : crédit « Illustration » supprimé ; « MVP · …
  uniquement » → **« Édition Metz · Moselle »** dans le footer.

✅ **Rafraîchis 2026-06-21** depuis la base prod (`/admin/comparables/stats` +
`/coverage`) : « 29 000+ » (total réel 29 682), « 17 quartiers »
(= `frontend/lib/districts.ts`), « 11 — Metz et sa couronne » (`_METRO_CITIES`,
seules communes ≥ 198 comparables). **Toujours codés en dur** — idéalement les
brancher sur un endpoint de comptage pour qu'ils ne se périment plus. Détail et
provenance : `/CONTEXT.md` §0 (entrée datée 2026-06-21).

## Livré dans ce lot (premier lot d'ancrage)

- **Wording home** (`frontend/app/page.tsx`) : eyebrow « Metz & Moselle » ;
  H1 « …cohérents avec le marché messin, quartier par quartier ? » ; sous-titre
  attaquant frontalement le **livre foncier** + vrais quartiers (Sablon, Queuleu,
  Devant-les-Ponts, Outre-Seille) ; pilier prix « médiane du quartier ».
- **Metadata / SEO local** (`frontend/app/layout.tsx`).
- **Token `--jaumont`** (or de la pierre de Jaumont) dans les deux charte CSS,
  réservé au cachet local. Le `--brick` reste l'unique accent d'action.
- **Cachet local** (`Seal` dans `components/design/Icons.tsx`) : anneau de sceau
  notarial + losange de marque, posé en or Jaumont en tête de la carte
  « Contexte local ». Unique signe local de l'UI.
- **Cachet à l'alérion** (`AlerionSeal`) : variante héraldique gravée, **réservée
  aux grands formats (≥ 64 px)** — favicon, en-tête de rapport, page « à propos ».
  Test de rendu (Pillow) : net à 64/120 px, illisible à 20 px (ailes/corps se
  confondent) → l'UI 20 px garde le losange. Affiner l'alérion 20 px = passe
  graphiste humaine (option (c) écartée pour l'instant).

## Roadmap

### Livré
- ✅ **Bloc « pourquoi local > national »** en home (`LocalEdgeSection`).
- ✅ **Page « méthode locale »** (`/methode`).
- ✅ **Édition nommée** : « édition Metz » assumé (eyebrow, footer, mark).
- ✅ **Mark alérion lisible** : `AlerionMark` (alérion *unique*) en prod, à la
  place du cachet aux trois alérions.
- ✅ **Preuve chiffrée + wording affirmé + mobile réparé** (refonte D2, ci-dessus).

### À faire (ordonné par ROI)
1. **Fiabiliser les chiffres de preuve** (« 17 000+ », « collecte hebdo ») —
   idéalement via un endpoint de comptage, pour qu'ils ne se périment pas.
   *Plus fort impact crédibilité restant.*
2. **Vraie photo héro N&B** libre de droits (la `SignatureBand` utilise toujours
   `hero-metz.jpg`, traité N&B/grain en CSS). Voir brief ci-dessous.
3. **Décision logo « clef de voûte »** : 6 variantes explorées
   (`Design System/preview/brand-keystone-clear.html` ; vote designer = v2, arc
   brisé gothique + clef Jaumont). L'alérion unique reste le mark de test en
   attendant l'arbitrage.

## Brief photo — héro marketing (à transmettre à un photographe)

- **Sujet** : architecture de pierre messine. Priorité 1 : **Porte des
  Allemands** (la plus reconnaissable, bien cadrable). Alternatives : cathédrale
  Saint-Étienne (façade ou contre-plongée de la nef extérieure), façades Jaumont
  rue Serpenoise / place Saint-Louis.
- **Traitement** : **noir & blanc**, légèrement chaud, **grain argentique**
  visible. (Le N&B est aussi, héraldiquement, la couleur réelle de Metz : *parti
  d'argent et de sable*.)
- **Cadrage** : la pierre est un **cadre, pas un sujet** — pas de carte postale.
  Plein cadre, exploitable en bandeau large. Prévoir une zone calme (ciel /
  ombre) pour poser un scrim parchemin à ~70 % en bas et le texte par-dessus.
- **Interdits** : couleur, ciel bleu saturé, drone, intérieurs avec couple
  souriant, foule, mise en scène touristique.
- **Format** : paysage ≥ 2400 px de large, `.jpg` qualité haute + master.

### Intégration (livrée — état placeholder)

Le hero plein cadre est codé (`HeroBanner` dans `frontend/app/page.tsx`) :
traitement N&B chaud + grain (CSS, donc une photo couleur convient), scrim
parchemin, titre en ink par-dessus. Tant qu'aucune image n'est branchée, un
placeholder pierre + cachet en filigrane tient le cadre. **Pour brancher la
vraie photo** : poser le fichier dans `frontend/public/` puis renseigner en haut
de `page.tsx` : `HERO_IMAGE = "/hero-metz.jpg"` et, si licence à attribution,
`HERO_CREDIT = "Photo : … · CC BY-SA 4.0 · Wikimedia Commons"`.

### Pistes libres de droits (À VÉRIFIER avant publication)

Recherche Wikimedia faite, mais **l'environnement bloque commons.wikimedia.org**
→ licences/auteurs/URL **non vérifiés depuis ici**. Ouvrir chaque page de fichier
dans un navigateur et confirmer (licence exacte + version, auteur, absence de
NC/ND) avant usage commercial. Aucun CC0/domaine public HD trouvé sur ces sujets ;
les pistes sont en **CC-BY-SA** (commercial OK, attribution + partage à l'identique).

- Porte des Allemands (prio 1) — `File:20201017_Porte_des_Allemands_Metz_09.jpg` (≈ 5869×3925).
- Porte des Allemands — `File:Porte_des_Allemands_MB.jpg` (≈ 4288×2848, probable Markus Bernet).
- Cathédrale Saint-Étienne — `File:24-Cathédrale_Saint-Étienne_de_Metz.jpg` (6000×4000).
- Repli — `File:Cathedrale-saint-etienne-metz-de-place-prefecture.jpg` (2592×1944, CC-BY-SA 2.5).

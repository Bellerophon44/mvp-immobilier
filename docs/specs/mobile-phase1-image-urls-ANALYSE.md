# Analyse — `POST /analyze` accepte `image_urls` optionnel (screening photo en mode `raw_text`)

> Rôle : ANALYSTE. Cadrage et challenge, pas de spec ni de solution
> d'implémentation. Décisions structurantes remontées au GATE 1.
>
> Périmètre : **backend seul**. L'extraction on-device (WebView / galerie /
> lazy-load) est HORS périmètre et n'est pas spécifiée ici.
>
> Sources relues (état réel du code, pas seulement la doc) : `backend/app/main.py`
> (`AnalyzeRequest`, endpoint `/analyze`), `backend/app/analysis.py`
> (`run_full_analysis`, `_merge_photo_status`), `backend/app/photo_evidence.py`
> (`assess_claims_with_photos`, `MAX_IMAGES`, `ELIGIBLE_TYPES`),
> `backend/app/url_fetch.py` (`extract_image_urls`, `_is_safe_url`),
> `backend/app/llm_semantic.py` (`local_claims`), `frontend/lib/api.ts`.
> Doc : `backend/CLAUDE.md` §1/§5/§6bis/§10/§12, `.claude/lessons.md` (9.10,
> photo-evidence, cross-agence-inc2b), `docs/specs/mobile-app-ANALYSE.md` §4/§5
> (spike A tranché : Option 1).

---

## 1. Reformulation et périmètre

### Objectif
Permettre à l'app mobile, en mode `raw_text` (le texte est extrait on-device car
LeBonCoin bloque le fetch serveur), de **conserver le screening photo des
allégations locales** en envoyant elle-même les URLs d'images de la galerie.
Concrètement : `POST /analyze` accepte un champ optionnel `image_urls:
list[str]` et le route vers le pipeline photo existant
(`run_full_analysis(..., image_urls=...)` → `_merge_photo_status` →
`assess_claims_with_photos`), y compris quand seul `raw_text` est fourni.

### IN (périmètre)
- Ajout d'un champ optionnel `image_urls` au modèle `AnalyzeRequest` (main.py:74).
- Câblage de ce champ vers `run_full_analysis(..., image_urls=...)` (déjà appelé
  à main.py:633-638, déjà accepté par la signature analysis.py:215-218).
- Garde-fou de sûreté / validation des URLs reçues du client (schéma, dédup,
  bornes) avant transmission au pipeline photo.
- Comportement de combinaison vs l'extraction HTML actuelle en mode URL
  (`extract_image_urls`, main.py:630) — voir Q1.
- Mise à jour éventuelle du contrat `frontend/lib/api.ts` (invariant README/§10).

### OUT (hors périmètre)
- Extraction on-device (WebView, lecture `<img>`/`data-src`/`srcset`, déroulé de
  galerie lazy-load) — c'est l'app mobile, traité ailleurs.
- Toute modification de `photo_evidence.py` (gating par type, `MAX_IMAGES`,
  `IMAGE_DETAIL`, cache, prompt) : le pipeline photo existant est réutilisé tel
  quel. Aucun changement de son contrat interne demandé.
- Le screening photo reste **NON-scoré** : zéro impact sur `global_score`,
  `breakdown`, verdicts (invariant §6bis).
- Le flux « collecte » cross-agence et l'upload d'octets (Option 2 de la spike)
  ne sont pas concernés.

---

## 2. État réel vérifié dans le code — circulation actuelle de `image_urls`

### a) Endpoint `/analyze` (main.py:589-643)
- `AnalyzeRequest` (main.py:74-82) déclare `raw_text`, `url`, `district`,
  `address`. **`image_urls` n'existe pas.** Le modèle n'a pas
  `model_config = ConfigDict(extra="forbid")` → Pydantic **ignore** par défaut
  tout champ extra (`extra="ignore"`). Conséquence directe : un client peut déjà
  POSTer `image_urls`, ce ne sera **ni rejeté (pas de 422) ni lu** — le champ est
  silencieusement jeté. C'est exactement le faux-vert documenté dans
  `.claude/lessons.md` [2026-06-13 cross-agence-inc2b-etape1] : « accepte sans
  422 » ≠ « le champ transite ». Tout test d'acceptation devra prouver le
  **transit réel**, pas l'absence de 422.
- La variable locale `image_urls` est initialisée à `None` (main.py:610).
  - **Branche raw_text** (main.py:611-613) : `image_urls` reste `None`. C'est
    précisément ici que le screening photo est inerte aujourd'hui.
  - **Branche URL** (main.py:614-630) : `image_urls = extract_image_urls(html,
    url) or None`. Les URLs proviennent du HTML re-fetché côté serveur, dédupées
    et résolues en absolu par `urljoin` (url_fetch.py:135-182).
- Passage au pipeline : `run_full_analysis(..., image_urls=image_urls)`
  (main.py:633-638).

### b) `run_full_analysis` (analysis.py:215-280)
- Signature accepte déjà `image_urls=None` (analysis.py:216-217). **Aucune
  modification de signature n'est nécessaire** côté pipeline.
- `local_claims` sont extraits par le LLM via `analyze_semantic(raw_text)`
  (analysis.py:219, llm_semantic.py:361 `_coerce_claims`). **Indépendant du
  HTML** : produit aussi bien en mode raw_text qu'en mode URL (voir Q5).
- `_merge_photo_status(local_ctx, image_urls)` est appelé (analysis.py:280),
  après construction de `local_ctx["claims"]` (deux branches : géocodée
  analysis.py:252 / repli quartier analysis.py:274).

### c) `_merge_photo_status` (analysis.py:179-191)
- Court-circuite si `not image_urls or local_ctx is None` (analysis.py:183) ou
  si pas de claims (analysis.py:186). Sinon délègue à
  `assess_claims_with_photos(ctx_claims, image_urls)` et fusionne `photo_status`
  par index.

### d) `assess_claims_with_photos` (photo_evidence.py:128-176)
- `image_urls = list(image_urls or [])` (photo_evidence.py:138).
- **Gating par TYPE** : seuls les claims de type ∈ `ELIGIBLE_TYPES =
  {"cathedrale","nature","autre"}` (photo_evidence.py:23, 140).
- **Court-circuit** : 0 claim éligible OU 0 image → `{}` sans appel LLM
  (photo_evidence.py:143-144).
- **Cap** : `images = image_urls[:MAX_IMAGES]` avec `MAX_IMAGES = 15`
  (photo_evidence.py:29, 147). `IMAGE_DETAIL = "high"` (photo_evidence.py:35).
- Repli sûr `non_trouve`, cache mémoire TTL 7j. **Aucune validation de schéma /
  SSRF sur les URLs reçues** : elles sont transmises telles quelles dans les
  parts `image_url` envoyées à OpenAI (photo_evidence.py:103-106). Aujourd'hui ce
  n'est pas un problème car les seules URLs qui y arrivent viennent de
  `extract_image_urls` (donc d'un HTML déjà re-fetché par `fetch_listing`, lui
  même gardé par `_is_safe_url`). Avec `image_urls` fourni par le client, **cette
  garantie de provenance disparaît** — c'est le cœur de Q2.

### Conclusion de l'état réel
Le câblage interne (`run_full_analysis` → `_merge_photo_status` →
`assess_claims_with_photos`) **fonctionne déjà** et est agnostique à la
provenance des URLs. Le seul maillon manquant est en **amont** : `/analyze`
n'expose ni ne route `image_urls` en mode raw_text (laissé à `None`,
main.py:610). Le changement demandé est donc très localisé (modèle Pydantic +
quelques lignes dans l'endpoint), ce qui plaide pour un périmètre minimal.

### RGPD — état observé
- En mode raw_text actuel, **aucune URL d'image ne transite**. En mode URL,
  `extract_image_urls` produit des URLs jamais loggées (main.py:628-629 le
  commente, et `assess_claims_with_photos` ne logue que des compteurs,
  photo_evidence.py:167-169). Le log d'entrée `/analyze` (main.py:595-602) logue
  `has_raw_text`, longueur, preview 60 chars, `has_url` et **l'URL de page** —
  mais **pas** `image_urls`. Le futur câblage devra **ne pas** ajouter
  `image_urls` à ce log (invariant §6bis « URLs d'images jamais loggées »).

---

## 3. Dépendances et ordre

- **Aucun prérequis backend manquant** : la signature `run_full_analysis(...,
  image_urls=...)` et tout le pipeline photo sont déjà en place et déployés
  (§6bis). Ce chantier est purement additif côté endpoint.
- **Dépendance fonctionnelle amont (hors périmètre, à signaler)** : l'app mobile
  doit extraire les URLs on-device. Le spike A (mobile-app-ANALYSE §5, 2026-06-23)
  a tranché Option 1 et confirmé que le CDN `img.leboncoin.fr` est ouvert (URLs
  non signées fetchables par OpenAI). Le backend de ce chantier n'a pas à
  attendre l'app : il peut être livré et testé indépendamment (envoi d'`image_urls`
  simulé).
- **Dépendance fonctionnelle interne (limite, voir Q5)** : le screening photo ne
  produit un `photo_status` que s'il existe au moins un claim **éligible**
  (type cathedrale/nature/autre). Si le LLM n'extrait aucun claim de ce type, les
  `image_urls` sont **inertes** (court-circuit photo_evidence.py:143). Ce n'est
  pas un bug, mais une limite à documenter : envoyer des `image_urls` ne garantit
  pas un appel vision.
- **Ordre** : ce chantier est un prérequis de la fonctionnalité mobile « conserver
  les photos en raw_text » mais n'a lui-même aucun prérequis non satisfait.

---

## 4. Risques et anti-patterns

1. **Faux-vert d'acceptation (leçon cross-agence-inc2b)** — RISQUE ÉLEVÉ de
   méthode de test. `AnalyzeRequest` n'a pas `extra="forbid"` : un test « POST
   avec `image_urls` ne renvoie pas 422 » serait **vert même sans déclaration du
   champ**. La preuve doit porter sur le **transit réel** jusqu'à
   `assess_claims_with_photos` (sonde d'appel) et sur la présence de `photo_status`
   dans la réponse. À porter en exigence pour le testeur.

2. **SSRF / relais d'URL arbitraire vers OpenAI** — voir Q2. Le risque SSRF
   *serveur* classique (notre backend qui fetche une IP interne) **n'existe pas
   ici** : le backend ne télécharge jamais les octets, c'est OpenAI qui fetche.
   Mais on ne veut pas faire de notre endpoint un **relais aveugle** d'URLs
   arbitraires (ex. `file://`, `http://169.254.169.254/...` envoyé à OpenAI,
   ou des URLs qui ne sont pas des images). Garde-fou en **whitelist positive**
   exigé (leçon 9.10 : jamais une blacklist de quelques caractères).

3. **Payload abusif / déni de service** — voir Q3. Sans cap d'entrée, un client
   peut POSTer des milliers d'URLs très longues ; même si `assess_claims_with_photos`
   cape ensuite à 15, la validation/dédup/résolution se ferait sur la liste
   entière. Cap d'entrée à poser AVANT le cap `MAX_IMAGES`.

4. **Rupture de contrat `/analyze` (invariant README + §10 + lessons)** — le
   contrat ne doit pas changer pour les appelants web. Champ **optionnel à défaut
   `None`** ⇒ comportement strictement inchangé quand absent. À verrouiller par un
   test de non-régression (raw_text sans `image_urls` → réponse identique, aucun
   appel vision). Côté `frontend/lib/api.ts` : voir Q4.

5. **Fuite RGPD par log** — risque si le futur câblage ajoute `image_urls` au log
   d'entrée. Invariant : URLs d'images jamais loggées. À acter comme contrainte de
   spec (ne logger au plus qu'un **compteur** d'URLs reçues, jamais les valeurs).

6. **Non-scoré préservé** — aucune des modifications ne doit toucher
   `compute_global_score`. Le risque est nul si on se limite à
   `_merge_photo_status` (déjà hors scoring), mais à re-vérifier en review.

7. **Pas de nouveau vendor, pas de coût structurel nouveau** — le seul coût est un
   appel vision `gpt-4.1-mini` supplémentaire (≈3-4k tokens d'entrée) **désormais
   aussi déclenchable en mode raw_text**. Aujourd'hui borné au mode URL ; demain
   un mode raw_text avec claims éligibles + images déclenchera l'appel. Coût marginal
   par analyse, amorti par cache, cohérent avec le MVP < 1 €/mois — **mais** le cap
   d'entrée (Q3) est ce qui empêche un abus de gonfler ce coût. Pas d'estimation de
   prix, pas de redistribution d'annonce : conforme §1.

---

## 5. Challenge du requirement (posture adversariale)

- **Le requirement est bien posé et sous-dimensionné au bon niveau.** Le câblage
  interne existe déjà ; le delta réel tient en ~10 lignes (champ Pydantic +
  validation + affectation). Il n'y a **pas plus simple** sans sacrifier la sûreté
  (on ne peut pas se passer de la validation des URLs, sinon relais aveugle).
- **Point de vigilance sur le sur-dimensionnement** : la tentation serait de
  réimplémenter dans `/analyze` une validation SSRF complète (résolution DNS,
  anti-rebind...). C'est **trop** pour ce que le backend fait réellement (il ne
  fetche pas). Une whitelist de schéma + rejet localhost/IP privées littérales +
  bornes suffit et reste cohérente avec l'esprit minimal de `_is_safe_url`
  (lui-même documenté comme volontairement minimal, CLAUDE §11). Ne pas
  sur-investir.
- **Réutiliser `_is_safe_url` tel quel ?** Tentant (DRY) mais à challenger : il a
  été écrit pour des URLs de **page** qu'on va fetcher nous-mêmes. Pour des URLs
  d'**image** relayées à OpenAI, la logique de validation est proche mais
  l'intention diffère (pas d'auto-protection serveur, mais hygiène de relais).
  Réutiliser la fonction est acceptable et économe ; à acter explicitement (Q2)
  plutôt que de dupliquer une variante divergente.

---

## 6. QUESTIONS POUR L'HUMAIN (GATE 1)

Chaque question a des options et une recommandation argumentée. Aucune n'est
tranchée par l'analyste.

### Q1 — Combinaison vs priorité en mode URL quand `image_urls` est AUSSI fourni
En mode URL, le serveur extrait déjà des URLs via `extract_image_urls(html)`
(main.py:630). Si un client fournit EN PLUS `image_urls` explicites, que fait-on ?
- (a) Les `image_urls` explicites **remplacent** l'extraction HTML.
- (b) **Fusion** (union dédupliquée) des deux sources, puis cap.
- (c) **Priorité** à l'une des deux sans fusion.

Impact `MAX_IMAGES` : dans tous les cas le cap à 15 est appliqué **après** par
`assess_claims_with_photos` (photo_evidence.py:147). Si fusion (b), l'ordre de
concaténation détermine quelles 15 URLs survivent au cap → choix non neutre.

**Recommandation : (a) remplacement.** C'est le cas le plus simple et le plus
sûr. En pratique le client mobile envoie soit `url` (sites non protégés, fetch
serveur), soit `raw_text + image_urls` (LBC) — la **co-occurrence url + image_urls
n'est pas un cas d'usage attendu**. Le remplacement évite : (i) un ordre de fusion
arbitraire qui décide silencieusement quelles images passent le cap ; (ii) une
dédup cross-source (URLs CDN vs URLs résolues par urljoin, formes différentes pour
la même image). Si le cas mixte devait exister, le client est mieux placé que le
serveur pour fusionner avant l'envoi. Le mode URL **sans** `image_urls` reste
strictement inchangé (extraction HTML, invariant rétro-compat).

### Q2 — Validation / sûreté des URLs fournies par le client
Ces URLs partent vers OpenAI (fetch côté OpenAI), pas vers notre serveur : le
risque SSRF *serveur* est différent (le backend ne télécharge rien). Mais on ne
veut pas relayer n'importe quoi. Que valider exactement ?
- Schéma `http`/`https` **obligatoire** (rejet `file:`, `data:`, `ftp:`, etc.).
- Rejet `localhost` / IP privées RFC1918 / `169.254.*` / `::1` (cohérent
  `_is_safe_url`, url_fetch.py:40-45) — défense en profondeur, évite de relayer
  une cible interne à OpenAI.
- Longueur max par URL (ex. ≤ 2048) pour borner le payload.
- Dédup en préservant l'ordre.

**Recommandation :**
1. **Whitelist positive** (leçon 9.10) : valider que le schéma ∈ {http, https} ET
   qu'un hostname non vide est présent ; rejeter (silencieusement, en filtrant
   l'URL) ce qui ne matche pas, plutôt que 422 sur tout le body (une URL douteuse
   ne doit pas faire échouer l'analyse entière — repli sûr, cohérent avec
   `_merge_photo_status` qui court-circuite proprement).
2. **Réutiliser `_is_safe_url`** (url_fetch.py:29-47) pour filtrer chaque URL,
   plutôt que dupliquer une variante : même esprit, source unique de vérité, et
   le rejet localhost/IP privées y est déjà en whitelist de schéma + blocklist
   d'hôtes. Acter ce choix explicitement.
3. **Filtrer, pas rejeter le body** : URL invalide → écartée de la liste ; liste
   vide après filtrage → `image_urls=None` (court-circuit photo, comportement
   identique à raw_text sans images).

NB : on ne valide PAS que l'URL est réellement une image (pas de HEAD/GET côté
serveur — ce serait réintroduire un fetch serveur, interdit RGPD §6bis). Si l'URL
n'est pas une image, OpenAI échoue proprement et le repli `non_trouve`
(photo_evidence.py:170-172) couvre le cas.

### Q3 — Cap du nombre d'`image_urls` acceptées dans le body
Faut-il borner le nombre d'URLs en entrée, indépendamment du cap `MAX_IMAGES`
appliqué en aval ?
- (a) Aucun cap d'entrée (on s'appuie sur `[:MAX_IMAGES]`).
- (b) Cap d'entrée explicite (ex. 30 ou 50), tronqué ou rejeté au-delà.

**Recommandation : (b), cap d'entrée explicite, troncature silencieuse (ex. 50).**
Raisons : (i) sans cap d'entrée, la validation/dédup/`_is_safe_url` s'exécuterait
sur une liste potentiellement énorme (payload abusif) AVANT le cap à 15 — coût CPU
et mémoire inutile ; (ii) un cap d'entrée généreux (50 >> 15) laisse de la marge
pour que le filtrage (Q2) écarte des URLs invalides tout en gardant ≥15 valides ;
(iii) troncature (garder les N premières) plutôt que 422, pour ne pas faire
échouer une analyse à cause d'une galerie trop fournie. Ordre des opérations
recommandé : cap d'entrée (50) → filtrage `_is_safe_url` + dédup → passage au
pipeline qui re-cape à `MAX_IMAGES` (15). Borne à fixer en spec ; toute borne sera
testée aux valeurs exactes (leçon 9.7 « bornes aux valeurs exactes »).

### Q4 — Mise à jour de `frontend/lib/api.ts`
L'invariant (README l.63, lessons) interdit de casser le schéma `/analyze` sans
MAJ `api.ts`. Or le web n'émet pas `image_urls` (`analyzeListing` construit un
body sans ce champ, api.ts:84-94). Faut-il quand même mettre à jour le client web ?
- (a) Mettre à jour `api.ts` maintenant (ajouter `image_urls?: string[]` au type
  de requête, sans l'envoyer) pour respecter l'invariant à la lettre.
- (b) Considérer hors périmètre : l'ajout est **additif et optionnel**, le web ne
  l'émet pas, le contrat de **réponse** (`ApiResult`) est inchangé.

**Recommandation : (b) avec nuance.** L'invariant vise à ne pas casser le contrat
côté client (réponse). Ici la **réponse** `/analyze` ne change pas (le
`photo_status` était déjà dans `LocalClaim`, api.ts:29). Le champ ajouté est en
**entrée** et **optionnel** : aucun client web existant ne casse. Donc pas de
mise à jour *obligatoire* d'`api.ts` pour la sécurité du contrat. **Nuance** : par
hygiène et pour documenter que le backend accepte désormais ce champ, ajouter une
ligne de commentaire ou le type optionnel dans `api.ts` est peu coûteux et évite
une dérive doc/code. À trancher : strict minimum (rien) vs documentation (type
optionnel non émis). L'analyste penche pour **documenter le type optionnel** (coût
quasi nul, cohérence repo), sans modifier `analyzeListing`.

### Q5 — Mode raw_text + claims éligibles : `image_urls` potentiellement inertes
Le screening photo ne s'exécute que s'il existe ≥1 claim **éligible** (type
cathedrale/nature/autre, photo_evidence.py:140-144). En mode raw_text, les
`local_claims` sont-ils produits ?
- **Vérifié** : OUI. `analyze_semantic(raw_text)` extrait `local_claims`
  (llm_semantic.py:361, `_coerce_claims`), **indépendamment du HTML** — le LLM ne
  voit que `raw_text` dans les deux modes. Donc les claims existent en raw_text.
- **Mais** : l'éligibilité dépend du **type** extrait par le LLM. Si l'annonce ne
  contient aucune allégation de type cathedrale/nature/autre (ex. seulement
  gare/transport/commerces, non éligibles), les `image_urls` envoyées seront
  **inertes** (court-circuit, aucun appel vision, aucun `photo_status` posé).

**Ce n'est pas un bug à corriger dans ce chantier**, mais une **limite à
documenter** : envoyer `image_urls` ne garantit pas un screening — il faut des
claims éligibles. Recommandation : **acter la limite dans la spec** (et un test
montrant que raw_text + image_urls + 0 claim éligible → 0 appel vision, réponse
inchangée), sans élargir `ELIGIBLE_TYPES` (hors périmètre, et le gating par type
est une décision GATE 1 antérieure de photo-evidence). Aucune action de
modification requise ; signaler à l'humain que l'efficacité réelle de la feature
dépend de la nature des allégations de l'annonce.

# photo-evidence — ANALYSE (GATE 1)

> Rôle : ANALYSTE. Ce document cadre et challenge le chantier "photo-evidence"
> (screening photo des allégations locales, Phase 0+1) face au code RÉEL. Il ne
> spécifie pas la solution et ne tranche aucun arbitrage structurant : il les
> remonte en fin de document. Lecture du code au 2026-06-07.

---

## 1. Objectif et périmètre

### Reformulation
En **mode URL uniquement**, après le fetch de l'annonce, l'application doit :
1. Extraire les URLs d'images de la page (et non plus seulement le texte).
2. Pour les seules allégations locales **visuellement vérifiables** (ex. "vue
   cathédrale"), faire **un seul** appel multimodal `gpt-4.1-mini` (images en
   `detail:"low"`) qui confirme / infirme chaque allégation éligible.
3. Enrichir chaque claim de `local_context.claims` d'un champ
   `photo_status ∈ {confirme, non_trouve, non_applicable}`.
4. UX : `confirme` → atout ("confirmé par une photo de l'annonce") ;
   `non_trouve` → renforce la liste des questions / à vérifier en visite.

### In
- `extract_image_urls(html, base_url)` dans `url_fetch.py` (sans casser
  `fetch_listing_text`).
- Nouveau module `photo_evidence.py` (`assess_claims_with_photos`), cache mémoire,
  repli silencieux.
- Branchement transient dans `run_full_analysis` / handler `/analyze` (mode URL).
- Ajout du champ `photo_status` dans les objets claim, rétro-compatible.
- MAJ `frontend/lib/api.ts` (`LocalClaim`) + mapping UX.

### Out (déjà tranché par l'humain, non rediscuté)
- Cross-agence / pHash / historique de prix.
- Toute persistance nouvelle (pas de table, pas de hash stocké, pas de photo
  stockée).
- Screening en mode texte collé (dégradation propre + micro-nudge).

### Challenge du requirement lui-même
Le périmètre est sain et minimal. **Un seul** point de sur-portée potentielle :
la ligne "exposer le tableau de photos de l'API JSON Bien'ici" (scraper). Voir
§3.6 — c'est, en l'état Phase 0+1, du hors-périmètre déguisé. À retirer du
chantier ou à requalifier explicitement en "préparation future, non branchée".

---

## 2. Contraintes dures — vérification face au code

| Contrainte | Tient ? | Preuve dans le code |
|---|---|---|
| Score 40/30/30 intact | OUI, si on ne touche pas `scoring.py`. Le bloc photo est non-scoré, comme `local_context`. | `app/scoring.py` ne lit que `price_pillar` et `semantic_pillar` ; `local_context` n'y entre jamais (`app/analysis.py:151-154`). Aucun chemin du score ne passe par les claims. |
| Aucune photo stockée | OUI, faisable. Le pipeline actuel est déjà 100 % transient (aucune écriture hors `comparables`/`feedback`). | Pas d'I/O disque dans `analysis.py` / `llm_semantic.py`. La seule DB est `Comparable`/`Feedback` (`db/models.py`). On envoie des **URLs** au LLM (`image_url`), pas des bytes ; rien à stocker. |
| Gating strict (jamais `confirme` sur gare/a31/ecoles/commerces/centre/transport/calme) | À IMPLÉMENTER côté `photo_evidence.py` ; faisable car le `type` du claim est déjà normalisé. | Enum `_CLAIM_TYPES` figé dans `llm_semantic.py:145-148` : `centre, cathedrale, gare, transport, commerces, nature, ecoles, calme, a31, autre`. Le gating filtre sur ce `type`. |
| Appel vision conditionnel (mode URL ET ≥1 claim éligible ET ≥1 image) | Faisable, mais nécessite de **propager le mode + les images** jusqu'à `run_full_analysis`, ce qui n'existe pas aujourd'hui (voir §3.3, point bloquant). |
| Cache mémoire (pattern `llm_semantic`) | Réplicable tel quel. | `_CACHE`, `_hash_text`, `_get_from_cache`, `_set_cache`, TTL 7 j : `llm_semantic.py:20-44`. La clé devra inclure le set d'URLs d'images + la liste des claims éligibles. |
| Repli silencieux | Pattern déjà en place. | `_FALLBACK` + `logger.exception("LLM call failed...")` : `llm_semantic.py:235-242`. À répliquer : toute erreur réseau/LLM ⇒ tous les claims éligibles restent `non_trouve` (ou `non_applicable`), jamais de blocage. |
| Schéma `/analyze` rétro-compatible | OUI : `claims` est une liste de dicts libres côté Pydantic (`local_context: Optional[Dict[str, Any]]`), ajouter une clé ne casse rien. MAJ front requise (anti-pattern #9). | `AnalyzeResponse.local_context: Optional[Dict[str, Any]]` (`app/main.py:73-74`). Côté front, `LocalClaim` est typé strict (`frontend/lib/api.ts:18-23`) → **doit** recevoir `photo_status?`. |

**Conclusion §2** : toutes les contraintes dures tiennent, à une réserve
d'architecture près (§3.3 : ni l'URL ni le HTML ne descendent aujourd'hui jusqu'à
l'analyse).

---

## 3. Cartographie d'impact (fichier:ligne)

### 3.1 `app/url_fetch.py` — extraction des images
- État actuel : `fetch_listing_text(url)` télécharge, parse, **décompose** une
  série de balises puis ne renvoie que le **texte** tronqué à 8000 chars
  (`url_fetch.py:49-88`). Le `resp.text` (HTML brut) n'est pas conservé ni renvoyé.
- Impact : ajouter `extract_image_urls(html, base_url)`. Deux remarques de fond :
  - `fetch_listing_text` fait `resp = requests.get(...)` puis jette le HTML.
    Pour ne pas **doubler le fetch réseau** (un GET texte + un GET pour images),
    il faut soit (a) une fonction `fetch_listing(url) -> {text, html}` qui fait
    **un seul** GET et renvoie les deux, soit (b) renvoyer le HTML en plus du
    texte. Recommandation analyste : un seul GET, sinon on double l'egress et la
    latence pour rien.
  - `extract_image_urls` doit résoudre les URLs relatives (`urljoin(base_url, src)`)
    et dédupliquer. Sources à harvester : `og:image` / `twitter:image` (meta),
    JSON-LD `image`, `<img>` dans `<main>`/`<article>`. **Attention** :
    `fetch_listing_text` **décompose `<script>`** (`url_fetch.py:75-76`) — or le
    JSON-LD est dans `<script type="application/ld+json">`. Donc l'extraction
    d'images doit se faire sur le HTML **avant** décomposition, pas sur le `soup`
    nettoyé. À cadrer dans la spec.

### 3.2 `app/photo_evidence.py` — NOUVEAU module
- `assess_claims_with_photos(claims, image_urls) -> dict[claim_index|text -> photo_status]`.
- Responsabilités : gating (filtrer les claims éligibles), cap d'images, appel
  vision conditionnel, parsing JSON strict, cache, repli silencieux.
- Réutilise le `client = OpenAI(...)` et `MODEL_NAME` (importer depuis
  `llm_semantic` ou réinstancier — la spec tranchera ; réinstancier évite un
  couplage mais duplique la lecture d'env).

### 3.3 `app/analysis.py` — POINT D'ARCHITECTURE BLOQUANT
- `run_full_analysis(raw_text, district_override="", address="")`
  (`analysis.py:116-118`) ne reçoit **que du texte**. Il n'a **ni l'URL ni le
  HTML ni le mode**. Les claims sont construits ici :
  - `claims = semantic_result.get("local_claims")` (`analysis.py:132`)
  - puis `assess_claims(...)` les enrichit en `local_context["claims"]`
    (`analysis.py:140-147`), avec les clés `{text, type, status, note}`.
- Donc pour ajouter `photo_status`, il faut :
  1. **Propager les images** (ou le HTML, ou l'URL) jusqu'à `run_full_analysis`.
     Aujourd'hui impossible sans changer la signature.
  2. Appeler `assess_claims_with_photos` **après** `assess_claims`, et fusionner
     `photo_status` dans chaque dict de `local_context["claims"]`.
- Recommandation analyste : ajouter un paramètre **optionnel** `image_urls:
  list[str] | None = None` à `run_full_analysis` (défaut `None` ⇒ comportement
  mode texte strictement inchangé). C'est le point d'injection le plus propre et
  rétro-compatible. Variante : passer `html`/`url` et faire l'extraction dans
  `analysis.py` — moins propre (mélange des responsabilités fetch/analyse).

### 3.4 `app/main.py` — handler `/analyze`
- Le mode est déjà distingué : branche `raw_text` (`main.py:278-280`) vs branche
  fetch URL (`main.py:281-293`), `fetched = fetch_listing_text(payload.url or "")`.
- Impact : en branche URL uniquement, récupérer le HTML (via la fonction unifiée
  §3.1), extraire les images, et les passer à `run_full_analysis(...,
  image_urls=...)` (`main.py:296-300`). Branche texte : ne rien changer
  (`image_urls=None`).
- Le mode texte reçoit déjà 0 image ⇒ dégradation propre automatique. Le
  micro-nudge "Collez l'URL..." est purement **front** (aucun champ backend requis
  pour ça ; éventuellement un drapeau, mais le front sait déjà qu'il est en mode
  texte via l'onglet — `frontend/lib/api.ts:50-55` reçoit `mode`).

### 3.5 `frontend/lib/api.ts` — contrat + UX (anti-pattern #9)
- `LocalClaim` est typé strict (`api.ts:18-23`). Ajouter
  `photo_status?: "confirme" | "non_trouve" | "non_applicable"` (optionnel ⇒
  rétro-compatible avec d'anciennes réponses).
- Mapping UX (`confirme` → atout, `non_trouve` → renforce les questions) : c'est
  du rendu, dans le composant qui affiche les claims (carte "Contexte local",
  `LocalContextCard` côté `components/design/`, cf. CLAUDE §10). Hors de `api.ts`
  mais à inclure dans le périmètre front du chantier.

### 3.6 `scrapers/sources/bienici.py` — challenge : utile en Phase 0+1 ?
- Le scraper bienici (`_parse_listing`, `bienici.py:190`) sert la **collecte CI**
  hebdo (`collect.yml`), pas l'analyse à la volée d'une URL utilisateur. Il
  produit des `PropertyListing` (`scrapers/models.py:5-29`) — qui **n'a aucun
  champ photo** aujourd'hui, et il ne capte **aucune image** (grep `photo|image`
  sur `bienici.py` = 0 résultat).
- En mode URL, l'utilisateur colle **une URL d'annonce** (souvent une agence
  locale type idemmo, cf. URL de référence CONTEXT §10) ; le pipeline d'analyse
  ne passe **jamais** par le scraper. Les deux mondes sont disjoints :
  scraper = collecte de comparables (agrégats prix) ; analyse = fetch HTML d'une
  URL arbitraire.
- **Tranche analyste** : exposer le tableau de photos de l'API Bien'ici est
  **hors-périmètre Phase 0+1**. Cela n'aide pas le screening d'une URL collée
  (le harvest se fait sur le HTML de la page via `extract_image_urls`). Y toucher
  ajoute du code mort "pour plus tard" dans un module en prod sensible
  (anti-bot, balayage par tranches). Recommandation : **ne pas toucher bienici**
  dans ce chantier. Si l'utilisateur colle une URL `bienici.com`, le fetch HTML
  est de toute façon bloqué (anti-bot, CONTEXT §4.3) → le screening dégradera
  proprement (0 image), ce qui est acceptable. (Voir Question 4.)

### 3.7 DB / CI
- Aucun impact DB (aucune persistance). Aucun impact `collect.yml` /
  `diagnose-scrapers.yml` si on ne touche pas les scrapers.
- Pas de tests automatisés backend hors `tests/` feedback existants ; la spec
  devra ajouter des tests sur le gating et le repli (cf. leçon "garde-fou =
  test", `.claude/lessons.md`).

---

## 4. Dépendances et ordre

1. **Prérequis #1 (interne, bloquant)** : unifier le fetch pour exposer le HTML
   (`url_fetch.py`) AVANT de pouvoir extraire les images. Sans ça, double GET.
2. **Prérequis #2 (interne, bloquant)** : élargir la signature de
   `run_full_analysis` (param `image_urls` optionnel) pour propager les images.
   Sans ça, impossible d'ajouter `photo_status` sans casser le mode texte.
3. `photo_evidence.py` dépend de #1 (images) et du gating (types figés dans
   `llm_semantic._CLAIM_TYPES`).
4. Le branchement `analysis.py` dépend de `photo_evidence.py` + de la structure
   `claims` produite par `assess_claims` (`metz_local.py:296-322`).
5. Front (`api.ts` + composant) dépend du contrat backend stabilisé.
6. **Prérequis EXTERNE (infra)** : egress HTTPS sortant autorisé vers les CDN
   d'images des agences ET vers `api.openai.com`. Même nature que la dépendance
   egress déjà notée pour la BAN (CLAUDE §11bis, "egress HTTPS vers
   api-adresse.data.gouv.fr"). À vérifier sur Fly et sur Claude Code on the web.

Aucun prérequis d'auth (l'endpoint `/analyze` est public, `main.py:260`).

---

## 5. Risques d'anti-pattern

- **Redistribution d'annonce brute (anti-pattern #3, CONTEXT §11)** : on n'envoie
  que des **URLs** d'images publiques au LLM, en transit, sans stockage, et on ne
  renvoie au front qu'un statut (`confirme/non_trouve/non_applicable`), **jamais
  l'image ni son URL**. Conforme, à condition que la spec interdise explicitement
  de renvoyer les URLs d'images dans la réponse `/analyze`.
- **Fausse précision (positionnement produit, CONTEXT §1.4)** : risque majeur =
  un `confirme` sur un type non visuel (gare/a31/...). Mitigé par le gating strict
  (§2). À verrouiller par un **test** (jamais `confirme` hors types visuels),
  sinon la leçon sera oubliée (`.claude/lessons.md`).
- **Faux positif visuel / complaisance LLM** : le LLM peut "confirmer" pour faire
  plaisir. Mitigation : prompt exigeant une **preuve visuelle explicite** ("ne
  confirme que si une image montre sans ambiguïté l'élément ; en cas de doute,
  réponds non_trouve"), `temperature` basse (le code actuel est à 0.2,
  `llm_semantic.py:17`), et formulation UX prudente côté `non_trouve`. La
  cohérence avec la couche B existante est déjà cette posture : "on ne contredit
  que le géographiquement douteux ; le non-vérifiable reste à vérifier, jamais
  cohérent par complaisance" (CONTEXT §11bis couche B).
- **Coût / dérive** (estimation §6) : un appel vision est plus cher qu'un appel
  texte. Sans cap d'images ni gating, on multiplie les tokens image. Mitigé par
  cap + `detail:"low"` + conditionnel. La sécurité financière (usage limit OpenAI,
  CONTEXT §3.3 / 9.4) reste la ceinture de sécurité.
- **Nouveau vendor** : AUCUN. On reste sur OpenAI `chat.completions` déjà utilisé.
- **RGPD (images tierces)** : voir §7 — gate humaine potentielle.
- **Rupture de contrat API (anti-pattern #9)** : couvert si `photo_status` est
  optionnel + MAJ `api.ts`.

---

## 6. Faisabilité technique de l'appel vision + coût

### 6.1 Forme de l'appel — CONFIRMÉE
`openai>=1.50` (`requirements.txt:6`) supporte les parts multimodales sur
`chat.completions.create`. La forme est :

```python
client.chat.completions.create(
    model=MODEL_NAME,                       # gpt-4.1-mini, multimodal OK
    temperature=0.2,
    response_format={"type": "json_object"},
    messages=[
        {"role": "system", "content": "<consigne honnêteté>"},
        {"role": "user", "content": [
            {"type": "text", "text": "<claims éligibles + format JSON attendu>"},
            {"type": "image_url",
             "image_url": {"url": "https://...jpg", "detail": "low"}},
            # ... une part image_url par image (cap N)
        ]},
    ],
)
```

`gpt-4.1-mini` est multimodal et accepte `image_url` + `detail:"low"`.
`response_format={"type":"json_object"}` est déjà le pattern maison
(`llm_semantic.py:227`, CONTEXT §12). **Pas de nouvelle dépendance, pas de
nouveau endpoint OpenAI.** Faisabilité confirmée.

### 6.2 Coût / latence — ordre de grandeur
- Analyse texte actuelle : ~0,001 € (CONTEXT §3.2, §3.3).
- En `detail:"low"`, chaque image coûte un forfait de tokens fixe et faible
  (indépendant de la résolution, ~quelques dizaines à ~85 tokens selon le
  modèle). Pour N=4-6 images, l'ordre de grandeur reste **du même ordre que
  l'appel texte** (quelques centièmes de centime), tant qu'on plafonne N.
- Latence : +1 aller-retour LLM (l'appel est **séparé** de l'analyse sémantique,
  donc séquentiel après-coup). Acceptable car conditionnel (rare).
- **Bornage** : (a) cap dur du nombre d'images (Question 6) ; (b)
  `detail:"low"` ; (c) gating (0 claim éligible ⇒ 0 appel) ; (d) cache mémoire ;
  (e) usage limit OpenAI (CONTEXT §3.3). À trafic quasi nul, l'impact mensuel
  reste << 1 €.

---

## 7. RGPD — images tierces vers OpenAI (gate potentielle)

- On envoie en **transit** à OpenAI des images **tierces** (photos d'annonces
  d'agences) pouvant contenir des personnes, plaques, intérieurs privés. Aucun
  stockage côté nous (transient), mais sous-traitance OpenAI le temps de l'appel.
- Posture actuelle du projet : minimisation assumée (pas d'IP dans `feedback`,
  CONTEXT §9.7), egress externe déjà pratiqué (BAN, OpenAI texte). L'ajout
  d'**images** est un cran au-dessus en sensibilité (donnée potentiellement à
  caractère personnel).
- Mitigations possibles : `detail:"low"` (basse résolution, limite la
  reconnaissance fine) ; ne pas stocker ; ne pas logguer les URLs d'images ;
  micro-disclaimer front ("les photos de l'annonce sont analysées en transit, non
  conservées"). Voir Question 3 — c'est un arbitrage à remonter, pas à trancher.

---

## 8. ToS / robots / egress (CDN images)

- Même posture que le fetch HTML actuel (`url_fetch.py`, UA Chrome) : on lit des
  ressources publiques liées depuis la page. On ne télécharge même pas les bytes
  côté serveur — on passe l'**URL** à OpenAI qui fetch l'image. Cela déplace le
  fetch image vers OpenAI (moins d'egress chez nous, mais dépendance à
  l'accessibilité publique de l'URL côté OpenAI : certains CDN d'agence peuvent
  exiger un referer/UA → l'image peut échouer ⇒ repli `non_trouve`, acceptable).
- Anti-bot des grands portails (CONTEXT §4.3) : si le fetch HTML échoue déjà
  (Leboncoin/SeLoger/Bien'ici), il n'y a ni texte ni image ⇒ on est déjà en 422
  avant même le screening. Le screening ne concerne donc en pratique que les
  petites agences fetchables (idemmo, etc.).

---

## 9. OPTIONS chiffrées (choix structurants)

### Option A — Injection par `image_urls` (param optionnel sur `run_full_analysis`)
- `main.py` (branche URL) extrait les images et les passe ; mode texte = `None`.
- + Séparation nette fetch / analyse ; rétro-compatible ; testable en isolant
  `photo_evidence` ; mode texte strictement inchangé.
- − Touche 3 fichiers (`url_fetch`, `analysis`, `main`).
- **Recommandation : Option A.** C'est le minimum propre.

### Option B — Passer `html` (ou `url`) à `run_full_analysis`, extraction interne
- + `main.py` change moins.
- − Mélange fetch/parse HTML dans l'orchestrateur d'analyse ; plus dur à tester ;
  risque de re-fetch.

### Option C — Appel vision fusionné dans `analyze_semantic` (un seul appel LLM)
- + Un seul aller-retour LLM (texte + vision ensemble).
- − Casse la séparation, alourdit le prompt principal, complique le cache
  (clé = texte aujourd'hui, `llm_semantic.py:216`), rend le mode texte et le mode
  URL divergents dans un module unique, et **ne respecte pas** la consigne "UN
  SEUL appel multimodal dédié". À écarter.

---

## 10. Synthèse adversariale

- Le chantier est faisable, peu coûteux, sans nouveau vendor, et respecte le
  score 40/30/30 et la non-persistance. Bon candidat MVP.
- Deux dettes d'architecture à régler en prérequis (HTML exposé + signature
  `run_full_analysis`) — petites mais bloquantes.
- Une portée à retirer (bienici, §3.6) sous peine de code mort.
- Le vrai risque produit n'est pas technique mais **éditorial** : un `confirme`
  de complaisance détruit le positionnement "pas de fausse précision". Le gating
  strict + un prompt exigeant + un test de verrou sont non négociables.

---

## QUESTIONS POUR L'HUMAIN (GATE 1)

1. **Liste exacte des types gatés (éligibles vision).** Le code fige 10 types
   (`llm_semantic.py:145-148`). La proposition retient `cathedrale`, `nature`, et
   `autre` "si c'est une vue". Or `autre` est un fourre-tout : un claim `autre`
   peut être tout sauf visuel.
   - Options : (a) éligibles = `{cathedrale, nature}` strictement ; (b) +
     `autre` mais alors le prompt vision doit lui-même répondre `non_applicable`
     si le claim n'est pas visuellement vérifiable.
   - **Reco** : (b) — `{cathedrale, nature, autre}` côté gating, mais le LLM
     classe `autre` en `non_applicable` s'il n'est pas une vue. Garde la
     souplesse sans risque de faux `confirme` (le test de verrou couvre les
     types non visuels durs).

2. **Cap d'images (N max envoyées en `detail:"low"`).**
   - Options : 4 / 6 / 8.
   - **Reco** : **6**. Couvre une galerie typique d'agence, borne le coût/latence,
     marge sous le plafond OpenAI. Sélection : les 6 premières après dédup, en
     priorisant `og:image`/JSON-LD (souvent la photo principale/extérieure, la
     plus utile pour "vue cathédrale").

3. **Disclaimer RGPD (images tierces vers OpenAI).** Faut-il une mention front
   explicite ?
   - Options : (a) aucune (transient, basse résolution, posture egress déjà
     assumée) ; (b) micro-mention discrète ("photos analysées en transit, non
     conservées") ; (c) gate juridique avant livraison.
   - **Reco** : (b). Cohérent avec la micro-mention RGPD du feedback (§9.7) et le
     ton prudent du produit, sans alourdir l'UX. (c) seulement si l'humain juge le
     risque "images de personnes" trop sensible.

4. **Faut-il toucher `scrapers/sources/bienici.py` ?** (exposer le tableau de
   photos de l'API).
   - Analyse : hors-périmètre Phase 0+1 (§3.6) — le scraper sert la collecte CI,
     pas l'analyse d'une URL collée ; `PropertyListing` n'a pas de champ photo.
   - **Reco** : **NON** dans ce chantier. Le harvest se fait sur le HTML via
     `extract_image_urls`. Confirmer qu'on assume de ne pas screener les URLs
     `bienici.com` (de toute façon bloquées anti-bot, CONTEXT §4.3).

5. **Formulation du verdict (honnêteté / anti-complaisance).** Le seuil de preuve
   pour `confirme` doit-il être "strict" (preuve visuelle non ambiguë requise,
   sinon `non_trouve`) ou "souple" ?
   - **Reco** : **strict** — "ne réponds `confirme` que si une image montre
     l'élément sans ambiguïté ; au moindre doute, `non_trouve`". Aligné sur la
     posture couche B (CONTEXT §11bis) et le positionnement "pas de fausse
     précision". À verrouiller par un test.

6. **Wording UX du statut `non_trouve`.** Doit-il apparaître comme une alerte ou
   comme une simple invitation à vérifier en visite ?
   - **Reco** : invitation neutre ("non visible sur les photos de l'annonce — à
     vérifier en visite"), jamais accusatoire (l'absence de photo ne prouve pas
     l'absence du fait). À cadrer avec le designer ; remonté car c'est un choix de
     ton produit, pas technique.

# photo-evidence — SPEC : Screening photo des allégations locales (Phase 0+1)

Role : spec-writer. Cahier des charges implementable. Source : `docs/specs/photo-evidence-ANALYSE.md`,
arbitrages GATE 1 (2026-06-07), code reel lu le 2026-06-07 (`app/url_fetch.py`,
`app/llm_semantic.py`, `app/analysis.py`, `app/main.py`, `app/metz_local.py`,
`frontend/lib/api.ts`, `tests/conftest.py`). Aucune ligne de solution n'est codee ici.

> **Amendement 2026-06-18** : pour reduire les faux `non_trouve` (reperes pourtant
> presents dans les photos mais hors des premieres images ou en arriere-plan), le
> **cap d'images passe de 6 a 15** (`MAX_IMAGES = 15`) et le **detail passe de
> `low` a `high`** (`IMAGE_DETAIL = "high"`, lisibilite des elements lointains).
> Le reste du contrat (gating par type, repli `non_trouve`, bloc non-score,
> cache, RGPD) est inchange. Les references `cap 6` / `detail:"low"` ci-dessous
> sont a lire avec ces nouvelles valeurs.

## 1. Objectif et perimetre

### Objectif
En mode URL uniquement, apres le fetch de l'annonce, extraire les URLs d'images de
la page et, pour les seules allegations locales **visuellement verifiables**, faire
**un seul** appel multimodal `gpt-4.1-mini` (images en `detail:"high"`) qui confirme
ou n'a pas trouve chaque allegation eligible. Chaque claim de `local_context.claims`
recoit un champ optionnel `photo_status`. Bloc **non-score** (le score 40/30/30 reste
strictement intact).

### In
- `app/url_fetch.py` : `extract_image_urls(html, base_url) -> list[str]` + exposition
  du HTML brut via **un seul** GET (pas de double fetch reseau).
- `app/photo_evidence.py` (NOUVEAU) : `assess_claims_with_photos(claims, image_urls)`
  (gating, cap 15, appel vision conditionnel, cache memoire, repli silencieux).
- `app/analysis.py` : parametre optionnel `image_urls` sur `run_full_analysis` ;
  fusion de `photo_status` dans chaque dict de `local_context["claims"]`.
- `app/main.py` : en branche URL, extraire les images et les passer via `image_urls=`.
- `app/llm_semantic.py` : durcissement du prompt d'EXTRACTION (les reperes nommes
  Centre Pompidou-Metz, Temple Neuf, Jardin Botanique sont classes en `autre`/`nature`,
  jamais `centre`) — cf. decision 8.
- `frontend/lib/api.ts` : champ optionnel `photo_status` sur `LocalClaim` + mapping UX
  (badge `confirme`, renfort `non_trouve`, rien sinon) + micro-mention RGPD + micro-nudge
  mode texte.
- Tests : `backend/tests/test_photo_evidence*.py`.

### Out (non-objectifs, voir §5)
- Toute persistance (table, hash stocke, photo ou URL d'image stockee).
- Toute modification de `scrapers/sources/bienici.py` (decision GATE 1, cf. analyse §3.6).
- Tout renvoi d'URL d'image ou de bytes dans la reponse `/analyze`.
- Toute modification de `scoring.py` (le bloc photo n'est jamais score).
- Screening en mode texte colle (degradation propre : `image_urls=None`).
- Nouveau vendor, nouveau secret, nouvel endpoint OpenAI.

## 2. Decisions actees (GATE 1)

1. **Types eligibles a la verification photo** = `{cathedrale, nature, autre}` parmi les
   10 de `llm_semantic._CLAIM_TYPES`. Le gating filtre sur ces 3 types. Les 7 types de
   distance/ambiance (`centre, gare, transport, commerces, ecoles, calme, a31`) ne sont
   **jamais** eligibles et ne peuvent **jamais** recevoir `confirme`. Pour un claim de
   type `autre`, le prompt vision doit repondre `non_applicable` si le claim n'est PAS
   une vue / un repere visuel.
2. **Cap images = 15** maximum, en `detail:"high"`. Selection : apres dedup, prioriser
   `og:image` / `twitter:image` / JSON-LD `image` (photo principale, souvent exterieure),
   puis les `<img>` de galerie, jusqu'a 15.
3. **Seuil `confirme` STRICT** : le modele ne repond `confirme` que si une image montre
   l'element SANS AMBIGUITE ; au moindre doute -> `non_trouve`. `temperature=0.2`.
   A verrouiller par test (§4).
4. **RGPD = micro-mention front** discrete (cf. micro-mention feedback 9.7), sans revue
   juridique bloquante : « Les photos de l'annonce sont analysees en transit et ne sont
   pas conservees. »
5. **Statut de repli (defaut sur) = `non_trouve`** : toute erreur reseau/LLM, JSON invalide,
   timeout ou absence de reponse exploitable pour un claim eligible -> ce claim recoit
   `non_trouve` (jamais `confirme`). L'analyse n'est jamais bloquee.
6. **Wording `non_trouve`** (front) = invitation neutre, jamais accusatoire :
   « non visible sur les photos de l'annonce — a verifier en visite ».
7. **Claims NON eligibles** (7 types de distance/ambiance) : **pas** de cle `photo_status`
   ajoutee (cle absente). Coherent avec le front (`photo_status?` optionnel).
8. **Durcissement du prompt d'extraction** (`llm_semantic.py`, GATE 1 suite) : pour eviter
   qu'un repere visuel nomme soit mal classe en type `centre` (non eligible) par confusion
   lexicale sur le mot « Centre », le prompt d'extraction precise que **Centre Pompidou-Metz,
   Temple Neuf, Jardin Botanique** (et reperes visuels analogues) doivent etre classes en
   `autre` (ou `nature` pour le Jardin Botanique / plans d'eau), **jamais** `centre` (qui
   reste reserve a la proximite du centre-ville). Verrouille par test (§4 critere 20).

### Points non tranches (a remonter si besoin avant dev)
- Egress HTTPS sortant : OpenAI fetch les images via les URLs transmises ; certains CDN
  d'agence exigent un referer/UA et peuvent refuser -> l'image echoue cote OpenAI -> repli
  `non_trouve` (acceptable, decision 5). Pas d'action requise cote nous.

## 3. Contrat technique

### 3.0 `app/llm_semantic.py` — durcissement du prompt d'extraction (decision 8)

- Dans `USER_PROMPT_TEMPLATE` (regle de classification de `local_claims`), preciser que les
  reperes visuels NOMMES — **Centre Pompidou-Metz, Temple Neuf, Jardin Botanique** et
  analogues — sont classes en `autre` (ou `nature` pour Jardin Botanique / plans d'eau),
  **jamais** `centre`. Le type `centre` reste reserve a la proximite du centre-ville.
- `_CLAIM_TYPES` (`llm_semantic.py:145-148`) reste INCHANGE (pas de nouveau type). Seul le
  libelle de la regle change : c'est une precision de classification, pas une extension de
  taxonomie.
- Aucun impact sur le score, le cache (cle = hash du texte), ni le format de sortie.

### 3.1 `app/url_fetch.py` — exposition HTML + extraction images

Contrainte CRUCIALE : le JSON-LD vit dans `<script type="application/ld+json">`, que le
nettoyage actuel **decompose** (`url_fetch.py:75-76`). L'extraction d'images doit donc
operer sur le **HTML brut**, AVANT decomposition des `<script>`.

- Exposer le HTML brut **sans doubler le GET reseau**. Forme retenue : une fonction qui
  fait **un seul** `requests.get` et renvoie a la fois le texte extrait (comportement
  actuel inchange) et le HTML brut (ou directement les `image_urls`). `fetch_listing_text`
  reste disponible et son contrat de sortie (texte tronque a `MAX_TEXT_LENGTH`, `None` si
  echec/vide/unsafe) est inchange.
- `extract_image_urls(html: str, base_url: str) -> list[str]` :
  - sources, dans cet ordre de priorite : meta `og:image` / `twitter:image`, JSON-LD
    `image` (cle `image` d'un objet `application/ld+json`), puis `<img>` (attribut `src`,
    a defaut `data-src`) de la galerie ;
  - resout les URLs relatives via `urljoin(base_url, src)` ;
  - deduplique en preservant l'ordre de priorite ;
  - ne leve jamais (HTML malforme / absence de balise -> liste eventuellement vide) ;
  - le cap a 15 peut etre applique ici ou dans `photo_evidence` ; la spec exige que la
    liste finalement transmise a l'appel vision ne depasse JAMAIS 15 (§4 critere 8).
- Filtre SSRF (`_is_safe_url`) inchange ; les URLs d'images ne sont pas re-fetchees cote
  serveur (on transmet l'URL a OpenAI).

### 3.2 `app/photo_evidence.py` — NOUVEAU module

`assess_claims_with_photos(claims: list[dict], image_urls: list[str]) -> dict`

- Retour : un mapping de l'identite du claim eligible vers son `photo_status`
  (`{confirme, non_trouve, non_applicable}`). L'identite du claim (index ou `text`)
  est laissee au dev mais doit permettre a `analysis.py` de fusionner sans ambiguite ;
  les claims non eligibles n'apparaissent PAS dans le mapping (§2 decision 7).
- Logger nomme : `logging.getLogger("photo_evidence")`, niveau INFO. Ne JAMAIS logguer
  les URLs d'images (RGPD, cf. analyse §7).
- **Gating** : ne retenir que les claims dont `type in {cathedrale, nature, autre}`.
- **Court-circuit (aucun appel vision)** : si 0 claim eligible OU `image_urls` vide
  -> retour immediat sans appel LLM.
- **Cap** : au plus 15 images transmises, `detail:"high"`.
- **Appel vision** : UN SEUL `client.chat.completions.create`, `model=MODEL_NAME`
  (`gpt-4.1-mini`), `temperature=0.2`, `response_format={"type":"json_object"}`, message
  `user` = une part `text` (claims eligibles + format JSON attendu) + N parts
  `image_url` (`{"url": ..., "detail": "high"}`). Le client OpenAI et `MODEL_NAME` sont
  reutilises (import depuis `llm_semantic` ou reinstanciation depuis `OPENAI_API_KEY` ;
  pas de nouveau secret).
- **System prompt (honnetete stricte, anti-complaisance)** : enonce que le modele ne
  repond `confirme` QUE si une image montre l'element sans ambiguite ; au moindre doute,
  `non_trouve` ; et `non_applicable` si le claim (type `autre`) n'est pas un repere visuel.
  Enumere les reperes visuels messins a reconnaitre : Cathedrale Saint-Etienne, la Moselle
  / plans d'eau (nature), Centre Pompidou-Metz, Temple Neuf, Jardin Botanique, plus toute
  vue atypique. Pas d'emoji. Pas d'estimation de prix.
- **Parsing strict** : sortie JSON attendue mappant chaque claim eligible -> un statut
  parmi `{confirme, non_trouve, non_applicable}`. Tout statut hors enum, manquant ou non
  parsable pour un claim eligible -> `non_trouve` (defaut sur, decision 5).
- **Cache memoire** : pattern `llm_semantic` (`_CACHE`, TTL 7 j). Cle = hash stable de
  (URLs images retenues + claims eligibles, normalises). Un meme couple (images, claims)
  ne declenche qu'un appel.
- **Repli silencieux** : toute exception reseau/LLM/JSON est capturee
  (`logger.exception(...)`), l'analyse continue, tous les claims eligibles recoivent
  `non_trouve` (decision 5). Jamais de propagation d'exception.

### 3.3 `app/analysis.py` — propagation et fusion

- Nouvelle signature :
  `run_full_analysis(raw_text, district_override="", address="", image_urls=None)`.
- Si `image_urls` est `None` ou vide : comportement **strictement inchange** (aucun appel
  vision, aucune cle `photo_status` ajoutee a aucun claim).
- Sinon : apres construction de `local_ctx["claims"]` (via `assess_claims`, structure
  `{text, type, status, note}`), appeler `assess_claims_with_photos(claims_eligibles,
  image_urls)` et fusionner `photo_status` dans le dict de chaque claim **eligible**.
  Les claims non eligibles restent inchanges (pas de cle `photo_status`).
- Si `local_ctx` est `None` (quartier non reconnu) ou `claims` vide : pas de fusion, pas
  d'effet de bord.

### 3.4 `app/main.py` — handler `/analyze`

- Branche **URL** uniquement : recuperer le HTML (fonction unifiee §3.1), extraire les
  images (`extract_image_urls`), et appeler `run_full_analysis(..., image_urls=...)`.
- Branche **texte** : `image_urls=None` (aucun changement de comportement).
- **Interdiction** : ne JAMAIS inclure d'URL d'image ni de bytes dans la reponse `/analyze`
  (anti-pattern #3). Seul le `photo_status` (statut) transite vers le front, porte par les
  claims de `local_context`.
- `AnalyzeResponse` reste inchange : `local_context: Optional[Dict[str, Any]]` accepte
  deja une cle supplementaire dans les dicts de `claims`. Codes d'erreur inchanges
  (400 / 422 / 500).

### 3.5 Variables d'environnement / secrets

Aucune nouvelle variable, aucun nouveau secret. Reutilisation de `OPENAI_API_KEY` et
`OPENAI_MODEL` existants.

### 3.6 Contrat frontend (`frontend/lib/api.ts` + composant)

- `LocalClaim` : ajouter `photo_status?: "confirme" | "non_trouve" | "non_applicable"`
  (optionnel -> retro-compatible avec les anciennes reponses). Ne pas modifier `ApiResult`,
  `ApiPillar`, `LocalContext` au-dela de ce champ, ni `analyzeListing`.
- Composant d'affichage des claims (carte « Contexte local », `LocalContextCard`) :
  - `confirme` -> badge « confirme par une photo » ;
  - `non_trouve` -> renfort « non visible sur les photos de l'annonce — a verifier en
    visite » ;
  - `non_applicable` ou absent -> aucun rendu specifique.
- Micro-mention RGPD discrete (decision 4) affichee pres du bloc « Contexte local » en
  mode URL : « Les photos de l'annonce sont analysees en transit et ne sont pas conservees. »
- Micro-nudge en mode texte (`AnalyzerInput`) : « Collez l'URL pour analyser aussi les
  photos. » Purement front (aucun champ backend requis).
- Reutilise le design system existant (tokens / polices). Pas de nouvelle lib UI.

## 4. Criteres d'acceptation (observables, testables par pytest)

Tests dans `backend/tests/test_photo_evidence*.py`. OpenAI **mocke** (aucun appel reseau
reel), isolation via `conftest.py` existant (base SQLite jetable, `OPENAI_API_KEY` factice).
Numerotation contractuelle pour testeur et reviewer.

1. **Gating dur — types de distance/ambiance jamais `confirme`** : pour chaque type
   `{centre, gare, transport, commerces, ecoles, calme, a31}`, meme avec des images et
   un mock vision qui renverrait `confirme`, le claim ne recoit JAMAIS `photo_status ==
   "confirme"`. Verifiable : aucun de ces types n'est transmis a l'appel vision et/ou
   leur `photo_status` final n'est jamais `confirme` (cle absente attendue, decision 7).
2. **Court-circuit 0 image** : `assess_claims_with_photos(claims_eligibles, [])` ne
   declenche **aucun** appel `client.chat.completions.create` (mock assert non appele) et
   retourne un mapping ne contenant aucun `confirme`.
3. **Court-circuit 0 claim eligible** : `assess_claims_with_photos([...non eligibles...],
   [urls])` ne declenche **aucun** appel vision (mock assert non appele).
4. **Appel vision conditionnel positif** : avec >=1 claim eligible ET >=1 image, exactement
   **un** appel `client.chat.completions.create` est emis (mock assert appele une fois),
   avec `response_format={"type":"json_object"}` et `temperature == 0.2`.
5. **detail high** : les parts `image_url` transmises a l'appel portent `detail == "high"`.
6. **Repli silencieux** : si le mock OpenAI leve une exception (reseau/LLM), aucun raise
   ne remonte ; tous les claims eligibles recoivent `photo_status == "non_trouve"` ;
   l'analyse complete (`run_full_analysis`) aboutit sans erreur.
7. **JSON invalide -> repli** : si le mock renvoie un contenu non parsable ou un statut hors
   enum pour un claim eligible, ce claim recoit `non_trouve` (jamais `confirme`).
8. **Cap 6** : avec une liste de >6 image_urls, l'appel vision ne transmet **au plus 6**
   parts `image_url` (mock : compter les parts `image_url` du message `user`).
9. **`extract_image_urls` — og:image + JSON-LD sur HTML brut** : sur un HTML contenant
   `<meta property="og:image">` et un `<script type="application/ld+json">{"image": ...}</script>`,
   les deux URLs sont extraites (preuve que l'extraction lit le HTML AVANT decomposition
   des `<script>`).
10. **`extract_image_urls` — galerie + URLs relatives resolues** : un `<img src="/photos/1.jpg">`
    avec `base_url = "https://agence.fr/annonce"` produit `https://agence.fr/photos/1.jpg`.
11. **`extract_image_urls` — dedup** : une URL presente a la fois en `og:image` et en
    `<img>` n'apparait qu'une fois dans la sortie.
12. **`extract_image_urls` — robustesse** : un HTML sans aucune image renvoie `[]` sans lever.
13. **Mode texte inchange** : `run_full_analysis(raw_text)` (sans `image_urls`, ou
    `image_urls=None`) ne declenche aucun appel vision (mock assert non appele) et ne produit
    aucune cle `photo_status` dans `local_context["claims"]`.
14. **Mapping `confirme`** : pour un claim eligible (`type == "cathedrale"`) avec un mock
    vision renvoyant `confirme`, le dict du claim dans `local_context["claims"]` porte
    `photo_status == "confirme"`.
15. **Mapping `non_trouve`** : pour un claim eligible avec mock vision renvoyant `non_trouve`,
    le dict du claim porte `photo_status == "non_trouve"`.
16. **`autre` non visuel -> `non_applicable`** : pour un claim `type == "autre"` avec mock
    vision renvoyant `non_applicable`, le dict du claim porte `photo_status ==
    "non_applicable"` (et jamais `confirme`).
17. **Claims non eligibles sans cle** : apres une analyse en mode URL, un claim de type
    non eligible (ex. `gare`) n'a PAS la cle `photo_status` dans son dict (decision 7).
18. **Retro-compat `/analyze`** : la reponse `POST /analyze` reste conforme a
    `AnalyzeResponse` (`global_score`, `verdict`, `confidence`, `pillars[]`, `actions`,
    `local_context`). Aucune URL d'image ni bytes ne figurent dans la reponse (verifiable
    par introspection : aucune valeur de la reponse n'est une URL d'image ; pas de cle
    `image_urls`/`images`/`photos`).
19. **Score intact** : pour un meme `raw_text` et un meme `price_pillar`/`semantic_pillar`,
    le `global_score` est identique avec ou sans `image_urls` (le bloc photo n'entre pas
    dans le score). Verifiable en comparant `run_full_analysis(text)` et
    `run_full_analysis(text, image_urls=[...])` sous mocks deterministes.
20. **Durcissement prompt d'extraction (decision 8)** : `USER_PROMPT_TEMPLATE`
    (`app/llm_semantic.py`) contient une consigne explicite classant Centre Pompidou-Metz /
    Temple Neuf / Jardin Botanique en `autre`/`nature` et **jamais** `centre`. Verrouille par
    une assertion de chaine sur le template (regression guard : la consigne ne doit pas
    disparaitre), `_CLAIM_TYPES` inchange (toujours 10 types).

## 5. Hors-perimetre / non-objectifs

- Toute persistance : aucune table, aucun hash stocke, aucune photo ni URL d'image stockee.
- Modification de `scrapers/sources/bienici.py` (decision GATE 1, analyse §3.6).
- Renvoi d'URL d'image ou de bytes dans la reponse `/analyze`.
- Modification de `scoring.py` ou de la ponderation 40/30/30.
- Screening en mode texte colle (degradation propre attendue).
- Fusion de l'appel vision dans `analyze_semantic` (Option C ecartee, analyse §9).
- Nouveau vendor, nouveau secret, nouvel endpoint OpenAI.
- Cross-agence / pHash / historique de prix.

## 6. Conformite (anti-patterns applicables)

- **Redistribution d'annonce brute (anti-pattern #3)** : on ne transmet que des URLs
  publiques a OpenAI, en transit, sans stockage ; la reponse `/analyze` ne renvoie qu'un
  statut, JAMAIS l'image ni son URL (critere 18). Les URLs d'images ne sont jamais loggees.
- **Fausse precision (positionnement produit)** : gating strict (types de distance/ambiance
  jamais `confirme`, criteres 1) + seuil `confirme` strict (`temperature=0.2`, prompt
  anti-complaisance, criteres 4/14) ; verrou par test obligatoire (sinon la lecon est
  oubliee, `.claude/lessons.md`).
- **RGPD (images tierces)** : `detail:"high"`, transit sans stockage, URLs non loggees,
  micro-mention front (decision 4). Pas de revue juridique bloquante.
- **Pas de secret en clair** : reutilisation de `OPENAI_API_KEY` ; aucun secret introduit.
- **Pas de nouveau vendor** : OpenAI `chat.completions` multimodal deja en place.
- **Contrat `/analyze` stable (anti-pattern #9)** : `AnalyzeResponse` inchange ;
  `photo_status` optionnel sur `LocalClaim` ; `frontend/lib/api.ts` mis a jour
  (invariant `.claude/lessons.md` ligne 19).
- **Conventions CLAUDE §12** : Python 3.12, logger nomme `photo_evidence`, pas de
  commentaire « what », pas d'emoji dans le code ni les prompts systeme.

SPEC prête pour GATE 2 (approbation humaine).

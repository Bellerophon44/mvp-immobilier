# SPEC — `POST /analyze` accepte `image_urls` optionnel (screening photo en mode `raw_text`)

> Rôle : SPEC-WRITER. Cahier des charges implémentable. Périmètre **backend
> seul**. Suite de `docs/specs/mobile-phase1-image-urls-ANALYSE.md` (GATE 1 actée).
> Le développeur et le testeur suivent CE document en aveugle.
>
> Code réel relu avant rédaction : `backend/app/main.py` (`AnalyzeRequest`
> l.74-82, endpoint `/analyze` l.589-643, log d'entrée l.595-602, variable
> `image_urls` l.610 + branches l.611-630, appel `run_full_analysis` l.633-638),
> `backend/app/analysis.py` (`run_full_analysis` l.215-280, `_merge_photo_status`
> l.179-191), `backend/app/photo_evidence.py` (`assess_claims_with_photos`
> l.128-176, `ELIGIBLE_TYPES` l.23, `MAX_IMAGES = 15` l.29, court-circuit
> l.143-144, cap l.147), `backend/app/url_fetch.py` (`_is_safe_url` l.29-47,
> `extract_image_urls` l.135-182), `frontend/lib/api.ts` (`analyzeListing`
> l.84-117, `LocalClaim.photo_status` l.29). Doc : `backend/CLAUDE.md`
> §1/§5/§6/§6bis/§10/§12, `.claude/lessons.md`.

---

## 1. Objectif

Permettre à l'app mobile, en mode `raw_text` (texte extrait on-device car
LeBonCoin bloque le fetch serveur), de conserver le screening photo des
allégations locales : `POST /analyze` accepte un champ optionnel `image_urls:
list[str]` et le route vers le pipeline photo existant
(`run_full_analysis(..., image_urls=...)` → `_merge_photo_status` →
`assess_claims_with_photos`), y compris quand seul `raw_text` est fourni.

Le pipeline interne accepte déjà `image_urls=...` (signature `run_full_analysis`
inchangée). Le seul maillon manquant est l'endpoint : `AnalyzeRequest` ne déclare
pas le champ, et en mode `raw_text` la variable locale `image_urls` reste `None`
(main.py:610-613).

---

## 2. Périmètre

### IN
- Déclaration d'un champ optionnel `image_urls: Optional[list[str]] = None` sur
  `AnalyzeRequest` (main.py:74-82).
- Câblage de ce champ vers `run_full_analysis(..., image_urls=...)` dans les
  **deux** branches de l'endpoint (`raw_text` ET `url`), selon les règles
  d'arbitrage actées (§4, §5).
- Traitement de sûreté des URLs reçues du client AVANT transmission au pipeline :
  dédup, validation/filtrage via `_is_safe_url`, troncature au cap d'entrée.
- Documentation du champ dans `frontend/lib/api.ts` (type de requête uniquement,
  sans émission par le web).

### OUT (hors périmètre — voir §8)
- Extraction on-device (WebView, lecture `<img>`/`data-src`/`srcset`, déroulé de
  galerie lazy-load) : c'est l'app mobile, traité ailleurs.
- Toute modification de `photo_evidence.py` (gating par type, `MAX_IMAGES`,
  `IMAGE_DETAIL`, cache, prompt) : pipeline photo réutilisé **tel quel**.
- Toute modification de `_merge_photo_status` ou de la signature de
  `run_full_analysis` (déjà capables de recevoir `image_urls`).
- Tout impact sur le scoring : le screening photo reste NON-scoré (§6bis CLAUDE).
- Le flux « collecte » cross-agence et l'upload d'octets (Option 2 spike).
- Tout fetch serveur des URLs d'images (le backend ne télécharge jamais les
  octets ; c'est OpenAI qui fetche côté `photo_evidence`).

---

## 3. État réel vérifié (rappel pour le développeur)

- `AnalyzeRequest` n'a **pas** `model_config = ConfigDict(extra="forbid")` →
  Pydantic est en `extra="ignore"` par défaut. Conséquence directe :
  aujourd'hui un client peut déjà POSTer `image_urls` ; ce n'est **ni rejeté (pas
  de 422) ni lu** — le champ est silencieusement jeté. C'est le faux-vert
  documenté `.claude/lessons.md` [2026-06-13 cross-agence-inc2b-etape1]. Un test
  « pas de 422 » NE PROUVE RIEN. Voir §6 (testabilité).
- main.py:610 initialise `image_urls = None`. Branche `raw_text` (l.611-613) :
  reste `None` (screening inerte aujourd'hui). Branche `url` (l.614-630) :
  `image_urls = extract_image_urls(html, url) or None`.
- `assess_claims_with_photos` (photo_evidence.py:138-147) fait déjà
  `list(image_urls or [])`, gate par `ELIGIBLE_TYPES`, court-circuite si 0 claim
  éligible OU 0 image (l.143-144), puis cape à `MAX_IMAGES = 15` (l.147). Aucune
  validation de schéma / SSRF sur les URLs reçues : aujourd'hui elles ne viennent
  que de `extract_image_urls` (HTML déjà fetché derrière `_is_safe_url`). Avec
  `image_urls` client, cette garantie de provenance disparaît → §4 Q2.
- Le log d'entrée `/analyze` (main.py:595-602) logue `has_raw_text`, longueur,
  preview 60 chars, `has_url`, et **l'URL de page**. Il ne logue PAS
  `image_urls` ; le câblage NE DOIT PAS l'y ajouter (§6bis RGPD).

---

## 4. Décisions actées (GATE 1) — non rediscutées

**D1 (Q1) — REMPLACER, pas fusionner.**
En mode URL, si `image_urls` est fourni explicitement par le client (liste
non vide APRÈS traitement §5), il REMPLACE l'extraction HTML
(`extract_image_urls`). En mode `raw_text`, `image_urls` du client est la seule
source possible. **Absence de `image_urls`** (champ absent, `null`, liste vide,
ou liste devenue vide après filtrage) ⇒ comportement strictement inchangé : mode
URL continue d'extraire du HTML, mode `raw_text` reste sans photo.

**D2 (Q2) — `_is_safe_url` + FILTRER (jamais rejeter le body).**
Chaque URL reçue est validée par `app.url_fetch._is_safe_url` (réutilisé tel
quel, source unique de vérité) : schéma `http`/`https` uniquement, hostname non
vide, rejet `localhost` / `127.0.0.1` / `0.0.0.0` / `::1` / IP privées RFC1918 /
`169.254.*`. Les URLs invalides sont FILTRÉES (retirées) ; les valides sont
GARDÉES. Une URL invalide ne fait JAMAIS échouer l'analyse (aucun 422 sur le body
pour une URL douteuse). Dédup en préservant l'ordre de première apparition.
On ne valide PAS que l'URL pointe une image (aucun HEAD/GET serveur — interdit
RGPD). Si l'URL n'est pas une image, OpenAI échoue proprement et le repli
`non_trouve` (photo_evidence.py:170-172) couvre le cas.

**D3 (Q3) — CAP D'ENTRÉE + TRONCATURE silencieuse.**
Le nombre d'`image_urls` traitées est borné à `MAX_INPUT_IMAGE_URLS = 50`, AVANT
le cap aval `MAX_IMAGES = 15` de `photo_evidence`. Au-delà du cap d'entrée, on
TRONQUE silencieusement (on garde les premières) ; JAMAIS de 422 pour une galerie
trop fournie.

**D4 (Q4) — DOCUMENTER `api.ts`, sans changer `analyzeListing`.**
Ajouter `image_urls?: string[]` au type décrivant le corps de requête `/analyze`
dans `frontend/lib/api.ts`, SANS modifier la signature ni le comportement de
`analyzeListing` (le web n'émet pas ce champ). Respecte l'invariant « ne pas
changer le schéma `/analyze` sans MAJ `api.ts` » (README l.63, CLAUDE §10).

**D5 (Q5) — Limite documentée (non un bug).**
Les `image_urls` sont INERTES s'il n'existe aucun claim de type éligible
(`cathedrale` / `nature` / `autre`). Envoyer `image_urls` ne garantit pas un
appel vision. Comportement attendu, à documenter (§7), pas à corriger ici (ne pas
élargir `ELIGIBLE_TYPES`).

---

## 5. Spécification fonctionnelle

### 5.1 Contrat `/analyze` mis à jour

`AnalyzeRequest` ajoute UN champ optionnel, sans `extra="forbid"` (modèle
inchangé par ailleurs) :

```python
class AnalyzeRequest(BaseModel):
    raw_text: Optional[str] = None
    url: Optional[str] = None
    district: Optional[str] = None
    address: Optional[str] = None
    image_urls: Optional[list[str]] = None  # screening photo (mode raw_text ou
                                             # override URL). Jamais loggees, jamais
                                             # stockees, jamais re-fetchees serveur.
```

- Le champ est **optionnel** (défaut `None`) → rétro-compatible : un body sans
  `image_urls` se comporte exactement comme avant.
- Le **contrat de réponse** `AnalyzeResponse` est INCHANGÉ. `photo_status` était
  déjà porté par chaque claim de `local_context.claims` (api.ts `LocalClaim`).
- Codes d'erreur inchangés : 400 (aucun input), 422 (URL fournie mais
  inaccessible), 500 (erreur interne). Aucune nouvelle cause de 422 ou 4xx liée à
  `image_urls`.

### 5.2 Constante et fonction de traitement

- Définir `MAX_INPUT_IMAGE_URLS = 50` (constante module `app/main.py`, nommée,
  pas de littéral magique inline).
- Le traitement des URLs client produit une `list[str]` propre, ou une liste
  vide. Une liste vide ⇒ `image_urls = None` passé au pipeline (court-circuit
  photo, comportement identique à « pas d'images »).

### 5.3 Ordre des opérations (sans ambiguïté)

À partir de `payload.image_urls` (peut être `None`, `[]`, ou une liste de
chaînes), produire `client_image_urls` :

1. Si `payload.image_urls` est `None` ou vide → résultat = `[]` (donc traité
   comme `None`, aucun effet). STOP.
2. Sinon, parcourir la liste **dans l'ordre reçu** et, pour chaque élément :
   - retenir uniquement les `str` non vides après `.strip()` (ignorer
     silencieusement tout non-`str` ou chaîne vide) ;
3. **Dédup** en préservant l'ordre de première apparition (sur la valeur
   `strip()`).
4. **Validation/filtrage** : garder chaque URL pour laquelle
   `_is_safe_url(url)` est vrai ; retirer les autres (silencieusement).
5. **Troncature** : garder les `MAX_INPUT_IMAGE_URLS` (50) premières URLs
   restantes.
6. Résultat : si la liste finale est non vide → c'est `client_image_urls` ; sinon
   `[]` (traité comme `None`).

> Ordre figé : nettoyage → dédup → validation/filtrage → troncature à
> `MAX_INPUT_IMAGE_URLS`. Le pipeline aval (`assess_claims_with_photos`) re-cape
> ensuite à `MAX_IMAGES = 15` ; ce second cap n'est PAS modifié.
> Dédup AVANT filtrage et AVANT troncature : deux occurrences identiques ne
> comptent qu'une fois dans le budget de 50.

### 5.4 Comportement par mode

- **Mode `raw_text`** (branche main.py:611-613) :
  `image_urls` est aujourd'hui laissé à `None`. Le câblage doit l'affecter à
  `client_image_urls or None` (résultat du §5.3). C'est l'unique source d'images
  en mode `raw_text`.
- **Mode URL** (branche main.py:614-630) :
  - Si `client_image_urls` est non vide → il REMPLACE l'extraction HTML
    (`image_urls = client_image_urls`). `extract_image_urls` peut ne pas être
    appelé, ou son résultat ignoré (au choix du développeur, sans effet
    observable tant que le remplacement est effectif).
  - Si `client_image_urls` est vide/absent → comportement INCHANGÉ :
    `image_urls = extract_image_urls(html, url) or None`.
- Dans les deux modes, l'appel reste
  `run_full_analysis(..., image_urls=image_urls)` (main.py:633-638), signature
  inchangée.

### 5.5 RGPD / logging

- Le log d'entrée `/analyze` (main.py:595-602) NE DOIT PAS ajouter les valeurs
  d'`image_urls`. Au plus un **compteur** (ex. `n_image_urls=%d` sur la liste
  reçue ou retenue) est toléré ; jamais les chaînes d'URL.
- Aucune persistance, aucun re-fetch serveur des URLs d'images.

### 5.6 Front (`frontend/lib/api.ts`)

- Ajouter `image_urls?: string[]` au type décrivant le corps de requête de
  `/analyze` (interface ou type associé à `analyzeListing`).
- NE PAS modifier la signature de `analyzeListing` ni la construction de son
  `body` (le web n'émet pas `image_urls`). Documentation pure.

---

## 6. Critères d'acceptation (testables, numérotés)

Fichier de tests cible : `backend/tests/test_mobile_phase1_image_urls.py`.
Toujours via le **chemin endpoint** (`TestClient`) sauf mention contraire ; les
URLs d'image et `OPENAI` sont mockés (pas d'appel réseau réel).

> Rappel testeur — fixtures autouse existantes (conftest.py) : `_reset_photo_cache`
> (vide `app.photo_evidence._CACHE` avant chaque test → indispensable pour asserter
> un compteur d'appels), `_init_db_schema` (scope session, crée le schéma avant
> tout appel direct à `run_full_analysis`), `OPENAI_API_KEY` factice. Un test qui
> appelle `run_full_analysis` directement (hors TestClient) exige le schéma : c'est
> déjà géré par `_init_db_schema`.
>
> Technique anti-faux-vert : la PREUVE DE TRANSIT consiste à mocker
> `app.analysis.assess_claims_with_photos` (ou `app.photo_evidence.client.chat
> .completions.create`) avec une sonde qui CAPTURE l'argument `image_urls` (resp.
> les parts `image_url`) RÉELLEMENT reçu, et à asserter son contenu exact — ET la
> présence de `photo_status` dans la réponse. Mocker `assess_claims_with_photos`
> est le point d'observation recommandé pour les URLs (signature
> `(claims, image_urls)`), avec un retour contrôlé `{idx: "confirme"}`. Pour
> garantir au moins un claim éligible, fournir un `raw_text` dont l'extraction
> sémantique produit un claim de type éligible — mocker `analyze_semantic` (ou
> `app.analysis.analyze_semantic`) pour renvoyer un `local_claims` contenant un
> claim de type `cathedrale`/`nature`/`autre` et un `listing` plaçant le bien dans
> un quartier reconnu, de façon déterministe sans appel LLM réel.

### Transit réel (cœur de la feature)

- **AC1 — `test_raw_text_image_urls_transit_to_assess`** : POST
  `{"raw_text": <annonce avec claim éligible>, "image_urls": ["https://cdn.x/a.jpg",
  "https://cdn.x/b.jpg"]}`. La sonde sur `assess_claims_with_photos` est appelée
  EXACTEMENT une fois ET reçoit `image_urls == ["https://cdn.x/a.jpg",
  "https://cdn.x/b.jpg"]` (ordre et valeurs exacts). Falsifiable : rouge si le
  champ n'est pas déclaré sur `AnalyzeRequest` (sonde jamais appelée avec ces
  URLs car `image_urls` reste `None`).

- **AC2 — `test_raw_text_image_urls_photo_status_in_response`** : même requête
  qu'AC1, la sonde retourne `{0: "confirme"}`. La réponse JSON contient
  `local_context.claims[i].photo_status == "confirme"` pour le claim éligible
  d'index transité. Prouve le transit jusqu'à la RÉPONSE, pas seulement l'appel
  (couvre le masquage `response_model`, leçon 9.10).

- **AC3 — `test_run_full_analysis_direct_passes_image_urls`** : appel DIRECT
  (hors TestClient) `run_full_analysis(raw_text, image_urls=[...])` avec la sonde
  sur `assess_claims_with_photos` ; la sonde reçoit la liste fournie et le
  `photo_status` est fusionné dans le claim. Vérifie la couche sous-jacente
  indépendamment du `response_model` (leçon 9.10).

### Non-régression (rétro-compatibilité)

- **AC4 — `test_raw_text_no_image_urls_no_vision_call`** : POST
  `{"raw_text": <annonce>}` SANS `image_urls`. La sonde sur
  `assess_claims_with_photos` n'est appelée avec AUCUNE image (ou
  `_merge_photo_status` court-circuite) → aucun `photo_status` posé ; réponse
  valide. Mode `raw_text` reste sans photo (comportement actuel inchangé).

- **AC5 — `test_url_mode_no_image_urls_uses_html_extraction`** : POST
  `{"url": "https://site-ok.example/annonce"}` SANS `image_urls`, avec
  `fetch_listing` mocké renvoyant `{"text": ..., "html": <html avec og:image>}`.
  Le screening utilise les URLs issues de `extract_image_urls` (la sonde reçoit
  les URLs extraites du HTML). Mode URL sans `image_urls` strictement inchangé.

- **AC6 — `test_response_contract_unchanged_without_image_urls`** : POST sans
  `image_urls` ; la réponse contient exactement les clés du contrat
  (`global_score`, `verdict`, `confidence`, `pillars`, `actions`,
  `local_context`) et aucune clé `image_urls`. Le contrat de réponse n'a pas
  changé.

### Override URL (D1)

- **AC7 — `test_url_mode_client_image_urls_replace_html`** : POST
  `{"url": "https://site-ok.example/annonce", "image_urls": ["https://cdn.x/z.jpg"]}`
  avec `fetch_listing` renvoyant un HTML contenant d'AUTRES URLs (og:image). La
  sonde reçoit `["https://cdn.x/z.jpg"]` UNIQUEMENT (les URLs HTML sont
  remplacées, pas fusionnées). Falsifiable : rouge en cas de fusion (la liste
  contiendrait les URLs HTML).

### Sûreté / validation (D2)

- **AC8 — `test_unsafe_urls_filtered_safe_kept`** : POST `raw_text` +
  `image_urls = ["file:///etc/passwd", "http://169.254.169.254/meta",
  "http://localhost/x.jpg", "http://10.0.0.5/x.jpg",
  "https://cdn.x/ok.jpg"]`. La sonde reçoit EXACTEMENT `["https://cdn.x/ok.jpg"]`
  (les 4 premières filtrées, la publique conservée). Aucun 422.

- **AC9 — `test_all_unsafe_urls_yield_no_vision_call`** : POST `raw_text` +
  `image_urls = ["file:///x", "http://localhost/y.jpg"]` (toutes invalides). Après
  filtrage la liste est vide → aucun `photo_status` posé (équivalent « pas
  d'images »), réponse valide, AUCUN 422. La liste vide après filtrage est traitée
  comme `None`.

- **AC10 — `test_dedup_preserves_order`** : POST `raw_text` +
  `image_urls = ["https://cdn.x/a.jpg", "https://cdn.x/b.jpg",
  "https://cdn.x/a.jpg"]`. La sonde reçoit `["https://cdn.x/a.jpg",
  "https://cdn.x/b.jpg"]` (doublon retiré, ordre de première apparition préservé).

### Cap d'entrée (D3, bornes aux valeurs exactes — leçon 9.7)

- **AC11 — `test_input_cap_exactly_50_all_kept`** : POST `raw_text` + 50 URLs
  valides DISTINCTES. La sonde reçoit une liste de longueur 50 (le pipeline aval
  re-capera à 15, mais la sonde mockée observe les 50 transmises). Aucune
  troncature à 50.

- **AC12 — `test_input_cap_51_truncated_to_50`** : POST `raw_text` + 51 URLs
  valides distinctes. La sonde reçoit EXACTEMENT les 50 PREMIÈRES (longueur 50,
  ordre préservé, la 51e absente). Troncature silencieuse, aucun 422.

> Note testeur : pour observer le cap d'entrée (50) plutôt que le cap aval (15),
> la sonde doit remplacer `assess_claims_with_photos` (qui reçoit la liste AVANT
> son propre `[:MAX_IMAGES]`). Si l'on observait `client.chat.completions.create`,
> on ne verrait que 15 (cap aval) — ne pas confondre les deux caps.

### Limite documentée (D5)

- **AC13 — `test_image_urls_inert_without_eligible_claim`** : POST `raw_text`
  dont l'extraction sémantique ne produit AUCUN claim de type éligible (mock
  `analyze_semantic` → `local_claims` vides ou uniquement type non éligible, ex.
  `gare`) + `image_urls` valides. AUCUN appel vision réel
  (`client.chat.completions.create` non appelé), aucun `photo_status` posé,
  réponse valide. Confirme la limite D5 (non un bug). Observer ici le client
  vision (court-circuit dans `assess_claims_with_photos`), pas la sonde de
  remplacement.

### RGPD (logging)

- **AC14 — `test_image_urls_never_logged`** : capturer les logs du logger `mvp`
  (caplog) pendant un POST `raw_text` + `image_urls = ["https://cdn.x/secret-uniq
  -token.jpg"]`. Aucun message émis ne contient la chaîne d'URL
  (`secret-uniq-token`). Un compteur numérique est toléré. Falsifiable : rouge si
  le câblage ajoute les URLs au log d'entrée.

### Déclaration du champ (anti-faux-vert)

- **AC15 — `test_image_urls_field_declared_on_model`** : statique —
  `"image_urls" in AnalyzeRequest.model_fields`. Garde-fou contre la suppression
  du champ (un champ extra ignoré ne ferait pas échouer un POST). NB : ce test
  seul ne suffit pas (cf. AC1-AC3 pour le transit) ; il complète, ne remplace pas.

### Front

- **AC16 — `test_api_ts_documents_image_urls`** : statique — `frontend/lib/api.ts`
  contient `image_urls?: string[]` (regex tolérante aux espaces) ET la signature
  de `analyzeListing` reste `(input: string, mode: "url" | "text", district?:
  string, address?: string)` inchangée. Documente le champ sans altérer le
  comportement web.

> Toute borne (50/51) est testée aux valeurs EXACTES (leçon 9.7). Tout AC de
> transit prouve l'appel ET la réponse, jamais la seule absence de 422 (leçon
> cross-agence-inc2b-etape1).

---

## 7. Limites / risques résiduels documentés

- **L1 (D5) — inertie sans claim éligible** : `image_urls` n'a aucun effet si le
  LLM n'extrait aucun claim de type `cathedrale`/`nature`/`autre`. Comportement
  attendu, verrouillé par AC13. L'efficacité réelle de la feature dépend de la
  nature des allégations de l'annonce.
- **L2 — pas de vérification que l'URL est une image** : on relaie l'URL à OpenAI
  sans HEAD/GET serveur (interdit RGPD). Une URL valide-mais-non-image tombe sur
  le repli `non_trouve` côté `photo_evidence`. Risque fonctionnel borné, pas de
  faux `confirme`.
- **L3 — `_is_safe_url` volontairement minimal** (CLAUDE §11) : pas de résolution
  DNS, donc une URL publique pointant après résolution vers une cible interne
  n'est pas attrapée. Comme le backend ne fetche PAS les octets (c'est OpenAI), le
  risque SSRF serveur est nul ; on reste cohérent avec l'esprit minimal existant,
  sans sur-investir.
- **L4 — coût vision en mode `raw_text`** : un appel vision `gpt-4.1-mini`
  (~3-4k tokens) devient désormais déclenchable hors mode URL. Borné par le cap
  d'entrée (50→15) et amorti par le cache `photo_evidence` (TTL 7j). Cohérent avec
  le MVP (< 1 €/mois).
- **L5 — co-occurrence `url` + `image_urls`** non attendue en usage réel ; gérée
  par remplacement (D1), pas par fusion, pour éviter un ordre de cap arbitraire.

---

## 8. Hors-périmètre / non-objectifs

- Extraction des URLs côté app mobile (WebView, galerie lazy-load).
- Modification de `photo_evidence.py` (gating, `MAX_IMAGES`, `IMAGE_DETAIL`,
  cache, prompt) ou de la signature de `run_full_analysis` /
  `_merge_photo_status`.
- Élargissement de `ELIGIBLE_TYPES`.
- Tout impact sur `compute_global_score` / `breakdown` / verdicts (NON-scoré).
- Validation « l'URL est-elle réellement une image » par requête serveur.
- Émission d'`image_urls` par le client web (`analyzeListing` inchangé).

---

## 9. Conformité (anti-patterns applicables)

- **RGPD** (CLAUDE §6bis) : `image_urls` jamais loggées (au plus un compteur),
  jamais stockées, jamais re-fetchées par le serveur. Vérifié par AC14.
- **Contrat `/analyze` stable** (README l.63, CLAUDE §10) : champ additif
  optionnel, réponse inchangée, `api.ts` mis à jour (D4). Vérifié par AC6, AC16.
- **NON-scoré** (CLAUDE §6bis) : aucune touche au scoring 40/30/30.
- **Pas de secret en clair** ; aucune nouvelle variable d'env ni secret introduit.
- **Pas d'estimation de prix, pas de DVF, pas de redistribution d'annonce brute**
  (CLAUDE §1) : sans objet ici (feature purement de transit de screening photo).
- **Conventions §12** : Python 3.12, logger nommé (`mvp` côté endpoint), pas de
  commentaire « what », pas d'emoji, constante nommée `MAX_INPUT_IMAGE_URLS` (pas
  de littéral magique).

### Contenu attendu du push (pour l'audit de livrable, leçon fix-issue-80)

1. `backend/app/main.py` — champ `image_urls` sur `AnalyzeRequest` ; constante
   `MAX_INPUT_IMAGE_URLS = 50` ; fonction/inline de traitement (§5.3) ; câblage
   dans les deux branches de `/analyze` (§5.4) ; log inchangé hors compteur (§5.5).
2. `frontend/lib/api.ts` — `image_urls?: string[]` documenté (§5.6), sans toucher
   `analyzeListing`.
3. `backend/tests/test_mobile_phase1_image_urls.py` — AC1..AC16.

> Point d'ambiguïté résiduel : AUCUN. Toutes les questions GATE 1 (Q1-Q5) sont
> tranchées et reportées en D1-D5. Si le développeur découvre une incohérence
> interne d'un AC, il la SIGNALE sans l'« optimiser » (leçon cross-agence-inc2a/atelier).

SPEC prête pour GATE 2 (approbation humaine).

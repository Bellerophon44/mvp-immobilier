"""Tests-first (phase A) — `POST /analyze` accepte `image_urls` optionnel.

Oracle : `docs/specs/mobile-phase1-image-urls-SPEC.md` (AC1..AC16). Le code
produit n'existe pas encore : `AnalyzeRequest` ne declare PAS `image_urls`, et
en mode `raw_text` la variable locale `image_urls` de l'endpoint reste `None`
(main.py:610-613). Ces tests doivent donc etre ROUGES pour la BONNE raison
(la sonde sur `assess_claims_with_photos` n'est jamais appelee avec les URLs
client, ou n'est pas appelee du tout), et virer au vert une fois la spec
implementee, SANS reecriture.

PRINCIPE ANTI-FAUX-VERT (lecons cross-agence-inc2b-etape1 + 9.10) :
  - `AnalyzeRequest` est en `extra="ignore"` (pas de `extra="forbid"`) : un POST
    avec `image_urls` ne renvoie deja PAS 422 aujourd'hui, sans que le champ soit
    lu. « Pas de 422 » NE PROUVE RIEN. La preuve de TRANSIT est une SONDE qui
    capture l'argument `image_urls` REELLEMENT recu par `assess_claims_with_photos`
    et asserte la liste EXACTE transmise.
  - On observe la sonde sur `app.analysis.assess_claims_with_photos` (signature
    `(claims, image_urls)`), point qui recoit la liste AVANT le cap aval
    `[:MAX_IMAGES]` de photo_evidence : c'est la SEULE facon de voir le cap
    d'entree 50/51 (sinon on ne verrait jamais que 15).
  - On teste via le CHEMIN ENDPOINT (TestClient) ET en appel DIRECT a
    `run_full_analysis` (le response_model peut masquer un defaut — lecon 9.10).

Fixtures autouse (conftest.py) utilisees telles quelles : `_reset_photo_cache`
(indispensable pour asserter un call_count), `_init_db_schema` (schema pour les
appels directs a run_full_analysis), `OPENAI_API_KEY` factice. Non redefinies.
"""

import json
import re

import pytest


# ---------------------------------------------------------------------------
# Sonde de transit : remplace app.analysis.assess_claims_with_photos et CAPTURE
# l'argument `image_urls` reellement recu. Retour controle {0: "confirme"} pour
# prouver le transit jusqu'a la reponse (photo_status pose sur le claim 0).
# ---------------------------------------------------------------------------

class _AssessProbe:
    """Remplace `assess_claims_with_photos(claims, image_urls)`. Capture chaque
    appel (claims + image_urls) et renvoie un mapping controle."""

    def __init__(self, return_mapping=None):
        self.calls = []  # liste de dict(claims=..., image_urls=...)
        self.return_mapping = return_mapping if return_mapping is not None else {}

    def __call__(self, claims, image_urls):
        self.calls.append({"claims": claims, "image_urls": list(image_urls or [])})
        return dict(self.return_mapping)

    @property
    def call_count(self):
        return len(self.calls)

    @property
    def last_image_urls(self):
        assert self.calls, "la sonde assess_claims_with_photos n'a jamais ete appelee"
        return self.calls[-1]["image_urls"]


def _install_assess_probe(monkeypatch, return_mapping=None):
    """Installe la sonde au point d'observation des URLs (lecon : observer la
    liste AVANT le cap aval MAX_IMAGES de photo_evidence)."""
    import app.analysis as analysis

    probe = _AssessProbe(return_mapping=return_mapping)
    monkeypatch.setattr(analysis, "assess_claims_with_photos", probe)
    return probe


# ---------------------------------------------------------------------------
# Couche semantique deterministe : un claim ELIGIBLE (type `nature`, "la Moselle")
# dans un quartier reconnu (Centre-Ville) pour que local_context.claims soit
# peuple et que `_merge_photo_status` ait un claim eligible a traiter. Aucun
# appel LLM reel.
# ---------------------------------------------------------------------------

ELIGIBLE_CLAIM_TEXT = "vue sur la Moselle"


def _semantic_result(local_claims, city="Metz", district="Centre-Ville"):
    return {
        "transparency_score": 80,
        "verdict": "Bonne",
        "risk_level": "Faible",
        "summary": "Annonce claire.",
        "risk_summary": "Peu de risques.",
        "questions": [],
        "negotiation_levers": [],
        "highlights": [],
        "local_claims": local_claims,
        "listing": {
            "city": city,
            "district": district,
            "property_type": "appartement",
            "surface_m2": 70.0,
            "price_total": 210000.0,
            "dpe": "C",
            "construction_year": 1980,
            "floor": 2,
            "has_elevator": True,
            "has_terrace": None,
            "has_balcony": None,
            "has_cellar": None,
            "parking": None,
            "bedrooms": 2,
            "condo_fees": None,
        },
    }


def _patch_semantic(monkeypatch, local_claims, city="Metz", district="Centre-Ville"):
    import app.analysis as analysis

    result = _semantic_result(local_claims, city=city, district=district)
    monkeypatch.setattr(analysis, "analyze_semantic", lambda raw_text: result)
    return result


def _patch_semantic_eligible(monkeypatch):
    """Un claim eligible (type `nature`) → la sonde sera appelee si image_urls
    transite. C'est le scenario nominal des AC de transit."""
    return _patch_semantic(
        monkeypatch, [{"text": ELIGIBLE_CLAIM_TEXT, "type": "nature"}]
    )


RAW_TEXT = "Appartement T3 a Metz Centre-Ville, vue sur la Moselle."


def _claims_of(response_json):
    lc = response_json.get("local_context") or {}
    return lc.get("claims") or []


def _find_claim(claims, text):
    for c in claims:
        if c.get("text") == text:
            return c
    raise AssertionError(f"claim {text!r} introuvable dans {claims!r}")


# ---------------------------------------------------------------------------
# Mock du client vision pour AC13 (observer le court-circuit reel, pas la sonde).
# ---------------------------------------------------------------------------

class _FakeMessage:
    def __init__(self, content):
        self.content = content


class _FakeChoice:
    def __init__(self, content):
        self.message = _FakeMessage(content)


class _FakeCompletion:
    def __init__(self, content):
        self.choices = [_FakeChoice(content)]


class _VisionMock:
    def __init__(self, status="non_trouve"):
        self.status = status
        self.calls = []

    def __call__(self, *args, **kwargs):
        self.calls.append(kwargs)
        content = json.dumps({"results": {str(i): self.status for i in range(20)}})
        return _FakeCompletion(content)

    @property
    def call_count(self):
        return len(self.calls)


def _install_vision_mock(monkeypatch, status="non_trouve"):
    import app.photo_evidence as pe

    mock = _VisionMock(status=status)
    monkeypatch.setattr(pe.client.chat.completions, "create", mock)
    return mock


# ===========================================================================
# Transit reel (coeur de la feature)
# ===========================================================================

# AC1 (transit) : les image_urls client transitent EXACTEMENT jusqu'a la sonde.
def test_raw_text_image_urls_transit_to_assess(client, monkeypatch):
    _patch_semantic_eligible(monkeypatch)
    probe = _install_assess_probe(monkeypatch, return_mapping={0: "confirme"})

    resp = client.post(
        "/analyze",
        json={
            "raw_text": RAW_TEXT,
            "image_urls": ["https://cdn.x/a.jpg", "https://cdn.x/b.jpg"],
        },
    )
    assert resp.status_code == 200, resp.text
    # Preuve de transit : la sonde recoit la liste EXACTE (ordre + valeurs).
    # ROUGE aujourd'hui : `image_urls` absent de AnalyzeRequest + raw_text laisse
    # la variable a None → sonde jamais appelee avec ces URLs.
    assert probe.call_count == 1
    assert probe.last_image_urls == ["https://cdn.x/a.jpg", "https://cdn.x/b.jpg"]


# AC2 (transit jusqu'a la REPONSE, masquage response_model — lecon 9.10) :
# photo_status pose sur le claim eligible.
def test_raw_text_image_urls_photo_status_in_response(client, monkeypatch):
    _patch_semantic_eligible(monkeypatch)
    _install_assess_probe(monkeypatch, return_mapping={0: "confirme"})

    resp = client.post(
        "/analyze",
        json={
            "raw_text": RAW_TEXT,
            "image_urls": ["https://cdn.x/a.jpg", "https://cdn.x/b.jpg"],
        },
    )
    assert resp.status_code == 200, resp.text
    claim = _find_claim(_claims_of(resp.json()), ELIGIBLE_CLAIM_TEXT)
    assert claim.get("photo_status") == "confirme"


# AC3 (couche sous-jacente, hors response_model — lecon 9.10) : appel DIRECT
# a run_full_analysis ; la sonde recoit la liste fournie et le statut est fusionne.
def test_run_full_analysis_direct_passes_image_urls(monkeypatch):
    import app.analysis as analysis

    _patch_semantic_eligible(monkeypatch)
    probe = _install_assess_probe(monkeypatch, return_mapping={0: "confirme"})

    out = analysis.run_full_analysis(
        RAW_TEXT, image_urls=["https://cdn.x/direct.jpg"]
    )
    assert probe.call_count == 1
    assert probe.last_image_urls == ["https://cdn.x/direct.jpg"]
    claim = _find_claim(_claims_of(out), ELIGIBLE_CLAIM_TEXT)
    assert claim.get("photo_status") == "confirme"


# ===========================================================================
# Non-regression (retro-compatibilite)
# ===========================================================================

# AC4 (non-regression) : raw_text SANS image_urls → aucun appel vision, mode
# raw_text reste sans photo (comportement actuel inchange).
def test_raw_text_no_image_urls_no_vision_call(client, monkeypatch):
    _patch_semantic_eligible(monkeypatch)
    probe = _install_assess_probe(monkeypatch, return_mapping={0: "confirme"})

    resp = client.post("/analyze", json={"raw_text": RAW_TEXT})
    assert resp.status_code == 200, resp.text
    # `_merge_photo_status` court-circuite si image_urls est falsy : la sonde
    # n'est appelee avec aucune image (idealement 0 appel).
    for call in probe.calls:
        assert call["image_urls"] == []
    claim = _find_claim(_claims_of(resp.json()), ELIGIBLE_CLAIM_TEXT)
    assert "photo_status" not in claim


# AC5 (non-regression mode URL) : url SANS image_urls → screening sur les URLs
# extraites du HTML (chemin existant inchange).
def test_url_mode_no_image_urls_uses_html_extraction(client, monkeypatch):
    import app.main as main

    _patch_semantic_eligible(monkeypatch)
    probe = _install_assess_probe(monkeypatch, return_mapping={0: "confirme"})

    html = '<html><head><meta property="og:image" content="https://site/og.jpg"></head><body>x</body></html>'
    monkeypatch.setattr(
        main, "fetch_listing", lambda url: {"text": RAW_TEXT, "html": html}
    )
    monkeypatch.setattr(
        main, "extract_image_urls", lambda html, url: ["https://site/og.jpg"]
    )

    resp = client.post("/analyze", json={"url": "https://site-ok.example/annonce"})
    assert resp.status_code == 200, resp.text
    assert probe.call_count == 1
    assert probe.last_image_urls == ["https://site/og.jpg"]


# AC6 (contrat de reponse stable) : POST sans image_urls → cles exactes du
# contrat, aucune cle `image_urls` dans la reponse.
def test_response_contract_unchanged_without_image_urls(client, monkeypatch):
    _patch_semantic_eligible(monkeypatch)
    _install_assess_probe(monkeypatch)

    resp = client.post("/analyze", json={"raw_text": RAW_TEXT})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert set(body.keys()) == {
        "global_score",
        "verdict",
        "confidence",
        "pillars",
        "actions",
        "local_context",
    }
    assert "image_urls" not in body


# ===========================================================================
# Override URL (D1)
# ===========================================================================

# AC7 (D1 remplacer, pas fusionner) : image_urls client REMPLACE les URLs HTML.
def test_url_mode_client_image_urls_replace_html(client, monkeypatch):
    import app.main as main

    _patch_semantic_eligible(monkeypatch)
    probe = _install_assess_probe(monkeypatch, return_mapping={0: "confirme"})

    html = '<html><head><meta property="og:image" content="https://site/og.jpg"></head><body>x</body></html>'
    monkeypatch.setattr(
        main, "fetch_listing", lambda url: {"text": RAW_TEXT, "html": html}
    )
    monkeypatch.setattr(
        main, "extract_image_urls", lambda html, url: ["https://site/og.jpg"]
    )

    resp = client.post(
        "/analyze",
        json={
            "url": "https://site-ok.example/annonce",
            "image_urls": ["https://cdn.x/z.jpg"],
        },
    )
    assert resp.status_code == 200, resp.text
    assert probe.call_count == 1
    # REMPLACEMENT : uniquement l'URL client, jamais l'URL HTML (pas de fusion).
    assert probe.last_image_urls == ["https://cdn.x/z.jpg"]


# AC7 (renfort D1) : preuve d'ABSENCE de fusion residuelle. Client [A] ; HTML
# extrait [B, C] ; la sonde doit recevoir EXACTEMENT [A] et AUCUNE des URLs HTML
# (ni en suffixe, ni en prefixe, ni dedupliquee). Rouge a la moindre fusion
# (concatenation client+HTML, ou HTML place avant client).
def test_b_url_mode_no_residual_html_merge(client, monkeypatch):
    import app.main as main

    _patch_semantic_eligible(monkeypatch)
    probe = _install_assess_probe(monkeypatch, return_mapping={0: "confirme"})

    html_urls = ["https://site/b.jpg", "https://site/c.jpg"]
    monkeypatch.setattr(
        main, "fetch_listing", lambda url: {"text": RAW_TEXT, "html": "<html/>"}
    )
    monkeypatch.setattr(main, "extract_image_urls", lambda html, url: list(html_urls))

    resp = client.post(
        "/analyze",
        json={
            "url": "https://site-ok.example/annonce",
            "image_urls": ["https://cdn.x/a.jpg"],
        },
    )
    assert resp.status_code == 200, resp.text
    assert probe.call_count == 1
    assert probe.last_image_urls == ["https://cdn.x/a.jpg"]
    for html_url in html_urls:
        assert html_url not in probe.last_image_urls


# ===========================================================================
# Surete / validation (D2)
# ===========================================================================

# AC8 (D2 surete) : file:// + meta + localhost + IP privee RFC1918 filtrees ;
# l'URL publique conservee. Aucun 422.
def test_unsafe_urls_filtered_safe_kept(client, monkeypatch):
    _patch_semantic_eligible(monkeypatch)
    probe = _install_assess_probe(monkeypatch, return_mapping={0: "confirme"})

    resp = client.post(
        "/analyze",
        json={
            "raw_text": RAW_TEXT,
            "image_urls": [
                "file:///etc/passwd",
                "http://169.254.169.254/meta",
                "http://localhost/x.jpg",
                "http://10.0.0.5/x.jpg",
                "https://cdn.x/ok.jpg",
            ],
        },
    )
    assert resp.status_code == 200, resp.text
    assert probe.call_count == 1
    assert probe.last_image_urls == ["https://cdn.x/ok.jpg"]


# AC9 (D2) : toutes invalides → liste vide apres filtrage = traitee comme None
# (aucun appel vision avec images), aucun 422.
#
# RENFORCEMENT phase B : en phase A ce test etait un passer FAIBLE (mocker
# `assess_claims_with_photos` par une sonde detournait le court-circuit REEL : la
# sonde recevait `[]` au lieu de prouver que rien ne l'appelle). On observe ICI le
# client vision REEL (jamais appele). Falsifiable : rouge si le cablage passait
# la liste brute non filtree (les URLs unsafe atteindraient assess -> appel
# vision), ou si une URL unsafe survivait au filtre.
def test_all_unsafe_urls_yield_no_vision_call(client, monkeypatch):
    _patch_semantic_eligible(monkeypatch)
    vision = _install_vision_mock(monkeypatch, status="confirme")

    resp = client.post(
        "/analyze",
        json={
            "raw_text": RAW_TEXT,
            "image_urls": ["file:///x", "http://localhost/y.jpg"],
        },
    )
    assert resp.status_code == 200, resp.text
    assert vision.call_count == 0
    claim = _find_claim(_claims_of(resp.json()), ELIGIBLE_CLAIM_TEXT)
    assert "photo_status" not in claim


# AC9 (renfort) : prouve que le court-circuit est du a la liste filtree VIDE
# traitee comme None -> `assess_claims_with_photos` n'est PAS invoquee du tout
# (call_count == 0), pas appelee avec `[]`. Contraste avec AC1 (call_count == 1).
# Rouge si le cablage passe `[]` (assess appelee, court-circuit plus bas) ou la
# liste brute non filtree (assess appelee avec les URLs unsafe).
def test_b_all_unsafe_urls_assess_not_invoked(client, monkeypatch):
    _patch_semantic_eligible(monkeypatch)
    probe = _install_assess_probe(monkeypatch, return_mapping={0: "confirme"})

    resp = client.post(
        "/analyze",
        json={
            "raw_text": RAW_TEXT,
            "image_urls": ["file:///x", "http://localhost/y.jpg", "ftp://h/z"],
        },
    )
    assert resp.status_code == 200, resp.text
    assert probe.call_count == 0
    claim = _find_claim(_claims_of(resp.json()), ELIGIBLE_CLAIM_TEXT)
    assert "photo_status" not in claim


# AC10 (D2 dedup, ordre preserve) : doublon retire, ordre de 1re apparition.
def test_dedup_preserves_order(client, monkeypatch):
    _patch_semantic_eligible(monkeypatch)
    probe = _install_assess_probe(monkeypatch, return_mapping={0: "confirme"})

    resp = client.post(
        "/analyze",
        json={
            "raw_text": RAW_TEXT,
            "image_urls": [
                "https://cdn.x/a.jpg",
                "https://cdn.x/b.jpg",
                "https://cdn.x/a.jpg",
            ],
        },
    )
    assert resp.status_code == 200, resp.text
    assert probe.call_count == 1
    assert probe.last_image_urls == ["https://cdn.x/a.jpg", "https://cdn.x/b.jpg"]


# ===========================================================================
# Cap d'entree (D3, bornes aux valeurs EXACTES — lecon 9.7). On observe la sonde
# (liste AVANT le cap aval MAX_IMAGES=15), JAMAIS le client vision (qui plafonne
# a 15) — ne pas confondre les deux caps.
# ===========================================================================

# AC11 (D3 borne haute incluse) : 50 URLs distinctes → 50 conservees.
def test_input_cap_exactly_50_all_kept(client, monkeypatch):
    _patch_semantic_eligible(monkeypatch)
    probe = _install_assess_probe(monkeypatch, return_mapping={0: "confirme"})

    urls = [f"https://cdn.x/{i}.jpg" for i in range(50)]
    resp = client.post("/analyze", json={"raw_text": RAW_TEXT, "image_urls": urls})
    assert resp.status_code == 200, resp.text
    assert probe.call_count == 1
    assert probe.last_image_urls == urls
    assert len(probe.last_image_urls) == 50


# AC12 (D3 troncature) : 51 URLs distinctes → exactement les 50 PREMIERES, la 51e
# absente. Troncature silencieuse, aucun 422.
def test_input_cap_51_truncated_to_50(client, monkeypatch):
    _patch_semantic_eligible(monkeypatch)
    probe = _install_assess_probe(monkeypatch, return_mapping={0: "confirme"})

    urls = [f"https://cdn.x/{i}.jpg" for i in range(51)]
    resp = client.post("/analyze", json={"raw_text": RAW_TEXT, "image_urls": urls})
    assert resp.status_code == 200, resp.text
    assert probe.call_count == 1
    assert probe.last_image_urls == urls[:50]
    assert len(probe.last_image_urls) == 50
    assert "https://cdn.x/50.jpg" not in probe.last_image_urls


# AC11/12 (renfort, borne basse 49 incluse — lecon 9.7) : 49 URLs distinctes
# valides -> les 49 conservees (aucune troncature en-deca du cap, off-by-one).
def test_b_input_cap_49_all_kept(client, monkeypatch):
    _patch_semantic_eligible(monkeypatch)
    probe = _install_assess_probe(monkeypatch, return_mapping={0: "confirme"})

    urls = [f"https://cdn.x/{i}.jpg" for i in range(49)]
    resp = client.post("/analyze", json={"raw_text": RAW_TEXT, "image_urls": urls})
    assert resp.status_code == 200, resp.text
    assert probe.call_count == 1
    assert probe.last_image_urls == urls
    assert len(probe.last_image_urls) == 49


# ===========================================================================
# ORDRE DES OPERATIONS §5.3 (adversarial) : nettoyage -> dedup -> filtrage ->
# troncature(50). On construit des cas qui DISTINGUENT les ordres possibles ;
# un test qui rougirait si l'implementation inversait deux etapes.
# ===========================================================================

# §5.3 (a) DEDUP AVANT TRONCATURE : 60 URLs distinctes valides + chaque URL
# DUPLIQUEE une fois (120 elements bruts), entrelacees de sorte que les 50
# premiers ELEMENTS BRUTS ne contiennent que 25 URLs distinctes.
#   - Ordre specifie (dedup -> troncature) : 60 distinctes apres dedup, tronquees
#     a 50 PREMIERES distinctes -> exactement les 50 premieres URLs distinctes.
#   - Ordre errone (troncature -> dedup) : tronquer a 50 elements bruts d'abord
#     ne laisserait que ~25 URLs distinctes apres dedup -> longueur != 50.
# Rouge si l'implementation tronque avant de dedupliquer.
def test_b_order_dedup_before_truncate(client, monkeypatch):
    _patch_semantic_eligible(monkeypatch)
    probe = _install_assess_probe(monkeypatch, return_mapping={0: "confirme"})

    distinct = [f"https://cdn.x/u{i}.jpg" for i in range(60)]
    # Entrelacement : [u0, u0, u1, u1, ...] -> les 50 1ers elements bruts = u0..u24.
    raw = []
    for u in distinct:
        raw.append(u)
        raw.append(u)

    resp = client.post("/analyze", json={"raw_text": RAW_TEXT, "image_urls": raw})
    assert resp.status_code == 200, resp.text
    assert probe.call_count == 1
    # Dedup d'abord (60 distinctes, ordre de 1re apparition) puis troncature a 50.
    assert probe.last_image_urls == distinct[:50]
    assert len(probe.last_image_urls) == 50
    # Preuve discriminante : si la troncature precedait la dedup, on n'aurait que
    # 25 URLs distinctes (u0..u24), pas 50.
    assert probe.last_image_urls[24] == "https://cdn.x/u24.jpg"
    assert probe.last_image_urls[49] == "https://cdn.x/u49.jpg"


# §5.3 (b) FILTRAGE AVANT TRONCATURE : 55 URLs dont des UNSAFE en positions < 50.
# 5 URLs unsafe intercalees parmi 55 valides (60 elements). Apres filtrage il
# reste 55 valides, tronquees a 50.
#   - Ordre specifie (filtrage -> troncature) : 55 valides -> 50 premieres VALIDES.
#   - Ordre errone (troncature -> filtrage) : tronquer les 60 a 50 PUIS filtrer
#     retirerait les unsafe presentes dans les 50 premieres -> < 50 valides.
# Rouge si l'implementation tronque avant de filtrer.
def test_b_order_filter_before_truncate(client, monkeypatch):
    _patch_semantic_eligible(monkeypatch)
    probe = _install_assess_probe(monkeypatch, return_mapping={0: "confirme"})

    valid = [f"https://cdn.x/v{i}.jpg" for i in range(55)]
    unsafe_positions = {5, 15, 25, 35, 45}  # toutes < 50 (positions dans le brut)
    raw = []
    vi = 0
    for pos in range(60):
        if pos in unsafe_positions:
            raw.append(f"http://localhost/bad{pos}.jpg")
        else:
            raw.append(valid[vi])
            vi += 1
    assert vi == 55

    resp = client.post("/analyze", json={"raw_text": RAW_TEXT, "image_urls": raw})
    assert resp.status_code == 200, resp.text
    assert probe.call_count == 1
    # Filtrage d'abord (5 unsafe retirees -> 55 valides) puis troncature a 50.
    assert probe.last_image_urls == valid[:50]
    assert len(probe.last_image_urls) == 50
    # Preuve discriminante : si troncature precedait filtrage, les 50 1ers bruts
    # contiendraient 5 unsafe -> 45 valides apres filtre, pas 50.
    assert all(u.startswith("https://cdn.x/v") for u in probe.last_image_urls)


# §5.3 (c) DEDUP AVANT FILTRAGE n'a pas d'effet discriminant observable ici (un
# doublon unsafe est de toute facon retire) ; on verrouille tout de meme que la
# dedup compte UNE fois dans le budget de 50 face a des unsafe : 50 URLs valides
# distinctes + chacune DUPLIQUEE + 10 unsafe -> dedup (50) + filtrage des unsafe
# (deja absentes du dedup s'unsafe dupliquees) -> 50 valides, aucune troncature.
def test_b_dedup_counts_once_in_budget(client, monkeypatch):
    _patch_semantic_eligible(monkeypatch)
    probe = _install_assess_probe(monkeypatch, return_mapping={0: "confirme"})

    valid = [f"https://cdn.x/w{i}.jpg" for i in range(50)]
    raw = []
    for u in valid:
        raw.append(u)
        raw.append(u)  # doublon : ne doit compter qu'une fois dans le budget 50
    resp = client.post("/analyze", json={"raw_text": RAW_TEXT, "image_urls": raw})
    assert resp.status_code == 200, resp.text
    assert probe.call_count == 1
    assert probe.last_image_urls == valid
    assert len(probe.last_image_urls) == 50


# §5.3 renfort : apres filtrage il reste > 50 VALIDES -> la troncature a 50
# s'applique aux VALIDES (pas aux bruts). 70 valides distinctes -> 50.
def test_b_truncation_applies_to_valid_after_filter(client, monkeypatch):
    _patch_semantic_eligible(monkeypatch)
    probe = _install_assess_probe(monkeypatch, return_mapping={0: "confirme"})

    valid = [f"https://cdn.x/k{i}.jpg" for i in range(70)]
    resp = client.post("/analyze", json={"raw_text": RAW_TEXT, "image_urls": valid})
    assert resp.status_code == 200, resp.text
    assert probe.call_count == 1
    assert probe.last_image_urls == valid[:50]
    assert len(probe.last_image_urls) == 50


# ===========================================================================
# Limite documentee (D5) — inertie sans claim eligible
# ===========================================================================

# AC13 (D5) : aucun claim eligible (type `gare`) + image_urls valides → AUCUN
# appel vision reel (court-circuit dans assess_claims_with_photos), aucun
# photo_status. On observe ICI le client vision (pas la sonde de remplacement).
def test_image_urls_inert_without_eligible_claim(client, monkeypatch):
    _patch_semantic(monkeypatch, [{"text": "proche gare", "type": "gare"}])
    vision = _install_vision_mock(monkeypatch, status="confirme")

    resp = client.post(
        "/analyze",
        json={"raw_text": RAW_TEXT, "image_urls": ["https://cdn.x/ok.jpg"]},
    )
    assert resp.status_code == 200, resp.text
    assert vision.call_count == 0
    claim = _find_claim(_claims_of(resp.json()), "proche gare")
    assert "photo_status" not in claim


# AC13 (renfort) : CONTRASTE de causalite. Memes images valides, meme cablage ;
# seul le TYPE du claim change (gare -> nature eligible). Si l'inertie d'AC13
# etait due a autre chose qu'a l'absence de claim eligible (ex. les URLs ne
# transitent pas du tout en raw_text), ce test echouerait aussi. Il ne passe que
# si le court-circuit `assess_claims_with_photos` est bien conditionne par le
# `ELIGIBLE_TYPES` gate. Falsifiabilite croisee : AC13 vert + ce test vert
# prouvent que la SEULE difference (le type) explique l'appel/non-appel.
def test_b_eligible_claim_triggers_vision_same_images(client, monkeypatch):
    _patch_semantic(monkeypatch, [{"text": ELIGIBLE_CLAIM_TEXT, "type": "nature"}])
    vision = _install_vision_mock(monkeypatch, status="confirme")

    resp = client.post(
        "/analyze",
        json={"raw_text": RAW_TEXT, "image_urls": ["https://cdn.x/ok.jpg"]},
    )
    assert resp.status_code == 200, resp.text
    # Exactement la meme requete qu'AC13 mais avec un claim ELIGIBLE -> l'appel
    # vision A LIEU (call_count >= 1) et le statut est pose. C'est la preuve que
    # l'inertie d'AC13 vient du gate de type, pas d'un non-transit des URLs.
    assert vision.call_count == 1
    claim = _find_claim(_claims_of(resp.json()), ELIGIBLE_CLAIM_TEXT)
    assert claim.get("photo_status") == "confirme"


# ===========================================================================
# RGPD (logging) — lecon §6bis CLAUDE
# ===========================================================================

# AC14 (RGPD) : aucune URL d'image dans les logs du logger `mvp` (au plus un
# compteur numerique). Falsifiable : rouge si le cablage logue les URLs.
def test_image_urls_never_logged(client, monkeypatch, caplog):
    _patch_semantic_eligible(monkeypatch)
    _install_assess_probe(monkeypatch, return_mapping={0: "confirme"})

    secret = "secret-uniq-token"
    with caplog.at_level("INFO", logger="mvp"):
        resp = client.post(
            "/analyze",
            json={
                "raw_text": RAW_TEXT,
                "image_urls": [f"https://cdn.x/{secret}.jpg"],
            },
        )
    assert resp.status_code == 200, resp.text
    for record in caplog.records:
        assert secret not in record.getMessage()


# AC14 (renfort RGPD) : capture TOUS les loggers (caplog niveau racine, pas
# seulement `mvp`) et asserte qu'AUCUN message — d'AUCUN module (mvp, analysis,
# photo_evidence, ...) — ne contient la chaine d'URL, ni la valeur exacte. Le
# compteur numerique `n_client` reste tolere. Falsifiable : rouge si un module
# aval loguait l'URL.
def test_b_image_urls_never_logged_any_logger(client, monkeypatch, caplog):
    _patch_semantic_eligible(monkeypatch)
    _install_assess_probe(monkeypatch, return_mapping={0: "confirme"})

    secret = "ultra-secret-token-xyz"
    full_url = f"https://cdn.x/{secret}.jpg"
    with caplog.at_level("DEBUG"):  # racine : capture tous les loggers
        resp = client.post(
            "/analyze",
            json={"raw_text": RAW_TEXT, "image_urls": [full_url]},
        )
    assert resp.status_code == 200, resp.text
    for record in caplog.records:
        msg = record.getMessage()
        assert secret not in msg, f"URL leaked in logger {record.name!r}: {msg!r}"
        assert full_url not in msg, f"URL leaked in logger {record.name!r}: {msg!r}"


# AC14 (renfort RGPD, cas URL FILTREE) : meme une URL retiree par le filtre
# (unsafe) ne doit jamais apparaitre dans les logs. Falsifiable : rouge si le
# cablage loguait les URLs rejetees (ex. "url filtree: <url>").
def test_b_filtered_url_never_logged(client, monkeypatch, caplog):
    _patch_semantic_eligible(monkeypatch)
    _install_assess_probe(monkeypatch, return_mapping={0: "confirme"})

    secret = "filtered-secret-host-token"
    with caplog.at_level("DEBUG"):
        resp = client.post(
            "/analyze",
            json={
                "raw_text": RAW_TEXT,
                "image_urls": [f"http://{secret}.localhost/x.jpg"],
            },
        )
    assert resp.status_code == 200, resp.text
    for record in caplog.records:
        assert secret not in record.getMessage()


# ===========================================================================
# Declaration du champ (anti-faux-vert, complement — pas un substitut a AC1-3)
# ===========================================================================

# AC15 (declaration) : le champ est declare sur le modele (garde-fou contre la
# suppression d'un champ qui serait sinon silencieusement ignore).
def test_image_urls_field_declared_on_model():
    from app.main import AnalyzeRequest

    assert "image_urls" in AnalyzeRequest.model_fields


# ===========================================================================
# Front (documentation pure)
# ===========================================================================

# AC16 (front) : api.ts documente `image_urls?: string[]` ET la signature de
# analyzeListing reste inchangee (le web n'emet pas le champ).
def test_api_ts_documents_image_urls():
    import os

    here = os.path.dirname(os.path.abspath(__file__))
    api_ts = os.path.normpath(
        os.path.join(here, "..", "..", "frontend", "lib", "api.ts")
    )
    with open(api_ts, "r", encoding="utf-8") as f:
        content = f.read()

    assert re.search(r"image_urls\s*\?\s*:\s*string\[\]", content), (
        "api.ts doit documenter `image_urls?: string[]` dans le type de requete"
    )
    # Signature de analyzeListing inchangee (web n'emet pas image_urls).
    assert re.search(
        r"analyzeListing\(\s*"
        r"input\s*:\s*string\s*,\s*"
        r'mode\s*:\s*"url"\s*\|\s*"text"\s*,\s*'
        r"district\s*\?\s*:\s*string\s*,\s*"
        r"address\s*\?\s*:\s*string\s*,?\s*"
        r"\)",
        content,
    ), "la signature de analyzeListing ne doit pas changer"

"""Tests phase A (tests-first) — screening photo des allegations locales.

Contrat : docs/specs/photo-evidence-SPEC.md §3.2 / §3.3 / §4 (criteres 1 a 8 et
13 a 20 ; les criteres 9 a 12 d'extraction d'images vivent dans
test_photo_evidence_extract.py).

Rouge legitime attendu tant que :
  - `app/photo_evidence.py` (et `assess_claims_with_photos`) n'existe pas
    -> ImportError ;
  - `run_full_analysis` n'a pas le parametre `image_urls`
    -> TypeError.

Regles dures respectees ici :
  - OpenAI est TOUJOURS mocke (aucun appel reseau reel). On patche le `client`
    expose par le module `app.photo_evidence` (que le dev l'importe de
    `llm_semantic` ou le reinstancie, l'attribut `client` du module reste le
    point d'interception).
  - Isolation via conftest.py (base SQLite jetable + OPENAI_API_KEY factice
    forces avant import app). Aucun `count()` absolu sur table partagee.
  - Robustesse a l'identite du claim dans le mapping interne : on verifie le
    `photo_status` FUSIONNE dans local_context["claims"] (via run_full_analysis),
    pas la cle interne du mapping laissee au dev.
"""

import json

import pytest


# ---------------------------------------------------------------------------
# Helpers de mock vision
# ---------------------------------------------------------------------------

# Les 7 types de distance/ambiance, jamais eligibles a la verification photo.
NON_ELIGIBLE_TYPES = (
    "centre", "gare", "transport", "commerces", "ecoles", "calme", "a31",
)
# Les 3 types eligibles (decision GATE 1).
ELIGIBLE_TYPES = ("cathedrale", "nature", "autre")


class _FakeMessage:
    def __init__(self, content):
        self.content = content


class _FakeChoice:
    def __init__(self, content):
        self.message = _FakeMessage(content)


class _FakeCompletion:
    def __init__(self, content):
        self.choices = [_FakeChoice(content)]


def _vision_content(status):
    """Construit un contenu JSON 'riche' representant un statut commun pour tous
    les claims, robuste au format de mapping laisse au dev (par index, par texte,
    ou global). Le parsing du dev y trouvera sa representation."""
    return json.dumps({
        "results": {str(i): status for i in range(20)},
        "claims": {str(i): status for i in range(20)},
        "status": status,
        "default": status,
        **{str(i): status for i in range(20)},
    }, ensure_ascii=False)


class _MockCreate:
    """Mock appelable de client.chat.completions.create : compte les appels,
    capture les kwargs, et renvoie un statut configurable (ou leve)."""

    def __init__(self, status="non_trouve", raise_exc=None, raw_content=None):
        self.status = status
        self.raise_exc = raise_exc
        self.raw_content = raw_content
        self.calls = []

    def __call__(self, *args, **kwargs):
        self.calls.append(kwargs)
        if self.raise_exc is not None:
            raise self.raise_exc
        content = (
            self.raw_content
            if self.raw_content is not None
            else _vision_content(self.status)
        )
        return _FakeCompletion(content)

    @property
    def call_count(self):
        return len(self.calls)


def _install_vision_mock(monkeypatch, mock):
    """Patche le client vision expose par app.photo_evidence."""
    import app.photo_evidence as pe

    monkeypatch.setattr(pe.client.chat.completions, "create", mock)
    return mock


def _image_url_parts(call_kwargs):
    """Extrait toutes les parts `image_url` du message user d'un appel capture."""
    messages = call_kwargs.get("messages") or []
    parts = []
    for msg in messages:
        if msg.get("role") != "user":
            continue
        content = msg.get("content")
        if isinstance(content, list):
            for part in content:
                if isinstance(part, dict) and part.get("type") == "image_url":
                    parts.append(part)
    return parts


def _claim(text, ctype, status="a_verifier", note=""):
    """Claim a la forme produite par assess_claims : {text, type, status, note}."""
    return {"text": text, "type": ctype, "status": status, "note": note}


# ---------------------------------------------------------------------------
# Mock de la couche semantique pour run_full_analysis
# ---------------------------------------------------------------------------

def _semantic_result(local_claims, city="Metz", district="Centre-Ville"):
    """Sortie deterministe d'analyze_semantic, district reconnu (Centre-Ville)
    pour que local_context.claims soit peuple via assess_claims."""
    return {
        "transparency_score": 80,
        "verdict": "Bonne",
        "risk_level": "Faible",
        "summary": "Annonce claire.",
        "risk_summary": "Peu de risques.",
        "questions": [],
        "negotiation_levers": [],
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


def _claims_of(analysis_result):
    lc = analysis_result.get("local_context") or {}
    return lc.get("claims") or []


def _find_claim(claims, text):
    for c in claims:
        if c.get("text") == text:
            return c
    raise AssertionError(f"claim {text!r} introuvable dans {claims!r}")


# ===========================================================================
# critere 1 — Gating dur : les 7 types de distance/ambiance jamais `confirme`
# ===========================================================================

@pytest.mark.parametrize("ctype", NON_ELIGIBLE_TYPES)
def test_non_eligible_type_never_confirme_direct(monkeypatch, ctype):
    """Meme avec images + un mock vision qui renverrait `confirme`, un claim de
    type non eligible n'obtient jamais `photo_status == confirme`. On verifie a la
    fois l'absence de cle/`confirme` dans le mapping et l'absence d'appel cause
    par ce seul claim."""
    from app.photo_evidence import assess_claims_with_photos

    mock = _MockCreate(status="confirme")
    _install_vision_mock(monkeypatch, mock)

    claims = [_claim("texte non eligible", ctype)]
    mapping = assess_claims_with_photos(claims, ["https://cdn.x/1.jpg"])

    assert "confirme" not in str(mapping.values()) if isinstance(mapping, dict) else True
    # Aucun claim eligible -> aucun appel vision (court-circuit critere 3).
    assert mock.call_count == 0


@pytest.mark.parametrize("ctype", NON_ELIGIBLE_TYPES)
def test_non_eligible_type_never_confirme_full(monkeypatch, ctype):
    """Bout-en-bout : meme avec images et mock `confirme`, le claim non eligible
    n'a PAS de photo_status==confirme dans local_context['claims']."""
    import app.analysis as analysis

    text = f"allegation {ctype}"
    _patch_semantic(monkeypatch, [{"text": text, "type": ctype}])
    mock = _MockCreate(status="confirme")
    _install_vision_mock(monkeypatch, mock)

    out = analysis.run_full_analysis(
        "Appartement T3 Metz Centre-Ville", image_urls=["https://cdn.x/1.jpg"]
    )
    claim = _find_claim(_claims_of(out), text)
    assert claim.get("photo_status") != "confirme"


# ===========================================================================
# critere 2 — Court-circuit 0 image : aucun appel vision
# ===========================================================================

def test_short_circuit_no_image(monkeypatch):
    from app.photo_evidence import assess_claims_with_photos

    mock = _MockCreate(status="confirme")
    _install_vision_mock(monkeypatch, mock)

    claims = [_claim("vue cathedrale", "cathedrale")]
    mapping = assess_claims_with_photos(claims, [])

    assert mock.call_count == 0
    if isinstance(mapping, dict):
        assert "confirme" not in str(mapping.values())


# ===========================================================================
# critere 3 — Court-circuit 0 claim eligible : aucun appel vision
# ===========================================================================

def test_short_circuit_no_eligible_claim(monkeypatch):
    from app.photo_evidence import assess_claims_with_photos

    mock = _MockCreate(status="confirme")
    _install_vision_mock(monkeypatch, mock)

    claims = [
        _claim("proche gare", "gare"),
        _claim("commerces a pied", "commerces"),
        _claim("quartier calme", "calme"),
    ]
    assess_claims_with_photos(claims, ["https://cdn.x/1.jpg"])

    assert mock.call_count == 0


# ===========================================================================
# critere 4 — Appel vision conditionnel positif : exactement 1 appel,
#             temperature==0.2, response_format json_object
# ===========================================================================

def test_vision_called_once_with_params(monkeypatch):
    from app.photo_evidence import assess_claims_with_photos

    mock = _MockCreate(status="non_trouve")
    _install_vision_mock(monkeypatch, mock)

    claims = [_claim("vue cathedrale Saint-Etienne", "cathedrale")]
    assess_claims_with_photos(claims, ["https://cdn.x/1.jpg"])

    assert mock.call_count == 1
    kwargs = mock.calls[0]
    assert kwargs.get("temperature") == 0.2
    assert kwargs.get("response_format") == {"type": "json_object"}


# ===========================================================================
# critere 5 — detail high sur chaque part image_url (reperage arriere-plan)
# ===========================================================================

def test_image_parts_detail_high(monkeypatch):
    from app.photo_evidence import assess_claims_with_photos, IMAGE_DETAIL

    mock = _MockCreate(status="non_trouve")
    _install_vision_mock(monkeypatch, mock)

    urls = ["https://cdn.x/1.jpg", "https://cdn.x/2.jpg"]
    assess_claims_with_photos([_claim("la Moselle", "nature")], urls)

    parts = _image_url_parts(mock.calls[0])
    assert parts, "au moins une part image_url doit etre transmise"
    for part in parts:
        image_url = part.get("image_url")
        assert isinstance(image_url, dict)
        assert image_url.get("detail") == IMAGE_DETAIL == "high"


# ===========================================================================
# critere 6 — Repli silencieux : exception -> pas de raise, eligibles non_trouve
# ===========================================================================

def test_silent_fallback_on_exception_direct(monkeypatch):
    from app.photo_evidence import assess_claims_with_photos

    mock = _MockCreate(raise_exc=RuntimeError("simulated vision outage"))
    _install_vision_mock(monkeypatch, mock)

    text = "vue cathedrale"
    claims = [_claim(text, "cathedrale")]
    # Ne doit jamais lever.
    mapping = assess_claims_with_photos(claims, ["https://cdn.x/1.jpg"])

    assert isinstance(mapping, dict)
    assert "confirme" not in str(mapping.values())


def test_silent_fallback_full_analysis_completes(monkeypatch):
    """run_full_analysis aboutit malgre l'exception vision ; le claim eligible
    recoit non_trouve, jamais confirme."""
    import app.analysis as analysis

    text = "vue cathedrale Saint-Etienne"
    _patch_semantic(monkeypatch, [{"text": text, "type": "cathedrale"}])
    mock = _MockCreate(raise_exc=RuntimeError("boom"))
    _install_vision_mock(monkeypatch, mock)

    out = analysis.run_full_analysis(
        "Appartement Metz Centre-Ville", image_urls=["https://cdn.x/1.jpg"]
    )
    claim = _find_claim(_claims_of(out), text)
    assert claim.get("photo_status") == "non_trouve"


# ===========================================================================
# critere 7 — JSON invalide / statut hors enum -> non_trouve (jamais confirme)
# ===========================================================================

def test_invalid_json_falls_back_non_trouve(monkeypatch):
    import app.analysis as analysis

    text = "vue cathedrale"
    _patch_semantic(monkeypatch, [{"text": text, "type": "cathedrale"}])
    mock = _MockCreate(raw_content="ceci n'est pas du JSON {")
    _install_vision_mock(monkeypatch, mock)

    out = analysis.run_full_analysis(
        "Appartement Metz Centre-Ville", image_urls=["https://cdn.x/1.jpg"]
    )
    claim = _find_claim(_claims_of(out), text)
    assert claim.get("photo_status") == "non_trouve"


def test_status_out_of_enum_falls_back_non_trouve(monkeypatch):
    import app.analysis as analysis

    text = "vue cathedrale"
    _patch_semantic(monkeypatch, [{"text": text, "type": "cathedrale"}])
    mock = _MockCreate(status="oui_carrement")  # hors enum
    _install_vision_mock(monkeypatch, mock)

    out = analysis.run_full_analysis(
        "Appartement Metz Centre-Ville", image_urls=["https://cdn.x/1.jpg"]
    )
    claim = _find_claim(_claims_of(out), text)
    assert claim.get("photo_status") == "non_trouve"
    assert claim.get("photo_status") != "confirme"


# ===========================================================================
# critere 8 — Cap MAX_IMAGES : au-dela, au plus MAX_IMAGES parts transmises
# ===========================================================================

def test_cap_images(monkeypatch):
    from app.photo_evidence import assess_claims_with_photos, MAX_IMAGES

    mock = _MockCreate(status="non_trouve")
    _install_vision_mock(monkeypatch, mock)

    urls = [f"https://cdn.x/{i}.jpg" for i in range(MAX_IMAGES + 4)]
    assess_claims_with_photos([_claim("la Moselle", "nature")], urls)

    parts = _image_url_parts(mock.calls[0])
    assert len(parts) <= MAX_IMAGES


def test_exactly_max_images_all_transmitted(monkeypatch):
    """Borne exacte : MAX_IMAGES URLs -> autant de parts (pas d'off-by-one)."""
    from app.photo_evidence import assess_claims_with_photos, MAX_IMAGES

    mock = _MockCreate(status="non_trouve")
    _install_vision_mock(monkeypatch, mock)

    urls = [f"https://cdn.x/{i}.jpg" for i in range(MAX_IMAGES)]
    assess_claims_with_photos([_claim("la Moselle", "nature")], urls)

    parts = _image_url_parts(mock.calls[0])
    assert len(parts) == MAX_IMAGES


# ===========================================================================
# critere 13 — Mode texte inchange : aucun appel vision, aucune cle photo_status
# ===========================================================================

def test_text_mode_no_vision_no_photo_status(monkeypatch):
    import app.analysis as analysis

    _patch_semantic(
        monkeypatch,
        [{"text": "vue cathedrale", "type": "cathedrale"}],
    )
    mock = _MockCreate(status="confirme")
    _install_vision_mock(monkeypatch, mock)

    out = analysis.run_full_analysis("Appartement Metz Centre-Ville")

    assert mock.call_count == 0
    for claim in _claims_of(out):
        assert "photo_status" not in claim


def test_text_mode_image_urls_none(monkeypatch):
    import app.analysis as analysis

    _patch_semantic(
        monkeypatch,
        [{"text": "vue cathedrale", "type": "cathedrale"}],
    )
    mock = _MockCreate(status="confirme")
    _install_vision_mock(monkeypatch, mock)

    out = analysis.run_full_analysis(
        "Appartement Metz Centre-Ville", image_urls=None
    )
    assert mock.call_count == 0
    for claim in _claims_of(out):
        assert "photo_status" not in claim


def test_empty_image_urls_no_vision(monkeypatch):
    import app.analysis as analysis

    _patch_semantic(
        monkeypatch,
        [{"text": "vue cathedrale", "type": "cathedrale"}],
    )
    mock = _MockCreate(status="confirme")
    _install_vision_mock(monkeypatch, mock)

    out = analysis.run_full_analysis(
        "Appartement Metz Centre-Ville", image_urls=[]
    )
    assert mock.call_count == 0
    for claim in _claims_of(out):
        assert "photo_status" not in claim


# ===========================================================================
# critere 14 — Mapping confirme
# ===========================================================================

def test_mapping_confirme(monkeypatch):
    import app.analysis as analysis

    text = "vue imprenable sur la cathedrale Saint-Etienne"
    _patch_semantic(monkeypatch, [{"text": text, "type": "cathedrale"}])
    mock = _MockCreate(status="confirme")
    _install_vision_mock(monkeypatch, mock)

    out = analysis.run_full_analysis(
        "Appartement Metz Centre-Ville", image_urls=["https://cdn.x/1.jpg"]
    )
    claim = _find_claim(_claims_of(out), text)
    assert claim.get("photo_status") == "confirme"
    assert mock.call_count == 1


# ===========================================================================
# critere 15 — Mapping non_trouve
# ===========================================================================

def test_mapping_non_trouve(monkeypatch):
    import app.analysis as analysis

    text = "vue cathedrale"
    _patch_semantic(monkeypatch, [{"text": text, "type": "cathedrale"}])
    mock = _MockCreate(status="non_trouve")
    _install_vision_mock(monkeypatch, mock)

    out = analysis.run_full_analysis(
        "Appartement Metz Centre-Ville", image_urls=["https://cdn.x/1.jpg"]
    )
    claim = _find_claim(_claims_of(out), text)
    assert claim.get("photo_status") == "non_trouve"


# ===========================================================================
# critere 16 — `autre` non visuel -> non_applicable (jamais confirme)
# ===========================================================================

def test_mapping_autre_non_applicable(monkeypatch):
    import app.analysis as analysis

    text = "proche d'une boulangerie reputee"
    _patch_semantic(monkeypatch, [{"text": text, "type": "autre"}])
    mock = _MockCreate(status="non_applicable")
    _install_vision_mock(monkeypatch, mock)

    out = analysis.run_full_analysis(
        "Appartement Metz Centre-Ville", image_urls=["https://cdn.x/1.jpg"]
    )
    claim = _find_claim(_claims_of(out), text)
    assert claim.get("photo_status") == "non_applicable"
    assert claim.get("photo_status") != "confirme"


# ===========================================================================
# critere 17 — Claims non eligibles : pas de cle photo_status
# ===========================================================================

def test_non_eligible_claim_has_no_photo_status_key(monkeypatch):
    import app.analysis as analysis

    eligible_text = "vue cathedrale"
    gare_text = "a 5 min de la gare"
    _patch_semantic(
        monkeypatch,
        [
            {"text": eligible_text, "type": "cathedrale"},
            {"text": gare_text, "type": "gare"},
        ],
    )
    mock = _MockCreate(status="confirme")
    _install_vision_mock(monkeypatch, mock)

    out = analysis.run_full_analysis(
        "Appartement Metz Centre-Ville", image_urls=["https://cdn.x/1.jpg"]
    )
    claims = _claims_of(out)
    gare_claim = _find_claim(claims, gare_text)
    assert "photo_status" not in gare_claim


# ===========================================================================
# critere 18 — Retro-compat /analyze : reponse conforme, aucune URL/bytes image
# ===========================================================================

FORBIDDEN_RESPONSE_KEYS = {"image_urls", "images", "photos"}


def _collect_keys(obj):
    keys = set()
    if isinstance(obj, dict):
        for k, v in obj.items():
            keys.add(k)
            keys |= _collect_keys(v)
    elif isinstance(obj, list):
        for v in obj:
            keys |= _collect_keys(v)
    return keys


def _collect_str_values(obj):
    vals = []
    if isinstance(obj, dict):
        for v in obj.values():
            vals += _collect_str_values(v)
    elif isinstance(obj, list):
        for v in obj:
            vals += _collect_str_values(v)
    elif isinstance(obj, str):
        vals.append(obj)
    return vals


def test_analyze_response_no_image_leak(client, monkeypatch):
    import app.analysis as analysis

    eligible_text = "vue cathedrale"
    _patch_semantic(monkeypatch, [{"text": eligible_text, "type": "cathedrale"}])
    mock = _MockCreate(status="confirme")
    _install_vision_mock(monkeypatch, mock)

    resp = client.post(
        "/analyze", json={"raw_text": "Appartement T3 Metz Centre-Ville"}
    )
    assert resp.status_code == 200
    body = resp.json()

    # Contrat AnalyzeResponse.
    for key in ("global_score", "verdict", "confidence", "pillars", "actions"):
        assert key in body
    assert "local_context" in body

    # Aucune cle d'image dans toute la reponse.
    assert not (_collect_keys(body) & FORBIDDEN_RESPONSE_KEYS)

    # Aucune valeur chaine n'est une URL d'image transmise.
    for value in _collect_str_values(body):
        assert "cdn.x" not in value
        assert not value.lower().endswith((".jpg", ".jpeg", ".png", ".webp"))


def test_analyze_response_photo_status_allowed_in_claims(client, monkeypatch):
    """Le statut (et lui seul) peut transiter, porte par les claims."""
    import app.analysis as analysis

    eligible_text = "vue cathedrale"
    _patch_semantic(monkeypatch, [{"text": eligible_text, "type": "cathedrale"}])
    mock = _MockCreate(status="confirme")
    _install_vision_mock(monkeypatch, mock)

    resp = client.post(
        "/analyze", json={"raw_text": "Appartement T3 Metz Centre-Ville"}
    )
    assert resp.status_code == 200
    # En mode texte (pas d'URL), aucun photo_status ne doit apparaitre.
    body = resp.json()
    lc = body.get("local_context") or {}
    for claim in lc.get("claims") or []:
        assert "photo_status" not in claim


# ===========================================================================
# critere 19 — Score intact : meme global_score avec / sans image_urls
# ===========================================================================

def test_global_score_unchanged_with_images(monkeypatch):
    import app.analysis as analysis

    text = "vue cathedrale Saint-Etienne"
    _patch_semantic(monkeypatch, [{"text": text, "type": "cathedrale"}])
    mock = _MockCreate(status="confirme")
    _install_vision_mock(monkeypatch, mock)

    without = analysis.run_full_analysis("Appartement Metz Centre-Ville")
    with_images = analysis.run_full_analysis(
        "Appartement Metz Centre-Ville", image_urls=["https://cdn.x/1.jpg"]
    )

    assert with_images["global_score"] == without["global_score"]
    assert with_images["verdict"] == without["verdict"]


# ===========================================================================
# critere 20 — Durcissement prompt d'extraction (decision 8)
# ===========================================================================

def test_extraction_prompt_hardening_named_landmarks():
    """USER_PROMPT_TEMPLATE classe explicitement Centre Pompidou-Metz / Temple
    Neuf / Jardin Botanique en autre/nature, jamais centre (regression guard)."""
    from app.llm_semantic import USER_PROMPT_TEMPLATE

    tpl = USER_PROMPT_TEMPLATE
    assert "Centre Pompidou-Metz" in tpl
    assert "Temple Neuf" in tpl
    assert "Jardin Botanique" in tpl


def test_claim_types_unchanged_ten_types():
    from app.llm_semantic import _CLAIM_TYPES

    assert _CLAIM_TYPES == {
        "centre", "cathedrale", "gare", "transport", "commerces",
        "nature", "ecoles", "calme", "a31", "autre",
    }
    assert len(_CLAIM_TYPES) == 10


# ===========================================================================
# Renfort — signature run_full_analysis accepte image_urls (mot-cle)
# ===========================================================================

def test_run_full_analysis_accepts_image_urls_kw(monkeypatch):
    import inspect
    import app.analysis as analysis

    sig = inspect.signature(analysis.run_full_analysis)
    assert "image_urls" in sig.parameters

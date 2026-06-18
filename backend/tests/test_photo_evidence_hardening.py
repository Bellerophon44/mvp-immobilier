"""Tests durcissants phase B (challenge adversarial) — photo-evidence.

Le TESTEUR cherche ici les trous que les 20 criteres de la spec ne capturent
pas explicitement :
  - le gating doit dependre du `type`, JAMAIS du `text` (un claim `centre`
    dont le texte contient "cathedrale" ne doit jamais fuiter `confirme`) ;
  - cap exact 6 (6 fournis -> 6 ; 7/8/20 fournis -> <=6) ;
  - isolation + correction du cache memoire (`_CACHE`) : hit intra-test sur
    couple identique, miss sur claims differents a images identiques ;
  - repli sur du parsing laxiste (MAJUSCULES, accents, espaces internes) ->
    `non_trouve`, jamais `confirme` par tolerance ;
  - aucun claim non eligible n'acquiert jamais `photo_status`, meme en mode URL.

Memes regles dures que test_photo_evidence.py : OpenAI mocke (aucun reseau),
isolation conftest (base SQLite jetable, OPENAI_API_KEY factice, reset _CACHE).
"""

import json

import pytest


# ---------------------------------------------------------------------------
# Helpers (reprend la forme de test_photo_evidence.py pour rester homogene)
# ---------------------------------------------------------------------------

NON_ELIGIBLE_TYPES = (
    "centre", "gare", "transport", "commerces", "ecoles", "calme", "a31",
)


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
    return json.dumps({
        "results": {str(i): status for i in range(20)},
    }, ensure_ascii=False)


class _MockCreate:
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
    import app.photo_evidence as pe

    monkeypatch.setattr(pe.client.chat.completions, "create", mock)
    return mock


def _image_url_parts(call_kwargs):
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
    return {"text": text, "type": ctype, "status": status, "note": note}


def _semantic_result(local_claims, city="Metz", district="Centre-Ville"):
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


def _patch_semantic(monkeypatch, local_claims):
    import app.analysis as analysis

    result = _semantic_result(local_claims)
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
# Gating par TYPE, jamais par TEXT (renfort critere 1)
# ===========================================================================

def test_gating_uses_type_not_text_centre_with_cathedrale_word(monkeypatch):
    """Un claim de type `centre` dont le TEXTE contient 'cathedrale' ne doit
    JAMAIS etre transmis a la vision ni recevoir confirme : c'est le `type` qui
    gate, pas le contenu lexical du texte."""
    from app.photo_evidence import assess_claims_with_photos

    mock = _MockCreate(status="confirme")
    _install_vision_mock(monkeypatch, mock)

    claims = [_claim("a deux pas de la cathedrale et du centre", "centre")]
    mapping = assess_claims_with_photos(claims, ["https://cdn.x/1.jpg"])

    assert mock.call_count == 0
    assert mapping == {}


def test_gating_uses_type_not_text_full_analysis(monkeypatch):
    """Bout-en-bout : type non eligible + texte evoquant un repere visuel ->
    aucun photo_status, jamais confirme."""
    import app.analysis as analysis

    text = "vue cathedrale depuis le centre, nature et Moselle a proximite"
    _patch_semantic(monkeypatch, [{"text": text, "type": "centre"}])
    mock = _MockCreate(status="confirme")
    _install_vision_mock(monkeypatch, mock)

    out = analysis.run_full_analysis(
        "Appartement Metz Centre-Ville", image_urls=["https://cdn.x/1.jpg"]
    )
    claim = _find_claim(_claims_of(out), text)
    assert "photo_status" not in claim
    assert mock.call_count == 0


@pytest.mark.parametrize("ctype", NON_ELIGIBLE_TYPES)
def test_non_eligible_mixed_with_eligible_no_leak(monkeypatch, ctype):
    """Mix d'un claim eligible et d'un non eligible (texte trompeur) : seul
    l'eligible est evalue ; le non eligible n'a pas de cle photo_status meme si
    son texte parle de cathedrale/nature."""
    import app.analysis as analysis

    elig = "vraie vue cathedrale"
    non_elig = "cathedrale et nature evoquees mais type non visuel"
    _patch_semantic(
        monkeypatch,
        [
            {"text": elig, "type": "cathedrale"},
            {"text": non_elig, "type": ctype},
        ],
    )
    mock = _MockCreate(status="confirme")
    _install_vision_mock(monkeypatch, mock)

    out = analysis.run_full_analysis(
        "Appartement Metz Centre-Ville", image_urls=["https://cdn.x/1.jpg"]
    )
    claims = _claims_of(out)
    assert _find_claim(claims, elig).get("photo_status") == "confirme"
    assert "photo_status" not in _find_claim(claims, non_elig)


# ===========================================================================
# Cap exact MAX_IMAGES (renfort critere 8 ; esprit lecon "bornes exactes")
# ===========================================================================

@pytest.mark.parametrize("extra", [1, 2, 14])
def test_cap_strict_upper(monkeypatch, extra):
    """Au-dela de MAX_IMAGES URLs, exactement MAX_IMAGES parts sont transmises."""
    from app.photo_evidence import assess_claims_with_photos, MAX_IMAGES

    mock = _MockCreate(status="non_trouve")
    _install_vision_mock(monkeypatch, mock)

    urls = [f"https://cdn.x/{i}.jpg" for i in range(MAX_IMAGES + extra)]
    assess_claims_with_photos([_claim("la Moselle", "nature")], urls)

    parts = _image_url_parts(mock.calls[0])
    assert len(parts) == MAX_IMAGES


@pytest.mark.parametrize("offset", [0, -1, -14])
def test_cap_below_or_equal_all_transmitted(monkeypatch, offset):
    """Borne basse / exacte : <=MAX_IMAGES URLs -> toutes transmises (pas de
    troncature off-by-one qui en perdrait une a la borne)."""
    from app.photo_evidence import assess_claims_with_photos, MAX_IMAGES

    mock = _MockCreate(status="non_trouve")
    _install_vision_mock(monkeypatch, mock)

    n = MAX_IMAGES + offset
    urls = [f"https://cdn.x/{i}.jpg" for i in range(n)]
    assess_claims_with_photos([_claim("la Moselle", "nature")], urls)

    parts = _image_url_parts(mock.calls[0])
    assert len(parts) == n


def test_cap_first_images_in_priority_order(monkeypatch):
    """Le cap retient les MAX_IMAGES PREMIERES URLs (ordre de priorite preserve),
    pas un sous-ensemble arbitraire : preuve que la troncature est un prefixe."""
    from app.photo_evidence import assess_claims_with_photos, MAX_IMAGES

    mock = _MockCreate(status="non_trouve")
    _install_vision_mock(monkeypatch, mock)

    urls = [f"https://cdn.x/{i}.jpg" for i in range(MAX_IMAGES + 5)]
    assess_claims_with_photos([_claim("la Moselle", "nature")], urls)

    parts = _image_url_parts(mock.calls[0])
    transmitted = [p["image_url"]["url"] for p in parts]
    assert transmitted == urls[:MAX_IMAGES]


# ===========================================================================
# Cache memoire : hit sur couple identique, miss sur claims differents
# ===========================================================================

def test_cache_hit_same_images_same_claims(monkeypatch):
    """Un meme couple (images, claims) ne declenche qu'UN appel vision : le 2e
    appel identique est servi par le cache (0 nouvel appel)."""
    from app.photo_evidence import assess_claims_with_photos

    mock = _MockCreate(status="confirme")
    _install_vision_mock(monkeypatch, mock)

    claims = [_claim("vue cathedrale", "cathedrale")]
    urls = ["https://cdn.x/1.jpg", "https://cdn.x/2.jpg"]

    first = assess_claims_with_photos(claims, urls)
    assert mock.call_count == 1
    second = assess_claims_with_photos(claims, urls)
    assert mock.call_count == 1  # cache hit, pas de nouvel appel
    assert first == second


def test_cache_miss_different_claims_same_images(monkeypatch):
    """La cle de cache discrimine sur les CLAIMS, pas seulement les images :
    memes images mais claims differents -> nouvel appel vision (pas de fuite du
    resultat precedent)."""
    from app.photo_evidence import assess_claims_with_photos

    mock = _MockCreate(status="confirme")
    _install_vision_mock(monkeypatch, mock)

    urls = ["https://cdn.x/1.jpg", "https://cdn.x/2.jpg"]

    assess_claims_with_photos([_claim("vue cathedrale", "cathedrale")], urls)
    assert mock.call_count == 1
    assess_claims_with_photos([_claim("la Moselle en contrebas", "nature")], urls)
    assert mock.call_count == 2  # claims differents -> cache miss legitime


def test_cache_miss_different_images_same_claims(monkeypatch):
    """Symetrie : memes claims mais images differentes -> nouvel appel."""
    from app.photo_evidence import assess_claims_with_photos

    mock = _MockCreate(status="confirme")
    _install_vision_mock(monkeypatch, mock)

    claims = [_claim("vue cathedrale", "cathedrale")]

    assess_claims_with_photos(claims, ["https://cdn.x/1.jpg"])
    assert mock.call_count == 1
    assess_claims_with_photos(claims, ["https://cdn.x/2.jpg"])
    assert mock.call_count == 2


def test_cache_isolated_between_tests_marker(monkeypatch):
    """Garde-fou anti-fuite inter-tests : au debut de CE test, le cache doit etre
    vide (reset par la fixture autouse _reset_photo_cache du conftest). Si un
    autre test avait laisse une entree, ce marqueur le detecterait."""
    import app.photo_evidence as pe

    assert pe._CACHE == {}


# ===========================================================================
# Repli sur parsing laxiste : MAJUSCULES / accents / espaces internes
# ===========================================================================

@pytest.mark.parametrize(
    "bad_status",
    ["CONFIRME", "Confirme", "confirmé", "con firme", "confirme!", "  confirme x"],
)
def test_laxist_confirme_variants_fall_back_non_trouve(monkeypatch, bad_status):
    """Un statut presque-confirme (casse, accent, espace interne, ponctuation)
    ne doit JAMAIS etre accepte comme confirme : repli sur non_trouve."""
    import app.analysis as analysis

    text = "vue cathedrale"
    _patch_semantic(monkeypatch, [{"text": text, "type": "cathedrale"}])
    raw = json.dumps({"results": {"0": bad_status}}, ensure_ascii=False)
    mock = _MockCreate(raw_content=raw)
    _install_vision_mock(monkeypatch, mock)

    out = analysis.run_full_analysis(
        "Appartement Metz Centre-Ville", image_urls=["https://cdn.x/1.jpg"]
    )
    claim = _find_claim(_claims_of(out), text)
    assert claim.get("photo_status") == "non_trouve"
    assert claim.get("photo_status") != "confirme"


def test_surrounding_whitespace_confirme_accepted(monkeypatch):
    """Tolerance LEGITIME (et bornee) : un confirme entoure d'espaces seulement
    (' confirme ') reste accepte (strip), ce n'est pas du laxisme semantique.
    Verrouille le comportement actuel pour eviter une regression dans un sens ou
    l'autre."""
    import app.analysis as analysis

    text = "vue cathedrale"
    _patch_semantic(monkeypatch, [{"text": text, "type": "cathedrale"}])
    raw = json.dumps({"results": {"0": "  confirme  "}}, ensure_ascii=False)
    mock = _MockCreate(raw_content=raw)
    _install_vision_mock(monkeypatch, mock)

    out = analysis.run_full_analysis(
        "Appartement Metz Centre-Ville", image_urls=["https://cdn.x/1.jpg"]
    )
    claim = _find_claim(_claims_of(out), text)
    assert claim.get("photo_status") == "confirme"


# ===========================================================================
# Mode URL : un claim non eligible n'acquiert JAMAIS photo_status (critere 17
# renforce, y compris quand un eligible est present et confirme)
# ===========================================================================

def test_url_mode_no_photo_status_on_any_non_eligible(monkeypatch):
    """En mode URL avec un eligible confirme, AUCUN des claims non eligibles
    n'a la cle photo_status (couverture des 7 types en une passe)."""
    import app.analysis as analysis

    eligible = "vue cathedrale"
    local_claims = [{"text": eligible, "type": "cathedrale"}]
    for t in NON_ELIGIBLE_TYPES:
        local_claims.append({"text": f"claim {t}", "type": t})
    _patch_semantic(monkeypatch, local_claims)
    mock = _MockCreate(status="confirme")
    _install_vision_mock(monkeypatch, mock)

    out = analysis.run_full_analysis(
        "Appartement Metz Centre-Ville", image_urls=["https://cdn.x/1.jpg"]
    )
    claims = _claims_of(out)
    assert _find_claim(claims, eligible).get("photo_status") == "confirme"
    for t in NON_ELIGIBLE_TYPES:
        c = _find_claim(claims, f"claim {t}")
        assert "photo_status" not in c, f"fuite photo_status sur type {t}"


# ===========================================================================
# RGPD : les URLs d'images ne doivent jamais etre loggees (analyse §7)
# ===========================================================================

def test_image_urls_never_logged(monkeypatch, caplog):
    """Aucune URL d'image ne doit apparaitre dans les logs du module
    photo_evidence (RGPD, anti-pattern #3)."""
    import logging
    from app.photo_evidence import assess_claims_with_photos

    mock = _MockCreate(status="non_trouve")
    _install_vision_mock(monkeypatch, mock)

    secret_url = "https://cdn.secret-agency.fr/photo-privee-12345.jpg"
    with caplog.at_level(logging.DEBUG, logger="photo_evidence"):
        assess_claims_with_photos([_claim("la Moselle", "nature")], [secret_url])

    for record in caplog.records:
        assert secret_url not in record.getMessage()
        assert "secret-agency" not in record.getMessage()


def test_image_urls_never_logged_on_failure(monkeypatch, caplog):
    """Meme sur exception (repli silencieux), l'URL ne fuit pas dans le log."""
    import logging
    from app.photo_evidence import assess_claims_with_photos

    mock = _MockCreate(raise_exc=RuntimeError("boom"))
    _install_vision_mock(monkeypatch, mock)

    secret_url = "https://cdn.secret-agency.fr/photo-privee-67890.jpg"
    with caplog.at_level(logging.DEBUG, logger="photo_evidence"):
        assess_claims_with_photos([_claim("la Moselle", "nature")], [secret_url])

    for record in caplog.records:
        assert secret_url not in record.getMessage()

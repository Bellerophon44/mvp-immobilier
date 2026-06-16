"""Phase B (challenge adversarial) — issue #100, chantier C, sous-palier C1.

Ces tests CHERCHENT activement les trous que la phase A (test_issue_100_C.py,
25 tests verts) n'a pas couverts. Ils s'appuient sur la spec
docs/specs/issue-100-C-SPEC.md §3.4 / §4 et sur le diff livre (geocode.py,
geo_gazetteer.py, market_stats.py). Pistes adversariales :

  1. Inter-communal AVEC bande DPE : le candidat quartier+DPE reunit-il les deux
     communes (et pas seulement le candidat quartier-sans-DPE) ?
  2. Bien cote Montigny d'un quartier inter-communal (symetrie Metz<->Montigny).
  3. Preseance ville/metropole : les niveaux secteur/ville/metropole ne recoivent
     JAMAIS `cities` de la table inter-communale ; la regle "ville preferee des
     MIN_COMPARABLES" reste intacte.
  4. Canonicalisation des communes de la table vs forme stockee.
  5. _INTERCOMMUNAL fige a l'import : coherence du chemin reellement parcouru.
  6. geocode enrichi : postcode absent (garde-fou dept), city sans citycode,
     features vides.
  7. Non-regression fine : un quartier mono-commune AVEC adresse geocodee garde
     le meme pool (pas d'elargissement venu d'une adresse).

Suite GRATUITE, deterministe : aucun appel reseau / LLM reel. Isolation par les
fixtures autouse du conftest. Le fichier NE modifie pas le code de production ni
les tests existants. Les helpers locaux (insert, BAN feature) repliquent ceux de
test_issue_100_C.py pour rester autonome (un fichier compagnon ne doit pas
importer un autre fichier de tests).
"""

import uuid

import pytest

import app.market_stats as market_stats
from app.market_stats import (
    MIN_COMPARABLES,
    MIN_REFINED_COMPARABLES,
    _METRO_CITIES,
    compute_market_stats,
)
from db.models import Comparable
from db.session import SessionLocal
from scrapers.base import canonical_city


CANON_ST = "Sainte-Therese"
COMMUNE_METZ = "Metz"
COMMUNE_MONTIGNY = "Montigny-Les-Metz"

SURFACE = 70.0
COMP_SURFACE = 70.0


def _insert(city, prices, district=None, property_type="appartement", dpe=None,
            surface=COMP_SURFACE):
    db = SessionLocal()
    try:
        canon = canonical_city(city)
        for pm2 in prices:
            db.add(Comparable(
                id=f"c1adv-{uuid.uuid4().hex}",
                source="test",
                city=canon,
                district=district,
                property_type=property_type,
                surface_m2=surface,
                price_total=pm2 * surface,
                price_m2=pm2,
                dpe=dpe,
            ))
        db.commit()
    finally:
        db.close()


def _spy_fetch(monkeypatch):
    calls = []
    original = market_stats._fetch_comparables

    def _spy(city, district, property_type, surface_min, surface_max,
             dpe_letters=None, districts=None, cities=None):
        calls.append({
            "city": city, "district": district, "districts": districts,
            "cities": None if cities is None else tuple(cities),
            "dpe_letters": None if dpe_letters is None else frozenset(dpe_letters),
        })
        return original(city, district, property_type, surface_min, surface_max,
                        dpe_letters=dpe_letters, districts=districts, cities=cities)

    monkeypatch.setattr(market_stats, "_fetch_comparables", _spy)
    return calls


# ===========================================================================
# Piste 1 — inter-communal AVEC bande DPE : le candidat quartier+DPE reunit
# bien les DEUX communes (pas seulement le candidat quartier-sans-DPE).
# ===========================================================================
def test_adv_intercommunal_with_dpe_band_unites_two_communes():
    """Bien avec DPE 'C' (bande C-D). N1 (Metz) + N2 (Montigny) du meme quartier
    Sainte-Therese et de la meme bande DPE, N1+N2 >= MIN_REFINED mais N1 seul <
    MIN_REFINED. Le PREMIER candidat (quartier + bande DPE) doit deja reunir les
    deux communes -> scope 'quartier', dpe_band 'C-D', count == N1+N2.

    Falsifiable : rouge si le candidat quartier+DPE filtre sur la seule commune
    (count == N1, ou retombe sur un scope plus large)."""
    n1, n2 = 6, 6
    assert n1 < MIN_REFINED_COMPARABLES and n1 + n2 >= MIN_REFINED_COMPARABLES
    # Tous en bande C-D (C et D) pour que le candidat quartier+DPE soit peuple.
    _insert(COMMUNE_METZ, [2700.0, 2800.0, 2900.0, 3000.0, 3100.0, 3200.0],
            district=CANON_ST, dpe="C")
    _insert(COMMUNE_MONTIGNY, [2750.0, 2850.0, 2950.0, 3050.0, 3150.0, 3250.0],
            district=CANON_ST, dpe="D")

    ms = compute_market_stats(
        city="Metz", district="Sainte-Thérèse", property_type="appartement",
        surface_m2=SURFACE, dpe="C",
    )
    assert ms is not None, "pool reuni >= MIN_REFINED ne doit pas etre None"
    assert ms["scope"] == "quartier", (
        f"scope 'quartier' attendu (communes reunies au niveau quartier+DPE), "
        f"recu {ms['scope']!r}"
    )
    assert ms["dpe_band"] == "C-D", (
        f"le candidat retenu doit etre le niveau quartier+DPE (bande C-D), recu "
        f"dpe_band={ms['dpe_band']!r}"
    )
    assert ms["count"] == n1 + n2, (
        f"count attendu N1+N2={n1 + n2} (deux communes reunies AVEC bande DPE), "
        f"recu {ms['count']} (pool reste limite a Metz si == {n1})"
    )


def test_adv_intercommunal_dpe_candidate_receives_cities(monkeypatch):
    """Sonde de l'appel : le candidat quartier+bande-DPE (1er candidat de la
    cascade) doit lui aussi recevoir `cities`, pas seulement le candidat
    quartier-sans-DPE. Verifie que les DEUX appels de niveau quartier portent
    cities == {Metz, Montigny} ET un dpe_letters non None pour le 1er."""
    _insert(COMMUNE_METZ, [2700.0, 2800.0, 2900.0], district=CANON_ST, dpe="C")
    _insert(COMMUNE_MONTIGNY, [2750.0, 2850.0, 2950.0], district=CANON_ST, dpe="D")
    calls = _spy_fetch(monkeypatch)

    compute_market_stats(
        city="Metz", district="Sainte-Thérèse", property_type="appartement",
        surface_m2=SURFACE, dpe="C",
    )

    quartier_calls = [c for c in calls if c["district"] == CANON_ST]
    assert quartier_calls, f"appels niveau quartier attendus. calls={calls}"
    dpe_quartier_calls = [c for c in quartier_calls if c["dpe_letters"] is not None]
    assert dpe_quartier_calls, (
        "un candidat quartier AVEC bande DPE doit exister dans la cascade quand "
        f"un DPE est fourni. quartier_calls={quartier_calls}"
    )
    for c in quartier_calls:
        assert c["cities"] is not None and set(c["cities"]) == {
            COMMUNE_METZ, COMMUNE_MONTIGNY
        }, (
            f"TOUT appel quartier (avec OU sans bande DPE) doit recevoir cities="
            f"{{Metz, Montigny}}, recu {c!r}"
        )


# ===========================================================================
# Piste 2 — bien cote Montigny : symetrie Metz <-> Montigny.
# ===========================================================================
def test_adv_montigny_side_property_unites_metz_too():
    """Un bien lu city='Montigny-Les-Metz', district Sainte-Therese, doit
    reunir AUSSI les comparables de Metz (symetrie). Le filtre quartier passe par
    `cities.in_()` donc la commune du bien ne restreint plus le pool.

    Falsifiable : rouge si le pool reste limite a Montigny (count == n_montigny)
    ou si seul un bien cote Metz beneficie de l'elargissement."""
    n_metz, n_montigny = 7, 5
    assert n_montigny < MIN_REFINED_COMPARABLES
    assert n_metz + n_montigny >= MIN_REFINED_COMPARABLES
    _insert(COMMUNE_METZ,
            [2600.0, 2700.0, 2800.0, 2900.0, 3000.0, 3100.0, 3200.0],
            district=CANON_ST)
    _insert(COMMUNE_MONTIGNY, [2650.0, 2750.0, 2850.0, 2950.0, 3050.0],
            district=CANON_ST)

    ms = compute_market_stats(
        city="Montigny-Les-Metz", district="Sainte-Thérèse",
        property_type="appartement", surface_m2=SURFACE,
    )
    assert ms is not None
    assert ms["scope"] == "quartier", (
        f"scope 'quartier' attendu cote Montigny, recu {ms['scope']!r}"
    )
    assert ms["count"] == n_metz + n_montigny, (
        f"count attendu N_metz+N_montigny={n_metz + n_montigny} (symetrie), recu "
        f"{ms['count']} (pool reste limite a Montigny si == {n_montigny})"
    )


def test_adv_montigny_side_quartier_call_receives_both_cities(monkeypatch):
    """Sonde : pour un bien city='Montigny-Les-Metz' resolu vers Sainte-Therese,
    l'appel niveau quartier passe cities=={Metz, Montigny}. Verrouille la
    symetrie au niveau de l'appel (pas seulement du resultat agrege)."""
    _insert(COMMUNE_MONTIGNY, [2650.0, 2750.0, 2850.0], district=CANON_ST)
    _insert(COMMUNE_METZ, [2600.0, 2700.0, 2800.0], district=CANON_ST)
    calls = _spy_fetch(monkeypatch)

    compute_market_stats(
        city="Montigny-Les-Metz", district="Sainte-Thérèse",
        property_type="appartement", surface_m2=SURFACE,
    )
    quartier_calls = [c for c in calls if c["district"] == CANON_ST]
    assert quartier_calls
    for c in quartier_calls:
        assert c["cities"] is not None and set(c["cities"]) == {
            COMMUNE_METZ, COMMUNE_MONTIGNY
        }, f"cote Montigny, l'appel quartier doit reunir les 2 communes, recu {c!r}"


# ===========================================================================
# Piste 3 — preseance ville / metropole : aucun niveau autre que quartier ne
# recoit `cities` issu de la table inter-communale ; la regle "ville preferee
# des MIN_COMPARABLES" reste intacte.
# ===========================================================================
def test_adv_sector_ville_levels_never_receive_intercommunal_cities(monkeypatch):
    """Pour un bien inter-communal, AUCUN appel de niveau secteur/ville ne doit
    recevoir cities=={Metz, Montigny} (l'elargissement est borne au quartier).
    Le niveau ville filtre sur la commune du bien ; le niveau metropole sur
    _METRO_CITIES, jamais sur la paire inter-communale curatee.

    Falsifiable : rouge si la table inter-communale polluait un autre niveau."""
    # Quartier creux (sous MIN_REFINED meme reuni) pour forcer la cascade a
    # descendre jusqu'a la ville/metropole et exercer ces niveaux.
    _insert(COMMUNE_METZ, [3000.0, 3100.0], district=CANON_ST)
    _insert(COMMUNE_MONTIGNY, [2900.0], district=CANON_ST)
    # Peupler la ville (sans district) pour qu'un niveau ville soit atteignable.
    _insert(COMMUNE_METZ, [2800.0, 2900.0, 3000.0, 3100.0, 3200.0], district=None)
    calls = _spy_fetch(monkeypatch)

    compute_market_stats(
        city="Metz", district="Sainte-Thérèse", property_type="appartement",
        surface_m2=SURFACE,
    )
    inter = {COMMUNE_METZ, COMMUNE_MONTIGNY}
    non_quartier = [c for c in calls if c["district"] != CANON_ST]
    for c in non_quartier:
        cities = set(c["cities"]) if c["cities"] is not None else None
        assert cities != inter, (
            f"un niveau non-quartier ({c['district']!r}/scope) ne doit JAMAIS "
            f"recevoir la paire inter-communale curatee {inter}, recu {c!r}"
        )


def test_adv_ville_preference_rule_unchanged_for_intercommunal():
    """La regle "ville preferee des MIN_COMPARABLES (5)" ne doit pas etre
    court-circuitee par l'inter-communal. Quartier reuni trop creux (< MIN_REFINED)
    mais ville >= MIN_COMPARABLES : la cascade doit retenir 'ville', pas elargir
    a la metropole ni rester bloquee au quartier creux.

    Falsifiable : rouge si l'elargissement quartier modifie la preseance ville."""
    # Quartier reuni = 3 (< MIN_REFINED=10) -> insuffisant au niveau quartier.
    _insert(COMMUNE_METZ, [3000.0, 3100.0], district=CANON_ST)
    _insert(COMMUNE_MONTIGNY, [2900.0], district=CANON_ST)
    # Ville Metz (hors quartier) = 5 (== MIN_COMPARABLES) -> doit etre preferee.
    _insert(COMMUNE_METZ, [2800.0, 2900.0, 3000.0, 3100.0, 3200.0], district="Autre")

    ms = compute_market_stats(
        city="Metz", district="Sainte-Thérèse", property_type="appartement",
        surface_m2=SURFACE,
    )
    assert ms is not None, "ville >= MIN_COMPARABLES ne doit pas donner None"
    assert ms["scope"] == "ville", (
        f"scope 'ville' attendu (regle MIN_COMPARABLES preservee), recu "
        f"{ms['scope']!r} count={ms.get('count')}"
    )
    # Au niveau ville, le pool est la commune du bien (Metz) : 2 (quartier) + 5
    # (autre quartier) = 7 comparables Metz, JAMAIS dilue par Montigny.
    assert ms["count"] == 7, (
        f"au niveau ville, seuls les comparables Metz comptent (7), recu "
        f"{ms['count']} (Montigny ne doit pas polluer le niveau ville)"
    )


# ===========================================================================
# Piste 4 — canonicalisation des communes de la table vs forme stockee.
# ===========================================================================
def test_adv_table_communes_match_stored_canonical_form():
    """La valeur de la table pour Sainte-Therese doit etre EXACTEMENT la forme
    stockee (canonicalisee a l'ingestion) des communes, sinon le filtre
    Comparable.city.in_(cities) raterait le pool Montigny. On insere sous la
    forme reellement stockee (canonical_city) et on verifie qu'un filtre par les
    valeurs de la table ramene bien ces lignes."""
    from app.geo_gazetteer import intercommunal_districts

    table = intercommunal_districts()
    communes = table[CANON_ST]
    # Les valeurs de la table doivent etre identiques a canonical_city(forme brute).
    assert communes == (canonical_city("Metz"), canonical_city("Montigny-lès-Metz")), (
        f"les valeurs de la table doivent etre les formes canoniques stockees, "
        f"recu {communes!r}"
    )
    # Et un comparable stocke sous canonical_city("Montigny-lès-Metz") doit etre
    # filtrable par la valeur de la table.
    _insert("Montigny-lès-Metz", [3000.0] * 6, district=CANON_ST)
    _insert("Metz", [3000.0] * 6, district=CANON_ST)
    db = SessionLocal()
    try:
        n = (
            db.query(Comparable)
            .filter(Comparable.district == CANON_ST)
            .filter(Comparable.city.in_(list(communes)))
            .count()
        )
    finally:
        db.close()
    assert n == 12, (
        f"le filtre city.in_(table[Sainte-Therese]) doit ramener les 12 lignes "
        f"(forme canonique alignee), recu {n} (canonicalisation desynchronisee ?)"
    )


# ===========================================================================
# Piste 5 — _INTERCOMMUNAL fige a l'import : coherence du chemin reel.
# ===========================================================================
def test_adv_market_stats_reads_module_level_intercommunal(monkeypatch):
    """compute_market_stats lit `market_stats._INTERCOMMUNAL` (fige a l'import).
    On le patche pour DESACTIVER l'inter-communalite de Sainte-Therese : le pool
    quartier ne doit plus reunir les deux communes (count == Metz seul). Prouve
    que c'est bien _INTERCOMMUNAL (pas un autre chemin) qui pilote l'elargissement,
    et qu'un patch a ce niveau est effectif (pas un faux-vert)."""
    monkeypatch.setattr(market_stats, "_INTERCOMMUNAL", {})
    n_metz, n_montigny = 6, 6
    _insert(COMMUNE_METZ, [2700.0, 2800.0, 2900.0, 3000.0, 3100.0, 3200.0],
            district=CANON_ST)
    _insert(COMMUNE_MONTIGNY, [2750.0, 2850.0, 2950.0, 3050.0, 3150.0, 3250.0],
            district=CANON_ST)

    ms = compute_market_stats(
        city="Metz", district="Sainte-Thérèse", property_type="appartement",
        surface_m2=SURFACE,
    )
    # Quartier Metz seul = 6 < MIN_REFINED -> la cascade descend ; ville Metz = 6
    # (les memes lignes, district=Sainte-Therese, mais filtre ville sans district
    # ramene les 6 lignes Metz). Le pool ne doit JAMAIS atteindre 12.
    assert ms is None or ms["count"] != n_metz + n_montigny, (
        f"table inter-communale vide -> aucun pool de 12 attendu, recu "
        f"count={None if ms is None else ms['count']} (un autre chemin elargit ?)"
    )


def test_adv_intercommunal_table_is_frozen_at_import():
    """_INTERCOMMUNAL est derive a l'import et coherent avec la derivation vive.
    Verifie qu'il contient bien la cle Sainte-Therese avec les 2 communes (pas un
    dict vide fige avant declaration), et qu'il EGALE la derivation a la demande
    (pas de divergence import vs appel)."""
    from app.geo_gazetteer import intercommunal_districts

    assert CANON_ST in market_stats._INTERCOMMUNAL, (
        "_INTERCOMMUNAL fige a l'import doit contenir Sainte-Therese"
    )
    assert market_stats._INTERCOMMUNAL[CANON_ST] == (COMMUNE_METZ, COMMUNE_MONTIGNY)
    assert market_stats._INTERCOMMUNAL == intercommunal_districts(), (
        "la table figee a l'import doit egaler la derivation a la demande"
    )


# ===========================================================================
# Piste 6 — geocode enrichi : robustesse postcode / citycode / features vides.
# ===========================================================================
class _FakeResp:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


@pytest.fixture()
def patch_ban(monkeypatch):
    import app.geocode as geocode

    geocode._CACHE.clear()
    state = {"payload": {"features": []}}

    def _fake_get(url, params=None, headers=None, timeout=None):
        return _FakeResp(state["payload"])

    monkeypatch.setattr(geocode.requests, "get", _fake_get)

    def _set(payload):
        state["payload"] = payload
        geocode._CACHE.clear()

    return _set


def _feature(props, lon=6.18, lat=49.11):
    return {"features": [{"properties": props,
                          "geometry": {"coordinates": [lon, lat]}}]}


def test_adv_geocode_missing_postcode_does_not_crash_guard(patch_ban):
    """Garde-fou dept 57 : le code lit `postcode`. Une feature SANS postcode ne
    doit pas crasher l'enrichissement (postcode -> None). Selon l'implementation
    du garde-fou, soit la feature est rejetee (None), soit acceptee avec
    postcode is None ; dans les DEUX cas : pas d'exception, et si acceptee,
    postcode is None (pas un KeyError, pas une chaine vide trompeuse)."""
    from app.geocode import geocode_address

    patch_ban(_feature({"score": 0.9, "city": "Metz", "citycode": "57463",
                        "label": "Rue Sans CP Metz"}))
    res = geocode_address("Rue Sans CP", city_hint="Metz")
    if res is not None:
        assert res.get("postcode") is None, (
            f"postcode absent -> None attendu (pas KeyError ni ''), recu "
            f"{res.get('postcode')!r}"
        )
        assert res.get("city") == "Metz"


def test_adv_geocode_city_without_citycode(patch_ban):
    """Feature avec `city` mais SANS `citycode` (cas BAN incomplet) : city remonte,
    citycode is None, pas d'exception."""
    from app.geocode import geocode_address

    patch_ban(_feature({"score": 0.9, "postcode": "57000", "city": "Metz",
                        "label": "Rue X 57000 Metz"}))
    res = geocode_address("Rue X", city_hint="Metz")
    assert res is not None, "feature dept 57, score haut -> geocodage attendu"
    assert res.get("city") == "Metz"
    assert res.get("citycode") is None, (
        f"citycode absent -> None attendu, recu {res.get('citycode')!r}"
    )


def test_adv_geocode_empty_features_returns_none(patch_ban):
    """Reponse BAN `features: []` -> None (repli silencieux, pas d'IndexError ni
    d'enrichissement sur une feature inexistante)."""
    from app.geocode import geocode_address

    patch_ban({"features": []})
    res = geocode_address("Adresse introuvable", city_hint="Metz")
    assert res is None, f"features vides -> None attendu, recu {res!r}"


def test_adv_geocode_empty_string_postcode_guard_not_dept57(patch_ban):
    """Un postcode present mais hors dept 57 (ex. '88...') reste rejete malgre
    city/citycode presents : l'enrichissement ne doit pas contourner le garde-fou
    via la presence de city."""
    from app.geocode import geocode_address

    patch_ban(_feature({"score": 0.95, "postcode": "88000", "city": "Epinal",
                        "citycode": "88160", "label": "Epinal"}))
    res = geocode_address("Place des Vosges", city_hint="Epinal")
    assert res is None, (
        f"postcode dept 88 doit rester rejete (garde-fou), recu {res!r}"
    )


# ===========================================================================
# Piste 7 — non-regression fine : quartier mono-commune AVEC adresse geocodee
# ne declenche aucun elargissement de pool.
# ===========================================================================
def test_adv_mono_commune_with_address_no_pool_widening(monkeypatch):
    """Un bien Sablon (mono-commune) reste sur cities=None au niveau quartier,
    qu'une adresse soit fournie ou non. C1 n'introduit l'elargissement QUE via la
    table curatee, jamais via la presence d'une adresse geocodee (D3 lit la
    commune reelle mais ne l'utilise pas pour elargir un quartier mono-commune).

    On exerce compute_market_stats directement (le coeur du pool) : la commune
    reelle BAN n'a aucun chemin pour injecter `cities` ici."""
    _insert(COMMUNE_METZ, [3000.0] * 10, district="Sablon")
    calls = _spy_fetch(monkeypatch)

    compute_market_stats(
        city="Metz", district="Sablon", property_type="appartement",
        surface_m2=SURFACE,
    )
    quartier_calls = [c for c in calls if c["district"] == "Sablon"]
    assert quartier_calls, "appel niveau quartier (Sablon) attendu"
    for c in quartier_calls:
        assert c["cities"] is None, (
            f"un quartier mono-commune ne recoit jamais cities, recu {c['cities']!r}"
        )


def test_adv_full_analysis_mono_commune_pool_identical_with_address(monkeypatch):
    """Bout-en-bout : pour un bien mono-commune (Sablon), le pilier prix est
    IDENTIQUE avec et sans adresse geocodee (commune reelle BAN lue, mais sans
    effet sur le pool). Falsifiable : rouge si la commune reelle BAN elargissait
    le pool d'un quartier mono-commune."""
    import app.analysis as analysis_mod
    from app.analysis import run_full_analysis

    monkeypatch.setattr(
        analysis_mod, "analyze_semantic",
        lambda raw_text: {
            "transparency_score": 70, "verdict": "Bonne", "risk_level": "Faible",
            "summary": "RAS.", "risk_summary": "RAS.", "questions": [],
            "negotiation_levers": [], "local_claims": [],
            "listing": {
                "city": "Metz", "district": "Sablon",
                "property_type": "appartement", "surface_m2": SURFACE,
                "price_total": 3000.0 * SURFACE, "dpe": None,
                "construction_year": None, "floor": None, "has_elevator": None,
                "has_terrace": None, "has_balcony": None, "has_cellar": None,
                "parking": None, "bedrooms": None, "condo_fees": None,
            },
        },
    )
    # geocode renvoie une adresse Metz valide AVEC commune reelle BAN.
    monkeypatch.setattr(
        analysis_mod, "geocode_address",
        lambda addr, city="Metz": {
            "lat": 49.10, "lon": 6.17, "score": 0.9,
            "label": "10 Rue du Sablon 57000 Metz",
            "city": "Metz", "citycode": "57463", "postcode": "57000",
        },
    )
    _insert(COMMUNE_METZ, [3000.0] * 10, district="Sablon")

    out_no = run_full_analysis("Appartement Sablon Metz 70 m2.")
    out_addr = run_full_analysis(
        "Appartement Sablon Metz 70 m2.", address="10 Rue du Sablon 57000 Metz"
    )
    p_no = out_no["pillars"][0]
    p_addr = out_addr["pillars"][0]
    assert p_no == p_addr, (
        "le pilier prix d'un bien mono-commune doit etre identique avec/sans "
        f"adresse geocodee.\n  sans={p_no}\n  avec={p_addr}"
    )

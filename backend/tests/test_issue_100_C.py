"""Tests-first (phase A) — issue #100, chantier C, sous-palier C1
(inter-communal & commune reelle). Spec : docs/specs/issue-100-C-SPEC.md §4.

Fichier de tests DEDIE (spec §3.6 ; lecon 2026-06-12 fix-issue-80 : ne pas heurter
un oracle de harnais executant un fichier existant en sous-processus, ne pas
editer _A.py / _B.py). Suite GRATUITE, deterministe : AUCUN appel reseau ni LLM
reel. `geocode_address` et `requests.get` sont patches ; `analyze_semantic` est
monkeypatche quand `run_full_analysis` / l'endpoint sont sollicites (cf. tests
existants). Isolation par les fixtures autouse du conftest (init_db session-scope,
reset `comparables`/`snapshots`, etc.).

ETAT ATTENDU EN PHASE A : ces tests doivent ECHOUER pour la BONNE raison (champ
`communes` absent de `GazetteerEntry`, `intercommunal_districts()` absente,
enrichissement city/citycode de `geocode_address` absent, activation `cities` au
niveau quartier non branchee), pas sur un ImportError de collecte. Les imports des
points d'accroche encore absents (`intercommunal_districts`) sont donc LOCAUX aux
tests qui en dependent, pour ne pas casser la collecte du module entier.

=============================================================================
PROTOCOLE GOLDEN ANTI-TAUTOLOGIE (spec §3.5 / risque §6.2 ; lecons faux-vert
2026-06-09 9.10, 2026-06-13, golden-d'ordre 2026-06-16) — A LIRE AVANT MODIF
=============================================================================
GOLDEN_PILLAR_SABLON ci-dessous a ete capture EN LITTERAL sur le comportement
AVANT C1, par execution directe de `compute_price_market_pillar` (code actuel,
DB temporaire ; cf. rapport de phase A). INTERDICTION de le regenerer depuis le
code POST-C1 : il serait alors toujours vert et ne prouverait rien. AC NR1
compare la sortie POST-implementation A CE LITTERAL : si C1 modifie la sortie
d'un bien mono-commune sans adresse, le test doit virer au rouge.
"""

import uuid

import pytest

import app.market_stats as market_stats
from app.market_stats import (
    MIN_COMPARABLES,
    MIN_REFINED_COMPARABLES,
    _METRO_CITIES,
    compute_market_stats,
    compute_price_market_pillar,
)
from db.models import Comparable
from db.session import SessionLocal
from scrapers.base import canonical_city, canonical_district


# Cle pivot du quartier inter-communal (chantier B : Botanique -> Sainte-Therese).
CANON_ST = "Sainte-Therese"
COMMUNE_METZ = "Metz"
COMMUNE_MONTIGNY = "Montigny-Les-Metz"   # forme canonique de "Montigny-lès-Metz"

SURFACE = 70.0
COMP_SURFACE = 70.0  # dans la fenetre +/-20 %
LISTING_PRICE_M2 = 3000.0

# Prix/m2 etales autour de 3000 (q1 < 3000 < q3 via numpy).
PRICES_5 = [2700.0, 2900.0, 3000.0, 3100.0, 3300.0]
PRICES_6 = [2600.0, 2800.0, 3000.0, 3000.0, 3200.0, 3400.0]
PRICES_10 = [
    2600.0, 2700.0, 2800.0, 2900.0, 3000.0,
    3000.0, 3100.0, 3200.0, 3300.0, 3400.0,
]


# ===========================================================================
# GOLDEN LITTERAL — capture sur l'ETAT ACTUEL (avant C1). Ne JAMAIS regenerer
# depuis le code C1 (spec §3.5, risque §6.2). Pool Sablon mono-commune, >=10
# comparables -> scope quartier (10 = PRICES_10).
# ===========================================================================
GOLDEN_PILLAR_SABLON = {
    "verdict": "Plutôt aligné",
    "explanation": (
        "Dans le quartier Sablon, le prix au m² se situe dans la fourchette "
        "courante observée (2825–3175 €/m²) pour des biens comparables."
    ),
    "confidence": "Élevée",
    "scope": "quartier",
    "scope_name": "Sablon",
    "dpe_band": None,
    "n_comparables": 10,
    # Prix au m² de l'annonce (210000 / 70), repère factuel exposé au front.
    "listing_price_m2": 3000,
    "refinable": False,
}


# ===========================================================================
# Helpers
# ===========================================================================
def _insert(city, prices, district=None, property_type="appartement", dpe=None):
    """Insere un comparable par prix/m2, ville canonicalisee, surface dans la
    fenetre +/-20 % du bien teste."""
    db = SessionLocal()
    try:
        canon = canonical_city(city)
        for pm2 in prices:
            db.add(Comparable(
                id=f"c1-{uuid.uuid4().hex}",
                source="test",
                city=canon,
                district=district,
                property_type=property_type,
                surface_m2=COMP_SURFACE,
                price_total=pm2 * COMP_SURFACE,
                price_m2=pm2,
                dpe=dpe,
            ))
        db.commit()
    finally:
        db.close()


def _ban_feature(score=0.9, postcode="57000", city="Metz", citycode="57463",
                 label="1 Rue Test 57000 Metz", lon=6.18, lat=49.11,
                 with_city_keys=True):
    """Construit une reponse BAN simulee (1 feature) au format api-adresse."""
    props = {"score": score, "postcode": postcode, "label": label}
    if with_city_keys:
        props["city"] = city
        props["citycode"] = citycode
    return {"features": [{"properties": props,
                          "geometry": {"coordinates": [lon, lat]}}]}


class _FakeResp:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


@pytest.fixture()
def patch_ban(monkeypatch):
    """Patche `requests.get` dans app.geocode pour renvoyer une feature BAN
    controlee, et vide le cache memoire (lecon cache geocode 9.7 / spec §6.5).
    Renvoie un setter pour configurer la payload par test."""
    import app.geocode as geocode

    geocode._CACHE.clear()
    state = {"payload": _ban_feature()}

    def _fake_get(url, params=None, headers=None, timeout=None):
        return _FakeResp(state["payload"])

    monkeypatch.setattr(geocode.requests, "get", _fake_get)

    def _set(payload):
        state["payload"] = payload
        geocode._CACHE.clear()

    return _set


# ===========================================================================
# AC1 — geocode_address expose city / citycode / postcode depuis la BAN (§3.1)
# ===========================================================================
def test_ac1_geocode_expose_city_citycode_postcode(patch_ban):
    """AC1 : feature BAN {score, postcode, city, citycode, label} -> le dict
    renvoye porte city/citycode/postcode EN PLUS de lat/lon/score/label.
    Rouge tant que l'enrichissement §3.1 n'est pas fait (KeyError sur city)."""
    from app.geocode import geocode_address

    patch_ban(_ban_feature(score=0.9, postcode="57000", city="Metz",
                           citycode="57463"))
    res = geocode_address("1 Rue Test", city_hint="Metz")

    assert res is not None, "AC1 : geocodage attendu non-None sur feature valide"
    # Champs historiques preserves.
    for k in ("lat", "lon", "score", "label"):
        assert k in res, f"AC1 : champ historique {k!r} manquant"
    # Champs C1.
    assert res["city"] == "Metz", f"AC1 : city attendu 'Metz', recu {res.get('city')!r}"
    assert res["citycode"] == "57463", (
        f"AC1 : citycode attendu '57463', recu {res.get('citycode')!r}"
    )
    assert res["postcode"] == "57000", (
        f"AC1 : postcode attendu '57000', recu {res.get('postcode')!r}"
    )


def test_ac1_geocode_reads_montigny_commune(patch_ban):
    """AC1 (cote Montigny) : la commune reelle BAN peut differer de Metz pour un
    bien a cheval. Verifie que city='Montigny-lès-Metz' / citycode INSEE remontent
    tels quels (toujours dept 57, score >= seuil)."""
    from app.geocode import geocode_address

    patch_ban(_ban_feature(score=0.85, postcode="57950", city="Montigny-lès-Metz",
                           citycode="57480", label="Rue X 57950 Montigny-lès-Metz"))
    res = geocode_address("Rue X", city_hint="Montigny-lès-Metz")

    assert res is not None
    assert res["city"] == "Montigny-lès-Metz", (
        f"AC1 : commune reelle attendue Montigny-lès-Metz, recu {res.get('city')!r}"
    )
    assert res["citycode"] == "57480"


# ===========================================================================
# AC1b — champs manquants -> None, garde-fous (dept 57 / score) inchanges (§3.1)
# ===========================================================================
def test_ac1b_missing_city_citycode_yield_none(patch_ban):
    """AC1b(a) : reponse BAN SANS city ni citycode -> dict valide avec
    city is None / citycode is None (pas de KeyError, pas d'exception)."""
    from app.geocode import geocode_address

    patch_ban(_ban_feature(with_city_keys=False))
    res = geocode_address("1 Rue Sans Ville", city_hint="Metz")

    assert res is not None, "AC1b : un geocodage valide ne doit pas echouer faute de city"
    assert res.get("city") is None, (
        f"AC1b : city is None attendu sur champ absent, recu {res.get('city')!r}"
    )
    assert res.get("citycode") is None, (
        f"AC1b : citycode is None attendu sur champ absent, recu {res.get('citycode')!r}"
    )


def test_ac1b_guard_department_unchanged(patch_ban):
    """AC1b(b) : un postcode hors dept 57 (ex. '54...') -> None (garde-fou dept
    inchange), l'enrichissement city/citycode ne doit pas le contourner."""
    from app.geocode import geocode_address

    patch_ban(_ban_feature(score=0.95, postcode="54000", city="Nancy",
                           citycode="54395"))
    res = geocode_address("Place Stanislas", city_hint="Nancy")
    assert res is None, (
        f"AC1b : un bien hors dept 57 doit rester None (garde-fou), recu {res!r}"
    )


def test_ac1b_guard_low_score_unchanged(patch_ban):
    """AC1b(b) : un score < 0.4 -> None (seuil _MIN_SCORE inchange), meme avec
    city/citycode presents."""
    from app.geocode import geocode_address

    patch_ban(_ban_feature(score=0.2, postcode="57000", city="Metz",
                           citycode="57463"))
    res = geocode_address("adresse floue", city_hint="Metz")
    assert res is None, (
        f"AC1b : score < 0.4 doit rester None (seuil inchange), recu {res!r}"
    )


# ===========================================================================
# AC2 — Schema (champ communes) + derivation intercommunal_districts() (§3.2/3.3)
# ===========================================================================
def test_ac2_gazetteer_entry_has_communes_field():
    """AC2.1 : GazetteerEntry possede un champ `communes: Tuple[str, ...]` de
    defaut (). Rouge tant que le champ n'est pas ajoute."""
    import dataclasses
    from app.geo_gazetteer import GazetteerEntry

    field_names = {f.name for f in dataclasses.fields(GazetteerEntry)}
    assert "communes" in field_names, (
        "AC2 : GazetteerEntry doit declarer un champ `communes` (spec §3.2)"
    )
    # Defaut () : une entree minimale construite sans `communes` doit l'avoir vide.
    field = next(f for f in dataclasses.fields(GazetteerEntry) if f.name == "communes")
    default = field.default
    if default is dataclasses.MISSING and field.default_factory is not dataclasses.MISSING:
        default = field.default_factory()
    assert default == (), (
        f"AC2 : defaut de `communes` attendu () (mono-commune), recu {default!r}"
    )


def test_ac2_intercommunal_table_contains_sainte_therese():
    """AC2.2 : intercommunal_districts() expose
    'Sainte-Therese' -> ('Metz', 'Montigny-Les-Metz') (canonicalise, ordre
    preserve, dedoublonne). Rouge tant que la fonction / la declaration n'existe
    pas (AttributeError ou KeyError)."""
    from app.geo_gazetteer import intercommunal_districts

    table = intercommunal_districts()
    assert CANON_ST in table, (
        f"AC2 : '{CANON_ST}' doit etre une cle de intercommunal_districts(), "
        f"cles={sorted(table)}"
    )
    communes = tuple(table[CANON_ST])
    assert communes == (COMMUNE_METZ, COMMUNE_MONTIGNY), (
        f"AC2 : communes attendues {(COMMUNE_METZ, COMMUNE_MONTIGNY)} (canonicalisees,"
        f" ordre preserve), recu {communes!r}"
    )
    # Dedoublonnage : pas de doublon dans la valeur.
    assert len(communes) == len(set(communes)), (
        f"AC2 : communes dedoublonnees attendues, recu {communes!r}"
    )


def test_ac2_all_table_communes_in_metro_cities():
    """AC2.3 : toute commune presente dans la table appartient a
    market_stats._METRO_CITIES (jamais de commune hors perimetre Metz Metropole)."""
    from app.geo_gazetteer import intercommunal_districts

    table = intercommunal_districts()
    for key, communes in table.items():
        for c in communes:
            assert c in _METRO_CITIES, (
                f"AC2 : commune {c!r} (quartier {key!r}) hors _METRO_CITIES "
                f"{_METRO_CITIES}"
            )


# ===========================================================================
# AC3 — quartiers mono-commune ABSENTS de la table (§3.3, pas d'elargissement)
# ===========================================================================
def test_ac3_mono_commune_districts_absent_from_table():
    """AC3 : la table ne contient QUE des quartiers >= 2 communes. Aucun quartier
    mono-commune (communes vide ou singleton) n'y figure ; pas de (commune,)
    redondant. Sablon / Borny / Centre-Ville en particulier sont absents."""
    from app.geo_gazetteer import intercommunal_districts, GAZETTEER

    table = intercommunal_districts()

    # Aucune valeur singleton ou vide dans la table.
    for key, communes in table.items():
        assert len(communes) >= 2, (
            f"AC3 : la table ne doit contenir que des quartiers >= 2 communes ; "
            f"{key!r} a {communes!r}"
        )

    for mono in ("Sablon", "Borny", "Centre-Ville"):
        assert mono not in table, (
            f"AC3 : quartier mono-commune {mono!r} ne doit PAS etre dans la table"
        )

    # Toute entree dont `communes` est vide/singleton est absente de la table.
    for key, entry in GAZETTEER.items():
        communes = getattr(entry, "communes", ())
        canon = []
        for c in communes:
            cc = canonical_city(c)
            if cc and cc not in canon:
                canon.append(cc)
        if len(canon) < 2:
            assert key not in table, (
                f"AC3 : l'entree mono-commune {key!r} (communes derivees {canon}) "
                f"ne doit pas figurer dans la table"
            )


# ===========================================================================
# AC4 — Pool inter-communal au niveau quartier (cas Botanique, DB de test) (§3.4)
# ===========================================================================
def test_ac4_intercommunal_pool_unites_two_communes():
    """AC4 : N1 comparables Metz/Sainte-Therese + N2 Montigny-Les-Metz/
    Sainte-Therese, avec N1+N2 >= MIN_REFINED mais N1 < MIN_REFINED. Le niveau
    quartier reunit les DEUX communes -> scope 'quartier' et count == N1+N2.
    Rouge tant que l'activation cities n'est pas branchee (count == N1 ou scope
    retombe secteur/ville)."""
    n1 = MIN_REFINED_COMPARABLES - 4   # 6 : < MIN_REFINED seul
    n2 = MIN_REFINED_COMPARABLES - 4   # 6 : N1+N2 = 12 >= MIN_REFINED
    assert n1 < MIN_REFINED_COMPARABLES and n1 + n2 >= MIN_REFINED_COMPARABLES

    _insert(COMMUNE_METZ, PRICES_6[:n1], district=CANON_ST)
    _insert(COMMUNE_MONTIGNY, PRICES_6[:n2], district=CANON_ST)

    ms = compute_market_stats(
        city="Metz", district="Sainte-Thérèse", property_type="appartement",
        surface_m2=SURFACE,
    )
    assert ms is not None, "AC4 : un pool reuni >= MIN_REFINED ne doit pas etre None"
    assert ms["scope"] == "quartier", (
        f"AC4 : scope 'quartier' attendu (communes reunies), recu {ms['scope']!r}"
    )
    assert ms["count"] == n1 + n2, (
        f"AC4 : count attendu N1+N2={n1 + n2} (deux communes reunies), recu "
        f"{ms['count']} (pool reste limite a Metz si == {n1})"
    )


# ===========================================================================
# AC5 — _fetch_comparables recoit `cities` au niveau quartier inter-communal,
# et NON pour un quartier mono-commune (§3.4, sonde de l'appel)
# ===========================================================================
def _spy_fetch(monkeypatch):
    """Espionne market_stats._fetch_comparables en enregistrant chaque appel
    (kwargs district/cities) tout en deleguant a l'original."""
    calls = []
    original = market_stats._fetch_comparables

    def _spy(city, district, property_type, surface_min, surface_max,
             dpe_letters=None, districts=None, cities=None):
        calls.append({"district": district, "districts": districts, "cities": cities})
        return original(city, district, property_type, surface_min, surface_max,
                        dpe_letters=dpe_letters, districts=districts, cities=cities)

    monkeypatch.setattr(market_stats, "_fetch_comparables", _spy)
    return calls


def test_ac5_quartier_level_receives_cities_for_intercommunal(monkeypatch):
    """AC5 : pour un bien resolu vers Sainte-Therese, l'appel du NIVEAU QUARTIER
    passe cities == ('Metz', 'Montigny-Les-Metz') ET district == 'Sainte-Therese'.
    Rouge tant que `cities` n'est pas transmis au niveau quartier."""
    _insert(COMMUNE_METZ, PRICES_6, district=CANON_ST)
    _insert(COMMUNE_MONTIGNY, PRICES_6, district=CANON_ST)
    calls = _spy_fetch(monkeypatch)

    compute_market_stats(
        city="Metz", district="Sainte-Thérèse", property_type="appartement",
        surface_m2=SURFACE,
    )

    quartier_calls = [c for c in calls if c["district"] == CANON_ST]
    assert quartier_calls, (
        f"AC5 : au moins un appel au niveau quartier (district={CANON_ST!r}) "
        f"attendu. Appels={calls}"
    )
    for c in quartier_calls:
        assert c["cities"] is not None, (
            f"AC5 : l'appel quartier inter-communal doit recevoir `cities` non None,"
            f" recu {c!r}"
        )
        assert set(c["cities"]) == {COMMUNE_METZ, COMMUNE_MONTIGNY}, (
            f"AC5 : cities attendu {{Metz, Montigny-Les-Metz}} au niveau quartier, "
            f"recu {c['cities']!r}"
        )


def test_ac5_mono_commune_quartier_receives_no_cities(monkeypatch):
    """AC5 (volet mono-commune) : pour un bien resolu vers Sablon (mono-commune),
    l'appel du niveau quartier passe cities is None (jamais d'elargissement hors
    table). Rouge si `cities` est transmis a tort."""
    _insert(COMMUNE_METZ, PRICES_10, district="Sablon")
    calls = _spy_fetch(monkeypatch)

    compute_market_stats(
        city="Metz", district="Sablon", property_type="appartement",
        surface_m2=SURFACE,
    )

    quartier_calls = [c for c in calls if c["district"] == "Sablon"]
    assert quartier_calls, (
        f"AC5 : au moins un appel niveau quartier (Sablon) attendu. Appels={calls}"
    )
    for c in quartier_calls:
        assert c["cities"] is None, (
            f"AC5 : un quartier mono-commune ne doit JAMAIS recevoir `cities` "
            f"(fake precision), recu {c['cities']!r}"
        )


# ===========================================================================
# Fixtures de monkeypatch LLM / geocode pour les AC NR (chemin run_full_analysis)
# ===========================================================================
def _fake_listing(city="Metz", district=None):
    return {
        "transparency_score": 70,
        "verdict": "Bonne",
        "risk_level": "Faible",
        "summary": "RAS.",
        "risk_summary": "RAS.",
        "questions": [],
        "negotiation_levers": [],
        "local_claims": [],
        "listing": {
            "city": city, "district": district, "property_type": "appartement",
            "surface_m2": SURFACE, "price_total": LISTING_PRICE_M2 * SURFACE,
            "dpe": None, "construction_year": None,
            "floor": None, "has_elevator": None, "has_terrace": None,
            "has_balcony": None, "has_cellar": None, "parking": None,
            "bedrooms": None, "condo_fees": None,
        },
    }


@pytest.fixture()
def fake_semantic_sablon(monkeypatch):
    """analyze_semantic deterministe : bien messin, quartier Sablon extrait du
    listing (mono-commune), sans appel LLM."""
    import app.analysis as analysis_mod
    monkeypatch.setattr(
        analysis_mod, "analyze_semantic",
        lambda raw_text: _fake_listing(city="Metz", district="Sablon"),
    )


# ===========================================================================
# AC NR1 — sans adresse, pool ET sortie identiques a A/B (mono-commune) (§4)
# ===========================================================================
def test_ac_nr1_mono_commune_no_address_matches_pre_c1_golden():
    """AC NR1 : un bien mono-commune (Sablon) SANS adresse produit un pilier prix
    IDENTIQUE au golden capture AVANT C1 (GOLDEN_PILLAR_SABLON). Falsifiable :
    rouge si C1 modifie le pool ou la sortie d'un bien mono-commune sans adresse,
    ou ajoute une cle au pilier."""
    _insert(COMMUNE_METZ, PRICES_10, district="Sablon")

    pillar = compute_price_market_pillar(
        city="Metz", district="Sablon", property_type="appartement",
        surface_m2=SURFACE, listing_price_m2=LISTING_PRICE_M2,
    )

    assert pillar == GOLDEN_PILLAR_SABLON, (
        "AC NR1 : la sortie d'un bien mono-commune sans adresse doit etre "
        f"STRICTEMENT identique au golden pre-C1.\n  golden={GOLDEN_PILLAR_SABLON}\n"
        f"  recu  ={pillar}"
    )


def test_ac_nr1_full_analysis_local_context_unchanged(client, fake_semantic_sablon):
    """AC NR1 (sortie /analyze) : sans adresse, le `local_context` d'un bien
    mono-commune (Sablon, precision quartier) et le set de cles de la reponse
    restent ceux de A/B (aucun champ nouveau)."""
    _insert(COMMUNE_METZ, PRICES_10, district="Sablon")

    resp = client.post(
        "/analyze",
        json={"raw_text": "Appartement T3 Sablon Metz, 70 m2, sans adresse."},
        headers={"Fly-Client-IP": "203.0.113.10"},
    )
    assert resp.status_code == 200, f"AC NR1 : /analyze 200 attendu, recu {resp.status_code}"
    body = resp.json()
    assert set(body.keys()) <= {
        "global_score", "verdict", "confidence", "pillars", "actions",
        "local_context",
    }, f"AC NR1 : aucune cle nouvelle attendue, recu {set(body.keys())}"

    lc = body.get("local_context") or {}
    assert lc.get("precision") == "quartier", (
        f"AC NR1 : precision 'quartier' attendue sans adresse, recu {lc.get('precision')!r}"
    )
    # Pas d'adresse stockee/exposee quand aucune n'est saisie (RGPD, AC C7).
    assert lc.get("address") in (None, ""), (
        f"AC NR1 : aucune adresse ne doit etre exposee sans saisie, recu {lc.get('address')!r}"
    )


# ===========================================================================
# AC NR2 — quartier inter-communal SANS adresse : la table agit (comportement
# voulu, pas une regression) (§4)
# ===========================================================================
def test_ac_nr2_intercommunal_without_address_still_unites():
    """AC NR2 : Sainte-Therese resolu depuis le TEXTE (sans adresse) reunit deja
    les deux communes au niveau quartier (meme assertion qu'AC4). Documente que la
    table (D2) aide MEME sans adresse, contrairement a la commune reelle BAN (D3)."""
    n1, n2 = 6, 6
    _insert(COMMUNE_METZ, PRICES_6[:n1], district=CANON_ST)
    _insert(COMMUNE_MONTIGNY, PRICES_6[:n2], district=CANON_ST)

    # Aucune adresse, aucun geocodage : appel direct par quartier (resolu du texte).
    ms = compute_market_stats(
        city="Metz", district="Sainte-Thérèse", property_type="appartement",
        surface_m2=SURFACE,
    )
    assert ms is not None and ms["scope"] == "quartier", (
        f"AC NR2 : scope 'quartier' attendu sans adresse, recu "
        f"{None if ms is None else ms['scope']!r}"
    )
    assert ms["count"] == n1 + n2, (
        f"AC NR2 : l'elargissement doit s'activer SANS adresse (count={n1 + n2}), "
        f"recu {ms['count']} (confusion D2/D3 si == {n1})"
    )


# ===========================================================================
# AC NR3 — geocodage en echec : repli identique a sans adresse (§4)
# ===========================================================================
@pytest.fixture()
def geocode_none(monkeypatch):
    """Patche geocode_address (vu depuis app.analysis) pour renvoyer None :
    reseau indisponible / score faible / hors dept (repli C1)."""
    import app.analysis as analysis_mod
    monkeypatch.setattr(analysis_mod, "geocode_address", lambda addr, city="Metz": None)


def _run(raw_text, address=""):
    from app.analysis import run_full_analysis
    return run_full_analysis(raw_text, address=address)


def test_ac_nr3_geocode_failure_matches_no_address(
    monkeypatch, geocode_none, fake_semantic_sablon
):
    """AC NR3 : avec une adresse mais geocode_address -> None, la sortie
    (local_context precision + pilier prix) est IDENTIQUE a sans adresse.
    Falsifiable : rouge si l'echec de geocodage change la sortie ou introduit un
    signalement."""
    _insert(COMMUNE_METZ, PRICES_10, district="Sablon")

    out_no_addr = _run("Appartement Sablon Metz 70 m2.")
    out_addr = _run("Appartement Sablon Metz 70 m2.", address="3 Rue Inconnue Metz")

    # Pilier prix strictement identique.
    p_no = out_no_addr["pillars"][0]
    p_addr = out_addr["pillars"][0]
    assert p_no == p_addr, (
        "AC NR3 : le pilier prix doit etre identique avec/sans adresse quand le "
        f"geocodage echoue.\n  sans={p_no}\n  avec={p_addr}"
    )

    lc_no = out_no_addr.get("local_context") or {}
    lc_addr = out_addr.get("local_context") or {}
    assert lc_addr.get("precision") == "quartier" == lc_no.get("precision"), (
        f"AC NR3 : precision 'quartier' attendue dans les deux cas, recu "
        f"avec={lc_addr.get('precision')!r} sans={lc_no.get('precision')!r}"
    )
    # Le set de cles du local_context ne gagne rien du fait de l'echec geocodage
    # (l'adresse saisie peut etre exposee, comme en A/B ; on tolere `address`).
    extra = set(lc_addr.keys()) - set(lc_no.keys()) - {"address"}
    assert not extra, (
        f"AC NR3 : aucun champ nouveau ne doit apparaitre sur echec geocodage, "
        f"diff={extra}"
    )


# ===========================================================================
# AC C5 — contrat /analyze et api.ts inchanges (§4)
# ===========================================================================
# Etat pre-C1 fige : set des cles attendues a chaque niveau (lecon 9.10 : pour le
# corps /analyze, FastAPI filtre via response_model, mais on asserte aussi les
# structures NON filtrees, pilier et local_context).
BODY_KEYS = {
    "global_score", "verdict", "confidence", "pillars", "actions", "local_context",
}
PILLAR_KEYS_EXPOSED = {
    "label", "verdict", "explanation", "points", "max", "scope",
    "scope_name", "dpe_band", "n_comparables", "refinable",
    "listing_price_m2",
}


def test_ac_c5_analyze_keys_unchanged(client, fake_semantic_sablon):
    """AC C5.1 : le set des cles de la reponse /analyze et de chaque pilier est
    identique a l'etat pre-C1 (aucune cle ajoutee/retiree). Le local_context ne
    gagne aucune cle (pas de city/citycode BAN expose en C1)."""
    _insert(COMMUNE_METZ, PRICES_10, district="Sablon")

    resp = client.post(
        "/analyze",
        json={"raw_text": "Appartement Sablon Metz 70 m2 contrat."},
        headers={"Fly-Client-IP": "203.0.113.55"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert set(body.keys()) == BODY_KEYS, (
        f"AC C5 : cles du corps figees. Diff={set(body.keys()) ^ BODY_KEYS}"
    )
    for pillar in body["pillars"]:
        extra = set(pillar.keys()) - PILLAR_KEYS_EXPOSED
        assert not extra, (
            f"AC C5 : pilier {pillar.get('label')!r} expose une cle non autorisee : "
            f"{extra}"
        )
    lc = body.get("local_context") or {}
    # C1 ne doit exposer ni city ni citycode BAN dans local_context (§3.5).
    for forbidden in ("city", "citycode", "communes", "real_city"):
        assert forbidden not in lc, (
            f"AC C5 : local_context ne doit pas gagner la cle {forbidden!r} (C1 "
            f"n'altere pas le contrat)"
        )


def test_ac_c5_api_ts_no_new_field():
    """AC C5.2 (statique) : frontend/lib/api.ts n'a pas besoin de changer — aucun
    champ local_context/pilier ajoute par C1. On verifie qu'api.ts ne reference
    aucun nouveau champ inter-communal (city/citycode/communes), preuve que le
    front reste sur les structures existantes (scope/scope_name/n_comparables)."""
    from pathlib import Path

    api_ts = Path(__file__).resolve().parents[2] / "frontend" / "lib" / "api.ts"
    assert api_ts.exists(), f"AC C5 : api.ts introuvable a {api_ts}"
    content = api_ts.read_text(encoding="utf-8")
    for forbidden in ("citycode", "intercommunal", "communes"):
        assert forbidden not in content, (
            f"AC C5 : api.ts ne doit pas referencer {forbidden!r} (contrat C1 stable)"
        )


# ===========================================================================
# AC C6 — pas de fake precision : seul intercommunal_districts() alimente cities
# (§4)
# ===========================================================================
def test_ac_c6_no_intercommunal_pool_for_unlisted_district(monkeypatch):
    """AC C6 : un quartier NON declare inter-communal (Borny) ne recoit jamais
    `cities` au niveau quartier, meme si des comparables d'une autre commune
    portent le meme district. Verrouille l'absence de regle de distance/frontiere."""
    _insert(COMMUNE_METZ, PRICES_6, district="Borny")
    _insert(COMMUNE_MONTIGNY, PRICES_6, district="Borny")
    calls = _spy_fetch(monkeypatch)

    compute_market_stats(
        city="Metz", district="Borny", property_type="appartement",
        surface_m2=SURFACE,
    )
    quartier_calls = [c for c in calls if c["district"] == "Borny"]
    assert quartier_calls, "AC C6 : appel niveau quartier (Borny) attendu"
    for c in quartier_calls:
        assert c["cities"] is None, (
            f"AC C6 : Borny (hors table) ne doit jamais recevoir `cities`, recu "
            f"{c['cities']!r} (fake precision / regle de frontiere interdite)"
        )


def test_ac_c6_table_only_source_of_intercommunal(monkeypatch):
    """AC C6 (revue) : le SEUL alimentateur de `cities` au niveau quartier est
    intercommunal_districts(). Si l'on vide la table, plus aucun appel quartier ne
    recoit `cities` (preuve qu'aucun autre chemin n'elargit le pool quartier)."""
    from app import geo_gazetteer as gazetteer

    monkeypatch.setattr(gazetteer, "intercommunal_districts", lambda: {})
    # Recharger la table derivee de market_stats si elle est calculee a l'import.
    if hasattr(market_stats, "_INTERCOMMUNAL"):
        monkeypatch.setattr(market_stats, "_INTERCOMMUNAL", {})

    _insert(COMMUNE_METZ, PRICES_6, district=CANON_ST)
    _insert(COMMUNE_MONTIGNY, PRICES_6, district=CANON_ST)
    calls = _spy_fetch(monkeypatch)

    compute_market_stats(
        city="Metz", district="Sainte-Thérèse", property_type="appartement",
        surface_m2=SURFACE,
    )
    quartier_calls = [c for c in calls if c["district"] == CANON_ST]
    for c in quartier_calls:
        assert c["cities"] is None, (
            f"AC C6 : table vide -> aucun elargissement quartier attendu, recu "
            f"cities={c['cities']!r} (un autre chemin alimente cities ?)"
        )


# ===========================================================================
# AC C7 — pas de persistance d'adresse / coordonnees / commune reelle (RGPD) (§4)
# ===========================================================================
def test_ac_c7_no_address_persistence_after_geocode(client, patch_ban, monkeypatch):
    """AC C7 : analyser un bien AVEC adresse ne persiste en base ni adresse, ni
    city/citycode BAN, ni coordonnees. Le cache geocode reste en memoire ; aucune
    nouvelle ligne nominative en base. On verifie qu'aucune table ne contient
    l'adresse saisie ni le citycode BAN."""
    import app.analysis as analysis_mod
    monkeypatch.setattr(
        analysis_mod, "analyze_semantic",
        lambda raw_text: _fake_listing(city="Metz", district="Sablon"),
    )
    _insert(COMMUNE_METZ, PRICES_10, district="Sablon")

    secret_addr = "13 Rue Tres Privee 57000 Metz"
    patch_ban(_ban_feature(score=0.95, postcode="57000", city="Metz",
                           citycode="57463", label=secret_addr))

    resp = client.post(
        "/analyze",
        json={"raw_text": "Appartement Sablon Metz.", "address": secret_addr},
        headers={"Fly-Client-IP": "203.0.113.77"},
    )
    assert resp.status_code == 200

    # Aucune table SQLite ne doit contenir l'adresse saisie ni le citycode BAN.
    from db.session import engine
    from sqlalchemy import inspect, text

    insp = inspect(engine)
    needles = ("Tres Privee", "57463")
    for table_name in insp.get_table_names():
        with engine.begin() as conn:
            rows = conn.execute(text(f'SELECT * FROM "{table_name}"')).fetchall()
        blob = "\n".join("|".join("" if v is None else str(v) for v in r) for r in rows)
        for needle in needles:
            assert needle not in blob, (
                f"AC C7 : la table {table_name!r} ne doit pas persister {needle!r} "
                f"(adresse/citycode BAN : RGPD non regresse)"
            )


# ===========================================================================
# AC C8 — centroid toujours None, pas de nouveau quartier (borne C2) (§4)
# ===========================================================================
def test_ac_c8_centroid_none_and_no_new_entry():
    """AC C8 : toute entree du gazetteer conserve centroid is None (C2 hors
    perimetre) ; aucun nouveau quartier n'est ajoute (C1 ajoute seulement le champ
    `communes` et le declare sur Sainte-Therese). On verrouille le nombre d'entrees
    (17, golden chantier B) et la presence de la cle pivot Sainte-Therese."""
    from app.geo_gazetteer import GAZETTEER

    for key, entry in GAZETTEER.items():
        assert entry.centroid is None, (
            f"AC C8 : centroid de {key!r} doit rester None (C2 hors C1), recu "
            f"{entry.centroid!r}"
        )
    assert len(GAZETTEER) == 17, (
        f"AC C8 : C1 n'ajoute aucun quartier ; 17 entrees attendues (golden B), "
        f"recu {len(GAZETTEER)}"
    )
    assert CANON_ST in GAZETTEER, "AC C8 : la cle pivot Sainte-Therese doit exister"


# ===========================================================================
# AC C9 — robustesse a l'ordre d'import (cycle) (§4)
# ===========================================================================
def test_ac_c9_import_order_robustness():
    """AC C9 : `python -c "import app.geo_gazetteer"` ET
    `python -c "import scrapers.base"` reussissent CHACUN en premier import
    (process separes). intercommunal_districts n'importe canonical_city que
    paresseusement (jamais au top-level de geo_gazetteer). Lecon 2026-06-16."""
    import subprocess
    import sys
    from pathlib import Path

    backend = Path(__file__).resolve().parents[1]
    for module in ("app.geo_gazetteer", "scrapers.base"):
        proc = subprocess.run(
            [sys.executable, "-c", f"import {module}"],
            cwd=str(backend), capture_output=True, text=True,
        )
        assert proc.returncode == 0, (
            f"AC C9 : `import {module}` en premier import doit reussir (cycle ?).\n"
            f"stderr={proc.stderr}"
        )


def test_ac_c9_no_toplevel_canonical_import_in_gazetteer():
    """AC C9 (statique) : geo_gazetteer n'importe pas canonical_city/_district au
    top-level (import paresseux requis). On verifie l'absence d'un import top-level
    `from scrapers.base import ...` dans le module source."""
    from pathlib import Path

    src = Path(__file__).resolve().parents[1] / "app" / "geo_gazetteer.py"
    content = src.read_text(encoding="utf-8")
    for line in content.splitlines():
        stripped = line.strip()
        # Un import top-level n'est pas indente.
        if line and not line[0].isspace():
            assert not stripped.startswith("from scrapers.base import"), (
                f"AC C9 : import top-level interdit dans geo_gazetteer : {stripped!r} "
                f"(canonical_* doit etre importe paresseusement)"
            )


# ===========================================================================
# AC C10 — canonical_district / canonical_city non modifiees (§4)
# ===========================================================================
def test_ac_c10_canonicalization_unchanged():
    """AC C10 : caracterisation inchangee de canonical_city / canonical_district
    sur un echantillon de libelles bruts. C1 APPELLE ces fonctions, ne les
    reecrit pas."""
    assert canonical_city("Montigny-lès-Metz") == "Montigny-Les-Metz", (
        f"AC C10 : canonical_city('Montigny-lès-Metz') doit valoir "
        f"'Montigny-Les-Metz', recu {canonical_city('Montigny-lès-Metz')!r}"
    )
    assert canonical_city("Metz") == "Metz"
    assert canonical_district("Metz - Sainte-Thérèse", "Metz") == "Sainte-Therese", (
        f"AC C10 : canonical_district('Metz - Sainte-Thérèse') doit valoir "
        f"'Sainte-Therese', recu "
        f"{canonical_district('Metz - Sainte-Thérèse', 'Metz')!r}"
    )

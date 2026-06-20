"""Tests-first (phase A) — issue GitHub #87.

Avertissement de perimetre hors-commune sur le pilier prix + relevement du seuil
`MIN_COMPARABLES` (3 -> 5). Spec : docs/specs/87-SPEC.md (AC1..AC5, AC-CONTRAT).

Ces tests doivent ECHOUER tant que le code n'existe pas (rouge legitime) :
- le wording d'avertissement (§3.2) n'existe pas encore dans l'explication ;
- `MIN_COMPARABLES` vaut encore 3 (cible : 5).

Isolation : la fixture autouse `conftest._reset_snapshots_table` vide la table
`comparables` AVANT chaque test (lecon 9.7 : jamais de `count()` absolu, jamais
de dependance a l'ordre). On insere donc un pool propre par test via le modele
`Comparable` dans la base jetable (`SessionLocal`), avec une `surface_m2` dans la
fenetre +/-20 % du bien et un `city` canonique. Aucun appel reseau ni OpenAI : le
chemin endpoint monkeypatche `analyze_semantic`.

Oracle de verdict (AC3) : les pools sont calibres pour que le prix du bien tombe
dans la fourchette Q1-Q3 -> verdict STABLE "Plutot aligne" (q1 < 3000 <= q3 sur
chaque pool, recalcule a la main, cf. docstring de `_insert_comparables`).
"""

import uuid

import pytest

import app.market_stats as market_stats
from app.market_stats import (
    MIN_COMPARABLES,
    MIN_REFINED_COMPARABLES,
    compute_price_market_pillar,
    interpret_price_positioning,
)
from db.models import Comparable
from db.session import SessionLocal
from scrapers.base import canonical_city


# Prix calibres : sur chacun des pools utilises ci-dessous (4, 5, 6, 10 valeurs
# centrees sur 3000 avec un etalement symetrique), numpy donne q1 < 3000 < q3 et
# median == 3000. Un bien a LISTING_PRICE_M2 == 3000 verifie q1 < prix <= q3 ->
# verdict "Plutot aligne", stable quel que soit le pool retenu (ville/metropole).
LISTING_PRICE_M2 = 3000.0
SURFACE = 70.0  # fenetre comparables : [56, 84]
COMP_SURFACE = 70.0  # dans la fenetre +/-20 %

# Pools de prix/m2 (etales autour de 3000, q1 < 3000 < q3 verifie via numpy).
PRICES_4 = [2800.0, 2950.0, 3050.0, 3200.0]
PRICES_5 = [2700.0, 2900.0, 3000.0, 3100.0, 3300.0]
PRICES_6 = [2600.0, 2800.0, 3000.0, 3000.0, 3200.0, 3400.0]
PRICES_10 = [
    2600.0, 2700.0, 2800.0, 2900.0, 3000.0,
    3000.0, 3100.0, 3200.0, 3300.0, 3400.0,
]


def _insert_comparables(city, prices, district=None, property_type="appartement",
                        dpe=None):
    """Insere un comparable par prix/m2 dans `prices`, en ville canonique, avec
    une surface dans la fenetre +/-20 % du bien teste. `price_total` est derive
    de `price_m2 * surface` pour rester coherent avec le modele."""
    db = SessionLocal()
    try:
        canon = canonical_city(city)
        for pm2 in prices:
            comp = Comparable(
                id=f"i87-{uuid.uuid4().hex}",
                source="test",
                city=canon,
                district=district,
                property_type=property_type,
                surface_m2=COMP_SURFACE,
                price_total=pm2 * COMP_SURFACE,
                price_m2=pm2,
                dpe=dpe,
            )
            db.add(comp)
        db.commit()
    finally:
        db.close()


def _pillar(city, district=None, dpe=None, surface=SURFACE,
            listing_price_m2=LISTING_PRICE_M2):
    return compute_price_market_pillar(
        city=city,
        district=district,
        property_type="appartement",
        surface_m2=surface,
        listing_price_m2=listing_price_m2,
        dpe=dpe,
    )


# Marqueurs d'oracle robustes du wording (§3.2 / §4) : on n'asserte PAS la phrase
# au caractere pres, seulement les invariants exigibles.
WARNING_MARKER = "repère"
NEIGHBOR_MARKER = "communes voisines"


def _has_warning(explanation):
    return WARNING_MARKER in explanation


# ===========================================================================
# Scenario 6 / AC5d — constantes (assertion statique, ancre la doctrine)
# ===========================================================================
def test_ac5d_min_comparables_constant_is_5():
    # Rouge attendu : MIN_COMPARABLES vaut encore 3 dans le code.
    assert MIN_COMPARABLES == 5, (
        "AC5d : MIN_COMPARABLES doit valoir 5 (plancher releve, spec §3.3)"
    )


def test_ac5d_min_refined_unchanged_is_10():
    assert MIN_REFINED_COMPARABLES == 10, (
        "AC5d : MIN_REFINED_COMPARABLES reste 10 (inchange, spec §3.3)"
    )


def test_ac5d_invariant_min_lt_refined():
    assert MIN_COMPARABLES < MIN_REFINED_COMPARABLES, (
        "AC5d : invariant MIN_COMPARABLES (5) < MIN_REFINED_COMPARABLES (10)"
    )


# ===========================================================================
# Scenario 1 / AC1 + AC5a — commune d'agglo creuse (4) + metropole fournie (>=5)
# ===========================================================================
def test_ac1_warning_appears_on_metropole_fallback():
    """Marly (metro), 4 comparables ville (creuse) + 1 ailleurs dans l'agglo :
    la cascade bascule au repli metropole et le wording apparait."""
    _insert_comparables("Marly", PRICES_4)            # ville Marly : 4 (< 5)
    _insert_comparables("Woippy", [3000.0])           # agglo : total metropole 5
    pillar = _pillar("Marly")

    assert pillar["scope"] == "metropole", (
        f"AC1/AC5a : commune creuse (4) doit basculer metropole, recu "
        f"scope={pillar['scope']!r}"
    )
    expl = pillar["explanation"]
    assert _has_warning(expl), (
        f"AC1 : le wording d'avertissement (marqueur {WARNING_MARKER!r}) doit "
        f"apparaitre sur repli metropole. explanation={expl!r}"
    )
    assert "Marly" in expl, (
        f"AC1 : l'explication doit nommer la commune du bien (Marly). "
        f"explanation={expl!r}"
    )
    assert pillar["scope_name"] in expl, (
        f"AC1 : l'explication doit nommer le perimetre elargi "
        f"({pillar['scope_name']!r}). explanation={expl!r}"
    )


def test_ac5a_border_4_comparables_switches_to_metropole():
    """Borne EXACTE 4 (entre l'ancien 3 et le nouveau 5) : 4 comparables ville
    -> scope metropole + wording (ancien comportement aurait garde la ville)."""
    _insert_comparables("Marly", PRICES_4)            # exactement 4
    _insert_comparables("Woippy", [2900.0, 3100.0])   # total metropole = 6
    pillar = _pillar("Marly")

    assert pillar["scope"] == "metropole", (
        f"AC5a : 4 comparables ville (< MIN_COMPARABLES=5) doit basculer "
        f"metropole, recu scope={pillar['scope']!r}"
    )
    assert _has_warning(pillar["explanation"]), (
        "AC5a : wording attendu sur ce repli metropole"
    )


# ===========================================================================
# Scenario 2 / AC2 + AC5b — commune d'agglo fournie (>=5), borne incluse a 5
# ===========================================================================
def test_ac5b_border_5_comparables_stays_ville():
    """Borne EXACTE 5 (incluse, >= MIN_COMPARABLES) : 5 comparables ville ->
    scope ville, pas de wording. Des comparables metropole existent pour prouver
    que la ville est PREFEREE des qu'elle atteint le plancher."""
    _insert_comparables("Marly", PRICES_5)            # exactement 5 (>= 5)
    _insert_comparables("Woippy", [2900.0, 3100.0])   # bruit metropole
    pillar = _pillar("Marly")

    assert pillar["scope"] == "ville", (
        f"AC5b : 5 comparables ville (== MIN_COMPARABLES) doit RESTER ville, "
        f"recu scope={pillar['scope']!r}"
    )
    expl = pillar["explanation"]
    assert not _has_warning(expl), (
        f"AC2/AC5b : aucun wording d'avertissement attendu au scope ville. "
        f"explanation={expl!r}"
    )
    assert NEIGHBOR_MARKER not in expl, (
        f"AC2/AC5b : pas de mention 'communes voisines' au scope ville. "
        f"explanation={expl!r}"
    )


def test_ac2_no_warning_when_ville():
    """Pool ville large (>= 5) hors agglo : scope ville, pas de wording."""
    _insert_comparables("Thionville", PRICES_6)       # hors _METRO_CITIES, 6 >= 5
    pillar = _pillar("Thionville")

    assert pillar["scope"] == "ville", (
        f"AC2 : pool ville fourni doit rester ville, recu "
        f"scope={pillar['scope']!r}"
    )
    assert not _has_warning(pillar["explanation"]), (
        f"AC2 : pas de wording au scope ville. "
        f"explanation={pillar['explanation']!r}"
    )


# ===========================================================================
# Scenario 3 / AC2 — bien messin, scope quartier ou secteur, pas de wording
# ===========================================================================
def test_ac2_no_warning_when_quartier():
    """Bien messin avec quartier peuple (>= MIN_REFINED=10) : scope quartier,
    pas de wording d'avertissement (le quartier reste DANS la commune du bien)."""
    _insert_comparables("Metz", PRICES_10, district="Sablon")
    pillar = _pillar("Metz", district="Sablon")

    assert pillar["scope"] in ("quartier", "secteur"), (
        f"AC2 : quartier messin peuple doit donner scope quartier/secteur, recu "
        f"scope={pillar['scope']!r}"
    )
    expl = pillar["explanation"]
    assert not _has_warning(expl), (
        f"AC2 : pas de wording d'avertissement au scope quartier/secteur. "
        f"explanation={expl!r}"
    )
    assert NEIGHBOR_MARKER not in expl, (
        f"AC2 : pas de mention 'communes voisines' au scope quartier. "
        f"explanation={expl!r}"
    )


# ===========================================================================
# Scenario 4 / AC3 + AC4 — verdict, points et confidence inchanges par le wording
# ===========================================================================
def test_ac3_verdict_stable_on_metropole_fallback():
    """Le wording n'altere QUE l'explication : le verdict reste celui dicte par
    les quartiles (prix 3000 dans Q1-Q3 -> 'Plutot aligne')."""
    _insert_comparables("Marly", PRICES_4)
    _insert_comparables("Woippy", [3000.0])
    pillar = _pillar("Marly")

    assert pillar["verdict"] == "Plutôt aligné", (
        f"AC3 : verdict attendu 'Plutôt aligné' (prix dans Q1-Q3), recu "
        f"{pillar['verdict']!r}"
    )


def test_ac3_verdict_matches_interpret_directly():
    """AC3 (falsifiabilite) : le verdict du pilier est STRICTEMENT celui que
    `interpret_price_positioning` produit pour le meme market_stats, prouvant que
    le wording (ajoute a `explanation`) ne touche pas `verdict`."""
    _insert_comparables("Marly", PRICES_4)
    _insert_comparables("Woippy", [3000.0])
    pillar = _pillar("Marly")

    ms = market_stats.compute_market_stats(
        city="Marly", district=None, property_type="appartement",
        surface_m2=SURFACE, dpe=None,
    )
    assert ms is not None and ms["scope"] == "metropole"
    base = interpret_price_positioning(LISTING_PRICE_M2, ms)
    assert pillar["verdict"] == base["verdict"], (
        "AC3 : le verdict du pilier doit etre identique a celui de "
        "interpret_price_positioning (le wording ne change que l'explication)"
    )


def test_ac4_points_and_confidence_unchanged_on_metropole():
    """AC4 : sur un cas a scope metropole, n_comparables / confidence sont ceux
    du pool, et `points` (derive du seul verdict via scoring.py) correspond au
    verdict 'aligne' (40/40). Le wording ne touche ni le scoring ni la confiance.
    """
    from app.scoring import compute_global_score

    _insert_comparables("Marly", PRICES_4)
    _insert_comparables("Woippy", [2900.0, 3100.0])   # total metropole = 6
    pillar = _pillar("Marly")

    assert pillar["scope"] == "metropole"
    assert pillar["n_comparables"] == 6, (
        f"AC4 : n_comparables doit refleter le pool metropole (6), recu "
        f"{pillar['n_comparables']}"
    )
    # confidence : count==6 (>=4, <10) -> "Moyenne" (compute_confidence inchangee)
    assert pillar["confidence"] == "Moyenne", (
        f"AC4 : confidence inchangee attendue 'Moyenne', recu "
        f"{pillar['confidence']!r}"
    )
    # points : fonction du seul verdict (AC3) ; 'Plutot aligne' -> 40/40
    semantic = {"transparency_score": 70, "risk_level": "Faible"}
    breakdown = compute_global_score(price_pillar=pillar, semantic_pillar=semantic)
    assert breakdown["breakdown"]["price"] == 40, (
        f"AC4 : points prix (derives du verdict 'aligne') = 40, recu "
        f"{breakdown['breakdown']['price']}"
    )


# ===========================================================================
# Scenario 5 / AC5c — bien HORS _METRO_CITIES avec 4 comparables -> Indetermine
# ===========================================================================
def test_ac5c_out_of_metro_4_comparables_indetermine():
    """Hors agglo (pas de candidat metropole), 4 comparables ville : le filet
    (ville, base) a < MIN_COMPARABLES=5 -> garde-fou final -> None -> pilier
    'Indetermine'."""
    _insert_comparables("Forbach", PRICES_4)          # hors _METRO_CITIES, 4 < 5
    pillar = _pillar("Forbach")

    assert pillar["verdict"] == "Indéterminé", (
        f"AC5c : 4 comparables hors agglo (< MIN_COMPARABLES=5) doit donner "
        f"'Indéterminé', recu verdict={pillar['verdict']!r}"
    )
    assert pillar["scope"] is None, (
        f"AC5c : scope None attendu sur 'Indéterminé', recu "
        f"{pillar['scope']!r}"
    )
    assert pillar["n_comparables"] == 0, (
        f"AC5c : n_comparables 0 attendu sur 'Indéterminé', recu "
        f"{pillar['n_comparables']}"
    )


# ===========================================================================
# Scenario 7 / AC-CONTRAT — cles du pilier (direct) + cles du corps /analyze
# ===========================================================================
PILLAR_KEYS = {
    "verdict", "explanation", "confidence", "scope", "scope_name",
    "dpe_band", "n_comparables", "refinable", "listing_price_m2",
}
PILLAR_KEYS_EXPOSED = {
    "label", "verdict", "explanation", "points", "max", "scope",
    "scope_name", "dpe_band", "n_comparables", "refinable",
    "listing_price_m2",
}
BODY_KEYS = {
    "global_score", "verdict", "confidence", "pillars", "actions",
    "local_context",
}


def test_ac_contract_b_pillar_keys_exact_metropole():
    """AC-CONTRAT (b) : hors Pydantic, le set des cles du dict retourne par
    `compute_price_market_pillar` est EXACTEMENT PILLAR_KEYS — falsifiable si un
    champ (ex. scope_is_fallback) est ajoute. Cas scope metropole (wording actif)."""
    _insert_comparables("Marly", PRICES_4)
    _insert_comparables("Woippy", [3000.0])
    pillar = _pillar("Marly")

    assert pillar["scope"] == "metropole"
    assert set(pillar.keys()) == PILLAR_KEYS, (
        f"AC-CONTRAT(b) : cles du pilier figees. Inattendues="
        f"{set(pillar.keys()) - PILLAR_KEYS}, manquantes="
        f"{PILLAR_KEYS - set(pillar.keys())}"
    )


def test_ac_contract_b_pillar_keys_exact_ville():
    """AC-CONTRAT (b) : meme set de cles exact au scope ville (pas de wording)."""
    _insert_comparables("Thionville", PRICES_6)
    pillar = _pillar("Thionville")

    assert pillar["scope"] == "ville"
    assert set(pillar.keys()) == PILLAR_KEYS, (
        f"AC-CONTRAT(b) : cles du pilier figees au scope ville. Diff="
        f"{set(pillar.keys()) ^ PILLAR_KEYS}"
    )


def test_ac_contract_b_pillar_keys_exact_indetermine():
    """AC-CONTRAT (b) : meme set de cles exact sur 'Indetermine'."""
    pillar = _pillar("Forbach")  # aucun comparable -> None -> Indetermine
    assert pillar["verdict"] == "Indéterminé"
    assert set(pillar.keys()) == PILLAR_KEYS, (
        f"AC-CONTRAT(b) : cles du pilier figees sur Indéterminé. Diff="
        f"{set(pillar.keys()) ^ PILLAR_KEYS}"
    )


@pytest.fixture()
def _fake_semantic_marly(monkeypatch):
    """Monkeypatch `analyze_semantic` (vu depuis app.analysis) pour un listing
    deterministe sur une commune d'agglo creuse (Marly), sans appel LLM. Permet
    d'exercer le chemin endpoint /analyze sur le cas repli metropole + wording."""
    import app.analysis as analysis_mod

    def _fake(raw_text):
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
                "city": "Marly",
                "district": None,
                "property_type": "appartement",
                "surface_m2": SURFACE,
                "price_total": LISTING_PRICE_M2 * SURFACE,
                "dpe": None,
                "construction_year": None,
                "floor": None, "has_elevator": None, "has_terrace": None,
                "has_balcony": None, "has_cellar": None, "parking": None,
                "bedrooms": None, "condo_fees": None,
            },
        }

    monkeypatch.setattr(analysis_mod, "analyze_semantic", _fake)


def test_ac_contract_a_analyze_body_and_pillar_keys(client, _fake_semantic_marly):
    """AC-CONTRAT (a) : via TestClient POST /analyze, les cles du corps sont
    EXACTEMENT BODY_KEYS et chaque pilier ne porte que PILLAR_KEYS_EXPOSED (§3.4).
    Cas repli metropole (Marly creuse + agglo) : prouve que le wording n'ajoute
    aucune cle au contrat (pillars est type `list`, FastAPI ne filtre pas —
    lecon 9.10)."""
    _insert_comparables("Marly", PRICES_4)
    _insert_comparables("Woippy", [3000.0])

    resp = client.post(
        "/analyze",
        json={"raw_text": "Appartement a Marly, 70 m2, issue 87."},
        headers={"Fly-Client-IP": "203.0.113.87"},
    )
    assert resp.status_code == 200, (
        f"AC-CONTRAT(a) : /analyze attendu 200, recu {resp.status_code}"
    )
    body = resp.json()
    assert set(body.keys()) == BODY_KEYS, (
        f"AC-CONTRAT(a) : cles du corps figees. Diff={set(body.keys()) ^ BODY_KEYS}"
    )

    price_pillar = body["pillars"][0]
    assert price_pillar["label"] == "Prix vs marché local"
    extra = set(price_pillar.keys()) - PILLAR_KEYS_EXPOSED
    assert not extra, (
        f"AC-CONTRAT(a) : le pilier prix expose une cle non autorisee : {extra} "
        f"(spec §3.4)"
    )
    # Le repli metropole doit etre observable de bout en bout (wording present).
    assert price_pillar["scope"] == "metropole", (
        f"AC-CONTRAT(a) : scope metropole attendu sur ce cas, recu "
        f"{price_pillar['scope']!r}"
    )
    assert _has_warning(price_pillar["explanation"]), (
        f"AC-CONTRAT(a) : wording attendu dans l'explication exposee. "
        f"explanation={price_pillar['explanation']!r}"
    )


# ===========================================================================
# Phase B (challenge adversarial) — sondes de falsifiabilite et anti-regression
# ===========================================================================
# Ces tests verrouillent des invariants que les AC de phase A ne prouvaient pas
# directement : la commune du bien transite par ARGUMENT explicite (pas par une
# cle interne du dict market_stats), et le wording ne fuit que dans `explanation`.

def test_phase_b_property_city_does_not_leak_into_market_stats_dict():
    """Le dev fait transiter la commune du bien jusqu'au wording. La spec (§3.1)
    autorise une cle interne (ex. `property_city`) MAIS exige qu'aucune cle
    nouvelle ne fuite dans le pilier expose. Verrou : le dict market_stats interne
    ne doit porter AUCUNE cle recopiant la commune du bien. Si un refactor futur
    reintroduit `property_city` dans market_stats, `compute_price_market_pillar`
    pourrait la recopier dans le pilier sans qu'aucun autre test ne le voie
    (lecon cross-agence-inc2b : prouver le transit reel, pas seulement l'absence
    d'erreur). scope_name reste autorise (perimetre, pas commune du bien)."""
    _insert_comparables("Marly", PRICES_4)
    _insert_comparables("Woippy", [3000.0])
    ms = market_stats.compute_market_stats(
        city="Marly", district=None, property_type="appartement",
        surface_m2=SURFACE, dpe=None,
    )
    assert ms is not None and ms["scope"] == "metropole"
    # scope_name est le PERIMETRE (Metz Metropole), jamais la commune du bien.
    assert "Marly" not in ms.get("scope_name", ""), (
        f"phase B : scope_name ne doit pas etre la commune du bien (Marly), "
        f"recu {ms.get('scope_name')!r}"
    )
    # Aucune cle ne doit s'appeler comme une cle de commune d'origine ni contenir
    # la valeur 'Marly' (anti-recopie dans le pilier expose).
    forbidden_keys = {"property_city", "city", "origin_city"}
    assert not (forbidden_keys & set(ms.keys())), (
        f"phase B : market_stats ne doit pas porter de cle de commune du bien "
        f"({forbidden_keys & set(ms.keys())}). Choix de transit = argument "
        f"explicite, pas cle interne du dict."
    )
    leaking = {k: v for k, v in ms.items() if k != "scope_name" and "Marly" in str(v)}
    assert not leaking, (
        f"phase B : aucune valeur de market_stats (hors scope_name) ne doit "
        f"contenir la commune du bien. Fuites={leaking}"
    )


def test_phase_b_warning_only_in_explanation_not_other_pillar_fields():
    """Falsifiabilite renforcee (AC3/AC4) : le wording (marqueur 'repere',
    'communes voisines', nom de commune) n'apparait QUE dans `explanation`,
    jamais dans verdict / scope / scope_name / dpe_band / confidence. Prouve que
    le wording n'altere aucun champ structurant du pilier."""
    _insert_comparables("Marly", PRICES_4)
    _insert_comparables("Woippy", [3000.0])
    pillar = _pillar("Marly")

    assert pillar["scope"] == "metropole"
    assert _has_warning(pillar["explanation"])  # wording bien present
    for field in ("verdict", "scope", "scope_name", "dpe_band", "confidence"):
        val = str(pillar.get(field))
        assert WARNING_MARKER not in val, (
            f"phase B : le marqueur {WARNING_MARKER!r} ne doit pas fuiter dans "
            f"le champ {field!r} (={val!r})"
        )
        assert NEIGHBOR_MARKER not in val, (
            f"phase B : 'communes voisines' ne doit pas fuiter dans {field!r}"
        )
    # scope_name reste le perimetre brut, sans phrase d'avertissement.
    assert pillar["scope_name"] == "Metz Métropole", (
        f"phase B : scope_name doit rester le perimetre brut, recu "
        f"{pillar['scope_name']!r}"
    )


def test_phase_b_scope_warning_unit_falsy_scope_name_falls_back():
    """Sonde unitaire directe de `_scope_warning` (chemin non couvert via la
    cascade) : si scope_name est falsy (None / ''), le wording retombe sur
    _METRO_NAME au lieu de produire 'None' ou un trou. Garantit pas de crash et
    pas de texte degrade sur un market_stats metropole sans scope_name."""
    for falsy in (None, ""):
        out = market_stats._scope_warning(
            {"scope": "metropole", "scope_name": falsy}, "Marly"
        )
        assert _has_warning(out), "phase B : wording attendu meme si scope_name falsy"
        assert market_stats._METRO_NAME in out, (
            f"phase B : fallback _METRO_NAME attendu, recu {out!r}"
        )
        assert "None" not in out, (
            f"phase B : aucune occurrence litterale 'None' dans le wording, "
            f"recu {out!r}"
        )
        assert "Marly" in out


def test_phase_b_scope_warning_unit_empty_for_all_non_metropole():
    """Sonde unitaire : `_scope_warning` renvoie '' pour TOUT scope non metropole
    (ville/quartier/secteur), pour un scope absent et pour un scope inconnu —
    aucun wording ne fuite hors du repli metropole (§4 AC2, condition exacte)."""
    for scope in ("ville", "quartier", "secteur", None, "departement"):
        out = market_stats._scope_warning(
            {"scope": scope, "scope_name": "X"}, "Marly"
        )
        assert out == "", (
            f"phase B : aucun wording attendu pour scope={scope!r}, recu {out!r}"
        )
    # market_stats sans cle 'scope' du tout : pas de crash, chaine vide.
    assert market_stats._scope_warning({}, "Marly") == ""


def test_phase_b_four_comparables_never_yields_a_range_any_scope():
    """Anti-contournement (§point 3) : aucun chemin ne doit produire une
    fourchette avec exactement 4 comparables. Un quartier messin a 4 (filet ville
    aussi a 4, pas de metropole exploitable) -> compute_market_stats renvoie None
    (garde-fou final len < MIN_COMPARABLES), jamais un scope quartier/ville a 4."""
    _insert_comparables("Metz", PRICES_4, district="Sablon")  # 4 quartier == 4 ville
    ms = market_stats.compute_market_stats(
        city="Metz", district="Sablon", property_type="appartement",
        surface_m2=SURFACE, dpe=None,
    )
    assert ms is None, (
        f"phase B : 4 comparables ne doivent JAMAIS produire de fourchette, "
        f"recu {None if ms is None else (ms['scope'], ms['count'])}"
    )

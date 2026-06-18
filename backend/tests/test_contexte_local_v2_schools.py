"""Tests-first (phase A) — Contexte local v2, volet D (ecoles) : AC31-AC40.
Spec : docs/specs/contexte-local-v2-SPEC.md §3.D / §4 / §5.

Volet D : snapshot Annuaire Education Nationale versionne
(`backend/app/data/schools_metz.json`), module `app/schools.py`, k-NN Haversine
(la plus proche par degre, <=4 facts), facts ecoles en mode ADRESSE uniquement,
claim `ecoles` reste A_VERIFIER (note enrichie sans jugement).

ETAT ATTENDU EN PHASE A : ROUGE — `app/schools.py` n'existe pas, `nearest_schools`
non plus, les facts ecoles ne sont pas produits. Les imports des points d'accroche
absents sont LOCAUX aux tests qui en dependent (ne pas casser la collecte du
module).

HOOK D'INJECTION SUPPOSEE (a signaler au developpeur) : les tests k-NN passent un
snapshot EXPLICITE plutot que de dependre du vrai `schools_metz.json` (donnee
reelle, non encore presente, et sans etat partage — spec §7). On suppose donc que
`nearest_schools` accepte une source de donnees injectable. Convention retenue :
parametre kw-only `schools: list[dict] | None = None` (snapshot module par defaut).
Si le developpeur prefere `_load_schools()` + monkeypatch d'une constante module,
ce fichier devra etre ajuste par le testeur — voir helper `_call_nearest` qui
centralise l'appel pour faciliter cet ajustement.

AUCUN appel reseau / LLM. Isolation par les fixtures autouse du conftest.
"""

import re
import subprocess
import sys
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[1]

DEGRE_ORDER = ["maternelle", "elementaire", "college", "lycee"]
DEGRE_LISIBLE = {
    "maternelle": "École maternelle",
    "elementaire": "École élémentaire",
    "college": "Collège",
    "lycee": "Lycée",
}


# Point de reference des tests k-NN (centre de Metz, proche cathedrale).
REF_LAT = 49.1193
REF_LON = 6.1757


def _make_school(name, degre, commune, lat, lon):
    return {"name": name, "degre": degre, "commune": commune, "lat": lat, "lon": lon}


# Snapshot de test EXPLICITE : 2 ecoles par degre maternelle/elementaire/college,
# une seule lycee, AUCUNE entree pour un autre degre. Pour chaque degre, l'ecole
# "_proche" est plus pres de (REF_LAT, REF_LON) que "_loin" (coords decalees).
SNAPSHOT = [
    _make_school("Mat Proche", "maternelle", "Metz", 49.1195, 6.1760),
    _make_school("Mat Loin", "maternelle", "Metz", 49.1400, 6.2100),
    _make_school("Elem Proche", "elementaire", "Metz", 49.1190, 6.1750),
    _make_school("Elem Loin", "elementaire", "Metz", 49.0900, 6.1300),
    _make_school("College Proche", "college", "Metz", 49.1200, 6.1770),
    _make_school("College Loin", "college", "Marly", 49.0700, 6.1600),
    _make_school("Lycee Unique", "lycee", "Metz", 49.1250, 6.1800),
]


def _call_nearest(lat, lon, snapshot):
    """Centralise l'appel a nearest_schools avec un snapshot injecte (hook supposee
    `schools=` kw-only). Si le developpeur choisit une autre hook d'injection,
    seul ce helper est a adapter (cote testeur)."""
    from app.schools import nearest_schools

    return nearest_schools(lat, lon, schools=snapshot)


# ===========================================================================
# AC31 — import sans cycle (sous-processus, premier import de chaque module)
# ===========================================================================
def test_ac31_import_app_schools_first_no_cycle():
    """AC31 : `python -c "import app.schools"` reussit en TOUT PREMIER import
    (process separe). Rouge tant que le module n'existe pas (ModuleNotFoundError),
    et le restera si un cycle top-level avec metz_local/analysis apparait."""
    proc = subprocess.run(
        [sys.executable, "-c", "import app.schools"],
        cwd=str(BACKEND), capture_output=True, text=True,
    )
    assert proc.returncode == 0, (
        f"AC31 : `import app.schools` en premier import doit reussir.\n"
        f"stderr={proc.stderr}"
    )


def test_ac31_import_metz_local_first_no_cycle():
    """AC31 : `python -c "import app.metz_local"` reussit aussi en premier import.
    Garde-fou cycle (lecon issue-100-B) : si metz_local importe schools au
    top-level et schools importe metz_local au top-level, l'un des deux casse."""
    proc = subprocess.run(
        [sys.executable, "-c", "import app.metz_local"],
        cwd=str(BACKEND), capture_output=True, text=True,
    )
    assert proc.returncode == 0, (
        f"AC31 : `import app.metz_local` en premier import doit reussir (cycle ?).\n"
        f"stderr={proc.stderr}"
    )


# ===========================================================================
# AC32 — k-NN correct : la plus proche par degre (identite exacte)
# ===========================================================================
def test_ac32_knn_returns_closest_per_degre_by_identity():
    """AC32 : pour chaque degre, nearest_schools renvoie l'ecole dont la distance
    Haversine est MINIMALE — verifie par IDENTITE (name), pas seulement la distance.
    Falsifiable : on echange ensuite la plus proche pour la plus lointaine et on
    s'attend a une selection differente."""
    out = _call_nearest(REF_LAT, REF_LON, SNAPSHOT)
    by_degre = {d["degre"]: d for d in out}
    assert by_degre.get("maternelle", {}).get("name") == "Mat Proche", (
        f"AC32 : maternelle la plus proche attendue 'Mat Proche', recu {by_degre.get('maternelle')!r}"
    )
    assert by_degre.get("elementaire", {}).get("name") == "Elem Proche", (
        f"AC32 : elementaire attendue 'Elem Proche', recu {by_degre.get('elementaire')!r}"
    )
    assert by_degre.get("college", {}).get("name") == "College Proche", (
        f"AC32 : college attendu 'College Proche', recu {by_degre.get('college')!r}"
    )
    assert by_degre.get("lycee", {}).get("name") == "Lycee Unique", (
        f"AC32 : lycee attendu 'Lycee Unique', recu {by_degre.get('lycee')!r}"
    )


def test_ac32_knn_falsifiable_when_moving_a_school():
    """AC32 (falsifiabilite) : en deplacant 'Mat Loin' TRES pres du point de
    reference (plus pres que 'Mat Proche'), la selection maternelle bascule sur
    'Mat Loin'. Prouve que la selection depend bien de la distance, pas d'un ordre
    de liste fige."""
    snap = [dict(s) for s in SNAPSHOT]
    for s in snap:
        if s["name"] == "Mat Loin":
            s["lat"], s["lon"] = REF_LAT, REF_LON  # colle au point de reference
    out = _call_nearest(REF_LAT, REF_LON, snap)
    by_degre = {d["degre"]: d for d in out}
    assert by_degre.get("maternelle", {}).get("name") == "Mat Loin", (
        f"AC32 : apres deplacement, la maternelle la plus proche doit etre "
        f"'Mat Loin', recu {by_degre.get('maternelle')!r}"
    )


def test_ac32_each_entry_has_required_keys():
    """AC32 (forme) : chaque dict renvoye porte {name, degre, commune, distance_km}
    et distance_km est un nombre positif coherent (Haversine)."""
    out = _call_nearest(REF_LAT, REF_LON, SNAPSHOT)
    for entry in out:
        assert set(["name", "degre", "commune", "distance_km"]) <= set(entry), (
            f"AC32 : dict ecole attendu {{name, degre, commune, distance_km}}, recu "
            f"{set(entry)}"
        )
        assert isinstance(entry["distance_km"], (int, float)) and entry["distance_km"] >= 0, (
            f"AC32 : distance_km positive attendue, recu {entry['distance_km']!r}"
        )


# ===========================================================================
# AC33 — au plus 4 entrees, 1 par degre, ordre fixe, degre absent omis
# ===========================================================================
def test_ac33_at_most_four_one_per_degre_ordered():
    """AC33 : au plus 4 entrees (une par degre present), triees dans l'ordre
    {maternelle, elementaire, college, lycee}. Le snapshot complet a les 4 degres."""
    out = _call_nearest(REF_LAT, REF_LON, SNAPSHOT)
    assert len(out) <= 4, f"AC33 : au plus 4 facts ecoles, recu {len(out)}"
    degres = [d["degre"] for d in out]
    assert len(degres) == len(set(degres)), (
        f"AC33 : un seul fact par degre attendu, recu {degres}"
    )
    # Ordre = sous-suite de DEGRE_ORDER (degres absents omis sans casser l'ordre).
    filtered_order = [d for d in DEGRE_ORDER if d in degres]
    assert degres == filtered_order, (
        f"AC33 : ordre attendu {filtered_order}, recu {degres}"
    )


def test_ac33_missing_degre_is_omitted():
    """AC33 (degre absent) : un snapshot sans aucun lycee produit au plus 3
    entrees, sans fact vide pour le lycee."""
    snap = [s for s in SNAPSHOT if s["degre"] != "lycee"]
    out = _call_nearest(REF_LAT, REF_LON, snap)
    degres = [d["degre"] for d in out]
    assert "lycee" not in degres, (
        f"AC33 : un degre absent du snapshot doit etre omis, recu {degres}"
    )
    assert len(out) <= 3, f"AC33 : <=3 facts attendus sans lycee, recu {len(out)}"


def test_ac33_empty_snapshot_returns_empty():
    """AC33 (snapshot vide) : nearest_schools sur un snapshot vide renvoie []."""
    out = _call_nearest(REF_LAT, REF_LON, [])
    assert out == [], f"AC33 : liste vide attendue sur snapshot vide, recu {out!r}"


# ===========================================================================
# AC34 — perimetre Metz + couronne : toutes les communes du snapshot reel
# appartiennent a _METRO_CITIES (forme canonique)
# ===========================================================================
def test_ac34_real_snapshot_communes_in_metro_cities():
    """AC34 : toutes les ecoles du snapshot REEL `schools_metz.json` ont une
    commune (canonicalisee) ∈ market_stats._METRO_CITIES. Falsifiable en injectant
    une commune hors perimetre. Rouge tant que le fichier data / le loader manque."""
    from app.market_stats import _METRO_CITIES
    from scrapers.base import canonical_city

    # On lit le snapshot via la hook de chargement du module (pas via mon propre
    # parsing) pour que le test verrouille la donnee REELLEMENT chargee a froid.
    from app.schools import _load_schools

    snapshot = _load_schools()
    assert isinstance(snapshot, list) and snapshot, (
        "AC34 : le snapshot reel doit etre une liste non vide d'ecoles"
    )
    for s in snapshot:
        canon = canonical_city(s["commune"])
        assert canon in _METRO_CITIES, (
            f"AC34 : commune {s['commune']!r} (canon {canon!r}) de l'ecole "
            f"{s.get('name')!r} hors _METRO_CITIES {_METRO_CITIES}"
        )


def test_ac34_real_snapshot_degres_valid():
    """AC34 (coherence donnee) : chaque entree du snapshot reel a un `degre` dans
    l'enum {maternelle, elementaire, college, lycee} et des coords numeriques."""
    from app.schools import _load_schools

    for s in _load_schools():
        assert s["degre"] in DEGRE_ORDER, (
            f"AC34 : degre invalide {s['degre']!r} pour {s.get('name')!r}"
        )
        assert isinstance(s["lat"], (int, float)) and isinstance(s["lon"], (int, float)), (
            f"AC34 : coords numeriques attendues pour {s.get('name')!r}"
        )


# ===========================================================================
# AC35 — facts ecoles en mode ADRESSE : label degre lisible, value vol d'oiseau
# ===========================================================================
@pytest.fixture()
def patch_schools(monkeypatch):
    """Force nearest_schools (vu depuis metz_local) a renvoyer un jeu de test
    deterministe, sans dependre du snapshot reel ni d'etat partage. On monkeypatche
    le symbole tel qu'IMPORTE par metz_local."""
    import app.metz_local as ml

    def _fake_nearest(lat, lon, schools=None):
        return [
            {"name": "Jean Moulin", "degre": "elementaire", "commune": "Metz",
             "distance_km": 0.35},
            {"name": "Robert Schuman", "degre": "lycee", "commune": "Metz",
             "distance_km": 1.2},
        ]

    monkeypatch.setattr(ml, "nearest_schools", _fake_nearest, raising=False)
    return _fake_nearest


def test_ac35_adresse_appends_school_facts(patch_schools):
    """AC35 : en mode ADRESSE, local_context_from_coords ajoute APRES les 4 facts
    POI un fact par ecole, label commencant par un degre lisible
    (École maternelle/élémentaire/Collège/Lycée) et value finissant par
    « à vol d'oiseau ». Rouge tant que metz_local n'appelle pas nearest_schools."""
    from app.metz_local import local_context_from_coords

    ctx = local_context_from_coords(REF_LAT, REF_LON)
    facts = ctx["facts"]
    assert len(facts) >= 6, (
        f"AC35 : 4 POI + 2 ecoles attendus (>=6 facts), recu {len(facts)} : "
        f"{[f['label'] for f in facts]}"
    )
    school_facts = facts[4:]
    # Au moins une ecole rendue, avec degre lisible en prefixe.
    prefixes = tuple(DEGRE_LISIBLE.values())
    matched = [f for f in school_facts if f["label"].startswith(prefixes)]
    assert matched, (
        f"AC35 : au moins un fact ecole avec prefixe degre lisible attendu, recu "
        f"{[f['label'] for f in school_facts]}"
    )
    for f in matched:
        assert f["value"].rstrip().endswith("à vol d'oiseau"), (
            f"AC35 : value ecole doit finir par 'à vol d'oiseau', recu {f['value']!r}"
        )


# ===========================================================================
# AC36 — pas de jugement de valeur dans les facts ecoles
# ===========================================================================
def test_ac36_no_value_judgement_in_school_facts(patch_schools):
    """AC36 : aucun label/value de fact ecole ne contient 'prisé', 'recherché',
    'bien desservi' (mots de jugement interdits)."""
    from app.metz_local import local_context_from_coords

    ctx = local_context_from_coords(REF_LAT, REF_LON)
    school_facts = ctx["facts"][4:]
    assert school_facts, (
        "AC36 : des facts ecoles sont attendus (snapshot injecte) pour que "
        "l'invariant ne soit pas vacue. Facts="
        f"{[f['label'] for f in ctx['facts']]}"
    )
    forbidden = ("prisé", "prise", "recherché", "recherche", "bien desservi", "desservi")
    for f in school_facts:
        blob = (f["label"] + " " + f["value"]).lower()
        for word in forbidden:
            assert word not in blob, (
                f"AC36 : mot de jugement {word!r} interdit dans un fact ecole, recu "
                f"{f!r}"
            )


# ===========================================================================
# AC37 — aucun fact ecole en mode QUARTIER
# ===========================================================================
def test_ac37_no_school_facts_in_quartier_mode(monkeypatch):
    """AC37 : en mode QUARTIER, aucun fact ecole n'est produit (local_context
    n'appelle pas nearest_schools). On rend nearest_schools explosif : s'il etait
    appele en mode quartier, le test rougirait."""
    import app.metz_local as ml

    def _boom(*a, **k):
        raise AssertionError("AC37 : nearest_schools ne doit PAS etre appele en mode quartier")

    monkeypatch.setattr(ml, "nearest_schools", _boom, raising=False)

    ctx = ml.local_context("Sablon")
    assert ctx is not None
    prefixes = tuple(DEGRE_LISIBLE.values())
    for f in ctx["facts"]:
        assert not f["label"].startswith(prefixes), (
            f"AC37 : aucun fact ecole attendu en mode quartier, recu {f['label']!r}"
        )


# ===========================================================================
# AC38 — distance vol d'oiseau, jamais de minutes pour les ecoles
# ===========================================================================
def test_ac38_school_facts_have_no_minutes(patch_schools):
    """AC38 : aucun fact ecole n'affiche un temps en minutes (le value ne matche
    pas `~\\d+ min`). Routing ecoles = OUT au lot 1 (fausse precision)."""
    from app.metz_local import local_context_from_coords

    ctx = local_context_from_coords(REF_LAT, REF_LON)
    school_facts = ctx["facts"][4:]
    assert school_facts, (
        "AC38 : des facts ecoles sont attendus (snapshot injecte) pour que "
        "l'invariant ne soit pas vacue. Facts="
        f"{[f['label'] for f in ctx['facts']]}"
    )
    minute_re = re.compile(r"~\d+\s*min")
    for f in school_facts:
        assert not minute_re.search(f["value"]), (
            f"AC38 : un fact ecole ne doit pas afficher de minutes, recu {f['value']!r}"
        )


# ===========================================================================
# Label ecole : pas de doublon de degre (« Collège College Arsenal »)
# Le snapshot Annuaire Education prefixe deja le degre dans `name` ; le fact ne
# doit pas le repeter. Regression du rendu observe en staging (2026-06-18).
# ===========================================================================
@pytest.mark.parametrize("name, degre, expected", [
    ("Maternelle Debussy", "maternelle", "École maternelle Debussy"),
    ("Ecole elementaire Debussy", "elementaire", "École élémentaire Debussy"),
    ("College Arsenal", "college", "Collège Arsenal"),
    ("Lycee Fabert", "lycee", "Lycée Fabert"),
    # Nom propre sans descripteur de degre : inchange.
    ("Jean Moulin", "elementaire", "École élémentaire Jean Moulin"),
    # Casse / accents indifferents pour la detection du prefixe.
    ("ÉCOLE MATERNELLE Les Hauts", "maternelle", "École maternelle Les Hauts"),
])
def test_school_label_no_degree_duplication(name, degre, expected):
    from app.metz_local import _DEGRE_LISIBLE, _clean_school_name

    label = f"{_DEGRE_LISIBLE.get(degre, 'École')} {_clean_school_name(name, degre)}"
    assert label == expected, f"label attendu {expected!r}, recu {label!r}"
    # Aucun mot de degre ne doit apparaitre deux fois (insensible a la casse).
    lowered = label.lower()
    for token in ("maternelle", "elementaire", "élémentaire", "college", "collège", "lycee", "lycée"):
        assert lowered.count(token) <= 1, (
            f"degre {token!r} duplique dans le label {label!r}"
        )


def test_school_facts_label_no_duplication_end_to_end(monkeypatch):
    """Bout en bout : des ecoles dont le `name` contient deja le degre produisent
    des labels sans doublon via local_context_from_coords."""
    import app.metz_local as ml

    def _fake_nearest(lat, lon, schools=None):
        return [
            {"name": "Maternelle Debussy", "degre": "maternelle", "commune": "Metz",
             "distance_km": 0.57},
            {"name": "College Arsenal", "degre": "college", "commune": "Metz",
             "distance_km": 0.11},
        ]

    monkeypatch.setattr(ml, "nearest_schools", _fake_nearest, raising=False)
    ctx = ml.local_context_from_coords(REF_LAT, REF_LON)
    labels = [f["label"] for f in ctx["facts"][4:]]
    assert "École maternelle Debussy" in labels, labels
    assert "Collège Arsenal" in labels, labels
    for label in labels:
        assert "College College" not in label and "Maternelle Maternelle" not in label, label


# ===========================================================================
# AC39 — claim `ecoles` reste A_VERIFIER (jamais coherent), adresse ET quartier
# ===========================================================================
def test_ac39_ecoles_claim_stays_a_verifier_quartier():
    """AC39 (mode quartier) : un claim {type:'ecoles'} reste A_VERIFIER apres
    assess_claims (jamais coherent). Falsifiable : rouge si le code bascule en
    coherent."""
    from app.metz_local import A_VERIFIER, COHERENT, assess_claims

    claims = [{"text": "École réputée à 2 min", "type": "ecoles"}]
    out = assess_claims("Sablon", claims, "Metz")
    assert out, "AC39 : un claim ecoles doit produire un resultat"
    ecoles = [c for c in out if c["type"] == "ecoles"]
    assert ecoles and ecoles[0]["status"] == A_VERIFIER, (
        f"AC39 : claim ecoles doit rester A_VERIFIER en mode quartier, recu "
        f"{ecoles[0]['status'] if ecoles else None!r}"
    )
    assert ecoles[0]["status"] != COHERENT, "AC39 : jamais coherent par complaisance"


def test_ac39_ecoles_claim_stays_a_verifier_adresse():
    """AC39 (mode adresse) : meme avec des distances exactes (dist_override), le
    claim ecoles reste A_VERIFIER — l'enrichissement de la note ne doit jamais le
    faire basculer en coherent."""
    from app.metz_local import A_VERIFIER, COHERENT, assess_claims

    claims = [{"text": "École à 300 m", "type": "ecoles"}]
    out = assess_claims(
        "Sablon", claims, "Metz",
        dist_override={"center": 0.5, "gare": 0.8},
    )
    ecoles = [c for c in out if c["type"] == "ecoles"]
    assert ecoles and ecoles[0]["status"] == A_VERIFIER, (
        f"AC39 : claim ecoles doit rester A_VERIFIER en mode adresse, recu "
        f"{ecoles[0]['status'] if ecoles else None!r}"
    )
    assert ecoles[0]["status"] != COHERENT


# ===========================================================================
# AC40 — note ecoles : distance factuelle possible (adresse), neutre (quartier)
# ===========================================================================
def test_ac40_ecoles_note_may_mention_distance_in_address_mode(monkeypatch):
    """AC40 (mode adresse) : la note du claim ecoles PEUT mentionner une distance
    factuelle (« ~<n> m » ou « ~<n>,<n> km » + « à vol d'oiseau ») sans aucun mot
    de jugement. On exerce le VRAI chemin run_full_analysis (couche qui produit),
    avec geocode patche et un snapshot ecoles injecte via metz_local.

    HOOK : l'enrichissement de la note (§3.D.3) se base sur l'ecole la plus proche.
    On patche nearest_schools pour fournir une elementaire a ~350 m, et on attend
    que la note du claim ecoles cite cette distance + 'à vol d'oiseau' sans jugement.
    Rouge tant que _assess_one n'enrichit pas la note en mode adresse."""
    import app.analysis as analysis_mod
    import app.metz_local as ml

    # Geocode -> coords connues (mode adresse).
    monkeypatch.setattr(
        analysis_mod, "geocode_address",
        lambda addr, city="Metz": {
            "lat": REF_LAT, "lon": REF_LON, "score": 0.9,
            "label": "Adresse Test Metz", "city": "Metz", "citycode": "57463",
            "postcode": "57000",
        },
    )
    # LLM deterministe avec un claim ecoles.
    monkeypatch.setattr(
        analysis_mod, "analyze_semantic",
        lambda raw_text: {
            "transparency_score": 70, "verdict": "Bonne", "risk_level": "Faible",
            "summary": "RAS.", "risk_summary": "RAS.", "questions": [],
            "negotiation_levers": [],
            "local_claims": [{"text": "Écoles à proximité", "type": "ecoles"}],
            "listing": {
                "city": "Metz", "district": "Sablon", "property_type": "appartement",
                "surface_m2": 70.0, "price_total": 210000.0, "dpe": None,
                "construction_year": None, "floor": None, "has_elevator": None,
                "has_terrace": None, "has_balcony": None, "has_cellar": None,
                "parking": None, "bedrooms": None, "condo_fees": None,
            },
        },
    )
    monkeypatch.setattr(
        ml, "nearest_schools",
        lambda lat, lon, schools=None: [
            {"name": "Jean Moulin", "degre": "elementaire", "commune": "Metz",
             "distance_km": 0.35},
        ],
        raising=False,
    )

    from app.analysis import run_full_analysis

    out = run_full_analysis("Appartement Sablon Metz 70 m2.", address="3 Rue Test Metz")
    lc = out.get("local_context") or {}
    claims = lc.get("claims") or []
    ecoles = [c for c in claims if c.get("type") == "ecoles"]
    assert ecoles, f"AC40 : un claim ecoles attendu, recu types {[c.get('type') for c in claims]}"
    note = ecoles[0].get("note") or ""
    dist_re = re.compile(r"~\d+(\s?m|,\d+\s?km|\s?km)")
    assert dist_re.search(note) and "à vol d'oiseau" in note, (
        f"AC40 : la note ecoles (mode adresse) doit citer une distance factuelle + "
        f"'à vol d'oiseau', recu {note!r}"
    )
    forbidden = ("prisé", "prise", "recherché", "recherche", "bien desservi")
    for word in forbidden:
        assert word not in note.lower(), (
            f"AC40 : mot de jugement {word!r} interdit dans la note ecoles, recu {note!r}"
        )


def test_ac40_ecoles_note_neutral_in_quartier_mode():
    """AC40 (mode quartier) : sans coordonnees, la note neutre actuelle est
    conservee (pas de distance factuelle inventee depuis un profil de quartier)."""
    from app.metz_local import assess_claims

    out = assess_claims("Sablon", [{"text": "Écoles proches", "type": "ecoles"}], "Metz")
    ecoles = [c for c in out if c["type"] == "ecoles"]
    assert ecoles, "AC40 : claim ecoles attendu"
    note = ecoles[0]["note"]
    assert not re.search(r"~\d+\s?m", note) and "à vol d'oiseau" not in note, (
        f"AC40 : aucune distance mesuree ne doit apparaitre en mode quartier, recu "
        f"{note!r}"
    )

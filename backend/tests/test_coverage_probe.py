"""
Probe de couverture read-only — GET /admin/comparables/coverage.

Contexte : docs/specs/comparables-coverage-ANALYSE.md §7 Q3 / §8 (mesurer la
couverture par (commune × type/source) sur la couronne de Metz, prerequis avant
tout chantier de densification). L'endpoint est strictement read-only et n'expose
que des compteurs agreges + libelles (conformite CONTEXT §11.3).

Isolation : le conftest autouse (`_reset_snapshots_table`) vide `comparables`
avant chaque test → on seed un jeu dedie et on asserte des valeurs exactes
(jamais un count() absolu fragile).
"""

from db.models import Comparable
from db.session import SessionLocal


ADMIN_TOKEN = "test-admin-token-coverage"


# Communes de la couronne (cf. _METRO_CITIES) et Metz, plusieurs types/sources.
# Forme canonique deja stockee telle quelle (le seed est direct, pas via la
# normalisation d'ingestion).
_SEED = [
    # Metz : 2 appartements bienici + 1 maison benedic
    ("metz-a1", "bienici", "Metz", "appartement"),
    ("metz-a2", "bienici", "Metz", "appartement"),
    ("metz-m1", "benedic", "Metz", "maison"),
    # Marly (couronne) : 1 maison immoheytienne + 1 maison benedic + 1 appart bienici
    ("marly-m1", "immoheytienne", "Marly", "maison"),
    ("marly-m2", "benedic", "Marly", "maison"),
    ("marly-a1", "bienici", "Marly", "appartement"),
    # Montigny-Les-Metz (couronne) : 1 appartement idemmo
    ("montigny-a1", "idemmo", "Montigny-Les-Metz", "appartement"),
    # Thionville (hors couronne) : 1 maison benedic
    ("thionville-m1", "benedic", "Thionville", "maison"),
]


def _seed_comparables(rows):
    db = SessionLocal()
    try:
        for listing_id, source, city, property_type in rows:
            db.add(
                Comparable(
                    id=listing_id,
                    source=source,
                    city=city,
                    property_type=property_type,
                    surface_m2=80.0,
                    price_total=250000.0,
                    price_m2=3125.0,
                )
            )
        db.commit()
    finally:
        db.close()


def _count_comparables():
    db = SessionLocal()
    try:
        return db.query(Comparable).count()
    finally:
        db.close()


def test_coverage_requires_admin_token_401(client, monkeypatch):
    # AC1 : ADMIN_TOKEN configure mais aucun token fourni (ou errone) -> 401.
    monkeypatch.setenv("ADMIN_TOKEN", ADMIN_TOKEN)

    resp_no_token = client.get("/admin/comparables/coverage")
    assert resp_no_token.status_code == 401, (
        f"sans token attendu 401, recu {resp_no_token.status_code} (AC1)"
    )

    resp_bad = client.get(
        "/admin/comparables/coverage",
        headers={"X-Admin-Token": "mauvais-token"},
    )
    assert resp_bad.status_code == 401, (
        f"token errone attendu 401, recu {resp_bad.status_code} (AC1)"
    )


def test_coverage_admin_token_not_configured_503(client, monkeypatch):
    # AC1 (variante) : ADMIN_TOKEN non configure -> 503 (probe desactivee), meme
    # mecanique que _check_admin_token sur les autres endpoints admin.
    monkeypatch.delenv("ADMIN_TOKEN", raising=False)

    resp = client.get(
        "/admin/comparables/coverage",
        headers={"X-Admin-Token": "peu-importe"},
    )
    assert resp.status_code == 503, (
        f"ADMIN_TOKEN non configure attendu 503, recu {resp.status_code} (AC1)"
    )


def test_coverage_aggregates_exact_counts(client, monkeypatch):
    # AC2 : base seedee connue (Metz + couronne + hors couronne, plusieurs types
    # et sources) -> total exact, et pour CHAQUE ville somme(by_type) == total ==
    # somme(by_source), avec les valeurs attendues.
    monkeypatch.setenv("ADMIN_TOKEN", ADMIN_TOKEN)
    _seed_comparables(_SEED)

    resp = client.get(
        "/admin/comparables/coverage",
        headers={"X-Admin-Token": ADMIN_TOKEN},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()

    assert body["total"] == len(_SEED), (
        f"total attendu {len(_SEED)}, recu {body['total']} (AC2)"
    )

    by_city = body["by_city"]
    assert set(by_city.keys()) == {
        "Metz",
        "Marly",
        "Montigny-Les-Metz",
        "Thionville",
    }, by_city.keys()

    # Invariant par ville : somme(by_type) == total == somme(by_source).
    for city, entry in by_city.items():
        assert sum(entry["by_type"].values()) == entry["total"], (
            f"{city}: somme by_type != total (AC2)"
        )
        assert sum(entry["by_source"].values()) == entry["total"], (
            f"{city}: somme by_source != total (AC2)"
        )

    # Valeurs exactes attendues.
    assert by_city["Metz"] == {
        "total": 3,
        "by_type": {"appartement": 2, "maison": 1},
        "by_source": {"bienici": 2, "benedic": 1},
    }
    assert by_city["Marly"] == {
        "total": 3,
        "by_type": {"maison": 2, "appartement": 1},
        "by_source": {"immoheytienne": 1, "benedic": 1, "bienici": 1},
    }
    assert by_city["Montigny-Les-Metz"] == {
        "total": 1,
        "by_type": {"appartement": 1},
        "by_source": {"idemmo": 1},
    }
    assert by_city["Thionville"] == {
        "total": 1,
        "by_type": {"maison": 1},
        "by_source": {"benedic": 1},
    }

    # Le total = somme des totaux par ville.
    assert sum(e["total"] for e in by_city.values()) == body["total"]


def test_coverage_is_read_only(client, monkeypatch):
    # AC3 : l'appel ne mute pas la base (nombre de lignes identique avant/apres).
    monkeypatch.setenv("ADMIN_TOKEN", ADMIN_TOKEN)
    _seed_comparables(_SEED)

    before = _count_comparables()
    resp = client.get(
        "/admin/comparables/coverage",
        headers={"X-Admin-Token": ADMIN_TOKEN},
    )
    assert resp.status_code == 200, resp.text
    after = _count_comparables()

    assert before == after == len(_SEED), (
        f"read-only viole : {before} avant, {after} apres (AC3)"
    )


def test_coverage_exposes_only_counts_and_labels(client, monkeypatch):
    # AC4 : la reponse ne contient QUE des entiers + libelles commune/type/source.
    # Aucune cle d'adresse/url/texte/prix par annonce ; `couronne` == _METRO_CITIES.
    from app.market_stats import _METRO_CITIES

    monkeypatch.setenv("ADMIN_TOKEN", ADMIN_TOKEN)
    _seed_comparables(_SEED)

    resp = client.get(
        "/admin/comparables/coverage",
        headers={"X-Admin-Token": ADMIN_TOKEN},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()

    assert set(body.keys()) == {"total", "by_city", "couronne"}, body.keys()
    assert isinstance(body["total"], int)

    forbidden = {
        "address",
        "url",
        "urls",
        "photo_urls",
        "text",
        "raw_text",
        "price",
        "price_total",
        "price_m2",
        "id",
        "listing_id",
        "surface_m2",
    }
    for city, entry in body["by_city"].items():
        assert isinstance(city, str)
        assert set(entry.keys()) == {"total", "by_type", "by_source"}, entry.keys()
        assert isinstance(entry["total"], int)
        for type_label, count in entry["by_type"].items():
            assert isinstance(type_label, str)
            assert isinstance(count, int)
            assert type_label not in forbidden
        for source_label, count in entry["by_source"].items():
            assert isinstance(source_label, str)
            assert isinstance(count, int)
            assert source_label not in forbidden

    assert sorted(body["couronne"]) == sorted(_METRO_CITIES), (
        "couronne doit refleter exactement _METRO_CITIES (AC4)"
    )
    # Les communes de couronne attendues doivent y figurer (lecture couronne).
    assert "Marly" in body["couronne"]
    assert "Metz" in body["couronne"]
    assert "Montigny-Les-Metz" in body["couronne"]

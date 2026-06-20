"""
Probe read-only du gisement de re-list cross-source — GET
/admin/comparables/cross-source-probe.

Contexte : GATE 1 de l'increment 3 (« mesurer le gisement cross-source AVANT
tout pipeline image »). L'endpoint expose les COMPTEURS AGREGES de
`tools.probe_cross_source.compute_probe` ; il est strictement read-only et
n'expose que des compteurs + libelles de source (conformite CONTEXT §11.3 :
aucun id/url/adresse/prix par-annonce).

Isolation : le conftest autouse (`_reset_snapshots_table`) vide `comparables`
avant chaque test → on seed un jeu dedie et on asserte des valeurs exactes
(jamais un count() absolu fragile). Les dates sont ancrees sur `utcnow()` (la
probe lit `now=None` → datetime.utcnow()) avec des marges larges pour rester
deterministe quel que soit l'instant d'execution.
"""

from datetime import datetime, timedelta

from db.models import Comparable
from db.session import SessionLocal


ADMIN_TOKEN = "test-admin-token-cross-source-probe"

ENDPOINT = "/admin/comparables/cross-source-probe"

EXPECTED_KEYS = {
    "total_pairs",
    "pairs_by_source_couple",
    "total_comparables",
    "disappeared",
    "by_source",
    "involved_pct",
}


def _insert(listing_id, source, last_seen_at, first_seen_at,
            surface=100.0, city="Metz", property_type="appartement",
            postal_code="57000", price_total=250000.0):
    db = SessionLocal()
    try:
        db.add(
            Comparable(
                id=listing_id,
                source=source,
                city=city,
                postal_code=postal_code,
                property_type=property_type,
                surface_m2=surface,
                price_total=price_total,
                price_m2=price_total / surface,
                first_seen_at=first_seen_at,
                last_seen_at=last_seen_at,
            )
        )
        db.commit()
    finally:
        db.close()


def _seed_one_candidate_pair():
    """A (benedic) disparu il y a 30 j ; B (bienici) apparu 10 j apres A, memes
    city/postal/type, surface identique → 1 paire candidate 'benedic<->bienici'.
    Marges larges pour rester dans la fenetre 180 j et au-dela du gap 7 j quel
    que soit `utcnow()`."""
    now = datetime.utcnow()
    a_last = now - timedelta(days=30)
    _insert("probe-A", "benedic", last_seen_at=a_last,
            first_seen_at=a_last - timedelta(days=5))
    b_first = a_last + timedelta(days=10)
    _insert("probe-B", "bienici", last_seen_at=b_first, first_seen_at=b_first)


def _count_comparables():
    db = SessionLocal()
    try:
        return db.query(Comparable).count()
    finally:
        db.close()


def test_cross_source_probe_requires_admin_token_401(client, monkeypatch):
    monkeypatch.setenv("ADMIN_TOKEN", ADMIN_TOKEN)

    resp_no_token = client.get(ENDPOINT)
    assert resp_no_token.status_code == 401, (
        f"sans token attendu 401, recu {resp_no_token.status_code}"
    )

    resp_bad = client.get(ENDPOINT, headers={"X-Admin-Token": "mauvais-token"})
    assert resp_bad.status_code == 401, (
        f"token errone attendu 401, recu {resp_bad.status_code}"
    )


def test_cross_source_probe_admin_token_not_configured_503(client, monkeypatch):
    monkeypatch.delenv("ADMIN_TOKEN", raising=False)

    resp = client.get(ENDPOINT, headers={"X-Admin-Token": "peu-importe"})
    assert resp.status_code == 503, (
        f"ADMIN_TOKEN non configure attendu 503, recu {resp.status_code}"
    )


def test_cross_source_probe_counts_one_candidate_pair(client, monkeypatch):
    monkeypatch.setenv("ADMIN_TOKEN", ADMIN_TOKEN)
    _seed_one_candidate_pair()

    resp = client.get(ENDPOINT, headers={"X-Admin-Token": ADMIN_TOKEN})
    assert resp.status_code == 200, resp.text
    body = resp.json()

    assert body["total_comparables"] == 2, body
    assert body["total_pairs"] == 1, body
    assert body["pairs_by_source_couple"] == {"benedic<->bienici": 1}, body
    assert body["by_source"] == {"benedic": 1, "bienici": 1}, body
    # Les deux membres sont impliques dans la (seule) paire.
    assert body["involved_pct"] == 100.0, body


def test_cross_source_probe_is_read_only(client, monkeypatch):
    monkeypatch.setenv("ADMIN_TOKEN", ADMIN_TOKEN)
    _seed_one_candidate_pair()

    before = _count_comparables()
    resp = client.get(ENDPOINT, headers={"X-Admin-Token": ADMIN_TOKEN})
    assert resp.status_code == 200, resp.text
    after = _count_comparables()

    assert before == after == 2, (
        f"read-only viole : {before} avant, {after} apres"
    )


def test_cross_source_probe_exposes_only_aggregate_counters(client, monkeypatch):
    # Conformite CONTEXT §11.3 : aucune cle re-publiable par-annonce, que des
    # compteurs agreges + libelles de source.
    monkeypatch.setenv("ADMIN_TOKEN", ADMIN_TOKEN)
    _seed_one_candidate_pair()

    resp = client.get(ENDPOINT, headers={"X-Admin-Token": ADMIN_TOKEN})
    assert resp.status_code == 200, resp.text
    body = resp.json()

    assert set(body.keys()) == EXPECTED_KEYS, body.keys()

    forbidden = {
        "address", "url", "urls", "photo_urls", "text", "raw_text",
        "price", "price_total", "price_m2", "id", "listing_id", "ids",
        "surface_m2", "reference", "customer_id", "lineage_id",
    }
    assert forbidden.isdisjoint(body.keys()), body.keys()

    # Aucun id d'annonce temoin ne fuite dans le corps serialise.
    import json
    serialized = json.dumps(body)
    assert "probe-A" not in serialized and "probe-B" not in serialized, serialized

    # Les couples de sources sont des libelles "a<->b", pas des ids.
    for couple in body["pairs_by_source_couple"]:
        assert "<->" in couple, couple

"""Chantier cross-agence — INCREMENT 1 — tests-first (phase A).

Contrat : docs/specs/cross-agence-INCREMENT1-SPEC.md §7 (AC1 a AC22).

ROUGE LEGITIME attendu tant que le code n'existe pas. Les echecs doivent porter
sur l'ABSENCE de la brique :
- colonnes `first_seen_at`/`last_seen_at` absentes de `comparables` (AC1) ;
- table `listing_price_snapshots` / modele `ListingPriceSnapshot` absents (AC2) ;
- `save_comparables` qui ecrase encore via `db.merge` (AC4/AC5) et n'ecrit aucun
  snapshot (AC3/AC7/AC8/AC9) ;
- endpoint `GET /admin/comparables/{id}/history` inexistant -> 404 de route au
  lieu du 401/200/404 attendus (AC11-AC14) ;
- maintenance sans la regle de retention (AC15-AC18).
PAS sur des erreurs de syntaxe / collecte.

Garde-fous (lecons 9.7 / 9.9 / 9.10) :
- isolation : la table `listing_price_snapshots` ET `comparables` sont videes
  AVANT chaque test par la fixture AUTOUSE `_reset_snapshots_table` de
  conftest.py (AC22), jamais en fixture locale ;
- pas de faux-vert : la logique de capture (first_seen immuable, snapshot
  conditionnel) est exercee en appelant `save_comparables` DIRECTEMENT sur la
  base jetable reelle puis en inspectant la DB via `SessionLocal` (lecon 9.10),
  jamais via un mock de `db.merge` ;
- bornes aux VALEURS EXACTES : AC9 (prix egal vs +1 euro) et AC15/AC16
  (730j vs 731j) testent les DEUX cotes de la borne ;
- AC14 anti-fuite : on asserte que l'ensemble des cles de la reponse est INCLUS
  dans le set autorise ET qu'aucune cle re-publiable n'apparait, sur la VRAIE
  reponse de l'endpoint.
"""

from datetime import datetime, timedelta

import pytest
from sqlalchemy import inspect, text


# Set autorise des cles de la reponse admin /history (SPEC §4.2 / AC14).
HISTORY_ALLOWED_KEYS = {
    "listing_id",
    "source",
    "first_seen_at",
    "last_seen_at",
    "weeks_on_market",
    "price_first",
    "price_last",
    "price_change_pct",
    "snapshots",
}
SNAPSHOT_ALLOWED_KEYS = {"price_total", "price_m2", "observed_at"}

# Cles de contenu re-publiable explicitement INTERDITES (CONTEXT §11.3 amende).
FORBIDDEN_KEYS = {
    "raw_text", "text", "title", "description", "address", "url", "photos",
    "photo", "image", "images", "city", "district", "postal_code",
}

ADMIN_TOKEN = "test-admin-token-cross-agence"


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------
def _make_ad(listing_id="cross-agence-1", price_total=250000.0, surface=80.0,
             city="Metz", source="bienici", postal_code="57000", **extra):
    ad = {
        "id": listing_id,
        "source": source,
        "city": city,
        "district": None,
        "postal_code": postal_code,
        "property_type": "appartement",
        "surface_m2": surface,
        "price_total": price_total,
    }
    ad.update(extra)
    return ad


@pytest.fixture()
def admin_token(monkeypatch):
    monkeypatch.setenv("ADMIN_TOKEN", ADMIN_TOKEN)
    return ADMIN_TOKEN


@pytest.fixture()
def frozen_now(monkeypatch):
    """Permet de controler `datetime.utcnow()` lu par `ingestion.save` afin de
    distinguer deux runs successifs a des instants STRICTEMENT distincts (AC5/AC6)
    sans dependre de la granularite de l'horloge. Le test fixe une valeur, appelle
    `save_comparables`, change la valeur, rappelle -> first/last comparables.
    """
    import ingestion.save as save_mod

    holder = {"now": datetime(2026, 1, 6, 4, 0, 0)}

    class _FrozenDateTime:
        @staticmethod
        def utcnow():
            return holder["now"]

    monkeypatch.setattr(save_mod, "datetime", _FrozenDateTime)
    return holder


def _row(listing_id):
    """Relit une ligne comparable par id via une session fraiche (pas de cache
    d'identite ORM d'un autre run)."""
    from db.session import SessionLocal
    from db.models import Comparable

    db = SessionLocal()
    try:
        return db.get(Comparable, listing_id)
    finally:
        db.close()


def _require_snapshots_table():
    """Echoue en AssertionError lisible si la table n'existe pas encore (phase
    tests-first) au lieu de laisser remonter une OperationalError brute. On
    ASSERTE l'existence (pas de tolerance silencieuse) : aucun test ne peut
    devenir vert tant que la table absente -> pas de faux-vert."""
    from db.session import engine
    from sqlalchemy import inspect as _inspect

    assert _inspect(engine).has_table("listing_price_snapshots"), (
        "table listing_price_snapshots absente : la brique de snapshots n'existe "
        "pas encore (rouge legitime tests-first)"
    )


def _snapshot_count(listing_id):
    from db.session import engine

    _require_snapshots_table()
    with engine.begin() as conn:
        return conn.execute(
            text("SELECT COUNT(*) FROM listing_price_snapshots WHERE listing_id = :lid"),
            {"lid": listing_id},
        ).scalar()


def _snapshots(listing_id):
    from db.session import engine

    _require_snapshots_table()
    with engine.begin() as conn:
        rows = conn.execute(
            text(
                "SELECT price_total, price_m2, observed_at FROM listing_price_snapshots "
                "WHERE listing_id = :lid ORDER BY observed_at ASC"
            ),
            {"lid": listing_id},
        ).fetchall()
    return rows


def _insert_comparable_direct(listing_id, last_seen_at, price_total=250000.0,
                              surface=80.0, source="bienici", first_seen_at=None):
    """Insere un comparable DIRECTEMENT en DB avec un last_seen_at controle, pour
    tester les bornes de retention a des dates precises (SPEC procedure §6)."""
    from db.session import engine

    first = first_seen_at if first_seen_at is not None else last_seen_at
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO comparables "
                "(id, source, city, property_type, surface_m2, price_total, price_m2, "
                " first_seen_at, last_seen_at, collected_at) "
                "VALUES (:id, :source, 'Metz', 'appartement', :surface, :price, :pm2, "
                " :first, :last, :last)"
            ),
            {
                "id": listing_id, "source": source, "surface": surface,
                "price": price_total, "pm2": price_total / surface,
                "first": first, "last": last_seen_at,
            },
        )


def _insert_snapshot_direct(listing_id, price_total=250000.0, surface=80.0,
                            observed_at=None):
    from db.session import engine

    obs = observed_at if observed_at is not None else datetime.utcnow()
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO listing_price_snapshots "
                "(listing_id, price_total, price_m2, observed_at) "
                "VALUES (:lid, :price, :pm2, :obs)"
            ),
            {"lid": listing_id, "price": price_total,
             "pm2": price_total / surface, "obs": obs},
        )


# ===========================================================================
# Schema & migration — AC1, AC2, AC3
# ===========================================================================
def test_comparables_has_seen_columns():
    # AC1 : apres init_db(), table_info(comparables) contient first_seen_at ET
    # last_seen_at.
    from db.session import init_db, engine

    init_db()
    with engine.begin() as conn:
        cols = {row[1] for row in conn.execute(text("PRAGMA table_info(comparables)"))}
    assert "first_seen_at" in cols, "colonne first_seen_at absente de comparables (AC1)"
    assert "last_seen_at" in cols, "colonne last_seen_at absente de comparables (AC1)"


def test_snapshots_table_and_index_exist():
    # AC2 : table listing_price_snapshots avec colonnes attendues + index sur
    # listing_id.
    from db.session import init_db, engine

    init_db()
    insp = inspect(engine)
    assert insp.has_table("listing_price_snapshots"), (
        "table listing_price_snapshots absente (AC2)"
    )
    cols = {c["name"] for c in insp.get_columns("listing_price_snapshots")}
    for expected in ("id", "listing_id", "price_total", "price_m2", "observed_at"):
        assert expected in cols, f"colonne {expected} absente de listing_price_snapshots (AC2)"

    indexed_cols = set()
    for idx in insp.get_indexes("listing_price_snapshots"):
        indexed_cols.update(idx.get("column_names") or [])
    # Un index PK/unique sur listing_id ou une PrimaryKey ne suffit pas : on veut
    # un index couvrant listing_id (lecture serie + purge).
    assert "listing_id" in indexed_cols, (
        "aucun index sur listing_id pour listing_price_snapshots (AC2)"
    )


def test_init_db_idempotent_twice():
    # AC3 : deux init_db() de suite ne levent pas et ne dupliquent aucune colonne.
    from db.session import init_db, engine

    init_db()
    with engine.begin() as conn:
        cols_first = [row[1] for row in conn.execute(text("PRAGMA table_info(comparables)"))]
    # 2e appel : ne doit pas lever.
    init_db()
    with engine.begin() as conn:
        cols_second = [row[1] for row in conn.execute(text("PRAGMA table_info(comparables)"))]

    assert cols_first == cols_second, "table_info diverge apres un 2e init_db (AC3)"
    # Pas de doublon de colonne.
    assert len(cols_second) == len(set(cols_second)), "colonne dupliquee apres init_db x2 (AC3)"


# ===========================================================================
# Capture first_seen / last_seen — AC4, AC5, AC6
# ===========================================================================
def test_first_observation_sets_first_and_last_and_initial_snapshot(frozen_now):
    # AC4 : 1re observation -> first_seen_at == last_seen_at (= instant run) et
    # exactement 1 snapshot.
    from ingestion.save import save_comparables

    frozen_now["now"] = datetime(2026, 1, 6, 4, 0, 0)
    save_comparables([_make_ad(listing_id="ac4-id", price_total=250000.0)])

    row = _row("ac4-id")
    assert row is not None, "comparable non ecrit a la 1re observation (AC4)"
    assert row.first_seen_at == row.last_seen_at, (
        "first_seen_at doit egaler last_seen_at a la 1re observation (AC4)"
    )
    assert row.first_seen_at == datetime(2026, 1, 6, 4, 0, 0), (
        "first_seen_at != instant du run (AC4)"
    )
    assert _snapshot_count("ac4-id") == 1, "snapshot initial non ecrit (AC4)"


def test_first_seen_never_overwritten_on_reobservation(frozen_now):
    # AC5 : deux runs successifs du meme id ; first_seen_at reste celui du 1er run
    # meme si le 2e run a un now strictement posterieur.
    from ingestion.save import save_comparables

    t1 = datetime(2026, 1, 6, 4, 0, 0)
    t2 = datetime(2026, 3, 10, 4, 0, 0)

    frozen_now["now"] = t1
    save_comparables([_make_ad(listing_id="ac5-id", price_total=250000.0)])

    frozen_now["now"] = t2
    save_comparables([_make_ad(listing_id="ac5-id", price_total=250000.0)])

    row = _row("ac5-id")
    assert row.first_seen_at == t1, (
        "first_seen_at a ete reecrit a la re-observation : il doit rester l'instant "
        "du 1er run (AC5). Probable db.merge non remplace par une lecture explicite."
    )


def test_last_seen_refreshed_on_reobservation(frozen_now):
    # AC6 : last_seen_at rafraichi au 2e run et > first_seen_at.
    from ingestion.save import save_comparables

    t1 = datetime(2026, 1, 6, 4, 0, 0)
    t2 = datetime(2026, 3, 10, 4, 0, 0)

    frozen_now["now"] = t1
    save_comparables([_make_ad(listing_id="ac6-id", price_total=250000.0)])

    frozen_now["now"] = t2
    save_comparables([_make_ad(listing_id="ac6-id", price_total=250000.0)])

    row = _row("ac6-id")
    assert row.last_seen_at == t2, "last_seen_at non rafraichi au 2e run (AC6)"
    assert row.last_seen_at > row.first_seen_at, (
        "last_seen_at doit etre strictement posterieur a first_seen_at (AC6)"
    )


# ===========================================================================
# Snapshots conditionnels — AC7, AC8, AC9
# ===========================================================================
def test_no_snapshot_when_price_unchanged(frozen_now):
    # AC7 : prix INCHANGE entre deux runs -> aucun nouveau snapshot (reste 1).
    from ingestion.save import save_comparables

    frozen_now["now"] = datetime(2026, 1, 6, 4, 0, 0)
    save_comparables([_make_ad(listing_id="ac7-id", price_total=250000.0)])

    frozen_now["now"] = datetime(2026, 3, 10, 4, 0, 0)
    save_comparables([_make_ad(listing_id="ac7-id", price_total=250000.0)])

    assert _snapshot_count("ac7-id") == 1, (
        "un snapshot a ete ecrit a prix identique : le snapshot doit etre "
        "conditionnel au changement de price_total (AC7)"
    )


def test_new_snapshot_only_when_price_changes(frozen_now):
    # AC8 : prix CHANGE -> +1 snapshot (passe a 2) ; observed_at du 2e = instant
    # du 2e run ; price_total = nouveau prix.
    from ingestion.save import save_comparables

    t2 = datetime(2026, 3, 10, 4, 0, 0)
    frozen_now["now"] = datetime(2026, 1, 6, 4, 0, 0)
    save_comparables([_make_ad(listing_id="ac8-id", price_total=250000.0)])

    frozen_now["now"] = t2
    save_comparables([_make_ad(listing_id="ac8-id", price_total=239000.0)])

    assert _snapshot_count("ac8-id") == 2, "nouveau snapshot non ecrit au changement de prix (AC8)"
    snaps = _snapshots("ac8-id")
    last = snaps[-1]
    assert last[0] == 239000.0, "price_total du 2e snapshot != nouveau prix (AC8)"
    # observed_at peut etre une str (SQLite) ou un datetime selon le typage.
    assert str(t2) in str(last[2]) or last[2] == t2, (
        "observed_at du 2e snapshot != instant du 2e run (AC8)"
    )


def test_price_change_boundary_exact_equality(frozen_now):
    # AC9 (cote egalite) : price_total strictement egal -> pas de snapshot.
    from ingestion.save import save_comparables

    frozen_now["now"] = datetime(2026, 1, 6, 4, 0, 0)
    save_comparables([_make_ad(listing_id="ac9-eq", price_total=250000.0)])

    frozen_now["now"] = datetime(2026, 2, 6, 4, 0, 0)
    save_comparables([_make_ad(listing_id="ac9-eq", price_total=250000.0)])

    assert _snapshot_count("ac9-eq") == 1, "borne egalite : aucun snapshot attendu (AC9)"


def test_price_change_boundary_one_euro_writes_snapshot(frozen_now):
    # AC9 (cote +1 euro) : une difference d'1 euro ecrit un snapshot.
    from ingestion.save import save_comparables

    frozen_now["now"] = datetime(2026, 1, 6, 4, 0, 0)
    save_comparables([_make_ad(listing_id="ac9-1e", price_total=250000.0)])

    frozen_now["now"] = datetime(2026, 2, 6, 4, 0, 0)
    save_comparables([_make_ad(listing_id="ac9-1e", price_total=250001.0)])

    assert _snapshot_count("ac9-1e") == 2, "borne +1 euro : un snapshot attendu (AC9)"


# ===========================================================================
# Garde-fous preserves — AC10
# ===========================================================================
def test_rejected_listing_out_of_band_creates_neither_comparable_nor_snapshot(frozen_now):
    # AC10 (bande prix/m2) : price_m2 hors [800, 12000] -> ni comparable ni snapshot.
    from ingestion.save import save_comparables

    frozen_now["now"] = datetime(2026, 1, 6, 4, 0, 0)
    # 20000 / 1 = 20000 euros/m2 > 12000 -> rejete.
    save_comparables([_make_ad(listing_id="ac10-band", price_total=20000.0, surface=1.0)])

    assert _row("ac10-band") is None, "comparable hors bande prix/m2 ne doit pas etre cree (AC10)"
    assert _snapshot_count("ac10-band") == 0, "aucun snapshot pour annonce rejetee (AC10)"


def test_rejected_listing_out_of_department_creates_neither_comparable_nor_snapshot(frozen_now):
    # AC10 (perimetre) : code postal hors dept 57 -> ni comparable ni snapshot.
    from ingestion.save import save_comparables

    frozen_now["now"] = datetime(2026, 1, 6, 4, 0, 0)
    save_comparables([
        _make_ad(listing_id="ac10-dept", price_total=250000.0, postal_code="54000")
    ])

    assert _row("ac10-dept") is None, "comparable hors dept 57 ne doit pas etre cree (AC10)"
    assert _snapshot_count("ac10-dept") == 0, "aucun snapshot pour annonce hors perimetre (AC10)"


# ===========================================================================
# Endpoint admin de lecture — AC11, AC12, AC13, AC14
# ===========================================================================
def test_history_requires_admin_token(client, admin_token):
    # AC11 : sans X-Admin-Token (ou token errone) -> 401 (pattern maison, PAS 403).
    resp_no_token = client.get("/admin/comparables/whatever/history")
    assert resp_no_token.status_code == 401, (
        f"sans token attendu 401, recu {resp_no_token.status_code} (AC11)"
    )

    resp_bad = client.get(
        "/admin/comparables/whatever/history",
        headers={"X-Admin-Token": "mauvais-token"},
    )
    assert resp_bad.status_code == 401, (
        f"token errone attendu 401, recu {resp_bad.status_code} (AC11)"
    )


def test_history_unknown_id_returns_404(client, admin_token, frozen_now):
    # AC12 : id inconnu -> 404. Garde anti-faux-vert (lecon 9.10) : une ROUTE
    # absente renverrait elle aussi 404, ce qui rendrait ce test vert sans
    # endpoint. On prouve d'abord que la route existe et SAIT renvoyer 200 pour
    # un id CONNU, PUIS qu'un id inconnu donne 404 -> distingue 404 de route
    # absente de 404 metier.
    from ingestion.save import save_comparables

    frozen_now["now"] = datetime(2026, 1, 6, 4, 0, 0)
    save_comparables([_make_ad(listing_id="ac12-known", price_total=250000.0)])

    known = client.get(
        "/admin/comparables/ac12-known/history",
        headers={"X-Admin-Token": admin_token},
    )
    assert known.status_code == 200, (
        f"un id CONNU doit renvoyer 200 (preuve que la route existe), recu "
        f"{known.status_code} (AC12)"
    )

    resp = client.get(
        "/admin/comparables/id-jamais-vu-xyz/history",
        headers={"X-Admin-Token": admin_token},
    )
    assert resp.status_code == 404, (
        f"id inconnu attendu 404, recu {resp.status_code} (AC12)"
    )


def test_history_returns_factual_metadata(client, admin_token, frozen_now):
    # AC13 : id connu avec 2 snapshots de prix differents -> 200 + metadonnees
    # factuelles, snapshots ordonnes, price_change_pct au bon signe (baisse < 0).
    from ingestion.save import save_comparables

    frozen_now["now"] = datetime(2026, 1, 6, 4, 0, 0)
    save_comparables([_make_ad(listing_id="ac13-id", price_total=250000.0, surface=80.0)])
    frozen_now["now"] = datetime(2026, 3, 10, 4, 0, 0)
    save_comparables([_make_ad(listing_id="ac13-id", price_total=239000.0, surface=80.0)])

    resp = client.get(
        "/admin/comparables/ac13-id/history",
        headers={"X-Admin-Token": admin_token},
    )
    assert resp.status_code == 200, f"id connu attendu 200, recu {resp.status_code} (AC13)"
    body = resp.json()

    assert body["listing_id"] == "ac13-id"
    assert body["source"] == "bienici"
    assert isinstance(body["weeks_on_market"], int), "weeks_on_market doit etre un entier (AC13)"
    assert body["price_first"] == 250000
    assert body["price_last"] == 239000
    assert body["price_change_pct"] is not None, "price_change_pct attendu avec 2 snapshots (AC13)"
    assert body["price_change_pct"] < 0, "baisse de prix -> price_change_pct negatif (AC13)"

    snaps = body["snapshots"]
    assert len(snaps) == 2, "2 snapshots attendus (AC13)"
    # Ordre croissant par observed_at.
    assert snaps[0]["observed_at"] <= snaps[1]["observed_at"], (
        "snapshots non ordonnes par observed_at croissant (AC13)"
    )
    assert snaps[0]["price_total"] == 250000
    assert snaps[1]["price_total"] == 239000


def test_history_exposes_no_republishable_content(client, admin_token, frozen_now):
    # AC14 : aucune cle re-publiable. On asserte l'INCLUSION dans le set autorise
    # ET l'absence des cles interdites, sur la VRAIE reponse de l'endpoint
    # (lecon 9.10 : prouver l'absence de fuite a la couche qui construit le dict).
    from ingestion.save import save_comparables

    frozen_now["now"] = datetime(2026, 1, 6, 4, 0, 0)
    save_comparables([_make_ad(
        listing_id="ac14-id", price_total=250000.0, surface=80.0,
        city="Metz", source="bienici", district="Sablon",
    )])
    frozen_now["now"] = datetime(2026, 3, 10, 4, 0, 0)
    save_comparables([_make_ad(
        listing_id="ac14-id", price_total=239000.0, surface=80.0,
        city="Metz", source="bienici", district="Sablon",
    )])

    resp = client.get(
        "/admin/comparables/ac14-id/history",
        headers={"X-Admin-Token": admin_token},
    )
    assert resp.status_code == 200
    body = resp.json()

    keys = set(body.keys())
    assert keys <= HISTORY_ALLOWED_KEYS, (
        f"la reponse /history expose des cles hors set autorise : {keys - HISTORY_ALLOWED_KEYS} (AC14)"
    )
    leaked = keys & FORBIDDEN_KEYS
    assert not leaked, f"cle(s) re-publiable(s) exposee(s) au niveau racine : {leaked} (AC14)"

    for snap in body["snapshots"]:
        snap_keys = set(snap.keys())
        assert snap_keys <= SNAPSHOT_ALLOWED_KEYS, (
            f"un snapshot expose des cles hors set autorise : {snap_keys - SNAPSHOT_ALLOWED_KEYS} (AC14)"
        )
        assert not (snap_keys & FORBIDDEN_KEYS), (
            f"un snapshot expose une cle re-publiable : {snap_keys & FORBIDDEN_KEYS} (AC14)"
        )


# ===========================================================================
# Retention / purge (bornes exactes) — AC15, AC16, AC17, AC18
# ===========================================================================
def test_retention_boundary_exactly_730_days_kept(client, admin_token):
    # AC15 : last_seen_at == now - 730j (exactement 24 mois) -> CONSERVE
    # (comparaison stricte last_seen_at < seuil) ; ses snapshots subsistent.
    from db.session import init_db

    init_db()
    now = datetime.utcnow()
    last_seen = now - timedelta(days=730)
    _insert_comparable_direct("ac15-keep", last_seen_at=last_seen)
    _insert_snapshot_direct("ac15-keep", observed_at=last_seen)

    resp = client.post(
        "/admin/comparables/maintenance",
        json={"dry_run": False},
        headers={"X-Admin-Token": admin_token},
    )
    assert resp.status_code == 200, f"maintenance attendu 200, recu {resp.status_code}"

    assert _row("ac15-keep") is not None, (
        "comparable a EXACTEMENT 730j doit etre CONSERVE (borne incluse, AC15)"
    )
    assert _snapshot_count("ac15-keep") == 1, "snapshots du comparable conserve supprimes a tort (AC15)"


def test_retention_boundary_731_days_purged_with_snapshots(client, admin_token):
    # AC16 : last_seen_at == now - 731j -> PURGE + snapshots supprimes ;
    # compteurs purged_retention et purged_snapshots refletent les suppressions.
    from db.session import init_db

    init_db()
    now = datetime.utcnow()
    last_seen = now - timedelta(days=731)
    _insert_comparable_direct("ac16-purge", last_seen_at=last_seen)
    _insert_snapshot_direct("ac16-purge", price_total=250000.0, observed_at=last_seen)
    _insert_snapshot_direct("ac16-purge", price_total=239000.0, observed_at=last_seen)

    resp = client.post(
        "/admin/comparables/maintenance",
        json={"dry_run": False},
        headers={"X-Admin-Token": admin_token},
    )
    assert resp.status_code == 200
    body = resp.json()

    assert _row("ac16-purge") is None, "comparable a 731j doit etre PURGE (AC16)"
    assert _snapshot_count("ac16-purge") == 0, "snapshots du comparable purge non supprimes (AC16)"
    assert body.get("purged_retention", 0) >= 1, (
        "compteur purged_retention absent ou ne compte pas la purge anciennete (AC16)"
    )
    assert body.get("purged_snapshots", 0) >= 2, (
        "compteur purged_snapshots absent ou ne compte pas les 2 snapshots supprimes (AC16)"
    )


def test_retention_dry_run_counts_without_deleting(client, admin_token):
    # AC17 : dry_run=true (defaut) ne supprime rien (comparable + snapshots
    # intacts), meme si purged_retention est compte.
    from db.session import init_db

    init_db()
    now = datetime.utcnow()
    last_seen = now - timedelta(days=731)
    _insert_comparable_direct("ac17-dry", last_seen_at=last_seen)
    _insert_snapshot_direct("ac17-dry", observed_at=last_seen)

    # dry_run par defaut (true) : ne pas passer dry_run.
    resp = client.post(
        "/admin/comparables/maintenance",
        json={},
        headers={"X-Admin-Token": admin_token},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["dry_run"] is True, "dry_run doit etre true par defaut (AC17)"

    assert _row("ac17-dry") is not None, "dry_run ne doit RIEN supprimer (comparable, AC17)"
    assert _snapshot_count("ac17-dry") == 1, "dry_run ne doit RIEN supprimer (snapshots, AC17)"


def test_retention_does_not_purge_null_last_seen(client, admin_token):
    # AC18 : une ligne last_seen_at IS NULL n'est PAS purgee par la regle de
    # retention (on ne supprime que sur un last_seen connu et expire).
    from db.session import init_db, engine

    init_db()
    # Insertion d'un comparable valide (prix/m2 in band, dept 57) avec
    # last_seen_at NULL et first_seen_at NULL.
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO comparables "
                "(id, source, city, postal_code, property_type, surface_m2, price_total, "
                " price_m2, first_seen_at, last_seen_at, collected_at) "
                "VALUES ('ac18-null', 'bienici', 'Metz', '57000', 'appartement', 80, "
                " 250000, 3125, NULL, NULL, NULL)"
            )
        )

    resp = client.post(
        "/admin/comparables/maintenance",
        json={"dry_run": False},
        headers={"X-Admin-Token": admin_token},
    )
    assert resp.status_code == 200

    assert _row("ac18-null") is not None, (
        "une ligne last_seen_at NULL ne doit PAS etre purgee par la retention (AC18)"
    )


# ===========================================================================
# Non-regression & contrat — AC19, AC20
# ===========================================================================
@pytest.fixture()
def no_fallback(monkeypatch):
    """`analyze_semantic` nominal deterministe (pas d'appel OpenAI reseau), pour
    exercer le contrat /analyze sans dependance externe (cf. test_events.py)."""
    import app.analysis as analysis_mod

    def _fake_semantic(raw_text):
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
                "city": None, "district": None, "property_type": None,
                "surface_m2": None, "price_total": None, "dpe": None,
                "construction_year": None, "floor": None, "has_elevator": None,
                "has_terrace": None, "has_balcony": None, "has_cellar": None,
                "parking": None, "bedrooms": None, "condo_fees": None,
            },
        }

    monkeypatch.setattr(analysis_mod, "analyze_semantic", _fake_semantic)


def test_analyze_contract_unchanged(client, no_fallback):
    # AC19 : /analyze ne gagne aucune cle. Le jeu de cles reste inclus dans le
    # contrat documente.
    resp = client.post(
        "/analyze",
        json={"raw_text": "Appartement T3 a Metz, 70 m2, increment 1 cross-agence."},
        headers={"Fly-Client-IP": "203.0.113.99"},
    )
    assert resp.status_code == 200, f"/analyze attendu 200, recu {resp.status_code} (AC19)"
    keys = set(resp.json().keys())
    allowed = {
        "global_score", "verdict", "confidence", "pillars", "actions",
        "local_context",
    }
    assert keys <= allowed, (
        f"le contrat /analyze ne doit gagner AUCUNE cle : {keys - allowed} (AC19)"
    )


def test_admin_import_still_works_and_now_records_history(client, admin_token):
    # AC20 : POST /admin/comparables conserve son contrat {received, saved,
    # total_in_db} ET capture l'historique : l'id importe est consultable via
    # /history (200, 1 snapshot).
    payload = {
        "items": [{
            "id": "ac20-id",
            "source": "bienici",
            "city": "Metz",
            "property_type": "appartement",
            "surface_m2": 80,
            "price_total": 250000,
            "postal_code": "57000",
        }]
    }
    resp = client.post(
        "/admin/comparables",
        json=payload,
        headers={"X-Admin-Token": admin_token},
    )
    assert resp.status_code == 200, f"/admin/comparables attendu 200, recu {resp.status_code} (AC20)"
    body = resp.json()
    assert set(body.keys()) == {"received", "saved", "total_in_db"}, (
        f"contrat /admin/comparables modifie : {set(body.keys())} (AC20)"
    )
    assert body["saved"] == 1

    hist = client.get(
        "/admin/comparables/ac20-id/history",
        headers={"X-Admin-Token": admin_token},
    )
    assert hist.status_code == 200, "l'id importe doit etre consultable via /history (AC20)"
    assert len(hist.json()["snapshots"]) == 1, "1 snapshot attendu apres import (AC20)"


# ===========================================================================
# Isolation — AC22
# ===========================================================================
def test_conftest_resets_snapshots_table():
    # AC22 (statique) : la fixture autouse de reset de listing_price_snapshots est
    # bien declaree dans conftest.py (jamais en fixture locale, lecon 9.9).
    import inspect as _inspect
    import tests.conftest as conftest_mod

    assert hasattr(conftest_mod, "_reset_snapshots_table"), (
        "fixture _reset_snapshots_table absente de conftest.py (AC22)"
    )
    src = _inspect.getsource(conftest_mod)
    assert "listing_price_snapshots" in src, (
        "le reset autouse ne vide pas listing_price_snapshots (AC22)"
    )
    # La fixture doit etre autouse (sinon elle ne s'applique pas a tous les
    # tests). Le marqueur pytest porte l'attribut `autouse` ; selon la version il
    # est expose via `_fixture_function_marker` (objet FixtureFunctionMarker) ou
    # `_pytestfixturefunction`.
    fn = conftest_mod._reset_snapshots_table
    marker = getattr(fn, "_fixture_function_marker", None) or getattr(
        fn, "_pytestfixturefunction", None
    )
    assert marker is not None, "_reset_snapshots_table n'est pas une fixture pytest (AC22)"
    assert getattr(marker, "autouse", False) is True, (
        "la fixture _reset_snapshots_table doit etre autouse (AC22)"
    )


def test_conftest_reimport_under_second_name_keeps_db_writable():
    # AC22 / regression phase B (cause racine du "readonly database" de phase A) :
    # importer conftest sous un SECOND nom de module (`tests.conftest`, alors que
    # pytest l'a charge comme `conftest`) re-execute son top-level. Sans la
    # sentinelle MVP_TEST_DB_BOOTSTRAPPED, ce double-import re-supprimait le
    # fichier SQLite SOUS le moteur SQLAlchemy connecte -> toutes les ecritures
    # suivantes echouaient en OperationalError "readonly database" (faux rouge
    # dependant de l'ordre). Ce test declenche le double-import PUIS prouve que
    # la base reste ecrivable.
    import tests.conftest as conftest_mod  # noqa: F401  (declencheur volontaire)
    from db.session import engine

    # La sentinelle doit etre posee et pointer la base jetable de la session.
    import os as _os
    assert _os.environ.get("MVP_TEST_DB_BOOTSTRAPPED") == _os.environ["DATABASE_PATH"], (
        "sentinelle MVP_TEST_DB_BOOTSTRAPPED absente ou incoherente : le "
        "double-import de conftest redeviendrait destructif (lecon phase A)"
    )

    # Ecriture reelle apres le double-import : ne doit PAS lever readonly.
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO listing_price_snapshots "
                "(listing_id, price_total, price_m2, observed_at) "
                "VALUES ('reimport-probe', 1000.0, 1000.0, :obs)"
            ),
            {"obs": datetime.utcnow()},
        )
        conn.execute(
            text("DELETE FROM listing_price_snapshots WHERE listing_id = 'reimport-probe'")
        )


def test_snapshots_table_starts_empty_between_runs(frozen_now):
    # AC22 (dynamique) : deux runs successifs de save_comparables partent d'une
    # table vierge -> pas d'accumulation inter-tests. Si l'isolation conftest ne
    # marchait pas, un comparable/snapshot d'un test precedent fausserait la
    # 1re observation ici (first_seen relu d'un run anterieur, snapshot deja la).
    from ingestion.save import save_comparables

    # En entree de test la table doit etre vierge pour cet id.
    assert _snapshot_count("ac22-iso") == 0, (
        "la table listing_price_snapshots n'est pas vierge en entree de test (AC22)"
    )
    assert _row("ac22-iso") is None, "comparables non vide en entree de test (AC22)"

    frozen_now["now"] = datetime(2026, 1, 6, 4, 0, 0)
    save_comparables([_make_ad(listing_id="ac22-iso", price_total=250000.0)])
    assert _snapshot_count("ac22-iso") == 1, (
        "1re observation isolee : exactement 1 snapshot (AC22)"
    )


# ===========================================================================
# Durcissements phase B (challenge) — adversite, bords fins, anti-fuite
# ===========================================================================
def test_rejected_reobservation_leaves_existing_history_untouched(frozen_now):
    # Phase B / AC5+AC10 combine : une RE-observation d'un id existant dont le
    # prix est desormais hors bande [800-12000] doit etre rejetee AVANT toute
    # ecriture -> la ligne existante garde son historique INTACT : last_seen_at
    # NON rafraichi, first_seen_at inchange, prix inchange, AUCUN snapshot.
    from ingestion.save import save_comparables

    t1 = datetime(2026, 1, 6, 4, 0, 0)
    frozen_now["now"] = t1
    save_comparables([_make_ad(listing_id="advers-id", price_total=250000.0, surface=80.0)])
    assert _snapshot_count("advers-id") == 1

    # 2e run : meme id, prix delirant (20000 euros/m2 > 12000 -> rejet bande).
    frozen_now["now"] = datetime(2026, 3, 10, 4, 0, 0)
    save_comparables([_make_ad(listing_id="advers-id", price_total=1600000.0, surface=80.0)])

    row = _row("advers-id")
    assert row.last_seen_at == t1, (
        "annonce rejetee = AUCUNE ecriture : last_seen_at ne doit PAS etre "
        "rafraichi par une re-observation hors bande (phase B)"
    )
    assert row.first_seen_at == t1, "first_seen_at altere par une re-observation rejetee (phase B)"
    assert row.price_total == 250000.0, (
        "le prix existant a ete ecrase par une re-observation hors bande (phase B)"
    )
    assert _snapshot_count("advers-id") == 1, (
        "un snapshot a ete ecrit pour une re-observation rejetee (phase B)"
    )


def test_history_legacy_row_returns_200_with_nulls_and_empty_snapshots(client, admin_token):
    # Phase B / SPEC §4.3 : ligne prod heritee (first_seen/last_seen NULL, aucun
    # snapshot) -> 200, pas 500 ; dates null, weeks_on_market null, price_* null,
    # price_change_pct null, snapshots [].
    from db.session import init_db, engine

    init_db()
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO comparables "
                "(id, source, city, property_type, surface_m2, price_total, price_m2, "
                " first_seen_at, last_seen_at, collected_at) "
                "VALUES ('legacy-id', 'bienici', 'Metz', 'appartement', 80, 250000, "
                " 3125, NULL, NULL, NULL)"
            )
        )

    resp = client.get(
        "/admin/comparables/legacy-id/history",
        headers={"X-Admin-Token": admin_token},
    )
    assert resp.status_code == 200, (
        f"ligne heritee sans dates ni snapshots : attendu 200, recu {resp.status_code} (phase B)"
    )
    body = resp.json()
    assert body["first_seen_at"] is None
    assert body["last_seen_at"] is None
    assert body["weeks_on_market"] is None, "weeks_on_market doit etre null si dates manquantes"
    assert body["price_first"] is None
    assert body["price_last"] is None
    assert body["price_change_pct"] is None
    assert body["snapshots"] == []
    # Meme une ligne heritee ne doit fuiter aucune cle re-publiable.
    assert set(body.keys()) <= HISTORY_ALLOWED_KEYS


def test_history_id_with_special_characters_in_url(client, admin_token, frozen_now):
    # Phase B : id stable contenant espaces / accents / & a encoder dans l'URL.
    # L'id reel est un sha256 hex, mais l'endpoint ne doit pas 500 sur un id
    # exotique passe encode, et le round-trip doit retrouver la ligne.
    #
    # Limite framework constatee (et figee ici) : Starlette/httpx DOUBLE-decode
    # le path param (`%2525` envoye -> `percent%` recu) ; un id contenant un `%`
    # litteral n'est donc PAS adressable via l'URL. Sans impact produit (ids =
    # sha256 hex), mais l'endpoint doit alors repondre un 404 metier generique,
    # jamais un 500.
    from urllib.parse import quote
    from ingestion.save import save_comparables

    weird_id = "id avec espaces & ç"
    frozen_now["now"] = datetime(2026, 1, 6, 4, 0, 0)
    save_comparables([_make_ad(listing_id=weird_id, price_total=250000.0)])
    assert _row(weird_id) is not None

    resp = client.get(
        f"/admin/comparables/{quote(weird_id, safe='')}/history",
        headers={"X-Admin-Token": admin_token},
    )
    assert resp.status_code == 200, (
        f"id avec caracteres speciaux encode : attendu 200, recu {resp.status_code} (phase B)"
    )
    assert resp.json()["listing_id"] == weird_id

    # Id avec % litteral : inatteignable (double-decode framework) mais doit
    # donner un 404 metier propre et generique, jamais un 500.
    percent_id = "id-percent%25-litteral"
    save_comparables([_make_ad(listing_id=percent_id, price_total=250000.0)])
    resp_pct = client.get(
        f"/admin/comparables/{quote(percent_id, safe='')}/history",
        headers={"X-Admin-Token": admin_token},
    )
    assert resp_pct.status_code == 404, (
        f"id avec % litteral : attendu 404 metier (double-decode framework), "
        f"recu {resp_pct.status_code} (phase B)"
    )
    assert resp_pct.json() == {"detail": "Identifiant inconnu."}


def test_history_error_responses_do_not_echo_input(client, admin_token):
    # Phase B / AC14 etendu aux erreurs : ni le 404 (id inconnu) ni le 401
    # (token errone) ne doivent echo-iser le contenu fourni par l'appelant
    # (anti log/reponse-injection, detail generique).
    probe_id = "id-sonde-jamais-stocke-9f8e7d"
    resp404 = client.get(
        f"/admin/comparables/{probe_id}/history",
        headers={"X-Admin-Token": admin_token},
    )
    assert resp404.status_code == 404
    assert probe_id not in resp404.text, (
        "le detail du 404 ne doit pas echo-iser l'id fourni (phase B / AC14)"
    )

    probe_token = "token-sonde-secret-3c2b1a"
    resp401 = client.get(
        "/admin/comparables/whatever/history",
        headers={"X-Admin-Token": probe_token},
    )
    assert resp401.status_code == 401
    assert probe_token not in resp401.text, (
        "le detail du 401 ne doit pas echo-iser le token fourni (phase B)"
    )


def test_retention_day_granularity_730_days_plus_hours_kept(client, admin_token):
    # Phase B / borne fine AC15-AC16 : l'implementation calcule l'age en jours
    # REVOLUS ((now - last_seen).days, troncature) au lieu du seuil litteral
    # `last_seen < now - 730j` de la spec §5.2. Ecart ASSUME et juge acceptable :
    # - les deux bornes testables de la spec tiennent (730j pile = conserve,
    #   731j = purge) ;
    # - la zone intermediaire (730j + quelques heures) est CONSERVEE, soit une
    #   retention prolongee d'au plus <24h, dans le sens conservateur (jamais de
    #   purge prematuree) et toujours "24 mois" au sens calendaire ;
    # - le litteral etait intestable (latence sub-seconde insert -> now endpoint).
    # Ce test FIGE cette semantique : purge seulement a partir de 731 jours pleins.
    from db.session import init_db

    init_db()
    now = datetime.utcnow()
    last_seen = now - timedelta(days=730, hours=6)
    _insert_comparable_direct("fine-730p6h", last_seen_at=last_seen)
    _insert_snapshot_direct("fine-730p6h", observed_at=last_seen)

    resp = client.post(
        "/admin/comparables/maintenance",
        json={"dry_run": False},
        headers={"X-Admin-Token": admin_token},
    )
    assert resp.status_code == 200
    assert _row("fine-730p6h") is not None, (
        "730j + 6h = 730 jours revolus -> CONSERVE (granularite jour, purge a "
        "partir de 731 jours pleins ; phase B)"
    )
    assert _snapshot_count("fine-730p6h") == 1
    assert resp.json()["purged_retention"] == 0


def test_maintenance_row_purgeable_for_two_reasons_counted_once(client, admin_token):
    # Phase B / interaction des purges : un comparable purgeable pour DEUX
    # raisons (hors bande prix/m2 ET retention expiree) doit etre supprime UNE
    # fois et compte UNE fois au total (pas de double comptage band+retention).
    from db.session import init_db

    init_db()
    now = datetime.utcnow()
    # 2 000 000 / 80 = 25 000 euros/m2 (hors bande) ET last_seen 731j (expire).
    _insert_comparable_direct(
        "double-purge", last_seen_at=now - timedelta(days=731),
        price_total=2000000.0, surface=80.0,
    )

    resp = client.post(
        "/admin/comparables/maintenance",
        json={"dry_run": False},
        headers={"X-Admin-Token": admin_token},
    )
    assert resp.status_code == 200
    body = resp.json()

    assert _row("double-purge") is None, "le comparable doit etre purge (phase B)"
    total_counted = body["purged_band"] + body["purged_retention"]
    assert total_counted == 1, (
        f"un comparable purgeable pour deux raisons doit etre compte UNE fois, "
        f"compte {total_counted} fois (band={body['purged_band']}, "
        f"retention={body['purged_retention']}) (phase B)"
    )


def test_maintenance_dry_run_retention_counters_without_mutation(client, admin_token):
    # Phase B / AC17 durci : en dry_run, les compteurs retention COMPTENT
    # (purged_retention/purged_snapshots > 0) mais rien n'est mute, et un second
    # appel dry_run renvoie les MEMES compteurs (pas d'effet de bord cache).
    from db.session import init_db

    init_db()
    now = datetime.utcnow()
    _insert_comparable_direct("dry-cnt", last_seen_at=now - timedelta(days=731))
    _insert_snapshot_direct("dry-cnt", observed_at=now - timedelta(days=731))

    first = client.post(
        "/admin/comparables/maintenance",
        json={"dry_run": True},
        headers={"X-Admin-Token": admin_token},
    )
    assert first.status_code == 200
    b1 = first.json()
    assert b1["purged_retention"] == 1, "dry_run doit COMPTER la purge retention (phase B)"
    assert b1["purged_snapshots"] == 1, "dry_run doit COMPTER les snapshots purgeables (phase B)"
    assert _row("dry-cnt") is not None
    assert _snapshot_count("dry-cnt") == 1

    second = client.post(
        "/admin/comparables/maintenance",
        json={"dry_run": True},
        headers={"X-Admin-Token": admin_token},
    )
    b2 = second.json()
    assert (b2["purged_retention"], b2["purged_snapshots"]) == (1, 1), (
        "un dry_run repete doit renvoyer les memes compteurs : un ecart "
        "trahirait une mutation cachee au 1er passage (phase B)"
    )


# ===========================================================================
# Verrouillage correctif post-phase B (2026-06-10) — cascade snapshots sur
# TOUTES les purges (band / zone / dept / retention) + balayage d'orphelins.
# Residuel identifie en phase B : les purges band/zone/dept supprimaient le
# comparable SANS ses snapshots (orphelins jamais rattrapes). Ces tests sont
# l'oracle qui manquait : sans eux, retirer la cascade ou le balayage ne
# casserait aucun test.
# ===========================================================================

# Contrat maintenance fige (SPEC §5.3 amendee) : cles existantes inchangees +
# purged_orphan_snapshots. Egalite STRICTE : toute cle ajoutee/retiree doit
# passer par la spec.
MAINTENANCE_RESPONSE_KEYS = {
    "dry_run", "purged_band", "purged_zone", "purged_dept", "renamed",
    "renamed_district", "purged_retention", "purged_snapshots",
    "purged_orphan_snapshots", "total_after",
}


def _insert_comparable_full(listing_id, city="Metz", postal_code="57000",
                            price_total=250000.0, surface=80.0,
                            last_seen_at=None):
    """Variante de _insert_comparable_direct avec city/postal_code controles,
    pour declencher specifiquement les purges zone et dept. last_seen_at recent
    par defaut (la retention ne doit PAS etre le chemin de purge exerce)."""
    from db.session import engine

    last = last_seen_at if last_seen_at is not None else datetime.utcnow()
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO comparables "
                "(id, source, city, postal_code, property_type, surface_m2, "
                " price_total, price_m2, first_seen_at, last_seen_at, collected_at) "
                "VALUES (:id, 'bienici', :city, :cp, 'appartement', :surface, "
                " :price, :pm2, :last, :last, :last)"
            ),
            {
                "id": listing_id, "city": city, "cp": postal_code,
                "surface": surface, "price": price_total,
                "pm2": price_total / surface, "last": last,
            },
        )


def test_cascade_band_zone_dept_purges_delete_snapshots_real_run(client, admin_token):
    # Correctif post-phase B / cascade : un comparable purge pour BAND, un pour
    # ZONE (chemin reel extra_out_of_scope) et un pour DEPT, chacun avec des
    # snapshots, en un seul run reel -> comparables ET snapshots supprimes,
    # snapshots comptes dans purged_snapshots (2+1+3=6, comptes distincts par
    # chemin pour discriminer une cascade partielle), AUCUN orphelin (les
    # cascades ne doivent pas fuir dans purged_orphan_snapshots).
    from db.session import init_db

    init_db()
    # Band : 2_000_000 / 80 = 25 000 euros/m2 > 12 000 -> purged_band.
    _insert_comparable_full("casc-band", price_total=2000000.0, surface=80.0)
    _insert_snapshot_direct("casc-band", price_total=2000000.0)
    _insert_snapshot_direct("casc-band", price_total=1900000.0)
    # Zone : ville en bande et dept 57, purgee via extra_out_of_scope.
    _insert_comparable_full("casc-zone", city="Metz", postal_code="57000")
    _insert_snapshot_direct("casc-zone")
    # Dept : ville inconnue des blocklists, code postal hors 57.
    _insert_comparable_full("casc-dept", city="Ville Hors Perimetre",
                            postal_code="54000")
    _insert_snapshot_direct("casc-dept", price_total=250000.0)
    _insert_snapshot_direct("casc-dept", price_total=245000.0)
    _insert_snapshot_direct("casc-dept", price_total=240000.0)

    resp = client.post(
        "/admin/comparables/maintenance",
        json={"dry_run": False, "extra_out_of_scope": ["Metz"]},
        headers={"X-Admin-Token": admin_token},
    )
    assert resp.status_code == 200
    body = resp.json()

    assert set(body.keys()) == MAINTENANCE_RESPONSE_KEYS, (
        f"contrat maintenance modifie : {set(body.keys()) ^ MAINTENANCE_RESPONSE_KEYS}"
    )
    assert body["purged_band"] == 1
    assert body["purged_zone"] == 1
    assert body["purged_dept"] == 1
    assert body["purged_snapshots"] == 6, (
        f"cascade band(2)+zone(1)+dept(3) : 6 snapshots attendus dans "
        f"purged_snapshots, recu {body['purged_snapshots']} (correctif cascade)"
    )
    assert body["purged_orphan_snapshots"] == 0, (
        "les snapshots cascades ne doivent JAMAIS etre comptes en orphelins "
        "(double comptage / fuite de compteur)"
    )

    for lid in ("casc-band", "casc-zone", "casc-dept"):
        assert _row(lid) is None, f"{lid} doit etre purge"
        assert _snapshot_count(lid) == 0, (
            f"snapshots de {lid} non supprimes : cascade absente sur ce chemin "
            f"de purge (correctif post-phase B)"
        )


def test_cascade_band_dry_run_counts_without_deleting_not_as_orphans(client, admin_token):
    # Correctif post-phase B / dry_run : la cascade COMPTE les snapshots des
    # comparables purgeables (purged_snapshots) sans rien supprimer, et ces
    # snapshots ne sont PAS comptes en orphelins (leur parent existe encore en
    # dry_run -> raisonnement du developer verifie en conditions reelles).
    from db.session import init_db

    init_db()
    _insert_comparable_full("dryc-band", price_total=2000000.0, surface=80.0)
    _insert_snapshot_direct("dryc-band", price_total=2000000.0)
    _insert_snapshot_direct("dryc-band", price_total=1900000.0)

    resp = client.post(
        "/admin/comparables/maintenance",
        json={"dry_run": True},
        headers={"X-Admin-Token": admin_token},
    )
    assert resp.status_code == 200
    body = resp.json()

    assert body["purged_band"] == 1
    assert body["purged_snapshots"] == 2, (
        "dry_run doit COMPTER les snapshots cascades d'une purge band"
    )
    assert body["purged_orphan_snapshots"] == 0, (
        "en dry_run le parent existe encore : ses snapshots ne sont pas des "
        "orphelins (pas de double comptage dry_run)"
    )
    assert _row("dryc-band") is not None, "dry_run ne doit RIEN supprimer (comparable)"
    assert _snapshot_count("dryc-band") == 2, "dry_run ne doit RIEN supprimer (snapshots)"


def test_orphan_snapshot_dry_run_counted_then_real_run_deleted(client, admin_token):
    # Correctif post-phase B / orphelins : un snapshot dont le listing_id
    # n'existe pas dans comparables est compte dans purged_orphan_snapshots
    # (compteur DEDIE, pas purged_snapshots). dry_run : compte sans supprimer ;
    # run reel : supprime.
    from db.session import init_db

    init_db()
    _insert_snapshot_direct("ghost-orphan", price_total=250000.0)
    assert _row("ghost-orphan") is None  # precondition : vraiment orphelin

    dry = client.post(
        "/admin/comparables/maintenance",
        json={"dry_run": True},
        headers={"X-Admin-Token": admin_token},
    )
    assert dry.status_code == 200
    b_dry = dry.json()
    assert b_dry["purged_orphan_snapshots"] == 1, (
        "l'orphelin preexistant doit etre COMPTE en dry_run"
    )
    assert b_dry["purged_snapshots"] == 0, (
        "un orphelin ne doit pas fuir dans purged_snapshots (compteur dedie)"
    )
    assert _snapshot_count("ghost-orphan") == 1, (
        "dry_run ne doit PAS supprimer l'orphelin"
    )

    real = client.post(
        "/admin/comparables/maintenance",
        json={"dry_run": False},
        headers={"X-Admin-Token": admin_token},
    )
    assert real.status_code == 200
    b_real = real.json()
    assert b_real["purged_orphan_snapshots"] == 1
    assert b_real["purged_snapshots"] == 0
    assert _snapshot_count("ghost-orphan") == 0, (
        "le balayage reel doit supprimer l'orphelin (correctif post-phase B)"
    )


def test_no_double_count_cascade_plus_preexisting_orphan_single_run(client, admin_token):
    # Correctif post-phase B / pas de double comptage : un MEME run contient une
    # purge band (2 snapshots cascades) ET un orphelin preexistant (1 snapshot).
    # Chaque snapshot doit etre compte UNE fois dans le BON compteur, en dry_run
    # comme en reel (parite dry/reel), et le run reel supprime tout. Si
    # l'autoflush n'appliquait pas les suppressions de boucle avant le balayage,
    # les 2 snapshots cascades seraient recomptes en orphelins (3 au lieu de 1).
    from db.session import init_db

    init_db()
    _insert_comparable_full("ndc-band", price_total=2000000.0, surface=80.0)
    _insert_snapshot_direct("ndc-band", price_total=2000000.0)
    _insert_snapshot_direct("ndc-band", price_total=1900000.0)
    _insert_snapshot_direct("ndc-ghost", price_total=250000.0)
    assert _row("ndc-ghost") is None  # precondition : orphelin

    dry = client.post(
        "/admin/comparables/maintenance",
        json={"dry_run": True},
        headers={"X-Admin-Token": admin_token},
    )
    b_dry = dry.json()
    assert (b_dry["purged_snapshots"], b_dry["purged_orphan_snapshots"]) == (2, 1), (
        f"dry_run : 2 cascades + 1 orphelin attendus, recu "
        f"(purged_snapshots={b_dry['purged_snapshots']}, "
        f"purged_orphan_snapshots={b_dry['purged_orphan_snapshots']})"
    )
    assert _snapshot_count("ndc-band") == 2 and _snapshot_count("ndc-ghost") == 1, (
        "dry_run ne doit rien supprimer"
    )

    real = client.post(
        "/admin/comparables/maintenance",
        json={"dry_run": False},
        headers={"X-Admin-Token": admin_token},
    )
    b_real = real.json()
    assert (b_real["purged_snapshots"], b_real["purged_orphan_snapshots"]) == (2, 1), (
        f"run reel : chaque snapshot compte UNE fois dans le bon compteur, recu "
        f"(purged_snapshots={b_real['purged_snapshots']}, "
        f"purged_orphan_snapshots={b_real['purged_orphan_snapshots']})"
    )
    assert b_real["purged_band"] == 1
    assert _row("ndc-band") is None
    assert _snapshot_count("ndc-band") == 0
    assert _snapshot_count("ndc-ghost") == 0


def test_maintenance_second_real_run_is_idempotent_all_counters_zero(client, admin_token):
    # Correctif post-phase B / idempotence : apres un run reel qui a purge
    # cascade + orphelin, un SECOND run reel ne trouve plus rien a faire ->
    # tous les compteurs de purge a 0 (un residu trahirait une suppression
    # incomplete au 1er passage : snapshot survivant ou orphelin regenere).
    from db.session import init_db

    init_db()
    now = datetime.utcnow()
    _insert_comparable_full("idem-band", price_total=2000000.0, surface=80.0)
    _insert_snapshot_direct("idem-band", price_total=2000000.0)
    _insert_comparable_direct("idem-ret", last_seen_at=now - timedelta(days=731))
    _insert_snapshot_direct("idem-ret", observed_at=now - timedelta(days=731))
    _insert_snapshot_direct("idem-ghost", price_total=250000.0)

    first = client.post(
        "/admin/comparables/maintenance",
        json={"dry_run": False},
        headers={"X-Admin-Token": admin_token},
    )
    assert first.status_code == 200
    b1 = first.json()
    assert b1["purged_band"] == 1 and b1["purged_retention"] == 1
    assert b1["purged_snapshots"] == 2 and b1["purged_orphan_snapshots"] == 1

    second = client.post(
        "/admin/comparables/maintenance",
        json={"dry_run": False},
        headers={"X-Admin-Token": admin_token},
    )
    assert second.status_code == 200
    b2 = second.json()
    zeroed = {
        k: b2[k] for k in (
            "purged_band", "purged_zone", "purged_dept", "purged_retention",
            "purged_snapshots", "purged_orphan_snapshots",
        )
    }
    assert all(v == 0 for v in zeroed.values()), (
        f"second run reel : tous les compteurs de purge doivent etre a 0, "
        f"recu {zeroed} (idempotence du correctif)"
    )
    assert b2["total_after"] == 0

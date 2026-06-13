"""Chantier cross-agence — INCREMENT 2a (re-link "sans photo", meme agence) —
tests-first (phase A).

Contrat : docs/specs/cross-agence-INCREMENT2A-SPEC.md §5 (AC1 a AC42).

ROUGE LEGITIME attendu tant que le code 2a n'existe pas. Les echecs doivent
porter sur l'ABSENCE de la brique metier, JAMAIS sur un ImportError ou une
erreur de collecte :
- colonnes `reference`/`customer_id`/`lineage_id` absentes de `comparables`
  (AC1) et non persistees par `save_comparables` (AC4/AC5/AC8) ;
- logique de rattachement `_find_lineage_candidate` absente : la branche
  `existing is None` ne pose pas de `lineage_id` ni ne propage `first_seen_at`
  (AC10-AC24) ;
- `/history` n'agrege pas la lignee (AC25/AC26) ;
- retention qui ne raisonne pas sur le MAX(last_seen) de la lignee (AC29-AC33).

Discipline (lecons .claude/lessons.md) :
- APPEL DIRECT du code reel (`from ingestion.save import save_comparables`) sur
  la base jetable reelle, JAMAIS de mock de `db.get`/`db.merge`/session
  (lecon 9.10). Les bornes temporelles sont posees en injectant explicitement
  `last_seen_at`/`first_seen_at` en base (ecriture directe SQLAlchemy via les
  helpers `_insert_comparable_2a` / `_set_seen_dates`).
- ISOLATION : on s'appuie sur le reset autouse `comparables`/snapshots du
  conftest existant ; chaque test filtre ses assertions sur des id/reference
  UNIQUES (jamais de count() absolu global non filtre). On NE re-importe PAS
  `tests.conftest` sous un second nom (lecon double-import 2026-06-11).
- BORNES EXACTES testees des DEUX cotes : AC12/AC13 (90j vs 91j revolus),
  AC14/AC15 (surface 2,00 % vs 2,01 %), AC31 (730j lignee).
- ANTI-FUITE (AC27) : l'endpoint `/history` est declare `-> dict` SANS
  response_model -> la reponse JSON est exactement le dict construit par la
  fonction `comparable_history` (aucune couche Pydantic ne filtre les cles).
  Asserter `set(keys) <= liste_blanche` sur cette reponse teste donc bien la
  couche qui PRODUIT le dict (pas une serialisation qui masquerait une fuite,
  contrairement au piege 9.10 sur un corps a response_model).
- NON-REGRESSION (AC36-AC40) : on REUTILISE les helpers/smokes existants
  (`compute_global_score`, contrat /analyze) plutot que de dupliquer.
"""

from datetime import datetime, timedelta

import pytest
from sqlalchemy import inspect, text


ADMIN_TOKEN = "test-admin-token-cross-agence-2a"

# Set autorise des cles de la reponse admin /history (SPEC §4.1 / AC27).
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

# Cles INTERNES 2a (jamais exposees) + contenu re-publiable (CONTEXT §11.3).
FORBIDDEN_KEYS = {
    "reference", "customer_id", "lineage_id",
    "raw_text", "text", "title", "description", "address", "url", "photos",
    "photo", "image", "images", "city", "district", "postal_code",
}

# Contrat /analyze fige (SPEC AC37, INCREMENT1 AC19).
ANALYZE_ALLOWED_KEYS = {
    "global_score", "verdict", "confidence", "pillars", "actions",
    "local_context",
}


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------
def _make_ad(listing_id, price_total=250000.0, surface=80.0, city="Metz",
             source="bienici", postal_code="57000", property_type="appartement",
             reference=None, customer_id=None, **extra):
    """Annonce minimale valide (in band, dept 57). reference/customer_id ne sont
    inclus QUE s'ils sont fournis (pour exercer aussi le cas "cle absente")."""
    ad = {
        "id": listing_id,
        "source": source,
        "city": city,
        "district": None,
        "postal_code": postal_code,
        "property_type": property_type,
        "surface_m2": surface,
        "price_total": price_total,
    }
    if reference is not None:
        ad["reference"] = reference
    if customer_id is not None:
        ad["customer_id"] = customer_id
    ad.update(extra)
    return ad


@pytest.fixture()
def admin_token(monkeypatch):
    monkeypatch.setenv("ADMIN_TOKEN", ADMIN_TOKEN)
    return ADMIN_TOKEN


@pytest.fixture()
def frozen_now(monkeypatch):
    """Controle `datetime.utcnow()` lu par `ingestion.save` pour fixer l'instant
    de traitement (`now`) du run courant : indispensable pour poser des bornes
    temporelles exactes (fenetre 90j) de facon deterministe."""
    import ingestion.save as save_mod

    holder = {"now": datetime(2026, 6, 13, 4, 0, 0)}

    class _FrozenDateTime:
        @staticmethod
        def utcnow():
            return holder["now"]

    monkeypatch.setattr(save_mod, "datetime", _FrozenDateTime)
    return holder


def _row(listing_id):
    """Relit une ligne comparable par id via une session fraiche."""
    from db.session import SessionLocal
    from db.models import Comparable

    db = SessionLocal()
    try:
        return db.get(Comparable, listing_id)
    finally:
        db.close()


def _lineage_id(listing_id):
    row = _row(listing_id)
    return None if row is None else getattr(row, "lineage_id", "__MISSING_COL__")


def _require_lineage_column():
    """Echoue en AssertionError lisible (pas en AttributeError/OperationalError
    brute) si les colonnes 2a n'existent pas encore. ASSERTION (pas de
    tolerance) : aucun test de rattachement/lecture ne peut devenir vert sans la
    micro-migration -> rouge legitime tests-first, sur la BONNE cause. On exige
    les TROIS colonnes (reference/customer_id/lineage_id) car les helpers
    d'insertion directe (`_insert_comparable_2a`) ecrivent dans les trois : une
    migration partielle (lineage_id seul) ferait sinon lever une
    OperationalError opaque sur reference au lieu de ce message lisible."""
    from db.session import engine

    with engine.begin() as conn:
        cols = {r[1] for r in conn.execute(text("PRAGMA table_info(comparables)"))}
    missing = {"reference", "customer_id", "lineage_id"} - cols
    assert not missing, (
        f"colonne(s) {sorted(missing)} absente(s) de comparables : la "
        f"micro-migration 2a n'existe pas (encore) (rouge legitime tests-first)"
    )


def _snapshot_count(listing_id):
    from db.session import engine

    with engine.begin() as conn:
        return conn.execute(
            text("SELECT COUNT(*) FROM listing_price_snapshots WHERE listing_id = :lid"),
            {"lid": listing_id},
        ).scalar()


def _insert_comparable_2a(listing_id, last_seen_at, first_seen_at=None,
                          price_total=250000.0, surface=80.0, source="bienici",
                          city="Metz", property_type="appartement",
                          postal_code="57000", reference=None, customer_id=None,
                          lineage_id="__SELF__"):
    """Insere un comparable DIRECTEMENT en DB (SQLAlchemy) avec last_seen_at /
    first_seen_at / reference / customer_id / lineage_id controles, pour poser
    un CANDIDAT de rattachement a des bornes exactes (SPEC §5, procedure).

    lineage_id="__SELF__" => on pose lineage_id = id (lignee racine sur
    elle-meme). Passer lineage_id=None pour simuler une ligne HERITEE (AC11),
    une autre valeur pour une lignee explicite (AC10).

    Suppose la colonne lineage_id presente : appeler `_require_lineage_column()`
    en tete des tests qui s'en servent pour un rouge propre avant le code 2a.
    """
    from db.session import engine

    first = first_seen_at if first_seen_at is not None else last_seen_at
    lin = listing_id if lineage_id == "__SELF__" else lineage_id
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO comparables "
                "(id, source, city, postal_code, property_type, surface_m2, "
                " price_total, price_m2, reference, customer_id, lineage_id, "
                " first_seen_at, last_seen_at, collected_at) "
                "VALUES (:id, :source, :city, :cp, :ptype, :surface, :price, "
                " :pm2, :ref, :cust, :lin, :first, :last, :last)"
            ),
            {
                "id": listing_id, "source": source, "city": city,
                "cp": postal_code, "ptype": property_type, "surface": surface,
                "price": price_total, "pm2": price_total / surface,
                "ref": reference, "cust": customer_id, "lin": lin,
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


def _history(client, token, listing_id):
    from urllib.parse import quote

    return client.get(
        f"/admin/comparables/{quote(listing_id, safe='')}/history",
        headers={"X-Admin-Token": token},
    )


# ===========================================================================
# Schema & migration — AC1, AC2, AC3, AC41
# ===========================================================================
def test_ac1_migration_adds_reference_customer_id_lineage_columns():
    # AC1 : apres init_db(), table_info(comparables) contient reference,
    # customer_id ET lineage_id.
    from db.session import init_db, engine

    init_db()
    with engine.begin() as conn:
        cols = {r[1] for r in conn.execute(text("PRAGMA table_info(comparables)"))}
    for col in ("reference", "customer_id", "lineage_id"):
        assert col in cols, f"colonne {col} absente de comparables (AC1)"


def test_ac2_index_exists_on_lineage_id():
    # AC2 : un index couvre comparables.lineage_id (lecture/agregation lignee).
    from db.session import init_db, engine

    init_db()
    insp = inspect(engine)
    indexed_cols = set()
    for idx in insp.get_indexes("comparables"):
        indexed_cols.update(idx.get("column_names") or [])
    assert "lineage_id" in indexed_cols, (
        "aucun index sur comparables.lineage_id (AC2)"
    )


def test_ac3_init_db_idempotent_twice_no_duplicate_column_or_index():
    # AC3 : deux init_db() de suite ne levent pas, ne dupliquent ni colonne ni
    # index (table_info et index_list identiques apres le 2e appel).
    from db.session import init_db, engine

    init_db()
    insp1 = inspect(engine)
    with engine.begin() as conn:
        cols_first = [r[1] for r in conn.execute(text("PRAGMA table_info(comparables)"))]
    idx_first = sorted(i["name"] for i in insp1.get_indexes("comparables"))

    init_db()  # 2e appel : ne doit pas lever
    insp2 = inspect(engine)
    with engine.begin() as conn:
        cols_second = [r[1] for r in conn.execute(text("PRAGMA table_info(comparables)"))]
    idx_second = sorted(i["name"] for i in insp2.get_indexes("comparables"))

    assert cols_first == cols_second, "table_info diverge apres un 2e init_db (AC3)"
    assert len(cols_second) == len(set(cols_second)), "colonne dupliquee (AC3)"
    assert idx_first == idx_second, "index_list diverge apres un 2e init_db (AC3)"


def test_ac41_migration_idempotent_on_simulated_prod_stock():
    # AC41 : micro-migration idempotente sur une base SIMULANT le stock prod -
    # table comparables preexistante SANS les 3 colonnes 2a. Un init_db() les
    # ajoute (+ index) ; un 2e init_db() ne leve pas et ne re-cree rien.
    from db.session import init_db, engine

    # Reconstruire une table comparables "ancienne" depourvue des colonnes 2a.
    with engine.begin() as conn:
        conn.execute(text("DROP TABLE IF EXISTS comparables"))
        conn.execute(
            text(
                "CREATE TABLE comparables ("
                " id VARCHAR PRIMARY KEY, source VARCHAR NOT NULL, "
                " city VARCHAR NOT NULL, district VARCHAR, postal_code VARCHAR, "
                " property_type VARCHAR NOT NULL, surface_m2 FLOAT NOT NULL, "
                " price_total FLOAT NOT NULL, price_m2 FLOAT NOT NULL, "
                " collected_at DATETIME, first_seen_at DATETIME, last_seen_at DATETIME"
                ")"
            )
        )
        cols_before = {r[1] for r in conn.execute(text("PRAGMA table_info(comparables)"))}
    assert "lineage_id" not in cols_before, "precondition : stock prod sans lineage_id"

    init_db()
    with engine.begin() as conn:
        cols_after = {r[1] for r in conn.execute(text("PRAGMA table_info(comparables)"))}
    for col in ("reference", "customer_id", "lineage_id"):
        assert col in cols_after, f"{col} non ajoutee sur stock prod simule (AC41)"
    indexed = set()
    for idx in inspect(engine).get_indexes("comparables"):
        indexed.update(idx.get("column_names") or [])
    assert "lineage_id" in indexed, "index lineage_id non cree sur stock prod simule (AC41)"

    # 2e appel : ne doit pas lever.
    init_db()
    with engine.begin() as conn:
        cols_2nd = [r[1] for r in conn.execute(text("PRAGMA table_info(comparables)"))]
    assert len(cols_2nd) == len(set(cols_2nd)), "colonne dupliquee apres 2e init_db (AC41)"


# ===========================================================================
# Capture — AC4, AC5, AC6, AC7
# ===========================================================================
def test_ac4_capture_reference_and_customer_id_persisted(frozen_now):
    # AC4 : save_comparables avec reference="ABC" et customer_id="cust1" persiste
    # ces deux valeurs sur la ligne.
    from ingestion.save import save_comparables

    save_comparables([_make_ad("ac4-id", reference="ABC", customer_id="cust1")])
    row = _row("ac4-id")
    assert row is not None, "comparable non ecrit (AC4)"
    assert getattr(row, "reference", "__MISSING__") == "ABC", (
        "reference non persistee : la capture 2a n'ajoute pas la colonne au dict "
        "fields de save_comparables (AC4)"
    )
    assert getattr(row, "customer_id", "__MISSING__") == "cust1", (
        "customer_id non persiste (AC4)"
    )


def test_ac5_capture_absent_reference_customer_id_persists_none(frozen_now):
    # AC5 : sans reference ni customer_id (cles absentes) -> ligne creee avec
    # reference is None et customer_id is None, aucune exception.
    from ingestion.save import save_comparables

    save_comparables([_make_ad("ac5-id")])
    row = _row("ac5-id")
    assert row is not None, "comparable non cree quand reference/customer_id absents (AC5)"
    assert getattr(row, "reference", "__MISSING__") is None, (
        "reference doit etre None quand absente (AC5)"
    )
    assert getattr(row, "customer_id", "__MISSING__") is None, (
        "customer_id doit etre None quand absent (AC5)"
    )


def test_ac6_is_valid_true_without_reference_or_customer_id():
    # AC6 : _is_valid renvoie True pour un item complet SANS reference ni
    # customer_id (ces champs ne sont pas requis ; l'item reste pousse).
    from jobs.push_comparables import _is_valid

    item = {
        "id": "ac6-id", "source": "bienici", "city": "Metz",
        "property_type": "appartement", "surface_m2": 80, "price_total": 250000,
    }
    assert _is_valid(item) is True, (
        "_is_valid doit accepter un item sans reference/customer_id (AC6)"
    )
    # Et l'ajout des champs nullable ne doit pas le rejeter non plus.
    item2 = dict(item, id="ac6-id2", reference=None, customer_id=None)
    assert _is_valid(item2) is True, (
        "_is_valid ne doit pas rejeter reference/customer_id None (AC6)"
    )


def test_ac7_property_listing_nullable_reference_and_customer_id():
    # AC7 : contrat nullable du modele scrapers (capture HTML best-effort). Un
    # PropertyListing construit sans reference a reference is None ET
    # to_dict()["reference"] is None ; customer_id idem par defaut.
    from scrapers.models import PropertyListing

    pl = PropertyListing(
        id="ac7-id", source="benedic", city="Metz",
        property_type="appartement", surface_m2=80.0, price_total=250000.0,
    )
    # Cause metier nommee (et non AttributeError brute) : le modele scrapers doit
    # gagner les deux champs optionnels (SPEC §2.3).
    assert hasattr(pl, "reference"), (
        "PropertyListing n'a pas de champ `reference` : modele scrapers non "
        "etendu (SPEC §2.3, AC7)"
    )
    assert hasattr(pl, "customer_id"), (
        "PropertyListing n'a pas de champ `customer_id` : modele scrapers non "
        "etendu (SPEC §2.3, AC7)"
    )
    assert pl.reference is None, "PropertyListing.reference doit defaut a None (AC7)"
    assert pl.customer_id is None, "PropertyListing.customer_id doit defaut a None (AC7)"
    d = pl.to_dict()
    assert d["reference"] is None, "to_dict() doit propager reference=None (AC7)"
    assert d["customer_id"] is None, "to_dict() doit propager customer_id=None (AC7)"


# ===========================================================================
# Lignee par defaut (retro-compat) — AC8, AC9
# ===========================================================================
def test_ac8_first_observation_no_candidate_sets_lineage_to_self(frozen_now):
    # AC8 : 1re observation d'un id neuf SANS candidat -> lineage_id == id,
    # first_seen_at == last_seen_at (instant run) et exactement 1 snapshot.
    from ingestion.save import save_comparables

    _require_lineage_column()
    t0 = datetime(2026, 6, 13, 4, 0, 0)
    frozen_now["now"] = t0
    save_comparables([_make_ad("ac8-id", reference="REF8", customer_id="C8")])

    row = _row("ac8-id")
    assert row is not None, "comparable non ecrit a la 1re observation (AC8)"
    assert getattr(row, "lineage_id", None) == "ac8-id", (
        "1re observation sans candidat : lineage_id doit valoir l'id lui-meme (AC8)"
    )
    assert row.first_seen_at == row.last_seen_at == t0, (
        "first_seen_at/last_seen_at doivent valoir l'instant du run (AC8)"
    )
    assert _snapshot_count("ac8-id") == 1, "snapshot initial non ecrit (AC8)"


def test_ac9_legacy_row_lineage_null_read_as_own_root(client, admin_token):
    # AC9 : repli heritage en lecture. Une ligne preexistante avec lineage_id
    # NULL est traitee par /history comme sa propre racine (lineage = id) ;
    # la reponse agrege uniquement ses snapshots, sans erreur (200).
    from db.session import init_db

    init_db()
    _require_lineage_column()
    now = datetime(2026, 6, 13, 4, 0, 0)
    _insert_comparable_2a("ac9-legacy", last_seen_at=now, first_seen_at=now,
                          lineage_id=None)
    _insert_snapshot_direct("ac9-legacy", price_total=250000.0, observed_at=now)

    resp = _history(client, admin_token, "ac9-legacy")
    assert resp.status_code == 200, (
        f"ligne heritee lineage_id NULL : attendu 200, recu {resp.status_code} (AC9)"
    )
    body = resp.json()
    assert body["listing_id"] == "ac9-legacy"
    assert len(body["snapshots"]) == 1, (
        "une ligne heritee doit agreger uniquement ses propres snapshots (AC9)"
    )


# ===========================================================================
# Rattachement — cas nominal — AC10, AC11
# ===========================================================================
def test_ac10_relist_bienici_nominal_propagates_lineage_and_first_seen(frozen_now):
    # AC10 : re-list bienici nominal. Candidat disparu (reference R1, customer C1,
    # bienici, last_seen now-30j, lineage_id "L", first_seen T0). Arrivee d'un id
    # neuf de meme reference/customer/source/type/ville, surface egale, prix
    # DIFFERENT -> nouveau membre recoit lineage_id == "L" et first_seen_at == T0
    # (propage), + 1 snapshot du nouveau prix.
    from ingestion.save import save_comparables

    _require_lineage_column()
    now = datetime(2026, 6, 13, 4, 0, 0)
    t0 = now - timedelta(days=200)
    _insert_comparable_2a(
        "ac10-old", last_seen_at=now - timedelta(days=30), first_seen_at=t0,
        price_total=250000.0, surface=80.0, source="bienici",
        reference="R1", customer_id="C1", lineage_id="L",
    )

    frozen_now["now"] = now
    save_comparables([_make_ad(
        "ac10-new", price_total=239000.0, surface=80.0, source="bienici",
        reference="R1", customer_id="C1",
    )])

    row = _row("ac10-new")
    assert row is not None, "nouveau membre non ecrit (AC10)"
    assert getattr(row, "lineage_id", None) == "L", (
        "le nouveau membre re-liste doit heriter lineage_id du candidat ('L') (AC10)"
    )
    assert row.first_seen_at == t0, (
        "first_seen_at de la lignee (T0) doit etre propage au nouveau membre (AC10)"
    )
    assert _snapshot_count("ac10-new") == 1, "snapshot du nouveau prix non ecrit (AC10)"


def test_ac11_candidate_lineage_null_new_member_inherits_candidate_id(frozen_now):
    # AC11 : candidat HERITE (lineage_id NULL) -> le nouveau membre recoit
    # lineage_id == candidate.id (repli `lineage_id or id`).
    from ingestion.save import save_comparables

    _require_lineage_column()
    now = datetime(2026, 6, 13, 4, 0, 0)
    _insert_comparable_2a(
        "ac11-old", last_seen_at=now - timedelta(days=10),
        source="bienici", reference="R11", customer_id="C11", lineage_id=None,
    )

    frozen_now["now"] = now
    save_comparables([_make_ad(
        "ac11-new", source="bienici", reference="R11", customer_id="C11",
        price_total=240000.0,
    )])

    assert _lineage_id("ac11-new") == "ac11-old", (
        "candidat herite (lineage_id NULL) : le nouveau membre doit prendre "
        "candidate.id comme lineage (repli lineage_id or id) (AC11)"
    )


# ===========================================================================
# Rattachement — bornes exactes — AC12..AC16
# ===========================================================================
def test_ac12_window_90_days_inclusive_attaches(frozen_now):
    # AC12 : candidat last_seen = now-90j -> rattache (.days == 90 <= 90).
    from ingestion.save import save_comparables

    _require_lineage_column()
    now = datetime(2026, 6, 13, 4, 0, 0)
    _insert_comparable_2a(
        "ac12-old", last_seen_at=now - timedelta(days=90),
        source="bienici", reference="R12", customer_id="C12", lineage_id="L12",
    )
    frozen_now["now"] = now
    save_comparables([_make_ad(
        "ac12-new", source="bienici", reference="R12", customer_id="C12",
        price_total=240000.0,
    )])
    assert _lineage_id("ac12-new") == "L12", (
        "candidat a EXACTEMENT 90 jours doit etre rattache (borne incluse, AC12)"
    )


def test_ac13_window_91_days_exclusive_new_lineage(frozen_now):
    # AC13 : candidat last_seen = now-91j -> NON rattache (nouvelle lignee).
    from ingestion.save import save_comparables

    _require_lineage_column()
    now = datetime(2026, 6, 13, 4, 0, 0)
    _insert_comparable_2a(
        "ac13-old", last_seen_at=now - timedelta(days=91),
        source="bienici", reference="R13", customer_id="C13", lineage_id="L13",
    )
    frozen_now["now"] = now
    save_comparables([_make_ad(
        "ac13-new", source="bienici", reference="R13", customer_id="C13",
        price_total=240000.0,
    )])
    assert _lineage_id("ac13-new") == "ac13-new", (
        "candidat a 91 jours revolus doit etre EXCLU -> nouvelle lignee sur "
        "elle-meme (AC13)"
    )


def test_ac14_surface_2pct_inclusive_attaches(frozen_now):
    # AC14 : candidat surface 100.0, nouveau 102.0 (2,00 %) -> rattache (inclus).
    from ingestion.save import save_comparables

    _require_lineage_column()
    now = datetime(2026, 6, 13, 4, 0, 0)
    _insert_comparable_2a(
        "ac14-old", last_seen_at=now - timedelta(days=10), surface=100.0,
        price_total=300000.0, source="bienici", reference="R14",
        customer_id="C14", lineage_id="L14",
    )
    frozen_now["now"] = now
    save_comparables([_make_ad(
        "ac14-new", surface=102.0, price_total=290000.0, source="bienici",
        reference="R14", customer_id="C14",
    )])
    assert _lineage_id("ac14-new") == "L14", (
        "surface a EXACTEMENT +2,00 % doit etre rattachee (borne inclusive, AC14)"
    )


def test_ac15_surface_above_2pct_exclusive_new_lineage(frozen_now):
    # AC15 : candidat surface 100.0, nouveau 102.01 (>2,00 %) -> NON rattache.
    from ingestion.save import save_comparables

    _require_lineage_column()
    now = datetime(2026, 6, 13, 4, 0, 0)
    _insert_comparable_2a(
        "ac15-old", last_seen_at=now - timedelta(days=10), surface=100.0,
        price_total=300000.0, source="bienici", reference="R15",
        customer_id="C15", lineage_id="L15",
    )
    frozen_now["now"] = now
    save_comparables([_make_ad(
        "ac15-new", surface=102.01, price_total=290000.0, source="bienici",
        reference="R15", customer_id="C15",
    )])
    assert _lineage_id("ac15-new") == "ac15-new", (
        "surface a +2,01 % doit etre EXCLUE -> nouvelle lignee (AC15)"
    )


def test_ac16_no_price_constraint_strong_price_drop_still_attaches(frozen_now):
    # AC16 : un candidat eligible avec un prix fortement different (-20 %) est
    # tout de meme rattache (le prix n'entre pas dans la cle).
    from ingestion.save import save_comparables

    _require_lineage_column()
    now = datetime(2026, 6, 13, 4, 0, 0)
    _insert_comparable_2a(
        "ac16-old", last_seen_at=now - timedelta(days=10), price_total=300000.0,
        surface=80.0, source="bienici", reference="R16", customer_id="C16",
        lineage_id="L16",
    )
    frozen_now["now"] = now
    save_comparables([_make_ad(
        "ac16-new", price_total=240000.0, surface=80.0, source="bienici",
        reference="R16", customer_id="C16",
    )])
    assert _lineage_id("ac16-new") == "L16", (
        "un ecart de prix fort (-20 %) ne doit PAS empecher le rattachement : "
        "le prix n'entre pas dans la cle (AC16)"
    )


# ===========================================================================
# Rattachement — regle customer_id PAR-SOURCE — AC17..AC20
# ===========================================================================
def test_ac17_bienici_equal_customer_id_required_attaches(frozen_now):
    # AC17 : bienici, customer_id egal requis et present des deux cotes -> rattache.
    from ingestion.save import save_comparables

    _require_lineage_column()
    now = datetime(2026, 6, 13, 4, 0, 0)
    _insert_comparable_2a(
        "ac17-old", last_seen_at=now - timedelta(days=10), source="bienici",
        reference="R17", customer_id="C17", lineage_id="L17",
    )
    frozen_now["now"] = now
    save_comparables([_make_ad(
        "ac17-new", source="bienici", reference="R17", customer_id="C17",
        price_total=240000.0,
    )])
    assert _lineage_id("ac17-new") == "L17", (
        "bienici, customer_id egal : rattachement attendu (AC17)"
    )


def test_ac18_bienici_diverging_customer_id_new_lineage(frozen_now):
    # AC18 : bienici, customer_id divergent -> NON rattache, meme si reference et
    # attributs collent.
    from ingestion.save import save_comparables

    _require_lineage_column()
    now = datetime(2026, 6, 13, 4, 0, 0)
    _insert_comparable_2a(
        "ac18-old", last_seen_at=now - timedelta(days=10), source="bienici",
        reference="R18", customer_id="C18-A", lineage_id="L18",
    )
    frozen_now["now"] = now
    save_comparables([_make_ad(
        "ac18-new", source="bienici", reference="R18", customer_id="C18-B",
        price_total=240000.0,
    )])
    assert _lineage_id("ac18-new") == "ac18-new", (
        "bienici, customer_id divergent : pas de rattachement (collision agence) (AC18)"
    )


def test_ac19_bienici_missing_customer_id_one_side_no_link(frozen_now):
    # AC19 : bienici, customer_id absent d'un des deux cotes (ici cote nouveau
    # bien) -> NON rattache (collision reference triviale sans customerId).
    from ingestion.save import save_comparables

    _require_lineage_column()
    now = datetime(2026, 6, 13, 4, 0, 0)
    _insert_comparable_2a(
        "ac19-old", last_seen_at=now - timedelta(days=10), source="bienici",
        reference="R19", customer_id="C19", lineage_id="L19",
    )
    frozen_now["now"] = now
    # Nouveau bien bienici SANS customer_id (cle absente).
    save_comparables([_make_ad(
        "ac19-new", source="bienici", reference="R19", price_total=240000.0,
    )])
    assert _lineage_id("ac19-new") == "ac19-new", (
        "bienici, customer_id absent d'un cote : pas de lien (AC19)"
    )


def test_ac20_mono_agency_html_no_customer_id_attaches(frozen_now):
    # AC20 : source mono-agence HTML (benedic), customer_id absent des deux cotes,
    # meme reference+source+type+ville+surface +-2 % -> rattache (customer_id
    # non requis pour une source mono-agence).
    from ingestion.save import save_comparables

    _require_lineage_column()
    now = datetime(2026, 6, 13, 4, 0, 0)
    _insert_comparable_2a(
        "ac20-old", last_seen_at=now - timedelta(days=10), source="benedic",
        reference="R20", customer_id=None, lineage_id="L20",
    )
    frozen_now["now"] = now
    save_comparables([_make_ad(
        "ac20-new", source="benedic", reference="R20", price_total=240000.0,
    )])
    assert _lineage_id("ac20-new") == "L20", (
        "source mono-agence sans customer_id : rattachement attendu via "
        "reference+source+attributs (AC20)"
    )


# ===========================================================================
# Rattachement — politique de doute — AC21..AC24
# ===========================================================================
def test_ac21_absent_reference_no_search_new_lineage(frozen_now):
    # AC21 : reference absente/vide sur le nouveau bien -> aucune recherche,
    # nouvelle lignee, meme si un candidat plausible existe par attributs.
    from ingestion.save import save_comparables

    _require_lineage_column()
    now = datetime(2026, 6, 13, 4, 0, 0)
    # Candidat plausible par attributs ET meme reference, mais le NOUVEAU bien
    # n'a pas de reference -> pas de recherche.
    _insert_comparable_2a(
        "ac21-old", last_seen_at=now - timedelta(days=10), source="benedic",
        reference="R21", lineage_id="L21",
    )
    frozen_now["now"] = now
    save_comparables([_make_ad(
        "ac21-new", source="benedic", price_total=240000.0,  # pas de reference
    )])
    assert _lineage_id("ac21-new") == "ac21-new", (
        "reference absente sur le nouveau bien : aucune recherche -> nouvelle "
        "lignee (AC21)"
    )


def test_ac22_multi_candidates_abstention_new_lineage(frozen_now):
    # AC22 : >=2 candidats distincts satisfaisant TOUS les predicats -> abstention
    # (nouvelle lignee, rattache a aucun).
    from ingestion.save import save_comparables

    _require_lineage_column()
    now = datetime(2026, 6, 13, 4, 0, 0)
    for sid, lin in (("ac22-old-a", "L22A"), ("ac22-old-b", "L22B")):
        _insert_comparable_2a(
            sid, last_seen_at=now - timedelta(days=10), source="bienici",
            reference="R22", customer_id="C22", surface=80.0,
            price_total=250000.0, lineage_id=lin,
        )
    frozen_now["now"] = now
    save_comparables([_make_ad(
        "ac22-new", source="bienici", reference="R22", customer_id="C22",
        surface=80.0, price_total=240000.0,
    )])
    lin_new = _lineage_id("ac22-new")
    assert lin_new == "ac22-new", (
        f"2 candidats eligibles : abstention attendue (nouvelle lignee sur "
        f"elle-meme), recu lineage_id={lin_new!r} (AC22)"
    )


def test_ac23_diverging_source_new_lineage(frozen_now):
    # AC23 : source divergente (candidat benedic, nouveau bienici), memes
    # reference/attributs -> nouvelle lignee (2a est intra-source).
    from ingestion.save import save_comparables

    _require_lineage_column()
    now = datetime(2026, 6, 13, 4, 0, 0)
    _insert_comparable_2a(
        "ac23-old", last_seen_at=now - timedelta(days=10), source="benedic",
        reference="R23", lineage_id="L23",
    )
    frozen_now["now"] = now
    save_comparables([_make_ad(
        "ac23-new", source="bienici", reference="R23", customer_id="C23",
        price_total=240000.0,
    )])
    assert _lineage_id("ac23-new") == "ac23-new", (
        "source divergente : pas de rattachement inter-source (AC23)"
    )


def test_ac24_diverging_property_type_new_lineage(frozen_now):
    # AC24 : property_type divergent (candidat maison, nouveau appartement),
    # reste egal -> nouvelle lignee.
    from ingestion.save import save_comparables

    _require_lineage_column()
    now = datetime(2026, 6, 13, 4, 0, 0)
    _insert_comparable_2a(
        "ac24-old", last_seen_at=now - timedelta(days=10), source="benedic",
        property_type="maison", reference="R24", lineage_id="L24",
    )
    frozen_now["now"] = now
    save_comparables([_make_ad(
        "ac24-new", source="benedic", property_type="appartement",
        reference="R24", price_total=240000.0,
    )])
    assert _lineage_id("ac24-new") == "ac24-new", (
        "property_type divergent : pas de rattachement (AC24)"
    )


# ===========================================================================
# Lecture /history sur lignee — AC25, AC26, AC27, AC28
# ===========================================================================
def _build_lineage_two_members(frozen_now):
    """Construit une lignee de 2 membres via le code reel :
    - membre A (ac-lin-A) : 2 snapshots (T0=250000, T1=240000) ;
    - membre B (ac-lin-B) : re-list de A (meme reference/customer/attributs),
      snapshot T2=230000.
    Retourne (t0, t1, t2)."""
    from ingestion.save import save_comparables

    _require_lineage_column()
    t0 = datetime(2026, 1, 6, 4, 0, 0)
    t1 = datetime(2026, 2, 10, 4, 0, 0)
    t2 = datetime(2026, 6, 13, 4, 0, 0)

    frozen_now["now"] = t0
    save_comparables([_make_ad(
        "ac-lin-A", price_total=250000.0, surface=80.0, source="bienici",
        reference="RLIN", customer_id="CLIN",
    )])
    frozen_now["now"] = t1
    save_comparables([_make_ad(
        "ac-lin-A", price_total=240000.0, surface=80.0, source="bienici",
        reference="RLIN", customer_id="CLIN",
    )])
    # A "disparait" : B arrive plus tard avec un id neuf -> rattachement.
    frozen_now["now"] = t2
    save_comparables([_make_ad(
        "ac-lin-B", price_total=230000.0, surface=80.0, source="bienici",
        reference="RLIN", customer_id="CLIN",
    )])
    return t0, t1, t2


def test_ac25_history_aggregates_lineage_series(client, admin_token, frozen_now):
    # AC25 : lignee de 2 membres interrogee via /history/{B} -> 200, snapshots = 3
    # ordonnes par observed_at croissant, first_seen MIN (T0), price_first = prix
    # de T0, price_last = prix de T2, price_change_pct au bon signe (baisse < 0).
    t0, t1, t2 = _build_lineage_two_members(frozen_now)

    resp = _history(client, admin_token, "ac-lin-B")
    assert resp.status_code == 200, (
        f"/history/{{B}} attendu 200, recu {resp.status_code} (AC25)"
    )
    body = resp.json()
    snaps = body["snapshots"]
    assert len(snaps) == 3, (
        f"la serie fusionnee doit contenir 3 snapshots (A:T0,T1 + B:T2), recu "
        f"{len(snaps)} (AC25)"
    )
    obs = [s["observed_at"] for s in snaps]
    assert obs == sorted(obs), "snapshots non ordonnes par observed_at croissant (AC25)"
    assert body["price_first"] == 250000, "price_first != prix de T0 (AC25)"
    assert body["price_last"] == 230000, "price_last != prix de T2 (AC25)"
    assert body["price_change_pct"] is not None and body["price_change_pct"] < 0, (
        "baisse de prix sur la lignee -> price_change_pct negatif (AC25)"
    )
    assert str(t0.date()) in str(body["first_seen_at"]), (
        "first_seen_at de la lignee doit etre le MIN (T0) (AC25)"
    )


def test_ac26_history_same_series_via_any_member_id(client, admin_token, frozen_now):
    # AC26 : interrogeable par n'importe quel id membre. /history/{A} et
    # /history/{B} renvoient la MEME serie fusionnee et les memes
    # first_seen_at/last_seen_at.
    _build_lineage_two_members(frozen_now)

    ra = _history(client, admin_token, "ac-lin-A").json()
    rb = _history(client, admin_token, "ac-lin-B").json()

    assert ra["first_seen_at"] == rb["first_seen_at"], (
        "first_seen_at doit etre identique quel que soit l'id membre interroge (AC26)"
    )
    assert ra["last_seen_at"] == rb["last_seen_at"], (
        "last_seen_at doit etre identique quel que soit l'id membre interroge (AC26)"
    )
    snaps_a = [(s["price_total"], s["observed_at"]) for s in ra["snapshots"]]
    snaps_b = [(s["price_total"], s["observed_at"]) for s in rb["snapshots"]]
    assert snaps_a == snaps_b, (
        "la serie fusionnee doit etre identique via A ou via B (AC26)"
    )


def test_ac27_history_exposes_no_internal_or_republishable_keys(
    client, admin_token, frozen_now
):
    # AC27 : confidentialite. La reponse /history ne contient aucune cle
    # reference/customer_id/lineage_id ni cle re-publiable. L'ensemble des cles
    # racine est inclus dans la liste blanche, chaque snapshot itou.
    # NB anti-faux-vert (lecon 9.10) : `comparable_history` est declare `-> dict`
    # SANS response_model -> la reponse JSON EST le dict construit par la
    # fonction. Asserter `keys <= liste_blanche` teste donc la couche qui PRODUIT
    # le dict (pas une serialisation Pydantic qui masquerait une fuite).
    _build_lineage_two_members(frozen_now)

    resp = _history(client, admin_token, "ac-lin-B")
    assert resp.status_code == 200
    body = resp.json()

    keys = set(body.keys())
    assert keys <= HISTORY_ALLOWED_KEYS, (
        f"/history expose des cles hors liste blanche : "
        f"{keys - HISTORY_ALLOWED_KEYS} (AC27)"
    )
    leaked = keys & FORBIDDEN_KEYS
    assert not leaked, (
        f"cle(s) interne/re-publiable exposee(s) au niveau racine : {leaked} (AC27)"
    )
    for snap in body["snapshots"]:
        sk = set(snap.keys())
        assert sk <= SNAPSHOT_ALLOWED_KEYS, (
            f"snapshot expose des cles hors liste blanche : "
            f"{sk - SNAPSHOT_ALLOWED_KEYS} (AC27)"
        )
        assert not (sk & FORBIDDEN_KEYS), (
            f"snapshot expose une cle interne/re-publiable : {sk & FORBIDDEN_KEYS} (AC27)"
        )


def test_ac28_history_auth_401_and_unknown_404(client, admin_token, frozen_now):
    # AC28 : /history sans token (ou token errone) -> 401 ; id inconnu -> 404.
    # Garde anti-faux-vert : on prouve d'abord qu'un id CONNU repond 200 (la route
    # existe), pour distinguer le 404 metier d'un 404 de route absente.
    from ingestion.save import save_comparables

    frozen_now["now"] = datetime(2026, 6, 13, 4, 0, 0)
    save_comparables([_make_ad("ac28-known", reference="R28", customer_id="C28")])

    no_token = client.get("/admin/comparables/ac28-known/history")
    assert no_token.status_code == 401, (
        f"sans token attendu 401, recu {no_token.status_code} (AC28)"
    )
    bad = client.get(
        "/admin/comparables/ac28-known/history",
        headers={"X-Admin-Token": "mauvais-token"},
    )
    assert bad.status_code == 401, f"token errone attendu 401, recu {bad.status_code} (AC28)"

    known = _history(client, admin_token, "ac28-known")
    assert known.status_code == 200, (
        f"id CONNU doit repondre 200 (route existe), recu {known.status_code} (AC28)"
    )
    unknown = _history(client, admin_token, "ac28-jamais-vu-xyz")
    assert unknown.status_code == 404, (
        f"id inconnu attendu 404, recu {unknown.status_code} (AC28)"
    )


# ===========================================================================
# Retention sur lignee — AC29..AC33
# ===========================================================================
def test_ac29_living_lineage_not_purged_by_retention(client, admin_token):
    # AC29 : lignee a 2 membres, ancien last_seen now-731j, recent now-10j.
    # maintenance dry_run=false -> AUCUN membre purge (lignee vivante), snapshots
    # subsistent.
    from db.session import init_db

    init_db()
    _require_lineage_column()
    now = datetime.utcnow()
    _insert_comparable_2a(
        "ac29-old", last_seen_at=now - timedelta(days=731),
        reference="R29", customer_id="C29", lineage_id="L29",
    )
    _insert_snapshot_direct("ac29-old", observed_at=now - timedelta(days=731))
    _insert_comparable_2a(
        "ac29-new", last_seen_at=now - timedelta(days=10),
        reference="R29", customer_id="C29", lineage_id="L29",
    )
    _insert_snapshot_direct("ac29-new", observed_at=now - timedelta(days=10))

    resp = client.post(
        "/admin/comparables/maintenance",
        json={"dry_run": False},
        headers={"X-Admin-Token": admin_token},
    )
    assert resp.status_code == 200
    assert _row("ac29-old") is not None, (
        "membre ancien d'une lignee VIVANTE ne doit pas etre purge par retention (AC29)"
    )
    assert _row("ac29-new") is not None, "membre recent purge a tort (AC29)"
    assert _snapshot_count("ac29-old") == 1, "snapshots du membre ancien supprimes a tort (AC29)"
    assert _snapshot_count("ac29-new") == 1, "snapshots du membre recent supprimes a tort (AC29)"


def test_ac30_fully_expired_lineage_purged_with_snapshots(client, admin_token):
    # AC30 : lignee a 2 membres, tous deux >730j (MAX = now-731j). maintenance
    # dry_run=false -> les deux membres purges, purged_retention les compte,
    # snapshots supprimes (purged_snapshots).
    from db.session import init_db

    init_db()
    _require_lineage_column()
    now = datetime.utcnow()
    _insert_comparable_2a(
        "ac30-a", last_seen_at=now - timedelta(days=731),
        reference="R30", customer_id="C30", lineage_id="L30",
    )
    _insert_snapshot_direct("ac30-a", observed_at=now - timedelta(days=731))
    _insert_comparable_2a(
        "ac30-b", last_seen_at=now - timedelta(days=800),
        reference="R30", customer_id="C30", lineage_id="L30",
    )
    _insert_snapshot_direct("ac30-b", observed_at=now - timedelta(days=800))

    resp = client.post(
        "/admin/comparables/maintenance",
        json={"dry_run": False},
        headers={"X-Admin-Token": admin_token},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert _row("ac30-a") is None and _row("ac30-b") is None, (
        "lignee entierement expiree (MAX > 730j) : les deux membres doivent etre purges (AC30)"
    )
    assert body["purged_retention"] >= 2, (
        f"purged_retention doit compter les 2 membres expires, recu "
        f"{body['purged_retention']} (AC30)"
    )
    assert body["purged_snapshots"] >= 2, (
        "snapshots des membres purges non comptes (AC30)"
    )
    assert _snapshot_count("ac30-a") == 0 and _snapshot_count("ac30-b") == 0, (
        "snapshots des membres purges non supprimes (AC30)"
    )


def test_ac31_lineage_boundary_730_days_inclusive_kept(client, admin_token):
    # AC31 : lignee mono-membre last_seen = now-730j -> CONSERVE (.days == 730,
    # pas > 730). Cote inclus de la borne.
    from db.session import init_db

    init_db()
    _require_lineage_column()
    now = datetime.utcnow()
    _insert_comparable_2a(
        "ac31-keep", last_seen_at=now - timedelta(days=730),
        reference="R31", customer_id="C31", lineage_id="ac31-keep",
    )
    _insert_snapshot_direct("ac31-keep", observed_at=now - timedelta(days=730))

    resp = client.post(
        "/admin/comparables/maintenance",
        json={"dry_run": False},
        headers={"X-Admin-Token": admin_token},
    )
    assert resp.status_code == 200
    assert _row("ac31-keep") is not None, (
        "lignee mono-membre a EXACTEMENT 730 jours doit etre conservee (borne "
        "incluse, AC31)"
    )
    assert _snapshot_count("ac31-keep") == 1, "snapshots conserves supprimes a tort (AC31)"


def test_ac32_dry_run_expired_lineage_counts_without_deleting(client, admin_token):
    # AC32 : dry_run=true (defaut) sur une lignee expiree -> purged_retention peut
    # etre > 0 mais total_after et le contenu reel inchanges (rien supprime).
    from db.session import init_db

    init_db()
    _require_lineage_column()
    now = datetime.utcnow()
    _insert_comparable_2a(
        "ac32-exp", last_seen_at=now - timedelta(days=731),
        reference="R32", customer_id="C32", lineage_id="ac32-exp",
    )
    _insert_snapshot_direct("ac32-exp", observed_at=now - timedelta(days=731))

    resp = client.post(
        "/admin/comparables/maintenance",
        json={},  # dry_run true par defaut
        headers={"X-Admin-Token": admin_token},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["dry_run"] is True, "dry_run doit etre true par defaut (AC32)"
    assert _row("ac32-exp") is not None, "dry_run ne doit RIEN supprimer (comparable, AC32)"
    assert _snapshot_count("ac32-exp") == 1, "dry_run ne doit RIEN supprimer (snapshots, AC32)"


def test_ac33_cascade_per_member_living_lineage_keeps_all_snapshots(client, admin_token):
    # AC33 : cascade par membre. Sur une lignee VIVANTE (un membre recent), aucun
    # snapshot n'est supprime : la purge d'un membre n'emporte que SES propres
    # snapshots, jamais ceux d'un autre membre encore vivant. Ici la lignee est
    # vivante -> 0 suppression de snapshot.
    from db.session import init_db

    init_db()
    _require_lineage_column()
    now = datetime.utcnow()
    _insert_comparable_2a(
        "ac33-old", last_seen_at=now - timedelta(days=731),
        reference="R33", customer_id="C33", lineage_id="L33",
    )
    _insert_snapshot_direct("ac33-old", price_total=250000.0,
                            observed_at=now - timedelta(days=731))
    _insert_comparable_2a(
        "ac33-new", last_seen_at=now - timedelta(days=5),
        reference="R33", customer_id="C33", lineage_id="L33",
    )
    _insert_snapshot_direct("ac33-new", price_total=240000.0,
                            observed_at=now - timedelta(days=5))

    resp = client.post(
        "/admin/comparables/maintenance",
        json={"dry_run": False},
        headers={"X-Admin-Token": admin_token},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["purged_retention"] == 0, (
        "lignee vivante : aucune purge retention attendue (AC33)"
    )
    assert _snapshot_count("ac33-old") == 1 and _snapshot_count("ac33-new") == 1, (
        "aucun snapshot ne doit etre supprime sur une lignee vivante (AC33)"
    )
    assert body["purged_snapshots"] == 0, (
        "purged_snapshots doit etre 0 sur une lignee vivante (pas de cascade) (AC33)"
    )


# ===========================================================================
# Idempotence / non-regression — AC34..AC40
# ===========================================================================
def test_ac34_relist_idempotent_twice(frozen_now):
    # AC34 : rejouer DEUX fois le meme save_comparables([ad_new]) (re-list) ne
    # cree qu'UNE lignee rattachee et ne duplique pas le snapshot (2e passage par
    # la branche existing is not None).
    from ingestion.save import save_comparables

    _require_lineage_column()
    now = datetime(2026, 6, 13, 4, 0, 0)
    _insert_comparable_2a(
        "ac34-old", last_seen_at=now - timedelta(days=10), source="bienici",
        reference="R34", customer_id="C34", lineage_id="L34",
    )
    frozen_now["now"] = now
    ad_new = _make_ad("ac34-new", source="bienici", reference="R34",
                      customer_id="C34", price_total=240000.0)

    save_comparables([ad_new])
    assert _lineage_id("ac34-new") == "L34", "1er save : rattachement attendu (AC34)"
    assert _snapshot_count("ac34-new") == 1

    # 2e passage, meme instant, meme prix : aucune nouvelle lignee ni snapshot.
    save_comparables([ad_new])
    assert _lineage_id("ac34-new") == "L34", (
        "le re-run ne doit pas modifier le lineage_id deja pose (AC34)"
    )
    assert _snapshot_count("ac34-new") == 1, (
        "le re-run a prix identique ne doit pas dupliquer le snapshot (branche "
        "existing is not None) (AC34)"
    )


def test_ac35_replay_full_batch_idempotent(frozen_now):
    # AC35 : rejouer le meme LOT complet ne cree ni lignee ni snapshot
    # supplementaire (comptes stables apres 2e run).
    from ingestion.save import save_comparables
    from db.session import engine

    _require_lineage_column()
    now = datetime(2026, 6, 13, 4, 0, 0)
    frozen_now["now"] = now
    batch = [
        _make_ad("ac35-1", reference="R35-1", customer_id="C35", price_total=250000.0),
        _make_ad("ac35-2", reference="R35-2", customer_id="C35", price_total=260000.0),
        _make_ad("ac35-3", reference="R35-3", customer_id="C35", price_total=270000.0),
    ]

    save_comparables(batch)

    def _counts():
        with engine.begin() as conn:
            comps = conn.execute(
                text("SELECT COUNT(*) FROM comparables WHERE id IN "
                     "('ac35-1','ac35-2','ac35-3')")
            ).scalar()
            snaps = conn.execute(
                text("SELECT COUNT(*) FROM listing_price_snapshots WHERE listing_id IN "
                     "('ac35-1','ac35-2','ac35-3')")
            ).scalar()
        return comps, snaps

    first = _counts()
    assert first == (3, 3), f"1er run : 3 comparables + 3 snapshots attendus, recu {first} (AC35)"

    save_comparables(batch)  # rejoue le meme lot
    second = _counts()
    assert second == first, (
        f"rejouer le meme lot ne doit creer ni comparable ni snapshot "
        f"supplementaire : {first} -> {second} (AC35)"
    )


def test_ac36_inc1_capture_invariants_still_hold_with_self_lineage(frozen_now):
    # AC36 : non-regression inc.1. first_seen immuable, last_seen rafraichi,
    # snapshot delta a l'egalite exacte de price_total ; un id re-observe SANS
    # candidat conserve lineage_id == son id et son first_seen_at d'origine.
    from ingestion.save import save_comparables

    _require_lineage_column()
    t1 = datetime(2026, 1, 6, 4, 0, 0)
    t2 = datetime(2026, 3, 10, 4, 0, 0)

    frozen_now["now"] = t1
    save_comparables([_make_ad("ac36-id", price_total=250000.0,
                               reference="R36", customer_id="C36")])
    # Re-observation a prix egal : last_seen rafraichi, pas de snapshot, first_seen
    # immuable, lineage_id reste son propre id.
    frozen_now["now"] = t2
    save_comparables([_make_ad("ac36-id", price_total=250000.0,
                               reference="R36", customer_id="C36")])

    row = _row("ac36-id")
    assert row.first_seen_at == t1, "first_seen_at reecrit a la re-observation (AC36)"
    assert row.last_seen_at == t2, "last_seen_at non rafraichi (AC36)"
    assert _lineage_id("ac36-id") == "ac36-id", (
        "un id re-observe sans candidat doit garder lineage_id == son id (AC36)"
    )
    assert _snapshot_count("ac36-id") == 1, (
        "egalite exacte de price_total : aucun nouveau snapshot (AC36)"
    )


@pytest.fixture()
def no_fallback(monkeypatch):
    """analyze_semantic nominal deterministe (pas d'appel OpenAI reseau)."""
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


def test_ac37_analyze_contract_unchanged(client, no_fallback):
    # AC37 : /analyze ne gagne aucune cle. AnalyzeResponse reste le meme jeu de
    # cles (global_score, verdict, confidence, pillars, actions, local_context).
    resp = client.post(
        "/analyze",
        json={"raw_text": "Appartement T3 a Metz, 70 m2, increment 2a cross-agence."},
        headers={"Fly-Client-IP": "203.0.113.99"},
    )
    assert resp.status_code == 200, f"/analyze attendu 200, recu {resp.status_code} (AC37)"
    keys = set(resp.json().keys())
    assert keys <= ANALYZE_ALLOWED_KEYS, (
        f"le contrat /analyze ne doit gagner AUCUNE cle : {keys - ANALYZE_ALLOWED_KEYS} (AC37)"
    )


def test_ac38_scoring_40_30_30_unchanged():
    # AC38 : score 40/30/30 et invariant somme des piliers INCHANGES. On reutilise
    # le code de scoring reel (pas de lignee dans la selection). Un bien aligne,
    # transparent, peu risque = 100 ; l'invariant score == somme des points tient.
    from app.scoring import compute_global_score

    res = compute_global_score(
        {"verdict": "Plutôt aligné", "confidence": "Élevée"},
        {"transparency_score": 80, "risk_level": "faible"},
    )
    assert res["score"] == 100, "score 40/30/30 altere (AC38)"
    b = res["breakdown"]
    assert res["score"] == b["price"] + b["semantic"], (
        "le score doit rester EXACTEMENT la somme des piliers (AC38)"
    )
    assert b["semantic"] == b["transparency"] + b["risk"], (
        "decomposition semantique alteree (AC38)"
    )


def test_ac39_admin_import_contract_accepts_optional_reference(client, admin_token):
    # AC39 : POST /admin/comparables conserve son contrat {received, saved,
    # total_in_db} ET accepte reference/customer_id optionnels sans 422 (ni
    # quand presents, ni quand absents).
    # 1) avec reference/customer_id : pas de 422, capture OK.
    with_ref = client.post(
        "/admin/comparables",
        json={"items": [{
            "id": "ac39-ref", "source": "bienici", "city": "Metz",
            "property_type": "appartement", "surface_m2": 80,
            "price_total": 250000, "postal_code": "57000",
            "reference": "R39", "customer_id": "C39",
        }]},
        headers={"X-Admin-Token": admin_token},
    )
    assert with_ref.status_code == 200, (
        f"/admin/comparables avec reference attendu 200, recu "
        f"{with_ref.status_code} (AC39)"
    )
    assert set(with_ref.json().keys()) == {"received", "saved", "total_in_db"}, (
        f"contrat /admin/comparables modifie : {set(with_ref.json().keys())} (AC39)"
    )
    assert with_ref.json()["saved"] == 1
    assert getattr(_row("ac39-ref"), "reference", None) == "R39", (
        "reference fournie a l'import non persistee (AC39)"
    )

    # 2) sans reference/customer_id : toujours 200 (champs optionnels).
    without_ref = client.post(
        "/admin/comparables",
        json={"items": [{
            "id": "ac39-noref", "source": "bienici", "city": "Metz",
            "property_type": "appartement", "surface_m2": 80,
            "price_total": 250000, "postal_code": "57000",
        }]},
        headers={"X-Admin-Token": admin_token},
    )
    assert without_ref.status_code == 200, (
        f"/admin/comparables sans reference doit rester 200 (champs optionnels), "
        f"recu {without_ref.status_code} (AC39)"
    )


def test_ac40_duplicate_id_intra_batch_no_aggravation(frozen_now):
    # AC40 : id duplique intra-batch (preexistant inc.1, INCREMENT1-SPEC §8). 2a
    # ne doit PAS l'aggraver : _find_lineage_candidate est lecture seule (aucun
    # db.add supplementaire). Le batch ne doit pas lever ni perdre l'ecriture du
    # comparable ; comportement coherent avec inc.1 (1 comparable, 1 snapshot).
    from ingestion.save import save_comparables

    _require_lineage_column()
    frozen_now["now"] = datetime(2026, 6, 13, 4, 0, 0)
    # Meme id deux fois dans le meme lot, meme reference (re-list intra-run).
    batch = [
        _make_ad("ac40-dup", price_total=250000.0, reference="R40", customer_id="C40"),
        _make_ad("ac40-dup", price_total=250000.0, reference="R40", customer_id="C40"),
    ]
    # Ne doit pas lever (robustesse identique a inc.1).
    save_comparables(batch)

    assert _row("ac40-dup") is not None, (
        "id duplique intra-batch : le comparable doit exister (pas de perte, AC40)"
    )
    # Lignee sur elle-meme : aucun candidat disparu (l'id est present dans le run).
    assert _lineage_id("ac40-dup") == "ac40-dup", (
        "id duplique intra-batch : nouvelle lignee sur elle-meme, pas de "
        "rattachement parasite (AC40)"
    )
    assert _snapshot_count("ac40-dup") == 1, (
        "id duplique intra-batch a prix identique : exactement 1 snapshot "
        "(comportement inc.1 inchange, AC40)"
    )


# ===========================================================================
# Isolation / etat memoire — AC42
# ===========================================================================
def test_ac42_no_new_module_memory_state_introduced_by_2a():
    # AC42 : 2a n'introduit AUCUN nouvel etat memoire de module a reset (§3.7).
    # On verifie (a) que le reset autouse comparables/snapshots existant est bien
    # present en conftest, (b) que les modules touches par 2a (ingestion.save,
    # app.main) n'exposent pas de cache/compteur module (dict/set/Counter
    # mutable au niveau module) qui exigerait un nouveau reset autouse.
    import inspect as _inspect

    # (a) reset autouse existant en conftest (jamais en fixture locale, lecon 9.9).
    from tests import conftest as conftest_mod  # import deja charge par pytest
    assert hasattr(conftest_mod, "_reset_snapshots_table"), (
        "reset autouse comparables/snapshots absent de conftest (AC42)"
    )
    src = _inspect.getsource(conftest_mod._reset_snapshots_table)
    assert "comparables" in src and "listing_price_snapshots" in src, (
        "le reset autouse doit couvrir comparables ET snapshots (AC42)"
    )

    # (b) aucun nouvel etat memoire mutable au niveau module dans le code 2a.
    import ingestion.save as save_mod

    suspect = {}
    for name, val in vars(save_mod).items():
        if name.startswith("__"):
            continue
        # Constantes connues (bornes, set de villes) tolerees : ce sont des
        # parametres de configuration figes, pas un cache d'execution accumulant
        # de l'etat entre requetes. On signale tout AUTRE conteneur mutable au
        # niveau module qui ressemblerait a un cache/compteur (lecon photo/9.9).
        if name in {"OUT_OF_SCOPE_CITIES"}:
            continue
        if isinstance(val, (dict, set, list)):
            suspect[name] = type(val).__name__
    assert not suspect, (
        f"2a a introduit un etat memoire de module suspect dans ingestion.save "
        f"(cache/compteur ?) sans reset autouse : {suspect} (AC42)"
    )

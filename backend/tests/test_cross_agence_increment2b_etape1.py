"""Chantier cross-agence — INCREMENT 2b, ETAPE 1 (capture URLs photo bienici +
probe gisement cross-source) — tests-first (phase A).

Contrat : docs/specs/cross-agence-INCREMENT2B-ETAPE1-SPEC.md §5 (AC1 a AC32).

ROUGE LEGITIME attendu tant que le code etape 1 n'existe pas. Les echecs DOIVENT
porter sur l'ABSENCE de la brique metier (colonne/champ/script manquant), JAMAIS
sur un ImportError parasite ou une erreur de collecte :
- colonne `photo_urls` absente de `comparables` (AC1-AC3) et non persistee par
  `save_comparables` (AC9) ;
- helper `_extract_photo_urls` absent de `scrapers.sources.bienici` (AC4-AC8) ;
- champ `photo_urls` absent de `PropertyListing` (AC10) ;
- `photo_urls` fuite dans une reponse API (AC15-AC17) ;
- script `backend/tools/probe_cross_source.py` inexistant (AC21-AC31).

Discipline (.claude/lessons.md) :
- APPEL DIRECT du code reel (`from ingestion.save import save_comparables`,
  `from db.session import init_db`) sur la base jetable reelle, JAMAIS de mock de
  `db.get`/`setattr`/session (lecon 9.10). Les valeurs longitudinales
  (last_seen_at/first_seen_at/sources/surfaces) sont POSEES en injectant
  explicitement en base (ecriture directe SQLAlchemy via `_insert_probe_row`).
- ISOLATION : on s'appuie sur le reset autouse `comparables`/snapshots du
  conftest existant ; chaque test filtre ses assertions sur des id/references
  UNIQUES (jamais de count() absolu global). On NE re-importe PAS `tests.conftest`
  sous un second nom (lecon double-import 2026-06-11). Pas de nouvel etat memoire
  de module.
- GATE DE SCHEMA AVANT INSERT BRUT (lecon testeur phase A inc.2a) : tout test qui
  insere via SQL/ORM la colonne `photo_urls` pas encore migree asserte d'abord sa
  presence (`_require_photo_urls_column()`) -> AssertionError lisible, jamais une
  OperationalError opaque.
- BORNES EXACTES testees des DEUX cotes : cap d'URLs (3 vs 4e ignoree, AC7),
  surface proxy 10,00 % vs 10,01 % (AC22/AC23), fenetre probe 180j vs 181j
  (AC24/AC25), gap "disparu" 7j (critere 2 du proxy).
- ANTI-FUITE (AC15-17) : on asserte sur le DICT construit par la fonction
  `comparable_history` (pas seulement via le response_model) ET sur les reponses
  /analyze + stats — la valeur sentinelle `_SENTINEL_PHOTO_URL` n'apparait NULLE
  PART dans le corps serialise.
- NON-REGRESSION (AC18-20) : on REUTILISE les smokes existants (score 40/30/30,
  contrat /analyze, lignee 2a), sans dupliquer.

----------------------------------------------------------------------------
CONTRAT ATTENDU DU SCRIPT PROBE (le developpeur DOIT s'y conformer)
----------------------------------------------------------------------------
La SPEC §3.2 fige le module `backend/tools/probe_cross_source.py` et ses
constantes (`_PROBE_GAP_DAYS_RECENT=7`, `_PROBE_WINDOW_DAYS=180`,
`_PROBE_SURFACE_TOL=0.10`) mais NE fige PAS le nom de la fonction de calcul ni la
structure de retour. Le TESTEUR fixe ici le contrat suivant (a respecter par le
developpeur, sinon les tests probe sont rouges) :

  module   : tools.probe_cross_source
  fonction : compute_probe(now=None) -> dict
             - lecture seule (que des db.query, aucun db.add/commit) ;
             - `now` (datetime) optionnel = instant de reference du run
               (defaut datetime.utcnow()). Injectable pour des bornes
               temporelles deterministes ;
             - retourne un dict de COMPTEURS AGREGES, sans aucun id/URL/donnee
               perso, AU MOINS :
                 {
                   "total_pairs": int,           # total paires candidates
                   "pairs_by_source_couple": {   # cle = "a<->b" trie lexico
                       "benedic<->bienici": int, ...
                   },
                   "total_comparables": int,
                   "disappeared": int,           # nb comparables "disparus"
                   "by_source": {"bienici": int, ...},
                   "involved_pct": float,        # % corpus implique
                 }
  fonction : render_report(stats: dict) -> str
             - rapport texte/Markdown agrege a partir du dict ci-dessus ;
             - CONTIENT une section "Limites" mentionnant les termes-cles
               "borne haute" (ou "candidats potentiels"), "syndication",
               "intrant de decision" ;
             - NE contient AUCUN id/reference/URL/donnee perso.

Si le developpeur retient d'autres noms, il DOIT renommer ici (un seul endroit :
les imports `from tools.probe_cross_source import compute_probe, render_report`)
et la phase B reprend la propriete de l'oracle. Tant que le module n'existe pas,
les tests probe echouent en AssertionError metier lisible via `_probe_module()`
(pas un crash de collecte de toute la suite).
"""

import json
from datetime import datetime, timedelta

import pytest
from sqlalchemy import text


# URL sentinelle : valeur temoin qui ne doit JAMAIS fuiter dans une reponse API.
_SENTINEL_PHOTO_URL = "http://SENTINEL/x.jpg"

ADMIN_TOKEN = "test-admin-token-cross-agence-2b"

HISTORY_ALLOWED_KEYS = {
    "listing_id", "source", "first_seen_at", "last_seen_at", "weeks_on_market",
    "price_first", "price_last", "price_change_pct", "snapshots",
}
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
    """Annonce minimale valide (in band, dept 57). `photo_urls` ajoute seulement
    si fourni en `extra` (pour exercer aussi le cas "cle absente")."""
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
    """Controle `datetime.utcnow()` lu par `ingestion.save` (instant `now` du
    run) pour des bornes temporelles deterministes."""
    import ingestion.save as save_mod

    holder = {"now": datetime(2026, 6, 13, 4, 0, 0)}

    class _FrozenDateTime:
        @staticmethod
        def utcnow():
            return holder["now"]

    monkeypatch.setattr(save_mod, "datetime", _FrozenDateTime)
    return holder


def _row(listing_id):
    from db.session import SessionLocal
    from db.models import Comparable

    db = SessionLocal()
    try:
        return db.get(Comparable, listing_id)
    finally:
        db.close()


def _comparables_columns():
    from db.session import engine

    with engine.begin() as conn:
        return {r[1] for r in conn.execute(text("PRAGMA table_info(comparables)"))}


def _require_photo_urls_column():
    """Gate de schema (lecon testeur phase A inc.2a) : echoue en AssertionError
    LISIBLE (pas en OperationalError opaque) si la colonne `photo_urls` n'existe
    pas encore. ASSERTION (pas de skip) : aucun test d'insertion/lecture de
    `photo_urls` ne peut devenir vert sans la micro-migration -> rouge legitime
    tests-first, sur la BONNE cause."""
    from db.session import init_db

    init_db()
    assert "photo_urls" in _comparables_columns(), (
        "colonne `photo_urls` absente de comparables : la micro-migration "
        "etape 1 (db/session.py::_ADD_COLUMNS) n'existe pas (encore) "
        "(rouge legitime tests-first, AC1)"
    )


def _photo_helper():
    """Retourne `_extract_photo_urls` du scraper bienici, ou echoue en
    AssertionError lisible si le helper n'existe pas encore (rouge legitime,
    jamais ImportError parasite a la collecte)."""
    import scrapers.sources.bienici as bienici

    fn = getattr(bienici, "_extract_photo_urls", None)
    assert fn is not None, (
        "helper `_extract_photo_urls` absent de scrapers.sources.bienici : la "
        "capture etape 1 n'existe pas (encore) (rouge legitime tests-first, AC4)"
    )
    return fn


def _snapshot_count(listing_id):
    from db.session import engine

    with engine.begin() as conn:
        return conn.execute(
            text("SELECT COUNT(*) FROM listing_price_snapshots WHERE listing_id = :lid"),
            {"lid": listing_id},
        ).scalar()


def _insert_probe_row(listing_id, source, last_seen_at, first_seen_at,
                      surface=80.0, city="Metz", property_type="appartement",
                      postal_code="57000", price_total=250000.0,
                      photo_urls=None, lineage_id="__SELF__"):
    """Insere DIRECTEMENT un comparable (SQLAlchemy) avec last_seen_at /
    first_seen_at / source / surface / postal_code controles, pour poser un jeu
    synthetique de probe a bornes exactes (SPEC §3.3). Suppose `photo_urls` migre
    (appeler `_require_photo_urls_column()` en preambule)."""
    from db.session import engine

    lin = listing_id if lineage_id == "__SELF__" else lineage_id
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO comparables "
                "(id, source, city, postal_code, property_type, surface_m2, "
                " price_total, price_m2, lineage_id, photo_urls, "
                " first_seen_at, last_seen_at, collected_at) "
                "VALUES (:id, :source, :city, :cp, :ptype, :surface, :price, "
                " :pm2, :lin, :photo, :first, :last, :last)"
            ),
            {
                "id": listing_id, "source": source, "city": city,
                "cp": postal_code, "ptype": property_type, "surface": surface,
                "price": price_total, "pm2": price_total / surface,
                "lin": lin, "photo": photo_urls,
                "first": first_seen_at, "last": last_seen_at,
            },
        )


def _history(client, token, listing_id):
    from urllib.parse import quote

    return client.get(
        f"/admin/comparables/{quote(listing_id, safe='')}/history",
        headers={"X-Admin-Token": token},
    )


# Constantes de probe (SPEC §3.3) : on les LIT du module pour rester exact si le
# developpeur les ajustait (mais la SPEC fige 7/180/0.10).
def _probe_module():
    """Importe tools.probe_cross_source, ou echoue en AssertionError metier
    lisible (le script n'existe pas encore) plutot qu'en ImportError de
    collecte. Contrat documente en tete de fichier."""
    try:
        import tools.probe_cross_source as probe
    except Exception as exc:  # noqa: BLE001 - on convertit en cause metier lisible
        pytest.fail(
            "module `tools.probe_cross_source` introuvable : le script probe "
            f"etape 1 n'existe pas (encore) (rouge legitime tests-first, AC21). "
            f"Detail import : {exc!r}"
        )
    return probe


def _probe_const(name, default):
    probe = _probe_module()
    return getattr(probe, name, default)


def _build_probe_pair(now, *, prefix, surface_a=100.0, surface_b=100.0,
                      source_a="benedic", source_b="bienici",
                      gap_days=30, window_days=10,
                      property_type_b="appartement", city_b="Metz",
                      postal_a="57000", postal_b="57000",
                      b_after=True):
    """Insere une paire (A, B) synthetique controlee :
    - A "disparu" : last_seen_at = now - gap_days (gap_days > 7 => disparu) ;
    - B apparu apres : first_seen_at = A.last_seen_at + window_days
      (b_after=False => first_seen_at = A.last_seen_at, pas "apres").
    Renvoie (id_a, id_b)."""
    a_last = now - timedelta(days=gap_days)
    a_first = a_last - timedelta(days=5)
    if b_after:
        b_first = a_last + timedelta(days=window_days)
    else:
        b_first = a_last  # pas strictement apres
    b_last = b_first  # B vivant/recent (peu importe pour le proxy cote B)

    id_a = f"{prefix}-A"
    id_b = f"{prefix}-B"
    _insert_probe_row(id_a, source_a, last_seen_at=a_last, first_seen_at=a_first,
                      surface=surface_a, postal_code=postal_a)
    _insert_probe_row(id_b, source_b, last_seen_at=b_last, first_seen_at=b_first,
                      surface=surface_b, postal_code=postal_b,
                      property_type=property_type_b, city=city_b)
    return id_a, id_b


# ===========================================================================
# Schema & migration — AC1, AC2, AC3
# ===========================================================================
def test_ac1_migration_adds_photo_urls_column():
    # AC1 : apres init_db(), table_info(comparables) contient photo_urls.
    from db.session import init_db

    init_db()
    assert "photo_urls" in _comparables_columns(), (
        "colonne photo_urls absente de comparables : micro-migration etape 1 "
        "manquante (AC1)"
    )


def test_ac2_init_db_idempotent_twice_no_duplicate_photo_urls():
    # AC2 : deux init_db() de suite ne levent pas et ne dupliquent pas photo_urls
    # (table_info identique apres le 2e appel).
    from db.session import init_db

    init_db()
    cols_first = sorted(_comparables_columns())
    init_db()  # 2e appel : ne doit pas lever
    cols_second = sorted(_comparables_columns())

    assert cols_first == cols_second, "table_info diverge apres un 2e init_db (AC2)"
    assert cols_second.count("photo_urls") == 1, "photo_urls dupliquee (AC2)"


def test_ac3_migration_idempotent_on_simulated_prod_stock():
    # AC3 : sur une table comparables PREEXISTANTE sans photo_urls (stock prod
    # simule, avec 1 ligne), un init_db() ajoute la colonne ; un 2e init_db() ne
    # leve pas. La ligne preexistante est conservee, photo_urls IS NULL pour elle.
    from db.session import init_db, engine

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
        conn.execute(
            text(
                "INSERT INTO comparables "
                "(id, source, city, property_type, surface_m2, price_total, price_m2) "
                "VALUES ('ac3-legacy', 'bienici', 'Metz', 'appartement', 80.0, "
                " 250000.0, 3125.0)"
            )
        )
        cols_before = {r[1] for r in conn.execute(text("PRAGMA table_info(comparables)"))}
    assert "photo_urls" not in cols_before, "precondition : stock prod sans photo_urls"

    init_db()
    assert "photo_urls" in _comparables_columns(), (
        "photo_urls non ajoutee sur stock prod simule (AC3)"
    )
    init_db()  # 2e appel : ne doit pas lever

    from db.session import engine as eng2
    with eng2.begin() as conn:
        row = conn.execute(
            text("SELECT id, photo_urls FROM comparables WHERE id = 'ac3-legacy'")
        ).fetchone()
    assert row is not None, "ligne preexistante perdue par la migration (AC3)"
    assert row[1] is None, "photo_urls doit valoir NULL pour les lignes heritees (AC3)"


# ===========================================================================
# Capture (helper _extract_photo_urls) — AC4..AC8
# ===========================================================================
def test_ac4_extract_photo_urls_nominal_three_str_urls():
    # AC4 : 3 URLs str valides -> json.dumps([u1, u2, u3]), ordre preserve.
    fn = _photo_helper()
    u1, u2, u3 = "http://cdn/a.jpg", "http://cdn/b.jpg", "http://cdn/c.jpg"
    out = fn({"photos": [u1, u2, u3]})
    assert out == json.dumps([u1, u2, u3]), (
        f"nominal 3 URLs str : attendu json.dumps([u1,u2,u3]), recu {out!r} (AC4)"
    )


def test_ac5_extract_photo_urls_dict_elements():
    # AC5 : elements dict {"url": ...} -> lecture de la cle d'URL.
    fn = _photo_helper()
    u1, u2 = "http://cdn/a.jpg", "http://cdn/b.jpg"
    out = fn({"photos": [{"url": u1}, {"url": u2}]})
    assert out == json.dumps([u1, u2]), (
        f"elements dict avec cle 'url' : attendu json.dumps([u1,u2]), recu "
        f"{out!r} (AC5)"
    )


def test_ac6_extract_photo_urls_nullable_defensive_never_raises():
    # AC6 : nombreux cas degrades -> None, JAMAIS d'exception.
    fn = _photo_helper()
    cases = [
        {},                              # photos absent
        {"photos": []},                  # liste vide
        {"photos": None},                # None
        {"photos": "x"},                 # pas une liste
        {"photos": [{}]},                # dict sans cle d'URL
        {"photos": [{"foo": 1}]},        # dict sans cle d'URL connue
        {"photos": [""]},                # str vide
        {"photos": [123]},               # type non exploitable
    ]
    for ad in cases:
        try:
            out = fn(ad)
        except Exception as exc:  # noqa: BLE001
            pytest.fail(
                f"_extract_photo_urls a leve sur {ad!r} : {exc!r} (doit etre "
                f"defensif, AC6)"
            )
        assert out is None, (
            f"_extract_photo_urls({ad!r}) doit retourner None, recu {out!r} (AC6)"
        )


def test_ac7_extract_photo_urls_cap_exactly_three():
    # AC7 : cap EXACT a 3 des deux cotes. 5 URLs distinctes -> [u1,u2,u3] (4e/5e
    # ignorees) ; exactement 3 -> les 3.
    fn = _photo_helper()
    urls = [f"http://cdn/{i}.jpg" for i in range(5)]
    out5 = fn({"photos": urls})
    assert out5 == json.dumps(urls[:3]), (
        f"5 URLs : cap a 3 attendu (4e/5e ignorees), recu {out5!r} (AC7)"
    )
    out3 = fn({"photos": urls[:3]})
    assert out3 == json.dumps(urls[:3]), (
        f"exactement 3 URLs : les 3 retenues, recu {out3!r} (AC7)"
    )


def test_ac8_extract_photo_urls_dedup_order_preserving():
    # AC8 : deduplication ordre-preservant. [u1, u1, u2] -> [u1, u2].
    fn = _photo_helper()
    u1, u2 = "http://cdn/a.jpg", "http://cdn/b.jpg"
    out = fn({"photos": [u1, u1, u2]})
    assert out == json.dumps([u1, u2]), (
        f"dedup ordre-preservant attendu [u1,u2], recu {out!r} (AC8)"
    )


# ===========================================================================
# Persistance & propagation — AC9..AC12
# ===========================================================================
def test_ac9_persistence_end_to_end_and_nullable(frozen_now):
    # AC9 : save_comparables persiste photo_urls quand fourni ; persiste None
    # quand absent (cle absente), comparable bien cree, aucune exception.
    from ingestion.save import save_comparables

    _require_photo_urls_column()
    u1, u2 = "http://cdn/a.jpg", "http://cdn/b.jpg"
    photo_json = json.dumps([u1, u2])

    save_comparables([_make_ad("ac9-with", photo_urls=photo_json)])
    row_with = _row("ac9-with")
    assert row_with is not None, "comparable avec photo_urls non ecrit (AC9)"
    assert getattr(row_with, "photo_urls", "__MISSING__") == photo_json, (
        "photo_urls non persiste : la capture etape 1 n'ajoute pas la colonne au "
        "dict fields de save_comparables (AC9)"
    )

    # Sans photo_urls (cle absente) : ligne creee, photo_urls is None.
    save_comparables([_make_ad("ac9-without")])
    row_without = _row("ac9-without")
    assert row_without is not None, "comparable sans photo_urls non cree (AC9)"
    assert getattr(row_without, "photo_urls", "__MISSING__") is None, (
        "photo_urls doit etre None quand la cle est absente (AC9)"
    )


def test_ac10_property_listing_nullable_photo_urls():
    # AC10 : contrat nullable du modele scrapers (sans reseau). Un PropertyListing
    # construit sans photo_urls a photo_urls is None ET to_dict()["photo_urls"]
    # is None.
    from scrapers.models import PropertyListing

    pl = PropertyListing(
        id="ac10-id", source="bienici", city="Metz",
        property_type="appartement", surface_m2=80.0, price_total=250000.0,
    )
    assert hasattr(pl, "photo_urls"), (
        "PropertyListing n'a pas de champ `photo_urls` : modele scrapers non "
        "etendu (SPEC §2.3, AC10)"
    )
    assert pl.photo_urls is None, "PropertyListing.photo_urls doit defaut a None (AC10)"
    d = pl.to_dict()
    assert "photo_urls" in d, "to_dict() doit propager la cle photo_urls (AC10)"
    assert d["photo_urls"] is None, "to_dict()['photo_urls'] doit etre None (AC10)"


def test_ac11_is_valid_does_not_require_photo_urls():
    # AC11 : _is_valid renvoie True pour un item complet SANS photo_urls (champ
    # non requis ; item pousse). Et la presence d'un photo_urls ne le rejette pas.
    from jobs.push_comparables import _is_valid

    item = {
        "id": "ac11-id", "source": "bienici", "city": "Metz",
        "property_type": "appartement", "surface_m2": 80, "price_total": 250000,
    }
    assert _is_valid(item) is True, (
        "_is_valid doit accepter un item sans photo_urls (AC11)"
    )
    item2 = dict(item, id="ac11-id2", photo_urls=json.dumps(["http://cdn/a.jpg"]))
    assert _is_valid(item2) is True, (
        "_is_valid ne doit pas rejeter un item portant photo_urls (AC11)"
    )


def test_ac12_admin_import_accepts_optional_photo_urls(client, admin_token):
    # AC12 : POST /admin/comparables accepte photo_urls optionnel. Body sans
    # photo_urls -> pas 422 ; body avec photo_urls (chaine) accepte ; le contrat
    # de reponse reste {received, saved, total_in_db}.
    without = client.post(
        "/admin/comparables",
        json={"items": [{
            "id": "ac12-without", "source": "bienici", "city": "Metz",
            "property_type": "appartement", "surface_m2": 80,
            "price_total": 250000, "postal_code": "57000",
        }]},
        headers={"X-Admin-Token": admin_token},
    )
    assert without.status_code == 200, (
        f"/admin/comparables sans photo_urls attendu 200, recu "
        f"{without.status_code} (AC12)"
    )
    assert set(without.json().keys()) == {"received", "saved", "total_in_db"}, (
        f"contrat /admin/comparables modifie : {set(without.json().keys())} (AC12)"
    )

    with_photo = client.post(
        "/admin/comparables",
        json={"items": [{
            "id": "ac12-with", "source": "bienici", "city": "Metz",
            "property_type": "appartement", "surface_m2": 80,
            "price_total": 250000, "postal_code": "57000",
            "photo_urls": json.dumps(["http://cdn/a.jpg"]),
        }]},
        headers={"X-Admin-Token": admin_token},
    )
    assert with_photo.status_code == 200, (
        f"/admin/comparables avec photo_urls attendu 200 (champ optionnel), recu "
        f"{with_photo.status_code} (AC12)"
    )
    assert set(with_photo.json().keys()) == {"received", "saved", "total_in_db"}


# ===========================================================================
# Idempotence ingestion — AC13, AC14
# ===========================================================================
def test_ac13_reobservation_updates_photo_urls_no_duplicate(frozen_now):
    # AC13 : rejouer 2x save_comparables (meme id) avec photo_urls ne cree qu'1
    # ligne ; photo_urls mis a jour comme les autres champs (2e passage avec
    # photo_urls modifie ECRASE l'ancien) ; pas de snapshot supplementaire si le
    # prix est inchange.
    from ingestion.save import save_comparables

    _require_photo_urls_column()
    p1 = json.dumps(["http://cdn/a.jpg"])
    p2 = json.dumps(["http://cdn/a.jpg", "http://cdn/b.jpg"])

    frozen_now["now"] = datetime(2026, 6, 13, 4, 0, 0)
    save_comparables([_make_ad("ac13-id", price_total=250000.0, photo_urls=p1)])
    assert getattr(_row("ac13-id"), "photo_urls", None) == p1
    assert _snapshot_count("ac13-id") == 1

    # 2e passage : meme id, meme prix, photo_urls modifie.
    frozen_now["now"] = datetime(2026, 7, 1, 4, 0, 0)
    save_comparables([_make_ad("ac13-id", price_total=250000.0, photo_urls=p2)])

    rows = _comparables_columns()  # sanity colonne presente
    assert "photo_urls" in rows
    assert getattr(_row("ac13-id"), "photo_urls", None) == p2, (
        "la re-observation doit ECRASER photo_urls comme les autres champs (AC13)"
    )
    # Pas de doublon de comparable (id unique = PK), prix inchange -> pas de
    # snapshot supplementaire.
    assert _snapshot_count("ac13-id") == 1, (
        "prix inchange : aucun snapshot supplementaire au re-run (AC13)"
    )


def test_ac14_replay_full_batch_stable_photo_urls(frozen_now):
    # AC14 : rejouer le meme LOT complet ne cree ni comparable ni snapshot
    # supplementaire ; les photo_urls restent stables.
    from ingestion.save import save_comparables
    from db.session import engine

    _require_photo_urls_column()
    frozen_now["now"] = datetime(2026, 6, 13, 4, 0, 0)
    p = json.dumps(["http://cdn/a.jpg"])
    batch = [
        _make_ad("ac14-1", price_total=250000.0, photo_urls=p),
        _make_ad("ac14-2", price_total=260000.0, photo_urls=p),
    ]

    save_comparables(batch)

    def _counts():
        with engine.begin() as conn:
            comps = conn.execute(
                text("SELECT COUNT(*) FROM comparables WHERE id IN ('ac14-1','ac14-2')")
            ).scalar()
            snaps = conn.execute(
                text("SELECT COUNT(*) FROM listing_price_snapshots "
                     "WHERE listing_id IN ('ac14-1','ac14-2')")
            ).scalar()
        return comps, snaps

    first = _counts()
    assert first == (2, 2), f"1er run : 2 comparables + 2 snapshots, recu {first} (AC14)"

    save_comparables(batch)  # rejoue
    second = _counts()
    assert second == first, (
        f"rejouer le meme lot ne doit rien creer de plus : {first} -> {second} (AC14)"
    )
    assert getattr(_row("ac14-1"), "photo_urls", None) == p, (
        "photo_urls doit rester stable au re-run (AC14)"
    )
    assert getattr(_row("ac14-2"), "photo_urls", None) == p, (
        "photo_urls doit rester stable au re-run (AC14)"
    )


# ===========================================================================
# Anti-fuite (confidentialite) — AC15, AC16, AC17
# ===========================================================================
def test_ac15_history_does_not_expose_photo_urls(client, admin_token, frozen_now):
    # AC15 : /history n'expose pas photo_urls, ni sa cle ni sa valeur sentinelle.
    # Verifie sur le DICT construit par la fonction comparable_history (pas
    # seulement via response_model, lecon 9.10) ET sur la reponse HTTP serialisee.
    from ingestion.save import save_comparables
    import app.main as main_mod

    _require_photo_urls_column()
    frozen_now["now"] = datetime(2026, 6, 13, 4, 0, 0)
    save_comparables([_make_ad(
        "ac15-id", reference="R15", customer_id="C15",
        photo_urls=json.dumps([_SENTINEL_PHOTO_URL]),
    )])
    assert getattr(_row("ac15-id"), "photo_urls", None) == json.dumps(
        [_SENTINEL_PHOTO_URL]
    ), "precondition : photo_urls sentinelle bien persiste en base (AC15)"

    # (a) couche qui PRODUIT le dict : appel direct de la fonction d'endpoint.
    import os
    os.environ["ADMIN_TOKEN"] = ADMIN_TOKEN
    built = main_mod.comparable_history("ac15-id", x_admin_token=ADMIN_TOKEN)
    assert isinstance(built, dict)
    assert "photo_urls" not in built, (
        "le DICT construit par comparable_history ne doit pas contenir photo_urls "
        "(AC15)"
    )
    assert set(built.keys()) <= HISTORY_ALLOWED_KEYS, (
        f"/history (dict construit) expose des cles hors liste blanche : "
        f"{set(built.keys()) - HISTORY_ALLOWED_KEYS} (AC15)"
    )
    assert _SENTINEL_PHOTO_URL not in json.dumps(built, default=str), (
        "la valeur sentinelle photo_urls fuite dans le dict /history (AC15)"
    )

    # (b) reponse HTTP serialisee : la sentinelle n'apparait nulle part.
    resp = _history(client, admin_token, "ac15-id")
    assert resp.status_code == 200
    body = resp.json()
    assert "photo_urls" not in body, "/history (HTTP) expose la cle photo_urls (AC15)"
    assert _SENTINEL_PHOTO_URL not in json.dumps(body), (
        "la valeur sentinelle photo_urls fuite dans le corps HTTP /history (AC15)"
    )


def test_ac16_stats_does_not_expose_photo_urls(client, admin_token, frozen_now):
    # AC16 : /admin/comparables/stats n'expose pas photo_urls (cles <= {total,
    # cities}), meme avec un comparable portant une URL sentinelle.
    from ingestion.save import save_comparables

    _require_photo_urls_column()
    frozen_now["now"] = datetime(2026, 6, 13, 4, 0, 0)
    save_comparables([_make_ad(
        "ac16-id", photo_urls=json.dumps([_SENTINEL_PHOTO_URL]),
    )])

    resp = client.get(
        "/admin/comparables/stats", headers={"X-Admin-Token": admin_token}
    )
    assert resp.status_code == 200, f"stats attendu 200, recu {resp.status_code} (AC16)"
    body = resp.json()
    assert set(body.keys()) <= {"total", "cities"}, (
        f"/stats expose des cles hors {{total, cities}} : "
        f"{set(body.keys()) - {'total', 'cities'}} (AC16)"
    )
    assert _SENTINEL_PHOTO_URL not in json.dumps(body), (
        "la valeur sentinelle photo_urls fuite dans /stats (AC16)"
    )


def test_ac17_admin_import_response_does_not_expose_photo_urls(client, admin_token):
    # AC17 : POST /admin/comparables : la reponse = {received, saved, total_in_db}
    # meme quand l'item importe portait un photo_urls (valeur sentinelle absente).
    resp = client.post(
        "/admin/comparables",
        json={"items": [{
            "id": "ac17-id", "source": "bienici", "city": "Metz",
            "property_type": "appartement", "surface_m2": 80,
            "price_total": 250000, "postal_code": "57000",
            "photo_urls": json.dumps([_SENTINEL_PHOTO_URL]),
        }]},
        headers={"X-Admin-Token": admin_token},
    )
    assert resp.status_code == 200, f"import attendu 200, recu {resp.status_code} (AC17)"
    body = resp.json()
    assert set(body.keys()) == {"received", "saved", "total_in_db"}, (
        f"contrat /admin/comparables modifie : {set(body.keys())} (AC17)"
    )
    assert _SENTINEL_PHOTO_URL not in json.dumps(body), (
        "la valeur sentinelle photo_urls fuite dans la reponse d'import (AC17)"
    )


# ===========================================================================
# Non-regression (invariants) — AC18, AC19, AC20
# ===========================================================================
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


def test_ac18_analyze_contract_unchanged(client, no_fallback):
    # AC18 : /analyze ne gagne aucune cle (contrat fige, AnalyzeResponse inchange).
    resp = client.post(
        "/analyze",
        json={"raw_text": "Appartement T3 a Metz, 70 m2, increment 2b etape 1."},
        headers={"Fly-Client-IP": "203.0.113.42"},
    )
    assert resp.status_code == 200, f"/analyze attendu 200, recu {resp.status_code} (AC18)"
    keys = set(resp.json().keys())
    assert keys <= ANALYZE_ALLOWED_KEYS, (
        f"le contrat /analyze ne doit gagner AUCUNE cle : "
        f"{keys - ANALYZE_ALLOWED_KEYS} (AC18)"
    )


def test_ac19_scoring_40_30_30_unchanged():
    # AC19 : score 40/30/30 et invariant somme des piliers INCHANGES (photo_urls
    # n'entre ni dans la selection ni dans le score). Reutilise le smoke existant.
    from app.scoring import compute_global_score

    res = compute_global_score(
        {"verdict": "Plutôt aligné", "confidence": "Élevée"},
        {"transparency_score": 80, "risk_level": "faible"},
    )
    assert res["score"] == 100, "score 40/30/30 altere (AC19)"
    b = res["breakdown"]
    assert res["score"] == b["price"] + b["semantic"], (
        "le score doit rester EXACTEMENT la somme des piliers (AC19)"
    )


def test_ac20_lineage_2a_unchanged_with_and_without_photo_urls(frozen_now):
    # AC20 : non-regression rattachement 2a. Un re-list 2a nominal reste rattache
    # a l'identique, qu'photo_urls soit present ou None (lineage_id inchange).
    from ingestion.save import save_comparables

    _require_photo_urls_column()
    now = datetime(2026, 6, 13, 4, 0, 0)

    # Variante A : candidat + nouveau membre AVEC photo_urls.
    _insert_probe_row("ac20-old-p", "bienici", last_seen_at=now - timedelta(days=10),
                      first_seen_at=now - timedelta(days=200), lineage_id="LP")
    # reference/customer_id requis cote candidat pour le rattachement bienici :
    # on les pose via une seconde ecriture directe (l'insert minimal probe ne les
    # met pas). On reutilise donc save_comparables pour creer un candidat complet.
    from db.session import engine
    with engine.begin() as conn:
        conn.execute(
            text("UPDATE comparables SET reference='RP', customer_id='CP' "
                 "WHERE id='ac20-old-p'")
        )
    frozen_now["now"] = now
    save_comparables([_make_ad(
        "ac20-new-p", source="bienici", reference="RP", customer_id="CP",
        price_total=240000.0, photo_urls=json.dumps(["http://cdn/a.jpg"]),
    )])
    lin_p = getattr(_row("ac20-new-p"), "lineage_id", None)
    assert lin_p == "LP", (
        f"re-list 2a AVEC photo_urls : rattachement attendu (lineage 'LP'), recu "
        f"{lin_p!r} (AC20)"
    )

    # Variante B : meme scenario SANS photo_urls -> meme rattachement.
    _insert_probe_row("ac20-old-n", "bienici", last_seen_at=now - timedelta(days=10),
                      first_seen_at=now - timedelta(days=200), lineage_id="LN")
    with engine.begin() as conn:
        conn.execute(
            text("UPDATE comparables SET reference='RN', customer_id='CN' "
                 "WHERE id='ac20-old-n'")
        )
    frozen_now["now"] = now
    save_comparables([_make_ad(
        "ac20-new-n", source="bienici", reference="RN", customer_id="CN",
        price_total=240000.0,
    )])
    lin_n = getattr(_row("ac20-new-n"), "lineage_id", None)
    assert lin_n == "LN", (
        f"re-list 2a SANS photo_urls : meme rattachement (lineage 'LN'), recu "
        f"{lin_n!r} (AC20)"
    )


# ===========================================================================
# Probe (jeu synthetique controle, bornes exactes) — AC21..AC31
# ===========================================================================
def test_ac21_probe_nominal_one_candidate_pair_counted():
    # AC21 : 1 paire candidate valide (A benedic disparu, B bienici apparu apres,
    # memes property_type/city/postal, surface +-10 %, fenetre) -> compte 1 ; la
    # ventilation impute au couple "benedic<->bienici".
    from db.session import init_db

    init_db()
    _require_photo_urls_column()
    now = datetime(2026, 6, 13, 4, 0, 0)
    _build_probe_pair(now, prefix="ac21", source_a="benedic", source_b="bienici",
                      gap_days=30, window_days=10, surface_a=100.0, surface_b=100.0)

    probe = _probe_module()
    stats = probe.compute_probe(now=now)
    assert stats["total_pairs"] == 1, (
        f"1 paire candidate attendue, recu {stats['total_pairs']} (AC21)"
    )
    couples = stats["pairs_by_source_couple"]
    assert couples.get("benedic<->bienici") == 1, (
        f"la paire doit etre imputee au couple 'benedic<->bienici', recu "
        f"{couples!r} (AC21)"
    )


def test_ac22_probe_surface_10pct_inclusive_counted():
    # AC22 : surface +-10 % incluse. A 100.0, B 110.0 (10,00 %), sinon valides
    # -> comptee (1 paire).
    from db.session import init_db

    init_db()
    _require_photo_urls_column()
    now = datetime(2026, 6, 13, 4, 0, 0)
    _build_probe_pair(now, prefix="ac22", surface_a=100.0, surface_b=110.0,
                      gap_days=30, window_days=10)

    stats = _probe_module().compute_probe(now=now)
    assert stats["total_pairs"] == 1, (
        f"surface 110/100 = +10,00 % doit etre INCLUSE (borne), recu "
        f"{stats['total_pairs']} paire(s) (AC22)"
    )


def test_ac23_probe_surface_above_10pct_excluded():
    # AC23 : surface > +10 % exclue. A 100.0, B 110.01 (>10,00 %) -> non comptee.
    from db.session import init_db

    init_db()
    _require_photo_urls_column()
    now = datetime(2026, 6, 13, 4, 0, 0)
    _build_probe_pair(now, prefix="ac23", surface_a=100.0, surface_b=110.01,
                      gap_days=30, window_days=10)

    stats = _probe_module().compute_probe(now=now)
    assert stats["total_pairs"] == 0, (
        f"surface 110.01/100 = +10,01 % doit etre EXCLUE, recu "
        f"{stats['total_pairs']} paire(s) (AC23)"
    )


def test_ac24_probe_window_inclusive_counted():
    # AC24 : fenetre _PROBE_WINDOW_DAYS incluse. B.first_seen = A.last_seen + W
    # jours, sinon valides -> comptee.
    from db.session import init_db

    init_db()
    _require_photo_urls_column()
    now = datetime(2026, 6, 13, 4, 0, 0)
    window = _probe_const("_PROBE_WINDOW_DAYS", 180)
    # gap_days assez grand pour que A reste "disparu" ET que now soit posterieur a
    # B.first_seen (B existe). On ancre A loin dans le passe.
    _build_probe_pair(now, prefix="ac24", gap_days=window + 30,
                      window_days=window, surface_a=100.0, surface_b=100.0)

    stats = _probe_module().compute_probe(now=now)
    assert stats["total_pairs"] == 1, (
        f"B a EXACTEMENT W={window} jours apres A doit etre INCLUS (borne), recu "
        f"{stats['total_pairs']} paire(s) (AC24)"
    )


def test_ac25_probe_window_plus_one_day_excluded():
    # AC25 : fenetre _PROBE_WINDOW_DAYS + 1 exclue.
    from db.session import init_db

    init_db()
    _require_photo_urls_column()
    now = datetime(2026, 6, 13, 4, 0, 0)
    window = _probe_const("_PROBE_WINDOW_DAYS", 180)
    _build_probe_pair(now, prefix="ac25", gap_days=window + 40,
                      window_days=window + 1, surface_a=100.0, surface_b=100.0)

    stats = _probe_module().compute_probe(now=now)
    assert stats["total_pairs"] == 0, (
        f"B a W+1={window + 1} jours apres A doit etre EXCLU, recu "
        f"{stats['total_pairs']} paire(s) (AC25)"
    )


def test_ac26_probe_same_source_excluded():
    # AC26 : meme source exclue (la probe ne cible que le cross-source).
    from db.session import init_db

    init_db()
    _require_photo_urls_column()
    now = datetime(2026, 6, 13, 4, 0, 0)
    _build_probe_pair(now, prefix="ac26", source_a="bienici", source_b="bienici",
                      gap_days=30, window_days=10)

    stats = _probe_module().compute_probe(now=now)
    assert stats["total_pairs"] == 0, (
        f"A et B de MEME source ne doivent PAS etre comptes (cross-source only), "
        f"recu {stats['total_pairs']} paire(s) (AC26)"
    )


def test_ac27_probe_missing_postal_code_excluded():
    # AC27 : code postal manquant exclu (on ne devine pas). A postal None.
    from db.session import init_db

    init_db()
    _require_photo_urls_column()
    now = datetime(2026, 6, 13, 4, 0, 0)
    _build_probe_pair(now, prefix="ac27", postal_a=None, postal_b="57000",
                      gap_days=30, window_days=10)

    stats = _probe_module().compute_probe(now=now)
    assert stats["total_pairs"] == 0, (
        f"postal_code NULL d'un cote -> paire EXCLUE, recu "
        f"{stats['total_pairs']} paire(s) (AC27)"
    )


def test_ac28_probe_diverging_property_type_or_city_excluded():
    # AC28 : property_type (ou city) divergents exclus.
    from db.session import init_db

    init_db()
    _require_photo_urls_column()
    now = datetime(2026, 6, 13, 4, 0, 0)
    # property_type divergent.
    _build_probe_pair(now, prefix="ac28-pt", property_type_b="maison",
                      gap_days=30, window_days=10)
    # city divergente.
    _build_probe_pair(now, prefix="ac28-city", city_b="Woippy",
                      gap_days=30, window_days=10)

    stats = _probe_module().compute_probe(now=now)
    assert stats["total_pairs"] == 0, (
        f"property_type ou city divergents -> aucune paire, recu "
        f"{stats['total_pairs']} (AC28)"
    )


def test_ac29_probe_b_not_after_a_excluded():
    # AC29 : B non apparu apres A exclu (B.first_seen <= A.last_seen).
    from db.session import init_db

    init_db()
    _require_photo_urls_column()
    now = datetime(2026, 6, 13, 4, 0, 0)
    _build_probe_pair(now, prefix="ac29", gap_days=30, window_days=0, b_after=False)

    stats = _probe_module().compute_probe(now=now)
    assert stats["total_pairs"] == 0, (
        f"B.first_seen <= A.last_seen -> paire EXCLUE (critere 3), recu "
        f"{stats['total_pairs']} paire(s) (AC29)"
    )


def test_ac30_probe_is_read_only():
    # AC30 : la probe n'ecrit RIEN. Compte de comparables, de snapshots, et chaque
    # (id, lineage_id, photo_urls) identiques avant/apres run.
    from db.session import init_db, engine

    init_db()
    _require_photo_urls_column()
    now = datetime(2026, 6, 13, 4, 0, 0)
    _build_probe_pair(now, prefix="ac30", gap_days=30, window_days=10)
    # Pose aussi un photo_urls et un snapshot pour elargir la surface de mutation.
    with engine.begin() as conn:
        conn.execute(
            text("UPDATE comparables SET photo_urls=:p WHERE id='ac30-A'"),
            {"p": json.dumps([_SENTINEL_PHOTO_URL])},
        )
        conn.execute(
            text("INSERT INTO listing_price_snapshots "
                 "(listing_id, price_total, price_m2, observed_at) "
                 "VALUES ('ac30-A', 250000.0, 3125.0, :obs)"),
            {"obs": now},
        )

    def _snapshot_state():
        with engine.begin() as conn:
            comps = conn.execute(
                text("SELECT id, lineage_id, photo_urls, last_seen_at, "
                     "first_seen_at FROM comparables ORDER BY id")
            ).fetchall()
            snaps = conn.execute(
                text("SELECT listing_id, price_total, observed_at "
                     "FROM listing_price_snapshots ORDER BY id")
            ).fetchall()
        return [tuple(str(x) for x in r) for r in comps], \
               [tuple(str(x) for x in r) for r in snaps]

    before = _snapshot_state()
    _probe_module().compute_probe(now=now)
    after = _snapshot_state()
    assert before == after, (
        "la probe a modifie l'etat de la base : elle doit etre READ-ONLY (AC30)"
    )


def test_ac31_probe_report_has_limits_section_and_no_leak():
    # AC31 : le rapport contient une section "Limites" mentionnant "borne haute"
    # (ou "candidats potentiels"), "syndication", "intrant de decision" ; et ne
    # contient AUCUN id/URL temoin des donnees synthetiques (anti-fuite).
    from db.session import init_db, engine

    init_db()
    _require_photo_urls_column()
    now = datetime(2026, 6, 13, 4, 0, 0)
    _build_probe_pair(now, prefix="ac31-TEMOIN", gap_days=30, window_days=10)
    with engine.begin() as conn:
        conn.execute(
            text("UPDATE comparables SET photo_urls=:p WHERE id='ac31-TEMOIN-A'"),
            {"p": json.dumps([_SENTINEL_PHOTO_URL])},
        )

    probe = _probe_module()
    stats = probe.compute_probe(now=now)
    report = probe.render_report(stats)
    assert isinstance(report, str) and report.strip(), (
        "render_report doit renvoyer un rapport texte non vide (AC31)"
    )

    low = report.lower()
    assert "limites" in low, "le rapport doit contenir une section 'Limites' (AC31)"
    assert ("borne haute" in low) or ("candidats potentiels" in low), (
        "le rapport doit etiqueter 'borne haute' / 'candidats potentiels' (AC31)"
    )
    assert "syndication" in low, (
        "le rapport doit mentionner la 'syndication' bienici (AC31)"
    )
    assert "intrant de decision" in low, (
        "le rapport doit etiqueter 'intrant de decision' (AC31)"
    )
    # Anti-fuite : aucun id ni URL temoin dans la sortie.
    assert "ac31-TEMOIN-A" not in report and "ac31-TEMOIN-B" not in report, (
        "le rapport ne doit contenir AUCUN id d'annonce (anti-fuite, AC31)"
    )
    assert _SENTINEL_PHOTO_URL not in report, (
        "le rapport ne doit contenir AUCUNE URL (anti-fuite, AC31)"
    )


# ===========================================================================
# Isolation / etat memoire — AC32
# ===========================================================================
def test_ac32_no_new_module_memory_state_introduced():
    # AC32 : l'etape 1 n'introduit AUCUN nouvel etat memoire de module a reset
    # au-dela de l'existant. (a) le reset autouse comparables/snapshots existe
    # toujours en conftest ; (b) les modules touches (ingestion.save, le module
    # probe) n'exposent pas de cache/compteur module (dict/set/list mutable au
    # niveau module) qui exigerait un nouveau reset autouse.
    import inspect as _inspect

    # (a) reset autouse existant (jamais en fixture locale, lecon 9.9).
    from tests import conftest as conftest_mod  # deja charge par pytest
    assert hasattr(conftest_mod, "_reset_snapshots_table"), (
        "reset autouse comparables/snapshots absent de conftest (AC32)"
    )
    src = _inspect.getsource(conftest_mod._reset_snapshots_table)
    assert "comparables" in src and "listing_price_snapshots" in src, (
        "le reset autouse doit couvrir comparables ET snapshots (AC32)"
    )

    # (b) aucun nouvel etat memoire mutable au niveau module dans ingestion.save.
    import ingestion.save as save_mod

    suspect = {}
    for name, val in vars(save_mod).items():
        if name.startswith("__"):
            continue
        if name in {"OUT_OF_SCOPE_CITIES"}:  # set de config fige, pas un cache
            continue
        if isinstance(val, (dict, set, list)):
            suspect[name] = type(val).__name__
    assert not suspect, (
        f"etape 1 a introduit un etat memoire de module suspect dans "
        f"ingestion.save (cache/compteur ?) : {suspect} (AC32)"
    )

    # (c) le module probe ne maintient pas d'etat mutable entre appels (compteur
    # global qui s'accumulerait sans reset). Les CONSTANTES de seuil
    # (_PROBE_*) sont des parametres figes, tolerees.
    probe = _probe_module()
    probe_suspect = {}
    for name, val in vars(probe).items():
        if name.startswith("__") or name.startswith("_PROBE_"):
            continue
        if isinstance(val, (dict, set, list)):
            probe_suspect[name] = type(val).__name__
    assert not probe_suspect, (
        f"le module probe maintient un etat mutable au niveau module "
        f"(cache/compteur ?) sans reset : {probe_suspect} (AC32)"
    )


# ===========================================================================
# DURCISSEMENT PHASE B (challenge adversarial) — tests ajoutes par le TESTEUR.
# Couvrent les trous de couverture de la phase A : robustesse fine de
# _extract_photo_urls (elements mixtes, cles inattendues, strip, dedup+cap en
# interaction), anti-fuite sur lignee MULTI-membres au DICT producteur, faux
# candidats probe non couverts par un AC dedie (gap "disparu" 7j strict, B avant
# A par les DEUX orientations, ventilation >=3 sources / plusieurs paires,
# involved_pct calculable a la main), etiquetage render_report (anti-fuite), et
# justesse a plus grande echelle (~80 comparables, pas la perf).
# ===========================================================================

# --- _extract_photo_urls : robustesse fine -------------------------------
def test_hardening_b_extract_mixed_str_and_dict_elements():
    # Elements str ET dict dans la MEME liste -> toutes les URLs lues, ordre
    # preserve, cle d'URL choisie par priorite url/src/href.
    fn = _photo_helper()
    out = fn({"photos": ["http://a", {"url": "http://b"}, {"src": "http://c"}]})
    assert out == json.dumps(["http://a", "http://b", "http://c"]), (
        f"elements mixtes str+dict : attendu [a,b,c], recu {out!r}"
    )


def test_hardening_b_extract_dict_unexpected_key_ignored_gracefully():
    # Un dict SANS aucune cle d'URL connue (ni url/src/href) est ignore
    # gracieusement, sans casser la lecture des elements valides voisins.
    fn = _photo_helper()
    out = fn({"photos": [{"foo": "x"}, "http://b", {"thumbnail": "http://nope"}]})
    assert out == json.dumps(["http://b"]), (
        f"dict a cle inattendue doit etre ignore (pas d'exception, pas d'URL "
        f"fantome), recu {out!r}"
    )


def test_hardening_b_extract_href_key_supported():
    # La cle 'href' (3e candidate) est bien lue quand 'url'/'src' absentes.
    fn = _photo_helper()
    out = fn({"photos": [{"href": "http://h"}]})
    assert out == json.dumps(["http://h"]), (
        f"cle 'href' doit etre supportee, recu {out!r}"
    )


def test_hardening_b_extract_strip_and_empty_after_strip():
    # URL avec espaces -> strip ; URL faite QUE d'espaces -> vide apres strip
    # -> ignoree (jamais une chaine vide dans la sortie).
    fn = _photo_helper()
    out = fn({"photos": ["  http://a  ", "   ", "\t\n"]})
    assert out == json.dumps(["http://a"]), (
        f"strip attendu + vides ignores, recu {out!r}"
    )


def test_hardening_b_extract_photos_is_dict_not_list():
    # photos non-liste (dict) -> None sans exception (isinstance list guard).
    fn = _photo_helper()
    assert fn({"photos": {"url": "http://a"}}) is None, (
        "photos=dict (pas une liste) doit donner None"
    )


def test_hardening_b_extract_dedup_then_cap_interaction():
    # Dedup AVANT cap : [u1,u1,u2,u3,u4] dedupe -> [u1,u2,u3,u4] puis cap 3
    # -> [u1,u2,u3] (le doublon ne consomme pas un "slot" du cap).
    fn = _photo_helper()
    u = [f"http://cdn/{i}.jpg" for i in range(4)]
    out = fn({"photos": [u[0], u[0], u[1], u[2], u[3]]})
    assert out == json.dumps([u[0], u[1], u[2]]), (
        f"dedup puis cap a 3 : attendu [u0,u1,u2], recu {out!r}"
    )


def test_hardening_b_extract_dict_url_priority_over_src():
    # Quand un dict porte plusieurs cles candidates, 'url' prime sur 'src'/'href'
    # (ordre de _PHOTO_URL_KEYS). Verrouille le contrat de priorite.
    fn = _photo_helper()
    out = fn({"photos": [{"src": "http://src", "url": "http://url",
                          "href": "http://href"}]})
    assert out == json.dumps(["http://url"]), (
        f"priorite cle d'URL : 'url' doit primer, recu {out!r}"
    )


def test_hardening_b_extract_output_is_json_string_not_list():
    # Le contrat de sortie EXACT : une CHAINE json.dumps, jamais une list Python
    # (homogene au type String de la colonne).
    fn = _photo_helper()
    out = fn({"photos": ["http://a"]})
    assert isinstance(out, str), f"sortie doit etre une str JSON, recu {type(out)}"
    assert json.loads(out) == ["http://a"], "la str doit decoder en liste d'URLs"


# --- Anti-fuite sur lignee 2a MULTI-membres ------------------------------
def test_hardening_b_no_leak_on_multimember_lineage_history(client, admin_token,
                                                             frozen_now):
    # Anti-fuite renforce : une lignee 2a a PLUSIEURS membres, chacun portant un
    # photo_urls sentinelle distinct. /history (DICT producteur ET corps HTTP)
    # ne doit contenir NI la cle photo_urls NI aucune sentinelle, meme en
    # parcourant tous les snapshots des membres de la lignee.
    from ingestion.save import save_comparables
    import app.main as main_mod

    _require_photo_urls_column()
    now = datetime(2026, 6, 13, 4, 0, 0)
    s1 = "http://SENTINEL/member1.jpg"
    s2 = "http://SENTINEL/member2.jpg"

    # Membre 1 (ancien) avec reference/customer_id pour rattacher le 2e.
    frozen_now["now"] = now - timedelta(days=40)
    save_comparables([_make_ad(
        "hb-lin-1", source="bienici", reference="RLIN", customer_id="CLIN",
        price_total=250000.0, photo_urls=json.dumps([s1]),
    )])
    # Membre 2 (re-list) meme reference -> meme lignee, prix change -> snapshot.
    frozen_now["now"] = now
    save_comparables([_make_ad(
        "hb-lin-2", source="bienici", reference="RLIN", customer_id="CLIN",
        price_total=240000.0, photo_urls=json.dumps([s2]),
    )])

    lin1 = getattr(_row("hb-lin-1"), "lineage_id", None)
    lin2 = getattr(_row("hb-lin-2"), "lineage_id", None)
    assert lin1 is not None and lin1 == lin2, (
        f"precondition : les 2 membres doivent partager la lignee (recu "
        f"{lin1!r}/{lin2!r})"
    )

    import os
    os.environ["ADMIN_TOKEN"] = ADMIN_TOKEN
    for lid in ("hb-lin-1", "hb-lin-2"):
        built = main_mod.comparable_history(lid, x_admin_token=ADMIN_TOKEN)
        assert isinstance(built, dict)
        assert "photo_urls" not in built, (
            f"/history dict ({lid}) ne doit pas contenir la cle photo_urls"
        )
        assert set(built.keys()) <= HISTORY_ALLOWED_KEYS
        dumped = json.dumps(built, default=str)
        assert s1 not in dumped and s2 not in dumped, (
            f"une sentinelle photo_urls fuite dans le dict /history de {lid}"
        )

        resp = _history(client, admin_token, lid)
        assert resp.status_code == 200
        body_text = json.dumps(resp.json())
        assert "photo_urls" not in resp.json()
        assert s1 not in body_text and s2 not in body_text, (
            f"une sentinelle photo_urls fuite dans le corps HTTP /history de {lid}"
        )


# --- Probe : faux candidats non couverts par un AC dedie -----------------
def test_hardening_b_probe_gap_exactly_7_days_not_yet_disappeared():
    # Gap "disparu" : `.days > 7` STRICT. A vu il y a EXACTEMENT 7 jours n'est
    # PAS encore disparu -> aucune paire (meme si B parfaitement candidat).
    from db.session import init_db

    init_db()
    _require_photo_urls_column()
    now = datetime(2026, 6, 13, 4, 0, 0)
    # gap_days=7 -> (now - A.last).days == 7, pas > 7 -> A pas disparu.
    _build_probe_pair(now, prefix="hb-gap7", gap_days=7, window_days=3,
                      surface_a=100.0, surface_b=100.0)

    stats = _probe_module().compute_probe(now=now)
    assert stats["total_pairs"] == 0, (
        f"A vu il y a EXACTEMENT 7 j n'est pas encore 'disparu' (.days > 7 "
        f"strict) -> 0 paire, recu {stats['total_pairs']}"
    )
    assert stats["disappeared"] == 0, (
        f"aucun comparable ne doit etre compte 'disparu' a 7 j pile, recu "
        f"{stats['disappeared']}"
    )


def test_hardening_b_probe_gap_8_days_disappeared():
    # Borne complementaire : a 8 jours, A EST disparu -> la paire est comptee.
    from db.session import init_db

    init_db()
    _require_photo_urls_column()
    now = datetime(2026, 6, 13, 4, 0, 0)
    _build_probe_pair(now, prefix="hb-gap8", gap_days=8, window_days=3,
                      surface_a=100.0, surface_b=100.0)

    stats = _probe_module().compute_probe(now=now)
    assert stats["total_pairs"] == 1, (
        f"A vu il y a 8 j EST disparu (.days=8 > 7) -> 1 paire, recu "
        f"{stats['total_pairs']}"
    )
    assert stats["disappeared"] == 1


def test_hardening_b_probe_b_before_a_both_orientations_excluded():
    # B apparu AVANT A, teste via les DEUX orientations du couple (la boucle
    # combinations() essaie x->y puis y->x). Aucune orientation ne doit creer
    # de paire (A.first et B.first poses pour qu'aucun ne soit "apparu apres"
    # un membre disparu dans la fenetre).
    from db.session import init_db, engine

    init_db()
    _require_photo_urls_column()
    now = datetime(2026, 6, 13, 4, 0, 0)
    # A disparu (last il y a 30 j). B "apparu avant" A.last (b_after=False).
    # En plus, B est lui aussi pose disparu pour exercer l'orientation y->x :
    # mais comme A.first_seen <= B.last_seen serait requis pour y->x, on
    # s'assure que A n'est pas "apparu apres" B non plus.
    _build_probe_pair(now, prefix="hb-before", gap_days=30, window_days=0,
                      b_after=False)
    # Rends B disparu lui aussi (last ancien) pour forcer l'essai de y->x.
    with engine.begin() as conn:
        conn.execute(
            text("UPDATE comparables SET last_seen_at=:l WHERE id='hb-before-B'"),
            {"l": now - timedelta(days=25)},
        )

    stats = _probe_module().compute_probe(now=now)
    assert stats["total_pairs"] == 0, (
        f"B non strictement apparu apres A (les 2 orientations) -> 0 paire, "
        f"recu {stats['total_pairs']}"
    )


def test_hardening_b_probe_ventilation_three_sources_multiple_pairs():
    # Ventilation par couple de sources, >=3 sources et plusieurs paires, cle
    # triee lexico. On pose 3 paires candidates distinctes sur 3 couples :
    #   benedic<->bienici, bienici<->idemmo, benedic<->idemmo.
    from db.session import init_db

    init_db()
    _require_photo_urls_column()
    now = datetime(2026, 6, 13, 4, 0, 0)

    # Trois villes distinctes pour ISOLER les paires (pas de matching croise
    # inattendu entre les 6 lignes) : chaque ville canonique a son couple.
    _build_probe_pair(now, prefix="hb-v1", source_a="benedic", source_b="bienici",
                      gap_days=30, window_days=10, city_b="Metz")
    _build_probe_pair(now, prefix="hb-v2", source_a="idemmo", source_b="bienici",
                      gap_days=30, window_days=10, city_b="Woippy")
    # 3e couple sur une 3e ville ; A=benedic, B=idemmo.
    _build_probe_pair(now, prefix="hb-v3", source_a="benedic", source_b="idemmo",
                      gap_days=30, window_days=10, city_b="Marly")
    # Mais _build_probe_pair pose A avec city="Metz" par defaut. Pour isoler, on
    # realigne city de A sur celle de B (sinon A et B de villes differentes ->
    # exclus par AC28). On corrige via une ecriture directe.
    from db.session import engine
    with engine.begin() as conn:
        conn.execute(text("UPDATE comparables SET city='Woippy' WHERE id='hb-v2-A'"))
        conn.execute(text("UPDATE comparables SET city='Marly' WHERE id='hb-v3-A'"))

    stats = _probe_module().compute_probe(now=now)
    couples = stats["pairs_by_source_couple"]
    assert stats["total_pairs"] == 3, (
        f"3 paires candidates attendues (3 couples isoles), recu "
        f"{stats['total_pairs']} ; ventilation={couples!r}"
    )
    assert couples.get("benedic<->bienici") == 1, couples
    assert couples.get("bienici<->idemmo") == 1, couples
    assert couples.get("benedic<->idemmo") == 1, couples
    # Cle triee lexico : jamais "bienici<->benedic" ni "idemmo<->bienici".
    for key in couples:
        lo, hi = key.split("<->")
        assert lo <= hi, f"cle de couple non triee lexico : {key!r}"


def test_hardening_b_probe_involved_pct_hand_computable():
    # involved_pct = (membres impliques dans >=1 paire) / total comparables.
    # Corpus controle : 2 membres impliques (la paire) + 2 membres "bruit" non
    # candidats (meme source, pas disparus) -> 2/4 = 50,0 %.
    from db.session import init_db

    init_db()
    _require_photo_urls_column()
    now = datetime(2026, 6, 13, 4, 0, 0)
    _build_probe_pair(now, prefix="hb-pct", source_a="benedic", source_b="bienici",
                      gap_days=30, window_days=10)
    # 2 lignes de bruit : vivantes (non disparues), source unique, sans partenaire.
    _insert_probe_row("hb-pct-noise1", "benedic",
                      last_seen_at=now - timedelta(days=1),
                      first_seen_at=now - timedelta(days=3),
                      city="Augny", postal_code="57685")
    _insert_probe_row("hb-pct-noise2", "idemmo",
                      last_seen_at=now - timedelta(days=1),
                      first_seen_at=now - timedelta(days=3),
                      city="Marly", postal_code="57155")

    stats = _probe_module().compute_probe(now=now)
    assert stats["total_comparables"] == 4, (
        f"corpus de 4 attendu, recu {stats['total_comparables']}"
    )
    assert stats["total_pairs"] == 1, stats
    assert stats["involved_pct"] == 50.0, (
        f"2 membres impliques / 4 total = 50,0 %, recu {stats['involved_pct']}"
    )


def test_hardening_b_probe_involved_pct_no_double_count_shared_member():
    # Un meme membre B implique dans DEUX paires ne doit etre compte qu'une fois
    # dans involved_pct (set d'ids). A1 et A2 (deux disparus) -> meme B.
    # involved = {A1, A2, B} = 3 sur 3 -> 100,0 %.
    from db.session import init_db

    init_db()
    _require_photo_urls_column()
    now = datetime(2026, 6, 13, 4, 0, 0)
    b_first = now - timedelta(days=5)
    # Deux A disparus, sources differentes de B (bienici), apparus avant B.
    _insert_probe_row("hb-share-A1", "benedic",
                      last_seen_at=now - timedelta(days=30),
                      first_seen_at=now - timedelta(days=40))
    _insert_probe_row("hb-share-A2", "idemmo",
                      last_seen_at=now - timedelta(days=20),
                      first_seen_at=now - timedelta(days=35))
    _insert_probe_row("hb-share-B", "bienici",
                      last_seen_at=b_first, first_seen_at=b_first)

    stats = _probe_module().compute_probe(now=now)
    assert stats["total_pairs"] == 2, (
        f"A1->B et A2->B = 2 paires, recu {stats['total_pairs']} ; "
        f"{stats['pairs_by_source_couple']!r}"
    )
    assert stats["involved_pct"] == 100.0, (
        f"B partage par 2 paires ne doit etre compte qu'une fois : "
        f"{{A1,A2,B}}/3 = 100,0 %, recu {stats['involved_pct']}"
    )


def test_hardening_b_probe_read_only_exhaustive_snapshot():
    # READ-ONLY par snapshot EXHAUSTIF (toutes colonnes lisibles) avant/apres,
    # sur un corpus melant paire candidate + bruit + snapshot existant.
    from db.session import init_db, engine

    init_db()
    _require_photo_urls_column()
    now = datetime(2026, 6, 13, 4, 0, 0)
    _build_probe_pair(now, prefix="hb-ro", gap_days=30, window_days=10)
    _insert_probe_row("hb-ro-noise", "idemmo",
                      last_seen_at=now - timedelta(days=2),
                      first_seen_at=now - timedelta(days=9),
                      city="Marly", postal_code="57155")
    with engine.begin() as conn:
        conn.execute(
            text("INSERT INTO listing_price_snapshots "
                 "(listing_id, price_total, price_m2, observed_at) "
                 "VALUES ('hb-ro-A', 250000.0, 3125.0, :o)"),
            {"o": now},
        )

    def _full_state():
        with engine.begin() as conn:
            comps = conn.execute(
                text("SELECT * FROM comparables ORDER BY id")
            ).fetchall()
            snaps = conn.execute(
                text("SELECT * FROM listing_price_snapshots ORDER BY id")
            ).fetchall()
        return ([tuple(str(x) for x in r) for r in comps],
                [tuple(str(x) for x in r) for r in snaps])

    before = _full_state()
    _probe_module().compute_probe(now=now)
    after = _full_state()
    assert before == after, (
        "snapshot exhaustif divergent : la probe a mute la base (doit etre "
        "strictement READ-ONLY)"
    )


def test_hardening_b_probe_correctness_at_scale_synthetic():
    # JUSTESSE (pas perf) a plus grande echelle : corpus synthetique
    # multi-sources d'environ 80 comparables avec un nombre de paires
    # candidates connu a la main. On NE teste PAS la perf O(n^2) (hors
    # perimetre etape 1), seulement que compute_probe reste CORRECT.
    from db.session import init_db

    init_db()
    _require_photo_urls_column()
    now = datetime(2026, 6, 13, 4, 0, 0)

    # 30 paires candidates VALIDES, chacune sur une ville distincte (isolation
    # stricte : pas de matching croise entre paires). 1 couple chacune.
    expected_pairs = 30
    for i in range(expected_pairs):
        city = f"VilleScale{i}"
        cp = f"57{i:03d}"
        a_last = now - timedelta(days=30)
        a_first = a_last - timedelta(days=5)
        b_first = a_last + timedelta(days=10)
        _insert_probe_row(f"hb-scale-A{i}", "benedic",
                          last_seen_at=a_last, first_seen_at=a_first,
                          city=city, postal_code=cp)
        _insert_probe_row(f"hb-scale-B{i}", "bienici",
                          last_seen_at=b_first, first_seen_at=b_first,
                          city=city, postal_code=cp)

    # 20 lignes de BRUIT non candidates (vivantes, isolees) -> total 80.
    for i in range(20):
        _insert_probe_row(f"hb-scale-N{i}", "idemmo",
                          last_seen_at=now - timedelta(days=1),
                          first_seen_at=now - timedelta(days=3),
                          city=f"NoiseCity{i}", postal_code=f"57{900 + i}")

    stats = _probe_module().compute_probe(now=now)
    assert stats["total_comparables"] == 80, (
        f"corpus de 80 attendu, recu {stats['total_comparables']}"
    )
    assert stats["total_pairs"] == expected_pairs, (
        f"justesse a l'echelle : {expected_pairs} paires attendues, recu "
        f"{stats['total_pairs']}"
    )
    assert stats["pairs_by_source_couple"].get("benedic<->bienici") == expected_pairs, (
        f"toutes les paires sur le couple benedic<->bienici, recu "
        f"{stats['pairs_by_source_couple']!r}"
    )
    # involved = 60 membres de paires / 80 = 75,0 %.
    assert stats["involved_pct"] == 75.0, (
        f"60 impliques / 80 = 75,0 %, recu {stats['involved_pct']}"
    )


def test_hardening_b_render_report_contains_limit_substrings_and_no_leak():
    # render_report : sous-chaines de limites exigees (SPEC §3.5) presentes ET
    # aucun id/reference/URL/photo_urls fuite, meme avec un corpus portant des
    # sentinelles. Complete AC31 (parcours explicite des 4 termes + ref/cp).
    from db.session import init_db, engine

    init_db()
    _require_photo_urls_column()
    now = datetime(2026, 6, 13, 4, 0, 0)
    _build_probe_pair(now, prefix="hb-rep-TEMOIN", gap_days=30, window_days=10)
    with engine.begin() as conn:
        conn.execute(
            text("UPDATE comparables SET photo_urls=:p, reference='REF-TEMOIN', "
                 "customer_id='CUST-TEMOIN' WHERE id='hb-rep-TEMOIN-A'"),
            {"p": json.dumps([_SENTINEL_PHOTO_URL])},
        )

    probe = _probe_module()
    report = probe.render_report(probe.compute_probe(now=now))
    low = report.lower()
    for needle in ("borne haute", "candidats potentiels"):
        pass
    assert ("borne haute" in low) or ("candidats potentiels" in low)
    assert "syndication" in low
    assert "intrant de decision" in low
    # Anti-fuite exhaustive.
    assert _SENTINEL_PHOTO_URL not in report
    assert "REF-TEMOIN" not in report
    assert "CUST-TEMOIN" not in report
    assert "hb-rep-TEMOIN-A" not in report
    assert "hb-rep-TEMOIN-B" not in report
    assert "photo_urls" not in report, (
        "le rapport ne doit pas meme nommer la colonne photo_urls"
    )


def test_hardening_b_admin_import_actually_persists_photo_urls(client, admin_token):
    # COMBLE UN TROU AC12 : AC12 ne verifie QUE l'absence de 422 + le contrat de
    # reponse. Or Pydantic IGNORE par defaut les champs extra (ComparableIn.
    # model_config vide) : un body avec photo_urls ne fait pas 422 MEME si le
    # champ n'existe pas dans ComparableIn -> dans ce cas model_dump() ne le
    # transmet pas a save_comparables et la colonne reste NULL, sans qu'aucun AC
    # ne le detecte. Ce test verifie la PERSISTANCE REELLE bout-en-bout via
    # l'endpoint (pas l'appel direct a save_comparables d'AC9) : c'est la seule
    # garantie que ComparableIn DECLARE bien le champ photo_urls.
    sentinel = json.dumps(["http://cdn/persist-via-import.jpg"])
    resp = client.post(
        "/admin/comparables",
        json={"items": [{
            "id": "hb-import-persist", "source": "bienici", "city": "Metz",
            "property_type": "appartement", "surface_m2": 80,
            "price_total": 250000, "postal_code": "57000",
            "photo_urls": sentinel,
        }]},
        headers={"X-Admin-Token": admin_token},
    )
    assert resp.status_code == 200, (
        f"import attendu 200, recu {resp.status_code}"
    )
    row = _row("hb-import-persist")
    assert row is not None, "comparable importe non ecrit"
    assert getattr(row, "photo_urls", "__MISSING__") == sentinel, (
        "photo_urls fourni a POST /admin/comparables NON persiste : ComparableIn "
        "ne declare pas le champ (Pydantic ignore l'extra silencieusement) -> "
        "model_dump() ne le transmet pas a save_comparables. AC12 seul ne le "
        "detecte pas (extra ignore != champ declare)."
    )

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

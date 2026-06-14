"""Robustesse d'ingestion a l'echelle (juin 2026).

Contexte : l'elargissement de la collecte bien'ici a la couronne a ~double le
volume pousse (~30k). Un run a echoue a l'ingestion (timeout du batch puis 500)
car _find_lineage_candidate (ingestion/save.py) filtre par `reference` egale pour
CHAQUE annonce neuve, sur une colonne NON indexee -> balayage de table par
insertion (O(n*m)). Correctif : index sur comparables.reference (+ migration
idempotente) et retry/backoff cote push_comparables.

Ces tests verrouillent les deux volets : presence de l'index apres init_db, et
resilience du client (reessais avant d'abandonner un batch).
"""

from sqlalchemy import inspect

import jobs.push_comparables as push


# ---------------------------------------------------------------------------
# Volet 1 : index sur `reference` cree par init_db (cause racine du O(n*m)).
# ---------------------------------------------------------------------------

def test_reference_index_exists_after_init_db():
    """init_db (appele en fixture session) doit avoir pose un index couvrant
    `reference` sur la table comparables — sinon la recherche de lignee balaie
    toute la table a chaque insertion."""
    from db.session import engine

    indexes = inspect(engine).get_indexes("comparables")
    ref_indexes = [ix for ix in indexes if ix.get("column_names") == ["reference"]]
    assert ref_indexes, (
        "aucun index sur la colonne `reference` ; "
        f"index presents : {[ix['column_names'] for ix in indexes]}"
    )


def test_lineage_index_still_present_no_regression():
    """L'index lineage_id existant ne doit pas avoir ete perdu par la migration."""
    from db.session import engine

    indexes = inspect(engine).get_indexes("comparables")
    assert any(ix.get("column_names") == ["lineage_id"] for ix in indexes)


def test_migration_idempotent_rerun():
    """Re-jouer la migration (CREATE INDEX IF NOT EXISTS) ne doit pas lever."""
    from db.session import init_db

    init_db()
    init_db()  # second passage : idempotence (IF NOT EXISTS)


# ---------------------------------------------------------------------------
# Volet 2 : retry/backoff cote client (defense en profondeur sur le 500/timeout).
# ---------------------------------------------------------------------------

def test_post_batch_retries_then_succeeds(monkeypatch):
    """Un batch transitoirement en echec (2 erreurs) doit reussir au 3e essai,
    sans propager l'exception."""
    monkeypatch.setattr(push.time, "sleep", lambda *_: None)
    calls = {"n": 0}

    def flaky(_url, _token, _items):
        calls["n"] += 1
        if calls["n"] < 3:
            raise TimeoutError("read timed out")
        return {"saved": 7}

    monkeypatch.setattr(push, "_post_batch", flaky)

    result = push._post_batch_with_retry("http://x", "t", [{"id": "a"}], 0)
    assert result == {"saved": 7}
    assert calls["n"] == 3  # 2 echecs + 1 succes


def test_post_batch_gives_up_after_max_retries(monkeypatch):
    """Apres MAX_RETRIES echecs, l'exception est relevee (le batch sera compte
    en echec par l'appelant) et _post_batch est appele exactement MAX_RETRIES fois."""
    monkeypatch.setattr(push.time, "sleep", lambda *_: None)
    calls = {"n": 0}

    def always_fail(_url, _token, _items):
        calls["n"] += 1
        raise RuntimeError("HTTP 500")

    monkeypatch.setattr(push, "_post_batch", always_fail)

    try:
        push._post_batch_with_retry("http://x", "t", [{"id": "a"}], 0)
        assert False, "devait relever apres MAX_RETRIES"
    except RuntimeError:
        pass
    assert calls["n"] == push.MAX_RETRIES


class _FakeListing:
    def __init__(self, d):
        self._d = d

    def to_dict(self):
        return dict(self._d)


def _valid_item(i: int) -> dict:
    return {
        "id": f"id-{i}", "source": "bienici", "city": "Metz",
        "property_type": "appartement", "surface_m2": 80, "price_total": 240000,
    }


def test_main_transient_batch_recovers_exit_0(monkeypatch):
    """Bout-en-bout : un batch qui echoue une fois puis passe au retry ne doit
    PAS faire echouer le run (exit 0)."""
    monkeypatch.setattr(push.time, "sleep", lambda *_: None)
    monkeypatch.setenv("BACKEND_URL", "http://backend")
    monkeypatch.setenv("ADMIN_TOKEN", "tok")
    monkeypatch.setattr(push, "load_all", lambda: ["bienici"])
    monkeypatch.setattr(push, "run_all", lambda: [_FakeListing(_valid_item(0))])

    calls = {"n": 0}

    def flaky(_url, _token, items):
        calls["n"] += 1
        if calls["n"] == 1:
            raise TimeoutError("read timed out")
        return {"saved": len(items)}

    monkeypatch.setattr(push, "_post_batch", flaky)

    assert push.main() == 0


def test_main_persistent_failure_exit_1(monkeypatch):
    """Bout-en-bout : un batch qui echoue tous ses essais laisse le run en echec
    (exit 1) — le signal rouge du job est conserve."""
    monkeypatch.setattr(push.time, "sleep", lambda *_: None)
    monkeypatch.setenv("BACKEND_URL", "http://backend")
    monkeypatch.setenv("ADMIN_TOKEN", "tok")
    monkeypatch.setattr(push, "load_all", lambda: ["bienici"])
    monkeypatch.setattr(push, "run_all", lambda: [_FakeListing(_valid_item(0))])
    monkeypatch.setattr(push, "_post_batch",
                        lambda *_a, **_k: (_ for _ in ()).throw(RuntimeError("500")))

    assert push.main() == 1

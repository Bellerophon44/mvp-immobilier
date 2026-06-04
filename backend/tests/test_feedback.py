"""Tests du critère 9.7 — collecte de feedback utilisateur (POST /feedback).

Contrat : docs/specs/9.7-SPEC.md §4 (12 critères d'acceptation).
Les imports de db.models.Feedback échouent tant que le modèle n'existe pas :
c'est le rouge légitime attendu en phase tests-first.
"""

EXPECTED_COLUMNS = {
    "id",
    "rating",
    "comment",
    "analysis_id",
    "global_score",
    "verdict",
    "prompt_variant",
    "created_at",
}

FORBIDDEN_COLUMNS = {"ip", "client_ip", "user_id", "session_id"}


# --- Critère 1 : golden path complet -> 201 + {"status": "ok"} -----------
def test_feedback_golden_path(client):
    resp = client.post(
        "/feedback",
        json={
            "rating": 5,
            "comment": "Tres clair",
            "analysis_id": "11111111-1111-1111-1111-111111111111",
            "global_score": 82,
            "verdict": "Coherence forte",
        },
    )
    assert resp.status_code == 201
    assert resp.json() == {"status": "ok"}


# --- Critère 2 : rating seul (champs D2 optionnels) -> 201 ---------------
def test_feedback_rating_only(client):
    resp = client.post("/feedback", json={"rating": 3})
    assert resp.status_code == 201
    assert resp.json() == {"status": "ok"}


# --- Critère 3 : rating manquant -> 422 ----------------------------------
def test_feedback_missing_rating(client):
    resp = client.post("/feedback", json={"comment": "test"})
    assert resp.status_code == 422


# --- Critère 4 : rating hors bornes (haut) -> 422 ------------------------
def test_feedback_rating_too_high(client):
    resp = client.post("/feedback", json={"rating": 6})
    assert resp.status_code == 422


# --- Critère 5 : rating hors bornes (bas / zéro) -> 422 ------------------
def test_feedback_rating_zero(client):
    resp = client.post("/feedback", json={"rating": 0})
    assert resp.status_code == 422


# --- Critère 6 : rating de type invalide -> 422 --------------------------
def test_feedback_rating_wrong_type(client):
    resp = client.post("/feedback", json={"rating": "bien"})
    assert resp.status_code == 422


# --- Critère 7 : commentaire trop long (1001 chars) -> 422 (pas tronqué) -
def test_feedback_comment_too_long(client):
    resp = client.post("/feedback", json={"rating": 4, "comment": "x" * 1001})
    assert resp.status_code == 422


# --- Critère 8 : corps vide {} -> 422 ------------------------------------
def test_feedback_empty_body(client):
    resp = client.post("/feedback", json={})
    assert resp.status_code == 422


# --- Critère 9 : persistance vérifiable ----------------------------------
def test_feedback_persisted(client):
    from db.models import Feedback
    from db.session import SessionLocal

    db = SessionLocal()
    try:
        before = db.query(Feedback).count()
    finally:
        db.close()

    payload = {
        "rating": 4,
        "comment": "Un retour utile",
        "analysis_id": "22222222-2222-2222-2222-222222222222",
        "global_score": 67,
        "verdict": "A creuser",
    }
    resp = client.post("/feedback", json=payload)
    assert resp.status_code == 201

    db = SessionLocal()
    try:
        after = db.query(Feedback).count()
        assert after == before + 1
        row = (
            db.query(Feedback)
            .filter(Feedback.analysis_id == payload["analysis_id"])
            .one()
        )
        assert row.rating == payload["rating"]
        assert row.comment == payload["comment"]
        assert row.analysis_id == payload["analysis_id"]
        assert row.global_score == payload["global_score"]
        assert row.verdict == payload["verdict"]
        assert row.created_at is not None
    finally:
        db.close()


# --- Critère 10 : aucune colonne IP / identifiant ------------------------
def test_feedback_no_pii_columns():
    from db.models import Feedback

    columns = {c.name for c in Feedback.__table__.columns}
    assert columns == EXPECTED_COLUMNS
    assert not (columns & FORBIDDEN_COLUMNS)


# --- Challenge B : bornes exactes incluses (rating 1 et 5) -> 201 --------
def test_feedback_rating_lower_bound_included(client):
    resp = client.post("/feedback", json={"rating": 1})
    assert resp.status_code == 201
    assert resp.json() == {"status": "ok"}


def test_feedback_rating_upper_bound_included(client):
    resp = client.post("/feedback", json={"rating": 5})
    assert resp.status_code == 201
    assert resp.json() == {"status": "ok"}


# --- Challenge B : commentaire a la borne exacte (1000) -> 201 -----------
def test_feedback_comment_exactly_1000_accepted(client):
    resp = client.post("/feedback", json={"rating": 4, "comment": "x" * 1000})
    assert resp.status_code == 201
    assert resp.json() == {"status": "ok"}


# --- Challenge B : rating float non entier (3.5) -> 422 (Pydantic, pas 500)
def test_feedback_rating_float_rejected(client):
    resp = client.post("/feedback", json={"rating": 3.5})
    assert resp.status_code == 422


# --- Challenge B : rating negatif -> 422 (pas de crash 500) --------------
def test_feedback_rating_negative_rejected(client):
    resp = client.post("/feedback", json={"rating": -1})
    assert resp.status_code == 422


# --- Challenge B : comment absent persiste None (pas "") -----------------
def test_feedback_absent_comment_persisted_as_none(client):
    from db.models import Feedback
    from db.session import SessionLocal

    marker = "33333333-3333-3333-3333-333333333333"
    resp = client.post("/feedback", json={"rating": 3, "analysis_id": marker})
    assert resp.status_code == 201

    db = SessionLocal()
    try:
        row = db.query(Feedback).filter(Feedback.analysis_id == marker).one()
        assert row.comment is None
    finally:
        db.close()


# --- Challenge B : rating float entier (3.0) ne crashe pas (pas de 500) ---
def test_feedback_rating_float_integer_no_500(client):
    # JSON ne distingue pas 3 de 3.0 ; le contrat ne doit jamais renvoyer 500.
    resp = client.post("/feedback", json={"rating": 3.0})
    assert resp.status_code in (201, 422)
    assert resp.status_code != 500


# --- Challenge B : comment vide explicite "" persiste tel quel (pas force) -
def test_feedback_empty_comment_persisted_verbatim(client):
    from db.models import Feedback
    from db.session import SessionLocal

    marker = "44444444-4444-4444-4444-444444444444"
    resp = client.post(
        "/feedback", json={"rating": 3, "comment": "", "analysis_id": marker}
    )
    assert resp.status_code == 201

    db = SessionLocal()
    try:
        row = db.query(Feedback).filter(Feedback.analysis_id == marker).one()
        assert row.comment == ""
    finally:
        db.close()


# --- Challenge B : le contenu du commentaire n'est jamais journalise -------
def test_feedback_comment_never_logged(client, caplog):
    import logging

    secret = "donnee-perso-a-ne-pas-logger-0612345678"
    with caplog.at_level(logging.DEBUG):
        resp = client.post(
            "/feedback", json={"rating": 5, "comment": secret}
        )
    assert resp.status_code == 201
    assert secret not in caplog.text


# --- Challenge B : schema SQL reel sans colonne PII (PRAGMA, pas ORM) -----
def test_feedback_sql_schema_has_no_pii(client):
    from db.session import engine
    from sqlalchemy import text

    with engine.connect() as conn:
        cols = {r[1] for r in conn.execute(text("PRAGMA table_info(feedback)"))}
    assert cols == EXPECTED_COLUMNS
    assert not (cols & FORBIDDEN_COLUMNS)


# --- Critère 11 : endpoint public (sans X-Admin-Token) -> 201 ------------
def test_feedback_public_no_admin_token(client):
    resp = client.post("/feedback", json={"rating": 2})
    assert resp.status_code == 201
    assert "x-admin-token" not in {k.lower() for k in resp.request.headers}
    assert resp.json() == {"status": "ok"}


# --- Critère 12 : contrat /analyze intact (test léger, non dupliqué) -----
def test_analyze_contract_unchanged(client):
    resp = client.post("/analyze", json={})
    assert resp.status_code == 400

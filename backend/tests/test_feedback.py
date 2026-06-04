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

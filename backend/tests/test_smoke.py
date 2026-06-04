def test_health_ok(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_root_advertises_service(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert resp.json()["service"] == "mvp-immobilier"


def test_analyze_requires_input(client):
    resp = client.post("/analyze", json={})
    assert resp.status_code == 400

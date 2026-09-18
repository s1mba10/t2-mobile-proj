def test_health_exposes_backend_instance(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.headers["x-backend-instance"] == "test-node"
    assert response.json()["instance_id"] == "test-node"
    assert response.json()["tls_terminated_here"] is False


def test_instance_endpoint(client):
    response = client.get("/api/v1/instance")
    assert response.status_code == 200
    body = response.json()
    assert body["hostname"]
    assert body["pid"] > 0


def test_home_page_renders_brand(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "другие правила" in response.text
    assert "test-node" in response.text


def test_tariffs_seeded(client):
    response = client.get("/api/v1/tariffs")
    assert response.status_code == 200
    names = {item["name"] for item in response.json()}
    assert "Мой онлайн" in names
    assert "Безлимит" in names


def test_login_uses_shared_session_cookie(client):
    response = client.post("/api/v1/auth/login", json={"phone": "79001234567", "pin": "1234"})
    assert response.status_code == 200
    assert "t2_session" in response.cookies
    me = client.get("/api/v1/account")
    assert me.status_code == 200
    assert me.json()["full_name"] == "Иван Петров"


def test_topup_persists_balance(client):
    client.post("/api/v1/auth/login", json={"phone": "79001234567", "pin": "1234"})
    before = client.get("/api/v1/account")
    start = float(before.json()["balance"])
    topped = client.post("/api/v1/account/topup", json={"amount": "100", "method": "sbp"})
    assert topped.status_code == 200
    after = client.get("/api/v1/account")
    assert float(after.json()["balance"]) == start + 100


def test_async_coverage_scan(client):
    response = client.get("/api/v1/coverage/scan")
    assert response.status_code == 200
    payload = response.json()
    assert len(payload["results"]) >= 7
    assert payload["served_by"]["instance_id"] == "test-node"


def test_status_page_identifies_node(client):
    response = client.get("/status")
    assert response.status_code == 200
    assert "test-node" in response.text

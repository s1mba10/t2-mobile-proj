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


async def test_second_node_startup_does_not_duplicate_data(client):
    """Повторная подготовка схемы — это старт второй ноды на той же БД."""
    from app.main import prepare_schema

    await prepare_schema()
    await prepare_schema()

    tariffs = client.get("/api/v1/tariffs").json()
    assert len(tariffs) == 6
    assert len({item["slug"] for item in tariffs}) == 6


async def test_dependency_wait_retries_until_ready():
    """Нода ждёт хранилище, а не падает на первой ошибке подключения."""
    from app.main import _wait_for

    attempts = {"n": 0}

    async def flaky() -> None:
        attempts["n"] += 1
        if attempts["n"] < 3:
            raise ConnectionRefusedError("storage is still booting")

    await _wait_for("Тестовое хранилище", flaky)
    assert attempts["n"] == 3


def test_metrics_endpoint_labels_by_node(client):
    """Метрики помечены идентификатором ноды — по ним видно распределение запросов."""
    client.get("/api/health")
    response = client.get("/api/metrics")

    assert response.status_code == 200
    assert "text/plain" in response.headers["content-type"]
    body = response.text
    assert 't2_instance_info{hostname=' in body
    assert 'instance_id="test-node"' in body
    assert "t2_http_requests_total" in body
    assert 'endpoint="/api/health"' in body


def test_metrics_collapse_path_parameters(client):
    """Город в пути сворачивается в шаблон, иначе растёт число временных рядов."""
    client.get("/api/v1/coverage/probe/Казань")
    body = client.get("/api/metrics").text

    assert 'endpoint="/api/v1/coverage/probe/{city}"' in body
    assert "Казань" not in body


def test_unhandled_exception_counted_as_server_error(client):
    """Падение обработчика должно попадать в метрики, иначе доля ошибок всегда нулевая."""
    from starlette.testclient import TestClient

    @client.app.get("/__boom__")
    async def _boom():
        raise RuntimeError("проверка учёта падений")

    raw = TestClient(client.app, raise_server_exceptions=False)
    assert raw.get("/__boom__").status_code == 500

    body = client.get("/api/metrics").text
    assert 'endpoint="/__boom__"' in body
    assert 'status="500"' in body

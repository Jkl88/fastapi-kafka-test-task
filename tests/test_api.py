from fastapi.testclient import TestClient
from urllib import error

import app.consumer as consumer_module
from app.config import settings
from app.main import app
import app.main as main_module


client = TestClient(app)


def test_healthcheck_returns_current_settings() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "kafka": settings.KAFKA_BOOTSTRAP_SERVERS,
        "topic": settings.KAFKA_TOPIC,
        "consumer_group": settings.KAFKA_CONSUMER_GROUP,
    }


def test_dashboard_page_returns_html() -> None:
    response = client.get("/dashboard")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "Дашборд консьюмеров" in response.text
    assert "publish-form" in response.text


def test_publish_calls_producer_and_returns_payload(monkeypatch) -> None:
    calls: list[tuple[str, dict[str, object]]] = []

    class StubProducer:
        def send_message(self, key: str, payload: dict[str, object]) -> None:
            calls.append((key, payload))

    monkeypatch.setattr(main_module, "producer_service", StubProducer())

    message = {
        "key": "user-1",
        "payload": {
            "event": "user_registered",
            "user_id": 1,
        },
    }

    response = client.post("/publish", json=message)

    assert response.status_code == 200
    assert response.json() == {
        "status": "sent",
        "topic": settings.KAFKA_TOPIC,
        "key": "user-1",
        "payload": {
            "event": "user_registered",
            "user_id": 1,
        },
    }
    assert calls == [("user-1", message["payload"])]


def test_publish_requires_key() -> None:
    response = client.post(
        "/publish",
        json={"payload": {"event": "missing_key"}},
    )

    assert response.status_code == 422


def test_publish_requires_payload_object() -> None:
    response = client.post(
        "/publish",
        json={"key": "user-1", "payload": "invalid"},
    )

    assert response.status_code == 422


def test_internal_consumer_event_updates_dashboard_snapshot() -> None:
    main_module.dashboard_store.reset()

    response = client.post(
        "/internal/consumer-events",
        json={
            "worker_name": "consumer_2",
            "partition": 1,
            "offset": 7,
            "key": "user-7",
            "value": {"event": "created", "user_id": 7},
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "accepted"
    assert body["snapshot"]["total_messages"] == 1
    assert body["snapshot"]["consumer_counts"]["consumer_2"] == 1
    assert body["snapshot"]["recent_events"][0]["worker_name"] == "consumer_2"


def test_dashboard_websocket_receives_initial_snapshot() -> None:
    main_module.dashboard_store.reset()

    with client.websocket_connect("/dashboard/ws") as websocket:
        snapshot = websocket.receive_json()

    assert snapshot["type"] == "snapshot"
    assert snapshot["total_messages"] == 0
    assert snapshot["consumer_counts"]["consumer_1"] == 0
    assert snapshot["consumer_counts"]["consumer_2"] == 0
    assert snapshot["consumer_counts"]["consumer_3"] == 0


def test_dashboard_websocket_receives_updates() -> None:
    main_module.dashboard_store.reset()

    with client.websocket_connect("/dashboard/ws") as websocket:
        initial_snapshot = websocket.receive_json()
        assert initial_snapshot["total_messages"] == 0

        response = client.post(
            "/internal/consumer-events",
            json={
                "worker_name": "consumer_3",
                "partition": 0,
                "offset": 3,
                "key": "same-key",
                "value": {"event": "updated", "user_id": 3},
            },
        )

        assert response.status_code == 200
        updated_snapshot = websocket.receive_json()

    assert updated_snapshot["total_messages"] == 1
    assert updated_snapshot["consumer_counts"]["consumer_3"] == 1
    assert updated_snapshot["recent_events"][0]["key"] == "same-key"


def test_consumer_report_failures_do_not_raise(monkeypatch) -> None:
    monkeypatch.setattr(
        consumer_module.settings,
        "CONSUMER_REPORT_URL",
        "http://example.invalid/internal/consumer-events",
    )

    def raise_url_error(*args, **kwargs):
        raise error.URLError("network down")

    monkeypatch.setattr(consumer_module.request, "urlopen", raise_url_error)

    consumer_module.report_processed_message(
        worker_name="consumer_1",
        partition=2,
        offset=11,
        key="user-11",
        value={"event": "created", "user_id": 11},
    )

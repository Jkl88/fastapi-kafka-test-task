from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from kafka.errors import KafkaError

from app.config import settings
from app.dashboard import dashboard_hub, dashboard_store, load_dashboard_html
from app.producer import producer_service
from app.schemas import ConsumerEventReport, PublishMessage


app = FastAPI(title="FastAPI Kafka Test Task")


@app.get("/health")
def healthcheck() -> dict[str, str]:
    return {
        "status": "ok",
        "kafka": settings.KAFKA_BOOTSTRAP_SERVERS,
        "topic": settings.KAFKA_TOPIC,
        "consumer_group": settings.KAFKA_CONSUMER_GROUP,
    }


@app.post("/publish")
def publish_message(message: PublishMessage) -> dict[str, object]:
    try:
        producer_service.send_message(key=message.key, payload=message.payload)
    except KafkaError as exc:
        raise HTTPException(
            status_code=503,
            detail="Kafka broker is unavailable",
        ) from exc

    return {
        "status": "sent",
        "topic": settings.KAFKA_TOPIC,
        "key": message.key,
        "payload": message.payload,
    }


@app.get("/dashboard", include_in_schema=False, response_class=HTMLResponse)
def dashboard_page() -> str:
    return load_dashboard_html()


@app.post("/internal/consumer-events", include_in_schema=False)
async def report_consumer_event(event: ConsumerEventReport) -> dict[str, object]:
    snapshot = dashboard_store.record_event(event)
    await dashboard_hub.broadcast(snapshot)
    return {
        "status": "accepted",
        "snapshot": snapshot.model_dump(mode="json"),
    }


@app.websocket("/dashboard/ws")
async def dashboard_websocket(websocket: WebSocket) -> None:
    await dashboard_hub.connect(websocket)
    await dashboard_hub.send_snapshot(websocket, dashboard_store.snapshot())

    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        dashboard_hub.disconnect(websocket)

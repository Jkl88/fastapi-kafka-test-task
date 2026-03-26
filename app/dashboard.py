from collections import deque
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path
from threading import Lock

from fastapi import WebSocket

from app.schemas import ConsumerEventDisplay, ConsumerEventReport, DashboardSnapshot


DASHBOARD_TEMPLATE_PATH = Path(__file__).parent / "templates" / "dashboard.html"


@lru_cache(maxsize=1)
def load_dashboard_html() -> str:
    return DASHBOARD_TEMPLATE_PATH.read_text(encoding="utf-8")


class DashboardStore:
    def __init__(
        self,
        default_consumers: tuple[str, ...] = ("consumer_1", "consumer_2", "consumer_3"),
        recent_limit: int = 50,
    ) -> None:
        self._default_consumers = default_consumers
        self._recent_limit = recent_limit
        self._lock = Lock()
        self.reset()

    def reset(self) -> None:
        with self._lock:
            self._consumer_counts = {consumer: 0 for consumer in self._default_consumers}
            self._recent_events: deque[ConsumerEventDisplay] = deque(maxlen=self._recent_limit)
            self._total_messages = 0

    def snapshot(self) -> DashboardSnapshot:
        with self._lock:
            return DashboardSnapshot(
                total_messages=self._total_messages,
                consumer_counts=dict(self._consumer_counts),
                recent_events=[event.model_copy(deep=True) for event in self._recent_events],
            )

    def record_event(self, event: ConsumerEventReport) -> DashboardSnapshot:
        with self._lock:
            self._consumer_counts.setdefault(event.worker_name, 0)
            self._consumer_counts[event.worker_name] += 1
            self._total_messages += 1
            self._recent_events.appendleft(
                ConsumerEventDisplay(
                    worker_name=event.worker_name,
                    partition=event.partition,
                    offset=event.offset,
                    key=event.key,
                    value=event.value,
                    received_at=datetime.now(UTC).strftime("%H:%M:%S"),
                )
            )
            return DashboardSnapshot(
                total_messages=self._total_messages,
                consumer_counts=dict(self._consumer_counts),
                recent_events=[event.model_copy(deep=True) for event in self._recent_events],
            )


class DashboardHub:
    def __init__(self) -> None:
        self._clients: list[WebSocket] = []
        self._lock = Lock()

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        with self._lock:
            self._clients.append(websocket)

    def disconnect(self, websocket: WebSocket) -> None:
        with self._lock:
            self._clients = [client for client in self._clients if client is not websocket]

    async def send_snapshot(self, websocket: WebSocket, snapshot: DashboardSnapshot) -> None:
        await websocket.send_json(snapshot.model_dump(mode="json"))

    async def broadcast(self, snapshot: DashboardSnapshot) -> None:
        with self._lock:
            clients = list(self._clients)

        stale_clients: list[WebSocket] = []
        payload = snapshot.model_dump(mode="json")

        for client in clients:
            try:
                await client.send_json(payload)
            except Exception:
                stale_clients.append(client)

        if stale_clients:
            with self._lock:
                self._clients = [client for client in self._clients if client not in stale_clients]


dashboard_store = DashboardStore()
dashboard_hub = DashboardHub()

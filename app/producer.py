import json
from threading import Lock
from typing import Any, Callable

from kafka import KafkaProducer

from app.config import settings


class KafkaProducerService:
    def __init__(
        self,
        producer_factory: Callable[[], KafkaProducer] | None = None,
    ) -> None:
        self._producer_factory = producer_factory or self._build_producer
        self._producer: KafkaProducer | None = None
        self._lock = Lock()

    def _build_producer(self) -> KafkaProducer:
        return KafkaProducer(
            bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS,
            value_serializer=lambda value: json.dumps(
                value,
                ensure_ascii=False,
            ).encode("utf-8"),
            key_serializer=lambda key: key.encode("utf-8"),
            acks="all",
            retries=5,
        )

    def _get_producer(self) -> KafkaProducer:
        if self._producer is None:
            with self._lock:
                if self._producer is None:
                    self._producer = self._producer_factory()
        return self._producer

    def send_message(self, key: str, payload: dict[str, Any]) -> None:
        producer = self._get_producer()
        future = producer.send(
            settings.KAFKA_TOPIC,
            key=key,
            value=payload,
        )
        future.get(timeout=10)
        producer.flush()

    def close(self) -> None:
        if self._producer is None:
            return
        self._producer.flush()
        self._producer.close()
        self._producer = None


producer_service = KafkaProducerService()

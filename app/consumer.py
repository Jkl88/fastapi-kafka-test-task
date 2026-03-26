import json
import logging
import os
import socket
import time
from urllib import error, request

from kafka import KafkaConsumer
from kafka.errors import NoBrokersAvailable

from app.config import settings


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger(__name__)


def create_consumer() -> KafkaConsumer:
    return KafkaConsumer(
        settings.KAFKA_TOPIC,
        bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS,
        group_id=settings.KAFKA_CONSUMER_GROUP,
        auto_offset_reset="earliest",
        enable_auto_commit=True,
        value_deserializer=lambda value: json.loads(value.decode("utf-8")),
        key_deserializer=lambda key: key.decode("utf-8") if key else None,
    )


def report_processed_message(
    worker_name: str,
    partition: int,
    offset: int,
    key: str | None,
    value: dict,
) -> None:
    if not settings.CONSUMER_REPORT_URL:
        return

    payload = json.dumps(
        {
            "worker_name": worker_name,
            "partition": partition,
            "offset": offset,
            "key": key,
            "value": value,
        }
    ).encode("utf-8")
    http_request = request.Request(
        settings.CONSUMER_REPORT_URL,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with request.urlopen(http_request, timeout=2):
            return
    except (error.URLError, TimeoutError, OSError) as exc:
        logger.warning("[%s] Failed to report message to API: %s", worker_name, exc)


def main() -> None:
    worker_name = os.getenv("WORKER_NAME") or socket.gethostname()

    while True:
        consumer: KafkaConsumer | None = None
        try:
            consumer = create_consumer()
            logger.info(
                "[%s] Consumer started. Group: %s",
                worker_name,
                settings.KAFKA_CONSUMER_GROUP,
            )

            for message in consumer:
                logger.info(
                    "[%s] Received message | partition=%s offset=%s key=%s value=%s",
                    worker_name,
                    message.partition,
                    message.offset,
                    message.key,
                    message.value,
                )
                report_processed_message(
                    worker_name=worker_name,
                    partition=message.partition,
                    offset=message.offset,
                    key=message.key,
                    value=message.value,
                )
        except NoBrokersAvailable:
            logger.warning("[%s] Kafka is not ready yet. Retry in 5 sec...", worker_name)
            time.sleep(5)
        except Exception as exc:
            logger.exception("[%s] Consumer crashed: %s", worker_name, exc)
            time.sleep(5)
        finally:
            if consumer is not None:
                consumer.close()


if __name__ == "__main__":
    main()

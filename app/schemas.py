from typing import Any, Literal

from pydantic import BaseModel, Field


class PublishMessage(BaseModel):
    key: str = Field(..., description="Message key used for partition routing")
    payload: dict[str, Any] = Field(..., description="Message payload")


class ConsumerEventReport(BaseModel):
    worker_name: str = Field(..., description="Consumer instance name")
    partition: int = Field(..., description="Kafka partition")
    offset: int = Field(..., description="Kafka offset")
    key: str | None = Field(default=None, description="Message key")
    value: dict[str, Any] = Field(..., description="Consumed message payload")


class ConsumerEventDisplay(ConsumerEventReport):
    received_at: str = Field(..., description="Time when the API recorded the event")


class DashboardSnapshot(BaseModel):
    type: Literal["snapshot"] = "snapshot"
    total_messages: int = Field(..., description="Total processed messages")
    consumer_counts: dict[str, int] = Field(..., description="Per-consumer counters")
    recent_events: list[ConsumerEventDisplay] = Field(
        default_factory=list,
        description="Recent consumed messages",
    )

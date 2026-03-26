from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    KAFKA_BOOTSTRAP_SERVERS: str = "kafka:9092"
    KAFKA_TOPIC: str = "events"
    KAFKA_CONSUMER_GROUP: str = "events-consumer-group"
    CONSUMER_REPORT_URL: str = "http://localhost:8000/internal/consumer-events"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()

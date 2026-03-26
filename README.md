# FastAPI + Kafka Test Task

Сервис на FastAPI с Kafka producer, consumer group из трех консьюмеров и простым live dashboard для демонстрации чтения сообщений.

## Реализовано

- HTTP API на FastAPI
- endpoint `POST /publish` для отправки сообщений в Kafka topic `events`
- endpoint `GET /health` для проверки конфигурации сервиса
- dashboard `GET /dashboard` с формой отправки сообщений
- WebSocket `WS /dashboard/ws` для live-обновления статистики
- внутренний endpoint `POST /internal/consumer-events`, куда consumers репортят прочитанные сообщения
- три отдельных consumer-контейнера в одной consumer group
- Docker Compose для запуска Kafka, API и consumers одной командой
- базовые API и dashboard tests

## Стек

- Python 3.12
- FastAPI
- kafka-python
- Kafka
- Docker Compose
- pytest

## Dashboard

Dashboard показывает:

- сколько сообщений в сумме уже прочитано
- сколько сообщений прочитал каждый consumer
- последние прочитанные сообщения с `consumer`, `partition`, `offset`, `key` и `value`

## Проверка API

### Healthcheck

```bash
curl http://localhost:8000/health
```

Ожидаемый ответ:

```json
{
  "status": "ok",
  "kafka": "kafka:9092",
  "topic": "events",
  "consumer_group": "events-consumer-group"
}
```

### Отправка сообщения

```bash
curl -X POST http://localhost:8000/publish \
  -H "Content-Type: application/json" \
  -d '{
    "key": "string",
    "payload": {JSON объект}
  }'
```

## Проверка работы consumer group

```bash
curl -X POST http://localhost:8000/publish -H "Content-Type: application/json" -d '{"key":"user-1","payload":{"event":"created","id":1}}'
curl -X POST http://localhost:8000/publish -H "Content-Type: application/json" -d '{"key":"user-2","payload":{"event":"created","id":2}}'
curl -X POST http://localhost:8000/publish -H "Content-Type: application/json" -d '{"key":"user-3","payload":{"event":"created","id":3}}'
```

Далее:

- dashboard на `http://localhost:8000/dashboard`
- или логи `docker compose logs -f consumer_1 consumer_2 consumer_3`

## Конфигурация

Поддерживаемые env-переменные:

- `KAFKA_BOOTSTRAP_SERVERS`
- `KAFKA_TOPIC`
- `KAFKA_CONSUMER_GROUP`
- `CONSUMER_REPORT_URL`

В Docker Compose для consumers используется:

```env
CONSUMER_REPORT_URL=http://api:8000/internal/consumer-events
```

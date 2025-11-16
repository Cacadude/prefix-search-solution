# Быстрый старт

## Запуск за 3 команды

```bash
# 1. Запуск всех сервисов
docker compose up -d

# 2. Ожидание инициализации (30-60 секунд)
# Проверка готовности
curl http://localhost:5000/health

# 3. Тестовый запрос
curl "http://localhost:5000/search?query=масло&top_k=3"
```

## Проверка работы

### 1. Проверка здоровья сервисов

```bash
# Проверка статуса контейнеров
docker compose ps

# Проверка здоровья API
curl http://localhost:5000/health
# Ожидается: {"status":"ok","elasticsearch":"connected"}
```

### 2. Тестовые запросы

```bash
# Короткий префикс
curl "http://localhost:5000/search?query=ма&top_k=3"

# Английский запрос
curl "http://localhost:5000/search?query=alkaline&top_k=3"

# С числовым признаком
curl "http://localhost:5000/search?query=масло 10л&top_k=3"

# Исправление раскладки
curl "http://localhost:5000/search?query=xfq&top_k=3"
```

### 3. Запуск оценки качества

```bash
# Запуск оценки на всех тестовых запросах
python tools/evaluate.py \
    --queries data/prefix_queries.csv \
    --output reports/evaluation_results.csv \
    --base-url http://localhost:5000

# Просмотр результатов
cat reports/metrics.json
```

## Ожидаемые результаты

- ✅ Покрытие: **96.67%** (58 из 60 запросов)
- ✅ Средняя задержка: **67.51 мс**
- ✅ Все сервисы работают корректно

## Остановка

```bash
# Остановка всех сервисов
docker compose down

# Остановка с удалением данных
docker compose down -v
```

## Устранение проблем

### Elasticsearch не запускается

```bash
# Проверка логов
docker compose logs elasticsearch

# Перезапуск
docker compose restart elasticsearch
```

### Данные не загрузились

```bash
# Проверка логов загрузки
docker compose logs init_data

# Перезапуск загрузки
docker compose restart init_data
```

### API не отвечает

```bash
# Проверка логов API
docker compose logs search_api

# Перезапуск API
docker compose restart search_api
```

## Дополнительная информация

- Полная документация: [README.md](README.md)
- Архитектура: [ARCHITECTURE.md](ARCHITECTURE.md)
- Тестирование: [TESTING.md](TESTING.md)


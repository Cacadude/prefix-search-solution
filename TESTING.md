# Инструкция по тестированию решения

## Запуск решения

### 1. Запуск через Docker Compose

```bash
# Запуск всех сервисов
docker-compose up -d

# Проверка статуса
docker-compose ps

# Просмотр логов
docker-compose logs -f search_api
```

### 2. Проверка работоспособности

```bash
# Проверка здоровья API
curl http://localhost:5000/health

# Тестовый запрос
curl "http://localhost:5000/search?query=масло&top_k=3"
```

## Оценка покрытия

### Запуск оценки

```bash
# Если API запущен в Docker
python tools/evaluate.py \
    --queries data/prefix_queries.csv \
    --output reports/evaluation_results.csv \
    --base-url http://localhost:5000

# Если API запущен локально
python tools/evaluate.py \
    --queries data/prefix_queries.csv \
    --output reports/evaluation_results.csv \
    --base-url http://localhost:5000
```

### Результаты

После выполнения оценки результаты сохраняются в:
- `reports/evaluation_results.csv` - детальные результаты по каждому запросу
- `reports/metrics.json` - общие метрики (покрытие, задержка)

### Интерпретация метрик

- **coverage_percent**: Процент запросов, вернувших хотя бы один результат
- **avg_latency_ms**: Средняя задержка ответа API в миллисекундах
- **queries_with_results**: Количество запросов с результатами
- **total_queries**: Общее количество запросов

**Целевой показатель**: coverage_percent ≥ 70%

## Тестирование отдельных сценариев

### Короткие префиксы (1-2 символа)
```bash
curl "http://localhost:5000/search?query=ма&top_k=5"
curl "http://localhost:5000/search?query=pr&top_k=5"
```

### Исправление раскладки
```bash
curl "http://localhost:5000/search?query=xfq&top_k=5"  # должно найти "чай"
```

### Числовые признаки
```bash
curl "http://localhost:5000/search?query=масло%20раст%2010л&top_k=5"
curl "http://localhost:5000/search?query=cheddar%205kg&top_k=5"
```

### Многоязычные запросы
```bash
curl "http://localhost:5000/search?query=prosecco%20rose&top_k=5"
curl "http://localhost:5000/search?query=riesling%20mos&top_k=5"
```

## Устранение проблем

### Elasticsearch не запускается
```bash
# Проверка логов
docker-compose logs elasticsearch

# Перезапуск
docker-compose restart elasticsearch
```

### Данные не загружены
```bash
# Ручная загрузка данных
docker-compose exec search_api python src/load_catalog.py \
    --catalog data/catalog_products.xml \
    --host elasticsearch \
    --port 9200 \
    --index products
```

### API не отвечает
```bash
# Проверка логов
docker-compose logs search_api

# Перезапуск
docker-compose restart search_api
```

## Очистка

```bash
# Остановка всех сервисов
docker-compose down

# Остановка с удалением данных Elasticsearch
docker-compose down -v
```


# Структура проекта

```
prefix-search-solution/
│
├── src/                          # Исходный код приложения
│   ├── load_catalog.py          # Загрузка каталога в Elasticsearch
│   └── search_api.py            # REST API для поиска
│
├── tools/                        # Вспомогательные инструменты
│   └── evaluate.py              # Скрипт оценки качества поиска
│
├── data/                         # Данные
│   ├── catalog_products.xml     # Каталог товаров (1000 SKU)
│   └── prefix_queries.csv       # Тестовые запросы (60 запросов)
│
├── reports/                      # Результаты оценки
│   ├── evaluation_results.csv   # Детальные результаты по каждому запросу
│   └── metrics.json             # Сводные метрики
│
├── docker-compose.yml           # Docker Compose конфигурация
├── Dockerfile                   # Образ для API сервиса
├── requirements.txt             # Python зависимости
│
├── README.md                    # Основная документация
├── QUICKSTART.md                # Быстрый старт
├── ARCHITECTURE.md              # Архитектура решения
├── SOLUTION_SUMMARY.md          # Краткое описание решения
├── TESTING.md                   # Инструкции по тестированию
├── CHANGELOG.md                 # История изменений
├── PROJECT_STRUCTURE.md         # Этот файл
└── .gitignore                   # Git ignore правила
```

## Описание файлов

### Исходный код

- **`src/load_catalog.py`**: 
  - Парсинг XML каталога
  - Создание индекса в Elasticsearch с анализаторами
  - Загрузка товаров в индекс
  - Retry логика для подключения

- **`src/search_api.py`**: 
  - Flask REST API
  - Обработка поисковых запросов
  - Нормализация и обработка запросов
  - Формирование запросов к Elasticsearch
  - Фильтрация результатов

### Инструменты

- **`tools/evaluate.py`**: 
  - Оценка качества поиска
  - Запуск тестовых запросов
  - Расчет метрик (покрытие, задержка)
  - Сохранение результатов в CSV и JSON

### Конфигурация

- **`docker-compose.yml`**: 
  - Конфигурация сервисов (Elasticsearch, init_data, search_api)
  - Настройки сети и volumes
  - Health checks

- **`Dockerfile`**: 
  - Образ для Python приложения
  - Установка зависимостей
  - Копирование кода

- **`requirements.txt`**: 
  - Python зависимости
  - Версии библиотек

### Документация

- **`README.md`**: Основная документация с инструкциями
- **`QUICKSTART.md`**: Быстрый старт за 3 команды
- **`ARCHITECTURE.md`**: Детальное описание архитектуры
- **`SOLUTION_SUMMARY.md`**: Краткое описание решения
- **`TESTING.md`**: Инструкции по тестированию
- **`CHANGELOG.md`**: История изменений

### Данные

- **`data/catalog_products.xml`**: Каталог из 1000 товаров
- **`data/prefix_queries.csv`**: 60 тестовых запросов

### Результаты

- **`reports/evaluation_results.csv`**: Детальные результаты оценки
- **`reports/metrics.json`**: Сводные метрики

## Зависимости

### Python библиотеки

- `elasticsearch>=8.0.0,<9.0.0` - клиент Elasticsearch
- `flask>=2.0.0` - веб-фреймворк
- `requests>=2.28.0` - HTTP клиент

### Внешние сервисы

- Elasticsearch 8.11.0 (через Docker)

## Порты

- **5000**: API сервис (Flask)
- **9200**: Elasticsearch

## Volumes

- **es_data**: Данные Elasticsearch (постоянное хранилище)


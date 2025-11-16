#!/bin/bash
# Скрипт инициализации данных в Elasticsearch

echo "Ожидание готовности Elasticsearch..."
sleep 10

echo "Загрузка каталога в Elasticsearch..."
python src/load_catalog.py \
    --catalog data/catalog_products.xml \
    --host elasticsearch \
    --port 9200 \
    --index products

echo "Инициализация завершена!"


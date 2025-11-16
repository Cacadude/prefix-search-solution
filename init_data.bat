@echo off
REM Скрипт инициализации данных в Elasticsearch для Windows

echo Ожидание готовности Elasticsearch...
timeout /t 10 /nobreak

echo Загрузка каталога в Elasticsearch...
python src\load_catalog.py --catalog data\catalog_products.xml --host localhost --port 9200 --index products

echo Инициализация завершена!


#!/usr/bin/env python3
"""Загрузка каталога товаров в Elasticsearch."""
from __future__ import annotations

import argparse
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

from elasticsearch import Elasticsearch
from elasticsearch.helpers import bulk


def parse_xml_catalog(xml_path: Path) -> list[dict[str, Any]]:
    """
    Парсит XML каталог товаров и возвращает список товаров в формате для Elasticsearch.
    
    Args:
        xml_path: Путь к XML файлу с каталогом товаров
    
    Returns:
        Список словарей с товарами, каждый содержит:
        - _id: идентификатор товара
        - _source: данные товара (name, category, brand, weight, keywords, etc.)
    """
    tree = ET.parse(xml_path)
    root = tree.getroot()
    products = []
    
    for product in root.findall("product"):
        product_id = product.get("id", "")
        name = product.findtext("name", "").strip()
        category = product.findtext("category", "").strip()
        brand = product.findtext("brand", "").strip()
        weight_elem = product.find("weight")
        weight = weight_elem.text.strip() if weight_elem is not None and weight_elem.text else "0"
        weight_unit = weight_elem.get("unit", "") if weight_elem is not None else ""
        package_size = product.findtext("package_size", "1").strip()
        keywords = product.findtext("keywords", "").strip()
        description = product.findtext("description", "").strip()
        price = product.findtext("price", "0").strip()
        image_url = product.findtext("image_url", "").strip()
        
        # Извлекаем числовые значения для фильтрации
        weight_value = 0
        try:
            weight_value = float(weight)
        except ValueError:
            pass
        
        products.append({
            "_id": product_id,
            "_source": {
                "id": product_id,
                "name": name,
                "category": category,
                "brand": brand,
                "weight": weight,
                "weight_unit": weight_unit,
                "weight_value": weight_value,
                "package_size": package_size,
                "keywords": keywords,
                "description": description,
                "price": float(price) if price else 0.0,
                "image_url": image_url,
                # Составляем поисковый текст
                "search_text": f"{name} {category} {brand} {keywords} {description}".lower(),
            }
        })
    
    return products


def create_index(es: Elasticsearch, index_name: str = "products") -> None:
    """
    Создает индекс в Elasticsearch с настройками для префиксного поиска.
    
    Настройки включают:
    - prefix_analyzer: edge_ngram + russian_stemmer для префиксного поиска
    - search_analyzer: стандартный анализатор для поиска
    - english_analyzer: анализатор для английских слов без стемминга
    - layout_analyzer: исправление раскладки клавиатуры
    
    Args:
        es: Клиент Elasticsearch
        index_name: Имя индекса (по умолчанию "products")
    """
    
    # Маппинг для транслитерации и раскладки (QWERTY -> ЙЦУКЕН)
    # Создаем маппинг для исправления раскладки
    layout_mappings = [
        "й => q", "ц => w", "у => e", "к => r", "е => t", "н => y", "г => u", "ш => i", "щ => o", "з => p",
        "х => [", "ъ => ]", "ф => a", "ы => s", "в => d", "а => f", "п => g", "р => h", "о => j", "л => k",
        "д => l", "ж => ;", "э => '", "я => z", "ч => x", "с => c", "м => v", "и => b", "т => n", "ь => m",
        "б => ,", "ю => .",
        # Обратный маппинг (qwerty -> йцукен)
        "q => й", "w => ц", "e => у", "r => к", "t => е", "y => н", "u => г", "i => ш", "o => щ", "p => з",
        "[ => х", "] => ъ", "a => ф", "s => ы", "d => в", "f => а", "g => п", "h => р", "j => о", "k => л",
        "l => д", "; => ж", "' => э", "z => я", "x => ч", "c => с", "v => м", "b => и", "n => т", "m => ь",
        ", => б", ". => ю",
    ]
    
    settings = {
        "analysis": {
            "char_filter": {
                "layout_filter": {
                    "type": "mapping",
                    "mappings": layout_mappings
                }
            },
            "analyzer": {
                "prefix_analyzer": {
                    "type": "custom",
                    "tokenizer": "standard",
                    "filter": [
                        "lowercase",
                        "russian_stop",
                        "russian_stemmer",
                        "edge_ngram_filter",
                    ]
                },
                "search_analyzer": {
                    "type": "custom",
                    "tokenizer": "standard",
                    "filter": ["lowercase", "russian_stop", "russian_stemmer"]
                },
                "english_analyzer": {
                    "type": "custom",
                    "tokenizer": "standard",
                    "filter": [
                        "lowercase",
                        "edge_ngram_filter",
                    ]
                },
                "layout_analyzer": {
                    "type": "custom",
                    "tokenizer": "keyword",
                    "char_filter": ["layout_filter"],
                    "filter": ["lowercase"]
                }
            },
            "filter": {
                "edge_ngram_filter": {
                    "type": "edge_ngram",
                    "min_gram": 1,
                    "max_gram": 15
                },
                "russian_stop": {
                    "type": "stop",
                    "stopwords": "_russian_"
                },
                "russian_stemmer": {
                    "type": "stemmer",
                    "language": "russian"
                }
            }
        }
    }
    
    mapping = {
        "properties": {
            "id": {"type": "keyword"},
            "name": {
                "type": "text",
                "analyzer": "prefix_analyzer",
                "search_analyzer": "search_analyzer",
                "fields": {
                    "keyword": {"type": "keyword"},
                    "layout": {
                        "type": "text",
                        "analyzer": "layout_analyzer"
                    }
                }
            },
            "category": {
                "type": "text",
                "analyzer": "prefix_analyzer",
                "search_analyzer": "search_analyzer",
                "fields": {
                    "keyword": {"type": "keyword"}
                }
            },
            "brand": {
                "type": "text",
                "analyzer": "prefix_analyzer",
                "search_analyzer": "search_analyzer",
                "fields": {
                    "keyword": {"type": "keyword"},
                    "english": {
                        "type": "text",
                        "analyzer": "english_analyzer"
                    },
                    "layout": {
                        "type": "text",
                        "analyzer": "layout_analyzer"
                    }
                }
            },
            "keywords": {
                "type": "text",
                "analyzer": "prefix_analyzer",
                "search_analyzer": "search_analyzer"
            },
            "description": {
                "type": "text",
                "analyzer": "prefix_analyzer",
                "search_analyzer": "search_analyzer"
            },
            "search_text": {
                "type": "text",
                "analyzer": "prefix_analyzer",
                "search_analyzer": "search_analyzer",
                "fields": {
                    "layout": {
                        "type": "text",
                        "analyzer": "layout_analyzer"
                    }
                }
            },
            "weight": {"type": "keyword"},
            "weight_unit": {"type": "keyword"},
            "weight_value": {"type": "float"},
            "package_size": {"type": "keyword"},
            "price": {"type": "float"},
            "image_url": {"type": "keyword"},
        }
    }
    
    # Удаляем индекс, если существует
    if es.indices.exists(index=index_name):
        es.indices.delete(index=index_name)
    
    # Создаем индекс
    es.indices.create(index=index_name, settings=settings, mappings=mapping)
    print(f"Индекс {index_name} создан успешно")


def load_products(es: Elasticsearch, products: list[dict[str, Any]], index_name: str = "products") -> None:
    """
    Загружает товары в Elasticsearch используя bulk API.
    
    Args:
        es: Клиент Elasticsearch
        products: Список товаров для загрузки
        index_name: Имя индекса
    """
    actions = []
    for product in products:
        action = {
            "_index": index_name,
            "_id": product["_id"],
            **product["_source"]
        }
        actions.append(action)
    
    success, failed = bulk(es, actions, chunk_size=500, request_timeout=60)
    print(f"Загружено товаров: {success}")
    if failed:
        print(f"Ошибок при загрузке: {len(failed)}")
        for item in failed[:5]:  # Показываем первые 5 ошибок
            print(f"  - {item}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Загрузка каталога в Elasticsearch")
    parser.add_argument("--catalog", default="data/catalog_products.xml", help="Путь к XML каталогу")
    parser.add_argument("--host", default="localhost", help="Elasticsearch host")
    parser.add_argument("--port", type=int, default=9200, help="Elasticsearch port")
    parser.add_argument("--index", default="products", help="Имя индекса")
    args = parser.parse_args()
    
    catalog_path = Path(args.catalog)
    if not catalog_path.exists():
        raise SystemExit(f"Каталог не найден: {catalog_path}")
    
    # Подключение к Elasticsearch с повторными попытками
    import time
    max_retries = 10
    retry_delay = 5
    es = None
    es_url = f"http://{args.host}:{args.port}"
    print(f"Попытка подключения к Elasticsearch: {es_url}")
    
    for attempt in range(max_retries):
        try:
            es = Elasticsearch([es_url], request_timeout=10)
            if es.ping():
                print(f"Подключено к Elasticsearch на {args.host}:{args.port}")
                break
            else:
                print(f"Попытка {attempt + 1}/{max_retries}: ping() вернул False")
        except Exception as e:
            print(f"Попытка {attempt + 1}/{max_retries}: Ошибка подключения - {type(e).__name__}: {e}")
        if attempt < max_retries - 1:
            print(f"Ожидание {retry_delay} секунд перед следующей попыткой...")
            time.sleep(retry_delay)
    
    if es is None:
        raise SystemExit(f"Не удалось создать клиент Elasticsearch")
    
    try:
        if not es.ping():
            raise SystemExit(f"Не удалось подключиться к Elasticsearch на {args.host}:{args.port} после {max_retries} попыток")
    except Exception as e:
        raise SystemExit(f"Ошибка при проверке подключения: {e}")
    
    print("Парсинг XML каталога...")
    products = parse_xml_catalog(catalog_path)
    print(f"Найдено товаров: {len(products)}")
    
    print("Создание индекса...")
    create_index(es, args.index)
    
    print("Загрузка товаров...")
    load_products(es, products, args.index)
    
    # Обновляем индекс для применения изменений
    es.indices.refresh(index=args.index)
    print("Готово!")


if __name__ == "__main__":
    main()


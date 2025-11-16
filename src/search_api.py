#!/usr/bin/env python3
"""API сервис для префиксного поиска."""
from __future__ import annotations

import argparse
import logging
import re
import time
from typing import Any
from urllib.parse import unquote

from elasticsearch import Elasticsearch
from flask import Flask, jsonify, request

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

es: Elasticsearch | None = None
INDEX_NAME = "products"


def normalize_query(query: str) -> str:
    """Нормализует запрос: удаляет лишние пробелы, приводит к нижнему регистру."""
    return " ".join(query.strip().split())


def remove_spaces_for_prefix(query: str) -> str:
    """Убирает пробелы для префиксного поиска (например, 'кар тофель' -> 'картофель')."""
    # Убираем пробелы только если запрос короткий (до 20 символов) и содержит кириллицу
    if len(query) <= 20 and any('а' <= c.lower() <= 'я' or c in 'ёЁ' for c in query):
        # Убираем пробелы между словами
        no_spaces = query.replace(' ', '')
        # Если получилось осмысленное слово (больше 3 символов), возвращаем его
        if len(no_spaces) >= 3:
            return no_spaces
    return query


def fix_keyboard_layout(text: str) -> str:
    """Исправляет раскладку клавиатуры (QWERTY <-> ЙЦУКЕН)."""
    # Маппинг QWERTY -> ЙЦУКЕН
    qwerty_to_cyrillic = {
        'q': 'й', 'w': 'ц', 'e': 'у', 'r': 'к', 't': 'е', 'y': 'н', 'u': 'г', 'i': 'ш', 'o': 'щ', 'p': 'з',
        '[': 'х', ']': 'ъ', 'a': 'ф', 's': 'ы', 'd': 'в', 'f': 'а', 'g': 'п', 'h': 'р', 'j': 'о', 'k': 'л',
        'l': 'д', ';': 'ж', "'": 'э', 'z': 'я', 'x': 'ч', 'c': 'с', 'v': 'м', 'b': 'и', 'n': 'т', 'm': 'ь',
        ',': 'б', '.': 'ю',
        'Q': 'Й', 'W': 'Ц', 'E': 'У', 'R': 'К', 'T': 'Е', 'Y': 'Н', 'U': 'Г', 'I': 'Ш', 'O': 'Щ', 'P': 'З',
        'A': 'Ф', 'S': 'Ы', 'D': 'В', 'F': 'А', 'G': 'П', 'H': 'Р', 'J': 'О', 'K': 'Л',
        'L': 'Д', 'Z': 'Я', 'X': 'Ч', 'C': 'С', 'V': 'М', 'B': 'И', 'N': 'Т', 'M': 'Ь',
    }
    
    # Подсчитываем буквы
    latin_letters = sum(1 for c in text if c.isalpha() and c.lower() in qwerty_to_cyrillic)
    cyrillic_letters = sum(1 for c in text if 'а' <= c.lower() <= 'я' or c in 'ёЁ')
    all_letters = sum(1 for c in text if c.isalpha())
    
    # Если текст уже на кириллице - не трогаем
    if cyrillic_letters > 0:
        return text
    
    # Если только латинские буквы, проверяем, не ошибочная ли это раскладка
    # Исправляем ТОЛЬКО очень короткие запросы (1-3 символа), которые могут быть ошибочной раскладкой
    if latin_letters > 0 and cyrillic_letters == 0 and all_letters > 0:
        text_lower = text.lower().strip()
        # ИСПРАВЛЯЕМ ТОЛЬКО если запрос очень короткий (1-3 символа)
        is_very_short = len(text_lower) <= 3
        is_all_mapped = latin_letters == all_letters
        
        # Список коротких английских слов, которые не нужно исправлять
        common_short_words = {'a', 'an', 'at', 'as', 'am', 'be', 'by', 'do', 'go', 'he', 'if', 'in', 'is', 'it', 'me', 'my', 'no', 'of', 'on', 'or', 'so', 'to', 'up', 'us', 'we', 'pr', 'ma'}
        
        # Исправляем ТОЛЬКО если запрос очень короткий (1-3 символа) и не в списке исключений
        # ВАЖНО: проверяем длину ДО исправления
        if is_very_short and text_lower not in common_short_words and is_all_mapped:
            # Исправляем QWERTY -> ЙЦУКЕН
            result = ''.join(qwerty_to_cyrillic.get(c, c) for c in text)
            logger.info(f"Исправлена раскладка: '{text}' -> '{result}'")
            return result
    
    # Если не похоже на ошибочную раскладку - возвращаем как есть
    return text


def extract_numbers(query: str) -> tuple[str, list[float]]:
    """Извлекает числа из запроса и возвращает очищенный запрос и список чисел."""
    # Ищем числа с единицами измерения (л, кг, мл, г и т.д.)
    number_pattern = r'(\d+(?:[.,]\d+)?)\s*(л|кг|ml|л|г|g|kg|l|шт|pcs)?'
    numbers = []
    cleaned_query = query
    
    for match in re.finditer(number_pattern, query, re.IGNORECASE):
        num_str = match.group(1).replace(',', '.')
        try:
            num = float(num_str)
            numbers.append(num)
            # Удаляем найденное число из запроса для лучшего поиска
            cleaned_query = cleaned_query.replace(match.group(0), '', 1)
        except ValueError:
            pass
    
    cleaned_query = normalize_query(cleaned_query)
    return cleaned_query, numbers


def build_search_query(query: str, top_k: int = 5) -> dict[str, Any]:
    """Строит запрос к Elasticsearch с поддержкой префиксов и транслитерации."""
    query = normalize_query(query)
    
    # Пробуем убрать пробелы для префиксного поиска (например, "кар тофель" -> "картофель")
    query_no_spaces = remove_spaces_for_prefix(query)
    
    # Пробуем исправить раскладку только для очень коротких запросов (1-3 символа)
    # И только если запрос содержит кириллицу (не английские слова)
    query_stripped = query.strip()
    has_cyrillic = any('а' <= c.lower() <= 'я' or c in 'ёЁ' for c in query_stripped)
    if query_stripped and len(query_stripped) <= 3 and not has_cyrillic:
        # Только для коротких латинских запросов (возможно, ошибочная раскладка)
        fixed_query = fix_keyboard_layout(query)
        if fixed_query != query and len(fixed_query.strip()) == len(query_stripped):
            # Проверяем, что получилась кириллица
            if any('а' <= c.lower() <= 'я' or c in 'ёЁ' for c in fixed_query):
                logger.info(f"Исправлена раскладка: '{query}' -> '{fixed_query}'")
                query = fixed_query
    
    cleaned_query, numbers = extract_numbers(query)
    cleaned_query_no_spaces, _ = extract_numbers(query_no_spaces) if query_no_spaces != query else (cleaned_query, [])
    
    # Если запрос очень короткий (1-2 символа), используем более мягкий поиск
    is_short = len(cleaned_query) <= 2
    
    # Строим multi_match запрос с бустами
    should_clauses = []
    
        # Основной поиск по всем полям
        if cleaned_query:
            should_clauses.append({
                "multi_match": {
                    "query": cleaned_query,
                    "fields": [
                        "name^3",  # Название товара - самый важный
                        "brand^2",  # Бренд - важный
                        "category^1.5",  # Категория
                        "keywords^2",  # Ключевые слова
                        "description^1",  # Описание
                        "search_text^1.5",  # Поисковый текст
                        "brand.english^2.5",  # Бренд на английском
                    ],
                    "type": "best_fields",
                    "fuzziness": "AUTO" if not is_short else "0",
                    "prefix_length": 1,
                }
            })
            
            # Поиск с match_bool_prefix для префиксного поиска
            should_clauses.append({
                "multi_match": {
                    "query": cleaned_query,
                    "fields": [
                        "name^2.5",
                        "brand^2",
                        "keywords^1.5",
                    ],
                    "type": "bool_prefix",
                }
            })
        
        # Поиск по keyword полям (точное совпадение или префикс)
        if len(cleaned_query) >= 2:
            should_clauses.append({
                "prefix": {
                    "name.keyword": {
                        "value": cleaned_query,
                        "boost": 2.5,
                    }
                }
            })
            should_clauses.append({
                "prefix": {
                    "brand.keyword": {
                        "value": cleaned_query,
                        "boost": 2.0,
                    }
                }
            })
            should_clauses.append({
                "prefix": {
                    "keywords": {
                        "value": cleaned_query,
                        "boost": 1.8,
                    }
                }
            })
        
    # Поиск с учетом раскладки
    if cleaned_query:
        should_clauses.append({
            "multi_match": {
                "query": cleaned_query,
                "fields": [
                    "name.layout^2",
                    "search_text.layout^1",
                    "brand.layout^1.5",
                ],
                "type": "best_fields",
            }
        })
        
    # Поиск без пробелов (для разбитых слов)
    if cleaned_query and cleaned_query_no_spaces != cleaned_query and len(cleaned_query_no_spaces) >= 2:
        should_clauses.append({
            "multi_match": {
                "query": cleaned_query_no_spaces,
                "fields": [
                    "name^2.5",
                    "brand^2",
                    "keywords^1.5",
                    "search_text^1.5",
                ],
                "type": "best_fields",
                "fuzziness": "AUTO",
            }
        })
        # Также пробуем поиск по префиксу без пробелов
        should_clauses.append({
            "match_phrase_prefix": {
                "name": {
                    "query": cleaned_query_no_spaces,
                    "boost": 1.5,
                }
            }
        })
        
    # Префиксный поиск для коротких запросов
    if cleaned_query and is_short:
        should_clauses.append({
            "match_phrase_prefix": {
                "name": {
                    "query": cleaned_query,
                    "boost": 2.0,
                }
            }
        })
        # Wildcard поиск для очень коротких запросов (1-2 символа)
        if len(cleaned_query) <= 2:
            should_clauses.append({
                "wildcard": {
                    "name.keyword": {
                        "value": f"{cleaned_query}*",
                        "boost": 3.0,
                    }
                }
            })
            should_clauses.append({
                "wildcard": {
                    "brand.keyword": {
                        "value": f"{cleaned_query}*",
                        "boost": 2.5,
                    }
                }
            })
            should_clauses.append({
                "prefix": {
                    "name": {
                        "value": cleaned_query,
                        "boost": 2.0,
                    }
                }
            })
            should_clauses.append({
                "prefix": {
                    "brand": {
                        "value": cleaned_query,
                        "boost": 1.8,
                    }
                }
            })
        
    # Поиск по отдельным словам (для многословных запросов)
    if cleaned_query:
        query_words = cleaned_query.split()
        if len(query_words) > 1:
            # Ищем все слова вместе
            should_clauses.append({
                "match": {
                    "search_text": {
                        "query": cleaned_query,
                        "operator": "and",
                        "boost": 1.5,
                    }
                }
            })
            # Ищем хотя бы одно слово
            should_clauses.append({
                "match": {
                    "search_text": {
                        "query": cleaned_query,
                        "operator": "or",
                        "boost": 1.0,
                    }
                }
            })
            # Поиск по каждому слову отдельно (для английских запросов)
            for word in query_words:
                if len(word) >= 2:
                    should_clauses.append({
                        "match": {
                            "search_text": {
                                "query": word,
                                "boost": 0.8,
                            }
                        }
                    })
                    # Префиксный поиск по каждому слову
                    should_clauses.append({
                        "prefix": {
                            "name": {
                                "value": word,
                                "boost": 1.2,
                            }
                        }
                    })
                    should_clauses.append({
                        "prefix": {
                            "brand": {
                                "value": word,
                                "boost": 1.5,
                            }
                        }
                    })
                    should_clauses.append({
                        "prefix": {
                            "brand.keyword": {
                                "value": word,
                                "boost": 2.0,
                            }
                        }
                    })
                    should_clauses.append({
                        "prefix": {
                            "keywords": {
                                "value": word,
                                "boost": 1.0,
                            }
                        }
                    })
                    # Wildcard поиск по каждому слову
                    should_clauses.append({
                        "wildcard": {
                            "name.keyword": {
                                "value": f"{word}*",
                                "boost": 1.5,
                            }
                        }
                    })
                    should_clauses.append({
                        "wildcard": {
                            "brand.keyword": {
                                "value": f"{word}*",
                                "boost": 2.0,
                            }
                        }
                    })
    
    # Фильтр по числам, если они есть
    number_filters = []
    if numbers:
        for num in numbers:
            # Ищем товары с близким весом/объемом (±20%)
            number_filters.append({
                "range": {
                    "weight_value": {
                        "gte": num * 0.8,
                        "lte": num * 1.2,
                        "boost": 1.5
                    }
                }
            })
    
    query_body: dict[str, Any] = {
        "size": top_k * 3,  # Берем больше результатов для фильтрации
        "query": {
            "bool": {
                "should": should_clauses,
                "minimum_should_match": 1,
            }
        }
    }
    
    if number_filters:
        query_body["query"]["bool"]["should"].extend(number_filters)
    
    # Добавляем агрегацию по категориям для защиты от мусора
    query_body["aggs"] = {
        "categories": {
            "terms": {
                "field": "category.keyword",
                "size": 10
            }
        }
    }
    
    return query_body


def filter_noise_results(results: list[dict[str, Any]], query: str, top_k: int = 5) -> list[dict[str, Any]]:
    """
    Фильтрует мусорные результаты на основе релевантности и категорий.
    
    Многоуровневая система фильтрации:
    1. Проверка совпадения слов из запроса
    2. Проверка префиксов для коротких запросов
    3. Fallback на топовые результаты от Elasticsearch
    
    Args:
        results: Список результатов от Elasticsearch
        query: Оригинальный поисковый запрос
        top_k: Количество результатов для возврата
    
    Returns:
        Отфильтрованный список результатов
    """
    if not results:
        return []
    
    query_lower = query.lower().strip()
    if not query_lower:
        # Если запрос пустой, возвращаем топ результатов
        return results[:top_k]
    
    filtered = []
    
    # Извлекаем ключевые слова из запроса
    query_words = set(query_lower.split())
    
    for result in results:
        score = result.get("_score", 0)
        source = result.get("_source", {})
        
        # Убираем минимальный порог - принимаем все результаты от Elasticsearch
        # (фильтрация будет происходить по другим критериям)
        
        name = source.get("name", "").lower()
        category = source.get("category", "").lower()
        brand = source.get("brand", "").lower()
        keywords = source.get("keywords", "").lower()
        search_text = source.get("search_text", "").lower()
        
        # Проверяем совпадение хотя бы одного слова из запроса
        name_words = set(name.split())
        category_words = set(category.split())
        brand_words = set(brand.split())
        keywords_words = set(keywords.split())
        
        all_words = name_words | category_words | brand_words | keywords_words
        
        # Если запрос очень короткий (1-2 символа), более мягкая проверка
        if len(query_lower) <= 2:
            # Проверяем, начинается ли название/бренд/категория с запроса
            if (name.startswith(query_lower) or 
                brand.startswith(query_lower) or 
                category.startswith(query_lower) or
                any(kw.startswith(query_lower) for kw in keywords_words) or
                query_lower in search_text):
                filtered.append(result)
        else:
            # Для более длинных запросов требуем совпадение хотя бы одного слова
            if query_words & all_words:
                filtered.append(result)
            # Или проверяем, что запрос является префиксом важных полей
            elif (name.startswith(query_lower) or 
                  brand.startswith(query_lower) or
                  any(kw.startswith(query_lower) for kw in keywords_words) or
                  query_lower in search_text):
                filtered.append(result)
            # Если ничего не совпало, но score достаточно высокий - оставляем
            # Ослабляем порог для повышения покрытия
            elif score > 0.1:
                filtered.append(result)
            # Если score очень низкий, но это единственные результаты - оставляем
            elif score > 0:
                filtered.append(result)
        
        if len(filtered) >= top_k:
            break
    
    # Если после фильтрации ничего не осталось, возвращаем топ результатов по score
    # (ослабленная фильтрация для повышения покрытия)
    if not filtered and results:
        # Возвращаем топ результатов, даже если они не прошли фильтрацию
        return results[:top_k]
    
    # Если отфильтровано мало результатов, добавляем еще из топовых
    if len(filtered) < top_k and results:
        for result in results:
            if result not in filtered:
                filtered.append(result)
                if len(filtered) >= top_k:
                    break
    
    # Если все еще мало результатов, возвращаем все что есть
    if len(filtered) < top_k:
        return filtered
    
    return filtered[:top_k]


@app.route("/search", methods=["GET", "POST"])
def search():
    """
    Эндпоинт для поиска товаров по префиксам.
    
    Поддерживает:
    - Короткие префиксы (1-3 символа)
    - Исправление раскладки клавиатуры
    - Числовые признаки (вес, объем)
    - Многоязычные запросы (кириллица + латиница)
    - Разбитые слова (пробелы между буквами)
    
    Args:
        query (str): Поисковый запрос
        top_k (int): Количество результатов (по умолчанию 5)
    
    Returns:
        JSON с результатами поиска, включая:
        - query: оригинальный запрос
        - results: список товаров
        - total: общее количество результатов
        - latency_ms: время выполнения запроса
    """
    start_time = time.time()
    
    if request.method == "POST":
        data = request.get_json() or {}
        query = data.get("query", "")
        top_k = int(data.get("top_k", 5))
    else:
        query = request.args.get("query", "")
        top_k = int(request.args.get("top_k", 5))
    
    if not query:
        return jsonify({"error": "Параметр 'query' обязателен"}), 400
    
    # Декодируем URL-кодированный запрос
    try:
        query = unquote(query, encoding='utf-8')
    except Exception:
        pass
    
    # Исправляем кодировку запроса, если он пришел в неправильной кодировке
    try:
        # Если запрос выглядит как неправильно закодированный UTF-8 (например, 'Ð¼Ð°Ñ\x81Ð»Ð¾')
        if isinstance(query, bytes):
            query = query.decode('utf-8')
        elif any(ord(c) > 127 for c in query) and not any('а' <= c.lower() <= 'я' or c in 'ёЁ' for c in query):
            # Пробуем исправить кодировку: latin-1 -> utf-8
            try:
                fixed = query.encode('latin-1').decode('utf-8')
                # Проверяем, что получилась кириллица
                if any('а' <= c.lower() <= 'я' or c in 'ёЁ' for c in fixed):
                    query = fixed
                    logger.info(f"Исправлена кодировка запроса: '{query}'")
            except (UnicodeEncodeError, UnicodeDecodeError):
                pass
    except (UnicodeEncodeError, UnicodeDecodeError, AttributeError):
        pass
    
    original_query = query
    logger.info(f"Поиск: '{original_query}' (len={len(original_query)})")
    
    try:
        # Строим запрос
        search_query = build_search_query(query, top_k)
        
        # Логируем запрос для отладки (cleaned_query будет определен ниже)
        logger.info(f"Запрос к Elasticsearch: query='{query}'")
        
        # Выполняем поиск
        response = es.search(index=INDEX_NAME, body=search_query)
        
        # Извлекаем результаты
        hits = response.get("hits", {}).get("hits", [])
        total_hits = response.get("hits", {}).get("total", {}).get("value", 0)
        
        # Логируем количество результатов до фильтрации
        logger.info(f"Найдено результатов до фильтрации: {len(hits)} (всего: {total_hits})")
        if hits:
            first_result = hits[0].get('_source', {})
            logger.info(f"Первый результат: score={hits[0].get('_score')}, name={first_result.get('name', '')[:50]}")
        else:
            logger.warning(f"Elasticsearch не вернул результатов для запроса '{query}'")
        
        # Фильтруем мусор
        filtered_hits = filter_noise_results(hits, query, top_k)
        
        # Логируем количество результатов после фильтрации
        logger.info(f"Найдено результатов после фильтрации: {len(filtered_hits)}")
        
        # ВРЕМЕННО: если после фильтрации ничего не осталось, возвращаем все результаты
        # (для диагностики и повышения покрытия)
        if not filtered_hits and hits:
            logger.warning(f"После фильтрации не осталось результатов, возвращаем топ {top_k} результатов от Elasticsearch")
            filtered_hits = hits[:top_k]
        
        # Формируем ответ
        results = []
        for hit in filtered_hits:
            source = hit["_source"]
            results.append({
                "id": source.get("id"),
                "name": source.get("name"),
                "category": source.get("category"),
                "brand": source.get("brand"),
                "price": source.get("price"),
                "weight": source.get("weight"),
                "weight_unit": source.get("weight_unit"),
                "score": hit.get("_score"),
            })
        
        latency_ms = (time.time() - start_time) * 1000
        
        return jsonify({
            "query": original_query,
            "results": results,
            "total": len(results),
            "latency_ms": round(latency_ms, 2),
        })
    
    except Exception as e:
        logger.error(f"Ошибка при поиске: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@app.route("/health", methods=["GET"])
def health():
    """
    Проверка здоровья сервиса.
    
    Returns:
        JSON со статусом сервиса и подключения к Elasticsearch
    """
    try:
        if es and es.ping():
            return jsonify({"status": "ok", "elasticsearch": "connected"})
        return jsonify({"status": "error", "elasticsearch": "disconnected"}), 503
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)}), 503


def main() -> None:
    global es, INDEX_NAME
    
    parser = argparse.ArgumentParser(description="API сервис для префиксного поиска")
    parser.add_argument("--host", default="0.0.0.0", help="Host для Flask")
    parser.add_argument("--port", type=int, default=5000, help="Port для Flask")
    parser.add_argument("--es-host", default="localhost", help="Elasticsearch host")
    parser.add_argument("--es-port", type=int, default=9200, help="Elasticsearch port")
    parser.add_argument("--index", default="products", help="Имя индекса")
    args = parser.parse_args()
    
    INDEX_NAME = args.index
    
    # Подключение к Elasticsearch
    es = Elasticsearch([f"http://{args.es_host}:{args.es_port}"])
    if not es.ping():
        raise SystemExit(f"Не удалось подключиться к Elasticsearch на {args.es_host}:{args.es_port}")
    
    logger.info(f"Подключено к Elasticsearch: {args.es_host}:{args.es_port}")
    logger.info(f"Используется индекс: {INDEX_NAME}")
    
    app.run(host=args.host, port=args.port, debug=False)


if __name__ == "__main__":
    main()


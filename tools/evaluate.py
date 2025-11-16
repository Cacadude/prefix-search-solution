#!/usr/bin/env python3
"""Скрипт оценки качества префиксного поиска."""
from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from pathlib import Path
from typing import Any

import requests

# Исправляем кодировку вывода для Windows
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')


def evaluate_queries(
    queries_path: Path,
    base_url: str = "http://localhost:5000",
    output_path: Path | None = None,
    top_k: int = 3,
) -> dict[str, Any]:
    """
    Оценивает качество поиска на тестовых запросах.
    
    Запускает все запросы из CSV файла, собирает результаты и метрики.
    
    Args:
        queries_path: Путь к CSV файлу с тестовыми запросами
        base_url: Базовый URL API сервиса
        output_path: Путь для сохранения результатов (опционально)
        top_k: Количество результатов для каждого запроса
    
    Returns:
        Словарь с метриками (coverage, latency, etc.)
    """
    
    # Читаем запросы
    queries = []
    with queries_path.open(encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            queries.append(row)
    
    results = []
    total_latency = 0
    successful_queries = 0
    queries_with_results = 0
    
    print(f"Обработка {len(queries)} запросов...")
    
    for i, query_row in enumerate(queries, 1):
        query = query_row.get("query", "").strip()
        if not query:
            continue
        
        print(f"[{i}/{len(queries)}] Обработка: '{query}'")
        
        try:
            # Выполняем поиск
            start_time = time.time()
            response = requests.get(
                f"{base_url}/search",
                params={"query": query, "top_k": top_k},
                timeout=10
            )
            latency = (time.time() - start_time) * 1000
            
            if response.status_code == 200:
                data = response.json()
                search_results = data.get("results", [])
                query_latency = data.get("latency_ms", latency)
                
                total_latency += query_latency
                successful_queries += 1
                
                if search_results:
                    queries_with_results += 1
                
                # Формируем строку результата
                result_row = {
                    "query": query,
                    "site": query_row.get("site", ""),
                    "type": query_row.get("type", ""),
                    "notes": query_row.get("notes", ""),
                    "top_1": search_results[0].get("name", "") if len(search_results) > 0 else "",
                    "top_1_score": search_results[0].get("score", "") if len(search_results) > 0 else "",
                    "top_1_category": search_results[0].get("category", "") if len(search_results) > 0 else "",
                    "top_2": search_results[1].get("name", "") if len(search_results) > 1 else "",
                    "top_2_score": search_results[1].get("score", "") if len(search_results) > 1 else "",
                    "top_2_category": search_results[1].get("category", "") if len(search_results) > 1 else "",
                    "top_3": search_results[2].get("name", "") if len(search_results) > 2 else "",
                    "top_3_score": search_results[2].get("score", "") if len(search_results) > 2 else "",
                    "top_3_category": search_results[2].get("category", "") if len(search_results) > 2 else "",
                    "latency_ms": round(query_latency, 2),
                    "total_results": len(search_results),
                    "judgement": "",  # Для ручной оценки
                }
            else:
                result_row = {
                    "query": query,
                    "site": query_row.get("site", ""),
                    "type": query_row.get("type", ""),
                    "notes": query_row.get("notes", ""),
                    "top_1": "",
                    "top_1_score": "",
                    "top_1_category": "",
                    "top_2": "",
                    "top_2_score": "",
                    "top_2_category": "",
                    "top_3": "",
                    "top_3_score": "",
                    "top_3_category": "",
                    "latency_ms": latency,
                    "total_results": 0,
                    "judgement": f"ERROR: {response.status_code}",
                }
            
            results.append(result_row)
        
        except Exception as e:
            print(f"  Ошибка: {e}")
            results.append({
                "query": query,
                "site": query_row.get("site", ""),
                "type": query_row.get("type", ""),
                "notes": query_row.get("notes", ""),
                "top_1": "",
                "top_1_score": "",
                "top_1_category": "",
                "top_2": "",
                "top_2_score": "",
                "top_2_category": "",
                "top_3": "",
                "top_3_score": "",
                "top_3_category": "",
                "latency_ms": 0,
                "total_results": 0,
                "judgement": f"EXCEPTION: {str(e)}",
            })
    
    # Сохраняем результаты
    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        fieldnames = [
            "query", "site", "type", "notes",
            "top_1", "top_1_score", "top_1_category",
            "top_2", "top_2_score", "top_2_category",
            "top_3", "top_3_score", "top_3_category",
            "latency_ms", "total_results", "judgement",
        ]
        
        with output_path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(results)
        
        print(f"\nРезультаты сохранены в: {output_path}")
    
    # Вычисляем метрики
    coverage = (queries_with_results / len(queries) * 100) if queries else 0
    avg_latency = (total_latency / successful_queries) if successful_queries > 0 else 0
    
    metrics = {
        "total_queries": len(queries),
        "successful_queries": successful_queries,
        "queries_with_results": queries_with_results,
        "coverage_percent": round(coverage, 2),
        "avg_latency_ms": round(avg_latency, 2),
    }
    
    print("\n" + "="*60)
    print("МЕТРИКИ:")
    print("="*60)
    print(f"Всего запросов: {metrics['total_queries']}")
    print(f"Успешных запросов: {metrics['successful_queries']}")
    print(f"Запросов с результатами: {metrics['queries_with_results']}")
    print(f"Покрытие: {metrics['coverage_percent']}%")
    print(f"Средняя задержка: {metrics['avg_latency_ms']} мс")
    print("="*60)
    
    return metrics


def main() -> None:
    parser = argparse.ArgumentParser(description="Оценка качества префиксного поиска")
    parser.add_argument("--queries", default="data/prefix_queries.csv", help="CSV с запросами")
    parser.add_argument("--output", default="reports/evaluation_results.csv", help="Путь для сохранения результатов")
    parser.add_argument("--base-url", default="http://localhost:5000", help="URL API сервиса")
    parser.add_argument("--top-k", type=int, default=3, help="Количество топ результатов")
    args = parser.parse_args()
    
    queries_path = Path(args.queries)
    if not queries_path.exists():
        raise SystemExit(f"Файл с запросами не найден: {queries_path}")
    
    output_path = Path(args.output)
    
    # Проверяем доступность API
    try:
        response = requests.get(f"{args.base_url}/health", timeout=5)
        if response.status_code != 200:
            print(f"Предупреждение: API сервис недоступен ({response.status_code})")
    except Exception as e:
        print(f"Предупреждение: Не удалось подключиться к API: {e}")
        print("Убедитесь, что API сервис запущен на", args.base_url)
    
    metrics = evaluate_queries(queries_path, args.base_url, output_path, args.top_k)
    
    # Сохраняем метрики в JSON
    metrics_path = output_path.parent / "metrics.json"
    with metrics_path.open("w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=2, ensure_ascii=False)
    print(f"\nМетрики сохранены в: {metrics_path}")


if __name__ == "__main__":
    main()


FROM python:3.11-slim

WORKDIR /app

# Устанавливаем зависимости
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копируем код
COPY src/ ./src/
COPY data/ ./data/
COPY tools/ ./tools/

# Устанавливаем права на выполнение
RUN chmod +x src/*.py tools/*.py

EXPOSE 5000

CMD ["python", "src/search_api.py", "--host", "0.0.0.0", "--port", "5000", "--es-host", "elasticsearch", "--es-port", "9200"]


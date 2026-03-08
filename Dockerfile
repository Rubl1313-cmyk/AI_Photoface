FROM python:3.11-slim

WORKDIR /app

# Устанавливаем системные зависимости
RUN apt-get update && apt-get install -y \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Копируем requirements и устанавливаем зависимости
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копируем весь код
COPY . .

# Создаём директорию для данных
RUN mkdir -p /app/data

# Открываем порт (HF Spaces использует 7860)
EXPOSE 7860

# Запускаем через uvicorn (FastAPI)
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "7860"]

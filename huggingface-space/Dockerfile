# 🤖 HuggingFace Space Dockerfile - Реальный FaceFusion
FROM python:3.11-slim

# Установка системных зависимостей
RUN apt-get update && apt-get install -y \
    build-essential \
    libgl1-mesa-glx \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    wget \
    git \
    cmake \
    libsndfile1 \
    libfontconfig1 \
    libxrender1 \
    libsm6 \
    libxt6 \
    ffmpeg \
    libavcodec-dev \
    libavformat-dev \
    libswscale-dev \
    && rm -rf /var/lib/apt/lists/*

# Рабочая директория
WORKDIR /app

# Копирование и установка зависимостей
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Клонирование и установка FaceFusion
RUN git clone https://github.com/facefusion/facefusion.git /tmp/facefusion && \
    cd /tmp/facefusion && \
    python install.py --skip-ffmpeg

# Копирование файлов проекта
COPY app.py .

# Создание директории для данных
RUN mkdir -p /app/data

# Переменные окружения
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# Порт для HuggingFace Spaces
EXPOSE 7860

# Запуск приложения
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "7860"]

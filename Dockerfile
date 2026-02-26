FROM python:3.10-slim

# Системные зависимости
RUN apt-get update && apt-get install -y \
    libgl1 libglib2.0-0 libsm6 libxext6 libxrender-dev libgomp1 \
    git wget ffmpeg libavcodec-dev libavformat-dev libswscale-dev curl libstdc++6 \
    && rm -rf /var/lib/apt/lists/*

ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1

WORKDIR /app

# Клонируем FaceFusion
RUN git clone --depth 1 https://github.com/facefusion/facefusion.git /opt/facefusion

WORKDIR /opt/facefusion

# Обновляем pip
RUN pip install --upgrade pip

# requirements.txt для FaceFusion
RUN cat > requirements.txt << 'EOF'
gradio==4.44.1
gradio-client==1.3.0
huggingface-hub==0.23.4
numpy==1.26.4
onnx==1.17.0
onnxruntime==1.23.2
opencv-python==4.10.0.84
scipy==1.14.1
pillow==10.4.0
requests==2.32.3
fastapi==0.110.0
uvicorn==0.27.1
python-multipart==0.0.9
aiofiles==23.2.1
tqdm==4.67.0
protobuf==5.28.0
typing-extensions==4.12.2
psutil==5.9.8
EOF

RUN pip install --no-cache-dir -r requirements.txt

WORKDIR /app

# requirements.txt для бота
RUN cat > requirements.txt << 'EOF'
aiogram==3.3.0
httpx==0.27.0
python-dotenv==1.0.0
numpy==1.26.4
Pillow==10.4.0
deep-translator==1.11.4
requests==2.32.3
opencv-python-headless==4.10.0.84
EOF

RUN pip install --no-cache-dir -r requirements.txt

# Копируем код
COPY . .

# Копируем FaceFusion сервер
COPY services/facefusion_server.py /opt/facefusion_server.py

# Скрипт запуска
COPY start.sh /start.sh
RUN chmod +x /start.sh

# Создаём директорию для данных (persistent storage на Render)
RUN mkdir -p /data

CMD ["/start.sh"]
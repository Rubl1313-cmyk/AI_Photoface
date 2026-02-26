#!/bin/bash
set -e

echo "=========================================="
echo "🚀 AI PhotoStudio - Запуск (Render.com)"
echo "=========================================="
echo "📅 Дата: $(date)"
echo "=========================================="

cd /opt/facefusion

# Запускаем FaceFusion API сервер
echo ""
echo "🔧 Запуск FaceFusion API сервера (порт 8081)..."
python /opt/facefusion_server.py &
API_PID=$!
echo "✅ API сервер запущен (PID: $API_PID)"

# Ждём запуска API
echo ""
echo "⏳ Ожидание запуска API..."
MAX_ATTEMPTS=36
ATTEMPT=0

while [ $ATTEMPT -lt $MAX_ATTEMPTS ]; do
    ATTEMPT=$((ATTEMPT + 1))
    if curl -s http://localhost:8081/health > /dev/null 2>&1; then
        echo "✅ API готов! (попытка $ATTEMPT/$MAX_ATTEMPTS)"
        break
    fi
    echo "⏳ Попытка $ATTEMPT/$MAX_ATTEMPTS... ждём 5 секунд"
    sleep 5
done

if ! curl -s http://localhost:8081/health > /dev/null 2>&1; then
    echo "❌ API не запустился"
    exit 1
fi

# Запускаем бота
echo ""
echo "🤖 Запуск Telegram бота..."
echo "=========================================="
cd /app
exec python main.py
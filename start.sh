#!/bin/bash
echo "=========================================="
echo "🚀 AI PhotoStudio - Запуск (Render.com)"
echo "=========================================="
echo "📅 Дата: $(date)"
echo "=========================================="

# Устанавливаем переменные окружения если не заданы
export PORT=${PORT:-8080}
export WEBHOOK_URL=${WEBHOOK_URL:-"https://ai-photoface.onrender.com/webhook"}

# Запускаем бота
python main.py

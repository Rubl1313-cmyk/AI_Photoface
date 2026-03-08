#!/bin/bash
echo "=========================================="
echo "🚀 AI PhotoStudio Pro v2.0 - Ultra Realistic"
echo "=========================================="
echo "📅 Дата: $(date)"
echo " Phoenix 1.0 + Enhanced FaceFusion"
echo "=========================================="

# Устанавливаем переменные окружения если не заданы
export PORT=${PORT:-8080}
export WEBHOOK_URL=${WEBHOOK_URL:-"https://ai-photoface.onrender.com/webhook"}

# Запускаем бота
python main.py

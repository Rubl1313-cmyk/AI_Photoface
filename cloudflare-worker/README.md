# 🌐 Cloudflare Worker - AI Image Generation

## 📁 Файлы:
- `worker.js` - основной код воркера
- `wrangler.toml` - конфигурация Cloudflare
- `package.json` - зависимости

## 🚀 Развертывание:

### 1. Установка Wrangler:
```bash
npm install -g wrangler
```

### 2. Авторизация:
```bash
wrangler login
```

### 3. Развертывание:
```bash
cd cloudflare-worker
npm install
wrangler deploy
```

## 🎯 Модели:

### Phoenix 1.0 (`@cf/leonardo/phoenix-1.0`)
- **Лучший для:** креативных промптов, текста
- **Скорость:** ~5 секунд
- **Качество:** высокое

### Lucid Origin (`@cf/leonardo/lucid-origin`)
- **Лучший для:** фотореализма, портретов
- **Скорость:** ~4 секунды
- **Качество:** максимальное

### SDXL Lightning (`@cf/stabilityai/stable-diffusion-xl-base-1.0`)
- **Лучший для:** быстрой генерации
- **Скорость:** ~3 секунды
- **Качество:** хорошее

### SDXL Turbo (`@cf/stabilityai/stable-diffusion-xl-turbo`)
- **Лучший для:** превью
- **Скорость:** ~1-2 секунды
- **Качество:** базовое

## 📡 API Эндпоинты:

### POST / (генерация изображения)
```json
{
  "prompt": "beautiful sunset over the ocean",
  "model": "lucid",
  "width": 1024,
  "height": 1024,
  "steps": 25,
  "guidance": 4.0,
  "negative_prompt": "ugly, blurry"
}
```

### POST / (inpainting)
```json
{
  "prompt": "person on the beach",
  "image_b64": "base64_encoded_image",
  "mask_b64": "base64_encoded_mask",
  "strength": 0.8,
  "model": "lucid"
}
```

## 🔧 Использование в боте:

```python
# В боте:
CF_WORKER_URL = "https://ai-image-generator.your-subdomain.workers.dev"

# Запрос на генерацию:
response = await client.post(f"{CF_WORKER_URL}", json={
    "prompt": "professional portrait",
    "model": "lucid"
})
```

## 📊 Производительность:
- **CPU лимит:** 50 секунд
- **Память:** 128MB
- **Параллельные запросы:** до 1000

## 💡 Особенности:
- Автоматическое улучшение промптов
- CORS поддержка
- Логирование запросов
- Обработка ошибок

После развертывания получи URL: `https://ai-image-generator.your-subdomain.workers.dev`

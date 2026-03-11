# 🤖 FaceFusion API - HuggingFace Space

## 📁 Файлы:
- `app.py` - FastAPI сервер
- `requirements.txt` - зависимости
- `README.md` - документация

## 🚀 Развертывание на HuggingFace:

### 1. Создай новый Space:
1. Зайди на [huggingface.co/spaces](https://huggingface.co/spaces)
2. Нажми "Create new Space"
3. Выбери "Docker" template
4. Назови: `facefusion-api`

### 2. Загрузи файлы:
```bash
git clone https://huggingface.co/spaces/your-username/facefusion-api
cd facefusion-api
# Скопируй файлы из huggingface-space/
git add .
git commit -m "Add FaceFusion API"
git push
```

### 3. Space автоматически развернется!

## 📡 API Эндпоинты:

### POST /swap - Замена лица
```python
import requests

files = {
    'target': open('target.jpg', 'rb'),
    'source': open('source.jpg', 'rb')
}

data = {
    'face_enhancer': 'true',
    'face_swapper_model': 'inswapper_128',
    'face_enhancer_model': 'gfpgan_1.4'
}

response = requests.post('https://your-space.hf.space/swap', files=files, data=data)
```

### POST /enhance - Улучшение лица
```python
files = {'image': open('photo.jpg', 'rb')}
data = {'enhancer_model': 'gfpgan_1.4'}

response = requests.post('https://your-space.hf.space/enhance', files=files, data=data)
```

### GET /models - Доступные модели
```python
response = requests.get('https://your-space.hf.space/models')
models = response.json()
```

## 🎯 Особенности:

### 🔄 Методы замены лиц:
- **InSwapper 128** - быстрый и точный
- **SimSwap** - высокое качество
- **Poisson Blending** - бесшовное смешивание
- **Seamless Cloning** - профессиональное качество

### 🔧 Улучшение качества:
- **GFPGAN 1.4** - восстановление лиц
- **CodeFormer** - улучшение деталей
- **Автоматическая постобработка**

### 📊 Анализ:
- Детекция лиц
- Оценка качества
- Рекомендации по улучшению

## 🔧 Интеграция с ботом:

```python
# В Railway боте:
FACEFUSION_URL = "https://your-space.hf.space"

# Замена лица:
async def swap_faces(source_bytes, target_bytes):
    files = {
        'target': ('target.jpg', target_bytes, 'image/jpeg'),
        'source': ('source.jpg', source_bytes, 'image/jpeg')
    }
    
    data = {
        'face_enhancer': 'true',
        'face_swapper_model': 'inswapper_128'
    }
    
    async with httpx.AsyncClient() as client:
        response = await client.post(f"{FACEFUSION_URL}/swap", files=files, data=data)
        return response.content
```

## 📈 Производительность:

### Лимиты HuggingFace Spaces:
- **CPU**: 2 cores
- **RAM**: 16GB
- **GPU**: T4 (если выбран GPU space)
- **Время**: до 30 минут на сессию

### Оптимизация:
- Кэширование моделей
- Пакетная обработка
- Автоматическая очистка

## 💡 Советы:

1. **Используй GPU Space** для ускорения
2. **Оптимизируй изображения** перед отправкой
3. **Кэшируй результаты** для повторных запросов
4. **Мониторь использование** ресурсов

## 🔗 После развертывания:

Получи URL: `https://your-space.hf.space`

Добавь в Railway переменные:
```env
FACEFUSION_URL=https://your-space.hf.space
```

**Готово для интеграции с ботом!** 🚀

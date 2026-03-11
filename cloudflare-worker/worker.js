// 🌐 Cloudflare Worker - Генерация изображений
// Использует Phoenix 1.0 и Lucid Origin - лучшие модели 2024

addEventListener('fetch', event => {
  event.respondWith(handleRequest(event.request))
})

async function handleRequest(request) {
  if (request.method === 'POST') {
    try {
      const body = await request.json()
      return await generateImage(body)
    } catch (error) {
      return new Response(JSON.stringify({ error: error.message }), {
        status: 400,
        headers: { 'Content-Type': 'application/json' }
      })
    }
  }
  
  return new Response('Cloudflare Worker - AI Image Generation', { status: 200 })
}

async function generateImage(body) {
  const { 
    prompt, 
    width = 1024, 
    height = 1024, 
    steps = 25, 
    guidance = 4.0,
    negative_prompt = '',
    image_b64,
    mask_b64,
    strength = 0.8,
    guidance_scale = 6.0,
    num_steps = 25,
    model = '@cf/leonardo/lucid-origin'  // Lucid по умолчанию для фотореализма
  } = body

  // Выбор модели
  let selectedModel = model
  if (model === 'phoenix') {
    selectedModel = '@cf/leonardo/phoenix-1.0'
  } else if (model === 'lucid') {
    selectedModel = '@cf/leonardo/lucid-origin'
  } else if (model === 'sdxl_lightning') {
    selectedModel = '@cf/stabilityai/stable-diffusion-xl-base-1.0'
  } else if (model === 'sdxl_turbo') {
    selectedModel = '@cf/stabilityai/stable-diffusion-xl-turbo'
  }

  try {
    let inputs
    
    if (image_b64 && mask_b64) {
      // Inpainting для фотосессии с заменой лица
      inputs = {
        prompt: enhancePrompt(prompt),
        image: decodeBase64(image_b64),
        mask: decodeBase64(mask_b64),
        width,
        height,
        strength,
        guidance_scale: guidance_scale,
        num_steps: Math.min(num_steps, 25),
        negative_prompt: enhanceNegativePrompt(negative_prompt)
      }
    } else {
      // Обычная генерация
      inputs = {
        prompt: enhancePrompt(prompt),
        width,
        height,
        steps: Math.min(steps, 25),
        guidance,
        negative_prompt: enhanceNegativePrompt(negative_prompt)
      }
    }

    console.log(`🎨 Generating with ${selectedModel}: ${prompt.substring(0, 50)}...`)
    
    const response = await ai.run(selectedModel, inputs)
    
    // Конвертация в JPEG
    const jpegBuffer = await convertToJPEG(response)
    
    return new Response(jpegBuffer, {
      status: 200,
      headers: { 
        'Content-Type': 'image/jpeg',
        'Cache-Control': 'no-cache',
        'Access-Control-Allow-Origin': '*'
      }
    })
    
  } catch (error) {
    console.error('❌ Generation error:', error)
    return new Response(JSON.stringify({ 
      error: 'Generation failed',
      details: error.message 
    }), {
      status: 500,
      headers: { 'Content-Type': 'application/json' }
    })
  }
}

function enhancePrompt(prompt) {
  // Улучшение промпта для лучшего качества
  const enhancements = [
    'ultra realistic',
    'professional photography', 
    'sharp focus',
    'natural lighting',
    'high quality',
    'detailed',
    '8k resolution'
  ]
  
  // Добавляем улучшения, если их еще нет
  let enhanced = prompt
  enhancements.forEach(enhancement => {
    if (!enhanced.toLowerCase().includes(enhancement.toLowerCase())) {
      enhanced += `, ${enhancement}`
    }
  })
  
  return enhanced
}

function enhanceNegativePrompt(negative) {
  // Улучшение негативного промпта
  const negatives = [
    'cartoon',
    'anime', 
    'artificial',
    'ugly',
    'deformed',
    'blurry',
    'low quality',
    'jpeg artifacts',
    'oversaturated',
    'overcontrasted',
    'noisy',
    'grainy',
    'signature',
    'watermark',
    'text'
  ]
  
  let enhanced = negative
  negatives.forEach(negative => {
    if (!enhanced.toLowerCase().includes(negative.toLowerCase())) {
      enhanced += `, ${negative}`
    }
  })
  
  return enhanced
}

function decodeBase64(base64String) {
  // Декодирование base64
  const binaryString = atob(base64String)
  const bytes = new Uint8Array(binaryString.length)
  
  for (let i = 0; i < binaryString.length; i++) {
    bytes[i] = binaryString.charCodeAt(i)
  }
  
  return bytes
}

async function convertToJPEG(imageBuffer) {
  // Конвертация изображения в JPEG
  try {
    // В реальном worker может потребоваться дополнительная обработка
    // Сейчас просто возвращаем как есть
    return imageBuffer
  } catch (error) {
    console.error('❌ JPEG conversion error:', error)
    return imageBuffer
  }
}

// Информация о доступных моделях
const MODELS = {
  phoenix: {
    name: 'Phoenix 1.0',
    description: 'Лучший для промптов и текста',
    model: '@cf/leonardo/phoenix-1.0',
    best_for: 'creative_prompts'
  },
  lucid: {
    name: 'Lucid Origin', 
    description: 'Лучший для фотореализма',
    model: '@cf/leonardo/lucid-origin',
    best_for: 'photorealistic'
  },
  sdxl_lightning: {
    name: 'SDXL Lightning',
    description: 'Быстрая генерация',
    model: '@cf/stabilityai/stable-diffusion-xl-base-1.0',
    best_for: 'speed'
  },
  sdxl_turbo: {
    name: 'SDXL Turbo',
    description: 'Молниеносная генерация',
    model: '@cf/stabilityai/stable-diffusion-xl-turbo',
    best_for: 'preview'
  }
}

// Эндпоинт для информации о моделях
addEventListener('scheduled', event => {
  event.waitUntil(handleScheduled())
})

async function handleScheduled() {
  console.log('🔄 Worker heartbeat')
}

// CORS поддержка
function handleCORS(request) {
  const corsHeaders = {
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type',
  }

  if (request.method === 'OPTIONS') {
    return new Response(null, { headers: corsHeaders })
  }

  return corsHeaders
}

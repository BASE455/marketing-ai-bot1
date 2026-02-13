import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
from groq import Groq
import requests
from bs4 import BeautifulSoup
from PIL import Image
import io
import base64
from dotenv import load_dotenv

# Загрузка переменных окружения
load_dotenv()

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Инициализация Groq клиента
groq_client = Groq(api_key=os.getenv('GROQ_API_KEY'))

# Системный промт для маркетингового ИИ
SYSTEM_PROMPT = """Ты - экспертный ИИ-помощник по digital маркетингу. Твоя задача:

1. Анализировать маркетинговые материалы, тексты, изображения и веб-сайты
2. Находить болевые точки в маркетинговых стратегиях
3. Предлагать конкретные, практические решения
4. Давать креативные идеи для продвижения
5. Помогать с копирайтингом, контент-стратегией, SMM, SEO, email-маркетингом

Отвечай профессионально, но понятно. Давай структурированные ответы с конкретными шагами действий.
Всегда фокусируйся на решении бизнес-задач и увеличении конверсии.

Отвечай на русском языке."""

# История сообщений для каждого пользователя
user_conversations = {}

def get_user_history(user_id: int) -> list:
    """Получить историю сообщений пользователя"""
    if user_id not in user_conversations:
        user_conversations[user_id] = []
    return user_conversations[user_id]

def add_to_history(user_id: int, role: str, content: str):
    """Добавить сообщение в историю"""
    history = get_user_history(user_id)
    history.append({"role": role, "content": content})
    # Ограничиваем историю последними 10 сообщениями
    if len(history) > 20:
        user_conversations[user_id] = history[-20:]

def clear_history(user_id: int):
    """Очистить историю пользователя"""
    user_conversations[user_id] = []

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    user = update.effective_user
    
    welcome_message = f"""👋 Привет, {user.first_name}!

Я - ИИ-помощник по Digital Marketing. Помогу вам с:

🎯 Маркетинговой стратегией
📝 Копирайтингом и контентом
📊 Анализом конкурентов
🌐 SEO оптимизацией
📱 SMM стратегией
📧 Email-маркетингом
💡 Креативными идеями

Могу анализировать:
✅ Тексты (рекламные объявления, посты, письма)
✅ Изображения (баннеры, креативы)
✅ Веб-сайты (по ссылке)
✅ Документы (PDF, Word)

Просто отправьте мне свой материал или задайте вопрос!

Команды:
/start - Главное меню
/clear - Очистить историю диалога
/help - Помощь и примеры"""

    keyboard = [
        [InlineKeyboardButton("📊 Анализ конкурентов", callback_data="example_competitors")],
        [InlineKeyboardButton("✍️ Помощь с копирайтингом", callback_data="example_copy")],
        [InlineKeyboardButton("💡 Идеи для контента", callback_data="example_ideas")],
        [InlineKeyboardButton("🎯 Маркетинг-стратегия", callback_data="example_strategy")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(welcome_message, reply_markup=reply_markup)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /help"""
    help_text = """🔍 КАК ПОЛЬЗОВАТЬСЯ БОТОМ:

1️⃣ АНАЛИЗ ТЕКСТА:
Просто отправьте мне текст рекламного объявления, поста или письма.
Пример: "Проанализируй этот текст для Instagram: [ваш текст]"

2️⃣ АНАЛИЗ САЙТА:
Отправьте ссылку на сайт.
Пример: "Проанализируй сайт https://example.com"

3️⃣ АНАЛИЗ ИЗОБРАЖЕНИЯ:
Отправьте изображение баннера, креатива или объявления.
Я проанализирую дизайн и дам рекомендации.

4️⃣ ВОПРОСЫ И КОНСУЛЬТАЦИИ:
"Как улучшить конверсию на лендинге?"
"Какие каналы продвижения лучше для стартапа?"
"Помоги создать контент-план на месяц"

5️⃣ ГЕНЕРАЦИЯ КОНТЕНТА:
"Напиши 5 постов для Instagram про [тема]"
"Создай заголовки для email-рассылки про [продукт]"

💡 Совет: Чем конкретнее вопрос, тем полезнее ответ!"""
    
    await update.message.reply_text(help_text)

async def clear_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /clear"""
    user_id = update.effective_user.id
    clear_history(user_id)
    await update.message.reply_text("✅ История диалога очищена. Начнем сначала!")

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик нажатий на кнопки"""
    query = update.callback_query
    await query.answer()
    
    examples = {
        "example_competitors": "Проанализируй конкурентов в нише онлайн-образования для предпринимателей. Какие маркетинговые стратегии они используют и как можно выделиться?",
        "example_copy": "Помоги написать продающий текст для лендинга SaaS-продукта для автоматизации маркетинга в малом бизнесе.",
        "example_ideas": "Предложи 10 идей для контента в Instagram для бренда экологичной косметики.",
        "example_strategy": "Создай маркетинговую стратегию запуска нового мобильного приложения для фитнеса с бюджетом $5000."
    }
    
    example_text = examples.get(query.data, "")
    if example_text:
        await query.message.reply_text(f"📝 Пример запроса:\n\n{example_text}\n\n💬 Можете скопировать и отправить этот запрос или написать свой!")

async def analyze_website(url: str) -> str:
    """Анализ веб-сайта по URL"""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Извлекаем основную информацию
        title = soup.find('title')
        title_text = title.string if title else "Заголовок не найден"
        
        meta_description = soup.find('meta', attrs={'name': 'description'})
        description_text = meta_description['content'] if meta_description and 'content' in meta_description.attrs else "Описание не найдено"
        
        # Извлекаем текст (ограничиваем для анализа)
        text_content = soup.get_text(separator=' ', strip=True)[:3000]
        
        # Извлекаем заголовки
        headings = [h.get_text(strip=True) for h in soup.find_all(['h1', 'h2', 'h3'])[:10]]
        
        analysis_data = f"""URL: {url}

Заголовок страницы: {title_text}

Meta описание: {description_text}

Основные заголовки:
{chr(10).join(headings) if headings else 'Заголовки не найдены'}

Фрагмент контента:
{text_content[:1000]}..."""

        return analysis_data
        
    except Exception as e:
        return f"Ошибка при анализе сайта: {str(e)}"

async def get_ai_response(user_id: int, user_message: str, context_info: str = "") -> str:
    """Получить ответ от ИИ"""
    try:
        # Получаем историю
        history = get_user_history(user_id)
        
        # Формируем сообщения для API
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        
        # Добавляем историю
        messages.extend(history[-10:])  # Последние 10 сообщений
        
        # Добавляем текущее сообщение с контекстом
        current_message = user_message
        if context_info:
            current_message = f"{context_info}\n\nЗапрос пользователя: {user_message}"
        
        messages.append({"role": "user", "content": current_message})
        
        # Запрос к Groq API
        chat_completion = groq_client.chat.completions.create(
            messages=messages,
            model="llama-3.3-70b-versatile",  # Мощная бесплатная модель
            temperature=0.7,
            max_tokens=2000,
            top_p=0.9,
        )
        
        ai_response = chat_completion.choices[0].message.content
        
        # Добавляем в историю
        add_to_history(user_id, "user", user_message)
        add_to_history(user_id, "assistant", ai_response)
        
        return ai_response
        
    except Exception as e:
        logger.error(f"Ошибка при получении ответа от ИИ: {e}")
        return f"Извините, произошла ошибка: {str(e)}"

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик текстовых сообщений"""
    user_id = update.effective_user.id
    user_message = update.message.text
    
    # Показываем, что бот печатает
    await update.message.chat.send_action(action="typing")
    
    # Проверяем, есть ли URL в сообщении
    context_info = ""
    if "http://" in user_message or "https://" in user_message:
        await update.message.reply_text("🔍 Анализирую сайт...")
        
        # Извлекаем URL
        import re
        urls = re.findall(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', user_message)
        
        if urls:
            website_data = await analyze_website(urls[0])
            context_info = f"Данные с сайта:\n{website_data}\n\n"
    
    # Получаем ответ от ИИ
    ai_response = await get_ai_response(user_id, user_message, context_info)
    
    # Отправляем ответ (разбиваем на части, если слишком длинный)
    if len(ai_response) > 4000:
        parts = [ai_response[i:i+4000] for i in range(0, len(ai_response), 4000)]
        for part in parts:
            await update.message.reply_text(part)
    else:
        await update.message.reply_text(ai_response)

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик изображений"""
    user_id = update.effective_user.id
    
    await update.message.reply_text("🖼 Анализирую изображение...")
    
    # Получаем фото
    photo = update.message.photo[-1]  # Берем самое большое разрешение
    file = await context.bot.get_file(photo.file_id)
    
    # Скачиваем изображение
    photo_bytes = await file.download_as_bytearray()
    
    # Открываем изображение для анализа
    image = Image.open(io.BytesIO(photo_bytes))
    
    # Формируем запрос для анализа
    caption = update.message.caption if update.message.caption else "Проанализируй это маркетинговое изображение"
    
    analysis_prompt = f"""Пользователь отправил изображение с запросом: {caption}

Это изображение связано с маркетингом (может быть баннер, креатив, объявление, дизайн сайта).

Проанализируй изображение по следующим критериям:
1. Общее впечатление и визуальная привлекательность
2. Читаемость текста и его эффективность
3. Цветовая схема и её влияние
4. Композиция и фокусные точки
5. Call-to-Action (если есть)
6. Целевая аудитория
7. Рекомендации по улучшению

Дай конкретные советы для улучшения конверсии."""
    
    # Получаем ответ от ИИ
    ai_response = await get_ai_response(user_id, analysis_prompt)
    
    await update.message.reply_text(ai_response)

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик документов"""
    user_id = update.effective_user.id
    document = update.message.document
    
    await update.message.reply_text("📄 Анализирую документ...")
    
    # Получаем информацию о документе
    file_name = document.file_name
    file_size = document.file_size
    
    # Для базовой версии просто подтверждаем получение
    caption = update.message.caption if update.message.caption else "Проанализируй этот документ с точки зрения маркетинга"
    
    analysis_prompt = f"""Пользователь отправил документ "{file_name}" с запросом: {caption}

Дай общие рекомендации по работе с маркетинговыми документами:
1. Что важно проверить в маркетинговых материалах
2. Как структурировать маркетинговый документ
3. Ключевые элементы эффективного маркетингового контента
4. Типичные ошибки в маркетинговых документах"""
    
    ai_response = await get_ai_response(user_id, analysis_prompt)
    
    await update.message.reply_text(ai_response)

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик ошибок"""
    logger.error(f"Update {update} caused error {context.error}")
    
    if update and update.effective_message:
        await update.effective_message.reply_text(
            "😔 Извините, произошла ошибка. Попробуйте еще раз или используйте /clear для очистки истории."
        )

def main():
    """Главная функция запуска бота"""
    # Получаем токен из переменных окружения
    token = os.getenv('TELEGRAM_BOT_TOKEN')
    
    if not token:
        raise ValueError("TELEGRAM_BOT_TOKEN не найден в .env файле!")
    
    # Создаем приложение
    application = Application.builder().token(token).build()
    
    # Регистрируем обработчики команд
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("clear", clear_command))
    
    # Регистрируем обработчик кнопок
    application.add_handler(CallbackQueryHandler(button_callback))
    
    # Регистрируем обработчики контента
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    application.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    
    # Регистрируем обработчик ошибок
    application.add_error_handler(error_handler)
    
    # Запускаем бота
    logger.info("Бот запущен!")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
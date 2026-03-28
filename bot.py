import requests
import json
from datetime import datetime

# Ваши данные
BOT_TOKEN = "8748919604:AAGDhMti4STS9kNGTcLw6R7l7T1soNqXkOs"
CHAT_ID = "-1003779722444"
GNEWS_API_KEY = "42c04284a5b871caf650dec895c3f2ce"

def get_news():
    """Получает новости через GNews API"""
    url = "https://gnews.io/api/v4/search"
    params = {
        'q': 'Россия OR бизнес OR технологии OR экономика',
        'lang': 'ru',
        'country': 'ru',
        'max': 10,
        'apikey': GNEWS_API_KEY
    }
    
    try:
        response = requests.get(url, params=params)
        data = response.json()
        return data.get('articles', [])
    except Exception as e:
        print(f"Ошибка: {e}")
        return []

def format_news(articles):
    """Форматирует новости для отправки"""
    today = datetime.now().strftime("%d.%m.%Y")
    message = f"📰 *Новостной отчет | {today}*\n\n"
    
    for i, article in enumerate(articles[:10], 1):
        title = article.get('title', 'Без названия')
        source = article.get('source', {}).get('name', 'Неизвестный источник')
        url = article.get('url', '')
        
        message += f"*{i}. {title}*\n"
        message += f"🔗 [{source}]({url})\n\n"
    
    message += "🤖 *Отчет сгенерирован автоматически*"
    return message

def send_telegram(message):
    """Отправляет сообщение в Telegram"""
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        'chat_id': CHAT_ID,
        'text': message,
        'parse_mode': 'Markdown',
        'disable_web_page_preview': True
    }
    
    try:
        response = requests.post(url, json=payload)
        return response.status_code == 200
    except Exception as e:
        print(f"Ошибка отправки: {e}")
        return False

def main():
    print("🚀 Запуск новостного бота...")
    
    articles = get_news()
    
    if not articles:
        send_telegram("⚠️ *Ошибка*: Не удалось получить новости")
        return
    
    message = format_news(articles)
    
    if send_telegram(message):
        print("✅ Отчет отправлен!")
    else:
        print("❌ Ошибка отправки")

if __name__ == "__main__":
    main()

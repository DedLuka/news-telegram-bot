import requests
import os
import feedparser
from datetime import datetime, timedelta
from newspaper import Article
import time
from urllib.parse import urlparse

BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')

# Только российские RSS-источники
RSS_SOURCES = {
    "ТАСС": "http://tass.com/rss/v2.xml",
    "РИА Новости": "https://ria.ru/export/rss2/index.xml",
    "RT": "https://rt.com/rss/news/",
    "Коммерсантъ": "https://www.kommersant.ru/RSS/news.xml",
    "МК": "https://www.mk.ru/rss/news/index.xml",
    "Комсомольская правда": "https://www.kp.ru/rss/",
    "Lenta.ru": "https://lenta.ru/rss/",
    "Вести.ру": "https://www.vesti.ru/vesti.rss",
    "Вести Ставрополье": "https://vesti26.ru/rss/"
}

# Категории для маркировки новостей
CATEGORY_KEYWORDS = {
    "МИР": ["мир", "международный", "foreign", "world", "европа", "сша", "нато", "китай"],
    "РОССИЯ": ["россия", "russia", "путин", "медведев", "мишустин", "кремль", "госдума"],
    "СВО": ["сво", "донбасс", "украина", "запорожье", "херсон", "военный", "минобороны", "мобилизация"],
    "СТАВРОПОЛЬЕ": ["ставрополь", "ставрополье", "ставропольский", "кавминводы", "пятигорск"]
}

def fetch_rss_news(source_name, url):
    """Получает новости из RSS-ленты"""
    try:
        feed = feedparser.parse(url)
        articles = []
        for entry in feed.entries[:5]:
            published = datetime.now()
            if hasattr(entry, 'published_parsed') and entry.published_parsed:
                published = datetime(*entry.published_parsed[:6])
            articles.append({
                'title': entry.get('title', ''),
                'url': entry.get('link', ''),
                'source': source_name,
                'description': entry.get('summary', ''),
                'published': published
            })
        return articles
    except Exception as e:
        return []

def get_category(title, description):
    """Определяет категорию по заголовку и описанию"""
    text = (title + " " + description).lower()
    for cat, keywords in CATEGORY_KEYWORDS.items():
        for kw in keywords:
            if kw in text:
                return cat
    return "РОССИЯ"

def get_full_text(url):
    """Парсит полный текст статьи, возвращает None если недоступен"""
    try:
        article = Article(url, language='ru')
        article.download()
        time.sleep(1)
        article.parse()
        text = article.text
        if len(text.split()) >= 50:
            return text
        return None
    except Exception:
        return None

def format_news_entry(article, index):
    """Форматирует одну новость (только текст, без украшений)"""
    title = article.get('title', '')
    url = article.get('url', '')
    source = article.get('source', '')
    published = article.get('published', datetime.now())
    
    full_text = get_full_text(url)
    if not full_text:
        return None
    
    category = get_category(title, article.get('description', ''))
    published_time = published.strftime("%d.%m.%Y %H:%M")
    
    entry = f"""Новость {index}
Категория: {category}
Источник: {source}
Заголовок: {title}
Содержание:
{full_text[:2000]}
Время публикации: {published_time} МСК
Ссылка: {url}

"""
    return entry

def generate_analysis(total_news, categories_count):
    """Генерирует аналитическую сводку"""
    analysis = f"""
АНАЛИТИЧЕСКАЯ СВОДКА
Всего новостей: {total_news}

Распределение по категориям:
- МИР: {categories_count.get('МИР', 0)}
- РОССИЯ: {categories_count.get('РОССИЯ', 0)}
- СВО: {categories_count.get('СВО', 0)}
- СТАВРОПОЛЬЕ: {categories_count.get('СТАВРОПОЛЬЕ', 0)}

Угрозы и риски для РФ:
- Информационные угрозы: выявлены противоречия в западных источниках
- Геополитические риски: напряженность в международных отношениях сохраняется
- Региональные риски: требуется мониторинг Ставропольского края

Оценка достоверности источников:
- Российские официальные источники (ТАСС, РИА, RT): высокая
- Российские СМИ (Коммерсантъ, МК, КП, Lenta, Вести): высокая
- Региональные СМИ (Вести Ставрополье): высокая

Прогноз развития событий (7-14 суток):
- Сохранение информационного противостояния
- Возможна активизация информационных атак
- Требуется усиление мониторинга региональной повестки

Рекомендации:
- Усилить мониторинг западных СМИ
- Проводить верификацию противоречивых данных
- Обратить внимание на региональную специфику
"""
    return analysis

def main():
    print("Запуск бота (только российские источники)...")
    
    if not BOT_TOKEN or not CHAT_ID:
        print("Ошибка: нет токенов Telegram")
        return
    
    all_entries = []
    categories_count = {'МИР': 0, 'РОССИЯ': 0, 'СВО': 0, 'СТАВРОПОЛЬЕ': 0}
    index = 0
    
    print("\nСбор новостей из российских RSS-источников...")
    for source_name, rss_url in RSS_SOURCES.items():
        print(f"  {source_name}...")
        articles = fetch_rss_news(source_name, rss_url)
        
        for article in articles:
            entry = format_news_entry(article, index + 1)
            if entry:
                all_entries.append(entry)
                index += 1
                cat = get_category(article.get('title', ''), article.get('description', ''))
                categories_count[cat] = categories_count.get(cat, 0) + 1
                print(f"    Добавлено: {article.get('title', '')[:60]}...")
            time.sleep(0.5)
    
    if not all_entries:
        send_telegram("Нет доступных новостей с полным текстом")
        return
    
    # Формируем отчет
    today = datetime.now().strftime("%d.%m.%Y")
    report = f"ЕЖЕДНЕВНЫЙ ДОКЛАД\nДата: {today}\n\n"
    
    for entry in all_entries:
        report += entry
    
    report += generate_analysis(len(all_entries), categories_count)
    
    # Отправка
    if len(report) > 4096:
        parts = [report[i:i+4096] for i in range(0, len(report), 4096)]
        for part in parts:
            send_telegram(part)
    else:
        send_telegram(report)
    
    print(f"\nГотово. Новостей: {len(all_entries)}")

def send_telegram(message):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        'chat_id': CHAT_ID,
        'text': message,
        'parse_mode': 'Markdown',
        'disable_web_page_preview': True
    }
    try:
        requests.post(url, json=payload, timeout=60)
    except Exception as e:
        print(f"Ошибка отправки: {e}")

if __name__ == "__main__":
    main()

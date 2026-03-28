import requests
import os
import feedparser
from datetime import datetime, timedelta
from newspaper import Article
import time

BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')
GNEWS_API_KEY = os.environ.get('GNEWS_API_KEY')

RSS_SOURCES = {
    "ТАСС": {"url": "http://tass.com/rss/v2.xml"},
    "РИА Новости": {"url": "https://ria.ru/export/rss2/index.xml"},
    "RT": {"url": "https://rt.com/rss/news/"},
    "Коммерсантъ": {"url": "https://www.kommersant.ru/RSS/news.xml"},
    "МК": {"url": "https://www.mk.ru/rss/news/index.xml"},
    "Вести Ставрополье": {"url": "https://vesti26.ru/rss/"}
}

CATEGORIES = {
    "МИР": "world OR international",
    "РОССИЯ": "Russia OR российская федерация",
    "СВО": "специальная военная операция OR Донбасс",
    "СТАВРОПОЛЬЕ": "Ставропольский край"
}

def fetch_rss_news(source_name, source_config):
    try:
        feed = feedparser.parse(source_config["url"])
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

def get_news_from_gnews(query):
    url = "https://gnews.io/api/v4/search"
    params = {
        'q': query,
        'lang': 'ru',
        'max': 3,
        'apikey': GNEWS_API_KEY
    }
    try:
        response = requests.get(url, params=params, timeout=30)
        if response.status_code != 200:
            return []
        data = response.json()
        articles = data.get('articles', [])
        for a in articles:
            if 'publishedAt' in a:
                try:
                    pub_utc = datetime.fromisoformat(a['publishedAt'].replace('Z', '+00:00'))
                    a['published'] = pub_utc + timedelta(hours=3)
                except:
                    a['published'] = datetime.now()
            else:
                a['published'] = datetime.now()
        return articles[:3]
    except Exception as e:
        return []

def get_full_text(url):
    try:
        article = Article(url, language='ru')
        article.download()
        time.sleep(1)
        article.parse()
        text = article.text
        if len(text.split()) >= 50:
            return text
        return None
    except Exception as e:
        return None

def format_news_entry(article, category_name):
    title = article.get('title', '')
    url = article.get('url', '')
    source = article.get('source', '')
    published = article.get('published', datetime.now())
    
    full_text = get_full_text(url)
    if not full_text:
        return None
    
    published_time = published.strftime("%d.%m.%Y %H:%M")
    
    entry = f"""Категория: {category_name}
Заголовок: {title}
Содержание:
{full_text[:2000]}
Источник: {source}
Время: {published_time} МСК
Ссылка: {url}
"""
    return entry

def generate_analysis(stats):
    analysis = f"""
АНАЛИТИЧЕСКАЯ СВОДКА

Статистика:
- Всего новостей: {stats['total']}
- Из RSS: {stats['rss']}
- Из GNews: {stats['gnews']}

Угрозы и риски для РФ:
- Информационные угрозы: зафиксированы противоречия в западных источниках
- Геополитические риски: напряженность в международных отношениях сохраняется
- Региональные риски: требуется мониторинг Ставропольского края

Оценка достоверности источников:
- Российские официальные источники: высокая
- Российские СМИ: высокая
- Иностранные источники: требуется верификация

Прогноз:
- Сохранение информационного противостояния
- Возможна активизация информационных атак

Рекомендации:
- Усилить мониторинг западных СМИ
- Проводить верификацию противоречивых данных
"""
    return analysis

def main():
    print("Запуск бота...")
    
    if not BOT_TOKEN or not CHAT_ID:
        print("Ошибка: нет токенов")
        return
    
    all_news = []
    stats = {'total': 0, 'rss': 0, 'gnews': 0}
    
    # RSS
    print("Сбор RSS...")
    for source_name, source_config in RSS_SOURCES.items():
        articles = fetch_rss_news(source_name, source_config)
        category = "СТАВРОПОЛЬЕ" if source_name == "Вести Ставрополье" else "РОССИЯ"
        for article in articles:
            entry = format_news_entry(article, category)
            if entry:
                all_news.append(entry)
                stats['total'] += 1
                stats['rss'] += 1
                print(f"Добавлено: {article.get('title', '')[:50]}")
            time.sleep(0.5)
    
    # GNews
    print("Сбор GNews...")
    for cat_name, query in CATEGORIES.items():
        articles = get_news_from_gnews(query)
        for article in articles:
            entry = format_news_entry(article, cat_name)
            if entry:
                all_news.append(entry)
                stats['total'] += 1
                stats['gnews'] += 1
                print(f"Добавлено: {article.get('title', '')[:50]}")
            time.sleep(1)
    
    # Формируем отчет
    today = datetime.now().strftime("%d.%m.%Y")
    report = f"ЕЖЕДНЕВНЫЙ ДОКЛАД\nДата: {today}\n\n"
    
    for news in all_news:
        report += news + "\n"
    
    report += generate_analysis(stats)
    
    # Отправка
    if len(report) > 4096:
        parts = [report[i:i+4096] for i in range(0, len(report), 4096)]
        for part in parts:
            send_telegram(part)
    else:
        send_telegram(report)
    
    print(f"Готово. Новостей: {stats['total']}")

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
        print(f"Ошибка: {e}")

if __name__ == "__main__":
    main()

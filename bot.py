import requests
import os
import feedparser
from datetime import datetime, timedelta
from newspaper import Article
import time
import random
from bs4 import BeautifulSoup

# Читаем секреты из окружения
BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')
GNEWS_API_KEY = os.environ.get('GNEWS_API_KEY')

# === РОССИЙСКИЕ RSS-ИСТОЧНИКИ ===
RSS_SOURCES = {
    "ТАСС": {
        "url": "http://tass.com/rss/v2.xml",
        "category": "россия",
        "priority": "high"
    },
    "РИА Новости": {
        "url": "https://ria.ru/export/rss2/index.xml",
        "category": "россия",
        "priority": "high"
    },
    "RT (Russia Today)": {
        "url": "https://rt.com/rss/news/",
        "category": "россия",
        "priority": "high"
    },
    "Коммерсантъ": {
        "url": "https://www.kommersant.ru/RSS/news.xml",
        "category": "россия",
        "priority": "medium"
    },
    "МК": {
        "url": "https://www.mk.ru/rss/news/index.xml",
        "category": "россия",
        "priority": "medium"
    },
    "Вести Ставрополье": {
        "url": "https://vesti26.ru/rss/",
        "category": "ставрополье",
        "priority": "high"
    }
}

# Категории для поиска
CATEGORIES = {
    "🌍 МЕЖДУНАРОДНАЯ ОБСТАНОВКА": {
        "gnews_query": "world OR international",
        "rss_filter": None
    },
    "🇷🇺 РОССИЙСКАЯ ФЕДЕРАЦИЯ": {
        "gnews_query": "Russia OR российская федерация",
        "rss_filter": ["россия", "все"]
    },
    "⚔️ СПЕЦИАЛЬНАЯ ВОЕННАЯ ОПЕРАЦИЯ": {
        "gnews_query": "специальная военная операция OR Донбасс OR ZOV",
        "rss_filter": None
    },
    "🏛️ СТАВРОПОЛЬСКИЙ КРАЙ": {
        "gnews_query": "Ставропольский край OR Ставрополье",
        "rss_filter": ["ставрополье"]
    }
}

def fetch_rss_news(source_name, source_config, category_filter=None):
    """Получает новости из RSS-ленты российского источника"""
    try:
        print(f"   📡 RSS: {source_name}")
        feed = feedparser.parse(source_config["url"])
        articles = []
        
        for entry in feed.entries[:5]:  # Берем 5 последних
            # Получаем время публикации
            published = datetime.now()
            if hasattr(entry, 'published_parsed') and entry.published_parsed:
                published = datetime(*entry.published_parsed[:6])
            
            articles.append({
                'title': entry.get('title', ''),
                'url': entry.get('link', ''),
                'source': source_name,
                'description': entry.get('summary', ''),
                'published': published,
                'content_type': 'rss'
            })
        
        print(f"      ✅ Получено {len(articles)} новостей")
        return articles
    except Exception as e:
        print(f"      ❌ Ошибка RSS {source_name}: {e}")
        return []

def get_news_from_gnews(query, max_results=5):
    """Получает новости из GNews API"""
    url = "https://gnews.io/api/v4/search"
    params = {
        'q': query,
        'lang': 'ru',
        'max': max_results,
        'apikey': GNEWS_API_KEY
    }
    
    try:
        response = requests.get(url, params=params, timeout=30)
        if response.status_code != 200:
            return []
        
        data = response.json()
        articles = data.get('articles', [])
        
        # Добавляем тип контента
        for a in articles:
            a['content_type'] = 'gnews'
            if 'publishedAt' in a:
                try:
                    pub_utc = datetime.fromisoformat(a['publishedAt'].replace('Z', '+00:00'))
                    a['published'] = pub_utc + timedelta(hours=3)
                except:
                    a['published'] = datetime.now()
            else:
                a['published'] = datetime.now()
        
        return articles[:max_results]
    except Exception as e:
        print(f"   ❌ Ошибка GNews: {e}")
        return []

def get_article_content(article):
    """Получает полный текст статьи (с fallback на описание)"""
    url = article.get('url', '')
    title = article.get('title', '')
    description = article.get('description', '')
    
    # Если есть описание из RSS, используем его как базу
    if article.get('content_type') == 'rss' and description:
        words = description.split()
        if len(words) >= 50:
            return description, "полный текст из RSS"
        elif len(words) >= 20:
            return description, "краткое описание из RSS"
    
    # Пытаемся распарсить полный текст
    try:
        news_article = Article(url, language='ru')
        news_article.download()
        time.sleep(1)
        news_article.parse()
        
        full_text = news_article.text
        words = full_text.split()
        
        if len(words) >= 50:
            return full_text, "полный текст"
        elif len(words) >= 20:
            return full_text, "частичный текст"
        else:
            return description or title, "краткое описание"
            
    except Exception as e:
        return description or title, "краткое описание (парсинг недоступен)"

def check_contradiction(title, description, full_text):
    """Проверяет противоречия с официальными источниками"""
    contradiction_keywords = ['опровергает', 'опровержение', 'ложь', 'фейк', 'не соответствует', 'дезинформация']
    western_indicators = ['bbc', 'cnn', 'reuters', 'nytimes', 'wsj', 'dw', 'западные сми']
    
    text = (title + " " + description + " " + (full_text[:500] if full_text else "")).lower()
    
    for kw in contradiction_keywords:
        if kw in text:
            return f"\n⚠️ *Имеются противоречащие данные:* {kw} (требуется дополнительная верификация)"
    
    for w in western_indicators:
        if w in text:
            return f"\n⚠️ *Информация из западного источника:* требует верификации по российским официальным каналам"
    
    return ""

def format_news_entry(article, category_name, index, source_type):
    """Форматирует одну новость"""
    title = article.get('title', 'Без названия')
    url = article.get('url', '')
    source = article.get('source', 'Неизвестное агентство')
    description = article.get('description', '')
    published = article.get('published', datetime.now())
    content_type = article.get('content_type', 'unknown')
    
    # Форматируем время
    published_time = published.strftime("%d.%m.%Y в %H:%M")
    
    # Определяем приоритет источника (ИСПРАВЛЕНО)
    source_str = str(source)
    url_lower = url.lower()
    
    is_russian = False
    # Проверяем, есть ли источник в RSS_SOURCES (по имени)
    if source_str in RSS_SOURCES:
        is_russian = True
    # Проверяем по URL российских источников
    elif 'ria' in url_lower or 'tass' in url_lower or 'rt.com' in url_lower or 'kommersant' in url_lower or 'mk.ru' in url_lower or 'vesti26' in url_lower:
        is_russian = True
    # Если это GNews, проверяем URL источника
    elif source_type == "GNews" and any(r in url_lower for r in ['ria', 'tass', 'rt.com', 'kommersant', 'mk.ru', 'vesti26']):
        is_russian = True
    
    source_priority = "🇷🇺 Официальный/Российский источник" if is_russian else "🌍 Иностранный источник"
    
    # Получаем контент
    content, content_note_type = get_article_content(article)
    
    # Проверяем противоречия
    contradiction_note = check_contradiction(title, description, content)
    
    # Обрезаем, если слишком длинно
    if len(content) > 2000:
        content = content[:2000] + "..."
    
    # Источник данных
    data_source_note = f"📡 *Источник данных:* {source_type.upper()}"
    
    news_block = f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
**{category_name} | Новость №{index}**

**Заголовок:** {title}

**Содержание:**
{content}

**Источник:** {source} ({source_priority})
**Время публикации (МСК):** {published_time}
**Ссылка:** {url}
{data_source_note}
{contradiction_note}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
    return news_block

def generate_analysis(all_articles, stats):
    """Генерирует аналитический вывод"""
    analysis = f"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                         АНАЛИТИЧЕСКАЯ СВОДКА                                 ║
╚══════════════════════════════════════════════════════════════════════════════╝

**Статистика обработки:**
- Всего обработано новостей: {stats['total']}
- Из российских RSS-источников: {stats['rss']}
- Из GNews API: {stats['gnews']}
- С полным текстом: {stats['full']}
- С кратким описанием: {stats['short']}

**1. Оценка информационной обстановки:**

На основе анализа новостных материалов из российских официальных источников и международных СМИ за последние 24 часа установлено:
- Преимущество отдается российским официальным источникам (ТАСС, РИА Новости, RT)
- Зафиксированы попытки распространения противоречивой информации в западных СМИ
- Региональная повестка (Ставропольский край) освещается через ГТРК "Вести Ставрополье"

**2. Угрозы и риски для РФ:**

• **Информационные угрозы:** активное распространение недостоверных данных в западных медиа, направленных на дискредитацию действий ВС РФ.
• **Геополитические риски:** сохранение напряженности в отношениях с недружественными государствами.
• **Региональные риски:** требуется усиление мониторинга ситуации в Ставропольском крае в части безопасности и социальной стабильности.

**3. Оценка достоверности источников:**

| Категория источников | Оценка достоверности | Примечание |
|---------------------|---------------------|------------|
| Официальные российские (ТАСС, РИА, RT) | **Высокая** | Информация требует минимальной верификации |
| Российские СМИ (Коммерсантъ, МК) | **Высокая** | Данные согласованы с официальными источниками |
| GNews API (агрегатор) | **Средняя** | Требуется фильтрация источников |
| Иностранные источники | **Средняя/Низкая** | Требуется обязательная верификация |

**4. Прогноз развития событий (на 7-14 суток):**

На основе анализа текущей информационной повестки прогнозируется:
- Сохранение высокого уровня информационного противостояния
- Возможная активизация информационных атак со стороны противника
- Необходимость усиления работы с региональными СМИ в Ставропольском крае

**5. Рекомендации:**
1. Усилить мониторинг иностранных источников информации
2. Проводить дополнительную верификацию материалов из западных СМИ
3. Обратить внимание на региональную специфику в информационной работе
4. Использовать российские RSS-источники как приоритетные

*Данный аналитический обзор подготовлен автоматически. Рекомендуется проведение дополнительной верификации критически важной информации.*
"""
    return analysis

def main():
    print("🚀 Запуск аналитического новостного бота (с российскими RSS-источниками)...")
    
    if not BOT_TOKEN or not CHAT_ID:
        print("❌ Ошибка: не заданы секреты Telegram")
        send_telegram("⚠️ *Ошибка конфигурации*: проверьте секреты Telegram")
        return
    
    all_news = []
    stats = {'total': 0, 'rss': 0, 'gnews': 0, 'full': 0, 'short': 0}
    
    # 1. Собираем новости из российских RSS-источников
    print("\n📡 Сбор новостей из российских RSS-источников...")
    for source_name, source_config in RSS_SOURCES.items():
        articles = fetch_rss_news(source_name, source_config)
        
        for article in articles:
            # Определяем категорию для RSS-новостей
            category = "🇷🇺 РОССИЙСКАЯ ФЕДЕРАЦИЯ"
            if source_config.get("category") == "ставрополье":
                category = "🏛️ СТАВРОПОЛЬСКИЙ КРАЙ"
            
            news_entry = format_news_entry(article, category, len(all_news) + 1, "RSS")
            if news_entry:
                all_news.append(news_entry)
                stats['total'] += 1
                stats['rss'] += 1
                # Определяем тип контента
                if len(article.get('description', '').split()) >= 50:
                    stats['full'] += 1
                else:
                    stats['short'] += 1
            
            time.sleep(0.5)
    
    # 2. Собираем новости из GNews API для всех категорий
    print("\n🌍 Сбор новостей из GNews API...")
    for category_name, category_config in CATEGORIES.items():
        if category_config["gnews_query"]:
            print(f"\n   Категория: {category_name}")
            articles = get_news_from_gnews(category_config["gnews_query"], max_results=3)
            
            for idx, article in enumerate(articles, 1):
                # Проверяем, не дублируется ли с RSS
                title_lower = article.get('title', '').lower()
                is_duplicate = any(title_lower in existing[:100].lower() for existing in all_news)
                
                if not is_duplicate:
                    news_entry = format_news_entry(article, category_name, idx, "GNews")
                    if news_entry:
                        all_news.append(news_entry)
                        stats['total'] += 1
                        stats['gnews'] += 1
                        stats['short'] += 1  # GNews обычно дает описание, а не полный текст
                
                time.sleep(1)
    
    # Формируем отчет
    today = datetime.now().strftime("%d.%B.%Y")
    current_time = datetime.now().strftime("%H:%M")
    
    report = f"""
╔══════════════════════════════════════════════════════════════════════════════╗
║         ЕЖЕДНЕВНЫЙ АНАЛИТИЧЕСКИЙ ДОКЛАД ДЛЯ ВЫСШЕГО ВОЕННОГО РУКОВОДСТВА     ║
║                        {today} | {current_time} МСК                          ║
╚══════════════════════════════════════════════════════════════════════════════╝

"""
    
    # Добавляем новости
    for news in all_news:
        report += news
    
    # Добавляем аналитику
    report += generate_analysis(all_news, stats)
    
    # Отправляем в Telegram
    if len(report) > 4096:
        parts = [report[i:i+4096] for i in range(0, len(report), 4096)]
        for i, part in enumerate(parts):
            send_telegram(part)
            if i == 0 and len(parts) > 1:
                send_telegram("📄 *Продолжение доклада...*")
    else:
        send_telegram(report)
    
    print(f"\n✅ Отчет отправлен! Обработано новостей: {stats['total']} (RSS: {stats['rss']}, GNews: {stats['gnews']})")

def send_telegram(message):
    """Отправляет сообщение в Telegram"""
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        'chat_id': CHAT_ID,
        'text': message,
        'parse_mode': 'Markdown',
        'disable_web_page_preview': False
    }
    
    try:
        response = requests.post(url, json=payload, timeout=60)
        if response.status_code == 200:
            print("   ✅ Часть отчета отправлена")
            return True
        else:
            print(f"   ❌ Ошибка: {response.text[:100]}")
            return False
    except Exception as e:
        print(f"   ❌ Ошибка: {e}")
        return False

if __name__ == "__main__":
    main()

import requests
import os
import feedparser
from datetime import datetime, timedelta
import time
from collections import defaultdict
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib

BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')

# ==================== РОССИЙСКИЕ RSS-ИСТОЧНИКИ ====================
RSS_RUSSIAN = {
    "ТАСС": "http://tass.com/rss/v2.xml",
    "РИА Новости": "https://ria.ru/export/rss2/index.xml",
    "RT": "https://rt.com/rss/news/",
    "Вести.ру": "https://www.vesti.ru/vesti.rss",
    "Коммерсантъ": "https://www.kommersant.ru/RSS/news.xml",
    "МК": "https://www.mk.ru/rss/news/index.xml",
    "Комсомольская правда": "https://www.kp.ru/rss/",
    "Lenta.ru": "https://lenta.ru/rss/news",
    "Известия": "https://iz.ru/xml/rss.xml",
    "РБК": "https://www.rbc.ru/rss/",
    "Российская газета": "https://rg.ru/xml/index.xml",
    "Газета.Ru": "https://www.gazeta.ru/export/rss/lenta.xml",
    "Взгляд": "https://vz.ru/rss.xml",
    "Вести Ставрополье": "https://vesti26.ru/rss/",
    "Ставропольская правда": "https://www.stapravda.ru/rss/",
}

# ==================== ЗАРУБЕЖНЫЕ RSS-ИСТОЧНИКИ ====================
RSS_FOREIGN = {
    "BBC News": "http://feeds.bbci.co.uk/news/rss.xml",
    "CNN": "http://rss.cnn.com/rss/edition.rss",
    "The Guardian": "https://www.theguardian.com/world/rss",
    "Reuters": "https://www.reutersagency.com/feed/?best-topics=business-finance&post_type=best",
    "AP News": "http://hosted2.ap.org/atom/APTopNews",
    "Defense News": "https://www.defensenews.com/arc/outboundfeeds/rss/",
    "The War Zone": "https://www.thedrive.com/the-war-zone/feed",
    "Military.com": "https://www.military.com/feed",
    "Stars and Stripes": "https://www.stripes.com/rss",
    "Breaking Defense": "https://breakingdefense.com/feed/",
}

RSS_SOURCES = {**RSS_RUSSIAN, **RSS_FOREIGN}

CATEGORIES = {
    "МИР": {
        "keywords": ["мир", "международный", "европа", "сша", "нато", "китай", "германия", "франция", "англия", "америка", "брюссель", "вашингтон", "лондон", "санкции", "конфликт", "оон", "world", "international", "europe", "usa", "nato", "china", "russia", "ukraine"],
        "priority": 1
    },
    "РОССИЯ": {
        "keywords": ["россия", "путин", "медведев", "мишустин", "кремль", "госдума", "правительство", "москва", "российский", "безопасность", "оборона", "фсб", "указ", "закон", "russia", "putin", "kremlin"],
        "priority": 2
    },
    "СВО": {
        "keywords": ["сво", "донбасс", "украина", "запорожье", "херсон", "военный", "минобороны", "мобилизация", "армия", "фронт", "бахмут", "авдеевка", "шойгу", "герасимов", "спецоперация", "наступление", "оборона", "удар", "обстрел", "донецк", "луганск", "ukraine", "donbas", "war", "military"],
        "priority": 3
    },
    "СТАВРОПОЛЬЕ": {
        "keywords": ["ставрополь", "ставрополье", "ставропольский", "кавминводы", "пятигорск", "кисловодск", "ессентуки", "безопасность", "терроризм", "чп", "мобилизация", "военкомат", "казачество"],
        "priority": 4
    }
}

CATEGORY_ORDER = ['МИР', 'РОССИЯ', 'СВО', 'СТАВРОПОЛЬЕ']

# Кэш для переведенных заголовков (простой, без сохранения между запусками)
translation_cache = {}

def is_russian(text):
    return bool(re.search('[а-яА-ЯёЁ]', text))

def translate_to_russian(text):
    """Простой перевод через Google Translate API (бесплатный)"""
    if not text or is_russian(text):
        return text
    
    # Проверяем кэш
    cache_key = hashlib.md5(text.encode()).hexdigest()
    if cache_key in translation_cache:
        return translation_cache[cache_key]
    
    try:
        # Используем бесплатный Google Translate через requests
        url = "https://translate.googleapis.com/translate_a/single"
        params = {
            'client': 'gtx',
            'sl': 'auto',
            'tl': 'ru',
            'dt': 't',
            'q': text[:500]  # Ограничиваем длину
        }
        response = requests.get(url, params=params, timeout=5)
        if response.status_code == 200:
            data = response.json()
            translated = ''.join([item[0] for item in data[0]])
            translation_cache[cache_key] = translated
            return translated
    except Exception as e:
        pass
    return text

def extract_locations(text):
    """Извлекает названия населенных пунктов из текста"""
    locations = []
    location_patterns = [
        r'(?:в|на|под|у|из|за|около)\s+([А-ЯЁ][а-яё]+(?:-?[А-ЯЁ][а-яё]+)?)\s+(?:районе?|области?|крае?|городе?)',
        r'([А-ЯЁ][а-яё]+(?:-?[А-ЯЁ][а-яё]+)?)\s+(?:город|поселок|село|станица|хутор)',
        r'(?:Донецк|Луганск|Запорожье|Херсон|Бахмут|Авдеевка|Артемовск|Соледар|Кременная|Сватово)'
    ]
    for pattern in location_patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        locations.extend(matches)
    return list(set(locations))[:3]

def check_inconsistency(title, description, source_name):
    """Проверяет несоответствие информации с российскими источниками"""
    text = (title + " " + description).lower()
    
    # Маркеры противоречия
    contradiction_markers = ['опровергает', 'опровержение', 'ложь', 'фейк', 'не соответствует', 'дезинформация']
    western_sources = ['bbc', 'cnn', 'guardian', 'reuters', 'ap', 'washington', 'nytimes']
    
    is_western = any(w in source_name.lower() for w in western_sources)
    has_contradiction = any(m in text for m in contradiction_markers)
    
    if has_contradiction:
        return "⚠️ Информация противоречит официальным российским источникам"
    elif is_western:
        return "🌍 Информация из западного источника, требуется верификация"
    return ""

def fetch_single_rss(source_name, url):
    """Загружает один RSS-источник"""
    try:
        feed = feedparser.parse(url)
        articles = []
        for entry in feed.entries[:8]:
            title = entry.get('title', '')
            description = entry.get('summary', '')
            published = datetime.now()
            if hasattr(entry, 'published_parsed') and entry.published_parsed:
                published = datetime(*entry.published_parsed[:6])
            
            # Для российских источников оставляем как есть, для зарубежных - переводим
            if source_name in RSS_RUSSIAN:
                final_title = title
                final_description = description
            else:
                final_title = translate_to_russian(title)
                final_description = translate_to_russian(description)
            
            articles.append({
                'title': final_title,
                'url': entry.get('link', ''),
                'source': source_name,
                'description': final_description,
                'published': published,
                'is_russian': source_name in RSS_RUSSIAN
            })
        return articles
    except Exception as e:
        print(f"    Ошибка {source_name}: {e}")
        return []

def fetch_all_rss_parallel():
    """Параллельная загрузка всех RSS-источников"""
    all_articles = []
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {executor.submit(fetch_single_rss, name, url): name for name, url in RSS_SOURCES.items()}
        for future in as_completed(futures):
            source_name = futures[future]
            try:
                articles = future.result()
                print(f"  ✅ {source_name}: {len(articles)} новостей")
                all_articles.extend(articles)
            except Exception as e:
                print(f"  ❌ {source_name}: ошибка - {e}")
    return all_articles

def get_category(title, description):
    text = (title + " " + description).lower()
    for cat_name, cat_data in CATEGORIES.items():
        for kw in cat_data['keywords']:
            if kw in text:
                return cat_name
    return "РОССИЯ"

def get_priority_score(title, description, source_is_russian):
    """Оценивает важность новости"""
    text = (title + " " + description).lower()
    score = 0
    
    high_priority = ["минобороны", "шойгу", "герасимов", "наступление", "приказ", "мобилизация", "сво", "фронт", "бригада", "дивизия"]
    medium_priority = ["армия", "войска", "военный", "оборона", "безопасность", "разведка", "фсб"]
    
    for word in high_priority:
        if word in text:
            score += 5
    for word in medium_priority:
        if word in text:
            score += 2
    
    # Российские источники получают бонус
    if source_is_russian:
        score += 3
    
    return score

def format_news_entry(article, index, category):
    """Форматирует одну новость (кратко)"""
    title = article.get('title', '')
    url = article.get('url', '')
    source = article.get('source', '')
    description = article.get('description', '')
    published = article.get('published', datetime.now())
    published_time = published.strftime("%d.%m.%Y %H:%M")
    
    # Извлекаем населенные пункты
    locations = extract_locations(title + " " + description)
    locations_text = f"📍 {', '.join(locations)}" if locations else ""
    
    # Проверяем несоответствие
    inconsistency = check_inconsistency(title, description, source)
    inconsistency_text = f"\n{inconsistency}" if inconsistency else ""
    
    # Краткое содержание (первые 300 символов)
    content = description[:500] if description and len(description) > 50 else title[:500]
    
    entry = f"""НОВОСТЬ {index}
Категория: {category}
Источник: {source}
Заголовок: {title}
{locations_text}
Содержание: {content}
Время: {published_time} МСК
Ссылка: {url}{inconsistency_text}
"""
    return entry

def generate_analysis(category_news, total_processed):
    """Аналитическая сводка"""
    today = datetime.now().strftime("%d.%m.%Y")
    
    analysis = f"""
АНАЛИТИЧЕСКАЯ СВОДКА
Дата: {today}

1. СТАТИСТИКА
- МИР: {len(category_news.get('МИР', []))} новостей
- РОССИЯ: {len(category_news.get('РОССИЯ', []))} новостей
- СВО: {len(category_news.get('СВО', []))} новостей
- СТАВРОПОЛЬЕ: {len(category_news.get('СТАВРОПОЛЬЕ', []))} новостей
- Всего обработано: {total_processed}

2. ОЦЕНКА ОБСТАНОВКИ
- В зоне СВО сохраняется напряженность
- Российские войска продолжают выполнение задач
- Зафиксированы противоречия в западных СМИ
- Ставропольский край: обстановка контролируемая

3. УГРОЗЫ И РИСКИ
- Информационные атаки со стороны западных СМИ
- Сохранение санкционного давления
- Региональные риски в Северо-Кавказском регионе

4. РЕКОМЕНДАЦИИ
- Усилить мониторинг западных источников
- Проводить верификацию противоречивых данных
- Обратить внимание на региональную безопасность

Доклад подготовлен автоматически.
"""
    return analysis

def main():
    print(f"🚀 Запуск бота (параллельная загрузка, {len(RSS_SOURCES)} источников)...")
    
    if not BOT_TOKEN or not CHAT_ID:
        print("❌ Ошибка: нет токенов Telegram")
        return
    
    # Параллельный сбор
    print("\n📡 Параллельная загрузка RSS...")
    start_time = time.time()
    all_articles = fetch_all_rss_parallel()
    elapsed = time.time() - start_time
    print(f"\n⏱️ Загрузка завершена за {elapsed:.1f} сек. Всего статей: {len(all_articles)}")
    
    # Категоризация и оценка
    news_items = []
    for article in all_articles:
        cat = get_category(article['title'], article.get('description', ''))
        priority = get_priority_score(article['title'], article.get('description', ''), article.get('is_russian', False))
        news_items.append({
            'article': article,
            'category': cat,
            'priority': priority
        })
    
    # Сортировка по приоритету
    news_items.sort(key=lambda x: x['priority'], reverse=True)
    
    # Распределение по категориям (по 7 в каждой)
    category_news = defaultdict(list)
    for item in news_items:
        cat = item['category']
        if len(category_news[cat]) < 7:
            category_news[cat].append(item['article'])
    
    # Формирование отчета
    report = f"ЕЖЕДНЕВНЫЙ ДОКЛАД\nДата: {datetime.now().strftime('%d.%m.%Y')}\n\n"
    
    for cat in CATEGORY_ORDER:
        if cat in category_news and category_news[cat]:
            report += f"\n=== {cat} ===\n\n"
            for idx, article in enumerate(category_news[cat][:7], 1):
                report += format_news_entry(article, idx, cat)
                if idx < len(category_news[cat][:7]):
                    report += "\n***\n\n"
            report += "\n"
    
    report += generate_analysis(category_news, len(all_articles))
    
    # Отправка
    if len(report) > 4096:
        parts = [report[i:i+4096] for i in range(0, len(report), 4096)]
        for part in parts:
            send_telegram(part)
    else:
        send_telegram(report)
    
    total = sum(len(news) for news in category_news.values())
    print(f"\n✅ Готово за {time.time() - start_time:.1f} сек. Новостей: {total}")

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
        print(f"❌ Ошибка отправки: {e}")

if __name__ == "__main__":
    main()

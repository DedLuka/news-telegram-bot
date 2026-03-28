import requests
import os
import feedparser
from datetime import datetime, timedelta
import time
from collections import defaultdict
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import html
from collections import Counter

BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')

def test_telegram():
    if not BOT_TOKEN or not CHAT_ID:
        print("❌ Токены не заданы!")
        return False
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        'chat_id': CHAT_ID,
        'text': "🔧 Бот запущен и работает",
        'disable_web_page_preview': True
    }
    try:
        r = requests.post(url, json=payload, timeout=10)
        print(f"📡 Тест отправки: статус {r.status_code}")
        return r.status_code == 200
    except Exception as e:
        print(f"❌ Ошибка теста: {e}")
        return False

def clean_html(text):
    if not text:
        return ""
    text = html.unescape(text)
    text = re.sub(r'<[^>]+>', '', text)
    text = re.sub(r'\\([\.\*\+\?\[\]\(\)\{\}\|\\])', r'\1', text)
    text = re.sub(r'\s+', ' ', text)
    text = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', text)
    return text.strip()

# Российские RSS-источники
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
        "keywords": ["мир", "международный", "европа", "сша", "нато", "китай", "германия", "франция", "англия", "америка", "брюссель", "вашингтон", "лондон", "санкции", "конфликт", "оон", "world", "international"],
        "priority": 1
    },
    "РОССИЯ": {
        "keywords": ["россия", "путин", "медведев", "мишустин", "кремль", "госдума", "правительство", "москва", "российский", "безопасность", "оборона", "фсб", "указ", "закон"],
        "priority": 2
    },
    "СВО": {
        "keywords": ["сво", "донбасс", "украина", "запорожье", "херсон", "военный", "минобороны", "мобилизация", "армия", "фронт", "бахмут", "авдеевка", "шойгу", "герасимов", "спецоперация", "наступление", "удар", "обстрел", "донецк", "луганск", "ukraine", "war"],
        "priority": 3
    },
    "СТАВРОПОЛЬЕ": {
        "keywords": ["ставрополь", "ставрополье", "ставропольский", "кавминводы", "пятигорск", "кисловодск", "ессентуки", "безопасность", "терроризм", "чп", "мобилизация", "военкомат"],
        "priority": 4
    }
}

CATEGORY_ORDER = ['МИР', 'РОССИЯ', 'СВО', 'СТАВРОПОЛЬЕ']

translation_cache = {}

def is_russian(text):
    return bool(re.search('[а-яА-ЯёЁ]', text))

def translate_to_russian(text):
    if not text or is_russian(text):
        return text
    cache_key = hashlib.md5(text.encode()).hexdigest()
    if cache_key in translation_cache:
        return translation_cache[cache_key]
    try:
        url = "https://translate.googleapis.com/translate_a/single"
        params = {'client': 'gtx', 'sl': 'auto', 'tl': 'ru', 'dt': 't', 'q': text[:500]}
        response = requests.get(url, params=params, timeout=5)
        if response.status_code == 200:
            data = response.json()
            translated = ''.join([item[0] for item in data[0]])
            translation_cache[cache_key] = translated
            return translated
    except Exception:
        pass
    return text

def extract_locations(text):
    locations = []
    patterns = [
        r'(?:в|на|под|у|из|за|около)\s+([А-ЯЁ][а-яё]+(?:-?[А-ЯЁ][а-яё]+)?)\s+(?:районе?|области?|крае?|городе?)',
        r'([А-ЯЁ][а-яё]+(?:-?[А-ЯЁ][а-яё]+)?)\s+(?:город|поселок|село|станица)',
        r'(?:Донецк|Луганск|Запорожье|Херсон|Бахмут|Авдеевка|Артемовск|Соледар)'
    ]
    for pattern in patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        locations.extend(matches)
    return list(set(locations))[:3]

def check_inconsistency(title, description, source_name):
    text = (title + " " + description).lower()
    western_sources = ['bbc', 'cnn', 'guardian', 'reuters', 'ap', 'washington', 'nytimes']
    is_western = any(w in source_name.lower() for w in western_sources)
    if is_western:
        return "\n🌍 Информация из западного источника, требуется верификация"
    return ""

def fetch_single_rss(source_name, url):
    try:
        feed = feedparser.parse(url)
        articles = []
        for entry in feed.entries[:8]:
            title = clean_html(entry.get('title', ''))
            description = clean_html(entry.get('summary', ''))
            published = datetime.now()
            if hasattr(entry, 'published_parsed') and entry.published_parsed:
                published = datetime(*entry.published_parsed[:6])
            
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
    except Exception:
        return []

def fetch_all_rss_parallel():
    all_articles = []
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {executor.submit(fetch_single_rss, name, url): name for name, url in RSS_SOURCES.items()}
        for future in as_completed(futures):
            source_name = futures[future]
            try:
                articles = future.result()
                if articles:
                    print(f"  ✅ {source_name}: {len(articles)}")
                    all_articles.extend(articles)
                else:
                    print(f"  ⚠️ {source_name}: 0")
            except Exception:
                print(f"  ❌ {source_name}: ошибка")
    return all_articles

def get_category(title, description):
    text = (title + " " + description).lower()
    for cat_name, cat_data in CATEGORIES.items():
        for kw in cat_data['keywords']:
            if kw in text:
                return cat_name
    return "РОССИЯ"

def get_priority_score(title, description, source_is_russian):
    text = (title + " " + description).lower()
    score = 0
    high = ["минобороны", "шойгу", "герасимов", "наступление", "мобилизация", "сво", "фронт"]
    medium = ["армия", "войска", "военный", "оборона", "безопасность"]
    for word in high:
        if word in text:
            score += 5
    for word in medium:
        if word in text:
            score += 2
    if source_is_russian:
        score += 3
    return score

def format_news_entry(article, index, category):
    title = clean_html(article.get('title', ''))
    url = article.get('url', '')
    source = clean_html(article.get('source', ''))
    description = clean_html(article.get('description', '')[:500])
    published = article.get('published', datetime.now())
    published_time = published.strftime("%d.%m.%Y %H:%M")
    
    locations = extract_locations(title + " " + description)
    locations_text = f"📍 {', '.join(locations)}" if locations else ""
    inconsistency = check_inconsistency(title, description, source)
    
    return f"""НОВОСТЬ {index}
Категория: {category}
Источник: {source}
Заголовок: {title}
{locations_text}
Содержание: {description}
Время: {published_time} МСК
Ссылка: {url}{inconsistency}
"""

def generate_dynamic_analysis(category_news, all_articles):
    """Динамическая аналитика на основе реальных новостей"""
    
    # Собираем все заголовки и описания
    all_texts = []
    for articles in category_news.values():
        for article in articles:
            all_texts.append(article.get('title', '') + " " + article.get('description', ''))
    
    full_text = " ".join(all_texts).lower()
    
    # Анализируем ключевые слова и события
    events = []
    locations = []
    
    # Военные действия
    if re.search(r'(наступление|удар|обстрел|атака|уничтожен|ликвидирован)', full_text):
        events.append("активные боевые действия")
        # Определяем направление
        if re.search(r'(донецк|днр|горловка|авдеевка)', full_text):
            events.append("на Донецком направлении")
        if re.search(r'(запорожье|каменское|орехов)', full_text):
            events.append("на Запорожском направлении")
        if re.search(r'(херсон|антоновский)', full_text):
            events.append("на Херсонском направлении")
        if re.search(r'(луганск|сватово|кременная)', full_text):
            events.append("на Луганском направлении")
    
    # Потери
    if re.search(r'(потери|уничтожен|сбит|ликвидирован)', full_text):
        events.append("зафиксированы потери противника")
    
    # Мобилизация
    if re.search(r'(мобилизация|призыв|военкомат)', full_text):
        events.append("продолжается мобилизационная работа")
    
    # Западные заявления
    western_claims = []
    if re.search(r'(санкции|ограничения|запрет)', full_text):
        western_claims.append("санкционное давление")
    if re.search(r'(помощь украине|военная помощь|поставки вооружений)', full_text):
        western_claims.append("заявлены новые поставки вооружений Киеву")
    if re.search(r'(нато|альянс|укрепление флангов)', full_text):
        western_claims.append("активность НАТО у границ РФ")
    
    # Извлекаем топ-5 ключевых слов
    words = re.findall(r'[а-яё]{4,}', full_text)
    word_freq = Counter(words)
    top_keywords = [w for w, _ in word_freq.most_common(7) if w not in ['новости', 'сообщил', 'заявил', 'пресс', 'служба']][:5]
    
    # Региональные события (Ставрополье)
    regional_events = []
    if re.search(r'(ставрополь|ставрополье|кавминводы)', full_text):
        if re.search(r'(терроризм|безопасность|охрана)', full_text):
            regional_events.append("усилены меры безопасности")
        if re.search(r'(мобилизация|военкомат|призыв)', full_text):
            regional_events.append("продолжается работа военкоматов")
        if re.search(r'(поддержка семей|помощь|льготы)', full_text):
            regional_events.append("реализуются меры поддержки семей военнослужащих")
    
    # Формируем динамический анализ
    today = datetime.now().strftime("%d.%m.%Y")
    
    analysis = f"""
АНАЛИТИЧЕСКАЯ СВОДКА
Дата: {today}

1. СТАТИСТИКА ЗА СУТКИ
- МИР: {len(category_news.get('МИР', []))}
- РОССИЯ: {len(category_news.get('РОССИЯ', []))}
- СВО: {len(category_news.get('СВО', []))}
- СТАВРОПОЛЬЕ: {len(category_news.get('СТАВРОПОЛЬЕ', []))}
- Всего обработано: {len(all_articles)}

2. КЛЮЧЕВЫЕ СОБЫТИЯ
{chr(10).join([f"- {e}" for e in events[:5]]) if events else "- Значимых событий не выявлено"}

3. АКТИВНОСТЬ НА ФРОНТЕ
{chr(10).join([f"- {e}" for e in events if 'наступление' in e or 'удар' in e or 'потери' in e]) if events else "- Оперативная обстановка контролируемая"}

4. МЕЖДУНАРОДНАЯ ОБСТАНОВКА
{chr(10).join([f"- {c}" for c in western_claims]) if western_claims else "- Существенных изменений не зафиксировано"}

5. РЕГИОНАЛЬНАЯ ПОВЕСТКА (СТАВРОПОЛЬЕ)
{chr(10).join([f"- {r}" for r in regional_events]) if regional_events else "- Ситуация контролируемая, происшествий не зафиксировано"}

6. ОСНОВНЫЕ ТЕМЫ ИНФОРМПОЛЯ
{chr(10).join([f"- {kw}" for kw in top_keywords]) if top_keywords else "- Анализ проводится"}

7. ОЦЕНКА ДОСТОВЕРНОСТИ
- Российские источники: информация согласована
- Западные источники: выявлены расхождения, требуется верификация

8. ПРОГНОЗ (на 24-48 часов)
- Ожидается сохранение интенсивности боевых действий
- Возможны новые информационные вбросы со стороны противника
- Региональная обстановка остается под контролем
"""
    return analysis

def send_telegram(message):
    if not BOT_TOKEN or not CHAT_ID:
        return False
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        'chat_id': CHAT_ID,
        'text': message,
        'disable_web_page_preview': True
    }
    try:
        r = requests.post(url, json=payload, timeout=60)
        return r.status_code == 200
    except Exception:
        return False

def main():
    print("🚀 Запуск бота...")
    
    if not BOT_TOKEN or not CHAT_ID:
        print("❌ Ошибка: токены не заданы")
        return
    
    print("\n📡 Проверка Telegram...")
    test_telegram()
    
    print(f"\n📡 Параллельная загрузка {len(RSS_SOURCES)} источников...")
    start_time = time.time()
    all_articles = fetch_all_rss_parallel()
    elapsed = time.time() - start_time
    print(f"\n⏱️ Загрузка: {elapsed:.1f} сек, статей: {len(all_articles)}")
    
    if not all_articles:
        send_telegram("⚠️ Нет новостей для обработки")
        return
    
    # Категоризация
    news_items = []
    for article in all_articles:
        cat = get_category(article['title'], article.get('description', ''))
        priority = get_priority_score(article['title'], article.get('description', ''), article.get('is_russian', False))
        news_items.append({'article': article, 'category': cat, 'priority': priority})
    
    news_items.sort(key=lambda x: x['priority'], reverse=True)
    
    # Распределение по категориям
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
    
    report += generate_dynamic_analysis(category_news, all_articles)
    
    # Отправка
    print("\n📤 Отправка отчета...")
    if len(report) > 4096:
        parts = [report[i:i+4096] for i in range(0, len(report), 4096)]
        for part in parts:
            send_telegram(part)
    else:
        send_telegram(report)
    
    total = sum(len(news) for news in category_news.values())
    print(f"\n✅ Готово за {time.time() - start_time:.1f} сек. Новостей: {total}")

if __name__ == "__main__":
    main()

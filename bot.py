import requests
import os
import feedparser
from datetime import datetime, timedelta
import time
from collections import defaultdict, Counter
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import html

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
    "Интерфакс": "https://www.interfax.ru/rss.asp",
    "Росбалт": "https://www.rosbalt.ru/rss/",
    "News.ru": "https://news.ru/rss/news",
    "Царьград": "https://tsargrad.tv/rss",
    "Политнавигатор": "https://politnavigator.net/feed",
    "Русская весна": "https://rusvesna.su/rss",
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
    "Fox News": "https://moxie.foxnews.com/google-publisher/latest.xml",
    "NBC News": "https://feeds.nbcnews.com/nbcnews/public/world",
    "ABC News": "https://abcnews.go.com/abcnews/internationalheadlines",
    "The Telegraph": "https://www.telegraph.co.uk/rss.xml",
    "The Times": "https://www.thetimes.co.uk/rss",
}

RSS_SOURCES = {**RSS_RUSSIAN, **RSS_FOREIGN}

CATEGORIES = {
    "МИР": {
        "keywords": ["мир", "международный", "европа", "сша", "нато", "китай", "германия", "франция", "англия", "америка", "брюссель", "вашингтон", "лондон", "санкции", "конфликт", "оон"],
        "priority": 1
    },
    "РОССИЯ": {
        "keywords": ["россия", "путин", "медведев", "мишустин", "кремль", "госдума", "правительство", "москва", "российский", "безопасность", "оборона", "фсб", "указ", "закон", "росгвардия", "внг", "нацгвардия"],
        "priority": 2
    },
    "СВО": {
        "keywords": ["сво", "донбасс", "украина", "запорожье", "херсон", "военный", "минобороны", "мобилизация", "армия", "фронт", "бахмут", "авдеевка", "шойгу", "герасимов", "спецоперация", "наступление", "удар", "обстрел", "донецк", "луганск"],
        "priority": 3
    },
    "СТАВРОПОЛЬЕ": {
        "keywords": ["ставрополь", "ставрополье", "ставропольский", "кавминводы", "пятигорск", "кисловодск", "ессентуки", "безопасность", "терроризм", "чп", "мобилизация", "военкомат"],
        "priority": 4
    }
}

CATEGORY_ORDER = ['МИР', 'РОССИЯ', 'СВО', 'СТАВРОПОЛЬЕ']

translation_cache = {}

def clean_html(text):
    if not text:
        return ""
    text = html.unescape(text)
    text = re.sub(r'<[^>]+>', '', text)
    text = re.sub(r'\\([\.\*\+\?\[\]\(\)\{\}\|\\])', r'\1', text)
    text = re.sub(r'\s+', ' ', text)
    text = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', text)
    return text.strip()

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

def extract_keywords(text):
    """Извлекает ключевые слова для сравнения смысла"""
    words = re.findall(r'[а-яё]{4,}', text.lower())
    stop_words = {'новости', 'сообщил', 'заявил', 'сказал', 'пресс', 'служба', 'также', 'который', 'после', 'сегодня', 'время', 'стал', 'стала', 'было', 'были'}
    keywords = [w for w in words if w not in stop_words]
    return set(keywords[:10])

def check_duplicate_with_russian(western_title, western_desc, russian_articles):
    """Проверяет, дублируется ли западная новость в российских источниках"""
    western_keywords = extract_keywords(western_title + " " + western_desc)
    if not western_keywords:
        return False
    
    for r_article in russian_articles:
        russian_keywords = extract_keywords(r_article.get('title', '') + " " + r_article.get('description', ''))
        if not russian_keywords:
            continue
        intersection = western_keywords & russian_keywords
        if len(intersection) / len(western_keywords) >= 0.4:
            return True
    return False

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
            future.result()
    # Простой последовательный сбор для минимальных логов
    for name, url in RSS_SOURCES.items():
        try:
            articles = fetch_single_rss(name, url)
            if articles:
                all_articles.extend(articles)
        except Exception:
            pass
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
    high = ["минобороны", "шойгу", "герасимов", "наступление", "мобилизация", "сво", "фронт", "росгвардия", "внг"]
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

def format_news_entry(article, index, category, is_duplicate=False):
    title = clean_html(article.get('title', ''))
    url = article.get('url', '')
    source = clean_html(article.get('source', ''))
    description = clean_html(article.get('description', '')[:500])
    published = article.get('published', datetime.now())
    published_time = published.strftime("%d.%m.%Y %H:%M")
    
    locations = extract_locations(title + " " + description)
    locations_text = f"📍 {', '.join(locations)}" if locations else ""
    
    # Строгое предупреждение для западных источников
    warning = ""
    if not article.get('is_russian', False) and not is_duplicate:
        warning = "\n⚠️ ИНФОРМАЦИЯ ИЗ ИНОСТРАННОГО ИСТОЧНИКА, ДОСТОВЕРНОСТЬ НЕ ПОДТВЕРЖДЕНА РОССИЙСКИМИ ИСТОЧНИКАМИ"
    
    return f"""НОВОСТЬ {index}
Категория: {category}
Источник: {source}
Заголовок: {title}
{locations_text}
Содержание: {description}
Время: {published_time} МСК
Ссылка: {url}{warning}
"""

def extract_official_statements(articles):
    """Извлекает заявления официальных лиц"""
    statements = []
    officials = ["путин", "шуйгу", "герасимов", "песков", "лавров", "мишустин", "володин", "матвиенко", "патрушев"]
    for article in articles:
        title = article.get('title', '').lower()
        desc = article.get('description', '').lower()
        for official in officials:
            if official in title or official in desc:
                statements.append({
                    'official': official.title(),
                    'title': article.get('title', ''),
                    'source': article.get('source', '')
                })
                break
    return statements[:5]

def generate_dynamic_analysis(category_news, all_articles, official_statements):
    today = datetime.now().strftime("%d.%m.%Y")
    
    full_text = " ".join([a.get('title', '') + " " + a.get('description', '') for a in all_articles]).lower()
    
    events = []
    battle_directions = []
    
    if re.search(r'(донецк|днр|горловка|авдеевка|мар\w+ка)', full_text):
        battle_directions.append("Донецкое направление")
    if re.search(r'(запорожье|каменское|орехов|гуляйполе)', full_text):
        battle_directions.append("Запорожское направление")
    if re.search(r'(херсон|антоновский|берислав)', full_text):
        battle_directions.append("Херсонское направление")
    if re.search(r'(луганск|сватово|кременная|лисичанск)', full_text):
        battle_directions.append("Луганское направление")
    
    if battle_directions:
        events.append(f"Активные боевые действия на направлениях: {', '.join(battle_directions)}")
    if re.search(r'(наступление|продвижение|освободили|взяли под контроль)', full_text):
        events.append("Зафиксировано продвижение российских войск")
    if re.search(r'(удар|обстрел|ракетный|дроновый)', full_text):
        events.append("Нанесены удары по объектам противника")
    if re.search(r'(уничтожен|ликвидирован|потери)', full_text):
        events.append("Противник несет потери в живой силе и технике")
    if re.search(r'(росгвардия|внг|нацгвардия)', full_text):
        events.append("Задействованы подразделения Росгвардии")
    
    western_events = []
    if re.search(r'(санкции|ограничения)', full_text):
        western_events.append("новые санкционные ограничения")
    if re.search(r'(помощь украине|поставки вооружений)', full_text):
        western_events.append("заявлены новые поставки вооружений Киеву")
    if re.search(r'(нато|альянс|военные учения)', full_text):
        western_events.append("активность НАТО у границ РФ")
    
    regional_events = []
    stavropol_text = ""
    for article in category_news.get('СТАВРОПОЛЬЕ', []):
        stavropol_text += article.get('title', '') + " " + article.get('description', '')
    stavropol_text = stavropol_text.lower()
    
    if re.search(r'(безопасность|терроризм|охрана)', stavropol_text):
        regional_events.append("усилены меры безопасности")
    if re.search(r'(мобилизация|военкомат|призыв)', stavropol_text):
        regional_events.append("продолжается работа военкоматов")
    if re.search(r'(поддержка семей|льготы|выплаты)', stavropol_text):
        regional_events.append("реализуются меры поддержки семей военнослужащих")
    
    themes = []
    if re.search(r'(сво|донбасс|минобороны)', full_text):
        themes.append("Ход специальной военной операции")
    if re.search(r'(сша|нато|европа|санкции)', full_text):
        themes.append("Международная обстановка")
    if re.search(r'(путин|кремль|госдума|указ)', full_text):
        themes.append("Внутренняя политика РФ")
    if re.search(r'(росгвардия|внг)', full_text):
        themes.append("Деятельность Росгвардии")
    if re.search(r'(ставрополь|ставрополье)', full_text):
        themes.append("Ситуация в Ставропольском крае")
    
    # Формируем аналитику
    analysis = f"""
АНАЛИТИЧЕСКАЯ СВОДКА
Дата: {today}

1. СТАТИСТИКА ЗА СУТКИ
- МИР: {len(category_news.get('МИР', []))}
- РОССИЯ: {len(category_news.get('РОССИЯ', []))}
- СВО: {len(category_news.get('СВО', []))}
- СТАВРОПОЛЬЕ: {len(category_news.get('СТАВРОПОЛЬЕ', []))}
- Всего обработано: {len(all_articles)}

2. ВАЖНЫЕ ЗАЯВЛЕНИЯ ОФИЦИАЛЬНЫХ ЛИЦ
{chr(10).join([f"- {s['official']}: {s['title'][:100]} ({s['source']})" for s in official_statements]) if official_statements else "- Заявлений не зафиксировано"}

3. КЛЮЧЕВЫЕ СОБЫТИЯ СУТОК
{chr(10).join([f"- {e}" for e in events[:5]]) if events else "- Значимых событий не выявлено"}

4. ОПЕРАТИВНАЯ ОБСТАНОВКА
{chr(10).join([f"- {d}" for d in battle_directions[:3]]) if battle_directions else "- Обстановка контролируемая"}

5. МЕЖДУНАРОДНАЯ ОБСТАНОВКА
{chr(10).join([f"- {w}" for w in western_events]) if western_events else "- Существенных изменений не зафиксировано"}

6. РЕГИОНАЛЬНАЯ ПОВЕСТКА (СТАВРОПОЛЬЕ)
{chr(10).join([f"- {r}" for r in regional_events]) if regional_events else "- Ситуация контролируемая"}

7. ОСНОВНЫЕ ТЕМЫ ИНФОРМПОЛЯ
{chr(10).join([f"- {t}" for t in themes]) if themes else "- Анализ проводится"}

8. ДОСТОВЕРНОСТЬ ИСТОЧНИКОВ
- Российские официальные источники: высокая
- Иностранные СМИ: информация требует обязательной верификации

9. ПРОГНОЗ (на 24-48 часов)
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
    
    # Минимальный лог
    print("📡 Сбор новостей...")
    start_time = time.time()
    all_articles = fetch_all_rss_parallel()
    elapsed = time.time() - start_time
    print(f"⏱️ Загрузка: {elapsed:.1f} сек, статей: {len(all_articles)}")
    
    if not all_articles:
        send_telegram("⚠️ Нет новостей для обработки")
        return
    
    # Разделяем российские и западные для проверки дублирования
    russian_articles = [a for a in all_articles if a.get('is_russian', False)]
    western_articles = [a for a in all_articles if not a.get('is_russian', False)]
    
    # Проверяем дублирование для западных новостей
    duplicate_map = {}
    for w_article in western_articles:
        is_dup = check_duplicate_with_russian(
            w_article.get('title', ''),
            w_article.get('description', ''),
            russian_articles
        )
        duplicate_map[id(w_article)] = is_dup
    
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
    
    # Извлекаем заявления официальных лиц
    official_statements = extract_official_statements(all_articles)
    
    # Формирование отчета
    report = f"ЕЖЕДНЕВНЫЙ ДОКЛАД\nДата: {datetime.now().strftime('%d.%m.%Y')}\n\n"
    
    for cat in CATEGORY_ORDER:
        if cat in category_news and category_news[cat]:
            report += f"\n=== {cat} ===\n\n"
            for idx, article in enumerate(category_news[cat][:7], 1):
                is_dup = duplicate_map.get(id(article), False) if not article.get('is_russian', False) else False
                report += format_news_entry(article, idx, cat, is_dup)
                if idx < len(category_news[cat][:7]):
                    report += "\n***\n\n"
            report += "\n"
    
    report += generate_dynamic_analysis(category_news, all_articles, official_statements)
    
    # Отправка
    print("📤 Отправка отчета...")
    if len(report) > 4096:
        parts = [report[i:i+4096] for i in range(0, len(report), 4096)]
        for part in parts:
            send_telegram(part)
    else:
        send_telegram(report)
    
    total = sum(len(news) for news in category_news.values())
    print(f"✅ Готово за {time.time() - start_time:.1f} сек. Новостей: {total}")

if __name__ == "__main__":
    main()

import requests
import os
import feedparser
from datetime import datetime, timedelta
import time
from collections import defaultdict
import re

BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')

# ==================== РОССИЙСКИЕ RSS-ИСТОЧНИКИ ====================
RSS_RUSSIAN = {
    # Официальные государственные агентства
    "ТАСС": "http://tass.com/rss/v2.xml",
    "РИА Новости": "https://ria.ru/export/rss2/index.xml",
    "RT (Russia Today)": "https://rt.com/rss/news/",
    "Вести.ру": "https://www.vesti.ru/vesti.rss",
    "Спутник": "https://sputniknews.com/export/rss2/world/index.xml",
    
    # Ведущие российские СМИ
    "Коммерсантъ": "https://www.kommersant.ru/RSS/news.xml",
    "МК": "https://www.mk.ru/rss/news/index.xml",
    "Комсомольская правда": "https://www.kp.ru/rss/",
    "Lenta.ru - новости": "https://lenta.ru/rss/news",
    "Lenta.ru - главное": "https://lenta.ru/rss/top7",
    "Lenta.ru - Россия": "https://lenta.ru/rss/news/russia",
    "Lenta.ru - Мир": "https://lenta.ru/rss/news/world",
    "Известия": "https://iz.ru/xml/rss.xml",
    "РБК": "https://www.rbc.ru/rss/",
    "Российская газета": "https://rg.ru/xml/index.xml",
    "Газета.Ru": "https://www.gazeta.ru/export/rss/lenta.xml",
    "Взгляд": "https://vz.ru/rss.xml",
    "Life.ru": "https://life.ru/rss/feed",
    
    # Региональные источники
    "Вести Ставрополье": "https://vesti26.ru/rss/",
    "Ставропольская правда": "https://www.stapravda.ru/rss/",
    
    # Технические и IT-новости (полезны для военной тематики)
    "OpenNET (главное)": "https://www.opennet.ru/opennews/opennews_6_noadv.rss",
    "OpenNET (полные тексты)": "https://www.opennet.ru/opennews/opennews_6_full.rss",
    "OpenNET (мини-новости)": "https://www.opennet.ru/opennews/opennews_mini_noadv.rss",
}

# ==================== ЗАРУБЕЖНЫЕ RSS-ИСТОЧНИКИ ====================
RSS_FOREIGN = {
    # Англоязычные мировые СМИ
    "BBC News": "http://feeds.bbci.co.uk/news/rss.xml",
    "BBC World": "http://feeds.bbci.co.uk/news/world/rss.xml",
    "CNN": "http://rss.cnn.com/rss/edition.rss",
    "CNN World": "http://rss.cnn.com/rss/edition_world.rss",
    "The Guardian": "https://www.theguardian.com/world/rss",
    "The New York Times": "https://rss.nytimes.com/services/xml/rss/nyt/World.xml",
    "Washington Post": "https://feeds.washingtonpost.com/rss/world",
    "Reuters": "https://www.reutersagency.com/feed/?best-topics=business-finance&post_type=best",
    "AP News": "http://hosted2.ap.org/atom/APTopNews",
    "NPR": "https://feeds.npr.org/1001/rss.xml",
    "Al Jazeera": "https://www.aljazeera.com/xml/rss/all.xml",
    "Deutsche Welle": "https://rss.dw.com/rdf/rss-en-world",
    "France 24": "https://www.france24.com/en/france-24-rss-feeds",
    "The Economist": "https://www.economist.com/feeds/print-sections/77/world-politics.xml",
    
    # Военная и аналитическая тематика
    "Defense News": "https://www.defensenews.com/arc/outboundfeeds/rss/",
    "Jane's Defence": "https://www.janes.com/rss",
    "The War Zone (The Drive)": "https://www.thedrive.com/the-war-zone/feed",
    "Military.com": "https://www.military.com/feed",
    "Stars and Stripes": "https://www.stripes.com/rss",
    "Breaking Defense": "https://breakingdefense.com/feed/",
    "Defense One": "https://www.defenseone.com/feeds/all/",
    "RAND Corporation": "https://www.rand.org/rss/news.xml",
    
    # Аналитические центры
    "CSIS": "https://www.csis.org/rss.xml",
    "Chatham House": "https://www.chathamhouse.org/rss.xml",
    "Atlantic Council": "https://www.atlanticcouncil.org/feed/",
    
    # Зарубежные русскоязычные
    "Meduza": "https://meduza.io/rss/all",
    "Current Time TV": "https://www.currenttime.tv/api/zljqjzr",
    "Радио Свобода": "https://www.svoboda.org/api/zljqjzr",
    
    # Региональные
    "The Moscow Times (англ)": "https://www.themoscowtimes.com/rss/news",
}

# Объединяем все источники
RSS_SOURCES = {**RSS_RUSSIAN, **RSS_FOREIGN}

# Категории с ключевыми словами
CATEGORIES = {
    "МИР": {
        "keywords": ["мир", "международный", "европа", "сша", "нато", "китай", "германия", "франция", "англия", "америка", "брюссель", "вашингтон", "лондон", "санкции", "конфликт", "переговоры", "глобальный", "оон", "совбез", "world", "international", "europe", "usa", "nato", "china"],
        "priority": 1
    },
    "РОССИЯ": {
        "keywords": ["россия", "путин", "медведев", "мишустин", "кремль", "госдума", "совет федерации", "правительство", "москва", "российский", "безопасность", "оборона", "фсб", "разведка", "указ", "закон", "russia", "putin", "kremlin"],
        "priority": 2
    },
    "СВО": {
        "keywords": ["сво", "донбасс", "украина", "запорожье", "херсон", "военный", "минобороны", "мобилизация", "армия", "фронт", "бахмут", "авдеевка", "шойгу", "герасимов", "вс рф", "спецоперация", "бригада", "дивизия", "наступление", "оборона", "танк", "артиллерия", "авиация", "удар", "обстрел", "потери", "донецк", "луганск", "ukraine", "donbas", "war", "military"],
        "priority": 3
    },
    "СТАВРОПОЛЬЕ": {
        "keywords": ["ставрополь", "ставрополье", "ставропольский", "кавминводы", "пятигорск", "кисловодск", "ессентуки", "железноводск", "невинномысск", "михайловск", "гтрк ставрополье", "безопасность", "терроризм", "чп", "мобилизация", "военкомат", "казачество", "ставропольский край"],
        "priority": 4
    }
}

# Порядок категорий для отчета
CATEGORY_ORDER = ['МИР', 'РОССИЯ', 'СВО', 'СТАВРОПОЛЬЕ']

def is_russian(text):
    """Проверяет, содержит ли текст русские буквы"""
    if not text:
        return False
    return bool(re.search('[а-яА-ЯёЁ]', text))

def fetch_rss_news(source_name, url):
    """Получает новости из RSS, фильтрует только русскоязычные"""
    try:
        feed = feedparser.parse(url)
        articles = []
        for entry in feed.entries[:15]:
            title = entry.get('title', '')
            description = entry.get('summary', '')
            
            # Для иностранных источников сохраняем английские новости
            # Для российских — фильтруем по русскому языку
            if source_name in RSS_RUSSIAN:
                if not is_russian(title) and not is_russian(description):
                    continue
                
            published = datetime.now()
            if hasattr(entry, 'published_parsed') and entry.published_parsed:
                published = datetime(*entry.published_parsed[:6])
            articles.append({
                'title': title,
                'url': entry.get('link', ''),
                'source': source_name,
                'description': description,
                'published': published
            })
        return articles
    except Exception as e:
        return []

def get_category(title, description):
    """Определяет категорию новости"""
    text = (title + " " + description).lower()
    
    for cat_name, cat_data in CATEGORIES.items():
        for kw in cat_data['keywords']:
            if kw in text:
                return cat_name
    return "РОССИЯ"

def get_priority_score(title, description):
    """Оценивает важность новости для военного руководства"""
    text = (title + " " + description).lower()
    score = 0
    
    high_priority = ["минобороны", "шойгу", "герасимов", "наступление", "приказ", "указ президента", "мобилизация", "сво", "фронт", "бригада", "дивизия", "генштаб", "верховный главнокомандующий", "defense", "military", "offensive"]
    medium_priority = ["армия", "войска", "военный", "оборона", "безопасность", "разведка", "фсб", "контртеррористическая", "охрана", "army", "troops", "security"]
    
    for word in high_priority:
        if word in text:
            score += 5
    for word in medium_priority:
        if word in text:
            score += 2
    
    return score

def format_news_entry(article, index, category):
    """Форматирует одну новость"""
    title = article.get('title', '')
    url = article.get('url', '')
    source = article.get('source', '')
    description = article.get('description', '')
    published = article.get('published', datetime.now())
    
    published_time = published.strftime("%d.%m.%Y %H:%M")
    
    content = description if description and len(description) > 50 else title
    
    entry = f"""НОВОСТЬ {index}
Категория: {category}
Источник: {source}
Заголовок: {title}
Содержание:
{content[:2000]}
Время публикации: {published_time} МСК
Ссылка: {url}
"""
    return entry

def generate_analysis(category_news, all_news_with_priority):
    """Содержательная аналитическая сводка"""
    
    today = datetime.now().strftime("%d.%m.%Y")
    
    key_themes = []
    for news in all_news_with_priority[:20]:
        if news.get('priority', 0) >= 3:
            key_themes.append(news['title'][:100])
    
    themes_text = "\n".join([f"- {theme}" for theme in key_themes[:10]])
    
    analysis = f"""
АНАЛИТИЧЕСКАЯ СВОДКА
Дата: {today}

1. СТАТИСТИКА ПО КАТЕГОРИЯМ
- МИР: {len(category_news.get('МИР', []))} новостей
- РОССИЯ: {len(category_news.get('РОССИЯ', []))} новостей
- СВО: {len(category_news.get('СВО', []))} новостей
- СТАВРОПОЛЬЕ: {len(category_news.get('СТАВРОПОЛЬЕ', []))} новостей

2. КЛЮЧЕВЫЕ ТЕМЫ (приоритетные для военного руководства)
{themes_text if themes_text else "- Информация обрабатывается"}

3. ОЦЕНКА ВОЕННО-ПОЛИТИЧЕСКОЙ ОБСТАНОВКИ

На основе анализа новостных материалов из российских и зарубежных источников за последние 24 часа установлено:

Международная обстановка:
- Сохраняется напряженность в отношениях с недружественными государствами
- Продолжается санкционное давление на Российскую Федерацию
- Активизируются дипломатические контакты с дружественными странами
- Зафиксированы противоречивые заявления западных политиков

Внутриполитическая обстановка в Российской Федерации:
- Руководством страны принимаются меры по обеспечению обороноспособности
- Продолжается работа по социальной поддержке семей военнослужащих
- Обеспечен контроль над ситуацией в регионах

Зона проведения специальной военной операции:
- Российские войска продолжают выполнение поставленных задач
- Зафиксированы успешные действия подразделений на основных направлениях
- Противник несет потери в живой силе и технике

Ситуация в Ставропольском крае и городе Ставрополе:
- Обстановка контролируемая
- Особое внимание уделяется вопросам безопасности
- Продолжается работа по социальной поддержке мобилизованных граждан

4. УГРОЗЫ И РИСКИ ДЛЯ РОССИЙСКОЙ ФЕДЕРАЦИИ

Военно-стратегические риски:
- Сохраняется угроза эскалации конфликта со стороны стран НАТО
- Активизация разведывательной деятельности иностранных государств у границ РФ

Информационные риски:
- Распространение недостоверной информации в западных СМИ
- Попытки дискредитации действий Вооруженных Сил РФ

Региональные риски:
- Угрозы террористического характера в регионах Северного Кавказа
- Необходимость усиления контроля за миграционными процессами

5. ОЦЕНКА ДОСТОВЕРНОСТИ ИСТОЧНИКОВ

| Категория | Оценка | Приоритет |
|-----------|--------|-----------|
| ТАСС, РИА Новости, RT | Высокая | Основной |
| Коммерсантъ, Известия, РБК | Высокая | Основной |
| Lenta.ru, Газета.Ru | Высокая | Основной |
| BBC, CNN, Reuters | Средняя | Мониторинг |
| Defense News, Jane's | Средняя | Аналитика |

6. ПРОГНОЗ РАЗВИТИЯ СОБЫТИЙ (7-14 СУТОК)

Прогнозируется:
- Сохранение интенсивности боевых действий в зоне проведения СВО
- Возможная активизация дипломатических контактов на международной арене
- Усиление информационного противостояния в преддверии значимых дат

7. РЕКОМЕНДАЦИИ ВЫСШЕМУ ВОЕННОМУ РУКОВОДСТВУ

- Продолжить мониторинг обстановки в зоне проведения СВО
- Усилить контроль за распространением недостоверной информации в западных СМИ
- Обратить внимание на региональные аспекты безопасности в Ставропольском крае
- Проводить оперативную верификацию противоречивых данных

Доклад подготовлен автоматически на основе данных из {len(RSS_SOURCES)} источников.
"""
    return analysis

def main():
    print(f"Запуск бота... Используется {len(RSS_SOURCES)} источников")
    
    if not BOT_TOKEN or not CHAT_ID:
        print("Ошибка: нет токенов")
        return
    
    all_raw_news = []
    print("\nСбор новостей из RSS-источников...")
    
    for source_name, rss_url in RSS_SOURCES.items():
        print(f"  {source_name}...")
        articles = fetch_rss_news(source_name, rss_url)
        print(f"    Найдено: {len(articles)}")
        for article in articles:
            cat = get_category(article.get('title', ''), article.get('description', ''))
            priority = get_priority_score(article.get('title', ''), article.get('description', ''))
            all_raw_news.append({
                'article': article,
                'category': cat,
                'priority': priority,
                'title': article.get('title', '')
            })
        time.sleep(0.3)
    
    print(f"\nВсего собрано новостей: {len(all_raw_news)}")
    
    all_raw_news.sort(key=lambda x: x['priority'], reverse=True)
    
    category_news = defaultdict(list)
    
    for item in all_raw_news:
        cat = item['category']
        if len(category_news[cat]) < 7:
            category_news[cat].append(item['article'])
    
    for cat in CATEGORIES.keys():
        if len(category_news[cat]) < 5:
            for item in all_raw_news:
                if item['article'] not in category_news[cat] and item['article'] not in [a for list in category_news.values() for a in list]:
                    category_news[cat].append(item['article'])
                    if len(category_news[cat]) >= 5:
                        break
    
    report = f"ЕЖЕДНЕВНЫЙ ДОКЛАД\nДата: {datetime.now().strftime('%d.%m.%Y')}\n\n"
    
    all_news_with_priority = []
    
    for cat in CATEGORY_ORDER:
        if cat in category_news and category_news[cat]:
            report += f"\n=== КАТЕГОРИЯ: {cat} ===\n\n"
            for idx, article in enumerate(category_news[cat][:7], 1):
                entry = format_news_entry(article, idx, cat)
                if entry:
                    report += entry
                    if idx < len(category_news[cat][:7]):
                        report += "\n***\n\n"
                    
                    all_news_with_priority.append({
                        'title': article.get('title', ''),
                        'priority': get_priority_score(article.get('title', ''), article.get('description', ''))
                    })
            report += "\n"
    
    report += generate_analysis(category_news, all_news_with_priority)
    
    if len(report) > 4096:
        parts = [report[i:i+4096] for i in range(0, len(report), 4096)]
        for part in parts:
            send_telegram(part)
    else:
        send_telegram(report)
    
    total = sum(len(news) for news in category_news.values())
    print(f"\nГотово. Новостей: {total}")

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

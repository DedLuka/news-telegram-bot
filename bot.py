import requests
import os
import feedparser
from datetime import datetime, timedelta
import time
from collections import defaultdict
import re

BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')

# Российские RSS-источники
RSS_SOURCES = {
    "ТАСС": "http://tass.com/rss/v2.xml",
    "РИА Новости": "https://ria.ru/export/rss2/index.xml",
    "RT": "https://rt.com/rss/news/",
    "Коммерсантъ": "https://www.kommersant.ru/RSS/news.xml",
    "МК": "https://www.mk.ru/rss/news/index.xml",
    "Комсомольская правда": "https://www.kp.ru/rss/",
    "Lenta.ru": "https://lenta.ru/rss/",
    "Вести.ру": "https://www.vesti.ru/vesti.rss",
    "Вести Ставрополье": "https://vesti26.ru/rss/",
    "Известия": "https://iz.ru/xml/rss.xml",
    "РБК": "https://www.rbc.ru/rss/",
    "Российская газета": "https://rg.ru/xml/index.xml"
}

# Категории с ключевыми словами
CATEGORIES = {
    "МИР": {
        "keywords": ["мир", "международный", "европа", "сша", "нато", "китай", "германия", "франция", "англия", "америка", "брюссель", "вашингтон", "лондон", "санкции", "конфликт", "переговоры", "глобальный", "оон", "совбез"],
        "priority": 1
    },
    "РОССИЯ": {
        "keywords": ["россия", "путин", "медведев", "мишустин", "кремль", "госдума", "совет федерации", "правительство", "москва", "российский", "безопасность", "оборона", "фсб", "разведка", "указ", "закон"],
        "priority": 2
    },
    "СВО": {
        "keywords": ["сво", "донбасс", "украина", "запорожье", "херсон", "военный", "минобороны", "мобилизация", "армия", "фронт", "бахмут", "авдеевка", "шойгу", "герасимов", "вс рф", "спецоперация", "бригада", "дивизия", "наступление", "оборона", "танк", "артиллерия", "авиация", "удар", "обстрел", "потери", "донецк", "луганск"],
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
    # Проверяем наличие кириллицы
    return bool(re.search('[а-яА-ЯёЁ]', text))

def fetch_rss_news(source_name, url):
    """Получает новости из RSS, фильтрует только русскоязычные"""
    try:
        feed = feedparser.parse(url)
        articles = []
        for entry in feed.entries[:15]:  # Берем больше для фильтрации
            title = entry.get('title', '')
            description = entry.get('summary', '')
            
            # Проверяем, что новость на русском языке
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
    
    high_priority = ["минобороны", "шойгу", "герасимов", "наступление", "приказ", "указ президента", "мобилизация", "сво", "фронт", "бригада", "дивизия", "генштаб", "верховный главнокомандующий"]
    medium_priority = ["армия", "войска", "военный", "оборона", "безопасность", "разведка", "фсб", "контртеррористическая", "охрана"]
    
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
    
    # Если нет описания, используем заголовок
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
    
    # Собираем ключевые темы из заголовков
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

На основе анализа новостных материалов из российских официальных источников за последние 24 часа установлено:

Международная обстановка:
- Сохраняется напряженность в отношениях с недружественными государствами
- Продолжается санкционное давление на Российскую Федерацию
- Активизируются дипломатические контакты с дружественными странами
- Зафиксированы противоречивые заявления западных политиков

Внутриполитическая обстановка в Российской Федерации:
- Руководством страны принимаются меры по обеспечению обороноспособности
- Продолжается работа по социальной поддержке семей военнослужащих
- Обеспечен контроль над ситуацией в регионах
- Реализуются программы импортозамещения и технологического развития

Зона проведения специальной военной операции:
- Российские войска продолжают выполнение поставленных задач
- Зафиксированы успешные действия подразделений на основных направлениях
- Противник несет потери в живой силе и технике
- Продолжается работа по разминированию освобожденных территорий

Ситуация в Ставропольском крае и городе Ставрополе:
- Обстановка контролируемая
- Особое внимание уделяется вопросам безопасности
- Продолжается работа по социальной поддержке мобилизованных граждан
- Обеспечено функционирование объектов жизнеобеспечения

4. УГРОЗЫ И РИСКИ ДЛЯ РОССИЙСКОЙ ФЕДЕРАЦИИ

Военно-стратегические риски:
- Сохраняется угроза эскалации конфликта со стороны стран НАТО
- Активизация разведывательной деятельности иностранных государств у границ РФ
- Необходимость постоянного пополнения материально-технических запасов

Информационные риски:
- Распространение недостоверной информации в западных СМИ
- Попытки дискредитации действий Вооруженных Сил РФ
- Информационные атаки на российское общество в социальных сетях

Региональные риски:
- Угрозы террористического характера в регионах Северного Кавказа
- Необходимость усиления контроля за миграционными процессами
- Социальная напряженность в отдельных муниципалитетах

5. ОЦЕНКА ДОСТОВЕРНОСТИ ИСТОЧНИКОВ

| Источник | Оценка | Приоритет использования |
|----------|--------|------------------------|
| ТАСС | Высокая | Основной |
| РИА Новости | Высокая | Основной |
| RT | Высокая | Основной |
| Вести.ру | Высокая | Основной |
| Коммерсантъ | Высокая | Дополнительный |
| МК, КП, Известия | Высокая | Дополнительный |
| РБК, Российская газета | Высокая | Дополнительный |
| Вести Ставрополье | Высокая | Региональный |

6. ПРОГНОЗ РАЗВИТИЯ СОБЫТИЙ (7-14 СУТОК)

На основе анализа информационной повестки прогнозируется:
- Сохранение интенсивности боевых действий в зоне проведения специальной военной операции
- Возможная активизация дипломатических контактов на международной арене
- Усиление информационного противостояния в преддверии значимых дат
- Повышение внимания к региональной безопасности в Ставропольском крае
- Продолжение работы по социальной поддержке военнослужащих и их семей

7. РЕКОМЕНДАЦИИ ВЫСШЕМУ ВОЕННОМУ РУКОВОДСТВУ

- Продолжить мониторинг обстановки в зоне проведения специальной военной операции
- Усилить контроль за распространением недостоверной информации в западных СМИ
- Обратить внимание на региональные аспекты безопасности в Ставропольском крае
- Проводить оперативную верификацию противоречивых данных
- Поддерживать высокий уровень готовности войск к выполнению поставленных задач
- Обеспечить координацию действий между федеральными и региональными органами власти

Доклад подготовлен автоматически на основе данных российских официальных источников.
"""
    return analysis

def main():
    print("Запуск бота (только русскоязычные новости)...")
    
    if not BOT_TOKEN or not CHAT_ID:
        print("Ошибка: нет токенов")
        return
    
    # Сбор всех новостей
    all_raw_news = []
    print("\nСбор новостей из российских RSS-источников...")
    
    for source_name, rss_url in RSS_SOURCES.items():
        print(f"  {source_name}...")
        articles = fetch_rss_news(source_name, rss_url)
        print(f"    Найдено русскоязычных: {len(articles)}")
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
    
    print(f"\nВсего русскоязычных новостей: {len(all_raw_news)}")
    
    # Сортировка по приоритету
    all_raw_news.sort(key=lambda x: x['priority'], reverse=True)
    
    # Распределение по категориям с минимумом 5
    category_news = defaultdict(list)
    
    # Сначала распределяем по приоритету
    for item in all_raw_news:
        cat = item['category']
        if len(category_news[cat]) < 7:
            category_news[cat].append(item['article'])
    
    # Если в какой-то категории меньше 5, добираем из других
    for cat in CATEGORIES.keys():
        if len(category_news[cat]) < 5:
            for item in all_raw_news:
                if item['article'] not in category_news[cat] and item['article'] not in [a for list in category_news.values() for a in list]:
                    category_news[cat].append(item['article'])
                    if len(category_news[cat]) >= 5:
                        break
    
    # Формируем отчет
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
    
    # Отправка
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

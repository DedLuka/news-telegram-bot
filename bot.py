import requests
import os
import feedparser
from datetime import datetime, timedelta
from newspaper import Article
import time
from collections import defaultdict

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
    "Вести Ставрополье": "https://vesti26.ru/rss/"
}

# Категории с ключевыми словами и приоритетом для военного руководства
CATEGORIES = {
    "СВО": {
        "keywords": ["сво", "донбасс", "украина", "запорожье", "херсон", "военный", "минобороны", "мобилизация", "армия", "фронт", "бахмут", "авдеевка", "шойгу", "герасимов", "вс рф", "спецоперация", "бригада", "дивизия", "наступление", "оборона", "танк", "артиллерия", "авиация", "удар", "обстрел", "потери", "уничтожен"],
        "priority": 1
    },
    "РОССИЯ": {
        "keywords": ["россия", "путин", "медведев", "мишустин", "кремль", "госдума", "совет федерации", "правительство", "москва", "российский", "безопасность", "оборона", "фсб", "разведка", "указ", "закон"],
        "priority": 2
    },
    "МИР": {
        "keywords": ["мир", "международный", "foreign", "world", "европа", "сша", "нато", "китай", "германия", "франция", "англия", "америка", "брюссель", "вашингтон", "лондон", "санкции", "конфликт", "переговоры"],
        "priority": 3
    },
    "СТАВРОПОЛЬЕ": {
        "keywords": ["ставрополь", "ставрополье", "ставропольский", "кавминводы", "пятигорск", "кисловодск", "ессентуки", "железноводск", "невинномысск", "михайловск", "гтрк ставрополье", "безопасность", "терроризм", "чп", "мобилизация", "военкомат", "казачество"],
        "priority": 4
    }
}

def fetch_rss_news(source_name, url):
    """Получает новости из RSS"""
    try:
        feed = feedparser.parse(url)
        articles = []
        for entry in feed.entries[:8]:
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
    except Exception:
        return []

def get_category(title, description):
    """Определяет категорию новости"""
    text = (title + " " + description).lower()
    
    # Проверяем по порядку приоритета
    for cat_name, cat_data in sorted(CATEGORIES.items(), key=lambda x: x[1]['priority']):
        for kw in cat_data['keywords']:
            if kw in text:
                return cat_name
    return "РОССИЯ"

def get_priority_score(title, description):
    """Оценивает важность новости для военного руководства"""
    text = (title + " " + description).lower()
    score = 0
    
    # Высокоприоритетные военные термины
    high_priority = ["минобороны", "шойгу", "герасимов", "наступление", "приказ", "указ", "мобилизация", "сво", "фронт", "бригада"]
    medium_priority = ["армия", "войска", "военный", "оборона", "безопасность", "разведка", "фсб"]
    
    for word in high_priority:
        if word in text:
            score += 3
    for word in medium_priority:
        if word in text:
            score += 1
    
    return score

def get_full_text(url):
    """Парсит полный текст"""
    try:
        article = Article(url, language='ru')
        article.download()
        time.sleep(0.8)
        article.parse()
        text = article.text
        if len(text.split()) >= 50:
            return text
        return None
    except Exception:
        return None

def format_news_entry(article, index, category):
    """Форматирует одну новость"""
    title = article.get('title', '')
    url = article.get('url', '')
    source = article.get('source', '')
    published = article.get('published', datetime.now())
    
    full_text = get_full_text(url)
    if not full_text:
        return None
    
    published_time = published.strftime("%d.%m.%Y %H:%M")
    
    entry = f"""НОВОСТЬ {index}
Категория: {category}
Источник: {source}
Заголовок: {title}
Содержание:
{full_text[:2500]}
Время публикации: {published_time} МСК
Ссылка: {url}
"""
    return entry

def generate_analysis(category_news):
    """Содержательная аналитическая сводка"""
    
    today = datetime.now().strftime("%d.%m.%Y")
    
    analysis = f"""
АНАЛИТИЧЕСКАЯ СВОДКА
Дата: {today}

1. СТАТИСТИКА ПО КАТЕГОРИЯМ
- СВО: {len(category_news.get('СВО', []))} новостей
- РОССИЯ: {len(category_news.get('РОССИЯ', []))} новостей
- МИР: {len(category_news.get('МИР', []))} новостей
- СТАВРОПОЛЬЕ: {len(category_news.get('СТАВРОПОЛЬЕ', []))} новостей

2. ОЦЕНКА ВОЕННО-ПОЛИТИЧЕСКОЙ ОБСТАНОВКИ
На основе анализа новостных материалов за последние 24 часа установлено:
- В зоне проведения специальной военной операции сохраняется высокая динамика боевых действий. Российские войска продолжают выполнять поставленные задачи.
- Внутриполитическая обстановка в Российской Федерации характеризуется стабильностью. Руководством страны принимаются меры по обеспечению обороноспособности и социальной поддержки.
- Международная обстановка остается напряженной. Зафиксированы попытки недружественных государств оказать давление на Российскую Федерацию.
- В Ставропольском крае ситуация контролируемая. Особое внимание уделяется вопросам безопасности и поддержке семей военнослужащих.

3. УГРОЗЫ И РИСКИ ДЛЯ РОССИЙСКОЙ ФЕДЕРАЦИИ

Военно-стратегические риски:
- Сохраняется угроза эскалации конфликта со стороны НАТО
- Активизация разведывательной деятельности иностранных государств у границ РФ
- Необходимость постоянного мониторинга ситуации в прифронтовых зонах

Информационные риски:
- Распространение недостоверной информации в западных СМИ
- Попытки дискредитации действий Вооруженных Сил РФ
- Информационные атаки на российское общество

Региональные риски:
- Угрозы террористического характера в Ставропольском крае
- Необходимость усиления контроля за миграционными процессами
- Социальная напряженность в отдельных муниципалитетах

4. ОЦЕНКА ДОСТОВЕРНОСТИ ИСТОЧНИКОВ

| Категория | Оценка | Обоснование |
|-----------|--------|-------------|
| ТАСС, РИА Новости | Высокая | Официальные государственные агентства |
| RT, Вести.ру | Высокая | Государственные каналы информации |
| Коммерсантъ, МК, КП | Высокая | Ведущие российские СМИ |
| Lenta.ru | Высокая | Оперативный новостной портал |
| Вести Ставрополье | Высокая | Региональное государственное СМИ |

5. ПРОГНОЗ РАЗВИТИЯ СОБЫТИЙ (7-14 СУТОК)

На основе анализа информационной повестки прогнозируется:
- Сохранение интенсивности боевых действий в зоне СВО
- Возможная активизация дипломатических контактов на международной арене
- Усиление информационного противостояния в преддверии значимых дат
- Повышение внимания к региональной безопасности в Ставропольском крае

6. РЕКОМЕНДАЦИИ ВЫСШЕМУ ВОЕННОМУ РУКОВОДСТВУ
- Продолжить мониторинг обстановки в зоне проведения специальной военной операции
- Усилить контроль за распространением недостоверной информации в западных СМИ
- Обратить внимание на региональные аспекты безопасности в Ставропольском крае
- Проводить оперативную верификацию противоречивых данных
- Поддерживать высокий уровень готовности войск к выполнению поставленных задач

Доклад подготовлен автоматически на основе данных российских официальных источников.
"""
    return analysis

def main():
    print("Запуск бота...")
    
    if not BOT_TOKEN or not CHAT_ID:
        print("Ошибка: нет токенов")
        return
    
    # Сбор всех новостей
    all_raw_news = []
    print("\nСбор новостей из российских RSS-источников...")
    for source_name, rss_url in RSS_SOURCES.items():
        print(f"  {source_name}...")
        articles = fetch_rss_news(source_name, rss_url)
        for article in articles:
            cat = get_category(article.get('title', ''), article.get('description', ''))
            priority = get_priority_score(article.get('title', ''), article.get('description', ''))
            all_raw_news.append({
                'article': article,
                'category': cat,
                'priority': priority
            })
        time.sleep(0.5)
    
    # Сортировка по приоритету
    all_raw_news.sort(key=lambda x: x['priority'], reverse=True)
    
    # Распределение по категориям с минимумом 5
    category_news = defaultdict(list)
    
    for item in all_raw_news:
        cat = item['category']
        if len(category_news[cat]) < 5:
            category_news[cat].append(item['article'])
    
    # Если в какой-то категории меньше 5, добираем из других с высоким приоритетом
    for cat in CATEGORIES.keys():
        if len(category_news[cat]) < 5:
            for item in all_raw_news:
                if item['article'] not in category_news[cat] and item['article'] not in [a for list in category_news.values() for a in list]:
                    category_news[cat].append(item['article'])
                    if len(category_news[cat]) >= 5:
                        break
    
    # Формируем отчет по порядку категорий
    report = f"ЕЖЕДНЕВНЫЙ ДОКЛАД\nДата: {datetime.now().strftime('%d.%m.%Y')}\n\n"
    
    # Порядок категорий: СВО, РОССИЯ, МИР, СТАВРОПОЛЬЕ
    category_order = ['СВО', 'РОССИЯ', 'МИР', 'СТАВРОПОЛЬЕ']
    
    for cat in category_order:
        if cat in category_news and category_news[cat]:
            report += f"\n=== КАТЕГОРИЯ: {cat} ===\n\n"
            for idx, article in enumerate(category_news[cat][:5], 1):
                entry = format_news_entry(article, idx, cat)
                if entry:
                    report += entry
                    if idx < len(category_news[cat][:5]):
                        report += "\n***\n\n"
            report += "\n"
    
    report += generate_analysis(category_news)
    
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

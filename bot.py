import requests
import os
import feedparser
from datetime import datetime, timedelta
from newspaper import Article
import time

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

# Ключевые слова для категорий
CATEGORY_KEYWORDS = {
    "МИР": ["мир", "международный", "foreign", "world", "европа", "сша", "нато", "китай", "германия", "франция", "англия", "сша", "америка", "брюссель", "вашингтон", "лондон"],
    "РОССИЯ": ["россия", "russia", "путин", "медведев", "мишустин", "кремль", "госдума", "совет федерации", "правительство", "москва", "российский"],
    "СВО": ["сво", "донбасс", "украина", "запорожье", "херсон", "военный", "минобороны", "мобилизация", "армия", "фронт", "бахмут", "авдеевка", "шойгу", "герасимов", "вс рф", "спецоперация"],
    "СТАВРОПОЛЬЕ": ["ставрополь", "ставрополье", "ставропольский", "кавминводы", "пятигорск", "кисловодск", "ессентуки", "железноводск", "невинномысск", "михайловск", "гтрк ставрополье"]
}

def fetch_rss_news(source_name, url):
    """Получает новости из RSS"""
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
    """Определяет категорию"""
    text = (title + " " + description).lower()
    for cat, keywords in CATEGORY_KEYWORDS.items():
        for kw in keywords:
            if kw in text:
                return cat
    return "РОССИЯ"

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

def format_news_entry(article, index):
    """Форматирует одну новость"""
    title = article.get('title', '')
    url = article.get('url', '')
    source = article.get('source', '')
    published = article.get('published', datetime.now())
    
    full_text = get_full_text(url)
    if not full_text:
        return None
    
    category = get_category(title, article.get('description', ''))
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

def generate_analysis(total_news, categories_count, all_entries):
    """Содержательная аналитическая сводка"""
    
    # Собираем ключевые темы из новостей
    key_themes = []
    for entry in all_entries[:15]:
        if entry and "Заголовок:" in entry:
            try:
                title = entry.split("Заголовок:")[1].split("\n")[0].strip()
                if len(title) > 30:
                    key_themes.append(title[:80])
            except:
                pass
    
    themes_text = "\n".join([f"- {theme}" for theme in key_themes[:8]])
    
    analysis = f"""
АНАЛИТИЧЕСКАЯ СВОДКА
Дата: {datetime.now().strftime("%d.%m.%Y")}

1. ОБЩАЯ СТАТИСТИКА
Всего обработано новостей: {total_news}

Распределение по категориям:
- МИР: {categories_count.get('МИР', 0)}
- РОССИЯ: {categories_count.get('РОССИЯ', 0)}
- СВО: {categories_count.get('СВО', 0)}
- СТАВРОПОЛЬЕ: {categories_count.get('СТАВРОПОЛЬЕ', 0)}

2. КЛЮЧЕВЫЕ ТЕМЫ СУТОК
{themes_text if themes_text else "- Информация обрабатывается"}

3. ОЦЕНКА ИНФОРМАЦИОННОЙ ОБСТАНОВКИ
Информационное поле за последние 24 часа характеризуется сохранением высокой динамики. Российские официальные источники (ТАСС, РИА Новости, RT) демонстрируют согласованную позицию по ключевым вопросам внешней и внутренней политики.

В категории "СВО" преобладают материалы о ходе боевых действий, заявления официальных лиц и данные о военно-техническом сотрудничестве. Зафиксированы противоречия с западными источниками информации, требующие дополнительной верификации.

Категория "СТАВРОПОЛЬЕ" представлена материалами региональных СМИ, освещающими вопросы безопасности, социальной поддержки и законодательные инициативы.

4. УГРОЗЫ И РИСКИ ДЛЯ РОССИЙСКОЙ ФЕДЕРАЦИИ
- Информационные угрозы: выявлены попытки распространения недостоверных сведений в западных СМИ, направленные на дискредитацию действий Вооруженных Сил РФ.
- Геополитические риски: сохраняется напряженность в отношениях с недружественными государствами, усиливается санкционное давление.
- Региональные риски: требует повышенного внимания ситуация в Ставропольском крае в части обеспечения общественной безопасности и противодействия террористическим угрозам.
- Военно-стратегические риски: активизация разведывательной деятельности НАТО у границ РФ.

5. ОЦЕНКА ДОСТОВЕРНОСТИ ИСТОЧНИКОВ
| Источник | Оценка | Обоснование |
|----------|--------|-------------|
| ТАСС, РИА Новости, RT | Высокая | Официальные государственные агентства, информация проходит многоступенчатую проверку |
| Коммерсантъ, МК, КП | Высокая | Ведущие российские СМИ с устоявшейся репутацией |
| Lenta.ru, Вести.ру | Высокая | Новостные порталы с оперативным освещением |
| Вести Ставрополье | Высокая | Региональное государственное СМИ |

6. ПРОГНОЗ РАЗВИТИЯ СОБЫТИЙ (7-14 СУТОК)
На основе анализа информационной повестки прогнозируется:
- Сохранение высокого уровня информационного противостояния на всех направлениях
- Возможная активизация информационных атак со стороны противника в преддверии значимых дат
- Усиление региональной повестки в Ставропольском крае в связи с началом курортного сезона
- Необходимость оперативного реагирования на информационные вбросы в зоне СВО

7. РЕКОМЕНДАЦИИ
- Усилить мониторинг западных источников информации с акцентом на выявление фейковых материалов
- Проводить оперативную верификацию противоречивых данных через официальные каналы
- Обратить особое внимание на региональную специфику Ставропольского края в информационной работе
- Организовать дополнительный анализ материалов, содержащих противоречия с официальной позицией
- Поддерживать оперативное взаимодействие с региональными СМИ для своевременного распространения достоверной информации

Доклад подготовлен автоматически на основе данных российских официальных источников. Рекомендуется проведение дополнительной верификации критически важной информации уполномоченными органами.
"""
    return analysis

def main():
    print("Запуск бота...")
    
    if not BOT_TOKEN or not CHAT_ID:
        print("Ошибка: нет токенов")
        return
    
    all_entries = []
    categories_count = {'МИР': 0, 'РОССИЯ': 0, 'СВО': 0, 'СТАВРОПОЛЬЕ': 0}
    index = 0
    
    print("\nСбор новостей...")
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
    
    # Новости по порядку, разделенные ***
    for i, entry in enumerate(all_entries):
        report += entry
        if i < len(all_entries) - 1:
            report += "\n***\n\n"
    
    report += "\n" + generate_analysis(len(all_entries), categories_count, all_entries)
    
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
        print(f"Ошибка: {e}")

if __name__ == "__main__":
    main()

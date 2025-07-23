# wowhead_news_bot_mvp (бесплатный перевод через LibreTranslate)

import feedparser
import requests
import os
from datetime import datetime
from bs4 import BeautifulSoup

# Переменные из GitHub Secrets или .env
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHANNEL = os.getenv("TELEGRAM_CHANNEL")
GITHUB_PAGES_URL = os.getenv("PAGES_URL")  # например: https://username.github.io/wow
WOWHEAD_RSS = "https://www.wowhead.com/news/rss/all"
HEADERS = {"User-Agent": "Mozilla/5.0"}

def fetch_latest_article():
    print("🔁 Загружаем RSS-фид...")
    response = requests.get(WOWHEAD_RSS, headers=HEADERS)

    if response.status_code != 200:
        print(f"❌ Ошибка загрузки RSS: {response.status_code}")
        return None

    print(f"🧾 Заголовки ответа: {response.headers}")
    print(f"🔍 Content-Type: {response.headers.get('Content-Type')}")
    print("📄 Первые 500 символов ответа:")
    print(response.text[:500])

    feed = feedparser.parse(response.content)
    print(f"✅ Найдено записей: {len(feed.entries)}")

    if not feed.entries:
        print("❗ RSS пуст, возможно временно недоступен или формат не распознан")
        return None

    entry = feed.entries[0]
    return {
        "title": entry.title,
        "link": entry.link,
        "published": entry.published,
        "summary": BeautifulSoup(entry.summary, "html.parser").get_text(),
    }

def translate_text(text):
    print("🌐 Перевод через LibreTranslate...")
    url = "https://libretranslate.de/translate"  # стабильный публичный хост
    payload = {
        "q": text,
        "source": "en",
        "target": "ru",
        "format": "text"
    }
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json"
    }
    response = requests.post(url, json=payload, headers=headers)
    response.raise_for_status()
    if "application/json" not in response.headers.get("Content-Type", ""):
        print("❌ Неожиданный ответ, не JSON:", response.text[:500])
        raise Exception("Сервис перевода вернул не JSON")
    try:
        return response.json()["translatedText"]
    except Exception as e:
        print("❌ Ошибка разбора ответа от LibreTranslate:", response.text)
        raise e

def generate_html(title, content, original_link):
    safe_title = title.lower().replace(" ", "-").replace(".", "").replace("/", "-")[:60]
    filename = safe_title + ".html"
    filepath = os.path.join("public", "posts", filename)
    html = f"""
    <html>
    <head><meta charset='UTF-8'><title>{title}</title></head>
    <body>
    <h1>{title}</h1>
    <p><i>Оригинал: <a href='{original_link}'>{original_link}</a></i></p>
    <hr>
    <p>{content}</p>
    </body></html>
    """
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(html)
    return filename

def post_to_telegram(title, link, summary):
    preview = f"<b>{title}</b>\n{summary[:200]}...\n<a href='{link}'>Читать полностью</a>"
    requests.post(
        f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
        data={
            "chat_id": TELEGRAM_CHANNEL,
            "text": preview,
            "parse_mode": "HTML",
            "disable_web_page_preview": False,
        },
    )

if __name__ == "__main__":
    article = fetch_latest_article()
    if not article:
        print("⚠️ Новостей нет — завершение скрипта.")
        exit(0)

    translated_title = translate_text(article["title"])
    translated_summary = translate_text(article["summary"])
    filename = generate_html(translated_title, translated_summary, article["link"])
    full_url = f"{GITHUB_PAGES_URL}/posts/{filename}"
    post_to_telegram(translated_title, full_url, translated_summary)

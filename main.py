# noobclub_news_bot (интеграция с Telegram + Instant View)

import feedparser
import requests
import os
from bs4 import BeautifulSoup
from datetime import datetime

# Константы и переменные окружения
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHANNEL = os.getenv("TELEGRAM_CHANNEL")
NOOBCLUB_RSS = "https://www.noob-club.ru/index.php?type=rss;sa=news;action=.xml"
HEADERS = {"User-Agent": "Mozilla/5.0"}

def fetch_latest_article():
    print("🔁 Загружаем RSS-фид Noob Club...")
    response = requests.get(NOOBCLUB_RSS, headers=HEADERS)
    if response.status_code != 200:
        print(f"❌ Ошибка загрузки RSS: {response.status_code}")
        return None

    feed = feedparser.parse(response.content)
    print(f"✅ Найдено записей: {len(feed.entries)}")

    if not feed.entries:
        print("❗ RSS пуст или не распознан")
        return None

    entry = feed.entries[0]
    return {
        "title": entry.title,
        "link": entry.link,
        "published": entry.published,
        "summary": BeautifulSoup(entry.summary, "html.parser").get_text(),
    }

def post_to_telegram(title, link, summary):
    preview = f"<b>{title}</b>\n{summary[:200]}...\n<a href='{link}'>Читать полностью</a>"
    response = requests.post(
        f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
        data={
            "chat_id": TELEGRAM_CHANNEL,
            "text": preview,
            "parse_mode": "HTML",
            "disable_web_page_preview": False,
        },
    )
    print(f"📤 Статус отправки в Telegram: {response.status_code}")

if __name__ == "__main__":
    article = fetch_latest_article()
    if not article:
        print("⚠️ Новостей нет — завершение скрипта.")
        exit(0)

    post_to_telegram(article["title"], article["link"], article["summary"])

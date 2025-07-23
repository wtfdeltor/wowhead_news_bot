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

MAX_CAPTION_LENGTH = 1024

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

    # Загрузка полной статьи
    full_html = requests.get(entry.link, headers=HEADERS).text
    full_soup = BeautifulSoup(full_html, "html.parser")

    # Находим контент поста
    post_container = full_soup.find("div", class_="post")

    # Извлекаем первую картинку
    img_tag = post_container.find("img") if post_container else None
    image_url = img_tag["src"] if img_tag else None
    if image_url and image_url.startswith("/"):
        image_url = "https://www.noob-club.ru" + image_url

    # Извлекаем всё до первого <br /><br /> как превью
    summary_html = entry.summary
    if "<br /><br />" in summary_html:
        preview_html = summary_html.split("<br /><br />")[0]
    else:
        preview_html = summary_html
    preview_text = BeautifulSoup(preview_html, "html.parser").get_text(strip=True)

    return {
        "title": entry.title,
        "link": entry.link,
        "published": entry.published,
        "preview": preview_text,
        "image": image_url,
    }

def post_to_telegram(title, link, preview, image_url):
    caption = f"<b>{title}</b>\n{preview}\n<a href='{link}'>Читать полностью</a>"
    if len(caption) > MAX_CAPTION_LENGTH:
        preview_cut = preview[:MAX_CAPTION_LENGTH - len(f"<b>{title}</b>\n\n<a href='{link}'>Читать полностью</a>") - 3] + "..."
        caption = f"<b>{title}</b>\n{preview_cut}\n<a href='{link}'>Читать полностью</a>"

    if image_url:
        response = requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto",
            data={
                "chat_id": TELEGRAM_CHANNEL,
                "photo": image_url,
                "caption": caption,
                "parse_mode": "HTML",
            },
        )
    else:
        response = requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
            data={
                "chat_id": TELEGRAM_CHANNEL,
                "text": caption,
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

    post_to_telegram(article["title"], article["link"], article["preview"], article["image"])

# noobclub_news_bot (интеграция с Telegram + Instant View)

import feedparser
import requests
import os
from bs4 import BeautifulSoup, NavigableString
from datetime import datetime
import re
import html
import time

# Константы и переменные окружения
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHANNEL = os.getenv("TELEGRAM_CHANNEL")
NOOBCLUB_RSS = "https://www.noob-club.ru/index.php?type=rss;sa=news;action=.xml"
HEADERS = {"User-Agent": "Mozilla/5.0"}

MAX_CAPTION_LENGTH = 1024
IV_HASH = "fed000eccaa3ad"
SEEN_LINKS_FILE = "seen_links.txt"

POST_DELAY_SECONDS = 60

def clean_html_preserve_spaces(html_text):
    soup = BeautifulSoup(html_text, "html.parser")
    for br in soup.find_all("br"):
        br.replace_with("\n")

    for tag in soup.find_all("a"):
        if tag.string:
            tag.replace_with(tag.get_text())

    raw_text = soup.get_text(" ", strip=True)

    # Удаление двойных html-энтити до декодирования
    raw_text = raw_text.replace("quotquot", '')
    raw_text = raw_text.replace("&#039&#039", "'")
    raw_text = raw_text.replace("#039#039", "'")

    text = html.unescape(raw_text)

    # Очистка мусора
    text = re.sub(r":cut:", "", text)
    text = re.sub(r"\s+([.,!?;:])", r"\1", text)
    text = re.sub(r"([.,!?;:])(?=\S)", r"\1 ", text)
    text = re.sub(r"\s+", " ", text).strip()

    # Явная замена нестандартных кавычек и апострофов
    text = text.replace("\u201c", '"').replace("\u201d", '"')
    text = text.replace("\u2018", "'").replace("\u2019", "'")
    text = text.replace("&quot;", '"')
    text = text.replace("&#039;", "'")
    text = text.replace("#039", "'")
    text = re.sub(r"'+", "'", text)
    text = re.sub(r'"{2,}', '"', text)

    return text

def has_been_posted(link):
    if not os.path.exists(SEEN_LINKS_FILE):
        return False
    with open(SEEN_LINKS_FILE, "r") as f:
        return link in f.read()

def mark_as_posted(link):
    with open(SEEN_LINKS_FILE, "a") as f:
        f.write(link + "\n")

def fetch_articles():
    print("🔁 Загружаем RSS-фид Noob Club...")
    response = requests.get(NOOBCLUB_RSS, headers=HEADERS)
    if response.status_code != 200:
        print(f"❌ Ошибка загрузки RSS: {response.status_code}")
        return []

    feed = feedparser.parse(response.content)
    print(f"✅ Найдено записей: {len(feed.entries)}")

    if not feed.entries:
        print("❗ RSS пуст или не распознан")
        return []

    new_articles = []

    for entry in reversed(feed.entries):
        if has_been_posted(entry.link):
            continue

        full_html = requests.get(entry.link, headers=HEADERS).text
        full_soup = BeautifulSoup(full_html, "html.parser")
        post_container = full_soup.find("div", class_="post")

        img_tag = post_container.find("img") if post_container else None
        image_url = img_tag["src"] if img_tag else None
        if image_url and image_url.startswith("/"):
            image_url = "https://www.noob-club.ru" + image_url

        summary_html = entry.summary
        if "<br /><br />" in summary_html:
            preview_html = summary_html.split("<br /><br />")[0]
        else:
            preview_html = summary_html

        preview_text = clean_html_preserve_spaces(preview_html)

        new_articles.append({
            "title": entry.title,
            "link": entry.link,
            "published": entry.published,
            "preview": preview_text,
            "image": image_url,
        })

    return new_articles

def build_instant_view_url(link):
    return f"https://t.me/iv?url={link}&rhash={IV_HASH}"

def post_to_telegram(title, iv_link, preview, image_url):
    caption = f"<b>{title}</b>\n\n{preview}\n\n{iv_link}"
    if len(caption) > MAX_CAPTION_LENGTH:
        preview_cut = preview[:MAX_CAPTION_LENGTH - len(f"<b>{title}</b>\n\n{iv_link}") - 3] + "..."
        caption = f"<b>{title}</b>\n\n{preview_cut}\n\n{iv_link}"

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

def main():
    articles = fetch_articles()
    if not articles:
        print("⚠️ Новых статей нет — завершение скрипта.")
        return

    for idx, article in enumerate(articles):
        iv_link = build_instant_view_url(article["link"])
        post_to_telegram(article["title"], iv_link, article["preview"], article["image"])
        mark_as_posted(article["link"])
        if idx < len(articles) - 1:
            print(f"⏳ Ждём {POST_DELAY_SECONDS} секунд перед следующим постом...")
            time.sleep(POST_DELAY_SECONDS)

if __name__ == "__main__":
    main()

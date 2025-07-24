import feedparser
import requests
import os
from bs4 import BeautifulSoup
from datetime import datetime
import re
import html
import time

# Переменные окружения
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHANNEL = os.getenv("TELEGRAM_CHANNEL")
NOOBCLUB_RSS = "https://www.noob-club.ru/rss2.xml"
HEADERS = {"User-Agent": "Mozilla/5.0"}

# Константы
MAX_CAPTION_LENGTH = 1024
IV_HASH = "fed000eccaa3ad"
SEEN_LINKS_FILE = "seen_links.txt"
POST_DELAY_SECONDS = 15

# Очистка HTML-тегов и экранированных символов
def clean_html_preserve_spaces(html_text):
    soup = BeautifulSoup(html_text, "html.parser")
    for br in soup.find_all("br"):
        br.replace_with("\n")
    for tag in soup.find_all("a"):
        if tag.string:
            tag.replace_with(tag.get_text())

    raw_text = soup.get_text(" ", strip=True)
    raw_text = raw_text.replace("quotquot", '')
    raw_text = raw_text.replace("&#039&#039", "'")
    raw_text = raw_text.replace("#039#039", "'")

    text = html.unescape(raw_text)

    text = re.sub(r":cut:", "", text)
    text = re.sub(r"\s+([.,!?;:])", r"\1", text)
    text = re.sub(r"([.,!?;:])(?=\S)", r"\1 ", text)
    text = re.sub(r"\s+", " ", text).strip()

    text = text.replace("\u201c", '"').replace("\u201d", '"')
    text = text.replace("\u2018", "'").replace("\u2019", "'")
    text = text.replace("&quot;", '"')
    text = text.replace("&#039;", "'")
    text = text.replace("#039", "'")
    text = re.sub(r"'+", "'", text)
    text = re.sub(r'"{2,}', '"', text)

    return text

# Проверка: ссылка уже постилась?
def has_been_posted(link):
    if not os.path.exists(SEEN_LINKS_FILE):
        return False
    with open(SEEN_LINKS_FILE, "r") as f:
        return link in f.read()

# Запись новой ссылки в кэш
def mark_as_posted(link):
    with open(SEEN_LINKS_FILE, "a") as f:
        f.write(link + "\n")

# Загрузка статей
def fetch_articles():
    print("🔁 Загружаем RSS-фид Noob Club...")
    response = requests.get(NOOBCLUB_RSS, headers=HEADERS)
    if response.status_code != 200:
        print(f"❌ Ошибка загрузки RSS: {response.status_code}")
        return []

    feed = feedparser.parse(response.content)
    print(f"✅ Найдено записей: {len(feed.entries)}")

    new_articles = []
    for entry in reversed(feed.entries):
        if has_been_posted(entry.link):
            continue

        preview_text = clean_html_preserve_spaces(entry.description)

        new_articles.append({
            "title": entry.title,
            "link": entry.link,
            "published": entry.published,
            "preview": preview_text,
        })

    return new_articles

# Генерация IV-ссылки
def build_instant_view_url(link):
    return f"https://t.me/iv?url={link}&rhash={IV_HASH}"

# Отправка поста в Telegram

def post_to_telegram(title, iv_link, preview):
    # Формируем caption без лишнего отступа
    caption = f"<b>{title}</b>\n\n{preview}<a href=\"{iv_link}\">\u200b</a>"

    if len(caption) > MAX_CAPTION_LENGTH:
        preview_cut = preview[:MAX_CAPTION_LENGTH - len(f"<b>{title}</b>\n\n<a href=\"{iv_link}\">\u200b</a>") - 5] + "..."
        caption = f"<b>{title}</b>\n\n{preview_cut}<a href=\"{iv_link}\">\u200b</a>"

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
    if response.status_code == 200:
        print("✅ Пост отправлен успешно")
    else:
        print(f"❌ Ошибка: {response.json()}")

# Основной цикл

def main():
    articles = fetch_articles()
    if not articles:
        print("⚠️ Новых статей нет — завершение скрипта.")
        return

    for idx, article in enumerate(articles):
        iv_link = build_instant_view_url(article["link"])
        post_to_telegram(article["title"], iv_link, article["preview"])
        mark_as_posted(article["link"])

        if idx < len(articles) - 1:
            print(f"⏳ Ждём {POST_DELAY_SECONDS} секунд перед следующим постом...")
            time.sleep(POST_DELAY_SECONDS)

if __name__ == "__main__":
    main()

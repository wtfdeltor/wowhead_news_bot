# noobclub_news_bot (интеграция с Telegram + Instant View)

import feedparser
import requests
import os
from bs4 import BeautifulSoup
import re
import html
import time

# Константы и переменные окружения
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHANNEL = os.getenv("TELEGRAM_CHANNEL")
NOOBCLUB_RSS = "https://www.noob-club.ru/index.php?type=rss;sa=news;action=.xml"
HEADERS = {"User-Agent": "Mozilla/5.0"}

MAX_CAPTION_LENGTH = 1024  # Максимально допустимая длина текста в посте Telegram
IV_HASH = "fed000eccaa3ad"  # Хэш шаблона Instant View
SEEN_LINKS_FILE = "seen_links.txt"  # Файл для хранения уже опубликованных ссылок
POST_DELAY_SECONDS = 15  # Задержка между публикациями
MAX_SEEN_LINKS = 5  # Максимум хранимых ссылок (по количеству доступных в RSS)

def clean_html_preserve_spaces(html_text):
    # Удаляет теги, сохраняя читаемый текст
    soup = BeautifulSoup(html_text, "html.parser")
    for br in soup.find_all("br"):
        br.replace_with("\n")

    for tag in soup.find_all("a"):
        if tag.string:
            tag.replace_with(tag.get_text())

    raw_text = soup.get_text(" ", strip=True)

    # Удаление мусора и лишних кодов
    raw_text = raw_text.replace("quotquot", '')
    raw_text = raw_text.replace("&#039&#039", "'")
    raw_text = raw_text.replace("#039#039", "'")

    text = html.unescape(raw_text)

    text = re.sub(r":cut:", "", text)
    text = re.sub(r"\s+([.,!?;:])", r"\1", text)
    text = re.sub(r"([.,!?;:])(?=\S)", r"\1 ", text)
    text = re.sub(r"\s+", " ", text).strip()

    # Нормализация кавычек и апострофов
    text = text.replace("\u201c", '"').replace("\u201d", '"')
    text = text.replace("\u2018", "'").replace("\u2019", "'")
    text = text.replace("&quot;", '"')
    text = text.replace("&#039;", "'")
    text = text.replace("#039", "'")
    text = re.sub(r"'+", "'", text)
    text = re.sub(r'"{2,}', '"', text)

    return text

def load_seen_links():
    # Загружает уже опубликованные ссылки из файла
    if not os.path.exists(SEEN_LINKS_FILE):
        open(SEEN_LINKS_FILE, "w").close()
        return []
    with open(SEEN_LINKS_FILE, "r") as f:
        return [line.strip() for line in f.readlines() if line.strip()]

def save_seen_links(links):
    # Сохраняет только последние N ссылок в файл
    with open(SEEN_LINKS_FILE, "w") as f:
        f.write("\n".join(links[-MAX_SEEN_LINKS:]) + "\n")

def has_been_posted(link, seen_links):
    return link.strip() in seen_links

def fetch_articles():
    print("🔁 Загружаем RSS-фид Noob Club...")
    try:
        response = requests.get(NOOBCLUB_RSS, headers=HEADERS)
        response.raise_for_status()
    except requests.RequestException as e:
        print(f"❌ Ошибка загрузки RSS: {e}")
        return []

    feed = feedparser.parse(response.content)
    print(f"✅ Найдено записей: {len(feed.entries)}")

    if not feed.entries:
        print("❗ RSS пуст или не распознан")
        return []

    seen_links = load_seen_links()
    new_articles = []

    for entry in reversed(feed.entries):
        if has_been_posted(entry.link, seen_links):
            continue

        # Получаем только первый абзац
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
            "image": None,
        })

    return new_articles

def build_instant_view_url(link):
    return f"https://t.me/iv?url={link}&rhash={IV_HASH}"

def post_to_telegram(title, iv_link, preview, image_url):
    # Ссылка Instant View скрыта с помощью zero-width space и вынесена на отдельную строку для отступа
    invisible_iv_link = f'<br>&#8203;<a href="{iv_link}">&#8203;</a><br>'
    caption = f"<b>{title}</b>\n\n{preview}\n\n{invisible_iv_link}"

    if len(caption) > MAX_CAPTION_LENGTH:
        preview_cut = preview[:MAX_CAPTION_LENGTH - len(f"<b>{title}</b>\n\n{invisible_iv_link}") - 6] + "..."
        caption = f"<b>{title}</b>\n\n{preview_cut}\n\n{invisible_iv_link}"

    try:
        # Используем sendMessage — так Telegram сможет отобразить Instant View
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
    except requests.RequestException as e:
        print(f"❌ Ошибка при отправке: {e}")

def main():
    articles = fetch_articles()
    if not articles:
        print("⚠️ Новых статей нет — завершение скрипта.")
        return

    seen_links = load_seen_links()

    for idx, article in enumerate(articles):
        iv_link = build_instant_view_url(article["link"])
        post_to_telegram(article["title"], iv_link, article["preview"], article["image"])
        seen_links.append(article["link"].strip())
        save_seen_links(seen_links)

        if idx < len(articles) - 1:
            print(f"⏳ Ждём {POST_DELAY_SECONDS} секунд перед следующим постом...")
            time.sleep(POST_DELAY_SECONDS)

if __name__ == "__main__":
    main()

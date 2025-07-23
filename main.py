# wowhead_news_bot_mvp (GitHub Actions Ready Version)

import feedparser
import requests
import openai
import os
from datetime import datetime
from bs4 import BeautifulSoup

# Переменные из GitHub Secrets или .env
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHANNEL = os.getenv("TELEGRAM_CHANNEL")
OPENAI_KEY = os.getenv("OPENAI_API_KEY")
GITHUB_PAGES_URL = os.getenv("PAGES_URL")  # например: https://username.github.io/wow

openai.api_key = OPENAI_KEY

WOWHEAD_RSS = "https://www.wowhead.com/news/rss"
HEADERS = {"User-Agent": "Mozilla/5.0"}


def fetch_latest_article():
    feed = feedparser.parse(WOWHEAD_RSS)
    entry = feed.entries[0]  # Последняя статья
    return {
        "title": entry.title,
        "link": entry.link,
        "published": entry.published,
        "summary": BeautifulSoup(entry.summary, "html.parser").get_text(),
    }


def translate_text(text):
    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": "Переведи следующий текст на русский. Сохрани стиль и термины WoW."},
            {"role": "user", "content": text}
        ]
    )
    return response.choices[0].message.content.strip()


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
    translated_title = translate_text(article["title"])
    translated_summary = translate_text(article["summary"])
    filename = generate_html(translated_title, translated_summary, article["link"])
    full_url = f"{GITHUB_PAGES_URL}/posts/{filename}"
    post_to_telegram(translated_title, full_url, translated_summary)

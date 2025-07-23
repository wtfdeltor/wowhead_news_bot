# noobclub_news_bot (интеграция с Telegram + Telegraph Instant View)

import feedparser
import requests
import os
from bs4 import BeautifulSoup, NavigableString
from datetime import datetime
import re
from telegraph import Telegraph

# Константы и переменные окружения
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHANNEL = os.getenv("TELEGRAM_CHANNEL")
NOOBCLUB_RSS = "https://www.noob-club.ru/index.php?type=rss;sa=news;action=.xml"
HEADERS = {"User-Agent": "Mozilla/5.0"}

MAX_CAPTION_LENGTH = 1024

def clean_html_preserve_spaces(html):
    soup = BeautifulSoup(html, "html.parser")
    for br in soup.find_all("br"):
        br.replace_with("\n")

    for tag in soup.find_all("a"):
        if tag.string:
            tag.replace_with(tag.get_text())

    # Удаление артефактов вроде :cut:
    text = soup.get_text(" ", strip=True)
    text = re.sub(r":cut:", "", text)

    # Пробелы и пунктуация
    text = re.sub(r'\s+([.,!?;:])', r'\1', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def fetch_latest_article(index=0):
    print("🔁 Загружаем RSS-фид Noob Club...")
    response = requests.get(NOOBCLUB_RSS, headers=HEADERS)
    if response.status_code != 200:
        print(f"❌ Ошибка загрузки RSS: {response.status_code}")
        return None

    feed = feedparser.parse(response.content)
    print(f"✅ Найдено записей: {len(feed.entries)}")

    if not feed.entries or index >= len(feed.entries):
        print("❗ RSS пуст или индекс вне диапазона")
        return None

    entry = feed.entries[index]

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

    preview_text = clean_html_preserve_spaces(preview_html)

    # Полный текст статьи
    content_html = str(post_container)

    return {
        "title": entry.title,
        "link": entry.link,
        "published": entry.published,
        "preview": preview_text,
        "image": image_url,
        "full_html": content_html,
    }

def create_telegraph_page(title, html):
    telegraph = Telegraph()
    telegraph.create_account(short_name="noobclubbot")

    allowed_tags = {
        "p", "strong", "em", "u", "a", "ul", "ol", "li",
        "blockquote", "code", "pre", "h3", "h4", "figure", "figcaption", "br", "img"
    }

    content = BeautifulSoup(html, "html.parser")

    for tag in content.find_all(True):
        if tag.name == "img" and ("1x1.gif" in tag.get("src", "") or "blank.gif" in tag.get("src", "")):
            tag.decompose()
            continue

        if tag.name == "img":
            figure = content.new_tag("figure")
            figcaption = content.new_tag("figcaption")
            figcaption.string = tag.get("alt", "")
            tag.wrap(figure)
            figure.append(figcaption)

        elif tag.name == "iframe" or tag.name == "video":
            src = tag.get("src") or tag.get("data-src")
            if src:
                link_tag = content.new_tag("a", href=src)
                link_tag.string = "Смотреть видео"
                tag.replace_with(link_tag)
            else:
                tag.decompose()

        elif tag.name == "div" and tag.get("class") == ["bbc_standard_quote"]:
            tag.name = "blockquote"

        elif tag.name in ["div", "span"]:
            tag.name = "p"

        elif tag.name not in allowed_tags:
            tag.unwrap()

        tag.attrs = {k: v for k, v in tag.attrs.items() if k in ("href", "src", "alt")}

    response = telegraph.create_page(
        title=title,
        html_content=str(content),
        author_name="Noob Club"
    )
    return f"https://telegra.ph/{response['path']}"

def post_to_telegram(title, iv_link, preview, image_url):
    caption = f"<b>{title}</b>\n\n{preview}\n\n<a href='{iv_link}'>Читать полностью</a>"
    if len(caption) > MAX_CAPTION_LENGTH:
        preview_cut = preview[:MAX_CAPTION_LENGTH - len(f"<b>{title}</b>\n\n<a href='{iv_link}'>Читать полностью</a>") - 3] + "..."
        caption = f"<b>{title}</b>\n\n{preview_cut}\n\n<a href='{iv_link}'>Читать полностью</a>"

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

    iv_link = create_telegraph_page(article["title"], article["full_html"])
    post_to_telegram(article["title"], iv_link, article["preview"], article["image"])

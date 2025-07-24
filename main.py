import feedparser
import requests
import os
from bs4 import BeautifulSoup
from datetime import datetime
import re
import html
import time
import yaml

# Константы и переменные окружения
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHANNEL = os.getenv("TELEGRAM_CHANNEL")
NOOBCLUB_RSS = "https://www.noob-club.ru/rss2.xml"
HEADERS = {"User-Agent": "Mozilla/5.0"}

MAX_CAPTION_LENGTH = 1024
IV_HASH = "fed000eccaa3ad"
SEEN_LINKS_FILE = "seen_links.txt"
POST_DELAY_SECONDS = 5
GLOSSARY_FILE = "tags_glossary.yaml"

# Загрузка YAML-глоссария
def load_glossary():
    if not os.path.exists(GLOSSARY_FILE):
        return {"categories": {}, "keywords": {}}
    with open(GLOSSARY_FILE, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

glossary = load_glossary()

# Парсинг description из HTML

def fetch_meta_description(link):
    try:
        res = requests.get(link, headers=HEADERS, timeout=10)
        if res.status_code != 200:
            return ""
        soup = BeautifulSoup(res.text, "html.parser")
        meta = soup.find("meta", {"name": "description"})
        return meta["content"] if meta and meta.has_attr("content") else ""
    except Exception as e:
        print(f"Ошибка при загрузке description: {e}")
        return ""

# Извлечение тегов только по description

def extract_tags_from_description(desc):
    tags = []
    desc_lower = desc.lower()

    # Категория (первая и единственная), строгий приоритет
    category_matched = None
    for cat, keywords in glossary.get("categories", {}).items():
        for word in keywords:
            if re.search(rf"\b{re.escape(word.lower())}\b", desc_lower):
                category_matched = f"#{cat}"
                break
        if category_matched:
            break

    if category_matched:
        tags.append(category_matched)

    # Остальные теги по ключевым словам
    keyword_hits = []
    for tag, patterns in glossary.get("keywords", {}).items():
        for pat in patterns:
            if re.search(pat, desc_lower, re.IGNORECASE):
                keyword_hits.append(tag)
                break

    tags += keyword_hits[:4]  # максимум 4 доп. тега
    return tags

# Очистка HTML превью

def extract_preview(summary_html):
    match = re.search(r"(.*?)(<a\s+href=[^>]+?>Читать далее</a>)", summary_html, re.DOTALL)
    return match.group(1) if match else summary_html

def clean_html_preserve_spaces(html_text):
    soup = BeautifulSoup(html_text, "html.parser")
    for br in soup.find_all("br"):
        br.replace_with("\n")
    for tag in soup.find_all("a"):
        tag.replace_with(tag.get_text())
    raw_text = soup.get_text(" ", strip=True)
    raw_text = raw_text.replace("quotquot", '').replace("&#039&#039", "'").replace("#039#039", "'")
    text = html.unescape(raw_text)
    text = re.sub(r":cut:", "", text)
    text = re.sub(r"\s+([.,!?;:])", r"\1", text)
    text = re.sub(r"([.,!?;:])(?=\S)", r"\1 ", text)
    text = re.sub(r"\s+", " ", text).strip()
    def fix_quotes_spacing(t):
        t = re.sub(r'(\s?)"(\S.*?)"(?=\s|[.,!?;:]|$)', r' "\2"', t)
        t = re.sub(r'\s+"', ' "', t)
        t = re.sub(r'"\s+', '" ', t)
        return re.sub(r'\s{2,}', ' ', t).strip()
    return fix_quotes_spacing(text)

# Проверка и сохранение ссылок

def has_been_posted(link):
    if not os.path.exists(SEEN_LINKS_FILE):
        return False
    with open(SEEN_LINKS_FILE, "r") as f:
        return link in f.read()

def mark_as_posted(link):
    with open(SEEN_LINKS_FILE, "a") as f:
        f.write(link + "\n")

# Загрузка статей

def fetch_articles():
    print("\U0001F501 Загружаем RSS-фид Noob Club...")
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
        summary_html = entry.summary
        preview_html = extract_preview(summary_html)
        preview_text = clean_html_preserve_spaces(preview_html)
        description_text = fetch_meta_description(entry.link)
        tags = extract_tags_from_description(description_text)
        new_articles.append({
            "title": entry.title,
            "link": entry.link,
            "published": entry.published,
            "preview": preview_text,
            "tags": tags,
        })
    return new_articles

# Instant View-ссылка

def build_instant_view_url(link):
    return f"https://t.me/iv?url={link}&rhash={IV_HASH}"

# Публикация в Telegram

def post_to_telegram(title, iv_link, preview, tags):
    tags_line = " ".join(tags)
    hidden_link = f"<a href=\"{iv_link}\">\u200b</a>"
    caption = f"<b>{title}</b>\n\n{preview}\n{tags_line} {hidden_link}"
    if len(caption) > MAX_CAPTION_LENGTH:
        cut_len = MAX_CAPTION_LENGTH - len(f"<b>{title}</b>\n\n{tags_line} {hidden_link}") - 5
        preview_cut = preview[:cut_len] + "..."
        caption = f"<b>{title}</b>\n\n{preview_cut}\n{tags_line} {hidden_link}"

    response = requests.post(
        f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
        data={
            "chat_id": TELEGRAM_CHANNEL,
            "text": caption,
            "parse_mode": "HTML",
            "disable_web_page_preview": False,
        },
    )
    print(f"\U0001F4E4 Статус отправки в Telegram: {response.status_code}")
    if response.status_code == 200:
        print("✅ Пост отправлен успешно")
    else:
        print(f"❌ Ошибка: {response.json()}")

# Главная функция

def main():
    articles = fetch_articles()
    if not articles:
        print("⚠️ Новых статей нет — завершение скрипта.")
        return
    for idx, article in enumerate(articles):
        iv_link = build_instant_view_url(article["link"])
        post_to_telegram(article["title"], iv_link, article["preview"], article["tags"])
        mark_as_posted(article["link"])
        if idx < len(articles) - 1:
            print(f"⏳ Ждём {POST_DELAY_SECONDS} секунд перед следующим постом...")
            time.sleep(POST_DELAY_SECONDS)

if __name__ == "__main__":
    main()

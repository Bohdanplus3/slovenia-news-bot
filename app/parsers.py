from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup

from app.fetcher import get_html

SOURCES = {
    "n1info": "https://n1info.si/",
    "rtvslo": "https://www.rtvslo.si/",
    "ljubljanainfo": "https://ljubljanainfo.com/",
    "zurnal24": "https://www.zurnal24.si/",
}


def normalize_url(url: str) -> str:
    parsed = urlparse(url)
    clean = parsed._replace(query="", fragment="")
    return clean.geturl().rstrip("/")


def extract_links_from_homepage(source_name: str, base_url: str) -> list[dict]:
    html = get_html(base_url)
    soup = BeautifulSoup(html, "html.parser")
    results = []

    for a in soup.select("a[href]"):
        href = a.get("href", "").strip()
        title = a.get_text(" ", strip=True)

        if not href:
            continue

        full_url = normalize_url(urljoin(base_url, href))

        if len(title) < 15:
            continue

        if not full_url.startswith("http"):
            continue

        if source_name == "n1info" and "n1info.si" not in full_url:
            continue
        if source_name == "rtvslo" and "rtvslo.si" not in full_url:
            continue
        if source_name == "ljubljanainfo" and "ljubljanainfo.com" not in full_url:
            continue
        if source_name == "zurnal24" and "zurnal24.si" not in full_url:
            continue

        results.append({
            "source": source_name,
            "url": full_url,
            "title": title
        })

    unique = []
    seen = set()
    for item in results:
        if item["url"] not in seen:
            seen.add(item["url"])
            unique.append(item)

    return unique[:40]


def extract_article(article_url: str) -> dict | None:
    try:
        html = get_html(article_url)
    except Exception as e:
        print(f"Ошибка загрузки статьи {article_url}: {e}")
        return None

    soup = BeautifulSoup(html, "html.parser")

    title = None
    image_url = None
    published_at = None
    text_parts = []

    og_title = soup.find("meta", attrs={"property": "og:title"})
    if og_title and og_title.get("content"):
        title = og_title.get("content").strip()

    if not title and soup.title and soup.title.text.strip():
        title = soup.title.text.strip()

    og_image = soup.find("meta", attrs={"property": "og:image"})
    if og_image and og_image.get("content"):
        image_url = urljoin(article_url, og_image.get("content").strip())

    possible_date_tags = [
        soup.find("meta", attrs={"property": "article:published_time"}),
        soup.find("meta", attrs={"name": "publish-date"}),
        soup.find("meta", attrs={"name": "date"}),
        soup.find("time"),
    ]

    for tag in possible_date_tags:
        if not tag:
            continue
        if tag.get("content"):
            published_at = tag.get("content").strip()
            break
        if tag.get("datetime"):
            published_at = tag.get("datetime").strip()
            break
        txt = tag.get_text(" ", strip=True)
        if txt:
            published_at = txt
            break

    article_block = soup.find("article")

    if not article_block:
        selectors = [
            ".entry-content",
            ".article__content",
            ".post-content",
            ".article-body",
            ".node-content",
            ".content-main",
        ]
        for sel in selectors:
            article_block = soup.select_one(sel)
            if article_block:
                break

    if article_block:
        paragraphs = article_block.find_all("p")
    else:
        paragraphs = soup.find_all("p")

    for p in paragraphs:
        txt = p.get_text(" ", strip=True)

        if not txt:
            continue

        if len(txt) < 40:
            continue

        lower_txt = txt.lower()

        bad_starts = [
            "preberite še",
            "preberi še",
            "sorodne novice",
            "oglas",
            "foto:",
            "video:",
        ]

        if any(lower_txt.startswith(x) for x in bad_starts):
            continue

        text_parts.append(txt)

    raw_text = "\n".join(text_parts).strip()

    if not raw_text or len(raw_text) < 400:
        fallback = soup.get_text(" ", strip=True)
        raw_text = fallback[:15000]

    if not title:
        title = article_url

    return {
        "url": article_url,
        "title": title,
        "published_at": published_at,
        "image_url": image_url,
        "raw_text": raw_text,
    }
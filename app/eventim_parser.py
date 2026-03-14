"""
Парсер мероприятий с eventim.si.

Eventim.si рендерит контент через JS, поэтому обычный requests/httpx
часто возвращает пустую страницу. Используем несколько стратегий:
1. Прямой парсинг HTML (иногда работает при правильном User-Agent)
2. Парсинг JSON из <script type="application/ld+json"> (структурированные данные)
3. Fallback — ljubljanainfo.com раздел events (чистый HTML)
"""

import json
import re
from datetime import datetime, timedelta
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from app.fetcher import get_html

EVENTIM_BASE = "https://www.eventim.si"

# Страницы поиска eventim
EVENTIM_URLS = [
    f"{EVENTIM_BASE}/si/search/?affiliate=SIT&in=eventseries&fun=srqb",
]

# Fallback источник мероприятий (чистый HTML)
FALLBACK_EVENTS_URLS = [
    "https://www.ljubljana.si/sl/moja-ljubljana/prireditve/",
    "https://ljubljanainfo.com/events/",
]

BIG_EVENT_THRESHOLD_DAYS = 180  # "крупные события" — за полгода


def _parse_date(s: str) -> datetime | None:
    if not s:
        return None
    s = s.strip()
    for fmt in ["%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M", "%Y-%m-%d",
                "%d.%m.%Y", "%d. %m. %Y", "%d %b %Y"]:
        try:
            return datetime.strptime(s[:len(fmt)], fmt)
        except ValueError:
            continue
    return None


def _extract_json_ld(soup: BeautifulSoup) -> list[dict]:
    """Достаём мероприятия из JSON-LD разметки (Schema.org Event)."""
    events = []
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string or "")
            items = data if isinstance(data, list) else [data]
            for item in items:
                if item.get("@type") not in ("Event", "MusicEvent",
                                              "TheaterEvent", "SportsEvent"):
                    continue
                name = item.get("name", "")
                url = item.get("url", "")
                start = _parse_date(item.get("startDate", ""))
                location = item.get("location", {})
                if isinstance(location, dict):
                    venue = location.get("name", "")
                else:
                    venue = str(location)
                if name:
                    events.append({
                        "name": name,
                        "url": url or EVENTIM_BASE,
                        "event_date": start,
                        "venue": venue,
                        "is_big": False,
                    })
        except Exception:
            continue
    return events


def _scrape_eventim() -> list[dict]:
    """Пытаемся парсить eventim.si."""
    events = []
    seen = set()

    for url in EVENTIM_URLS:
        try:
            html = get_html(url)
        except Exception as e:
            print(f"  Eventim недоступен ({e})")
            continue

        soup = BeautifulSoup(html, "html.parser")

        # Стратегия 1: JSON-LD
        json_events = _extract_json_ld(soup)
        if json_events:
            print(f"  Eventim JSON-LD: {len(json_events)} событий")
            for ev in json_events:
                if ev["url"] not in seen:
                    seen.add(ev["url"])
                    events.append(ev)
            continue

        # Стратегия 2: HTML карточки
        cards = soup.select(
            "[class*='event'], [class*='product'], [class*='show'], "
            "[class*='listing'], article, li.result"
        )
        print(f"  Eventim HTML карточки: {len(cards)}")

        for card in cards:
            try:
                name_el = card.select_one(
                    "h1, h2, h3, h4, "
                    "[class*='title'], [class*='name'], [class*='heading']"
                )
                if not name_el:
                    continue
                name = name_el.get_text(" ", strip=True)
                if len(name) < 3:
                    continue

                link_el = card.select_one("a[href]")
                href = link_el.get("href", "") if link_el else ""
                full_url = urljoin(EVENTIM_BASE, href) if href else EVENTIM_BASE

                if full_url in seen:
                    continue
                seen.add(full_url)

                date_el = card.select_one(
                    "time, [class*='date'], [class*='when'], [itemprop='startDate']"
                )
                date_str = ""
                event_date = None
                if date_el:
                    date_str = (date_el.get("datetime")
                                or date_el.get("content")
                                or date_el.get_text(" ", strip=True))
                    event_date = _parse_date(date_str)

                venue_el = card.select_one(
                    "[class*='venue'], [class*='location'], [class*='place'], "
                    "[itemprop='location']"
                )
                venue = venue_el.get_text(" ", strip=True) if venue_el else ""

                events.append({
                    "name": name,
                    "url": full_url,
                    "event_date": event_date,
                    "venue": venue,
                    "is_big": False,
                })
            except Exception:
                continue

    return events


def _scrape_fallback() -> list[dict]:
    """Fallback: парсим Ljubljana.si / ljubljanainfo.com."""
    events = []
    seen = set()

    for url in FALLBACK_EVENTS_URLS:
        try:
            html = get_html(url)
        except Exception as e:
            print(f"  Fallback {url} недоступен: {e}")
            continue

        soup = BeautifulSoup(html, "html.parser")

        # JSON-LD сначала
        json_events = _extract_json_ld(soup)
        for ev in json_events:
            if ev["url"] not in seen:
                seen.add(ev["url"])
                events.append(ev)

        # HTML карточки
        for card in soup.select("article, .event, .event-item, li.post"):
            try:
                name_el = card.select_one("h1,h2,h3,h4,a")
                if not name_el:
                    continue
                name = name_el.get_text(" ", strip=True)
                if len(name) < 5:
                    continue

                link_el = card.select_one("a[href]")
                href = link_el.get("href", "") if link_el else ""
                full_url = urljoin(url, href) if href else url

                if full_url in seen:
                    continue
                seen.add(full_url)

                date_el = card.select_one(
                    "time, [class*='date'], [class*='datum']"
                )
                event_date = None
                if date_el:
                    ds = (date_el.get("datetime")
                          or date_el.get_text(" ", strip=True))
                    event_date = _parse_date(ds)

                venue_el = card.select_one("[class*='venue'],[class*='locat']")
                venue = venue_el.get_text(" ", strip=True) if venue_el else ""

                events.append({
                    "name": name,
                    "url": full_url,
                    "event_date": event_date,
                    "venue": venue,
                    "is_big": False,
                })
            except Exception:
                continue

    return events


def build_eventim_digest() -> str:
    today = datetime.now()
    # Ближайшая неделя до следующей среды
    days_to_wed = (2 - today.weekday()) % 7 or 7
    week_end = today + timedelta(days=days_to_wed)
    far_end = today + timedelta(days=BIG_EVENT_THRESHOLD_DAYS)

    print("Собираю мероприятия...")

    # Пробуем eventim, потом fallback
    events = _scrape_eventim()
    if not events:
        print("  Eventim пуст, пробую fallback источники...")
        events = _scrape_fallback()

    if not events:
        print("  Мероприятий не найдено")
        return ""

    print(f"  Всего событий до фильтрации: {len(events)}")

    # Делим на: эта неделя / крупные за полгода / без даты
    week_events = []
    big_events = []
    no_date_events = []

    for ev in events:
        d = ev.get("event_date")
        if d is None:
            no_date_events.append(ev)
        elif today.date() <= d.date() <= week_end.date():
            week_events.append(ev)
        elif week_end.date() < d.date() <= far_end.date():
            big_events.append(ev)

    week_events.sort(key=lambda x: x["event_date"])
    big_events.sort(key=lambda x: x["event_date"])

    if not week_events and not big_events and not no_date_events:
        return ""

    lines = []

    # ── Ближайшая неделя ─────────────────────────────────────────────────────
    show_week = week_events or no_date_events[:5]
    if show_week:
        lines.append(
            f"🎭 <b>Мероприятия в Словении: "
            f"{today.strftime('%d.%m')} – {week_end.strftime('%d.%m.%Y')}</b>"
        )
        lines.append("")
        for ev in show_week[:15]:
            d = ev.get("event_date")
            date_str = d.strftime("%d.%m") if d else "📅 дата уточняется"
            venue = f" • {ev['venue']}" if ev.get("venue") else ""
            name = ev["name"][:80]
            lines.append(f"📌 <b>{date_str}</b>{venue}")
            lines.append(f'<a href="{ev["url"]}">{name}</a>')
            lines.append("")

    # ── Крупные события за полгода ───────────────────────────────────────────
    if big_events:
        lines.append("🌟 <b>Крупные события — ближайшие полгода</b>")
        lines.append("")
        for ev in big_events[:10]:
            d = ev["event_date"]
            date_str = d.strftime("%d.%m.%Y")
            venue = f" • {ev['venue']}" if ev.get("venue") else ""
            name = ev["name"][:80]
            lines.append(f"📌 <b>{date_str}</b>{venue}")
            lines.append(f'<a href="{ev["url"]}">{name}</a>')
            lines.append("")

    lines.append(f"🔗 Все мероприятия: {EVENTIM_BASE}")
    return "\n".join(lines).strip()

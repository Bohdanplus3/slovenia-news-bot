import sqlite3
from app.config import DB_PATH

ALL_CATEGORIES = {
    "politics":  "🏛 Политика / власть",
    "crime":     "🚔 Происшествия / криминал",
    "economy":   "💼 Экономика / бизнес",
    "transport": "🚧 Транспорт / инфраструктура",
    "society":   "👥 Общество / социалка",
    "ecology":   "🌿 Экология / природа",
    "health":    "🏥 Медицина / здоровье",
    "education": "🎓 Образование",
}

# Маппинг: что AI может вернуть → наш ключ
CATEGORY_MAP = {
    "политик": "politics", "власт": "politics", "правительств": "politics",
    "парламент": "politics", "выбор": "politics", "партия": "politics",
    "происшестви": "crime", "криминал": "crime", "полиция": "crime",
    "суд": "crime", "арест": "crime", "преступ": "crime", "убийств": "crime",
    "авария": "crime", "пожар": "crime", "кража": "crime",
    "эконом": "economy", "бизнес": "economy", "рынок": "economy",
    "финанс": "economy", "компани": "economy", "налог": "economy",
    "зарплат": "economy", "цен": "economy", "инфляц": "economy",
    "транспорт": "transport", "инфраструктур": "transport", "дорог": "transport",
    "автобус": "transport", "поезд": "transport", "аэропорт": "transport",
    "строительств": "transport",
    "общество": "society", "социал": "society", "жильё": "society",
    "жилье": "society", "миграц": "society", "беженц": "society",
    "экологи": "ecology", "природ": "ecology", "климат": "ecology",
    "загрязнен": "ecology", "заповедн": "ecology",
    "медицин": "health", "здоровь": "health", "больниц": "health",
    "вакцин": "health", "лечени": "health", "врач": "health",
    "образовани": "education", "школ": "education", "университет": "education",
    "студент": "education",
}


def map_category(ai_category: str) -> str | None:
    """Маппит категорию от AI на наш ключ. Возвращает None если не распознана."""
    low = ai_category.lower()
    for word, key in CATEGORY_MAP.items():
        if word in low:
            return key
    return None


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS articles (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        url TEXT UNIQUE,
        source TEXT,
        original_title TEXT,
        published_at TEXT,
        image_url TEXT,
        raw_text TEXT,
        sent INTEGER DEFAULT 0,
        category TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT
    )
    """)

    # По умолчанию — все категории включены, бот не на паузе
    defaults = {
        "active_categories": ",".join(ALL_CATEGORIES.keys()),
        "paused": "0",
    }
    for key, val in defaults.items():
        cur.execute("SELECT 1 FROM settings WHERE key=?", (key,))
        if not cur.fetchone():
            cur.execute("INSERT INTO settings (key,value) VALUES (?,?)", (key, val))

    conn.commit()
    conn.close()


def get_setting(key: str) -> str:
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT value FROM settings WHERE key=?", (key,))
    row = cur.fetchone()
    conn.close()
    return row["value"] if row else ""


def set_setting(key: str, value: str):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("INSERT OR REPLACE INTO settings (key,value) VALUES (?,?)", (key, value))
    conn.commit()
    conn.close()


def get_active_categories() -> set:
    val = get_setting("active_categories")
    if not val:
        return set(ALL_CATEGORIES.keys())
    return set(val.split(","))


def set_active_categories(categories: set):
    set_setting("active_categories", ",".join(sorted(categories)))


def is_paused() -> bool:
    return get_setting("paused") == "1"


def set_paused(paused: bool):
    set_setting("paused", "1" if paused else "0")


def article_exists(url: str) -> bool:
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM articles WHERE url=?", (url,))
    row = cur.fetchone()
    conn.close()
    return row is not None


def save_article(url, source, original_title, published_at, image_url, raw_text,
                 sent=False, category=""):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
    INSERT OR IGNORE INTO articles
        (url, source, original_title, published_at, image_url, raw_text, sent, category)
    VALUES (?,?,?,?,?,?,?,?)
    """, (url, source, original_title, published_at, image_url, raw_text,
          1 if sent else 0, category))
    conn.commit()
    conn.close()


def get_last_sent(limit: int = 5) -> list:
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
    SELECT original_title, url, source, created_at, category
    FROM articles WHERE sent=1
    ORDER BY created_at DESC LIMIT ?
    """, (limit,))
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


def get_stats() -> dict:
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) as total FROM articles")
    total = cur.fetchone()["total"]
    cur.execute("SELECT COUNT(*) as sent FROM articles WHERE sent=1")
    sent = cur.fetchone()["sent"]
    cur.execute("SELECT source, COUNT(*) as cnt FROM articles WHERE sent=1 GROUP BY source")
    by_source = {r["source"]: r["cnt"] for r in cur.fetchall()}
    conn.close()
    return {"total": total, "sent": sent, "by_source": by_source}


# Обратная совместимость
def mark_article_seen(url, source, original_title, published_at=None,
                      image_url=None, raw_text=""):
    save_article(url, source, original_title, published_at, image_url, raw_text)

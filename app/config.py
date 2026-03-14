import os
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
OWNER_ID = int(os.getenv("OWNER_ID", "0"))
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

CHECK_INTERVAL_MINUTES = int(os.getenv("CHECK_INTERVAL_MINUTES", "60"))
DB_PATH = os.getenv("DB_PATH", "news_bot.db")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")  # gpt-5-mini не существует
REQUEST_TIMEOUT = float(os.getenv("REQUEST_TIMEOUT", "20"))
MAX_ARTICLES_PER_CYCLE = int(os.getenv("MAX_ARTICLES_PER_CYCLE", "10"))
EVENTIM_WEEKDAY = int(os.getenv("EVENTIM_WEEKDAY", "3"))
TZ = os.getenv("TZ", "Europe/Ljubljana")
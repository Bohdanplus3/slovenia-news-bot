import threading
from app.scheduler import start_scheduler
from app.bot import run_bot

if __name__ == "__main__":
    # Telegram-бот (команды /filters, /status) — в отдельном потоке
    bot_thread = threading.Thread(target=run_bot, daemon=True)
    bot_thread.start()

    # Scheduler (сбор новостей) — в главном потоке
    start_scheduler()

import time
from datetime import datetime
from apscheduler.schedulers.blocking import BlockingScheduler

from app.config import CHECK_INTERVAL_MINUTES, TZ, MAX_ARTICLES_PER_CYCLE, EVENTIM_WEEKDAY
from app.database import (
    init_db, article_exists, save_article,
    get_active_categories, ALL_CATEGORIES, map_category,
    is_paused,
)
from app.parsers import SOURCES, extract_links_from_homepage, extract_article
from app.filters import probably_about_slovenia
from app.summarizer import build_post
from app.telegram_sender import send_news_to_owner, send_text_to_owner, send_test_message
from app.eventim_parser import build_eventim_digest
from app.bot import consume_trigger


def process_news_cycle():
    # Пауза — пропускаем цикл
    if is_paused():
        print(f"[{datetime.now().strftime('%H:%M')}] Бот на паузе, цикл пропущен")
        return

    print(f"\n=== Цикл [{datetime.now().strftime('%Y-%m-%d %H:%M')}] ===")

    active_categories = get_active_categories()
    all_cats = set(ALL_CATEGORIES.keys())

    if active_categories == all_cats:
        print("Категории: все")
    else:
        labels = [ALL_CATEGORIES[k] for k in ALL_CATEGORIES if k in active_categories]
        print(f"Категории: {', '.join(labels)}")

    articles_sent = 0

    for source_name, base_url in SOURCES.items():
        if articles_sent >= MAX_ARTICLES_PER_CYCLE:
            print(f"Лимит {MAX_ARTICLES_PER_CYCLE} статей достигнут")
            break

        print(f"\n[{source_name}]")

        try:
            previews = extract_links_from_homepage(source_name, base_url)
            print(f"  Ссылок найдено: {len(previews)}")
        except Exception as e:
            print(f"  Ошибка загрузки главной: {e}")
            continue

        # Небольшая задержка между источниками чтобы не банили
        time.sleep(1)

        new_count = 0
        for item in previews:
            if articles_sent >= MAX_ARTICLES_PER_CYCLE:
                break

            url = item["url"]

            if article_exists(url):
                continue

            new_count += 1
            print(f"  Новая: {url}")

            # Задержка между запросами к одному сайту
            time.sleep(0.5)

            try:
                article = extract_article(url)
            except Exception as e:
                print(f"    → ошибка загрузки: {e}")
                save_article(url, source_name, item.get("title", ""), None, None, "")
                continue

            if not article:
                save_article(url, source_name, item.get("title", ""), None, None, "")
                continue

            article_text = article["raw_text"]

            if not article_text or len(article_text.strip()) < 300:
                print("    → мало текста, пропуск")
                save_article(url, source_name, article.get("title", ""), None, None, "")
                continue

            if not probably_about_slovenia(article["title"], article_text, url):
                print("    → не Словения, пропуск")
                save_article(url, source_name, article.get("title", ""), None, None, "")
                continue

            print("    → AI...")

            try:
                ai_result = build_post(
                    title=article["title"],
                    source=source_name,
                    url=url,
                    text=article_text,
                )
            except Exception as e:
                print(f"    → ошибка AI: {e}")
                continue

            if not ai_result.get("is_relevant"):
                print("    → AI: нерелевантно")
                save_article(url, source_name, article.get("title", ""), None, None, "")
                continue

            # Проверяем категорию
            ai_cat_raw = ai_result.get("category", "")
            matched_key = map_category(ai_cat_raw)

            if matched_key and matched_key not in active_categories:
                print(f"    → категория '{ai_cat_raw}' выключена, пропуск")
                save_article(url, source_name, article.get("title", ""),
                             None, None, "", sent=False, category=matched_key)
                continue

            print(f"    → релевантно! [{ai_cat_raw}] score={ai_result.get('importance_score')}")

            article_data = {
                "source": source_name,
                "title": article["title"],
                "url": url,
                "image_url": article.get("image_url"),
            }

            try:
                send_news_to_owner(article_data, ai_result)
                articles_sent += 1
                print("    → отправлено ✓")
            except Exception as e:
                print(f"    → ошибка отправки: {e}")
                continue

            save_article(
                url=url,
                source=source_name,
                original_title=article["title"],
                published_at=article.get("published_at"),
                image_url=article.get("image_url"),
                raw_text=article_text,
                sent=True,
                category=matched_key or ai_cat_raw,
            )

        if new_count == 0:
            print("  Новых нет")

    print(f"\n=== Готово. Отправлено: {articles_sent} ===\n")


def process_eventim_digest():
    if is_paused():
        return
    print(f"=== Eventim [{datetime.now().strftime('%Y-%m-%d %H:%M')}] ===")
    try:
        digest = build_eventim_digest()
    except Exception as e:
        print(f"Ошибка eventim: {e}")
        return
    if not digest:
        print("Eventim: пусто")
        return
    try:
        send_text_to_owner(digest)
        print("Eventim отправлен ✓")
    except Exception as e:
        print(f"Ошибка отправки eventim: {e}")


def check_immediate_trigger():
    """Проверяет флаг от кнопки /test — запускает цикл немедленно."""
    if consume_trigger():
        print("Принудительный запуск цикла (кнопка Тест)")
        process_news_cycle()


def start_scheduler():
    init_db()

    try:
        send_test_message()
        print("Старт — тестовое сообщение отправлено")
    except Exception as e:
        print(f"Не удалось отправить тест: {e}")

    scheduler = BlockingScheduler(timezone=TZ)

    # Основной цикл новостей
    scheduler.add_job(
        process_news_cycle,
        "interval",
        minutes=CHECK_INTERVAL_MINUTES,
        next_run_time=datetime.now(),
        id="news_cycle",
    )

    # Проверка флага "запустить сейчас" — каждые 5 секунд
    scheduler.add_job(
        check_immediate_trigger,
        "interval",
        seconds=5,
        id="trigger_check",
    )

    # Eventim — каждый четверг в 10:00
    scheduler.add_job(
        process_eventim_digest,
        "cron",
        day_of_week=EVENTIM_WEEKDAY,
        hour=10,
        minute=0,
        id="eventim_digest",
    )

    print(f"Scheduler: новости каждые {CHECK_INTERVAL_MINUTES} мин | Eventim по чт 10:00")
    scheduler.start()

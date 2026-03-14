import httpx

from app.config import TELEGRAM_BOT_TOKEN, OWNER_ID

API_URL = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"


def send_test_message():
    response = httpx.post(
        f"{API_URL}/sendMessage",
        data={
            "chat_id": OWNER_ID,
            "text": "✅ Бот запущен и может отправлять сообщения.",
            "parse_mode": "HTML",
        },
        timeout=20
    )
    response.raise_for_status()


def send_news_to_owner(article: dict, ai_result: dict):
    post_text = (ai_result.get("post_ru") or "").strip()
    image_url = article.get("image_url")

    if not post_text:
        print("Пустой post_ru, отправка пропущена")
        return

    # Убираем дублирующиеся пустые строки
    lines = post_text.splitlines()
    cleaned_lines = []
    prev_empty = False
    for line in lines:
        is_empty = line.strip() == ""
        if is_empty and prev_empty:
            continue
        cleaned_lines.append(line)
        prev_empty = is_empty

    post_text = "\n".join(cleaned_lines).strip()

    if image_url:
        try:
            # Caption у Telegram максимум 1024 символа
            caption = post_text
            if len(caption) > 1024:
                # Обрезаем до ближайшего конца абзаца
                caption = caption[:1000]
                for sep in ["\n\n", "\n", ". "]:
                    idx = caption.rfind(sep)
                    if idx > 300:
                        caption = caption[:idx].rstrip()
                        break
                caption += "\n\n<i>(сообщение обрезано)</i>"

            response = httpx.post(
                f"{API_URL}/sendPhoto",
                data={
                    "chat_id": OWNER_ID,
                    "photo": image_url,
                    "caption": caption,
                    "parse_mode": "HTML",
                },
                timeout=30
            )
            response.raise_for_status()
            return
        except Exception as e:
            print(f"Ошибка отправки фото ({e}), отправляю текстом")

    # Текстовое сообщение — лимит 4096 символов
    text = post_text
    if len(text) > 4096:
        text = text[:4050].rstrip() + "\n\n<i>(сообщение обрезано)</i>"

    response = httpx.post(
        f"{API_URL}/sendMessage",
        data={
            "chat_id": OWNER_ID,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": "true",
        },
        timeout=30
    )
    response.raise_for_status()


def send_text_to_owner(text: str):
    """Отправить произвольный HTML-текст владельцу."""
    if len(text) > 4096:
        text = text[:4050].rstrip() + "\n\n<i>(сообщение обрезано)</i>"

    response = httpx.post(
        f"{API_URL}/sendMessage",
        data={
            "chat_id": OWNER_ID,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": "true",
        },
        timeout=30
    )
    response.raise_for_status()

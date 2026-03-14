import sqlite3

conn = sqlite3.connect('news_bot.db')

for col, definition in [
    ("sent", "INTEGER DEFAULT 0"),
    ("category", "TEXT DEFAULT ''"),
]:
    try:
        conn.execute(f"ALTER TABLE articles ADD COLUMN {col} {definition}")
        conn.commit()
        print(f"{col} — добавлено")
    except Exception as e:
        if "duplicate column" in str(e).lower():
            print(f"{col} — уже есть")
        else:
            print(f"{col} — ошибка: {e}")

conn.close()
print("Готово!")

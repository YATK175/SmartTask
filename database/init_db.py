
from pathlib import Path
import sqlite3


# Коренева папка проєкту
BASE_DIR = Path(__file__).resolve().parent.parent

# Шляхи до SQL-схеми та бази даних
SCHEMA_PATH = BASE_DIR / "database" / "SmartTask_schema.sql"
DATABASE_PATH = BASE_DIR / "instance" / "smarttask.db"


def initialize_database():
    """Створює таблиці бази даних на основі SQL-схеми."""

    if not SCHEMA_PATH.exists():
        raise FileNotFoundError(
            f"SQL-схему не знайдено: {SCHEMA_PATH}"
        )

    DATABASE_PATH.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    sql_schema = SCHEMA_PATH.read_text(encoding="utf-8")

    with sqlite3.connect(DATABASE_PATH) as connection:
        # Увімкнення контролю зовнішніх ключів
        connection.execute("PRAGMA foreign_keys = ON")

        # Виконання SQL-команд
        connection.executescript(sql_schema)

        # Отримання списку створених таблиць
        tables = connection.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'table'
            AND name NOT LIKE 'sqlite_%'
            ORDER BY name
            """
        ).fetchall()

        # Перевірка цілісності БД
        integrity = connection.execute(
            "PRAGMA integrity_check"
        ).fetchone()[0]

    print("\n=== SMARTTASK DATABASE ===")
    print(f"Database: {DATABASE_PATH}")
    print("\nCreated tables:")

    for table in tables:
        print(f"[OK] {table[0]}")

    print(f"\nIntegrity check: {integrity}")
    print("\nDatabase initialization completed!")


if __name__ == "__main__":
    initialize_database()

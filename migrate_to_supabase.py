import sqlite3
import os
import psycopg2
from dotenv import load_dotenv

# ============================================================
# LOAD ENVIRONMENT
# ============================================================

load_dotenv()

DATABASE_URL = os.environ.get("DATABASE_URL")

if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL is missing from .env")


# ============================================================
# CONNECT TO SQLITE
# ============================================================

sqlite_db = sqlite3.connect("database.db")
sqlite_db.row_factory = sqlite3.Row


# ============================================================
# CONNECT TO SUPABASE POSTGRESQL
# ============================================================

postgres_db = psycopg2.connect(
    DATABASE_URL
)

postgres_cursor = postgres_db.cursor()


# ============================================================
# TABLE LIST
# ============================================================

TABLES = [
    "contact_messages",
    "events",
    "gallery",
    "hero",
    "ministers",
    "newsletter_subscribers",
    "push_subscriptions",
    "site_settings",
    "volunteer_applications",
    "first_image",
]


# ============================================================
# CHECK TABLE EXISTS
# ============================================================

def sqlite_table_exists(table_name):
    result = sqlite_db.execute(
        """
        SELECT name
        FROM sqlite_master
        WHERE type = 'table'
        AND name = ?
        """,
        (table_name,)
    ).fetchone()

    return result is not None


# ============================================================
# GET SQLITE COLUMNS
# ============================================================

def get_sqlite_columns(table_name):
    rows = sqlite_db.execute(
        f'PRAGMA table_info("{table_name}")'
    ).fetchall()

    return [row["name"] for row in rows]


# ============================================================
# GET POSTGRES COLUMNS
# ============================================================

def get_postgres_columns(table_name):
    postgres_cursor.execute(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = 'public'
        AND table_name = %s
        ORDER BY ordinal_position
        """,
        (table_name,)
    )

    return [row[0] for row in postgres_cursor.fetchall()]


# ============================================================
# MIGRATE ONE TABLE
# ============================================================

def migrate_table(table_name):

    print()
    print("-" * 60)
    print(f"Migrating: {table_name}")
    print("-" * 60)

    # Check SQLite table
    if not sqlite_table_exists(table_name):
        print("SQLite table does not exist. Skipping.")
        return

    # Get columns
    sqlite_columns = get_sqlite_columns(table_name)
    postgres_columns = get_postgres_columns(table_name)

    if not postgres_columns:
        print("PostgreSQL table does not exist. Skipping.")
        return

    # Only use columns that exist in BOTH databases
    common_columns = [
        column
        for column in sqlite_columns
        if column in postgres_columns
    ]

    if not common_columns:
        print("No matching columns found. Skipping.")
        return

    print("Columns:")
    print(", ".join(common_columns))

    # Read SQLite rows
    column_sql = ", ".join(
        f'"{column}"'
        for column in common_columns
    )

    rows = sqlite_db.execute(
        f'SELECT {column_sql} FROM "{table_name}"'
    ).fetchall()

    print(f"SQLite records found: {len(rows)}")

    if not rows:
        print("Nothing to migrate.")
        return

    # PostgreSQL column names
    postgres_column_sql = ", ".join(
        f'"{column}"'
        for column in common_columns
    )

    placeholders = ", ".join(
        ["%s"] * len(common_columns)
    )

    # Insert
    insert_sql = f"""
        INSERT INTO "{table_name}"
        ({postgres_column_sql})
        VALUES ({placeholders})
    """

    migrated = 0

    for row in rows:

        values = [
            row[column]
            for column in common_columns
        ]

        try:
            postgres_cursor.execute(
                insert_sql,
                values
            )

            migrated += 1

        except Exception as e:

            print(
                f"Could not migrate row: {e}"
            )

            postgres_db.rollback()

            # Re-create cursor after rollback
            postgres_cursor = postgres_db.cursor()

    postgres_db.commit()

    print(
        f"Migrated {migrated} / {len(rows)} record(s)."
    )


# ============================================================
# RUN MIGRATION
# ============================================================

print()
print("=" * 60)
print("SQLITE → SUPABASE MIGRATION")
print("=" * 60)

for table in TABLES:

    try:
        migrate_table(table)

    except Exception as e:

        print()
        print(f"ERROR migrating {table}:")
        print(e)

        postgres_db.rollback()


# ============================================================
# CLOSE DATABASES
# ============================================================

sqlite_db.close()
postgres_cursor.close()
postgres_db.close()

print()
print("=" * 60)
print("MIGRATION FINISHED")
print("=" * 60)
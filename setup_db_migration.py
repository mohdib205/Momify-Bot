"""
setup_db_migration.py

we will this Run ONCE to add the token_usage table to our existing PostgreSQL database:
    python setup_db_migration.py

Sync psycopg2 — same driver as core/logger.py, no asyncpg needed.
"""

import psycopg2
from core.config import DB_URL


def migrate():
    conn = psycopg2.connect(DB_URL)
    cur  = conn.cursor()
    try:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS token_usage (
                id                BIGSERIAL PRIMARY KEY,
                parent_id         TEXT,
                baby_id           TEXT,
                model             TEXT,
                prompt_tokens     INTEGER NOT NULL DEFAULT 0,
                completion_tokens INTEGER NOT NULL DEFAULT 0,
                total_tokens      INTEGER NOT NULL DEFAULT 0,
                mode              TEXT,          -- data | weak | fallback | emergency
                created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
            );

            CREATE INDEX IF NOT EXISTS idx_token_usage_created_at
                ON token_usage (created_at);

            CREATE INDEX IF NOT EXISTS idx_token_usage_parent_id
                ON token_usage (parent_id);
        """)
        conn.commit()
        print("✅ token_usage table ready")
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    migrate()
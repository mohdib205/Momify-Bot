"""
setup_db.py
Run once to create all required tables in PostgreSQL.
Usage: python setup_db.py
"""

import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()

DB_URL = os.environ.get("DB_URL")
if not DB_URL:
    raise ValueError("DB_URL not set in environment / .env file")

conn = psycopg2.connect(DB_URL)
cur  = conn.cursor()

# ── Table 1: chat_logs ──────────────────────────────────────────────────────
cur.execute("""
    CREATE TABLE IF NOT EXISTS chat_logs (
        id               SERIAL PRIMARY KEY,
        query            TEXT        NOT NULL,
        reply            TEXT        NOT NULL,
        mode             VARCHAR(20) NOT NULL,
        score            FLOAT,
        response_time_ms FLOAT,
        parent_id        VARCHAR(100),   -- extracted from JWT token
        baby_id          VARCHAR(50),    -- selected baby ID
        created_at       TIMESTAMP   DEFAULT NOW()
    );
""")

# ── Migration: add parent_id and baby_id if table already exists ─────────────
cur.execute("""
    ALTER TABLE chat_logs
    ADD COLUMN IF NOT EXISTS parent_id VARCHAR(100),
    ADD COLUMN IF NOT EXISTS baby_id   VARCHAR(50);
""")

# ── Indexes on chat_logs for per-user analysis ───────────────────────────────
cur.execute("CREATE INDEX IF NOT EXISTS idx_chat_logs_parent_id ON chat_logs (parent_id);")
cur.execute("CREATE INDEX IF NOT EXISTS idx_chat_logs_baby_id   ON chat_logs (baby_id);")

# ── Table 2: doctor_feedback ────────────────────────────────────────────────
cur.execute("""
    CREATE TABLE IF NOT EXISTS doctor_feedback (
        id              SERIAL PRIMARY KEY,

        -- The conversation turn being reviewed
        query           TEXT        NOT NULL,
        bot_response    TEXT        NOT NULL,

        -- Retrieval metadata (copied from chat_logs for easy analysis)
        mode            VARCHAR(20),
        score           FLOAT,

        -- Doctor's verdict
        verdict         VARCHAR(30) NOT NULL,
            -- values: 'Correct' | 'Partially correct' | 'Incorrect'

        -- Structured failure category (populated when verdict != Correct)
        failure_reason  VARCHAR(100),
            -- values: 'Should have given home remedy first'
            --         'Should NOT have mentioned medicine'
            --         'Wrong medicine category named'
            --         'Should have escalated to emergency'
            --         'Missing important advice'
            --         'Language / tone issue'
            --         'Gave dose / frequency / duration'
            --         "Said 'consult doctor' incorrectly"
            --         'Other'

        -- Free text notes from the doctor
        doctor_notes    TEXT,

        -- Who reviewed it
        reviewed_by     VARCHAR(100) NOT NULL,
        reviewed_at     TIMESTAMP    DEFAULT NOW()
    );
""")

# ── Indexes for fast analysis queries ───────────────────────────────────────
cur.execute("CREATE INDEX IF NOT EXISTS idx_feedback_verdict        ON doctor_feedback (verdict);")
cur.execute("CREATE INDEX IF NOT EXISTS idx_feedback_failure_reason ON doctor_feedback (failure_reason);")
cur.execute("CREATE INDEX IF NOT EXISTS idx_feedback_mode           ON doctor_feedback (mode);")
cur.execute("CREATE INDEX IF NOT EXISTS idx_feedback_reviewed_by    ON doctor_feedback (reviewed_by);")

conn.commit()
cur.close()
conn.close()

print(" Tables created/updated successfully:")
print("   → chat_logs (with parent_id, baby_id)")
print("   → doctor_feedback")
print("   → indexes on verdict, failure_reason, mode, reviewed_by, parent_id, baby_id")
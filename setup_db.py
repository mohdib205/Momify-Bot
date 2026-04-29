import psycopg2
from core.config import DB_URL

def setup():
    conn = psycopg2.connect(DB_URL)
    cur  = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS chat_logs (
            id               SERIAL PRIMARY KEY,
            timestamp        TIMESTAMP NOT NULL,
            query            TEXT NOT NULL,
            reply            TEXT NOT NULL,
            mode             VARCHAR(20) NOT NULL,
            score            FLOAT NOT NULL,
            response_time_ms FLOAT NOT NULL
        );
    """)

    conn.commit()
    cur.close()
    conn.close()
    print("Table chat_logs created successfully.")

if __name__ == "__main__":
    setup()
        
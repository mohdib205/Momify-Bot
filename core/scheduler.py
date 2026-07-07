"""
core/scheduler.py

Daily token usage email — sync version, matches your psycopg2 + sync FastAPI stack.

Uses APScheduler's BackgroundScheduler:
- Runs in a background THREAD inside the same process (not async, not a separate process)
- Fires once a day at a fixed IST time
- No event loop, no asyncio — fits your existing sync codebase exactly

Install: pip install apscheduler
"""

import os
import smtplib
from datetime import datetime, timezone, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import psycopg2
import psycopg2.extras
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from core.config import DB_URL
from core.logger import app_logger

IST = timezone(timedelta(hours=5, minutes=30))


# ── Data fetch ─────────────────────────────────────────────────────────────

def _fetch_daily_stats(date_ist: datetime) -> dict:
    """Pull today's token usage from PostgreSQL. Sync, psycopg2, RealDictCursor
    so rows come back as dicts (same convenience asyncpg gave us, no async needed)."""

    day_start_utc = date_ist.replace(hour=0, minute=0, second=0, microsecond=0).astimezone(timezone.utc)
    day_end_utc   = date_ist.replace(hour=23, minute=59, second=59, microsecond=0).astimezone(timezone.utc)

    conn = psycopg2.connect(DB_URL)
    cur  = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    try:
        cur.execute("""
            SELECT
                COUNT(*)                            AS requests,
                COALESCE(SUM(prompt_tokens), 0)      AS prompt_tokens,
                COALESCE(SUM(completion_tokens), 0)  AS completion_tokens,
                COALESCE(SUM(total_tokens), 0)       AS total_tokens
            FROM token_usage
            WHERE created_at BETWEEN %s AND %s
        """, (day_start_utc, day_end_utc))
        totals = cur.fetchone()

        cur.execute("""
            SELECT mode, COUNT(*) AS requests, SUM(total_tokens) AS tokens
            FROM token_usage
            WHERE created_at BETWEEN %s AND %s
            GROUP BY mode
            ORDER BY tokens DESC
        """, (day_start_utc, day_end_utc))
        by_mode = cur.fetchall()

        cur.execute("""
            SELECT parent_id, COUNT(*) AS requests, SUM(total_tokens) AS tokens
            FROM token_usage
            WHERE created_at BETWEEN %s AND %s
            GROUP BY parent_id
            ORDER BY tokens DESC
            LIMIT 5
        """, (day_start_utc, day_end_utc))
        top_parents = cur.fetchall()

        return {
            "totals":      dict(totals) if totals else {"requests": 0, "prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
            "by_mode":     [dict(r) for r in by_mode],
            "top_parents": [dict(r) for r in top_parents],
        }
    finally:
        cur.close()
        conn.close()


# ── Email building ────────────────────────────────────────────────────────

def _build_email_html(date_str: str, stats: dict) -> str:
    totals = stats["totals"]

    mode_rows = "".join(
        f"<tr><td>{r['mode']}</td><td>{r['requests']}</td><td>{r['tokens']:,}</td></tr>"
        for r in stats["by_mode"]
    ) or "<tr><td colspan='3'>No data</td></tr>"

    parent_rows = "".join(
        f"<tr><td>{r['parent_id']}</td><td>{r['requests']}</td><td>{r['tokens']:,}</td></tr>"
        for r in stats["top_parents"]
    ) or "<tr><td colspan='3'>No data</td></tr>"

    return f"""
    <html><body style="font-family:sans-serif;color:#222;max-width:600px;margin:auto">
      <h2 style="color:#e91e8c">🍼 Momify AI — Daily Token Report</h2>
      <p style="color:#666">{date_str} (IST)</p>

      <h3>📊 Summary</h3>
      <table border="1" cellpadding="8" cellspacing="0" style="border-collapse:collapse;width:100%">
        <tr style="background:#fce4ec"><th>Metric</th><th>Value</th></tr>
        <tr><td>Total Requests</td><td><b>{totals['requests']}</b></td></tr>
        <tr><td>Prompt Tokens</td><td>{totals['prompt_tokens']:,}</td></tr>
        <tr><td>Completion Tokens</td><td>{totals['completion_tokens']:,}</td></tr>
        <tr><td>Total Tokens Used</td><td><b>{totals['total_tokens']:,}</b></td></tr>
      </table>

      <h3>🔀 Breakdown by Mode</h3>
      <table border="1" cellpadding="8" cellspacing="0" style="border-collapse:collapse;width:100%">
        <tr style="background:#fce4ec"><th>Mode</th><th>Requests</th><th>Tokens</th></tr>
        {mode_rows}
      </table>

      <h3>👩 Top 5 Active Parents</h3>
      <table border="1" cellpadding="8" cellspacing="0" style="border-collapse:collapse;width:100%">
        <tr style="background:#fce4ec"><th>Parent ID</th><th>Requests</th><th>Tokens</th></tr>
        {parent_rows}
      </table>

      <p style="color:#999;font-size:12px;margin-top:24px">
        Sent automatically by Momify chatbot scheduler · {date_str}
      </p>
    </body></html>
    """


def _send_email(subject: str, html_body: str):
    smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com")
    smtp_port = int(os.getenv("SMTP_PORT", 587))
    smtp_user = os.getenv("SMTP_USER")
    smtp_pass = os.getenv("SMTP_PASSWORD")
    from_addr = os.getenv("REPORT_EMAIL_FROM", smtp_user)
    to_addr   = os.getenv("REPORT_EMAIL_TO")

    if not all([smtp_user, smtp_pass, to_addr]):
        app_logger.error("scheduler: SMTP_USER / SMTP_PASSWORD / REPORT_EMAIL_TO not set — skipping email")
        return

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = from_addr
    msg["To"]      = to_addr
    msg.attach(MIMEText(html_body, "html"))

    with smtplib.SMTP(smtp_host, smtp_port) as server:
        server.ehlo()
        server.starttls()
        server.login(smtp_user, smtp_pass)
        server.sendmail(from_addr, to_addr, msg.as_string())

    app_logger.info(f"scheduler: daily report sent to {to_addr}")


# ── The job APScheduler calls ────────────────────────────────────────────

def send_daily_report():
    now_ist  = datetime.now(IST)
    date_str = now_ist.strftime("%d %B %Y")

    try:
        stats   = _fetch_daily_stats(now_ist)
        html    = _build_email_html(date_str, stats)
        subject = f"Momify AI — Token Usage Report · {date_str}"
        _send_email(subject, html)
    except Exception as e:
        app_logger.error(f"scheduler: daily report failed — {e}")


# ── Scheduler setup — called once from main.py at startup ───────────────────

scheduler = BackgroundScheduler(timezone="Asia/Kolkata")

def start_scheduler():
    """
    Call this once from main.py on app startup.
    Fires send_daily_report() every day at 23:59 IST.
    Runs in a background thread — does not block requests, does not need async.
    """
    scheduler.add_job(
        send_daily_report,
        trigger=CronTrigger(hour=15, minute=48),
        id="daily_token_report",
        replace_existing=True,
    )
    scheduler.start()
    app_logger.info("scheduler: daily token report job scheduled for 23:59 IST")



# ============================================================
#sending mail to admin in case of exhaustation of both keys
# ============================================================

def send_admin_alert_email(subject: str):
    """
    Urgent alert — used when both Groq keys are exhausted (daily limit).
    Reuses the same SMTP config as the daily token report.
    """
    body = f"""
    <html><body style="font-family:sans-serif;color:#222;max-width:600px;margin:auto">
      <h2 style="color:#d32f2f">🚨 Momify AI — Urgent: Action Required</h2>
      <p>Both Groq API keys (primary and secondary) have hit their
      <b>daily</b> token/request limit (TPD/RPD).</p>
      <p>The chatbot is currently returning <code>SERVICE_UNAVAILABLE</code>
      to all parents until this is resolved.</p>
      <h3>Action needed</h3>
      <ol>
        <li>Generate a fresh Groq API key — ideally from a separate Groq
            account/organization, since limits are per-organization and a
            second key from the same account won't help.</li>
        <li>Update <code>GROQ_API_KEY_PRIMARY</code> or
            <code>GROQ_API_KEY_SECONDARY</code> in <code>.env</code>.</li>
        <li>Restart the app, or call the admin reset endpoint to clear the
            "both keys dead" state without a full restart.</li>
      </ol>
      <p style="color:#999;font-size:12px;margin-top:24px">
        Sent automatically by Momify chatbot — {subject}
      </p>
    </body></html>
    """
    _send_email(subject, body)
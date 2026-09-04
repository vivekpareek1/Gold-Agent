"""
Postgres access layer. Uses a dedicated schema (config.DB_SCHEMA, default
"gold_agent") inside the shared free Postgres instance so this project's
tables never collide with anything else living on that database.
"""
import psycopg2
import psycopg2.extras
import config


def get_connection():
    if not config.DATABASE_URL:
        raise RuntimeError("DATABASE_URL is not set in the environment.")
    return psycopg2.connect(config.DATABASE_URL)


def init_db():
    """Creates the schema and trades table if they don't already exist."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(f"CREATE SCHEMA IF NOT EXISTS {config.DB_SCHEMA};")
            cur.execute(f"""
                CREATE TABLE IF NOT EXISTS {config.DB_SCHEMA}.trades (
                    id SERIAL PRIMARY KEY,
                    mode TEXT NOT NULL,                    -- 'live' or 'backtest'
                    direction TEXT NOT NULL,                -- 'BUY' or 'SELL'
                    entry_time TIMESTAMPTZ NOT NULL,
                    entry_price DOUBLE PRECISION NOT NULL,
                    sl DOUBLE PRECISION NOT NULL,
                    tp DOUBLE PRECISION NOT NULL,
                    size_oz DOUBLE PRECISION NOT NULL,
                    confidence INTEGER,
                    reasoning TEXT,
                    status TEXT NOT NULL DEFAULT 'OPEN',    -- 'OPEN', 'CLOSED_TP', 'CLOSED_SL', 'CLOSED_MANUAL'
                    exit_time TIMESTAMPTZ,
                    exit_price DOUBLE PRECISION,
                    pnl DOUBLE PRECISION,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
                );
            """)
            cur.execute(f"""
                CREATE INDEX IF NOT EXISTS idx_trades_mode_time
                ON {config.DB_SCHEMA}.trades (mode, entry_time DESC);
            """)
        conn.commit()
    finally:
        conn.close()


def insert_trade(mode, direction, entry_time, entry_price, sl, tp, size_oz, confidence, reasoning):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(f"""
                INSERT INTO {config.DB_SCHEMA}.trades
                    (mode, direction, entry_time, entry_price, sl, tp, size_oz, confidence, reasoning, status)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,'OPEN')
                RETURNING id;
            """, (mode, direction, entry_time, entry_price, sl, tp, size_oz, confidence, reasoning))
            trade_id = cur.fetchone()[0]
        conn.commit()
        return trade_id
    finally:
        conn.close()


def close_trade(trade_id, exit_time, exit_price, status, pnl):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(f"""
                UPDATE {config.DB_SCHEMA}.trades
                SET exit_time=%s, exit_price=%s, status=%s, pnl=%s
                WHERE id=%s;
            """, (exit_time, exit_price, status, pnl, trade_id))
        conn.commit()
    finally:
        conn.close()


def get_open_trade(mode):
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(f"""
                SELECT * FROM {config.DB_SCHEMA}.trades
                WHERE mode=%s AND status='OPEN'
                ORDER BY entry_time DESC LIMIT 1;
            """, (mode,))
            return cur.fetchone()
    finally:
        conn.close()


def get_open_trades_count(mode):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(f"SELECT COUNT(*) FROM {config.DB_SCHEMA}.trades WHERE mode=%s AND status='OPEN';", (mode,))
            return cur.fetchone()[0]
    finally:
        conn.close()


def get_todays_realized_pnl(mode):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(f"""
                SELECT COALESCE(SUM(pnl), 0) FROM {config.DB_SCHEMA}.trades
                WHERE mode=%s AND status != 'OPEN' AND exit_time::date = CURRENT_DATE;
            """, (mode,))
            return float(cur.fetchone()[0])
    finally:
        conn.close()


def get_consecutive_losses(mode):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(f"""
                SELECT pnl FROM {config.DB_SCHEMA}.trades
                WHERE mode=%s AND status != 'OPEN'
                ORDER BY exit_time DESC LIMIT 20;
            """, (mode,))
            rows = [r[0] for r in cur.fetchall()]
        count = 0
        for pnl in rows:
            if pnl is not None and pnl < 0:
                count += 1
            else:
                break
        return count
    finally:
        conn.close()


def get_all_trades(mode=None, limit=500):
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            if mode:
                cur.execute(f"""
                    SELECT * FROM {config.DB_SCHEMA}.trades
                    WHERE mode=%s ORDER BY entry_time DESC LIMIT %s;
                """, (mode, limit))
            else:
                cur.execute(f"""
                    SELECT * FROM {config.DB_SCHEMA}.trades
                    ORDER BY entry_time DESC LIMIT %s;
                """, (limit,))
            return cur.fetchall()
    finally:
        conn.close()


def get_summary(mode):
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(f"""
                SELECT
                    COUNT(*) FILTER (WHERE status != 'OPEN') AS closed_trades,
                    COUNT(*) FILTER (WHERE status = 'OPEN') AS open_trades,
                    COUNT(*) FILTER (WHERE pnl > 0) AS wins,
                    COUNT(*) FILTER (WHERE pnl <= 0 AND status != 'OPEN') AS losses,
                    COALESCE(SUM(pnl), 0) AS total_pnl,
                    COALESCE(AVG(pnl) FILTER (WHERE pnl > 0), 0) AS avg_win,
                    COALESCE(AVG(pnl) FILTER (WHERE pnl <= 0 AND status != 'OPEN'), 0) AS avg_loss
                FROM {config.DB_SCHEMA}.trades WHERE mode=%s;
            """, (mode,))
            return cur.fetchone()
    finally:
        conn.close()

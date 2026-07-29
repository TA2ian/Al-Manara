"""Database initialization."""
import asyncpg
import logging
from config import Config

logger = logging.getLogger(__name__)
_pool = None


async def init_db():
    """Initialize database connection pool."""
    global _pool
    _pool = await asyncpg.create_pool(
        Config.DATABASE_URL,
        min_size=5,
        max_size=20,
        command_timeout=60
    )
    logger.info("Database pool created")

    # Create tables
    async with _pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                telegram_id BIGINT UNIQUE NOT NULL,
                username TEXT,
                full_name TEXT,
                shamcash_account TEXT,
                shamcash_qr_photo_id TEXT,
                language TEXT DEFAULT 'ar',
                terms_accepted BOOLEAN DEFAULT FALSE,
                terms_accepted_at TIMESTAMP,
                is_verified BOOLEAN DEFAULT FALSE,
                verification_status TEXT DEFAULT 'pending',
                is_blocked BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                id SERIAL PRIMARY KEY,
                order_number TEXT UNIQUE NOT NULL,
                user_id INTEGER REFERENCES users(id),
                network TEXT NOT NULL,
                amount_usdt REAL NOT NULL,
                exchange_rate REAL NOT NULL,
                payment_currency TEXT NOT NULL,
                base_amount REAL NOT NULL,
                fee_percent REAL DEFAULT 0,
                fee_amount REAL DEFAULT 0,
                total_amount REAL NOT NULL,
                wallet_address TEXT NOT NULL,
                status TEXT DEFAULT 'pending',
                receipt_photo_id TEXT,
                receipt_upload_count INTEGER DEFAULT 0,
                txid TEXT,
                admin_notes TEXT,
                customer_rating INTEGER,
                customer_comment TEXT,
                created_at TIMESTAMP DEFAULT NOW(),
                approved_at TIMESTAMP,
                payment_deadline TIMESTAMP,
                completed_at TIMESTAMP
            )
        """)

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS exchange_rates (
                id SERIAL PRIMARY KEY,
                rate REAL NOT NULL,
                updated_by BIGINT,
                updated_at TIMESTAMP DEFAULT NOW()
            )
        """)

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS audit_logs (
                id SERIAL PRIMARY KEY,
                user_id INTEGER,
                admin_id BIGINT,
                action TEXT NOT NULL,
                details TEXT,
                previous_value TEXT,
                new_value TEXT,
                severity TEXT DEFAULT 'info',
                timestamp TIMESTAMP DEFAULT NOW()
            )
        """)

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS blocked_users (
                id SERIAL PRIMARY KEY,
                telegram_id BIGINT NOT NULL,
                reason TEXT,
                blocked_by BIGINT,
                blocked_at TIMESTAMP DEFAULT NOW(),
                expires_at TIMESTAMP
            )
        """)

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS feedback_messages (
                id SERIAL PRIMARY KEY,
                user_id INTEGER REFERENCES users(id),
                message TEXT NOT NULL,
                status TEXT DEFAULT 'pending',
                admin_reply TEXT,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)

        # Insert default exchange rate if empty
        count = await conn.fetchval("SELECT COUNT(*) FROM exchange_rates")
        if count == 0:
            await conn.execute(
                "INSERT INTO exchange_rates (rate, updated_by) VALUES ($1, $2)",
                15000.0, 0
            )


async def get_pool():
    """Get database pool."""
    return _pool


async def close_db():
    """Close database pool."""
    if _pool:
        await _pool.close()
        logger.info("Database pool closed")

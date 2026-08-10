"""Database initialization and compatibility migrations for Al-Manara."""
import asyncpg
import logging
from config import Config

logger = logging.getLogger(__name__)
_pool = None


async def init_db():
    """Initialize database connection pool and apply additive schema changes."""
    global _pool
    if not Config.DATABASE_URL:
        raise RuntimeError("DATABASE_URL is required")

    _pool = await asyncpg.create_pool(
        Config.DATABASE_URL,
        min_size=5,
        max_size=20,
        command_timeout=60,
    )
    logger.info("Database pool created")

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
                wallet_qr_photo_id TEXT,
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

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS saved_addresses (
                id SERIAL PRIMARY KEY,
                user_id INTEGER REFERENCES users(id),
                address TEXT NOT NULL,
                network TEXT NOT NULL,
                label TEXT DEFAULT '',
                qr_photo_id TEXT,
                is_default BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW()
            )
        """)

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS payment_methods (
                id SERIAL PRIMARY KEY,
                code TEXT UNIQUE NOT NULL,
                provider TEXT NOT NULL,
                currency TEXT NOT NULL,
                display_name TEXT NOT NULL,
                account_identifier TEXT NOT NULL DEFAULT '',
                qr_photo_id TEXT,
                enabled BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW()
            )
        """)

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS bot_settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TIMESTAMP DEFAULT NOW()
            )
        """)

        # Additive compatibility migrations for databases created by older versions.
        await conn.execute(
            "ALTER TABLE saved_addresses ADD COLUMN IF NOT EXISTS qr_photo_id TEXT"
        )
        await conn.execute(
            "ALTER TABLE saved_addresses ADD COLUMN IF NOT EXISTS is_default BOOLEAN DEFAULT FALSE"
        )
        await conn.execute(
            "ALTER TABLE saved_addresses ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP DEFAULT NOW()"
        )
        await conn.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_blocked_users_telegram_id ON blocked_users (telegram_id)"
        )
        await conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_orders_user_status ON orders (user_id, status)"
        )
        await conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_orders_deadline ON orders (status, payment_deadline)"
        )
        await conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_saved_addresses_user ON saved_addresses (user_id)"
        )

        # Insert default exchange rate if empty.
        count = await conn.fetchval("SELECT COUNT(*) FROM exchange_rates")
        if count == 0:
            await conn.execute(
                "INSERT INTO exchange_rates (rate, updated_by) VALUES ($1, $2)",
                15000.0,
                0,
            )


async def get_pool():
    """Get database pool."""
    return _pool


async def close_db():
    """Close database pool."""
    global _pool
    if _pool:
        await _pool.close()
        _pool = None
        logger.info("Database pool closed")

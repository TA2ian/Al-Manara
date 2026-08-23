import asyncpg
import logging
from config import Config
from database_wallet_guards import install_order_wallet_guard

logger = logging.getLogger(__name__)
_pool = None


async def init_db():
    """Initialize database connection pool and apply additive schema changes."""
    global _pool
    if not Config.DATABASE_URL:
        raise RuntimeError("DATABASE_URL is required")

    _pool = await asyncpg.create_pool(Config.DATABASE_URL, min_size=5, max_size=20, command_timeout=60)
    logger.info("Database pool created")

    async with _pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY, telegram_id BIGINT UNIQUE NOT NULL, username TEXT,
                phone_number TEXT, phone_verified BOOLEAN DEFAULT FALSE,
                full_name TEXT, shamcash_account TEXT, shamcash_qr_photo_id TEXT,
                language TEXT DEFAULT 'ar', terms_accepted BOOLEAN DEFAULT FALSE,
                terms_accepted_at TIMESTAMP, is_verified BOOLEAN DEFAULT FALSE,
                verification_status TEXT DEFAULT 'pending', is_blocked BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                id SERIAL PRIMARY KEY, order_number TEXT UNIQUE NOT NULL, user_id INTEGER REFERENCES users(id),
                network TEXT NOT NULL, amount_usdt NUMERIC(24,8) NOT NULL, exchange_rate NUMERIC(24,8) NOT NULL,
                payment_currency TEXT NOT NULL, base_amount NUMERIC(24,8) NOT NULL,
                fee_percent NUMERIC(12,6) DEFAULT 0, fee_amount NUMERIC(24,8) DEFAULT 0,
                total_amount NUMERIC(24,8) NOT NULL, wallet_address TEXT NOT NULL, wallet_qr_photo_id TEXT,
                payment_method_code TEXT, payment_account_snapshot TEXT, payment_qr_photo_id TEXT,
                status TEXT DEFAULT 'pending', receipt_photo_id TEXT, receipt_upload_count INTEGER DEFAULT 0,
                txid TEXT, admin_notes TEXT, customer_rating INTEGER, customer_comment TEXT,
                customer_status_message_id BIGINT,
                created_at TIMESTAMP DEFAULT NOW(), approved_at TIMESTAMP, payment_deadline TIMESTAMP,
                completed_at TIMESTAMP
            )
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS exchange_rates (
                id SERIAL PRIMARY KEY, rate NUMERIC(24,8) NOT NULL,
                rate_currency TEXT NOT NULL DEFAULT 'NEW.SYP', updated_by BIGINT, updated_at TIMESTAMP DEFAULT NOW()
            )
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS audit_logs (
                id SERIAL PRIMARY KEY, user_id INTEGER, admin_id BIGINT, action TEXT NOT NULL,
                details TEXT, previous_value TEXT, new_value TEXT, severity TEXT DEFAULT 'info', timestamp TIMESTAMP DEFAULT NOW()
            )
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS blocked_users (
                id SERIAL PRIMARY KEY, telegram_id BIGINT NOT NULL, reason TEXT, blocked_by BIGINT,
                blocked_at TIMESTAMP DEFAULT NOW(), expires_at TIMESTAMP
            )
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS feedback_messages (
                id SERIAL PRIMARY KEY, user_id INTEGER REFERENCES users(id), message TEXT NOT NULL,
                status TEXT DEFAULT 'pending', admin_reply TEXT, created_at TIMESTAMP DEFAULT NOW()
            )
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS saved_addresses (
                id SERIAL PRIMARY KEY, user_id INTEGER REFERENCES users(id), address TEXT NOT NULL,
                network TEXT NOT NULL, label TEXT DEFAULT '', qr_photo_id TEXT, is_default BOOLEAN DEFAULT FALSE,
                verification_status TEXT DEFAULT 'pending', verified_at TIMESTAMP, deleted_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT NOW(), updated_at TIMESTAMP DEFAULT NOW()
            )
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS payment_methods (
                id SERIAL PRIMARY KEY, code TEXT UNIQUE NOT NULL, provider TEXT NOT NULL, currency TEXT NOT NULL,
                display_name TEXT NOT NULL, account_identifier TEXT NOT NULL DEFAULT '', qr_photo_id TEXT,
                enabled BOOLEAN DEFAULT TRUE, created_at TIMESTAMP DEFAULT NOW(), updated_at TIMESTAMP DEFAULT NOW()
            )
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS bot_settings (
                key TEXT PRIMARY KEY, value TEXT NOT NULL, updated_at TIMESTAMP DEFAULT NOW()
            )
        """)

        await conn.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS phone_number TEXT")
        await conn.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS phone_verified BOOLEAN DEFAULT FALSE")
        await conn.execute("ALTER TABLE saved_addresses ADD COLUMN IF NOT EXISTS qr_photo_id TEXT")
        await conn.execute("ALTER TABLE saved_addresses ADD COLUMN IF NOT EXISTS is_default BOOLEAN DEFAULT FALSE")
        await conn.execute("ALTER TABLE saved_addresses ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP DEFAULT NOW()")
        await conn.execute("ALTER TABLE saved_addresses ADD COLUMN IF NOT EXISTS verification_status TEXT DEFAULT 'pending'")
        await conn.execute("ALTER TABLE saved_addresses ADD COLUMN IF NOT EXISTS verified_at TIMESTAMP")
        await conn.execute("ALTER TABLE saved_addresses ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMP")
        await conn.execute("ALTER TABLE orders ADD COLUMN IF NOT EXISTS payment_method_code TEXT")
        await conn.execute("ALTER TABLE orders ADD COLUMN IF NOT EXISTS payment_account_snapshot TEXT")
        await conn.execute("ALTER TABLE orders ADD COLUMN IF NOT EXISTS payment_qr_photo_id TEXT")
        await conn.execute("ALTER TABLE orders ADD COLUMN IF NOT EXISTS customer_status_message_id BIGINT")
        await conn.execute("ALTER TABLE exchange_rates ADD COLUMN IF NOT EXISTS rate_currency TEXT DEFAULT 'NEW.SYP'")

        await conn.execute("ALTER TABLE orders ALTER COLUMN amount_usdt TYPE NUMERIC(24,8) USING amount_usdt::NUMERIC")
        await conn.execute("ALTER TABLE orders ALTER COLUMN exchange_rate TYPE NUMERIC(24,8) USING exchange_rate::NUMERIC")
        await conn.execute("ALTER TABLE orders ALTER COLUMN base_amount TYPE NUMERIC(24,8) USING base_amount::NUMERIC")
        await conn.execute("ALTER TABLE orders ALTER COLUMN fee_percent TYPE NUMERIC(12,6) USING fee_percent::NUMERIC")
        await conn.execute("ALTER TABLE orders ALTER COLUMN fee_amount TYPE NUMERIC(24,8) USING fee_amount::NUMERIC")
        await conn.execute("ALTER TABLE orders ALTER COLUMN total_amount TYPE NUMERIC(24,8) USING total_amount::NUMERIC")
        await conn.execute("ALTER TABLE exchange_rates ALTER COLUMN rate TYPE NUMERIC(24,8) USING rate::NUMERIC")

        migrated = await conn.fetchval("SELECT value FROM bot_settings WHERE key = 'currency_migration_new_syp_v1'")
        if migrated is None:
            await conn.execute("UPDATE exchange_rates SET rate = rate / 100, rate_currency = 'NEW.SYP' WHERE rate > 1000")
            await conn.execute("UPDATE payment_methods SET currency = 'NEW.SYP', updated_at = NOW() WHERE currency = 'SYP'")
            await conn.execute("INSERT INTO bot_settings (key, value) VALUES ('currency_migration_new_syp_v1', 'done')")

        legacy_method = await conn.fetchrow(
            """SELECT id, account_identifier, qr_photo_id, enabled
               FROM payment_methods
              WHERE provider = 'ShamCash' AND code = 'shamcash_syp'
              LIMIT 1"""
        )
        canonical_syp = await conn.fetchrow(
            """SELECT id, account_identifier, qr_photo_id
               FROM payment_methods
              WHERE provider = 'ShamCash' AND code = 'shamcash_new_syp'
              LIMIT 1"""
        )
        if legacy_method:
            if canonical_syp:
                if not canonical_syp["account_identifier"] and legacy_method["account_identifier"]:
                    await conn.execute(
                        "UPDATE payment_methods SET account_identifier = $1, updated_at = NOW() WHERE id = $2",
                        legacy_method["account_identifier"],
                        canonical_syp["id"],
                    )
                if not canonical_syp["qr_photo_id"] and legacy_method["qr_photo_id"]:
                    await conn.execute(
                        "UPDATE payment_methods SET qr_photo_id = $1, updated_at = NOW() WHERE id = $2",
                        legacy_method["qr_photo_id"],
                        canonical_syp["id"],
                    )
                await conn.execute("DELETE FROM payment_methods WHERE id = $1", legacy_method["id"])
            else:
                await conn.execute(
                    """UPDATE payment_methods
                          SET code = 'shamcash_new_syp', currency = 'NEW.SYP',
                              display_name = 'ShamCash الليرة السورية الجديدة', updated_at = NOW()
                        WHERE id = $1""",
                    legacy_method["id"],
                )

        await conn.execute("""INSERT INTO payment_methods
            (code, provider, currency, display_name, account_identifier, enabled)
            VALUES ('shamcash_usd', 'ShamCash', 'USD', 'ShamCash USD', $1, TRUE)
            ON CONFLICT (code) DO NOTHING""", Config.get_shamcash_usd())
        await conn.execute("""INSERT INTO payment_methods
            (code, provider, currency, display_name, account_identifier, enabled)
            VALUES ('shamcash_new_syp', 'ShamCash', 'NEW.SYP', 'ShamCash NEW.SYP', $1, TRUE)
            ON CONFLICT (code) DO NOTHING""", Config.get_shamcash_syp())

        await conn.execute("CREATE INDEX IF NOT EXISTS idx_blocked_users_telegram_id ON blocked_users (telegram_id)")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_orders_user_status ON orders (user_id, status)")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_orders_deadline ON orders (status, payment_deadline)")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_saved_addresses_user ON saved_addresses (user_id)")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_payment_methods_currency_enabled ON payment_methods (currency, enabled)")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_users_phone_verified ON users (phone_verified)")
        await conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS uq_saved_addresses_active ON saved_addresses (user_id, address, network) WHERE deleted_at IS NULL")

        await conn.execute("""
            CREATE OR REPLACE FUNCTION protect_verified_wallet()
            RETURNS TRIGGER AS $$
            BEGIN
                IF TG_OP = 'UPDATE' AND OLD.verification_status = 'verified' THEN
                    IF NEW.address IS DISTINCT FROM OLD.address OR NEW.network IS DISTINCT FROM OLD.network
                       OR NEW.qr_photo_id IS DISTINCT FROM OLD.qr_photo_id OR NEW.verification_status IS DISTINCT FROM OLD.verification_status THEN
                        RAISE EXCEPTION 'Verified wallet is immutable; delete and add a new wallet instead';
                    END IF;
                END IF;
                IF TG_OP = 'DELETE' THEN
                    IF EXISTS (SELECT 1 FROM orders WHERE user_id = OLD.user_id AND wallet_address = OLD.address
                              AND network = OLD.network AND status IN ('pending','waiting_payment','receipt_received','payment_confirmed')) THEN
                        RAISE EXCEPTION 'Wallet is linked to an active order and cannot be deleted';
                    END IF;
                    RETURN OLD;
                END IF;
                RETURN NEW;
            END;
            $$ LANGUAGE plpgsql;
        """)
        await conn.execute("DROP TRIGGER IF EXISTS trg_protect_verified_wallet ON saved_addresses")
        await conn.execute("""CREATE TRIGGER trg_protect_verified_wallet
            BEFORE UPDATE OR DELETE ON saved_addresses
            FOR EACH ROW EXECUTE FUNCTION protect_verified_wallet()""")

        await conn.execute("""
            CREATE OR REPLACE FUNCTION snapshot_order_payment_method()
            RETURNS TRIGGER AS $$
            DECLARE method_row RECORD;
            BEGIN
                IF NEW.payment_currency = 'SYP' THEN NEW.payment_currency := 'NEW.SYP'; END IF;
                IF NEW.payment_currency IN ('USD', 'NEW.SYP') AND NEW.payment_method_code IS NULL THEN
                    SELECT code, account_identifier, qr_photo_id INTO method_row
                    FROM payment_methods
                    WHERE provider = 'ShamCash'
                      AND currency = NEW.payment_currency
                      AND code IN ('shamcash_usd', 'shamcash_new_syp')
                      AND enabled = TRUE
                    ORDER BY id ASC LIMIT 1;
                    IF FOUND THEN
                        NEW.payment_method_code := method_row.code;
                        NEW.payment_account_snapshot := method_row.account_identifier;
                        NEW.payment_qr_photo_id := method_row.qr_photo_id;
                    END IF;
                END IF;
                RETURN NEW;
            END;
            $$ LANGUAGE plpgsql;
        """)
        await conn.execute("DROP TRIGGER IF EXISTS trg_snapshot_order_payment_method ON orders")
        await conn.execute("""CREATE TRIGGER trg_snapshot_order_payment_method
            BEFORE INSERT ON orders FOR EACH ROW EXECUTE FUNCTION snapshot_order_payment_method()""")

        await conn.execute("""
            CREATE OR REPLACE FUNCTION prevent_multiple_active_orders()
            RETURNS TRIGGER AS $$
            BEGIN
                IF NEW.status IN ('pending','waiting_payment','receipt_received','payment_confirmed') AND NEW.user_id IS NOT NULL
                   AND (TG_OP = 'INSERT' OR OLD.status NOT IN ('pending','waiting_payment','receipt_received','payment_confirmed')) THEN
                    PERFORM pg_advisory_xact_lock(2147483000, NEW.user_id);
                    IF EXISTS (SELECT 1 FROM orders WHERE user_id = NEW.user_id
                               AND status IN ('pending','waiting_payment','receipt_received','payment_confirmed')
                               AND id <> COALESCE(NEW.id, -1)) THEN
                        RAISE EXCEPTION 'active order already exists for user %', NEW.user_id USING ERRCODE = '23514';
                    END IF;
                END IF;
                RETURN NEW;
            END;
            $$ LANGUAGE plpgsql;
        """)
        await conn.execute("DROP TRIGGER IF EXISTS trg_prevent_multiple_active_orders ON orders")
        await conn.execute("""CREATE TRIGGER trg_prevent_multiple_active_orders
            BEFORE INSERT OR UPDATE OF user_id, status ON orders
            FOR EACH ROW EXECUTE FUNCTION prevent_multiple_active_orders()""")

        await install_order_wallet_guard(conn)

        await conn.execute("""
            CREATE OR REPLACE FUNCTION enforce_order_state_transition()
            RETURNS TRIGGER AS $$
            BEGIN
                IF NEW.status IS DISTINCT FROM OLD.status THEN
                    IF NOT ((OLD.status='pending' AND NEW.status IN ('waiting_payment','rejected','expired')) OR
                            (OLD.status='waiting_payment' AND NEW.status IN ('receipt_received','rejected','expired','pending')) OR
                            (OLD.status='receipt_received' AND NEW.status IN ('waiting_payment','payment_confirmed','rejected')) OR
                            (OLD.status='payment_confirmed' AND NEW.status IN ('completed'))) THEN
                        RAISE EXCEPTION 'invalid order state transition: % -> %', OLD.status, NEW.status USING ERRCODE='P0001';
                    END IF;
                END IF;
                RETURN NEW;
            END;
            $$ LANGUAGE plpgsql;
        """)
        await conn.execute("DROP TRIGGER IF EXISTS trg_enforce_order_state_transition ON orders")
        await conn.execute("""CREATE TRIGGER trg_enforce_order_state_transition
            BEFORE UPDATE OF status ON orders FOR EACH ROW EXECUTE FUNCTION enforce_order_state_transition()""")

        count = await conn.fetchval("SELECT COUNT(*) FROM exchange_rates")
        if count == 0:
            await conn.execute("INSERT INTO exchange_rates (rate, rate_currency, updated_by) VALUES ($1, 'NEW.SYP', $2)", "150.00", 0)


async def get_pool():
    return _pool


async def close_db():
    global _pool
    if _pool:
        await _pool.close()
        _pool = None
        logger.info("Database pool closed")

"""Canonical PostgreSQL constraints for wallet, payment, identity, and time snapshots."""
from config import Config


async def install_order_constraints(conn):
    """Install canonical database invariants used by wallet, payment, identity, and order flows."""
    await conn.execute("ALTER TABLE payment_methods ADD COLUMN IF NOT EXISTS recipient_name TEXT")
    await conn.execute("ALTER TABLE saved_addresses ADD COLUMN IF NOT EXISTS is_default BOOLEAN DEFAULT FALSE")
    await conn.execute("ALTER TABLE saved_addresses ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMP")
    await conn.execute("ALTER TABLE saved_addresses ADD COLUMN IF NOT EXISTS created_at TIMESTAMP DEFAULT NOW()")
    await conn.execute("ALTER TABLE orders ADD COLUMN IF NOT EXISTS payment_recipient_name_snapshot TEXT")
    await conn.execute("ALTER TABLE orders ADD COLUMN IF NOT EXISTS payment_account_snapshot TEXT")
    await conn.execute("ALTER TABLE orders ADD COLUMN IF NOT EXISTS payment_qr_photo_id TEXT")
    await conn.execute("ALTER TABLE orders ADD COLUMN IF NOT EXISTS customer_full_name_snapshot TEXT")
    await conn.execute("ALTER TABLE orders ADD COLUMN IF NOT EXISTS customer_telegram_id_snapshot BIGINT")
    await conn.execute("ALTER TABLE orders ADD COLUMN IF NOT EXISTS customer_username_snapshot TEXT")
    await conn.execute("ALTER TABLE orders ADD COLUMN IF NOT EXISTS customer_shamcash_account_snapshot TEXT")
    await conn.execute("ALTER TABLE orders ADD COLUMN IF NOT EXISTS payment_deadline TIMESTAMP")
    await conn.execute("ALTER TABLE orders ADD COLUMN IF NOT EXISTS approved_at TIMESTAMP")
    await conn.execute("ALTER TABLE orders ADD COLUMN IF NOT EXISTS created_at TIMESTAMP DEFAULT NOW()")
    await conn.execute("ALTER TABLE orders ADD COLUMN IF NOT EXISTS order_number TEXT")

    await conn.execute("""
        CREATE TABLE IF NOT EXISTS misconduct_incidents (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id),
            telegram_id BIGINT NOT NULL,
            order_id INTEGER NOT NULL REFERENCES orders(id),
            admin_id BIGINT NOT NULL,
            incident_number INTEGER NOT NULL CHECK (incident_number BETWEEN 1 AND 3),
            reason TEXT NOT NULL,
            suspension_expires_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT NOW()
        )
    """)
    await conn.execute("CREATE INDEX IF NOT EXISTS idx_misconduct_user_created ON misconduct_incidents (user_id, created_at DESC)")
    await conn.execute("CREATE INDEX IF NOT EXISTS idx_misconduct_order ON misconduct_incidents (order_id)")

    await conn.execute(
        """UPDATE payment_methods
              SET recipient_name = COALESCE(NULLIF(BTRIM(recipient_name), ''), NULLIF(BTRIM($1), ''), 'ShamCash')
            WHERE provider='ShamCash' AND code IN ('shamcash_usd', 'shamcash_new_syp')""",
        Config.get_shamcash_name(),
    )

    await conn.execute(
        """UPDATE orders o
              SET customer_full_name_snapshot = NULLIF(BTRIM(to_jsonb(u)->>'full_name'), ''),
                  customer_telegram_id_snapshot = u.telegram_id,
                  customer_username_snapshot = NULLIF(BTRIM(to_jsonb(u)->>'username'), ''),
                  customer_shamcash_account_snapshot = NULLIF(BTRIM(to_jsonb(u)->>'shamcash_account'), '')
             FROM users u
            WHERE o.user_id = u.id
              AND (o.customer_full_name_snapshot IS NULL
                OR o.customer_telegram_id_snapshot IS NULL
                OR o.customer_username_snapshot IS NULL
                OR o.customer_shamcash_account_snapshot IS NULL)"""
    )

    await conn.execute("""
        CREATE OR REPLACE FUNCTION snapshot_order_customer_identity()
        RETURNS TRIGGER AS $$
        DECLARE
            customer_full_name TEXT;
            customer_username TEXT;
            customer_shamcash_account TEXT;
            customer_telegram_id BIGINT;
            customer_is_verified BOOLEAN;
            customer_phone_verified BOOLEAN;
            customer_phone_number TEXT;
            customer_terms_accepted BOOLEAN;
        BEGIN
            IF NEW.user_id IS NULL THEN
                RAISE EXCEPTION 'order customer is required' USING ERRCODE='23514';
            END IF;
            SELECT u.is_verified, u.phone_verified, u.phone_number, u.terms_accepted,
                   u.telegram_id, to_jsonb(u)->>'full_name',
                   to_jsonb(u)->>'username', to_jsonb(u)->>'shamcash_account'
              INTO customer_is_verified, customer_phone_verified, customer_phone_number,
                   customer_terms_accepted, customer_telegram_id, customer_full_name,
                   customer_username, customer_shamcash_account
              FROM users u
             WHERE u.id = NEW.user_id;
            IF NOT FOUND THEN
                RAISE EXCEPTION 'order customer does not exist' USING ERRCODE='23514';
            END IF;
            customer_full_name := NULLIF(BTRIM(customer_full_name), '');
            customer_username := NULLIF(BTRIM(customer_username), '');
            customer_shamcash_account := NULLIF(BTRIM(customer_shamcash_account), '');
            customer_phone_number := NULLIF(BTRIM(customer_phone_number), '');
            IF customer_terms_accepted IS NOT TRUE THEN
                RAISE EXCEPTION 'order customer must accept terms' USING ERRCODE='23514';
            END IF;
            IF customer_is_verified IS NOT TRUE THEN
                RAISE EXCEPTION 'order customer is not verified' USING ERRCODE='23514';
            END IF;
            IF customer_phone_verified IS NOT TRUE OR customer_phone_number IS NULL THEN
                RAISE EXCEPTION 'order customer phone is not verified' USING ERRCODE='23514';
            END IF;
            IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema = current_schema() AND table_name = 'users' AND column_name = 'full_name') AND customer_full_name IS NULL THEN
                RAISE EXCEPTION 'order customer full name is missing' USING ERRCODE='23514';
            END IF;
            IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema = current_schema() AND table_name = 'users' AND column_name = 'shamcash_account') AND customer_shamcash_account IS NULL THEN
                RAISE EXCEPTION 'order customer ShamCash account is missing' USING ERRCODE='23514';
            END IF;
            IF TG_OP = 'INSERT' THEN
                NEW.customer_full_name_snapshot := customer_full_name;
                NEW.customer_telegram_id_snapshot := customer_telegram_id;
                NEW.customer_username_snapshot := customer_username;
                NEW.customer_shamcash_account_snapshot := customer_shamcash_account;
                RETURN NEW;
            END IF;
            IF NEW.user_id IS DISTINCT FROM OLD.user_id THEN
                RAISE EXCEPTION 'order customer snapshot is immutable' USING ERRCODE='23514';
            END IF;
            IF NEW.customer_full_name_snapshot IS DISTINCT FROM OLD.customer_full_name_snapshot
               OR NEW.customer_telegram_id_snapshot IS DISTINCT FROM OLD.customer_telegram_id_snapshot
               OR NEW.customer_username_snapshot IS DISTINCT FROM OLD.customer_username_snapshot
               OR NEW.customer_shamcash_account_snapshot IS DISTINCT FROM OLD.customer_shamcash_account_snapshot THEN
                RAISE EXCEPTION 'order customer identity snapshot is immutable' USING ERRCODE='23514';
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)
    await conn.execute("DROP TRIGGER IF EXISTS trg_snapshot_order_customer_identity ON orders")
    await conn.execute("""CREATE TRIGGER trg_snapshot_order_customer_identity
        BEFORE INSERT OR UPDATE OF user_id, customer_full_name_snapshot,
            customer_telegram_id_snapshot, customer_username_snapshot,
            customer_shamcash_account_snapshot
        ON orders FOR EACH ROW EXECUTE FUNCTION snapshot_order_customer_identity()""")

    await conn.execute("""
        CREATE OR REPLACE FUNCTION enforce_order_wallet_snapshot()
        RETURNS TRIGGER AS $$
        DECLARE wallet_row RECORD;
        BEGIN
            IF TG_OP = 'UPDATE' THEN
                IF NEW.user_id IS DISTINCT FROM OLD.user_id OR NEW.wallet_address IS DISTINCT FROM OLD.wallet_address
                   OR NEW.network IS DISTINCT FROM OLD.network OR NEW.wallet_qr_photo_id IS DISTINCT FROM OLD.wallet_qr_photo_id THEN
                    RAISE EXCEPTION 'order wallet snapshot is immutable' USING ERRCODE='23514';
                END IF;
                RETURN NEW;
            END IF;
            SELECT id, address, network, qr_photo_id, verification_status, deleted_at INTO wallet_row
              FROM saved_addresses
             WHERE user_id = NEW.user_id AND address = NEW.wallet_address AND network = NEW.network AND deleted_at IS NULL
             ORDER BY id ASC LIMIT 1;
            IF NOT FOUND THEN RAISE EXCEPTION 'order wallet is not registered for this user' USING ERRCODE='23514'; END IF;
            IF wallet_row.verification_status <> 'verified' THEN RAISE EXCEPTION 'order wallet is not verified' USING ERRCODE='23514'; END IF;
            IF wallet_row.qr_photo_id IS NULL OR btrim(wallet_row.qr_photo_id) = '' THEN RAISE EXCEPTION 'verified order wallet must have a stored QR' USING ERRCODE='23514'; END IF;
            IF NEW.wallet_qr_photo_id IS DISTINCT FROM wallet_row.qr_photo_id THEN RAISE EXCEPTION 'order wallet QR does not match the verified saved wallet' USING ERRCODE='23514'; END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)
    await conn.execute("DROP TRIGGER IF EXISTS trg_enforce_order_wallet_snapshot ON orders")
    await conn.execute("""CREATE TRIGGER trg_enforce_order_wallet_snapshot
        BEFORE INSERT OR UPDATE OF user_id, wallet_address, network, wallet_qr_photo_id ON orders
        FOR EACH ROW EXECUTE FUNCTION enforce_order_wallet_snapshot()""")

    await conn.execute("""
        CREATE OR REPLACE FUNCTION snapshot_order_payment_method()
        RETURNS TRIGGER AS $$
        DECLARE method_row RECORD;
        BEGIN
            IF NEW.payment_currency NOT IN ('USD', 'NEW.SYP') THEN RAISE EXCEPTION 'unsupported payment currency: %', NEW.payment_currency USING ERRCODE='23514'; END IF;
            IF NEW.payment_method_code IS NULL THEN
                SELECT code, account_identifier, recipient_name, qr_photo_id INTO method_row
                FROM payment_methods WHERE provider='ShamCash' AND currency=NEW.payment_currency AND enabled=TRUE ORDER BY id ASC LIMIT 1;
            ELSE
                SELECT code, account_identifier, recipient_name, qr_photo_id INTO method_row
                FROM payment_methods WHERE code=NEW.payment_method_code AND provider='ShamCash' AND currency=NEW.payment_currency AND enabled=TRUE LIMIT 1;
                IF NOT FOUND THEN RAISE EXCEPTION 'invalid or disabled payment method for order currency' USING ERRCODE='23514'; END IF;
            END IF;
            IF NOT FOUND THEN RAISE EXCEPTION 'no enabled ShamCash payment method for order currency' USING ERRCODE='23514'; END IF;
            IF method_row.recipient_name IS NULL OR btrim(method_row.recipient_name) = '' THEN RAISE EXCEPTION 'ShamCash recipient name is not configured' USING ERRCODE='23514'; END IF;
            IF method_row.account_identifier IS NULL OR btrim(method_row.account_identifier) = '' THEN RAISE EXCEPTION 'ShamCash receiving address is not configured' USING ERRCODE='23514'; END IF;
            IF method_row.qr_photo_id IS NULL OR btrim(method_row.qr_photo_id) = '' THEN RAISE EXCEPTION 'ShamCash payment QR is not configured' USING ERRCODE='23514'; END IF;
            NEW.payment_method_code := method_row.code;
            NEW.payment_recipient_name_snapshot := method_row.recipient_name;
            NEW.payment_account_snapshot := method_row.account_identifier;
            NEW.payment_qr_photo_id := method_row.qr_photo_id;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)
    await conn.execute("DROP TRIGGER IF EXISTS trg_snapshot_order_payment_method ON orders")
    await conn.execute("""CREATE TRIGGER trg_snapshot_order_payment_method
        BEFORE INSERT ON orders FOR EACH ROW EXECUTE FUNCTION snapshot_order_payment_method()""")

    await conn.execute("""
        CREATE OR REPLACE FUNCTION protect_order_payment_snapshot()
        RETURNS TRIGGER AS $$
        BEGIN
            IF NEW.payment_method_code IS DISTINCT FROM OLD.payment_method_code
               OR NEW.payment_recipient_name_snapshot IS DISTINCT FROM OLD.payment_recipient_name_snapshot
               OR NEW.payment_account_snapshot IS DISTINCT FROM OLD.payment_account_snapshot
               OR NEW.payment_qr_photo_id IS DISTINCT FROM OLD.payment_qr_photo_id THEN
                RAISE EXCEPTION 'order payment snapshot is immutable' USING ERRCODE='23514';
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)
    await conn.execute("DROP TRIGGER IF EXISTS trg_protect_order_payment_snapshot ON orders")
    await conn.execute("""CREATE TRIGGER trg_protect_order_payment_snapshot
        BEFORE UPDATE OF payment_method_code, payment_recipient_name_snapshot, payment_account_snapshot, payment_qr_photo_id
        ON orders FOR EACH ROW EXECUTE FUNCTION protect_order_payment_snapshot()""")

    await conn.execute("""
        CREATE OR REPLACE FUNCTION protect_order_payment_deadline()
        RETURNS TRIGGER AS $$
        BEGIN
            IF TG_OP = 'UPDATE' AND OLD.payment_deadline IS NOT NULL
               AND NEW.payment_deadline IS DISTINCT FROM OLD.payment_deadline
               AND NEW.status <> 'pending' THEN
                RAISE EXCEPTION 'payment deadline is immutable once assigned' USING ERRCODE='23514';
            END IF;
            IF NEW.payment_deadline IS NOT NULL AND NEW.approved_at IS NOT NULL
               AND NEW.payment_deadline < NEW.approved_at THEN
                RAISE EXCEPTION 'payment deadline cannot precede approval time' USING ERRCODE='23514';
            END IF;
            IF NEW.payment_deadline IS NOT NULL AND NEW.created_at IS NOT NULL
               AND NEW.payment_deadline < NEW.created_at THEN
                RAISE EXCEPTION 'payment deadline cannot precede order creation time' USING ERRCODE='23514';
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)
    await conn.execute("DROP TRIGGER IF EXISTS trg_protect_order_payment_deadline ON orders")
    await conn.execute("""CREATE TRIGGER trg_protect_order_payment_deadline
        BEFORE INSERT OR UPDATE OF payment_deadline, approved_at, created_at, status
        ON orders FOR EACH ROW EXECUTE FUNCTION protect_order_payment_deadline()""")

    await conn.execute("""
        CREATE OR REPLACE FUNCTION protect_receipt_submission()
        RETURNS TRIGGER AS $$
        BEGIN
            IF (NEW.receipt_photo_id IS DISTINCT FROM OLD.receipt_photo_id
                OR NEW.receipt_upload_count IS DISTINCT FROM OLD.receipt_upload_count)
               AND OLD.status <> 'waiting_payment'
               AND NEW.status <> 'receipt_received' THEN
                RAISE EXCEPTION 'receipt submission is not allowed for this order state' USING ERRCODE='23514';
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)
    await conn.execute("DROP TRIGGER IF EXISTS trg_protect_receipt_submission ON orders")
    await conn.execute("""CREATE TRIGGER trg_protect_receipt_submission
        BEFORE UPDATE OF receipt_photo_id, receipt_upload_count, status
        ON orders FOR EACH ROW EXECUTE FUNCTION protect_receipt_submission()""")

    await conn.execute("""
        CREATE OR REPLACE FUNCTION prevent_active_order_deletion()
        RETURNS TRIGGER AS $$
        BEGIN
            IF OLD.status IN ('pending', 'waiting_payment', 'receipt_received', 'payment_confirmed') THEN
                RAISE EXCEPTION 'active order prevents customer deletion: %', OLD.order_number USING ERRCODE='23514';
            END IF;
            RETURN OLD;
        END;
        $$ LANGUAGE plpgsql;
    """)
    await conn.execute("DROP TRIGGER IF EXISTS trg_prevent_active_order_deletion ON orders")
    await conn.execute("""CREATE TRIGGER trg_prevent_active_order_deletion
        BEFORE DELETE ON orders
        FOR EACH ROW EXECUTE FUNCTION prevent_active_order_deletion()""")

    await conn.execute("""
        DELETE FROM saved_addresses
        WHERE id IN (
            SELECT id FROM (
                SELECT id,
                       ROW_NUMBER() OVER (PARTITION BY user_id ORDER BY is_default DESC, created_at ASC, id ASC) AS rn
                FROM saved_addresses
                WHERE deleted_at IS NULL AND is_default = TRUE
            ) ranked
            WHERE ranked.rn > 1
        )
    """)
    await conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS uq_saved_addresses_one_default ON saved_addresses (user_id) WHERE deleted_at IS NULL AND is_default = TRUE")

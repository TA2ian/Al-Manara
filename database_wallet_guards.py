"""Database-level guards for immutable, verified customer wallet snapshots."""


async def install_order_wallet_guard(conn):
    """Protect order wallet snapshots at the database boundary.

    A new order must reference a verified, non-deleted wallet with the exact
    stored QR. Once the order exists, its wallet snapshot cannot be changed.
    This protects historical orders even if the saved wallet is later deleted.
    """
    await conn.execute("""
        CREATE OR REPLACE FUNCTION enforce_order_wallet_snapshot()
        RETURNS TRIGGER AS $$
        DECLARE wallet_row RECORD;
        BEGIN
            IF TG_OP = 'UPDATE' THEN
                IF NEW.user_id IS DISTINCT FROM OLD.user_id
                   OR NEW.wallet_address IS DISTINCT FROM OLD.wallet_address
                   OR NEW.network IS DISTINCT FROM OLD.network
                   OR NEW.wallet_qr_photo_id IS DISTINCT FROM OLD.wallet_qr_photo_id THEN
                    RAISE EXCEPTION 'order wallet snapshot is immutable' USING ERRCODE='23514';
                END IF;
                RETURN NEW;
            END IF;

            IF NEW.user_id IS NULL THEN
                RAISE EXCEPTION 'order user_id is required for wallet validation' USING ERRCODE='23514';
            END IF;

            SELECT id, address, network, qr_photo_id, verification_status, deleted_at
              INTO wallet_row
              FROM saved_addresses
             WHERE user_id = NEW.user_id
               AND address = NEW.wallet_address
               AND network = NEW.network
               AND deleted_at IS NULL
             ORDER BY id ASC
             LIMIT 1;

            IF NOT FOUND THEN
                RAISE EXCEPTION 'order wallet is not registered for this user' USING ERRCODE='23514';
            END IF;

            IF wallet_row.verification_status <> 'verified' THEN
                RAISE EXCEPTION 'order wallet is not verified' USING ERRCODE='23514';
            END IF;

            IF wallet_row.qr_photo_id IS NULL OR btrim(wallet_row.qr_photo_id) = '' THEN
                RAISE EXCEPTION 'verified order wallet must have a stored QR' USING ERRCODE='23514';
            END IF;

            IF NEW.wallet_qr_photo_id IS DISTINCT FROM wallet_row.qr_photo_id THEN
                RAISE EXCEPTION 'order wallet QR does not match the verified saved wallet' USING ERRCODE='23514';
            END IF;

            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)
    await conn.execute("DROP TRIGGER IF EXISTS trg_enforce_order_wallet_snapshot ON orders")
    await conn.execute("""
        CREATE TRIGGER trg_enforce_order_wallet_snapshot
        BEFORE INSERT OR UPDATE OF user_id, wallet_address, network, wallet_qr_photo_id ON orders
        FOR EACH ROW EXECUTE FUNCTION enforce_order_wallet_snapshot()
    """)

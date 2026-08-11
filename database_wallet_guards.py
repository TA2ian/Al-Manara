"""Database-level guards for immutable, verified customer wallet snapshots."""


async def install_order_wallet_guard(conn):
    """Prevent new orders from using an unverified/mismatched saved wallet.

    The application layer selects a verified wallet and stores its address/network/QR
    in the order. This trigger is defense-in-depth: direct SQL or a future handler
    cannot create a new order with a wallet that is not owned by the user, verified,
    non-deleted, and backed by the exact stored QR.
    """
    await conn.execute("""
        CREATE OR REPLACE FUNCTION enforce_order_wallet_snapshot()
        RETURNS TRIGGER AS $$
        DECLARE wallet_row RECORD;
        BEGIN
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
        BEFORE INSERT ON orders
        FOR EACH ROW EXECUTE FUNCTION enforce_order_wallet_snapshot()
    """)

"""Database invariants for controlled receipt-retry deadline extensions."""


async def install_receipt_retry_constraints(conn) -> None:
    """Allow only the canonical five-minute retry extension after receipt rejection."""
    await conn.execute(
        """
        CREATE OR REPLACE FUNCTION protect_order_payment_deadline()
        RETURNS TRIGGER AS $$
        BEGIN
            IF TG_OP = 'UPDATE'
               AND OLD.payment_deadline IS NOT NULL
               AND NEW.payment_deadline IS DISTINCT FROM OLD.payment_deadline
            THEN
                IF OLD.status = 'receipt_received'
                   AND NEW.status = 'waiting_payment'
                   AND NEW.payment_deadline > CURRENT_TIMESTAMP
                   AND NEW.payment_deadline <= CURRENT_TIMESTAMP + INTERVAL '6 minutes'
                THEN
                    NULL;
                ELSIF NEW.status <> 'pending' THEN
                    RAISE EXCEPTION 'payment deadline is immutable outside canonical order transitions' USING ERRCODE='23514';
                END IF;
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
        """
    )
    await conn.execute("DROP TRIGGER IF EXISTS trg_protect_order_payment_deadline ON orders")
    await conn.execute(
        """
        CREATE TRIGGER trg_protect_order_payment_deadline
        BEFORE INSERT OR UPDATE OF payment_deadline, approved_at, created_at, status
        ON orders FOR EACH ROW EXECUTE FUNCTION protect_order_payment_deadline()
        """
    )

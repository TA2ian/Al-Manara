"""Canonical PostgreSQL order-state trigger synchronized with the service graph."""


async def install_order_state_constraints(conn):
    """Replace the legacy database state trigger with the authoritative lifecycle graph."""
    await conn.execute(
        """
        CREATE OR REPLACE FUNCTION enforce_order_state_transition()
        RETURNS TRIGGER AS $$
        BEGIN
            IF NEW.status IS DISTINCT FROM OLD.status THEN
                IF NOT (
                    (OLD.status = 'pending' AND NEW.status IN ('waiting_payment', 'rejected', 'expired'))
                    OR (OLD.status = 'waiting_payment' AND NEW.status IN ('receipt_received', 'rejected', 'expired', 'pending'))
                    OR (OLD.status = 'receipt_received' AND NEW.status IN ('waiting_payment', 'payment_confirmed', 'rejected'))
                    OR (OLD.status = 'payment_confirmed' AND NEW.status IN ('completed', 'closed_without_fulfillment'))
                ) THEN
                    RAISE EXCEPTION 'invalid order state transition: % -> %', OLD.status, NEW.status USING ERRCODE = 'P0001';
                END IF;
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    await conn.execute("DROP TRIGGER IF EXISTS trg_enforce_order_state_transition ON orders")
    await conn.execute(
        """
        CREATE TRIGGER trg_enforce_order_state_transition
        BEFORE UPDATE OF status ON orders
        FOR EACH ROW EXECUTE FUNCTION enforce_order_state_transition()
        """
    )

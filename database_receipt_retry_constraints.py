"""Database invariants for controlled receipt-retry deadline extensions."""


async def install_receipt_retry_constraints(conn) -> None:
    """Allow only canonical receipt retry extensions and valid receipt submissions."""
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

    await conn.execute(
        """
        CREATE OR REPLACE FUNCTION protect_receipt_submission_window()
        RETURNS TRIGGER AS $$
        BEGIN
            IF TG_OP = 'UPDATE'
               AND (
                    NEW.receipt_photo_id IS DISTINCT FROM OLD.receipt_photo_id
                    OR NEW.receipt_upload_count IS DISTINCT FROM OLD.receipt_upload_count
               )
            THEN
                IF NEW.status = 'waiting_payment'
                   AND NEW.payment_deadline IS NOT NULL
                   AND NEW.payment_deadline > CURRENT_TIMESTAMP
                THEN
                    RETURN NEW;
                END IF;

                IF OLD.status = 'waiting_payment'
                   AND NEW.status = 'receipt_received'
                THEN
                    RETURN NEW;
                END IF;

                RAISE EXCEPTION 'receipt submission is not allowed outside the active payment window' USING ERRCODE='23514';
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    await conn.execute("DROP TRIGGER IF EXISTS trg_protect_receipt_submission_window ON orders")
    await conn.execute(
        """
        CREATE TRIGGER trg_protect_receipt_submission_window
        BEFORE UPDATE OF receipt_photo_id, receipt_upload_count, status, payment_deadline
        ON orders FOR EACH ROW EXECUTE FUNCTION protect_receipt_submission_window()
        """
    )

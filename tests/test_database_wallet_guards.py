"""Integration tests for the PostgreSQL wallet/order security boundary.

These tests are intentionally skipped unless TEST_DATABASE_URL is configured.
The CI environment enables them with a disposable PostgreSQL service.
"""
import os
import unittest


@unittest.skipUnless(os.getenv("TEST_DATABASE_URL"), "TEST_DATABASE_URL is not configured")
class DatabaseWalletGuardTests(unittest.IsolatedAsyncioTestCase):
    SCHEMA = "almanara_guard_test"

    async def asyncSetUp(self):
        import asyncpg

        self.pool = await asyncpg.create_pool(os.environ["TEST_DATABASE_URL"], min_size=1, max_size=2)
        async with self.pool.acquire() as conn:
            await conn.execute(f"DROP SCHEMA IF EXISTS {self.SCHEMA} CASCADE")
            await conn.execute(f"CREATE SCHEMA {self.SCHEMA}")
            await conn.execute(f"SET search_path TO {self.SCHEMA}")
            await conn.execute("""
                CREATE TABLE users (
                    id SERIAL PRIMARY KEY,
                    telegram_id BIGINT UNIQUE NOT NULL
                )
            """)
            await conn.execute("""
                CREATE TABLE saved_addresses (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER REFERENCES users(id),
                    address TEXT NOT NULL,
                    network TEXT NOT NULL,
                    qr_photo_id TEXT,
                    verification_status TEXT DEFAULT 'pending',
                    deleted_at TIMESTAMP
                )
            """)
            await conn.execute("""
                CREATE TABLE orders (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER REFERENCES users(id),
                    wallet_address TEXT NOT NULL,
                    network TEXT NOT NULL,
                    wallet_qr_photo_id TEXT,
                    status TEXT DEFAULT 'pending'
                )
            """)
            await conn.execute("""
                CREATE FUNCTION protect_verified_wallet()
                RETURNS TRIGGER AS $$
                BEGIN
                    IF TG_OP = 'UPDATE' AND OLD.verification_status = 'verified' THEN
                        IF NEW.address IS DISTINCT FROM OLD.address
                           OR NEW.network IS DISTINCT FROM OLD.network
                           OR NEW.qr_photo_id IS DISTINCT FROM OLD.qr_photo_id
                           OR NEW.verification_status IS DISTINCT FROM OLD.verification_status THEN
                            RAISE EXCEPTION 'Verified wallet is immutable';
                        END IF;
                    END IF;
                    IF TG_OP = 'DELETE' THEN
                        IF EXISTS (SELECT 1 FROM orders WHERE user_id = OLD.user_id AND wallet_address = OLD.address
                                  AND network = OLD.network AND status IN ('pending','waiting_payment','receipt_received','payment_confirmed')) THEN
                            RAISE EXCEPTION 'Wallet is linked to an active order';
                        END IF;
                        RETURN OLD;
                    END IF;
                    RETURN NEW;
                END;
                $$ LANGUAGE plpgsql;
                CREATE TRIGGER trg_protect_verified_wallet
                BEFORE UPDATE OR DELETE ON saved_addresses
                FOR EACH ROW EXECUTE FUNCTION protect_verified_wallet();
            """)
            await conn.execute("""
                CREATE FUNCTION validate_order_wallet()
                RETURNS TRIGGER AS $$
                BEGIN
                    IF NOT EXISTS (
                        SELECT 1 FROM saved_addresses w
                        WHERE w.user_id = NEW.user_id
                          AND w.address = NEW.wallet_address
                          AND w.network = NEW.network
                          AND w.verification_status = 'verified'
                          AND w.deleted_at IS NULL
                          AND w.qr_photo_id IS NOT NULL
                          AND w.qr_photo_id = NEW.wallet_qr_photo_id
                    ) THEN
                        RAISE EXCEPTION 'Order wallet must be a verified wallet with matching stored QR';
                    END IF;
                    RETURN NEW;
                END;
                $$ LANGUAGE plpgsql;
                CREATE TRIGGER trg_validate_order_wallet
                BEFORE INSERT OR UPDATE OF user_id, wallet_address, network, wallet_qr_photo_id ON orders
                FOR EACH ROW EXECUTE FUNCTION validate_order_wallet();
            """)
            await conn.execute("INSERT INTO users (telegram_id) VALUES (1001), (1002)")
            await conn.execute("""INSERT INTO saved_addresses
                (user_id,address,network,qr_photo_id,verification_status)
                VALUES (1,'0xGOOD','BEP20','qr-good','verified')""")

    async def asyncTearDown(self):
        await self.pool.close()
        import asyncpg
        conn = await asyncpg.connect(os.environ["TEST_DATABASE_URL"])
        try:
            await conn.execute(f"DROP SCHEMA IF EXISTS {self.SCHEMA} CASCADE")
        finally:
            await conn.close()

    async def _execute(self, sql, *args):
        async with self.pool.acquire() as conn:
            await conn.execute(f"SET search_path TO {self.SCHEMA}")
            return await conn.execute(sql, *args)

    async def _fetchval(self, sql, *args):
        async with self.pool.acquire() as conn:
            await conn.execute(f"SET search_path TO {self.SCHEMA}")
            return await conn.fetchval(sql, *args)

    async def _insert_order(self, **kwargs):
        defaults = dict(user_id=1, wallet_address="0xGOOD", network="BEP20", wallet_qr_photo_id="qr-good")
        defaults.update(kwargs)
        await self._execute(
            """INSERT INTO orders
                (user_id,wallet_address,network,wallet_qr_photo_id)
                VALUES ($1,$2,$3,$4)""",
            defaults["user_id"], defaults["wallet_address"], defaults["network"], defaults["wallet_qr_photo_id"]
        )

    async def test_verified_wallet_with_matching_qr_is_accepted(self):
        await self._insert_order()

    async def test_pending_wallet_is_rejected(self):
        await self._execute("""INSERT INTO saved_addresses
            (user_id,address,network,qr_photo_id,verification_status)
            VALUES (1,'0xPENDING','BEP20','qr-pending','pending')""")
        with self.assertRaises(Exception):
            await self._insert_order(wallet_address="0xPENDING", wallet_qr_photo_id="qr-pending")

    async def test_missing_qr_is_rejected(self):
        await self._execute("""INSERT INTO saved_addresses
            (user_id,address,network,qr_photo_id,verification_status)
            VALUES (1,'0xNOQR','TRC20',NULL,'verified')""")
        with self.assertRaises(Exception):
            await self._insert_order(wallet_address="0xNOQR", network="TRC20", wallet_qr_photo_id=None)

    async def test_mismatched_qr_is_rejected(self):
        with self.assertRaises(Exception):
            await self._insert_order(wallet_qr_photo_id="qr-other")

    async def test_other_users_wallet_is_rejected(self):
        with self.assertRaises(Exception):
            await self._insert_order(user_id=2)

    async def test_verified_wallet_cannot_be_modified(self):
        with self.assertRaises(Exception):
            await self._execute("UPDATE saved_addresses SET address='0xCHANGED' WHERE id=1")

    async def test_verified_wallet_qr_cannot_be_modified(self):
        with self.assertRaises(Exception):
            await self._execute("UPDATE saved_addresses SET qr_photo_id='qr-changed' WHERE id=1")

    async def test_verified_wallet_cannot_be_deleted_while_order_is_active(self):
        await self._insert_order()
        with self.assertRaises(Exception):
            await self._execute("DELETE FROM saved_addresses WHERE id=1")

    async def test_verified_wallet_can_be_deleted_when_not_linked_to_active_order(self):
        await self._execute("DELETE FROM saved_addresses WHERE id=1")
        remaining = await self._fetchval("SELECT COUNT(*) FROM saved_addresses WHERE id=1")
        self.assertEqual(remaining, 0)


if __name__ == "__main__":
    unittest.main()

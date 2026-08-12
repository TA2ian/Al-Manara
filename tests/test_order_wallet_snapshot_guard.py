"""PostgreSQL integration coverage for immutable order wallet snapshots."""
import os
import unittest


@unittest.skipUnless(os.getenv("TEST_DATABASE_URL"), "TEST_DATABASE_URL is not configured")
class OrderWalletSnapshotGuardTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        import asyncpg

        self.pool = await asyncpg.create_pool(os.environ["TEST_DATABASE_URL"], min_size=1, max_size=2)
        async with self.pool.acquire() as conn:
            await conn.execute("DROP SCHEMA IF EXISTS order_snapshot_guard_test CASCADE")
            await conn.execute("CREATE SCHEMA order_snapshot_guard_test")
            await conn.execute("SET search_path TO order_snapshot_guard_test")
            await conn.execute("""
                CREATE TABLE saved_addresses (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    address TEXT NOT NULL,
                    network TEXT NOT NULL,
                    qr_photo_id TEXT,
                    verification_status TEXT NOT NULL DEFAULT 'pending',
                    deleted_at TIMESTAMP
                )
            """)
            await conn.execute("""
                CREATE TABLE orders (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    wallet_address TEXT NOT NULL,
                    network TEXT NOT NULL,
                    wallet_qr_photo_id TEXT
                )
            """)
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
                            RAISE EXCEPTION 'order wallet snapshot is immutable';
                        END IF;
                        RETURN NEW;
                    END IF;

                    SELECT id, address, network, qr_photo_id, verification_status, deleted_at
                      INTO wallet_row
                      FROM saved_addresses
                     WHERE user_id = NEW.user_id
                       AND address = NEW.wallet_address
                       AND network = NEW.network
                       AND deleted_at IS NULL
                     LIMIT 1;

                    IF NOT FOUND OR wallet_row.verification_status <> 'verified'
                       OR wallet_row.qr_photo_id IS NULL
                       OR btrim(wallet_row.qr_photo_id) = ''
                       OR NEW.wallet_qr_photo_id IS DISTINCT FROM wallet_row.qr_photo_id THEN
                        RAISE EXCEPTION 'invalid order wallet snapshot';
                    END IF;
                    RETURN NEW;
                END;
                $$ LANGUAGE plpgsql;
                CREATE TRIGGER trg_enforce_order_wallet_snapshot
                BEFORE INSERT OR UPDATE OF user_id, wallet_address, network, wallet_qr_photo_id ON orders
                FOR EACH ROW EXECUTE FUNCTION enforce_order_wallet_snapshot();
            """)
            await conn.execute("""INSERT INTO saved_addresses
                (user_id,address,network,qr_photo_id,verification_status)
                VALUES (1,'0xGOOD','BEP20','qr-good','verified')""")

    async def asyncTearDown(self):
        async with self.pool.acquire() as conn:
            await conn.execute("DROP SCHEMA IF EXISTS order_snapshot_guard_test CASCADE")
        await self.pool.close()

    async def test_valid_snapshot_is_accepted(self):
        async with self.pool.acquire() as conn:
            await conn.execute("""INSERT INTO orders
                (user_id,wallet_address,network,wallet_qr_photo_id)
                VALUES (1,'0xGOOD','BEP20','qr-good')""")

    async def test_address_cannot_change_after_creation(self):
        async with self.pool.acquire() as conn:
            order_id = await conn.fetchval("""INSERT INTO orders
                (user_id,wallet_address,network,wallet_qr_photo_id)
                VALUES (1,'0xGOOD','BEP20','qr-good') RETURNING id""")
            with self.assertRaises(Exception):
                await conn.execute("UPDATE orders SET wallet_address='0xOTHER' WHERE id=$1", order_id)

    async def test_network_cannot_change_after_creation(self):
        async with self.pool.acquire() as conn:
            order_id = await conn.fetchval("""INSERT INTO orders
                (user_id,wallet_address,network,wallet_qr_photo_id)
                VALUES (1,'0xGOOD','BEP20','qr-good') RETURNING id""")
            with self.assertRaises(Exception):
                await conn.execute("UPDATE orders SET network='TRC20' WHERE id=$1", order_id)

    async def test_qr_cannot_change_after_creation(self):
        async with self.pool.acquire() as conn:
            order_id = await conn.fetchval("""INSERT INTO orders
                (user_id,wallet_address,network,wallet_qr_photo_id)
                VALUES (1,'0xGOOD','BEP20','qr-good') RETURNING id""")
            with self.assertRaises(Exception):
                await conn.execute("UPDATE orders SET wallet_qr_photo_id='qr-other' WHERE id=$1", order_id)

    async def test_non_wallet_order_updates_remain_possible(self):
        async with self.pool.acquire() as conn:
            await conn.execute("ALTER TABLE orders ADD COLUMN status TEXT DEFAULT 'pending'")
            order_id = await conn.fetchval("""INSERT INTO orders
                (user_id,wallet_address,network,wallet_qr_photo_id)
                VALUES (1,'0xGOOD','BEP20','qr-good') RETURNING id""")
            await conn.execute("UPDATE orders SET status='waiting_payment' WHERE id=$1", order_id)

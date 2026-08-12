"""PostgreSQL integration tests for order payment snapshots."""
import os
import unittest


@unittest.skipUnless(os.getenv("TEST_DATABASE_URL"), "TEST_DATABASE_URL is not configured")
class PaymentSnapshotGuardTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        import asyncpg
        from database_wallet_guards import install_order_wallet_guard

        self.pool = await asyncpg.create_pool(
            os.environ["TEST_DATABASE_URL"], min_size=1, max_size=2,
            server_settings={"search_path": "payment_guard_test"},
        )
        async with self.pool.acquire() as conn:
            await conn.execute("DROP SCHEMA IF EXISTS payment_guard_test CASCADE")
            await conn.execute("CREATE SCHEMA payment_guard_test")
            await conn.execute("SET search_path TO payment_guard_test")
            await conn.execute("""CREATE TABLE users (
                id SERIAL PRIMARY KEY, telegram_id BIGINT UNIQUE NOT NULL,
                is_verified BOOLEAN DEFAULT FALSE, phone_verified BOOLEAN DEFAULT FALSE,
                phone_number TEXT, terms_accepted BOOLEAN DEFAULT FALSE
            )""")
            await conn.execute("""CREATE TABLE saved_addresses (
                id SERIAL PRIMARY KEY, user_id INTEGER REFERENCES users(id), address TEXT NOT NULL,
                network TEXT NOT NULL, qr_photo_id TEXT, verification_status TEXT DEFAULT 'pending', deleted_at TIMESTAMP)""")
            await conn.execute("""CREATE TABLE payment_methods (
                id SERIAL PRIMARY KEY, code TEXT UNIQUE NOT NULL, provider TEXT NOT NULL, currency TEXT NOT NULL,
                account_identifier TEXT NOT NULL DEFAULT '', qr_photo_id TEXT, enabled BOOLEAN DEFAULT TRUE)""")
            await conn.execute("""CREATE TABLE orders (
                id SERIAL PRIMARY KEY, user_id INTEGER REFERENCES users(id), wallet_address TEXT NOT NULL,
                network TEXT NOT NULL, wallet_qr_photo_id TEXT, payment_currency TEXT NOT NULL,
                payment_method_code TEXT, payment_account_snapshot TEXT, payment_qr_photo_id TEXT, status TEXT DEFAULT 'pending')""")
            await conn.execute("""INSERT INTO users
                (telegram_id,is_verified,phone_verified,phone_number,terms_accepted)
                VALUES (2001,TRUE,TRUE,'+10000000000',TRUE)""")
            await conn.execute("""INSERT INTO saved_addresses
                (user_id,address,network,qr_photo_id,verification_status)
                VALUES (1,'0xPAY','BEP20','wallet-qr','verified')""")
            await conn.execute("""INSERT INTO payment_methods
                (code,provider,currency,account_identifier,qr_photo_id,enabled)
                VALUES ('shamcash_new_syp','ShamCash','NEW.SYP','ACCOUNT-A','payment-qr-a',TRUE)""")
            await install_order_wallet_guard(conn)

    async def asyncTearDown(self):
        async with self.pool.acquire() as conn:
            await conn.execute("DROP SCHEMA IF EXISTS payment_guard_test CASCADE")
        await self.pool.close()

    async def _insert_order(self):
        async with self.pool.acquire() as conn:
            return await conn.fetchrow("""INSERT INTO orders
                (user_id,wallet_address,network,wallet_qr_photo_id,payment_currency)
                VALUES (1,'0xPAY','BEP20','wallet-qr','NEW.SYP') RETURNING *""")

    async def test_payment_method_is_snapshotted_on_insert(self):
        row = await self._insert_order()
        self.assertEqual(row["payment_method_code"], "shamcash_new_syp")
        self.assertEqual(row["payment_account_snapshot"], "ACCOUNT-A")
        self.assertEqual(row["payment_qr_photo_id"], "payment-qr-a")

    async def test_snapshot_is_immutable(self):
        row = await self._insert_order()
        with self.assertRaises(Exception):
            async with self.pool.acquire() as conn:
                await conn.execute("UPDATE orders SET payment_account_snapshot='ACCOUNT-B' WHERE id=$1", row["id"])

    async def test_changed_payment_method_does_not_change_existing_order(self):
        row = await self._insert_order()
        async with self.pool.acquire() as conn:
            await conn.execute("UPDATE payment_methods SET account_identifier='ACCOUNT-B', qr_photo_id='payment-qr-b' WHERE code='shamcash_new_syp'")
            current = await conn.fetchrow("SELECT payment_account_snapshot,payment_qr_photo_id FROM orders WHERE id=$1", row["id"])
        self.assertEqual(current["payment_account_snapshot"], "ACCOUNT-A")
        self.assertEqual(current["payment_qr_photo_id"], "payment-qr-a")

    async def test_disabled_explicit_payment_method_is_rejected(self):
        async with self.pool.acquire() as conn:
            await conn.execute("UPDATE payment_methods SET enabled=FALSE WHERE code='shamcash_new_syp'")
        with self.assertRaises(Exception):
            await self._insert_order()

    async def test_legacy_syp_is_normalized_to_new_syp(self):
        row = await self._insert_order()
        async with self.pool.acquire() as conn:
            current = await conn.fetchval("SELECT payment_currency FROM orders WHERE id=$1", row["id"])
        self.assertEqual(current, "NEW.SYP")


if __name__ == "__main__":
    unittest.main()

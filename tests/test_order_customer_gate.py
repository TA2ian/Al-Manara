"""Database integration tests for the canonical order customer gate."""
import os
import unittest


@unittest.skipUnless(os.getenv("TEST_DATABASE_URL"), "TEST_DATABASE_URL is not configured")
class OrderCustomerGateTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        import asyncpg
        from database_order_constraints import install_order_constraints

        self.pool = await asyncpg.create_pool(
            os.environ["TEST_DATABASE_URL"],
            min_size=1,
            max_size=2,
            server_settings={"search_path": "almanara_customer_gate_test,public"},
        )
        async with self.pool.acquire() as conn:
            await conn.execute("DROP SCHEMA IF EXISTS almanara_customer_gate_test CASCADE")
            await conn.execute("CREATE SCHEMA almanara_customer_gate_test")
            await conn.execute("SET search_path TO almanara_customer_gate_test, public")
            await conn.execute("""
                CREATE TABLE users (
                    id SERIAL PRIMARY KEY,
                    telegram_id BIGINT UNIQUE NOT NULL,
                    is_verified BOOLEAN DEFAULT FALSE,
                    phone_verified BOOLEAN DEFAULT FALSE,
                    phone_number TEXT,
                    terms_accepted BOOLEAN DEFAULT FALSE
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
                CREATE TABLE payment_methods (
                    id SERIAL PRIMARY KEY,
                    code TEXT,
                    provider TEXT,
                    currency TEXT,
                    enabled BOOLEAN DEFAULT TRUE,
                    account_identifier TEXT,
                    qr_photo_id TEXT
                )
            """)
            await conn.execute("""
                CREATE TABLE orders (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER REFERENCES users(id),
                    wallet_address TEXT NOT NULL,
                    network TEXT NOT NULL,
                    wallet_qr_photo_id TEXT,
                    status TEXT DEFAULT 'pending',
                    payment_currency TEXT DEFAULT 'USD',
                    payment_method_code TEXT,
                    payment_account_snapshot TEXT,
                    payment_qr_photo_id TEXT
                )
            """)
            await conn.execute("""
                INSERT INTO payment_methods(
                    code, provider, currency, enabled, account_identifier, qr_photo_id
                ) VALUES ('SHAM_USD', 'ShamCash', 'USD', TRUE, 'acct', 'payqr')
            """)
            await conn.execute("""
                INSERT INTO users(
                    telegram_id, is_verified, phone_verified, phone_number, terms_accepted
                ) VALUES (1001, FALSE, FALSE, NULL, FALSE)
            """)
            await conn.execute("""
                INSERT INTO saved_addresses(
                    user_id, address, network, qr_photo_id, verification_status
                ) VALUES (1, '0xGOOD', 'BEP20', 'walletqr', 'verified')
            """)
            await install_order_constraints(conn)

    async def asyncTearDown(self):
        async with self.pool.acquire() as conn:
            await conn.execute("DROP SCHEMA IF EXISTS almanara_customer_gate_test CASCADE")
        await self.pool.close()

    async def _insert_order(self):
        async with self.pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO orders(
                    user_id, wallet_address, network, wallet_qr_photo_id, payment_currency
                ) VALUES (1, '0xGOOD', 'BEP20', 'walletqr', 'USD')
            """)

    async def test_unverified_customer_is_rejected(self):
        with self.assertRaises(Exception):
            await self._insert_order()

    async def test_verified_customer_with_verified_phone_and_terms_is_accepted(self):
        async with self.pool.acquire() as conn:
            await conn.execute("""
                UPDATE users
                   SET is_verified=TRUE,
                       phone_verified=TRUE,
                       phone_number='+10000000000',
                       terms_accepted=TRUE
                 WHERE id=1
            """)
        await self._insert_order()

    async def test_verified_without_phone_is_rejected(self):
        async with self.pool.acquire() as conn:
            await conn.execute("""
                UPDATE users
                   SET is_verified=TRUE,
                       terms_accepted=TRUE
                 WHERE id=1
            """)
        with self.assertRaises(Exception):
            await self._insert_order()

    async def test_verified_without_terms_is_rejected(self):
        async with self.pool.acquire() as conn:
            await conn.execute("""
                UPDATE users
                   SET is_verified=TRUE,
                       phone_verified=TRUE,
                       phone_number='+10000000000'
                 WHERE id=1
            """)
        with self.assertRaises(Exception):
            await self._insert_order()

    async def test_wallet_qr_cannot_be_cleared_after_order_creation(self):
        async with self.pool.acquire() as conn:
            await conn.execute("""
                UPDATE users
                   SET is_verified=TRUE,
                       phone_verified=TRUE,
                       phone_number='+10000000000',
                       terms_accepted=TRUE
                 WHERE id=1
            """)
        await self._insert_order()
        async with self.pool.acquire() as conn:
            with self.assertRaises(Exception):
                await conn.execute("""
                    UPDATE orders
                       SET wallet_qr_photo_id=NULL
                     WHERE id=1
                """)
            qr = await conn.fetchval(
                "SELECT wallet_qr_photo_id FROM orders WHERE id=1"
            )
        self.assertEqual(qr, "walletqr")


if __name__ == '__main__':
    unittest.main()

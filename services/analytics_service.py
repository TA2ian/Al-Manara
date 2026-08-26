"""Centralized operational and financial analytics queries."""
from __future__ import annotations

from database import get_pool


ACTIVE_STATUSES = (
    "pending",
    "waiting_payment",
    "receipt_received",
    "payment_confirmed",
)


class AnalyticsService:
    """Own analytics aggregation so handlers remain presentation-only."""

    @classmethod
    async def dashboard(cls) -> dict:
        pool = await get_pool()
        if not pool:
            raise RuntimeError("Database pool is not initialized")

        async with pool.acquire() as conn:
            periods = await conn.fetchrow(
                """SELECT
                    COUNT(*) FILTER (WHERE created_at >= CURRENT_DATE) AS today_orders,
                    COUNT(*) FILTER (WHERE created_at >= CURRENT_DATE AND status = 'completed') AS today_completed,
                    COALESCE(SUM(amount_usdt) FILTER (WHERE created_at >= CURRENT_DATE), 0) AS today_usdt,
                    COALESCE(SUM(fee_amount) FILTER (WHERE created_at >= CURRENT_DATE), 0) AS today_fees,
                    COUNT(*) FILTER (WHERE created_at >= CURRENT_DATE - INTERVAL '7 days') AS week_orders,
                    COUNT(*) FILTER (WHERE created_at >= CURRENT_DATE - INTERVAL '7 days' AND status = 'completed') AS week_completed,
                    COALESCE(SUM(amount_usdt) FILTER (WHERE created_at >= CURRENT_DATE - INTERVAL '7 days'), 0) AS week_usdt,
                    COALESCE(SUM(fee_amount) FILTER (WHERE created_at >= CURRENT_DATE - INTERVAL '7 days'), 0) AS week_fees,
                    COUNT(*) FILTER (WHERE created_at >= DATE_TRUNC('month', CURRENT_DATE)) AS month_orders,
                    COUNT(*) FILTER (WHERE created_at >= DATE_TRUNC('month', CURRENT_DATE) AND status = 'completed') AS month_completed,
                    COALESCE(SUM(amount_usdt) FILTER (WHERE created_at >= DATE_TRUNC('month', CURRENT_DATE)), 0) AS month_usdt,
                    COALESCE(SUM(fee_amount) FILTER (WHERE created_at >= DATE_TRUNC('month', CURRENT_DATE)), 0) AS month_fees
                   FROM orders"""
            )
            states = await conn.fetch(
                """SELECT status, COUNT(*) AS count, COALESCE(SUM(amount_usdt), 0) AS usdt
                   FROM orders
                  WHERE status = ANY($1::text[])
                  GROUP BY status
                  ORDER BY status""",
                list(ACTIVE_STATUSES),
            )
            expired_today = await conn.fetchval(
                "SELECT COUNT(*) FROM orders WHERE status = 'expired' AND created_at >= CURRENT_DATE"
            )

        return {
            "periods": dict(periods),
            "states": [dict(row) for row in states],
            "expired_today": expired_today,
        }

    @classmethod
    async def financial(cls) -> dict:
        pool = await get_pool()
        if not pool:
            raise RuntimeError("Database pool is not initialized")

        async with pool.acquire() as conn:
            summary = await conn.fetchrow(
                """SELECT
                    COUNT(*) AS total_orders,
                    COUNT(*) FILTER (WHERE status = 'completed') AS completed_orders,
                    COUNT(*) FILTER (WHERE status = 'rejected') AS rejected_orders,
                    COUNT(*) FILTER (WHERE status = 'expired') AS expired_orders,
                    COUNT(*) FILTER (WHERE status = ANY($1::text[])) AS active_orders,
                    COALESCE(SUM(amount_usdt) FILTER (WHERE status = 'completed'), 0) AS completed_usdt,
                    COALESCE(SUM(fee_amount) FILTER (WHERE status = 'completed'), 0) AS completed_fees,
                    COALESCE(SUM(amount_usdt) FILTER (WHERE status = ANY($1::text[])), 0) AS active_usdt,
                    COALESCE(AVG(customer_rating) FILTER (WHERE customer_rating IS NOT NULL), 0) AS average_rating,
                    COALESCE(AVG(EXTRACT(EPOCH FROM (completed_at - created_at)) / 3600) FILTER (
                        WHERE status = 'completed' AND completed_at IS NOT NULL AND created_at IS NOT NULL
                    ), 0) AS average_completion_hours
                   FROM orders""",
                list(ACTIVE_STATUSES),
            )
            today = await conn.fetchrow(
                """SELECT
                    COUNT(*) AS completed_orders,
                    COALESCE(SUM(amount_usdt), 0) AS usdt,
                    COALESCE(SUM(fee_amount), 0) AS fees
                   FROM orders
                  WHERE status = 'completed' AND completed_at >= CURRENT_DATE"""
            )
            currencies = await conn.fetch(
                """SELECT payment_currency, COUNT(*) AS count,
                          COALESCE(SUM(total_amount), 0) AS total_amount,
                          COALESCE(SUM(amount_usdt), 0) AS usdt
                     FROM orders
                    WHERE status = 'completed'
                    GROUP BY payment_currency
                    ORDER BY payment_currency"""
            )
            networks = await conn.fetch(
                """SELECT network, COUNT(*) AS count,
                          COALESCE(SUM(amount_usdt), 0) AS usdt
                     FROM orders
                    WHERE status = 'completed'
                    GROUP BY network
                    ORDER BY network"""
            )
            users = await conn.fetchrow(
                """SELECT
                    COUNT(*) AS total_users,
                    COUNT(*) FILTER (WHERE created_at >= CURRENT_DATE) AS new_today,
                    COUNT(*) FILTER (WHERE created_at >= CURRENT_DATE - INTERVAL '30 days') AS new_30d
                   FROM users"""
            )

        return {
            "summary": dict(summary),
            "today": dict(today),
            "currencies": [dict(row) for row in currencies],
            "networks": [dict(row) for row in networks],
            "users": dict(users),
        }

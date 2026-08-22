"""Consistent display behavior for PostgreSQL NUMERIC values.

Database money/rate fields are stored with high precision for calculations,
but Telegram-facing messages should not expose storage scale such as
``50.00000000``. This module keeps the underlying Decimal value intact while
making its default string representation suitable for UI output.
"""
from decimal import Decimal
from typing import Any

import asyncpg


class DisplayDecimal(Decimal):
    """Decimal that renders with two fractional digits by default."""

    def __str__(self) -> str:
        return format(self.quantize(Decimal("0.01")), "f")


_original_create_pool = asyncpg.create_pool


async def _create_pool_with_display_numeric(*args: Any, **kwargs: Any):
    """Wrap asyncpg pools so PostgreSQL NUMERIC values use DisplayDecimal."""
    original_init = kwargs.get("init")

    async def init_connection(connection: Any) -> None:
        await connection.set_type_codec(
            "numeric",
            schema="pg_catalog",
            encoder=lambda value: Decimal.__str__(value),
            decoder=DisplayDecimal,
            format="text",
        )
        if original_init:
            await original_init(connection)

    kwargs["init"] = init_connection
    return await _original_create_pool(*args, **kwargs)


asyncpg.create_pool = _create_pool_with_display_numeric

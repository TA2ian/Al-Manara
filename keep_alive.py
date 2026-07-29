"""Keep alive service for Render."""
from aiohttp import web
from datetime import datetime


def keep_alive(app: web.Application):
    """Add keep alive endpoints."""

    async def health_check(request):
        """Health check endpoint."""
        return web.json_response({
            'status': 'ok',
            'timestamp': datetime.now().isoformat(),
            'service': 'crypto-topup-bot'
        })

    async def metrics(request):
        """Metrics endpoint."""
        return web.json_response({
            'status': 'ok',
            'timestamp': datetime.now().isoformat()
        })

    app.router.add_get('/health', health_check)
    app.router.add_get('/metrics', metrics)

# Al-Manara Telegram Bot

Telegram bot for Al-Manara USDT purchase and top-up services.

## Core capabilities

- USDT purchase flows with supported networks and currencies
- Arabic/English user experience
- Account and wallet verification
- Saved-wallet and QR validation
- Sequential order creation and lifecycle controls
- ShamCash payment methods with admin setup and validation
- Customer and admin dashboards
- Rate limiting and anti-abuse controls
- Audit logging
- PostgreSQL persistence

## Local development

```bash
pip install -r requirements.txt
python main.py
```

Copy `.env.example` to `.env` and provide the required runtime configuration.

## Runtime architecture

```text
main.py              Application entry point
bot.py               Dispatcher and router registration
config.py            Runtime configuration
database.py          PostgreSQL access
database_order_constraints.py
                     Database-level order invariants
handlers/            Customer, verification, order and admin flows
services/            Business and policy services
keyboards/           Inline and reply keyboard definitions
middleware/          Cross-cutting middleware
security/            Security helpers
locales/             User-facing translations
scripts/              Operational utilities
tests/               Regression and architecture gates
```

## Data and infrastructure

Al-Manara uses PostgreSQL as its runtime database through `DATABASE_URL`.
Supabase is not a runtime dependency and is not required for application operation.

## Important operational rules

- Customer and admin navigation are isolated.
- Dashboard reply keyboards are shown only at dashboard boundaries and removed during multi-step flows.
- New users must accept the required onboarding terms before order creation.
- Full legal terms remain available after registration through the Legal Center.
- Wallet, QR, payment and order data are validated before an order is created and protected by database-level invariants where applicable.
- Administrative actions require explicit admin authorization.

## Release verification

The project is not considered release-ready until the full CI/release verification suite passes, including router integrity, wallet and order lifecycle guards, payment/receipt transitions, currency/rate flows, and functional regression tests.

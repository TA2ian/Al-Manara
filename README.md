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
- Receipt OCR and verification assistance with admin-controlled final decisions
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
config.py            Deployment/runtime configuration and admin allowlist
database.py          PostgreSQL access
database_order_constraints.py
                     Database-level order invariants
handlers/            Customer, verification, order and admin flows
services/            Business, financial and policy services
keyboards/           Inline and reply keyboard definitions
middleware/          Cross-cutting middleware
security/            Security helpers
locales/             User-facing translations
scripts/              Operational utilities
tests/               Regression and architecture gates
```

## Policy architecture

Business rules that must survive restarts are progressively centralized behind authoritative policy/services rather than being duplicated across handlers.

### Operational policies

`services/operational_policy_service.py` is the runtime authority for configurable operational settings currently covering:

- Service fee percentage, including network-specific fee policies
- Payment processing timeout
- Minimum order, maximum order and daily order limits
- Validation and audit logging for policy changes

Persistent settings are stored through `services/settings_service.py` in the `bot_settings` table and cached in memory for runtime reads. Configuration in `config.py` is used for deployment defaults and required infrastructure settings; it is not intended to duplicate persistent business settings.

### Financial precision and rounding

The current financial calculation contract is implemented by `services/exchange_service.py`:

| Value | Current precision | Rounding |
|---|---:|---|
| USD / NEW.SYP monetary amounts | `0.01` | `ROUND_HALF_UP` |
| USDT amounts | `0.00000001` | `ROUND_HALF_UP` |
| Exchange rates | `0.00000001` | `ROUND_HALF_UP` |

`NEW.SYP` currently shares the general fiat monetary precision (`0.01`). If currency-specific precision becomes a business requirement, it should be introduced through an explicit currency policy rather than by adding scattered rounding rules to handlers.

### Tolerance policy status

Receipt analysis currently uses a `2%` amount comparison tolerance inside `services/receipt_verifier.py`. This is an implementation rule, not yet a separately configurable `Tolerance Policy` or `Tolerance Timing Policy`.

Until those policies are explicitly defined and centralized, the receipt verifier must not be treated as the authority for unrelated order or financial rules. Any future change to tolerance should preserve the separation between calculation, receipt verification and the administrator's final decision.

### Administrator model

Administrative authorization currently uses the configured `Config.ADMIN_IDS` allowlist. The project intentionally keeps administrative authority explicit and centralized. A separate `Backup Admin` role is not currently defined as an independent policy and must not be inferred from the generic admin allowlist.

## Payment and receipt flow

The payment lifecycle separates customer submission, automated verification assistance and administrator decisions. Receipt OCR can extract and compare date, sender/recipient identity or account information and amount, but receipt analysis does not by itself complete the payment. Administrative actions remain the authoritative decision point for approval, rejection and related order transitions.

Supported payment networks currently include `BEP20`, `TRC20`, `TON`, `ARB`, `SOLANA` and `ETH`, with compatibility aliases normalized by the exchange service. TXID handling must remain network-aware and must not introduce an unrelated global restriction that blocks valid `TRC20` or other supported transaction formats.

## Data and infrastructure

Al-Manara uses PostgreSQL as its runtime database through `DATABASE_URL`.
Supabase is not a runtime dependency and is not required for application operation.

Operational settings are persisted in PostgreSQL rather than relying exclusively on process environment variables. Deployment secrets and infrastructure configuration remain environment-based.

## Important operational rules

- Customer and admin navigation are isolated.
- Dashboard reply keyboards are shown only at dashboard boundaries and removed during multi-step flows.
- New users must accept the required onboarding terms before order creation.
- Full legal terms remain available after registration through the Legal Center.
- Wallet, QR, payment and order data are validated before an order is created and protected by database-level invariants where applicable.
- Administrative actions require explicit admin authorization.
- Order deadlines are derived from the configured processing policy; user-facing deadline messaging should describe the configured processing window rather than depend on client-provided timezone or device-clock values.
- Order state and payment evidence must remain authoritative in the database; client-visible timestamps are presentation data and must not be trusted as a security boundary.
- Maintenance modes must preserve explicitly allowed in-progress operational actions according to their policy instead of acting as a blanket first-click gate.

## Documentation and evolution policy

The README is maintained as an architectural contract, not as a copy of implementation details. When a business rule changes, the authoritative implementation, regression tests and this document should be reviewed together.

The project follows a strict cleanup rule for legacy logic:

1. Unused legacy code is removed.
2. Legacy behavior that is still required is reimplemented or integrated through the current authoritative architecture.
3. Duplicate handlers and competing policy authorities are removed or blocked by regression tests.
4. New functionality must depend on the current domain contracts rather than resurrecting first-version behavior.

This is particularly important while the bot is still in its initial development stage: future features must be able to extend the current architecture without old, inactive paths silently intercepting or overriding them.

## Release verification

The project is not considered release-ready until the full CI/release verification suite passes, including router integrity, wallet and order lifecycle guards, payment/receipt transitions, currency/rate flows, policy controls, TXID/network handling, and functional regression tests.

A green CI run validates the current test suite; it does not replace end-to-end testing inside the Telegram bot for critical customer/admin flows.

# Crypto Top-Up Telegram Bot

Enterprise-grade Telegram bot for USDT top-up services (BEP20 & TRC20), built with aiogram 3, aiohttp, and PostgreSQL.

## Stack

- **Language:** Python 3.11
- **Framework:** aiogram 3.4 (Telegram bot) + aiohttp (webhook server)
- **Database:** PostgreSQL (Replit built-in, auto-provisioned)
- **Languages:** Arabic & English

## How to run

The workflow **"Start bot"** runs `python3 main.py`.

The bot starts an aiohttp webhook server on port 8000. On Replit the webhook URL is automatically derived from `REPLIT_DEV_DOMAIN`.

## Required secrets

Set these in Replit Secrets before starting:

| Secret | Description |
|---|---|
| `BOT_TOKEN` | Telegram bot token from @BotFather |
| `ADMIN_IDS` | Comma-separated Telegram user IDs for admins |
| `SECRET_TOKEN` | Random string used to verify webhook requests |
| `ENCRYPTION_KEY` | 32-character key for encrypted backups |
| `SHAMCASH_USD_ACCOUNT` | Sham Cash USD account number |
| `SHAMCASH_SYP_ACCOUNT` | Sham Cash SYP account number |
| `SHAMCASH_NAME` | Business name shown on payment details |

## Architecture

```
main.py              # Entry point — aiohttp server + webhook setup
config.py            # Configuration (reads env vars; auto-detects REPLIT_DEV_DOMAIN)
bot.py               # Bot & dispatcher setup
database.py          # PostgreSQL connection + schema init (CREATE TABLE IF NOT EXISTS)
states.py            # aiogram FSM states
handlers/            # Message handlers (start, order, profile, admin, feedback, my_orders)
services/            # Business logic (exchange rate, locale, notifications, QR, wallet validation)
keyboards/           # Inline and reply keyboards
middleware/          # Rate limiting, maintenance mode
security/            # Encrypted backup helpers
locales/             # ar.json, en.json translations
logs/                # Runtime log files (bot.log)
```

## User preferences

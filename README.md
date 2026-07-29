# Crypto Top-Up Telegram Bot

Enterprise-grade Telegram bot for USDT top-up services.

## Features

- ✅ BEP20 & TRC20 support
- ✅ Multi-language (Arabic/English)
- ✅ User verification system
- ✅ Dual currency (USD/SYP)
- ✅ Order tracking with visual timeline
- ✅ Admin panel with dashboard
- ✅ Rate limiting & anti-abuse
- ✅ Audit logging
- ✅ Encrypted backups
- ✅ Webhook support
- ✅ PostgreSQL database

## Quick Start

### 1. Clone and Setup

```bash
git clone <your-repo>
cd crypto-topup-bot
cp .env.example .env
# Edit .env with your values
```

### 2. Local Development

```bash
pip install -r requirements.txt
python main.py
```

### 3. Deploy on Render

1. Fork this repository to GitHub
2. Create new Web Service on Render
3. Connect your GitHub repository
4. Add environment variables
5. Deploy!

### Environment Variables

```env
BOT_TOKEN=your_bot_token_from_BotFather
ADMIN_IDS=your_telegram_id,another_admin_id
DATABASE_URL=postgresql://...
WEBHOOK_HOST=https://your-bot.onrender.com
SECRET_TOKEN=random_secret_string
ENCRYPTION_KEY=32_character_encryption_key
```

## Commands

- `/start` - Start bot and accept terms
- `/admin` - Admin panel (admins only)

## Architecture

```
crypto-topup-bot/
├── main.py              # Entry point
├── config.py            # Configuration
├── bot.py               # Bot & dispatcher setup
├── database.py          # PostgreSQL connection
├── states.py            # FSM states
├── handlers/            # Message handlers
├── services/            # Business logic
├── keyboards/           # UI keyboards
├── middleware/          # Rate limit, maintenance
├── security/            # Encryption
├── locales/             # Translations
└── scripts/             # Utilities
```

## License

MIT

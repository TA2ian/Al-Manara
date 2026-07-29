# Crypto Top-Up Telegram Bot - Complete Build Prompt for Replit

## Project Overview
Build a production-ready Telegram bot for USDT top-up services (selling USDT to customers). The bot runs on Replit with free tier, uses SQLite (upgradable to PostgreSQL), and supports BEP20/TRC20 networks with payment via Sham Cash in Syrian Pounds (SYP) or US Dollars (USD).

## Architecture

```
crypto-topup-bot/
├── main.py              # Entry point (webhook + polling hybrid)
├── config.py            # Configuration from environment variables
├── database.py          # SQLite with aiosqlite
├── states.py            # FSM states
├── bot.py               # Bot & dispatcher setup
├── keep_alive.py        # Flask keep-alive for Replit
├── requirements.txt     # Dependencies
├── .env                 # Environment variables
├── .replit              # Replit configuration
├── replit.nix           # Nix packages
├── handlers/
│   ├── __init__.py
│   ├── start.py         # /start, terms acceptance, welcome
│   ├── verification.py  # User KYC (name, Sham Cash account, QR)
│   ├── order.py         # Create order (network, amount, wallet, currency)
│   ├── my_orders.py     # Order history & tracking
│   ├── profile.py       # User profile
│   ├── settings.py      # Language settings
│   ├── feedback.py      # Send feedback to admins (max 200 chars)
│   └── admin.py         # Admin panel with dashboard
├── services/
│   ├── __init__.py
│   ├── locale_service.py     # i18n (ar/en)
│   ├── wallet_validator.py   # BEP20/TRC20 address validation
│   ├── qr_scanner.py         # QR code scanning (optional)
│   ├── exchange_service.py   # USD/SYP rate & fee calculation
│   ├── rate_limiter.py       # Rate limiting middleware
│   ├── notification_service.py # Admin notifications
│   ├── scheduler.py          # Payment reminders & cleanup
│   └── image_optimizer.py    # Compress images before storage
├── keyboards/
│   ├── __init__.py
│   ├── reply.py           # Compact reply keyboard (3 buttons)
│   └── inline.py          # All inline keyboards
├── middleware/
│   ├── __init__.py
│   ├── rate_limit.py      # Rate limiting
│   └── maintenance.py     # Maintenance mode blocker
├── models/
│   ├── __init__.py
│   ├── user.py            # User dataclass
│   └── order.py           # Order dataclass
├── locales/
│   ├── ar.json            # Arabic translations
│   └── en.json            # English translations
├── security/
│   ├── __init__.py
│   └── encryption.py      # Fernet encryption for sensitive data
└── data/                  # SQLite database files
```

## Core Workflow

### 1. New User Onboarding
```
User clicks /start
→ Show Terms & Disclaimer (with accept/decline buttons)
→ If accepted: show welcome message + main menu
→ If new user: prompt for verification (name, Sham Cash account, QR optional)
→ Verification sent to admin for approval
→ After approval: user can create orders
```

### 2. Order Creation Flow
```
User clicks "💰 جديد" (New)
→ Select network: [BEP20] [TRC20]
→ Enter amount in USDT (min 10, max 5000)
→ Enter wallet address (validated per network)
→ Optional: upload QR code for cross-verification
→ Select payment currency: [USD] [SYP]
→ Show order summary with:
    - USDT amount, network, wallet address
    - Exchange rate (1 USD = X SYP)
    - Base amount in selected currency
    - Service fee (configurable % or fixed)
    - Total amount due
→ User confirms
→ Order created with status: PENDING
→ Admin notified
```

### 3. Admin Approval Flow
```
Admin sees notification in Telegram
→ Clicks "View Order" in admin panel
→ Sees order details
→ Clicks "Approve" or "Reject"
→ If approved:
    - Order status: WAITING_PAYMENT
    - User receives Sham Cash payment details (account number, QR, amount)
    - 60-minute timer starts
    - Reminders at 15min and 45min
→ If rejected:
    - User receives rejection message with reason
```

### 4. Payment Flow
```
User pays via Sham Cash
→ Uploads payment receipt photo
→ Admin receives receipt notification
→ Admin verifies payment manually
→ Admin clicks "Confirm Payment"
→ Order status: PAYMENT_CONFIRMED
→ Admin sends USDT to user
→ Admin enters TXID
→ User receives:
    - USDT sent confirmation
    - TXID (copyable)
    - Link to blockchain explorer
    - Rating request (1-5 stars)
```

### 5. Order Status Timeline
```
PENDING → APPROVED → WAITING_PAYMENT → RECEIPT_RECEIVED → PAYMENT_CONFIRMED → PROCESSING → COMPLETED
                    ↓                    ↓
                 EXPIRED              REJECTED
```

## Database Schema (SQLite)

```sql
-- users
id INTEGER PRIMARY KEY
telegram_id BIGINT UNIQUE NOT NULL
username TEXT
full_name TEXT
shamcash_account TEXT
shamcash_qr_photo_id TEXT
language TEXT DEFAULT 'ar'
terms_accepted BOOLEAN DEFAULT FALSE
terms_accepted_at TIMESTAMP
is_verified BOOLEAN DEFAULT FALSE
verification_status TEXT DEFAULT 'pending'
is_blocked BOOLEAN DEFAULT FALSE
created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP

-- orders
id INTEGER PRIMARY KEY
order_number TEXT UNIQUE NOT NULL
user_id INTEGER REFERENCES users(id)
network TEXT NOT NULL -- BEP20 or TRC20
amount_usdt REAL NOT NULL
exchange_rate REAL NOT NULL
payment_currency TEXT NOT NULL -- USD or SYP
base_amount REAL NOT NULL
fee_percent REAL DEFAULT 0
fee_amount REAL DEFAULT 0
total_amount REAL NOT NULL
wallet_address TEXT NOT NULL
status TEXT DEFAULT 'pending'
receipt_photo_id TEXT
receipt_upload_count INTEGER DEFAULT 0
txid TEXT
admin_notes TEXT
customer_rating INTEGER
customer_comment TEXT
created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
approved_at TIMESTAMP
payment_deadline TIMESTAMP
completed_at TIMESTAMP

-- exchange_rates
id INTEGER PRIMARY KEY
rate REAL NOT NULL
updated_by BIGINT
updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP

-- audit_logs
id INTEGER PRIMARY KEY
user_id INTEGER
admin_id BIGINT
action TEXT NOT NULL
details TEXT
previous_value TEXT
new_value TEXT
severity TEXT DEFAULT 'info'
timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP

-- blocked_users
id INTEGER PRIMARY KEY
telegram_id BIGINT NOT NULL
reason TEXT
blocked_by BIGINT
blocked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
expires_at TIMESTAMP

-- feedback_messages
id INTEGER PRIMARY KEY
user_id INTEGER REFERENCES users(id)
message TEXT NOT NULL
status TEXT DEFAULT 'pending'
admin_reply TEXT
created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
```

## Key Features

### Security
- Rate limiting: 5s cooldown, 100/hour, 500/day per user
- Input validation for all fields
- Wallet address validation (BEP20: 0x + 40 hex, TRC20: T + 33 base58)
- Cross-network address checking (warn if address valid on other network)
- Block system with auto-expiry
- Audit logging for all admin actions
- Maintenance mode (admins only during maintenance)

### User Experience
- Terms & Disclaimer on first use (must accept)
- Compact reply keyboard: [💰 جديد] [📋 طلباتي] [⚙️]
- Inline keyboard for all other actions
- Order visual timeline with status tracking
- Smart reminders (15min, 45min, expiry)
- Quick actions for returning users (reorder, copy wallet, check rate)
- Feedback system (max 200 chars)
- Multi-language (Arabic/English)

### Admin Experience
- Dashboard with daily stats (orders, completed, pending, total USDT)
- Pending orders list with approve/reject actions
- Order details with all info
- Batch actions (approve multiple, export)
- Quick reply templates
- Settings management:
  - Exchange rate update
  - Fee configuration (% + fixed)
  - Sham Cash accounts (USD/SYP)
  - Order limits (min/max)
  - Payment timeout
- Analytics (daily/weekly/monthly)
- Backup/restore system

### Technical
- Hybrid webhook + polling (webhook for production, polling for Replit dev)
- Keep-alive endpoint for Replit (Flask on port 8080)
- Image optimization (compress receipts, max 500KB)
- QR code generation for Sham Cash payment (SVG format)
- Scheduled tasks (reminders, cleanup, backup)
- Error handling with user-friendly messages
- Logging to file + console

## Environment Variables (.env)

```
BOT_TOKEN=your_bot_token_from_BotFather
ADMIN_IDS=123456789,987654321

# Database (SQLite for Replit)
DATABASE_URL=sqlite:///data/bot.db

# For future PostgreSQL upgrade
# DATABASE_URL=postgresql://...

# Webhook (optional, for custom domain)
WEBHOOK_HOST=
WEBHOOK_PATH=/webhook

# Server
HOST=0.0.0.0
PORT=5000

# Security
SECRET_TOKEN=random_secret_for_webhook
ENCRYPTION_KEY=32_character_encryption_key

# Rate Limiting
RATE_LIMIT_COOLDOWN=5
RATE_LIMIT_HOURLY=100
RATE_LIMIT_DAILY=500

# Order Limits
MIN_ORDER=10
MAX_ORDER=5000
DAILY_LIMIT=10000

# Payment
PAYMENT_TIMEOUT=60

# Sham Cash
SHAMCASH_USD_ACCOUNT=09XXXXXXXX
SHAMCASH_SYP_ACCOUNT=09YYYYYYYY
SHAMCASH_NAME=Your Business Name

# Fees
SERVICE_FEE_PERCENT=0
SERVICE_FEE_FIXED=0

# Maintenance
MAINTENANCE_MODE=false
```

## Replit Configuration

### .replit
```toml
run = "python main.py"
language = "python3"

[packager]
language = "python3"
```

### replit.nix
```nix
{ pkgs }: {
  deps = [
    pkgs.python311
    pkgs.python311Packages.pip
    pkgs.zbar
    pkgs.libzbar
  ];
}
```

## Requirements (requirements.txt)

```
aiogram==3.4.1
aiohttp==3.9.1
aiosqlite==0.20.0
APScheduler==3.10.4
Pillow==10.2.0
qrcode==7.4.2
python-dotenv==1.0.0
cryptography==42.0.0
pyzbar==0.1.9
Flask==3.0.0
```

## Implementation Order

1. **Phase 1: Core Setup**
   - config.py, database.py, states.py
   - Locale service + translations
   - Keep-alive server

2. **Phase 2: User Flow**
   - /start + terms acceptance
   - User verification (KYC)
   - Profile & settings

3. **Phase 3: Order Flow**
   - Create order (network, amount, wallet, currency)
   - Order summary with fee calculation
   - Order storage & retrieval

4. **Phase 4: Admin Flow**
   - Admin panel (/admin)
   - Approve/reject orders
   - Payment confirmation
   - TXID entry

5. **Phase 5: Polish**
   - Notifications & reminders
   - Rate limiting
   - Error handling
   - Logging
   - Backup system

## Important Notes

- Sham Cash has NO API - all payment verification is manual by admin
- QR codes for payment are generated as SVG (small size, ~3KB)
- Receipt photos are stored as Telegram file_id only (no local storage)
- SQLite is sufficient for 5-10 orders/day (upgrade to PostgreSQL if scaling)
- All sensitive data (wallet addresses, TXIDs) should be encrypted
- Keep Replit project always on (use UptimeRobot or similar for pinging)
- Set BOT_TOKEN and ADMIN_IDS before first run
- First admin must set exchange rate before any orders can be created

## Admin Commands

```
/admin - Open admin panel
```

## User Commands

```
/start - Start bot / Show main menu
```

All other interactions via buttons (Reply + Inline keyboards).

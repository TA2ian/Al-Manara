from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

SUPPORTED_WALLET_NETWORKS = ("BEP20", "TRC20", "TON", "ARB", "SOLANA", "ETH")


_NETWORK_LABELS_AR = {
    "BEP20": "🟡 BEP20 (BNB Chain)",
    "TRC20": "🔷 TRC20 (TRON)",
    "TON": "💎 TON",
    "ARB": "🔵 ARB (Arbitrum)",
    "SOLANA": "🟣 Solana",
    "ETH": "⚪ Ethereum (ETH)",
}

_NETWORK_LABELS_EN = {
    "BEP20": "🟡 BEP20 (BNB Chain)",
    "TRC20": "🔷 TRC20 (TRON)",
    "TON": "💎 TON",
    "ARB": "🔵 ARB (Arbitrum)",
    "SOLANA": "🟣 Solana",
    "ETH": "⚪ Ethereum (ETH)",
}


def wallet_network_keyboard(lang: str = "ar", *, cancel_callback: str = "wallet_back") -> InlineKeyboardMarkup:
    labels = _NETWORK_LABELS_AR if lang == "ar" else _NETWORK_LABELS_EN
    rows = [
        [
            InlineKeyboardButton(text=labels["BEP20"], callback_data="wallet_network_BEP20"),
            InlineKeyboardButton(text=labels["TRC20"], callback_data="wallet_network_TRC20"),
        ],
        [
            InlineKeyboardButton(text=labels["TON"], callback_data="wallet_network_TON"),
            InlineKeyboardButton(text=labels["ARB"], callback_data="wallet_network_ARB"),
        ],
        [
            InlineKeyboardButton(text=labels["SOLANA"], callback_data="wallet_network_SOLANA"),
            InlineKeyboardButton(text=labels["ETH"], callback_data="wallet_network_ETH"),
        ],
        [InlineKeyboardButton(text="❌ إلغاء" if lang == "ar" else "❌ Cancel", callback_data=cancel_callback)],
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)

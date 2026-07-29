"""Order model."""
from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class Order:
    """Order entity."""
    id: int
    order_number: str
    user_id: int
    network: str  # BEP20 or TRC20
    amount_usdt: float
    exchange_rate: float
    payment_currency: str  # USD or SYP
    base_amount: float
    fee_percent: float
    fee_amount: float
    total_amount: float
    wallet_address: str
    status: str = "pending"
    receipt_photo_id: Optional[str] = None
    receipt_upload_count: int = 0
    txid: Optional[str] = None
    admin_notes: Optional[str] = None
    customer_rating: Optional[int] = None
    customer_comment: Optional[str] = None
    created_at: Optional[datetime] = None
    approved_at: Optional[datetime] = None
    payment_deadline: Optional[datetime] = None
    completed_at: Optional[datetime] = None


@dataclass
class OrderTimeline:
    """Order timeline entry."""
    timestamp: datetime
    status: str
    description: str
    admin_id: Optional[int] = None

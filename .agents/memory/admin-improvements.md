---
name: Admin Panel Improvements
description: Paginated order lists, enhanced dashboard, auto-approve, order timeline
---

## Admin Panel Improvements

### Order lists pagination
- `pending_orders` and `admin_active_orders` now show 5 orders per page with prev/next navigation
- `_fetch_orders_page(list_type, page)` helper with LIMIT/OFFSET
- Pagination keyboard reuses the working pattern from `admin_list_users`

### Enhanced dashboard
- Three time ranges: today, last 7 days, this month
- Active order breakdown by status (pending/waiting_payment/receipt_received/payment_confirmed/expired)
- Customer metrics: total, verified, repeat customers (2+ orders), avg rating

### Auto-approve for trusted customers
- Toggle via `admin_auto_approve` → `admin_auto_approve_toggle` → stored in `bot_settings` table
- Auto-approve activates in `confirm_order()` when user has 3+ completed orders
- Order goes directly to `waiting_payment` with payment instructions sent to user
- Admin notification shows "⚡ (توثيق تلقائي)" badge

### Order timeline
- `admin_timeline_{order_id}` shows full audit trail from audit_logs table
- Order detail keyboard with timeline, notes, and back buttons

### Keyboard layout
- Compact 3-column layout fits more actions in fewer rows
- New buttons: تفاصيل طلب (search), توثيق تلقائي (auto-approve settings)

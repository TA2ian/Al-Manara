"""Bot instance creation."""
from aiogram import Dispatcher


def create_dispatcher() -> Dispatcher:
    """Create dispatcher from the single authoritative router graph."""
    from handlers import (
        start,
        saved_wallets,
        order_wallet_policy,
        order_wallet_qr_policy,
        payment_currency_policy,
        wallet_qr_first_policy,
        wallets,
        order_amount_policy,
        order_confirmation_policy,
        profile,
        active_order_policy,
        receipt_processing_policy,
        receipt_document_policy,
        customer_orders_policy,
        feedback,
        admin_entry,
        admin_broadcast_policy,
        verification_admin_policy,
        verification_pending_policy,
        verification_policy,
        verification_keyboard_cleanup,
        admin_rate_policy,
        admin_navigation_policy,
        admin_approval_policy,
        admin_rejection_policy,
        admin_payment_confirmation_policy,
        admin_transfer_policy,
        admin_note_policy,
        admin_order_list_policy,
        admin_user_management_policy,
        admin_utility_policy,
        admin_maintenance_policy,
        admin_settings_policy,
        payment_method_setup_policy,
        payment_method_legacy_compat,
        language_policy,
        customer_navigation_policy,
        customer_settings_policy,
        admin_tools_policy,
        admin_search_policy,
        legal_navigation_policy,
    )
    from middleware.rate_limit import RateLimitMiddleware
    from middleware.maintenance import MaintenanceMiddleware
    from middleware.ownership import OwnershipMiddleware
    from middleware.state_processing_lock import StateProcessingLockMiddleware

    dp = Dispatcher()
    dp.message.middleware(RateLimitMiddleware())
    dp.callback_query.middleware(RateLimitMiddleware())
    dp.message.middleware(MaintenanceMiddleware())
    dp.callback_query.middleware(MaintenanceMiddleware())
    dp.message.middleware(StateProcessingLockMiddleware())
    dp.callback_query.middleware(OwnershipMiddleware())

    dp.include_router(start.router)
    dp.include_router(customer_settings_policy.router)
    dp.include_router(payment_method_legacy_compat.router)
    dp.include_router(payment_method_setup_policy.router)

    dp.include_router(admin_note_policy.router)
    dp.include_router(admin_tools_policy.router)
    dp.include_router(admin_search_policy.router)
    dp.include_router(order_amount_policy.router)

    dp.include_router(saved_wallets.router)
    dp.include_router(order_wallet_policy.router)
    dp.include_router(order_wallet_qr_policy.router)
    dp.include_router(payment_currency_policy.router)
    dp.include_router(wallet_qr_first_policy.router)
    dp.include_router(wallets.router)
    dp.include_router(order_confirmation_policy.router)
    dp.include_router(active_order_policy.router)
    dp.include_router(profile.router)
    dp.include_router(receipt_processing_policy.router)
    dp.include_router(receipt_document_policy.router)
    dp.include_router(customer_orders_policy.router)
    dp.include_router(feedback.router)

    dp.include_router(admin_entry.router)
    dp.include_router(admin_broadcast_policy.router)
    dp.include_router(verification_admin_policy.router)
    dp.include_router(admin_rate_policy.router)
    dp.include_router(admin_navigation_policy.router)
    dp.include_router(admin_approval_policy.router)
    dp.include_router(admin_rejection_policy.router)
    dp.include_router(admin_payment_confirmation_policy.router)
    dp.include_router(admin_transfer_policy.router)
    dp.include_router(admin_order_list_policy.router)
    dp.include_router(admin_user_management_policy.router)
    dp.include_router(admin_utility_policy.router)
    dp.include_router(admin_maintenance_policy.router)
    dp.include_router(admin_settings_policy.router)

    dp.include_router(verification_pending_policy.router)
    dp.include_router(verification_keyboard_cleanup.router)
    dp.include_router(verification_policy.router)
    dp.include_router(language_policy.router)
    dp.include_router(legal_navigation_policy.router)
    dp.include_router(customer_navigation_policy.router)

    return dp

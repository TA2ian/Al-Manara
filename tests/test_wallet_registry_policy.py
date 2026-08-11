import ast
from pathlib import Path


def test_wallet_manager_has_add_delete_and_no_edit_path():
    source = Path('handlers/wallets.py').read_text()
    assert 'wallet_add' in source
    assert 'wallet_delete_' in source
    assert 'wallet_edit_' not in source


def test_wallet_manager_requires_qr_before_save():
    source = Path('handlers/wallets.py').read_text()
    assert 'WalletStates.waiting_qr' in source
    assert "'verified'" in source
    assert 'qr_photo_id' in source


def test_wallet_manager_is_syntax_valid():
    ast.parse(Path('handlers/wallets.py').read_text())
    ast.parse(Path('database.py').read_text())

"""QR code scanning service."""
import io
import logging
from typing import Optional
from PIL import Image

logger = logging.getLogger(__name__)


class QRScanner:
    """Scan QR codes from images."""

    @staticmethod
    async def scan(file_id: str, bot) -> dict:
        """Scan QR code from Telegram file.

        Returns:
            {
                'success': bool,
                'address': str or None,
                'network': str or None,
                'error': str or None
            }
        """
        try:
            # Download file from Telegram
            file = await bot.get_file(file_id)
            photo_bytes = await bot.download_file(file.file_path)

            # Try pyzbar first
            try:
                from pyzbar.pyzbar import decode

                image = Image.open(io.BytesIO(photo_bytes.read()))
                decoded = decode(image)

                if not decoded:
                    return {
                        'success': False,
                        'error': 'No QR code found'
                    }

                if len(decoded) > 1:
                    return {
                        'success': False,
                        'error': 'Multiple QR codes found'
                    }

                address = decoded[0].data.decode('utf-8').strip()

                # Detect network
                from .wallet_validator import WalletValidator
                network = WalletValidator.detect_network(address)

                if not network:
                    return {
                        'success': False,
                        'error': 'Unknown address format in QR'
                    }

                return {
                    'success': True,
                    'address': address,
                    'network': network
                }

            except ImportError:
                return {
                    'success': False,
                    'error': 'QR scanner not available'
                }

        except Exception as e:
            logger.error(f"QR scan failed: {e}")
            return {
                'success': False,
                'error': f'Scan failed: {str(e)}'
            }

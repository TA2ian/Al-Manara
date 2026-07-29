"""
Manual restore script.

Usage:
    python scripts/restore.py backups/backup_20250729_143052.sql.gz.enc
"""

import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


async def main():
    print("⚠️  This script requires the backup_service module.")
    print("Please implement backup_service.restore_backup() first.")

    # List available backups
    backup_dir = "backups"
    if os.path.exists(backup_dir):
        print("\nAvailable backups:")
        for f in sorted(os.listdir(backup_dir), reverse=True):
            if f.endswith('.enc'):
                filepath = os.path.join(backup_dir, f)
                size = os.path.getsize(filepath)
                print(f"  - {f} ({size/1024:.1f} KB)")


if __name__ == "__main__":
    asyncio.run(main())

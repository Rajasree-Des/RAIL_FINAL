"""Diagnostic script to run Report 10-13 and capture detailed output."""

import asyncio
import sys
import logging
from datetime import datetime

# Enable verbose logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s %(levelname)s %(name)s: %(message)s'
)

from app.automation.run import attach_to_railmadad


async def run_test():
    print("=" * 60)
    print("Starting Report 10-13 diagnostic test")
    print("=" * 60)
    
    result = await attach_to_railmadad(
        user_id=None,
        report_slugs=['comprehensive-10-13'],
        run_id=f'test-run-{datetime.now().strftime("%H%M%S")}',
        date_from='2026-07-29',
        date_to='2026-07-29',
    )
    
    print("\n" + "=" * 60)
    print("RESULT SUMMARY")
    print("=" * 60)
    print(f'Success: {result.success}')
    print(f'Connected: {result.connected}')
    print(f'Tab Found: {result.tab_found}')
    print(f'Error: {result.error}')
    print(f'Error Code: {result.error_code}')
    
    if result.reports:
        print("\nREPORT RESULTS:")
        for r in result.reports:
            print(f'  {r.slug}:')
            print(f'    Status: {r.status}')
            print(f'    Error: {r.error}')
            print(f'    Row Count: {r.row_count}')
            print(f'    Excel Path: {r.excel_path}')
            print(f'    PDF Path: {r.pdf_path}')


if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    
    asyncio.run(run_test())

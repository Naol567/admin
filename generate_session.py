"""
Run this ONCE on your phone/Termux to generate the Telegram session file.
After running, upload 'forex_repost_bot.session' to Railway.

Usage:
    pip install telethon
    python generate_session.py
"""

import asyncio
from telethon import TelegramClient

API_ID   = input("Enter your API_ID: ").strip()
API_HASH = input("Enter your API_HASH: ").strip()

async def main():
    client = TelegramClient("forex_repost_bot", int(API_ID), API_HASH)
    await client.start()  # Will prompt for phone number + OTP
    me = await client.get_me()
    print(f"\n✅ Session created for: {me.first_name} (@{me.username})")
    print("📁 File saved: forex_repost_bot.session")
    print("➡️  Upload this file to Railway before deploying.")
    await client.disconnect()

asyncio.run(main())

import os
import aiohttp
import asyncio

async def test_telegram():
    telegram_bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    telegram_chat_id = os.getenv("TELEGRAM_CHAT_ID")

    url = f"https://api.telegram.org/bot{telegram_bot_token}/sendMessage"
    payload = {"chat_id": telegram_chat_id, "text": "Test message", "parse_mode": "MarkdownV2"}

    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=payload) as response:
            print(await response.json())

asyncio.run(test_telegram())
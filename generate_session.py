import asyncio

from pyrogram import Client

# Get these from https://my.telegram.org/apps
API_ID = 23678585  # Replace with your actual API ID
API_HASH = "0ef7b2d89db102e3347e0b73f6d4ab6e"  # Replace with your actual API Hash


async def main():
    async with Client("my_userbot", api_id=API_ID, api_hash=API_HASH) as app:
        print("\n\nYour session string:")
        print(await app.export_session_string())
        print("\n\nCopy this string!")


if __name__ == "__main__":
    asyncio.run(main())

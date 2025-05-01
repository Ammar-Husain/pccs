import asyncio
import os

from pyrogram import Client

# Get these from https://my.telegram.org/apps
API_ID = 23678585  # Replace with your actual API ID
API_HASH = "0ef7b2d89db102e3347e0b73f6d4ab6e"  # Replace with your actual API Hash


async def main():
    async with Client("my_userbot", api_id=API_ID, api_hash=API_HASH) as app:
        print("\n\nYour session string:")
        sess_str = await app.export_session_string()
        print(sess_str)
        print("\n\nCopy this string!")

        to_write = input("Write it to /.env file? [y/N]: ")
        if to_write == "y":
            with open("./.env", "a") as f:
                f.write(f"\nSESSION_STRING={sess_str}\n")


if __name__ == "__main__":
    asyncio.run(main())

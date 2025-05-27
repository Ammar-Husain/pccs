import asyncio
import os

import dotenv
from pyrogram import Client


async def main():
    # Get these from https://my.telegram.org/apps
    dotenv.load_dotenv()
    API_ID = os.getenv("API_ID")
    API_HASH = os.getenv("API_HASH")

    if not API_ID:
        print(
            "Missing API ID, make sure to include it in your environment or .env file"
        )
        return
    if not API_HASH:
        print(
            "Missing API HASH, make sure to include it in your environment or .env file"
        )
        return

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

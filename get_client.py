import os

import dotenv
from pyrogram import Client


def get_client():
    dotenv.load_dotenv()
    API_ID = os.getenv("API_ID")
    API_HASH = os.getenv("API_HASH")
    SESSION_STRING = os.getenv("SESSION_STRING")

    if not SESSION_STRING or not API_ID or not API_HASH:
        print("incomplete credential")
        print(f"session string is {SESSION_STRING}")
        print(f"api id is {API_ID}")
        print(f"api hash is {API_HASH}")
        return

    client = Client(
        name="get_client",
        api_id=API_ID,
        api_hash=API_HASH,
        session_string=SESSION_STRING,
    )

    return client

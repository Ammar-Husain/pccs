import asyncio
import os

import dotenv
from pyrogram import Client
from tqdm import tqdm


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


async def copy_to(client, src_link=None, dest_link=None, cur=0, end=0):
    if not src_link:
        src_link = input("Source Chat link:\n")

    src_chat = await client.get_chat(src_link)

    if not dest_link:
        dest_link = input("Destination Chat link:\n")

    messages = []
    async for message in client.get_chat_history(src_chat.id):
        if message.video:
            messages.append(message)

    messages = messages[cur:] if not end else messages[cur:end]
    messages = messages[::-1]

    dest_chat = await client.get_chat(dest_link)
    for message in tqdm(messages, unit="vidoe", desc="Forwarding"):

        await message.forward(dest_chat.id)

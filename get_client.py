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


async def copy_to(client, src_id, dest_id, cur=0, end=0):
    src_chann = await client.get_chat(src_id)

    messages = []
    async for message in client.get_chat_history(src_chann.id):
        if message.video:
            messages.append(message)

    messages = messages[cur:] if not end else messages[cur:end]

    dest_chann = await client.get_chat(dest_id)

    for message in tqdm(messages, unit="vidoe", desc="Forwarding"):
        await message.forward(dest_chann.id)

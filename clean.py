import asyncio

from get_client import get_client as gc


async def main():
    cl = gc()
    await cl.start()
    c = 1
    async for message in cl.get_chat_history("me"):
        if message.text and "download and uploading" in message.text:
            await message.delete()
            print(f"deleted {c}")
            c += 1


asyncio.get_event_loop().run_until_complete(main())

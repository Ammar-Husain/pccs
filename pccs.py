import asyncio
import os

from dotenv import load_dotenv
from pyrogram import Client, enums, filters
from pyrogram.errors import ChannelInvalid, FloodWait
from pyrogram.types import ChatPrivileges, Message

load_dotenv()

API_HASH = os.getenv("API_HASH")
API_ID = os.getenv("API_ID")
SESSION_STRING = os.getenv("SESSION_STRING")
MASTER_CHAT_USERNAME = os.getenv("MASTER_CHAT_USERNAME")


class ChannelCopier:
    def __init__(self):
        self.app = Client(
            "channel_copier",
            api_id=API_ID,
            api_hash=API_HASH,
            session_string=SESSION_STRING,
            in_memory=True,  # Important for mobile devices
        )
        self.source_id = None
        self.dest_id = None

    async def start(self):
        await self.app.start()
        print("Bot started successfully!")
        print("The Bot is awaiting for the command from the master")

        self.app.add_handler(
            self.app.on_message(filters.chat(MASTER_CHAT_USERNAME) & filters.text)(
                self.do_if_command
            )
        )

        # Keep running
        await self.idle()

    async def do_if_command(self, client: Client, message: Message):
        print("A message came from the master")

        if message.text[0:3] == "***":
            print("the message is a command")
        else:
            print("The message is not a command")
            return

        link = message.text[3:]
        try:
            self.source_id = await self.resolve_channel_id(link)
        except Exception as e:
            print(f"Failed to resolve channel: {e}")
            await client.send_message(message.from_user.id, "Invalid channel link")
            return

        print(f"Source channel ID: {self.source_id}")

        await client.send_message(
            message.from_user.id, "Task recived, channel found, starting process..."
        )

        # Create destination channel
        self.dest_id = await self.create_destination_channel()
        print(f"Destination channel ID: {self.dest_id}")

        await self.archive_existing_videos()

        dest_chat = await client.get_chat(self.dest_id)
        dest_chat_link = dest_chat.invite_link

        await client.send_message(
            message.from_user.id, f"Mission Completed, here you are {dest_chat_link}"
        )

    async def resolve_channel_id(self, link):
        try:
            chat = await self.app.get_chat(link)
            return chat.id
        except Exception as e:
            raise ValueError(f"Failed to resolve channel: {e}") from e

    async def create_destination_channel(self):
        source_chat = await self.app.get_chat(self.source_id)
        dest_title = f"{source_chat.title} [Private Copy]"

        # Check existing channels
        async for dialog in self.app.get_dialogs():
            if (
                dialog.chat.title == dest_title
                and dialog.chat.type == enums.ChatType.CHANNEL
            ):
                print("Using existing copy channel")
                return dialog.chat.id

        # Create new private channel
        try:
            new_channel = await self.app.create_channel(
                title=dest_title, description="Automated Private Copy"
            )

            return new_channel.id

        except FloodWait as e:
            print(f"Waiting {e.value} seconds before retrying...")
            await asyncio.sleep(e.value)
            return await self.create_destination_channel()

    async def handle_video(self, client: Client, message: Message):
        try:
            # MASTER_CHAT_USERNAMEo
            path = await message.download()

            # Create caption
            caption = message.caption or ""

            # Upload to destination
            await self.app.send_video(
                chat_id=self.dest_id,
                video=path,
                caption=caption,
                supports_streaming=True,
            )
            print(f"Copied video {message.id}")

        except FloodWait as e:
            print(f"Flood wait: {e.value}s")
            await asyncio.sleep(e.value)
        except Exception as e:
            print(f"Error copying video: {e}")
        else:
            if os.path.exists(path):
                os.remove(path)

    async def archive_existing_videos(self):
        print("Archiving historical videos...")
        async for message in self.app.get_chat_history(self.source_id):
            if message.video:
                await self.handle_video(self.app, message)

    async def idle(self):
        print("Bot is running. Press Ctrl+C to stop.")
        while True:
            await asyncio.sleep(3600)  # 1 hour

    async def stop(self):
        await self.app.stop()


async def main():
    copier = ChannelCopier()
    try:
        await copier.start()
    except ChannelInvalid:
        print("Error: Not a member of the source channel.")
    except Exception as e:
        print(f"Fatal error: {e}")
    finally:
        await copier.stop()


if __name__ == "__main__":
    try:
        asyncio.get_event_loop().run_until_complete(main())
    except KeyboardInterrupt:
        print("\nBot stopped by user")

import asyncio
import os

from dotenv import dotenv_values, load_dotenv
from pyrogram import Client, enums, filters
from pyrogram.errors import ChannelInvalid, FloodWait
from pyrogram.types import ChatPrivileges, Message

load_dotenv()
dotenv_values()

API_HASH = os.getenv("API_HASH")
API_ID = os.getenv("API_ID")
SESSION_STRING = os.getenv("SESSION_STRING")
MASTER_CHAT_USERNAME = os.getenv("MASTER_CHAT_USERNAME")
print(f"SESSION STRING IS {SESSION_STRING}")


class ChannelCopier:
    def __init__(self):
        self.app = Client(
            "my_userbot",
            api_id=API_ID,
            api_hash=API_HASH,
            session_string=SESSION_STRING or None,
            in_memory=bool(SESSION_STRING),  # Important for mobile devices
        )

    async def start(self):
        print("program started")
        await self.app.start()
        print("Bot started successfully!")
        print("The Bot is awaiting for commands from the master")

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
        # link = re.search("^(?:https?://)?(?:www\\.)?(?:t(?:elegram)?\\.(?:org|me|dog)/(?:joinchat/|\\+))([\\w-]+)$", message.text)

        try:
            src_chann = await self.resolve_channel_id(link)
        except Exception as e:
            print(f"Failed to resolve channel: {e}")
            await self.app.send_message(message.from_user.id, "Invalid channel link")
            return

        print(f"Source channel ID: {src_chann.id}")

        await self.app.send_message(
            message.from_user.id, "Task recived, channel found, starting process..."
        )

        # Create destination channel
        dest_chann_id = await self.create_destination_channel(
            src_chann.title + " [COPY]"
        )

        print(f"Destination channel ID: {dest_chann_id}")

        dest_chann = await self.app.get_chat(dest_chann_id)

        await self.app.send_message(
            message.from_user.id,
            f"Mission Strarted, you can follow up here {dest_chann.invite_link}",
        )

        await self.archive_existing_videos(src_chann.id, dest_chann.id)

        print("Mission Completed")
        await self.app.send_message(
            message.from_user.id,
            f"Mission Completed, here you are {dest_chann.invite_link}",
        )

    async def resolve_channel_id(self, link):
        try:
            chat = await self.app.get_chat(link)
            return chat
        except Exception as e:
            raise ValueError(f"Failed to resolve channel: {e}") from e

    async def create_destination_channel(self, title):
        # Check existing channels
        async for dialog in self.app.get_dialogs():
            if (
                dialog.chat.title == title
                and dialog.chat.type == enums.ChatType.CHANNEL
            ):
                print("Using existing copy channel")
                return dialog.chat.id

        # Create new private channel
        try:
            new_channel = await self.app.create_channel(
                title=title, description="Automated Private Copy"
            )

            return new_channel.id

        except FloodWait as e:
            print(f"Waiting {e.value} seconds before retrying...")
            await asyncio.sleep(e.value)
            return await self.create_destination_channel(title)

    async def download_and_upload(self, client: Client, message: Message, dest_id):
        try:
            path = await message.download()

            # Create caption
            caption = message.caption or ""

            # Upload to destination
            await self.app.send_video(
                chat_id=dest_id,
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

    async def archive_existing_videos(self, src_id, dest_id):
        print("Archiving historical videos...")
        src_chann = await self.app.get_chat(src_id)

        if src_chann.has_protected_content:
            async for message in self.app.get_chat_history(src_id):
                if message.video:
                    await self.download_and_upload(self.app, message, dest_id)
        else:
            try:
                async for message in self.app.get_chat_history(src_id):
                    if message.video:
                        await message.forward(dest_id)
            except:
                pass

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

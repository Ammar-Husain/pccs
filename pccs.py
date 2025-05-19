import asyncio
import os

import dotenv
from pyrogram import Client, enums, filters
from pyrogram.errors import ChannelInvalid, FloodWait
from pyrogram.types import ChatPreview, Message

is_prod = os.getenv("PRODUCTION")

if not is_prod:
    conf = dotenv.dotenv_values()
    API_ID = conf["API_ID"]
    API_HASH = conf["API_HASH"]
    SESSION_STRING = conf["SESSION_STRING"]
    MASTER_CHAT_USERNAME = conf["MASTER_CHAT_USERNAME"]
    print(f"SESSION STRING imported from dotenv is {SESSION_STRING}")


else:
    API_ID = os.getenv("API_ID")
    API_HASH = os.getenv("API_HASH")
    SESSION_STRING = os.getenv("SESSION_STRING")
    MASTER_CHAT_USERNAME = os.getenv("MASTER_CHAT_USERNAME")

    if not MASTER_CHAT_USERNAME == "me" or MASTER_CHAT_USERNAME == "self":
        MASTER_CHAT_USERNAME = "@" + MASTER_CHAT_USERNAME

    print(f"SESSION STRING imported from enviroment is {SESSION_STRING}")


class ChannelCopier:
    def __init__(self):
        self.app = Client(
            "my_userbot",
            api_id=API_ID,
            api_hash=API_HASH,
            session_string=SESSION_STRING or None,
            in_memory=bool(SESSION_STRING),  # Important for mobile devices
        )
        self.advertising = False

    async def start(self):
        print("program started")
        try:
            await self.app.start()
        except ConnectionError as e:
            print("Connection Error:", e)

        print("Bot started successfully!")
        print("The Bot is awaiting for commands from the master")

        self.app.add_handler(
            self.app.on_message(filters.chat(MASTER_CHAT_USERNAME) & filters.text)(
                self.parse_cammand
            )
        )

        # Keep running
        await self.idle()

    async def parse_cammand(self, client: Client, message: Message):
        print("A message came from the master")

        if message.text[0:3] == "***":
            print("the message is a command")
            command = message.text[3:]
        else:
            print("The message is not a command")
            return

        if command[:2] == "sc":
            link = command[3:]
            await self.copy_content(link, message.from_user.id)

        elif command[:2] == "sr":
            print("send regulary")
            link, text, interval = command[3:].split(sep="|")
            await message.reply(
                f"I am going to send '{text}' to {link} every {interval}s to stop send `***sa`",
                quote=True,
            )
            await self.send_regularly(link, text, int(interval))

        elif command[:2] == "sa":
            await message.reply("Stoping all adevertisements...", quote=True)
            self.advertising = False

        else:
            await message.reply("Invalid command", quote=True)

    async def copy_content(self, link, customer_id):
        try:
            src_chann = await self.resolve_channel_id(link)
        except Exception as e:
            print(f"Failed to resolve channel: {e}")
            await self.app.send_message(customer_id, "Invalid channel link")
            return

        print(f"Source channel ID: {src_chann.id}")

        await self.app.send_message(
            customer_id,
            "Task recived, channel found, starting Copying Process...",
        )

        # Create destination channel
        dest_chann_id = await self.create_destination_channel(
            src_chann.title + " [COPY]"
        )

        dest_chann = await self.app.get_chat(dest_chann_id)

        print(f"Destination channel ID: {dest_chann.id}")

        await self.app.send_message(
            customer_id,
            f"Mission Strarted, you can follow up here {dest_chann.invite_link}",
        )

        await self.archive_existing_videos(src_chann.id, dest_chann.id)

        print("Mission Completed")
        await self.app.send_message(
            customer_id,
            f"Mission Completed, here you are {dest_chann.invite_link}",
        )

    async def resolve_channel_id(self, link):
        try:
            chat = await self.app.get_chat(link)

            if isinstance(chat, ChatPreview):
                print("joining the channel")
                await self.app.join_chat(link)
                chat = await self.app.get_chat(link)

            return chat
        except Exception as e:
            raise ValueError(f"Failed to resolve channel: {e}") from e

    async def create_destination_channel(self, title):
        # Check existing channels
        # async for dialog in self.app.get_dialogs():
        #     if (
        #         dialog.chat.title == title
        #         and dialog.chat.type == enums.ChatType.CHANNEL
        #     ):
        #         print("Using existing copy channel")
        #         return dialog.chat.id
        #

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
            video_path = await message.download()
            thumb_path = await self.app.download_media(message.video.thumbs[0].file_id)
            print(thumb_path)

            # Create caption and other metadata
            caption = message.caption or ""
            duration = message.video.duration

            print(duration)

            # Upload to destination
            await self.app.send_video(
                chat_id=dest_id,
                video=video_path,
                thumb=thumb_path,
                caption=caption,
                duration=duration,
                supports_streaming=True,
            )
            print(f"Copied video {message.id}")

        except FloodWait as e:
            print(f"Flood wait: {e.value}s")
            await asyncio.sleep(e.value)
        except Exception as e:
            print(f"Error copying video: {e}")
        else:
            if os.path.exists(video_path):
                os.remove(video_path)
            if os.path.exists(thumb_path):
                os.remove(thumb_path)

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
            except Exception as e:
                print(f"Exception during forwarding: {e}")

    async def send_regularly(self, chat_link, text, interval):
        def is_reply_to_me(client, message):
            print(message)
            replied = message.reply_to_message
            if (
                replied
                and replied.from_user
                and replied.from_user.id == message._client.me.id
            ):
                print("a message has been replied to")
                return True
            else:
                return False

        self.advertising = True

        print(f"chat_link is {chat_link}, text is {text}, interval is {interval}")

        chat = await self.app.get_chat(chat_link)

        async def add_and_inform(client, message):
            print("adding and informing the user", message.from_user.first_name)
            # await client.add_contact(message.from_user.id, message.user.first_name)
            # await message.reply("ضفتك تعال خاص", quote=True)
            print("added to the contacts:", message.from_user.username)

        if chat.id:
            filter_ = filters.chat(chat.id)  # & filters.create(is_reply_to_me)
            print("Chat id for sr is", chat.id)
            self.app.add_handler(self.app.on_message(filter_)(add_and_inform))

            while self.advertising:
                await self.app.send_message(chat.id, text)
                await asyncio.sleep(interval)

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

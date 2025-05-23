import asyncio
import os
from datetime import datetime
from itertools import islice

import dotenv
from pyrogram import Client, enums, filters
from pyrogram.errors import ChannelInvalid, FloodWait
from pyrogram.types import ChatPreview, Message
from tqdm import tqdm

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
                self.parse_command
            )
        )

        # Keep running
        await self.idle()

    async def parse_command(self, client: Client, message: Message):
        print("A message came from the master")

        if message.text[0:3] == "***":
            print("the message is a command")
            command = message.text[3:]
        else:
            print("The message is not a command")
            return

        if command[:2] == "sc":
            target = command[3:]
            if "|" in command:

                if target.count("|") == 1:
                    link, cur = target.split("|")
                    cur = int(cur) if cur.isnumeric() else 0
                    await self.copy_content(link, cur, message.from_user.id, False)

                elif target.count("|") == 2:
                    link, cur, safe = target.split("|")
                    cur = int(cur) if cur.isnumeric() else 0
                    await self.copy_content(link, cur, message.from_user.id, safe)

            else:
                await self.copy_content(target, 0, message.from_user.id, False)

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

    async def copy_content(self, link, cur, customer_id, safe):
        try:
            src_chann = await self.resolve_channel_id(link)
        except Exception as e:
            print(f"Failed to resolve channel: {e}")
            await self.app.send_message(customer_id, e)
            return

        print(f"Source channel ID: {src_chann.id}")

        await self.app.send_message(
            customer_id,
            f"Task recived, channel found, starting Copying Process from {cur}...",
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

        bar_message = await self.app.send_message(
            customer_id,
            "Progress Bar",
        )

        await self.archive_existing_videos(
            src_chann.id,
            cur,
            dest_chann.id,
            customer_id,
            bar_message.id,
            bar_message.date,
            safe,
        )

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

    async def download_and_upload(self, message_or_id, src_id, dest_id):
        try:
            if isinstance(message_or_id, int):
                message = await self.app.get_messages(src_id, message_id)
            else:
                message = message_or_id

            video_path = await message.download()
            thumb_path = await self.app.download_media(message.video.thumbs[0].file_id)

            if not video_path:
                await self.app.send_message(
                    "me", "There was an incomplete download of a file"
                )
                await asyncio.sleep(1)
                return await self.download_and_upload(message, src_id, dest_id)

            # Create caption and other metadata
            caption = message.caption or ""
            duration = message.video.duration

            # Upload to destination
            await self.app.send_video(
                chat_id=dest_id,
                video=video_path,
                thumb=thumb_path,
                caption=caption,
                duration=duration,
                supports_streaming=True,
            )

        except FloodWait as e:
            print(f"Flood wait: {e.value}s")
            if int(e.value) > 60:
                await self.app.send_message(
                    dest_id, f"FloodWait: wait {int(e.value)/60} seconds"
                )
            await asyncio.sleep(e.value)
            await self.download_and_upload(message, src_id, dest_id)

        except Exception as e:
            print(f"Error copying video: {e}")
            await self.app.send_message(
                dest_id, f"Error download and uploading: {e}\nretrying"
            )
            return await self.download_and_upload(message, src_id, dest_id)

        else:
            if os.path.exists(video_path):
                os.remove(video_path)
            if os.path.exists(thumb_path):
                os.remove(thumb_path)

    async def archive_existing_videos(
        self,
        src_id,
        cur,
        dest_id,
        customer_id,
        bar_message_id,
        bar_message_time,
        safe=False,
    ):
        print("Archiving historical videos...")
        src_chann = await self.app.get_chat(src_id)

        if src_chann.has_protected_content:
            await self.archive_protected(
                src_id,
                cur,
                dest_id,
                customer_id,
                bar_message_id,
                bar_message_time,
                safe,
            )
        else:
            # await self.archive_non_protected(src_id, cur, dest_id, customer_id, bar_message_id, bar_message_time)
            await self.archive_non_protected(src_id, cur, dest_id)

    async def archive_protected(
        self,
        src_id,
        cur,
        dest_id,
        customer_id,
        bar_message_id,
        bar_message_time,
        safe=False,
    ):
        video_messages_or_ids = []

        if safe:  # store ids only
            async for message in self.app.get_chat_history(src_id):
                if message.video:
                    video_messages_or_ids.append(message.id)

        else:  # store the whole message
            async for message in self.app.get_chat_history(src_id):
                if message.video:
                    video_messages_or_ids.append(message)

        await self.app.edit_message_text(
            customer_id,
            bar_message_id,
            "non-safe mode is on, Messages Objects Copied 100%",
        )

        video_messages_or_ids = video_messages_or_ids[cur:]
        videos_count = len(video_messages_or_ids)
        for i, video_message in enumerate(video_messages_or_ids):
            await self.download_and_upload(video_message, src_id, dest_id)

            elapsed = (datetime.now() - bar_message_time).seconds
            bar = tqdm.format_meter(
                n=i + 1,
                total=videos_count,
                elapsed=elapsed,
                prefix="Downloading",
                unit="video",
            )
            await self.app.edit_message_text(customer_id, bar_message_id, bar)

    # async def archive_non_protected(self, src_id, cur, dest_id, customer_id, bar_message_id, bar_message_time):
    async def archive_non_protected(self, src_id, cur, dest_id):

        async for message in self.app.get_chat_history(src_id):
            if message.video:
                videos_ids.append(message.id)

        videos_ids = videos_ids[cur:]

        # forward messages indivisually
        for video_message_id in tqdm(videos_ids, unit="video", desc="Forwarding"):
            try:
                await self.app.forward_messages(dest_id, src_id, video_message_id)
            except FloodWait as e:
                print(f"Flood wait: {e.value} seconds")
                await self.app.send_message(
                    dest_id, f"FloodWait: wait {int(e.value)/60} seconds"
                )
                await asyncio.sleep(e.value + 1)
                await message.forward(dest_id)

        # forward in chunks
        # it = iter(videos_ids)
        # messages_chunks = list(iter(lambda: list(islice(it, 100)), []))
        # #
        # print(
        #     f"{len(videos_ids)} vidoes found, divided into {len(messages_chunks)} chunks."
        # )
        #
        # for i, chunk in enumerate(messages_chunks):
        #     try:
        #         await self.app.forward_messages(
        #             dest_id,
        #             src_id,
        #             chunk,
        #         )
        #
        #         elapsed = (datetime.now() - bar_message_time).seconds
        #         bar = tqdm.format_meter(
        #             n=i + 1,
        #             total=len(messages_chunks),
        #             elapsed=elapsed,
        #             prefix="Forwarding",
        #             unit="chunk",
        #         )
        #         await self.app.edit_message_text(customer_id, bar_message_id, bar)
        #
        # except FloodWait as e:
        #     print(f"Flood wait: {e.value} seconds")
        #     await self.app.send_messages(dest_id, f"FloodWait: wait {int(e.value)/60} seconds")
        #     await asyncio.sleep(e.value + 3)
        #     await self.app.forward_messages(
        #         dest_id,
        #         src_id,
        #         chunk,
        #     )

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

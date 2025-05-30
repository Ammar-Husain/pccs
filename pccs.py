import asyncio
import os
import pickle
import random
import re
import signal
import sys
from datetime import datetime, timedelta, timezone
from itertools import islice

import dotenv
from _pickle import UnpicklingError
from pyrogram import Client, enums, filters
from pyrogram.errors import (
    ChannelInvalid,
    ChatAdminRequired,
    FileReferenceExpired,
    FloodPremiumWait,
    FloodWait,
)
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
    MASTER_CHAT_USERNAME = os.getenv("MASTER_CHAT_USERNAME")

    if not MASTER_CHAT_USERNAME == "me" or MASTER_CHAT_USERNAME == "self":
        MASTER_CHAT_USERNAME = "@" + MASTER_CHAT_USERNAME

    if not dotenv.find_dotenv():
        with open(".env", "w") as f:
            f.write("NSS='1'")

    try:
        nss = dotenv.dotenv_values()["NSS"]
    except KeyError:
        nss = "1"

    if nss == "1":
        SESSION_STRING = os.getenv("SESSION_STRING1")
        print(f"SESSION STRING 1 imported from enviroment is {SESSION_STRING}")
        with open(dotenv.find_dotenv(), "w") as f:
            f.write("NSS='2'")

    elif nss == "2":
        SESSION_STRING = os.getenv("SESSION_STRING2")
        print(f"SESSION STRING 2 imported from enviroment is {SESSION_STRING}")
        with open(dotenv.find_dotenv(), "w") as f:
            f.write("NSS='1'")


class ChannelCopier:
    def __init__(self):
        self.app = Client(
            "my_userbot",
            api_id=API_ID,
            api_hash=API_HASH,
            session_string=SESSION_STRING or None,
            in_memory=bool(SESSION_STRING),  # Important for mobile devices
            sleep_threshold=60,
        )
        self.tasks_count = 0
        self.state = {}
        self.tz = timezone(timedelta(hours=2))
        self.advertising = False

        self.shutdown_event = asyncio.Event()
        handle_sigterm = lambda _, __: asyncio.get_event_loop().call_soon_threadsafe(
            self.shutdown_event.set
        )
        signal.signal(signal.SIGTERM, handle_sigterm)
        signal.signal(signal.SIGINT, handle_sigterm)

    @staticmethod
    def allow_cancellation(func):
        async def wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except asyncio.CancelledError:
                for arg in args:
                    if isinstance(arg, Message):
                        command_message = arg
                for arg in kwargs:
                    if isinstance(kwargs[arg], Message):
                        command_message = kwargs[arg]

                print("a task has been cancelled")
                await command_message.reply_text(
                    "this task has been cancelled", quote=True
                )

        return wrapper

    async def start(self):
        print("program started")
        try:
            await self.app.start()
            print("Bot is running. Press Ctrl+C to stop.")

            # dailogs = []
            # async for dialog in self.app.get_dialogs():
            #     dialogs.append(dialog)

            print("Bot started successfully!")
            print("The Bot is awaiting for commands from the master")

            await self.app.send_message(
                MASTER_CHAT_USERNAME, "Listening for commands here"
            )

        except ConnectionError:
            print("ConnectionError:", e)
        except (FloodWait, FloodPremiumWait) as e:
            await self.app.send_message("me", e)

        self.app.add_handler(
            self.app.on_message(
                filters.chat(MASTER_CHAT_USERNAME) & (filters.text | filters.document)
            )(self.parse_command)
        )

        # Keep running
        await self.idle()

    async def parse_command(self, client: Client, message: Message):
        print("A message came from the master!")

        if message.document and "pickled" in message.document.file_name:
            task_id = str(self.tasks_count + 1)

            task = asyncio.create_task(self.file_to_channel(message))
            task.add_done_callback(
                lambda _: task_id in self.state and self.state.pop(task_id)
            )

            self.tasks_count += 1
            self.state[task_id] = {
                "type": "file_to_channel",
                "target": message.document.file_name,
                "started": datetime.now(self.tz),
                "task": task,
            }

            return

        elif not message.text:
            return
        elif message.text[0:3] == "***":
            print("the message is a command")
            command = message.text[3:]
        else:
            print("The message is not a command")
            return

        if command[:2] == "sc":
            target = command[3:]
            if "|" in command:
                params = target.split("|")
                if not len(params) == 4:
                    await message.reply(
                        "the sc command must be in the form `***sc src_link|cur|dest_link|safe` or `***sc src_link`"
                    )
                    return

                src_chann, cur, dest_chann, safe = params

                try:
                    cur = 0 if cur == "" else int(cur)
                except ValueError:
                    await message.reply(
                        f"cur must be empty string or numeric value, {cur} was given instead"
                    )

                task_id = str(self.tasks_count + 1)
                task = asyncio.create_task(
                    self.copy_content(message, src_chann, cur, dest_chann, safe)
                )
                task.add_done_callback(
                    lambda _: task_id in self.state and self.state.pop(task_id)
                )

                self.tasks_count += 1
                self.state[task_id] = {
                    "type": "copy content",
                    "target": src_chann,
                    "started": datetime.now(self.tz),
                    "task": task,
                }

            else:
                task_id = str(self.tasks_count + 1)
                task = asyncio.create_task(self.copy_content(message, target))
                task.add_done_callback(
                    lambda _: task_id in self.state and self.state.pop(task_id)
                )

                self.tasks_count += 1
                self.state[task_id] = {
                    "type": "copy content",
                    "target": target,
                    "started": datetime.now(self.tz),
                    "task": task,
                }

        elif command[:2] == "ec":
            link = command[3:]
            task_id = str(self.tasks_count + 1)
            task = asyncio.create_task(self.channel_to_file(link, message))
            task.add_done_callback(
                lambda _: task_id in self.state and self.state.pop(task_id)
            )

            self.tasks_count += 1
            self.state[task_id] = {
                "type": "channel_to_file",
                "target": link,
                "started": datetime.now(self.tz),
                "task": task,
            }

        elif command[:5] == "state":
            await self.get_state(message)

        elif command[:4] == "kill":
            if len(command) == 4:
                await message.reply(
                    "You must specify the id of the task to kill", qoute=True
                )
            task_id = command[4:]
            await self.kill_task(message, task_id)

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

    @allow_cancellation
    async def copy_content(
        self, command_message, src_link, cur=0, dest_link=None, safe=False
    ):

        try:
            src_chann = await self.resolve_channel_id(src_link)
        except Exception as e:
            print(f"Failed to resolve source channel: {e}")
            await command_message.reply_text(
                f"Failed to resolve source channel\n{e}", quote=True
            )
            return

        print(f"Source channel ID: {src_chann.id}")

        await command_message.reply_text(
            f"Task recived, source channel found, starting Copying Process from {cur}..."
        )
        if dest_link:
            try:
                dest_chann = await self.resolve_channel_id(dest_link)
                msg = await self.app.send_message(dest_chann.id, ".")
                await msg.delete()
            except ChatAdminRequired:
                await command_message.reply_text(
                    "You must have write permissions in destination channel"
                )
                return

            except Exception as e:
                print(f"Failed to resolve destination channel\n{e}")
                await command_message.reply_text(
                    f"Failed to resolve destination channel\n{e}"
                )
                return

        else:
            dest_chann_id = await self.create_destination_channel(
                src_chann.title + " [COPY]"
            )

            dest_chann = await self.app.get_chat(dest_chann_id)

        print(f"Destination channel ID: {dest_chann.id}")

        await command_message.reply_text(
            f"Mission Strarted, you can follow up here {dest_chann.invite_link}"
        )

        bar_message = await command_message.reply_text("Progress Bar")
        await bar_message.pin(both_sides=True)
        await self.archive_existing_videos(
            src_chann.id, cur, dest_chann.id, safe, bar_message
        )

        print("Mission Completed")
        await command_message.reply_text(
            f"Mission Completed, here you are {dest_chann.invite_link}"
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

        # Create new private channel

        try:
            new_channel = await self.app.create_channel(
                title=title, description="Automated Private Copy"
            )

            return new_channel.id

        except (FloodWait, FloodPremiumWait) as e:
            print(f"Waiting {e.value} seconds before retrying...")
            await asyncio.sleep(e.value)
            return await self.create_destination_channel(title)

    async def download_and_upload(self, message_or_id, src_id, dest_id, bar_message):
        if isinstance(message_or_id, int):
            message = await self.app.get_messages(src_id, message_or_id)
        elif isinstance(message_or_id, Message):
            message = message_or_id
        else:
            raise TypeError(
                f"message or id must be of type int or pyrogram.types.Message, {type(message_or_id)} was given instead"
            )

        if not message.video and not message.photo:
            await self.app.send_message(
                dest_id,
                f"message of id {message.id} contain NO media!, how did it reach here?",
            )
            return

        try:
            if message.photo:
                photo_path = await self.app.download_media(message.photo.file_id)
                await self.app.send_photo(dest_id, photo_path, caption=message.caption)
                return

            video_path = await self.app.download_media(message.video.file_id)

            thumb_path = None
            if video_path:
                if message.video.thumbs:
                    thumb_path = await self.app.download_media(
                        message.video.thumbs[0].file_id
                    )
                else:
                    await self.app.send_message(
                        dest_id, "the next video contain no thumbnail"
                    )
            else:
                await self.app.send_message(
                    dest_id, f"Failed to download video of id {message.id}, retrying..."
                )
                await asyncio.sleep(random.uniform(2, 5))
                return await self.download_and_upload(
                    message, src_id, dest_id, bar_message
                )

            print(f"video of id {message.id} has been downloaded successfully")
            # Create caption and other metadata
            caption = message.caption or ""
            duration = message.video.duration

            # Upload to destination
            await self.app.send_video(
                chat_id=dest_id,
                video=video_path,
                thumb=thumb_path,
                caption=caption,
                supports_streaming=True,
                duration=duration,
            )

            print(f"video of id {message.id} has been uploaded successfully")
        except (FloodWait, FloodPremiumWait) as e:
            print(f"Flood wait: {e.value}s")
            try:
                wait_period = timedelta(seconds=e.value)
                now = datetime.now(self.tz)
                end_time = (now + wait_period).strftime("%H:%M:%S")
                cause = re.search(r"(\(.+\))", str(e)).group(1)
                await bar_message.edit_text(
                    bar_message.text
                    + f"\nFloodWaited for {wait_period.seconds//60}:{wait_period.seconds%60}, until {end_time},  {cause}, last_message_id: {message.id}",
                )

            except:
                pass
            sleep_time = e.value if e.value > 10 else e.value * 3
            await asyncio.sleep(sleep_time)
            await self.download_and_upload(message, src_id, dest_id, bar_message)

        except FileReferenceExpired:
            print("expired file")
            raise

        except Exception as e:
            print(f"Error copying video: {e}")
            try:
                await self.app.send_message(
                    "me",
                    f"""
                Error download and uploading: {e}
                video path is {video_path}
                download video size is {os.path.getsize(video_path)}
                telegram video size is {message.video.file_size}
                video message id is {message.id}
                retrying
                """,
                )
            except (FloodWait, FloodPremiumWait):
                pass

            # await asyncio.sleep(3)
            # return await self.download_and_upload(message, src_id, dest_id, bar_message)

        else:
            if video_path and os.path.exists(video_path):
                os.remove(video_path)
            if thumb_path and os.path.exists(thumb_path):
                os.remove(thumb_path)

    async def archive_existing_videos(
        self,
        src_id,
        cur,
        dest_id,
        safe,
        bar_message,
    ):
        print("Archiving historical videos...")
        src_chann = await self.app.get_chat(src_id)

        if src_chann.has_protected_content:
            await self.archive_protected(src_id, cur, dest_id, safe, bar_message)
        else:
            # await self.archive_non_protected(src_id, cur, dest_id, bar_message)
            await self.app.edit_message_text(
                bar_message.chat.id,
                bar_message.id,
                "No need for a bar, channel is not protected, just chill a little bit",
            )
            await self.archive_non_protected(src_id, cur, dest_id, bar_message)

    async def archive_protected(
        self,
        src_id,
        cur,
        dest_id,
        safe,
        bar_message,
    ):
        video_messages_or_ids = []

        if safe:  # store the ids only
            async for message in self.app.get_chat_history(src_id):
                if message.video:
                    video_messages_or_ids.append(message.id)

            await self.app.edit_message_text(
                bar_message.chat.id,
                bar_message.id,
                "Safe mode is on, this give higher stability, but If you were kicked, it is the end",
            )
        else:  # store the whole message
            async for message in self.app.get_chat_history(src_id):
                if message.video:
                    video_messages_or_ids.append(message)

            await self.app.edit_message_text(
                bar_message.chat.id,
                bar_message.id,
                "non-safe mode is on, Messages Objects Copied 100%",
            )

        videos_count = len(video_messages_or_ids)

        if cur:
            if cur >= videos_count:
                await self.app.edit_message_text(
                    bar_message.chat.id,
                    bar_message.id,
                    f"""
                    cur is the video the transfer stop in the last time, it must be less than total videos numbers
                    cur was {cur}, the source channel contain {videos_count} videos
                    """,
                )
                return

            video_messages_or_ids = video_messages_or_ids[cur:]
            videos_count = len(video_messages_or_ids)

        for i, video_message in enumerate(video_messages_or_ids):
            await asyncio.sleep(random.uniform(2, 5))
            await self.download_and_upload(video_message, src_id, dest_id, bar_message)

            elapsed = (datetime.now() - bar_message.date).seconds
            bar = tqdm.format_meter(
                n=i + 1,
                total=videos_count,
                elapsed=elapsed,
                prefix="Downloading",
                unit="video",
            )
            await self.app.edit_message_text(bar_message.chat.id, bar_message.id, bar)

    async def archive_non_protected(self, src_id, cur, dest_id, bar_message):
        # async def archive_non_protected(self, src_id, cur, dest_id):
        video_ids = []
        async for message in self.app.get_chat_history(src_id):
            if message.video:
                video_ids.append(message.id)

        if cur:
            if cur >= len(video_ids):
                await self.app.edit_message_text(
                    bar_message.chat.id,
                    bar_message.id,
                    f"""
                    cur is the video the transfer stop in the last time, it must be less than total videos numbers
                    cur was {cur}, the source channel contain {videos_count} videos
                    """,
                )
                return

            video_ids = video_ids[cur:]

        # forward messages indivisually
        for video_message_id in tqdm(video_ids, unit="video", desc="Forwarding"):
            try:
                await self.app.forward_messages(dest_id, src_id, video_message_id)
            except (FloodWait, FloodPremiumWait) as e:
                wait_period = timedelta(seconds=e.value)
                now = datetime.now(self.tz)
                end_time = (now + wait_period).strftime("%H:%M:%S")
                cause = re.search(r"(\(.+\))", str(e))
                print(f"Flood wait: {e.value} seconds")
                await bar_message.reply_text(
                    f"FloodWait: {wait_period.seconds//60}:{wait_period.seconds%60}, Ends {end_time}, last message id:{video_message_id}, {cause}",
                    qoute=True,
                )

                await asyncio.sleep(e.value + 1)
                await self.app.forward_messages(dest_id, src_id, video_message_id)

        # forward in chunks
        # it = iter(video_ids)
        # messages_chunks = list(iter(lambda: list(islice(it, 100)), []))
        # #
        # print(
        #     f"{len(video_ids)} vidoes found, divided into {len(messages_chunks)} chunks."
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
        #         elapsed = (datetime.now(self.tz) - bar_message.date).seconds
        #         bar = tqdm.format_meter(
        #             n=i + 1,
        #             total=len(messages_chunks),
        #             elapsed=elapsed,
        #             prefix="Forwarding",
        #             unit="chunk",
        #         )
        #         await self.app.edit_message_text(bar_message.chat.id, bar_message.id, bar)
        #
        # except FloodWait as e:
        #     print(f"Flood wait: {e.value} seconds")
        #         wait_period = timedelta(seconds=e.value)
        #         now = datetime.now(self.tz)
        #         end_time = (now + wait_period).strftime("%H:%M:%S")
        #         cause = re.search(r"(\(.+\))", str(e))
        #         await bar_message.reply_text(
        #             f"FloodWait: {wait_period.seconds//60}:{wait_period.seconds%60}, Ends {end_time}, {cause}", quote=True
        #         )
        #     await asyncio.sleep(e.value)
        #     await self.app.forward_messages(
        #         dest_id,
        #         src_id,
        #         chunk,
        #     )

    @allow_cancellation
    async def channel_to_file(self, chann_link, command_message):
        try:
            src_chann = await self.resolve_channel_id(chann_link)
        except:
            await command_message.reply_text("Chat not found")
            return
        else:
            await command_message.reply_text("Chat Found, Exctracting content")

        messages = []
        async for message in self.app.get_chat_history(src_chann.id):
            messages.append(message)

        file_name = src_chann.title + "-history(pickled)"

        with open(file_name, "wb") as f:
            pickle.dump(messages, f)

        try:
            await self.app.send_document(command_message.chat.id, file_name)
        except Exception as e:
            await command_message.reply_text(f"Error sending file, {e}")

        if os.path.exists(file_name):
            os.remove(file_name)

    @allow_cancellation
    async def file_to_channel(self, command_message: Message):
        print("a file to channel process started")
        if not command_message.document:
            await command_message.reply("You need to attach the file to the message")
            return

        file_path = await self.app.download_media(command_message.document.file_id)
        try:
            with open(file_path, "rb") as f:
                messages = pickle.load(f)
        except TypeError:
            await command_message.reply(
                "The file content must be a binary pickled list[pyrogram.types.Messages] object."
            )
            return
        except UnpicklingError:
            await command_message.reply("The file is corrupted")
            return

        messages_exist = False
        all_messages = True
        types = set()
        for message in messages:
            if isinstance(message, Message) and not messages_exist:
                messages_exist = True

            elif not isinstance(message, Message):
                if all_messages:
                    all_messages = False

                types.add(type(message))

        if not messages_exist:
            await command_message.reply(
                f"""
                The file is intact but it doesn't contain any item of type <class pyrogram.types.Message>
                the content of the file is of types {types}
                """
            )
            return

        elif not all_messages:
            await command_message.reply(
                f"""
                Warning: the file is intact and contain messages, but it also contain other types such as {types}\n
                starting the operation the  available messages though... 
                """
            )

            messages = filter(lambda m: isinstance(m, Message))

        else:
            await command_message.reply(
                """The file is intact, the content is messages, starting the operation.."""
            )

        title = (
            command_message.document.file_name.replace("-history(pickled)", "")
            + " from file"
        )
        dest_chann_id = await self.create_destination_channel(title)
        dest_chann = await self.app.get_chat(dest_chann_id)

        await command_message.reply(
            f"""
            You can follow up here: {dest_chann.invite_link}
            """
        )

        bar_message = await command_message.reply("Progress Bar")
        await bar_message.pin(both_sides=True)
        messages_count = len(messages)
        expireds = 0
        for i, message in enumerate(messages):
            try:
                if message.video or message.photo:
                    await self.download_and_upload(
                        message, None, dest_chann.id, bar_message
                    )

                elif message.text:
                    await self.app.send_message(dest_chann.id, message.text)
                elif message.document:
                    await self.app.send_document(
                        dest_chann.id, message.document.file_id, caption=message.caption
                    )
                elif message.audio:
                    await self.app.send_audio(
                        dest_chann.id, message.audio.file_id, caption=message.caption
                    )

            except TypeError:
                pass
            except FileReferenceExpired:
                await self.app.send_message(dest_chann.id, "an expired file")
                expireds += 1
                if expireds >= 5:
                    await command_message.reply(
                        f"""
                        5 consecutive expired files were encountered, this cause process termination, here is the result {dest_chann.invite_link}
                        """
                    )
                    return
            else:
                if expireds:
                    expireds = 0

            elapsed = (datetime.now() - bar_message.date).seconds
            bar = tqdm.format_meter(
                n=i + 1,
                total=messages_count,
                elapsed=elapsed,
                prefix="Uploading...",
                unit="message",
            )
            await bar_message.edit_text(bar)

        await command_message.reply(
            f"""
            Mission Completed, here you are {dest_chann.invite_link}
            """
        )

    async def get_state(self, message):
        state = f"tasks count is {self.tasks_count}.\n"
        for k in self.state:
            task = self.state[k]
            task_str = f"\n\ttask{k}:\n\ttype: {task["type"]}\n\ttarget: {task["target"]}\n\tstarted: {task["started"]}"
            state += task_str

        if not len(self.state):
            state += "No Tasks are running"
        await message.reply_text(state, quote=True)

    async def kill_task(self, message, task_id):
        if not task_id.isnumeric():
            await message.reply_text(
                "Kill command must be in the form '***killn', where n is a numeric value.",
                quote=True,
            )
            return

        if not task_id in self.state:
            if int(task_id) <= self.tasks_count:
                await message.reply(
                    "This task is done or has been killed already", quote=True
                )
            else:
                await message.reply(
                    f"Task not found, No task has the id of {task_id} yet, use state command to see the currently running tasks.",
                    quote=True,
                )
            return

        task = self.state[task_id]["task"]
        task.cancel()

    # async def send_regularly(self, chat_link, text, interval):
    #     def is_reply_to_me(client, message):
    #         print(message)
    #         replied = message.reply_to_message
    #         if (
    #             replied
    #             and replied.from_user
    #             and replied.from_user.id == message._client.me.id
    #         ):
    #             print("a message has been replied to")
    #             return True
    #         else:
    #             return False
    #
    #     self.advertising = True
    #
    #     print(f"chat_link is {chat_link}, text is {text}, interval is {interval}")
    #
    #     chat = await self.app.get_chat(chat_link)
    #
    #     async def add_and_inform(client, message):
    #         print("adding and informing the user", message.from_user.first_name)
    #         # await client.add_contact(message.from_user.id, message.user.first_name)
    #         # await message.reply("ضفتك تعال خاص", quote=True)
    #         print("added to the contacts:", message.from_user.username)
    #
    #     if chat.id:
    #         filter_ = filters.chat(chat.id)  # & filters.create(is_reply_to_me)
    #         print("Chat id for sr is", chat.id)
    #         self.app.add_handler(self.app.on_message(filter_)(add_and_inform))
    #
    #         while self.advertising:
    #             await self.app.send_message(chat.id, text)
    #             await asyncio.sleep(interval)

    async def idle(self):
        await self.shutdown_event.wait()
        await self.stop()

    async def stop(self):
        try:
            await self.app.send_message(MASTER_CHAT_USERNAME, "See You Later!")
        except Exception as e:
            print(e)

        for task in self.state:
            task["task"].cancel()

        await self.app.stop()
        sys.exit(0)


async def main():
    copier = ChannelCopier()
    try:
        await copier.start()

    except Exception as e:
        print(f"Fatal error: {e}")
        await copier.app.send_message(MASTER_CHAT_USERNAME, f"an Error: {e}")

    finally:
        if copier.app.is_connected:
            await copier.stop()


if __name__ == "__main__":
    asyncio.get_event_loop().run_until_complete(main())

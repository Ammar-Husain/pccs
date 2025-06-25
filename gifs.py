from pyrogram import Client
from pyrogram.raw import functions, types
from tqdm import tqdm

from get_client import get_client

app = get_client()


async def remove_all_saved_gifs():
    async with app:
        # Get saved GIFs
        print("Your Gifs will be deleted in groups of 200 hundred gift each")
        while True:
            saved_gifs = await app.invoke(functions.messages.GetSavedGifs(hash=0))
            if not saved_gifs:
                print("✅ All GIFS Has Been Removed")
                break

            # Loop through each GIF and unsave it
            for doc in tqdm(saved_gifs.gifs):
                await app.invoke(
                    functions.messages.SaveGif(
                        id=types.InputDocument(
                            id=doc.id,
                            access_hash=doc.access_hash,
                            file_reference=doc.file_reference,
                        ),
                        unsave=True,
                    )
                )


app.run(remove_all_saved_gifs())

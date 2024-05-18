import os
from dotenv import load_dotenv
import discord
from discord.ext import commands
import requests
import easyocr
from PIL import Image

def get_name():
    image_path = 'submitted_image.png'
    img = Image.open(image_path)
    width, height = img.size
    new_width = width // 2
    new_height = height // 10
    left = 0
    top = 0
    right = new_width
    bottom = new_height
    cropped_img = img.crop((left, top, right, bottom))
    cropped_img.save("cropped.png")

    reader = easyocr.Reader(['en'])  # Specify languages to be used (e.g., English)

    # Read the image file and perform OCR
    results = reader.readtext("cropped.png")
    # Extract and print the text
    return results[0][1]

def save_image(image_data, folder_path, filename):
    if not os.path.exists(folder_path):
        os.makedirs(folder_path)
    with open(os.path.join(folder_path, filename), "wb") as file:
        file.write(image_data)

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

intents=discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print("Bot is online")
    
@bot.command()
async def hello(ctx):
    await ctx.send("Hello!")

@bot.command()
async def submit(ctx):
    user_id = ctx.author.id
    char_list = []

    if ctx.message.attachments:
        for i, attachment in enumerate(ctx.message.attachments):
            # Download the image
            image_url = attachment.url
            image_data = requests.get(image_url).content
            
            with open("submitted_image.png", "wb") as file:
                file.write(image_data)

            name = get_name().lower()
            char_list.append(name)

            # Create folders if they don't exist
            character_folder = os.path.join("character", name)
            user_folder = os.path.join("user", str(user_id))
            save_image(image_data, character_folder, f"{name}_{user_id}.png")
            save_image(image_data, user_folder, f"{name}_{user_id}.png")
        
        # Send names of characters submitted
        if char_list:
            char_list_str = ", ".join(set(char_list))
            await ctx.send(f"Characters submitted: {char_list_str}")
        else:
            await ctx.send("No characters submitted.")
    else:
        await ctx.send("No attachments found in your message.")


@bot.command()
async def view(ctx, *, query: str = None):
    if query is None:
        await ctx.send("Please specify a user or character name.")
        return

    query = query.lower()

    member = None
    if ctx.message.mentions:
        member = ctx.message.mentions[0]  # Get the mentioned member
        query = member.display_name.lower()  # Set query to member's display name

    user_folder = os.path.join("user", str(member.id) if member else "")
    character_folder = os.path.join("character", query)

    if os.path.exists(user_folder) and member:
        await ctx.send(f"Displaying {member.display_name}'s characters:")
        files = os.listdir(user_folder)
        if files:
            for file_name in files:
                with open(os.path.join(user_folder, file_name), "rb") as file:
                    await ctx.send(file=discord.File(file))
            await ctx.send(f"End of {member.display_name}'s characters.")
        else:
            await ctx.send(f"{member.display_name}'s folder is empty.")
    elif os.path.exists(character_folder):
        await ctx.send(f"Displaying all results for {query}:")
        files = os.listdir(character_folder)
        if files:
            for file_name in files:
                with open(os.path.join(character_folder, file_name), "rb") as file:
                    await ctx.send(file=discord.File(file))
            await ctx.send(f"End of results for {query}.")
        else:
            await ctx.send(f"{query}'s folder is empty.")
    else:
        await ctx.send(f"No folder found for '{query}'.")

bot.run(TOKEN)



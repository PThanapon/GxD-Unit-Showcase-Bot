import os
from dotenv import load_dotenv
import discord
from discord.ext import commands
import requests
from PIL import Image
from io import BytesIO
import re
import zipfile
import asyncio
import subprocess

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
OCR_SPACE_API_KEY = os.getenv("OCR_SPACE_API_KEY")

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

def compress_image(image, max_size_kb=500):
    output_io = BytesIO()

    # Convert image to RGB mode (JPEG doesn't support transparency)
    if image.mode in ("RGBA", "P"):
        image = image.convert("RGB")

    quality = 85

    while True:
        image.save(output_io, format='JPEG', quality=quality)
        size_kb = output_io.tell() / 1024
        if size_kb <= max_size_kb or quality <= 5:
            break
        output_io.seek(0)
        output_io.truncate()
        quality -= 5

    return output_io.getvalue()

def get_closest_match(ocr_result, character_list):
    print(ocr_result)
    ocr_result = re.sub(r'[^\w\s-]', '', ocr_result.lower())

    closest_match = None
    closest_distance = float('inf')
    for character_name in character_list:
        normalized_name = re.sub(r'[^\w\s-]', '', character_name.lower())
        distance = levenshtein_distance(ocr_result, normalized_name)
        if distance < closest_distance:
            closest_match = character_name
            closest_distance = distance

    return closest_match

def levenshtein_distance(s1, s2):
    if len(s1) > len(s2):
        s1, s2 = s2, s1

    distances = range(len(s1) + 1)
    for i2, c2 in enumerate(s2):
        distances_ = [i2+1]
        for i1, c1 in enumerate(s1):
            if c1 == c2:
                distances_.append(distances[i1])
            else:
                distances_.append(1 + min((distances[i1], distances[i1 + 1], distances_[-1])))
        distances = distances_
    return distances[-1]

def save_image(image_data, folder_path, filename):
    if not os.path.exists(folder_path):
        os.makedirs(folder_path)
    with open(os.path.join(folder_path, filename), "wb") as file:
        file.write(image_data)

@bot.command()
async def test_alias(ctx, *, query = None):
    character_list, _, info_list = load_list()
    alias_dict = get_alias_dict()

    for k, v in alias_dict.items():
        if query in v:
            query = k
    await ctx.send(get_closest_match(query, character_list))
    

@bot.event
async def on_ready():
    print("Bot is online")

@bot.command()
async def submit(ctx):
    user_id = ctx.author.id
    char_list = []
    
    if user_id == 361584297599172620 and rei_check():
        await ctx.send("High risk target detected, verification will be needed. <@258120963508535297>")
    elif user_id == 361584297599172620:
        await ctx.send("Dab has already been mentioned, verification will be needed.")
    
    if ctx.message.mentions:
        user_id = ctx.message.mentions[0].id

    if ctx.message.attachments:
        character_list, available_list = load_list()
        for i, attachment in enumerate(ctx.message.attachments):
            image_url = attachment.url
            image_data = requests.get(image_url).content
            with open("submitted_image.png", "wb") as file:
                file.write(image_data)

            ocr_result = get_name("submitted_image.png", character_list).lower()

            print(ocr_result)

            if ocr_result == "eda bully":
                await ctx.send("Stop bullying Eda! ~~or maybe something else went wrong~~")
                return
            
            if ocr_result == "error":
                await ctx.send("Something went wrong, please try again later.")
                return
            
            char_list.append(ocr_result)

            # Update the available list
            if ocr_result not in available_list:
                available_list.append(ocr_result)
                save_available_list(available_list)

            character_folder = os.path.join("character", ocr_result.lower())
            user_folder = os.path.join("user", str(user_id))
            save_image(compress_image(Image.open("submitted_image.png")), character_folder, f"{ocr_result}_{user_id}.png".lower())
            #save_image(image_data, user_folder, f"{ocr_result}_{user_id}.png".lower())

        if char_list:
            await ctx.send(f"Characters submitted: {', '.join(set(char_list))}")
        else:
            await ctx.send("No characters submitted.")
    else:
        await ctx.send("No attachments found in your message.")

def get_name(image_path, character_list):
    img = Image.open(image_path)
    width, height = img.size
    new_width = width // 2
    new_height = height // 10
    left = 0
    top = 0
    right = new_width
    bottom = new_height
    cropped_img = img.crop((left, top, right, bottom))

    compressed_image_data = compress_image(cropped_img)

    response = requests.post(
        "https://api.ocr.space/parse/image",
        files={"filename": ("image.jpg", compressed_image_data)},
        data={"apikey": OCR_SPACE_API_KEY}
    )

    result = response.json()
    if result["IsErroredOnProcessing"]:
        print("Error in OCR processing")
        return "error"

    parsed_text = result["ParsedResults"][0]["ParsedText"].strip()
 
    if parsed_text == "":
        return "Eda Bully"
  
    closest_match = get_closest_match(parsed_text, character_list)
    return closest_match

def save_alias(dct):
    with open("alias.txt", "w") as file:
        for k, v in dct.items():
            if v:
                v = [n.lower() for n in v]
                line = k.lower() + ", " + ", ".join(v) + "\n"
            else:
                line = k.lower() + "\n"
            file.write(line)
            
def save_info(dct):
    with open("infolink.txt", "w") as file:
        for k, v in dct.items():
            line = f"{k}, {v} \n"
            file.write(line)

def get_alias_dict():
    alias_dict = {}

    with open("alias.txt", "r") as file:
        for line in file.readlines():
            lst = line.strip().split(", ")
            alias_dict[lst[0]] = lst[1:]

    return alias_dict

def get_info_dict():
    info_dict = {}

    with open("infolink.txt", "r") as file:
        for line in file.readlines():
            lst = line.strip().split(", ")
            info_dict[lst[0]] = lst[1]

    return info_dict

def rei_check():
    with open("rei.txt", "r") as f:
        rei = f.read().strip()
    return int(rei)

@bot.command()
async def view(ctx, *, query = None):
    if ctx.author.id == 510780948514734100:
        await ctx.send("Please stop bullying Ruele!")
    if query is None:
        await ctx.send("Please specify a user and/or character name.")
        return
    
    # Extract user mention and character name from the query
    member = None
    character_name = query

    if ctx.message.mentions:
        member = ctx.message.mentions[0]
        character_name = query.replace(member.mention, "").strip().lower()
        
    print(f"character name: {character_name}")
    print(f"member mentioned: {member}")

    character_list, _ = load_list()
    alias_dict = get_alias_dict()
    info_dict = get_info_dict()
    

    for k, v in alias_dict.items():
        if character_name.lower() in v:
            print(f"alias {character_name.lower()} found for {k}")
            character_name = k

    if character_name:
        print(f"matching {character_name}")
        closest_match = get_closest_match(character_name.lower().strip(), character_list)
        character_name = closest_match.lower()

    user_folder = os.path.join("user", str(member.id) if member else "").lower()
    character_folder = os.path.join("character", character_name).lower() if character_name else ""
    
    print(member, character_name, user_folder, character_folder)

    if member and character_name:
        # Check if there are images for the specific character and user
        user_character_folder = os.path.join("character", character_name, f"{character_name}_{str(member.id)}.png")
        if os.path.exists(user_character_folder):
            await ctx.send(f"Displaying {member.display_name}'s {character_name}:")
            with open(user_character_folder, "rb") as file:
                await ctx.send(file=discord.File(file))
            await ctx.send(f"End of {member.display_name}'s {character_name}.")
        else:
            await ctx.send(f"No images found for {member.display_name}'s {character_name}.")	
    elif member:
        await ctx.send(f"Please do !view @user (character name) instead!")
        return
        if member.id in [701482792273444986]:
            await ctx.send(f"Too much attachment. For the health of the unit showcase bot, viewing is aborted")
            return
        # Display all characters for the specified user
        if os.path.exists(user_folder):
            await ctx.send(f"Displaying {member.display_name}'s characters:")
            files = os.listdir(user_folder)
            if files:
                attachments = []
                character_names = []

                for file_name in files:
                    with open(os.path.join(user_folder, file_name), "rb") as file:
                        character_name = os.path.splitext(file_name)[0].split('_')[0]
                        character_names.append(character_name)
                        attachments.append(discord.File(file, filename=file_name))

                        # Check if we have reached the attachment limit
                        if len(attachments) == 10:
                            await ctx.send(
                                content=f"{member.display_name}'s characters: {', '.join(character_names)}",
                                files=attachments
                            )
                            # Reset for the next batch
                            attachments = []
                            character_names = []

                # Send any remaining attachments
                if attachments:
                    await ctx.send(
                        content=f"{member.display_name}'s characters: {', '.join(character_names)}",
                        files=attachments)
          
                await ctx.send(f"End of {member.display_name}'s characters.")
            else:
                await ctx.send(f"{member.display_name}'s folder is empty.")
        else:
            await ctx.send(f"No folder found for {member.display_name}.")

    elif character_name:
        # Display all users for the specified character
        if os.path.exists(character_folder):
            if character_name in info_dict:
                await ctx.send(f"## __[{character_name.title()}'s Build Recommendations]({info_dict[character_name]})__ ```Click above for build information ``` \n")

            await ctx.send(f"\n Displaying all results for {character_name}:")
            files = os.listdir(character_folder)
            if files:
                attachments = []
                user_names = []

                for file_name in files:
                    with open(os.path.join(character_folder, file_name), "rb") as file:
                        user_id = file_name.split('_')[-1].split('.')[0]
                        user = await bot.fetch_user(user_id)
                        user_names.append(f"{user.display_name}")
                        attachments.append(discord.File(file, filename=file_name))

                        # Check if we have reached the attachment limit
                        if len(attachments) == 10:
                            message_content = f"{character_name} of: {', '.join(user_names)}"
                            await ctx.send(
                                content=message_content,
                                files=attachments
                            )
                            # Reset for the next batch
                            attachments = []
                            user_names = []

                # Send any remaining attachments
                if attachments:
                    message_content = f"{character_name} of: {', '.join(user_names)}"
                    await ctx.send(
                        content=message_content,
                        files=attachments
                    )

            await ctx.send(f"End of results for {character_name}.")
        else:
            await ctx.send(f"No folder found for '{character_name}'.")


    else:
        await ctx.send("Please specify a user and/or character name.")

@bot.command()
async def unsubmit(ctx, *, query = None):
    if query is None:
        await ctx.send("Please specify a user and/or character name.")
        return

    # Extract user mention and character name from the query
    user_id = ctx.author.id
    print(user_id)
    character_name = query.strip()

    if ctx.message.mentions and str(user_id) != "258120963508535297":
        await ctx.send("You do not have permission to ping remove")
        return
    elif ctx.message.mentions and user_id == "258120963508535297":
        member = ctx.message.mentions[0]
        user_id = member.id
        character_name = query.replace(member.mention, "").strip()

    character_list, _ = load_list()
    alias_dict = get_alias_dict()

    for k, v in alias_dict.items():
        if query in v:
            character_name = k

    remove_all = False
    if character_name.lower() == "all":
        remove_all =  True

    if character_name:
        closest_match = get_closest_match(character_name, character_list)
        print(closest_match)
        character_name = closest_match.lower()
    else:
        ctx.send("Please do !unsubmit (character name), otherwise do !unsubmit all, to remove all your submissions")

    user_folder = os.path.join("user", str(user_id))

    print(remove_all)
    if remove_all:
        delete_list = []
        if os.path.exists(user_folder):
            files = os.listdir(user_folder)
            if files:
                for file_name in files:
                    with open(os.path.join(user_folder, file_name), "rb") as file:
                        character_name = os.path.splitext(file_name)[0].split('_')[0]
                        delete_list.append(character_name)
                    os.remove(os.path.join(user_folder, file_name))
            else:
                await ctx.send("No submission to delete.")
        else:
            await ctx.send(f"No folder found.")

        for character in delete_list:
            user_character_folder = os.path.join("character", character, f"{character}_{user_id}.png").lower()
            os.remove(user_character_folder)
        await ctx.send("All submission removed successfully")
    else:
        character_user_png = os.path.join("character", character_name, f"{character_name}_{user_id}.png")
        user_character_png = os.path.join("user", str(user_id), f"{character_name}_{user_id}.png")
        user_folder = os.path.join("user", str(user_id))

        try:
            print(user_character_png)
            print(character_user_png)
            os.remove(character_user_png)
            await ctx.send(f"Removed submission for {character_name} successfully")
        except Exception as e:
            print(e)
            await ctx.send("Error in removal")


@bot.command()
async def available(ctx):
    # Load the character list and available list
    _, available_list = load_list()

    # Sort the available list alphabetically
    available_list_sorted = sorted(available_list)

    # Join the sorted list with new line characters
    available_characters = ", ".join(available_list_sorted)

    # Send the available characters as a message
    await ctx.send(f"Available characters:\n\n{available_characters}")

@bot.command()
async def alias(ctx, *, query = None):
    if not query or "," not in query:
        await ctx.send("Please submit alias in the format '!alias (alias/abbrievation), (character name)'")
        return

    alias_dict = get_alias_dict()

    input_alias, input_character  = query.split(",")
    character_list, _ = load_list()
    input_alias, character = input_alias.lower(), get_closest_match(input_character, character_list).lower().strip()
    print(f"alias: {input_alias}, character: {character}")
    
    if (input_alias in alias_dict) or (character.strip() not in character_list):
        print(input_alias in alias_dict, character not in character_list)
        if input_alias in alias_dict:
            await ctx.send("Please submit alias in the format '!alias (alias/abbrievation), (character name)'")
        elif character.strip() not in character_list:
            await ctx.send(f"{character} not in character list")
        return
    else:
        for k, v in alias_dict.items():
            if input_alias in v:
                await ctx.send(f"Alias {input_alias} is taken for {k}")
                return
        print(character)
        
        temp = []
        if not alias_dict.get(character):
            alias_dict[character] = [input_alias]
        else:
            alias_dict[character].append(input_alias)
        save_alias(alias_dict)
    await ctx.send(f"Alias {input_alias} set for {input_character}")
    
@bot.command()
async def info(ctx, *, query = None):
    if "," not in query:
        await ctx.send("Please submit alias in the format '!info (link), (character name)'")
        return

    info_dict = get_info_dict()

    link, character  = query.split(",")
    character_list, _ = load_list()
    character = get_closest_match(character, character_list).lower()
    
    info_dict[character] = link
    save_info(info_dict)
    await ctx.send(f"Link set/updated for {character}")

@bot.command()
async def remove_alias(ctx, *, query = None):
    if "," not in query:
        await ctx.send("Please submit alias in the format '!remove_alias (alias/abbrievation), (character name)'")
        return

    alias_dict = get_alias_dict()

    input_alias, input_character  = query.split(",")
    character_list, _ = load_list()
    input_alias, character = input_alias.lower(), get_closest_match(input_character, character_list).lower()
    if (input_alias in alias_dict) or (character not in alias_dict):
        await ctx.send("Please submit alias in the format '!alias (alias/abbrievation), (character name)'")
        return
    else:
        print(character)
        try:
            alias_dict[character].remove(input_alias)
        except:
            await ctx.send("Either input alias doesnt exist or SirDab messes something up")
        save_alias(alias_dict)
    await ctx.send(f"Alias {input_alias} remove for {input_character}")

@bot.command()
async def get_alias(ctx, *, query):
    character_list, _ = load_list()
    character = get_closest_match(query, character_list).lower()
    await ctx.send(f"Alias for '{character}' are: {get_alias_dict()[character]}")
    
@bot.command()
async def template(ctx):
    with open("GxD Hero Recommendation Template.txt", "rb") as f:
        await ctx.send("Here is your file:", file=discord.File(f, "GxD Hero Recommendation Template.txt"))

# ignore
'''
@bot.command()
async def backup(ctx, start: str = "0", end: str = "0"):
    if not ctx.author.id == 258120963508535297:
        await ctx.send("Nothing happened!")
        return
        
    zip_filename = "backup.zip"
    if start == "0" and end == "0": 
        file_list = [
            "main.py", 
            "alias.txt", 
            "available_list.txt", 
            "character_list.txt", 
            "infolink.txt", 
            "GxD Hero Recommendation Template.txt"
        ] 
    else: file_list = []
    folders_list = [
        "character"
    ]

    def create_zip():
        with zipfile.ZipFile(zip_filename, 'w') as zipf:
            # Add the static files to the zip
            for file in file_list:
                if os.path.isfile(file):
                    zipf.write(file)

            # Add the characters within the specified interval to the zip
            for folder in folders_list:
                if os.path.isdir(folder):
                    for root, dirs, files in os.walk(folder):
                        for file in files:
                            # Assuming character files start with letters (a-z)
                            character_name = os.path.splitext(file)[0]  # Remove file extension

                            # Check if the character is within the specified range
                            if start and end:
                                if start <= character_name[0] <= end:
                                    full_path = os.path.join(root, file)
                                    zipf.write(full_path, os.path.relpath(full_path, folder))
                            else:
                                # If no range is specified, include all characters
                                full_path = os.path.join(root, file)
                                zipf.write(full_path, os.path.relpath(full_path, folder))

    await asyncio.to_thread(create_zip)

    max_file_size = 8 * 1024 * 1024  # 8MB (Discord limit for non-Nitro users)

    try:
        # Handle large zip file splitting into parts
        if os.path.getsize(zip_filename) > max_file_size:
            part_number = 1
            with open(zip_filename, "rb") as f:
                while True:
                    chunk = f.read(max_file_size)
                    if not chunk:
                        break
                    part_filename = f"{zip_filename}.part{part_number}"
                    with open(part_filename, "wb") as part_file:
                        part_file.write(chunk)
                    await ctx.send(file=discord.File(part_filename))
                    os.remove(part_filename)  # Delete the part file after sending
                    part_number += 1
        else:
            await ctx.send(file=discord.File(zip_filename))
    finally:
        # Delete the original zip file after sending
        if os.path.exists(zip_filename):
            os.remove(zip_filename)
'''

def load_list():
    with open("character_list.txt", "r") as file:
        c_list = file.read().splitlines()
        character_list = [c.lower() for c in c_list]
    if os.path.exists("available_list.txt"):
        with open("available_list.txt", "r") as file:
            available_list = file.read().splitlines()
    else:
        available_list = []
    return character_list, available_list

def save_available_list(available_list):
    with open("available_list.txt", "w") as file:
        file.write("\n".join(available_list))

@bot.command()
async def folder(ctx):
    _, available_list = load_list()
    for char in available_list:
        if not os.path.exists(f"character/{char}"):
            os.makedirs(f"character/{char}")
        
@bot.command()
async def me(ctx):
    user_id = ctx.author.id
    character_list = []
    folder = os.listdir("character")
    for character in folder:
        submission = os.listdir(f"character/{character}")
        if f"{character}_{user_id}.png" in submission:
            character_list.append(character)
            
    if character_list:
        await ctx.send(f"You have {len(character_list)} submissions.\n\n{', '.join(character_list)}")
    else:
        await ctx.send(f"Unable to find any submission")        

@bot.command()
async def homework(ctx):
    await ctx.send('running "homework.py"')
    subprocess.run(["python", "homework.py"])
    await ctx.send('finished executing')
    

bot.run(TOKEN)









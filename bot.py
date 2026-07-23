import os
import json
import time
from collections import defaultdict

import discord
from discord import app_commands
from discord.ext import commands
from googletrans import Translator


TOKEN = os.getenv("DISCORD_TOKEN")


USER_COOLDOWN = 8
USER_MINUTE_LIMIT = 10
USER_DAILY_LIMIT = 100
GLOBAL_DAILY_LIMIT = 1500

CACHE_HOURS = 24
MAX_MESSAGE_LENGTH = 1000


DATA = "/data" if os.path.exists("/data") else "."
os.makedirs(DATA, exist_ok=True)

CACHE_FILE = f"{DATA}/cache.json"
USAGE_FILE = f"{DATA}/usage.json"


def load(file, default):
    if os.path.exists(file):
        with open(file, "r") as f:
            return json.load(f)
    return default


def save(file, data):
    with open(file, "w") as f:
        json.dump(data, f, indent=2)


cache = load(CACHE_FILE, {})

usage = load(
    USAGE_FILE,
    {
        "users": {},
        "global": 0,
        "date": time.strftime("%Y-%m-%d")
    }
)


# Reset daily usage
today = time.strftime("%Y-%m-%d")

if usage.get("date") != today:
    usage = {
        "users": {},
        "global": 0,
        "date": today
    }

    save(USAGE_FILE, usage)



translator = Translator()


intents = discord.Intents.default()
intents.message_content = True


bot = commands.Bot(
    command_prefix="!",
    intents=intents
)


cooldowns = {}
minute = defaultdict(list)



async def translate_message(
    interaction: discord.Interaction,
    message: discord.Message,
    target: str
):

    if message.author.bot:
        await interaction.response.send_message(
            "Bots cannot be translated.",
            ephemeral=True
        )
        return


    text = message.content.strip()


    if not text:
        await interaction.response.send_message(
            "No text found.",
            ephemeral=True
        )
        return


    if len(text) > MAX_MESSAGE_LENGTH:
        await interaction.response.send_message(
            "Message too long.",
            ephemeral=True
        )
        return



    uid = str(interaction.user.id)

    now = time.time()



    # cooldown
    if uid in cooldowns:

        if now - cooldowns[uid] < USER_COOLDOWN:

            await interaction.response.send_message(
                "Please wait before translating again.",
                ephemeral=True
            )
            return


    cooldowns[uid] = now



    # per minute
    minute[uid] = [
        x for x in minute[uid]
        if now - x < 60
    ]


    if len(minute[uid]) >= USER_MINUTE_LIMIT:

        await interaction.response.send_message(
            "You reached the minute limit.",
            ephemeral=True
        )
        return


    minute[uid].append(now)



    # daily
    user_count = usage["users"].get(uid,0)


    if user_count >= USER_DAILY_LIMIT:

        await interaction.response.send_message(
            "You reached your daily limit.",
            ephemeral=True
        )
        return



    if usage["global"] >= GLOBAL_DAILY_LIMIT:

        await interaction.response.send_message(
            "The bot daily limit has been reached.",
            ephemeral=True
        )
        return



    await interaction.response.defer(ephemeral=True)



    key = f"{target}:{text}"



    if key in cache:

        if now - cache[key]["time"] < CACHE_HOURS * 3600:

            result = cache[key]["text"]

        else:
            del cache[key]
            result = None

    else:
        result = None



    if result is None:

        translated = translator.translate(
            text,
            dest=target
        )

        result = translated.text


        cache[key] = {
            "text": result,
            "time": now
        }


        save(
            CACHE_FILE,
            cache
        )



    usage["users"][uid] = user_count + 1
    usage["global"] += 1

    save(
        USAGE_FILE,
        usage
    )



    embed = discord.Embed(
        title="🌎 Translation"
    )


    embed.add_field(
        name="Original",
        value=text[:1024],
        inline=False
    )


    embed.add_field(
        name="Translated",
        value=result[:1024],
        inline=False
    )


    await interaction.followup.send(
        embed=embed,
        ephemeral=True
    )





# ==========================
# DISCORD RIGHT CLICK APPS
# ==========================


@app_commands.context_menu(
    name="Translate to English"
)
async def translate_english(
    interaction: discord.Interaction,
    message: discord.Message
):

    await translate_message(
        interaction,
        message,
        "en"
    )



@app_commands.context_menu(
    name="Translate to Spanish"
)
async def translate_spanish(
    interaction: discord.Interaction,
    message: discord.Message
):

    await translate_message(
        interaction,
        message,
        "es"
    )




@bot.event
async def on_ready():

    bot.tree.add_command(
        translate_english
    )

    bot.tree.add_command(
        translate_spanish
    )


    await bot.tree.sync()


    print(
        f"Logged in as {bot.user}"
    )


bot.run(TOKEN)







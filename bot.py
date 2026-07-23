import os
import json
import time
from collections import defaultdict

import discord
from discord import app_commands
from discord.ext import commands
from deep_translator import GoogleTranslator


TOKEN = os.getenv("DISCORD_TOKEN")


# =========================
# LIMIT SETTINGS
# =========================

USER_COOLDOWN = 8
USER_MINUTE_LIMIT = 10
USER_DAILY_LIMIT = 100
GLOBAL_DAILY_LIMIT = 1500

CACHE_HOURS = 24
MAX_MESSAGE_LENGTH = 1000


# =========================
# STORAGE
# =========================

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



cache = load(
    CACHE_FILE,
    {}
)


usage = load(
    USAGE_FILE,
    {
        "users": {},
        "global": 0,
        "date": time.strftime("%Y-%m-%d")
    }
)


# Reset daily counters

today = time.strftime("%Y-%m-%d")

if usage.get("date") != today:

    usage = {
        "users": {},
        "global": 0,
        "date": today
    }

    save(
        USAGE_FILE,
        usage
    )



# =========================
# DISCORD SETUP
# =========================


intents = discord.Intents.default()
intents.message_content = True


bot = commands.Bot(
    command_prefix="!",
    intents=intents
)



cooldowns = {}

minute_usage = defaultdict(list)



# =========================
# TRANSLATION FUNCTION
# =========================


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
            "Message is too long.",
            ephemeral=True
        )

        return



    now = time.time()

    user_id = str(interaction.user.id)



    # cooldown

    if user_id in cooldowns:

        if now - cooldowns[user_id] < USER_COOLDOWN:

            await interaction.response.send_message(
                "Please wait before translating again.",
                ephemeral=True
            )

            return



    cooldowns[user_id] = now



    # minute limit

    minute_usage[user_id] = [

        t for t in minute_usage[user_id]

        if now - t < 60

    ]


    if len(minute_usage[user_id]) >= USER_MINUTE_LIMIT:


        await interaction.response.send_message(
            "You reached the minute limit.",
            ephemeral=True
        )

        return



    minute_usage[user_id].append(now)



    # daily limits

    current_user = usage["users"].get(
        user_id,
        0
    )



    if current_user >= USER_DAILY_LIMIT:


        await interaction.response.send_message(
            "You reached your daily translation limit.",
            ephemeral=True
        )

        return



    if usage["global"] >= GLOBAL_DAILY_LIMIT:


        await interaction.response.send_message(
            "The bot has reached its daily global limit.",
            ephemeral=True
        )

        return



    await interaction.response.defer(
        ephemeral=True
    )



    # CACHE

    cache_key = f"{target}:{text}"



    result = None



    if cache_key in cache:

        if now - cache[cache_key]["time"] < CACHE_HOURS * 3600:

            result = cache[cache_key]["text"]



    # Translate if not cached

    if result is None:


        result = GoogleTranslator(
            source="auto",
            target=target
        ).translate(text)



        cache[cache_key] = {

            "text": result,

            "time": now

        }


        save(
            CACHE_FILE,
            cache
        )



    # Usage tracking

    usage["users"][user_id] = current_user + 1

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



# =========================
# DISCORD APP COMMANDS
# =========================


@app_commands.context_menu(
    name="Translate to English"
)
async def translate_to_english(
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
async def translate_to_spanish(
    interaction: discord.Interaction,
    message: discord.Message
):

    await translate_message(
        interaction,
        message,
        "es"
    )



# =========================
# START BOT
# =========================


@bot.event
async def on_ready():

    # Prevent duplicate registrations

    if not bot.tree.get_commands():

        bot.tree.add_command(
            translate_to_english
        )

        bot.tree.add_command(
            translate_to_spanish
        )


    await bot.tree.sync()


    print(
        f"Logged in as {bot.user}"
    )



bot.run(TOKEN)

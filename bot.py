import os
import json
import time
import uuid
import requests
from collections import defaultdict

import discord
import deepl

from discord import app_commands
from discord.ext import commands
from deep_translator import GoogleTranslator

# =========================
# SPANISH GAMING SLANG
# =========================

SLANG_PHRASES = {
    "bingo mano": "bingo bro",
    "gracias mano": "gracias bro",
    "hola mano": "hola bro",
    "que pasa mano": "que pasa bro",
    "qué pasa mano": "qué pasa bro",
    "dale mano": "dale bro",
    "vamos mano": "vamos bro",
}


def apply_slang_fixes(text):

    for old, new in SLANG_PHRASES.items():

        text = text.replace(
            old,
            new
        )

    return text
# =========================
# API KEYS
# =========================

TOKEN = os.getenv("DISCORD_TOKEN")

DEEPL_API_KEY = os.getenv("DEEPL_API_KEY")

AZURE_TRANSLATOR_KEY = os.getenv("AZURE_TRANSLATOR_KEY")

AZURE_TRANSLATOR_REGION = os.getenv("AZURE_TRANSLATOR_REGION")


# =========================
# LIMIT SETTINGS
# =========================

USER_COOLDOWN = 8

USER_MINUTE_LIMIT = 10

USER_DAILY_LIMIT = 100

GLOBAL_DAILY_LIMIT = 1500


CACHE_HOURS = 24

MAX_MESSAGE_LENGTH = 1000


# DeepL free monthly character safety limit

DEEPL_CHARACTER_LIMIT = 900000


# Azure free monthly character safety limit

AZURE_CHARACTER_LIMIT = 1500000



# =========================
# STORAGE
# =========================

DATA = "/data" if os.path.exists("/data") else "."

os.makedirs(DATA, exist_ok=True)


CACHE_FILE = f"{DATA}/cache.json"

USAGE_FILE = f"{DATA}/usage.json"

DEEPL_USAGE_FILE = f"{DATA}/deepl_usage.json"

AZURE_USAGE_FILE = f"{DATA}/azure_usage.json"

TRANSLATOR_MODE_FILE = f"{DATA}/translator_mode.json"



def load(file, default):

    if os.path.exists(file):

        with open(file, "r") as f:

            return json.load(f)

    return default



def save(file, data):

    with open(file, "w") as f:

        json.dump(
            data,
            f,
            indent=2
        )



# =========================
# CACHE
# =========================

cache = load(
    CACHE_FILE,
    {}
)



# =========================
# USER/GLOBAL USAGE
# =========================

usage = load(
    USAGE_FILE,
    {
        "users": {},
        "global": 0,
        "date": time.strftime("%Y-%m-%d")
    }
)



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
# DEEPL USAGE TRACKING
# =========================

current_month = time.strftime("%Y-%m")


deepl_usage = load(
    DEEPL_USAGE_FILE,
    {
        "characters_used": 0,
        "month": current_month
    }
)



# Reset DeepL counter monthly

if deepl_usage.get("month") != current_month:

    deepl_usage = {

        "characters_used": 0,

        "month": current_month

    }

    save(
        DEEPL_USAGE_FILE,
        deepl_usage
    )





# =========================
# AZURE USAGE TRACKING
# =========================

azure_usage = load(
    AZURE_USAGE_FILE,
    {
        "characters_used": 0,
        "month": current_month
    }
)



# Reset Azure counter monthly

if azure_usage.get("month") != current_month:


    azure_usage = {

        "characters_used": 0,

        "month": current_month

    }


    save(
        AZURE_USAGE_FILE,
        azure_usage
    )





# =========================
# TRANSLATOR MODE
# =========================
#
# auto  = DeepL → Azure → Google
# deepl = DeepL only
# azure = Azure only
# google = Google only


translator_mode = load(
    TRANSLATOR_MODE_FILE,
    {
        "mode": "auto"
    }
)



if translator_mode.get("mode") not in [

    "auto",

    "deepl",

    "azure",

    "google"

]:

    translator_mode = {

        "mode": "auto"

    }


    save(
        TRANSLATOR_MODE_FILE,
        translator_mode
    )





# =========================
# DEEPL CONNECTION
# =========================

deepl_client = None



if DEEPL_API_KEY:


    deepl_client = deepl.Translator(

        DEEPL_API_KEY

    )


else:


    print(
        "WARNING: No DeepL API key found."
    )





# =========================
# AZURE CONNECTION
# =========================

def azure_translate(text, target):


    if not AZURE_TRANSLATOR_KEY:

        return None



    endpoint = (

        "https://api.cognitive.microsofttranslator.com/translate"

    )



    params = {

        "api-version": "3.0",

        "to": target

    }



    headers = {


        "Ocp-Apim-Subscription-Key":

            AZURE_TRANSLATOR_KEY,


        "Ocp-Apim-Subscription-Region":

            AZURE_TRANSLATOR_REGION,


        "Content-Type":

            "application/json",


        "X-ClientTraceId":

            str(uuid.uuid4())

    }



    body = [

        {

            "text": text

        }

    ]



    response = requests.post(

        endpoint,

        params=params,

        headers=headers,

        json=body

    )



    if response.status_code != 200:


        print(
            response.text
        )

        return None



    data = response.json()



    return data[0]["translations"][0]["text"]

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

# Apply Spanish gaming slang fixes
text = apply_slang_fixes(text))



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





    # Cooldown

    if user_id in cooldowns:


        if now - cooldowns[user_id] < USER_COOLDOWN:


            await interaction.response.send_message(

                "Please wait before translating again.",

                ephemeral=True

            )

            return



    cooldowns[user_id] = now





    # Minute limit

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





    # Daily limits

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

            "The bot reached its global daily limit.",

            ephemeral=True

        )

        return





    await interaction.response.defer(

        ephemeral=True

    )





    # =========================
    # CACHE CHECK
    # =========================


    cache_key = f"{translator_mode['mode']}:{target}:{text}"


    result = None



    if cache_key in cache:


        if now - cache[cache_key]["time"] < CACHE_HOURS * 3600:


            result = cache[cache_key]["text"]





    # =========================
    # TRANSLATION ENGINE
    # =========================


    if result is None:



        mode = translator_mode["mode"]





        # ---------------------
        # DeepL
        # ---------------------

        if mode in ["auto", "deepl"]:


            if (

                deepl_client

                and deepl_usage["characters_used"] + len(text)

                <= DEEPL_CHARACTER_LIMIT

            ):


                try:


                    target_language = (

                        "EN-US"

                        if target == "en"

                        else "ES"

                    )



                    translated = deepl_client.translate_text(

                        text,

                        target_lang=target_language

                    )



                    result = translated.text



                    deepl_usage["characters_used"] += len(text)



                    save(

                        DEEPL_USAGE_FILE,

                        deepl_usage

                    )



                    print(

                        "Used DeepL"

                    )



                except Exception as e:


                    print(

                        f"DeepL error: {e}"

                    )

                    result = None





        # ---------------------
        # Azure
        # ---------------------

        if result is None and mode in ["auto", "azure"]:


            if (

                azure_usage["characters_used"] + len(text)

                <= AZURE_CHARACTER_LIMIT

            ):


                try:


                    result = azure_translate(

                        text,

                        target

                    )



                    if result:


                        azure_usage["characters_used"] += len(text)



                        save(

                            AZURE_USAGE_FILE,

                            azure_usage

                        )



                        print(

                            "Used Azure Translator"

                        )



                except Exception as e:


                    print(

                        f"Azure error: {e}"

                    )

                    result = None






        # ---------------------
        # Google
        # ---------------------

        if result is None and mode in ["auto", "google"]:


            try:


                result = GoogleTranslator(

                    source="auto",

                    target=target

                ).translate(text)



                print(

                    "Used Google Translate"

                )



            except Exception as e:


                print(

                    f"Google error: {e}"

                )

                result = "Translation failed."







        # Save cache

        cache[cache_key] = {


            "text": result,


            "time": now


        }



        save(

            CACHE_FILE,

            cache

        )





    # =========================
    # USAGE TRACKING
    # =========================


    usage["users"][user_id] = current_user + 1

    usage["global"] += 1



    save(

        USAGE_FILE,

        usage

    )





    # =========================
    # RESPONSE
    # =========================


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
# TRANSLATOR SWITCH COMMAND
# =========================

@bot.command()
@commands.has_permissions(administrator=True)
async def translator(ctx, mode=None):


    if mode not in [

        "auto",

        "deepl",

        "azure",

        "google"

    ]:


        await ctx.send(

            "Usage: `!translator auto`, `!translator deepl`, `!translator azure`, or `!translator google`"

        )

        return




    translator_mode["mode"] = mode



    save(

        TRANSLATOR_MODE_FILE,

        translator_mode

    )



    await ctx.send(

        f"✅ Translator switched to **{mode.upper()}**"

    )





# =========================
# DEEPL STATUS
# =========================

@bot.command()
@commands.has_permissions(administrator=True)
async def deeplstatus(ctx):

    used = deepl_usage["characters_used"]

    remaining = DEEPL_CHARACTER_LIMIT - used

    embed = discord.Embed(
        title="🔤 DeepL Usage"
    )

    embed.add_field(
        name="Used",
        value=f"{used:,} / {DEEPL_CHARACTER_LIMIT:,}",
        inline=False
    )

    embed.add_field(
        name="Remaining",
        value=f"{remaining:,} characters",
        inline=False
    )

    embed.add_field(
        name="Current Mode",
        value=translator_mode["mode"].upper(),
        inline=False
    )

    await ctx.send(
        embed=embed
    )





# =========================
# AZURE STATUS
# =========================

@bot.command()
@commands.has_permissions(administrator=True)
async def azurestatus(ctx):


    used = azure_usage["characters_used"]


    remaining = AZURE_CHARACTER_LIMIT - used



    embed = discord.Embed(

        title="☁️ Azure Translator Usage"

    )


    embed.add_field(

        name="Used",

        value=f"{used:,} / {AZURE_CHARACTER_LIMIT:,}",

        inline=False

    )


    embed.add_field(

        name="Remaining",

        value=f"{remaining:,} characters",

        inline=False

    )


    embed.add_field(

        name="Month",

        value=azure_usage["month"],

        inline=False

    )


    await ctx.send(

        embed=embed

    )





# =========================
# FULL TRANSLATOR STATUS
# =========================

@bot.command()
@commands.has_permissions(administrator=True)
async def translatorstatus(ctx):


    embed = discord.Embed(

        title="🌎 Translator Status"

    )


    embed.add_field(

        name="Current Mode",

        value=translator_mode["mode"].upper(),

        inline=False

    )


    embed.add_field(

        name="DeepL",

        value=f"{deepl_usage['characters_used']:,}/{DEEPL_CHARACTER_LIMIT:,}",

        inline=False

    )


    embed.add_field(

        name="Azure",

        value=f"{azure_usage['characters_used']:,}/{AZURE_CHARACTER_LIMIT:,}",

        inline=False

    )


    embed.add_field(

        name="Google",

        value="Available fallback",

        inline=False

    )


    await ctx.send(

        embed=embed

    )





# =========================
# DISCORD CONTEXT MENUS
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
# BOT STARTUP
# =========================


@bot.event
async def on_ready():


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


    print(

        f"Translator mode: {translator_mode['mode']}"

    )


    print(

        "DeepL:",

        deepl_client is not None

    )


    print(

        "Azure:",

        AZURE_TRANSLATOR_KEY is not None

    )





bot.run(TOKEN)

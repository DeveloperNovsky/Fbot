import os
import json
import discord
from discord.ext import commands
import random
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")

# Discord intents
intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

# File paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
RAFFLE_FILE = os.path.join(BASE_DIR, "raffle_entries.json")

# ---------------- LOAD / SAVE ---------------- #

def save_entries():
    with open(RAFFLE_FILE, "w", encoding="utf-8") as f:
        json.dump(raffle_entries, f, indent=2)

if os.path.exists(RAFFLE_FILE):
    with open(RAFFLE_FILE, "r", encoding="utf-8") as f:
        raffle_entries = json.load(f)
else:
    raffle_entries = {}

def add_ticket(name):
    raffle_entries[name] = raffle_entries.get(name, 0) + 1

# ---------------- EVENTS ---------------- #

@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user}")

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    lines = []

    for raw_line in message.content.splitlines():
        raw_line = raw_line.strip()
        if not raw_line:
            continue

        # ✅ CLEAN FIX: take only text before "|"
        name = raw_line.split("|")[0].strip()

        if len(name) < 2:
            continue

        lines.append(name)

    if len(lines) >= 1:
        for name in lines:
            add_ticket(name)

        save_entries()

        summary = "\n".join(
            f"{name}: total {raffle_entries[name]}"
            for name in lines
        )

        await message.channel.send(
            f"🎟️ **Raffle tickets added:**\n```{summary}```"
        )
        return

    await bot.process_commands(message)

# ---------------- COMMANDS ---------------- #

@bot.command()
async def entries(ctx):
    if not raffle_entries:
        await ctx.send("No raffle entries yet.")
        return

    total = sum(raffle_entries.values())
    summary = "\n".join(
        f"{name}: {count} ticket(s)"
        for name, count in sorted(raffle_entries.items())
    )

    await ctx.send(
        f"**Raffle Entries ({total} total tickets):**\n```{summary}```"
    )

@bot.command()
async def drawwinner(ctx):
    if not raffle_entries:
        await ctx.send("No raffle entries to draw from!")
        return

    names = list(raffle_entries.keys())
    weights = list(raffle_entries.values())

    winner = random.choices(names, weights=weights, k=1)[0]

    await ctx.send(f"🎉 **Winner:** {winner}")

@bot.command()
async def reset(ctx):
    raffle_entries.clear()
    save_entries()
    await ctx.send("✅ All raffle entries cleared.")

bot.run(DISCORD_TOKEN)


import os
import json
import random
import discord
from discord.ext import commands

# ================== CONFIG ==================

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True

bot = commands.Bot(command_prefix="!", intents=intents)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
RAFFLE_FILE = os.path.join(BASE_DIR, "raffle_entries.json")

DEFAULT_TICKETS = 1

# ================== DATA ==================

def load_entries():
    if not os.path.exists(RAFFLE_FILE):
        return {}

    with open(RAFFLE_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

        if isinstance(data, list):
            migrated = {}
            for name in data:
                migrated[name] = migrated.get(name, 0) + 1
            save_entries(migrated)
            return migrated

        if isinstance(data, dict):
            return data

    return {}

def save_entries(entries=None):
    if entries is None:
        entries = raffle_entries
    with open(RAFFLE_FILE, "w", encoding="utf-8") as f:
        json.dump(entries, f, indent=2)

raffle_entries = load_entries()

# 🔑 tracks the last batch added
last_batch = []

def add_ticket(name):
    raffle_entries[name] = raffle_entries.get(name, 0) + 1

def remove_ticket(name):
    if name not in raffle_entries:
        return False

    raffle_entries[name] -= 1
    if raffle_entries[name] <= 0:
        del raffle_entries[name]
        return True

    return False

# ================== NAME CLEANING ==================

def extract_names_from_text(content: str):
    names = []

    for line in content.splitlines():
        line = line.strip()
        if not line:
            continue

        name = line.split("|")[0].strip()

        if len(name) >= 2:
            names.append(name)

    return list(dict.fromkeys(names))

# ================== EVENTS ==================

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")

@bot.event
async def on_message(message):
    global last_batch

    if message.author == bot.user:
        return

    if message.content:
        names = extract_names_from_text(message.content)

        if len(names) >= 2:
            last_batch = names.copy()  # ✅ save batch

            for name in names:
                add_ticket(name)

            save_entries()

            summary = "\n".join(
                f"{name}: total {raffle_entries[name]}"
                for name in names
            )

            await message.channel.send(
                f"🎟️ **Raffle tickets added**:\n```{summary}```"
            )
            return

    await bot.process_commands(message)

# ================== COMMANDS ==================

@bot.command()
async def removele(ctx):
    global last_batch

    if not last_batch:
        await ctx.send("❌ No previous batch to remove.")
        return

    removed_summary = []

    for name in last_batch:
        if name in raffle_entries:
            removed = remove_ticket(name)
            status = "removed (now 0)" if removed else f"now {raffle_entries[name]}"
            removed_summary.append(f"{name}: -1 ({status})")

    save_entries()
    last_batch = []  # prevent double remove

    await ctx.send(
        f"❌ **Removed 1 raffle ticket from last batch:**\n```"
        + "\n".join(removed_summary)
        + "```"
    )

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

    await ctx.send(
        f"🎉 The winner is **{winner}** with **{raffle_entries[winner]} ticket(s)**!"
    )

@bot.command()
async def reset(ctx):
    raffle_entries.clear()
    save_entries()
    await ctx.send("✅ All raffle entries have been cleared.")

# ================== START ==================

bot.run(DISCORD_TOKEN)

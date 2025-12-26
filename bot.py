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

# ================== CHANNEL RESTRICTION ==================
ALLOWED_CHANNELS = [1033249948084477982]

# ================== DATA ==================
def load_entries():
    if not os.path.exists(RAFFLE_FILE):
        return {}, {}
    with open(RAFFLE_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
        return data.get("raffle_entries", {}), data.get("display_names", {})

def save_entries(entries=None, display_names=None):
    if entries is None:
        entries = raffle_entries
    if display_names is None:
        display_names = user_display_names
    with open(RAFFLE_FILE, "w", encoding="utf-8") as f:
        json.dump(
            {"raffle_entries": entries, "display_names": display_names},
            f,
            indent=2
        )

raffle_entries, user_display_names = load_entries()
last_batch = []

# ================== HELPERS ==================
def add_ticket(username, display_name=None, amount=1):
    key = username.lower()
    raffle_entries[key] = raffle_entries.get(key, 0) + amount
    if display_name:
        user_display_names[key] = display_name

def remove_ticket(username, amount=1):
    key = username.lower()
    if key not in raffle_entries:
        return False
    raffle_entries[key] -= amount
    if raffle_entries[key] <= 0:
        del raffle_entries[key]
        user_display_names.pop(key, None)
        return True
    return False

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
    if message.author == bot.user:
        return
    if message.channel.id not in ALLOWED_CHANNELS:
        return
    await bot.process_commands(message)

# ================== COMMANDS ==================
@bot.command()
async def addt(ctx, *args):
    global last_batch
    if ctx.channel.id not in ALLOWED_CHANNELS:
        return

    last_batch = []
    added_summary = []
    username_parts = []

    for arg in args:
        try:
            tickets = int(arg)
            username = " ".join(username_parts)
            key = username.lower()
            add_ticket(key, display_name=username, amount=tickets)
            last_batch.extend([key] * tickets)
            added_summary.append(f"{username}: +{tickets} (Total: {raffle_entries[key]})")
            username_parts = []
        except ValueError:
            username_parts.append(arg)

    save_entries()
    await ctx.send("✅ **Tickets added:**\n```" + "\n".join(added_summary) + "```")

@bot.command()
async def removet(ctx, *args):
    if ctx.channel.id not in ALLOWED_CHANNELS:
        return

    removed_summary = []
    username_parts = []

    for arg in args:
        try:
            tickets = int(arg)
            username = " ".join(username_parts)
            key = username.lower()
            removed = min(tickets, raffle_entries.get(key, 0))
            remove_ticket(key, removed)
            removed_summary.append(
                f"{user_display_names.get(key, username)}: -{removed}"
            )
            username_parts = []
        except ValueError:
            username_parts.append(arg)

    save_entries()
    await ctx.send("✅ **Tickets removed:**\n```" + "\n".join(removed_summary) + "```")

@bot.command()
async def removele(ctx):
    global last_batch
    if not last_batch:
        await ctx.send("❌ No previous batch to remove.")
        return

    summary = []
    for name in set(last_batch):
        count = last_batch.count(name)
        remove_ticket(name, count)
        summary.append(f"{user_display_names.get(name, name)}: -{count}")

    save_entries()
    last_batch = []
    await ctx.send("❌ **Last batch removed:**\n```" + "\n".join(summary) + "```")

@bot.command()
async def entries(ctx):
    total = sum(raffle_entries.values())
    summary = "\n".join(
        f"{user_display_names.get(name, name)}: {count}"
        for name, count in raffle_entries.items()
    )
    await ctx.send(f"**Raffle Entries ({total}):**\n```{summary}```")

@bot.command(name="p")
async def pasteentries(ctx, *, content):
    """
    Add raffle tickets via pasted list.
    Each line = 1 ticket.
    Usage: !p <pasted names>
    """
    global last_batch

    if ctx.channel.id not in ALLOWED_CHANNELS:
        return

    names = extract_names_from_text(content)
    if not names:
        await ctx.send("❌ No valid names found.")
        return

    last_batch = []
    summary = []

    for name in names:
        key = name.lower()
        add_ticket(key, display_name=name)
        last_batch.append(key)
        summary.append(f"{name}: total {raffle_entries[key]}")

    save_entries()
    await ctx.send(
        "🎟️ **Raffle tickets added from paste:**\n```"
        + "\n".join(summary)
        + "```"
    )

@bot.command()
async def drawwinner(ctx):
    winner = random.choices(
        list(raffle_entries.keys()),
        weights=raffle_entries.values(),
        k=1
    )[0]
    await ctx.send(
        f"🎉 Winner: **{user_display_names.get(winner, winner)}** "
        f"({raffle_entries[winner]} tickets)"
    )

@bot.command()
async def reset(ctx):
    raffle_entries.clear()
    user_display_names.clear()
    save_entries()
    await ctx.send("✅ All raffle entries cleared.")

# ================== START ==================
bot.run(DISCORD_TOKEN)

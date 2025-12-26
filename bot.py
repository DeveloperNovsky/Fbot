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

ALLOWED_CHANNELS = [1033249948084477982]  # Replace with your channel ID

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
        json.dump({"raffle_entries": entries, "display_names": display_names}, f, indent=2)

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
        raffle_entries.pop(key)
        user_display_names.pop(key, None)
        return True
    return False

def extract_names_from_text(content: str):
    names = []
    for line in content.splitlines():
        line = line.strip()
        if not line:
            continue
        name = line.split("|")[0].split(":")[0].strip()
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
    """Add tickets to multiple users. Deletes command after processing."""
    await ctx.message.delete()
    global last_batch
    if ctx.channel.id not in ALLOWED_CHANNELS:
        return

    if len(args) < 2:
        await ctx.send("❌ Usage: !addt username tickets [username tickets...]")
        return

    last_batch = []
    added_summary = []
    name_parts = []

    for arg in args:
        if arg.isdigit():
            tickets = int(arg)
            username = " ".join(name_parts)
            key = username.lower()
            add_ticket(key, username, tickets)
            last_batch.extend([key] * tickets)
            added_summary.append(f"{username}: +{tickets} (Total {raffle_entries[key]})")
            name_parts = []
        else:
            name_parts.append(arg)

    save_entries()
    await ctx.send("✅ **Tickets added:**\n" + "\n".join(added_summary))

@bot.command()
async def removet(ctx, *args):
    """Remove tickets from multiple users. Deletes command after processing."""
    await ctx.message.delete()
    if ctx.channel.id not in ALLOWED_CHANNELS:
        return

    removed_summary = []
    name_parts = []

    for arg in args:
        if arg.isdigit():
            tickets = int(arg)
            username = " ".join(name_parts)
            key = username.lower()
            if key in raffle_entries:
                removed = min(tickets, raffle_entries[key])
                remove_ticket(key, removed)
                removed_summary.append(f"{user_display_names.get(key, username)}: -{removed}")
            else:
                removed_summary.append(f"{username}: ❌ No tickets")
            name_parts = []
        else:
            name_parts.append(arg)

    save_entries()
    await ctx.send("✅ **Tickets removed:**\n" + "\n".join(removed_summary))

@bot.command()
async def removele(ctx):
    """Remove last batch of tickets. Deletes command after processing."""
    await ctx.message.delete()
    global last_batch
    if not last_batch:
        await ctx.send("❌ No previous batch.")
        return

    summary = []
    for name in set(last_batch):
        count = last_batch.count(name)
        remove_ticket(name, count)
        summary.append(f"{user_display_names.get(name, name)}: -{count}")

    last_batch = []
    save_entries()
    await ctx.send("❌ **Last batch removed:**\n" + "\n".join(summary))

@bot.command()
async def entries(ctx):
    """Show total entries. Deletes command after processing."""
    await ctx.message.delete()
    total = sum(raffle_entries.values())
    await ctx.send(f"🎟️ Entries ({total} total)")

@bot.command()
@commands.has_permissions(administrator=True)
async def restore(ctx, *, content):
    """Restore raffle entries from pasted list. Deletes command after processing."""
    await ctx.message.delete()
    global last_batch

    lines = content.splitlines()
    raffle_entries.clear()
    user_display_names.clear()
    last_batch = []

    total_tickets = 0
    for line in lines:
        line = line.strip()
        if not line:
            continue
        name = line.split(":")[0].split("|")[0].strip()
        key = name.lower()
        if len(name) < 2:
            continue
        add_ticket(key, name, 1)
        last_batch.append(key)
        total_tickets += 1

    save_entries()
    await ctx.send(f"✅ Raffle entries restored ({total_tickets} total tickets)")

@bot.command()
async def drawwinner(ctx):
    """Draw a winner. Deletes command after processing."""
    await ctx.message.delete()
    if not raffle_entries:
        await ctx.send("No entries.")
        return
    winner = random.choices(list(raffle_entries.keys()), weights=raffle_entries.values(), k=1)[0]
    await ctx.send(f"🎉 Winner: **{user_display_names.get(winner, winner)}** ({raffle_entries[winner]} tickets)")

@bot.command()
async def reset(ctx):
    """Reset all entries. Deletes command after processing."""
    await ctx.message.delete()
    raffle_entries.clear()
    user_display_names.clear()
    save_entries()
    await ctx.send("✅ Raffle reset.")

# ================== START ==================
bot.run(DISCORD_TOKEN)


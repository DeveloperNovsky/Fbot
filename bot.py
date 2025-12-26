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
ALLOWED_CHANNELS = [1033249948084477982]  # replace with your channel ID

# ================== DATA ==================
def load_entries():
    if not os.path.exists(RAFFLE_FILE):
        return {}, {}
    with open(RAFFLE_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
        # Expecting format: {"raffle_entries": {...}, "display_names": {...}}
        raffle_entries = data.get("raffle_entries", {})
        display_names = data.get("display_names", {})
        return raffle_entries, display_names

def save_entries(entries=None, display_names=None):
    if entries is None:
        entries = raffle_entries
    if display_names is None:
        display_names = user_display_names
    with open(RAFFLE_FILE, "w", encoding="utf-8") as f:
        json.dump({"raffle_entries": entries, "display_names": display_names}, f, indent=2)

raffle_entries, user_display_names = load_entries()
last_batch = []  # Track last batch of usernames

# ================== HELPERS ==================
def add_ticket(username, display_name=None, amount=1):
    """Add tickets in a case-insensitive way and store display name"""
    key = username.lower()
    raffle_entries[key] = raffle_entries.get(key, 0) + amount
    if display_name:
        user_display_names[key] = display_name

def remove_ticket(username, amount=1):
    """Remove tickets in a case-insensitive way"""
    key = username.lower()
    if key not in raffle_entries:
        return False
    raffle_entries[key] -= amount
    if raffle_entries[key] <= 0:
        del raffle_entries[key]
        if key in user_display_names:
            del user_display_names[key]
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

def restore_entries_from_text(content: str):
    restored = {}
    display_names = {}
    for line in content.splitlines():
        line = line.strip()
        if not line or ":" not in line or "Raffle Entries" in line:
            continue
        if line.startswith("!restoreentries"):
            line = line[len("!restoreentries"):].strip()
        try:
            username, rest = line.split(":", 1)
            username_key = username.strip().lower()
            display_names[username_key] = username.strip()  # preserve capitalization
            count = int(next(word for word in rest.split() if word.isdigit()))
            if count > 0:
                restored[username_key] = count
        except Exception:
            continue
    return restored, display_names

# ================== EVENTS ==================
@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")

@bot.event
async def on_message(message):
    global last_batch
    if message.author == bot.user:
        return
    if message.channel.id not in ALLOWED_CHANNELS:
        return
    if message.content.startswith(bot.command_prefix):
        await bot.process_commands(message)
        return

    if message.content:
        names = extract_names_from_text(message.content)
        if len(names) >= 2:
            last_batch = [name.lower() for name in names]
            for name in names:
                add_ticket(name.lower(), display_name=name)
            save_entries()
            summary = "\n".join(f"{user_display_names.get(name, name)}: total {raffle_entries[name]}" for name in last_batch)
            await message.channel.send(f"🎟️ **Raffle tickets added**:\n```{summary}```")

# ================== COMMANDS ==================
@bot.command()
async def addt(ctx, *args):
    global last_batch
    if ctx.channel.id not in ALLOWED_CHANNELS:
        return
    if len(args) < 2:
        await ctx.send("❌ Usage: !addt username tickets")
        return

    try:
        tickets = int(args[-1])
    except ValueError:
        await ctx.send("❌ Last argument must be the number of tickets")
        return
    if tickets <= 0:
        await ctx.send("❌ Number of tickets must be greater than 0")
        return

    username = " ".join(args[:-1])
    username_key = username.lower()

    add_ticket(username_key, display_name=username, amount=tickets)
    save_entries()
    last_batch = [username_key] * tickets

    await ctx.send(f"✅ Added **{tickets} ticket(s)** to **{username}**. Total tickets: **{raffle_entries[username_key]}**")

@bot.command()
async def removet(ctx, *args):
    if ctx.channel.id not in ALLOWED_CHANNELS:
        return
    if len(args) < 2:
        await ctx.send("❌ Usage: !removet username tickets")
        return

    try:
        tickets = int(args[-1])
    except ValueError:
        await ctx.send("❌ Last argument must be the number of tickets")
        return
    if tickets <= 0:
        await ctx.send("❌ Number of tickets must be greater than 0")
        return

    username = " ".join(args[:-1])
    username_key = username.lower()

    if username_key not in raffle_entries:
        await ctx.send(f"❌ {username} has no tickets.")
        return

    removed_tickets = min(tickets, raffle_entries[username_key])
    remove_ticket(username_key, removed_tickets)
    save_entries()

    display_name = user_display_names.get(username_key, username)
    await ctx.send(f"✅ Removed **{removed_tickets} ticket(s)** from **{display_name}**. Remaining tickets: **{raffle_entries.get(username_key, 0)}**")

@bot.command()
async def removele(ctx):
    global last_batch
    if ctx.channel.id not in ALLOWED_CHANNELS:
        return
    if not last_batch:
        await ctx.send("❌ No previous batch to remove.")
        return
    removed_summary = []
    batch_counts = {}
    for name in last_batch:
        batch_counts[name] = batch_counts.get(name, 0) + 1
    for name, count in batch_counts.items():
        removed = remove_ticket(name, count)
        status = "removed (now 0)" if removed else f"now {raffle_entries.get(name, 0)}"
        display_name = user_display_names.get(name, name)
        removed_summary.append(f"{display_name}: -{count} ({status})")
    save_entries()
    last_batch = []
    await ctx.send(f"❌ **Removed raffle tickets from last batch:**\n```" + "\n".join(removed_summary) + "```")

@bot.command()
async def entries(ctx):
    if ctx.channel.id not in ALLOWED_CHANNELS:
        return
    if not raffle_entries:
        await ctx.send("No raffle entries yet.")
        return
    total = sum(raffle_entries.values())
    summary = "\n".join(f"{user_display_names.get(name, name)}: {count} ticket(s)" for name, count in sorted(raffle_entries.items()))
    await ctx.send(f"**Raffle Entries ({total} total tickets):**\n```{summary}```")

@bot.command()
@commands.has_permissions(administrator=True)
async def restoreentries(ctx):
    if ctx.channel.id not in ALLOWED_CHANNELS:
        return
    restored, display_names = restore_entries_from_text(ctx.message.content)
    if not restored:
        await ctx.send("❌ No valid raffle entries found to restore.")
        return
    raffle_entries.clear()
    raffle_entries.update(restored)
    user_display_names.clear()
    user_display_names.update(display_names)
    save_entries()
    total_tickets = sum(raffle_entries.values())
    summary = "\n".join(f"{user_display_names.get(name, name)}: {count} ticket(s)" for name, count in raffle_entries.items())
    await ctx.send(f"✅ **Raffle entries restored successfully** ({total_tickets} total tickets):\n```{summary}```")

@bot.command()
async def drawwinner(ctx):
    if ctx.channel.id not in ALLOWED_CHANNELS:
        return
    if not raffle_entries:
        await ctx.send("No raffle entries to draw from!")
        return
    names = list(raffle_entries.keys())
    weights = list(raffle_entries.values())
    winner = random.choices(names, weights=weights, k=1)[0]
    display_name = user_display_names.get(winner, winner)
    await ctx.send(f"🎉 The winner is **{display_name}** with **{raffle_entries[winner]} ticket(s)**!")

@bot.command()
async def reset(ctx):
    if ctx.channel.id not in ALLOWED_CHANNELS:
        return
    raffle_entries.clear()
    user_display_names.clear()
    save_entries()
    await ctx.send("✅ All raffle entries have been cleared.")

# ================== START ==================
bot.run(DISCORD_TOKEN)

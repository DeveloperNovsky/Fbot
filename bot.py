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

ALLOWED_CHANNELS = [1033249948084477982]  # your channel ID

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
    """
    Add tickets to multiple users.
    Example: !addt DMR 5 L CBO 2 Do It Now 3
    """
    global last_batch
    if ctx.channel.id not in ALLOWED_CHANNELS:
        return

    if len(args) < 2:
        await ctx.send("❌ Usage: !addt username tickets [username tickets ...]")
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
            added_summary.append(f"{username}: {raffle_entries[key]} ticket(s)")
            username_parts = []
        except ValueError:
            username_parts.append(arg)

    if username_parts:
        await ctx.send(f"❌ Missing ticket number for: {' '.join(username_parts)}")
        return

    save_entries()
    await ctx.send(f"✅ **Tickets added successfully:**\n```{chr(10).join(added_summary)}```")

@bot.command()
async def removet(ctx, *args):
    """
    Remove tickets from multiple users.
    Example: !removet DMR 3 L CBO 1 Do It Now 2
    """
    if ctx.channel.id not in ALLOWED_CHANNELS:
        return

    if len(args) < 2:
        await ctx.send("❌ Usage: !removet username tickets [username tickets ...]")
        return

    removed_summary = []
    username_parts = []

    for arg in args:
        try:
            tickets = int(arg)
            username = " ".join(username_parts)
            key = username.lower()
            if key not in raffle_entries:
                removed_summary.append(f"{username}: 0 ticket(s)")
            else:
                removed_tickets = min(tickets, raffle_entries[key])
                remove_ticket(key, removed_tickets)
                removed_summary.append(f"{user_display_names.get(key, username)}: {raffle_entries.get(key, 0)} ticket(s)")
            username_parts = []
        except ValueError:
            username_parts.append(arg)

    if username_parts:
        await ctx.send(f"❌ Missing ticket number for: {' '.join(username_parts)}")
        return

    save_entries()
    await ctx.send(f"✅ **Tickets removed successfully:**\n```{chr(10).join(removed_summary)}```")

@bot.command()
async def removele(ctx):
    global last_batch
    if not last_batch:
        await ctx.send("❌ No previous batch.")
        return

    summary = []
    for name in set(last_batch):
        count = last_batch.count(name)
        remove_ticket(name, count)
        summary.append(f"{user_display_names.get(name, name)}: {raffle_entries.get(name, 0)} ticket(s)")

    last_batch = []
    save_entries()
    await ctx.send(f"❌ **Last batch removed:**\n```{chr(10).join(summary)}```")

@bot.command()
async def entries(ctx):
    total = sum(raffle_entries.values())
    summary = "\n".join(
        f"{user_display_names.get(k, k)}: {v} ticket(s)"
        for k, v in raffle_entries.items()
    )
    await ctx.send(f"🎟️ **Entries ({total} total):**\n```{summary}```")

@bot.command(name="p")
async def pasteentries(ctx, *, content):
    """
    Paste entries (1 ticket per line).
    """
    global last_batch
    if ctx.channel.id not in ALLOWED_CHANNELS:
        return

    names = extract_names_from_text(content)
    if not names:
        await ctx.send("❌ No valid names found in the pasted content.")
        return

    last_batch = [name.lower() for name in names]
    for name in last_batch:
        add_ticket(name, display_name=name)

    save_entries()
    summary = "\n".join(f"{user_display_names.get(name, name)}: {raffle_entries[name]} ticket(s)" for name in set(last_batch))
    await ctx.send(f"🎟️ **Raffle tickets added from paste:**\n```{summary}```")

@bot.command()
@commands.has_permissions(administrator=True)
async def restoreentries(ctx, *, content):
    """
    Restore raffle entries from a pasted list.
    Each line: username: X ticket(s) or just username (1 ticket).
    """
    global last_batch
    if ctx.channel.id not in ALLOWED_CHANNELS:
        return

    # Remove command text if accidentally included
    if content.startswith("!restoreentries"):
        content = content[len("!restoreentries"):].strip()

    restored = {}
    display_names = {}
    last_batch = []

    for line in content.splitlines():
        line = line.strip()
        if not line:
            continue

        username = line.split(":")[0].split("|")[0].strip()
        key = username.lower()
        if len(username) < 2:
            continue

        try:
            count = int(next(word for word in line.split() if word.isdigit()))
        except StopIteration:
            count = 1

        restored[key] = count
        display_names[key] = username
        last_batch.extend([key] * count)

    if not restored:
        await ctx.send("❌ No valid raffle entries found to restore.")
        return

    raffle_entries.clear()
    raffle_entries.update(restored)
    user_display_names.clear()
    user_display_names.update(display_names)
    save_entries()

    summary = "\n".join(f"{user_display_names.get(name, name)}: {raffle_entries[name]} ticket(s)" for name in restored)
    total_tickets = sum(raffle_entries.values())
    await ctx.send(f"✅ **Raffle entries restored ({total_tickets} total tickets):**\n```{summary}```")

@bot.command()
async def drawwinner(ctx):
    if not raffle_entries:
        await ctx.send("No entries.")
        return
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
    await ctx.send("✅ Raffle reset.")

# ================== START ==================
bot.run(DISCORD_TOKEN)



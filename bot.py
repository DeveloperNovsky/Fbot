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

# ================== FILE PATHS ==================
RAFFLE_FILE = "/data/raffle_entries.json"    # Persisted on Railway volume
DONATIONS_FILE = "/data/donations.json"      # Persisted on Railway volume
ALLOWED_CHANNELS = [1033249948084477982]    # Replace with your channel ID

# Ensure /data directory exists
os.makedirs("/data", exist_ok=True)

# ================== RAFFLE DATA ==================
def load_entries():
    if not os.path.exists(RAFFLE_FILE):
        return {}, {}
    with open(RAFFLE_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
        return data.get("raffle_entries", {}), data.get("display_names", {})

def save_entries():
    with open(RAFFLE_FILE, "w", encoding="utf-8") as f:
        json.dump({"raffle_entries": raffle_entries, "display_names": user_display_names}, f, indent=2)

raffle_entries, user_display_names = load_entries()
last_batch = []

def add_ticket(username, display_name=None, amount=1):
    key = username.lower()
    raffle_entries[key] = raffle_entries.get(key, 0) + amount
    if display_name:
        user_display_names[key] = display_name

def remove_ticket(username, amount=1):
    key = username.lower()
    if key not in raffle_entries:
        return
    raffle_entries[key] -= amount
    if raffle_entries[key] <= 0:
        raffle_entries.pop(key)
        user_display_names.pop(key, None)

# ================== DONATIONS DATA ==================
def load_donations():
    if os.path.exists(DONATIONS_FILE):
        with open(DONATIONS_FILE, "r", encoding="utf-8") as f:
            try:
                data = json.load(f)
                data.setdefault("donations", {})
                data.setdefault("clan_bank", 0)
                return data
            except json.JSONDecodeError:
                pass
    data = {"donations": {}, "clan_bank": 0}
    with open(DONATIONS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    return data

def save_donations():
    with open(DONATIONS_FILE, "w", encoding="utf-8") as f:
        json.dump(donations_data, f, indent=2)

donations_data = load_donations()

def parse_amount(amount: str) -> int:
    amount = amount.lower().replace(",", "").strip()
    if amount.endswith("k"):
        return int(float(amount[:-1]) * 1_000)
    if amount.endswith("m"):
        return int(float(amount[:-1]) * 1_000_000)
    if amount.endswith("b"):
        return int(float(amount[:-1]) * 1_000_000_000)
    if amount.isdigit():
        return int(amount)
    raise ValueError

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

# ================== RAFFLE COMMANDS ==================
@bot.command()
async def addt(ctx, *args):
    global last_batch
    last_batch = []
    name_parts = []
    summary = []

    for arg in args:
        if arg.isdigit():
            tickets = int(arg)
            name = " ".join(name_parts)
            add_ticket(name, name, tickets)
            last_batch.extend([name.lower()] * tickets)
            summary.append(f"{name}: +{tickets}")
            name_parts = []
        else:
            name_parts.append(arg)

    save_entries()
    await ctx.send(f"✅ Tickets added:\n```" + "\n".join(summary) + "```")

@bot.command()
async def removet(ctx, *args):
    name_parts = []
    summary = []

    for arg in args:
        if arg.isdigit():
            tickets = int(arg)
            name = " ".join(name_parts)
            remove_ticket(name, tickets)
            summary.append(f"{name}: -{tickets}")
            name_parts = []
        else:
            name_parts.append(arg)

    save_entries()
    await ctx.send(f"❌ Tickets removed:\n```" + "\n".join(summary) + "```")

@bot.command()
async def entries(ctx):
    if not raffle_entries:
        await ctx.send("🎟️ Entries (0 total)")
        return

    lines = []
    total = 0
    for key, count in raffle_entries.items():
        name = user_display_names.get(key, key)
        lines.append(f"{name}: {count}")
        total += count

    await ctx.send(f"🎟️ Entries ({total} total):\n```" + "\n".join(lines) + "```")

@bot.command()
async def drawwinner(ctx):
    if not raffle_entries:
        await ctx.send("No entries.")
        return
    winner = random.choices(list(raffle_entries.keys()), weights=raffle_entries.values(), k=1)[0]
    await ctx.send(f"🎉 Winner: **{user_display_names.get(winner, winner)}** ({raffle_entries[winner]} tickets)")

@bot.command()
async def reset(ctx):
    raffle_entries.clear()
    user_display_names.clear()
    save_entries()
    await ctx.send("✅ Raffle reset.")

# ================== FIXED PASTE COMMAND ==================
@bot.command()
async def p(ctx):
    """Paste raid log – adds +1 ticket per name"""
    global last_batch
    last_batch = []

    content = ctx.message.content[len(ctx.prefix + ctx.command.name):].strip()
    lines = content.splitlines()
    added = []

    for line in lines:
        line = line.strip()
        if not line:
            continue
        if "|" in line:
            name = line.split("|")[0].strip()
        else:
            name = line
        add_ticket(name, name, 1)
        last_batch.append(name.lower())
        added.append(name)

    save_entries()

    if not added:
        await ctx.send("❌ No valid names found.")
        return

    await ctx.send(f"✅ Added **{len(added)}** raffle tickets:\n```" + "\n".join(added) + "```")

# ================== REMOVE LAST BATCH ==================
@bot.command()
async def removele(ctx):
    global last_batch
    if not last_batch:
        await ctx.send("❌ No previous paste batch to remove.")
        return
    removed_summary = []
    for key in last_batch:
        if key in raffle_entries:
            remove_ticket(key, 1)
            removed_summary.append(user_display_names.get(key, key))
    last_batch = []
    save_entries()
    await ctx.send(f"❌ Removed last paste batch:\n```" + "\n".join(removed_summary) + "```")

# ================== DONATION COMMANDS ==================
@bot.command()
async def adddn(ctx, arg1: str, arg2: str = None):
    amount = None
    username = None

    if ctx.message.mentions:
        user = ctx.message.mentions[0]
        username = user.display_name
        for part in ctx.message.content.split():
            if part.lower().endswith(("k","m","b")) or part.replace(",","").isdigit():
                amount = part
                break
    else:
        if arg1.lower().endswith(("k","m","b")):
            amount = arg1
            username = arg2
        else:
            username = arg1
            amount = arg2

    if not amount or not username:
        await ctx.send("❌ Usage: !adddn <user> <amount>")
        return

    try:
        value = parse_amount(amount)
    except ValueError:
        await ctx.send("❌ Invalid amount. Use 10m / 500k / 1b")
        return

    key = username.lower()
    donations_data["donations"][key] = donations_data["donations"].get(key, 0) + value
    donations_data["clan_bank"] += value
    save_donations()

    await ctx.send(
        f"💰 **Donation Added**\n"
        f"User: **{username}**\n"
        f"Amount: `{value:,}` gp\n"
        f"Donation Clan Bank: `{donations_data['donations'][key]:,}` gp\n"
        f"Clan Bank: `{donations_data['clan_bank']:,}` gp"
    )

@bot.command()
async def donations(ctx):
    await ctx.send(f"💰 Clan Bank Total: `{donations_data['clan_bank']:,}` gp")

# ================== START BOT ==================
bot.run(DISCORD_TOKEN)


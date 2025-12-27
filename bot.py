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
DONATION_FILE = os.path.join(BASE_DIR, "donations.json")

ALLOWED_CHANNELS = [1033249948084477982]  # your channel ID

# ================== RAFFLE DATA ==================
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

# ================== RAFFLE HELPERS ==================
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

# ================== DONATIONS ==================
def load_donations():
    if not os.path.exists(DONATION_FILE):
        return {"clan_bank": 0, "donations": {}}
    with open(DONATION_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_donations(data):
    with open(DONATION_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

def parse_amount(amount_str: str):
    s = amount_str.lower().replace(",", "")
    if s.endswith("b"):
        return int(float(s[:-1]) * 1_000_000_000)
    if s.endswith("m"):
        return int(float(s[:-1]) * 1_000_000)
    if s.endswith("k"):
        return int(float(s[:-1]) * 1_000)
    return int(s)

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
    if len(args) < 2:
        await ctx.send("❌ Usage: !addt username tickets")
        return

    name_parts = []
    for arg in args:
        if arg.isdigit():
            tickets = int(arg)
            username = " ".join(name_parts)
            add_ticket(username, username, tickets)
            name_parts = []
        else:
            name_parts.append(arg)

    save_entries()
    await ctx.send("✅ Tickets added.")

@bot.command()
async def removet(ctx, *args):
    name_parts = []
    for arg in args:
        if arg.isdigit():
            tickets = int(arg)
            username = " ".join(name_parts)
            remove_ticket(username, tickets)
            name_parts = []
        else:
            name_parts.append(arg)

    save_entries()
    await ctx.send("✅ Tickets removed.")

@bot.command()
async def entries(ctx):
    total = sum(raffle_entries.values())
    await ctx.send(f"🎟️ **Entries ({total} total)**")

@bot.command()
async def restore(ctx):
    lines = ctx.message.content.splitlines()[1:]

    raffle_entries.clear()
    user_display_names.clear()

    for line in lines:
        name = line.split(":")[0].strip()
        if len(name) < 2:
            continue
        add_ticket(name, name, 1)

    save_entries()
    await ctx.send(f"✅ **Raffle entries restored ({sum(raffle_entries.values())} total)**")

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

# ================== DONATION COMMANDS ==================
@bot.command()
async def adddn(ctx, amount: str, *, username: str):
    """
    !adddn 10m DMR
    !adddn 250k L CBO
    """

    donations = load_donations()

    try:
        value = parse_amount(amount)
    except ValueError:
        await ctx.send("❌ Invalid amount. Use 10m / 500k / 1b")
        return

    key = username.lower()

    donations["donations"][key] = donations["donations"].get(key, 0) + value
    donations["clan_bank"] += value

    save_donations(donations)

    await ctx.send(
        f"💰 **Donation Added**\n"
        f"User: **{username}**\n"
        f"Amount: `{value:,}` gp\n"
        f"User Total: `{donations['donations'][key]:,}` gp\n"
        f"Clan Bank: `{donations['clan_bank']:,}` gp"
    )

@bot.command()
async def clanbank(ctx):
    data = load_donations()
    await ctx.send(f"🏦 **Clan Bank:** `{data['clan_bank']:,}` gp")

# ================== START ==================
bot.run(DISCORD_TOKEN)

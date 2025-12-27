import os
import json
import random
import sqlite3
import discord
from discord.ext import commands
from pathlib import Path

# ================== CONFIG ==================
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True

bot = commands.Bot(command_prefix="!", intents=intents)

BASE_DIR = Path(__file__).parent

RAFFLE_FILE = BASE_DIR / "raffle_entries.json"
DB_FILE = BASE_DIR / "donations.db"

ALLOWED_CHANNELS = [1033249948084477982]

# ================== RAFFLE DATA ==================
def load_entries():
    if not RAFFLE_FILE.exists():
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
    return False

# ================== DONATIONS DATABASE ==================
# Initialize SQLite database
conn = sqlite3.connect(DB_FILE)
c = conn.cursor()
c.execute("""
CREATE TABLE IF NOT EXISTS donations (
    username TEXT PRIMARY KEY,
    total_donated INTEGER
)
""")
c.execute("""
CREATE TABLE IF NOT EXISTS clan_bank (
    id INTEGER PRIMARY KEY,
    total INTEGER
)
""")
# Ensure there's always one row for clan bank
c.execute("INSERT OR IGNORE INTO clan_bank (id, total) VALUES (1, 0)")
conn.commit()
conn.close()

def add_donation(username: str, amount: int):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    # Update user donation
    c.execute("INSERT INTO donations (username, total_donated) VALUES (?, ?) "
              "ON CONFLICT(username) DO UPDATE SET total_donated = total_donated + ?",
              (username, amount, amount))
    # Update clan bank
    c.execute("UPDATE clan_bank SET total = total + ? WHERE id = 1", (amount,))
    conn.commit()
    conn.close()

def get_user_donation(username: str) -> int:
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT total_donated FROM donations WHERE username = ?", (username,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else 0

def get_clan_bank() -> int:
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT total FROM clan_bank WHERE id = 1")
    row = c.fetchone()
    conn.close()
    return row[0] if row else 0

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
            key = name.lower()
            add_ticket(key, name, tickets)
            last_batch.extend([key] * tickets)
            summary.append(f"{name}: +{tickets}")
            name_parts = []
        else:
            name_parts.append(arg)

    save_entries()
    await ctx.send(f"✅ Tickets added.\n```" + "\n".join(summary) + "```")

@bot.command()
async def removet(ctx, *args):
    name_parts = []
    summary = []

    for arg in args:
        if arg.isdigit():
            tickets = int(arg)
            name = " ".join(name_parts)
            key = name.lower()
            removed = min(tickets, raffle_entries.get(key, 0))
            remove_ticket(key, removed)
            summary.append(f"{name}: -{removed}")
            name_parts = []
        else:
            name_parts.append(arg)

    save_entries()
    await ctx.send(f"❌ Tickets removed.\n```" + "\n".join(summary) + "```")

@bot.command()
async def entries(ctx):
    total = sum(raffle_entries.values())
    await ctx.send(f"🎟️ Entries ({total} total)")

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

# ================== DONATIONS COMMANDS ==================
@bot.command()
async def adddn(ctx, arg1: str, arg2: str = None):
    """
    Add a donation to a user and update clan bank.
    Usage: !adddn @User 500k or !adddn Username 500k
    """
    amount = None
    username = None

    if ctx.message.mentions:
        user = ctx.message.mentions[0]
        username = user.display_name
        for part in ctx.message.content.split():
            if part.lower().endswith(("k", "m", "b")) or part.replace(",", "").isdigit():
                amount = part
                break
    else:
        if arg1.lower().endswith(("k", "m", "b")) or arg1.replace(",", "").isdigit():
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

    # Add donation
    add_donation(username.lower(), value)
    user_total = get_user_donation(username.lower())
    clan_total = get_clan_bank()

    await ctx.send(
        f"💰 **Donation Added**\n"
        f"User: **{username}**\n"
        f"Amount: `{value:,}` gp\n"
        f"Donation Clan Bank: `{user_total:,}` gp\n"
        f"Clan Bank: `{clan_total:,}` gp"
    )

@bot.command()
async def donations(ctx):
    total = get_clan_bank()
    await ctx.send(f"💰 Clan Bank Total: `{total:,}` gp")

# ================== START BOT ==================
bot.run(DISCORD_TOKEN)


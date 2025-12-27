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

# ================== RAFFLE COMMANDS ==================
# ... all your existing raffle commands (addt, removet, removele, entries, restore, drawwinner, reset) stay here ...

# ================== DONATION SYSTEM ==================
DONATION_FILE = os.path.join(BASE_DIR, "donations.json")

def load_donations():
    if not os.path.exists(DONATION_FILE):
        return {"clan_bank": 0, "users": {}}
    with open(DONATION_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_donations():
    with open(DONATION_FILE, "w", encoding="utf-8") as f:
        json.dump(donations, f, indent=2)

donations = load_donations()

@bot.command()
async def adddn(ctx, member: discord.Member, amount: str):
    if ctx.channel.id not in ALLOWED_CHANNELS:
        return

    amt = amount.lower().replace(",", "")
    try:
        if amt.endswith("k"):
            value = int(float(amt[:-1]) * 1_000)
        elif amt.endswith("m"):
            value = int(float(amt[:-1]) * 1_000_000)
        elif amt.endswith("b"):
            value = int(float(amt[:-1]) * 1_000_000_000)
        else:
            await ctx.send("❌ Invalid amount. Use 10m / 500k / 1b")
            return
    except:
        await ctx.send("❌ Invalid amount. Use 10m / 500k / 1b")
        return

    key = str(member)
    donations["users"][key] = donations["users"].get(key, 0) + value
    donations["clan_bank"] += value
    save_donations()

    await ctx.send(
        f"💰 **Donation Clan Bank:** {key} donated {amount}.\n"
        f"Clan Bank Total: {donations['clan_bank']:,}"
    )

@bot.command()
async def donations_total(ctx):
    if ctx.channel.id not in ALLOWED_CHANNELS:
        return
    total = donations["clan_bank"]
    await ctx.send(f"💰 **Donation Clan Bank Total:** {total:,}")

@bot.command()
async def topdonors(ctx, top: int = 5):
    if ctx.channel.id not in ALLOWED_CHANNELS:
        return
    if not donations["users"]:
        await ctx.send("No donations yet.")
        return
    sorted_donors = sorted(donations["users"].items(), key=lambda x: x[1], reverse=True)
    message = [f"💰 **Top {top} Donors:**"]
    for i, (user, amount) in enumerate(sorted_donors[:top], start=1):
        message.append(f"{i}. {user}: {amount:,}")
    await ctx.send("\n".join(message))

# ================== START ==================
bot.run(DISCORD_TOKEN)

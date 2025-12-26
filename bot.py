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
        return data.get("raffle_entries", {}), data.get("display_names", {})

def save_entries():
    with open(RAFFLE_FILE, "w", encoding="utf-8") as f:
        json.dump(
            {
                "raffle_entries": raffle_entries,
                "display_names": user_display_names,
            },
            f,
            indent=2,
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
        raffle_entries.pop(key, None)
        user_display_names.pop(key, None)
        return True
    return False

def extract_names_from_text(content):
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
    """
    !addt DMR 5 L CBO 2 Do It Now 3
    """
    global last_batch
    if ctx.channel.id not in ALLOWED_CHANNELS:
        return

    if len(args) < 2:
        await ctx.send("❌ Usage: !addt username tickets [username tickets ...]")
        return

    last_batch = []
    summary = []
    name_parts = []

    for arg in args:
        if arg.isdigit():
            tickets = int(arg)
            if tickets <= 0 or not name_parts:
                await ctx.send("❌ Invalid ticket amount or missing username.")
                return

            username = " ".join(name_parts)
            key = username.lower()
            add_ticket(key, display_name=username, amount=tickets)
            last_batch.extend([key] * tickets)
            summary.append(f"{username}: +{tickets} (Total {raffle_entries[key]})")
            name_parts = []
        else:
            name_parts.append(arg)

    if name_parts:
        await ctx.send(f"❌ Missing ticket count for: {' '.join(name_parts)}")
        return

    save_entries()
    await ctx.send("✅ **Tickets added:**\n```" + "\n".join(summary) + "```")

@bot.command()
async def removet(ctx, *args):
    """
    !removet DMR 2 L CBO 1
    """
    if ctx.channel.id not in ALLOWED_CHANNELS:
        return

    summary = []
    name_parts = []

    for arg in args:
        if arg.isdigit():
            tickets = int(arg)
            if tickets <= 0 or not name_parts:
                await ctx.send("❌ Invalid ticket amount or missing username.")
                return

            username = " ".join(name_parts)
            key = username.lower()
            removed = min(tickets, raffle_entries.get(key, 0))
            if removed > 0:
                remove_ticket(key, removed)
                summary.append(
                    f"{user_display_names.get(key, username)}: -{removed}"
                )
            else:
                summary.append(f"{username}: ❌ No tickets")
            name_parts = []
        else:
            name_parts.append(arg)

    save_entries()
    await ctx.send("✅ **Tickets removed:**\n```" + "\n".join(summary) + "```")

@bot.command()
async def removele(ctx):
    global last_batch
    if not last_batch:
        await ctx.send("❌ No previous batch to remove.")
        return

    summary = []
    counts = {}
    for name in last_batch:
        counts[name] = counts.get(name, 0) + 1

    for name, count in counts.items():
        remove_ticket(name, count)
        summary.append(f"{user_display_names.get(name, name)}: -{count}")

    last_batch.clear()
    save_entries()
    await ctx.send("❌ **Last batch removed:**\n```" + "\n".join(summary) + "```")

@bot.command()
async def entries(ctx):
    if not raffle_entries:
        await ctx.send("No raffle entries yet.")
        return

    total = sum(raffle_entries.values())
    summary = "\n".join(
        f"{user_display_names.get(k, k)}: {v} ticket(s)"
        for k, v in sorted(raffle_entries.items())
    )
    await ctx.send(f"🎟️ **Raffle Entries ({total} total):**\n```{summary}```")

@bot.command()
@commands.has_permissions(administrator=True)
async def restoreentries(ctx):
    """
    Paste list directly after command.
    Each line = 1 ticket.
    """
    global last_batch

    lines = ctx.message.content.splitlines()[1:]
    content = "\n".join(lines).strip()
    names = extract_names_from_text(content)

    if not names:
        await ctx.send("❌ No valid raffle entries found to restore.")
        return

    raffle_entries.clear()
    user_display_names.clear()
    last_batch = []

    for name in names:
        add_ticket(name.lower(), display_name=name)
        last_batch.append(name.lower())

    save_entries()
    await ctx.send(
        f"✅ **Raffle entries restored ({len(names)} tickets):**\n```"
        + "\n".join(f"{name}: 1 ticket" for name in names)
        + "```"
    )

@bot.command()
async def drawwinner(ctx):
    if not raffle_entries:
        await ctx.send("No raffle entries.")
        return

    winner = random.choices(
        list(raffle_entries.keys()),
        weights=raffle_entries.values(),
        k=1,
    )[0]

    await ctx.send(
        f"🎉 **Winner:** {user_display_names.get(winner, winner)} "
        f"({raffle_entries[winner]} ticket(s))"
    )

@bot.command()
async def reset(ctx):
    raffle_entries.clear()
    user_display_names.clear()
    save_entries()
    await ctx.send("✅ Raffle reset complete.")

# ================== START ==================
bot.run(DISCORD_TOKEN)

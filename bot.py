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
        return {}
    with open(RAFFLE_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_entries(entries=None):
    if entries is None:
        entries = raffle_entries
    with open(RAFFLE_FILE, "w", encoding="utf-8") as f:
        json.dump(entries, f, indent=2)

raffle_entries = load_entries()
last_batch = []  # Track last batch of usernames

# ================== HELPERS ==================
def add_ticket(username, amount=1):
    raffle_entries[username] = raffle_entries.get(username, 0) + amount

def remove_ticket(username, amount=1):
    if username not in raffle_entries:
        return False
    raffle_entries[username] -= amount
    if raffle_entries[username] <= 0:
        del raffle_entries[username]
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

# ================== IMPROVED RESTORE PARSER ==================
def restore_entries_from_text(content: str):
    restored = {}
    for line in content.splitlines():
        line = line.strip()
        if not line or ":" not in line or "Raffle Entries" in line:
            continue
        # Skip "!restoreentries" if it appears at the start of the line
        if line.startswith("!restoreentries"):
            line = line[len("!restoreentries"):].strip()
        try:
            username, rest = line.split(":", 1)
            username = username.strip()
            # Extract first integer in the rest of the line as ticket count
            count = int(next(word for word in rest.split() if word.isdigit()))
            if count > 0:
                restored[username] = count
        except Exception:
            continue
    return restored

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

    # Ignore command messages
    if message.content.startswith(bot.command_prefix):
        await bot.process_commands(message)
        return

    # Process normal text messages for batch ticket addition
    if message.content:
        names = extract_names_from_text(message.content)
        if len(names) >= 2:
            last_batch = names.copy()
            for name in names:
                add_ticket(name)
            save_entries()
            summary = "\n".join(f"{name}: total {raffle_entries[name]}" for name in names)
            await message.channel.send(f"🎟️ **Raffle tickets added**:\n```{summary}```")

# ================== COMMANDS ==================
@bot.command()
async def addt(ctx, username: str, tickets: int):
    """Add X tickets to a username (typed manually)."""
    global last_batch
    if ctx.channel.id not in ALLOWED_CHANNELS:
        return
    if tickets <= 0:
        await ctx.send("❌ Number of tickets must be greater than 0.")
        return

    add_ticket(username, tickets)
    save_entries()
    last_batch = [username] * tickets
    await ctx.send(f"✅ Added **{tickets} ticket(s)** to **{username}**. Total tickets: **{raffle_entries[username]}**")

@bot.command()
async def removet(ctx, username: str, tickets: int):
    """Remove X tickets from a username (typed manually)."""
    if ctx.channel.id not in ALLOWED_CHANNELS:
        return
    if tickets <= 0:
        await ctx.send("❌ Number of tickets must be greater than 0.")
        return
    if username not in raffle_entries:
        await ctx.send(f"❌ {username} has no tickets.")
        return

    removed_tickets = min(tickets, raffle_entries[username])
    remove_ticket(username, removed_tickets)
    save_entries()
    await ctx.send(f"✅ Removed **{removed_tickets} ticket(s)** from **{username}**. Remaining tickets: **{raffle_entries.get(username, 0)}**")

@bot.command()
async def removele(ctx):
    """Remove tickets from last batch."""
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
        removed_summary.append(f"{name}: -{count} ({status})")
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
    summary = "\n".join(f"{name}: {count} ticket(s)" for name, count in sorted(raffle_entries.items()))
    await ctx.send(f"**Raffle Entries ({total} total tickets):**\n```{summary}```")

@bot.command()
@commands.has_permissions(administrator=True)
async def restoreentries(ctx):
    """Restore raffle entries from a text block."""
    if ctx.channel.id not in ALLOWED_CHANNELS:
        return
    restored = restore_entries_from_text(ctx.message.content)
    if not restored:
        await ctx.send("❌ No valid raffle entries found to restore.")
        return

    raffle_entries.clear()
    raffle_entries.update(restored)
    save_entries()

    total_tickets = sum(raffle_entries.values())
    summary = "\n".join(f"{name}: {count} ticket(s)" for name, count in raffle_entries.items())
    await ctx.send(
        f"✅ **Raffle entries restored successfully** ({total_tickets} total tickets):\n```{summary}```"
    )

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
    await ctx.send(f"🎉 The winner is **{winner}** with **{raffle_entries[winner]} ticket(s)**!")

@bot.command()
async def reset(ctx):
    if ctx.channel.id not in ALLOWED_CHANNELS:
        return
    raffle_entries.clear()
    save_entries()
    await ctx.send("✅ All raffle entries have been cleared.")

# ================== START ==================
bot.run(DISCORD_TOKEN)


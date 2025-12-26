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
intents.members = True  # Needed to resolve member IDs

bot = commands.Bot(command_prefix="!", intents=intents)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
RAFFLE_FILE = os.path.join(BASE_DIR, "raffle_entries.json")

# ================== CHANNEL RESTRICTION ==================
ALLOWED_CHANNELS = [1033249948084477982]  # replace if needed

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
last_batch = []  # store user IDs

# ================== HELPERS ==================
def add_ticket(user_id, amount=1):
    raffle_entries[user_id] = raffle_entries.get(user_id, 0) + amount

def remove_ticket(user_id, amount=1):
    if user_id not in raffle_entries:
        return False
    raffle_entries[user_id] -= amount
    if raffle_entries[user_id] <= 0:
        del raffle_entries[user_id]
        return True
    return False

def extract_names_from_text(content: str):
    # For text-based entries (non-Discord users), just keep names as strings
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
    for line in content.splitlines():
        line = line.strip()
        if not line or ":" not in line or "Raffle Entries" in line:
            continue
        try:
            name_part, count_part = line.split(":", 1)
            name = name_part.strip()
            count = int(count_part.strip().split(" ")[0])
            if count > 0:
                restored[name] = count
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

    if message.content:
        names = extract_names_from_text(message.content)
        if len(names) >= 2:
            last_batch = names.copy()
            for name in names:
                add_ticket(name)
            save_entries()
            summary = "\n".join(f"{name}: total {raffle_entries[name]}" for name in names)
            await message.channel.send(f"🎟️ **Raffle tickets added**:\n```{summary}```")
            return

    await bot.process_commands(message)

# ================== COMMANDS ==================
@bot.command()
async def addt(ctx, member: discord.Member, tickets: int):
    """Add X tickets to a user and track as last batch."""
    global last_batch
    if ctx.channel.id not in ALLOWED_CHANNELS:
        return
    if tickets <= 0:
        await ctx.send("❌ Number of tickets must be greater than 0.")
        return
    user_id = str(member.id)
    add_ticket(user_id, tickets)
    save_entries()
    last_batch = [user_id] * tickets
    await ctx.send(f"✅ Added **{tickets} ticket(s)** to **{member}**. Total tickets: **{raffle_entries[user_id]}**")

@bot.command()
@commands.has_permissions(administrator=True)
async def removet(ctx, member: discord.Member, tickets: int):
    """Remove X tickets from a user (admin only)."""
    if ctx.channel.id not in ALLOWED_CHANNELS:
        return
    if tickets <= 0:
        await ctx.send("❌ Number of tickets must be greater than 0.")
        return
    user_id = str(member.id)
    if user_id not in raffle_entries:
        await ctx.send(f"❌ {member} has no tickets.")
        return
    removed = min(tickets, raffle_entries[user_id])
    remove_ticket(user_id, removed)
    save_entries()
    await ctx.send(f"✅ Removed **{removed} ticket(s)** from **{member}**. Remaining tickets: **{raffle_entries.get(user_id, 0)}**")

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
    for uid in last_batch:
        batch_counts[uid] = batch_counts.get(uid, 0) + 1
    for uid, count in batch_counts.items():
        removed = remove_ticket(uid, count)
        user = bot.get_user(int(uid))
        name = str(user) if user else uid
        status = "removed (now 0)" if removed else f"now {raffle_entries.get(uid, 0)}"
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
    summary = []
    for uid, count in sorted(raffle_entries.items()):
        user = bot.get_user(int(uid))
        name = str(user) if user else uid
        summary.append(f"{name}: {count} ticket(s)")
    await ctx.send(f"**Raffle Entries ({total} total tickets):**\n```" + "\n".join(summary) + "```")

@bot.command()
@commands.has_permissions(administrator=True)
async def restoreentries(ctx):
    if ctx.channel.id not in ALLOWED_CHANNELS:
        return
    restored = restore_entries_from_text(ctx.message.content)
    if not restored:
        await ctx.send("❌ No valid raffle entries found to restore.")
        return
    raffle_entries.clear()
    raffle_entries.update(restored)
    save_entries()
    total = sum(restored.values())
    summary = "\n".join(f"{uid}: {count} ticket(s)" for uid, count in restored.items())
    await ctx.send(f"✅ **Raffle entries restored successfully** ({total} total tickets):\n```{summary}```")

@bot.command()
async def drawwinner(ctx):
    if ctx.channel.id not in ALLOWED_CHANNELS:
        return
    if not raffle_entries:
        await ctx.send("No raffle entries to draw from!")
        return
    names = list(raffle_entries.keys())
    weights = list(raffle_entries.values())
    winner_id = random.choices(names, weights=weights, k=1)[0]
    winner_user = bot.get_user(int(winner_id))
    winner_name = str(winner_user) if winner_user else winner_id
    await ctx.send(f"🎉 The winner is **{winner_name}** with **{raffle_entries[winner_id]} ticket(s)**!")

@bot.command()
async def reset(ctx):
    if ctx.channel.id not in ALLOWED_CHANNELS:
        return
    raffle_entries.clear()
    save_entries()
    await ctx.send("✅ All raffle entries have been cleared.")

# ================== START ==================
bot.run(DISCORD_TOKEN)

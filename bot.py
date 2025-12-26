import os
import json
import random
import discord
from discord.ext import commands

# ---------------- CONFIG ---------------- #
DATA_FILE = "raffle_entries.json"
DEFAULT_TICKETS = 1

# ---------------- DISCORD SETUP ---------------- #
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# ---------------- DATA HANDLING ---------------- #
def load_entries():
    if not os.path.exists(DATA_FILE):
        return {}
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_entries(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

raffle_entries = load_entries()
last_batch = []

def add_ticket(name, amount=1):
    raffle_entries[name] = raffle_entries.get(name, 0) + amount

def remove_ticket(name, amount=1):
    if name in raffle_entries:
        raffle_entries[name] -= amount
        if raffle_entries[name] <= 0:
            del raffle_entries[name]

# ---------------- EVENTS ---------------- #
@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")

@bot.event
async def on_message(message):
    global last_batch

    if message.author == bot.user:
        return

    lines = [
        line.strip()
        for line in message.content.splitlines()
        if len(line.strip()) >= 2
    ]

    # Require at least 2 names to prevent accidents
    if len(lines) >= 2:
        last_batch = lines.copy()

        for name in lines:
            add_ticket(name, DEFAULT_TICKETS)

        save_entries(raffle_entries)

        summary = "\n".join(
            f"{name}: total {raffle_entries[name]} ticket(s)"
            for name in lines
        )

        await message.channel.send(
            f"🎟️ **Raffle tickets added**:\n```{summary}```"
        )
        return

    await bot.process_commands(message)

# ---------------- COMMANDS ---------------- #
@bot.command()
async def entries(ctx):
    if not raffle_entries:
        await ctx.send("No raffle entries yet.")
        return

    total = sum(raffle_entries.values())
    summary = "\n".join(
        f"{name}: {count} ticket(s)"
        for name, count in sorted(raffle_entries.items())
    )

    await ctx.send(
        f"**Raffle Entries ({total} total tickets):**\n```{summary}```"
    )

@bot.command()
async def drawwinner(ctx):
    if not raffle_entries:
        await ctx.send("No raffle entries to draw from!")
        return

    names = list(raffle_entries.keys())
    weights = list(raffle_entries.values())

    winner = random.choices(names, weights=weights, k=1)[0]
    await ctx.send(
        f"🎉 The winner is **{winner}** with **{raffle_entries[winner]} ticket(s)**!"
    )

@bot.command()
async def removele(ctx):
    global last_batch

    if not last_batch:
        await ctx.send("No previous batch to remove.")
        return

    removed = []

    for name in last_batch:
        if name in raffle_entries:
            remove_ticket(name, DEFAULT_TICKETS)
            removed.append(name)

    save_entries(raffle_entries)
    last_batch = []

    if removed:
        summary = "\n".join(f"{name}: -1 ticket" for name in removed)
        await ctx.send(
            f"❌ Removed raffle tickets from last batch:\n```{summary}```"
        )
    else:
        await ctx.send("Nothing to remove.")

@bot.command()
async def reset(ctx):
    raffle_entries.clear()
    save_entries(raffle_entries)
    await ctx.send("✅ All raffle entries have been cleared.")

# ---------------- RUN BOT (Railway) ---------------- #
bot.run(os.environ["DISCORD_TOKEN"])


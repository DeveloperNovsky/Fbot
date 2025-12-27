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
RAFFLE_FILE = "/data/raffle_entries.json"     # Persisted on Railway volume
DONATIONS_FILE = "/data/donations.json"       # Persisted on Railway volume

ALLOWED_CHANNELS = [1033249948084477982]

os.makedirs("/data", exist_ok=True)

DONATION_ROLES = [
    (1_000_000, "Bronze - 1M Donation"),
    (3_000_000, "Iron - 3M Donation"),
    (5_000_000, "Steel - 5M Donation"),
    (10_000_000, "Black - 10M Donation"),
    (20_000_000, "Mithril - 20M Donation"),
    (50_000_000, "Adamant - 50M Donation"),
    (100_000_000, "Rune - 100M Donation"),
    (200_000_000, "Gilded - 200M Donation"),
    (300_000_000, "Dragon - 300M Donation"),
    (500_000_000, "3rd Age - 500M Donation"),
    (750_000_000, "Spectral - 750M Donation"),
    (1_000_000_000, "Arcane - 1B Donation"),
    (1_500_000_000, "Elysian - 1.5B Donation"),
    (2_000_000_000, "Elder - 2B Donation"),
    (3_000_000_000, "Kodai - 3B Donation"),
    (4_000_000_000, "Twisted - 4B Donation"),
]

# ================== RAFFLE DATA ==================
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
                "display_names": user_display_names
            },
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
    name_parts = []
    summary = []

    for arg in args:
        if arg.isdigit():
            tickets = int(arg)
            name = " ".join(name_parts)
            add_ticket(name, name, tickets)
            summary.append(f"{name}: +{tickets}")
            name_parts = []
        else:
            name_parts.append(arg)

    save_entries()
    await ctx.send("✅ Tickets added:\n```" + "\n".join(summary) + "```")

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
    await ctx.send("❌ Tickets removed:\n```" + "\n".join(summary) + "```")

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

    await ctx.send(
        f"🎟️ Entries ({total} total):\n```" +
        "\n".join(lines) +
        "```"
    )

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

# ================== ✅ FIXED PASTE COMMAND ==================
@bot.command()
async def p(ctx):
    """Paste raid log – adds tickets per name; supports optional :count"""
    global last_batch
    last_batch = []

    content = ctx.message.content
    content = content[len(ctx.prefix + ctx.command.name):].strip()
    lines = content.splitlines()

    added = []

    for line in lines:
        line = line.strip()
        if not line:
            continue

        if "|" in line:
            line = line.split("|")[0].strip()

        if ":" in line:
            parts = line.split(":")
            name = parts[0].strip()
            try:
                count = int(parts[1].strip())
            except ValueError:
                count = 1
        else:
            name = line
            count = 1

        if not name:
            continue

        add_ticket(name, name, count)
        last_batch.extend([name.lower()] * count)
        added.append(f"{name}: {count}")

    save_entries()

    if not added:
        await ctx.send("❌ No valid names found.")
        return

    await ctx.send(
        f"✅ Added **{sum(int(x.split(':')[1].strip()) for x in added)}** raffle tickets:\n```" +
        "\n".join(added) +
        "```"
    )

# ================== ✅ RESTORE COMMAND ==================
@bot.command()
async def restore(ctx):
    """Restore raffle entries from copy-paste with exact ticket counts"""
    content = ctx.message.content
    content = content[len(ctx.prefix + ctx.command.name):].strip()
    lines = content.splitlines()

    restored = []
    global last_batch
    last_batch = []

    for line in lines:
        line = line.strip()
        if not line:
            continue

        if ":" in line:
            parts = line.split(":")
            name = parts[0].strip()
            try:
                count = int(parts[1].strip())
            except ValueError:
                count = 1
        else:
            name = line
            count = 1

        add_ticket(name, name, count)
        last_batch.extend([name.lower()] * count)
        restored.append(f"{name}: {count}")

    save_entries()

    if not restored:
        await ctx.send("❌ No valid names to restore.")
        return

    await ctx.send(
        f"✅ Raffle entries restored ({sum(int(x.split(':')[1].strip()) for x in restored)} tickets):\n```" +
        "\n".join(restored) +
        "```"
    )

# ================== REMOVE LAST BATCH ==================
@bot.command()
async def removele(ctx):
    """Remove the last batch of pasted tickets"""
    global last_batch
    if not last_batch:
        await ctx.send("❌ No previous paste batch to remove.")
        return

    summary = []
    for key in last_batch:
        if key in raffle_entries:
            raffle_entries[key] -= 1
            if raffle_entries[key] <= 0:
                raffle_entries.pop(key)
                user_display_names.pop(key, None)
            summary.append(key)

    save_entries()
    last_batch = []
    await ctx.send(f"❌ Last batch removed:\n```" + "\n".join(summary) + "```")

# ================== DONATION COMMANDS ==================
@bot.command()
async def adddn(ctx, arg1: str, arg2: str = None):
    amount = None
    username = None
    member = None

    # Mention support
    if ctx.message.mentions:
        member = ctx.message.mentions[0]
        username = member.display_name
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

        member = discord.utils.find(
            lambda m: m.display_name.lower() == username.lower(),
            ctx.guild.members
        )

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

    total_donated = donations_data["donations"][key]

    awarded_role = None

    # ===== ROLE HANDLING =====
    if member:
        # Find highest role they qualify for
        for threshold, role_name in reversed(DONATION_ROLES):
            if total_donated >= threshold:
                role = discord.utils.get(ctx.guild.roles, name=role_name)
                if role and role not in member.roles:
                    # Remove lower donation roles
                    for _, lower_role_name in DONATION_ROLES:
                        lower_role = discord.utils.get(ctx.guild.roles, name=lower_role_name)
                        if lower_role and lower_role in member.roles:
                            await member.remove_roles(lower_role)

                    await member.add_roles(role)
                    awarded_role = role.name
                break

    message = (
        f"💰 **Donation Added**\n"
        f"User: **{username}**\n"
        f"Amount Credited: `{value:,}` gp\n"
        f"Total Donation to Clan Bank: `{total_donated:,}` gp\n"
        f"Clan Bank: `{donations_data['clan_bank']:,}` gp"
    )

    if awarded_role:
        message += f"\n🏅 **New Rank Awarded:** `{awarded_role}`"

    await ctx.send(message)

@bot.command()
@commands.has_permissions(administrator=True)
async def resetd(ctx, *, username: str):
    member = None

    # Mention support
    if ctx.message.mentions:
        member = ctx.message.mentions[0]
        username = member.display_name
    else:
        member = discord.utils.find(
            lambda m: m.display_name.lower() == username.lower(),
            ctx.guild.members
        )

    key = username.lower()

    if key not in donations_data["donations"]:
        await ctx.send(f"❌ **{username}** has no recorded donations.")
        return

    # Reset donation amount
    donations_data["donations"][key] = 0
    save_donations()

    # Remove donation roles
    if member:
        for _, role_name in DONATION_ROLES:
            role = discord.utils.get(ctx.guild.roles, name=role_name)
            if role and role in member.roles:
                await member.remove_roles(role)

    await ctx.send(
        f"♻️ **Donations Reset**\n"
        f"User: **{username}**\n"
        f"Total Donation to Clan Bank: `0` gp"
    )

@bot.command()
async def donations(ctx):
    await ctx.send(f"💰 Clan Bank Total: `{donations_data['clan_bank']:,}` gp")

# ================== START BOT ==================
bot.run(DISCORD_TOKEN)





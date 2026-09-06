import os
import json
import random
import re
from datetime import datetime

import discord
from discord.ext import commands

# ================== CONFIG ==================
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

# ================== FILE PATHS ==================
RAFFLE_FILE = "/data/raffle_entries.json"
DONATIONS_FILE = "/data/donations.json"

ALLOWED_CHANNELS = [
    1111111111111111111,  # Mydiscord
    1340371301654859907,  # Clan bank in Fyre Bird
    1454932497988190278,  # Fyrebird owner commands chat
    1454933219467329537,  # Fyre setup channel
]

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

    return (
        data.get("raffle_entries", {}),
        data.get("display_names", {})
    )


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
    """
    Loads the donation database.

    IMPORTANT:
    This function no longer automatically overwrites a missing/invalid
    donations file with an empty database.

    This prevents a future restart/deployment from silently wiping
    the in-memory data and creating a fresh database.
    """

    if not os.path.exists(DONATIONS_FILE):
        print("WARNING: donations.json does not exist.")
        print("Starting with an empty in-memory database.")
        print("No donations file has been automatically created.")

        return {
            "donations": {},
            "clan_bank": 0
        }

    try:
        with open(DONATIONS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)

        data.setdefault("donations", {})
        data.setdefault("clan_bank", 0)

        return data

    except json.JSONDecodeError as e:
        print("ERROR: donations.json contains invalid JSON.")
        print(e)

        return {
            "donations": {},
            "clan_bank": 0
        }


def save_donations():
    """
    Saves donations safely using a temporary file first.
    """

    temp_file = DONATIONS_FILE + ".tmp"

    with open(temp_file, "w", encoding="utf-8") as f:
        json.dump(
            donations_data,
            f,
            indent=2
        )

    os.replace(temp_file, DONATIONS_FILE)


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


# ============================================================
# DONATION RECOVERY SYSTEM
# ============================================================

# This variable stores the latest recovery scan in memory.
recovery_data = None


def extract_number(text):
    """
    Extracts numbers such as:

    584,366,000
    20,000,000
    5M
    """

    if not text:
        return None

    match = re.search(r"`?([\d,]+)`?\s*gp", text, re.IGNORECASE)

    if match:
        try:
            return int(match.group(1).replace(",", ""))
        except ValueError:
            pass

    return None


def extract_field_number(text, field_names):
    """
    Finds a number following one of the specified field names.

    Example:

    Clan Bank: `584,366,000` gp

    or

    New Clan Bank Total: `584,366,000` gp
    """

    for field in field_names:

        pattern = (
            re.escape(field)
            + r"\s*:\s*`?([\d,]+)`?\s*gp?"
        )

        match = re.search(
            pattern,
            text,
            re.IGNORECASE
        )

        if match:
            try:
                return int(
                    match.group(1).replace(",", "")
                )
            except ValueError:
                pass

    return None


def extract_user_name(text):
    """
    Extracts:

    User: **Trainman33**

    or:

    Recipient: **Some Name**
    """

    patterns = [
        r"User:\s*\*\*(.*?)\*\*",
        r"Recipient:\s*\*\*(.*?)\*\*"
    ]

    for pattern in patterns:

        match = re.search(
            pattern,
            text,
            re.IGNORECASE
        )

        if match:
            name = match.group(1).strip()

            if name:
                return name

    return None


def parse_recovery_message(message):
    """
    Examines a Discord message and determines whether it is one
    of the bot's historical donation records.

    Returns:
        {
            "type": "...",
            "user": "...",
            "total": ...,
            "bank": ...,
            "amount": ...
        }

    or None if it is not a donation record.
    """

    text_parts = []

    if message.content:
        text_parts.append(message.content)

    # Also inspect embeds in case older bot versions used embeds.
    for embed in message.embeds:

        if embed.title:
            text_parts.append(embed.title)

        if embed.description:
            text_parts.append(embed.description)

        for field in embed.fields:

            if field.name:
                text_parts.append(field.name)

            if field.value:
                text_parts.append(field.value)

    text = "\n".join(text_parts).strip()

    if not text:
        return None

    # --------------------------------------------------------
    # DONATION ADDED
    # --------------------------------------------------------

    if "Donation Added" in text:

        user = extract_user_name(text)

        total = extract_field_number(
            text,
            [
                "Total Donation to Clan Bank"
            ]
        )

        bank = extract_field_number(
            text,
            [
                "Clan Bank"
            ]
        )

        amount = extract_field_number(
            text,
            [
                "Amount Credited"
            ]
        )

        if user and total is not None:

            return {
                "type": "donation_added",
                "user": user,
                "total": total,
                "bank": bank,
                "amount": amount
            }

    # --------------------------------------------------------
    # DONATION CREDITED
    # --------------------------------------------------------

    if "Donation Credited" in text:

        user = extract_user_name(text)

        total = extract_field_number(
            text,
            [
                "Total Donation to Clan Bank"
            ]
        )

        bank = extract_field_number(
            text,
            [
                "Clan Bank"
            ]
        )

        amount = extract_field_number(
            text,
            [
                "Amount Credited"
            ]
        )

        if user and total is not None:

            return {
                "type": "donation_credited",
                "user": user,
                "total": total,
                "bank": bank,
                "amount": amount
            }

    # --------------------------------------------------------
    # DONATION CREDIT SET
    # --------------------------------------------------------

    if "Donation Credit Set" in text:

        user = extract_user_name(text)

        total = extract_field_number(
            text,
            [
                "New Total Donation"
            ]
        )

        bank = extract_field_number(
            text,
            [
                "Clan Bank"
            ]
        )

        if user and total is not None:

            return {
                "type": "donation_set",
                "user": user,
                "total": total,
                "bank": bank
            }

    # --------------------------------------------------------
    # DONATION RESET
    # --------------------------------------------------------

    if "Donation Reset" in text:

        user = extract_user_name(text)

        if user:

            bank = extract_field_number(
                text,
                [
                    "Clan Bank"
                ]
            )

            return {
                "type": "donation_reset",
                "user": user,
                "total": 0,
                "bank": bank
            }

    # --------------------------------------------------------
    # CLAN BANK UPDATED
    # --------------------------------------------------------

    if "Clan Bank Updated" in text:

        bank = extract_field_number(
            text,
            [
                "New Clan Bank Total"
            ]
        )

        amount = extract_field_number(
            text,
            [
                "Added"
            ]
        )

        if bank is not None:

            return {
                "type": "bank_add",
                "bank": bank,
                "amount": amount
            }

    # --------------------------------------------------------
    # PAYOUT PROCESSED
    # --------------------------------------------------------

    if "Payout Processed" in text:

        bank = extract_field_number(
            text,
            [
                "Remaining Clan Bank"
            ]
        )

        amount = extract_field_number(
            text,
            [
                "Amount Paid Out"
            ]
        )

        if bank is not None:

            return {
                "type": "payout",
                "bank": bank,
                "amount": amount
            }

    # --------------------------------------------------------
    # CLAN BANK TOTAL SET
    # --------------------------------------------------------

    if "Clan Bank Total Set" in text:

        bank = extract_field_number(
            text,
            [
                "New Clan Bank Total"
            ]
        )

        if bank is not None:

            return {
                "type": "bank_set",
                "bank": bank
            }

    return None


@bot.command()
@commands.has_permissions(administrator=True)
async def recoverdonations(ctx):
    """
    Scans the ENTIRE Discord history of the current channel.

    IMPORTANT:
    This command DOES NOT modify donations.json.
    It only creates a recovery preview.
    """

    global recovery_data

    await ctx.send(
        "🔎 **Starting donation recovery scan...**\n"
        "I'm scanning the entire message history of this channel.\n"
        "This may take a little while."
    )

    recovered_users = {}

    latest_bank = None

    donation_events = 0
    scanned_messages = 0

    try:

        async for message in ctx.channel.history(
            limit=None,
            oldest_first=True
        ):

            scanned_messages += 1

            # Only inspect bot-generated messages.
            #
            # This prevents normal commands such as:
            #
            # !adddn @user 10m
            #
            # from being interpreted as donation records.
            if not message.author.bot:
                continue

            record = parse_recovery_message(message)

            if not record:
                continue

            donation_events += 1

            # ------------------------------------------------
            # USER DONATION
            # ------------------------------------------------

            if record["type"] in (
                "donation_added",
                "donation_credited",
                "donation_set",
                "donation_reset"
            ):

                user = record["user"]

                recovered_users[user] = {
                    "total": record["total"],
                    "last_event": record["type"],
                    "message_id": message.id,
                    "timestamp": message.created_at.isoformat()
                }

            # ------------------------------------------------
            # CLAN BANK
            # ------------------------------------------------

            if record.get("bank") is not None:

                latest_bank = {
                    "amount": record["bank"],
                    "event": record["type"],
                    "message_id": message.id,
                    "timestamp": message.created_at.isoformat()
                }

    except discord.Forbidden:

        await ctx.send(
            "❌ **I can't read this channel's history.**\n\n"
            "Make sure the bot has:\n"
            "• View Channel\n"
            "• Read Message History\n\n"
            "Then run `!recoverdonations` again."
        )

        return

    except discord.HTTPException as e:

        await ctx.send(
            f"❌ Discord returned an error while reading history:\n"
            f"`{e}`"
        )

        return

    # --------------------------------------------------------
    # BUILD RECOVERY DATA
    # --------------------------------------------------------

    recovered_donations = {}

    for username, info in recovered_users.items():

        recovered_donations[username] = info["total"]

    # Current database
    current_users = donations_data.get(
        "donations",
        {}
    )

    current_bank = donations_data.get(
        "clan_bank",
        0
    )

    recovery_data = {
        "users": recovered_users,
        "donations": recovered_donations,
        "historical_bank": (
            latest_bank["amount"]
            if latest_bank
            else None
        ),
        "historical_bank_event": (
            latest_bank["event"]
            if latest_bank
            else None
        ),
        "current_users": dict(current_users),
        "current_bank": current_bank,
        "scanned_messages": scanned_messages,
        "donation_events": donation_events
    }

    # --------------------------------------------------------
    # DISPLAY RESULTS
    # --------------------------------------------------------

    if not recovered_users:

        await ctx.send(
            f"⚠️ **No historical donation records were found.**\n\n"
            f"Messages scanned: `{scanned_messages:,}`\n"
            f"Donation records found: `0`\n\n"
            "Make sure you're running this command in the "
            "channel containing the old donation bot messages."
        )

        return

    lines = []

    for username, info in sorted(
        recovered_users.items(),
        key=lambda x: x[1]["total"],
        reverse=True
    ):

        lines.append(
            f"{username}: {info['total']:,} gp"
        )

    # Discord has a 2000-character message limit.
    # Split the list into multiple messages.

    chunks = []
    current_chunk = ""

    for line in lines:

        if len(current_chunk) + len(line) + 1 > 1800:

            chunks.append(current_chunk)
            current_chunk = ""

        current_chunk += line + "\n"

    if current_chunk:
        chunks.append(current_chunk)

    await ctx.send(
        "✅ **DONATION RECOVERY SCAN COMPLETE**\n\n"
        f"Messages scanned: `{scanned_messages:,}`\n"
        f"Donation records found: `{donation_events:,}`\n"
        f"Unique users recovered: `{len(recovered_users):,}`\n"
        f"Historical Clan Bank: `"
        f"{latest_bank['amount']:,} gp`"
        if latest_bank
        else
        "Historical Clan Bank: `Not found`"
    )

    await ctx.send(
        "📋 **Recovered Users:**"
    )

    for index, chunk in enumerate(chunks, start=1):

        await ctx.send(
            f"```text\n{chunk}```"
        )

    # --------------------------------------------------------
    # CURRENT DATABASE COMPARISON
    # --------------------------------------------------------

    await ctx.send(
        "⚠️ **CURRENT DATABASE WAS NOT CHANGED.**\n\n"
        f"Current users in donations.json: "
        f"`{len(current_users):,}`\n"
        f"Current Clan Bank in donations.json: "
        f"`{current_bank:,} gp`\n\n"
        "If the recovery list looks correct, run:\n"
        "`!confirmrecovery`"
    )


@bot.command()
@commands.has_permissions(administrator=True)
async def confirmrecovery(ctx):
    """
    Writes the recovery data to donations.json.

    A backup of the current file is created first.
    """

    global recovery_data
    global donations_data

    if recovery_data is None:

        await ctx.send(
            "❌ There is no recovery scan waiting.\n\n"
            "Run `!recoverdonations` first."
        )

        return

    recovered_users = recovery_data["users"]
    historical_bank = recovery_data["historical_bank"]
    current_users = recovery_data["current_users"]
    current_bank = recovery_data["current_bank"]

    # --------------------------------------------------------
    # BACKUP CURRENT DATABASE
    # --------------------------------------------------------

    backup_path = None

    if os.path.exists(DONATIONS_FILE):

        timestamp = datetime.now().strftime(
            "%Y%m%d_%H%M%S"
        )

        backup_path = (
            f"/data/donations_before_recovery_"
            f"{timestamp}.json"
        )

        with open(
            DONATIONS_FILE,
            "r",
            encoding="utf-8"
        ) as source:

            with open(
                backup_path,
                "w",
                encoding="utf-8"
            ) as backup:

                backup.write(
                    source.read()
                )

    # --------------------------------------------------------
    # BUILD RECOVERED USER DATA
    # --------------------------------------------------------

    recovered_donations = {}

    # Historical Discord data uses names because the old
    # messages contain display names rather than IDs.
    #
    # We try to match those names to current Discord members.
    # If a member cannot be found, we store the name as a
    # fallback key so the data is NOT lost.
    
    guild = ctx.guild

    matched_count = 0
    unmatched_count = 0

    for username, info in recovered_users.items():

        total = info["total"]

        matched_member = None

        # Try exact display name first.
        for member in guild.members:

            if member.display_name.lower() == username.lower():

                matched_member = member
                break

        # Try username second.
        if matched_member is None:

            for member in guild.members:

                if member.name.lower() == username.lower():

                    matched_member = member
                    break

        if matched_member:

            recovered_donations[
                str(matched_member.id)
            ] = total

            matched_count += 1

        else:

            # Fallback key.
            #
            # This is intentionally NOT discarded.
            recovered_donations[
                f"recovered:{username.lower()}"
            ] = total

            unmatched_count += 1

    # --------------------------------------------------------
    # PRESERVE CURRENT USERS THAT WERE NOT FOUND IN HISTORY
    # --------------------------------------------------------

    for key, value in current_users.items():

        if key not in recovered_donations:

            recovered_donations[key] = value

    # --------------------------------------------------------
    # DETERMINE CLAN BANK
    # --------------------------------------------------------

    #
    # The historical bank is the last bank balance explicitly
    # recorded in Discord.
    #
    # We DO NOT automatically throw away the current database
    # balance.
    #
    # If the historical bank exists, use it as the recovered
    # historical baseline.
    #

    if historical_bank is not None:

        proposed_bank = historical_bank

    else:

        proposed_bank = current_bank

    # --------------------------------------------------------
    # SAVE
    # --------------------------------------------------------

    donations_data = {
        "donations": recovered_donations,
        "clan_bank": proposed_bank
    }

    save_donations()

    # Recovery is consumed.
    recovery_data = None

    # --------------------------------------------------------
    # REPORT
    # --------------------------------------------------------

    message = (
        "✅ **DONATION DATA RECOVERED**\n\n"
        f"Users recovered: `{len(recovered_users):,}`\n"
        f"Matched to Discord members: `{matched_count:,}`\n"
        f"Name-only records: `{unmatched_count:,}`\n"
        f"Recovered Clan Bank: `{proposed_bank:,} gp`\n\n"
    )

    if backup_path:

        message += (
            f"🛡️ **Backup created:**\n"
            f"`{backup_path}`\n\n"
        )

    message += (
        "The recovered data has now been written to "
        "`/data/donations.json`."
    )

    await ctx.send(message)


@bot.command()
@commands.has_permissions(administrator=True)
async def recoverycancel(ctx):
    """
    Clears the pending recovery scan without changing the database.
    """

    global recovery_data

    if recovery_data is None:

        await ctx.send(
            "ℹ️ There is no pending recovery scan."
        )

        return

    recovery_data = None

    await ctx.send(
        "🛑 **Recovery cancelled.**\n"
        "Your donations database was not changed."
    )


@bot.command()
@commands.has_permissions(administrator=True)
async def donationdata(ctx):
    """
    Displays the current donation database.
    """

    users = donations_data.get(
        "donations",
        {}
    )

    bank = donations_data.get(
        "clan_bank",
        0
    )

    lines = []

    for key, value in sorted(
        users.items(),
        key=lambda x: x[1],
        reverse=True
    ):

        lines.append(
            f"{key}: {value:,} gp"
        )

    if not lines:
        lines.append("No users found.")

    # Split for Discord's message limit.

    chunks = []
    current_chunk = ""

    for line in lines:

        if len(current_chunk) + len(line) + 1 > 1800:

            chunks.append(current_chunk)
            current_chunk = ""

        current_chunk += line + "\n"

    if current_chunk:
        chunks.append(current_chunk)

    await ctx.send(
        f"💰 **CURRENT DONATION DATABASE**\n"
        f"Clan Bank: `{bank:,} gp`\n"
        f"Users: `{len(users):,}`"
    )

    for chunk in chunks:

        await ctx.send(
            f"```text\n{chunk}```"
        )


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
@commands.has_permissions(administrator=True)
async def addt(ctx, *, input: str):

    parts = input.strip().split()

    if len(parts) < 2:
        await ctx.send(
            "❌ Usage: !addt <name> <tickets> "
            "[<name> <tickets> ...]"
        )
        return

    summary = []
    i = 0

    while i < len(parts) - 1:

        ticket_str = parts[i + 1]

        if not ticket_str.isdigit():

            await ctx.send(
                f"❌ Ticket count must be a number, got: "
                f"{ticket_str}"
            )

            return

        ticket_count = int(ticket_str)

        username_parts = [parts[i]]

        j = i + 1

        while (
            j < len(parts) - 1
            and not parts[j + 1].isdigit()
        ):

            j += 1
            username_parts.append(parts[j])

        username = " ".join(
            username_parts
        ).strip()

        add_ticket(
            username,
            username,
            ticket_count
        )

        summary.append(
            f"{username}: +{ticket_count}"
        )

        i = j + 2

    save_entries()

    if summary:

        await ctx.send(
            "✅ Tickets added:\n```"
            + "\n".join(summary)
            + "```"
        )

    else:

        await ctx.send(
            "❌ No valid entries found."
        )


@bot.command()
@commands.has_permissions(administrator=True)
async def removet(ctx, *, input: str):

    parts = input.strip().split()

    if len(parts) < 2:

        await ctx.send(
            "❌ Usage: !removet <name> <tickets> "
            "[<name> <tickets> ...]"
        )

        return

    summary = []
    i = 0

    while i < len(parts) - 1:

        ticket_str = parts[i + 1]

        if not ticket_str.isdigit():

            await ctx.send(
                f"❌ Ticket count must be a number, "
                f"got: {ticket_str}"
            )

            return

        ticket_count = int(ticket_str)

        username_parts = [parts[i]]

        j = i + 1

        while (
            j < len(parts) - 1
            and not parts[j + 1].isdigit()
        ):

            j += 1
            username_parts.append(parts[j])

        username = " ".join(
            username_parts
        ).strip()

        remove_ticket(
            username,
            ticket_count
        )

        summary.append(
            f"{username}: -{ticket_count}"
        )

        i = j + 2

    save_entries()

    if summary:

        await ctx.send(
            "❌ Tickets removed:\n```"
            + "\n".join(summary)
            + "```"
        )

    else:

        await ctx.send(
            "❌ No valid entries found."
        )


@bot.command()
@commands.has_permissions(administrator=True)
async def entries(ctx):

    if not raffle_entries:

        await ctx.send(
            "🎟️ Entries (0 total)"
        )

        return

    lines = []
    total = 0

    for key, count in raffle_entries.items():

        name = user_display_names.get(
            key,
            key
        )

        lines.append(
            f"{name}: {count}"
        )

        total += count

    await ctx.send(
        f"🎟️ Entries ({total} total):\n```"
        + "\n".join(lines)
        + "```"
    )


@bot.command()
@commands.has_permissions(administrator=True)
async def drawwinner(ctx):

    if not raffle_entries:

        await ctx.send(
            "No entries."
        )

        return

    winner = random.choices(
        list(raffle_entries.keys()),
        weights=raffle_entries.values(),
        k=1
    )[0]

    await ctx.send(
        f"🎉 Winner: **"
        f"{user_display_names.get(winner, winner)}** "
        f"({raffle_entries[winner]} tickets)"
    )


@bot.command()
@commands.has_permissions(administrator=True)
async def reset(ctx):

    raffle_entries.clear()
    user_display_names.clear()

    save_entries()

    await ctx.send(
        "✅ Raffle reset."
    )


# ================== PASTE COMMAND ==================

@bot.command()
@commands.has_permissions(administrator=True)
async def p(ctx):

    global last_batch

    last_batch = []

    content = ctx.message.content[
        len(ctx.prefix + ctx.command.name):
    ].strip()

    lines = content.splitlines()

    added = []

    for line in lines:

        line = line.strip()

        if not line:
            continue

        if "|" in line:
            line = line.split("|")[0].strip()

        if " - " in line:
            line = line.split(" - ")[0].strip()

        name = " ".join(
            line.split()
        )

        if not name:
            continue

        if ":" in name:

            parts = name.split(":")

            name = parts[0].strip()

            try:
                count = int(
                    parts[1].strip()
                )
            except ValueError:
                count = 1

        else:

            count = 1

        add_ticket(
            name,
            name,
            count
        )

        last_batch.extend(
            [name.lower()] * count
        )

        added.append(
            f"{name}: {count}"
        )

    save_entries()

    if not added:

        await ctx.send(
            "❌ No valid names found."
        )

        return

    await ctx.send(
        f"✅ Added **"
        f"{sum(int(x.split(':')[1]) for x in added)}"
        f"** raffle tickets:\n```"
        + "\n".join(added)
        + "```"
    )


# ================== RESTORE COMMAND ==================

@bot.command()
@commands.has_permissions(administrator=True)
async def restore(ctx):

    content = ctx.message.content[
        len(ctx.prefix + ctx.command.name):
    ].strip()

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
                count = int(
                    parts[1].strip()
                )
            except ValueError:
                count = 1

        else:

            name = line
            count = 1

        add_ticket(
            name,
            name,
            count
        )

        last_batch.extend(
            [name.lower()] * count
        )

        restored.append(
            f"{name}: {count}"
        )

    save_entries()

    if not restored:

        await ctx.send(
            "❌ No valid names to restore."
        )

        return

    await ctx.send(
        f"✅ Raffle entries restored "
        f"({sum(int(x.split(':')[1].strip()) for x in restored)} "
        f"tickets):\n```"
        + "\n".join(restored)
        + "```"
    )


# ================== REMOVE LAST BATCH ==================

@bot.command()
@commands.has_permissions(administrator=True)
async def removele(ctx):

    global last_batch

    if not last_batch:

        await ctx.send(
            "❌ No previous paste batch to remove."
        )

        return

    summary = []

    for key in last_batch:

        if key in raffle_entries:

            raffle_entries[key] -= 1

            if raffle_entries[key] <= 0:

                raffle_entries.pop(key)

                user_display_names.pop(
                    key,
                    None
                )

            summary.append(key)

    save_entries()

    last_batch = []

    await ctx.send(
        "❌ Last batch removed:\n```"
        + "\n".join(summary)
        + "```"
    )


# ================== DONATION COMMANDS ==================

@bot.command()
@commands.has_permissions(administrator=True)
async def adddn(
    ctx,
    member: discord.Member = None,
    amount: str = None
):

    if not member or not amount:

        await ctx.send(
            "❌ Usage: !adddn @user <amount>"
        )

        return

    try:

        value = parse_amount(amount)

    except ValueError:

        await ctx.send(
            "❌ Invalid amount. Use 10m / 500k / 1b"
        )

        return

    key = str(member.id)

    donations_data["donations"][key] = (
        donations_data["donations"].get(key, 0)
        + value
    )

    donations_data["clan_bank"] += value

    save_donations()

    total_donated = donations_data[
        "donations"
    ][key]

    awarded_role = None

    for threshold, role_name in reversed(
        DONATION_ROLES
    ):

        if total_donated >= threshold:

            role = discord.utils.get(
                ctx.guild.roles,
                name=role_name
            )

            if role and role not in member.roles:

                for _, lower_role_name in DONATION_ROLES:

                    lower_role = discord.utils.get(
                        ctx.guild.roles,
                        name=lower_role_name
                    )

                    if (
                        lower_role
                        and lower_role in member.roles
                    ):

                        try:

                            await member.remove_roles(
                                lower_role
                            )

                        except discord.Forbidden:

                            pass

                try:

                    await member.add_roles(
                        role
                    )

                    awarded_role = role.name

                except discord.Forbidden:

                    pass

            break

    message = (
        f"💰 **Donation Added**\n"
        f"User: **{member.display_name}**\n"
        f"Amount Credited: `{value:,}` gp\n"
        f"Total Donation to Clan Bank: "
        f"`{total_donated:,}` gp\n"
        f"Clan Bank: "
        f"`{donations_data['clan_bank']:,}` gp"
    )

    if awarded_role:

        message += (
            f"\n🏅 **New Rank Awarded:** "
            f"`{awarded_role}`"
        )

    await ctx.send(
        message
    )


@bot.command()
@commands.has_permissions(administrator=True)
async def resetd(ctx):

    if not ctx.message.mentions:

        await ctx.send(
            "❌ Usage: `!resetd @username`"
        )

        return

    member = ctx.message.mentions[0]

    key = str(member.id)

    previous_total = donations_data[
        "donations"
    ].get(key, 0)

    donations_data[
        "donations"
    ][key] = 0

    save_donations()

    removed_roles = []

    for _, role_name in DONATION_ROLES:

        role = discord.utils.get(
            ctx.guild.roles,
            name=role_name
        )

        if role and role in member.roles:

            try:

                await member.remove_roles(
                    role
                )

                removed_roles.append(
                    role.name
                )

            except discord.Forbidden:

                pass

    message = (
        f"♻️ **Donation Reset**\n"
        f"User: **{member.display_name}**\n"
        f"Previous Total: `{previous_total:,}` gp\n"
        f"New Total: `0` gp"
    )

    if removed_roles:

        message += (
            "\n🧹 **Roles Removed:**\n```"
            + "\n".join(removed_roles)
            + "```"
        )

    await ctx.send(
        message
    )


@bot.command()
@commands.has_permissions(administrator=True)
async def removetotal(ctx, *, input: str):

    parts = input.strip().split()

    if not parts:

        await ctx.send(
            "❌ Usage: !removetotal <username1> "
            "[<username2> ...]"
        )

        return

    summary = []

    i = 0

    while i < len(parts):

        username_parts = [parts[i]]

        j = i + 1

        while (
            j < len(parts)
            and not parts[j].isdigit()
        ):

            username_parts.append(
                parts[j]
            )

            j += 1

        username = " ".join(
            username_parts
        ).strip()

        if username.lower() in raffle_entries:

            raffle_entries.pop(
                username.lower()
            )

            user_display_names.pop(
                username.lower(),
                None
            )

            summary.append(
                f"{username}: removed completely"
            )

        else:

            summary.append(
                f"{username}: not found"
            )

        i = j

    save_entries()

    await ctx.send(
        "❌ Users removed totally:\n```"
        + "\n".join(summary)
        + "```"
    )


@bot.command()
@commands.has_permissions(administrator=True)
async def payout(
    ctx,
    member: discord.Member = None,
    amount: str = None,
    *,
    description: str = None
):

    if not member or not amount:

        await ctx.send(
            "❌ Usage: !payout @user <amount> "
            "[description]"
        )

        return

    try:

        value = parse_amount(amount)

    except ValueError:

        await ctx.send(
            "❌ Invalid amount. Use 10m / 500k / 1b"
        )

        return

    if donations_data["clan_bank"] < value:

        await ctx.send(
            "❌ Insufficient funds in the clan bank."
        )

        return

    donations_data[
        "clan_bank"
    ] -= value

    save_donations()

    message = (
        f"💸 **Payout Processed**\n"
        f"User: **{member.display_name}**\n"
        f"Amount Paid Out: `{value:,}` gp\n"
    )

    if description:

        message += (
            f"Description: *{description}*\n"
        )

    message += (
        f"Remaining Clan Bank: "
        f"`{donations_data['clan_bank']:,}` gp"
    )

    await ctx.send(
        message,
        allowed_mentions=discord.AllowedMentions.none()
    )


@bot.command()
@commands.has_permissions(administrator=True)
async def credit(
    ctx,
    member: discord.Member = None,
    amount: str = None,
    *,
    description: str = None
):

    if not member or not amount:

        await ctx.send(
            "❌ Usage: !credit @user <amount> <description>"
        )

        return

    try:

        value = parse_amount(amount)

    except ValueError:

        await ctx.send(
            "❌ Invalid amount. Use 10m / 500k / 1b"
        )

        return

    key = str(member.id)

    donations_data[
        "donations"
    ][key] = (
        donations_data["donations"].get(key, 0)
        + value
    )

    save_donations()

    total_donated = donations_data[
        "donations"
    ][key]

    awarded_role = None

    for threshold, role_name in reversed(
        DONATION_ROLES
    ):

        if total_donated >= threshold:

            role = discord.utils.get(
                ctx.guild.roles,
                name=role_name
            )

            if role and role not in member.roles:

                for _, lower_role_name in DONATION_ROLES:

                    lower_role = discord.utils.get(
                        ctx.guild.roles,
                        name=lower_role_name
                    )

                    if (
                        lower_role
                        and lower_role in member.roles
                    ):

                        try:

                            await member.remove_roles(
                                lower_role
                            )

                        except discord.Forbidden:

                            pass

                try:

                    await member.add_roles(
                        role
                    )

                    awarded_role = role.name

                except discord.Forbidden:

                    pass

            break

    message = (
        f"💰 **Donation Credited**\n"
        f"User: **{member.display_name}**\n"
        f"Amount Credited: `{value:,}` gp\n"
    )

    if description:

        message += (
            f"Description: *{description}*\n"
        )

    message += (
        f"Total Donation to Clan Bank: "
        f"`{total_donated:,}` gp\n"
        f"Clan Bank: "
        f"`{donations_data['clan_bank']:,}` gp"
    )

    if awarded_role:

        message += (
            f"\n🏅 **New Rank Awarded:** "
            f"`{awarded_role}`"
        )

    await ctx.send(
        message
    )


@bot.command()
@commands.has_permissions(administrator=True)
async def setcb(
    ctx,
    amount: str = None
):

    if not amount:

        await ctx.send(
            "❌ Usage: !setcb <amount>"
        )

        return

    try:

        value = parse_amount(amount)

    except ValueError:

        await ctx.send(
            "❌ Invalid amount. Use 10m / 500k / 1b"
        )

        return

    donations_data[
        "clan_bank"
    ] = value

    save_donations()

    await ctx.send(
        f"💰 **Clan Bank Total Set**\n"
        f"New Clan Bank Total: "
        f"`{donations_data['clan_bank']:,}` gp"
    )


@bot.command()
@commands.has_permissions(administrator=True)
async def donations(ctx):

    await ctx.send(
        f"💰 Clan Bank Total: "
        f"`{donations_data['clan_bank']:,}` gp"
    )


@bot.command()
@commands.has_permissions(administrator=True)
async def addds(
    ctx,
    amount: str = None,
    *,
    description: str = None
):

    if not amount:

        await ctx.send(
            "❌ Usage: !addds <amount> [description]"
        )

        return

    try:

        value = parse_amount(amount)

    except ValueError:

        await ctx.send(
            "❌ Invalid amount. Use 10m / 500k / 1b"
        )

        return

    donations_data[
        "clan_bank"
    ] += value

    save_donations()

    hypothetical_role = None

    for threshold, role_name in reversed(
        DONATION_ROLES
    ):

        if value >= threshold:

            hypothetical_role = role_name
            break

    message = (
        f"💰 **Clan Bank Updated**\n"
        f"Added: `{value:,}` gp"
    )

    if description:

        message += (
            f"\nDescription: {description}"
        )

    if hypothetical_role:

        message += (
            f"\n🏅 Would qualify for role: "
            f"`{hypothetical_role}`"
        )

    message += (
        f"\nNew Clan Bank Total: "
        f"`{donations_data['clan_bank']:,}` gp"
    )

    await ctx.send(
        message
    )


@bot.command()
@commands.has_permissions(administrator=True)
async def setcredit(
    ctx,
    member: discord.Member = None,
    amount: str = None
):

    if not member or not amount:

        await ctx.send(
            "❌ Usage: !setcredit @user <amount>"
        )

        return

    try:

        value = parse_amount(amount)

    except ValueError:

        await ctx.send(
            "❌ Invalid amount. Use 10m / 500k / 1b"
        )

        return

    key = str(member.id)

    donations_data[
        "donations"
    ][key] = value

    save_donations()

    awarded_role = None

    for threshold, role_name in reversed(
        DONATION_ROLES
    ):

        role = discord.utils.get(
            ctx.guild.roles,
            name=role_name
        )

        if not role:
            continue

        if value >= threshold:

            if role not in member.roles:

                for _, lower_role_name in DONATION_ROLES:

                    lower_role = discord.utils.get(
                        ctx.guild.roles,
                        name=lower_role_name
                    )

                    if (
                        lower_role
                        and lower_role in member.roles
                    ):

                        try:

                            await member.remove_roles(
                                lower_role
                            )

                        except discord.Forbidden:

                            pass

                try:

                    await member.add_roles(
                        role
                    )

                    awarded_role = role.name

                except discord.Forbidden:

                    pass

            break

    message = (
        f"📝 **Donation Credit Set**\n"
        f"User: **{member.display_name}**\n"
        f"New Total Donation: `{value:,}` gp\n"
        f"Clan Bank: "
        f"`{donations_data['clan_bank']:,}` gp"
    )

    if awarded_role:

        message += (
            f"\n🏅 **Rank Applied:** "
            f"`{awarded_role}`"
        )

    await ctx.send(
        message,
        allowed_mentions=discord.AllowedMentions.none()
    )


@bot.command()
@commands.has_permissions(administrator=True)
async def payoutnd(
    ctx,
    name: str = None,
    amount: str = None,
    *,
    description: str = None
):

    if not name or not amount:

        await ctx.send(
            "❌ Usage: !payoutnd <name> "
            "<amount> <description>"
        )

        return

    try:

        value = parse_amount(amount)

    except ValueError:

        await ctx.send(
            "❌ Invalid amount. Use 10m / 500k / 1b"
        )

        return

    if donations_data[
        "clan_bank"
    ] < value:

        await ctx.send(
            "❌ Insufficient funds in the clan bank."
        )

        return

    donations_data[
        "clan_bank"
    ] -= value

    save_donations()

    message = (
        f"💸 **Payout Processed "
        f"(Non-Discord User)**\n"
        f"Recipient: **{name}**\n"
        f"Amount Paid Out: `{value:,}` gp\n"
    )

    if description:

        message += (
            f"Description: *{description}*\n"
        )

    message += (
        f"Remaining Clan Bank: "
        f"`{donations_data['clan_bank']:,}` gp"
    )

    await ctx.send(
        message
    )


@bot.command()
@commands.has_permissions(administrator=True)
async def checkud(
    ctx,
    member: discord.Member = None
):

    if not member:

        await ctx.send(
            "❌ Usage: !checkud @user"
        )

        return

    key = str(member.id)

    total = donations_data[
        "donations"
    ].get(key, 0)

    await ctx.send(
        f"💰 **Total Donation to Clan Bank**\n"
        f"User: **{member.display_name}**\n"
        f"Total Donated: `{total:,}` gp"
    )


# ================== ERROR HANDLER ==================

@bot.event
async def on_command_error(ctx, error):

    if isinstance(
        error,
        commands.CommandNotFound
    ):
        return

    if isinstance(
        error,
        commands.MissingPermissions
    ):

        await ctx.send(
            "❌ You need Administrator permissions "
            "to use this command."
        )

        return

    print(
        f"Command error in {ctx.command}: "
        f"{repr(error)}"
    )


# ================== START BOT ==================

bot.run(DISCORD_TOKEN)


import os
import json
import random
import re
import copy
from datetime import datetime

import discord
from discord.ext import commands

# ================== CONFIG ==================

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True

bot = commands.Bot(
    command_prefix="!",
    intents=intents
)

# ================== FILE PATHS ==================

RAFFLE_FILE = "/data/raffle_entries.json"

# ================== DONATION STORAGE ==================

DONATIONS_FILE = "/data/donations.json"

# Automatic donation backups are stored here.
DONATION_BACKUP_DIR = "/data/donation_backups"

# Keep the most recent 50 automatic/manual backups.
MAX_DONATION_BACKUPS = 50

# Make sure Railway's persistent volume directories exist.
os.makedirs("/data", exist_ok=True)
os.makedirs(DONATION_BACKUP_DIR, exist_ok=True)

# ================== ALLOWED CHANNELS ==================

ALLOWED_CHANNELS = [
    1111111111111111111,  # Mydiscord
    1340371301654859907,  # Clan bank in Fyre Bird
    1454932497988190278,  # Fyrebird owner commands chat
    1454933219467329537,  # Fyre setup channel
]

# ================== DONATION ROLES ==================

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

# ============================================================
# RAFFLE DATA
# ============================================================

def load_entries():

    if not os.path.exists(RAFFLE_FILE):
        return {}, {}

    try:

        with open(
            RAFFLE_FILE,
            "r",
            encoding="utf-8"
        ) as f:

            data = json.load(f)

        return (
            data.get("raffle_entries", {}),
            data.get("display_names", {})
        )

    except Exception as e:

        print(
            f"WARNING: Could not load raffle data: {e}"
        )

        return {}, {}


def save_entries():

    temp_file = RAFFLE_FILE + ".tmp"

    try:

        with open(
            temp_file,
            "w",
            encoding="utf-8"
        ) as f:

            json.dump(
                {
                    "raffle_entries": raffle_entries,
                    "display_names": user_display_names
                },
                f,
                indent=2
            )

            f.flush()
            os.fsync(f.fileno())

        os.replace(
            temp_file,
            RAFFLE_FILE
        )

        return True

    except Exception as e:

        print(
            f"ERROR: Could not save raffle data: {e}"
        )

        try:

            if os.path.exists(temp_file):
                os.remove(temp_file)

        except OSError:
            pass

        return False


raffle_entries, user_display_names = load_entries()

last_batch = []


def add_ticket(
    username,
    display_name=None,
    amount=1
):

    key = username.lower()

    raffle_entries[key] = (
        raffle_entries.get(key, 0)
        + amount
    )

    if display_name:

        user_display_names[key] = display_name


def remove_ticket(
    username,
    amount=1
):

    key = username.lower()

    if key not in raffle_entries:
        return

    raffle_entries[key] -= amount

    if raffle_entries[key] <= 0:

        raffle_entries.pop(key)

        user_display_names.pop(
            key,
            None
        )


# ============================================================
# SAFE DONATION STORAGE
# ============================================================

# This becomes False automatically if the database is
# missing, corrupt, or otherwise invalid.
#
# When False, donation-changing commands are blocked so the
# bot cannot accidentally overwrite the database with blanks.
donation_database_healthy = True


def validate_donation_database(data):

    if not isinstance(data, dict):

        raise ValueError(
            "Donation database is not a JSON object."
        )

    if "donations" not in data:

        raise ValueError(
            "Donation database is missing 'donations'."
        )

    if "clan_bank" not in data:

        raise ValueError(
            "Donation database is missing 'clan_bank'."
        )

    if not isinstance(
        data["donations"],
        dict
    ):

        raise ValueError(
            "'donations' must be a dictionary."
        )

    if not isinstance(
        data["clan_bank"],
        int
    ):

        raise ValueError(
            "'clan_bank' must be an integer."
        )

    # Make sure every stored donation value is an integer.
    for key, value in data["donations"].items():

        if not isinstance(value, int):

            raise ValueError(
                f"Donation value for '{key}' "
                f"is not an integer."
            )

        if value < 0:

            raise ValueError(
                f"Donation value for '{key}' "
                f"cannot be negative."
            )

    if data["clan_bank"] < 0:

        raise ValueError(
            "Clan bank cannot be negative."
        )

    return True


def cleanup_old_donation_backups():

    try:

        backups = []

        for filename in os.listdir(
            DONATION_BACKUP_DIR
        ):

            if not filename.startswith(
                "donations_"
            ):
                continue

            if not filename.endswith(
                ".json"
            ):
                continue

            path = os.path.join(
                DONATION_BACKUP_DIR,
                filename
            )

            backups.append(path)

        backups.sort(
            key=os.path.getmtime,
            reverse=True
        )

        for old_backup in backups[
            MAX_DONATION_BACKUPS:
        ]:

            try:
                os.remove(old_backup)

            except OSError:
                pass

    except Exception as e:

        print(
            f"WARNING: Backup cleanup failed: {e}"
        )


def create_donation_backup(
    reason="automatic"
):

    if not os.path.exists(
        DONATIONS_FILE
    ):

        print(
            "BACKUP SKIPPED: "
            "donations.json does not exist."
        )

        return None

    try:

        timestamp = datetime.now().strftime(
            "%Y%m%d_%H%M%S_%f"
        )[:-3]

        backup_path = os.path.join(
            DONATION_BACKUP_DIR,
            f"donations_{timestamp}_{reason}.json"
        )

        with open(
            DONATIONS_FILE,
            "rb"
        ) as source:

            data = source.read()

        with open(
            backup_path,
            "wb"
        ) as backup:

            backup.write(data)
            backup.flush()
            os.fsync(
                backup.fileno()
            )

        print(
            f"Donation backup created: "
            f"{backup_path}"
        )

        cleanup_old_donation_backups()

        return backup_path

    except Exception as e:

        print(
            "WARNING: Could not create "
            f"donation backup: {e}"
        )

        return None


def load_donations():

    global donation_database_healthy

    # --------------------------------------------------------
    # MISSING FILE
    # --------------------------------------------------------

    if not os.path.exists(
        DONATIONS_FILE
    ):

        donation_database_healthy = False

        print(
            "\n"
            "====================================================\n"
            "🚨 CRITICAL DONATION DATABASE WARNING\n"
            "====================================================\n"
            "donations.json DOES NOT EXIST.\n"
            "\n"
            "The bot WILL NOT create a blank database.\n"
            "Donation-changing commands will be blocked.\n"
            "\n"
            f"Expected file:\n{DONATIONS_FILE}\n"
            "====================================================\n"
        )

        return {
            "donations": {},
            "clan_bank": 0
        }

    # --------------------------------------------------------
    # LOAD EXISTING FILE
    # --------------------------------------------------------

    try:

        with open(
            DONATIONS_FILE,
            "r",
            encoding="utf-8"
        ) as f:

            data = json.load(f)

        validate_donation_database(
            data
        )

        donation_database_healthy = True

        print(
            "\n"
            "====================================================\n"
            "💰 DONATION DATABASE LOADED\n"
            "====================================================\n"
            f"Users: "
            f"{len(data['donations']):,}\n"
            f"Clan Bank: "
            f"{data['clan_bank']:,} gp\n"
            f"File: {DONATIONS_FILE}\n"
            "Status: HEALTHY\n"
            "====================================================\n"
        )

        return data

    except (
        json.JSONDecodeError,
        ValueError,
        TypeError,
        OSError
    ) as e:

        donation_database_healthy = False

        print(
            "\n"
            "====================================================\n"
            "🚨 CRITICAL DONATION DATABASE ERROR\n"
            "====================================================\n"
            f"{e}\n"
            "\n"
            "The bot WILL NOT overwrite the file.\n"
            "Donation-changing commands are blocked.\n"
            "\n"
            "The existing donation data has been protected.\n"
            "====================================================\n"
        )

        return {
            "donations": {},
            "clan_bank": 0
        }


def save_donations():

    global donation_database_healthy

    # --------------------------------------------------------
    # VALIDATE BEFORE WRITING
    # --------------------------------------------------------

    try:

        validate_donation_database(
            donations_data
        )

    except Exception as e:

        print(
            "\n"
            "🚨 SAVE BLOCKED!\n"
            "Donation database failed validation:\n"
            f"{e}\n"
            "The existing donations.json was NOT changed."
        )

        donation_database_healthy = False

        return False

    # --------------------------------------------------------
    # BACKUP EXISTING DATABASE FIRST
    # --------------------------------------------------------

    if os.path.exists(
        DONATIONS_FILE
    ):

        create_donation_backup(
            reason="before_save"
        )

    # --------------------------------------------------------
    # ATOMIC SAVE
    # --------------------------------------------------------

    temp_file = (
        DONATIONS_FILE
        + ".tmp"
    )

    try:

        with open(
            temp_file,
            "w",
            encoding="utf-8"
        ) as f:

            json.dump(
                donations_data,
                f,
                indent=2
            )

            f.flush()

            os.fsync(
                f.fileno()
            )

        # The old file stays in place until the new file
        # is completely written.
        os.replace(
            temp_file,
            DONATIONS_FILE
        )

        # Verify the newly written file can actually be
        # read back as valid JSON.
        with open(
            DONATIONS_FILE,
            "r",
            encoding="utf-8"
        ) as f:

            verification_data = json.load(f)

        validate_donation_database(
            verification_data
        )

        donation_database_healthy = True

        print(
            "Donation database saved "
            "and verified successfully."
        )

        return True

    except Exception as e:

        donation_database_healthy = False

        print(
            "\n"
            "🚨 CRITICAL: DONATION SAVE FAILED\n"
            f"{e}\n"
            "\n"
            "The previous donations.json should "
            "remain intact."
        )

        try:

            if os.path.exists(
                temp_file
            ):

                os.remove(
                    temp_file
                )

        except OSError:
            pass

        return False


donations_data = load_donations()


def donation_database_available():

    return (
        donation_database_healthy
        and os.path.exists(
            DONATIONS_FILE
        )
    )


async def require_donation_database(ctx):

    if donation_database_available():
        return True

    await ctx.send(
        "🚨 **DONATION DATABASE PROTECTED**\n\n"
        "I detected a problem with "
        "`donations.json`.\n\n"
        "I have intentionally **blocked donation "
        "changes** so your data cannot be "
        "accidentally overwritten.\n\n"
        "Check the Railway Volume before making "
        "any donation changes."
    )

    return False


def rollback_donations(
    backup_state
):

    global donations_data

    donations_data.clear()

    donations_data.update(
        copy.deepcopy(
            backup_state
        )
    )


def backup_donation_state():

    return copy.deepcopy(
        donations_data
    )


# ============================================================
# DONATION RECOVERY SYSTEM
# ============================================================

recovery_data = None


def extract_number(text):

    if not text:
        return None

    match = re.search(
        r"`?([\d,]+)`?\s*gp",
        text,
        re.IGNORECASE
    )

    if match:

        try:

            return int(
                match.group(1)
                .replace(",", "")
            )

        except ValueError:
            pass

    return None


def extract_field_number(
    text,
    field_names
):

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
                    match.group(1)
                    .replace(",", "")
                )

            except ValueError:
                pass

    return None


def extract_user_name(text):

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


def parse_recovery_message(
    message
):

    text_parts = []

    if message.content:

        text_parts.append(
            message.content
        )

    for embed in message.embeds:

        if embed.title:

            text_parts.append(
                embed.title
            )

        if embed.description:

            text_parts.append(
                embed.description
            )

        for field in embed.fields:

            if field.name:

                text_parts.append(
                    field.name
                )

            if field.value:

                text_parts.append(
                    field.value
                )

    text = "\n".join(
        text_parts
    ).strip()

    if not text:
        return None

    # --------------------------------------------------------
    # DONATION ADDED
    # --------------------------------------------------------

    if "Donation Added" in text:

        user = extract_user_name(
            text
        )

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

        user = extract_user_name(
            text
        )

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

        user = extract_user_name(
            text
        )

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

        user = extract_user_name(
            text
        )

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

            if not message.author.bot:
                continue

            record = parse_recovery_message(
                message
            )

            if not record:
                continue

            donation_events += 1

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
            "❌ Discord returned an error while reading history:\n"
            f"`{e}`"
        )

        return

    recovered_donations = {}

    for username, info in recovered_users.items():

        recovered_donations[
            username
        ] = info["total"]

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
        "current_users": dict(
            current_users
        ),
        "current_bank": current_bank,
        "scanned_messages": scanned_messages,
        "donation_events": donation_events
    }

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

    chunks = []
    current_chunk = ""

    for line in lines:

        if (
            len(current_chunk)
            + len(line)
            + 1
            > 1800
        ):

            chunks.append(
                current_chunk
            )

            current_chunk = ""

        current_chunk += line + "\n"

    if current_chunk:
        chunks.append(
            current_chunk
        )

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

    for chunk in chunks:

        await ctx.send(
            f"```text\n{chunk}```"
        )

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

    global recovery_data
    global donations_data

    if recovery_data is None:

        await ctx.send(
            "❌ There is no recovery scan waiting.\n\n"
            "Run `!recoverdonations` first."
        )

        return

    recovered_users = recovery_data[
        "users"
    ]

    historical_bank = recovery_data[
        "historical_bank"
    ]

    current_users = recovery_data[
        "current_users"
    ]

    current_bank = recovery_data[
        "current_bank"
    ]

    # --------------------------------------------------------
    # BACKUP CURRENT DATABASE
    # --------------------------------------------------------

    backup_path = None

    if os.path.exists(
        DONATIONS_FILE
    ):

        backup_path = create_donation_backup(
            reason="before_recovery"
        )

    # --------------------------------------------------------
    # BUILD RECOVERED USER DATA
    # --------------------------------------------------------

    recovered_donations = {}

    guild = ctx.guild

    matched_count = 0
    unmatched_count = 0

    for username, info in recovered_users.items():

        total = info["total"]

        matched_member = None

        # Exact display name.
        for member in guild.members:

            if (
                member.display_name.lower()
                == username.lower()
            ):

                matched_member = member
                break

        # Username fallback.
        if matched_member is None:

            for member in guild.members:

                if (
                    member.name.lower()
                    == username.lower()
                ):

                    matched_member = member
                    break

        if matched_member:

            recovered_donations[
                str(matched_member.id)
            ] = total

            matched_count += 1

        else:

            recovered_donations[
                f"recovered:{username.lower()}"
            ] = total

            unmatched_count += 1

    # --------------------------------------------------------
    # PRESERVE CURRENT USERS NOT FOUND IN HISTORY
    # --------------------------------------------------------

    for key, value in current_users.items():

        if key not in recovered_donations:

            recovered_donations[
                key
            ] = value

    # --------------------------------------------------------
    # DETERMINE BANK
    # --------------------------------------------------------

    if historical_bank is not None:

        proposed_bank = historical_bank

    else:

        proposed_bank = current_bank

    # --------------------------------------------------------
    # SAVE RECOVERY
    # --------------------------------------------------------

    previous_state = backup_donation_state()

    donations_data.clear()

    donations_data.update(
        {
            "donations": recovered_donations,
            "clan_bank": proposed_bank
        }
    )

    if not save_donations():

        rollback_donations(
            previous_state
        )

        await ctx.send(
            "🚨 **RECOVERY SAVE FAILED**\n\n"
            "The recovered data was **NOT** committed.\n"
            "The previous in-memory database was restored.\n\n"
            "Check the Railway logs before trying again."
        )

        return

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
            "🛡️ **Backup created before recovery:**\n"
            f"`{os.path.basename(backup_path)}`\n\n"
        )

    message += (
        "The recovered data has now been written to "
        "`/data/donations.json`."
    )

    await ctx.send(
        message
    )


@bot.command()
@commands.has_permissions(administrator=True)
async def recoverycancel(ctx):

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

        lines.append(
            "No users found."
        )

    chunks = []
    current_chunk = ""

    for line in lines:

        if (
            len(current_chunk)
            + len(line)
            + 1
            > 1800
        ):

            chunks.append(
                current_chunk
            )

            current_chunk = ""

        current_chunk += line + "\n"

    if current_chunk:

        chunks.append(
            current_chunk
        )

    await ctx.send(
        f"💰 **CURRENT DONATION DATABASE**\n"
        f"Clan Bank: `{bank:,} gp`\n"
        f"Users: `{len(users):,}`"
    )

    for chunk in chunks:

        await ctx.send(
            f"```text\n{chunk}```"
        )


# ============================================================
# DONATION BACKUP COMMANDS
# ============================================================

@bot.command()
@commands.has_permissions(administrator=True)
async def backupdonations(ctx):

    if not os.path.exists(
        DONATIONS_FILE
    ):

        await ctx.send(
            "🚨 **No donations.json found.**\n"
            "No backup was created."
        )

        return

    backup_path = create_donation_backup(
        reason="manual"
    )

    if not backup_path:

        await ctx.send(
            "❌ Failed to create donation backup.\n"
            "Check the Railway logs."
        )

        return

    filename = os.path.basename(
        backup_path
    )

    await ctx.send(
        "🛡️ **DONATION BACKUP CREATED**\n\n"
        f"Backup: `{filename}`\n"
        f"Users: `{len(donations_data['donations']):,}`\n"
        f"Clan Bank: `{donations_data['clan_bank']:,} gp`\n\n"
        "Your current donation database has been backed up."
    )


@bot.command()
@commands.has_permissions(administrator=True)
async def listbackups(ctx):

    try:

        backups = []

        for filename in os.listdir(
            DONATION_BACKUP_DIR
        ):

            if not filename.startswith(
                "donations_"
            ):

                continue

            if not filename.endswith(
                ".json"
            ):

                continue

            path = os.path.join(
                DONATION_BACKUP_DIR,
                filename
            )

            backups.append(
                (
                    os.path.getmtime(path),
                    filename
                )
            )

        backups.sort(
            reverse=True
        )

    except Exception as e:

        await ctx.send(
            "❌ Could not read backup directory:\n"
            f"`{e}`"
        )

        return

    if not backups:

        await ctx.send(
            "📂 **No donation backups found.**"
        )

        return

    lines = []

    for index, (
        timestamp,
        filename
    ) in enumerate(
        backups[:MAX_DONATION_BACKUPS],
        start=1
    ):

        date = datetime.fromtimestamp(
            timestamp
        ).strftime(
            "%Y-%m-%d %H:%M:%S"
        )

        size = os.path.getsize(
            os.path.join(
                DONATION_BACKUP_DIR,
                filename
            )
        )

        lines.append(
            f"{index}. {date} — "
            f"{size:,} bytes — `{filename}`"
        )

    chunks = []
    current = ""

    for line in lines:

        if (
            len(current)
            + len(line)
            + 1
            > 1800
        ):

            chunks.append(
                current
            )

            current = ""

        current += line + "\n"

    if current:

        chunks.append(
            current
        )

    await ctx.send(
        "🛡️ **DONATION BACKUPS**\n"
        f"Total available: `{len(backups):,}`"
    )

    for chunk in chunks:

        await ctx.send(
            f"```text\n{chunk}```"
        )


@bot.command()
@commands.has_permissions(administrator=True)
async def restorebackup(
    ctx,
    backup_number: int = None
):

    if backup_number is None:

        await ctx.send(
            "❌ Usage: `!restorebackup <number>`\n\n"
            "Run `!listbackups` first."
        )

        return

    try:

        backups = []

        for filename in os.listdir(
            DONATION_BACKUP_DIR
        ):

            if not filename.startswith(
                "donations_"
            ):
                continue

            if not filename.endswith(
                ".json"
            ):
                continue

            path = os.path.join(
                DONATION_BACKUP_DIR,
                filename
            )

            backups.append(
                (
                    os.path.getmtime(path),
                    filename
                )
            )

        backups.sort(
            reverse=True
        )

    except Exception as e:

        await ctx.send(
            "❌ Could not read backups:\n"
            f"`{e}`"
        )

        return

    if (
        backup_number < 1
        or backup_number > len(backups)
    ):

        await ctx.send(
            "❌ Invalid backup number.\n\n"
            f"Available backups: `1-{len(backups)}`"
        )

        return

    selected_filename = backups[
        backup_number - 1
    ][1]

    selected_path = os.path.join(
        DONATION_BACKUP_DIR,
        selected_filename
    )

    # --------------------------------------------------------
    # READ AND VALIDATE SELECTED BACKUP
    # --------------------------------------------------------

    try:

        with open(
            selected_path,
            "r",
            encoding="utf-8"
        ) as f:

            restored_data = json.load(f)

        validate_donation_database(
            restored_data
        )

    except Exception as e:

        await ctx.send(
            "🚨 **BACKUP RESTORE BLOCKED**\n\n"
            "The selected backup failed validation.\n"
            f"Error: `{e}`\n\n"
            "Your current database was NOT changed."
        )

        return

    # --------------------------------------------------------
    # BACKUP CURRENT DATABASE BEFORE RESTORING
    # --------------------------------------------------------

    current_backup = None

    if os.path.exists(
        DONATIONS_FILE
    ):

        current_backup = create_donation_backup(
            reason="before_restore"
        )

    # --------------------------------------------------------
    # KEEP CURRENT STATE IN CASE RESTORE FAILS
    # --------------------------------------------------------

    previous_state = backup_donation_state()

    donations_data.clear()

    donations_data.update(
        restored_data
    )

    if not save_donations():

        rollback_donations(
            previous_state
        )

        await ctx.send(
            "🚨 **RESTORE FAILED**\n\n"
            "The selected backup was valid, but "
            "the restored database could not be saved.\n\n"
            "The previous in-memory database was restored.\n"
            "Your current donations.json should remain intact."
        )

        return

    await ctx.send(
        "✅ **DONATION BACKUP RESTORED**\n\n"
        f"Restored backup:\n"
        f"`{selected_filename}`\n\n"
        f"Users: "
        f"`{len(restored_data['donations']):,}`\n"
        f"Clan Bank: "
        f"`{restored_data['clan_bank']:,} gp`\n\n"
        "The backup file was NOT deleted."
        + (
            f"\n\n🛡️ Current database was backed up first:\n"
            f"`{os.path.basename(current_backup)}`"
            if current_backup
            else ""
        )
    )


@bot.command()
@commands.has_permissions(administrator=True)
async def donationstatus(ctx):

    file_exists = os.path.exists(
        DONATIONS_FILE
    )

    backup_count = 0

    try:

        backup_count = len([
            f
            for f in os.listdir(
                DONATION_BACKUP_DIR
            )
            if (
                f.startswith("donations_")
                and f.endswith(".json")
            )
        ])

    except OSError:
        pass

    users = donations_data.get(
        "donations",
        {}
    )

    bank = donations_data.get(
        "clan_bank",
        0
    )

    status = (
        "🟢 HEALTHY"
        if donation_database_available()
        else "🔴 PROTECTED / ERROR"
    )

    await ctx.send(
        "💾 **DONATION DATABASE STATUS**\n\n"
        f"Status: **{status}**\n"
        f"File exists: `{file_exists}`\n"
        f"Users: `{len(users):,}`\n"
        f"Clan Bank: `{bank:,} gp`\n"
        f"Local Backups: `{backup_count:,}`\n"
        f"Database: `{DONATIONS_FILE}`\n"
        f"Backup Folder: `{DONATION_BACKUP_DIR}`"
    )


# ============================================================
# EVENTS
# ============================================================

@bot.event
async def on_ready():

    print(
        f"Logged in as {bot.user}"
    )


@bot.event
async def on_message(message):

    if message.author == bot.user:
        return

    if (
        message.channel.id
        not in ALLOWED_CHANNELS
    ):

        return

    await bot.process_commands(
        message
    )


# ============================================================
# RAFFLE COMMANDS
# ============================================================

@bot.command()
@commands.has_permissions(administrator=True)
async def addt(
    ctx,
    *,
    input: str
):

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

        ticket_str = parts[
            i + 1
        ]

        if not ticket_str.isdigit():

            await ctx.send(
                f"❌ Ticket count must be a number, "
                f"got: {ticket_str}"
            )

            return

        ticket_count = int(
            ticket_str
        )

        username_parts = [
            parts[i]
        ]

        j = i + 1

        while (
            j < len(parts) - 1
            and not parts[j + 1].isdigit()
        ):

            j += 1

            username_parts.append(
                parts[j]
            )

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
async def removet(
    ctx,
    *,
    input: str
):

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

        ticket_str = parts[
            i + 1
        ]

        if not ticket_str.isdigit():

            await ctx.send(
                f"❌ Ticket count must be a number, "
                f"got: {ticket_str}"
            )

            return

        ticket_count = int(
            ticket_str
        )

        username_parts = [
            parts[i]
        ]

        j = i + 1

        while (
            j < len(parts) - 1
            and not parts[j + 1].isdigit()
        ):

            j += 1

            username_parts.append(
                parts[j]
            )

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
        list(
            raffle_entries.keys()
        ),
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


# ============================================================
# PASTE COMMAND
# ============================================================

@bot.command()
@commands.has_permissions(administrator=True)
async def p(ctx):

    global last_batch

    last_batch = []

    content = ctx.message.content[
        len(
            ctx.prefix
            + ctx.command.name
        ):
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

            line = line.split(
                " - "
            )[0].strip()

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


# ============================================================
# RESTORE RAFFLE COMMAND
# ============================================================

@bot.command()
@commands.has_permissions(administrator=True)
async def restore(ctx):

    content = ctx.message.content[
        len(
            ctx.prefix
            + ctx.command.name
        ):
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


# ============================================================
# REMOVE LAST RAFFLE BATCH
# ============================================================

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

                raffle_entries.pop(
                    key
                )

                user_display_names.pop(
                    key,
                    None
                )

            summary.append(
                key
            )

    save_entries()

    last_batch = []

    await ctx.send(
        "❌ Last batch removed:\n```"
        + "\n".join(summary)
        + "```"
    )


# ============================================================
# DONATION COMMANDS
# ============================================================

@bot.command()
@commands.has_permissions(administrator=True)
async def adddn(
    ctx,
    member: discord.Member = None,
    amount: str = None
):

    if not await require_donation_database(ctx):
        return

    if not member or not amount:

        await ctx.send(
            "❌ Usage: !adddn @user <amount>"
        )

        return

    try:

        value = parse_amount(
            amount
        )

    except ValueError:

        await ctx.send(
            "❌ Invalid amount. Use 10m / 500k / 1b"
        )

        return

    previous_state = backup_donation_state()

    key = str(member.id)

    donations_data[
        "donations"
    ][key] = (
        donations_data[
            "donations"
        ].get(key, 0)
        + value
    )

    donations_data[
        "clan_bank"
    ] += value

    if not save_donations():

        rollback_donations(
            previous_state
        )

        await ctx.send(
            "🚨 **Donation NOT saved.**\n"
            "The change was rolled back because "
            "the database could not be safely saved."
        )

        return

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

            if (
                role
                and role not in member.roles
            ):

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

    if not await require_donation_database(ctx):
        return

    if not ctx.message.mentions:

        await ctx.send(
            "❌ Usage: `!resetd @username`"
        )

        return

    member = ctx.message.mentions[0]

    key = str(member.id)

    previous_state = backup_donation_state()

    previous_total = donations_data[
        "donations"
    ].get(key, 0)

    donations_data[
        "donations"
    ][key] = 0

    if not save_donations():

        rollback_donations(
            previous_state
        )

        await ctx.send(
            "🚨 **Donation reset NOT saved.**\n"
            "The change was rolled back."
        )

        return

    removed_roles = []

    for _, role_name in DONATION_ROLES:

        role = discord.utils.get(
            ctx.guild.roles,
            name=role_name
        )

        if (
            role
            and role in member.roles
        ):

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
async def removetotal(
    ctx,
    *,
    input: str
):

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

        username_parts = [
            parts[i]
        ]

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

        if (
            username.lower()
            in raffle_entries
        ):

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

    if not await require_donation_database(ctx):
        return

    if not member or not amount:

        await ctx.send(
            "❌ Usage: !payout @user <amount> "
            "[description]"
        )

        return

    try:

        value = parse_amount(
            amount
        )

    except ValueError:

        await ctx.send(
            "❌ Invalid amount. Use 10m / 500k / 1b"
        )

        return

    if (
        donations_data[
            "clan_bank"
        ]
        < value
    ):

        await ctx.send(
            "❌ Insufficient funds in the clan bank."
        )

        return

    previous_state = backup_donation_state()

    donations_data[
        "clan_bank"
    ] -= value

    if not save_donations():

        rollback_donations(
            previous_state
        )

        await ctx.send(
            "🚨 **Payout NOT saved.**\n"
            "The change was rolled back."
        )

        return

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

    if not await require_donation_database(ctx):
        return

    if not member or not amount:

        await ctx.send(
            "❌ Usage: !credit @user <amount> <description>"
        )

        return

    try:

        value = parse_amount(
            amount
        )

    except ValueError:

        await ctx.send(
            "❌ Invalid amount. Use 10m / 500k / 1b"
        )

        return

    previous_state = backup_donation_state()

    key = str(member.id)

    donations_data[
        "donations"
    ][key] = (
        donations_data[
            "donations"
        ].get(key, 0)
        + value
    )

    if not save_donations():

        rollback_donations(
            previous_state
        )

        await ctx.send(
            "🚨 **Donation credit NOT saved.**\n"
            "The change was rolled back."
        )

        return

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

            if (
                role
                and role not in member.roles
            ):

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

    if not await require_donation_database(ctx):
        return

    if not amount:

        await ctx.send(
            "❌ Usage: !setcb <amount>"
        )

        return

    try:

        value = parse_amount(
            amount
        )

    except ValueError:

        await ctx.send(
            "❌ Invalid amount. Use 10m / 500k / 1b"
        )

        return

    previous_state = backup_donation_state()

    donations_data[
        "clan_bank"
    ] = value

    if not save_donations():

        rollback_donations(
            previous_state
        )

        await ctx.send(
            "🚨 **Clan bank change NOT saved.**\n"
            "The change was rolled back."
        )

        return

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

    if not await require_donation_database(ctx):
        return

    if not amount:

        await ctx.send(
            "❌ Usage: !addds <amount> [description]"
        )

        return

    try:

        value = parse_amount(
            amount
        )

    except ValueError:

        await ctx.send(
            "❌ Invalid amount. Use 10m / 500k / 1b"
        )

        return

    previous_state = backup_donation_state()

    donations_data[
        "clan_bank"
    ] += value

    if not save_donations():

        rollback_donations(
            previous_state
        )

        await ctx.send(
            "🚨 **Clan bank update NOT saved.**\n"
            "The change was rolled back."
        )

        return

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

    if not await require_donation_database(ctx):
        return

    if not member or not amount:

        await ctx.send(
            "❌ Usage: !setcredit @user <amount>"
        )

        return

    try:

        value = parse_amount(
            amount
        )

    except ValueError:

        await ctx.send(
            "❌ Invalid amount. Use 10m / 500k / 1b"
        )

        return

    previous_state = backup_donation_state()

    key = str(member.id)

    donations_data[
        "donations"
    ][key] = value

    if not save_donations():

        rollback_donations(
            previous_state
        )

        await ctx.send(
            "🚨 **Donation total NOT saved.**\n"
            "The change was rolled back."
        )

        return

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

    if not await require_donation_database(ctx):
        return

    if not name or not amount:

        await ctx.send(
            "❌ Usage: !payoutnd <name> "
            "<amount> <description>"
        )

        return

    try:

        value = parse_amount(
            amount
        )

    except ValueError:

        await ctx.send(
            "❌ Invalid amount. Use 10m / 500k / 1b"
        )

        return

    if (
        donations_data[
            "clan_bank"
        ]
        < value
    ):

        await ctx.send(
            "❌ Insufficient funds in the clan bank."
        )

        return

    previous_state = backup_donation_state()

    donations_data[
        "clan_bank"
    ] -= value

    if not save_donations():

        rollback_donations(
            previous_state
        )

        await ctx.send(
            "🚨 **Payout NOT saved.**\n"
            "The change was rolled back."
        )

        return

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


# ============================================================
# AMOUNT PARSER
# ============================================================

def parse_amount(
    amount: str
) -> int:

    amount = (
        amount
        .lower()
        .replace(",", "")
        .strip()
    )

    if amount.endswith("k"):

        return int(
            float(
                amount[:-1]
            )
            * 1_000
        )

    if amount.endswith("m"):

        return int(
            float(
                amount[:-1]
            )
            * 1_000_000
        )

    if amount.endswith("b"):

        return int(
            float(
                amount[:-1]
            )
            * 1_000_000_000
        )

    if amount.isdigit():

        return int(
            amount
        )

    raise ValueError


# ============================================================
# ERROR HANDLER
# ============================================================

@bot.event
async def on_command_error(
    ctx,
    error
):

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


# ============================================================
# START BOT
# ============================================================

if not DISCORD_TOKEN:
    print("🚨 ERROR: DISCORD_TOKEN environment variable is missing.")
else:
    print("🚀 Starting Fyre Bird Bot...")

    try:
        bot.run(DISCORD_TOKEN)
    except Exception as e:
        print(f"🚨 BOT CRASHED: {type(e).__name__}: {e}")
        raise
    finally:
        print("⚠️ bot.run() has returned. The bot process is ending.")


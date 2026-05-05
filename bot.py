import os
import io
import matplotlib.pyplot as plt
import time
import discord
from discord.ext import commands, tasks
from groq import Groq
from dotenv import load_dotenv
from collections import deque
from database import get_world, upsert_world, get_stats, upsert_stats, log_command, log_activity

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN").replace("*", "5")
GROQ_API_KEY = os.getenv("GROQ_API_KEY").replace("*", "7").replace("&", "gsk_")

client = Groq(api_key=GROQ_API_KEY)

LIEAND_GUILD_ID = 1233621574700109924
TARGET_USER_ID = 908954867962380298

def is_admin(world, user_id):
    return user_id == TARGET_USER_ID or str(user_id) in world.get("admins", [])

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix=["!", "?"], intents=intents)

FACTIONS = [
    "The Council",
    "The Lurkers",
    "The They Gang",
    "The Randos"
]

TERRITORIES = {
    "general": {"name": "The Capital of Nullreach", "type": "capital"},
    "war": {"name": "The Bloodfields", "type": "battlefield"},
    "void": {"name": "The Cursed Expanse", "type": "cursed"}
}

# =========================
# 🌍 DATABASE FUNCTIONS
# =========================

def load_world(server_id):
    doc = get_world(server_id)

    if doc:
        return {
            "factions": doc.get("factions", {f: {"influence": 0} for f in FACTIONS}),
            "players": doc.get("players", {}),
            "lore": doc.get("lore", []),
            "admins": doc.get("admins", [])
        }

    return {
        "factions": {f: {"influence": 0} for f in FACTIONS},
        "players": {},
        "lore": [],
        "admins": []
    }

def save_world(server_id, data):
    upsert_world(server_id, data["factions"], data["players"], data["lore"], data.get("admins", []))

# =========================
# EVENT BUFFER
# =========================

event_buffers = {}

def get_buffer(guild_id):
    gid = str(guild_id)
    if gid not in event_buffers:
        event_buffers[gid] = deque(maxlen=50)
    return event_buffers[gid]

# =========================
# UTILITIES
# =========================

WAR_TRIGGERS = ["attack", "raid", "declare war", "invade", "destroy", "battle"]

def detect_war(text):
    return any(w in text.lower() for w in WAR_TRIGGERS)

def assign_faction(world, user):
    if user in world["players"]:
        return world["players"][user]

    counts = {f: 0 for f in FACTIONS}
    for f in world["players"].values():
        counts[f] += 1

    faction = min(counts, key=counts.get)
    world["players"][user] = faction
    return faction

def add_influence(world, faction, amount=1):
    world["factions"][faction]["influence"] += amount

# =========================
# DM SYSTEM
# =========================

async def send_lore_dm(text):
    try:
        user = await bot.fetch_user(TARGET_USER_ID)
        if not user:
            return

        for chunk in [text[i:i+1900] for i in range(0, len(text), 1900)]:
            await user.send("📜 **Moon Castle Chronicle Update**\n\n" + chunk)

    except Exception as e:
        print("DM failed:", e)

# =========================
# EVENTS
# =========================

@bot.event
async def on_message(message):
    if message.author.bot:
        return
    if not message.guild or message.guild.id != LIEAND_GUILD_ID:
        return

    world = load_world(message.guild.id)
    buffer = get_buffer(message.guild.id)
    stats = get_stats(message.guild.id)

    user = str(message.author)
    faction = assign_faction(world, user)

    channel = message.channel.name
    territory = TERRITORIES.get(channel, {"name": channel, "type": "unknown"})

    gain = max(1, len(message.content) // 25)
    add_influence(world, faction, gain)

    event_type = "message"
    if detect_war(message.content):
        event_type = "WAR_EVENT"
        stats["war_events"] += 1

    # Update stats
    stats["total_messages"] += 1
    counts = stats["message_counts"]
    counts[user] = counts.get(user, 0) + 1
    stats["message_counts"] = counts

    # Track faction influence history
    history = stats["faction_history"]
    history.append({
        "The Council": world["factions"]["The Council"]["influence"],
        "The Lurkers": world["factions"]["The Lurkers"]["influence"],
        "The They Gang": world["factions"]["The They Gang"]["influence"],
        "The Randos": world["factions"]["The Randos"]["influence"],
        "timestamp": str(message.created_at)
    })
    if len(history) > 500:
        history = history[-500:]
    stats["faction_history"] = history

    event = {
        "user": user,
        "faction": faction,
        "territory": territory["name"],
        "content": message.content,
        "type": event_type
    }

    buffer.append(event)
    save_world(message.guild.id, world)
    upsert_stats(message.guild.id, stats["total_messages"], stats["war_events"], stats["message_counts"], stats["faction_history"])
    log_activity(message.guild.id, user, faction, territory["name"], message.content, event_type)

    await bot.process_commands(message)
# =========================
# GROQ LORE
# =========================

def generate_lore(events):
    formatted = "\n".join(
        f"🔥 WAR: {e['faction']} attacked — {e['content']}"
        if e.get("type") == "WAR_EVENT"
        else f"[{e['faction']}] {e['user']}: {e['content']}"
        for e in events
    )

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": "You are a fantasy chronicler. Never mention Discord."},
            {"role": "user", "content": formatted}
        ]
    )

    return response.choices[0].message.content

# =========================
# COMMANDS
# =========================

@bot.command()
async def lore(ctx):
    if ctx.guild.id != LIEAND_GUILD_ID:
        return
    log_command(ctx.guild.id, str(ctx.author), "!lore")
    world = load_world(ctx.guild.id)
    buffer = get_buffer(ctx.guild.id)

    if len(buffer) < 3:
        await ctx.send("Not enough history yet.")
        return

    lore = generate_lore(list(buffer))

    world["lore"].append(lore)
    save_world(ctx.guild.id, world)

    await ctx.send("📜 **Chronicle Entry:**")
    await ctx.send(lore[:1900])
    await send_lore_dm(lore)

@bot.command()
async def admin(ctx, *, args: str):
    if ctx.guild.id != LIEAND_GUILD_ID:
        return

    world = load_world(ctx.guild.id)
    if not is_admin(world, ctx.author.id):
        await ctx.send("❌ You don't have permission to use this command.")
        return

    try:
        parts = args.rsplit(" ", 1)
        message = parts[0]
        channel_mention = parts[1]

        channel_id = int(channel_mention.strip("<#>"))
        channel = bot.get_channel(channel_id)

        if not channel:
            await ctx.send("❌ Channel not found.")
            return

        await channel.send(f"**Admin Message:** {message}")
        await ctx.message.delete()
        log_command(ctx.guild.id, str(ctx.author), "!admin", f"→ #{channel.name}: {message[:50]}")

    except Exception as e:
        await ctx.send(f"❌ Error: {e}\nUsage: `!admin <message> <#channel>`")

@bot.command()
async def swap(ctx, player1: str, player2: str):
    if ctx.guild.id != LIEAND_GUILD_ID:
        return

    world = load_world(ctx.guild.id)
    if not is_admin(world, ctx.author.id):
        await ctx.send("❌ You don't have permission to swap players.")
        return

    world = load_world(ctx.guild.id)

    if player1 not in world["players"]:
        await ctx.send(f"❌ Player `{player1}` not found.")
        return

    if player2 not in world["players"]:
        await ctx.send(f"❌ Player `{player2}` not found.")
        return

    faction1 = world["players"][player1]
    faction2 = world["players"][player2]

    if faction1 == faction2:
        await ctx.send(f"❌ Both players are already in **{faction1}**.")
        return

    world["players"][player1] = faction2
    world["players"][player2] = faction1
    save_world(ctx.guild.id, world)

    log_command(ctx.guild.id, str(ctx.author), "!swap", f"{player1} ↔ {player2}")
    await ctx.send(f"✅ Swapped **{player1}** ({faction1}) ↔ **{player2}** ({faction2})")

@bot.command()
async def msgboard(ctx):
    if ctx.guild.id != LIEAND_GUILD_ID:
        return

    log_command(ctx.guild.id, str(ctx.author), "!msgboard")
    stats = get_stats(ctx.guild.id)
    counts = stats.get("message_counts", {})

    if not counts:
        await ctx.send("No messages recorded yet.")
        return

    sorted_players = sorted(counts.items(), key=lambda x: x[1], reverse=True)[:10]
    players = [p for p, _ in sorted_players]
    messages = [c for _, c in sorted_players]

    fig, ax = plt.subplots(figsize=(10, 5))
    bars = ax.barh(players[::-1], messages[::-1], color="steelblue")
    ax.bar_label(bars, padding=3)
    ax.set_xlabel("Messages")
    ax.set_title("Top 10 Most Active Players")
    plt.tight_layout()

    buf = io.BytesIO()
    plt.savefig(buf, format="png")
    buf.seek(0)
    plt.close()

    await ctx.send(file=discord.File(buf, filename="leaderboard.png"))

@bot.command()
async def factions(ctx):
    if ctx.guild.id != LIEAND_GUILD_ID:
        return

    log_command(ctx.guild.id, str(ctx.author), "!factions")
    world = load_world(ctx.guild.id)

    FACTION_ICONS = {
        "The Council": "👑",
        "The Lurkers": "🕵️",
        "The They Gang": "⚡",
        "The Randos": "🎲"
    }

    msg = "\n⚔️  FACTIONS OF LMC  ⚔️\n"
    msg += "━" * 32 + "\n"

    for f, data in world["factions"].items():
        members = sorted([p for p, faction in world["players"].items() if faction == f])
        icon = FACTION_ICONS.get(f, "🏴")
        members_str = ", ".join(f"`{m}`" for m in members) if members else "*No members*"
        msg += f"{icon} {f} ({len(members)})\n{members_str}\n"
        msg += "─" * 32 + "\n"

    await ctx.send(msg)


@bot.command()
async def world(ctx):
    if ctx.guild.id != LIEAND_GUILD_ID:
        return
    log_command(ctx.guild.id, str(ctx.author), "!world")
    w = load_world(ctx.guild.id)

    FACTION_ICONS = {
        "The Council": "👑",
        "The Lurkers": "🕵️",
        "The They Gang": "⚡",
        "The Randos": "🎲"
    }

    sorted_factions = sorted(w["factions"].items(), key=lambda x: x[1]["influence"], reverse=True)
    numbers = ["🥇", "🥈", "🥉", "4️⃣"]

    msg = "🏰  **LMC INFLUENCE**  🏰\n"
    msg += "━" * 28 + "\n"
    for i, (f, data) in enumerate(sorted_factions):
        icon = FACTION_ICONS.get(f, "🏴")
        msg += f"{numbers[i]} {icon} **{f}** — `{data['influence']}` influence ⚡\n"

    await ctx.send(msg)
    
@bot.command()
async def influence(ctx, amount: int, *, faction: str):
    if ctx.guild.id != LIEAND_GUILD_ID:
        return

    world = load_world(ctx.guild.id)
    if not is_admin(world, ctx.author.id):
        await ctx.send("❌ You don't have permission to modify influence.")
        return
    log_command(ctx.guild.id, str(ctx.author), "!influence", f"{faction} {'+' if amount >= 0 else ''}{amount}")
    world = load_world(ctx.guild.id)

    if faction not in FACTIONS:
        await ctx.send(f"❌ Invalid faction. Choose from: {', '.join(FACTIONS)}")
        return

    old = world["factions"][faction]["influence"]
    world["factions"][faction]["influence"] += amount
    new = world["factions"][faction]["influence"]
    save_world(ctx.guild.id, world)

    sign = "+" if amount >= 0 else ""
    await ctx.send(f"✅ **{faction}** influence: {old} → {new} ({sign}{amount})")

@bot.command()
async def move(ctx, player: str, *, faction: str):
    if ctx.guild.id != LIEAND_GUILD_ID:
        return

    world = load_world(ctx.guild.id)
    if not is_admin(world, ctx.author.id):
        await ctx.send("❌ You don't have permission to move players.")
        return
    log_command(ctx.guild.id, str(ctx.author), "!move", f"{player} → {faction}")
    world = load_world(ctx.guild.id)

    if player not in world["players"]:
        await ctx.send(f"❌ Player `{player}` not found.")
        return

    if faction not in FACTIONS:
        await ctx.send(f"❌ Invalid faction. Choose from: {', '.join(FACTIONS)}")
        return

    old_faction = world["players"][player]
    world["players"][player] = faction
    save_world(ctx.guild.id, world)

    await ctx.send(f"✅ Moved `{player}` from **{old_faction}** to **{faction}**.")

@bot.command()
async def promote(ctx, member: discord.Member):
    if ctx.guild.id != LIEAND_GUILD_ID:
        return
    if ctx.author.id != TARGET_USER_ID:
        await ctx.send("❌ Only the owner can promote admins.")
        return
    world = load_world(ctx.guild.id)
    admins = world.get("admins", [])
    if str(member.id) in admins:
        await ctx.send(f"⚠️ {member.display_name} is already an admin.")
        return
    admins.append(str(member.id))
    world["admins"] = admins
    save_world(ctx.guild.id, world)
    log_command(ctx.guild.id, str(ctx.author), "!promote", f"{member.display_name} ({member.id})")
    await ctx.send(f"✅ Promoted **{member.display_name}** to admin.")

@bot.command()
async def demote(ctx, member: discord.Member):
    if ctx.guild.id != LIEAND_GUILD_ID:
        return
    if ctx.author.id != TARGET_USER_ID:
        await ctx.send("❌ Only the owner can demote admins.")
        return
    world = load_world(ctx.guild.id)
    admins = world.get("admins", [])
    if str(member.id) not in admins:
        await ctx.send(f"⚠️ {member.display_name} is not an admin.")
        return
    admins.remove(str(member.id))
    world["admins"] = admins
    save_world(ctx.guild.id, world)
    log_command(ctx.guild.id, str(ctx.author), "!demote", f"{member.display_name} ({member.id})")
    await ctx.send(f"✅ Demoted **{member.display_name}** from admin.")

@bot.command()
async def adminlist(ctx):
    if ctx.guild.id != LIEAND_GUILD_ID:
        return
    world = load_world(ctx.guild.id)
    admin_ids = world.get("admins", [])
    if not admin_ids:
        await ctx.send("No admins currently promoted.")
        return
    names = []
    for uid in admin_ids:
        try:
            user = await bot.fetch_user(int(uid))
            names.append(f"• {user.display_name}")
        except:
            names.append(f"• Unknown ({uid})")
    await ctx.send("**🛡️ Admins:**\n" + "\n".join(names))

@bot.command(name="slime")
async def slime(ctx, member: discord.Member):
    await ctx.send(
        f"{ctx.author.mention} has slimed {member.mention} out!",
        allowed_mentions=discord.AllowedMentions(users=False)
    )

@bot.command(name="love")
async def love(ctx, member: discord.Member):
    await ctx.send(
        f"{ctx.author.mention} has shown {member.mention} love!",
        allowed_mentions=discord.AllowedMentions(users=False)
    )

@bot.command(name="kirk")
async def slime(ctx, member: discord.Member):
    await ctx.send(
        f"{ctx.author.mention} has kirked {member.mention}!",
        allowed_mentions=discord.AllowedMentions(users=False)
    )

@bot.command(name="kill")
async def love(ctx, member: discord.Member):
    await ctx.send(
        f"{ctx.author.mention} has issued judgement.\n**Public execution** for {member.mention} is *imminent*.",
        allowed_mentions=discord.AllowedMentions(users=False)
    )

# =========================
# AUTO LORE
# =========================

@tasks.loop(minutes=20)
async def auto_lore():
    for guild in bot.guilds:
        if guild.id != LIEAND_GUILD_ID:
            continue

        world = load_world(guild.id)
        buffer = get_buffer(guild.id)

        if len(buffer) < 5:
            continue

        lore = generate_lore(list(buffer))

        world["lore"].append(lore)
        buffer.clear()

        save_world(guild.id, world)

        channel = discord.utils.get(guild.text_channels, name="lore")

        if channel:
            await channel.send("📜 **Moon Castle Chronicle Update**")
            await channel.send(lore[:1900])

        await send_lore_dm(lore)

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    auto_lore.start()

bot.run(DISCORD_TOKEN)

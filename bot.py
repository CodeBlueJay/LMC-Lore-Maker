import os
import time
import discord
from discord.ext import commands, tasks
from groq import Groq
from dotenv import load_dotenv
from collections import deque
from database import get_world, upsert_world

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN").replace("*", "5")
GROQ_API_KEY = os.getenv("GROQ_API_KEY").replace("*", "7").replace("&", "gsk_")

client = Groq(api_key=GROQ_API_KEY)

LIEAND_GUILD_ID = 1233621574700109924
TARGET_USER_ID = 908954867962380298

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

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
            "lore": doc.get("lore", [])
        }

    return {
        "factions": {f: {"influence": 0} for f in FACTIONS},
        "players": {},
        "lore": []
    }

def save_world(server_id, data):
    upsert_world(server_id, data["factions"], data["players"], data["lore"])

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

    user = str(message.author)
    faction = assign_faction(world, user)

    channel = message.channel.name
    territory = TERRITORIES.get(channel, {"name": channel, "type": "unknown"})

    gain = max(1, len(message.content) // 25)
    add_influence(world, faction, gain)

    event = {
        "user": user,
        "faction": faction,
        "territory": territory["name"],
        "content": message.content
    }

    if detect_war(message.content):
        event["type"] = "WAR_EVENT"

    buffer.append(event)
    save_world(message.guild.id, world)

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
async def world(ctx):
    if ctx.guild.id != LIEAND_GUILD_ID:
        return

    world = load_world(ctx.guild.id)

    msg = "\n".join(
        f"{f}: {data['influence']} influence"
        for f, data in world["factions"].items()
    )

    await ctx.send(msg)

@bot.command()
async def factions(ctx):
    if ctx.guild.id != LIEAND_GUILD_ID:
        return

    world = load_world(ctx.guild.id)

    msg = "**⚔️ Factions:**\n"
    for f in world["factions"]:
        members = [p for p, faction in world["players"].items() if faction == f]
        msg += f"\n**{f}:**\n"
        if members:
            msg += "\n".join(f"  • {m}" for m in sorted(members))
        else:
            msg += "  *No members*"
        msg += "\n"

    await ctx.send(msg)

@bot.command()
async def influence(ctx, amount: int, *, faction: str):
    if ctx.guild.id != LIEAND_GUILD_ID:
        return

    if ctx.author.id != TARGET_USER_ID:
        await ctx.send("❌ You don't have permission to modify influence.")
        return

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

    if ctx.author.id != TARGET_USER_ID:
        await ctx.send("❌ You don't have permission to move players.")
        return

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

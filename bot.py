import os
import json
import time
import discord
from discord.ext import commands, tasks
from groq import Groq
from dotenv import load_dotenv
from collections import deque

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN").replace("*", "5")
GROQ_API_KEY = os.getenv("GROQ_API_KEY").replace("*", "7").replace("&", "gsk_")

client = Groq(api_key=GROQ_API_KEY)

# =========================
# 🔒 SERVER + USER LOCK
# =========================

LIEAND_GUILD_ID = 1233621574700109924
TARGET_USER_ID = 908954867962380298

# =========================
# BOT SETUP
# =========================

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

# =========================
# FACTIONS
# =========================

FACTIONS = [
    "The Council",
    "The Lurkers",
    "The They Gang",
    "The Randos"
]

# =========================
# TERRITORIES
# =========================

TERRITORIES = {
    "general": {"name": "The Capital of Nullreach", "type": "capital"},
    "war": {"name": "The Bloodfields", "type": "battlefield"},
    "void": {"name": "The Cursed Expanse", "type": "cursed"}
}

# =========================
# WORLD STORAGE (server-specific)
# =========================

WORLD_FILE = "world.json"

def load_world():
    if os.path.exists(WORLD_FILE):
        with open(WORLD_FILE, "r") as f:
            return json.load(f)
    return {}

worlds = load_world()

def get_world(guild_id):
    gid = str(guild_id)

    if gid not in worlds:
        worlds[gid] = {
            "factions": {f: {"influence": 0} for f in FACTIONS},
            "players": {},
            "lore": []
        }

    return worlds[gid]


def save_worlds():
    with open(WORLD_FILE, "w") as f:
        json.dump(worlds, f, indent=2)

# =========================
# EVENT BUFFER (per server)
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
    t = text.lower()
    return any(w in t for w in WAR_TRIGGERS)

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
# 📩 DM SYSTEM
# =========================

async def send_lore_dm(text):
    try:
        user = await bot.fetch_user(TARGET_USER_ID)

        if not user:
            return

        chunks = [text[i:i+1900] for i in range(0, len(text), 1900)]

        for chunk in chunks:
            await user.send("📜 **Moon Castle Chronicle Update**\n\n" + chunk)

    except Exception as e:
        print("DM failed:", e)

# =========================
# EVENT COLLECTION
# =========================

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    # 🔒 ONLY THIS SERVER
    if not message.guild or message.guild.id != LIEAND_GUILD_ID:
        return

    world = get_world(message.guild.id)
    buffer = get_buffer(message.guild.id)

    user = str(message.author)
    faction = assign_faction(world, user)

    channel = message.channel.name

    territory = TERRITORIES.get(channel, {
        "name": channel,
        "type": "unknown"
    })

    gain = max(1, len(message.content) // 25)
    add_influence(world, faction, gain)

    event = {
        "user": user,
        "faction": faction,
        "channel": channel,
        "territory": territory["name"],
        "territory_type": territory["type"],
        "content": message.content,
        "time": time.time()
    }

    if detect_war(message.content):
        event["type"] = "WAR_EVENT"

    buffer.append(event)
    save_worlds()

    await bot.process_commands(message)

# =========================
# 🧠 GROQ LORE ENGINE
# =========================

def generate_lore(events):
    formatted = "\n".join(
        (
            f"🔥 WAR: {e['faction']} attacked in {e['territory']} — {e['content']}"
            if e.get("type") == "WAR_EVENT"
            else f"[{e['faction']}] {e['user']} in {e['territory']}: {e['content']}"
        )
        for e in events
    )

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {
                "role": "system",
                "content": (
                    "You are the Chronicler of Lieand's Moon Castle. "
                    "This is a living fantasy realm. "
                    "Factions are political nations. Territories are regions. "
                    "Wars become epic battles or invasions. "
                    "Never mention Discord or bots."
                )
            },
            {
                "role": "user",
                "content": f"""
Turn these events into a lore entry.

Rules:
- Give a dramatic title
- Write like ancient history
- Expand wars into battles or conflicts
- Treat factions as kingdoms

EVENTS:
{formatted}
"""
            }
        ]
    )

    return response.choices[0].message.content

# =========================
# 📜 COMMANDS
# =========================

@bot.command()
async def factions(ctx):
    if not ctx.guild or ctx.guild.id != LIEAND_GUILD_ID:
        return

    world = get_world(ctx.guild.id)

    msg = "🏰 **Moon Castle Faction Members**\n\n"
    for f in FACTIONS:
        members = [p for p, fac in world["players"].items() if fac == f]
        member_list = ", ".join(members) if members else "No members"
        msg += f"**{f}**: {member_list}\n"

    await ctx.send(msg)

@bot.command()
async def lore(ctx):
    if not ctx.guild or ctx.guild.id != LIEAND_GUILD_ID:
        return

    world = get_world(ctx.guild.id)
    buffer = get_buffer(ctx.guild.id)

    if len(buffer) < 3:
        await ctx.send("Not enough history yet.")
        return

    lore = generate_lore(list(buffer))

    world["lore"].append(lore)
    save_worlds()

    await ctx.send("📜 **Chronicle Entry:**")
    await ctx.send(lore[:1900])

    await send_lore_dm(lore)

@bot.command()
async def world(ctx):
    if not ctx.guild or ctx.guild.id != LIEAND_GUILD_ID:
        return

    world = get_world(ctx.guild.id)

    msg = "🏰 **Moon Castle Faction Influence**\n\n"

    for f, data in world["factions"].items():
        msg += f"{f}: {data['influence']} influence\n"

    await ctx.send(msg)

@bot.command()
async def move(ctx, player: str, *, faction: str):
    """Move a player to a different faction. Usage: !move <player> <faction>"""
    # Only allow the specific user
    if ctx.author.id != TARGET_USER_ID:
        await ctx.send("❌ You don't have permission to use this command.")
        return
    
    if not ctx.guild or ctx.guild.id != LIEAND_GUILD_ID:
        return

    # Check if command is from authorized server
    world = get_world(ctx.guild.id)
    
    # Normalize faction name to match case
    faction_found = None
    for f in FACTIONS:
        if f.lower() == faction.lower():
            faction_found = f
            break
    
    if not faction_found:
        factions_list = ", ".join(FACTIONS)
        await ctx.send(f"❌ Faction not found. Available: {factions_list}")
        return
    
    # Find player in world
    if player not in world["players"]:
        await ctx.send(f"❌ Player '{player}' not found in world.")
        return
    
    old_faction = world["players"][player]
    world["players"][player] = faction_found
    save_worlds()
    
    await ctx.send(f"✅ **{player}** moved from **{old_faction}** to **{faction_found}**")

# =========================
# ⏱️ AUTO LORE SYSTEM
# =========================

@tasks.loop(minutes=20)
async def auto_lore():
    for guild in bot.guilds:

        if guild.id != LIEAND_GUILD_ID:
            continue

        world = get_world(guild.id)
        buffer = get_buffer(guild.id)

        if len(buffer) < 5:
            return

        lore = generate_lore(list(buffer))

        world["lore"].append(lore)
        buffer.clear()

        save_worlds()

        channel = discord.utils.get(guild.text_channels, name="lore")

        if channel:
            await channel.send("📜 **Moon Castle Chronicle Update**")
            await channel.send(lore[:1900])

        await send_lore_dm(lore)

# =========================
# READY EVENT
# =========================

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    auto_lore.start()

# =========================
# RUN BOT
# =========================

bot.run(DISCORD_TOKEN)
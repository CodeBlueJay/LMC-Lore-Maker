import streamlit as st
import json
import os
import subprocess
import sys

WORLD_FILE = "world.json"
BOT_PID_FILE = "bot.pid"

# =========================
# BOT INITIALIZATION
# =========================

def bot_running(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True

@st.cache_resource
def initialize_bot():
    """Start the bot once and avoid duplicates across reruns."""
    if os.path.exists(BOT_PID_FILE):
        try:
            with open(BOT_PID_FILE, "r") as f:
                pid = int(f.read().strip())
        except Exception:
            pid = None

        if pid and bot_running(pid):
            return None

        try:
            os.remove(BOT_PID_FILE)
        except OSError:
            pass

    proc = subprocess.Popen([sys.executable, "bot.py"])
    with open(BOT_PID_FILE, "w") as f:
        f.write(str(proc.pid))
    return proc

# Initialize bot on app startup
initialize_bot()

# =========================
# STREAMLIT CONFIG
# =========================

st.set_page_config(page_title="Moon Castle", layout="wide")

# =========================
# LOAD WORLD
# =========================

def load_world():
    if os.path.exists(WORLD_FILE):
        with open(WORLD_FILE, "r") as f:
            return json.load(f)
    return {}

world = load_world()

st.title("🏰 Lieand's Moon Castle - Live Chronicle")

# =========================
# REFRESH BUTTON
# =========================

if st.button("🔄 Refresh"):
    st.rerun()

# =========================
# FACTIONS
# =========================

st.header("👑 Factions")

if world:
    for guild_id, data in world.items():
        st.subheader(f"Server ID: {guild_id}")

        factions = data.get("factions", {})

        for f, info in factions.items():
            st.write(f"**{f}** → {info['influence']} influence")

# =========================
# LORE VIEW
# =========================

st.header("📜 Recent Lore")

if world:
    for guild_id, data in world.items():
        lore = data.get("lore", [])[-5:]

        for entry in reversed(lore):
            st.text_area("Chronicle Entry", entry, height=200)

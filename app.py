import streamlit as st
import json
import time
import os
import subprocess
import threading
import sys

WORLD_FILE = "world.json"
LOCK_FILE = "bot.lock"

# =========================
# BOT INITIALIZATION
# =========================

def start_bot():
    """Start the bot in a separate thread"""
    try:
        subprocess.Popen(["python", "bot.py"])
    except Exception as e:
        print(f"Error starting bot: {e}")

@st.cache_resource
def initialize_bot():
    """Initialize bot only once using Streamlit's cache"""
    if not os.path.exists(LOCK_FILE):
        with open(LOCK_FILE, "w") as f:
            f.write(str(time.time()))
        
        # Start bot in a separate thread
        bot_thread = threading.Thread(target=start_bot, daemon=True)
        bot_thread.start()

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

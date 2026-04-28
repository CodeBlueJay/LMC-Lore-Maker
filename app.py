import streamlit as st
import os
import subprocess
import sys
from dotenv import load_dotenv
load_dotenv()
from database import get_world, upsert_world, supabase

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
# LOAD & SAVE WORLD
# =========================

def load_world():
    res = supabase.table("worlds").select("*").execute()
    data = {}
    for doc in res.data:
        data[doc["server_id"]] = {
            "factions": doc.get("factions", {}),
            "players": doc.get("players", {}),
            "lore": doc.get("lore", [])
        }
    return data

def save_world(world):
    for server_id, data in world.items():
        upsert_world(server_id, data["factions"], data["players"], data["lore"])

# =========================
# AUTHENTICATION STATE
# =========================

if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

# =========================
# PAGE LAYOUT
# =========================

# Top bar with title and login button
col_title, col_login = st.columns([5, 1])

with col_title:
    st.title("🏰 Lieand's Moon Castle")

with col_login:
    if not st.session_state.authenticated:
        if st.button("🔐 Admin", key="admin_btn"):
            st.session_state.show_login = True
    else:
        col_user, col_logout = st.columns(2)
        with col_user:
            st.write("✅ Admin")
        with col_logout:
            if st.button("Logout"):
                st.session_state.authenticated = False
                st.rerun()

# =========================
# LOGIN MODAL
# =========================

if st.session_state.get("show_login", False) and not st.session_state.authenticated:
    st.divider()
    st.subheader("🔐 Admin Login")
    
    username = st.text_input("Username", key="username_input")
    password = st.text_input("Password", type="password", key="password_input")
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Login"):
            if username == "admin" and password == "root":
                st.session_state.authenticated = True
                st.session_state.show_login = False
                st.rerun()
            else:
                st.error("Invalid credentials")
    
    with col2:
        if st.button("Cancel"):
            st.session_state.show_login = False
            st.rerun()
    
    st.divider()

# =========================
# REFRESH BUTTON
# =========================

if st.button("🔄 Refresh Data"):
    st.rerun()

world = load_world()

# =========================
# PUBLIC DASHBOARD (Always visible)
# =========================

st.header("👑 Factions Overview")

if world:
    for guild_id, data in world.items():
        factions = data.get("factions", {})
        players = data.get("players", {})

        # Faction influence
        col1, col2, col3, col4 = st.columns(4)
        columns = [col1, col2, col3, col4]
        
        for idx, (f, info) in enumerate(factions.items()):
            with columns[idx % 4]:
                st.metric(label=f, value=f"{info['influence']} ⚡")

        # Player count per faction
        st.write("**Players per Faction:**")
        faction_counts = {}
        faction_players = {f: [] for f in factions.keys()}
        
        for p, f in players.items():
            faction_counts[f] = faction_counts.get(f, 0) + 1
            faction_players[f].append(p)
        
        col1, col2, col3, col4 = st.columns(4)
        columns = [col1, col2, col3, col4]
        
        for idx, f in enumerate(data.get("factions", {}).keys()):
            count = faction_counts.get(f, 0)
            with columns[idx % 4]:
                st.info(f"**{f}**\n{count} 👥")
        
        # Player list per faction
        st.write("**Members by Faction:**")
        col1, col2, col3, col4 = st.columns(4)
        columns = [col1, col2, col3, col4]
        
        for idx, f in enumerate(data.get("factions", {}).keys()):
            with columns[idx % 4]:
                st.write(f"**{f}**")
                if faction_players.get(f):
                    for player in sorted(faction_players.get(f, [])):
                        st.write(f"  • {player}")
                else:
                    st.write("  *No members*")

# =========================
# RECENT LORE (Always visible)
# =========================

st.divider()
st.header("📜 Recent Lore")

if world:
    for guild_id, data in world.items():
        lore = data.get("lore", [])[-5:]

        if lore:
            for i, entry in enumerate(reversed(lore), 1):
                with st.expander(f"📖 Entry {len(lore) - i + 1}"):
                    st.text(entry)
        else:
            st.info("No lore entries yet")

# =========================
# ADMIN PANEL (Only if authenticated)
# =========================

if st.session_state.authenticated:
    st.divider()
    st.header("🛠️ Admin Panel")
    
    admin_tab1, admin_tab2 = st.tabs(["👥 Manage Players", "📊 Admin Dashboard"])
    
    with admin_tab1:
        st.subheader("Move Players Between Factions")
        
        if world:
            for guild_id, data in world.items():
                factions = list(data.get("factions", {}).keys())
                players = data.get("players", {})
                
                # Move player to faction
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    player_name = st.selectbox(
                        "Select Player",
                        sorted(players.keys()),
                        key=f"player_select_{guild_id}"
                    )
                
                with col2:
                    new_faction = st.selectbox(
                        "Move to Faction",
                        factions,
                        key=f"faction_select_{guild_id}"
                    )
                
                with col3:
                    if st.button("Move Player", key=f"move_btn_{guild_id}"):
                        if player_name:
                            data["players"][player_name] = new_faction
                            save_world(world)
                            st.success(f"✅ Moved {player_name} to {new_faction}")
                            st.rerun()
                
                # Player management table
                st.write("**All Players:**")
                player_data = []
                for p, f in sorted(players.items()):
                    player_data.append({"Player": p, "Faction": f})
                
                if player_data:
                    st.dataframe(player_data, use_container_width=True)
    
    with admin_tab2:
        st.subheader("Modify Faction Influence")
        
        if world:
            for guild_id, data in world.items():
                factions = list(data.get("factions", {}).keys())
                
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    faction_to_mod = st.selectbox(
                        "Select Faction",
                        factions,
                        key=f"faction_mod_select_{guild_id}"
                    )
                
                with col2:
                    influence_change = st.number_input(
                        "Amount to add/subtract",
                        value=0,
                        key=f"influence_change_{guild_id}"
                    )
                
                with col3:
                    if st.button("Update Influence", key=f"influence_btn_{guild_id}"):
                        data["factions"][faction_to_mod]["influence"] += int(influence_change)
                        save_world(world)
                        st.success(f"✅ Updated {faction_to_mod} influence by {influence_change}")
                        st.rerun()

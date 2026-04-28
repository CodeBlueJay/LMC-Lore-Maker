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
    import pandas as pd
    import plotly.express as px

    for guild_id, data in world.items():
        lore = data.get("lore", [])
        recent_lore = lore[-5:]

        if recent_lore:
            for i, entry in enumerate(reversed(recent_lore), 1):
                with st.expander(f"📖 Entry {len(recent_lore) - i + 1}"):
                    st.text(entry)
        else:
            st.info("No lore entries yet")

        # Timeline
        logs = supabase.table("command_logs") \
            .select("*") \
            .eq("server_id", guild_id) \
            .eq("command", "!lore") \
            .order("timestamp", desc=False) \
            .execute()

        if logs.data:
            df = pd.DataFrame(logs.data)
            df["timestamp"] = pd.to_datetime(df["timestamp"])
            df["entry"] = [f"Entry {i+1}" for i in range(len(df))]

            fig = px.scatter(
                df,
                x="timestamp",
                y=[1] * len(df),
                text="entry",
                title="Lore Generation Timeline",
                labels={"timestamp": "Time"},
                hover_data={"user_name": True, "timestamp": True}
            )
            fig.update_traces(marker=dict(size=12, symbol="diamond"), textposition="top center")
            fig.update_yaxes(visible=False)
            fig.update_layout(height=250)
            st.plotly_chart(fig, use_container_width=True)

# =========================
# ADMIN PANEL (Only if authenticated)
# =========================

if st.session_state.authenticated:
    st.divider()
    st.header("🛠️ Admin Panel")
    from database import get_stats, get_command_logs, get_activity_feed, log_command

    admin_tab1, admin_tab2, admin_tab3 = st.tabs(["👥 Manage Players", "📊 Manage Influences", "📈 Stats & Logs"])

    with admin_tab1:
        if world:
            for guild_id, data in world.items():
                factions = list(data.get("factions", {}).keys())
                players = data.get("players", {})

                # Move player
                st.subheader("🔀 Move Player")
                col1, col2, col3 = st.columns(3)
                with col1:
                    player_name = st.selectbox("Select Player", sorted(players.keys()), key=f"player_select_{guild_id}")
                with col2:
                    new_faction = st.selectbox("Move to Faction", factions, key=f"faction_select_{guild_id}")
                with col3:
                    if st.button("Move Player", key=f"move_btn_{guild_id}"):
                        if player_name:
                            old_faction = data["players"][player_name]
                            data["players"][player_name] = new_faction
                            save_world(world)
                            log_command(guild_id, "admin", "!move", f"{player_name}: {old_faction} → {new_faction}")
                            st.success(f"✅ Moved {player_name} to {new_faction}")
                            st.rerun()

                st.divider()

                # Swap players
                st.subheader("🔄 Swap Players")
                col1, col2, col3 = st.columns(3)
                sorted_players = sorted(players.keys())
                with col1:
                    swap_player1 = st.selectbox("Player 1", sorted_players, key=f"swap1_{guild_id}")
                with col2:
                    swap_player2 = st.selectbox("Player 2", sorted_players, key=f"swap2_{guild_id}")
                with col3:
                    if st.button("Swap", key=f"swap_btn_{guild_id}"):
                        if swap_player1 == swap_player2:
                            st.error("❌ Select two different players.")
                        elif data["players"][swap_player1] == data["players"][swap_player2]:
                            st.error("❌ Both players are in the same faction.")
                        else:
                            f1 = data["players"][swap_player1]
                            f2 = data["players"][swap_player2]
                            data["players"][swap_player1] = f2
                            data["players"][swap_player2] = f1
                            save_world(world)
                            log_command(guild_id, "admin", "!swap", f"{swap_player1} ({f1}) ↔ {swap_player2} ({f2})")
                            st.success(f"✅ Swapped {swap_player1} ↔ {swap_player2}")
                            st.rerun()

                st.divider()

                # Add new player
                st.subheader("➕ Add New Player")
                col1, col2, col3 = st.columns(3)
                with col1:
                    new_player_name = st.text_input("Player Username", key=f"new_player_{guild_id}")
                with col2:
                    new_player_faction = st.selectbox("Assign to Faction", factions, key=f"new_player_faction_{guild_id}")
                with col3:
                    if st.button("Add Player", key=f"add_player_btn_{guild_id}"):
                        if new_player_name:
                            if new_player_name in data["players"]:
                                st.warning(f"⚠️ {new_player_name} already exists in {data['players'][new_player_name]}")
                            else:
                                data["players"][new_player_name] = new_player_faction
                                save_world(world)
                                log_command(guild_id, "admin", "add_player", f"{new_player_name} → {new_player_faction}")
                                st.success(f"✅ Added {new_player_name} to {new_player_faction}")
                                st.rerun()
                        else:
                            st.error("Please enter a player name.")

                st.divider()

                # Player table
                st.write("**All Players:**")
                player_data = [{"Player": p, "Faction": f} for p, f in sorted(players.items())]
                if player_data:
                    st.dataframe(player_data, use_container_width=True)

    with admin_tab2:
        st.subheader("Modify Faction Influence")
        if world:
            for guild_id, data in world.items():
                factions = list(data.get("factions", {}).keys())
                col1, col2, col3 = st.columns(3)
                with col1:
                    faction_to_mod = st.selectbox("Select Faction", factions, key=f"faction_mod_select_{guild_id}")
                with col2:
                    influence_change = st.number_input("Amount to add/subtract", value=0, key=f"influence_change_{guild_id}")
                with col3:
                    if st.button("Update Influence", key=f"influence_btn_{guild_id}"):
                        old = data["factions"][faction_to_mod]["influence"]
                        data["factions"][faction_to_mod]["influence"] += int(influence_change)
                        new = data["factions"][faction_to_mod]["influence"]
                        save_world(world)
                        sign = "+" if influence_change >= 0 else ""
                        log_command(guild_id, "admin", "influence", f"{faction_to_mod}: {old} → {new} ({sign}{influence_change})")
                        st.success(f"✅ Updated {faction_to_mod} influence by {influence_change}")
                        st.rerun()

    with admin_tab3:
        for guild_id in world:
            import pandas as pd
            import plotly.express as px
    
            stats = get_stats(guild_id)
            logs = get_command_logs(guild_id)
            feed = get_activity_feed(guild_id)
            players = world[guild_id].get("players", {})
            factions_data = world[guild_id].get("factions", {})
    
            st.subheader("📊 Stats")
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Total Messages", stats["total_messages"])
            with col2:
                st.metric("War Events", stats["war_events"])
            with col3:
                counts = stats.get("message_counts", {})
                if counts:
                    top_player = max(counts, key=counts.get)
                    st.metric("Most Active", top_player, f"{counts[top_player]} msgs")
    
            # Influence line chart - all 4 factions
            st.subheader("📈 Faction Influence Over Time")
            history = stats.get("faction_history", [])
            if history and "The Council" in history[0]:
                df = pd.DataFrame(history)
                df["timestamp"] = pd.to_datetime(df["timestamp"])
                df = df.sort_values("timestamp")
                df_melted = df.melt(
                    id_vars="timestamp",
                    value_vars=["The Council", "The Lurkers", "The They Gang", "The Randos"],
                    var_name="Faction",
                    value_name="Influence"
                )
                fig = px.line(df_melted, x="timestamp", y="Influence", color="Faction",
                              title="All Faction Influence Over Time")
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("No influence history yet — data will appear as players chat.")
    
            # Pie chart - faction membership
            st.subheader("🥧 Faction Membership Distribution")
            faction_counts = {f: 0 for f in factions_data}
            for p, f in players.items():
                if f in faction_counts:
                    faction_counts[f] += 1
            if any(v > 0 for v in faction_counts.values()):
                fig = px.pie(
                    values=list(faction_counts.values()),
                    names=list(faction_counts.keys()),
                    title="Players per Faction"
                )
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("No players yet.")
    
            # Bar chart - most active players
            st.subheader("🏆 Most Active Players")
            counts = stats.get("message_counts", {})
            if counts:
                sorted_players = sorted(counts.items(), key=lambda x: x[1], reverse=True)
                df_players = pd.DataFrame(sorted_players, columns=["Player", "Messages"])
                fig = px.bar(df_players, x="Player", y="Messages",
                             title="Messages Sent per Player",
                             color="Messages", color_continuous_scale="blues")
                fig.update_layout(xaxis_tickangle=-45)
                st.plotly_chart(fig, use_container_width=True)
                st.dataframe(df_players, use_container_width=True)
            else:
                st.info("No message data yet.")
    
            # Command logs
            st.subheader("📋 Command Logs")
            if logs:
                st.dataframe(
                    [{"Time": l["timestamp"], "User": l["user_name"], "Command": l["command"], "Details": l["details"]} for l in logs],
                    use_container_width=True
                )
            else:
                st.info("No commands logged yet.")
    
            # Activity feed
            st.subheader("📡 Activity Feed")
            if feed:
                for entry in feed:
                    icon = "🔥" if entry["event_type"] == "WAR_EVENT" else "💬"
                    st.write(f"{icon} **{entry['user_name']}** ({entry['faction']}) in {entry['territory']}: {entry['content'][:100]}")
            else:
                st.info("No activity yet.")

if st.session_state.authenticated:
    st.divider()
    st.header("🛠️ Admin Panel")
    from database import get_stats, get_command_logs, get_activity_feed, log_command

    admin_tab1, admin_tab2, admin_tab3 = st.tabs(["👥 Manage Players", "📊 Admin Dashboard", "📈 Stats & Logs"])

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
            stats = get_stats(guild_id)
            logs = get_command_logs(guild_id)
            feed = get_activity_feed(guild_id)

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

            st.subheader("🏆 Most Active Players")
            if counts:
                sorted_players = sorted(counts.items(), key=lambda x: x[1], reverse=True)
                st.dataframe([{"Player": p, "Messages": c} for p, c in sorted_players], use_container_width=True)

            st.subheader("📈 Faction Influence Over Time")
            history = stats.get("faction_history", [])
            if history:
                import pandas as pd
                import plotly.express as px
                df = pd.DataFrame(history)
                df["timestamp"] = pd.to_datetime(df["timestamp"])
                df = df.sort_values("timestamp")
                fig = px.line(df, x="timestamp", y="influence", color="faction",
                              title="Faction Influence Over Time",
                              labels={"timestamp": "Time", "influence": "Influence", "faction": "Faction"})
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("No influence history yet.")

            st.subheader("📋 Command Logs")
            if logs:
                st.dataframe(
                    [{"Time": l["timestamp"], "User": l["user_name"], "Command": l["command"], "Details": l["details"]} for l in logs],
                    use_container_width=True
                )
            else:
                st.info("No commands logged yet.")

            st.subheader("📡 Activity Feed")
            if feed:
                for entry in feed:
                    icon = "🔥" if entry["event_type"] == "WAR_EVENT" else "💬"
                    st.write(f"{icon} **{entry['user_name']}** ({entry['faction']}) in {entry['territory']}: {entry['content'][:100]}")
            else:
                st.info("No activity yet.")

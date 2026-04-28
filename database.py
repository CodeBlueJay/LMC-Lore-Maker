from supabase import create_client
from dotenv import load_dotenv
import os

load_dotenv()

supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

def get_world(server_id):
    res = supabase.table("worlds").select("*").eq("server_id", str(server_id)).execute()
    return res.data[0] if res.data else None

def upsert_world(server_id, factions, players, lore):
    supabase.table("worlds").upsert({
        "server_id": str(server_id),
        "factions": factions,
        "players": players,
        "lore": lore
    }).execute()

def get_stats(server_id):
    res = supabase.table("stats").select("*").eq("server_id", str(server_id)).execute()
    return res.data[0] if res.data else {
        "total_messages": 0,
        "war_events": 0,
        "message_counts": {},
        "faction_history": []
    }

def upsert_stats(server_id, total_messages, war_events, message_counts, faction_history):
    supabase.table("stats").upsert({
        "server_id": str(server_id),
        "total_messages": total_messages,
        "war_events": war_events,
        "message_counts": message_counts,
        "faction_history": faction_history
    }).execute()

def log_command(server_id, user_name, command, details=""):
    supabase.table("command_logs").insert({
        "server_id": str(server_id),
        "user_name": user_name,
        "command": command,
        "details": details
    }).execute()

def log_activity(server_id, user_name, faction, territory, content, event_type="message"):
    supabase.table("activity_feed").insert({
        "server_id": str(server_id),
        "user_name": user_name,
        "faction": faction,
        "territory": territory,
        "content": content[:200],
        "event_type": event_type
    }).execute()

def get_command_logs(server_id, limit=20):
    res = supabase.table("command_logs").select("*").eq("server_id", str(server_id)).order("timestamp", desc=True).limit(limit).execute()
    return res.data

def get_activity_feed(server_id, limit=20):
    res = supabase.table("activity_feed").select("*").eq("server_id", str(server_id)).order("timestamp", desc=True).limit(limit).execute()
    return res.data

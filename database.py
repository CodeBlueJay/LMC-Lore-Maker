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
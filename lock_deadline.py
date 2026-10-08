# lock_deadline.py
import datetime
import os
import requests
from supabase import create_client, Client

# 1. Database Connection via System Environment Tokens
URL = os.environ.get("SUPABASE_URL")
KEY = os.environ.get("SUPABASE_KEY")
if not URL or not KEY:
    print("Critical Error: Missing secure environment secrets.")
    exit(1)
supabase: Client = create_client(URL, KEY)

# 2. Dynamic Timeline Reckoner
SEASON_START = datetime.datetime(2026, 9, 9, 0, 0, 0)
now = datetime.datetime.now()
current_week = 1 if now < SEASON_START else min(22, ((now - SEASON_START).days // 7) + 1)
print(f"Initiating Lock Protocol for NFL Week {current_week}...")

# 3. Resolve Active Game slug (Processes Main and 2nd_Chance sequentially)
for game_slug in ["Main", "2nd_Chance"]:
    print(f"\nEvaluating bracket rosters for: {game_slug}")
    
    # Promote all valid un-locked entries to Finalized
    supabase.table("user_picks").update({"pick_state": "Finalized"}).eq("game_type", game_slug).eq("week", current_week).eq("pick_state", "Confirmed").execute()
    
    # Track missing entries
    active = supabase.table("tournament_registrations").select("user_id, byes_used").eq("game_type", game_slug).eq("is_enrolled", True).execute().data
    picks = supabase.table("user_picks").select("user_id").eq("game_type", game_slug).eq("week", current_week).execute().data
    logged_ids = {p["user_id"] for p in (picks or [])}
    late_queue = [p for p in (active or []) if p["user_id"] not in logged_ids]
    
    if not late_queue:
        print(f"Roster perfect for {game_slug}. No overrides required.")
        continue
        
    # Query Best available FPI franchise
    rec_team = "KC"
    try:
        res = requests.get("https://espn.com", timeout=4)
        if res.status_code == 200:
            rec_team = res.json().get("items", [])[0]["team"]["abbreviation"].upper()
    except Exception: pass

    # Execute penalty routing loops
    for player in late_queue:
        u_id = player["user_id"]
        if player.get("byes_used", 0) == 0:
            supabase.table("user_picks").insert({"user_id": u_id, "game_type": game_slug, "week": current_week, "team_picked": "BYE", "pick_state": "Finalized"}).execute()
            supabase.table("tournament_registrations").update({"byes_used": 1}).eq("user_id", u_id).eq("game_type", game_slug).execute()
            print(f"Auto-assigned protective BYE.")
        else:
            supabase.table("user_picks").insert({"user_id": u_id, "game_type": game_slug, "week": current_week, "team_picked": rec_team, "pick_state": "Finalized"}).execute()
            print(f"BYE empty. Auto-assigned premium penalty powerhouse: {rec_team}")

print("\nWeekly Lock Protocol Completed Successfully.")

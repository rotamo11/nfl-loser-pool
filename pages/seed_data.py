import random
import uuid
import streamlit as st
from supabase import create_client, Client

# Initialize database connections
URL = st.secrets["SUPABASE_URL"]
KEY = st.secrets["SUPABASE_KEY"]
supabase: Client = create_client(URL, KEY)

def seed_pool_database():
    st.write("⏳ Commencing data seeding operation...")

    # --- 1. INSERT MOCK WEEKLY SCHEDULE LINES ---
    mock_games = [
        # Week 1 Schedule Matrix
        {"week": 1, "away_team": "BUF", "home_team": "KC", "kickoff_time": "2026-09-10T20:20:00Z", "espn_favored_team": "KC", "espn_favored_tier": 3.5, "winner": "KC", "is_shutout": False},
        {"week": 1, "away_team": "DET", "home_team": "SF", "kickoff_time": "2026-09-13T13:00:00Z", "espn_favored_team": "SF", "espn_favored_tier": 7.0, "winner": "DET", "is_shutout": True}, 
        {"week": 1, "away_team": "DAL", "home_team": "PHI", "kickoff_time": "2026-09-13T16:25:00Z", "espn_favored_team": "PHI", "espn_favored_tier": 2.5, "winner": "TIE", "is_shutout": False},
        
        # Week 2 Schedule Matrix
        {"week": 2, "away_team": "MIA", "home_team": "BUF", "kickoff_time": "2026-09-17T20:15:00Z", "espn_favored_team": "BUF", "espn_favored_tier": 6.0, "winner": None, "is_shutout": False},
        {"week": 2, "away_team": "BAL", "home_team": "CIN", "kickoff_time": "2026-09-20T13:00:00Z", "espn_favored_team": "BAL", "espn_favored_tier": 1.5, "winner": None, "is_shutout": False},
        {"week": 2, "away_team": "NYG", "home_team": "WAS", "kickoff_time": "2026-09-20T13:00:00Z", "espn_favored_team": "WAS", "espn_favored_tier": 3.0, "winner": None, "is_shutout": False}
    ]
    
    for game in mock_games:
        # FIX: Check if game exists by week and away_team to prevent duplication instead of risking constraint errors
        existing_game = supabase.table("nfl_schedule").select("id").eq("week", game["week"]).eq("away_team", game["away_team"]).execute().data
        if existing_game:
            supabase.table("nfl_schedule").update(game).eq("id", existing_game[0]["id"]).execute()
        else:
            supabase.table("nfl_schedule").insert(game).execute()
            
    st.success("Mock schedule lines mapped.")

    # --- 2. GENERATE DUMMY PLAYERS & REGISTER TO BRACKETS ---
    dummy_names = ["Stephen King", "Amanda Conley", "Bill Kazmierski", "John Doe", "Jane Smith", "Bob Miller", "Alice Vance", "Charlie Brown", "David Davis", "Eva Elks"]
    teams_pool = ["BUF", "KC", "DET", "SF", "DAL", "PHI", "MIA", "BAL", "CIN", "WAS"]

    for name in dummy_names:
        fake_uid = str(uuid.uuid4())
        
        # Check if user already exists under this username to avoid duplicate entry constraint failures
        existing_user = supabase.table("users").select("id").eq("username", name).execute().data
        if existing_user:
            fake_uid = existing_user[0]["id"]
        else:
            supabase.table("users").insert({"id": fake_uid, "username": name}).execute()
        
        for track in ["Main", "2nd_Chance"]:
            # FIX: Cleaned up ON CONFLICT behavior to match the explicit primary key
            supabase.table("tournament_registrations").upsert({
                "user_id": fake_uid,
                "game_type": track,
                "bracket_status": "Loser Bracket",
                "byes_used": 0
            }, on_conflict="user_id,game_type").execute()
            
            # Clear old mock selections for this user/track combo to allow clean re-runs
            supabase.table("user_picks").delete().eq("user_id", fake_uid).eq("game_type", track).execute()
            
            # --- 3. GENERATE RANDOM PICK CHOICES FOR W1 & W2 ---
            w1_pick = random.choice(teams_pool[:6])
            w1_state = "Correct" if w1_pick not in ["KC", "DET"] else "Incorrect" 
            if w1_pick == "SF" and w1_state == "Correct": 
                w1_pick = "SF_SO" 
                
            supabase.table("user_picks").insert({
                "user_id": fake_uid, "game_type": track, "week": 1, "team_picked": w1_pick, "pick_state": w1_state
            }).execute()

            w2_pick = random.choice([t for t in teams_pool if t != w1_pick.replace("_SO", "")])
            w2_state = random.choice(["Confirmed", "Finalized"])
            
            supabase.table("user_picks").insert({
                "user_id": fake_uid, "game_type": track, "week": 2, "team_picked": w2_pick, "pick_state": w2_state
            }).execute()
            
        # Update dynamic player bracket totals based on outcomes generated above
        for track in ["Main", "2nd_Chance"]:
            user_picks = supabase.table("user_picks").select("*").eq("user_id", fake_uid).eq("game_type", track).execute().data
            wrongs = sum(1 for p in user_picks if p["pick_state"] == "Incorrect")
            
            status = "Loser Bracket" if wrongs == 0 else "Winner Bracket" if wrongs == 1 else "Eliminated"
            supabase.table("tournament_registrations").update({"bracket_status": status}).eq("user_id", fake_uid).eq("game_type", track).execute()

    st.success("Seeding routine complete! Open your Results dashboard to view the generated testing parameters.")

if __name__ == "__main__":
    if st.button("Trigger Seed Script Execution"):
        seed_pool_database()

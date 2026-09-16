import streamlit as st
import requests
from supabase import create_client, Client

URL = st.secrets["SUPABASE_URL"]
KEY = st.secrets["SUPABASE_KEY"]
supabase: Client = create_client(URL, KEY)

# You get this API Key completely free from the-odds-api.com
# Paste it into your Streamlit Cloud Advanced Secrets!
API_KEY = st.secrets.get("THE_ODDS_API_KEY", "YOUR_FREE_API_KEY")

st.set_page_config(layout="wide")
st.title("🎯 Loser Pool Commissioner Engine")

admin_week = st.number_input("Configure Processing Targets (Week Num)", min_value=1, max_value=22, value=2)
admin_mode = st.selectbox("Select Target Roster Pool Group", ["Main Pool", "2nd Chance Game"])
admin_slug = "Main" if admin_mode == "Main Pool" else "2nd_Chance"

# ==========================================
# 🆕 AUTOMATED REFRESH: LIVE API INGESTION
# ==========================================
if st.button("🔄 Sync Live NFL Schedule & Spreads from API"):
    with st.spinner("Fetching latest lines from The Odds API..."):
        # Hit the American Football (NFL) spreads market endpoint
        odds_url = f"https://the-odds-api.com{API_KEY}&regions=us&markets=spreads&oddsFormat=american"
        response = requests.get(odds_url)
        
        if response.status_code == 200:
            games_data = response.json()
            synced_count = 0
            
            for game in games_data:
                home_team = game["home_team"]
                away_team = game["away_team"]
                kickoff = game["commence_time"]
                
                # Default backup variables
                favored_team = "TBD"
                favored_tier = 99.0  # Higher number means less favored
                
                # Look through bookmaker outcomes to find the point spread handicap line
                if game.get("bookmakers"):
                    # Use DraftKings or the first bookmaker listed in the JSON return data
                    bookie = game["bookmakers"][0]
                    market = next((m for m in bookie["markets"] if m["key"] == "spreads"), None)
                    if market:
                        outcomes = market["outcomes"]
                        # The favorite is whichever team has a negative handicap spread line (e.g., -7)
                        fav_outcome = min(outcomes, key=lambda x: x["point"])
                        favored_team = fav_outcome["name"]
                        favored_tier = abs(fav_outcome["point"]) # Stores the numerical spread value
                
                # Standardize team names into 3-letter abbreviations matching your roster
                # (e.g., "Buffalo Bills" -> "BUF")
                # Insert or update data on your live Supabase nfl_schedule table grid mapping array
                supabase.table("nfl_schedule").upsert({
                    "week": admin_week,
                    "away_team": away_team[:3].upper(),
                    "home_team": home_team[:3].upper(),
                    "kickoff_time": kickoff,
                    "espn_favored_team": favored_team[:3].upper(),
                    "espn_favored_tier": favored_tier
                }).execute()
                synced_count += 1
                
            st.success(f"Successfully loaded and calculated {synced_count} match lines for Week {admin_week}!")
        else:
            st.error(f"API Connection Rejected: Error Code {response.status_code}")

st.markdown("---")

# ==========================================
# 🚀 AUTOMATED FALLBACK ROUTINES BUTTON
# ==========================================
if st.button("🚀 Execute Sunday Noon ESPN Fallback Routines"):
    with st.spinner("Re-indexing missing player submittals against league rules..."):
        
        active_players = supabase.table("tournament_registrations").select("*").eq("game_type", admin_slug).neq("bracket_status", "Eliminated").execute().data
        # Select matchups that haven't kicked off yet, ordered by the largest spread favorite
        unplayed_matches = supabase.table("nfl_schedule").select("*").eq("week", admin_week).order("espn_favored_tier", desc=True).execute().data
        
        fallback_count = 0
        bye_burn_count = 0
        
        for player in active_players:
            existing = supabase.table("user_picks").select("*").eq("user_id", player["user_id"]).eq("game_type", admin_slug).eq("week", admin_week).execute().data
            
            if not existing:
                # Fallback Step 1 & 2: Burn their single bye alternative if available
                if player["byes_used"] < 1:
                    supabase.table("user_picks").insert({
                        "user_id": player["user_id"], "game_type": admin_slug, "week": admin_week, "team_picked": "BYE", "pick_state": "Finalized"
                    }).execute()
                    supabase.table("tournament_registrations").update({"byes_used": 1}).eq("user_id", player["user_id"]).eq("game_type", admin_slug).execute()
                    bye_burn_count += 1
                
                # Fallback Step 3: Auto-assign the highest favored available team (No repeat checks applied)
                else:
                    if unplayed_matches:
                        top_favored = unplayed_matches[0]["espn_favored_team"]
                        
                        supabase.table("user_picks").insert({
                            "user_id": player["user_id"], 
                            "game_type": admin_slug, 
                            "week": admin_week, 
                            "team_picked": top_favored, 
                            "pick_state": "Finalized"
                        }).execute()
                        fallback_count += 1
                        
        st.success(f"Processing sequence complete! {bye_burn_count} Byes burned. {fallback_count} Autopicks assigned via live API favorites data.")

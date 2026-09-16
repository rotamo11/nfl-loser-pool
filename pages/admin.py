import streamlit as st
from supabase import create_client, Client

URL = st.secrets["SUPABASE_URL"]
KEY = st.secrets["SUPABASE_KEY"]
supabase: Client = create_client(URL, KEY)

st.set_page_config(layout="wide")
st.title("🎯 Loser Pool Commissioner Engine")

# Administrative Parameter Configuration Matrix Controls
admin_week = st.number_input("Configure Processing Targets (Week Num)", min_value=1, max_value=22, value=2)
admin_mode = st.selectbox("Select Target Roster Pool Group", ["Main Pool", "2nd Chance Game"])
admin_slug = "Main" if admin_mode == "Main Pool" else "2nd_Chance"

st.warning("⚠️ Critical Loop Engine Override: Executing these functions will modify active player statuses.")

# --- 4. STEP 4 AUTOMATED DEFAULT FALLBACK ACTIONS ---
if st.button("🚀 Execute Sunday Noon ESPN Fallback Routines"):
    with st.spinner("Re-indexing missing player submittals against league rules..."):
        
        # 1. Gather all active non-eliminated players for this specific pool
        active_players = supabase.table("tournament_registrations").select("*").eq("game_type", admin_slug).neq("bracket_status", "Eliminated").execute().data
        
        # 2. Gather active match lines from data indices (Ordered by highest favored priority)
        unplayed_matches = supabase.table("nfl_schedule").select("*").eq("week", admin_week).order("espn_favored_tier").execute().data
        
        fallback_count = 0
        bye_burn_count = 0
        
        for player in active_players:
            # Check if this player already has a submission logged
            existing = supabase.table("user_picks").select("*").eq("user_id", player["user_id"]).eq("game_type", admin_slug).eq("week", admin_week).execute().data
            
            if not existing:
                # Rule Route A: Burn their seasonal bye alternative option if available
                if player["byes_used"] < 1:
                    supabase.table("user_picks").insert({
                        "user_id": player["user_id"], "game_type": admin_slug, "week": admin_week, "team_picked": "BYE", "pick_state": "Finalized"
                    }).execute()
                    
                    supabase.table("tournament_registrations").update({"byes_used": 1}).eq("user_id", player["user_id"]).eq("game_type", admin_slug).execute()
                    bye_burn_count += 1
                
                # Rule Route B: Force-assign highest favored ESPN team (Duplication check skipped!)
                else:
                    if unplayed_matches:
                        top_favored = unplayed_matches[0]["espn_favored_team"] # Pull first index matching highest tier favorability
                        
                        supabase.table("user_picks").insert({
                            "user_id": player["user_id"], 
                            "game_type": admin_slug, 
                            "week": admin_week, 
                            "team_picked": top_favored, 
                            "pick_state": "Finalized"
                        }).execute()
                        fallback_count += 1
                        
        st.success(f"Processing sequence complete! {bye_burn_count} Byes burned. {fallback_count} Autopicks assigned via ESPN favorites.")

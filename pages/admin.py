import streamlit as st
import requests
from supabase import create_client, Client

# Initialize database connections securely
URL = st.secrets["SUPABASE_URL"]
KEY = st.secrets["SUPABASE_KEY"]
supabase: Client = create_client(URL, KEY)

# Free API key from the-odds-api.com
API_KEY = st.secrets.get("THE_ODDS_API_KEY", "YOUR_FREE_API_KEY")

st.set_page_config(layout="wide")
st.title("Loser Pool Commissioner Engine")

# Parameter Configuration Matrix Controls
admin_week = st.number_input("Configure Processing Targets (Week Num)", min_value=1, max_value=22, value=2)
admin_mode = st.selectbox("Select Target Roster Pool Group", ["Main Pool", "2nd Chance Game"])
admin_slug = "Main" if admin_mode == "Main Pool" else "2nd_Chance"

st.markdown("---")

st.warning("⚠️ Executing the functions below can modify active player statuses.  Be sure the correct week and pool selected and proceed with caution!")

# ==========================================
# 🔄 STEP 1: SYNC SCHEDULE & ODDS FROM API
# ==========================================
if st.button("🔄 Sync Live NFL Schedule & Spreads from API", use_container_width=True):
    with st.spinner("Fetching latest lines from The Odds API..."):
        odds_url = f"https://the-odds-api.com?apiKey={API_KEY}&regions=us&markets=spreads&oddsFormat=american"
        try:
            # 1. Fetch the raw response data package
            response = requests.get(odds_url)
            
            # 2. 🛡️ CRUCIAL GUARD RAIL: Stop immediately if the server didn't return a perfect 200 OK
            if response.status_code != 200:
                st.error(f"❌ The Odds API Denied the Connection (HTTP Status {response.status_code})")
                st.markdown("**Here is the exact message your API key returned:**")
                st.code(response.text) # This reveals the actual API error message on your screen!
            else:
                # 3. Safe to parse now that we verified it is valid data
                games_data = response.json()
                synced_count = 0
                
                for game in games_data:
                    home_team = game["home_team"]
                    away_team = game["away_team"]
                    kickoff = game["commence_time"]
                    
                    favored_team = "TBD"
                    favored_tier = 99.0
                    
                    if game.get("bookmakers"):
                        bookie = game["bookmakers"][0] if isinstance(game["bookmakers"], list) and len(game["bookmakers"]) > 0 else game["bookmakers"]
                        if isinstance(bookie, dict) and bookie.get("markets"):
                            market = next((m for m in bookie["markets"] if m["key"] == "spreads"), None)
                            if market and market.get("outcomes"):
                                outcomes = market["outcomes"]
                                fav_outcome = min(outcomes, key=lambda x: x.get("point", 0))
                                favored_team = fav_outcome["name"]
                                favored_tier = abs(fav_outcome.get("point", 0))
                    
                    clean_away = away_team[:3].upper()
                    clean_home = home_team[:3].upper()
                    clean_fav = favored_team[:3].upper()
                    
                    supabase.table("nfl_schedule").upsert({
                        "week": admin_week,
                        "away_team": clean_away,
                        "home_team": clean_home,
                        "kickoff_time": kickoff,
                        "espn_favored_team": clean_fav,
                        "espn_favored_tier": favored_tier
                    }).execute()
                    synced_count += 1
                    
                st.success(f"Successfully loaded and calculated {synced_count} match lines for Week {admin_week}!")
                st.rerun()
        except Exception as e:
            st.error(f"API Connection Failed: {str(e)}")

# ========================================
# STEP 2: RUN SUNDAY NOON FALLBACKS
# ========================================
if st.button("Execute Deadline Routines", use_container_width=True):
    with st.spinner("Re-indexing missing player submittals against league rules..."):
        active_players = supabase.table("tournament_registrations").select("*").eq("game_type", admin_slug).neq("bracket_status", "Eliminated").execute().data
        unplayed_matches = supabase.table("nfl_schedule").select("*").eq("week", admin_week).order("espn_favored_tier", desc=True).execute().data
        
        fallback_count = 0
        bye_burn_count = 0
        
        for player in active_players:
            existing = supabase.table("user_picks").select("*").eq("user_id", player["user_id"]).eq("game_type", admin_slug).eq("week", admin_week).execute().data
            
            if not existing:
                if player["byes_used"] < 1:
                    supabase.table("user_picks").insert({
                        "user_id": player["user_id"], "game_type": admin_slug, "week": admin_week, "team_picked": "BYE", "pick_state": "Finalized"
                    }).execute()
                    supabase.table("tournament_registrations").update({"byes_used": 1}).eq("user_id", player["user_id"]).eq("game_type", admin_slug).execute()
                    bye_burn_count += 1
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
                        
        st.success(f"Processing complete! {bye_burn_count} Byes burned. {fallback_count} Autopicks assigned via live API favorites.")
        st.rerun()

st.markdown("---")

# ==========================================
# STEP 3: RESULTS PANEL Matrix
# ==========================================
st.subheader(f"Results Panel: Week {admin_week} ({admin_mode})")
schedule_res = supabase.table("nfl_schedule").select("*").eq("week", admin_week).execute().data

if not schedule_res:
    st.info("No games synced for this week yet. Click the API Sync button above to populate the schedule.")
else:
    for match in schedule_res:
        match_id = match["id"]
        away = match["away_team"].upper()
        home = match["home_team"].upper()
        
        with st.container(border=True):
            col_match, col_winner, col_shutout, col_action = st.columns([2.5, 2, 1.5, 1.5])
            
            with col_match:
                st.markdown(
                    f"""
                    <div style="display:flex; align-items:center; gap:10px; padding-top:10px; font-family:sans-serif;">
                        <img src="app/static/{away}.svg" width="30" height="20" style="object-fit:contain;"/> 
                        <b>{away}</b> 
                        <span style="color:gray;">@</span> 
                        <img src="app/static/{home}.svg" width="30" height="20" style="object-fit:contain;"/> 
                        <b>{home}</b>
                    </div>
                    """, 
                    unsafe_allow_html=True
                )
           
            with col_winner:
                winner_selection = st.radio(
                    "Designate Winner:",
                    options=[away, home, "TIE"],
                    index=None,
                    key=f"winner_{match_id}",
                    horizontal=True,
                    label_visibility="collapsed"
                )
                
            with col_shutout:
                is_so = st.checkbox("Shutout", key=f"so_{match_id}")
                
            with col_action:
                if st.button("Lock Score & Compute", key=f"lock_{match_id}", use_container_width=True):
                    # 🛡️ Safety Check: Halt execution if no option was selected
                    if winner_selection is None:
                        st.error("Please select a winner before locking the result!")
                    else:
                        with st.spinner("Processing player picks..."):
                            supabase.table("nfl_schedule").update({
                                "winner": winner_selection,
                                "is_shutout": is_so
                            }).eq("id", match_id).execute()
                            
                            active_picks = supabase.table("user_picks").select("*").eq("game_type", admin_slug).eq("week", admin_week).in_("team_picked", [away, f"{away}_SO", home, f"{home}_SO"]).execute().data
                            
                            for pick in active_picks:
                                chosen_team = pick["team_picked"].replace("_SO", "")
                                
                                if winner_selection == "TIE":
                                    pick_result = "Incorrect"
                                elif chosen_team != winner_selection:
                                    pick_result = "Correct"
                                else:
                                    pick_result = "Incorrect"
                                    
                                final_team_name = pick["team_picked"]
                                if pick_result == "Correct" and is_so and not final_team_name.endswith("_SO"):
                                    final_team_name = f"{chosen_team}_SO"
                                
                                supabase.table("user_picks").update({
                                    "pick_state": pick_result,
                                    "team_picked": final_team_name
                                }).eq("id", pick["id"]).execute()
                                
                                # Recalculate dynamic bracket statuses for pool accounts
                                user_id = pick["user_id"]
                                all_user_picks = supabase.table("user_picks").select("*").eq("game_type", admin_slug).eq("user_id", user_id).execute().data
                                wrong_count = sum(1 for p in all_user_picks if p["pick_state"] == "Incorrect")
                                if wrong_count == 0:
                                    new_bracket = "Loser Bracket"
                                elif wrong_count == 1:
                                    new_bracket = "Winner Bracket"
                                else:
                                    new_bracket = "Eliminated"
                                supabase.table("tournament_registrations").update({
                                    "bracket_status": new_bracket
                                }).eq("user_id", user_id).eq("game_type", admin_slug).execute()
                                st.success(f"Game results locked! Outcomes evaluated.")
                                st.rerun()

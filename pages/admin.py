import streamlit as st
import requests
import os
from supabase import create_client, Client

# --- DATABASE SETUP ---
URL = st.secrets["SUPABASE_URL"]
KEY = st.secrets["SUPABASE_KEY"]
supabase: Client = create_client(URL, KEY)

# Free API key token registry lookup from the-odds-api.com
API_KEY = st.secrets.get("THE_ODDS_API_KEY", "YOUR_FREE_API_KEY")

st.set_page_config(layout="wide")

# --- CUSTOM SIDEBAR CONFIGURATION ---
with st.sidebar:
    # 1. Main Game Mode Selector
    game_mode = st.selectbox("Select Pool", ["Main", "2nd Chance"])
    game_slug = "Main" if game_mode == "Main" else "2nd_Chance"
    CURRENT_WEEK = 2  

    # 2. Dynamic Theme Profile Mapping
    sidebar_bg = "#1d3d70" if game_slug == "Main" else "#974706"
    
    st.markdown(
        f"""
        <style>
            /* Dynamic sidebar color assignment */
            [data-testid="stSidebar"] {{
                background-color: {sidebar_bg} !important;
            }}
            /* Overwrite sidebar text to remain clean white across modes */
            [data-testid="stSidebar"] .stText, [data-testid="stSidebar"] p, 
            [data-testid="stSidebar"] h3, [data-testid="stSidebar"] label {{
                color: #ffffff !important;
            }}
            /* Force dropdown selection text contrast values */
            [data-testid="stSidebar"] div[data-baseweb="select"] div {{
                color: #1e293b !important;
            }}
        </style>
        """,
        unsafe_allow_html=True
    )
        
    st.markdown("<hr style='margin:10px 0 15px 0; border:0; border-top:1px solid rgba(255,255,255,0.3);'/>", unsafe_allow_html=True)
    
    # Basic navigation paths open to every pool competitor
    st.page_link("app.py", label="Picks")
    st.page_link("pages/overview.py", label="Overview")
    st.page_link("pages/chat.py", label="Chat")
    st.page_link("pages/rules.py", label="Rules")
    
    # ROLE GATE: Check if the logged-in session belongs to a valid administrator
    is_logged_in_admin = False
    if st.session_state.get("user"):
        try:
            admin_check = supabase.table("users").select("is_admin").eq("id", st.session_state.user.id).single().execute().data
            if admin_check and admin_check.get("is_admin", False):
                is_logged_in_admin = True
        except Exception:
            pass # Fail safely to hidden links if error occurs
            
    # Links dynamically append only if the identity verification pass clears
    if is_logged_in_admin:
        st.page_link("pages/admin.py", label="Admin")
        st.page_link("pages/seed_data.py", label="Seed Data")
    
# --- UNIFIED MASTER FRAME BRAND HEADER (Theme-Adaptive Native Fix) ---
header_col1, header_col2 = st.columns([1, 5])

with header_col1:
    local_logo = "static/loser-logo.png"
    if os.path.exists(local_logo):
        st.image(local_logo, use_container_width=True)
    else:
        st.image("https://espncdn.com", use_container_width=True)

with header_col2:
    # 1. Main Title
    st.html(
        f"""
        <div style="display: flex; align-items: flex-end; height: 85px; padding-bottom: 5px;">
            <h1 style="margin:0; font-weight:900; font-size:32px; letter-spacing:-1px;">
                2026 NFL Loser Pool &bull; {game_mode} &bull; Week {CURRENT_WEEK}
            </h1>
        </div>
        """
    )
    
    # 2. Rule Parameters Grid Rows
    metric_col1, metric_col2, metric_col3 = st.columns(3)
    with metric_col1:
        st.caption("**Weeks 1-14**")
        st.markdown("Pick 1 team to lose")
    with metric_col2:
        st.caption("**Weeks 15-18**")
        st.markdown("Pick 2 teams to lose")
    with metric_col3:
        st.caption("**Playoffs**")
        st.markdown("Pick ALL losers (repeats allowed)")
        
    # 3. Deadline Summary Row
    st.info(f"**Weekly Deadline:** Noon ET Sunday, or by kickoff of earlier game")
    
    # 4. Financials & History Footer Strip
    st.html(
        """
        <div style="margin-top:10px; padding-top:8px; border-top:1px solid rgba(128,128,128,0.2); font-family:monospace; font-size:14px; color:#3b82f6; font-weight:bold;">
            74 Players | $1850 Purse ($1110 1st / $555 2nd / $185 3rd) <br>
            <span style="opacity:0.7; font-weight:normal; font-size:14px; color:var(--text-color);">
                Last Year's Losers: S. King ($765) • A. Conley ($382.50) • B. Kazmierski ($127.50)
            </span>
        </div>
        """
    )

st.markdown("---")

# Verify current user holds administrator access clearances before displaying forms
current_user = st.session_state.get("user", None)
is_authenticated_admin = False

if current_user:
    user_record = supabase.table("users").select("is_admin").eq("id", current_user.id).execute().data
    if user_record and user_record[0].get("is_admin", False):
        is_authenticated_admin = True

# Safety checkpoint guard block: Allow developer masquerade bypass for setup staging
if not is_authenticated_admin and not st.toggle("Bypassing Admin Check for Staging/Testing"):
    st.error("Access Revoked. This panel is reserved exclusively for the League Commissioner.")
    st.stop()

# --- SEGREGATED ADMINISTRATION CONSOLE TABS ---
tab_scores, tab_users = st.tabs(["🏁 Game & Score Processing", "👥 League Roster Management"])

# ==========================================
# 🏁 TAB 1: SCORE AND SCHEDULE PROCESSING
# ==========================================
with tab_scores:
    st.warning("Executing the functions below will modify active player statuses.")
    
    col_sync, col_fallback = st.columns(2)
    with col_sync:
        if st.button("Sync Live NFL Schedule & Spreads from API", use_container_width=True):
            with st.spinner("Fetching latest lines from The Odds API..."):
                odds_url = f"https://the-odds-api.com{API_KEY}&regions=us&markets=spreads&oddsFormat=american"
                try:
                    response = requests.get(odds_url)
                    if response.status_code != 200:
                        st.error(f"The Odds API Denied Connection (HTTP Status {response.status_code})")
                        st.code(response.text)
                    else:
                        games_data = response.json()
                        synced_count = 0
                        for game in games_data:
                            home_team, away_team = game["home_team"], game["away_team"]
                            kickoff = game["commence_time"]
                            favored_team, favored_tier = "TBD", 99.0
                            
                            if game.get("bookmakers"):
                                bookie = game["bookmakers"][0] if isinstance(game["bookmakers"], list) and len(game["bookmakers"]) > 0 else game["bookmakers"]
                                if isinstance(bookie, dict) and bookie.get("markets"):
                                    market = next((m for m in bookie["markets"] if m["key"] == "spreads"), None)
                                    if market and market.get("outcomes"):
                                        outcomes = market["outcomes"]
                                        fav_outcome = min(outcomes, key=lambda x: x.get("point", 0))
                                        favored_team = fav_outcome["name"]
                                        favored_tier = abs(fav_outcome.get("point", 0))
                            
                            supabase.table("nfl_schedule").upsert({
                                "week": admin_week, "away_team": away_team[:3].upper(), "home_team": home_team[:3].upper(),
                                "kickoff_time": kickoff, "espn_favored_team": favored_team[:3].upper(), "espn_favored_tier": favored_tier
                            }).execute()
                            synced_count += 1
                        st.success(f"Successfully loaded and calculated {synced_count} match lines for Week {admin_week}!")
                        st.rerun()
                except Exception as e:
                    st.error(f"API Connection Failed: {str(e)}")

    with col_fallback:
        if st.button("Execute Deadline Routines", use_container_width=True):
            with st.spinner("Re-indexing missing player submittals against league rules..."):
                active_players = supabase.table("tournament_registrations").select("*").eq("game_type", game_slug).neq("bracket_status", "Eliminated").execute().data
                unplayed_matches = supabase.table("nfl_schedule").select("*").eq("week", admin_week).order("espn_favored_tier", desc=True).execute().data
                
                fallback_count, bye_burn_count = 0, 0
                for player in active_players:
                    existing = supabase.table("user_picks").select("*").eq("user_id", player["user_id"]).eq("game_type", game_slug).eq("week", admin_week).execute().data
                    if not existing:
                        if player["byes_used"] < 1:
                            supabase.table("user_picks").insert({"user_id": player["user_id"], "game_type": game_slug, "week": admin_week, "team_picked": "BYE", "pick_state": "Finalized"}).execute()
                            supabase.table("tournament_registrations").update({"byes_used": 1}).eq("user_id", player["user_id"]).eq("game_type", game_slug).execute()
                            bye_burn_count += 1
                        elif unplayed_matches:
                            top_favored = unplayed_matches[0]["espn_favored_team"]
                            supabase.table("user_picks").insert({"user_id": player["user_id"], "game_type": game_slug, "week": admin_week, "team_picked": top_favored, "pick_state": "Finalized"}).execute()
                            fallback_count += 1
                st.success(f"Processing complete! {bye_burn_count} Byes burned. {fallback_count} Autopicks assigned.")
                st.rerun()

    st.markdown("---")
    schedule_res = supabase.table("nfl_schedule").select("*").eq("week", admin_week).execute().data

    if not schedule_res:
        st.info("No games synced for this week yet. Click the API Sync button above to populate the schedule.")
    else:
        for match in schedule_res:
            match_id = match["id"]
            away, home = match["away_team"].upper(), match["home_team"].upper()
            
            with st.container(border=True):
                col_match, col_winner, col_shutout, col_action = st.columns([2.5, 2, 1.5, 1.5])
                
                with col_match:
                    try:
                        with open(f"static/{away}.svg", "r") as f: 
                            clean_away_svg = f.read().replace("<svg", "<svg style='width:100%; height:100%;'")
                        away_logo = f'<div style="width:28px; height:18px; display:inline-block; vertical-align:middle; margin-right:6px;">{clean_away_svg}</div>'
                    except Exception: 
                        away_logo = ""
                        
                    try:
                        with open(f"static/{home}.svg", "r") as f: 
                            clean_home_svg = f.read().replace("<svg", "<svg style='width:100%; height:100%;'")
                        home_logo = f'<div style="width:28px; height:18px; display:inline-block; vertical-align:middle; margin-right:6px;">{clean_home_svg}</div>'
                    except Exception: 
                        home_logo = ""

                    st.markdown(f'<div style="display:flex; align-items:center; gap:4px; padding-top:10px; font-family:sans-serif;">{away_logo}<b>{away}</b> <span style="color:gray;">@</span> {home_logo}<b>{home}</b></div>', unsafe_allow_html=True)
                
                with col_winner:
                    # FIX: index=None keeps the winner radio choices unselected by default
                    winner_selection = st.radio("Winner:", options=[away, home, "TIE"], index=None, key=f"winner_{match_id}", horizontal=True, label_visibility="collapsed")
                    
                with col_shutout:
                    is_so = st.checkbox("Shutout", key=f"so_{match_id}")
                    
                with col_action:
                    if st.button("Lock & Compute", key=f"lock_{match_id}", use_container_width=True):
                        # 🛡️ Safety Check: Prevent submission if no winner has been selected
                        if winner_selection is None:
                            st.error("Select winner first!")
                        else:
                            with st.spinner("Processing player picks..."):
                                supabase.table("nfl_schedule").update({"winner": winner_selection, "is_shutout": is_so}).eq("id", match_id).execute()
                                active_picks = supabase.table("user_picks").select("*").eq("game_type", game_slug).eq("week", admin_week).in_("team_picked", [away, f"{away}_SO", home, f"{home}_SO"]).execute().data
                                
                                for pick in active_picks:
                                    chosen_team = pick["team_picked"].replace("_SO", "")
                                    pick_result = "Incorrect" if winner_selection == "TIE" else "Correct" if chosen_team != winner_selection else "Incorrect"
                                    
                                    final_team_name = pick["team_picked"]
                                    if pick_result == "Correct" and is_so and not final_team_name.endswith("_SO"):
                                        final_team_name = f"{chosen_team}_SO"
                                    
                                    supabase.table("user_picks").update({"pick_state": pick_result, "team_picked": final_team_name}).eq("id", pick["id"]).execute()
                                    
                                    user_id = pick["user_id"]
                                    all_user_picks = supabase.table("user_picks").select("*").eq("game_type", game_slug).eq("user_id", user_id).execute().data
                                    wrong_count = sum(1 for p in all_user_picks if p["pick_state"] == "Incorrect")
                                    new_bracket = "Loser Bracket" if wrong_count == 0 else "Winner Bracket" if wrong_count == 1 else "Eliminated"
                                    
                                    supabase.table("tournament_registrations").update({"bracket_status": new_bracket}).eq("user_id", user_id).eq("game_type", game_slug).execute()
                                st.success("Results evaluated and locked!")
                                st.rerun()

# ==========================================
# TAB 2: ROSTER & PROFILE MANAGEMENT
# ==========================================
with tab_users:
    st.subheader("Manage Users")
    
    all_users = supabase.table("users").select("*").order("username").execute().data
    col_user_list, col_user_edit = st.columns(2)
    
    with col_user_list:
        st.markdown("### Current Users")
        if not all_users:
            st.info("No registered users inside database metadata cache charts.")
        else:
            for u in all_users:
                admin_label = " [ADMIN]" if u.get("is_admin", False) else ""
                display_text = f"**{u['username']}** ({u.get('first_name','') or ''} {u.get('last_name','') or ''}){admin_label}"
                
                if st.button(display_text, key=f"select_user_{u['id']}", use_container_width=True):
                    st.session_state.selected_mgmt_user = u
                    st.rerun()
                    
        st.markdown("---")
        with st.expander("Register and Onboard New User"):
            with st.form("new_player_form", clear_on_submit=True):
                new_username = st.text_input("Username")
                new_first = st.text_input("First Name")
                new_last = st.text_input("Last Name")
                new_email = st.text_input("Email Address")
                new_cell = st.text_input("Cell Phone Number")
                new_is_admin = st.checkbox("Grant Admin?")
                
                if st.form_submit_button("Onboard Competitor Account"):
                    if not new_username.strip():
                        st.error("Username cannot be evaluated blank.")
                    else:
                        import uuid
                        generated_uid = str(uuid.uuid4())
                        supabase.table("users").insert({
                            "id": generated_uid, "username": new_username.strip(), "first_name": new_first.strip(),
                            "last_name": new_last.strip(), "email": new_email.strip(), "cell_phone": new_cell.strip(),
                            "is_admin": new_is_admin, "first_login_complete": False
                        }).execute()
                        
                        for track in ["Main", "2nd_Chance"]:
                            supabase.table("tournament_registrations").insert({
                                "user_id": generated_uid, "game_type": track, "bracket_status": "Loser Bracket", "byes_used": 0
                            }).execute()
                        st.success(f"Profile {new_username} registered across Main and 2nd Chance tracks!")
                        st.rerun()

    with col_user_edit:
        st.markdown("### 🖋️ Profile Editor Sheet")
        selected_user = st.session_state.get("selected_mgmt_user", None)
        
        if not selected_user:
            st.info("Select a player from the left panel sheet to edit profile details.")
        else:
            with st.form("edit_player_form"):
                st.markdown(f"Editing Ledger Index ID: `{selected_user['id']}`")
                edit_username = st.text_input("Username Code Token", value=selected_user["username"])
                edit_first = st.text_input("First Name", value=selected_user.get("first_name") or "")
                edit_last = st.text_input("Last Name", value=selected_user.get("last_name") or "")
                edit_email = st.text_input("Email Address", value=selected_user.get("email") or "")
                edit_cell = st.text_input("Cell Phone Line Number", value=selected_user.get("cell_phone") or "")
                edit_is_admin = st.checkbox("Grant Platform Administrative Status privileges", value=selected_user.get("is_admin", False))
                edit_notes = st.text_input("Notes", value=selected_user.get("notes") or "")
                
                c_save, c_del = st.columns(2)
                with c_save:
                    if st.form_submit_button("Commit Changes to Database", use_container_width=True):
                        supabase.table("users").update({
                            "username": edit_username.strip(), "first_name": edit_first.strip(), "last_name": edit_last.strip(),
                            "email": edit_email.strip(), "cell_phone": edit_cell.strip(), "is_admin": edit_is_admin
                        }).eq("id", selected_user["id"]).execute()
                        st.success("User updated successfully in database!")
                        st.session_state.selected_mgmt_user = None
                        st.rerun()
                        
                with c_del:
                    if st.form_submit_button("Wipe Player from Tournament", use_container_width=True):
                        supabase.table("user_picks").delete().eq("user_id", selected_user["id"]).execute()
                        supabase.table("tournament_registrations").delete().eq("user_id", selected_user["id"]).execute()
                        supabase.table("users").delete().eq("id", selected_user["id"]).execute()
                        st.warning("User profile has been purged.")
                        st.session_state.selected_mgmt_user = None
                        st.rerun()

import streamlit as st
from supabase import create_client, Client

# 1. Initialize Supabase Database Client Connections
URL = st.secrets["SUPABASE_URL"]
KEY = st.secrets["SUPABASE_KEY"]
supabase: Client = create_client(URL, KEY)

st.set_page_config(layout="wide")

# 2. Main Navigation & Persistent Mode Toggles
game_mode = st.sidebar.selectbox("🎯 Select Pool Tournament", ["Main Pool", "2nd Chance Game"])
game_slug = "Main" if game_mode == "Main Pool" else "2nd_Chance"

# Core Configuration State Parameters
CURRENT_WEEK = 2  # Increment this as the season rolls forward

# --- Header Brand Banner Matrix ---
st.markdown(
    f"""
    <div style="background-color:#000080; padding:20px; border-radius:8px; color:white; margin-bottom:20px;">
        <h1 style="margin:0; font-weight:900;">2026 NFL LOSER POOL</h1>
        <p style="margin:5px 0 0 0; font-size:14px; opacity:0.9;">
            Active Mode: <b>{game_mode}</b> • Submit Week {CURRENT_WEEK} selections below.
        </p>
    </div>
    """, 
    unsafe_allow_html=True
)

# Persistent Helpful Quick Links Sidebar
st.sidebar.markdown("### 🔗 Quick Links")
st.sidebar.markdown("[📅 NFL Schedule Grid](http://espn.com)")
st.sidebar.markdown("[📊 ESPN Matchup Odds](https://espn.com)")
st.sidebar.markdown("[📈 ESPN Power Index (FPI)](https://espn.com)")

# --- 3. USER AUTHENTICATION STATE CONTROL ---
if 'user' not in st.session_state:
    st.session_state.user = None

if not st.session_state.user:
    st.subheader("🔒 Competitor Login Portal")
    
    # 🧪 MASQUERADE / TESTING MODE OVERRIDE
    testing_mode = st.checkbox("🧪 Enable Developer Masquerade Mode (Testing Only)")
    
    if testing_mode:
        try:
            # Fetch all user profiles from the database to populate the masquerade list
            users_list = supabase.table("users").select("id", "username").execute().data
            if users_list:
                user_options = {u["username"]: u["id"] for u in users_list}
                selected_user_name = st.selectbox("Masquerade as Player:", list(user_options.keys()))
                
                if st.button("Masquerade Login", use_container_width=True):
                    # Mock an authenticated session object matching the selected player's ID
                    class MockUser:
                        def __init__(self, uid):
                            self.id = uid
                    
                    st.session_state.user = MockUser(user_options[selected_user_name])
                    st.success(f"Masquerading successfully as {selected_user_name}!")
                    st.rerun()
            else:
                st.info("No players found in the database. Please run the seed_data.py script first.")
        except Exception as e:
            st.error(f"Could not load users for masquerade mode: {str(e)}")
            
    else:
        # Standard Production Login Window
        email = st.text_input("Registered Email Address")
        password = st.text_input("Password", type="password")
        
        if st.button("Log In", use_container_width=True):
            try:
                res = supabase.auth.sign_in_with_password({"email": email, "password": password})
                st.session_state.user = res.user
                st.success("Session secured!")
                st.rerun()
            except Exception:
                st.error("Authentication rejected. Verify your email and password.")
else:
    # Button to quickly log out and switch users during testing
    if st.sidebar.button("🚪 Log Out / Clear Session"):
        st.session_state.user = None
        st.session_state.selected_teams = []
        st.rerun()
        
    user_id = st.session_state.user.id
    
    # Fetch player details and registration bracket standing profiles
    reg_profile = supabase.table("tournament_registrations").select("*").eq("user_id", user_id).eq("game_type", game_slug).execute().data
    
    if not reg_profile:
        st.warning("You are not registered in this specific pool track. Toggle your sidebar filter options.")
    elif reg_profile[0]["bracket_status"] == "Eliminated":
        st.error("🔴 You have been Eliminated from this tournament track. Form access is locked, but you can navigate to the Overview page in the sidebar.")
    else:
        player_status = reg_profile[0]["bracket_status"]
        st.caption(f"Status: **{player_status}**")

        # --- 4. RETRIEVE HISTORICAL PLAY DATA & ENFORCE DUPLICATE RULES ---
        all_picks_res = supabase.table("user_picks").select("*").eq("user_id", user_id).eq("game_type", game_slug).execute().data
        
        # Display horizontal historical strip component
        st.write("### 📜 Your Season Selection History")
        if all_picks_res:
            cols = st.columns(min(len(all_picks_res), 18))
            for i, p in enumerate(sorted(all_picks_res, key=lambda x: x["week"])):
                with cols[i % 18]:
                    clean_t = p["team_picked"].replace("_SO", "")
                    has_so = "*" if p["team_picked"].endswith("_SO") else ""
                    st.markdown(f"<div style='border:1px solid #cbd5e1; padding:4px; border-radius:4px; text-align:center; background:#f8fafc; font-size:11px;'>W{p['week']}<br><b>{clean_t}{has_so}</b></div>", unsafe_allowed_html=True)
        else:
            st.info("No prior weeks on record yet for this season.")

        # Identify previously selected teams. If a team has a shutout suffix (_SO), ignore it once so it passes the duplicate filter validation pass.
        used_teams = []
        for p in all_picks_res:
            if p["week"] < 19:  # Regular season rule only
                if p["team_picked"].endswith("_SO"):
                    # Strip the suffix but keep it out of the filter block once to allow a secondary use rule path
                    continue
                used_teams.append(p["team_picked"])

        # Determine the number of picks required based on the game rules
        required_picks = 1 if CURRENT_WEEK <= 14 else 2 if CURRENT_WEEK <= 18 else 99
        st.write(f"### 🏈 Week {CURRENT_WEEK} Matchups — Pick **{required_picks}** Team(s) to Lose")

        # Fetch scheduled matchups from Supabase
        matchups = supabase.table("nfl_schedule").select("*").eq("week", CURRENT_WEEK).execute().data

        # Track active form selections across the current session state object
        if "selected_teams" not in st.session_state:
            st.session_state.selected_teams = []

        if not matchups:
            st.info("No matchups loaded for this week yet. The commissioner will push the active schedule shortly.")
        else:
            # --- 5. RENDER THE SELECTION MATCHUP ROWS ---
            for match in matchups:
                m_id = match["id"]
                away = match["away_team"]
                home = match["home_team"]

                # Enforce dynamic duplicate lockout validation checks
                away_is_used = away in used_teams and CURRENT_WEEK <= 18
                home_is_used = home in used_teams and CURRENT_WEEK <= 18

                # Freeze unselected items once they hit their required total
                limit_reached = len(st.session_state.selected_teams) >= required_picks
                
                col_away, col_vs, col_home = st.columns()

                with col_away:
                    is_sel_away = away in st.session_state.selected_teams
                    dis_away = away_is_used or (limit_reached and not is_sel_away)
                    
                    # Layout wrapping text, flags, and team identifiers
                    btn_label_away = f"🏈 {away} (Already Used)" if away_is_used else f"🏈 {away}"
                    if st.button(btn_label_away, key=f"btn_a_{m_id}", disabled=dis_away, type="primary" if is_sel_away else "secondary", use_container_width=True):
                        if is_sel_away:
                            st.session_state.selected_teams.remove(away)
                        else:
                            st.session_state.selected_teams.append(away)
                        st.rerun()

                with col_vs:
                    st.markdown("<center style='color:gray; font-size:11px; padding-top:6px;'>VS</center>", unsafe_allowed_html=True)

                with col_home:
                    is_sel_home = home in st.session_state.selected_teams
                    dis_home = home_is_used or (limit_reached and not is_sel_home)
                    
                    btn_label_home = f"{home} (Already Used) 🏈" if home_is_used else f"{home} 🏈"
                    if st.button(btn_label_home, key=f"btn_h_{m_id}", disabled=dis_home, type="primary" if is_sel_home else "secondary", use_container_width=True):
                        if is_sel_home:
                            st.session_state.selected_teams.remove(home)
                        else:
                            st.session_state.selected_teams.append(home)
                        st.rerun()

            # Optional: Allow selecting a league Bye option slot
            st.markdown("---")
            is_bye_selected = "BYE" in st.session_state.selected_teams
            dis_bye = (reg_profile[0]["byes_used"] >= 1) or (limit_reached and not is_bye_selected)
            if st.button("🌟 Use Weekly League Bye Option", type="primary" if is_bye_selected else "secondary", disabled=dis_bye):
                if is_bye_selected:
                    st.session_state.selected_teams.remove("BYE")
                else:
                    st.session_state.selected_teams.append("BYE")
                st.rerun()

            # --- 6. ACTION CONTROLS & THE 3-OPTION DIALOGUE POPUP ---
            st.markdown("---")
            c_sub, c_res = st.columns()
            
            # The submit action button is only unlocked once the required number of choices is reached
            submit_disabled = len(st.session_state.selected_teams) != required_picks
            
            with c_sub:
                if st.button("🚀 Submit Selection", disabled=submit_disabled, use_container_width=True):
                    st.session_state.show_confirmation_modal = True

            with c_res:
                if st.button("Reset Form", use_container_width=True):
                    st.session_state.selected_teams = []
                    st.rerun()

            # --- 7. THE SPECIFIED 3-BRANCH CONFIRMATION FLOW WINDOW ---
            if st.session_state.get("show_confirmation_modal", False):
                st.markdown("### ⚠️ Final Verification Check Required")
                st.warning(f"You are selecting: **{', '.join(st.session_state.selected_teams)}** to lose their game(s).")
                
                m_c1, m_c2, m_c3 = st.columns(3)
                
                with m_c1:
                    if st.button("Option 2: Confirm Pick (Allows later edits)", use_container_width=True):
                        # Saves to database but leaves status open as an editable draft
                        for team in st.session_state.selected_teams:
                            supabase.table("user_picks").upsert({
                                "user_id": user_id, "game_type": game_slug, "week": CURRENT_WEEK, "team_picked": team, "pick_state": "Confirmed"
                            }, on_conflict="user_id,game_type,week,team_picked").execute()
                        st.session_state.show_confirmation_modal = False
                        st.success("Draft saved successfully!")
                        st.rerun()

                with m_c2:
                    if st.button("Option 3: Finalize Pick (Locks entry entirely)", use_container_width=True):
                        # Locks down the decision completely and opens up master overview visualization access
                        for team in st.session_state.selected_teams:
                            supabase.table("user_picks").upsert({
                                "user_id": user_id, 
                                "game_type": game_slug, 
                                "week": CURRENT_WEEK, 
                                "team_picked": team, 
                                "pick_state": "Finalized"
                            }, on_conflict="user_id,game_type,week,team_picked").execute()
                        st.session_state.show_confirmation_modal = False
                        st.balloons()
                        st.success("Pick locked down! Overview accessibility unlocked.")
                        st.rerun()

                with m_c3:
                    if st.button("Option 1: Go Back / Cancel", use_container_width=True):
                        st.session_state.show_confirmation_modal = False
                        st.rerun()

import streamlit as st
from supabase import create_client, Client

# 1. Initialize Supabase Database Client Connections
URL = st.secrets["SUPABASE_URL"]
KEY = st.secrets["SUPABASE_KEY"]
supabase: Client = create_client(URL, KEY)

st.set_page_config(layout="wide")

# 2. Main Navigation & Persistent Mode Toggles
game_mode = st.sidebar.selectbox("Select Pool Tournament", ["Main Pool", "2nd Chance Game"])
game_slug = "Main" if game_mode == "Main Pool" else "2nd_Chance"

# Sets #1d3d70ff for Main Pool and #974706 for 2nd Chance Game
sidebar_bg = "#1d3d70ff" if game_slug == "Main" else "#974706"

st.markdown(
    f"""
    <style>
        /* Targets the main sidebar panel container */
        [data-testid="stSidebar"] {{
            background-color: {sidebar_bg} !important;
        }}
        
        /* Optional: Forces all text/labels inside the sidebar to remain white and legible */
        [data-testid="stSidebar"] .stText, 
        [data-testid="stSidebar"] p, 
        [data-testid="stSidebar"] h3,
        [data-testid="stSidebar"] label {{
            color: white !important;
        }}
        
        /* Optional: Makes the selectbox dropdown label text white */
        [data-testid="stSidebar"] div[data-baseweb="select"] div {{
            color: #1e293b !important; /* Keeps internal dropdown text dark for readability */
        }}
    </style>
    """,
    unsafe_allow_html=True
)

# Core Configuration State Parameters
current_week = 2  # Increment this as the season rolls forward

# --- 1. BRAND HEADER DISPLAY MATRICES ---
# Split the row into two columns for your logo image and title text alignment
header_col1, header_col2 = st.columns([1, 6])

with header_col1:
    # Load your local logo file safely using the guaranteed native image tool
    st.image("static/loser-logo.png", width=200)
with header_col2:
    st.markdown(
        f"""
        <div style="padding:10px; border-radius:8px; color:white; margin-bottom:12px; font-family:sans-serif;">
            <h1 style="margin:0; font-weight:900; letter-spacing:-1px;">2026 NFL Loser Pool &bull; {game_mode} &bull; Week {current_week}</h1>
            <div style="display:grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap:10px; font-size:14px; margin-bottom:12px; margin-top:12px; opacity:0.9;">
                <div><b>Through Week 14:</b> Pick 1 team to lose each week</div>
                <div><b>Weeks 15-18:</b> Pick 2 teams to lose each week</div>
                <div><b>Playoffs:</b> Pick loser of ALL games (Repeats allowed)</div>
            </div>
            <div style="display:grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap:10px; font-size:14px; margin-bottom:12px; margin-top:12px; opacity:0.9;">
                <div><b>Weekly Deadline:</b> Noon ET Sunday or by kickoff if taking an earlier game</div>
            </div>
            <div style="margin-top:12px; padding-top:8px; border-top:1px solid #1e3a8a; font-family:monospace; font-size:11.5px; color:#93c5fd;">
                74 Players | $1850 Purse ($1110 1st / $555 2nd / $185 3rd) | Last year's losers: Stephen King took 1st for $765, Amanda Conley took 2nd for $382.50, Bill Kazmierski took 3rd for $127.50
            </div>
        </div>
        """, 
        unsafe_allow_html=True
    )

# Persistent Helpful Quick Links Sidebar
st.sidebar.markdown("### 🔗 Quick Links")
st.sidebar.markdown("[NFL Schedule Grid](http://www.espn.com/nfl/schedulegrid)")
st.sidebar.markdown("[ESPN Odds](https://www.espn.com/nfl/odds)")
st.sidebar.markdown("[ESPN Power Index (FPI)](https://www.espn.com/nfl/fpi)")

# --- 3. USER AUTHENTICATION STATE CONTROL ---
if 'user' not in st.session_state:
    st.session_state.user = None

if not st.session_state.user:
    st.subheader("🔒 Competitor Login Portal")
    
    # 🧪 MASQUERADE / TESTING MODE OVERRIDE
    testing_mode = st.checkbox("Enable Developer Masquerade Mode (Testing Only)")
    
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
    if st.sidebar.button("Log Out"):
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
        st.write("Your Season Selection History (asterisk denotes a shutout)")# FIX: Only render columns if history count is greater than zero
        if all_picks_res:
            num_cols = min(len(all_picks_res), 18)
            if num_cols > 0:
                cols = st.columns([1] * num_cols) # Passes an explicit list of widths
                for i, p in enumerate(sorted(all_picks_res, key=lambda x: x["week"])):
                    with cols[i % num_cols]:
                        clean_t = p["team_picked"].replace("_SO", "")
                        has_so = "*" if p["team_picked"].endswith("_SO") else ""
                        st.markdown(f"<div style='border:1px solid #cbd5e1; padding:4px; border-radius:4px; text-align:center; background:#1d3d70ff; font-size:12px;'>Wk {p['week']}<br><b><img src="app/static/{clean_t}.svg" width="30" height="20" style="object-fit:contain;"/>{clean_t}{has_so}</b></div>", unsafe_allow_html=True)
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
        # Determine the dynamic singular or plural noun spelling structure
        team_word = "team" if current_week <= 14 else "teams"

        required_picks = 1 if current_week <= 14 else 2 if current_week <= 18 else 99
        st.write(f"### Week {current_week} Matchups — Pick **{required_picks}** {team_word} to Lose")

        # Fetch scheduled matchups from Supabase
        matchups = supabase.table("nfl_schedule").select("*").eq("week", current_week).execute().data

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
                away_logo = "app/static/{away}.svg"
                home = match["home_team"]
                home_logo = "app/static/{home}.svg"

                # Enforce dynamic duplicate lockout validation checks
                away_is_used = away in used_teams and current_week <= 18
                home_is_used = home in used_teams and current_week <= 18

                # Freeze unselected items once they hit their required total
                limit_reached = len(st.session_state.selected_teams) >= required_picks
                
                col_away, col_vs, col_home = st.columns([2.5, 1.0, 2.5])

                with col_away:
                    is_sel_away = away in st.session_state.selected_teams
                    dis_away = away_is_used or (limit_reached and not is_sel_away)
                    
                    # Layout wrapping text, flags, and team identifiers
                    btn_label_away = f"{away} (Already Used)" if away_is_used else f"{away}"
                    if st.button(btn_label_away, key=f"btn_a_{m_id}", disabled=dis_away, type="primary" if is_sel_away else "secondary", use_container_width=True):
                        if is_sel_away:
                            st.session_state.selected_teams.remove(away)
                        else:
                            st.session_state.selected_teams.append(away)
                        st.rerun()

                with col_vs:
                    st.markdown("<center style='color:gray; font-size:12px; padding-top:6px;'>@</center>", unsafe_allow_html=True)

                with col_home:
                    is_sel_home = home in st.session_state.selected_teams
                    dis_home = home_is_used or (limit_reached and not is_sel_home)
                    
                    btn_label_home = f"{home} (Already Used)" if home_is_used else f"{home}"
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
            if st.button("Use My Bye", type="primary" if is_bye_selected else "secondary", disabled=dis_bye):
                if is_bye_selected:
                    st.session_state.selected_teams.remove("BYE")
                else:
                    st.session_state.selected_teams.append("BYE")
                st.rerun()

            # --- 6. ACTION CONTROLS & THE 3-OPTION DIALOGUE POPUP ---
            st.markdown("---")
            c_sub, c_res = st.columns([1, 1])
            
            # The submit action button is only unlocked once the required number of choices is reached
            submit_disabled = len(st.session_state.selected_teams) != required_picks
            
            with c_sub:
                if st.button("Continue", disabled=submit_disabled, use_container_width=True):
                    st.session_state.show_confirmation_modal = True

            with c_res:
                if st.button("Reset", use_container_width=True):
                    st.session_state.selected_teams = []
                    st.rerun()

            # --- 7. THE SPECIFIED 3-BRANCH CONFIRMATION FLOW WINDOW ---
            if st.session_state.get("show_confirmation_modal", False):
                st.markdown("### Confirm or Finalize?")
                st.warning(f"You are selecting the following to lose: **{', '.join(st.session_state.selected_teams)}** ")
                
                m_c1, m_c2, m_c3 = st.columns(3)
                
                with m_c1:
                    if st.button("Confirm Pick (can still edit, Overview not available)", use_container_width=True):
                        # Saves to database but leaves status open as an editable draft
                        for team in st.session_state.selected_teams:
                            supabase.table("user_picks").upsert({
                                "user_id": user_id, "game_type": game_slug, "week": current_week, "team_picked": team, "pick_state": "Confirmed"
                            }, on_conflict="user_id,game_type,week,team_picked").execute()
                        st.session_state.show_confirmation_modal = False
                        st.success("Your pick has been Confirmed and can still be edited - it will become Finalized once the deadline passes")
                        st.rerun()

                with m_c2:
                    if st.button("Finalize Pick (locks entry, Overview available)", use_container_width=True):
                        # Locks down the decision completely and opens up master overview visualization access
                        for team in st.session_state.selected_teams:
                            supabase.table("user_picks").upsert({
                                "user_id": user_id, 
                                "game_type": game_slug, 
                                "week": current_week, 
                                "team_picked": team, 
                                "pick_state": "Finalized"
                            }, on_conflict="user_id,game_type,week,team_picked").execute()
                        st.session_state.show_confirmation_modal = False
                        st.balloons()
                        st.success("Pick locked down! Overview accessibility unlocked.")
                        st.rerun()

                with m_c3:
                    if st.button("Cancel", use_container_width=True):
                        st.session_state.show_confirmation_modal = False
                        st.rerun()

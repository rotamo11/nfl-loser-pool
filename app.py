import streamlit as st
from supabase import create_client, Client
import os
import datetime

st.set_page_config(layout="wide")

# --- DATABASE SETUP ---
URL = st.secrets["SUPABASE_URL"]
KEY = st.secrets["SUPABASE_KEY"]
supabase: Client = create_client(URL, KEY)

# --- CUSTOM SIDEBAR CONFIGURATION ---
with st.sidebar:
    # 1. Main Game Mode Selector
    game_mode = st.selectbox("Select Pool", ["Main", "2nd Chance"])
    game_slug = "Main" if game_mode == "Main" else "2nd_Chance"

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

    # --- AUTOMATIC SEASON TIMELINE RECKONER ---
    # Week 1 Wednesday anchor timestamp (September 9, 2026 at 00:00:00)
    SEASON_START_WEDNESDAY = datetime.datetime(2026, 9, 9, 0, 0, 0)
    now = datetime.datetime.now()
    
    # Calculate the elapsed weeks since kickoff
    if now < SEASON_START_WEDNESDAY:
        CALCULATED_CURRENT_WEEK = 1
    else:
        elapsed_days = (now - SEASON_START_WEDNESDAY).days
        CALCULATED_CURRENT_WEEK = min(22, (elapsed_days // 7) + 1)
    
    # Helper function to convert numeric weeks to custom regular season or playoff string labels
    def get_week_label(week_num):
        if week_num == 19:
            return "Wildcard"
        elif week_num == 20:
            return "Divisional"
        elif week_num == 21:
            return "Conference"
        elif week_num == 22:
            return "Super Bowl"
        else:
            return f"Week {week_num}"
    
    # --- SIDEBAR INTERFACE ENHANCEMENT ---
    with st.sidebar:
        week_options = []
        for w in range(1, 23):
            base_label = get_week_label(w)
            # Append current tag to the active week calculation
            if w == CALCULATED_CURRENT_WEEK:
                week_options.append(f"{base_label} (current)")
            else:
                week_options.append(base_label)
                
        # Default automatically to the calculated current week row index matching the browser time
        selected_week_label = st.selectbox(
            "Select Target Week", 
            options=week_options, 
            index=CALCULATED_CURRENT_WEEK - 1
        )
        
        # --- Reverse Map the Selection Label Back into a Clear Database Week Integer ---
        # Strip the (current) tag out if present
        clean_label = selected_week_label.replace(" (current)", "")
        
        if "Wildcard" in clean_label:
            SELECTED_WEEK = 19
        elif "Divisional" in clean_label:
            SELECTED_WEEK = 20
        elif "Conference" in clean_label:
            SELECTED_WEEK = 21
        elif "Super Bowl" in clean_label:
            SELECTED_WEEK = 22
        else:
            # Extract the trailing integer for regular season weeks (e.g., "Week 2" -> 2)
            SELECTED_WEEK = int(clean_label.split(" ")[1])

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
                2026 NFL Loser Pool &bull; {game_mode} &bull; {selected_week_label}
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

# --- USER SELECTION AUTHENTICATION & OVERRIDES GATES ---
if 'user' not in st.session_state:
    st.session_state.user = None
if 'force_password_change' not in st.session_state:
    st.session_state.force_password_change = False

if st.session_state.force_password_change:
    st.subheader("🔒 Update Your Temporary Password")
    new_pw = st.text_input("New Permanent Password", type="password")
    confirm_pw = st.text_input("Confirm Permanent Password", type="password")
    
    if st.button("Save & Update Password", use_container_width=True):
        if len(new_pw.strip()) < 6:
            st.error("Password must be at least 6 characters long.")
        elif new_pw != confirm_pw:
            st.error("Passwords do not match. Please verify your typing entry.")
        else:
            try:
                supabase.auth.update_user({"password": new_pw.strip()})
                supabase.table("users").update({"first_login_complete": True}).eq("id", st.session_state.user.id).execute()
                st.session_state.force_password_change = False
                st.success("Password updated successfully! Welcome, you loser, you!")
                st.rerun()
            except Exception as e:
                st.error(f"Failed to update password: {str(e)}")

elif not st.session_state.user:
    st.subheader("Login")
    testing_mode = st.checkbox("Enable Developer Masquerade Mode (Testing Only)")
    
    if testing_mode:
        try:
            users_list = supabase.table("users").select("id", "username").execute().data
            if users_list:
                user_options = {u["username"]: u["id"] for u in users_list}
                selected_user_name = st.selectbox("Masquerade as Player:", list(user_options.keys()))
                
                if st.button("Masquerade Login", use_container_width=True):
                    class MockUser:
                        def __init__(self, uid): self.id = uid
                    st.session_state.user = MockUser(user_options[selected_user_name])
                    st.session_state.force_password_change = False
                    st.success(f"Masquerading successfully as {selected_user_name}!")
                    st.rerun()
        except Exception as e:
            st.error(f"Could not load users for masquerade: {str(e)}")
    else:
        email = st.text_input("Email Address")
        password = st.text_input("Password", type="password")
        if st.button("Log In", use_container_width=True):
            try:
                res = supabase.auth.sign_in_with_password({"email": email, "password": password})
                st.session_state.user = res.user
                profile_check = supabase.table("users").select("first_login_complete").eq("id", res.user.id).single().execute().data
                if not profile_check or not profile_check.get("first_login_complete", False):
                    st.session_state.force_password_change = True
                st.success("Authentication validated.")
                st.rerun()
            except Exception:
                st.error("Authentication rejected. Verify your email and password.")
else:
    if st.sidebar.button("Log Out"):
        st.session_state.user = None
        st.session_state.selected_teams = []
        st.session_state.force_password_change = False
        st.rerun()
        
    user_id = st.session_state.user.id
    reg_profile = supabase.table("tournament_registrations").select("*").eq("user_id", user_id).eq("game_type", game_slug).execute().data
    
    if not reg_profile:
        st.warning("You are not registered in this specific pool track. Toggle your sidebar filter options.")
    elif reg_profile[0]["bracket_status"] == "Eliminated":
        st.error("You have been Eliminated from this game. Form access is locked, but you can navigate to the Overview page in the sidebar.")
    else:
        # 1. Recover the current player's clean bracket text status string
        player_status = reg_profile[0]["bracket_status"]
        user_profile = supabase.table("users").select("username").eq("id", user_id).single().execute().data
        username_token = user_profile.get("username", "Anonymous Player") if user_profile else "Anonymous Player"
        
        # 2. Dynamic Roster Counter: Query all active profiles registered to this game track
        all_regs = supabase.table("tournament_registrations").select("bracket_status").eq("game_type", game_slug).execute().data
        
        # Count only players who do NOT have an 'Eliminated' status string profile flag
        remaining_count = sum(1 for r in all_regs if r["bracket_status"] != "Eliminated")
        
        # 3. Render the responsive Flexbox status baseline bar
        # var(--text-color) forces matching contrast automatically across light & dark theme shifts
        st.markdown(
            f"""
            <div style="display: flex; justify-content: space-between; align-items: center; width: 100%; margin-bottom: 15px; font-family: sans-serif; font-size: 14px; font-weight: 500; color: var(--text-color); opacity: 0.85;">
                <div><h3>Status for <b>{username_token}</b>: {player_status}</h3></div>
                <div style="text-align: right;"><h3>Remaining Players: <b>{remaining_count}</b></h3></div>
            </div>
            """,
            unsafe_allow_html=True
        )

        # --- RECOVER USER COMPREHENSIVE SELECTION RECORDS ---
        all_picks_res = supabase.table("user_picks").select("*").eq("user_id", user_id).eq("game_type", game_slug).execute().data
        
        st.write("### Your Season Selection History")
        if all_picks_res:
            num_cols = min(len(all_picks_res), 18)
            if num_cols > 0:
                cols = st.columns(num_cols)
                for i, p in enumerate(sorted(all_picks_res, key=lambda x: x["week"])):
                    with cols[i % num_cols]:
                        clean_t = p["team_picked"].replace("_SO", "")
                        has_so = "*" if p["team_picked"].endswith("_SO") else ""
                        st.markdown(
                            f"""
                            <div style="border:1px solid #cbd5e1; padding:6px 4px; border-radius:4px; text-align:center; background:#000000; font-size:12px; font-family:sans-serif; box-shadow: 0 1px 2px rgba(0,0,0,0.05);">
                                <span style="color:#cbd5e1; font-size:12px; font-weight:bold; display:block; margin-bottom:2px;">Week {p['week']}</span>
                                <div style="display:flex; flex-direction:column; align-items:center; justify-content:center; gap:2px;">
                                    <img src="app/static/{clean_t.upper()}.svg" width="28" height="18" style="object-fit:contain;"/>
                                    <b style="color:#cbd5e1; font-size:12px;">{clean_t.upper()}{has_so}</b>
                                </div>
                            </div>
                            """, 
                            unsafe_allow_html=True
                        )
        else:
            st.info("No prior weeks on record yet for this season.")

        used_teams = []
        for p in all_picks_res:
            if p["week"] < 19:
                if p["team_picked"].endswith("_SO"): continue
                used_teams.append(p["team_picked"])

        # Singular vs. Plural string mapping rule definitions
        team_word = "team" if CALCULATED_CURRENT_WEEK <= 14 else "teams"
        required_picks = 1 if CALCULATED_CURRENT_WEEK <= 14 else 2 if CALCULATED_CURRENT_WEEK <= 18 else 6 if CALCULATED_CURRENT_WEEK == 19 else 4 if CALCULATED_CURRENT_WEEK == 20 else 2 if CALCULATED_CURRENT_WEEK == 21 else 1 if CALCULATED_CURRENT_WEEK == 22 else 99
        st.write(f"### Matchups — Pick **{required_picks}** {team_word} to Lose")

        matchups = supabase.table("nfl_schedule").select("*").eq("week", CALCULATED_CURRENT_WEEK).execute().data

        if "selected_teams" not in st.session_state:
            st.session_state.selected_teams = []

        if not matchups:
            st.info("No matchups loaded for this week yet.")
        else:
            # --- 5. RENDER THE SELECTION MATCHUP ROWS WITH OPTIMIZED VECTORS ---
            for match in matchups:
                m_id = match["id"]
                away = match["away_team"].upper()
                home = match["home_team"].upper()

                away_is_used = away in used_teams and CALCULATED_CURRENT_WEEK <= 18
                home_is_used = home in used_teams and CALCULATED_CURRENT_WEEK <= 18
                limit_reached = len(st.session_state.selected_teams) >= required_picks
                
                col_a_logo, col_a_btn, col_vs, col_h_btn, col_h_logo = st.columns([0.6, 2.5, 0.4, 2.5, 0.6])

                with col_a_logo:
                    try:
                        with open(f"static/{away}.svg", "r") as f:
                            svg_code = f.read()
                        # THE FIXED INLINE ENFORCER: Forces the vector paths to 100% bounds inside the tag properties
                        clean_svg = svg_code.replace("<svg", "<svg style='width:100%; height:100%; display:block;'")
                        st.markdown(f'<div style="width:32px; height:24px; padding-top:6px; margin:0 auto; display:flex; align-items:center;">{clean_svg}</div>', unsafe_allow_html=True)
                    except Exception: st.write("")
                    
                with col_a_btn:
                    is_sel_away = away in st.session_state.selected_teams
                    dis_away = away_is_used or (limit_reached and not is_sel_away)
                    btn_label_away = f"{away} (Used)" if away_is_used else f"{away}"
                    if st.button(btn_label_away, key=f"btn_a_{m_id}", disabled=dis_away, type="primary" if is_sel_away else "secondary", use_container_width=True):
                        if is_sel_away: st.session_state.selected_teams.remove(away)
                        else: st.session_state.selected_teams.append(away)
                        st.rerun()

                with col_vs:
                    st.markdown("<center style='color:#64748b; font-size:12px; font-weight:bold; padding-top:8px;'>@</center>", unsafe_allow_html=True)

                with col_h_btn:
                    is_sel_home = home in st.session_state.selected_teams
                    dis_home = home_is_used or (limit_reached and not is_sel_home)
                    btn_label_home = f"{home} (Used)" if home_is_used else f"{home}"
                    if st.button(btn_label_home, key=f"btn_h_{m_id}", disabled=dis_home, type="primary" if is_sel_home else "secondary", use_container_width=True):
                        if is_sel_home: st.session_state.selected_teams.remove(home)
                        else: st.session_state.selected_teams.append(home)
                        st.rerun()

                with col_h_logo:
                    try:
                        with open(f"static/{home}.svg", "r") as f:
                            svg_code = f.read()
                        # THE FIXED INLINE ENFORCER: Forces the vector paths to 100% bounds inside the tag properties
                        clean_svg = svg_code.replace("<svg", "<svg style='width:100%; height:100%; display:block;'")
                        st.markdown(f'<div style="width:32px; height:24px; padding-top:6px; margin:0 auto; display:flex; align-items:center;">{clean_svg}</div>', unsafe_allow_html=True)
                    except Exception: st.write("")

            st.markdown("---")
            is_bye_selected = "BYE" in st.session_state.selected_teams
            dis_bye = (reg_profile[0]["byes_used"] >= 1) or (limit_reached and not is_bye_selected)
            if st.button("Use My Bye", type="primary" if is_bye_selected else "secondary", disabled=dis_bye):
                if is_bye_selected: st.session_state.selected_teams.remove("BYE")
                else: st.session_state.selected_teams.append("BYE")
                st.rerun()

            # --- 6. ACTION SUBMIT CONTROLS MATRIX ---
            st.markdown("---")
            c_sub, c_res = st.columns(2)
            submit_disabled = len(st.session_state.selected_teams) != required_picks
            
            with c_sub:
                if st.button("Next", disabled=submit_disabled, use_container_width=True):
                    st.session_state.show_confirmation_modal = True
            with c_res:
                if st.button("Reset", use_container_width=True):
                    st.session_state.selected_teams = []
                    st.rerun()

            # --- 7. THREE-OPTION VERIFICATION DIALOGUE POPUP ---
            if st.session_state.get("show_confirmation_modal", False):
                st.markdown("### Confirmed or Finalized?")
                st.warning(f"You are selecting the following to lose: **{', '.join(st.session_state.selected_teams)}** ")
                
                m_c1, m_c2, m_c3 = st.columns(3)
                with m_c1:
                    if st.button("Confirm Pick (can still edit, Overview not visible)", use_container_width=True):
                        for team in st.session_state.selected_teams:
                            supabase.table("user_picks").upsert({"user_id": user_id, "game_type": game_slug, "week": CALCULATED_CURRENT_WEEK, "team_picked": team, "pick_state": "Confirmed"}, on_conflict="user_id,game_type,week,team_picked").execute()
                        st.session_state.show_confirmation_modal = False
                        st.success("Pick has been Confirmed and will become Finalized once the deadline passes")
                        st.rerun()
                with m_c2:
                    if st.button("Finalize Pick (locks entry, Overview is visible)", use_container_width=True):
                        for team in st.session_state.selected_teams:
                            supabase.table("user_picks").upsert({"user_id": user_id, "game_type": game_slug, "week": CALCULATED_CURRENT_WEEK, "team_picked": team, "pick_state": "Finalized"}, on_conflict="user_id,game_type,week,team_picked").execute()
                        st.session_state.show_confirmation_modal = False
                        st.balloons()
                        st.success("Pick locked down! Overview accessibility unlocked.")
                        st.rerun()
                with m_c3:
                    if st.button("Option 1: Go Back / Cancel", use_container_width=True):
                        st.session_state.show_confirmation_modal = False
                        st.rerun()

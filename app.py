import streamlit as st
from supabase import create_client, Client
import base64
import os

# --- DATABASE SETUP ---
URL = st.secrets["SUPABASE_URL"]
KEY = st.secrets["SUPABASE_KEY"]
supabase: Client = create_client(URL, KEY)

st.set_page_config(layout="wide")

# --- CUSTOM SIDEBAR CONFIGURATION ---
with st.sidebar:
    # 1. Permanent Brand Anchor Logo
    local_sidebar_logo = "static/loser-logo.png"
    if os.path.exists(local_sidebar_logo):
        st.image(local_sidebar_logo, use_container_width=True)
    else:
        st.image("https://espncdn.com", use_container_width=True)
        
    st.markdown("<hr style='margin:10px 0 15px 0; border:0; border-top:1px solid #cbd5e1;'/>", unsafe_allow_html=True)
    
    # 2. Main Game Mode Selector
    game_mode = st.selectbox("Select Pool Tournament", ["Main Pool", "2nd Chance Game"])
    game_slug = "Main" if game_mode == "Main Pool" else "2nd_Chance"
    CURRENT_WEEK = 2  

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
    
    st.markdown("<br>Tournament Menu", unsafe_allow_html=True)
    # 3. Mandated Custom Navigation Folder Structure Routes Matrix
    st.page_link("app.py", label="Selections")
    st.page_link("pages/overview.py", label="Overview")
    st.page_link("pages/chat.py", label="Smack")
    st.page_link("pages/rules.py", label="Rules")
    st.page_link("pages/admin.py", label="Admin")
    st.page_link("pages/seed_data.py", label="Seed Data")

# --- DYNAMIC BACKGROUND PATTERN COLOR ENGINE ---
sidebar_bg = "#1d3d70ff" if game_slug == "Main" else "#974706"

st.markdown(
    f"""
    <style>
        [data-testid="stSidebar"] {{
            background-color: {sidebar_bg} !important;
        }}
        [data-testid="stSidebar"] .stText, 
        [data-testid="stSidebar"] p, 
        [data-testid="stSidebar"] h3,
        [data-testid="stSidebar"] label {{
            color: white !important;
        }}
        [data-testid="stSidebar"] div[data-baseweb="select"] div {{
            color: #1e293b !important;
        }}
    </style>
    """,
    unsafe_allow_html=True
)

# --- UNIFIED TOP FRAME TEXT TITLE BANNER HEADER ---
try:
    with open("static/loser-logo.png", "rb") as image_file:
        encoded_logo = base64.b64encode(image_file.read()).decode()
    header_logo_src = f"data:image/png;base64,{encoded_logo}"
except Exception:
    header_logo_src = ""

active_title_mode = "Main Game" if game_slug == "Main" else "2nd Chance Game"
if header_logo_src:
    header_html = f"""
    <div style="display:flex; align-items:center; gap:15px; margin-bottom:25px; font-family:sans-serif;">
        <img src="{header_logo_src}" width="65" height="65" style="object-fit:contain;"/>
        <h2 style="margin:0; font-weight:900; color:#1e293b; letter-spacing:-0.5px;">
            2026 Loser Pool &bull; {active_title_mode} &bull; Week {CURRENT_WEEK}
        </h2>
    </div>
    """
else:
    header_html = f"""
    <div style="margin-bottom:25px; font-family:sans-serif;">
        <h2 style="margin:0; font-weight:900; color:#1e293b;">
            2026 Loser Pool &bull; {active_title_mode} &bull; Week {CURRENT_WEEK}
        </h2>
    </div>
    """
st.markdown(header_html, unsafe_allow_html=True)

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
                st.success("Password updated successfully! Welcome to the pool.")
                st.rerun()
            except Exception as e:
                st.error(f"Failed to update password: {str(e)}")

elif not st.session_state.user:
    st.subheader("Competitor Login Portal")
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
        email = st.text_input("Registered Email Address")
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
        st.error("You have been Eliminated from this tournament track. Form access is locked, but you can navigate to the Overview page in the sidebar.")
    else:
        player_status = reg_profile[0]["bracket_status"]
        st.caption(f"Status: **{player_status}**")

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
                                <span style="color:#cbd5e1; font-size:12px; font-weight:bold; display:block; margin-bottom:2px;">Weekk {p['week']}</span>
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
        team_word = "team" if CURRENT_WEEK <= 14 else "teams"
        required_picks = 1 if CURRENT_WEEK <= 14 else 2 if CURRENT_WEEK <= 18 else 99
        st.write(f"### Matchups — Pick **{required_picks}** {team_word} to Lose")

        matchups = supabase.table("nfl_schedule").select("*").eq("week", CURRENT_WEEK).execute().data

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

                away_is_used = away in used_teams and CURRENT_WEEK <= 18
                home_is_used = home in used_teams and CURRENT_WEEK <= 18
                limit_reached = len(st.session_state.selected_teams) >= required_picks
                
                col_a_logo, col_a_btn, col_vs, col_h_btn, col_h_logo = st.columns([0.6, 2.5, 0.4, 2.5, 0.6])

                with col_a_logo:
                    try:
                        with open(f"static/{away}.svg", "r") as f: svg_code = f.read()
                        st.markdown(f'<div style="width:32px; height:24px; padding-top:6px; margin:0 auto; display:flex; align-items:center;"><style>div svg {{ width:100% !important; height:100% !important; }}</style>{svg_code}</div>', unsafe_allow_html=True)
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
                        with open(f"static/{home}.svg", "r") as f: svg_code = f.read()
                        st.markdown(f'<div style="width:32px; height:24px; padding-top:6px; margin:0 auto; display:flex; align-items:center;"><style>div svg {{ width:100% !important; height:100% !important; }}</style>{svg_code}</div>', unsafe_allow_html=True)
                    except Exception: st.write("")

            st.markdown("---")
            is_bye_selected = "BYE" in st.session_state.selected_teams
            dis_bye = (reg_profile[0]["byes_used"] >= 1) or (limit_reached and not is_bye_selected)
            if st.button("Use Weekly League Bye Option", type="primary" if is_bye_selected else "secondary", disabled=dis_bye):
                if is_bye_selected: st.session_state.selected_teams.remove("BYE")
                else: st.session_state.selected_teams.append("BYE")
                st.rerun()

            # --- 6. ACTION SUBMIT CONTROLS MATRIX ---
            st.markdown("---")
            c_sub, c_res = st.columns(2)
            submit_disabled = len(st.session_state.selected_teams) != required_picks
            
            with c_sub:
                if st.button("Submit", disabled=submit_disabled, use_container_width=True):
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
                            supabase.table("user_picks").upsert({"user_id": user_id, "game_type": game_slug, "week": CURRENT_WEEK, "team_picked": team, "pick_state": "Confirmed"}, on_conflict="user_id,game_type,week,team_picked").execute()
                        st.session_state.show_confirmation_modal = False
                        st.success("Pick has been Confirmed and will become Finalized once the deadline passes")
                        st.rerun()
                with m_c2:
                    if st.button("Finalize Pick (locks entry, Overview is visible)", use_container_width=True):
                        for team in st.session_state.selected_teams:
                            supabase.table("user_picks").upsert({"user_id": user_id, "game_type": game_slug, "week": CURRENT_WEEK, "team_picked": team, "pick_state": "Finalized"}, on_conflict="user_id,game_type,week,team_picked").execute()
                        st.session_state.show_confirmation_modal = False
                        st.balloons()
                        st.success("Pick locked down! Overview accessibility unlocked.")
                        st.rerun()
                with m_c3:
                    if st.button("Option 1: Go Back / Cancel", use_container_width=True):
                        st.session_state.show_confirmation_modal = False
                        st.rerun()

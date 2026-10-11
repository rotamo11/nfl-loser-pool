import streamlit as st
from supabase import create_client, Client
import os
import datetime
import time
import base64
import requests

# --- SETUP MANDATORY FIRST DIRECTIVE PASS ---
st.set_page_config(layout="wide")
URL, KEY = st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"]
supabase: Client = create_client(URL, KEY)

# --- AUTOMATIC TIMELINE CALCULATOR ENGINE ---
SEASON_START_WEDNESDAY = datetime.datetime(2026, 9, 9, 0, 0, 0)
now = datetime.datetime.now()
CALCULATED_CURRENT_WEEK = 1 if now < SEASON_START_WEDNESDAY else min(22, ((now - SEASON_START_WEDNESDAY).days // 7) + 1)

def get_week_label(week_num):
    if week_num == 19: return "Wildcard"
    elif week_num == 20: return "Divisional"
    elif week_num == 21: return "Conference"
    elif week_num == 22: return "Super Bowl"
    else: return f"Week {week_num}"

# --- CUSTOM SIDEBAR CONFIGURATION ---
with st.sidebar:
    game_mode = st.selectbox("Select Pool", ["Main", "2nd Chance"])
    game_slug = "Main" if game_mode == "Main" else "2nd_Chance"
    sidebar_bg = "#1d3d70" if game_slug == "Main" else "#974706"

    st.markdown(
        f"""
        <style>
            [data-testid="stSidebar"] {{ background-color: {sidebar_bg} !important; }}
            [data-testid="stSidebar"] *, [data-testid="stSidebar"] p, 
            [data-testid="stSidebar"] h3, [data-testid="stSidebar"] label,
            [data-testid="stSidebar"] span, [data-testid="stSidebar"] summary {{
                color: #ffffff !important; -webkit-text-fill-color: #ffffff !important; opacity: 1.0 !important;
            }}
            [data-testid="stSidebar"] button, [data-testid="stSidebar"] button p, 
            [data-testid="stSidebar"] button span, [data-testid="stSidebar"] [data-testid="baseButton-secondary"] {{
                color: #ffffff !important; -webkit-text-fill-color: #ffffff !important;
                background-color: #334155 !important; border: 1px solid rgba(255, 255, 255, 0.2) !important; border-radius: 4px !important;
            }}
            [data-testid="stSidebar"] button:hover {{ background-color: #475569 !important; }}
            [data-testid="stSidebar"] input {{
                color: #ffffff !important; -webkit-text-fill-color: #ffffff !important;
                background-color: #0f172a !important; border: 1px solid rgba(255, 255, 255, 0.2) !important;
            }}
            [data-testid="stSidebar"] div[data-baseweb="select"] div,
            [data-testid="stSidebar"] ul[role="listbox"] * {{
                color: #1e293b !important; -webkit-text-fill-color: #1e293b !important;
            }}
        </style>
        """,
        unsafe_allow_html=True
    )

    def get_base64_logo_html(team_code):
        try:
            t_clean = team_code.replace("_SO", "").strip().upper()
            file_path = f"static/BYE.svg" if t_clean == "BYE" else f"static/{t_clean}.svg"
            if os.path.exists(file_path):
                with open(file_path, "rb") as f:
                    encoded = base64.b64encode(f.read()).decode("utf-8")
                return f'<img src="data:image/svg+xml;base64,{encoded}" width="24" height="15" style="object-fit:contain; vertical-align:middle; margin-right:4px;"/>'
        except Exception: pass
        return ""

    week_options = [f"{get_week_label(w)} (current)" if w == CALCULATED_CURRENT_WEEK else get_week_label(w) for w in range(1, 23)]
    selected_week_label = st.selectbox("Select Target Week", options=week_options, index=CALCULATED_CURRENT_WEEK - 1)
    clean_label = selected_week_label.replace(" (current)", "")
    
    if "Wildcard" in clean_label: NEW_WEEK = 19
    elif "Divisional" in clean_label: NEW_WEEK = 20
    elif "Conference" in clean_label: NEW_WEEK = 21
    elif "Super Bowl" in clean_label: NEW_WEEK = 22
    else: NEW_WEEK = int(clean_label.split(" ")[1])
        
    if "active_week_tracker" not in st.session_state or st.session_state.active_week_tracker != NEW_WEEK:
        st.session_state.active_week_tracker = NEW_WEEK
        st.session_state.selected_teams = []
    
    SELECTED_WEEK = st.session_state.active_week_tracker
    st.markdown("<hr style='margin:10px 0 15px 0; border:0; border-top:1px solid rgba(255,255,255,0.3);'/>", unsafe_allow_html=True)
    st.page_link("app.py", label="Picks")
    st.page_link("pages/overview.py", label="Overview")
    st.page_link("pages/chat.py", label="Chat")
    st.page_link("pages/rules.py", label="Rules")

    is_logged_in_admin = False
    if st.session_state.get("user"):
        try:
            admin_check = supabase.table("users").select("is_admin").eq("id", st.session_state.user.id).single().execute().data
            if admin_check and admin_check.get("is_admin", False):
                is_logged_in_admin = True
        except Exception: pass
            
    if is_logged_in_admin:
        st.page_link("pages/admin.py", label="Admin")
    
    st.markdown("<hr style='margin:10px 0 15px 0; border:0; border-top:1px solid rgba(255,255,255,0.3);'/>", unsafe_allow_html=True)
    st.page_link("http://espn.com", label="ESPN NFL Schedule Grid")
    st.page_link("https://espn.com", label="ESPN Odds")
    st.page_link("https://espn.com", label="ESPN Power Index")
    
    if st.session_state.get("user"):
        try:
            user_id = st.session_state.user.id
            u_prof = supabase.table("users").select("*").eq("id", user_id).single().execute().data
            if u_prof:
                st.markdown("<hr style='margin:15px 0 10px 0; border:0; border-top:1px solid rgba(255,255,255,0.15);'/>", unsafe_allow_html=True)
                with st.expander("Account Settings"):
                    with st.form("sidebar_profile_form"):
                        e_user = st.text_input("Username", value=u_prof.get("username") or "", key="sb_u")
                        e_first = st.text_input("First Name", value=u_prof.get("first_name") or "", key="sb_f")
                        e_last = st.text_input("Last Name", value=u_prof.get("last_name") or "", key="sb_l")
                        e_mail = st.text_input("Email Address", value=u_prof.get("email") or "", key="sb_e")
                        e_cell = st.text_input("Cell Phone Number", value=u_prof.get("cell_phone") or "", key="sb_c")
                        
                        carrier_options = ["Select Provider", "Verizon", "AT&T", "T-Mobile", "Sprint"]
                        current_db_carrier = u_prof.get("cell_carrier") or "Select Provider"
                        try: default_carrier_idx = carrier_options.index(current_db_carrier)
                        except ValueError: default_carrier_idx = 0
                        e_carrier = st.selectbox("Provider (Required for SMS):", options=carrier_options, index=default_carrier_idx, key="sb_carrier_select")
                        
                        pref_email = u_prof.get("alert_email", True) if u_prof.get("alert_email") is not None else True
                        pref_sms = u_prof.get("alert_sms", False)
                        st.markdown("<p style='font-size:12px; margin-bottom:2px; font-weight:bold;'>Receive Missing Pick Alerts Via:</p>", unsafe_allow_html=True)
                        c_chk_em, c_chk_sms = st.columns(2)
                        with c_chk_em: opt_email = st.checkbox("Email", value=pref_email, key="sb_alert_em")
                        with c_chk_sms: opt_sms = st.checkbox("SMS Text", value=pref_sms, key="sb_alert_sms")
                        
                        if st.form_submit_button("Save Profile Updates", width='stretch'):
                            if not e_user.strip() or not e_mail.strip(): st.error("Required fields cannot be left blank.")
                            elif opt_sms and e_carrier == "Select Provider": st.error("**Action Required:** You must select a Cellular Network Provider to enable SMS text alerts.")
                            else:
                                supabase.table("users").update({
                                    "username": e_user.strip(), "first_name": e_first.strip(), "last_name": e_last.strip(),
                                    "email": e_mail.strip(), "cell_phone": e_cell.strip(),
                                    "cell_carrier": None if e_carrier == "Select Provider" else e_carrier,
                                    "alert_email": opt_email, "alert_sms": opt_sms
                                }).eq("id", user_id).execute()
                                st.toast("Preferences Synchronized!")
                                st.rerun()
                    with st.form("sidebar_password_form", clear_on_submit=True):
                        sb_new_pw = st.text_input("New Password:", type="password", key="sb_pwd1")
                        sb_conf_pw = st.text_input("Confirm New Password:", type="password", key="sb_pwd2")
                        if st.form_submit_button("Commit Password Change", width='stretch'):
                            clean_sb_pw = sb_new_pw.strip()
                            if len(clean_sb_pw) < 6: st.sidebar.error("Password must be at least 6 characters long.")
                            elif clean_sb_pw != sb_conf_pw.strip(): st.sidebar.error("Passwords do not match.")
                            else:
                                with st.spinner("Updating encryption vaults..."):
                                    try:
                                        auth_endpoint = f"{URL}/auth/v1/admin/users/{user_id}"
                                        auth_headers = {"Authorization": f"Bearer {KEY}", "apikey": KEY, "Content-Type": "application/json"}
                                        auth_payload = {"password": clean_sb_pw}
                                        auth_response = requests.put(auth_endpoint, json=auth_payload, headers=auth_headers)
                                        if auth_response.status_code in [200, 201]:
                                            st.sidebar.success("Password updated successfully!")
                                            st.toast("Security encryption synchronized!")
                                        else: st.sidebar.error(f"Server Rejected Update: {auth_response.text}")
                                    except Exception as pw_err: st.sidebar.error(f"Failed to update password: {str(pw_err)}")
                if st.button("Log Out", key="sidebar_logout_btn", width='stretch'):
                    st.session_state.user = None
                    st.session_state.selected_teams = []
                    st.session_state.force_password_change = False
                    st.rerun()
        except Exception: pass

# --- UNIFIED MASTER FRAME BRAND HEADER (Theme-Adaptive Native Fix) ---
header_col1, header_col2 = st.columns([1, 5])
with header_col1:
    local_logo = "static/loser-logo.png"
    if os.path.exists(local_logo): st.image(local_logo, width='stretch')
    else: st.image("https://espncdn.com", width='stretch')
with header_col2:
    st.html(f'<div style="display: flex; align-items: flex-end; height: 85px; padding-bottom: 5px;"><h1 style="margin:0; font-weight:900; font-size:32px; letter-spacing:-1px;">2026 NFL Loser Pool &bull; {game_mode} &bull; {selected_week_label}</h1></div>')
    metric_col1, metric_col2, metric_col3 = st.columns(3)
    with metric_col1:
        st.caption("**Weeks 1-14**"); st.markdown("Pick 1 team to lose")
    with metric_col2:
        st.caption("**Weeks 15-18**"); st.markdown("Pick 2 teams to lose")
    with metric_col3:
        st.caption("**Playoffs**"); st.markdown("Pick ALL losers (repeats allowed)")
    st.info(f"**Weekly Deadline:** Noon ET Sunday, or by kickoff of earlier game")
    st.html('<div style="margin-top:10px; padding-top:8px; border-top:1px solid rgba(128,128,128,0.2); font-family:monospace; font-size:14px; color:#3b82f6; font-weight:bold;">74 Players | $1850 Purse ($1110 1st / $555 2nd / $185 3rd) <br><span style="opacity:0.7; font-weight:normal; font-size:14px; color:var(--text-color);">Last Year\'s Losers: S. King ($765) • A. Conley ($382.50) • B. Kazmierski ($127.50)</span></div>')

st.markdown("---")
if 'user' not in st.session_state: st.session_state.user = None
if 'force_password_change' not in st.session_state: st.session_state.force_password_change = False

if st.session_state.force_password_change:
    st.subheader("Update Your Temporary Password")
    new_pw = st.text_input("New Permanent Password", type="password")
    confirm_pw = st.text_input("Confirm Permanent Password", type="password")
    if st.button("Save & Update Password", width='stretch'):
        if len(new_pw.strip())  0 and not reg_profile[0].get("is_enrolled", False):
        st.error(f"**Not Enrolled.** Your profile is not currently active for **{game_mode}** this season.")
    elif isinstance(reg_profile, list) and len(reg_profile) > 0 and reg_profile[0].get("bracket_status") == "Eliminated":
        st.error(f"**Eliminated.** You have been eliminated from the {game_mode} game. Access locked, but you can view the Overview.")
    else:
        active_profile = reg_profile[0]
        player_status = active_profile["bracket_status"]
        if not active_profile.get("is_paid", False):
            st.warning("**Payment Reminder:** Entry fee is outstanding. Please send $25 to @Robert-Moore-65 on Venmo.")

        user_profile_res = supabase.table("users").select("*").eq("id", user_id).single().execute().data
        user_profile = user_profile_res if user_profile_res else {}
        username_token = user_profile.get("username", "Anonymous Player")
        
        all_regs = supabase.table("tournament_registrations").select("bracket_status").eq("game_type", game_slug).eq("is_enrolled", True).execute().data
        remaining_count = sum(1 for r in all_regs if r["bracket_status"] != "Eliminated")
        
        # --- CONTINUATION OF RECOVERED ACCOUNT STATUS BAR PASS ---
        st.markdown(
            f"""
            <div style="display: flex; justify-content: space-between; align-items: center; width: 100%; font-family: sans-serif; font-size: 14px; font-weight: 500; color: var(--text-color); opacity: 0.85;">
                <div><h4>Status for <b>{username_token}</b>: {player_status}</h4></div>
                <div style="text-align: right;"><h4>Remaining Active Players: <b>{remaining_count}</b></h4></div>
            </div>
            """,
            unsafe_allow_html=True
        )
        st.markdown("---")

        # --- RECOVER USER COMPREHENSIVE SELECTION RECORDS ---
        all_picks_res = supabase.table("user_picks").select("*").eq("user_id", user_id).eq("game_type", game_slug).execute().data
        st.write("#### Your Season Selection History")
        
        sched_rows = supabase.table("nfl_schedule").select("week", "away_team", "home_team", "winner").execute().data
        history_outcome_lookup = {}
        for match in (sched_rows or []):
            w_num = match["week"]
            away, home = match["away_team"].upper(), match["home_team"].upper()
            loser_code = match.get("winner")
            if w_num not in history_outcome_lookup: 
                history_outcome_lookup[w_num] = {}
            if loser_code:
                if loser_code == "TIE":
                    history_outcome_lookup[w_num][away] = "Incorrect"
                    history_outcome_lookup[w_num][home] = "Incorrect"
                else:
                    history_outcome_lookup[w_num][loser_code] = "Correct"
                    opposing_team = home if loser_code == away else away
                    history_outcome_lookup[w_num][opposing_team] = "Incorrect"

        if all_picks_res:
            picks_by_week_map = {p["week"]: p for p in all_picks_res}
            rail_html_cards = []
            for w in range(1, 23):
                p = picks_by_week_map.get(w, None)
                if not p:
                    card_html = f'<div style="flex: 1; min-width: 45px; border: 1px dashed rgba(148, 163, 184, 0.4); padding: 6px 2px; border-radius: 4px; text-align: center; min-height: 65px; display: flex; flex-direction: column; align-items: center; justify-content: center; opacity: 0.4; font-family: sans-serif;"><span style="font-size: 9px; color: var(--text-color); font-weight: bold; display: block;">Wk {w}</span><span style="font-size: 12px; color: var(--text-color);">&bull;</span></div>'
                else:
                    t_pick = p["team_picked"].upper()
                    p_state = p.get("pick_state", "Pending")
                    clean_team_key = t_pick.replace("_SO", "").strip()
                    if clean_team_key == "BYE": 
                        card_bg = "background-color: rgba(16, 185, 129, 0.15); border: 1px solid #10b981; color: var(--text-color);"
                    else:
                        week_results = history_outcome_lookup.get(w, {})
                        game_outcome = week_results.get(clean_team_key, "Pending")
                        if p_state == "Correct" or game_outcome == "Correct": 
                            card_bg = "background-color: rgba(16, 185, 129, 0.15); border: 1px solid #10b981; color: var(--text-color);"
                        elif p_state == "Incorrect" or game_outcome == "Incorrect": 
                            card_bg = "background-color: rgba(239, 68, 68, 0.15); border: 1px solid #ef4444; color: var(--text-color);"
                        else: 
                            card_bg = "background-color: rgba(148, 163, 184, 0.05); border: 1px solid rgba(148, 163, 184, 0.3); color: var(--text-color);"
                    
                    logo_html = ""
                    try:
                        t_clean = t_pick.replace("_SO", "").strip().upper()
                        file_name = "BYE.svg" if t_clean == "BYE" else f"{t_clean}.svg"
                        base_dir = os.path.dirname(os.path.abspath(__file__))
                        absolute_logo_path = os.path.join(base_dir, "static", file_name)
                        if os.path.exists(absolute_logo_path):
                            with open(absolute_logo_path, "rb") as f: 
                                encoded_raw_bytes = base64.b64encode(f.read()).decode("utf-8")
                            logo_html = f'<img src="data:image/svg+xml;base64,{encoded_raw_bytes}" width="24" height="15" style="object-fit:contain; vertical-align:middle; display:block; margin:0 auto;"/>'
                    except Exception: pass
                    
                    has_so_star = "🎯" if t_pick.endswith("_SO") else ""
                    card_html = f'<div style="{card_bg} flex: 1; min-width: 55px; padding: 6px 2px; border-radius: 4px; text-align: center; min-height: 65px; display: flex; flex-direction: column; align-items: center; justify-content: center; box-shadow: 0 1px 1px rgba(0,0,0,0.02); font-family: sans-serif; box-sizing: border-box;"><span style="font-size: 9px; opacity: 0.7; font-weight: bold; display: block; color: inherit; margin-bottom: 2px;">Wk {w}</span><div style="display: flex; justify-content: center; min-height: 15px; align-items: center; width: 100%; margin-bottom: 2px;">{logo_html}</div><span style="font-size: 10px; font-weight: 800; display: block; color: inherit; line-height: 1;">{clean_team_key}{has_so_star}</span></div>'
                rail_html_cards.append(card_html)
            
            st.html(f'<div style="display: flex; gap: 4px; width: 100%; overflow-x: auto; padding: 5px 0; margin-bottom: 15px;">{"".join(rail_html_cards)}</div>')
        else: 
            st.info("No prior selection records on file yet for this regular season campaign.")
        st.markdown("<br>", unsafe_allow_html=True)

        current_picks = [p for p in all_picks_res if p["week"] == SELECTED_WEEK]
        is_finalized = any(p["pick_state"] == "Finalized" for p in current_picks)
        is_confirmed = any(p["pick_state"] == "Confirmed" for p in current_picks)
        
        matchups = supabase.table("nfl_schedule").select("*").eq("week", SELECTED_WEEK).execute().data
        if "selected_teams" not in st.session_state: 
            st.session_state.selected_teams = []
        # --- BRANCH C: FORM OPEN FOR INPUT / AMENDMENT ---
        if not matchups:
            st.info("No matchups loaded for this week yet.")
        else: 
            confirmed_picks_this_week = [p["team_picked"] for p in current_picks if p["pick_state"] == "Confirmed"]
            if confirmed_picks_this_week:
                st.info(f"**Confirmed Pick:** You currently have **{', '.join(confirmed_picks_this_week)}** selected. Choices below will alter your entry.")

            finalized_picks_this_week = [p["team_picked"] for p in current_picks if p["pick_state"] == "Finalized"]
            if finalized_picks_this_week:
                st.info(f"**Finalized Pick:** You have locked in **{', '.join(finalized_picks_this_week)}**. Edits are no longer allowed.")

            used_teams = {}
            for p in all_picks_res:
                clean_pick_name = p["team_picked"].replace("_SO", "")
                if p["week"] != SELECTED_WEEK and p["week"] < 19:
                    if not p["team_picked"].endswith("_SO"): used_teams[clean_pick_name] = p["week"]
                elif p["week"] == SELECTED_WEEK and p["pick_state"] == "Finalized":
                    if not p["team_picked"].endswith("_SO"): used_teams[clean_pick_name] = p["week"]

        # 🚀 1. THE LIMIT DETECTOR: Calculate choice constraints dynamically
        current_picks_count = len(st.session_state.selected_teams)
        if SELECTED_WEEK <= 14: max_allowed_picks = 1
        elif SELECTED_WEEK <= 18: max_allowed_picks = 2
        elif SELECTED_WEEK == 19: max_allowed_picks = 6
        elif SELECTED_WEEK == 20: max_allowed_picks = 4
        elif SELECTED_WEEK == 21: max_allowed_picks = 2
        elif SELECTED_WEEK == 22: max_allowed_picks = 1
        else: max_allowed_picks = 32
        limit_reached = current_picks_count >= max_allowed_picks

        # 🚀 2. FIXED MOBILE-FIRST MATCHUP GRID & SUBMISSION CONTROLS
        main_grid_col1, main_grid_col2 = st.columns(2)
        for idx, match in enumerate(matchups):
            m_id = match["id"]
            away, home = match["away_team"].upper(), match["home_team"].upper()
            game_time_label = match.get("kickoff_display_label") or "Sunday 1:00 PM ET"
            
            is_game_locked = False
            if match.get("kickoff_time"):
                try:
                    if datetime.datetime.now() >= datetime.datetime.fromisoformat(str(match["kickoff_time"])): 
                        is_game_locked = True
                except Exception: pass

            is_sel_away = away in st.session_state.selected_teams or f"{away}_SO" in st.session_state.selected_teams
            is_sel_home = home in st.session_state.selected_teams or f"{home}_SO" in st.session_state.selected_teams
            
            with (main_grid_col1 if idx % 2 == 0 else main_grid_col2):
                with st.container(border=True):
                    c_logos, c_away_btn, c_home_btn = st.columns([2.0, 4.0, 4.0])
                    with c_logos:
                        st.html(f'<div style="display:flex; justify-content:center; align-items:center; gap:4px; height:35px; width:100%;">{get_base64_logo_html(away)}<span style="font-size:10px; color:gray; font-weight:bold;">@</span>{get_base64_logo_html(home)}</div>')
                    with c_away_btn:
                        if st.button(f"{away} (Used)" if away in used_teams else away, key=f"ma_{m_id}", disabled=is_finalized or is_game_locked or away in used_teams or (limit_reached and not is_sel_away), type="primary" if is_sel_away else "secondary", width='stretch'):
                            st.session_state.selected_teams.remove(away) if is_sel_away else st.session_state.selected_teams.append(away)
                            st.rerun()
                    with c_home_btn:
                        if st.button(f"{home} (Used)" if home in used_teams else home, key=f"mh_{m_id}", disabled=is_finalized or is_game_locked or home in used_teams or (limit_reached and not is_sel_home), type="primary" if is_sel_home else "secondary", width='stretch'):
                            st.session_state.selected_teams.remove(home) if is_sel_home else st.session_state.selected_teams.append(home)
                            st.rerun()

        # 🚀 3. SUBMISSION DIALOGUE MODAL & CONTROLS
        st.markdown("---")
        if st.button("Submit Picks Sheet", disabled=is_finalized or len(st.session_state.selected_teams) != (1 if SELECTED_WEEK <= 14 else 2 if SELECTED_WEEK <= 18 else 1), width='stretch', type="primary"):
            st.session_state.show_confirmation_modal = True

        if st.session_state.get("show_confirmation_modal", False):
            st.warning(f"Confirming choices: **{', '.join(st.session_state.selected_teams)}**")
            m_c1, m_c2, m_c3 = st.columns(3)
            with m_c1:
                if st.button("Confirm (Editable)", width='stretch'):
                    supabase.table("user_picks").delete().eq("user_id", user_id).eq("game_type", game_slug).eq("week", SELECTED_WEEK).execute()
                    for team in st.session_state.selected_teams:
                        supabase.table("user_picks").insert({"user_id": user_id, "game_type": game_slug, "week": SELECTED_WEEK, "team_picked": team, "pick_state": "Confirmed"}).execute()
                    st.session_state.show_confirmation_modal = False
                    st.rerun()
            with m_c2:
                if st.button("Finalize (Locked)", width='stretch'):
                    supabase.table("user_picks").delete().eq("user_id", user_id).eq("game_type", game_slug).eq("week", SELECTED_WEEK).execute()
                    for team in st.session_state.selected_teams:
                        supabase.table("user_picks").insert({"user_id": user_id, "game_type": game_slug, "week": SELECTED_WEEK, "team_picked": team, "pick_state": "Finalized"}).execute()
                    st.session_state.show_confirmation_modal = False
                    st.rerun()
            with m_c3:
                if st.button("Cancel Pass", width='stretch'):
                    st.session_state.show_confirmation_modal = False
                    st.rerun()

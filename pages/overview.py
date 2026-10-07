import streamlit as st
from supabase import create_client, Client
import os
import csv
import io
import uuid
import datetime
import base64
import requests

# --- SETUP MANDATORY FIRST DIRECTIVE PASS ---
st.set_page_config(layout="wide")

URL, KEY = st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"]
supabase: Client = create_client(URL, KEY)

# INITIALIZER SAFEGUARD FIX:      --------------------------------------   IS THIS NEEDED???   -------------------------------------------
# Prevents st.session_state KeyError crashes if users bookmark or deep-link directly to subpages
if "user" not in st.session_state:
    st.session_state.user = None
if "selected_teams" not in st.session_state:
    st.session_state.selected_teams = []
if "force_password_change" not in st.session_state:
    st.session_state.force_password_change = False

URL, KEY = st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"]
supabase: Client = create_client(URL, KEY)

# --- AUTOMATIC TIMELINE CALCULATOR ENGINE ---
SEASON_START_WEDNESDAY = datetime.datetime(2026, 9, 9, 0, 0, 0)
now = datetime.datetime.now()
CALCULATED_CURRENT_WEEK = 1 if now < SEASON_START_WEDNESDAY else min(22, ((now - SEASON_START_WEDNESDAY).days // 7) + 1)

def get_week_label(w_idx):
    return {19: "Wildcard", 20: "Divisional", 21: "Conference", 22: "Super Bowl"}.get(w_idx, f"Week {w_idx}")

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
        if week_num == 19: return "Wildcard"
        elif week_num == 20: return "Divisional"
        elif week_num == 21: return "Conference"
        elif week_num == 22: return "Super Bowl"
        else: return f"Week {week_num}"

    # Helper function to generate clean base64 image strings safely across Chrome/Firefox
    def get_base64_logo_html(team_code):
        try:
            # Strip out both _SO suffix strings AND whitespace before checking file paths
            t_clean = team_code.replace("_SO", "").strip().upper()
            
            # Diverts routing to look up BYE.svg asset if player utilized their bye slot option
            file_path = f"static/BYE.svg" if t_clean == "BYE" else f"static/{t_clean}.svg"
            
            if os.path.exists(file_path):
                with open(file_path, "rb") as f:
                    encoded = base64.b64encode(f.read()).decode("utf-8")
                return f'<img src="data:image/svg+xml;base64,{encoded}" width="24" height="15" style="object-fit:contain; vertical-align:middle; margin-right:4px;"/>'
        except Exception: 
            pass
        return ""

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
        
        if "Wildcard" in clean_label: NEW_WEEK = 19
        elif "Divisional" in clean_label: NEW_WEEK = 20
        elif "Conference" in clean_label: NEW_WEEK = 21
        elif "Super Bowl" in clean_label: NEW_WEEK = 22
        else: NEW_WEEK = int(clean_label.split(" ")[1])
            
        # FIX: Detect if the user changed the dropdown week. If so, wipe active session selection cache!
        if "active_week_tracker" not in st.session_state or st.session_state.active_week_tracker != NEW_WEEK:
            st.session_state.active_week_tracker = NEW_WEEK
            st.session_state.selected_teams = [] 
        
        SELECTED_WEEK = st.session_state.active_week_tracker

    st.markdown("<hr style='margin:10px 0 15px 0; border:0; border-top:1px solid rgba(255,255,255,0.3);'/>", unsafe_allow_html=True)
    
    # Basic navigation paths open to every pool player
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
        except Exception: pass
            
    # Links dynamically append only if the identity verification pass clears
    if is_logged_in_admin:
        st.page_link("pages/admin.py", label="Admin")
    
    st.markdown("<hr style='margin:10px 0 15px 0; border:0; border-top:1px solid rgba(255,255,255,0.3);'/>", unsafe_allow_html=True)
    
    # Basic navigation paths open to every pool player
    st.page_link("http://espn.com", label="ESPN NFL Schedule Grid")
    st.page_link("https://espn.com", label="ESPN Odds")
    st.page_link("https://espn.com", label="ESPN Power Index")
    
    # Self-Service Profile Management Drawer nested inside the left rail navigation
    if st.session_state.get("user"):
        try:
            user_id = st.session_state.user.id
            u_prof = supabase.table("users").select("*").eq("id", user_id).single().execute().data
            if u_prof:
                st.markdown("<hr style='margin:15px 0 10px 0; border:0; border-top:1px solid rgba(255,255,255,0.15);'/>", unsafe_allow_html=True)
                with st.expander("⚙️ Account Settings"):
                    with st.form("sidebar_profile_form"):
                        e_user = st.text_input("Username", value=u_prof.get("username") or "", key="sb_u")
                        e_first = st.text_input("First Name", value=u_prof.get("first_name") or "", key="sb_f")
                        e_last = st.text_input("Last Name", value=u_prof.get("last_name") or "", key="sb_l")
                        e_mail = st.text_input("Email", value=u_prof.get("email") or "", key="sb_e")
                        e_cell = st.text_input("Cell Phone (123-456-7890)", value=u_prof.get("cell_phone") or "", key="sb_c")
                        
                        if st.form_submit_button("Save Profile Updates", width='stretch'):
                            if not e_user.strip() or not e_mail.strip():
                                st.error("Fields cannot be left blank.")
                            else:
                                collision = False
                                if e_user.strip() != u_prof.get("username"):
                                    chk = supabase.table("users").select("id").eq("username", e_user.strip()).execute().data
                                    if chk: collision = True
                                    
                                if collision:
                                    st.error(f"Username {e_user.strip()} already claimed. Please try again.")
                                else:
                                    supabase.table("users").update({
                                        "username": e_user.strip(), "first_name": e_first.strip(),
                                        "last_name": e_last.strip(), "email": e_mail.strip(), "cell_phone": e_cell.strip()
                                    }).eq("id", user_id).execute()
                                    st.toast("Profile Saved!")
                                    st.rerun()
                    with st.form("sidebar_password_form", clear_on_submit=True):
                        sb_new_pw = st.text_input("New Secure Password:", type="password", key="sb_pwd1")
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
                                        if auth_response.status_code == 200 or auth_response.status_code == 201:
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
    with metric_col1: st.caption("**Weeks 1-14**"); st.markdown("Pick 1 team to lose")
    with metric_col2: st.caption("**Weeks 15-18**"); st.markdown("Pick 2 teams to lose")
    with metric_col3: st.caption("**Playoffs**"); st.markdown("Pick ALL losers (repeats allowed)")
    st.info(f"**Weekly Deadline:** Noon ET Sunday, or by kickoff of earlier game")
    st.html('<div style="margin-top:10px; padding-top:8px; border-top:1px solid rgba(128,128,128,0.2); font-family:monospace; font-size:14px; color:#3b82f6; font-weight:bold;">74 Players | $1850 Purse ($1110 1st / $555 2nd / $185 3rd) <br><span style="opacity:0.7; font-weight:normal; font-size:14px; color:var(--text-color);">Last Year\'s Losers: S. King ($765) • A. Conley ($382.50) • B. Kazmierski ($127.50)</span></div>')

st.markdown("---")

# Extract row references safely out of the array format
active_profile = reg_profile[0] if isinstance(reg_profile, list) else reg_profile
player_status = active_profile["bracket_status"]

# PAYMENT NOTICE: If enrolled but unpaid, render a gentle reminder banner without locking the form
if not active_profile.get("is_paid", False):
    st.warning("**Payment Reminder:** Our ledger shows your entry fee for this pool track is currently outstanding. Please settle up with the Commissioner as soon as possible by sending $25 to @Robert-Moore-65 on Venmo or rotamo@yahoo.com on PayPal.")

# Recover user info from Supabase
user_profile_res = supabase.table("users").select("*").eq("id", user_id).single().execute().data
user_profile = user_profile_res if user_profile_res else {}
username_token = user_profile.get("username", "Anonymous Player")

# Dynamic Roster Counter
all_regs = supabase.table("tournament_registrations").select("bracket_status").eq("game_type", game_slug).eq("is_enrolled", True).execute().data
remaining_count = sum(1 for r in all_regs if r["bracket_status"] != "Eliminated")

# Render the responsive Flexbox status baseline bar using the Username Code Token
st.markdown(
    f"""
    <div style="display: flex; justify-content: space-between; align-items: center; width: 100%; font-family: sans-serif; font-size: 14px; font-weight: 500; color: var(--text-color); opacity: 0.85;">
        <div>Status for <b>{username_token}</b>: {player_status}</div>
        <div style="text-align: right;">Remaining Active Players: <b>{remaining_count}</b></div>
    </div>
    """,
    unsafe_allow_html=True
)

st.markdown("---")

# ====================================================================
# 🛡️ GLOBAL ACCESSIBILITY & SECURITY PRIVACY GATES RECKONER
# ====================================================================
current_user_logged_in = st.session_state.get("user")
current_user_uid = current_user_logged_in.id if current_user_logged_in else None

# Check if the current user has finalized a team choice OR deployed a BYE option
user_has_finalized_this_week = False
if current_user_uid:
    # 🚀 THE FIX: Pull any pick for this week that is finalized (team picks and BYE entries)
    user_pick_record = supabase.table("user_picks").select("team_picked").eq("user_id", current_user_uid).eq("game_type", game_slug).eq("week", SELECTED_WEEK).eq("pick_state", "Finalized").execute().data
    if user_pick_record:
        user_has_finalized_this_week = True

# Calculate if the target week's locks have passed chronologically
is_past_week_locked = SELECTED_WEEK < CALCULATED_CURRENT_WEEK

# Absolute override criteria: Unlocked if it is an old week, or if the user already committed their choice
reveal_picks_condition = is_past_week_locked or user_has_finalized_this_week # or is_logged_in_admin

# ==========================================
# 📊 SEGMENT A: WEEKLY PICK DISTRIBUTION LIST
# ==========================================
st.write(f"### 📊 Weekly Selection Distribution — {get_week_label(SELECTED_WEEK)}")

if not reveal_picks_condition:
    st.warning("🔒 **Selection Distribution Hidden.** You must finalize your own selections for this week under the **Picks** tab before opponents' collective choices are revealed.")
else:
    all_selections = supabase.table("user_picks").select("team_picked").eq("game_type", game_slug).eq("week", SELECTED_WEEK).execute().data
    schedule_map = supabase.table("nfl_schedule").select("away_team", "home_team", "winner").eq("week", SELECTED_WEEK).execute().data

    outcome_lookup = {}
    for match in (schedule_map or []):
        away, home = match["away_team"].upper(), match["home_team"].upper()
        loser_code = match.get("winner")
        if loser_code:
            if loser_code == "TIE": outcome_lookup[away] = "Incorrect"; outcome_lookup[home] = "Incorrect"
            else:
                outcome_lookup[loser_code] = "Correct"
                opposing_team = home if loser_code == away else away
                outcome_lookup[opposing_team] = "Incorrect"

    if not all_selections: st.info(f"No selection records have been finalized yet for {get_week_label(SELECTED_WEEK)}.")
    else:
        counts = {}
        for s in all_selections:
            t = s["team_picked"].upper()
            counts[t] = counts.get(t, 0) + 1
            
        sorted_distribution = sorted(
            counts.items(), 
            key=lambda item: (0, 0, "") if item[0] == "BYE" else (1, -item[1], item[0])
        )
        dist_cols = st.columns(min(len(sorted_distribution), 10))
        for idx, (team, count) in enumerate(sorted_distribution):
            with dist_cols[idx % 10]:
                so_label = " 🎯" if team.endswith("_SO") else ""
                clean_team_key = team.replace("_SO", "").strip()
                if clean_team_key == "BYE": card_style = "background-color: rgba(16, 185, 129, 0.15); border: 1px solid #10b981; color: var(--text-color);"
                else:
                    game_state = outcome_lookup.get(clean_team_key, "Pending")
                    if game_state == "Correct": card_style = "background-color: rgba(16, 185, 129, 0.15); border: 1px solid #10b981; color: var(--text-color);"
                    elif game_state == "Incorrect": card_style = "background-color: rgba(239, 68, 68, 0.15); border: 1px solid #ef4444; color: var(--text-color);"
                    else: card_style = "background-color: transparent; border: 1px solid rgba(148, 163, 184, 0.3); color: var(--text-color);"
                st.markdown(f"""<div style="{card_style} padding:8px 4px; border-radius:6px; text-align:center; box-shadow: 0 1px 2px rgba(0,0,0,0.05); margin-bottom:10px; font-family:sans-serif;"><div style="display:flex; justify-content:center; margin-bottom:4px;">{get_base64_logo_html(team)}</div><b style="font-size:13px; color: inherit;">{team.replace('_SO','')}{so_label}</b><span style="display:block; font-size:18px; font-weight:900; color:#2563eb; margin-top:2px;">{count}</span><span style="font-size:10px; color: gray; opacity: 0.8; display:block;">Picks</span></div>""", unsafe_allow_html=True)

st.markdown("---")

# ==========================================
# 🏆 SEGMENT B: COMPLETE LEAGUE STANDINGS MATRIX
# ==========================================
st.write("### 🏆 Live Championship Standings Grid")

users_list = supabase.table("users").select("id", "username").order("username").execute().data
registrations = supabase.table("tournament_registrations").select("*").eq("game_type", game_slug).eq("is_enrolled", True).execute().data
all_historical_picks = supabase.table("user_picks").select("*").eq("game_type", game_slug).execute().data

if not registrations:
    st.info("No active enrolled competitor rows verified on record for this game tournament track.")
else:
    user_map = {u["id"]: u["username"] for u in users_list}
    picks_by_user = {}
    for p in all_historical_picks:
        picks_by_user.setdefault(p["user_id"], {})[p["week"]] = p
        
    # 🚀 EXTRA OPTIMIZATION FIX: Gather ALL of the current user's finalized choices in a local cache array.
    # This completely eliminates 1,500+ repeating database queries!
    current_user_finalized_weeks = set()
    if current_user_uid:
        for p in all_historical_picks:
            if p["user_id"] == current_user_uid and p.get("pick_state") == "Finalized":
                current_user_finalized_weeks.add(p["week"])

    loser_bracket_players, winner_bracket_players, eliminated_players = [], [], []
    for reg in registrations:
        status = reg.get("bracket_status", "Eliminated")
        if status == "Loser Bracket": loser_bracket_players.append(reg)
        elif status == "Winner Bracket": winner_bracket_players.append(reg)
        else: eliminated_players.append(reg)
            
    loser_bracket_players.sort(key=lambda r: user_map.get(r["user_id"], "").lower())
    winner_bracket_players.sort(key=lambda r: user_map.get(r["user_id"], "").lower())
    eliminated_players.sort(key=lambda r: user_map.get(r["user_id"], "").lower())
    
    visible_weeks = list(range(1, CALCULATED_CURRENT_WEEK + 1))
    
    def render_bracket_table(bracket_title, players_group):
        if not players_group:
            st.caption(f"*No players currently active inside {bracket_title}*")
            return
            
        players_group_count = len(players_group)
        st.markdown(f"#### 🏅 {bracket_title}: {players_group_count} Players")
        header_row = "| Player | " + " | ".join(f"Wk {w}" for w in visible_weeks) + " |"
        divider_row = "| :--- | " + " | ".join(" :---: " for _ in visible_weeks) + " |"
        table_markdown_lines = [header_row, divider_row]
        
        for reg in players_group:
            u_id = reg["user_id"]
            uname = user_map.get(u_id, "Anonymous")
            user_weeks_map = picks_by_user.get(u_id, {})
            row_cells = [f"**{uname}**"]
            
            for w_num in visible_weeks:
                p_data = user_weeks_map.get(w_num, None)
                if not p_data: 
                    row_cells.append("&bull;")
                else:
                    t_pick = p_data["team_picked"].upper()
                    p_state = p_data.get("pick_state", "Pending")
                    
                    is_current_loop_week_locked = w_num < CALCULATED_CURRENT_WEEK
                    
                    # 🚀 READ FROM LOCAL CACHE: Lightning-fast check with zero network overhead
                    user_has_finalized_for_loop_week = w_num in current_user_finalized_weeks
                    
                    is_own_profile_row = (u_id == current_user_uid)
                    reveal_tile_cell = is_current_loop_week_locked or user_has_finalized_for_loop_week or is_own_profile_row # or is_logged_in_admin
                    
                    if not reveal_tile_cell: 
                        cell_content = '<div style="background-color: rgba(148, 163, 184, 0.15); padding: 4px 6px; border-radius: 4px; font-weight:600; font-size:10px; color:gray; white-space:nowrap;">🔒 Hidden</div>'
                    else:
                        logo_html = get_base64_logo_html(t_pick)
                        clean_team_display = t_pick.replace('_SO', '')
                        if t_pick.endswith("_SO"): 
                            clean_team_display += "🎯"
                            
                        if p_state == "Correct" or t_pick == "BYE": 
                            bg_style = "background-color: rgba(16, 185, 129, 0.15); padding: 4px 6px; border-radius: 4px; display: inline-flex; align-items: center; gap: 2px;"
                        elif p_state == "Incorrect": 
                            bg_style = "background-color: rgba(239, 68, 68, 0.15); padding: 4px 6px; border-radius: 4px; display: inline-flex; align-items: center; gap: 2px;"
                        else: 
                            bg_style = "display: inline-flex; align-items: center; gap: 2px; color: var(--text-color);"
                            
                        cell_content = f'<div style="{bg_style}">{logo_html}<span style="font-weight:600; font-size:11px;">{clean_team_display}</span></div>'
                    row_cells.append(cell_content)
            table_markdown_lines.append("| " + " | ".join(row_cells) + " |")
        st.markdown("\n".join(table_markdown_lines), unsafe_allow_html=True)
        st.markdown("<br>", unsafe_allow_html=True)

    render_bracket_table("Loser Bracket", loser_bracket_players)
    render_bracket_table("Winner Bracket", winner_bracket_players)
    render_bracket_table("Eliminated", eliminated_players)


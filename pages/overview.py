import streamlit as st
from supabase import create_client, Client
import datetime
import base64
import os

# --- ST.SET_PAGE_CONFIG MUST BE THE ABSOLUTE FIRST DIRECTIVE ---
st.set_page_config(layout="wide")

# --- DATABASE SETUP ---
URL = st.secrets["SUPABASE_URL"]
KEY = st.secrets["SUPABASE_KEY"]
supabase: Client = create_client(URL, KEY)

# --- AUTOMATIC SEASON TIMELINE RECKONER ---
SEASON_START_WEDNESDAY = datetime.datetime(2026, 9, 9, 0, 0, 0)
now = datetime.datetime.now()

if now < SEASON_START_WEDNESDAY:
    CALCULATED_CURRENT_WEEK = 1
else:
    elapsed_days = (now - SEASON_START_WEDNESDAY).days
    CALCULATED_CURRENT_WEEK = min(22, (elapsed_days // 7) + 1)

def get_week_label(week_num):
    if week_num == 19: return "Wildcard"
    elif week_num == 20: return "Divisional"
    elif week_num == 21: return "Conference"
    elif week_num == 22: return "Super Bowl"
    else: return f"Week {week_num}"

# --- CUSTOM SIDEBAR CONFIGURATION ---
with st.sidebar:
    local_sidebar_logo = "static/loser-logo.png"
    if os.path.exists(local_sidebar_logo):
        st.image(local_sidebar_logo, width='stretch')
    else:
        st.image("https://espncdn.com", width='stretch')
        
    st.markdown("<hr style='margin:10px 0 15px 0; border:0; border-top:1px solid #cbd5e1;'/>", unsafe_allow_html=True)
    
    game_mode = st.selectbox("Select Pool Tournament", ["Main Pool", "2nd Chance Game"])
    game_slug = "Main" if game_mode == "Main Pool" else "2nd_Chance"
    
    week_options = []
    for w in range(1, 23):
        base_label = get_week_label(w)
        if w == CALCULATED_CURRENT_WEEK: week_options.append(f"{base_label} (current)")
        else: week_options.append(base_label)
            
    selected_week_label = st.selectbox("📆 Select Target Pool Week", options=week_options, index=CALCULATED_CURRENT_WEEK - 1)
    clean_label = selected_week_label.replace(" (current)", "")
    
    if "Wildcard" in clean_label: SELECTED_WEEK = 19
    elif "Divisional" in clean_label: SELECTED_WEEK = 20
    elif "Conference" in clean_label: SELECTED_WEEK = 21
    elif "Super Bowl" in clean_label: SELECTED_WEEK = 22
    else: SELECTED_WEEK = int(clean_label.split(" "))
    
    st.markdown("<br>### 🗂️ Tournament Menu", unsafe_allow_html=True)
    st.page_link("app.py", label="Picks", icon="🔐")
    st.page_link("pages/overview.py", label="Results", icon="📈")
    st.page_link("pages/chat.py", label="Smack", icon="🗣️")
    st.page_link("pages/rules.py", label="Rules", icon="📝")
    
    is_logged_in_admin = False
    if st.session_state.get("user"):
        try:
            admin_check = supabase.table("users").select("is_admin").eq("id", st.session_state.user.id).single().execute().data
            if admin_check and admin_check.get("is_admin", False): is_logged_in_admin = True
        except Exception: pass
            
    if is_logged_in_admin:
        st.page_link("pages/admin.py", label="Admin", icon="🛠️")
        st.page_link("pages/seed_data.py", label="Seed Data", icon="🌱")

    st.markdown("<hr style='margin:15px 0 10px 0; border:0; border-top:1px solid rgba(255,255,255,0.15);'/>", unsafe_allow_html=True)
    st.markdown("<h3 style='margin:0 0 5px 0; font-size:12px; opacity:0.7;'>🔗 League Resources</h3>", unsafe_allow_html=True)
    st.markdown("<a href='https://espn.com' target='_blank' style='color:#60a5fa; text-decoration:none; font-size:13px; font-weight:bold;'>🏈 Live ESPN Vegas Odds Lines</a>", unsafe_allow_html=True)

    # --- SELF-SERVICE PROFILE SETTINGS EXTENSION ---
    if st.session_state.get("user"):
        try:
            user_id = st.session_state.user.id
            u_prof = supabase.table("users").select("*").eq("id", user_id).single().execute().data
            if u_prof:
                st.markdown("<hr style='margin:15px 0 10px 0; border:0; border-top:1px solid rgba(255,255,255,0.15);'/>", unsafe_allow_html=True)
                with st.expander("⚙️ Profile & Contact Settings"):
                    with st.form("sidebar_profile_form"):
                        e_first = st.text_input("First Name", value=u_prof.get("first_name") or "", key="sb_f")
                        e_last = st.text_input("Last Name", value=u_prof.get("last_name") or "", key="sb_l")
                        e_user = st.text_input("Username Token ID", value=u_prof.get("username") or "", key="sb_u")
                        e_mail = st.text_input("Email Address", value=u_prof.get("email") or "", key="sb_e")
                        e_cell = st.text_input("Cell Phone Number", value=u_prof.get("cell_phone") or "", key="sb_c")
                        
                        if st.form_submit_button("Save Contact Details 🚀", width='stretch'):
                            supabase.table("users").update({"username": e_user.strip(), "first_name": e_first.strip(), "last_name": e_last.strip(), "email": e_mail.strip(), "cell_phone": e_cell.strip()}).eq("id", user_id).execute()
                            st.toast("Profile Saved!")
                            st.rerun()

                with st.expander("🔒 Change Account Password"):
                    with st.form("sidebar_password_form", clear_on_submit=True):
                        sb_new_pw = st.text_input("New Secure Password:", type="password", key="sb_pwd1")
                        sb_conf_pw = st.text_input("Confirm New Password:", type="password", key="sb_pwd2")
                        
                        if st.form_submit_button("Commit Password Change 🔐", width='stretch'):
                            clean_sb_pw = sb_new_pw.strip()
                            if len(clean_sb_pw) < 6: st.sidebar.error("❌ Password must be at least 6 characters long.")
                            elif clean_sb_pw != sb_conf_pw.strip(): st.sidebar.error("❌ Passwords do not match.")
                            else:
                                auth_endpoint = f"{URL}/auth/v1/admin/users/{user_id}"
                                auth_headers = {"Authorization": f"Bearer {KEY}", "apikey": KEY, "Content-Type": "application/json"}
                                auth_payload = {"password": clean_sb_pw}
                                import requests
                                auth_response = requests.put(auth_endpoint, json=auth_payload, headers=auth_headers)
                                if auth_response.status_code in:
                                    st.sidebar.success("🎉 Password updated successfully!")
                                    st.toast("Security synchronized!")
                                else: st.sidebar.error(f"❌ Error: {auth_response.text}")
        except Exception: pass

    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("🚪 Log Out / Clear Session", key="sidebar_logout_btn", width='stretch'):
        st.session_state.user = None
        st.session_state.selected_teams = []
        st.session_state.force_password_change = False
        st.rerun()

# Dynamic left rail color mapping injection
sidebar_bg = "#1d3d70" if game_slug == "Main" else "#974706"
st.markdown(f"<style>[data-testid='stSidebar'] {{ background-color: {sidebar_bg} !important; }} [data-testid='stSidebar'] .stText, [data-testid='stSidebar'] p, [data-testid='stSidebar'] h3, [data-testid='stSidebar'] label {{ color: #ffffff !important; }} [data-testid='stSidebar'] div[data-baseweb='select'] div {{ color: #1e293b !important; }}</style>", unsafe_allow_html=True)

# --- UNIFIED BRAND TITLE FRAME BANNER ---
header_col1, header_col2 = st.columns()
with header_col1:
    if os.path.exists("static/loser-logo.png"): st.image("static/loser-logo.png", width='stretch')
with header_col2:
    st.html(f"<div style='display: flex; align-items: flex-end; height: 100px; padding-bottom: 5px;'><h1 style='margin:0; font-weight:900; font-size:32px; letter-spacing:-1px;'>2026 NFL Loser Pool &bull; {game_mode} &bull; Standings Dashboard</h1></div>")

st.markdown("---")

# Helper function to generate clean base64 image strings safely across Chrome/Firefox
def get_base64_logo_html(team_code):
    try:
        t_clean = team_code.replace("_SO", "").strip().upper()
        # 🚀 FIX B: Look up local BYE.svg asset if player utilized their bye slot option
        file_path = f"static/BYE.svg" if t_clean == "BYE" else f"static/{t_clean}.svg"
        
        if os.path.exists(file_path):
            with open(file_path, "rb") as f:
                encoded = base64.b64encode(f.read()).decode("utf-8")
            return f'<img src="data:image/svg+xml;base64,{encoded}" width="24" height="15" style="object-fit:contain; vertical-align:middle; margin-right:4px;"/>'
    except Exception: pass
    return ""

# ==========================================
# 📊 SEGMENT A: WEEKLY PICK DISTRIBUTION LIST
# ==========================================
st.write(f"### 📊 Weekly Selection Distribution — {get_week_label(SELECTED_WEEK)}")

# Fetch all active locked picks for this targeted timeline segment
all_selections = supabase.table("user_picks").select("team_picked").eq("game_type", game_slug).eq("week", SELECTED_WEEK).execute().data

if not all_selections:
    st.info(f"No selection records have been finalized or committed yet for {get_week_label(SELECTED_WEEK)}.")
else:
    # Tally selection frequencies
    counts = {}
    for s in all_selections:
        t = s["team_picked"].upper()
        counts[t] = counts.get(t, 0) + 1
        
    # 🚀 FIX C: ADVANCED CUSTOM ORDER SORTING ENGINE
    # Forces 'BYE' to always sit at rank index 1, followed by highest count desc, then name asc
    def sorting_weight_key(item):
        team_name, selection_count = item
        if team_name == "BYE":
            return (0, 0, "")
        else:
            return (1, -selection_count, team_name)
            
    sorted_distribution = sorted(counts.items(), key=sorting_weight_key)
    
    # Render compact visual grid distribution deck mapping wide rules columns layout
    dist_cols = st.columns(min(len(sorted_distribution), 10))
    for idx, (team, count) in enumerate(sorted_distribution):
        with dist_cols[idx % 10]:
            so_label = " ✴️" if team.endswith("_SO") else ""
            st.markdown(
                f"""
                <div style="border:1px solid #cbd5e1; padding:8px 4px; border-radius:6px; text-align:center; background:var(--background-color, white); box-shadow: 0 1px 2px rgba(0,0,0,0.05); margin-bottom:10px;">
                    <div style="display:flex; justify-content:center; margin-bottom:4px;">{get_base64_logo_html(team)}</div>
                    <b style="font-size:13px; color:var(--text-color);">{team.replace('_SO','')}{so_label}</b>
                    <span style="display:block; font-size:18px; font-weight:900; color:#2563eb; margin-top:2px;">{count}</span>
                    <span style="font-size:10px; color:gray; display:block;">Picks</span>
                </div>
                """, 
                unsafe_allow_html=True
            )

st.markdown("---")

# ==========================================
# 🏆 SEGMENT B: COMPLETE LEAGUE STANDINGS MATRIX
# ==========================================
st.write("### 🏆 Live Championship Standings Grid")

# 🚀 FIX A: Replaced old CSS grid blocks with native Streamlit wide column blocks to guarantee Chrome rendering compliance
users_list = supabase.table("users").select("id", "username").order("username").execute().data
registrations = supabase.table("tournament_registrations").select("*").eq("game_type", game_slug).eq("is_enrolled", True).execute().data
all_historical_picks = supabase.table("user_picks").select("*").eq("game_type", game_slug).execute().data

if not registrations:
    st.info("No active enrolled competitor rows verified on record for this game tournament track.")
else:
    # Group logs by user accounts keys
    user_map = {u["id"]: u["username"] for u in users_list}
    picks_by_user = {}
    for p in all_historical_picks:
        picks_by_user.setdefault(p["user_id"], {})[p["week"]] = p
        
    # Sort league participants cleanly by their bracket rankings (Loser > Winner > Eliminated)
    def bracket_rank_weight(r):
        b = r.get("bracket_status", "Eliminated")
        return 0 if b == "Loser Bracket" else 1 if b == "Winner Bracket" else 2
        
    sorted_regs = sorted(registrations, key=bracket_rank_weight)
    
    # Establish complete seasonal grid columns header mapping arrays
    # Maps up to the calculated week index to prevent columns from spilling empty nodes forward
    visible_weeks_range = range(1, CALCULATED_CURRENT_WEEK + 1)
    
    for p_reg in sorted_regs:
        u_id = p_reg["user_id"]
        uname = user_map.get(u_id, "Anonymous")
        b_status = p_reg["bracket_status"]
        
        # Color coding assignment strings matching bracket weights
        if b_status == "Loser Bracket": b_color = "#10b981"
        elif b_status == "Winner Bracket": b_color = "#f59e0b"
        else: b_color = "#ef4444"
            
        with st.container(border=True):
            # Split profile and seasonal cells cleanly inside an elastic wide grid layer
            col_profile, col_weeks_strip = st.columns([2.5, 9.5])
            
            with col_profile:
                st.markdown(
                    f"""
                    <div style="padding-top:4px; font-family:sans-serif;">
                        <b style="font-size:15px; color:var(--text-color);">{uname}</b><br>
                        <span style="display:inline-block; padding:2px 6px; font-size:11px; font-weight:bold; color:white; background:{b_color}; border-radius:4px; margin-top:4px;">{b_status}</span>
                    </div>
                    """, 
                    unsafe_allow_html=True
                )
                
            with col_weeks_strip:
                user_weeks_map = picks_by_user.get(u_id, {})
                num_strip_cols = max(len(visible_weeks_range), 1)
                strip_columns = st.columns(num_strip_cols)
                
                for idx, w_num in enumerate(visible_weeks_range):
                    with strip_columns[idx % num_strip_cols]:
                        p_data = user_weeks_map.get(w_num, None)
                        
                        if not p_data:
                            st.markdown("<center style='color:#cbd5e1; font-size:12px; padding-top:10px;'>&bull;</center>", unsafe_allow_html=True)
                        else:
                            t_pick = p_data["team_picked"].upper()
                            p_state = p_data.get("pick_state", "Pending")
                            
                            # Add subtle card outlines indicating win/loss results
                            state_border = "2px solid #10b981" if p_state == "Correct" else "2px solid #ef4444" if p_state == "Incorrect" else "1px dashed #cbd5e1"
                            has_so_star = "*" if t_pick.endswith("_SO") else ""
                            
                            st.markdown(
                                f"""
                                <div style="border:{state_border}; padding:4px 2px; border-radius:4px; text-align:center; background:#ffffff; font-size:11px; box-shadow:0 1px 1px rgba(0,0,0,0.02);">
                                    <span style="font-size:9px; color:gray; font-weight:bold; display:block; margin-bottom:2px;">Wk {w_num}</span>
                                    <div style="display:flex; flex-direction:column; align-items:center; justify-content:center; gap:1px;">
                                        {get_base64_logo_html(t_pick)}
                                        <b style="color:#1e293b; font-size:10px; font-weight:700;">{t_pick.replace('_SO','')}{has_so_star}</b>
                                    </div>
                                </div>
                                """, 
                                unsafe_allow_html=True
                            )

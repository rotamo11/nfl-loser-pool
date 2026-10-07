import streamlit as st
from supabase import create_client, Client
import os
import csv
import io
import uuid
import datetime
import base64

# --- SETUP MANDATORY FIRST DIRECTIVE PASS ---
st.set_page_config(layout="wide")
URL, KEY = st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"]
supabase: Client = create_client(URL, KEY)

# INITIALIZER SAFEGUARD FIX:
# Prevents st.session_state KeyError crashes if users bookmark or deep-link directly to subpages
if "user" not in st.session_state:
    st.session_state.user = None
if "selected_teams" not in st.session_state:
    st.session_state.selected_teams = []
if "force_password_change" not in st.session_state:
    st.session_state.force_password_change = False

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
        
        if "Wildcard" in clean_label:
            NEW_WEEK = 19
        elif "Divisional" in clean_label:
            NEW_WEEK = 20
        elif "Conference" in clean_label:
            NEW_WEEK = 21
        elif "Super Bowl" in clean_label:
            NEW_WEEK = 22
        else:
            # Extract the trailing integer for regular season weeks (e.g., "Week 2" -> 2)
            NEW_WEEK = int(clean_label.split(" ")[1])
        # FIX: Detect if the user changed the dropdown week. If so, wipe active session selection cache!
        if "active_week_tracker" not in st.session_state or st.session_state.active_week_tracker != NEW_WEEK:
            st.session_state.active_week_tracker = NEW_WEEK
            st.session_state.selected_teams = [] # Clears workspace parameters for fresh week view mapping
        
        SELECTED_WEEK = st.session_state.active_week_tracker

    st.markdown("<hr style='margin:10px 0 15px 0; border:0; border-top:1px solid rgba(255,255,255,0.3);'/>", unsafe_allow_html=True)
    
    # Basic navigation paths open to every pool player
    st.page_link("app.py", label="Picks")
    st.page_link("pages/overview.py", label="Overview")
    st.page_link("pages/chat.py", label="Chat")
    st.page_link("pages/rules.py", label="Rules")

    # ROLE GATE: Check if the logged-in session belongs to a valid administrator
    is_logged_in_admin = True
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
        # st.page_link("pages/seed_data.py", label="Seed Data")
    
    st.markdown("<hr style='margin:10px 0 15px 0; border:0; border-top:1px solid rgba(255,255,255,0.3);'/>", unsafe_allow_html=True)
    
    # Basic navigation paths open to every pool player
    st.page_link("http://www.espn.com/nfl/schedulegrid", label="ESPN NFL Schedule Grid")
    st.page_link("https://www.espn.com/nfl/odds", label="ESPN Odds")
    st.page_link("https://www.espn.com/nfl/fpi", label="ESPN Power Index")
    
    # Self-Service Profile Management Drawer nested inside the left rail navigation
    if st.session_state.get("user"):
        try:
            # Safely fetch active session profile details
            current_user = st.session_state.get("user")
            user_id = current_user.id if current_user else None
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
                                # Pre-empt duplicate token crashes
                                collision = False
                                if e_user.strip() != u_prof.get("username"):
                                    chk = supabase.table("users").select("id").eq("username", e_user.strip()).execute().data
                                    if chk: collision = True
                                    
                                if collision:
                                    st.error("Username {e_user.strip()} already claimed. Please try again.")
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
                            if len(clean_sb_pw) < 6:
                                st.sidebar.error("Password must be at least 6 characters long.")
                            elif clean_sb_pw != sb_conf_pw.strip():
                                        st.sidebar.error("Passwords do not match.")
                            else:
                                with st.spinner("Updating encryption vaults..."):
                                    try:
                                        # SECURE REST ENFORCER: Bypasses browser cache token lookups entirely
                                        # This forces the change through using your master administrative service role key!
                                        auth_endpoint = f"{URL}/auth/v1/admin/users/{user_id}"
                                        auth_headers = {
                                            "Authorization": f"Bearer {KEY}",
                                            "apikey": KEY,
                                            "Content-Type": "application/json"
                                        }
                                        auth_payload = {"password": clean_sb_pw}
                                        
                                        import requests
                                        auth_response = requests.put(auth_endpoint, json=auth_payload, headers=auth_headers)
                                        
                                        if auth_response.status_code in [200, 201]:
                                            st.sidebar.success("Password updated successfully!")
                                            st.toast("Security encryption synchronized!")
                                        else:
                                            st.sidebar.error(f"Server Rejected Update: {auth_response.text}")
                                    except Exception as pw_err:
                                        st.sidebar.error(f"Failed to update password: {str(pw_err)}")
                # Logout button appears only when logged in
                if st.button("Log Out", key="sidebar_logout_btn", width='stretch'):
                    st.session_state.user = None
                    st.session_state.selected_teams = []
                    st.session_state.force_password_change = False
                    st.rerun()
        except Exception:
            pass

# --- UNIFIED MASTER FRAME BRAND HEADER (Theme-Adaptive Native Fix) ---
header_col1, header_col2 = st.columns([1, 5])

with header_col1:
    local_logo = "static/loser-logo.png"
    if os.path.exists(local_logo):
        st.image(local_logo, width='stretch')
    else:
        st.image("https://espncdn.com", width='stretch')

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

# THE FIXED VERSION: Extracts the ID safely only if a user is logged in
current_user = st.session_state.get("user")
user_id = current_user.id if current_user else None

# ====================================================================
# THE FIX: GATED ENROLLMENT LOOKUP PASS (Guest Fallback Resilient)
# ====================================================================
reg_profile = None

# Only query tournament registrations if we have a valid, logged-in user session ID
if user_id:
    try:
        reg_profile = supabase.table("tournament_registrations").select("*").eq("user_id", user_id).eq("game_type", game_slug).execute().data
    except Exception:
        reg_profile = None

# --- EVALUATE ACCESS RULES ---
if user_id and not reg_profile:
    st.error(f"**Access Locked.** You are not registered for the {game_mode} game.")
    st.info("Please contact the League Commissioner to initialize your account profile: nfl.loser.pool@gmail.com")
    st.stop()

elif user_id and isinstance(reg_profile, list) and len(reg_profile) > 0 and not reg_profile[0].get("is_enrolled", False):
    st.error(f"**Not Enrolled.** Your profile is not currently enrolled in the **{game_mode}** game for this season.")
    st.info("*Note: If you have already paid or submitted entry data to the Commissioner, access will open automatically once your enrollment status is enabled.*")
    st.stop()
    
elif user_id and isinstance(reg_profile, list) and len(reg_profile) > 0 and reg_profile[0].get("bracket_status") == "Eliminated":
    # Optional notification flag, but do not stop execution since eliminated players can still view standings!
    st.toast("Viewing scoreboard as an eliminated participant.")

# Safe extraction of individual player status metadata
if user_id and reg_profile and len(reg_profile) > 0:
    active_profile = reg_profile[0]
    player_status = active_profile.get("bracket_status", "Active")
    is_paid_status = active_profile.get("is_paid", False)
else:
    player_status = "Public Viewer"
    is_paid_status = True

# PAYMENT REMINDER: Only fire if a logged-in user is genuinely unpaid
if user_id and not is_paid_status:
    st.warning("**Payment Reminder:** Our ledger shows your entry fee for this pool track is currently outstanding. Please settle up with the Commissioner as soon as possible by sending $25 to @Robert-Moore-65 on Venmo.")

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
        <div style="display: flex; justify-content: space-between; align-items: center; width: 100%; font-family: sans-serif; font-size: 14px; font-weight: 500; color:#3b82f6;">
            <div>Status for <b>{username_token}</b>: {player_status}</div>
            <div style="text-align: right;">Remaining Active Players: <b>{remaining_count}</b></div>
        </div>
        """,
        unsafe_allow_html=True
    )

    st.markdown("---")

st.subheader("Locker Room Chat")

if 'user' not in st.session_state or not st.session_state.user:
    st.warning("You must be logged into the main page to access the live chat room.")
else:
    user_id = st.session_state.user.id
    
    # 1. Fetch current player profile to anchor their username
    user_profile = supabase.table("users").select("username").eq("id", user_id).single().execute().data
    username = user_profile.get("username", "Anonymous Player") if user_profile else "Anonymous Player"

    # 2. Render Message Submission Input Box
    with st.form("chat_form", clear_on_submit=True):
        user_message = st.text_input("Spit some banter or talk trash:", placeholder="Your message...")
        submit_msg = st.form_submit_button("Send Message", width='stretch')
        
        if submit_msg and user_message.strip():
            # Ingest message record directly into live database
            supabase.table("pool_chat").insert({
                "user_id": user_id,
                "username": username,
                "message": user_message.strip()
            }).execute()
            st.toast("Message broadcasted!")
            st.rerun()

    st.markdown("---")

    # 3. Pull and display the historical scroll of chat entries
    chat_logs = supabase.table("pool_chat").select("*").order("created_at", desc=True).limit(50).execute().data

    if chat_logs:
        for msg in chat_logs:
            # Format time stamp visuals
            raw_time = msg["created_at"][:16].replace("T", " ")
            st.markdown(
                f"""
                <div style="background:white; padding:10px; border-radius:6px; border-left:4px solid #000080; margin-bottom:8px; box-shadow: 0 1px 2px rgba(0,0,0,0.05);">
                    <span style="font-weight:black; color:#1e3a8a;">{msg['username']}</span> 
                    <span style="font-size:10px; color:gray; float:right;">{raw_time}</span>
                    <p style="margin:5px 0 0 0; font-size:13px; color:#334155;">{msg['message']}</p>
                </div>
                """, 
                unsafe_allow_html=True
            )
    else:
        st.info("Hey there, you loser!  Tell us why you're no winner!")

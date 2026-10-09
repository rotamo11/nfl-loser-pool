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
                color: #999999 !important;
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
            # THE FIXED VERSION: Extracts the ID safely only if a user is logged in
            current_user = st.session_state.get("user")
            user_id = current_user.id if current_user else None
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
                        
                        # 1. NEW CELL CARRIER CARRIER GATEWAY SELECTOR
                        # Tracks the exact telecom provider network strings needed for free text routing
                        carrier_options = ["Select Provider", "Verizon", "AT&T", "T-Mobile", "Sprint"]
                        current_db_carrier = u_prof.get("cell_carrier") or "Select Provider"
                        
                        try: default_carrier_idx = carrier_options.index(current_db_carrier)
                        except ValueError: default_carrier_idx = 0
                            
                        e_carrier = st.selectbox("Cellular Network Provider (For Free SMS Alerts):", options=carrier_options, index=default_carrier_idx, key="sb_carrier_select")
                        
                        # 2. DYNAMIC ALERTS TIERS SETROWS
                        pref_email = u_prof.get("alert_email", True) if u_prof.get("alert_email") is not None else True
                        pref_sms = u_prof.get("alert_sms", False)
                        
                        st.markdown("<p style='font-size:12px; margin-bottom:2px; font-weight:bold;'>Receive Missing Pick Alerts Via:</p>", unsafe_allow_html=True)
                        c_chk_em, c_chk_sms = st.columns(2)
                        with c_chk_em: opt_email = st.checkbox("Email", value=pref_email, key="sb_alert_em")
                        with c_chk_sms: opt_sms = st.checkbox("SMS Text", value=pref_sms, key="sb_alert_sms")
                        
                        if st.form_submit_button("Save Profile Updates", width='stretch'):
                            if not e_user.strip() or not e_mail.strip():
                                st.error("Required fields cannot be left blank.")
                            elif opt_sms and e_carrier == "Select Provider":
                                st.error("**Action Required:** You must select a Cellular Network Provider to enable free SMS text alerts.")
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

# --- USER SELECTION AUTHENTICATION & OVERRIDES GATES ---
if 'user' not in st.session_state:
    st.session_state.user = None
if 'force_password_change' not in st.session_state:
    st.session_state.force_password_change = False

if st.session_state.force_password_change:
    st.subheader("Update Your Temporary Password")
    new_pw = st.text_input("New Permanent Password", type="password")
    confirm_pw = st.text_input("Confirm Permanent Password", type="password")
    
    if st.button("Save & Update Password", width='stretch'):
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
    # THREE-WAY DISCOVERY ROUTING SYSTEM MATRIX
    if "auth_mode" not in st.session_state:
        st.session_state.auth_mode = "Login"
        
    c_log, c_jn, c_rst = st.columns(3)
    with c_log:
        if st.button("Account Login", width='stretch', type="primary" if st.session_state.auth_mode == "Login" else "secondary"):
            st.session_state.auth_mode = "Login"
            st.rerun()
    with c_jn:
        if st.button("Join a Pool", width='stretch', type="primary" if st.session_state.auth_mode == "Join" else "secondary"):
            st.session_state.auth_mode = "Join"
            st.rerun()
    with c_rst:
        if st.button("Reset Password", width='stretch', type="primary" if st.session_state.auth_mode == "Reset" else "secondary"):
            st.session_state.auth_mode = "Reset"
            st.rerun()

    # st.markdown("<br>", unsafe_allow_html=True)

    # ==========================================
    # CHANNEL 1: STANDARD ACCOUNT LOGIN PORTAL
    # ==========================================
    if st.session_state.auth_mode == "Login":
        st.subheader("Player Login")
        url_params = st.query_params
        #dev_pass_unlocked = url_params.get("dev", "").lower() == "true"
        
        testing_mode = False
        #if dev_pass_unlocked:
        testing_mode = st.checkbox("Enable Developer Masquerade Mode")
        
        if testing_mode: # and dev_pass_unlocked:
            try:
                users_list = supabase.table("users").select("id", "username").execute().data
                if users_list:
                    user_options = {u["username"]: u["id"] for u in users_list}
                    selected_user_name = st.selectbox("Masquerade as Player:", list(user_options.keys()))
                    if st.button("Masquerade Login", width='stretch'):
                        class MockUser:
                            def __init__(self, uid): self.id = uid
                        st.session_state.user = MockUser(user_options[selected_user_name])
                        st.session_state.force_password_change = False
                        st.session_state.selected_teams = []
                        st.success(f"Masquerading as {selected_user_name}!")
                        st.rerun()
            except Exception as e: st.error(f"Error: {str(e)}")
        else:
            email = st.text_input("Email Address")
            password = st.text_input("Password", type="password")
            if st.button("Log In", width='stretch'):
                try:
                    res = supabase.auth.sign_in_with_password({"email": email, "password": password})
                    st.session_state.user = res.user
                    profile_check = supabase.table("users").select("first_login_complete").eq("id", res.user.id).single().execute().data
                    # Force password change if reset by admin or first login incomplete
                    if not profile_check or not profile_check.get("first_login_complete", False):
                        st.session_state.force_password_change = True
                    st.session_state.selected_teams = []
                    st.success("Authentication validated.")
                    st.rerun()
                except Exception: st.error("Authentication rejected. Check your credentials.")

    # ==========================================
    # CHANNEL 2: ELIGIBILITY-GATED JOIN REQUESTS
    # ==========================================
    elif st.session_state.auth_mode == "Join":
        st.subheader("Request to Join")
        
        # Pull 2nd chance timeline setting from schedule logs
        sched_meta = supabase.table("nfl_schedule").select("second_chance_start").limit(1).execute().data
        sc_start = sched_meta[0]["second_chance_start"] if sched_meta else 6
        
        # Enforce timeline rules eligibility checkpoints
        main_open = CALCULATED_CURRENT_WEEK <= 2
        sec_open = CALCULATED_CURRENT_WEEK <= (sc_start + 1)
        
        if not main_open and not sec_open:
            st.error("Enrollment Closed. Both the Main Game and 2nd Chance Game enrollment windows have expired for this year.")
        else:
            target_pool_track = "Main Game" if CALCULATED_CURRENT_WEEK <= 2 else "2nd_Chance"
            st.info(f"Requests submitted right now will automatically route into the **{target_pool_track if target_pool_track=='Main Game' else '2nd Chance Game'}** based on the currently active enrollment window.")
            
            with st.form("join_request_form", clear_on_submit=True):
                j_user = st.text_input("Choose unique Username *")
                j_first = st.text_input("First Name")
                j_last = st.text_input("Last Name")
                j_mail = st.text_input("Email Address *")
                j_cell = st.text_input("Cell Phone Number")
                
                if st.form_submit_button("Submit Request to Commissioner"):
                    if not j_user.strip() or not j_mail.strip():
                        st.error("Username and Email are mandatory fields.")
                    else:
                        try:
                            # Pre-check collisions across active players
                            collision = supabase.table("users").select("id").eq("username", j_user.strip()).execute().data
                            if collision:
                                st.error("That username code handle is already taken.")
                            else:
                                supabase.table("join_requests").insert({
                                    "username": j_user.strip(), "first_name": j_first.strip(), "last_name": j_last.strip(),
                                    "email": j_mail.strip(), "cell_phone": j_cell.strip(), "target_game": target_pool_track
                                }).execute()
                                st.success("Application submitted! Your profile is sitting in the Commissioner queue for enrollment confirmation.")
                        except Exception as e: st.error(f"Submission Error: {str(e)}")

    # ==========================================
    # CHANNEL 3: DOUBLE-VERIFIED PASSWORD RESET
    # ==========================================
    elif st.session_state.auth_mode == "Reset":
        st.subheader("Request Secure Password Reset Link")
        reset_email_input = st.text_input("Your Registered Email Address:")
        
        if st.button("Send Reset Email link", width='stretch'):
            clean_email = reset_email_input.strip()
            
            if not  clean_email:
                st.error("Email Address field is mandatory.")
            else:
                with st.spinner("Verifying identity records..."):
                    # DOUBLE LOCK PRE-CHECK: Match BOTH columns simultaneously to locate the exact player ID
                    account_match = supabase.table("users").select("id, email").eq("email", clean_email).execute().data
                    
                    if not account_match:
                        st.error("Account Verification Failed. No player record matches that specific Email.")
                    else:
                        try:
                            # Pull the targeted email stream parameter
                            target_record = account_match[0]
                            
                            # Fires standard authentication password reset link via Supabase mailing servers
                            supabase.auth.reset_password_for_email(
                                target_record["email"],
                                {"redirect_to": "https://streamlit.app"}
                            )
                            st.success("Reset link sent! Check your email inbox and spam folders to re-establish your access.")
                        except Exception as e:
                            st.error(f"Mailing server error: {str(e)}")
else:        
    user_id = st.session_state.user.id
    reg_profile = supabase.table("tournament_registrations").select("*").eq("user_id", user_id).eq("game_type", game_slug).execute().data
    
    # THE ENROLLMENT GATEWAY LOCK: Check if registration exists and if enrollment flag is active
    if not reg_profile:
        st.error(f"**Access Locked.** You are not registered for the {game_mode} game.")
        st.info("Please contact the League Commissioner to initialize your account profile: nfl.loser.pool@gmail.com")
    
    elif isinstance(reg_profile, list) and len(reg_profile) > 0 and not reg_profile[0].get("is_enrolled", False):
        st.error(f"**Not Enrolled.** Your profile is not currently enrolled in the **{game_mode}** game for the this season.")
        st.info("*Note: If you have already paid or submitted entry data to the Commissioner, access will open automatically once your enrollment status is enabled.*")
        
    elif isinstance(reg_profile, list) and len(reg_profile) > 0 and reg_profile[0].get("bracket_status") == "Eliminated":
        st.error(f"**Eliminated.** You have been eliminated from the {game_mode} game. Selection access is locked, but you can still view the Overview page.")
        
    else:
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
                <div><h4>Status for <b>{username_token}</b>: {player_status}</h4></div>
                <div style="text-align: right;"><h4>Remaining Active Players: <b>{remaining_count}</b></h4></div>
            </div>
            """,
            unsafe_allow_html=True
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

# ====================================================================
# GLOBAL ACCESSIBILITY & SECURITY PRIVACY GATES RECKONER
# ====================================================================
current_user_logged_in = st.session_state.get("user")

# THE FIX: Use an explicit conditional step to extract ID only if an active user object exists
if current_user_logged_in is not None and hasattr(current_user_logged_in, 'id'):
    current_user_uid = current_user_logged_in.id
else:
    current_user_uid = None

# Check if the current user has finalized a pick for the active selected week
user_has_finalized_this_week = False
if current_user_uid:
    user_pick_record = supabase.table("user_picks").select("id").eq("user_id", current_user_uid).eq("game_type", game_slug).eq("week", SELECTED_WEEK).eq("pick_state", "Finalized").execute().data
    if user_pick_record:
        user_has_finalized_this_week = True

# Calculate if the target week's locks have passed chronologically
is_past_week_locked = SELECTED_WEEK < CALCULATED_CURRENT_WEEK

# Absolute override criteria: Unlocked if it is an old week, if the user committed, or if admin
reveal_picks_condition = is_past_week_locked or user_has_finalized_this_week # or is_logged_in_admin

# ==========================================
# SEGMENT A: WEEKLY PICK DISTRIBUTION LIST
# ==========================================
st.write(f"### Weekly Selection Distribution — {get_week_label(SELECTED_WEEK)}")

if not reveal_picks_condition:
    st.warning("**Selection Distribution Hidden:** You must be logged in with your own selection(s) finalized for this week under **Picks** before picks are revealed for other players.")
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
                    if game_state == "Correct": card_style = "background-color: rgba(16, 185, 129, 0.15); border: 1px solid #10b981 ; color: var(--text-color);"
                    elif game_state == "Incorrect": card_style = "background-color: rgba(239, 68, 68, 0.15); border: 1px solid #ef4444; color: var(--text-color);"
                    else: card_style = "background-color: transparent; border: 1px solid rgba(148, 163, 184, 0.3); color: var(--text-color);"
                st.markdown(f"""<div style="{card_style} padding:8px 4px; border-radius:6px; text-align:center; box-shadow: 0 1px 2px rgba(0,0,0,0.05); margin-bottom:10px; font-family:sans-serif;"><div style="display:flex; justify-content:center; margin-bottom:4px;">{get_base64_logo_html(team)}</div><b style="font-size:13px; color: inherit;">{team.replace('_SO','')}{so_label}</b><span style="display:block; font-size:18px; font-weight:900; color:#2563eb; margin-top:2px;">{count}</span></div>""", unsafe_allow_html=True)

st.markdown("---")

# ==========================================
# SEGMENT B: COMPLETE LEAGUE STANDINGS MATRIX
# ==========================================
st.write("### Live Championship Standings Grid")

users_list = supabase.table("users").select("*").order("username").execute().data
registrations = supabase.table("tournament_registrations").select("*").eq("game_type", game_slug).eq("is_enrolled", True).execute().data
all_historical_picks = supabase.table("user_picks").select("*").eq("game_type", game_slug).execute().data

if not registrations:
    st.info("No active enrolled competitor rows verified on record for this game tournament track.")
else:
    user_map = {u["id"]: u["username"] for u in users_list}
    picks_by_user = {}
    for p in all_historical_picks:
        picks_by_user.setdefault(p["user_id"], {})[p["week"]] = p
        
    # EXTRA OPTIMIZATION FIX: Gather ALL of the current user's finalized choices in a local cache array.
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
        st.markdown(f"#### {bracket_title}: {players_group_count} Players")
        
        # 🚀 1. INJECT FIXED TOOLTIP LAYOUT RULES
        st.html(
            """
            <style>
                .tip-wrapper { position: relative; display: inline-block; cursor: help; border-bottom: 1px dashed rgba(128,128,128,0.5); }
                .tip-wrapper .tip-card {
                    visibility: hidden; width: 140px; background-color: #1e293b; color: #ffffff;
                    text-align: center; border-radius: 4px; padding: 4px 8px; position: absolute;
                    z-index: 999; bottom: 125%; left: 0; opacity: 0; transition: opacity 0.2s;
                    font-size: 11px; font-weight: bold; box-shadow: 0 2px 4px rgba(0,0,0,0.15);
                    font-family: sans-serif; pointer-events: none;
                }
                .tip-wrapper:hover .tip-card { visibility: visible; opacity: 1; }
            </style>
            """
        )
        
        # 🚀 2. FIXED UNIFORM COLUMN HEADERS ROW PASS
        # Build matching weekly text tags to align perfectly right above player picks
        header_html_cells = []
        for w_num in visible_weeks:
            header_html_cells.append(f'<div style="flex:1; text-align:center; font-size:11px; font-weight:800; color:var(--text-color); opacity:0.8; max-width:55px;">Wk {w_num}</div>')
            
        unified_table_header = f"""
        <div style="display: flex; align-items: center; width: 100%; padding: 6px 0; border-bottom: 2px solid rgba(128,128,128,0.3); font-family: sans-serif;">
            <div style="width: 150px; min-width: 120px; font-size: 12px; font-weight: 900; uppercase; color:var(--text-color); opacity:0.8;">PLAYER</div>
            <div style="display: flex; flex: 1; align-items: center; gap: 6px; overflow-x: auto;">
                {"".join(header_html_cells)}
            </div>
        </div>
        """
        st.html(unified_table_header)
        
        # 🚀 3. INDIVIDUAL LEAGUE PLAYER ROW LOOPS
        for reg in players_group:
            u_id = reg["user_id"]
            uname = user_map.get(u_id, "Anonymous")
            user_weeks_map = picks_by_user.get(u_id, {})
            
            user_record = next((u for u in users_list if u["id"] == u_id), None)
            first_name_str = user_record.get("first_name") or "" if user_record else ""
            last_name_str = user_record.get("last_name") or "" if user_record else ""
            full_display_name = f"{first_name_str} {last_name_str}".strip() or "Registered Player"
            
            row_html_cells = []
            for w_num in visible_weeks:
                p_data = user_weeks_map.get(w_num, None)
                if not p_data: 
                    row_html_cells.append('<div style="flex:1; text-align:center; color:#cbd5e1; font-size:12px;">&bull;</div>')
                else:
                    t_pick = p_data["team_picked"].upper()
                    p_state = p_data.get("pick_state", "Pending")
                    
                    is_current_loop_week_locked = w_num < CALCULATED_CURRENT_WEEK
                    user_has_finalized_for_loop_week = w_num in current_user_finalized_weeks
                    is_own_profile_row = (u_id == current_user_uid)
                    reveal_tile_cell = is_current_loop_week_locked or user_has_finalized_for_loop_week or is_own_profile_row or is_logged_in_admin
                    
                    if not reveal_tile_cell:
                        row_html_cells.append('<div style="flex:1; background-color: rgba(148, 163, 184, 0.15); padding: 4px 2px; border-radius: 4px; font-weight:600; font-size:10px; color:gray; text-align:center; white-space:nowrap; max-width:55px;">🔒 Hid</div>')
                    else:
                        logo_html = get_base64_logo_html(t_pick)
                        clean_team_display = t_pick.replace('_SO', '')
                        if t_pick.endswith("_SO"): clean_team_display += "🎯"
                            
                        if p_state == "Correct" or t_pick == "BYE": 
                            bg_style = "background-color: rgba(255, 229, 153, 0.15); padding: 4px 6px; border-radius: 4px; display: inline-flex; align-items: center; justify-content:center; gap: 2px; flex:1; max-width:55px;"
                        elif p_state == "Incorrect": 
                            bg_style = "background-color: rgba(239, 68, 68, 0.15); padding: 4px 6px; border-radius: 4px; display: inline-flex; align-items: center; justify-content:center; gap: 2px; flex:1; max-width:55px;"
                        else: 
                            bg_style = "display: inline-flex; align-items: center; justify-content:center; gap: 2px; color: var(--text-color); flex:1; max-width:55px;"
                            
                        cell_div = f'<div style="{bg_style}">{logo_html}<span style="font-weight:600; font-size:11px;">{clean_team_display}</span></div>'
                        row_html_cells.append(cell_div)
            
            unified_row_container = f"""
            <div style="display: flex; align-items: center; width: 100%; padding: 4px 0; border-bottom: 1px solid rgba(128,128,128,0.15); font-family: sans-serif;">
                <div style="width: 150px; min-width: 120px; font-size: 14px; font-weight: bold; white-space: nowrap;">
                    <div class="tip-wrapper" style="color: var(--text-color);">
                        {uname}
                        <div class="tip-card">👤 ID: {full_display_name}</div>
                    </div>
                </div>
                <div style="display: flex; flex: 1; align-items: center; gap: 6px; overflow-x: auto;">
                    {"".join(row_html_cells)}
                </div>
            </div>
            """
            st.html(unified_row_container)
        st.markdown("<br>", unsafe_allow_html=True)

    render_bracket_table("Loser Bracket", loser_bracket_players)
    render_bracket_table("Winner Bracket", winner_bracket_players)
    render_bracket_table("Eliminated", eliminated_players)


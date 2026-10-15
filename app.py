import streamlit as st
from supabase import create_client, Client
import os
import datetime
import time
import uuid
import base64
import extra_streamlit_components as cookie_manager

# --- INITIALIZE THE HIGH-PERFORMANCE BROWSER COOKIE MANAGER ---
# Using a static anchor key prevents the component from resetting on refresh
cookie_ctx = cookie_manager.CookieManager(key="loser_pool_cookie_anchor")

# --- INITIALIZE SECURE STREAMLIT AUTHENTICATION STORAGE TIER ---
if 'user' not in st.session_state: 
    st.session_state.user = None

# 🚀 THE BULLETPROOF URL-ANCHORED SESSION RESTORATION GATEWAY
# Reads parameters directly from the browser's address query string instantly on load!
if st.session_state.user is None:
    # Read live browser query parameters
    url_params = st.query_params
    
    if "session_key" in url_params:
        saved_refresh_token = url_params["session_key"]
        
        if saved_refresh_token and str(saved_refresh_token).strip() not in ["None", ""]:
            try:
                # Instantly exchange the url refresh key for a live authenticated profile session
                recovered_session = supabase.auth.refresh_session(saved_refresh_token)
                if recovered_session and recovered_session.user:
                    st.session_state.user = recovered_session.user
                    st.session_state.selected_teams = []
                    st.session_state.force_password_change = False
                    
                    # ROTATION SECURITY: Keep the URL bar updated with the newly cycled token string
                    new_refresh_token = recovered_session.session.refresh_token
                    st.query_params["session_key"] = new_refresh_token
            except Exception:
                # If token expires or gets corrupted, clear out the broken URL key safely
                if "session_key" in st.query_params:
                    del st.query_params["session_key"]

# --- SETUP MANDATORY FIRST DIRECTIVE PASS ---
st.set_page_config(layout="wide")
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
                        
                        # 1. NEW CELL CARRIER CARRIER GATEWAY SELECTOR
                        # Tracks the exact telecom provider network strings needed for free text routing
                        carrier_options = ["Select Provider", "Verizon", "AT&T", "T-Mobile", "Sprint"]
                        current_db_carrier = u_prof.get("cell_carrier") or "Select Provider"
                        
                        try: default_carrier_idx = carrier_options.index(current_db_carrier)
                        except ValueError: default_carrier_idx = 0
                            
                        e_carrier = st.selectbox("Provider (Required for SMS):", options=carrier_options, index=default_carrier_idx, key="sb_carrier_select")
                        
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
                                st.error("**Action Required:** You must select a Cellular Network Provider to enable SMS text alerts.")
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
                # 🚀 THE SMART ADMIN RESTORATION LOGOUT ROUTER
                logout_label = "Return to Admin Session" if "admin_backup_uid" in st.session_state else "Log Out"
                
                if st.button(logout_label, key="sidebar_logout_btn", width='stretch'):
                    if "admin_backup_uid" in st.session_state:
                        class AdminUser:
                            def __init__(self, uid): self.id = uid
                        st.session_state.user = AdminUser(st.session_state.admin_backup_uid)
                        del st.session_state.admin_backup_uid
                        st.session_state.selected_teams = []
                        st.session_state.force_password_change = False
                        st.toast("Admin session restored successfully!")
                    else:
                        st.session_state.user = None
                        st.session_state.selected_teams = []
                        st.session_state.force_password_change = False
                        
                        # 🚀 Wipes out the persistent URL parameter instantly on logout
                        if "session_key" in st.query_params:
                            del st.query_params["session_key"]
                            
                    time.sleep(0.3)
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

    # ====================================================================
    # CHANNEL 1: SECURE ACCOUNT LOGIN & ADMIN MASQUERADE PORTAL
    # ====================================================================
    if st.session_state.auth_mode == "Login":
        st.subheader("Player Login")
        
        # 🚀 THE FIX: Synchronize variable naming declarations with top-of-file tokens
        current_user_logged_in = st.session_state.get("user")
        is_authenticated_admin = False
        
        # Master Supabase User ID string identifier
        MASTER_ADMIN_UID = "3f3a74a6-3725-4a3b-abda-015e73cb6f4b" 
        
        if current_user_logged_in:
            try:
                u_id_str = str(current_user_logged_in.id).strip()
                if u_id_str == MASTER_ADMIN_UID:
                    is_authenticated_admin = True
            except Exception: pass

        # Only show masquerade controls if YOU are logged in as admin
        if is_authenticated_admin:
            st.success(f"⚡ **Admin Authorization Verified.** Dev tools unlocked.")
            testing_mode = st.checkbox("Enable Developer Masquerade Mode", key="admin_session_masq_toggle")
            
            if testing_mode:
                try:
                    users_list = supabase.table("users").select("id", "username").execute().data
                    if users_list:
                        user_options = {u["username"]: u["id"] for u in users_list}
                        selected_user_name = st.selectbox("Select Player Identity to Assume:", list(user_options.keys()))
                        if st.button("Assume Selected Identity", width='stretch', type="primary"):
                            class MockUser:
                                def __init__(self, uid): self.id = uid
                            st.session_state.admin_backup_uid = MASTER_ADMIN_UID
                            st.session_state.user = MockUser(user_options[selected_user_name])
                            st.session_state.force_password_change = False
                            st.session_state.selected_teams = []
                            st.success(f"Session shifted to {selected_user_name}!")
                            time.sleep(0.5)
                            st.rerun()
                except Exception as e: st.error(f"Masquerade Error: {str(e)}")
                st.markdown("---")

        # Standard secure login interface fields open to all users
        if not current_user_logged_in or not is_authenticated_admin or (is_authenticated_admin and not st.session_state.get("admin_session_masq_toggle")):
            email = st.text_input("Email Address", key="main_login_email")
            password = st.text_input("Password", type="password", key="main_login_pwd")
            
            # 🚀 THE FIX: Isolate the button click logic cleanly to prevent refresh exceptions
            submit_login_click = st.button("Log In", width='stretch', type="primary")
            
            if submit_login_click:
                if not email.strip() or not password.strip():
                    st.error("Please enter both your email address and password.")
                else:
                    try:
                        res = supabase.auth.sign_in_with_password({"email": email.strip(), "password": password})
                        st.session_state.user = res.user
                        
                        # 🚀 THE SECURE URL ANCHOR:
                        # Extract the secure Refresh Token from the database response object
                        secure_refresh_string = res.session.refresh_token
                        
                        # Inject the refresh token directly into the browser's address query bar
                        st.query_params["session_key"] = secure_refresh_string
                        
                        profile_check = supabase.table("users").select("first_login_complete").eq("id", res.user.id).single().execute().data
                        if not profile_check or not profile_check.get("first_login_complete", False):
                            st.session_state.force_password_change = True
                            
                        st.session_state.selected_teams = []
                        st.success("Authentication validated. Secure Persistent Session Active!")
                        time.sleep(0.3)
                        st.rerun()
                        
                    except Exception: 
                        st.error("❌ **Authentication rejected:** The email or password you entered is incorrect. Please check your spelling and try again.")

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

    # ====================================================================
    # SECURE SMART SELF-ENROLLMENT GATE (2ND CHANCE MATRIX INTERCEPTOR)
    # ====================================================================
    elif isinstance(reg_profile, list) and len(reg_profile) > 0 and not reg_profile[0].get("is_enrolled", False):
        st.error(f"**Not Enrolled.** Your profile is not currently active for the **{game_mode}** game this season.")
        
        # 1. Pull the 2nd Chance timeline start week setting from schedule logs
        sched_meta = supabase.table("nfl_schedule").select("second_chance_start").limit(1).execute().data
        sc_start_week = sched_meta[0]["second_chance_start"] if sched_meta else 6
        
        # 2. Check timeline eligibility: Open until the conclusion of the 2nd Chance starting week
        is_2nd_chance_window_open = CALCULATED_CURRENT_WEEK <= (sc_start_week + 1)
        
        if game_mode == "2nd Chance" and is_2nd_chance_window_open:
            st.info("**Good News!** The enrollment window for the 2nd Chance Pool is currently open. You can activate your slot right now to jump into this week's action instantly.")
            
            # Render high-visibility self-service registration button row layout
            if st.button("Join the 2nd Chance Game", key="user_self_enroll_btn", type="primary", width='stretch'):
                with st.spinner("Synchronizing league roster ledgers..."):
                    try:
                        # Update the target user's enrollment tracking metrics natively in Supabase
                        supabase.table("tournament_registrations").update({
                            "is_enrolled": True,
                            "bracket_status": "Loser Bracket", # Enters un-eliminated with clean loss sheet
                            "byes_used": 0,
                            "is_paid": False  # Flaunted as unpaid until Venmo pass clears
                        }).eq("user_id", user_id).eq("game_type", "2nd_Chance").execute()
                        
                        st.success("Roster enrollment verified! Welcome to the 2nd Chance game.")
                        time.sleep(2)
                        st.rerun()
                    except Exception as err:
                        st.error(f" Roster verification exception: {str(err)}")
        else:
            # Traditional baseline disclaimer notice for closed tracks or Main game overrides
            st.info("*Note: If you are looking to join the Main Game, or if you have already paid or submitted entry data to the Commissioner, access will open automatically once your enrollment status is enabled.*")
    
    elif isinstance(reg_profile, list) and len(reg_profile) > 0 and reg_profile[0].get("bracket_status") == "Eliminated":
        st.error(f"**Eliminated.** You have been eliminated from the {game_mode} game. Selection access is locked, but you can still view the Overview page.")
        
    else:
        # Extract row references safely out of the array format
        active_profile = reg_profile[0] if isinstance(reg_profile, list) else reg_profile
        player_status = active_profile["bracket_status"]
        
        # PAYMENT NOTICE: If enrolled but unpaid, render a gentle reminder banner without locking the form
        if not active_profile.get("is_paid", False):
            st.warning("**Payment Reminder:** Our ledger shows your entry fee for this pool track is currently outstanding. Please settle up with the Commissioner as soon as possible by sending $25 to @Robert-Moore-65 on Venmo.")

        # Recover user info from Supabase
        user_profile_res = supabase.table("users").select("*").eq("id", user_id).single().execute().data
        user_profile = user_profile_res if user_profile_res else {}
        username_token = user_profile.get("username", "Anonymous Player")

        # Inject the Admin Masquerade Portal directly into your post-login view layer
        # Replace this string with your exact Supabase User ID string from your auth dashboard console
        MASTER_ADMIN_UID = "3f3a74a6-3725-4a3b-abda-015e73cb6f4b"
        
        if str(user_id).strip() == MASTER_ADMIN_UID:
            with st.container(border=True):
                st.markdown("#### Commissioner Session Masquerade Portal")
                st.caption("This utility control panel is restricted to your Admin ID only. Enabling Masquerade allows you to swap identities and test player views.")
                
                testing_mode = st.checkbox("Enable Developer Masquerade Mode", key="admin_session_masq_toggle")
                if testing_mode:
                    try:
                        users_list = supabase.table("users").select("id", "username").execute().data
                        if users_list:
                            user_options = {u["username"]: u["id"] for u in users_list}
                            selected_user_name = st.selectbox("Select Player Identity to Assume:", list(user_options.keys()))
                            if st.button("Assume Selected Identity", width='stretch', type="primary"):
                                class MockUser:
                                    def __init__(self, uid): self.id = uid
                                st.session_state.user = MockUser(user_options[selected_user_name])
                                st.session_state.force_password_change = False
                                st.session_state.selected_teams = []
                                st.success(f"Session successfully shifted to {selected_user_name}!")
                                time.sleep(1)
                                st.rerun()
                    except Exception as e: st.error(f"Masquerade Error: {str(e)}")
            st.markdown("<br>", unsafe_allow_html=True)
        
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

        # --- RECOVER USER COMPREHENSIVE SELECTION RECORDS ---
        all_picks_res = supabase.table("user_picks").select("*").eq("user_id", user_id).eq("game_type", game_slug).execute().data
        
        # ====================================================================
        # SELECTION LEDGER DISCOVERY ENGINE (22-WEEK HISTORY RAIL)
        # ====================================================================
        st.write("#### Your Season Selection History")
        
        # 1. Fetch active schedule records to determine real-time card color shading
        sched_rows = supabase.table("nfl_schedule").select("week", "away_team", "home_team", "winner").execute().data
        
        # Build an indexed game outcome lookup table: { week_num: { 'BUF': 'Correct' } }
        history_outcome_lookup = {}
        for match in (sched_rows or []):
            w_num = match["week"]
            away = match["away_team"].upper()
            home = match["home_team"].upper()
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
                    # Low-profile empty placeholder cell text string
                    card_html = f"""
                    <div style="flex: 1; min-width: 45px; border: 1px dashed rgba(148, 163, 184, 0.4); padding: 6px 2px; border-radius: 4px; text-align: center; min-height: 65px; display: flex; flex-direction: column; align-items: center; justify-content: center; opacity: 0.4; font-family: sans-serif;">
                        <span style="font-size: 9px; color: var(--text-color); font-weight: bold; display: block;">Wk {w}</span>
                        <span style="font-size: 12px; color: var(--text-color);">&bull;</span>
                    </div>
                    """
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
                    
                    # 🚀 THE UNBREAKABLE INLINE FIXED EMBED ENGINE:
                    # Bypasses all cross-page function references to decode files directly inline
                    logo_html = ""
                    try:
                        t_clean = t_pick.replace("_SO", "").strip().upper()
                        file_name = "BYE.svg" if t_clean == "BYE" else f"{t_clean}.svg"
                        
                        # Pinpoint exact system physical folder boundaries
                        base_dir = os.path.dirname(os.path.abspath(__file__))
                        absolute_logo_path = os.path.join(base_dir, "static", file_name)
                        
                        if os.path.exists(absolute_logo_path):
                            import base64
                            with open(absolute_logo_path, "rb") as f:
                                encoded_raw_bytes = base64.b64encode(f.read()).decode("utf-8")
                            logo_html = f'<img src="data:image/svg+xml;base64,{encoded_raw_bytes}" width="24" height="15" style="object-fit:contain; vertical-align:middle; display:block; margin:0 auto;"/>'
                    except Exception:
                        pass
                        
                    has_so_star = "🎯" if t_pick.endswith("_SO") else ""
                    
                    # Unified clean single-quote html card block wrapper concatenation
                    card_html = (
                        f'<div style="{card_bg} flex: 1; min-width: 55px; padding: 6px 2px; border-radius: 4px; text-align: center; min-height: 65px; display: flex; flex-direction: column; align-items: center; justify-content: center; box-shadow: 0 1px 1px rgba(0,0,0,0.02); font-family: sans-serif; box-sizing: border-box;">'
                        f'<span style="font-size: 9px; opacity: 0.7; font-weight: bold; display: block; color: inherit; margin-bottom: 2px;">Wk {w}</span>'
                        f'<div style="display: flex; justify-content: center; min-height: 15px; align-items: center; width: 100%; margin-bottom: 2px;">{logo_html}</div>'
                        f'<span style="font-size: 10px; font-weight: 800; display: block; color: inherit; line-height: 1;">{clean_team_key}{has_so_star}</span>'
                        f'</div>'
                    )
                rail_html_cards.append(card_html)
            
            # Combine all cards into a high-density horizontal flexbox container frame wrapper
            unified_rail_container = f"""
            <div style="display: flex; gap: 4px; width: 100%; overflow-x: auto; padding: 5px 0; margin-bottom: 15px;">
                {"".join(rail_html_cards)}
            </div>
            """
            st.html(unified_rail_container)
            
        else:
            st.info("No prior selection records on file yet for this regular season campaign.")
            
        st.markdown("<br>", unsafe_allow_html=True)

        used_teams = []
        for p in all_picks_res:
            if p["week"] < 19:
                if p["team_picked"].endswith("_SO"): continue
                used_teams.append(p["team_picked"])

        # ====================================================================
        # 🚀 THE SUBMISSION STATE NOTIFICATION BLOCK (Restored Pass)
        # ====================================================================
        # 1. Gather any existing entries logged on file for this specific target week
        current_picks = [p for p in all_picks_res if p["week"] == SELECTED_WEEK]
        is_finalized = any(p["pick_state"] in ["Finalized", "Correct", "Incorrect"] for p in current_picks)
        is_confirmed = any(p["pick_state"] == "Confirmed" for p in current_picks)

        # 2. Render highly visible information banners explaining pick states to players
        confirmed_picks_this_week = [p["team_picked"] for p in current_picks if p["pick_state"] == "Confirmed"]
        if confirmed_picks_this_week:
            st.info(f"**Confirmed Pick:** You currently have **{', '.join(confirmed_picks_this_week)}** selected for this week. Clicking choices below will alter your Confirmed pick entry.")

        finalized_picks_this_week = [p["team_picked"] for p in current_picks if p["pick_state"] in ["Finalized", "Correct", "Incorrect"]]
        if finalized_picks_this_week:
            st.success(f"**Finalized Pick Locked:** You have officially locked in **{', '.join(finalized_picks_this_week)}** for this week. You can view competitor picks under the Overview tab, but edits are no longer allowed.")

        # 3. Pre-seed your active session tracking arrays on mount from these database rows
        if "selected_teams" not in st.session_state or not st.session_state.selected_teams:
            st.session_state.selected_teams = [p["team_picked"].upper() for p in current_picks]


            # 1. NEW MATCHING EXTENSION: Build a dictionary map linking team keys to their week of use
            # Stores structure format as: {'MIA': 1, 'BUF': 2}
            used_teams = {}
            for p in all_picks_res:
                clean_pick_name = p["team_picked"].replace("_SO", "")
                
                # Rule A: A team is permanently used if locked in a completely separate PRIOR week
                if p["week"] != SELECTED_WEEK and p["week"] < 19:
                    if not p["team_picked"].endswith("_SO"): 
                        used_teams[clean_pick_name] = p["week"]
                        
                # Rule B: A team is also used if it was already FINALIZED for the current target week
                elif p["week"] == SELECTED_WEEK and p["pick_state"] == "Finalized":
                    if not p["team_picked"].endswith("_SO"): 
                        used_teams[clean_pick_name] = p["week"]



        # 🚀 THE LIMIT DETECTOR PATCH: Calculates choice constraints dynamically
        # 1. Tally up how many teams the player has selected or confirmed on their current workspace layout sheet
        current_picks_count = len(st.session_state.selected_teams)
        
        # 2. Establish maximum limits based on your league rules timeline parameters
        if SELECTED_WEEK <= 14:
            max_allowed_picks = 1
        elif SELECTED_WEEK <= 18:
            max_allowed_picks = 2
        elif SELECTED_WEEK == 19:
            max_allowed_picks = 6 # Wildcard
        elif SELECTED_WEEK == 20:
            max_allowed_picks = 4 # Divisional
        elif SELECTED_WEEK == 21:
            max_allowed_picks = 2 # Conference Championship
        elif SELECTED_WEEK == 22:
            max_allowed_picks = 1 # Super Bowl
        else:
            max_allowed_picks = 32 # Catch all
            
        # 3. Securely set the missing Boolean flag variable for your button disabling configurations
        limit_reached = current_picks_count >= max_allowed_picks
        team_word = "team" if SELECTED_WEEK <= 14 else "teams"
        required_picks = 1 if SELECTED_WEEK <= 14 else 2 if SELECTED_WEEK <= 18 else 1
        
        st.write(f"Select **{required_picks}** {team_word} to lose from the matchups below:")
        
        matchups = supabase.table("nfl_schedule").select("*").eq("week", SELECTED_WEEK).execute().data
        
        if "selected_teams" not in st.session_state: 
            st.session_state.selected_teams = []
            
        # ====================================================================
        # 📊 THE CHRONOLOGICAL MATCHUP SORTING ENGINE
        # ====================================================================
        # Sorts matchups from earliest to latest; groups NULL times at the bottom by ID
        if matchups:
            matchups = sorted(
                matchups,
                key=lambda x: (
                    0, 
                    str(x.get("kickoff_time")), 
                    x.get("id")
                ) if x.get("kickoff_time") is not None else (
                    1, 
                    "", 
                    x.get("id")
                )
            )

        # ====================================================================
        # 📱 FIXED MOBILE-FIRST MATCHUP MASTER LOOP (INLINE WORKSPACE CONTROLS)
        # ====================================================================
        main_grid_col1, main_grid_col2 = st.columns(2)
        
        for idx, match in enumerate(matchups):
            m_id = match["id"]
            away, home = match["away_team"].upper(), match["home_team"].upper()
            
            # Secure Kickoff Validation Pass & Dynamic Calendar Isolation Pass
            kickoff_raw = match.get("kickoff_time")
            game_time_label = "Sunday 1:00 PM ET"
            is_game_locked, is_early_game = False, False
            
            # THE FIX: Only lock out or force-finalize selections if viewing the active calendar week!
            is_currently_active_week = (SELECTED_WEEK == CALCULATED_CURRENT_WEEK)
            is_past_week = (SELECTED_WEEK < CALCULATED_CURRENT_WEEK)
            
            if is_past_week:
                is_game_locked = True # Past weeks are universally closed
                
            if kickoff_raw and is_currently_active_week:
                try:
                    clean_time_str = str(kickoff_raw).replace(" ", "T").strip()[:19]
                    kickoff_dt_et = datetime.datetime.fromisoformat(clean_time_str)
                    now_utc = datetime.datetime.now(datetime.timezone.utc)
                    now_et_naive = (now_utc - datetime.timedelta(hours=4)).replace(tzinfo=None)
                    
                    if now_et_naive >= kickoff_dt_et: 
                        is_game_locked = True
                        
                    sunday_deadline = datetime.datetime(kickoff_dt_et.year, kickoff_dt_et.month, kickoff_dt_et.day, 12, 0, 0)
                    while sunday_deadline.weekday() != 6: sunday_deadline -= datetime.timedelta(days=1)
                    if kickoff_dt_et < sunday_deadline: 
                        is_early_game = True
                except Exception: pass

            # Re-generate the friendly display label formatting smoothly for future slates
            if kickoff_raw and not is_past_week:
                try:
                    clean_str = str(kickoff_raw).replace(" ", "T").strip()[:19]
                    dt = datetime.datetime.fromisoformat(clean_str)
                    day_name = dt.strftime("%A")
                    display_hour = dt.hour if dt.hour <= 12 else dt.hour - 12
                    if display_hour == 0: display_hour = 12
                    game_time_label = f"{day_name} {display_hour}:{dt.minute:02d} {'PM' if dt.hour >= 12 else 'AM'} ET"
                except Exception: pass

            # Resolve Active States Natively for this Matchup Slot
            db_away_pick = next((p for p in current_picks if p["team_picked"].upper() == away), None)
            db_home_pick = next((p for p in current_picks if p["team_picked"].upper() == home), None)
            active_db_pick = db_away_pick or db_home_pick
            
            # Determine current pick state configuration tiers
            has_db_confirmed = active_db_pick is not None and active_db_pick.get("pick_state") == "Confirmed"
            has_db_finalized = active_db_pick is not None and active_db_pick.get("pick_state") in ["Finalized", "Correct", "Incorrect"]
            
            # Read local session state selections cache values
            is_sel_away = away in st.session_state.selected_teams
            is_sel_home = home in st.session_state.selected_teams
            has_workspace_selection = is_sel_away or is_sel_home
            
            # Force auto-highlight matching state loops on page initial load
            if active_db_pick and not has_workspace_selection and not is_finalized:
                if db_away_pick: st.session_state.selected_teams.append(away); is_sel_away = True
                if db_home_pick: st.session_state.selected_teams.append(home); is_sel_home = True
                has_workspace_selection = True

            away_is_used = away in used_teams and not (active_db_pick and db_away_pick)
            home_is_used = home in used_teams and not (active_db_pick and db_home_pick)
            
            # Render layout paths into alternating column containers grids
            with (main_grid_col1 if idx % 2 == 0 else main_grid_col2):
                with st.container(border=True):
                    c_logos, c_away_btn, c_home_btn = st.columns([2.0, 4.0, 4.0])
                    
                    with c_logos:
                        st.html(f'<div style="display:flex; justify-content:center; align-items:center; gap:4px; height:35px; width:100%;">{get_base64_logo_html(away)}<span style="font-size:10px; color:gray; font-weight:bold;">@</span>{get_base64_logo_html(home)}</div>')
                    
                    with c_away_btn:
                        lbl_away = f"{away} (Used)" if away_is_used else away
                        dis_away = is_game_locked or has_db_finalized or away_is_used or (limit_reached and not is_sel_away)
                        if st.button(lbl_away, key=f"btn_aw_{m_id}", disabled=dis_away, type="primary" if is_sel_away else "secondary", width='stretch'):
                            if is_sel_away: st.session_state.selected_teams.remove(away)
                            else:
                                st.session_state.selected_teams = [t for t in st.session_state.selected_teams if t in [away, home]] # Clear row conflicts
                                st.session_state.selected_teams.append(away)
                            st.rerun()
                            
                    with c_home_btn:
                        lbl_home = f"{home} (Used)" if home_is_used else home
                        dis_home = is_game_locked or has_db_finalized or home_is_used or (limit_reached and not is_sel_home)
                        if st.button(lbl_home, key=f"btn_hm_{m_id}", disabled=dis_home, type="primary" if is_sel_home else "secondary", width='stretch'):
                            if is_sel_home: st.session_state.selected_teams.remove(home)
                            else:
                                st.session_state.selected_teams = [t for t in st.session_state.selected_teams if t in [away, home]]
                                st.session_state.selected_teams.append(home)
                            st.rerun()
                    # --- DYNAMIC INLINE ACTION BUTTONS SYSTEM RAIL ---
                    # Only visible if a choice is actively selected in session workspace or exists in the database
                    if has_workspace_selection or active_db_pick:
                        st.markdown("<div style='margin: 4px 0;'></div>", unsafe_allow_html=True)
                        c_conf, c_fin, c_res = st.columns(3)
                        active_team_choice = away if is_sel_away else home
                        
                        with c_conf:
                            # Confirmed state handler button parameters
                            if has_db_finalized:
                                st.button("Confirmed", key=f"inf_c_{m_id}", disabled=True, width='stretch')
                            else:
                                if st.button("Confirm", key=f"act_c_{m_id}", type="primary" if has_db_confirmed else "secondary", disabled=is_game_locked, width='stretch'):
                                    supabase.table("user_picks").delete().eq("user_id", user_id).eq("game_type", game_slug).eq("week", SELECTED_WEEK).execute()
                                    target_state = "Finalized" if is_early_game else "Confirmed"
                                    supabase.table("user_picks").insert({"user_id": user_id, "game_type": game_slug, "week": SELECTED_WEEK, "team_picked": active_team_choice, "pick_state": target_state}).execute()
                                    st.toast("Selection Confirmed!")
                                    time.sleep(0.3); st.rerun()
                                    
                        with c_fin:
                            # Finalized state button logic with absolute confirmation requirement popover modal
                            if has_db_finalized:
                                st.button("Finalized", key=f"inf_f_{m_id}", type="primary", disabled=True, width='stretch')
                            else:
                                # Use st.popover to enforce the user confirmation requirement right inside the matchup box container
                                with st.popover("Finalize", key=f"pop_f_{m_id}", use_container_width=True):
                                    st.warning("Finalizing locks this choice permanently. Edits are not allowed after this step.")
                                    if st.button("Yes, Lock It In", key=f"h_lock_{m_id}", type="primary", use_container_width=True):
                                        supabase.table("user_picks").delete().eq("user_id", user_id).eq("game_type", game_slug).eq("week", SELECTED_WEEK).execute()
                                        supabase.table("user_picks").insert({"user_id": user_id, "game_type": game_slug, "week": SELECTED_WEEK, "team_picked": active_team_choice, "pick_state": "Finalized"}).execute()
                                        st.session_state.selected_teams = []
                                        st.balloons()
                                        time.sleep(0.5); st.rerun()
                                        
                        with c_res:
                            # Reset control state logic router parameters
                            if has_db_finalized:
                                pass # Simply do not present the Reset button once hard-locked to Finalized state
                            else:
                                if st.button("Reset", key=f"act_r_{m_id}", disabled=is_game_locked, width='stretch'):
                                    if has_db_confirmed:
                                        # If already written to DB as Confirmed, remove row record entirely from ledger sheets
                                        supabase.table("user_picks").delete().eq("user_id", user_id).eq("game_type", game_slug).eq("week", SELECTED_WEEK).execute()
                                        st.toast("Database Entry Removed")
                                    else:
                                        st.toast("Workspace Reset Completed")
                                    st.session_state.selected_teams = [t for t in st.session_state.selected_teams if t not in [away, home]]
                                    time.sleep(0.3); st.rerun()

                    # Footnote metadata row timestamps metrics
                    st.markdown("<div style='margin-top: 4px;'></div>", unsafe_allow_html=True)
                    if is_game_locked: st.markdown(f"<span style='color:#ef4444; font-size:11px; font-weight:bold;'>Kickoff Passed ({game_time_label})</span>", unsafe_allow_html=True)
                    else: st.markdown(f"<span style='color:gray; font-size:11px; font-weight:500;'>{game_time_label}</span>", unsafe_allow_html=True)

        # --- DEDICATED LEAGUE BYE SLOT UTILITY CARD BLOCK ---
        st.markdown("---")
        is_bye_selected = "BYE" in st.session_state.selected_teams
        db_bye_pick = next((p for p in current_picks if p["team_picked"].upper() == "BYE"), None)
        has_bye_finalized = db_bye_pick is not None and db_bye_pick.get("pick_state") in ["Finalized", "Correct", "Incorrect"]
        
        # THE ABSOLUTE REFRESH FIX: Scan user selection logs for ANY historical bye usage
        # Searches across every week state configuration to block multi-bye choices securely
        historical_byes_spent = 0
        if all_picks_res:
            historical_byes_spent = sum(1 for p in all_picks_res if p.get("team_picked", "").upper() == "BYE")
            
        # A bye is used if spent historically, or if already locked for this specific week selection
        has_already_exhausted_bye = (historical_byes_spent >= 1) and not (db_bye_pick is not None)
        
        dis_bye = is_finalized or has_bye_finalized or has_already_exhausted_bye or (limit_reached and not is_bye_selected)
        
        if not has_bye_finalized:
            # Button highlights as active primary if selected in current workspace or active week row
            lbl_bye_btn = "Bye Already Used This Season" if has_already_exhausted_bye else "Use My Bye"
            
            if st.button(lbl_bye_btn, type="primary" if is_bye_selected or db_bye_pick else "secondary", disabled=dis_bye, width='stretch'):
                supabase.table("user_picks").delete().eq("user_id", user_id).eq("game_type", game_slug).eq("week", SELECTED_WEEK).execute()
                if is_bye_selected or db_bye_pick:
                    st.session_state.selected_teams = [t for t in st.session_state.selected_teams if t != "BYE"]
                    st.toast("BYE Slot Choice Cleared")
                else:
                    st.session_state.selected_teams = ["BYE"]
                    supabase.table("user_picks").insert({"user_id": user_id, "game_type": game_slug, "week": SELECTED_WEEK, "team_picked": "BYE", "pick_state": "Confirmed"}).execute()
                    st.toast("BYE Option Logged as Confirmed")
                time.sleep(0.3); st.rerun()
        else:
            st.button("Bye Option Finalized & Exhausted", disabled=True, type="primary", width='stretch')


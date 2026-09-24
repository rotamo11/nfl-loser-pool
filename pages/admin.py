import streamlit as st
import os
import csv
import io
import uuid
import datetime
from supabase import create_client, Client

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

with st.sidebar:
    st.image("static/loser-logo.png", use_container_width=True)
    game_mode = st.selectbox("Select Pool Tournament", ["Main Pool", "2nd Chance Game"])
    game_slug = "Main" if game_mode == "Main Pool" else "2nd_Chance"
    
    w_opts = [f"{get_week_label(w)} (current)" if w == CALCULATED_CURRENT_WEEK else get_week_label(w) for w in range(1, 23)]
    s_lbl = st.selectbox("📆 Target Pool Week", options=w_opts, index=CALCULATED_CURRENT_WEEK - 1).replace(" (current)", "")
    admin_week = 19 if "Wild" in s_lbl else 20 if "Div" in s_lbl else 21 if "Conf" in s_lbl else 22 if "Super" in s_lbl else int(s_lbl.split(" ")[1])

# Dynamic color injection
st.markdown(f"<style>[data-testid='stSidebar'] {{ background-color: {'#1d3d70' if game_slug=='Main' else '#974706'} !important; }}</style>", unsafe_allow_html=True)

st.html(f"<h2>2026 Commissioner Board &bull; {game_mode} &bull; {get_week_label(admin_week)}</h2><hr/>")

tab_scores, tab_users, tab_csv = st.tabs(["🏁 Game & Score Processing", "👥 League Roster Management", "📂 Applications Queue & CSV Utilities"])

# ==========================================
# TAB 1: GAME & SCORE PROCESSING
# ==========================================
with tab_scores:
    # Recover configuration meta bounds
    sched_meta = supabase.table("nfl_schedule").select("second_chance_start").limit(1).execute().data
    sc_start = sched_meta[0]["second_chance_start"] if sched_meta else 6
    
    st.markdown("### 🍩 Configure Post-Season / 2nd Chance Parameters")
    new_sc_week = st.number_input("Set 2nd Chance Launch Target (NFL Week Number):", min_value=1, max_value=17, value=sc_start)
    if st.button("Update 2nd Chance Kickoff Line", use_container_width=True):
        supabase.table("nfl_schedule").update({"second_chance_start": new_sc_week}).neq("week", 99).execute()
        st.success(f"2nd Chance Game start week line moved to Week {new_sc_week}!")
        st.rerun()
        
    st.markdown("---")
    schedule_res = supabase.table("nfl_schedule").select("*").eq("week", admin_week).execute().data
    if not schedule_res: st.info("No games matched for this week segment parameters.")
    else:
        for match in schedule_res:
            m_id = match["id"]
            away, home = match["away_team"].upper(), match["home_team"].upper()
            with st.container(border=True):
                c_m, c_w, c_s, c_a = st.columns([2.5, 2, 1.5, 1.5])
                with c_m: st.markdown(f"<b>{away}</b> @ <b>{home}</b>", unsafe_allow_html=True)
                with c_w: w_sel = st.radio("Winner:", [away, home, "TIE"], index=None, key=f"w_{m_id}", horizontal=True, label_visibility="collapsed")
                with c_s: is_so = st.checkbox("Shutout", key=f"s_{m_id}")
                with c_a:
                    if st.button("Lock Results", key=f"l_{m_id}", use_container_width=True):
                        if not w_sel: st.error("Select winner")
                        else:
                            supabase.table("nfl_schedule").update({"winner": w_sel, "is_shutout": is_so}).eq("id", m_id).execute()
                            picks = supabase.table("user_picks").select("*").eq("game_type", game_slug).eq("week", admin_week).in_("team_picked", [away, f"{away}_SO", home, f"{home}_SO"]).execute().data
                            for p in picks:
                                ct = p["team_picked"].replace("_SO", "")
                                res = "Incorrect" if w_sel == "TIE" else "Correct" if ct != w_sel else "Incorrect"
                                supabase.table("user_picks").update({"pick_state": res, "team_picked": f"{ct}_SO" if res=="Correct" and is_so else p["team_picked"]}).eq("id", p["id"]).execute()
                                upks = supabase.table("user_picks").select("*").eq("game_type", game_slug).eq("user_id", p["user_id"]).execute().data
                                wrg = sum(1 for k in upks if k["pick_state"] == "Incorrect")
                                supabase.table("tournament_registrations").update({"bracket_status": "Loser Bracket" if wrg==0 else "Winner Bracket" if wrg==1 else "Eliminated"}).eq("user_id", p["user_id"]).eq("game_type", game_slug).execute()
                            st.success("Calculated!")
                            st.rerun()

# ==========================================
# 👥 TAB 2: ROSTER & PROFILE MANAGEMENT
# ==========================================
with tab_users:
    all_users = supabase.table("users").select("*").order("username").execute().data
    all_regs = supabase.table("tournament_registrations").select("*").eq("game_type", game_slug).execute().data
    regs_map = {r["user_id"]: r for r in all_regs}
    
    col_l, col_r = st.columns(2)
    with col_l:
        st.markdown(f"### 📋 Current Roster Sheets ({game_mode} Status View)")
        for u in all_users:
            rg = regs_map.get(u["id"])
            badge = "🚫 [Not Enrolled]" if not rg or not rg.get("is_enrolled") else "💲 [Paid]" if rg.get("is_paid") else "❌ [UNPAID]"
            admin_label = " ⭐ [ADMIN]" if u.get("is_admin", False) else ""
            
            if st.button(f"{u['username']} ({u.get('first_name','') or ''}) {admin_label} {badge}", key=f"u_{u['id']}", use_container_width=True):
                st.session_state.selected_mgmt_user = u
                st.rerun()
                
    with col_r:
        st.markdown("### 🖋️ Profile Profile Editor Sheet")
        selected_user = st.session_state.get("selected_mgmt_user")
        if not selected_user: 
            st.info("Select a competitor from the left list to modify parameters.")
        else:
            # 🚀 FIX: Securely pulls separate registration tracking details for both pools
            main_reg_data = supabase.table("tournament_registrations").select("*").eq("user_id", selected_user["id"]).eq("game_type", "Main").execute().data
            sec_reg_data = supabase.table("tournament_registrations").select("*").eq("user_id", selected_user["id"]).eq("game_type", "2nd_Chance").execute().data
            
            mr = main_reg_data[0] if main_reg_data else {"is_enrolled": False, "is_paid": False}
            sr_lock = sec_reg_data[0] if sec_reg_data else {"is_enrolled": False, "is_paid": False}
            
            with st.form("edit_user_form"):
                st.markdown(f"Editing Database User Index ID: **{selected_user['username']}**")
                e_user = st.text_input("Username Code Token", value=selected_user.get("username") or "")
                e_first = st.text_input("First Name", value=selected_user.get("first_name") or "")
                e_last = st.text_input("Last Name", value=selected_user.get("last_name") or "")
                e_mail = st.text_input("Email Address", value=selected_user.get("email") or "")
                e_cell = st.text_input("Cell Phone Number", value=selected_user.get("cell_phone") or "")
                
                forced_temp_pw = st.text_input("Assign Temporary Overwrite Password (Forces reset on next login):", value="", type="password")
                edit_is_admin = st.checkbox("Grant Platform Administrative Status privileges", value=selected_user.get("is_admin", False))
                edit_notes = st.text_area("User Profile Account Notes Ledger", value=selected_user.get("notes") or "")
                
                st.markdown("---")
                st.markdown("#### 🏆 Main Pool Track Access Settings")
                m_en = st.checkbox("Enrolled in Main Pool", value=mr.get("is_enrolled", False))
                m_pd = st.checkbox("Main Pool Paid", value=mr.get("is_paid", False))
                
                st.markdown("#### 🍩 2nd Chance Pool Track Access Settings")
                s_en = st.checkbox("Enrolled in 2nd Chance Pool", value=sr_lock.get("is_enrolled", False))
                s_pd = st.checkbox("2nd Chance Pool Paid", value=sr_lock.get("is_paid", False))
                
                if st.form_submit_button("Commit Alterations Sheet", use_container_width=True):
                    supabase.table("users").update({
                        "username": e_user.strip(), "first_name": e_first.strip(), "last_name": e_last.strip(), 
                        "email": e_mail.strip(), "cell_phone": e_cell.strip(), "is_admin": edit_is_admin, "notes": edit_notes.strip()
                    }).eq("id", selected_user["id"]).execute()
                    
                    # 🚀 THE ABSOLUTE FIX: Bypasses library wrapper limits to update auth passwords directly via REST
                    if forced_temp_pw.strip():
                        try:
                            auth_endpoint = f"{URL}/auth/v1/admin/users/{selected_user['id']}"
                            auth_headers = {
                                "Authorization": f"Bearer {KEY}",
                                "apikey": KEY,
                                "Content-Type": "application/json"
                            }
                            auth_payload = {"password": forced_temp_pw.strip()}
                            
                            import requests
                            auth_response = requests.put(auth_endpoint, json=auth_payload, headers=auth_headers)
                            
                            # Checks for valid success codes (200 OK or 201 Created)
                            if auth_response.status_code in:
                                supabase.table("users").update({"first_login_complete": False}).eq("id", selected_user["id"]).execute()
                            else:
                                st.error(f"⚠️ Auth Server rejected password update: {auth_response.text}")
                        except Exception as auth_ex:
                            st.error(f"⚠️ Identity Server Communication Failure: {str(auth_ex)}")

                        
                    supabase.table("tournament_registrations").upsert({"user_id": selected_user["id"], "game_type": "Main", "is_enrolled": m_en, "is_paid": m_pd}, on_conflict="user_id,game_type").execute()
                    supabase.table("tournament_registrations").upsert({"user_id": selected_user["id"], "game_type": "2nd_Chance", "is_enrolled": s_en, "is_paid": s_pd}, on_conflict="user_id,game_type").execute()
                    
                    st.success("Synchronized successfully!")
                    st.session_state.selected_mgmt_user = None
                    st.rerun()

# ==========================================
# 📂 TAB 3: APPLICATIONS & CSV UTILITIES
# ==========================================
with tab_csv:
    st.subheader("👥 Live Joining Applications Queue")
    requests = supabase.table("join_requests").select("*").eq("status", "Pending").execute().data
    
    if not requests: 
        st.info("Applications ledger is currently clear.")
    else:
        for req in requests:
            with st.container(border=True):
                c_inf, c_acc, c_rej = st.columns([4, 1, 1])
                with c_inf:
                    st.markdown(
                        f"""👤 **{req['username']}** ({req['first_name']} {req['last_name']}) <br>
                        🎯 Route Target: **{req['target_game']} Pool** <br>
                        📞 Contact: `{req['email']}` | `{req['cell_phone']}`""", 
                        unsafe_allow_html=True
                    )
                with c_acc:
                    if st.button("Approve ✔️", key=f"acc_{req['id']}", use_container_width=True):
                        try:
                            # Generate a fresh unique internal database ID for the player profile
                            gen_id = str(uuid.uuid4())
                            
                            # Onboard the primary profile record card
                            supabase.table("users").insert({
                                "id": gen_id, "username": req["username"], "first_name": req["first_name"], 
                                "last_name": req["last_name"], "email": req["email"], "cell_phone": req["cell_phone"], 
                                "first_login_complete": False
                            }).execute()
                            
                            # 🚀 AUTOMATED FORCED BYE INJECTION ENFORCEMENT ENGINE
                            for track in ["Main", "2nd_Chance"]:
                                is_target = (track == req["target_game"])
                                
                                # Check if joining during the exact second week of that pool's specific timeline
                                is_wk2_join = False
                                if track == "Main" and CALCULATED_CURRENT_WEEK == 2: 
                                    is_wk2_join = True
                                elif track == "2nd_Chance" and CALCULATED_CURRENT_WEEK == (sc_start + 1): 
                                    is_wk2_join = True
                                
                                # Setup initial bracket parameters
                                supabase.table("tournament_registrations").insert({
                                    "user_id": gen_id, "game_type": track, "bracket_status": "Loser Bracket", 
                                    "byes_used": 1 if (is_target and is_wk2_join) else 0,
                                    "is_enrolled": is_target, "is_paid": False
                                }).execute()
                                
                                # Burn their week 1 choice automatically with a hardlocked BYE selection row
                                if is_target and is_wk2_join:
                                    bye_target_week = 1 if track == "Main" else sc_start
                                    supabase.table("user_picks").insert({
                                        "user_id": gen_id, "game_type": track, "week": bye_target_week, 
                                        "team_picked": "BYE", "pick_state": "Finalized"
                                    }).execute()
                                    
                            supabase.table("join_requests").update({"status": "Approved"}).eq("id", req["id"]).execute()
                            st.success(f"Player {req['username']} onboarded cleanly!")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Failed to onboard applicant: {str(e)}")
                            
                with c_rej:
                    if st.button("Purge ❌", key=f"rej_{req['id']}", use_container_width=True):
                        supabase.table("join_requests").update({"status": "Rejected"}).eq("id", req["id"]).execute()
                        st.rerun()

    st.markdown("<hr style='margin:30px 0;'/>", unsafe_allow_html=True)
    st.subheader("📊 Legacy CSV Ingestion Utilities")

    # --- BULK SCHEDULE IMPORT ENGINE ---
    st.markdown("### 🏈 Bulk Import NFL Master Schedule")
    schedule_file = st.file_uploader("Choose nfl_schedule.csv File", type="csv", key="sched_upload")
    if schedule_file is not None:
        if st.button("🚀 Execute Schedule Database Overwrite", use_container_width=True):
            try:
                input_data = schedule_file.getvalue().decode("utf-8")
                reader = csv.DictReader(io.StringIO(input_data))
                synced_games = 0
                for row in reader:
                    if not row.get("week") or not row.get("away_team") or not row.get("home_team"):
                        continue
                    raw_time = row.get("kickoff_time", "").strip()
                    clean_time = None if raw_time == "" or raw_time.upper() == "TBD" else raw_time
                    
                    supabase.table("nfl_schedule").upsert({
                        "week": int(row["week"]), "away_team": row["away_team"].strip().upper()[:3],
                        "home_team": row["home_team"].strip().upper()[:3], "kickoff_time": clean_time
                    }, on_conflict="week,away_team,home_team").execute()
                    synced_games += 1
                st.success(f"Successfully loaded {synced_games} match lines into the database!")
                st.rerun()
            except Exception as e: 
                st.error(f"Schedule Parsing Failure: {str(e)}")

    st.markdown("---")

    # --- BULK USER IMPORT ENGINE (Fixed Secure Auth Mapping) ---
    st.markdown("### 👥 Bulk Import League Players")
    users_file = st.file_uploader("Choose league_users.csv File", type="csv", key="users_upload")
    if users_file is not None:
        if st.button("🚀 Execute Bulk Roster Onboarding", use_container_width=True):
            try:
                input_data = users_file.getvalue().decode("utf-8")
                reader = csv.DictReader(io.StringIO(input_data))
                onboarded_players = 0
                
                for row in reader:
                    # Guard line: Skip completely blank rows or missing core items
                    if not row.get("username") or not row.get("email"):
                        continue
                        
                    clean_email = row["email"].strip()
                    clean_username = row["username"].strip()
                    # Fallback to a default temporary password if left blank in the spreadsheet
                    temp_pw = row["temporary_password"].strip() if "temporary_password" in row and row["temporary_password"] else "Welcome2026!"
                    
                    # 1. 🚀 GENERATE CORE SECURE ACCOUNT INSIDE SUPABASE AUTH ENGINE
                    # This registers their password safely so they can log in instantly
                    try:
                        auth_user = supabase.auth.admin.create_user({
                            "email": clean_email,
                            "password": temp_pw,
                            "email_confirm": True  # Automatically verifies their email so they bypass activation screens
                        })
                        generated_uid = auth_user.user.id
                    except Exception as auth_err:
                        # If they already exist in the auth table, look up their ID to update details instead of crashing
                        if "already has been registered" in str(auth_err) or "already exists" in str(auth_err):
                            existing_user_data = supabase.table("users").select("id").eq("username", clean_username).execute().data
                            generated_uid = existing_user_data[0]["id"] if existing_user_data else str(uuid.uuid4())
                        else:
                            raise auth_err

                    # 2. Sync their data columns to your custom profile table using the matching generated ID
                    supabase.table("users").upsert({
                        "id": generated_uid, 
                        "username": clean_username, 
                        "first_name": row["first_name"].strip(),
                        "last_name": row["last_name"].strip(), 
                        "email": clean_email, 
                        "cell_phone": row["cell_phone"].strip(),
                        "is_admin": row["is_admin"].strip().upper() == "TRUE", 
                        "notes": row["notes"].strip() if "notes" in row and row["notes"] else "", 
                        "first_login_complete": False  # Triggers the forced password reset screen upon their first login!
                    }, on_conflict="username").execute()
                    
                    # 3. Establish their entries inside both tournament tracks automatically
                    m_en = row["main_enrolled"].strip().upper() == "TRUE" if "main_enrolled" in row else False
                    m_pd = row["main_paid"].strip().upper() == "TRUE" if "main_paid" in row else False
                    s_en = row["second_enrolled"].strip().upper() == "TRUE" if "second_enrolled" in row else False
                    s_pd = row["second_paid"].strip().upper() == "TRUE" if "second_paid" in row else False
                    
                    supabase.table("tournament_registrations").upsert({"user_id": generated_uid, "game_type": "Main", "bracket_status": "Loser Bracket", "byes_used": 0, "is_enrolled": m_en, "is_paid": m_pd}, on_conflict="user_id,game_type").execute()
                    supabase.table("tournament_registrations").upsert({"user_id": generated_uid, "game_type": "2nd_Chance", "bracket_status": "Loser Bracket", "byes_used": 0, "is_enrolled": s_en, "is_paid": s_pd}, on_conflict="user_id,game_type").execute()
                    onboarded_players += 1
                    
                st.success(f"Successfully batch-registered {onboarded_players} participant accounts into the authentication engine!")
                st.rerun()
            except Exception as e: 
                st.error(f"User Profile Roster Failure: {str(e)}")



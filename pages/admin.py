import streamlit as st
import requests
import os
import csv
import io
import uuid
import datetime
import time
from supabase import create_client, Client

# --- ST.SET_PAGE_CONFIG MUST BE THE ABSOLUTE FIRST DIRECTIVE ---
st.set_page_config(layout="wide")

# --- DATABASE SETUP ---
URL = st.secrets["SUPABASE_URL"]
KEY = st.secrets["SUPABASE_KEY"]
supabase: Client = create_client(URL, KEY)
API_KEY = st.secrets.get("THE_ODDS_API_KEY", "YOUR_FREE_API_KEY")

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
    # local_sidebar_logo = "static/loser-logo.png"
    # if os.path.exists(local_sidebar_logo):
        # st.image(local_sidebar_logo, use_container_width=True)
    # else:
        # st.image("https://espncdn.com", use_container_width=True)
        
    st.markdown("<hr style='margin:10px 0 15px 0; border:0; border-top:1px solid #cbd5e1;'/>", unsafe_allow_html=True)
    
    game_mode = st.selectbox("Select Pool", ["Main", "2nd Chance"])
    game_slug = "Main" if game_mode == "Main" else "2nd_Chance"
    
    week_options = []
    for w in range(1, 23):
        base_label = get_week_label(w)
        if w == CALCULATED_CURRENT_WEEK: week_options.append(f"{base_label} (current)")
        else: week_options.append(base_label)
            
    selected_week_label = st.selectbox("Select Week", options=week_options, index=CALCULATED_CURRENT_WEEK - 1)
    clean_label = selected_week_label.replace(" (current)", "")
    
    if "Wildcard" in clean_label: SELECTED_WEEK = 19
    elif "Divisional" in clean_label: SELECTED_WEEK = 20
    elif "Conference" in clean_label: SELECTED_WEEK = 21
    elif "Super Bowl" in clean_label: SELECTED_WEEK = 22
    SELECTED_WEEK = int(clean_label.split(" ")[1])
    
    st.page_link("app.py", label="Picks")
    st.page_link("pages/overview.py", label="Overview")
    st.page_link("pages/chat.py", label="Banter")
    st.page_link("pages/rules.py", label="Rules")
    st.page_link("pages/admin.py", label="Admin")

# --- DYNAMIC SIDEBAR BACKGROUND COLOR ENGINE ---
sidebar_bg = "#1d3d70" if game_slug == "Main" else "#974706"
st.markdown(f"<style>[data-testid='stSidebar'] {{ background-color: {sidebar_bg} !important; }} [data-testid='stSidebar'] .stText, [data-testid='stSidebar'] p, [data-testid='stSidebar'] h3, [data-testid='stSidebar'] label {{ color: #ffffff !important; }} [data-testid='stSidebar'] div[data-baseweb='select'] div {{ color: #1e293b !important; }}</style>", unsafe_allow_html=True)

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

# Verify current user holds administrator access clearances before displaying forms
current_user = st.session_state.get("user", None)
is_authenticated_admin = False
if current_user:
    user_record = supabase.table("users").select("is_admin").eq("id", current_user.id).execute().data
    if user_record and user_record[0].get("is_admin", False): is_authenticated_admin = True

if not is_authenticated_admin and not st.toggle("🧪 Bypassing Admin Check for Staging/Testing"):
    st.error("🔒 Access blocked. This panel is reserved exclusively for the League Commissioner.")
    st.stop()

tab_scores, tab_users, tab_csv = st.tabs(["Game Processing", "Manage Users", "Bulk CSV Import"])

# ==========================================
# TAB 1: GAME PROCESSING
# ==========================================
with tab_scores:
    st.info("Select the LOSER (or TIE) and specify SHUTOUT if applicable for each game below followed by Lock & Compute to update the Overview.")
    schedule_res = supabase.table("nfl_schedule").select("*").eq("week", SELECTED_WEEK).execute().data

    if not schedule_res:
        st.info(f"No games loaded for {get_week_label(SELECTED_WEEK)} yet. Head to the Bulk CSV Import tab to upload your schedule.")
    else:
        for match in schedule_res:
            match_id = match["id"]
            away, home = match["away_team"].upper(), match["home_team"].upper()
            
            with st.container(border=True):
                col_match, col_loser, col_shutout, col_action = st.columns([2.5, 2, 1.5, 1.5])
                with col_match:
                    st.markdown(f'<div style="padding-top:10px; font-family:sans-serif; font-size:14px;"><b>{away}</b> <span style="color:gray;">@</span> <b>{home}</b></div>', unsafe_allow_html=True)
                with col_loser:
                    loser_selection = st.radio("Loser:", options=[away, home, "TIE"], index=None, key=f"loser_{match_id}", horizontal=True, label_visibility="collapsed")
                with col_shutout:
                    is_so = st.checkbox("Shutout", key=f"so_{match_id}")
                with col_action:
                    if st.button("Lock & Compute", key=f"lock_{match_id}", use_container_width=True):
                        if loser_selection is None: st.error("Select loser first!")
                        else:
                            with st.spinner("Processing player picks..."):
                                supabase.table("nfl_schedule").update({"loser": loser_selection, "is_shutout": is_so}).eq("id", match_id).execute()
                                active_picks = supabase.table("user_picks").select("*").eq("game_type", game_slug).eq("week", SELECTED_WEEK).in_("team_picked", [away, f"{away}_SO", home, f"{home}_SO"]).execute().data
                                
                                for pick in active_picks:
                                    chosen_team = pick["team_picked"].replace("_SO", "")
                                    pick_result = "Incorrect" if loser_selection == "TIE" else "Correct" if chosen_team != loser_selection else "Incorrect"
                                    final_team_name = f"{chosen_team}_SO" if pick_result == "Correct" and is_so else pick["team_picked"]
                                    supabase.table("user_picks").update({"pick_state": pick_result, "team_picked": final_team_name}).eq("id", pick["id"]).execute()
                                    
                                    all_user_picks = supabase.table("user_picks").select("*").eq("game_type", game_slug).eq("user_id", pick["user_id"]).execute().data
                                    wrong_count = sum(1 for p in all_user_picks if p["pick_state"] == "Incorrect")
                                    new_bracket = "Loser Bracket" if wrong_count == 0 else "Winner Bracket" if wrong_count == 1 else "Eliminated"
                                    supabase.table("tournament_registrations").update({"bracket_status": new_bracket}).eq("user_id", pick["user_id"]).eq("game_type", game_slug).execute()
                                st.success("Results evaluated and locked!")
                                time.sleep(3)
                                st.rerun()

# ==========================================
# TAB 2: MANAGE USERS
# ==========================================
with tab_users:
    st.subheader("Manage Users")
    
    all_users = supabase.table("users").select("*").order("username").execute().data
    all_regs = supabase.table("tournament_registrations").select("*").eq("game_type", game_slug).execute().data
    regs_map = {r["user_id"]: r for r in all_regs}
    
    col_user_list, col_user_edit = st.columns(2)
    
    with col_user_list:
        st.markdown(f"### Current Players ({game_mode} Status View)")
        if not all_users: st.info("No registered users inside database.")
        else:
            for u in all_users:
                # FIX: Appends status context badges (Paid/Unpaid/Not Enrolled) dynamically to select menu options
                u_reg = regs_map.get(u["id"], None)
                if not u_reg or not u_reg.get("is_enrolled", False): status_badge = "🚫 [Not Enrolled]"
                elif u_reg.get("is_paid", False): status_badge = "💲 [Paid]"
                else: status_badge = "❌ [UNPAID]"
                
                admin_label = " ⭐ [ADMIN]" if u.get("is_admin", False) else ""
                display_text = f"{u['username']} &bull; {u.get('first_name','') or ''} {u.get('last_name','') or ''} {admin_label} {status_badge}"
                
                if st.button(display_text, key=f"select_user_{u['id']}", use_container_width=True):
                    st.session_state.selected_mgmt_user = u
                    st.rerun()

    with col_user_edit:
        st.markdown("### 🖋️ Profile Profile Editor Sheet")
        selected_user = st.session_state.get("selected_mgmt_user", None)
        
        if not selected_user: st.info("Select a player from the left panel to edit profile details.")
        else:
            # Recover individual registration rows for both tracks to toggle explicitly inside form rows
            main_reg = supabase.table("tournament_registrations").select("*").eq("user_id", selected_user["id"]).eq("game_type", "Main").execute().data
            sec_reg = supabase.table("tournament_registrations").select("*").eq("user_id", selected_user["id"]).eq("game_type", "2nd_Chance").execute().data
            
            mr = main_reg[0] if main_reg else {"is_enrolled": False, "is_paid": False}
            sr = sec_reg[0] if sec_reg else {"is_enrolled": False, "is_paid": False}

            with st.form("edit_player_form"):
                st.markdown(f"Username: **{selected_user['username']}**")
                edit_first = st.text_input("First Name", value=selected_user.get("first_name") or "")
                edit_last = st.text_input("Last Name", value=selected_user.get("last_name") or "")
                edit_email = st.text_input("Email Address", value=selected_user.get("email") or "")
                edit_cell = st.text_input("Cell Phone", value=selected_user.get("cell_phone") or "")
                edit_is_admin = st.checkbox("Grant Admin", value=selected_user.get("is_admin", False))
                edit_notes = st.text_area("Notes", value=selected_user.get("notes") or "")
                
                st.markdown("---")
                st.markdown("#### Main Access Settings")
                m_enroll = st.checkbox("Enrolled in Main", value=mr.get("is_enrolled", False))
                m_paid = st.checkbox("Main Fees Paid", value=mr.get("is_paid", False))
                
                st.markdown("#### 2nd Chance Access Settings")
                s_enroll = st.checkbox("Enrolled in 2nd Chance", value=sr.get("is_enrolled", False))
                s_paid = st.checkbox("2nd Chance Fees Paid", value=sr.get("is_paid", False))
                
                if st.form_submit_button("Commit Changes to Database", use_container_width=True):
                    supabase.table("users").update({
                        "first_name": edit_first.strip(), "last_name": edit_last.strip(), "email": edit_email.strip(),
                        "cell_phone": edit_cell.strip(), "is_admin": edit_is_admin, "notes": edit_notes.strip()
                    }).eq("id", selected_user["id"]).execute()
                    
                    supabase.table("tournament_registrations").upsert({"user_id": selected_user["id"], "game_type": "Main", "is_enrolled": m_enroll, "is_paid": m_paid}, on_conflict="user_id,game_type").execute()
                    supabase.table("tournament_registrations").upsert({"user_id": selected_user["id"], "game_type": "2nd_Chance", "is_enrolled": s_enroll, "is_paid": s_paid}, on_conflict="user_id,game_type").execute()
                    
                    st.success("Database records synchronized successfully!")
                    time.sleep(3)
                    st.session_state.selected_mgmt_user = None
                    st.rerun()

# ==========================================
# TAB 3: BULK CSV IMPORT
# ==========================================
with tab_csv:
    st.subheader("Bulk CSV Import")
    
    st.markdown("### Import NFL Master Schedule")
    schedule_file = st.file_uploader("Choose nfl_schedule.csv File", type="csv", key="sched_upload")
    if schedule_file is not None:
        if st.button("Execute Schedule Database Update", use_container_width=True):
            try:
                input_data = schedule_file.getvalue().decode("utf-8")
                reader = csv.DictReader(io.StringIO(input_data))
                synced_games = 0
                for row in reader:
                    supabase.table("nfl_schedule").upsert({
                        "week": int(row["week"]), "away_team": row["away_team"].strip().upper()[:3],
                        "home_team": row["home_team"].strip().upper()[:3], "kickoff_time": row["kickoff_time"].strip()
                    }, on_conflict="week,away_team,home_team").execute()
                    synced_games += 1
                st.success(f"Successfully loaded {synced_games} NFL games into the database!")
                time.sleep(3)
                st.rerun()
            except Exception as e: st.error(f"Schedule Parsing Failure: {str(e)}")

    st.markdown("<hr style='margin:25px 0;'/>", unsafe_allow_html=True)

    st.markdown("### Import Users")
    users_file = st.file_uploader("Choose league_users.csv File", type="csv", key="users_upload")
    if users_file is not None:
        if st.button("Execute Roster Onboarding Routine", use_container_width=True):
            try:
                input_data = users_file.getvalue().decode("utf-8")
                reader = csv.DictReader(io.StringIO(input_data))
                onboarded_players = 0
                for row in reader:
                    existing = supabase.table("users").select("id").eq("username", row["username"].strip()).execute().data
                    generated_uid = existing[0]["id"] if existing else str(uuid.uuid4())
                    
                    supabase.table("users").upsert({
                        "id": generated_uid, "username": row["username"].strip(), "first_name": row["first_name"].strip(),
                        "last_name": row["last_name"].strip(), "email": row["email"].strip(), "cell_phone": row["cell_phone"].strip(),
                        "is_admin": row["is_admin"].strip().upper() == "TRUE", "notes": row["notes"].strip() if "notes" in row and row["notes"] else "", "first_login_complete": False
                    }, on_conflict="username").execute()
                    
                    # 🚀 FIX: Maps the newly split spreadsheet columns directly to the individual tournament trackers
                    m_en = row["main_enrolled"].strip().upper() == "TRUE" if "main_enrolled" in row else False
                    m_pd = row["main_paid"].strip().upper() == "TRUE" if "main_paid" in row else False
                    s_en = row["second_enrolled"].strip().upper() == "TRUE" if "second_enrolled" in row else False
                    s_pd = row["second_paid"].strip().upper() == "TRUE" if "second_paid" in row else False
                    
                    supabase.table("tournament_registrations").upsert({"user_id": generated_uid, "game_type": "Main", "bracket_status": "Loser Bracket", "byes_used": 0, "is_enrolled": m_en, "is_paid": m_pd}, on_conflict="user_id,game_type").execute()
                    supabase.table("tournament_registrations").upsert({"user_id": generated_uid, "game_type": "2nd_Chance", "bracket_status": "Loser Bracket", "byes_used": 0, "is_enrolled": s_en, "is_paid": s_pd}, on_conflict="user_id,game_type").execute()
                    onboarded_players += 1
                    
                st.success(f"Successfully loaded {onboarded_players} profiles with split enrollment tracking parameters!")
                st.rerun()
            except Exception as e: st.error(f"User Profile Roster Failure: {str(e)}")

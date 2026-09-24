import random
import uuid
import streamlit as st
from supabase import create_client, Client
import os
import datetime

st.set_page_config(layout="wide")

# Initialize database connections
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
        st.page_link("pages/seed_data.py", label="Seed Data")
    
    st.markdown("<hr style='margin:10px 0 15px 0; border:0; border-top:1px solid rgba(255,255,255,0.3);'/>", unsafe_allow_html=True)
    
    # Basic navigation paths open to every pool player
    st.page_link("http://www.espn.com/nfl/schedulegrid", label="ESPN NFL Schedule Grid")
    st.page_link("https://www.espn.com/nfl/odds", label="ESPN Odds")
    st.page_link("https://www.espn.com/nfl/fpi", label="ESPN Power Index")
    
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

def seed_pool_database():
    st.write("⏳ Commencing data seeding operation...")

    # --- 1. INSERT MOCK WEEKLY SCHEDULE LINES ---
    mock_games = [
        # Week 1 Schedule Matrix
        {"week": 1, "away_team": "BUF", "home_team": "KC", "kickoff_time": "2026-09-10T20:20:00Z", "espn_favored_team": "KC", "espn_favored_tier": 3.5, "winner": "KC", "is_shutout": False},
        {"week": 1, "away_team": "DET", "home_team": "SF", "kickoff_time": "2026-09-13T13:00:00Z", "espn_favored_team": "SF", "espn_favored_tier": 7.0, "winner": "DET", "is_shutout": True}, 
        {"week": 1, "away_team": "DAL", "home_team": "PHI", "kickoff_time": "2026-09-13T16:25:00Z", "espn_favored_team": "PHI", "espn_favored_tier": 2.5, "winner": "TIE", "is_shutout": False},
        
        # Week 2 Schedule Matrix
        {"week": 2, "away_team": "MIA", "home_team": "BUF", "kickoff_time": "2026-09-17T20:15:00Z", "espn_favored_team": "BUF", "espn_favored_tier": 6.0, "winner": None, "is_shutout": False},
        {"week": 2, "away_team": "BAL", "home_team": "CIN", "kickoff_time": "2026-09-20T13:00:00Z", "espn_favored_team": "BAL", "espn_favored_tier": 1.5, "winner": None, "is_shutout": False},
        {"week": 2, "away_team": "NYG", "home_team": "WAS", "kickoff_time": "2026-09-20T13:00:00Z", "espn_favored_team": "WAS", "espn_favored_tier": 3.0, "winner": None, "is_shutout": False}
    ]
    
    for game in mock_games:
        # FIX: Check if game exists by week and away_team to prevent duplication instead of risking constraint errors
        existing_game = supabase.table("nfl_schedule").select("id").eq("week", game["week"]).eq("away_team", game["away_team"]).execute().data
        if existing_game:
            supabase.table("nfl_schedule").update(game).eq("id", existing_game[0]["id"]).execute()
        else:
            supabase.table("nfl_schedule").insert(game).execute()
            
    st.success("Mock schedule lines mapped.")

    # --- 2. GENERATE DUMMY PLAYERS & REGISTER TO BRACKETS ---
    dummy_names = ["Stephen King", "Amanda Conley", "Bill Kazmierski", "John Doe", "Jane Smith", "Bob Miller", "Alice Vance", "Charlie Brown", "David Davis", "Eva Elks"]
    teams_pool = ["BUF", "KC", "DET", "SF", "DAL", "PHI", "MIA", "BAL", "CIN", "WAS"]

    for name in dummy_names:
        fake_uid = str(uuid.uuid4())
        
        # Check if user already exists under this username to avoid duplicate entry constraint failures
        existing_user = supabase.table("users").select("id").eq("username", name).execute().data
        if existing_user:
            fake_uid = existing_user[0]["id"]
        else:
            supabase.table("users").insert({"id": fake_uid, "username": name}).execute()
        
        for track in ["Main", "2nd_Chance"]:
            # FIX: Cleaned up ON CONFLICT behavior to match the explicit primary key
            supabase.table("tournament_registrations").upsert({
                "user_id": fake_uid,
                "game_type": track,
                "bracket_status": "Loser Bracket",
                "byes_used": 0
            }, on_conflict="user_id,game_type").execute()
            
            # Clear old mock selections for this user/track combo to allow clean re-runs
            supabase.table("user_picks").delete().eq("user_id", fake_uid).eq("game_type", track).execute()
            
            # --- 3. GENERATE RANDOM PICK CHOICES FOR W1 & W2 ---
            w1_pick = random.choice(teams_pool[:6])
            w1_state = "Correct" if w1_pick not in ["KC", "DET"] else "Incorrect" 
            if w1_pick == "SF" and w1_state == "Correct": 
                w1_pick = "SF_SO" 
                
            supabase.table("user_picks").insert({
                "user_id": fake_uid, "game_type": track, "week": 1, "team_picked": w1_pick, "pick_state": w1_state
            }).execute()

            w2_pick = random.choice([t for t in teams_pool if t != w1_pick.replace("_SO", "")])
            w2_state = random.choice(["Confirmed", "Finalized"])
            
            supabase.table("user_picks").insert({
                "user_id": fake_uid, "game_type": track, "week": 2, "team_picked": w2_pick, "pick_state": w2_state
            }).execute()
            
        # Update dynamic player bracket totals based on outcomes generated above
        for track in ["Main", "2nd_Chance"]:
            user_picks = supabase.table("user_picks").select("*").eq("user_id", fake_uid).eq("game_type", track).execute().data
            wrongs = sum(1 for p in user_picks if p["pick_state"] == "Incorrect")
            
            status = "Loser Bracket" if wrongs == 0 else "Winner Bracket" if wrongs == 1 else "Eliminated"
            supabase.table("tournament_registrations").update({"bracket_status": status}).eq("user_id", fake_uid).eq("game_type", track).execute()

    st.success("Seeding routine complete! Open your Overview dashboard to view the generated testing parameters.")

if __name__ == "__main__":
    if st.button("Trigger Seed Script Execution"):
        seed_pool_database()

import random
import uuid
import streamlit as st
from supabase import create_client, Client
import os

# Initialize database connections
URL = st.secrets["SUPABASE_URL"]
KEY = st.secrets["SUPABASE_KEY"]
supabase: Client = create_client(URL, KEY)

st.set_page_config(layout="wide")

# --- CUSTOM SIDEBAR CONFIGURATION ---
with st.sidebar:
    # 1. Main Game Mode Selector
    game_mode = st.selectbox("Select Pool", ["Main", "2nd Chance"])
    game_slug = "Main" if game_mode == "Main" else "2nd_Chance"
    CURRENT_WEEK = 2  

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
        
    st.markdown("<hr style='margin:10px 0 15px 0; border:0; border-top:1px solid rgba(255,255,255,0.3);'/>", unsafe_allow_html=True)
    
    # 3. Streamlit Standard Page Routing Links Matrix
    st.page_link("app.py", label="Picks")
    st.page_link("pages/overview.py", label="Results")
    st.page_link("pages/chat.py", label="Chat")
    st.page_link("pages/rules.py", label="Rules")
    st.page_link("pages/admin.py", label="Admin")
    st.page_link("pages/seed_data.py", label="Seed Data")
    
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
                2026 NFL Loser Pool &bull; {game_mode} &bull; Week {CURRENT_WEEK}
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

    st.success("Seeding routine complete! Open your Results dashboard to view the generated testing parameters.")

if __name__ == "__main__":
    if st.button("Trigger Seed Script Execution"):
        seed_pool_database()

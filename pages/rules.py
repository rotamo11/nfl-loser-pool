import streamlit as st
from supabase import create_client, Client
import os
import datetime

st.set_page_config(layout="wide")

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

st.header("Official Pool Rules & Details")
st.markdown("---")

# --- SECTION 1: CORE GAMEPLAY ---
st.subheader("Weekly Pick Requirements")
st.markdown(
    """
    * **Weeks 1–14:** Select exactly **one team** per week that you think will **lose** their game.
    * **Weeks 15–18:** Select exactly **two teams** per week to lose (byes are completed).
    * **The Playoffs:** Select the **loser of every single game** scheduled for that weekend.
    * **The Bye Option:** You may choose to use **one seasonal bye** at any time (Regular Season or Playoffs) instead of picking a team. A bye only covers one single game slot during multi-pick weeks.
    """
)

# --- SECTION 2: DEADLINES & FALLBACKS ---
st.subheader("Deadlines & Auto-Fallbacks")
st.markdown(
    """
    * **Submission Deadline:** Picks must be finalized by **NOON Eastern Time on Sunday**, or by kickoff time if your chosen team plays an earlier game (e.g., Thursday/Saturday).
    * **Missing a Deadline:** If you fail to submit on time, the system will apply auto-fallbacks in this order:
        1. Burn your seasonal **Bye** (if available).
        2. Assign you the **highest favored team available** to you that hasn't played yet based on live ESPN Odds (with the ESPN Power Index used as a tiebreaker if needed). 
    * **Late Joiners:** Players can join the Main or 2nd Chance game **one week late** by automatically burning their bye for the missed week. Early in the season, late additions can pick any team whose game has not started yet.
    """
)

# --- SECTION 3: BRACKETS & SELECTION RESTRICTIONS ---
st.subheader("Brackets, Striking, & Repeat Picks")
st.markdown(
    """
    * **Double Elimination Brackets:**
        * **Loser's Bracket:** Everyone starts here with 0 wrong picks.
        * **Winner's Bracket:** Moving here occurs after your **first wrong pick** (or if your chosen team ends in a **Tie**).
        * **Elimination:** A second wrong pick results in complete elimination from the tournament.
    * **Regular Season Repeat Picks:** You cannot pick the same team more than once. If you accidentally submit a duplicate, you can fix it before the weekly deadline.
    * **The Shutout Exception:** If you correctly pick a team that gets **shut out (loses without scoring)**, you earn the right to pick them **one more time** later in the regular season. A 0-0 tie counts as a shutout, but not a correct pick since neither team lost.
    * **Playoff Repeat Picks:** Repeat selection restrictions are completely turned off once the playoffs begin.
    """
)

# --- SECTION 4: PRIZES & TIEBREAKERS ---
st.subheader("Purse Distribution & Tiebreaker Hierarchy")

# Render Prize Table Matrix
st.markdown("### Purse Split ($1,850 Total across 74 Players)")
st.table({
    "Rank Place": ["1st Place", "2nd Place", "3rd Place"],
    "Payout Percentage": ["60%", "30%", "10%"],
    "Cash Amount": ["$1,110.00", "$555.00", "$185.00"]
})

# Render Tiebreaker Sequential Numbered List
st.markdown("### Tiebreaker Sequence")
st.markdown(
    """
    If multiple players qualify for a prize spot at the end of the year, ties are broken using this strict sequence:
    1. **Fewest Wrong:** The player with the fewest total losses all year wins.
    2. **Saved the Bye:** A player who finished the year without using their bye beats a player who used it.
    3. **Head-to-Head:** Continue tracking head-to-head picks as long as games remain.
    4. **Side Agreement:** Players can negotiate a separate bet or choose to split the cash evenly.
    5. **Super Bowl Points:** Whoever guesses closest to the **combined total points** scored in the Super Bowl without going over wins. If everyone goes over, it goes to whoever is closest.
    6. **Even Split:** Cash is split evenly if a tie remains after the Super Bowl.
    """
)
st.caption("*Note: Super Bowl combined point totals are only gathered and evaluated if a tiebreaker becomes absolutely necessary to protect the spirit of the game.*")

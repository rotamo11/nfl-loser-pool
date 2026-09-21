import streamlit as st
import os

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
    # st.markdown("<h3 style='margin:0 0 10px 0; font-size:14px;'>Menu</h3>", unsafe_allow_html=True)
    
    # 3. Streamlit Standard Page Routing Links Matrix
    st.page_link("app.py", label="Picks")
    st.page_link("pages/overview.py", label="Results")
    st.page_link("pages/chat.py", label="Smack")
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
    # st.html(f"<h1 style='margin:0; font-weight:900; font-size:32px; letter-spacing:-1px;'>2026 NFL Loser Pool &bull; {game_mode} &bull; Week {CURRENT_WEEK}</h1>")
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

st.title("Official Pool Rules & Details")
st.markdown("---")

# --- SECTION 1: CORE GAMEPLAY ---
st.header("Weekly Pick Requirements")
st.markdown(
    """
    * **Weeks 1–14:** Select exactly **one team** per week that you think will **lose** their game.
    * **Weeks 15–18:** Select exactly **two teams** per week to lose (byes are completed).
    * **The Playoffs:** Select the **loser of every single game** scheduled for that weekend.
    * **The Bye Option:** You may choose to use **one seasonal bye** at any time (Regular Season or Playoffs) instead of picking a team. A bye only covers one single game slot during multi-pick weeks.
    """
)

# --- SECTION 2: DEADLINES & FALLBACKS ---
st.header("Deadlines & Auto-Fallbacks")
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
st.header("Brackets, Striking, & Repeat Picks")
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
st.header("Purse Distribution & Tiebreaker Hierarchy")

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

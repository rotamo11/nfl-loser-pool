import streamlit as st
import os

# 2. Main Navigation & Persistent Mode Toggles
game_mode = st.sidebar.selectbox("Select Pool Tournament", ["Main Pool", "2nd Chance Game"])
game_slug = "Main" if game_mode == "Main Pool" else "2nd_Chance"

# Core Configuration State Parameters
current_week = 2  # Increment this as the season rolls forward

# --- 1. BRAND HEADER DISPLAY MATRICES ---
# Split the row into two columns for your logo image and title text alignment
header_col1, header_col2 = st.columns([1, 6])

with header_col1:
    # Load your local logo file safely using the guaranteed native image tool
    st.image("static/loser-logo.png", width=200)
with header_col2:
    st.markdown(
        f"""
        <div style="padding:10px; border-radius:8px; color:white; margin-bottom:12px; font-family:sans-serif;">
            <h1 style="margin:0; font-weight:900; letter-spacing:-1px;">2026 NFL Loser Pool &bull; {game_mode} &bull; Week {current_week}</h1>
            <div style="display:grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap:10px; font-size:14px; margin-bottom:12px; margin-top:12px; opacity:0.9;">
                <div><b>Through Week 14:</b> Pick 1 team to lose each week</div>
                <div><b>Weeks 15-18:</b> Pick 2 teams to lose each week</div>
                <div><b>Playoffs:</b> Pick loser of ALL games (Repeats allowed)</div>
            </div>
            <div style="display:grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap:10px; font-size:14px; margin-bottom:12px; margin-top:12px; opacity:0.9;">
                <div><b>Weekly Deadline:</b> Noon ET Sunday or by kickoff if taking an earlier game</div>
            </div>
            <div style="margin-top:12px; padding-top:8px; border-top:1px solid #1e3a8a; font-family:monospace; font-size:11.5px; color:#93c5fd;">
                74 Players | $1850 Purse ($1110 1st / $555 2nd / $185 3rd) | Last year's losers: Stephen King took 1st for $765, Amanda Conley took 2nd for $382.50, Bill Kazmierski took 3rd for $127.50
            </div>
        </div>
        """, 
        unsafe_allow_html=True
    )

# Optional sidebar text details can still be appended below the links if desired
with st.sidebar:
    st.markdown("<div style='text-align:center; color:gray; font-size:11px;'>2026 Commissioner Portal</div>", unsafe_allow_html=True)

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

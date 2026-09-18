import streamlit as st
import os

# --- PERSISTENT SIDEBAR LOGO ---
# st.logo pins the image to the top of the sidebar above the automatic page routes
local_logo_path = "static/nfl-logo-square.png"
if os.path.exists(local_logo_path):
    st.logo(local_logo_path, icon_image=local_logo_path)
else:
    # Stable fallback CDN if the repository hasn't finished building
    st.logo("https://espncdn.com")

st.markdown(
    """
    <style>
        /* Target Streamlit's internal visual container wrapper for the sidebar logo */
        [data-testid="stLogo"] {
            height: 190px !important;  /* Bumps the bounding height constraint up */
            width: 190px !important;
            max-width: 100% !important;
        }
        /* Target the actual logo image element itself */
        [data-testid="stLogo"] img {
            height: 190px !important;   /* Adjust this pixel value to make it smaller or larger */
            width: 190px !important;
            object-fit: contain;
        }
        /* Optional: Add a clean structural cushion space between the enlarged logo and links */
        [data-testid="stSidebarNav"] {
            margin-top: 15px !important;
        }
    </style>
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

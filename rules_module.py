from nicegui import ui

def render_rules_view(pool_slug: str):
    is_2nd = (pool_slug == "2nd_Chance")

    ui.label("2026 Official NFL Loser Pool Rules").classes("text-2xl font-black mb-1")
    ui.label("Pick team(s) you think will LOSE each week. If they win or tie, it is considered a wrong pick.").classes("text-sm font-semibold opacity-80 mb-4")

    sections = [
        ("1. Weekly Pick Requirements", [
            "**Weeks 1–14:** Pick **1 team** to lose each week.",
            "**Weeks 15–18:** Pick **2 teams** to lose each week.",
            "**Playoffs (Wildcard through Super Bowl):** Pick **ALL losers** for every playoff game each week (repeats allowed).",
            "**No Repeat Picks (Regular Season):** During Weeks 1–18, you cannot pick the same team twice unless you earned a Shutout Bonus on that team.",
        ]),
        ("2. Deadlines & Auto-Locks", [
            "**Standard Deadline:** Sunday at **12:00 PM ET**.",
            "**Early Games (Thursday, Friday, Saturday, International):** Picks involving an early game lock at that specific game's kickoff and automatically finalize.",
            "**Confirmed vs. Finalized:** A **Confirmed** pick is saved to the database, remains editable until kickoff, and keeps opponents' current-week picks hidden. A **Finalized** pick is permanently locked and reveals opponents' picks for that week.",
        ]),
        ("3. Elimination & Bracket Format", [
            "**Main Pool (Double Elimination):** Everyone starts in the **Loser Bracket** (0 wrong). Your first incorrect pick moves you to the **Winner Bracket** (1 wrong). A second incorrect pick eliminates you.",
            "**2nd Chance Pool (Single Elimination):** Begins in Week 6. One incorrect pick immediately eliminates you.",
            "**Ties:** A tie counts as an incorrect pick (wrong).",
        ]),
        ("4. Season BYE & Shutout Bonus", [
            "**One Season BYE:** Each player receives **1 BYE** per pool, which can either be used during the regular season (Weeks 1–18) or the playoffs. Using your BYE safely advances you without requiring a pick. Please note that a BYE only covers a single matchup; during multi-matchup weeks, you must still pick a loser for the remaining games.",
            "**Shutout Bonus (🎯):** If the team you pick to lose is shut out (scores 0 points), the Commissioner awards a **Shutout Bonus**, unlocking that team so you can pick them to lose **one more time** later in the season.",
        ]),
        ("5. Entry Fees & Payout Breakdown", [
            "**Main Pool ($25 Entry • 74 Players • $1,850 Purse):** 1st Place: **$1,110** (60%) • 2nd Place: **$555** (30%) • 3rd Place: **$185** (10%).",
            "**2nd Chance Pool ($25 Entry • 26 Players • $650 Purse):** 1st Place: **$390** (60%) • 2nd Place: **$195** (30%) • 3rd Place: **$65** (10%).",
            "**Tiebreakers:** If multiple players are eliminated in the same final week, the remaining prize money is split evenly unless broken by the following tiebreakers. To avoid splitting prizes among qualifying players, tiebreakers are applied in this order:", [
                "**Fewest Wrong Picks:** The player with fewer incorrect picks across the entire season wins.",
                "**Unused Bye:** A player who did not use their bye wins over a player who used theirs.",
                "**Continue Head-to-Head:** Tied players continue picking head-to-head until a winner is determined for as long as there are games remaining in the season.",
                "**Player Agreement:** Tied players may agree to settle the tie privately (such as making a side bet or voluntarily agreeing to split the winnings).",
                "**Super Bowl Combined Points:** The player whose prediction is closest to the final combined score of the Super Bowl without going over wins (if all tied players go over, the player closest to the final total wins).",
                "**Even Split:** If the Super Bowl concludes and the tie is still unbroken, the remaining prize money is split evenly.",
            ]
        ]),
    ]

    with ui.column().classes("w-full gap-3"):
        for title, bullets in sections:
            with ui.card().classes("w-full p-4 border border-slate-200 dark:border-slate-700 shadow-none"):
                ui.label(title).classes("text-base font-extrabold mb-1.5")
                for b in bullets:
                    ui.markdown(f"- {b}").classes("text-xs md:text-sm leading-relaxed my-0.5")

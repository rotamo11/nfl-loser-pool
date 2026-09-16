import streamlit as st
from supabase import create_client, Client

# Initialize database connection context
URL = st.secrets["SUPABASE_URL"]
KEY = st.secrets["SUPABASE_KEY"]
supabase: Client = create_client(URL, KEY)

st.set_page_config(layout="wide")

# Determine active tournament mode filter ruleset
game_mode = st.sidebar.selectbox("🎯 Select Pool Tournament", ["Main Pool", "2nd Chance Game"])
game_slug = "Main" if game_mode == "Main Pool" else "2nd_Chance"
current_week = 2  # Manually advance this index as the season rolls on

# --- 1. BRAND HEADER DISPLAY MATRICES ---
st.markdown(
    f"""
    <div style="background-color:#000080; padding:20px; border-radius:8px; color:white; margin-bottom:20px;">
        <h1 style="margin:0; font-weight:900; letter-spacing:-1px;">2026 NFL LOSER POOL — {game_mode.upper()}</h1>
        <div style="display:grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap:10px; font-size:12px; margin-top:10px; opacity:0.9;">
            <div>• <b>Through Week 14:</b> Pick 1 team to lose each week</div>
            <div>• <b>Weeks 15-18:</b> Pick 2 teams to lose each week</div>
            <div>• <b>Playoffs:</b> Pick loser of ALL games (Repeats allowed)</div>
            <div>• <b>Deadlines:</b> NOON ET Sunday or game kickoff time</div>
        </div>
        <div style="margin-top:12px; padding-top:8px; border-top:1px solid #1e3a8a; font-family:monospace; font-size:11px; color:#93c5fd;">
            74 Players | $1850 Purse ($1110 1st / $555 2nd / $185 3rd) | Historical: S. King took 1st for $765
        </div>
    </div>
    """, 
    unsafe_allow_html=True
)

# --- 2. RETRIEVE LEAGUE AND SELECTION DATA ---
users_res = supabase.table("users").select("*").execute().data
regs_res = supabase.table("tournament_registrations").select("*").eq("game_type", game_slug).execute().data
picks_res = supabase.table("user_picks").select("*").eq("game_type", game_slug).execute().data

# Mock Session Control verification guard rails
logged_in_uid = st.session_state.get("user", type("Obj", (object,), {"id": None})()).id
user_current_pick = next((p for p in picks_res if p["user_id"] == logged_in_uid and p["week"] == current_week), None)
user_is_eliminated = any(r for r in regs_res if r["user_id"] == logged_in_uid and r["bracket_status"] == "Eliminated")

# Security Rule: Users can only see live boards if they are finalized or out of running
can_view_live_picks = (user_current_pick and user_current_pick["pick_state"] == "Finalized") or user_is_eliminated

# Mapping dictionary linking primary registration structures to main user profiles
user_map = {u["id"]: u["username"] for u in users_res}

# --- 3. SELECTION TALLY GRID ENGINE (TOP LEFT WINDOW) ---
st.markdown("### 📊 Weekly Selection Distribution")
tally_counts = {}
for p in picks_res:
    if p["week"] == current_week:
        # Hide picks if current user hasn't met validation requirements yet
        if can_view_live_picks:
            tally_counts[p["team_picked"]] = tally_counts.get(p["team_picked"], 0) + 1

sorted_tallies = sorted(tally_counts.items(), key=lambda item: (-item[1], item[0]))

if sorted_tallies:
    tally_cols = st.columns(min(len(sorted_tallies), 6))
    for idx, (team, count) in enumerate(sorted_tallies):
        clean_team = team.replace("_SO", "")
        with tally_cols[idx % 6]:
            st.markdown(
                f"""
                <div style="background:white; border:1px solid #e2e8f0; padding:6px; border-radius:4px; display:flex; align-items:center; gap:8px;">
                    <img src="https://espncdn.com{clean_team.lower()}.png" width="24" height="16" style="object-fit:contain;"/>
                    <span style="font-weight:bold; font-size:13px;">{clean_team}</span>
                    <span style="margin-left:auto; background:#dbeafe; color:#1e40af; font-size:11px; padding:2px 6px; border-radius:10px; font-weight:bold;">{count}</span>
                </div>
                """, 
                unsafe_allow_html=True
            )
else:
    st.info("🔒 Selection tallies remain hidden until your own weekly entry is Finalized.")

# --- 4. RENDER BRACKET MATRIX GIRD ---
st.markdown("<br>### 📋 Complete Tournament Roster Grid", unsafe_allow_html=True)

# Bucket players into their designated operational brackets
bracket_buckets = {
    "🟢 Undefeated (Loser's Bracket)": [r for r in regs_res if r["bracket_status"] == "Loser Bracket"],
    "🟡 One Strike Remaining (Winner's Bracket)": [r for r in regs_res if r["bracket_status"] == "Winner Bracket"],
    "🔵 Super Bowl Tiebreaker Window": [r for r in regs_res if r["bracket_status"] == "Tiebreaker"],
    "🔴 Eliminated Competitors": [r for r in regs_res if r["bracket_status"] == "Eliminated"]
}

for bracket_name, registrants in bracket_buckets.items():
    if not registrants:
        continue
        
    st.markdown(f"<div style='background:#f1f5f9; padding:6px 12px; font-weight:bold; border-radius:4px; margin-top:15px;'>{bracket_name}</div>", unsafe_allow_html=True)
    
    # Generate interactive HTML table matrix strings
    html_table = """
    <table style="width:100%; border-collapse:collapse; background:white; font-size:12px; margin-top:5px;">
        <thead>
            <tr style="background:#334155; color:white; text-align:center;">
                <th style="padding:8px; border:1px solid #cbd5e1; text-align:left;">Competitor</th>
                <th style="padding:8px; border:1px solid #cbd5e1;">Byes</th>
    """
    # Append header matrix rows up to Week 18 limits
    for w in range(1, 19):
        html_table += f'<th style="padding:4px; border:1px solid #cbd5e1; width:45px;">W{w}</th>'
    html_table += "</tr></thead><tbody>"
    
    for reg in registrants:
        username = user_map.get(reg["user_id"], "Unknown Player")
        html_table += f"""
            <tr style="border-bottom:1px solid #e2e8f0;">
                <td style="padding:6px; border:1px solid #cbd5e1; font-weight:bold; color:#1e293b;">{username}</td>
                <td style="padding:6px; border:1px solid #cbd5e1; text-align:center; font-family:monospace;">{reg['byes_used']}/1</td>
        """
        
        # Populate custom cells dynamically based on selection state parameters
        for w in range(1, 19):
            w_pick = next((p for p in picks_res if p["user_id"] == reg["user_id"] and p["week"] == w), None)
            
            if not w_pick:
                html_table += '<td style="border:1px solid #cbd5e1; bg:#fafafa;"></td>'
                continue
                
            # Restrict visual tracking for active weeks if security constraints aren't validated
            if w == current_week and not can_view_live_picks:
                icon_tag = "🔒" if w_pick["pick_state"] == "Confirmed" else "❌ Hidden"
                html_table += f'<td style="border:1px solid #cbd5e1; text-align:center; color:#94a3b8; font-size:10px;">{icon_tag}</td>'
                continue
                
            clean_team = w_pick["team_picked"].replace("_SO", "")
            has_asterisk = "*" if w_pick["team_picked"].endswith("_SO") else ""
            
            # Match layout conditions to correct hexadecimal design specifications
            bg_color = "transparent"
            indicator_icon = ""
            
            if w_pick["pick_state"] == "Correct":
                bg_color = "#008000"  # Direct Green Rule
                indicator_icon = '<span style="position:absolute; bottom:1px; right:2px; color:white; font-size:8px; font-weight:black;">✓</span>'
            elif w_pick["pick_state"] == "Incorrect":
                bg_color = "#FF0000"  # Direct Red Rule
                indicator_icon = '<span style="position:absolute; bottom:1px; right:2px; color:white; font-size:8px; font-weight:black;">X</span>'
            elif w_pick["pick_state"] == "Finalized":
                indicator_icon = '<span style="position:absolute; bottom:1px; right:2px; font-size:8px;">🔒</span>'
                
            if clean_team == "BYE":
                html_table += f'<td style="border:1px solid #cbd5e1; background:{bg_color}; text-align:center; font-weight:bold; color:gray; position:relative;">BYE{indicator_icon}</td>'
            else:
                html_table += f"""
                <td style="border:1px solid #cbd5e1; background:{bg_color}; text-align:center; position:relative; padding:2px;">
                    <div style="display:flex; flex-direction:column; align-items:center; justify-content:center;">
                        <img src="https://espncdn.com{clean_team.lower()}.png" width="30" height="20" style="object-fit:contain; padding-bottom:2px;"/>
                        <span style="font-size:7px; font-weight:bold; line-height:1; color:inherit;">{clean_team}{has_asterisk}</span>
                    </div>
                    {indicator_icon}
                </td>
                """
        html_table += "</tr>"
        
    html_table += "</tbody></table>"
    st.markdown(html_table, unsafe_allow_html=True)

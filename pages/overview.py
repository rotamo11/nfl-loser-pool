import streamlit as st
from supabase import create_client, Client

# Initialize database connection context
URL = st.secrets["SUPABASE_URL"]
KEY = st.secrets["SUPABASE_KEY"]
supabase: Client = create_client(URL, KEY)

st.set_page_config(layout="wide")

# Determine active tournament mode filter ruleset
game_mode = st.sidebar.selectbox("Select Pool Tournament", ["Main Pool", "2nd Chance Game"])
game_slug = "Main" if game_mode == "Main Pool" else "2nd_Chance"
current_week = 2  # Manually advance this index as the season rolls on

# --- 1. BRAND HEADER DISPLAY MATRICES ---
# Split the row into two columns for your logo image and title text alignment
header_col1, header_col2 = st.columns([1, 6])

with header_col1:
    # Load your local logo file safely using the guaranteed native image tool
    st.image("static/loser-logo.png", width=200)
with header_col2:
    st.markdown(
        f"""
        <div style="padding:10px; border-radius:8px; color:white; margin-bottom:12px; margin-top:12px; font-family:sans-serif;">
            <h1 style="margin:0; font-weight:900; letter-spacing:-1px;">2026 NFL Loser Pool &bull; {game_mode} &bull; Week {current_week}</h1>
            <div style="display:grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap:10px; font-size:14px; margin-bottom:12px; margin-top:12px; opacity:0.9;">
                <div><b>Through Week 14:</b> Pick 1 team to lose each week</div>
                <div><b>Weeks 15-18:</b> Pick 2 teams to lose each week</div>
                <div><b>Playoffs:</b> Pick loser of ALL games (Repeats allowed)</div>
            </div>
            <div style="display:grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap:10px; font-size:14px; margin-bottom:12px; margin-top:12px; opacity:0.9;">
                <div><b>Weekly Deadline:</b> NOON ET Sunday or by kickoff if taking an earlier game</div>
            </div>
            <div style="margin-top:12px; padding-top:8px; border-top:1px solid #1e3a8a; font-family:monospace; font-size:11.5px; color:#93c5fd;">
                74 Players | $1850 Purse ($1110 1st / $555 2nd / $185 3rd) | Last year's losers: Stephen King took 1st for $765, Amanda Conley took 2nd for $382.50, Bill Kazmierski took 3rd for $127.50
            </div>
        </div>
        """, 
        unsafe_allow_html=True
    )

# --- 2. RETRIEVE LEAGUE AND SELECTION DATA ---
users_res = supabase.table("users").select("*").execute().data
regs_res = supabase.table("tournament_registrations").select("*").eq("game_type", game_slug).execute().data
picks_res = supabase.table("user_picks").select("*").eq("game_type", game_slug).execute().data

# Safe Session Verification Guard
current_user = st.session_state.get("user", None)
logged_in_uid = current_user.id if current_user is not None else None

user_current_pick = None
if logged_in_uid:
    user_current_pick = next((p for p in picks_res if p["user_id"] == logged_in_uid and p["week"] == current_week), None)

user_is_eliminated = False
if logged_in_uid:
    user_is_eliminated = any(r for r in regs_res if r["user_id"] == logged_in_uid and r["bracket_status"] == "Eliminated")

# Security Rule: Users can only see live boards if they are finalized or out of running
can_view_live_picks = (user_current_pick and user_current_pick["pick_state"] == "Finalized") or user_is_eliminated

user_map = {u["id"]: u["username"] for u in users_res}

# --- 3. SELECTION TALLY GRID ENGINE (TOP LEFT WINDOW) ---
st.markdown("### Weekly Selection Distribution")

# Fix: Show privacy lockout notice immediately if player hasn't finalized validation passes
if not can_view_live_picks:
    st.info("🔒 Selection tallies remain hidden until your own weekly entry is Finalized.")
else:
    tally_counts = {}
    for p in picks_res:
        if p["week"] == current_week:
            tally_counts[p["team_picked"]] = tally_counts.get(p["team_picked"], 0) + 1

    sorted_tallies = sorted(tally_counts.items(), key=lambda item: (-item[1], item[0]))

    if sorted_tallies:
        num_tally_cols = min(len(sorted_tallies), 6)
        if num_tally_cols > 0:
            tally_cols = st.columns([1] * num_tally_cols)
            for idx, (team, count) in enumerate(sorted_tallies):
                clean_team = team.replace("_SO", "")
                with tally_cols[idx % num_tally_cols]:
                    logo_img = "" if clean_team == "BYE" else f'<img src="app/static/{clean_team.upper()}.svg" width="24" height="16" style="object-fit:contain;"/>'
                    st.markdown(
                        f"""
                        <div style="background:white; border:1px solid #e2e8f0; padding:6px; border-radius:4px; display:flex; align-items:center; gap:8px; font-family:sans-serif;">
                            {logo_img}
                            <span style="font-weight:bold; font-size:13px;">{clean_team}</span>
                            <span style="margin-left:auto; background:#dbeafe; color:#1e40af; font-size:11px; padding:2px 6px; border-radius:10px; font-weight:bold;">{count}</span>
                        </div>
                        """, 
                        unsafe_allow_html=True
                    )
    else:
        st.info("Nobody has placed a submission pick for Week 2 yet.")

# --- 4. RENDER BRACKET MATRIX GRID ---
st.markdown("<br>### Complete Tournament Roster Grid", unsafe_allow_html=True)

bracket_buckets = {
    "🟢 Loser's Bracket": [r for r in regs_res if r["bracket_status"] == "Loser Bracket"],
    "🟡 Winner's Bracket": [r for r in regs_res if r["bracket_status"] == "Winner Bracket"],
    "🔵 Tiebreaker": [r for r in regs_res if r["bracket_status"] == "Tiebreaker"],
    "🔴 Eliminated": [r for r in regs_res if r["bracket_status"] == "Eliminated"]
}

html_iframe_payload = """
<!DOCTYPE html>
<html>
<head>
<style>
    body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; margin: 0; background: #f8fafc; padding: 10px; }
    .bracket-title { background:#e2e8f0; padding:8px 12px; font-weight:bold; border-radius:4px; margin-top:20px; color:#334155; font-size:13px; }
    table { width:100%; border-collapse:collapse; background:white; font-size:12px; margin-top:5px; box-shadow: 0 1px 3px rgba(0,0,0,0.05); }
    th { background:#334155; color:white; padding:8px; border:1px solid #cbd5e1; font-weight:bold; }
    td { border:1px solid #cbd5e1; padding:4px; text-align:center; vertical-align:middle; }
    .player-name { text-align:left; font-weight:bold; color:#1e293b; background:#f8fafc; padding-left:8px; min-width:150px; }
    .bye-cell { font-family:monospace; text-align:center; background:#f8fafc; }
</style>
</head>
<body>
"""

for bracket_name, registrants in bracket_buckets.items():
    if not registrants:
        continue
        
    html_iframe_payload += f"""
    <div class="bracket-title">{bracket_name}</div>
    <table>
        <thead>
            <tr>
                <th style="text-align:left; padding-left:8px;">Competitor</th>
                <th style="width:40px;">Byes</th>
    """
    for w in range(1, 19):
        html_iframe_payload += f'<th style="width:45px;">W{w}</th>'
    html_iframe_payload += "</tr></thead><tbody>"
    
    for reg in registrants:
        username = user_map.get(reg["user_id"], "Unknown Player")
        html_iframe_payload += f"""
            <tr>
                <td class="player-name">{username}</td>
                <td class="bye-cell">{reg['byes_used']}/1</td>
        """
        
        for w in range(1, 19):
            w_pick = next((p for p in picks_res if p["user_id"] == reg["user_id"] and p["week"] == w), None)
            
            if not w_pick:
                html_iframe_payload += '<td style="background:#fafafa;"></td>'
                continue
                
            if w == current_week and not can_view_live_picks:
                icon_tag = "🔒 Confirmed" if w_pick["pick_state"] == "Confirmed" else "🔒 Hidden"
                html_iframe_payload += f'<td style="color:#94a3b8; font-size:10px; background:#f1f5f9; font-weight:bold;">{icon_tag}</td>'
                continue
                
            clean_team = w_pick["team_picked"].replace("_SO", "")
            has_asterisk = "*" if w_pick["team_picked"].endswith("_SO") else ""
            
            bg_color = "transparent"
            text_color = "#1e293b"
            indicator_icon = ""
            
            if w_pick["pick_state"] == "Correct":
                bg_color = "#008000"
                text_color = "white"
                indicator_icon = '<span style="position:absolute; bottom:1px; right:3px; color:white; font-size:9px; font-weight:900;">✓</span>'
            elif w_pick["pick_state"] == "Incorrect":
                bg_color = "#FF0000"
                text_color = "white"
                indicator_icon = '<span style="position:absolute; bottom:1px; right:3px; color:white; font-size:9px; font-weight:900;">X</span>'
            elif w_pick["pick_state"] == "Finalized":
                indicator_icon = '<span style="position:absolute; bottom:1px; right:3px; font-size:8px;">🔒</span>'
                
            if clean_team == "BYE":
                html_iframe_payload += f'<td style="background:{bg_color}; font-weight:bold; color:{text_color}; position:relative;">BYE{indicator_icon}</td>'
            else:
                # Inline SVG Embedded Fix: Reads the file code directly from your static folder
                try:
                    with open(f"static/{clean_team.upper()}.svg", "r") as svg_file:
                        svg_code = svg_file.read()
                    # Wrap the raw SVG code in a styled container to control height/width dynamically
                    logo_html = f'<div style="width:28px; height:18px; display:inline-block;">{svg_code}</div>'
                except Exception:
                    # Fallback to plain text if the file is missing or has a typo
                    logo_html = f'<b>{clean_team}</b>'

                html_iframe_payload += f"""
                <td style="background:{bg_color}; position:relative; color:{text_color}; padding:2px;">
                    <div style="display:flex; flex-direction:column; align-items:center; justify-content:center;">
                        {logo_html}
                        <span style="font-size:8px; font-weight:bold; line-height:1; margin-top:1px;">{clean_team}{has_asterisk}</span>
                    </div>
                    {indicator_icon}
                </td>
                """
        html_iframe_payload += "</tr>"
    html_iframe_payload += "</tbody></table>"

html_iframe_payload += "</body></html>"

# Render safely via standard new st.iframe parameters
st.iframe(src=f"data:text/html;charset=utf-8,{html_iframe_payload}", height=1200)

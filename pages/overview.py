import streamlit as st
from supabase import create_client, Client
import os

# Initialize database connection context
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

# --- 2. RETRIEVE LEAGUE AND SELECTION DATA ---
users_res = supabase.table("users").select("*").execute().data
regs_res = supabase.table("tournament_registrations").select("*").eq("game_type", game_slug).execute().data
picks_res = supabase.table("user_picks").select("*").eq("game_type", game_slug).execute().data

# Safe Session Verification Guard
current_user = st.session_state.get("user", None)
logged_in_uid = current_user.id if current_user is not None else None

user_current_pick = None
if logged_in_uid:
    user_current_pick = next((p for p in picks_res if p["user_id"] == logged_in_uid and p["week"] == CURRENT_WEEK), None)

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
        if p["week"] == CURRENT_WEEK:
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
    "Loser's Bracket": [r for r in regs_res if r["bracket_status"] == "Loser Bracket"],
    "Winner's Bracket": [r for r in regs_res if r["bracket_status"] == "Winner Bracket"],
    "Tiebreaker": [r for r in regs_res if r["bracket_status"] == "Tiebreaker"],
    "Eliminated": [r for r in regs_res if r["bracket_status"] == "Eliminated"]
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
                
            if w == CURRENT_WEEK and not can_view_live_picks:
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

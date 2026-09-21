import streamlit as st
from supabase import create_client, Client
import os
import base64
import datetime

st.set_page_config(layout="wide")

# Initialize database connection context
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
    
    # Basic navigation paths open to every pool competitor
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

# --- RETRIEVE LEAGUE AND SELECTION DATA ---
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

# Privacy Lockout Validation Check
can_view_live_picks = (user_current_pick and user_current_pick["pick_state"] == "Finalized") or user_is_eliminated
user_map = {u["id"]: u["username"] for u in users_res}

# --- MINIMALIST LOW-PROFILE SELECTION DISTRIBUTION GRID ---
st.markdown("### Weekly Selection Distribution")

if not can_view_live_picks:
    st.info("Selection tallies remain hidden until your own weekly entry is Finalized.")
else:
    tally_counts = {}
    for p in picks_res:
        if p["week"] == CURRENT_WEEK:
            tally_counts[p["team_picked"]] = tally_counts.get(p["team_picked"], 0) + 1

    # FIX: Map precise indices: -item[1] sorts count descending, item[0] sorts name alphabetically ascending
    sorted_tallies = sorted(tally_counts.items(), key=lambda item: (-item[1], item[0]))

    if sorted_tallies:
        # Create a horizontal row layout utilizing up to 10 low-profile inline slots
        num_tally_cols = min(len(sorted_tallies), 10)
        tally_cols = st.columns(num_tally_cols)
        
        for idx, (team, count) in enumerate(sorted_tallies):
            clean_team = team.replace("_SO", "")
            col_target = tally_cols[idx % num_tally_cols]
            
            with col_target:
                if clean_team == "BYE":
                    st.markdown(f"**BYE** `{count}`")
                else:
                    try:
                        # 1. Read raw SVG file data parameters
                        with open(f"static/{clean_team.upper()}.svg", "rb") as svg_file:
                            encoded_svg = base64.b64encode(svg_file.read()).decode("utf-8")
                        
                        # 2. THE FIXED SECURE EMBED: Wraps bytes securely inside a standard <img> route
                        # This tricks Streamlit's security filter, forcing the logo to load instantly!
                        svg_data_url = f"data:image/svg+xml;base64,{encoded_svg}"
                        
                        # 3. Compile horizontal layout string block
                        flat_html_tally = f"""<div style="display:inline-flex; align-items:center; gap:6px; font-family:sans-serif; font-weight:bold; font-size:15px; color:var(--text-color); vertical-align:middle;"><img src="{svg_data_url}" width="26" height="18" style="object-fit:contain; vertical-align:middle;"/>{clean_team}<span style="font-family:sans-serif; font-weight:bold; font-size:15px; color:var(--text-color); vertical-align:middle;">{count}</span></div>"""
                        st.html(flat_html_tally)
                        
                    except Exception:
                        st.markdown(f"**{clean_team}** `{count}`")
    else:
        st.info("Nobody has placed a submission pick for this week yet.")

st.markdown("---")

# --- MASTER TOURNAMENT ROSTER GRID ---
# st.markdown("### Complete Tournament Roster Grid")

bracket_buckets = {
    "Loser's Bracket": [r for r in regs_res if r["bracket_status"] == "Loser Bracket"],
    "Winner's Bracket": [r for r in regs_res if r["bracket_status"] == "Winner Bracket"],
    "Tiebreaker": [r for r in regs_res if r["bracket_status"] == "Tiebreaker"],
    "Eliminated": [r for r in regs_res if r["bracket_status"] == "Eliminated"]
}

# Base iframe document construction layout template properties
html_iframe_payload = """
<!DOCTYPE html>
<html>
<head>
<style>
    body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; margin: 0; background: transparent; padding: 10px; }
    @media (prefers-color-scheme: dark) { body { color: #f8fafc; } }
    .bracket-title { background:#e2e8f0; padding:8px 12px; font-weight:bold; border-radius:4px; margin-top:20px; color:#334155; font-size:13px; }
    table { width:100%; border-collapse:collapse; background:white; font-size:12px; margin-top:5px; box-shadow: 0 1px 3px rgba(0,0,0,0.05); }
    @media (prefers-color-scheme: dark) { table { background: #1e293b; } }
    th { background:#334155; color:white; padding:8px; border:1px solid #cbd5e1; font-weight:bold; }
    @media (prefers-color-scheme: dark) { th { border: 1px solid #475569; } }
    td { border:1px solid #cbd5e1; padding:4px; text-align:center; vertical-align:middle; color: #1e293b; }
    @media (prefers-color-scheme: dark) { td { border: 1px solid #475569; color: #f8fafc; } }
    .player-name { text-align:left; font-weight:bold; color:#1e293b; background:#f8fafc; padding-left:8px; min-width:150px; }
    @media (prefers-color-scheme: dark) { .player-name { background: #1e293b; color: #f8fafc; } }
    .bye-cell { font-family:monospace; text-align:center; background:#f8fafc; }
    @media (prefers-color-scheme: dark) { .bye-cell { background: #1e293b; } }
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
                html_iframe_payload += '<td></td>'
                continue
                
            if w == CURRENT_WEEK and not can_view_live_picks:
                icon_tag = "Confirmed" if w_pick["pick_state"] == "Confirmed" else "Hidden"
                html_iframe_payload += f'<td style="color:#94a3b8; font-size:10px; background:rgba(0,0,0,0.05); font-weight:bold;">{icon_tag}</td>'
                continue
                
            clean_team = w_pick["team_picked"].replace("_SO", "")
            has_asterisk = "*" if w_pick["team_picked"].endswith("_SO") else ""
            
            bg_color = "transparent"
            text_color = "inherit"
            indicator_icon = ""
            
            if w_pick["pick_state"] == "Correct":
                bg_color = "#008000"
                text_color = "white"
                indicator_icon = '<span style="position:absolute; bottom:1px; right:3px; color:white; font-size:9px; font-weight:900;"></span>'
            elif w_pick["pick_state"] == "Incorrect":
                bg_color = "#FF0000"
                text_color = "white"
                indicator_icon = '<span style="position:absolute; bottom:1px; right:3px; color:white; font-size:9px; font-weight:900;"></span>'
            elif w_pick["pick_state"] == "Finalized":
                indicator_icon = '<span style="position:absolute; bottom:1px; right:3px; font-size:8px;"></span>'
                
            if clean_team == "BYE":
                html_iframe_payload += f'<td style="background:{bg_color}; font-weight:bold; color:{text_color}; position:relative;">BYE{indicator_icon}</td>'
            else:
                try:
                    # 1. READ THE LOCAL ASSET AS BINARY SECURELY
                    # This searches strictly using the clean_team variable (e.g., 'SF')
                    import base64
                    with open(f"static/{clean_team.upper()}.svg", "rb") as svg_file:
                        encoded_table_svg = base64.b64encode(svg_file.read()).decode("utf-8")
                    
                    # 2. Convert into a clean base64 image data url string
                    table_svg_url = f"data:image/svg+xml;base64,{encoded_table_svg}"
                    
                    # 3. Mount cleanly inside a standard web <img> tag layout frame
                    logo_html = f'<img src="{table_svg_url}" width="28" height="18" style="object-fit:contain; display:block; margin:0 auto;"/>'
                except Exception:
                    # Safe fallback text if the file is completely missing
                    logo_html = f'<b>{clean_team}</b>'

                html_iframe_payload += f"""
                <td style="background:{bg_color}; position:relative; color:{text_color}; padding:2px;">
                    <div style="display:flex; flex-direction:column; align-items:center; justify-content:center;">
                        {logo_html}
                        <span style="font-size:8px; font-weight:bold; line-height:1; margin-top:2px;">{clean_team}{has_asterisk}</span>
                    </div>
                    {indicator_icon}
                </td>
                """
        html_iframe_payload += "</tr>"
    html_iframe_payload += "</tbody></table>"

html_iframe_payload += "</body></html>"

# This wraps raw SVG code securely, preventing the browser from clipping the text stream
encoded_payload = base64.b64encode(html_iframe_payload.encode("utf-8")).decode("utf-8")

# Pass the safe base64 token data stream directly to the iframe frame
st.iframe(src=f"data:text/html;base64,{encoded_payload}", height=1200)



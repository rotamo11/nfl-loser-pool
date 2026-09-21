import streamlit as st
from supabase import create_client, Client
import os
import datetime

st.set_page_config(layout="wide")

# Initialize database connection
URL = st.secrets["SUPABASE_URL"]
KEY = st.secrets["SUPABASE_KEY"]
supabase: Client = create_client(URL, KEY)

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

st.subheader("Locker Room Chat")

if 'user' not in st.session_state or not st.session_state.user:
    st.warning("You must be logged into the main page to access the live chat room.")
else:
    user_id = st.session_state.user.id
    
    # 1. Fetch current player profile to anchor their username
    user_profile = supabase.table("users").select("username").eq("id", user_id).single().execute().data
    username = user_profile.get("username", "Anonymous Player") if user_profile else "Anonymous Player"

    # 2. Render Message Submission Input Box
    with st.form("chat_form", clear_on_submit=True):
        user_message = st.text_input("Spit some banter or talk trash:", placeholder="Your message...")
        submit_msg = st.form_submit_button("Send Message", use_container_width=True)
        
        if submit_msg and user_message.strip():
            # Ingest message record directly into live database
            supabase.table("pool_chat").insert({
                "user_id": user_id,
                "username": username,
                "message": user_message.strip()
            }).execute()
            st.toast("Message broadcasted!")
            st.rerun()

    st.markdown("---")

    # 3. Pull and display the historical scroll of chat entries
    chat_logs = supabase.table("pool_chat").select("*").order("created_at", desc=True).limit(50).execute().data

    if chat_logs:
        for msg in chat_logs:
            # Format time stamp visuals
            raw_time = msg["created_at"][:16].replace("T", " ")
            st.markdown(
                f"""
                <div style="background:white; padding:10px; border-radius:6px; border-left:4px solid #000080; margin-bottom:8px; box-shadow: 0 1px 2px rgba(0,0,0,0.05);">
                    <span style="font-weight:black; color:#1e3a8a;">{msg['username']}</span> 
                    <span style="font-size:10px; color:gray; float:right;">{raw_time}</span>
                    <p style="margin:5px 0 0 0; font-size:13px; color:#334155;">{msg['message']}</p>
                </div>
                """, 
                unsafe_allow_html=True
            )
    else:
        st.info("Hey there, you loser!  Tell us why you're no winner!")

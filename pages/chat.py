import streamlit as st
from supabase import create_client, Client
import os

# Initialize database connection
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
    st.page_link("pages/overview.py", label="Overview")
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

st.subheader("Locker Room Chat")

if 'user' not in st.session_state or not st.session_state.user:
    st.warning("🔒 You must be logged into the main page to access the live chat room.")
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

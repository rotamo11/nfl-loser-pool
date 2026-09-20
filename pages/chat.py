import streamlit as st
from supabase import create_client, Client

# Initialize database connection
URL = st.secrets["SUPABASE_URL"]
KEY = st.secrets["SUPABASE_KEY"]
supabase: Client = create_client(URL, KEY)
# 2. Main Navigation & Persistent Mode Toggles
game_mode = st.sidebar.selectbox("Select Pool Tournament", ["Main Pool", "2nd Chance Game"])
game_slug = "Main" if game_mode == "Main Pool" else "2nd_Chance"

# Sets #1d3d70ff for Main Pool and #974706 for 2nd Chance Game
sidebar_bg = "#1d3d70ff" if game_slug == "Main" else "#974706"

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

st.set_page_config(layout="wide")
st.title("Loser Pool Locker Room Chat")

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

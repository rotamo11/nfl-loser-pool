import streamlit as st
from supabase import create_client, Client

# Initialize database connection
URL = st.secrets["SUPABASE_URL"]
KEY = st.secrets["SUPABASE_KEY"]
supabase: Client = create_client(URL, KEY)

st.set_page_config(layout="wide")
st.title("💬 Loser Pool Locker Room Chat")

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
        submit_msg = st.form_submit_button("Send Message 🚀", use_container_width=True)
        
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
                unsafe_allowed_html=True
            )
    else:
        st.info("Hey there, you loser!  Tell us why you're no winner!")

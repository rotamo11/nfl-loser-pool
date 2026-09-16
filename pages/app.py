import streamlit as st
from supabase import create_client, Client

# Securely extract environmental configuration variables
URL = st.secrets["SUPABASE_URL"]
KEY = st.secrets["SUPABASE_KEY"]
supabase: Client = create_client(URL, KEY)

st.set_page_config(layout="wide")

# Persistent Context Selector: Toggle between Main Pool and the 2nd Chance Bracket
game_mode = st.sidebar.selectbox("🎯 Select Pool Tournament", ["Main Pool", "2nd Chance Game"])
game_slug = "Main" if game_mode == "Main Pool" else "2nd_Chance"

st.title(f"🏈 NFL Loser Pool Dashboard: {game_mode}")

# Beginner Auth State Verification Loop
if 'user' not in st.session_state:
    st.session_state.user = None

if not st.session_state.user:
    st.subheader("🔒 Player Credentials Portal")
    email = st.text_input("Registered Email")
    password = st.text_input("Password", type="password")
    if st.button("Log In"):
        try:
            res = supabase.auth.sign_in_with_password({"email": email, "password": password})
            st.session_state.user = res.user
            st.rerun()
        except Exception:
            st.error("Authentication rejected.")
else:
    st.success(f"Verified Session Connection.")
    # Application operational modules (Forms, Overview Grids) inherit the `game_slug` filter rule here.

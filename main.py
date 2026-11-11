import os
from nicegui import ui, app
from supabase import create_client, Client

# 1. Initialize Supabase (Set these in Render/Railway Environment Variables)
SUPABASE_URL = os.environ.get("SUPABASE_URL", "YOUR_SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "YOUR_SUPABASE_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# 2. Persistent Login Restoration Helper
def get_authenticated_user():
    refresh_token = app.storage.user.get("refresh_token")
    if not refresh_token:
        return None
    try:
        res = supabase.auth.refresh_session(refresh_token)
        if res and res.user and res.session:
            # Rotate and save the fresh 7-day refresh token automatically
            app.storage.user["refresh_token"] = res.session.refresh_token
            app.storage.user["user_id"] = res.user.id
            return res.user
    except Exception:
        app.storage.user.clear()
    return None

# 3. Shared Top Navigation & Dynamic Theme Layout
def render_layout(active_page: str, content_builder):
    user = get_authenticated_user()
    
    # Default pool state persisted in user storage
    if "pool" not in app.storage.user:
        app.storage.user["pool"] = "Main"
        
    # Dark mode preference persisted in user storage
    dark_mode = ui.dark_mode(value=app.storage.user.get("dark_mode", False))

    def apply_pool_theme(pool_name: str):
        app.storage.user["pool"] = pool_name
        bg_hex = "#1d3d70" if pool_name == "Main" else "#974706"
        ui.query("body").style(f"background-color: {bg_hex}; transition: background-color 0.3s;")

    # Apply initial background color on page load
    apply_pool_theme(app.storage.user["pool"])

    # --- TOP NAVIGATION HEADER ---
    with ui.header().classes("bg-transparent shadow-none px-4 pt-3 pb-0 flex flex-col items-center"):
        with ui.row().classes("w-full max-w-5xl items-center justify-between"):
            ui.label("🏈 2026 NFL Loser Pool").classes("text-white text-xl font-black tracking-tight")
            
            with ui.row().classes("items-center gap-2"):
                # Light / Dark Content Theme Toggle
                def toggle_theme():
                    dark_mode.toggle()
                    app.storage.user["dark_mode"] = dark_mode.value
                ui.button(icon="contrast", on_click=toggle_theme).props("flat round color=white")
                
                if user:
                    def handle_logout():
                        app.storage.user.clear()
                        ui.navigate.to("/")
                    ui.button("Log Out", on_click=handle_logout).props("outline color=white size=sm")

        # Main vs. 2nd Chance Tabs
        with ui.tabs(value=app.storage.user["pool"], on_change=lambda e: (apply_pool_theme(e.value), ui.navigate.reload())).classes("text-white mt-2") as pool_tabs:
            ui.tab("Main", label="Main Pool")
            ui.tab("2nd_Chance", label="2nd Chance")

        # Horizontal Page Navigation Links Spread Below Tabs
        with ui.row().classes("w-full max-w-5xl justify-center gap-4 py-2 border-t border-white/20 text-sm font-semibold"):
            nav_items = [
                ("Picks", "/"),
                ("Overview", "/overview"),
                ("Chat", "/chat"),
                ("Rules", "/rules"),
            ]
            for label, route in nav_items:
                style = "text-amber-300 underline" if active_page == label else "text-white/80 hover:text-white"
                ui.link(label, route).classes(f"no-underline {style}")

    # --- MAIN CONTENT CARD (White in Light Mode, Dark Slate in Dark Mode) ---
    with ui.column().classes("w-full items-center px-3 py-4"):
        with ui.card().classes("w-full max-w-5xl p-5 rounded-xl shadow-lg bg-white dark:bg-slate-900"):
            if not user:
                render_login_box()
            else:
                content_builder(user, app.storage.user["pool"])

# 4. Native Login Card
def render_login_box():
    ui.label("Player Login").classes("text-2xl font-bold mb-2")
    email_input = ui.input("Email Address").classes("w-full")
    pass_input = ui.input("Password", password=True, password_toggle_button=True).classes("w-full")
    
    def attempt_login():
        try:
            res = supabase.auth.sign_in_with_password({
                "email": email_input.value.strip(),
                "password": pass_input.value.strip()
            })
            if res and res.session:
                app.storage.user["refresh_token"] = res.session.refresh_token
                app.storage.user["user_id"] = res.user.id
                ui.notify("Logged in! Session saved for 7 days.", type="positive")
                ui.navigate.reload()
        except Exception as e:
            ui.notify(f"Login Error: {str(e)}", type="negative", timeout=8000)

    ui.button("Log In", on_click=attempt_login).classes("w-full mt-3 bg-blue-600 text-white")

# 5. Page Routes
@ui.page("/")
def picks_page():
    def build_picks(user, pool):
        ui.label(f"Weekly Picks — {pool.replace('_', ' ')}").classes("text-xl font-bold")
        ui.label("Your mobile-friendly matchup cards will render right here.").classes("text-gray-500 dark:text-gray-400")
    render_layout("Picks", build_picks)

@ui.page("/overview")
def overview_page():
    def build_overview(user, pool):
        ui.label(f"Standings Overview — {pool.replace('_', ' ')}").classes("text-xl font-bold")
        ui.label("Your unified scrolling bracket grid will render right here.").classes("text-gray-500 dark:text-gray-400")
    render_layout("Overview", build_overview)

@ui.page("/chat")
def chat_page():
    render_layout("Chat", lambda u, p: ui.label("League Trash Talk & Chat").classes("text-xl font-bold"))

@ui.page("/rules")
def rules_page():
    render_layout("Rules", lambda u, p: ui.label("2026 Official Pool Rules").classes("text-xl font-bold"))

# 6. Start App (storage_secret encrypts the browser cookie!)
ui.run(
    host="0.0.0.0",
    port=int(os.environ.get("PORT", 8080)),
    storage_secret=os.environ.get("STORAGE_SECRET", "change-this-to-a-random-long-secret-key"),
    title="2026 NFL Loser Pool"
)

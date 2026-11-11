import os
import base64
from nicegui import ui, app
from supabase import create_client, Client
from picks_module import render_picks_view
from overview_module import render_overview_view

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def get_logo_uri(filename: str) -> str:
    for path in [f"static/{filename}", filename]:
        if os.path.exists(path):
            with open(path, "rb") as f:
                b64 = base64.b64encode(f.read()).decode("utf-8")
            return f"data:image/png;base64,{b64}"
    return ""

def get_authenticated_user():
    refresh_token = app.storage.user.get("refresh_token")
    if not refresh_token:
        return None
    try:
        res = supabase.auth.refresh_session(refresh_token)
        if res and res.user and res.session:
            app.storage.user["refresh_token"] = res.session.refresh_token
            app.storage.user["user_id"] = res.user.id
            return res.user
    except Exception:
        app.storage.user.clear()
    return None

def render_layout(active_page: str, content_builder):
    user = get_authenticated_user()
    if "pool" not in app.storage.user:
        app.storage.user["pool"] = "Main"

    is_dark = app.storage.user.get("dark_mode", False)
    dark_mode = ui.dark_mode(value=is_dark)

    current_tab = app.storage.user["pool"]
    bg_hex = "#974706" if current_tab == "2nd_Chance" else "#1d3d70"
    ui.query("body").style(f"background-color: {bg_hex}; margin: 0; padding: 0;")

    # --- SOLID TOP BANNER (Responsive Mobile & Desktop) ---
    logo_uri = get_logo_uri("nfl-logo-square.png")

    with ui.column().classes("w-full items-center px-3 pt-2 pb-2 text-white"):
        # 1. Top-Right Utility Row (Theme Toggle + Logout side-by-side)
        with ui.row().classes("w-full max-w-5xl justify-end items-center gap-2"):
            def toggle_theme():
                app.storage.user["dark_mode"] = not dark_mode.value
                ui.navigate.reload()

            ui.button(icon="dark_mode" if not is_dark else "light_mode", on_click=toggle_theme).props("flat round dense color=white")

            if user:
                def handle_logout():
                    app.storage.user.clear()
                    ui.navigate.to("/")
                ui.button("Log Out", on_click=handle_logout).props("outline color=white size=sm")

        # 2. Main Header Content Area (Full-width enabled)
        with ui.row().classes("w-full max-w-5xl items-stretch justify-between gap-4 no-wrap mt-1"):
            # Desktop-Only Full-Height Left Logo
            if logo_uri:
                ui.image(logo_uri).classes("hidden md:block w-36 object-contain self-stretch shrink-0 rounded-lg")

            # Centered Header Text & Rules
            with ui.column().classes("flex-1 items-center text-center justify-center gap-1"):
                # Mobile-Only Inline Logo + Title Row
                with ui.row().classes("items-center justify-center gap-2 no-wrap"):
                    if logo_uri:
                        ui.image(logo_uri).classes("block md:hidden h-9 w-9 object-contain shrink-0 rounded")
                    ui.label("NFL Loser Pool").classes("text-2xl md:text-3xl font-black tracking-tight")

                # 3-Column Rules Summary
                with ui.row().classes("w-full justify-center gap-4 md:gap-10 text-xs mt-1"):
                    with ui.column().classes("items-center gap-0"):
                        ui.label("Weeks 1-14").classes("font-extrabold text-amber-300")
                        ui.label("Pick 1 team to lose")
                    with ui.column().classes("items-center gap-0"):
                        ui.label("Weeks 15-18").classes("font-extrabold text-amber-300")
                        ui.label("Pick 2 teams to lose")
                    with ui.column().classes("items-center gap-0"):
                        ui.label("Playoffs").classes("font-extrabold text-amber-300")
                        ui.label("Pick ALL losers (repeats allowed)")

                ui.label("Weekly Deadline: Noon ET Sunday, or by kickoff of earlier game").classes(
                    "text-xs font-bold bg-white/15 px-3 py-1 rounded-full mt-1"
                )

                if current_tab == "2nd_Chance":
                    ui.label("26 Players: $650 Purse ($390 for 1st / $195 for 2nd / $65 for 3rd)").classes("text-xs font-bold text-amber-200 mt-1")
                    ui.label("Last Year's Losers: D. Bobrow ($300) • M. Ellis ($150) • D. Tashima ($50)").classes("text-[11px] text-white/80")
                else:
                    ui.label("74 Players | $1850 Purse ($1110 1st / $555 2nd / $185 3rd)").classes("text-xs font-bold text-blue-200 mt-1")
                    ui.label("Last Year's Losers: S. King ($765) • A. Conley ($382.50) • B. Kazmierski ($127.50)").classes("text-[11px] text-white/80")

            # 3. Top-Right Theme Toggle & Logout Controls
            with ui.column().classes("items-end justify-between shrink-0"):
                def toggle_theme():
                    app.storage.user["dark_mode"] = not dark_mode.value
                    ui.navigate.reload()

                ui.button(icon="dark_mode" if not is_dark else "light_mode", on_click=toggle_theme).props("flat round color=white")

                if user:
                    def handle_logout():
                        app.storage.user.clear()
                        ui.navigate.to("/")
                    ui.button("Log Out", on_click=handle_logout).props("outline color=white size=sm")
        # --- 3 TABS: MAIN, 2ND CHANCE, PROFILE ---
        def on_tab_change(e):
            if e.value != app.storage.user["pool"]:
                app.storage.user["pool"] = e.value
                ui.navigate.reload()

        with ui.tabs(value=current_tab, on_change=on_tab_change).classes("text-white mt-3"):
            ui.tab("Main", label="Main")
            ui.tab("2nd_Chance", label="2nd Chance")
            ui.tab("Profile", label="Profile")

        # --- SPREAD-OUT PAGE NAVIGATION LINKS (Hidden when viewing Profile tab) ---
        if current_tab != "Profile":
            with ui.row().classes("w-full max-w-4xl justify-around items-center py-2 mt-1 border-t border-white/25 text-sm font-bold"):
                nav_items = [
                    ("Picks", "/"),
                    ("Brackets", "/brackets"),
                    ("Chat", "/chat"),
                    ("Rules", "/rules"),
                ]
                for label, route in nav_items:
                    is_active = (active_page == label)
                    cls = "text-amber-300 underline underline-offset-4" if is_active else "text-white/85 hover:text-white"
                    ui.link(label, route).classes(f"no-underline {cls}")

    # --- MAIN CONTENT CONTAINER (Explicitly switches between white and dark slate) ---
    card_theme = "bg-slate-900 text-white border border-slate-700" if is_dark else "bg-white text-slate-900"

    with ui.column().classes("w-full items-center px-3 pb-8 pt-2"):
        with ui.card().classes(f"w-full max-w-5xl p-5 rounded-xl shadow-xl {card_theme}"):
            if not user:
                render_login_box()
            elif current_tab == "Profile":
                render_profile_placeholder(user)
            else:
                content_builder(user, current_tab)

def render_profile_placeholder(user):
    ui.label("Player Profile & Alert Settings").classes("text-xl font-bold mb-2")
    ui.label(f"Logged in as: {user.email}").classes("text-sm opacity-75")

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

    ui.button("Log In", on_click=attempt_login).classes("w-full mt-3 bg-blue-600 text-white font-bold")

# --- PAGE ROUTES ---
@ui.page("/")
def picks_page():
    render_layout("Picks", lambda user, pool: render_picks_view(supabase, user, pool))

@ui.page("/brackets")
def brackets_page():
    render_layout("Brackets", lambda user, pool: render_overview_view(supabase, user, pool))

@ui.page("/chat")
def chat_page():
    render_layout("Chat", lambda u, p: ui.label("League Trash Talk & Chat").classes("text-xl font-bold"))

@ui.page("/rules")
def rules_page():
    render_layout("Rules", lambda u, p: ui.label("2026 Official Pool Rules").classes("text-xl font-bold"))

ui.run(
    host="0.0.0.0",
    port=int(os.environ.get("PORT", 8080)),
    storage_secret=os.environ.get("STORAGE_SECRET", "change-this-to-a-random-long-secret-key"),
    title="2026 NFL Loser Pool"
)

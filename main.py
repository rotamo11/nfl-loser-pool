import os
import base64
from nicegui import ui, app
from supabase import create_client, Client
from picks_module import render_picks_view
from overview_module import render_overview_view

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# 1. Add this right after initializing Supabase in main.py
if os.path.exists("static"):
    app.add_static_files("/static", "static")

def get_static_logo_url(filename: str) -> str:
    if os.path.exists(f"static/{filename}"):
        return f"/static/{filename}"
    if os.path.exists(filename):
        return f"/{filename}"
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
    is_2nd = (current_tab == "2nd_Chance")

    # Pool Accent Colors vs. Light/Dark Theme Backgrounds
    pool_hex = "#974706" if is_2nd else "#1d3d70"
    page_bg = "#0f172a" if is_dark else "#f8fafc"
    ui.query("body").style(f"background-color: {page_bg}; margin: 0; padding: 0;")

    # Adaptive Light/Dark Text & Accent Classes
    text_main = "text-white" if is_dark else "text-slate-900"
    text_muted = "text-white/80" if is_dark else "text-slate-600"
    week_hdr_cls = "text-amber-300" if is_dark else ("text-amber-700" if is_2nd else "text-blue-800")
    purse_cls = "text-amber-200" if (is_dark and is_2nd) else ("text-blue-200" if is_dark else ("text-amber-800" if is_2nd else "text-blue-900"))
    btn_color = "white" if is_dark else "dark"

    logo_url = get_static_logo_url("loser-logo.png")

    # --- SOLID TOP BANNER (Matches Light/Dark Theme with Pool Accent Strip) ---
    with ui.column().classes(f"w-full items-center px-3 pt-2 pb-2 {text_main}").style(f"border-top: 6px solid {pool_hex};"):
        
        # 1. Top-Right Utility Row (Theme Toggle + Logout side-by-side)
        with ui.row().classes("w-full max-w-5xl justify-end items-center gap-2"):
            def toggle_theme():
                app.storage.user["dark_mode"] = not dark_mode.value
                ui.navigate.reload()

            ui.button(icon="dark_mode" if not is_dark else "light_mode", on_click=toggle_theme).props(f"flat round dense color={btn_color}")

            if user:
                def handle_logout():
                    app.storage.user.clear()
                    ui.navigate.to("/")
                ui.button("Log Out", on_click=handle_logout).props(f"outline color={btn_color} size=sm")

        # 2. Main Header Content Area (Mobile unchanged, Desktop scaled ~1.5x)
        with ui.row().classes("w-full max-w-5xl items-stretch justify-between gap-4 md:gap-6 no-wrap mt-1"):
            # Desktop-Only Full-Height Left Logo (Classes applied directly to the NiceGUI wrapper element)
            if logo_url:
                ui.html(
                    f'<img src="{logo_url}" style="width: 100%; height: 100%; object-fit: contain;" class="rounded-xl" />'
                ).classes("hidden md:flex items-center justify-center w-96 h-160 shrink-0")

            # Centered Header Text & Rules
            with ui.column().classes("flex-1 items-center text-center justify-center gap-1 md:gap-2"):
                # Title Row (Mobile text-2xl unchanged, Desktop scaled to md:text-4xl)
                with ui.row().classes("items-center justify-center gap-2 no-wrap"):
                    if logo_url:
                        ui.html(f'<img src="{logo_url}" class="block md:hidden h-9 w-9 object-contain p-0.5 shrink-0 rounded" />')
                    ui.label("NFL Loser Pool").classes("text-2xl md:text-4xl font-black tracking-tight")

                # 3-Column Rules Summary (Mobile text-xs unchanged, Desktop scaled to md:text-sm)
                with ui.row().classes("w-full justify-center gap-4 md:gap-10 text-xs md:text-sm mt-1"):
                    with ui.column().classes("items-center gap-0 md:gap-0.5"):
                        ui.label("Weeks 1-14").classes(f"font-extrabold {week_hdr_cls}")
                        ui.label("Pick 1 team to lose")
                    with ui.column().classes("items-center gap-0 md:gap-0.5"):
                        ui.label("Weeks 15-18").classes(f"font-extrabold {week_hdr_cls}")
                        ui.label("Pick 2 teams to lose")
                    with ui.column().classes("items-center gap-0 md:gap-0.5"):
                        ui.label("Playoffs").classes(f"font-extrabold {week_hdr_cls}")
                        ui.label("Pick ALL losers (repeats allowed)")

                # Deadline Pill Badge (Mobile text-xs unchanged, Desktop scaled to md:text-sm)
                ui.label("Weekly Deadline: Noon ET Sunday, or by kickoff of earlier game").classes(
                    "text-xs md:text-sm font-bold text-white px-3 md:px-5 py-1 md:py-1.5 rounded-full mt-1"
                ).style(f"background-color: {pool_hex};")

                # Purse & Last Year's Losers (Mobile text-xs/11px unchanged, Desktop scaled to md:text-base/sm)
                if is_2nd:
                    ui.label("26 Players: $650 Purse ($390 for 1st / $195 for 2nd / $65 for 3rd)").classes(f"text-xs md:text-base font-bold mt-1 {purse_cls}")
                    ui.label("Last Year's Losers: D. Bobrow ($300) • M. Ellis ($150) • D. Tashima ($50)").classes(f"text-[11px] md:text-sm {text_muted}")
                else:
                    ui.label("74 Players | $1850 Purse ($1110 1st / $555 2nd / $185 3rd)").classes(f"text-xs md:text-base font-bold mt-1 {purse_cls}")
                    ui.label("Last Year's Losers: S. King ($765) • A. Conley ($382.50) • B. Kazmierski ($127.50)").classes(f"text-[11px] md:text-sm {text_muted}")

        # 3. Tabs & Page Links
        def on_tab_change(e):
            if e.value != app.storage.user["pool"]:
                app.storage.user["pool"] = e.value
                ui.navigate.reload()

        with ui.tabs(value=current_tab, on_change=on_tab_change).classes(f"{text_main} mt-3").props(f"indicator-color={'amber' if is_2nd else 'primary'}"):
            ui.tab("Main", label="Main")
            ui.tab("2nd_Chance", label="2nd Chance")
            ui.tab("Profile", label="Profile")

        if current_tab != "Profile":
            border_sep = "border-white/20" if is_dark else "border-slate-300"
            with ui.row().classes(f"w-full max-w-4xl justify-around items-center py-2 mt-1 border-t {border_sep} text-sm font-bold"):
                nav_items = [("Picks", "/"), ("Brackets", "/brackets"), ("Chat", "/chat"), ("Rules", "/rules")]
                for label, route in nav_items:
                    is_active = (active_page == label)
                    if is_active:
                        cls = "text-amber-400 underline underline-offset-4" if is_dark else ("text-amber-700 underline underline-offset-4" if is_2nd else "text-blue-700 underline underline-offset-4")
                    else:
                        cls = "text-white/80 hover:text-white" if is_dark else "text-slate-600 hover:text-slate-900"
                    ui.link(label, route).classes(f"no-underline {cls}")

    # --- MAIN CONTENT CONTAINER (White in Light Mode, Dark Slate in Dark Mode, Pool Border) ---
    card_theme = "bg-slate-900 text-white" if is_dark else "bg-white text-slate-900"
    with ui.column().classes("w-full items-center px-3 pb-8 pt-2"):
        with ui.card().classes(f"w-full max-w-5xl p-5 rounded-xl shadow-xl {card_theme}").style(f"border-top: 4px solid {pool_hex};"):
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

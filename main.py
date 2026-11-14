import os
import base64
from nicegui import ui, app
from supabase import create_client, Client
from picks_module import render_picks_view
from overview_module import render_overview_view
from profile_module import render_profile_view
from admin_module import render_admin_view, is_admin_user
from chat_module import render_chat_view, get_unread_chat_count
from rules_module import render_rules_view

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "") # Your public anon key (used for user auth)
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", SUPABASE_KEY) # Secret key for DB writes/deletes

supabase_auth: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

# 1. Add this right after initializing Supabase in main.py
if os.path.exists("static"):
    app.add_static_files("/static", "static")

def get_static_logo_url(filename: str) -> str:
    if os.path.exists(f"static/{filename}"):
        return f"/static/{filename}"
    if os.path.exists(filename):
        return f"/{filename}"
    return ""

class MasqueradeUser:
    def __init__(self, uid: str, email: str = ""):
        self.id = uid
        self.email = email

def get_authenticated_user():
    refresh_token = app.storage.user.get("refresh_token")
    if not refresh_token:
        return None
    try:
        res = supabase_auth.auth.refresh_session(refresh_token)
        if res and res.user and res.session:
            app.storage.user["refresh_token"] = res.session.refresh_token
            app.storage.user["real_user_id"] = str(res.user.id)

            # Check if an admin is actively masquerading as another player
            masq_uid = app.storage.user.get("masquerade_uid")
            if masq_uid:
                u_row = supabase.table("users").select("email").eq("id", masq_uid).execute().data
                m_email = u_row[0].get("email", "") if u_row else ""
                return MasqueradeUser(masq_uid, m_email)

            app.storage.user["user_id"] = str(res.user.id)
            return res.user
    except Exception:
        app.storage.user.clear()
    return None

def resolve_default_pool(user) -> str:
    if not user:
        return "Main"
    try:
        uid = str(user.id)
        regs = supabase.table("tournament_registrations").select("game_type, is_enrolled, bracket_status").eq("user_id", uid).execute().data or []
        reg_map = {r["game_type"]: r for r in regs}

        sc_reg = reg_map.get("2nd_Chance")
        is_sc_enrolled = bool(sc_reg and sc_reg.get("is_enrolled", False))

        main_reg = reg_map.get("Main")
        is_main_active = bool(
            main_reg
            and main_reg.get("is_enrolled", False)
            and main_reg.get("bracket_status") != "Eliminated"
        )

        # Land on 2nd Chance ONLY if enrolled in 2nd Chance AND (eliminated or not enrolled in Main)
        if is_sc_enrolled and not is_main_active:
            return "2nd_Chance"
    except Exception:
        pass
    return "Main"

def render_layout(active_page: str, content_builder):
    user = get_authenticated_user()
    uid_str = str(user.id) if user else None

    # Re-evaluate default pool once on fresh login or when switching masquerade targets
    if uid_str and app.storage.user.get("pool_initialized_for") != uid_str:
        app.storage.user["pool"] = resolve_default_pool(user)
        app.storage.user["pool_initialized_for"] = uid_str
    elif "pool" not in app.storage.user:
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
        
        # 0. Active Masquerade Restore Banner (Visible only while impersonating a player)
        if app.storage.user.get("masquerade_uid"):
            masq_name = app.storage.user.get("masquerade_name", "Player")
            with ui.row().classes("w-full max-w-5xl items-center justify-between bg-purple-700 text-white px-4 py-1.5 rounded-lg mb-2 shadow"):
                ui.label(f"Masquerading as: {masq_name}").classes("text-xs md:text-sm font-extrabold")
                def exit_masquerade():
                    app.storage.user.pop("masquerade_uid", None)
                    app.storage.user.pop("masquerade_name", None)
                    ui.notify("Restored Commissioner session.", type="info")
                    ui.navigate.to("/admin")
                ui.button("Exit Masquerade", on_click=exit_masquerade).props("unelevated dense size=sm color=white text-color=purple-9").classes("font-bold px-2")

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
        with ui.row().classes("w-full max-w-5xl items-center justify-between gap-4 md:gap-8 no-wrap mt-1"):
            # Desktop-Only Full-Height Left Logo using native ui.image()
            if logo_url:
                ui.image(logo_url).props("fit=contain").classes("hidden md:block shrink-0 rounded-xl").style("width: 220px; height: 220px;")

            # Centered Header Text & Rules
            with ui.column().classes("flex-1 items-center text-center justify-center gap-1 md:gap-2"):
                # Title Row (Mobile text-2xl unchanged, Desktop scaled to md:text-4xl)
                with ui.row().classes("items-center justify-center gap-2 no-wrap"):
                    if logo_url:
                        ui.html(f'<img src="{logo_url}" class="block md:hidden h-9 w-9 object-contain p-0.5 shrink-0 rounded" />')
                    ui.label("NFL Loser Pool").classes("text-3xl md:text-3xl font-black tracking-tight")

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

        # 3. 50/50 Split Primary Pool Selector Bar (Main vs. 2nd Chance)
        def select_pool(target_pool: str):
            if app.storage.user.get("pool") != target_pool:
                app.storage.user["pool"] = target_pool
                ui.navigate.reload()

        border_bar = "border-slate-700" if is_dark else "border-slate-300"
        inactive_txt = "text-slate-200 hover:bg-white/10" if is_dark else "text-slate-700 hover:bg-slate-200/70"

        with ui.row().classes(f"w-full max-w-5xl mt-3 rounded-lg overflow-hidden border {border_bar} gap-0 no-wrap"):
            # Left Half: Main Pool (#1d3d70 when active)
            main_active = (current_tab == "Main")
            main_cls = "flex-1 py-2.5 text-center font-black text-sm md:text-base cursor-pointer select-none transition-colors " + (
                "text-white" if main_active else f"bg-transparent {inactive_txt}"
            )
            main_el = ui.label("Main").classes(main_cls)
            if main_active:
                main_el.style("background-color: #1d3d70;")
            main_el.on("click", lambda: select_pool("Main"))

            # Right Half: 2nd Chance Pool (#974706 when active)
            sc_active = (current_tab == "2nd_Chance")
            sc_cls = "flex-1 py-2.5 text-center font-black text-sm md:text-base cursor-pointer select-none transition-colors " + (
                "text-white" if sc_active else f"bg-transparent {inactive_txt}"
            )
            sc_el = ui.label("2nd Chance").classes(sc_cls)
            if sc_active:
                sc_el.style("background-color: #974706;")
            sc_el.on("click", lambda: select_pool("2nd_Chance"))

        # 4. Unified Page Navigation Row (Picks, Brackets, Chat, Rules, Profile, [Admin])
        unread_chat = get_unread_chat_count(supabase, user) if active_page != "Chat" else 0
        with ui.row().classes("w-full max-w-5xl justify-around items-center py-2.5 mt-1 text-xs md:text-sm font-bold flex-wrap gap-2"):
            nav_items = [
                ("Picks", "/"),
                ("Brackets", "/brackets"),
                ("Chat", "/chat"),
                ("Rules", "/rules"),
                ("Profile", "/profile"),
            ]
            if is_admin_user(supabase, user):
                nav_items.append(("Admin", "/admin"))

            for label, route in nav_items:
                is_active = (active_page == label)
                if is_active:
                    cls = "text-amber-400 underline underline-offset-4" if is_dark else (
                        "text-amber-700 underline underline-offset-4" if is_2nd else "text-blue-700 underline underline-offset-4"
                    )
                else:
                    cls = "text-white/80 hover:text-white" if is_dark else "text-slate-600 hover:text-slate-900"

                with ui.row().classes("items-center gap-1 no-wrap"):
                    ui.link(label, route).classes(f"no-underline {cls}")
                    if label == "Chat" and unread_chat > 0:
                        badge_txt = "9+" if unread_chat > 9 else str(unread_chat)
                        ui.label(badge_txt).classes(
                            "bg-red-600 text-white text-[10px] font-black px-1.5 py-0.2 rounded-full leading-tight shadow-sm"
                        )

    # --- MAIN CONTENT CONTAINER ---
    card_theme = "bg-slate-900 text-white" if is_dark else "bg-white text-slate-900"
    with ui.column().classes("w-full items-center px-3 pb-8 pt-1"):
        with ui.card().classes(f"w-full max-w-5xl p-5 rounded-xl shadow-xl {card_theme}").style(f"border-top: 4px solid {pool_hex};"):
            if not user:
                render_login_box()
            else:
                content_builder(user, current_tab)

def render_login_box():
    ui.label("Player Login").classes("text-2xl font-bold mb-2")
    email_input = ui.input("Email Address").classes("w-full")
    pass_input = ui.input("Password", password=True, password_toggle_button=True).classes("w-full")

    def attempt_login():
        try:
            res = supabase_auth.auth.sign_in_with_password({
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

    # Trigger login when pressing Enter in either input box
    email_input.on("keydown.enter", attempt_login)
    pass_input.on("keydown.enter", attempt_login)

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
    render_layout("Chat", lambda user, pool: render_chat_view(supabase, user, pool))

@ui.page("/rules")
def rules_page():
    render_layout("Rules", lambda user, pool: render_rules_view(pool))

@ui.page("/profile")
def profile_page():
    render_layout("Profile", lambda user, pool: render_profile_view(supabase, user))

@ui.page("/admin")
def admin_page():
    render_layout("Admin", lambda user, pool: render_admin_view(supabase, user))

ui.run(
    host="0.0.0.0",
    port=int(os.environ.get("PORT", 8080)),
    storage_secret=os.environ.get("STORAGE_SECRET", "change-this-to-a-random-long-secret-key"),
    title="2026 NFL Loser Pool"
)

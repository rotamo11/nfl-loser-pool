import os
import time
from types import SimpleNamespace
from nicegui import ui, app
from supabase import create_client, Client

from picks_module import render_picks_view
from overview_module import render_overview_view
from chat_module import render_chat_view
from rules_module import render_rules_view
from profile_module import render_profile_view
from admin_module import render_admin_view, is_admin_user

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY") or os.environ.get("SUPABASE_KEY", "")
SUPABASE_ANON_KEY = os.environ.get("SUPABASE_ANON_KEY") or SUPABASE_SERVICE_KEY

supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
supabase_auth: Client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)

app.add_static_files("/static", "static")

AUTH_CACHE_TTL = 900  # Cache auth & admin status for 15 minutes per session

def get_authenticated_user():
    """Returns the active user (or masqueraded user), caching session checks for fast navigation."""
    now = time.time()
    cached_uid = app.storage.user.get("user_id")
    cached_email = app.storage.user.get("user_email")
    last_verified = app.storage.user.get("auth_verified_at", 0)

    real_user = None
    if cached_uid and cached_email and (now - last_verified) < AUTH_CACHE_TTL:
        real_user = SimpleNamespace(id=cached_uid, email=cached_email)
    else:
        refresh_token = app.storage.user.get("refresh_token")
        if not refresh_token:
            return None
        try:
            res = supabase_auth.auth.refresh_session(refresh_token)
            if res and res.session and res.user:
                app.storage.user["refresh_token"] = res.session.refresh_token
                app.storage.user["user_id"] = str(res.user.id)
                app.storage.user["user_email"] = res.user.email or ""
                app.storage.user["auth_verified_at"] = now

                if "dark_mode" not in app.storage.user:
                    u_row = supabase.table("users").select("dark_mode").eq("id", str(res.user.id)).execute().data or []
                    first_row = next(iter(u_row), {})
                    if first_row:
                        app.storage.user["dark_mode"] = bool(first_row.get("dark_mode", False))

                real_user = res.user
        except Exception:
            saved_theme = app.storage.user.get("dark_mode", False)
            app.storage.user.clear()
            app.storage.user["dark_mode"] = saved_theme
            return None

    if not real_user:
        return None

    # Developer Masquerade Support
    masq_uid = app.storage.user.get("masquerade_uid")
    if masq_uid and str(masq_uid) != str(real_user.id):
        if get_cached_admin_status(real_user):
            return SimpleNamespace(id=masq_uid, email=f"masquerade:{masq_uid}")
        app.storage.user.pop("masquerade_uid", None)
        app.storage.user.pop("masquerade_name", None)

    return real_user

def get_cached_admin_status(user) -> bool:
    if not user:
        return False
    now = time.time()
    cached_val = app.storage.user.get("is_admin_cached")
    cached_at = app.storage.user.get("is_admin_cached_at", 0)
    if cached_val is not None and (now - cached_at) < AUTH_CACHE_TTL:
        return bool(cached_val)

    flag = is_admin_user(supabase, user)
    app.storage.user["is_admin_cached"] = flag
    app.storage.user["is_admin_cached_at"] = now
    return flag

def get_unread_chat_count(user) -> int:
    if not user:
        return 0
    try:
        u_rows = supabase.table("users").select("last_read_chat_at").eq("id", str(user.id)).execute().data or []
        first_row = next(iter(u_rows), {})
        last_read = first_row.get("last_read_chat_at")
        q = supabase.table("pool_chat").select("id", count="exact").neq("user_id", str(user.id))
        if last_read:
            q = q.gt("created_at", last_read)
        res = q.execute()
        return res.count or 0
    except Exception:
        return 0
def render_login_box():
    ui.label("Player Login").classes("text-2xl font-bold mb-2")
    email_input = ui.input("Email Address").classes("w-full")
    pass_input = ui.input("Password", password=True, password_toggle_button=True).classes("w-full")

    def attempt_login():
        try:
            res = supabase_auth.auth.sign_in_with_password({
                "email": email_input.value.strip(),
                "password": pass_input.value.strip(),
            })
            if res and res.session and res.user:
                app.storage.user["refresh_token"] = res.session.refresh_token
                app.storage.user["user_id"] = str(res.user.id)
                app.storage.user["user_email"] = res.user.email or ""
                app.storage.user["auth_verified_at"] = time.time()

                u_row = supabase.table("users").select("dark_mode, is_admin").eq("id", str(res.user.id)).execute().data or []
                first_row = next(iter(u_row), {})
                if first_row:
                    app.storage.user["dark_mode"] = bool(first_row.get("dark_mode", False))
                    app.storage.user["is_admin_cached"] = bool(first_row.get("is_admin", False))
                    app.storage.user["is_admin_cached_at"] = time.time()

                ui.notify("Logged in! Session saved for 7 days.", type="positive")
                ui.navigate.reload()
        except Exception as e:
            ui.notify(f"Login Error: {str(e)}", type="negative", timeout=8000)

    email_input.on("keydown.enter", attempt_login)
    pass_input.on("keydown.enter", attempt_login)
    ui.button("Log In", on_click=attempt_login).classes("w-full mt-3 bg-blue-600 text-white font-bold")

@ui.page("/")
@ui.page("/{subpath:path}")
def spa_shell(subpath: str = ""):
    is_dark = app.storage.user.get("dark_mode", False)
    ui.dark_mode(value=is_dark)

    if app.storage.user.get("pool") not in ["Main", "2nd_Chance"]:
        app.storage.user["pool"] = "Main"

    # Sync active_route on initial page load / refresh
    app.storage.user["active_route"] = "/" + subpath.strip("/") if subpath.strip("/") else "/"

    user = get_authenticated_user()
    logo_url = "/static/loser-logo.png" if os.path.exists("static/loser-logo.png") else ""

    # Masquerade Banner
    if user and app.storage.user.get("masquerade_uid"):
        masq_name = app.storage.user.get("masquerade_name", "Player")
        with ui.row().classes("w-full bg-purple-700 text-white px-4 py-1.5 items-center justify-between text-xs font-bold"):
            ui.label(f"🕵️ MASQUERADE MODE ACTIVE — Viewing as: {masq_name}")
            def exit_masquerade():
                app.storage.user.pop("masquerade_uid", None)
                app.storage.user.pop("masquerade_name", None)
                ui.navigate.reload()
            ui.button("Exit Masquerade", on_click=exit_masquerade, color="white").props("flat dense size=xs")

    @ui.refreshable
    def app_shell():
        current_tab = app.storage.user.get("pool", "Main")
        is_2nd = (current_tab == "2nd_Chance")
        pool_hex = "#974706" if is_2nd else "#1d3d70"
        active_path = app.storage.user.get("active_route", "/")

        banner_bg = "bg-slate-950 text-white" if is_dark else "bg-slate-100 text-slate-900"
        week_hdr_cls = "text-amber-400" if is_dark else ("text-amber-800" if is_2nd else "text-blue-900")
        purse_cls = "text-amber-300" if is_dark else ("text-amber-900" if is_2nd else "text-blue-950")
        text_muted = "text-white/75" if is_dark else "text-slate-600"

        with ui.column().classes(f"w-full items-center pt-2 px-3 pb-0 {banner_bg}"):
            # 1. Centered Logo + Title
            with ui.row().classes("w-full max-w-5xl items-center justify-center gap-2.5 mt-1 no-wrap"):
                if logo_url:
                    ui.html(f'<img src="{logo_url}" class="h-10 w-10 md:h-12 md:w-12 object-contain p-0.5 shrink-0 rounded" />')
                ui.label("NFL Loser Pool").classes("text-2xl sm:text-3xl md:text-4xl font-black tracking-tight whitespace-nowrap")

            # 2. Centered Rules Summary, Deadline Pill, & Purse History
            with ui.column().classes("w-full max-w-5xl items-center text-center justify-center gap-1 md:gap-2 mt-2"):
                with ui.row().classes("w-full justify-center gap-4 md:gap-10 text-xs md:text-sm"):
                    with ui.column().classes("items-center gap-0 md:gap-0.5"):
                        ui.label("Weeks 1-14").classes(f"font-extrabold {week_hdr_cls}")
                        ui.label("Pick 1 team to lose")
                    with ui.column().classes("items-center gap-0 md:gap-0.5"):
                        ui.label("Weeks 15-18").classes(f"font-extrabold {week_hdr_cls}")
                        ui.label("Pick 2 teams to lose")
                    with ui.column().classes("items-center gap-0 md:gap-0.5"):
                        ui.label("Playoffs").classes(f"font-extrabold {week_hdr_cls}")
                        ui.label("Pick ALL losers (repeats allowed)")

                ui.label("Weekly Deadline: Noon ET Sunday, or by kickoff of earlier game").classes(
                    "text-xs md:text-sm font-bold text-white px-3 md:px-5 py-1 md:py-1.5 rounded-full mt-1"
                ).style(f"background-color: {pool_hex};")

                if is_2nd:
                    ui.label("26 Players: $650 Purse ($390 for 1st / $195 for 2nd / $65 for 3rd)").classes(f"text-xs md:text-base font-bold mt-1 {purse_cls}")
                    ui.label("Last Year's Losers: D. Bobrow ($300) • M. Ellis ($150) • D. Tashima ($50)").classes(f"text-[11px] md:text-sm {text_muted}")
                else:
                    ui.label("74 Players | $1850 Purse ($1110 1st / $555 2nd / $185 3rd)").classes(f"text-xs md:text-base font-bold mt-1 {purse_cls}")
                    ui.label("Last Year's Losers: S. King ($765) • A. Conley ($382.50) • B. Kazmierski ($127.50)").classes(f"text-[11px] md:text-sm {text_muted}")

            # 3. 50/50 Split Primary Pool Selector Bar
            def select_pool(target_pool: str):
                if app.storage.user.get("pool") != target_pool:
                    app.storage.user["pool"] = target_pool
                    app_shell.refresh()

            border_bar = "border-slate-700" if is_dark else "border-slate-300"
            inactive_txt = "text-slate-200 hover:bg-white/10" if is_dark else "text-slate-700 hover:bg-slate-200/70"

            with ui.row().classes(f"w-full max-w-5xl mt-3 rounded-lg overflow-hidden border {border_bar} gap-0 no-wrap"):
                main_active = (current_tab == "Main")
                main_el = ui.label("Main").classes(
                    "flex-1 py-2.5 text-center font-black text-sm md:text-base cursor-pointer select-none transition-colors "
                    + ("text-white" if main_active else f"bg-transparent {inactive_txt}")
                )
                if main_active:
                    main_el.style("background-color: #1d3d70;")
                main_el.on("click", lambda: select_pool("Main"))

                sc_active = (current_tab == "2nd_Chance")
                sc_el = ui.label("2nd Chance").classes(
                    "flex-1 py-2.5 text-center font-black text-sm md:text-base cursor-pointer select-none transition-colors "
                    + ("text-white" if sc_active else f"bg-transparent {inactive_txt}")
                )
                if sc_active:
                    sc_el.style("background-color: #974706;")
                sc_el.on("click", lambda: select_pool("2nd_Chance"))

            # 4. Instant SPA Navigation Row
            unread_chat = get_unread_chat_count(user) if active_path != "/chat" else 0
            with ui.row().classes("w-full max-w-5xl justify-around items-center py-2.5 mt-1 text-xs md:text-sm font-bold flex-wrap gap-2"):
                nav_items = [
                    ("Picks", "/"),
                    ("Brackets", "/brackets"),
                    ("Chat", "/chat"),
                    ("Rules", "/rules"),
                    ("Profile", "/profile"),
                ]
                if get_cached_admin_status(user):
                    nav_items.append(("Admin", "/admin"))

                for label, route in nav_items:
                    is_active = (active_path == route)
                    if is_active:
                        cls = "text-amber-400 underline underline-offset-4" if is_dark else (
                            "text-amber-700 underline underline-offset-4" if is_2nd else "text-blue-700 underline underline-offset-4"
                        )
                    else:
                        cls = "text-white/80 hover:text-white" if is_dark else "text-slate-600 hover:text-slate-900"

                    with ui.row().classes("items-center gap-1 no-wrap cursor-pointer") as nav_btn:
                        ui.label(label).classes(cls)
                        if label == "Chat" and unread_chat > 0:
                            badge_txt = "9+" if unread_chat > 9 else str(unread_chat)
                            ui.label(badge_txt).classes(
                                "bg-red-600 text-white text-[10px] font-black px-1.5 py-0.2 rounded-full leading-tight shadow-sm"
                            )

                    def go_to_route(r=route):
                        app.storage.user["active_route"] = r
                        ui.navigate.to(r)
                        app_shell.refresh()

                    nav_btn.on("click", go_to_route)

        # --- MAIN CONTENT CONTAINER WITH ui.sub_pages ---
        card_theme = "bg-slate-900 text-white" if is_dark else "bg-white text-slate-900"
        with ui.column().classes("w-full items-center px-3 pb-8 pt-1"):
            with ui.card().classes(f"w-full max-w-5xl p-5 rounded-xl shadow-xl {card_theme}").style(f"border-top: 4px solid {pool_hex};"):
                if not user:
                    render_login_box()
                else:
                    pool_now = app.storage.user.get("pool", "Main")
                    ui.sub_pages({
                        "/": lambda: render_picks_view(supabase, user, pool_now),
                        "/brackets": lambda: render_overview_view(supabase, user, pool_now),
                        "/chat": lambda: render_chat_view(supabase, user),
                        "/rules": lambda: render_rules_view(pool_now),
                        "/profile": lambda: render_profile_view(supabase, user),
                        "/admin": lambda: render_admin_view(supabase, user),
                    }).classes("w-full")

    app_shell()

if __name__ in {"__main__", "__mp_main__"}:
    ui.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 8080)),
        title="NFL Loser Pool",
        storage_secret=os.environ.get("STORAGE_SECRET", "nfl_loser_pool_secret_2026_key"),
    )

import os
import base64
import datetime
from zoneinfo import ZoneInfo
from nicegui import ui, app

ET_ZONE = ZoneInfo("America/New_York")
SEASON_START_WEDNESDAY = datetime.datetime(2026, 9, 9, 0, 0, 0, tzinfo=ET_ZONE)

def get_current_nfl_week() -> int:
    now_et = datetime.datetime.now(ET_ZONE)
    if now_et < SEASON_START_WEDNESDAY:
        return 1
    return min(22, ((now_et - SEASON_START_WEDNESDAY).days // 7) + 1)

def get_week_col_label(w: int) -> str:
    return {19: "WC", 20: "DIV", 21: "CONF", 22: "SB"}.get(w, f"Wk {w}")

# Replace get_logo_data_uri at the top of overview_module.py with:
def get_logo_url(team_code: str) -> str:
    clean = team_code.replace("_SO", "").strip().upper()
    fname = f"{'BYE' if clean == 'BYE' else clean}.svg"
    return f"/static/{fname}" if os.path.exists(f"static/{fname}") else ""

def render_overview_view(supabase, user, pool_slug: str):
    current_user_id = str(user.id)
    current_week = get_current_nfl_week()

    # 1. Fetch Users, Registrations, and All Picks for the Active Pool
    users_data = supabase.table("users").select("id, username, first_name, last_name").execute().data or []
    user_info_map = {}
    for u in users_data:
        uid = str(u["id"])
        full_name = f"{u.get('first_name') or ''} {u.get('last_name') or ''}".strip() or "Registered Player"
        user_info_map[uid] = {
            "username": u.get("username") or "Anonymous",
            "full_name": full_name
        }

    regs_data = (
        supabase.table("tournament_registrations")
        .select("*")
        .eq("game_type", pool_slug)
        .eq("is_enrolled", True)
        .execute()
        .data or []
    )

    if not regs_data:
        ui.label(f"No enrolled players found for {pool_slug.replace('_', ' ')}.").classes("text-gray-500 italic")
        return

    all_picks = (
        supabase.table("user_picks")
        .select("*")
        .eq("game_type", pool_slug)
        .execute()
        .data or []
    )

    # Index picks by user_id -> week -> list of picks (supports multi-pick weeks 15-18 & playoffs)
    picks_by_user = {}
    viewer_finalized_weeks = set()

    for p in all_picks:
        uid = str(p["user_id"])
        w = p["week"]
        picks_by_user.setdefault(uid, {}).setdefault(w, []).append(p)
        if uid == current_user_id and p.get("pick_state") in ["Finalized", "Correct", "Incorrect"]:
            viewer_finalized_weeks.add(w)

    # Determine starting week (Week 6 for 2nd Chance, Week 1 for Main)
    start_week = 6 if pool_slug == "2nd_Chance" else 1
    max_visible_week = max(current_week, max((p["week"] for p in all_picks), default=current_week))
    visible_weeks = list(range(start_week, min(22, max_visible_week) + 1))

    # Group players by bracket status and sort alphabetically by username
    def sort_players(plist):
        return sorted(plist, key=lambda r: user_info_map.get(str(r["user_id"]), {}).get("username", "").lower())

    loser_bracket = sort_players([r for r in regs_data if r.get("bracket_status") == "Loser Bracket"])
    winner_bracket = sort_players([r for r in regs_data if r.get("bracket_status") == "Winner Bracket"])
    eliminated_bracket = sort_players([r for r in regs_data if r.get("bracket_status") == "Eliminated"])

    is_dark = app.storage.user.get("dark_mode", False)

    # Current Player Status Header
    current_user_name = user_info_map.get(current_user_id, {}).get("username", "Player")
    current_reg = next((r for r in regs_data if str(r["user_id"]) == current_user_id), None)
    current_status = current_reg.get("bracket_status", "Not Enrolled") if current_reg else "Not Enrolled"

    active_total = len(loser_bracket) + len(winner_bracket)
    with ui.row().classes("w-full items-center justify-between mb-4 pb-2 border-b border-gray-200 dark:border-slate-700"):
        ui.label(f"Status for {current_user_name}: {current_status}").classes("text-lg md:text-xl font-black")
        ui.badge(f"Remaining Active: {active_total} / {len(regs_data)}", color="primary").classes("text-xs font-bold px-2 py-1")

    def build_bracket_section(title: str, badge_color: str, players: list):
        if not players:
            return

        with ui.row().classes("items-center gap-2 mt-4 mb-2"):
            ui.label(title).classes("text-lg font-extrabold")
            ui.badge(str(len(players)), color=badge_color).classes("font-bold")

        border_cls = "border-slate-700 divide-slate-700" if is_dark else "border-gray-200 divide-gray-200"
        hdr_bg = "bg-slate-800 text-slate-200" if is_dark else "bg-gray-100 text-slate-800"

        with ui.element("div").classes(f"w-full overflow-x-auto border rounded-lg mb-4 {border_cls}"):
            with ui.column().classes(f"min-w-max gap-0 divide-y {border_cls}"):
                
                # --- HEADER ROW ---
                with ui.row().classes(f"w-full items-center py-2 px-2 no-wrap gap-1 {hdr_bg}"):
                    ui.label("PLAYER").classes(f"w-36 shrink-0 font-black text-xs sticky left-0 z-10 px-1 {hdr_bg}")
                    for w in visible_weeks:
                        ui.label(get_week_col_label(w)).classes("w-16 shrink-0 text-center font-extrabold text-xs")

                # --- PLAYER ROWS ---
                for reg in players:
                    uid = str(reg["user_id"])
                    info = user_info_map.get(uid, {"username": "Anonymous", "full_name": "Registered Player"})
                    user_week_map = picks_by_user.get(uid, {})
                    is_own_row = (uid == current_user_id)

                    if is_own_row:
                        row_bg = "bg-blue-950/60" if is_dark else "bg-blue-50/70"
                        sticky_bg = "bg-slate-800" if is_dark else "bg-blue-50"
                    else:
                        row_bg = "bg-slate-900" if is_dark else "bg-white"
                        sticky_bg = "bg-slate-900" if is_dark else "bg-white"

                    with ui.row().classes(f"w-full items-center py-1.5 px-2 no-wrap gap-1 {row_bg}"):
                        with ui.element("div").classes(f"w-36 shrink-0 sticky left-0 z-10 px-1 {sticky_bg}"):
                            lbl = ui.label(info["username"]).classes("text-xs font-bold truncate cursor-help underline decoration-dotted decoration-gray-400")
                            with lbl:
                                ui.tooltip(f"👤 {info['full_name']}").classes("bg-slate-800 text-white text-xs font-semibold")

                        for w in visible_weeks:
                            week_entries = user_week_map.get(w, [])
                            if not week_entries:
                                dot_cls = "text-slate-600" if is_dark else "text-gray-400"
                                ui.label("•").classes(f"w-16 shrink-0 text-center font-bold text-sm {dot_cls}")
                                continue

                            week_passed = (w < current_week)
                            viewer_locked = (w in viewer_finalized_weeks)
                            can_reveal = week_passed or is_own_row or viewer_locked

                            if not can_reveal:
                                hid_cls = "bg-slate-800 text-slate-400" if is_dark else "bg-gray-200/70 text-gray-500"
                                with ui.element("div").classes("w-16 shrink-0 flex justify-center"):
                                    ui.label("🔒 Hid").classes(f"px-1.5 py-0.5 rounded text-[10px] font-bold {hid_cls}")
                            else:
                                with ui.column().classes("w-16 shrink-0 items-center justify-center gap-0.5"):
                                    for entry in week_entries:
                                        raw_pick = entry["team_picked"].upper()
                                        clean_team = raw_pick.replace("_SO", "").strip()
                                        state = entry.get("pick_state", "Pending")
                                        has_so = raw_pick.endswith("_SO")

                                        if state == "Correct" or clean_team == "BYE":
                                            cell_cls = "bg-emerald-500/20 text-emerald-300 border border-emerald-500/40" if is_dark else "bg-emerald-500/20 text-emerald-800 border border-emerald-500/40"
                                        elif state == "Incorrect":
                                            cell_cls = "bg-red-500/20 text-red-300 border border-red-500/40" if is_dark else "bg-red-500/20 text-red-800 border border-red-500/40"
                                        else:
                                            cell_cls = "bg-slate-800 text-slate-200 border border-slate-700" if is_dark else "bg-gray-100 text-gray-800"

                                        with ui.row().classes(f"w-full items-center justify-center gap-1 px-1.5 py-0.5 rounded no-wrap {cell_cls}"):
                                            if url := get_logo_url(clean_team):
                                                ui.html(f'<img src="{url}" class="w-5 h-3.5 object-contain p-0.5 shrink-0" />')
                                            display_txt = f"{clean_team}{'🎯' if has_so else ''}"
                                            ui.label(display_txt).classes("text-[10px] font-extrabold leading-none")

    build_bracket_section("Loser Bracket (0 Wrong)", "green", loser_bracket)
    build_bracket_section("Winner Bracket (1 Wrong)", "amber", winner_bracket)
    build_bracket_section("Eliminated", "red", eliminated_bracket)

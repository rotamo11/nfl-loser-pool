import os
import base64
import datetime
from zoneinfo import ZoneInfo
from nicegui import ui

ET_ZONE = ZoneInfo("America/New_York")
SEASON_START_WEDNESDAY = datetime.datetime(2026, 9, 9, 0, 0, 0, tzinfo=ET_ZONE)

def get_current_nfl_week() -> int:
    now_et = datetime.datetime.now(ET_ZONE)
    if now_et < SEASON_START_WEDNESDAY:
        return 1
    return min(22, ((now_et - SEASON_START_WEDNESDAY).days // 7) + 1)

def get_week_col_label(w: int) -> str:
    return {19: "WC", 20: "DIV", 21: "CONF", 22: "SB"}.get(w, f"Wk {w}")

def get_logo_data_uri(team_code: str) -> str:
    clean = team_code.replace("_SO", "").strip().upper()
    path = f"static/{'BYE' if clean == 'BYE' else clean}.svg"
    if os.path.exists(path):
        with open(path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode("utf-8")
        return f"data:image/svg+xml;base64,{b64}"
    return ""

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

    # Determine visible week columns (up to current week, or 2nd chance start)
    max_visible_week = max(current_week, max((p["week"] for p in all_picks), default=current_week))
    visible_weeks = list(range(1, min(22, max_visible_week) + 1))

    # Group players by bracket status and sort alphabetically by username
    def sort_players(plist):
        return sorted(plist, key=lambda r: user_info_map.get(str(r["user_id"]), {}).get("username", "").lower())

    losers_bracket = sort_players([r for r in regs_data if r.get("bracket_status") == "Loser Bracket"])
    second_chance_bracket = sort_players([r for r in regs_data if r.get("bracket_status") == "2nd Chance Bracket"])
    eliminated_bracket = sort_players([r for r in regs_data if r.get("bracket_status") == "Eliminated"])

    # Summary Counter Strip
    active_total = len(losers_bracket) + len(second_chance_bracket)
    with ui.row().classes("w-full items-center justify-between mb-4 pb-2 border-b border-gray-200 dark:border-slate-700"):
        ui.label(f"Standings Overview — {pool_slug.replace('_', ' ')}").classes("text-xl font-black")
        ui.badge(f"Active Remaining: {active_total} / {len(regs_data)}", color="primary").classes("text-xs font-bold px-2 py-1")
    def build_bracket_section(title: str, badge_color: str, players: list):
        if not players:
            return

        with ui.row().classes("items-center gap-2 mt-4 mb-2"):
            ui.label(title).classes("text-lg font-extrabold")
            ui.badge(str(len(players)), color=badge_color).classes("font-bold")

        # Single outer horizontal scroll container for the entire bracket table
        with ui.element("div").classes("w-full overflow-x-auto border border-gray-200 dark:border-slate-700 rounded-lg mb-4"):
            with ui.column().classes("min-w-max gap-0 divide-y divide-gray-200 dark:divide-slate-700"):
                
                # --- HEADER ROW ---
                with ui.row().classes("w-full items-center bg-gray-100 dark:bg-slate-800 py-2 px-2 no-wrap gap-1"):
                    ui.label("PLAYER").classes("w-36 shrink-0 font-black text-xs sticky left-0 bg-gray-100 dark:bg-slate-800 z-10 px-1")
                    for w in visible_weeks:
                        ui.label(get_week_col_label(w)).classes("w-16 shrink-0 text-center font-extrabold text-xs")

                # --- PLAYER ROWS ---
                for reg in players:
                    uid = str(reg["user_id"])
                    info = user_info_map.get(uid, {"username": "Anonymous", "full_name": "Registered Player"})
                    user_week_map = picks_by_user.get(uid, {})
                    is_own_row = (uid == current_user_id)

                    row_bg = "bg-blue-50/40 dark:bg-blue-900/10" if is_own_row else "bg-white dark:bg-slate-900"

                    with ui.row().classes(f"w-full items-center py-1.5 px-2 no-wrap gap-1 {row_bg}"):
                        # Sticky Username Cell with Hover/Tap Tooltip
                        with ui.element("div").classes(f"w-36 shrink-0 sticky left-0 z-10 px-1 {row_bg}"):
                            lbl = ui.label(info["username"]).classes("text-xs font-bold truncate cursor-help underline decoration-dotted decoration-gray-400")
                            with lbl:
                                ui.tooltip(f"👤 {info['full_name']}").classes("bg-slate-800 text-white text-xs font-semibold")

                        # Week Pick Cells
                        for w in visible_weeks:
                            week_entries = user_week_map.get(w, [])
                            if not week_entries:
                                ui.label("•").classes("w-16 shrink-0 text-center text-gray-400 font-bold text-sm")
                                continue

                            # Anti-Scouting Privacy Curtain Check
                            week_passed = (w < current_week)
                            viewer_locked = (w in viewer_finalized_weeks)
                            can_reveal = week_passed or is_own_row or viewer_locked

                            if not can_reveal:
                                with ui.element("div").classes("w-16 shrink-0 flex justify-center"):
                                    ui.label("🔒 Hid").classes("px-1.5 py-0.5 rounded bg-gray-200/70 dark:bg-slate-700 text-gray-500 dark:text-gray-300 text-[10px] font-bold")
                            else:
                                # Stack multiple picks vertically if Week 15-18 or Playoffs
                                with ui.column().classes("w-16 shrink-0 items-center justify-center gap-0.5"):
                                    for entry in week_entries:
                                        raw_pick = entry["team_picked"].upper()
                                        clean_team = raw_pick.replace("_SO", "").strip()
                                        state = entry.get("pick_state", "Pending")
                                        has_so = raw_pick.endswith("_SO")

                                        if state == "Correct" or clean_team == "BYE":
                                            cell_cls = "bg-emerald-500/20 text-emerald-800 dark:text-emerald-300 border border-emerald-500/40"
                                        elif state == "Incorrect":
                                            cell_cls = "bg-red-500/20 text-red-800 dark:text-red-300 border border-red-500/40"
                                        else:
                                            cell_cls = "bg-gray-100 dark:bg-slate-800 text-gray-800 dark:text-gray-200"

                                        with ui.row().classes(f"w-full items-center justify-center gap-0.5 px-1 py-0.5 rounded no-wrap {cell_cls}"):
                                            if uri := get_logo_data_uri(clean_team):
                                                ui.image(uri).classes("w-4 h-3 object-contain shrink-0")
                                            display_txt = f"{clean_team}{'🎯' if has_so else ''}"
                                            ui.label(display_txt).classes("text-[10px] font-extrabold leading-none")

    # Render All Active & Eliminated Brackets
    build_bracket_section("🏅 Loser Bracket (0 Losses)", "green", losers_bracket)
    build_bracket_section("🥈 2nd Chance Bracket (1 Loss)", "amber", second_chance_bracket)
    build_bracket_section("❌ Eliminated", "red", eliminated_bracket)

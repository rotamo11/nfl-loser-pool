import os
import datetime
from collections import Counter
from zoneinfo import ZoneInfo
from nicegui import ui, app
from admin_module import is_admin_user

ET_ZONE = ZoneInfo("America/New_York")
SEASON_START_WEDNESDAY = datetime.datetime(2026, 9, 9, 0, 0, 0, tzinfo=ET_ZONE)

def get_current_nfl_week() -> int:
    now_et = datetime.datetime.now(ET_ZONE)
    if now_et < SEASON_START_WEDNESDAY:
        return 1
    return min(22, ((now_et - SEASON_START_WEDNESDAY).days // 7) + 1)

def get_week_col_label(w: int) -> str:
    return {19: "WC", 20: "DIV", 21: "CONF", 22: "SB"}.get(w, f"Wk {w}")

def get_week_full_label(w: int) -> str:
    return {19: "Wildcard", 20: "Divisional", 21: "Conference", 22: "Super Bowl"}.get(w, f"Week {w}")

def get_logo_url(team_code: str) -> str:
    clean = team_code.replace("_SO", "").strip().upper()
    fname = f"{'BYE' if clean == 'BYE' else clean}.svg"
    return f"/static/{fname}" if os.path.exists(f"static/{fname}") else ""

def render_overview_view(supabase, user, pool_slug: str):
    current_user_id = str(user.id)
    current_week = get_current_nfl_week()
    is_dark = app.storage.user.get("dark_mode", False)
    admin_flag = is_admin_user(supabase, user)

    if "selected_week" not in app.storage.user:
        app.storage.user["selected_week"] = current_week

    users_data = supabase.table("users").select("id, username, first_name, last_name").execute().data or []
    user_info_map = {}
    for u in users_data:
        uid = str(u["id"])
        full_name = f"{u.get('first_name') or ''} {u.get('last_name') or ''}".strip() or "Registered Player"
        user_info_map[uid] = {"username": u.get("username") or "Anonymous", "full_name": full_name}

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

    all_picks = supabase.table("user_picks").select("*").eq("game_type", pool_slug).execute().data or []

    picks_by_user = {}
    viewer_finalized_weeks = set()
    team_week_outcomes = {}

    for p in all_picks:
        uid = str(p["user_id"])
        w = p["week"]
        picks_by_user.setdefault(uid, {}).setdefault(w, []).append(p)
        if uid == current_user_id and p.get("pick_state") in ["Finalized", "Correct", "Incorrect"]:
            viewer_finalized_weeks.add(w)
        clean_t = p["team_picked"].replace("_SO", "").strip().upper()
        if p.get("pick_state") in ["Correct", "Incorrect"]:
            team_week_outcomes[(w, clean_t)] = p["pick_state"]

    start_week = 6 if pool_slug == "2nd_Chance" else 1
    max_visible_week = max(current_week, max((p["week"] for p in all_picks), default=current_week))
    visible_weeks = list(range(start_week, min(22, max_visible_week) + 1))

    def sort_players(plist):
        return sorted(plist, key=lambda r: user_info_map.get(str(r["user_id"]), {}).get("username", "").lower())

    losers_bracket = sort_players([r for r in regs_data if r.get("bracket_status") == "Loser Bracket"])
    winner_bracket = sort_players([r for r in regs_data if r.get("bracket_status") == "Winner Bracket"])
    eliminated_bracket = sort_players([r for r in regs_data if r.get("bracket_status") == "Eliminated"])

    # Current Player Status Header
    current_user_name = user_info_map.get(current_user_id, {}).get("username", "Player")
    current_reg = next((r for r in regs_data if str(r["user_id"]) == current_user_id), None)
    current_status = current_reg.get("bracket_status", "Not Enrolled") if current_reg else "Not Enrolled"
    active_total = len(losers_bracket) + len(winner_bracket)

    with ui.row().classes("w-full items-center justify-between mb-3 pb-2 border-b border-gray-200 dark:border-slate-700"):
        ui.label(f"Status for {current_user_name}: {current_status}").classes("text-lg md:text-xl font-black")
        ui.badge(f"Remaining Active: {active_total} / {len(regs_data)}", color="primary").classes("text-xs font-bold px-2 py-1")
    # Target (Wed-Tue) Week Selector + Admin "Show All Picks" Checkbox
    week_opts = {
        w: f"{get_week_full_label(w)} (current)" if w == current_week else get_week_full_label(w)
        for w in range(start_week, 23)
    }
    default_sel_w = app.storage.user["selected_week"] if app.storage.user["selected_week"] in week_opts else current_week

    with ui.row().classes("w-full items-center gap-4 mb-3 flex-wrap"):
        dist_week_sel = ui.select(week_opts, value=default_sel_w, label="Target (Wed-Tue)").classes("w-52")
        admin_reveal_chk = ui.checkbox("Show All Picks (Admin)", value=False) if admin_flag else None

    @ui.refreshable
    def overview_body():
        target_w = dist_week_sel.value
        app.storage.user["selected_week"] = target_w
        admin_override = bool(admin_reveal_chk and admin_reveal_chk.value)

        # ================================================================
        # WEEKLY PICK DISTRIBUTION (Shaded Correct/Incorrect)
        # ================================================================
        with ui.card().classes("w-full p-3 mb-4 border border-slate-200 dark:border-slate-700 shadow-none"):
            ui.label(f"{get_week_full_label(target_w)} Pick Distribution").classes("text-sm font-extrabold mb-1")

            week_passed = (target_w < current_week)
            viewer_locked = (target_w in viewer_finalized_weeks)

            if not (week_passed or viewer_locked or admin_override):
                ui.label(f"🔒 Lock in your {get_week_full_label(target_w)} pick on the Picks page to unlock this week's distribution.").classes(
                    "text-xs font-semibold opacity-75 italic py-1"
                )
            else:
                enrolled_ids = {str(r["user_id"]) for r in regs_data}
                week_team_counts = Counter()
                for p in all_picks:
                    if str(p["user_id"]) in enrolled_ids and p["week"] == target_w:
                        clean_t = p["team_picked"].replace("_SO", "").strip().upper()
                        if clean_t:
                            week_team_counts[clean_t] += 1

                if not week_team_counts:
                    ui.label("No picks logged for this week yet.").classes("text-xs opacity-70 italic py-1")
                else:
                    sorted_dist = sorted(week_team_counts.items(), key=lambda item: (0 if item[0] == "BYE" else 1, -item[1], item[0]))
                    total_logged = sum(week_team_counts.values())

                    with ui.row().classes("w-full flex-wrap gap-2 mt-1"):
                        for team_code, count in sorted_dist:
                            pct = round((count / total_logged) * 100)
                            outcome = team_week_outcomes.get((target_w, team_code))

                            if outcome == "Correct" or team_code == "BYE":
                                pill_cls = "bg-emerald-500/20 text-emerald-300 border-emerald-500/40" if is_dark else "bg-emerald-500/20 text-emerald-800 border-emerald-500/40"
                            elif outcome == "Incorrect":
                                pill_cls = "bg-red-500/20 text-red-300 border-red-500/40" if is_dark else "bg-red-500/20 text-red-800 border-red-500/40"
                            else:
                                pill_cls = "bg-slate-800/60 border-slate-700" if is_dark else "bg-slate-50 border-slate-200"

                            with ui.row().classes(f"items-center gap-1.5 px-2.5 py-1.5 rounded-lg border {pill_cls} no-wrap"):
                                if url := get_logo_url(team_code):
                                    ui.html(f'<img src="{url}" class="w-5 h-3.5 object-contain p-0.5 shrink-0" />')
                                ui.label(team_code).classes("text-xs font-extrabold")
                                ui.badge(f"{count}", color="primary" if team_code != "BYE" else "positive").classes("text-[10px] font-bold")

        # ================================================================
        # BRACKET TABLES
        # ================================================================
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
                    with ui.row().classes(f"w-full items-center py-2 px-2 no-wrap gap-1 {hdr_bg}"):
                        ui.label("PLAYER").classes(f"w-36 shrink-0 font-black text-xs sticky left-0 z-10 px-1 {hdr_bg}")
                        for w in visible_weeks:
                            ui.label(get_week_col_label(w)).classes("w-16 shrink-0 text-center font-extrabold text-xs")

                    for reg in players:
                        uid = str(reg["user_id"])
                        info = user_info_map.get(uid, {"username": "Anonymous", "full_name": "Registered Player"})
                        user_week_map = picks_by_user.get(uid, {})
                        is_own_row = (uid == current_user_id)

                        row_bg = ("bg-blue-950/60" if is_dark else "bg-blue-50/70") if is_own_row else ("bg-slate-900" if is_dark else "bg-white")
                        sticky_bg = ("bg-slate-800" if is_dark else "bg-blue-50") if is_own_row else ("bg-slate-900" if is_dark else "bg-white")

                        with ui.row().classes(f"w-full items-center py-1.5 px-2 no-wrap gap-1 {row_bg}"):
                            with ui.element("div").classes(f"w-36 shrink-0 sticky left-0 z-10 px-1 {sticky_bg}"):
                                lbl = ui.label(info["username"]).classes("text-xs font-bold truncate cursor-help underline decoration-dotted decoration-gray-400")
                                with lbl:
                                    ui.tooltip(f"👤 {info['full_name']}").classes("bg-slate-800 text-white text-xs font-semibold")

                            for w in visible_weeks:
                                week_entries = user_week_map.get(w, [])
                                if not week_entries:
                                    ui.label("•").classes(f"w-16 shrink-0 text-center font-bold text-sm {'text-slate-600' if is_dark else 'text-gray-400'}")
                                    continue

                                can_reveal = (w < current_week) or is_own_row or (w in viewer_finalized_weeks) or admin_override
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
                                            if state == "Correct" or clean_team == "BYE":
                                                cell_cls = "bg-emerald-500/20 text-emerald-300 border border-emerald-500/40" if is_dark else "bg-emerald-500/20 text-emerald-800 border border-emerald-500/40"
                                            elif state == "Incorrect":
                                                cell_cls = "bg-red-500/20 text-red-300 border border-red-500/40" if is_dark else "bg-red-500/20 text-red-800 border border-red-500/40"
                                            else:
                                                cell_cls = "bg-slate-800 text-slate-200 border border-slate-700" if is_dark else "bg-gray-100 text-gray-800"

                                            with ui.row().classes(f"w-full items-center justify-center gap-1 px-1.5 py-0.5 rounded no-wrap {cell_cls}"):
                                                if url := get_logo_url(clean_team):
                                                    ui.html(f'<img src="{url}" class="w-5 h-3.5 object-contain p-0.5 shrink-0" />')
                                                ui.label(f"{clean_team}{'🎯' if raw_pick.endswith('_SO') else ''}").classes("text-[10px] font-extrabold leading-none")

        build_bracket_section("Loser Bracket (0 Wrong)", "green", losers_bracket)
        build_bracket_section("Winner Bracket (1 Wrong)", "amber", winner_bracket)
        build_bracket_section("Eliminated", "red", eliminated_bracket)

    dist_week_sel.on_value_change(lambda: overview_body.refresh())
    if admin_reveal_chk:
        admin_reveal_chk.on_value_change(lambda: overview_body.refresh())
    overview_body()

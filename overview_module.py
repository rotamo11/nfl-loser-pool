import os
import asyncio
from nicegui import ui, app, run
from picks_module import get_current_nfl_week, get_logo_url

def get_week_col_header(w: int) -> str:
    if w <= 18:
        return f"Wk {w}"
    return {19: "WC", 20: "Div", 21: "Conf", 22: "SB"}.get(w, f"Wk {w}")

def get_week_full_label(w: int) -> str:
    if w <= 18:
        return f"Week {w}"
    return {19: "Wild Card", 20: "Divisional", 21: "Conference", 22: "Super Bowl"}.get(w, f"Week {w}")

async def render_overview_view(supabase, user, pool_slug: str):
    current_week = get_current_nfl_week()
    current_user_id = str(user.id)

    # Fetch users, registrations, and picks concurrently for fast tab switching
    users, regs, all_picks = await asyncio.gather(
        run.io_bound(lambda: supabase.table("users").select("id, username, first_name, last_name").execute().data or []),
        run.io_bound(lambda: supabase.table("tournament_registrations").select("user_id, game_type, is_enrolled, bracket_status").eq("game_type", pool_slug).eq("is_enrolled", True).execute().data or []),
        run.io_bound(lambda: supabase.table("user_picks").select("user_id, week, team_picked, pick_state").eq("game_type", pool_slug).execute().data or []),
    )

    user_map = {}
    for u in users:
        uid = str(u["id"])
        uname = (u.get("username") or "Unknown").strip()
        full_name = f"{u.get('first_name') or ''} {u.get('last_name') or ''}".strip()
        user_map[uid] = {"username": uname, "full_name": full_name}

    enrolled_uid_set = {str(r["user_id"]) for r in regs}
    is_viewer_enrolled = (current_user_id in enrolled_uid_set)

    picks_by_user = {}
    viewer_finalized_weeks = set()
    team_week_outcomes = {}
    weeks_with_picks = set()
    weeks_with_unfinalized = set()

    for p in all_picks:
        uid = str(p["user_id"])
        w = p["week"]
        state = p.get("pick_state")
        picks_by_user.setdefault(uid, {}).setdefault(w, []).append(p)
        weeks_with_picks.add(w)

        if state in ["Finalized", "Correct", "Incorrect"]:
            if uid == current_user_id:
                viewer_finalized_weeks.add(w)
        else:
            weeks_with_unfinalized.add(w)

        clean_t = p["team_picked"].replace("_SO", "").strip().upper()
        if state in ["Correct", "Incorrect"]:
            team_week_outcomes[(w, clean_t)] = state

    fully_finalized_weeks = weeks_with_picks - weeks_with_unfinalized

    start_week = 6 if pool_slug == "2nd_Chance" else 1
    end_week = max(start_week, current_week)
    visible_weeks = list(range(start_week, end_week + 1))

    is_dark = app.storage.user.get("dark_mode", False)
    pool_label = "2nd Chance" if pool_slug == "2nd_Chance" else "Main"

    viewer_reg = next((r for r in regs if str(r["user_id"]) == current_user_id), None)
    viewer_status = viewer_reg.get("bracket_status", "Not Enrolled") if viewer_reg else "Not Enrolled"
    active_total = sum(1 for r in regs if r.get("bracket_status") != "Eliminated")

    # Line 1: [Pool] Pool - Standings
    ui.label(f"{pool_label} Pool - Standings").classes("text-xl font-black")

    # Line 2: Status (left) & Remaining Active #/# (right)
    with ui.row().classes("w-full items-center justify-between pb-2 mb-3 border-b border-gray-200 dark:border-slate-700"):
        ui.label(f"Status: {viewer_status}").classes("text-sm md:text-base font-extrabold")
        ui.badge(f"Remaining Active: {active_total} / {len(regs)}", color="primary").classes("text-xs font-bold px-2.5 py-1")

    # Line 3: Enclosed Rectangle Week Selector with "(present)" tag
    week_opts = {
        w: f"{get_week_full_label(w)} (present)" if w == current_week else get_week_full_label(w)
        for w in visible_weeks
    }
    with ui.row().classes("w-full items-center mb-3"):
        dist_week_select = ui.select(
            week_opts,
            value=end_week,
            label="Select Week (Wed-Tue)",
        ).props("dense outlined").classes("w-52")

    if not is_viewer_enrolled:
        ui.label(
            f"Note: You are viewing the {pool_label} Pool as a spectator. Current-week picks reveal once all picks for the week are finalized."
        ).classes("text-xs font-semibold text-amber-600 dark:text-amber-400 mb-2")

    @ui.refreshable
    def overview_body():
        target_w = dist_week_select.value
        admin_override = bool(app.storage.user.get("admin_reveal_override", False))

        # --- WEEKLY PICK DISTRIBUTION ---
        dist_border = "border-amber-500/40" if pool_slug == "2nd_Chance" else "border-blue-500/40"
        with ui.card().classes(f"w-full p-3 mb-4 border {dist_border} shadow-none"):
            ui.label(f"{get_week_full_label(target_w)} Pick Distribution").classes("text-sm font-extrabold mb-1")

            week_passed = (target_w < current_week)
            viewer_locked = (target_w in viewer_finalized_weeks)
            all_locked = (target_w in fully_finalized_weeks)

            if not (week_passed or viewer_locked or all_locked or admin_override):
                ui.label(f"🔒 Lock in your {get_week_full_label(target_w)} pick on the Picks page (or wait for all picks to finalize) to unlock this week's distribution.").classes(
                    "text-xs font-semibold opacity-75 italic py-1"
                )
            else:
                week_team_counts = {}
                for uid in enrolled_uid_set:
                    for p in picks_by_user.get(uid, {}).get(target_w, []):
                        if p.get("pick_state") in ["Finalized", "Correct", "Incorrect"]:
                            clean_code = p["team_picked"].replace("_SO", "").strip().upper()
                            week_team_counts[clean_code] = week_team_counts.get(clean_code, 0) + 1

                if not week_team_counts:
                    ui.label(f"No finalized picks logged yet for {get_week_full_label(target_w)}.").classes("text-xs opacity-70 italic")
                else:
                    def dist_sort_key(pair):
                        team, cnt = pair
                        return (0 if team == "BYE" else 1, -cnt, team)

                    sorted_dist = sorted(week_team_counts.items(), key=dist_sort_key)
                    total_logged = sum(week_team_counts.values())
                    desktop_cols = min(len(sorted_dist), 15)

                    ui.add_head_html("""
                        <style>
                            .dist-grid-dynamic {
                                display: grid;
                                grid-template-columns: repeat(5, minmax(0, 1fr));
                                gap: 0.35rem;
                                width: 100%;
                            }
                            @media (min-width: 640px) {
                                .dist-grid-dynamic { grid-template-columns: repeat(min(var(--cols, 8), 8), minmax(0, 1fr)); }
                            }
                            @media (min-width: 1024px) {
                                .dist-grid-dynamic { grid-template-columns: repeat(var(--cols, 15), minmax(0, 1fr)); }
                            }
                        </style>
                    """)

                    with ui.element("div").classes("dist-grid-dynamic mt-2").style(f"--cols: {desktop_cols};"):
                        for team_code, count in sorted_dist:
                            pct = round((count / total_logged) * 100)
                            outcome = team_week_outcomes.get((target_w, team_code))

                            if outcome == "Correct" or team_code == "BYE":
                                card_cls = "bg-emerald-500/20 text-emerald-300 border-emerald-500/40" if is_dark else "bg-emerald-500/20 text-emerald-800 border-emerald-500/40"
                            elif outcome == "Incorrect":
                                card_cls = "bg-red-500/20 text-red-300 border-red-500/40" if is_dark else "bg-red-500/20 text-red-800 border-red-500/40"
                            else:
                                card_cls = "bg-slate-800/60 border-slate-700" if is_dark else "bg-slate-50 border-slate-200"

                            with ui.column().classes(f"w-full items-center justify-center py-1.5 px-1 rounded-lg border {card_cls} gap-0.5 text-center"):
                                if url := get_logo_url(team_code):
                                    ui.html(f'<img src="{url}" class="w-6 h-4 object-contain p-0.5 shrink-0" />')
                                ui.label(team_code).classes("text-[11px] font-black leading-tight")
                                ui.label(f"{count}").classes("text-[11px] font-extrabold opacity-85 leading-none")
                                with ui.tooltip():
                                    ui.label(f"{team_code}: {count} pick{'s' if count != 1 else ''} ({pct}%)")
        # --- BRACKET TABLES ---
        def build_bracket_section(section_title: str, badge_color: str, players_list: list):
            if not players_list:
                return

            players_list = sorted(players_list, key=lambda x: x["username"].lower())
            with ui.row().classes("items-center gap-2 mt-4 mb-2"):
                ui.label(section_title).classes("text-base font-extrabold")
                ui.badge(f"{len(players_list)}", color=badge_color).classes("text-xs font-bold")

            sticky_bg = "bg-slate-900" if is_dark else "bg-white"
            border_cls = "border-slate-700" if is_dark else "border-gray-200"
            header_bg = "bg-slate-800/80 text-slate-200" if is_dark else "bg-gray-100 text-gray-800"

            with ui.element("div").classes(f"w-full overflow-x-auto border {border_cls} rounded-lg mb-4"):
                with ui.column().classes("min-w-max gap-0"):
                    with ui.row().classes(f"items-center py-2 px-2 {header_bg} border-b {border_cls} text-xs font-extrabold no-wrap gap-1"):
                        ui.label("Player").classes(f"w-36 md:w-44 shrink-0 sticky left-0 z-10 {header_bg} px-2 py-0.5")
                        for w in visible_weeks:
                            ui.label(get_week_col_header(w)).classes("w-16 shrink-0 text-center")

                    for pl in players_list:
                        uid = pl["uid"]
                        is_own_row = (uid == current_user_id)
                        user_week_map = picks_by_user.get(uid, {})
                        row_highlight = (
                            ("bg-blue-950/40" if is_dark else "bg-blue-50/70")
                            if is_own_row else ""
                        )

                        with ui.row().classes(f"items-center py-1.5 px-2 border-b {border_cls} {row_highlight} no-wrap gap-1"):
                            with ui.row().classes(f"w-36 md:w-44 shrink-0 sticky left-0 z-10 {sticky_bg} {row_highlight} px-2 py-0.5 items-center gap-1 cursor-pointer"):
                                name_cls = "font-black text-blue-500" if is_own_row else "font-bold"
                                ui.label(pl["username"]).classes(f"text-xs md:text-sm truncate {name_cls}")
                                if pl["full_name"]:
                                    with ui.tooltip():
                                        ui.label(pl["full_name"])

                            for w in visible_weeks:
                                week_entries = user_week_map.get(w, [])
                                if not week_entries:
                                    ui.label("•").classes(f"w-16 shrink-0 text-center font-bold text-sm {'text-slate-600' if is_dark else 'text-gray-400'}")
                                    continue

                                can_reveal = (
                                    (w < current_week)
                                    or is_own_row
                                    or (w in viewer_finalized_weeks)
                                    or (w in fully_finalized_weeks)
                                    or admin_override
                                )
                                if not can_reveal:
                                    hid_cls = "bg-slate-800 text-slate-400" if is_dark else "bg-gray-200/70 text-gray-500"
                                    with ui.element("div").classes("w-16 shrink-0 flex justify-center"):
                                        ui.label("🔒 Hid").classes(f"px-1.5 py-0.5 rounded text-[10px] font-bold {hid_cls}")
                                else:
                                    with ui.column().classes("w-16 shrink-0 items-center justify-center gap-0.5"):
                                        for entry in week_entries:
                                            raw_team = entry["team_picked"]
                                            state = entry["pick_state"]
                                            is_so = raw_team.endswith("_SO")
                                            clean_code = raw_team.replace("_SO", "").strip().upper()
                                            display_txt = f"{clean_code} 🎯" if is_so else clean_code

                                            if state == "Correct":
                                                pill_cls = "bg-emerald-500/20 text-emerald-300 border-emerald-500/40" if is_dark else "bg-emerald-500/20 text-emerald-800 border-emerald-500/40"
                                            elif state == "Incorrect":
                                                pill_cls = "bg-red-500/20 text-red-300 border-red-500/40" if is_dark else "bg-red-500/20 text-red-800 border-red-500/40"
                                            elif state == "Finalized":
                                                pill_cls = "bg-blue-500/20 text-blue-300 border-blue-500/40" if is_dark else "bg-blue-500/20 text-blue-800 border-blue-500/40"
                                            else:
                                                pill_cls = "bg-amber-500/20 text-amber-300 border-amber-500/40" if is_dark else "bg-amber-500/20 text-amber-800 border-amber-500/40"

                                            with ui.row().classes(f"px-1.5 py-0.5 rounded border text-[11px] font-extrabold items-center justify-center gap-1 no-wrap {pill_cls}"):
                                                if url := get_logo_url(clean_code):
                                                    ui.html(f'<img src="{url}" class="w-4 h-3 object-contain p-0.5 shrink-0" />')
                                                ui.label(display_txt).classes("leading-none")

        loser_bracket, winner_bracket, eliminated = [], [], []
        for r in regs:
            uid = str(r["user_id"])
            info = user_map.get(uid, {"username": "Unknown", "full_name": ""})
            player_obj = {"uid": uid, "username": info["username"], "full_name": info["full_name"]}
            status = r.get("bracket_status") or "Loser Bracket"

            if status == "Loser Bracket":
                loser_bracket.append(player_obj)
            elif status == "Winner Bracket" and pool_slug != "2nd_Chance":
                winner_bracket.append(player_obj)
            else:
                eliminated.append(player_obj)

        build_bracket_section("Loser Bracket (0 Wrong)", "positive", loser_bracket)
        if pool_slug != "2nd_Chance":
            build_bracket_section("Winner Bracket (1 Wrong)", "warning", winner_bracket)
        build_bracket_section(
            "Eliminated (1+ Wrong)" if pool_slug == "2nd_Chance" else "Eliminated (2+ Wrong)",
            "negative",
            eliminated
        )

    dist_week_select.on_value_change(lambda: overview_body.refresh())
    overview_body()

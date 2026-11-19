import os
import asyncio
import datetime
from zoneinfo import ZoneInfo
from nicegui import ui, app, run
from enrollment_helper import get_open_registration_pools, notify_admins_of_join_request

ET_ZONE = ZoneInfo("America/New_York")
SEASON_START_WEDNESDAY = datetime.datetime(2026, 9, 9, 0, 0, 0, tzinfo=ET_ZONE)

def get_current_nfl_week() -> int:
    now_et = datetime.datetime.now(ET_ZONE)
    if now_et < SEASON_START_WEDNESDAY:
        return 1
    return min(22, ((now_et - SEASON_START_WEDNESDAY).days // 7) + 1)

def get_week_label(w: int) -> str:
    return {19: "Wild Card", 20: "Divisional", 21: "Conference", 22: "Super Bowl"}.get(w, f"Week {w}")

def get_logo_url(team_code: str) -> str:
    clean = team_code.replace("_SO", "").strip().upper()
    fname = f"{'BYE' if clean == 'BYE' else clean}.svg"
    return f"/static/{fname}" if os.path.exists(f"static/{fname}") else ""

def render_history_rail(all_picks: list, all_matches: list, start_week: int):
    ui.label("Your Season Selection History").classes("font-bold text-base mb-1")
    outcomes = {}
    for m in all_matches:
        w = m["week"]
        outcomes.setdefault(w, {})
        loser = m.get("winner")
        if loser == "TIE":
            outcomes[w][m["away_team"].upper()] = "Incorrect"
            outcomes[w][m["home_team"].upper()] = "Incorrect"
        elif loser:
            outcomes[w][loser.upper()] = "Correct"
            opp = m["home_team"].upper() if loser.upper() == m["away_team"].upper() else m["away_team"].upper()
            outcomes[w][opp] = "Incorrect"

    picks_by_wk = {}
    for p in all_picks:
        picks_by_wk.setdefault(p["week"], []).append(p)

    with ui.row().classes("w-full overflow-x-auto no-wrap gap-1 pb-2 mb-3"):
        for w in range(start_week, 23):
            wk_hdr = get_week_label(w) if w >= 19 else f"Wk {w}"
            wk_list = picks_by_wk.get(w, [])
            if not wk_list:
                with ui.column().classes("min-w-[52px] min-h-[64px] border border-dashed border-gray-400/50 rounded items-center justify-center p-1 opacity-50 shrink-0"):
                    ui.label(wk_hdr).classes("text-[9px] font-bold text-center leading-tight")
                    ui.label("•").classes("text-xs")
            else:
                for p in wk_list:
                    raw_pick = p["team_picked"].upper()
                    clean_team = raw_pick.replace("_SO", "").strip()
                    state = p.get("pick_state", "Pending")
                    res = outcomes.get(w, {}).get(clean_team, "Pending")

                    if clean_team == "BYE" or state == "Correct" or res == "Correct":
                        box_cls = "bg-emerald-500/15 border-emerald-500"
                    elif state == "Incorrect" or res == "Incorrect":
                        box_cls = "bg-red-500/15 border-red-500"
                    else:
                        box_cls = "bg-slate-400/10 border-slate-400/40"

                    with ui.column().classes(f"min-w-[56px] min-h-[64px] border rounded items-center justify-center p-1 shrink-0 {box_cls}"):
                        ui.label(wk_hdr).classes("text-[9px] font-bold opacity-75 text-center leading-tight")
                        if url := get_logo_url(clean_team):
                            ui.html(f'<img src="{url}" class="w-7 h-5 object-contain p-0.5 my-0.5" />')
                        tag = f"{clean_team}{'🎯' if raw_pick.endswith('_SO') else ''}"
                        ui.label(tag).classes("text-[10px] font-extrabold leading-none")

async def render_picks_view(supabase, user, pool_slug: str):
    user_id = str(user.id)
    current_week = get_current_nfl_week()
    start_week = 6 if pool_slug == "2nd_Chance" else 1

    if "selected_week" not in app.storage.user or app.storage.user["selected_week"] < start_week:
        app.storage.user["selected_week"] = max(start_week, current_week)

    u_res, pool_regs, initial_picks, all_matches = await asyncio.gather(
        run.io_bound(lambda: supabase.table("users").select("username, first_name, last_name, email, cell_phone").eq("id", user_id).execute().data or []),
        run.io_bound(lambda: supabase.table("tournament_registrations").select("*").eq("game_type", pool_slug).eq("is_enrolled", True).execute().data or []),
        run.io_bound(lambda: supabase.table("user_picks").select("*").eq("user_id", user_id).eq("game_type", pool_slug).execute().data or []),
        run.io_bound(lambda: supabase.table("nfl_schedule").select("*").execute().data or []),
    )

    user_row = next(iter(u_res), {})
    current_user_name = user_row.get("username") or "Player"

    active_reg = next((r for r in pool_regs if str(r["user_id"]) == user_id), None)
    current_status = active_reg.get("bracket_status", "Not Enrolled") if active_reg else "Not Enrolled"
    active_total = sum(1 for r in pool_regs if r.get("bracket_status") != "Eliminated")

    pool_label = "2nd Chance" if pool_slug == "2nd_Chance" else "Main"

    # Line 1: [Pool] Pool - Picks
    ui.label(f"{pool_label} Pool - Picks").classes("text-xl font-black")

    # Line 2: Status (left) & Remaining Active #/# (right)
    with ui.row().classes("w-full items-center justify-between pb-2 mb-3 border-b border-gray-200 dark:border-slate-700"):
        ui.label(f"Status: {current_status}").classes("text-sm md:text-base font-extrabold")
        ui.badge(f"Remaining Active: {active_total} / {len(pool_regs)}", color="primary").classes("text-xs font-bold px-2.5 py-1")
    # Verify Enrollment & Self-Enrollment Request Flow
    if not active_reg or not active_reg.get("is_enrolled", False):
        open_pools = get_open_registration_pools(supabase)

        with ui.card().classes("w-full p-5 border border-amber-500/40 shadow-none text-center items-center"):
            ui.label(f"Not Enrolled in {pool_label}.").classes("text-red-500 font-bold text-lg mb-1")

            if pool_slug in open_pools:
                @ui.refreshable
                def self_enroll_area():
                    pending_now = (
                        supabase.table("enrollment_requests")
                        .select("id")
                        .eq("user_id", user_id)
                        .eq("game_type", pool_slug)
                        .eq("status", "Pending")
                        .execute()
                        .data or []
                    )
                    if pending_now:
                        ui.badge("Request Pending Commissioner Approval", color="amber-8").classes("text-xs font-bold px-3 py-1 mt-2")
                    else:
                        ui.label(f"Registration for {pool_label} is currently OPEN.").classes("text-xs opacity-80 mb-3")

                        async def request_pool_join():
                            clean_email = (em_in.value or "").strip().lower()
                            clean_user = (uname_in.value or "").strip()
                            if not clean_email or "@" not in clean_email or not clean_user:
                                ui.notify("Please enter a valid email address and username.", type="negative")
                                return
        
                            sub_btn.props("loading")
                            payload = {
                                "user_id": None,
                                "email": clean_email,
                                "username": clean_user,
                                "first_name": (fn_in.value or "").strip(),
                                "last_name": (ln_in.value or "").strip(),
                                "cell_phone": (ph_in.value or "").strip(),
                                "game_type": pool_sel.value,
                                "status": "Pending",
                            }
                            try:
                                await run.io_bound(lambda: supabase.table("enrollment_requests").insert(payload).execute())
                                await run.io_bound(notify_admins_of_join_request, supabase, payload)
                                join_dlg.close()
                                ui.notify("Join request sent! The Commissioner has been notified.", type="positive", timeout=6000)
                            finally:
                                sub_btn.props(remove="loading")
        
                        with ui.row().classes("w-full justify-end gap-2 mt-2"):
                            ui.button("Cancel", on_click=join_dlg.close).props("flat")
                            sub_btn = ui.button("Submit Request", on_click=submit_guest_request, color="primary").classes("font-bold")

                self_enroll_area()
            else:
                ui.label(f"Registration for {pool_label} is currently closed. Contact the Commissioner for assistance.").classes("text-xs opacity-75")
        return

    # Elimination Message Directing User to Standings Page
    if current_status == "Eliminated":
        ui.label("Tough break — you’re a winner and have been eliminated from this pool. Check out the Standings page to follow and admire the remaining losers.").classes("text-red-600 font-bold")
        return

    draft_picks = set()
    state_cache = {"picks": initial_picks, "first_load": True}

    # Line 3: Enclosed Rectangle Week Selector with "(present)" tag
    week_opts = {
        w: f"{get_week_label(w)} (present)" if w == current_week else get_week_label(w)
        for w in range(start_week, 23)
    }

    def change_week(e):
        app.storage.user["selected_week"] = e.value
        draft_picks.clear()
        matchup_board.refresh()

    with ui.row().classes("w-full items-center mb-3"):
        ui.select(
            week_opts,
            value=app.storage.user["selected_week"],
            label="Select Week  (Wed-Tue)",
            on_change=change_week,
        ).props("dense outlined").classes("w-52")

    @ui.refreshable
    def matchup_board():
        target_week = app.storage.user["selected_week"]
        if state_cache["first_load"]:
            all_picks = state_cache["picks"]
            state_cache["first_load"] = False
        else:
            all_picks = supabase.table("user_picks").select("*").eq("user_id", user_id).eq("game_type", pool_slug).execute().data or []

        render_history_rail(all_picks, all_matches, start_week)

        week_picks = [p for p in all_picks if p["week"] == target_week]
        used_teams = {
            p["team_picked"].replace("_SO", "").upper()
            for p in all_picks
            if p["week"] < 19 and not p["team_picked"].endswith("_SO") and p["week"] != target_week
        }

        if not draft_picks:
            for p in week_picks:
                if p["pick_state"] == "Confirmed":
                    draft_picks.add(p["team_picked"].replace("_SO", "").upper())

        matches = [m for m in all_matches if m["week"] == target_week]
        matches = sorted(matches, key=lambda m: (0, str(m["kickoff_time"]), m["id"]) if m.get("kickoff_time") else (1, "", m["id"]))

        max_picks = 1 if target_week <= 14 else (2 if target_week <= 18 else max(1, len(matches)))
        finalized_picks = [p for p in week_picks if p["pick_state"] in ["Finalized", "Correct", "Incorrect"]]
        confirmed_picks = [p for p in week_picks if p["pick_state"] == "Confirmed"]
        is_week_finalized = (len(finalized_picks) >= max_picks)

        for p in finalized_picks:
            ui.label(f"🔒 Finalized Pick: {p['team_picked']}").classes("w-full p-3 rounded bg-green-100 text-green-900 font-bold mb-2")
        for p in confirmed_picks:
            ui.label(f"Confirmed Pick (Editable): {p['team_picked']}").classes("w-full p-3 rounded bg-blue-100 text-blue-900 font-bold mb-2")

        total_saved = len(week_picks)
        if total_saved < max_picks:
            remaining_needed = max_picks - total_saved
            ui.label(
                f"Additional Pick(s) Needed: You have saved {total_saved} of {max_picks} required picks for {get_week_label(target_week)} ({remaining_needed} still needed)."
            ).classes("w-full p-3 rounded bg-amber-100 text-amber-900 font-bold mb-2")
        with ui.grid().classes("w-full grid-cols-1 md:grid-cols-2 gap-3 mt-2"):
            for m in matches:
                away, home = m["away_team"].upper(), m["home_team"].upper()
                kickoff_raw = m.get("kickoff_time")
                is_locked, is_early = (target_week < current_week), False
                time_label = "TBD (Flex Scheduling Pending)"

                if kickoff_raw:
                    dt_naive = datetime.datetime.fromisoformat(str(kickoff_raw).replace(" ", "T")[:19])
                    dt_et = dt_naive.replace(tzinfo=ET_ZONE)
                    if target_week == current_week and datetime.datetime.now(ET_ZONE) >= dt_et:
                        is_locked = True
                    sunday_noon = dt_et.replace(hour=12, minute=0, second=0)
                    while sunday_noon.weekday() != 6:
                        sunday_noon -= datetime.timedelta(days=1)
                    if target_week == current_week and dt_et < sunday_noon:
                        is_early = True
                    time_label = dt_et.strftime("%a %-m/%-d/%y %-I:%M %p ET")

                db_pick = next((p for p in week_picks if p["team_picked"].replace("_SO", "").upper() in [away, home]), None)
                is_db_conf = db_pick and db_pick["pick_state"] == "Confirmed"
                is_db_fin = db_pick and db_pick["pick_state"] in ["Finalized", "Correct", "Incorrect"]

                sel_away = away in draft_picks or (db_pick and db_pick["team_picked"].replace("_SO", "").upper() == away)
                sel_home = home in draft_picks or (db_pick and db_pick["team_picked"].replace("_SO", "").upper() == home)
                limit_hit = (len(draft_picks) >= max_picks)

                with ui.card().classes("w-full p-3 border border-slate-300 dark:border-slate-700 shadow-sm"):
                    with ui.row().classes("w-full items-center justify-between gap-2 no-wrap"):
                        for idx_t, (team, is_sel) in enumerate([(away, sel_away), (home, sel_home)]):
                            if idx_t == 1:
                                ui.label("@").classes("text-xs text-slate-500 dark:text-slate-400 font-black shrink-0")

                            used = team in used_teams
                            disabled = is_locked or is_week_finalized or is_db_fin or used or (limit_hit and not is_sel)

                            def toggle_team(t=team, active=is_sel):
                                if max_picks == 1:
                                    draft_picks.clear()
                                else:
                                    draft_picks.discard(t)
                                if not active:
                                    draft_picks.add(t)
                                matchup_board.refresh()

                            if is_sel:
                                btn_cls = "flex-1 font-extrabold text-xs bg-blue-600 text-white border-2 border-blue-400 shadow"
                            elif disabled:
                                btn_cls = "flex-1 font-bold text-xs bg-slate-100 dark:bg-slate-800/50 text-slate-400 dark:text-slate-500 border border-slate-200 dark:border-slate-800 opacity-60"
                            else:
                                btn_cls = "flex-1 font-extrabold text-xs bg-slate-200 hover:bg-slate-300 dark:bg-slate-700 dark:hover:bg-slate-600 text-slate-900 dark:text-white border border-slate-400 dark:border-slate-500 shadow-sm cursor-pointer"

                            btn_text = f"{team} (Used)" if used else team
                            logo_u = get_logo_url(team)

                            with ui.button(on_click=toggle_team).props(f"{'disable' if disabled else ''} flat no-caps").classes(btn_cls):
                                with ui.row().classes("items-center justify-center gap-1.5 no-wrap py-0.5"):
                                    if logo_u:
                                        ui.html(f'<img src="{logo_u}" class="w-6 h-4 object-contain p-0.5 shrink-0" />')
                                    ui.label(btn_text).classes("leading-none")

                    if sel_away or sel_home or db_pick:
                        chosen_team = away if sel_away else home
                        with ui.row().classes("w-full gap-2 mt-2"):
                            def save_confirm(t=chosen_team, early=is_early):
                                if max_picks == 1:
                                    supabase.table("user_picks").delete().eq("user_id", user_id).eq("game_type", pool_slug).eq("week", target_week).execute()
                                else:
                                    supabase.table("user_picks").delete().eq("user_id", user_id).eq("game_type", pool_slug).eq("week", target_week).eq("team_picked", t).execute()
                                state = "Finalized" if early else "Confirmed"
                                supabase.table("user_picks").insert({
                                    "user_id": user_id, "game_type": pool_slug, "week": target_week,
                                    "team_picked": t, "pick_state": state
                                }).execute()
                                ui.notify(f"Pick {state}!", type="positive")
                                matchup_board.refresh()

                            ui.button("Confirm", on_click=save_confirm, color="primary" if is_db_conf else "blue-2").props(
                                f"{'disable' if (is_locked or is_db_fin) else ''} dense unelevated"
                            ).classes("flex-1 text-xs")

                            def open_finalize_dialog(t=chosen_team):
                                with ui.dialog() as dialog, ui.card():
                                    ui.label(f"Lock in {t} permanently?").classes("font-bold text-lg")
                                    ui.label("Once finalized, you cannot change your pick and opponent picks will unlock.").classes("text-sm text-gray-500")
                                    with ui.row().classes("w-full justify-end gap-2 mt-3"):
                                        ui.button("Cancel", on_click=dialog.close).props("flat")

                                        def commit_final():
                                            if max_picks == 1:
                                                supabase.table("user_picks").delete().eq("user_id", user_id).eq("game_type", pool_slug).eq("week", target_week).execute()
                                            else:
                                                supabase.table("user_picks").delete().eq("user_id", user_id).eq("game_type", pool_slug).eq("week", target_week).eq("team_picked", t).execute()
                                            supabase.table("user_picks").insert({
                                                "user_id": user_id, "game_type": pool_slug, "week": target_week,
                                                "team_picked": t, "pick_state": "Finalized"
                                            }).execute()
                                            dialog.close()
                                            ui.notify(f"{t} Finalized!", type="positive")
                                            matchup_board.refresh()

                                        ui.button("Yes, Finalize", on_click=commit_final, color="green")
                                dialog.open()

                            ui.button("🔒 Finalized" if is_db_fin else "Finalize", on_click=open_finalize_dialog, color="green" if is_db_fin else "green-2").props(
                                f"{'disable' if (is_locked or is_db_fin) else ''} dense unelevated"
                            ).classes("flex-1 text-xs")

                            if not is_db_fin:
                                def reset_choice(t=chosen_team, in_db=is_db_conf):
                                    draft_picks.discard(t)
                                    if in_db:
                                        supabase.table("user_picks").delete().eq("user_id", user_id).eq("game_type", pool_slug).eq("week", target_week).eq("team_picked", t).execute()
                                        ui.notify("Confirmed pick removed.", type="info")
                                    matchup_board.refresh()

                                ui.button("Reset", on_click=reset_choice, color="red-2").props(
                                    f"{'disable' if is_locked else ''} dense unelevated"
                                ).classes("flex-1 text-xs")

                    if is_locked:
                        ui.label(f"🔒 Deadline or Kickoff Passed ({time_label})").classes("text-xs text-red-500 font-semibold mt-1")
                    else:
                        ui.label(f"{time_label}").classes("text-xs text-gray-500 dark:text-gray-400 mt-1")

        # --- USE MY BYE SLOT SECTION ---
        ui.separator().classes("my-4")
        bye_used_prior = any(p["team_picked"].upper() == "BYE" and p["week"] != target_week for p in all_picks)
        db_bye_this_week = next((p for p in week_picks if p["team_picked"].upper() == "BYE"), None)
        bye_finalized_this_week = db_bye_this_week and db_bye_this_week["pick_state"] in ["Finalized", "Correct", "Incorrect"]
        bye_disabled = (target_week < current_week) or is_week_finalized

        if bye_finalized_this_week:
            ui.button("🔒 BYE Finalized for This Week", color="green").props("disable unelevated").classes("w-full font-bold")
        elif bye_used_prior:
            ui.button("🔒 Season BYE Already Used", color="grey-5").props("disable unelevated").classes("w-full font-bold")
        else:
            with ui.row().classes("w-full gap-2"):
                def confirm_bye():
                    supabase.table("user_picks").delete().eq("user_id", user_id).eq("game_type", pool_slug).eq("week", target_week).execute()
                    supabase.table("user_picks").insert({
                        "user_id": user_id,
                        "game_type": pool_slug,
                        "week": target_week,
                        "team_picked": "BYE",
                        "pick_state": "Confirmed",
                    }).execute()
                    draft_picks.clear()
                    ui.notify("BYE Confirmed (Editable).", type="positive")
                    matchup_board.refresh()

                ui.button(
                    "Confirm BYE" if not db_bye_this_week else "BYE Confirmed",
                    on_click=confirm_bye,
                    color="primary" if db_bye_this_week else "blue-3",
                ).props(f"{'disable' if bye_disabled else ''} unelevated").classes("flex-1 font-bold")

                def open_bye_finalize():
                    with ui.dialog() as dlg, ui.card():
                        ui.label("Finalize your Season BYE?").classes("font-bold text-lg")
                        ui.label("You only get one BYE per season. Locking it in cannot be undone.").classes("text-sm text-gray-500")
                        with ui.row().classes("w-full justify-end gap-2 mt-3"):
                            ui.button("Cancel", on_click=dlg.close).props("flat")

                            def lock_bye():
                                supabase.table("user_picks").delete().eq("user_id", user_id).eq("game_type", pool_slug).eq("week", target_week).execute()
                                supabase.table("user_picks").insert({
                                    "user_id": user_id,
                                    "game_type": pool_slug,
                                    "week": target_week,
                                    "team_picked": "BYE",
                                    "pick_state": "Finalized",
                                }).execute()
                                draft_picks.clear()
                                dlg.close()
                                ui.notify("BYE Finalized!", type="positive")
                                matchup_board.refresh()

                            ui.button("Yes, Finalize BYE", on_click=lock_bye, color="green")
                    dlg.open()

                ui.button("Finalize BYE", on_click=open_bye_finalize, color="green-3").props(f"{'disable' if bye_disabled else ''} unelevated").classes("flex-1 font-bold")

                if db_bye_this_week:
                    def clear_bye():
                        supabase.table("user_picks").delete().eq("user_id", user_id).eq("game_type", pool_slug).eq("week", target_week).execute()
                        ui.notify("BYE selection removed.", type="info")
                        matchup_board.refresh()

                    ui.button("Reset BYE", on_click=clear_bye, color="red-3").props(f"{'disable' if bye_disabled else ''} unelevated").classes("flex-1 font-bold")

    matchup_board()

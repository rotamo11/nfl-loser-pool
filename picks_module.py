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

def get_week_label(w: int) -> str:
    return {19: "Wildcard", 20: "Divisional", 21: "Conference", 22: "Super Bowl"}.get(w, f"Week {w}")

def get_logo_data_uri(team_code: str) -> str:
    clean = team_code.replace("_SO", "").strip().upper()
    path = f"static/{'BYE' if clean == 'BYE' else clean}.svg"
    if os.path.exists(path):
        with open(path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode("utf-8")
        return f"data:image/svg+xml;base64,{b64}"
    return ""

def render_history_rail(supabase, all_picks: list):
    ui.label("Your Season Selection History").classes("font-bold text-base mb-1")
    sched_rows = supabase.table("nfl_schedule").select("week", "away_team", "home_team", "winner").execute().data or []
    outcomes = {}
    for m in sched_rows:
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

    picks_map = {p["week"]: p for p in all_picks}
    with ui.row().classes("w-full overflow-x-auto no-wrap gap-1 pb-2 mb-3"):
        for w in range(1, 23):
            p = picks_map.get(w)
            if not p:
                with ui.column().classes("min-w-[52px] min-h-[64px] border border-dashed border-gray-400/50 rounded items-center justify-center p-1 opacity-50 shrink-0"):
                    ui.label(f"Wk {w}").classes("text-[9px] font-bold")
                    ui.label("•").classes("text-xs")
            else:
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
                    ui.label(f"Wk {w}").classes("text-[9px] font-bold opacity-75 leading-none")
                    if uri := get_logo_data_uri(clean_team):
                        ui.image(uri).classes("w-6 h-4 object-contain my-0.5")
                    tag = f"{clean_team}{'🎯' if raw_pick.endswith('_SO') else ''}"
                    ui.label(tag).classes("text-[10px] font-extrabold leading-none")

def render_picks_view(supabase, user, pool_slug: str):
    user_id = user.id
    current_week = get_current_nfl_week()
    if "selected_week" not in app.storage.user:
        app.storage.user["selected_week"] = current_week

    # 1. Verify Enrollment & Bracket Status
    reg_res = supabase.table("tournament_registrations").select("*").eq("user_id", user_id).eq("game_type", pool_slug).execute().data
    active_reg = reg_res[0] if (isinstance(reg_res, list) and len(reg_res) > 0) else {}

    if not active_reg or not active_reg.get("is_enrolled", False):
        ui.label(f"Not Enrolled in {pool_slug.replace('_', ' ')}.").classes("text-red-500 font-bold text-lg")
        return
    if active_reg.get("bracket_status") == "Eliminated":
        ui.label("You have been eliminated from this pool but can still view the Brackets page.").classes("text-red-500 font-bold")
        return

    draft_picks = set()
    @ui.refreshable
    def matchup_board():
        target_week = app.storage.user["selected_week"]
        all_picks = supabase.table("user_picks").select("*").eq("user_id", user_id).eq("game_type", pool_slug).execute().data or []
        render_history_rail(supabase, all_picks)

        week_picks = [p for p in all_picks if p["week"] == target_week]
        used_teams = {
            p["team_picked"].replace("_SO", "").upper()
            for p in all_picks
            if p["week"] < 19 and not p["team_picked"].endswith("_SO") and p["week"] != target_week
        }

        if not draft_picks:
            for p in week_picks:
                if p["pick_state"] == "Confirmed":
                    draft_picks.add(p["team_picked"].upper())

        max_picks = 1 if target_week <= 14 else (2 if target_week <= 18 else 6)
        is_week_finalized = any(p["pick_state"] in ["Finalized", "Correct", "Incorrect"] for p in week_picks)

        for p in week_picks:
            if p["pick_state"] in ["Finalized", "Correct", "Incorrect"]:
                ui.label(f"🔒 Finalized Pick: {p['team_picked']}").classes("w-full p-3 rounded bg-green-100 text-green-900 font-bold mb-2")
            elif p["pick_state"] == "Confirmed":
                ui.label(f"📋 Confirmed Pick (Editable): {p['team_picked']}").classes("w-full p-3 rounded bg-blue-100 text-blue-900 font-bold mb-2")

        raw_matches = supabase.table("nfl_schedule").select("*").eq("week", target_week).execute().data or []
        matches = sorted(raw_matches, key=lambda m: (0, str(m["kickoff_time"]), m["id"]) if m.get("kickoff_time") else (1, "", m["id"]))

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
                    time_label = dt_et.strftime("%A %-I:%M %p ET")

                db_pick = next((p for p in week_picks if p["team_picked"].replace("_SO", "").upper() in [away, home]), None)
                is_db_conf = db_pick and db_pick["pick_state"] == "Confirmed"
                is_db_fin = db_pick and db_pick["pick_state"] in ["Finalized", "Correct", "Incorrect"]

                sel_away = away in draft_picks or (db_pick and db_pick["team_picked"].startswith(away))
                sel_home = home in draft_picks or (db_pick and db_pick["team_picked"].startswith(home))
                limit_hit = (len(draft_picks) >= max_picks)

                with ui.card().classes("w-full p-3 border border-gray-200 dark:border-slate-700 shadow-sm"):
                    with ui.row().classes("w-full items-center justify-between gap-2 no-wrap"):
                        with ui.row().classes("items-center gap-1 shrink-0"):
                            if uri := get_logo_data_uri(away):
                                ui.image(uri).classes("w-6 h-4 object-contain")
                            ui.label("@").classes("text-xs text-gray-400 font-bold")
                            if uri := get_logo_data_uri(home):
                                ui.image(uri).classes("w-6 h-4 object-contain")

                        for team, is_sel in [(away, sel_away), (home, sel_home)]:
                            used = team in used_teams
                            disabled = is_locked or is_db_fin or used or (limit_hit and not is_sel)

                            def toggle_team(t=team, active=is_sel):
                                draft_picks.clear() if max_picks == 1 else draft_picks.discard(t)
                                if not active:
                                    draft_picks.add(t)
                                matchup_board.refresh()

                            ui.button(f"{team} (Used)" if used else team, on_click=toggle_team, color="primary" if is_sel else "grey-4").props(
                                f"{'disable' if disabled else ''} unelevated"
                            ).classes("flex-1 font-bold text-xs")
                    if sel_away or sel_home or db_pick:
                        chosen_team = away if sel_away else home
                        with ui.row().classes("w-full gap-2 mt-2"):
                            def save_confirm(t=chosen_team, early=is_early):
                                supabase.table("user_picks").delete().eq("user_id", user_id).eq("game_type", pool_slug).eq("week", target_week).execute()
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
                                            supabase.table("user_picks").delete().eq("user_id", user_id).eq("game_type", pool_slug).eq("week", target_week).execute()
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
                                        supabase.table("user_picks").delete().eq("user_id", user_id).eq("game_type", pool_slug).eq("week", target_week).execute()
                                        ui.notify("Confirmed pick removed.", type="info")
                                    matchup_board.refresh()

                                ui.button("Reset", on_click=reset_choice, color="red-2").props(
                                    f"{'disable' if is_locked else ''} dense unelevated"
                                ).classes("flex-1 text-xs")

                    if is_locked:
                        ui.label(f"🔒 Kickoff Passed ({time_label})").classes("text-xs text-red-500 font-semibold mt-1")
                    else:
                        ui.label(f"⏰ {time_label}").classes("text-xs text-gray-500 dark:text-gray-400 mt-1")

        # --- USE MY BYE SLOT SECTION ---
        ui.separator().classes("my-4")
        bye_used_prior = any(p["team_picked"].upper() == "BYE" and p["week"] != target_week for p in all_picks)
        db_bye_this_week = next((p for p in week_picks if p["team_picked"].upper() == "BYE"), None)
        bye_finalized_this_week = db_bye_this_week and db_bye_this_week["pick_state"] in ["Finalized", "Correct", "Incorrect"]
        past_week_locked = (target_week < current_week)

        if bye_finalized_this_week:
            ui.button("🔒 BYE Finalized for This Week", color="green").props("disable unelevated").classes("w-full font-bold")
        elif bye_used_prior:
            ui.button("🔒 Season BYE Already Used", color="grey-5").props("disable unelevated").classes("w-full font-bold")
        else:
            with ui.row().classes("w-full gap-2"):
                def confirm_bye():
                    supabase.table("user_picks").delete().eq("user_id", user_id).eq("game_type", pool_slug).eq("week", target_week).execute()
                    supabase.table("user_picks").insert({
                        "user_id": user_id, "game_type": pool_slug, "week": target_week,
                        "team_picked": "BYE", "pick_state": "Confirmed"
                    }).execute()
                    draft_picks.clear()
                    ui.notify("BYE Confirmed (Editable).", type="positive")
                    matchup_board.refresh()

                ui.button("Confirm BYE" if not db_bye_this_week else "✓ BYE Confirmed", on_click=confirm_bye,
                          color="primary" if db_bye_this_week else "blue-3").props(f"{'disable' if past_week_locked else ''} unelevated").classes("flex-1 font-bold")

                def open_bye_finalize():
                    with ui.dialog() as dlg, ui.card():
                        ui.label("Finalize your Season BYE?").classes("font-bold text-lg")
                        ui.label("You only get one BYE per season. Locking it in cannot be undone.").classes("text-sm text-gray-500")
                        with ui.row().classes("w-full justify-end gap-2 mt-3"):
                            ui.button("Cancel", on_click=dlg.close).props("flat")
                            def lock_bye():
                                supabase.table("user_picks").delete().eq("user_id", user_id).eq("game_type", pool_slug).eq("week", target_week).execute()
                                supabase.table("user_picks").insert({
                                    "user_id": user_id, "game_type": pool_slug, "week": target_week,
                                    "team_picked": "BYE", "pick_state": "Finalized"
                                }).execute()
                                draft_picks.clear()
                                dlg.close()
                                ui.notify("BYE Finalized!", type="positive")
                                matchup_board.refresh()
                            ui.button("Yes, Finalize BYE", on_click=lock_bye, color="green")
                    dlg.open()

                ui.button("Finalize BYE", on_click=open_bye_finalize, color="green-3").props(f"{'disable' if past_week_locked else ''} unelevated").classes("flex-1 font-bold")

                if db_bye_this_week:
                    def clear_bye():
                        supabase.table("user_picks").delete().eq("user_id", user_id).eq("game_type", pool_slug).eq("week", target_week).execute()
                        ui.notify("BYE selection removed.", type="info")
                        matchup_board.refresh()
                    ui.button("Reset BYE", on_click=clear_bye, color="red-3").props(f"{'disable' if past_week_locked else ''} unelevated").classes("flex-1 font-bold")

    week_opts = {w: f"{get_week_label(w)} (current)" if w == current_week else get_week_label(w) for w in range(1, 23)}
    def change_week(e):
        app.storage.user["selected_week"] = e.value
        draft_picks.clear()
        matchup_board.refresh()

    ui.select(week_opts, value=app.storage.user["selected_week"], label="Target (Starts Wed)", on_change=change_week).classes("w-48 mb-3")
    matchup_board()

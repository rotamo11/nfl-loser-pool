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
    if w <= 18:
        return f"Week {w}"
    return {19: "Wild Card", 20: "Divisional", 21: "Conference", 22: "Super Bowl"}.get(w, f"Week {w}")

def get_logo_url(team_abbr: str) -> str:
    clean = team_abbr.replace("_SO", "").strip().upper()
    if clean in ["BYE", "NO_PICK", "TIE", "PENDING", ""]:
        return ""
    filename = "WAS.svg" if clean == "WSH" else f"{clean}.svg"
    if os.path.exists(f"static/{filename}"):
        return f"/static/{filename}"
    return ""

async def render_picks_view(supabase, user, pool_slug: str):
    user_id = str(user.id)
    current_week = get_current_nfl_week()

    # Fetch registration, user picks, NFL schedule, and user profile in parallel
    reg_rows, all_picks, all_matches, u_rows = await asyncio.gather(
        run.io_bound(lambda: supabase.table("tournament_registrations").select("*").eq("user_id", user_id).eq("game_type", pool_slug).execute().data or []),
        run.io_bound(lambda: supabase.table("user_picks").select("*").eq("user_id", user_id).eq("game_type", pool_slug).execute().data or []),
        run.io_bound(lambda: supabase.table("nfl_schedule").select("*").execute().data or []),
        run.io_bound(lambda: supabase.table("users").select("username, first_name, last_name, email, cell_phone").eq("id", user_id).execute().data or []),
    )

    reg = next(iter(reg_rows), None)
    u_info = next(iter(u_rows), {})

    # --- SELF-ENROLLMENT REQUEST CARD FOR UN-ENROLLED PLAYERS ---
    if not reg or not reg.get("is_enrolled"):
        pool_label = pool_slug.replace("_", " ")
        open_pools = get_open_registration_pools(supabase)

        with ui.card().classes("w-full p-5 border border-amber-500/40 shadow-none text-center items-center"):
            ui.label(f"You are not currently enrolled in the {pool_label} Pool.").classes("text-base font-extrabold mb-1")

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
                        ui.badge("⏳ Request Pending Commissioner Approval", color="amber-8").classes("text-xs font-bold px-3 py-1 mt-2")
                    else:
                        ui.label(f"Registration for {pool_label} is currently OPEN!").classes("text-xs opacity-80 mb-3")

                        def request_pool_join():
                            payload = {
                                "user_id": user_id,
                                "email": (u_info.get("email") or user.email or "").strip().lower(),
                                "username": (u_info.get("username") or "Player").strip(),
                                "first_name": (u_info.get("first_name") or "").strip(),
                                "last_name": (u_info.get("last_name") or "").strip(),
                                "cell_phone": (u_info.get("cell_phone") or "").strip(),
                                "game_type": pool_slug,
                                "status": "Pending",
                            }
                            supabase.table("enrollment_requests").insert(payload).execute()
                            notify_admins_of_join_request(supabase, payload)
                            ui.notify(f"✅ Request sent to join {pool_label}! The Commissioner has been notified.", type="positive")
                            self_enroll_area.refresh()

                        ui.button(f"Request to Join {pool_label}", icon="how_to_reg", on_click=request_pool_join, color="primary").classes("font-bold px-6")

                self_enroll_area()
            else:
                ui.label(f"Registration for {pool_label} is currently closed. Contact the Commissioner for assistance.").classes("text-xs opacity-75")
        return

    b_status = reg.get("bracket_status") or "Loser Bracket"
    if b_status == "Eliminated":
        ui.label("💀 You have been ELIMINATED from this pool.").classes("text-red-500 font-extrabold text-lg mb-3")
        return

    # --- TOP STATUS HEADER & WEEK DROPDOWN ---
    start_week = 10 if pool_slug == "2nd_Chance" else 1
    available_weeks = list(range(start_week, 23))
    default_week = max(start_week, current_week)

    with ui.row().classes("w-full items-center justify-between mb-3 flex-wrap gap-2"):
        with ui.row().classes("items-center gap-2"):
            ui.label("Active Bracket:").classes("text-sm font-bold opacity-80")
            badge_col = "positive" if b_status == "Loser Bracket" else "warning"
            ui.badge(b_status, color=badge_col).classes("text-xs font-extrabold px-2.5 py-1")

        week_options = {w: get_week_label(w) for w in available_weeks}
        week_select = ui.select(week_options, value=default_week, label="Select Week").props("dense outlined").classes("w-44")

    # --- SEASON PICK HISTORY STRIP ---
    sorted_history = sorted(all_picks, key=lambda x: x["week"])
    if sorted_history:
        with ui.row().classes("w-full items-center gap-1.5 flex-wrap mb-3"):
            ui.label("Your Picks:").classes("text-xs font-bold opacity-75 mr-1")
            for hp in sorted_history:
                wk_lbl = f"W{hp['week']}" if hp["week"] <= 18 else get_week_label(hp["week"])[:3]
                raw_t = hp["team_picked"].upper()
                st = hp["pick_state"]
                disp = f"{raw_t.replace('_SO', '')} 🎯" if raw_t.endswith("_SO") else raw_t
                p_col = "green" if st == "Correct" else ("red" if st == "Incorrect" else ("blue" if st == "Finalized" else "amber-8"))
                ui.badge(f"{wk_lbl}: {disp}", color=p_col).classes("text-[11px] font-bold")
    @ui.refreshable
    def matchup_board():
        target_week = week_select.value
        now_et = datetime.datetime.now(ET_ZONE)

        # Reload current user's picks fresh when board refreshes after Confirm/Finalize/Reset
        fresh_picks = supabase.table("user_picks").select("*").eq("user_id", user_id).eq("game_type", pool_slug).execute().data or []
        week_picks = [p for p in fresh_picks if p["week"] == target_week]

        matches = [m for m in all_matches if m["week"] == target_week]
        matches = sorted(matches, key=lambda m: (0, str(m["kickoff_time"]), m["id"]) if m.get("kickoff_time") else (1, "", m["id"]))

        if not matches:
            ui.label(f"No matchups scheduled yet for {get_week_label(target_week)}.").classes("text-sm opacity-75")
            return

        max_picks = 1 if target_week <= 14 else (2 if target_week <= 18 else len(matches))

        # Determine used teams (respecting _SO shutout bonus & Playoff repeats)
        used_teams = set()
        if target_week <= 18:
            pick_counts = {}
            so_teams = set()
            for p in fresh_picks:
                if p["week"] == target_week:
                    continue
                raw = p["team_picked"].upper()
                base = raw.replace("_SO", "")
                if base not in ["BYE", "NO_PICK"]:
                    pick_counts[base] = pick_counts.get(base, 0) + 1
                    if raw.endswith("_SO"):
                        so_teams.add(base)
            for tm, cnt in pick_counts.items():
                allowed = 2 if tm in so_teams else 1
                if cnt >= allowed:
                    used_teams.add(tm)

        db_selected_teams = {p["team_picked"].replace("_SO", "").upper() for p in week_picks}
        finalized_count = sum(1 for p in week_picks if p.get("pick_state") in ["Finalized", "Correct", "Incorrect"])
        is_week_finalized = (finalized_count >= max_picks)

        selected_state = {"teams": set(db_selected_teams)}

        # Sunday Noon ET deadline calculation for target_week
        week_wed = SEASON_START_WEDNESDAY + datetime.timedelta(days=(target_week - 1) * 7)
        sunday_noon_et = week_wed + datetime.timedelta(days=4, hours=12)

        with ui.row().classes("w-full items-center justify-between mb-2"):
            ui.label(f"Select {max_picks} Team{'s' if max_picks > 1 else ''} to LOSE ({get_week_label(target_week)})").classes("text-base font-extrabold")
            if is_week_finalized:
                ui.badge("🔒 Week Finalized", color="blue").classes("text-xs font-bold")

        team_btns = {}

        def refresh_btn_styles():
            cur_sel = selected_state["teams"]
            limit_hit = (len(cur_sel) >= max_picks)
            for tm, meta in team_btns.items():
                btn = meta["btn"]
                is_sel = (tm in cur_sel)
                locked_row = meta["is_locked"] or is_week_finalized or (tm in used_teams) or (limit_hit and not is_sel)

                if locked_row:
                    btn.props("disable")
                else:
                    btn.props(remove="disable")

                if is_sel:
                    btn.classes(remove="bg-slate-100 dark:bg-slate-800 text-slate-900 dark:text-white border-slate-300 dark:border-slate-700",
                                add="bg-blue-600 text-white border-blue-500 shadow-md")
                else:
                    btn.classes(remove="bg-blue-600 text-white border-blue-500 shadow-md",
                                add="bg-slate-100 dark:bg-slate-800 text-slate-900 dark:text-white border-slate-300 dark:border-slate-700")

        with ui.grid().classes("w-full grid-cols-1 md:grid-cols-2 gap-2.5"):
            for m in matches:
                away, home = m["away_team"].upper(), m["home_team"].upper()
                kickoff_raw = m.get("kickoff_time")

                time_label = "TBD"
                game_started = False
                if kickoff_raw:
                    dt_naive = datetime.datetime.fromisoformat(str(kickoff_raw).replace(" ", "T")[:19])
                    dt_et = dt_naive.replace(tzinfo=ET_ZONE)
                    time_label = dt_et.strftime("%A %-m/%-d/%y %-I:%M %p ET")
                    game_started = (now_et >= dt_et)

                past_sunday_noon = (now_et >= sunday_noon_et)
                is_locked = (target_week < current_week) or game_started or past_sunday_noon

                with ui.card().classes("w-full p-2.5 border border-slate-200 dark:border-slate-700 shadow-none"):
                    with ui.row().classes("w-full items-center justify-between text-[11px] opacity-75 mb-1.5"):
                        ui.label(f"⏰ {time_label}").classes("font-semibold")
                        if is_locked:
                            ui.label("🔒 Locked").classes("font-bold text-red-500")

                    with ui.row().classes("w-full items-center justify-between gap-2 no-wrap"):
                        for idx_t, tm in enumerate([away, home]):
                            if idx_t == 1:
                                ui.label("@").classes("text-xs text-slate-500 dark:text-slate-400 font-black shrink-0")

                            def make_toggle(team_code):
                                def toggle_team():
                                    if is_week_finalized:
                                        return
                                    cur = selected_state["teams"]
                                    if team_code in cur:
                                        cur.remove(team_code)
                                    elif len(cur) < max_picks:
                                        cur.add(team_code)
                                    refresh_btn_styles()
                                return toggle_team

                            with ui.button(on_click=make_toggle(tm)).props("unelevated no-caps").classes(
                                "flex-1 py-2 px-2 rounded-lg border font-extrabold text-xs md:text-sm transition-all"
                            ) as t_btn:
                                with ui.row().classes("items-center justify-center gap-1.5 no-wrap"):
                                    if logo_u := get_logo_url(tm):
                                        ui.html(f'<img src="{logo_u}" class="w-5 h-3.5 object-contain shrink-0" />')
                                    ui.label(tm)

                            team_btns[tm] = {"btn": t_btn, "is_locked": is_locked}

        refresh_btn_styles()

        # --- CONFIRM / FINALIZE / RESET BUTTONS ---
        def save_picks(target_state: str):
            chosen = sorted(selected_state["teams"])
            if len(chosen) != max_picks:
                ui.notify(f"Please select exactly {max_picks} team{'s' if max_picks > 1 else ''}.", type="warning")
                return
            supabase.table("user_picks").delete().eq("user_id", user_id).eq("game_type", pool_slug).eq("week", target_week).execute()
            rows = [
                {"user_id": user_id, "game_type": pool_slug, "week": target_week, "team_picked": t, "pick_state": target_state}
                for t in chosen
            ]
            supabase.table("user_picks").insert(rows).execute()
            ui.notify(f"Picks {target_state.lower()}!", type="positive")
            matchup_board.refresh()

        def open_finalize_dialog():
            chosen = sorted(selected_state["teams"])
            if len(chosen) != max_picks:
                ui.notify(f"Please select exactly {max_picks} team{'s' if max_picks > 1 else ''} first.", type="warning")
                return
            with ui.dialog() as fin_dlg, ui.card().classes("p-5 max-w-md"):
                ui.label("Finalize Weekly Pick(s)?").classes("text-lg font-black")
                ui.label(f"You are locking in: {', '.join(chosen)}. Once finalized, picks cannot be changed and league picks for this week will unlock.").classes("text-xs opacity-80 my-2")
                with ui.row().classes("w-full justify-end gap-2 mt-3"):
                    ui.button("Cancel", on_click=fin_dlg.close).props("flat")
                    ui.button("Yes, Finalize", on_click=lambda: (fin_dlg.close(), save_picks("Finalized")), color="positive").classes("font-bold")
            fin_dlg.open()

        with ui.row().classes("w-full gap-2 mt-4 flex-wrap"):
            ui.button("Confirm Pick(s)", on_click=lambda: save_picks("Confirmed"), color="primary").props(
                f"{'disable' if is_week_finalized else ''} unelevated"
            ).classes("flex-1 font-bold")

            ui.button("Finalize Pick(s)", on_click=open_finalize_dialog, color="positive").props(
                f"{'disable' if is_week_finalized else ''} unelevated"
            ).classes("flex-1 font-bold")

            if week_picks and not is_week_finalized:
                def reset_week_picks():
                    supabase.table("user_picks").delete().eq("user_id", user_id).eq("game_type", pool_slug).eq("week", target_week).execute()
                    ui.notify("Week selections cleared.", type="info")
                    matchup_board.refresh()
                ui.button("Reset", on_click=reset_week_picks, color="red").props("outline unelevated").classes("font-bold")

        # --- USE MY BYE SLOT SECTION ---
        ui.separator().classes("my-4")
        bye_used_prior = any(p["team_picked"].upper() == "BYE" and p["week"] != target_week for p in fresh_picks)
        db_bye_this_week = next((p for p in week_picks if p["team_picked"].upper() == "BYE"), None)
        bye_disabled = (target_week < current_week) or is_week_finalized or (now_et >= sunday_noon_et)

        with ui.card().classes("w-full p-3 border border-slate-200 dark:border-slate-700 shadow-none"):
            ui.label("🛡️ Season BYE Slot (1 Per Pool)").classes("text-sm font-extrabold mb-1")
            if bye_used_prior:
                ui.label("You have already used your Season BYE in this pool.").classes("text-xs opacity-70 italic")
            else:
                ui.label("Use your one-time BYE to skip picking a team this week and automatically advance.").classes("text-xs opacity-75 mb-2")

                def save_bye(st: str):
                    supabase.table("user_picks").delete().eq("user_id", user_id).eq("game_type", pool_slug).eq("week", target_week).execute()
                    supabase.table("user_picks").insert({
                        "user_id": user_id,
                        "game_type": pool_slug,
                        "week": target_week,
                        "team_picked": "BYE",
                        "pick_state": st,
                    }).execute()
                    ui.notify(f"Season BYE {st.lower()}!", type="positive")
                    matchup_board.refresh()

                with ui.row().classes("w-full gap-2 flex-wrap"):
                    ui.button(
                        "Confirm BYE" if not db_bye_this_week else "✓ BYE Confirmed",
                        on_click=lambda: save_bye("Confirmed"),
                        color="primary" if db_bye_this_week else "blue-3",
                    ).props(f"{'disable' if bye_disabled else ''} unelevated").classes("flex-1 font-bold")

                    ui.button(
                        "Finalize BYE",
                        on_click=lambda: save_bye("Finalized"),
                        color="positive",
                    ).props(f"{'disable' if bye_disabled else ''} unelevated").classes("flex-1 font-bold")

    week_select.on_value_change(lambda: matchup_board.refresh())
    matchup_board()

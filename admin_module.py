import os
import csv
import io
import asyncio
import datetime
from zoneinfo import ZoneInfo
from nicegui import ui, app, run
from picks_module import get_current_nfl_week, get_week_label, get_logo_url
from enrollment_helper import ET_ZONE
from background_cron_reminders import (
    send_smtp_email,
    send_ntfy_push,
    resolve_week_default_info,
    get_required_picks,
)

def is_admin_user(supabase, user) -> bool:
    if not user:
        return False
    try:
        res = supabase.table("users").select("is_admin").eq("id", str(user.id)).execute().data or []
        first = next(iter(res), {})
        return bool(first.get("is_admin", False))
    except Exception:
        return False

def execute_manual_deadline_lock(supabase, target_week: int) -> str:
    confirmed_picks = (
        supabase.table("user_picks")
        .select("id")
        .eq("week", target_week)
        .eq("pick_state", "Confirmed")
        .execute()
        .data or []
    )
    for p in confirmed_picks:
        supabase.table("user_picks").update({"pick_state": "Finalized"}).eq("id", p["id"]).execute()

    regs = (
        supabase.table("tournament_registrations")
        .select("id, user_id, game_type, is_enrolled, bracket_status")
        .eq("is_enrolled", True)
        .neq("bracket_status", "Eliminated")
        .execute()
        .data or []
    )
    all_picks = supabase.table("user_picks").select(
        "id, user_id, game_type, week, team_picked, pick_state"
    ).execute().data or []
    matches = supabase.table("nfl_schedule").select("id").eq("week", target_week).execute().data or []
    required_count = 1 if target_week <= 14 else (2 if target_week <= 18 else max(1, len(matches)))

    def_rows = supabase.table("default_picks").select("week, team").order("week", desc=False).execute().data or []
    def_map = {int(r["week"]): r["team"].upper().strip() for r in def_rows if r.get("team")}
    default_team = def_map.get(target_week)
    if not default_team:
        prior = [w for w in sorted(def_map.keys(), reverse=True) if w < target_week]
        first_prior = next(iter(prior), None)
        if first_prior is not None:
            default_team = def_map[first_prior]
            supabase.table("default_picks").upsert({
                "week": target_week,
                "team": default_team,
                "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat()
            }).execute()

    auto_byes, auto_defaults, no_picks = 0, 0, 0
    for r in regs:
        uid, gtype = str(r["user_id"]), r["game_type"]
        user_pool_picks = [p for p in all_picks if str(p["user_id"]) == uid and p["game_type"] == gtype]
        missing_slots = required_count - sum(1 for p in user_pool_picks if p["week"] == target_week)
        if missing_slots <= 0:
            continue

        bye_used = any((p.get("team_picked") or "").upper().strip() == "BYE" for p in user_pool_picks)
        for _ in range(missing_slots):
            if not bye_used:
                new_row = {"user_id": uid, "game_type": gtype, "week": target_week, "team_picked": "BYE", "pick_state": "Finalized"}
                supabase.table("user_picks").insert(new_row).execute()
                user_pool_picks.append(new_row)
                all_picks.append(new_row)
                bye_used = True
                auto_byes += 1
            elif default_team:
                new_row = {"user_id": uid, "game_type": gtype, "week": target_week, "team_picked": default_team, "pick_state": "Finalized"}
                supabase.table("user_picks").insert(new_row).execute()
                user_pool_picks.append(new_row)
                all_picks.append(new_row)
                auto_defaults += 1
            else:
                new_row = {"user_id": uid, "game_type": gtype, "week": target_week, "team_picked": "NO_PICK", "pick_state": "Incorrect"}
                supabase.table("user_picks").insert(new_row).execute()
                user_pool_picks.append(new_row)
                all_picks.append(new_row)
                no_picks += 1
    for r in regs:
        uid, gtype = str(r["user_id"]), r["game_type"]
        losses = sum(1 for p in all_picks if str(p["user_id"]) == uid and p["game_type"] == gtype and p.get("pick_state") == "Incorrect")
        new_status = ("Eliminated" if losses >= 1 else "Loser Bracket") if gtype == "2nd_Chance" else (
            "Loser Bracket" if losses == 0 else ("Winner Bracket" if losses == 1 else "Eliminated")
        )
        if new_status != r.get("bracket_status"):
            supabase.table("tournament_registrations").update({"bracket_status": new_status}).eq("id", r["id"]).execute()

    return (
        f"Week {target_week} lock complete: {len(confirmed_picks)} finalized, "
        f"{auto_byes} auto-BYEs, {auto_defaults} default picks ({default_team or 'None'}), {no_picks} NO_PICK losses."
    )

def execute_manual_reminders(supabase, target_week: int, admin_only_uid: str | None = None) -> str:
    smtp_user = os.environ.get("SMTP_USER", "")
    smtp_pass = os.environ.get("SMTP_PASS", "")
    app_url = os.environ.get("APP_URL", "https://nfl-loser-pool-production.up.railway.app")
    if not os.environ.get("RESEND_API_KEY") and (not smtp_user or not smtp_pass):
        raise RuntimeError("Missing SMTP_USER or SMTP_PASS in Railway environment variables.")

    users = supabase.table("users").select("id, username, email, alert_personal_topic, alert_email, alert_sms, is_admin").execute().data or []
    user_map = {str(u["id"]): u for u in users}
    default_team, is_saved = resolve_week_default_info(supabase, target_week)
    status_note = f"Explicitly saved for Week {target_week}" if is_saved else f"Inherited from prior week (not yet saved for Week {target_week})"

    admin_sent = 0
    for adm in [u for u in users if u.get("is_admin") and (not admin_only_uid or str(u["id"]) == admin_only_uid)]:
        adm_name = adm.get("username") or "Admin"
        if adm.get("alert_email") and adm.get("email"):
            send_smtp_email(
                smtp_user, smtp_pass, adm["email"],
                f"Admin Check: Week {target_week} Default Pick is {default_team}",
                f"Hey {adm_name},\n\nPlease verify the Week {target_week} auto-pick default team before Sunday at NOON ET.\n\n"
                f"Current Default Team: {default_team} ({status_note})\n\nUpdate or confirm in Admin: \n\n{app_url}/admin\n",
            )
            admin_sent += 1
        if adm.get("alert_sms"):
            adm_topic = (adm.get("alert_personal_topic") or "").strip() or f"nflloserpool-{str(adm['id'])[:8]}"
            send_ntfy_push(adm_topic, f"Admin Check: Week {target_week} Default = {default_team}",
                           f"Verify Week {target_week} default team ({default_team} - {status_note}) before Sunday at NOON ET.", f"{app_url}/admin")
            admin_sent += 1

    regs = supabase.table("tournament_registrations").select("user_id, game_type").eq("is_enrolled", True).neq("bracket_status", "Eliminated").execute().data or []
    week_picks = supabase.table("user_picks").select("user_id, game_type").eq("week", target_week).execute().data or []
    matches = supabase.table("nfl_schedule").select("id").eq("week", target_week).execute().data or []
    required_count = get_required_picks(target_week, len(matches))

    missing_by_user = {}
    for r in regs:
        uid = str(r["user_id"])
        if admin_only_uid and uid != admin_only_uid:
            continue
        gtype = r["game_type"]
        if sum(1 for p in week_picks if str(p["user_id"]) == uid and p["game_type"] == gtype) < required_count:
            missing_by_user.setdefault(uid, []).append(gtype.replace("_", " "))

    sent_emails, sent_pushes = 0, 0
    for uid, missing_pools in missing_by_user.items():
        u = user_map.get(uid)
        if not u:
            continue
        uname = u.get("username") or "Player"
        pools_label = " & ".join(missing_pools)
        if u.get("alert_email") and u.get("email"):
            send_smtp_email(
                smtp_user, smtp_pass, u["email"],
                f"NFL Loser Pool Reminder: Week {target_week} Pick Needed ({pools_label})",
                f"Hey {uname},\n\nYou still need to submit your Week {target_week} pick(s) for the {pools_label} Pool.\n\n"
                f"You have until Sunday at NOON ET (or by kickoff of an earlier game) to avoid being given your BYE (if available) or the highest favored/ranked team that still has yet to play this week.\n\n"
                f"Submit your pick now: \n\n{app_url}\n",
            )
            sent_emails += 1
        if u.get("alert_sms"):
            personal_topic = (u.get("alert_personal_topic") or "").strip() or f"nflloserpool-{uid[:8]}"
            send_ntfy_push(personal_topic, f"NFL Loser Pool: Week {target_week} Pick Needed",
                           f"Hey {uname}, submit your {pools_label} Pool pick before Sunday at NOON ET to avoid being given your BYE (if available) or the highest favored/ranked team that still has yet to play this week.", app_url)
            sent_pushes += 1

    scope = "Test (Admin Only)" if admin_only_uid else "All Missing Players"
    return f"Week {target_week} reminders ({scope}): {admin_sent} admin alerts, {sent_emails} player emails, {sent_pushes} push alerts sent."
async def render_admin_view(supabase, user, on_badge_change=None):
    is_masquerading = bool(app.storage.user.get("masquerade_uid"))
    if is_masquerading or not (app.storage.user.get("is_admin_cached") or is_admin_user(supabase, user)):
        ui.label("🔒 Access Denied: Admin Privileges Required.").classes("text-red-500 font-bold text-lg")
        return

    current_week = get_current_nfl_week()
    ui.label("Admin Control Console").classes("text-xl font-black")

    users_data, regs_data, picks_data, sched_data, pending_data = await asyncio.gather(
        run.io_bound(lambda: supabase.table("users").select("*").execute().data or []),
        run.io_bound(lambda: supabase.table("tournament_registrations").select("*").execute().data or []),
        run.io_bound(lambda: supabase.table("user_picks").select("*").execute().data or []),
        run.io_bound(lambda: supabase.table("nfl_schedule").select("*").execute().data or []),
        run.io_bound(lambda: supabase.table("enrollment_requests").select("id").eq("status", "Pending").execute().data or []),
    )
    cache = {"users": users_data, "regs": regs_data, "picks": picks_data, "sched": sched_data}
    refresh_hooks = {}
    init_pending_cnt = len(pending_data)

    with ui.tabs().classes("w-full mb-3") as admin_tabs:
        t_results = ui.tab("Results")
        t_deadline = ui.tab("Deadline Tools")
        t_csv = ui.tab("CSV Import")
        with ui.tab("Registrations") as t_reg:
            reg_tab_badge = ui.badge(str(init_pending_cnt), color="red").classes(
                f"ml-1.5 text-[10px] font-black {'hidden' if init_pending_cnt == 0 else ''}"
            )
        t_users = ui.tab("User Management")

    with ui.tab_panels(admin_tabs, value=t_results).classes("w-full bg-transparent"):
        with ui.tab_panel(t_results).classes("px-0"):
            week_opts = {w: f"{get_week_label(w)} (current)" if w == current_week else get_week_label(w) for w in range(1, 23)}
            sel_week = ui.select(week_opts, value=current_week, label="Select Week").props("dense outlined").classes("w-52 mb-3")

            @ui.refreshable
            def results_panel():
                w_num = sel_week.value
                enr_regs = [r for r in cache["regs"] if r.get("is_enrolled")]
                wk_picks = [p for p in cache["picks"] if p["week"] == w_num]

                def calc_pool_stats(pool_slug: str):
                    p_regs = [r for r in enr_regs if r.get("game_type") == pool_slug]
                    wrong_wk = sum(1 for p in wk_picks if p.get("game_type") == pool_slug and p.get("pick_state") == "Incorrect")
                    elim_this_wk = 0
                    for r in p_regs:
                        if r.get("bracket_status") != "Eliminated":
                            continue
                        uid = str(r["user_id"])
                        u_losses_up_to = [p for p in cache["picks"] if str(p["user_id"]) == uid and p.get("game_type") == pool_slug and p.get("pick_state") == "Incorrect" and p["week"] <= w_num]
                        u_losses_before = [p for p in u_losses_up_to if p["week"] < w_num]
                        thresh = 1 if pool_slug == "2nd_Chance" else 2
                        if len(u_losses_before) < thresh and len(u_losses_up_to) >= thresh:
                            elim_this_wk += 1

                    loser_cnt = sum(1 for r in p_regs if r.get("bracket_status") == "Loser Bracket")
                    winner_cnt = sum(1 for r in p_regs if r.get("bracket_status") == "Winner Bracket")
                    elim_cnt = sum(1 for r in p_regs if r.get("bracket_status") == "Eliminated")
                    return wrong_wk, elim_this_wk, loser_cnt, winner_cnt, elim_cnt

                m_wrong, m_elim_wk, m_l, m_w, m_e = calc_pool_stats("Main")
                sc_wrong, sc_elim_wk, sc_l, _, sc_e = calc_pool_stats("2nd_Chance")

                with ui.grid().classes("w-full grid-cols-1 md:grid-cols-2 gap-3 mb-4"):
                    with ui.card().classes("p-3.5 text-white shadow-none").style("background-color: #1d3d70;"):
                        ui.label("Summary - Main Pool").classes("font-black text-sm md:text-base mb-1")
                        ui.label(f"Wrong Picks This Week: {m_wrong}").classes("text-xs font-bold")
                        ui.label(f"Players Eliminated This Week: {m_elim_wk}").classes("text-xs font-bold mb-1")
                        ui.label(f"Loser Bracket: {m_l}  |  Winner Bracket: {m_w}  |  Eliminated: {m_e}").classes("text-xs font-extrabold opacity-90")

                    with ui.card().classes("p-3.5 text-white shadow-none").style("background-color: #974706;"):
                        ui.label("Summary - 2nd Chance Pool").classes("font-black text-sm md:text-base mb-1")
                        ui.label(f"Wrong Picks This Week: {sc_wrong}").classes("text-xs font-bold")
                        ui.label(f"Players Eliminated This Week: {sc_elim_wk}").classes("text-xs font-bold mb-1")
                        ui.label(f"Loser Bracket: {sc_l}  |  Eliminated: {sc_e}").classes("text-xs font-extrabold opacity-90")

                ui.label("Select the LOSER of each matchup (or tie) and select SO if it was a shutout.").classes("text-xs font-semibold opacity-75 mb-3")
                matches = [m for m in cache["sched"] if m["week"] == w_num]
                matches = sorted(matches, key=lambda m: (0, str(m["kickoff_time"]), m["id"]) if m.get("kickoff_time") else (1, "", m["id"]))

                if not matches:
                    ui.label("No games found for this week.").classes("text-sm opacity-70")
                    return

                controls = {}
                for m in matches:
                    mid = m["id"]
                    away, home = m["away_team"].upper(), m["home_team"].upper()
                    db_loser = m.get("winner") or "PENDING"
                    db_so = bool(m.get("is_shutout", False))
                    init_val = db_loser if db_loser in ["PENDING", away, home, "TIE"] else "PENDING"

                    time_label = "TBD"
                    if kickoff_raw := m.get("kickoff_time"):
                        dt_naive = datetime.datetime.fromisoformat(str(kickoff_raw).replace(" ", "T")[:19])
                        dt_et = dt_naive.replace(tzinfo=ET_ZONE)
                        time_label = dt_et.strftime("%a %-m/%-d/%y %-I:%M %p ET")

                    state_holder = {"value": init_val}
                    with ui.card().classes("w-full p-2.5 mb-2 border border-slate-300 dark:border-slate-700 shadow-none"):
                        with ui.row().classes("w-full items-center justify-between gap-2 flex-wrap"):
                            with ui.row().classes("items-center gap-2.5 flex-wrap"):
                                ui.label(time_label).classes("text-xs font-semibold opacity-75 w-40 shrink-0")
                                opt_buttons = {}

                                def make_selector(choice_val, btns_dict, holder):
                                    def select_opt():
                                        holder["value"] = choice_val
                                        for k, b in btns_dict.items():
                                            if k == choice_val:
                                                b.classes(remove="opacity-60 border-slate-300 dark:border-slate-700", add="bg-blue-600 text-white border-blue-500 shadow-sm")
                                            else:
                                                b.classes(remove="bg-blue-600 text-white border-blue-500 shadow-sm", add="opacity-60 border-slate-300 dark:border-slate-700")
                                    return select_opt

                                for idx_opt, opt_val in enumerate(["PENDING", away, home, "TIE"]):
                                    if idx_opt == 2:
                                        ui.label("@").classes("text-xs font-black text-slate-400")
                                    is_active = (opt_val == init_val)
                                    base_cls = "px-2.5 py-1 rounded-md border text-xs font-extrabold cursor-pointer transition-all " + (
                                        "bg-blue-600 text-white border-blue-500 shadow-sm" if is_active else "opacity-60 border-slate-300 dark:border-slate-700"
                                    )
                                    with ui.row().classes(f"items-center gap-1.5 no-wrap {base_cls}") as opt_box:
                                        if opt_val in [away, home]:
                                            if logo_u := get_logo_url(opt_val):
                                                ui.html(f'<img src="{logo_u}" class="w-5 h-3.5 object-contain shrink-0" />')
                                        ui.label(opt_val).classes("leading-none")
                                    opt_buttons[opt_val] = opt_box
                                    opt_box.on("click", make_selector(opt_val, opt_buttons, state_holder))

                            chk = ui.checkbox("🎯 SO", value=db_so).props("dense").classes("text-xs font-bold shrink-0")
                            controls[mid] = {"away": away, "home": home, "state": state_holder, "chk": chk}

                def run_db_scoring_batch(week_num, snapshot):
                    losers_set, winners_set, shutouts_set, ties_set, pending_teams = set(), set(), set(), set(), set()
                    for mid, item in snapshot.items():
                        res_val, so_val = item["res_val"], item["so_val"]
                        supabase.table("nfl_schedule").update({"winner": None if res_val == "PENDING" else res_val, "is_shutout": so_val}).eq("id", mid).execute()
                        if res_val == "PENDING":
                            pending_teams.update([item["away"], item["home"]])
                        elif res_val == "TIE":
                            ties_set.update([item["away"], item["home"]])
                        elif res_val in [item["away"], item["home"]]:
                            losers_set.add(res_val)
                            opp = item["home"] if res_val == item["away"] else item["away"]
                            winners_set.add(opp)
                            if so_val:
                                shutouts_set.add(res_val)

                    week_picks = supabase.table("user_picks").select("*").eq("week", week_num).execute().data or []
                    for p in week_picks:
                        raw_t = p["team_picked"].upper()
                        base_t = raw_t.replace("_SO", "")
                        if base_t == "BYE":
                            supabase.table("user_picks").update({"pick_state": "Correct"}).eq("id", p["id"]).execute()
                        elif base_t in pending_teams:
                            if p.get("pick_state") in ["Correct", "Incorrect"] or raw_t.endswith("_SO"):
                                supabase.table("user_picks").update({"pick_state": "Finalized", "team_picked": base_t}).eq("id", p["id"]).execute()
                        elif base_t in losers_set:
                            final_t = f"{base_t}_SO" if base_t in shutouts_set else base_t
                            supabase.table("user_picks").update({"pick_state": "Correct", "team_picked": final_t}).eq("id", p["id"]).execute()
                        elif base_t in winners_set or base_t in ties_set:
                            supabase.table("user_picks").update({"pick_state": "Incorrect", "team_picked": base_t}).eq("id", p["id"]).execute()

                    all_regs = supabase.table("tournament_registrations").select("*").eq("is_enrolled", True).execute().data or []
                    all_picks = supabase.table("user_picks").select("*").execute().data or []
                    for r in all_regs:
                        uid, gtype = r["user_id"], r["game_type"]
                        losses = sum(1 for p in all_picks if p["user_id"] == uid and p["game_type"] == gtype and p.get("pick_state") == "Incorrect")
                        new_status = ("Eliminated" if losses >= 1 else "Loser Bracket") if gtype == "2nd_Chance" else (
                            "Loser Bracket" if losses == 0 else ("Winner Bracket" if losses == 1 else "Eliminated")
                        )
                        supabase.table("tournament_registrations").update({"bracket_status": new_status}).eq("id", r["id"]).execute()

                    cache["sched"] = supabase.table("nfl_schedule").select("*").execute().data or []
                    cache["picks"] = all_picks
                    cache["regs"] = supabase.table("tournament_registrations").select("*").execute().data or []

                async def process_dual_pool_scores():
                    save_btn.props("loading")
                    notif = ui.notification(f"Saving Week {w_num} results & recalculating brackets...", spinner=True, timeout=None, type="info")
                    try:
                        snapshot = {mid: {"away": it["away"], "home": it["home"], "res_val": it["state"]["value"], "so_val": it["chk"].value} for mid, it in controls.items()}
                        await run.io_bound(run_db_scoring_batch, w_num, snapshot)
                        notif.message, notif.spinner, notif.type, notif.timeout = f"Week {w_num} scored & brackets updated!", False, "positive", 4.0
                        results_panel.refresh()
                    except Exception as err:
                        notif.message, notif.spinner, notif.type, notif.timeout = f"Error: {err}", False, "negative", 8.0
                    finally:
                        save_btn.props(remove="loading")

                save_btn = ui.button("Save & Process Both Pools", on_click=process_dual_pool_scores, color="primary").classes("w-full mt-3 font-bold")

            sel_week.on_value_change(lambda: results_panel.refresh())
            results_panel()
        with ui.tab_panel(t_deadline).classes("px-0"):
            ui.label("Weekly Auto-Pick Default Team").classes("text-base font-extrabold mb-1")
            def_week_opts = {w: get_week_label(w) for w in range(1, 23)}

            with ui.row().classes("w-full items-center gap-3 mb-2 flex-wrap"):
                def_week_sel = ui.select(def_week_opts, value=current_week, label="Select Week").classes("w-48")
                team_sel = ui.select([], label="Default Team").classes("w-40")

                def save_default_team():
                    w_num = def_week_sel.value
                    chosen = (team_sel.value or "").strip().upper()
                    if chosen:
                        supabase.table("default_picks").upsert({"week": w_num, "team": chosen, "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat()}).execute()
                        ui.notify(f"Saved {chosen} as Week {w_num} default pick!", type="positive")
                        default_pick_status.refresh()
                        missing_picks_preview.refresh()

                ui.button("Save Week Default", on_click=save_default_team, color="primary").classes("font-bold")

            @ui.refreshable
            def default_pick_status():
                w_num = def_week_sel.value
                all_defs = supabase.table("default_picks").select("*").order("week", desc=False).execute().data or []
                def_map = {int(d["week"]): d["team"].upper() for d in all_defs}
                saved_exact = def_map.get(w_num)
                prior_weeks = [w for w in sorted(def_map.keys(), reverse=True) if w < w_num]
                first_prior = next(iter(prior_weeks), None)
                inherited = def_map[first_prior] if (not saved_exact and first_prior is not None) else None
                active_team = saved_exact or inherited or "SEA"

                wk_matches = [m for m in cache["sched"] if m["week"] == w_num]
                teams_set = {t.upper() for m in wk_matches for t in (m.get("away_team"), m.get("home_team")) if t} or {"SEA"}
                sorted_teams = sorted(teams_set | {active_team})
                team_sel.options, team_sel.value = sorted_teams, active_team
                team_sel.update()

                if saved_exact:
                    ui.label(f"Explicitly saved for Week {w_num}: {saved_exact}").classes("text-xs font-bold text-emerald-600 dark:text-emerald-400 mb-2")
                elif inherited:
                    ui.label(f"Not yet saved for Week {w_num} — will auto-inherit prior default: {inherited}").classes("text-xs font-bold text-amber-600 dark:text-amber-400 mb-2")
                else:
                    ui.label(f"No default saved yet for Week {w_num}.").classes("text-xs font-bold text-red-500 mb-2")

            default_pick_status()
            ui.separator().classes("my-5")

            with ui.card().classes("w-full p-4 border border-amber-500/40 shadow-none"):
                ui.label("Manual Deadline Lock & Reminder Triggers").classes("text-base font-extrabold mb-2")

                def open_lock_confirm():
                    w_target = def_week_sel.value
                    with ui.dialog() as lock_dlg, ui.card().classes("p-5 max-w-md"):
                        ui.label(f"Run Deadline Lock for {get_week_label(w_target)}?").classes("text-lg font-black")
                        with ui.row().classes("w-full justify-end gap-2 mt-3"):
                            ui.button("Cancel", on_click=lock_dlg.close).props("flat")

                            async def confirm_run_lock():
                                lock_dlg.close()
                                lock_btn.props("loading")
                                notif = ui.notification(f"Running lock for {get_week_label(w_target)}...", spinner=True, timeout=None, type="info")
                                try:
                                    msg = await run.io_bound(execute_manual_deadline_lock, supabase, w_target)
                                    cache["picks"] = await run.io_bound(lambda: supabase.table("user_picks").select("*").execute().data or [])
                                    cache["regs"] = await run.io_bound(lambda: supabase.table("tournament_registrations").select("*").execute().data or [])
                                    notif.message, notif.spinner, notif.type, notif.timeout = msg, False, "positive", 6.0
                                    default_pick_status.refresh()
                                    missing_picks_preview.refresh()
                                except Exception as err:
                                    notif.message, notif.spinner, notif.type, notif.timeout = f"Lock failed: {err}", False, "negative", 8.0
                                finally:
                                    lock_btn.props(remove="loading")

                            ui.button("Confirm & Lock Week", on_click=confirm_run_lock, color="amber-8").classes("font-bold text-white")
                    lock_dlg.open()

                def copy_missing_emails():
                    w_target = def_week_sel.value
                    active_regs = [r for r in cache["regs"] if r.get("is_enrolled") and r.get("bracket_status") != "Eliminated"]
                    wk_matches = [m for m in cache["sched"] if m["week"] == w_target]
                    req_count = 1 if w_target <= 14 else (2 if w_target <= 18 else max(1, len(wk_matches)))
                    user_email_map = {str(u["id"]): (u.get("email") or "").strip().lower() for u in cache["users"] if u.get("email")}

                    missing_emails = set()
                    for r in active_regs:
                        uid = str(r["user_id"])
                        gtype = r["game_type"]
                        wk_cnt = sum(1 for p in cache["picks"] if str(p["user_id"]) == uid and p["game_type"] == gtype and p["week"] == w_target)
                        if wk_cnt < req_count and user_email_map.get(uid):
                            missing_emails.add(user_email_map[uid])

                    if not missing_emails:
                        ui.notify(f"No missing picks for {get_week_label(w_target)}!", type="positive")
                        return

                    email_list_str = ", ".join(sorted(missing_emails))
                    ui.clipboard.write(email_list_str)
                    ui.notify(f"Copied {len(missing_emails)} missing player email(s) to clipboard!", type="positive", timeout=6000)

                with ui.row().classes("items-center gap-3 flex-wrap"):
                    lock_btn = ui.button("Run Deadline Lock Now", icon="lock_clock", on_click=open_lock_confirm, color="amber-8").classes("font-bold text-white")
                    ui.button("Copy Missing Player Emails", icon="content_copy", on_click=copy_missing_emails, color="primary").classes("font-bold")

            ui.separator().classes("my-5")

            @ui.refreshable
            def missing_picks_preview():
                w_target = def_week_sel.value
                user_name_map = {str(u["id"]): f"{u.get('username') or 'Unknown'} ({u.get('first_name') or ''} {u.get('last_name') or ''})".strip() for u in cache["users"]}
                active_regs = [r for r in cache["regs"] if r.get("is_enrolled") and r.get("bracket_status") != "Eliminated"]
                wk_matches = [m for m in cache["sched"] if m["week"] == w_target]
                req_count = 1 if w_target <= 14 else (2 if w_target <= 18 else max(1, len(wk_matches)))
                active_default = (team_sel.value or "SEA").strip().upper()
                def get_pool_missing(pool_name: str):
                    missing_list = []
                    for r in [x for x in active_regs if x.get("game_type") == pool_name]:
                        uid = str(r["user_id"])
                        u_picks = [p for p in cache["picks"] if str(p["user_id"]) == uid and p["game_type"] == pool_name]
                        missing_slots = req_count - sum(1 for p in u_picks if p["week"] == w_target)
                        if missing_slots <= 0:
                            continue
                        bye_used = any((p.get("team_picked") or "").upper().strip() == "BYE" for p in u_picks)
                        if not bye_used and missing_slots == 1:
                            outcome, is_bye = "BYE Available", True
                        elif not bye_used and missing_slots > 1:
                            outcome, is_bye = f"1 BYE + {missing_slots - 1} Default ({active_default})", True
                        else:
                            outcome, is_bye = f"{f'{missing_slots}x ' if missing_slots > 1 else ''}Default ({active_default})", False
                        missing_list.append({"name": user_name_map.get(uid, uid), "outcome": outcome, "is_bye": is_bye})
                    return sorted(missing_list, key=lambda x: x["name"].lower())

                main_missing, sc_missing = get_pool_missing("Main"), get_pool_missing("2nd_Chance")
                ui.label(f"Missing Picks & Auto-Assign Preview ({get_week_label(w_target)})").classes("text-base font-extrabold mb-2")

                with ui.grid().classes("w-full grid-cols-1 md:grid-cols-2 gap-4"):
                    for title, items, accent in [("Main Pool", main_missing, "border-blue-500/40"), ("2nd Chance Pool", sc_missing, "border-amber-500/40")]:
                        with ui.card().classes(f"w-full p-3 border {accent} shadow-none"):
                            with ui.row().classes("w-full items-center justify-between mb-2 pb-1 border-b border-slate-200 dark:border-slate-700"):
                                ui.label(title).classes("text-sm font-extrabold")
                                ui.badge(f"{len(items)} Missing", color="primary" if items else "positive").classes("text-xs font-bold")
                            if not items:
                                ui.label("All active players have submitted picks!").classes("text-xs opacity-70 italic py-1")
                            else:
                                with ui.column().classes("w-full gap-1.5"):
                                    for entry in items:
                                        with ui.row().classes("w-full items-center justify-between gap-2 text-xs"):
                                            ui.label(entry["name"]).classes("font-semibold truncate")
                                            ui.badge(entry["outcome"], color="green" if entry["is_bye"] else "amber-8").classes("text-[10px] font-bold shrink-0")

            def_week_sel.on_value_change(lambda: (default_pick_status.refresh(), missing_picks_preview.refresh()))
            missing_picks_preview()

        # ================================================================
        # TAB 3: CSV IMPORT (PICKS, NFL SCHEDULE, & PLAYERS)
        # ================================================================
        with ui.tab_panel(t_csv).classes("px-0"):
            async def read_csv_upload(e) -> str:
                raw_bytes = b""
                if hasattr(e, "content") and e.content is not None:
                    e.content.seek(0)
                    data = e.content.read()
                    raw_bytes = await data if hasattr(data, "__await__") else data
                elif hasattr(e, "file") and e.file is not None:
                    data = e.file.read()
                    raw_bytes = await data if hasattr(data, "__await__") else data
                if not raw_bytes:
                    raise ValueError("Uploaded file arrived empty (0 bytes).")
                return raw_bytes.decode("utf-8-sig")

            with ui.grid().classes("w-full grid-cols-1 md:grid-cols-3 gap-4"):
                with ui.card().classes("w-full p-4 border border-slate-300 dark:border-slate-700 shadow-none"):
                    ui.label("Upload Picks CSV").classes("text-base font-extrabold mb-1")
                    ui.label("Columns: game_type, email, week, team_picked, pick_state").classes("text-xs opacity-75 mb-3")
                    picks_lbl = ui.label("Ready").classes("text-xs font-bold text-blue-600 dark:text-blue-400 mt-2")

                    async def on_picks_csv(e):
                        picks_lbl.text = "Processing..."
                        try:
                            text = await read_csv_upload(e)
                            def run_imp():
                                reader = csv.DictReader(io.StringIO(text))
                                reader.fieldnames = [h.strip().lower() for h in (reader.fieldnames or [])]
                                email_map = {u["email"].strip().lower(): str(u["id"]) for u in cache["users"] if u.get("email")}
                                ins, skip = [], 0
                                for row in reader:
                                    uid = email_map.get((row.get("email") or "").strip().lower())
                                    if not uid:
                                        skip += 1
                                        continue
                                    gtype = "2nd_Chance" if (row.get("game_type") or "").strip().lower() in ["2nd_chance", "2nd chance", "2ndchance"] else "Main"
                                    wk, tm, st = int(str(row["week"]).strip()), str(row["team_picked"]).strip().upper(), (row.get("pick_state") or "Finalized").strip()
                                    supabase.table("user_picks").delete().eq("user_id", uid).eq("game_type", gtype).eq("week", wk).eq("team_picked", tm).execute()
                                    ins.append({"user_id": uid, "game_type": gtype, "week": wk, "team_picked": tm, "pick_state": st})
                                if ins:
                                    supabase.table("user_picks").insert(ins).execute()
                                cache["picks"] = supabase.table("user_picks").select("*").execute().data or []
                                return f"Imported {len(ins)} picks ({skip} skipped)."
                            picks_lbl.text = await run.io_bound(run_imp)
                        except Exception as err:
                            picks_lbl.text = f"Error: {err}"

                    ui.upload(on_upload=on_picks_csv, auto_upload=True).props("accept=.csv").classes("w-full")
                with ui.card().classes("w-full p-4 border border-slate-300 dark:border-slate-700 shadow-none"):
                    ui.label("Import NFL Schedule").classes("text-base font-extrabold mb-1")
                    ui.label("Columns: week, away_team, home_team, kickoff_time").classes("text-xs opacity-75 mb-3")
                    sched_lbl = ui.label("Ready").classes("text-xs font-bold text-blue-600 dark:text-blue-400 mt-2")

                    async def on_sched_csv(e):
                        sched_lbl.text = "Processing..."
                        try:
                            text = await read_csv_upload(e)
                            def run_imp():
                                reader = csv.DictReader(io.StringIO(text))
                                reader.fieldnames = [h.strip().lower() for h in (reader.fieldnames or [])]
                                rows = []
                                for row in reader:
                                    wk = int(str(row["week"]).strip())
                                    aw = str(row["away_team"]).strip().upper()
                                    hm = str(row["home_team"]).strip().upper()
                                    ko = (row.get("kickoff_time") or "").strip() or None
                                    supabase.table("nfl_schedule").delete().eq("week", wk).eq("away_team", aw).eq("home_team", hm).execute()
                                    rows.append({"week": wk, "away_team": aw, "home_team": hm, "kickoff_time": ko})
                                if rows:
                                    supabase.table("nfl_schedule").insert(rows).execute()
                                cache["sched"] = supabase.table("nfl_schedule").select("*").execute().data or []
                                return f"Imported {len(rows)} matchups."
                            sched_lbl.text = await run.io_bound(run_imp)
                        except Exception as err:
                            sched_lbl.text = f"Error: {err}"

                    ui.upload(on_upload=on_sched_csv, auto_upload=True).props("accept=.csv").classes("w-full")

                with ui.card().classes("w-full p-4 border border-slate-300 dark:border-slate-700 shadow-none"):
                    ui.label("Import Players").classes("text-base font-extrabold mb-1")
                    ui.label("Columns: username, first_name, last_name, email, cell_phone, is_admin, main_enrolled, main_paid, second_enrolled, second_paid, notes, temporary_password").classes("text-[11px] opacity-75 mb-3")
                    ply_lbl = ui.label("Ready").classes("text-xs font-bold text-blue-600 dark:text-blue-400 mt-2")

                    async def on_players_csv(e):
                        ply_lbl.text = "Processing..."
                        try:
                            text = await read_csv_upload(e)
                            def parse_bool(val) -> bool:
                                return str(val or "").strip().lower() in ["1", "true", "yes", "y", "x"]

                            def run_imp():
                                reader = csv.DictReader(io.StringIO(text))
                                reader.fieldnames = [h.strip().lower() for h in (reader.fieldnames or [])]
                                existing_by_email = {u["email"].strip().lower(): str(u["id"]) for u in cache["users"] if u.get("email")}
                                created, updated = 0, 0
                                for row in reader:
                                    em = (row.get("email") or "").strip().lower()
                                    if not em:
                                        continue
                                    uid = existing_by_email.get(em)
                                    if not uid:
                                        pwd = (row.get("temporary_password") or "").strip() or f"Loser{datetime.datetime.now().year}!"
                                        auth_res = supabase.auth.admin.create_user({"email": em, "password": pwd, "email_confirm": True})
                                        uid = str(auth_res.user.id)
                                        created += 1
                                    else:
                                        updated += 1

                                    email_prefix = next(iter(em.split("@")), "Player")
                                    supabase.table("users").upsert({
                                        "id": uid,
                                        "email": em,
                                        "username": (row.get("username") or email_prefix).strip(),
                                        "first_name": (row.get("first_name") or "").strip(),
                                        "last_name": (row.get("last_name") or "").strip(),
                                        "cell_phone": (row.get("cell_phone") or "").strip(),
                                        "alert_personal_topic": f"nflloserpool-{uid[:8]}",
                                        "is_admin": parse_bool(row.get("is_admin")),
                                        "notes": (row.get("notes") or "").strip(),
                                    }).execute()

                                    for gtype, enr_col, paid_col in [("Main", "main_enrolled", "main_paid"), ("2nd_Chance", "second_enrolled", "second_paid")]:
                                        is_enr, is_pd = parse_bool(row.get(enr_col)), parse_bool(row.get(paid_col))
                                        ex_reg = supabase.table("tournament_registrations").select("id").eq("user_id", uid).eq("game_type", gtype).execute().data or []
                                        if ex_reg:
                                            supabase.table("tournament_registrations").update({"is_enrolled": is_enr, "is_paid": is_pd}).eq("id", next(iter(ex_reg))["id"]).execute()
                                        else:
                                            supabase.table("tournament_registrations").insert({"user_id": uid, "game_type": gtype, "is_enrolled": is_enr, "is_paid": is_pd, "bracket_status": "Loser Bracket"}).execute()

                                cache["users"] = supabase.table("users").select("*").execute().data or []
                                cache["regs"] = supabase.table("tournament_registrations").select("*").execute().data or []
                                return f"Created {created}, updated {updated} players."
                            ply_lbl.text = await run.io_bound(run_imp)
                        except Exception as err:
                            ply_lbl.text = f"Error: {err}"

                    ui.upload(on_upload=on_players_csv, auto_upload=True).props("accept=.csv").classes("w-full")
        # ================================================================
        # TAB 4: REGISTRATIONS (PENDING REQUESTS TOP, WINDOWS BELOW)
        # ================================================================
        with ui.tab_panel(t_reg).classes("px-0"):
            def handle_approve_click(req_obj: dict):
                try:
                    clean_em = (req_obj.get("email") or "").strip().lower()
                    email_prefix = next(iter(clean_em.split("@")), "Player")
                    clean_un = (req_obj.get("username") or email_prefix).strip()
                    target_uid = req_obj.get("user_id")

                    if not target_uid:
                        existing_u = supabase.table("users").select("id").eq("email", clean_em).execute().data or []
                        first_u = next(iter(existing_u), {})
                        if first_u:
                            target_uid = str(first_u["id"])
                        else:
                            temp_pwd = f"Loser{datetime.datetime.now().year}!"
                            try:
                                auth_res = supabase.auth.admin.create_user({"email": clean_em, "password": temp_pwd, "email_confirm": True})
                                target_uid = str(auth_res.user.id)
                            except Exception:
                                all_auth = supabase.auth.admin.list_users()
                                matched = next((au for au in all_auth if (getattr(au, "email", "") or "").lower() == clean_em), None)
                                if not matched:
                                    raise
                                target_uid = str(matched.id)
                                supabase.auth.admin.update_user_by_id(target_uid, {"password": temp_pwd, "email_confirm": True})

                            supabase.table("users").upsert({
                                "id": target_uid,
                                "email": clean_em,
                                "username": clean_un,
                                "first_name": (req_obj.get("first_name") or "").strip(),
                                "last_name": (req_obj.get("last_name") or "").strip(),
                                "cell_phone": (req_obj.get("cell_phone") or "").strip(),
                                "alert_personal_topic": f"nflloserpool-{target_uid[:8]}",
                                "alert_email": True,
                                "alert_sms": False,
                                "is_admin": False,
                            }).execute()

                    existing_reg = supabase.table("tournament_registrations").select("id").eq("user_id", target_uid).eq("game_type", req_obj["game_type"]).execute().data or []
                    if existing_reg:
                        supabase.table("tournament_registrations").update({"is_enrolled": True, "bracket_status": "Loser Bracket"}).eq("id", next(iter(existing_reg))["id"]).execute()
                    else:
                        supabase.table("tournament_registrations").insert({"user_id": target_uid, "game_type": req_obj["game_type"], "is_enrolled": True, "is_paid": False, "bracket_status": "Loser Bracket"}).execute()

                    supabase.table("enrollment_requests").update({"status": "Approved", "user_id": target_uid}).eq("id", req_obj["id"]).execute()
                    cache["users"] = supabase.table("users").select("*").execute().data or []
                    cache["regs"] = supabase.table("tournament_registrations").select("*").execute().data or []

                    ui.notify(f"Approved {clean_un}! Copy their welcome info in User Management.", type="positive", timeout=6000)
                    pending_requests_panel.refresh()
                    if "roster" in refresh_hooks:
                        refresh_hooks["roster"]()
                except Exception as err:
                    ui.notify(f"Approval error: {err}", type="negative", timeout=10000)

            def handle_decline_click(req_obj: dict):
                try:
                    supabase.table("enrollment_requests").update({"status": "Declined"}).eq("id", req_obj["id"]).execute()
                    ui.notify(f"Declined {req_obj.get('username') or 'Player'}.", type="info")
                    pending_requests_panel.refresh()
                except Exception as err:
                    ui.notify(f"Decline error: {err}", type="negative", timeout=10000)
            @ui.refreshable
            def pending_requests_panel():
                reqs = supabase.table("enrollment_requests").select("*").eq("status", "Pending").order("created_at", desc=False).execute().data or []
                cnt = len(reqs)
                reg_tab_badge.text = str(cnt)
                reg_tab_badge.classes(remove="hidden") if cnt > 0 else reg_tab_badge.classes(add="hidden")
                ui.label(f"Pending Join Requests ({cnt})").classes("text-base font-extrabold mb-2")

                if not reqs:
                    ui.label("No pending join requests right now.").classes("text-xs opacity-70 italic mb-2")
                    return

                for rq in reqs:
                    gtype = rq["game_type"]
                    uname = rq.get("username") or "Player"
                    email = rq.get("email") or ""
                    full_nm = f"{rq.get('first_name') or ''} {rq.get('last_name') or ''}".strip()
                    is_new_acct = not bool(rq.get("user_id"))

                    with ui.card().classes("w-full p-3 mb-2 border border-blue-500/40 shadow-none"):
                        with ui.row().classes("w-full items-center justify-between gap-2 flex-wrap"):
                            with ui.column().classes("gap-0.5"):
                                with ui.row().classes("items-center gap-2"):
                                    ui.label(uname).classes("text-sm font-extrabold")
                                    ui.badge(gtype.replace("_", " "), color="amber-8" if gtype == "2nd_Chance" else "primary").classes("text-[10px] font-bold")
                                    if is_new_acct:
                                        ui.badge("NEW ACCOUNT", color="purple").classes("text-[10px] font-bold")
                                ui.label(f"{email}  •  {full_nm or 'No name'}  •  {rq.get('cell_phone') or 'No phone'}").classes("text-xs opacity-80")

                            with ui.row().classes("items-center gap-2"):
                                ui.button("Approve", on_click=lambda _e, r=rq: handle_approve_click(r), color="positive").props("size=sm").classes("font-bold")
                                ui.button("Decline", on_click=lambda _e, r=rq: handle_decline_click(r), color="red").props("outline size=sm")

            pending_requests_panel()
            ui.separator().classes("my-4")
            ui.label("Self-Enrollment Registration Windows (Eastern Time)").classes("text-base font-extrabold mb-1")
            ui.label("Controls when the Request to Join button appears on the Login screen and un-enrolled Picks tabs.").classes("text-xs opacity-75 mb-3")

            win_rows = supabase.table("registration_windows").select("*").execute().data or []
            win_map = {r["game_type"]: r for r in win_rows}

            with ui.grid().classes("w-full grid-cols-1 md:grid-cols-2 gap-4"):
                for gtype, label_title, default_open, default_close in [
                    ("Main", "Main Pool (Default: 6 Wks Pre-Season)", "2026-07-29 00:00", "2026-09-13 12:00"),
                    ("2nd_Chance", "2nd Chance Pool (Default: 2 Wks Pre-Start)", "2026-09-30 00:00", "2026-10-19 12:00"),
                ]:
                    existing_w = win_map.get(gtype)
                    open_str, close_str = default_open, default_close
                    if existing_w:
                        try:
                            o_dt = datetime.datetime.fromisoformat(str(existing_w["opens_at"]).replace("Z", "+00:00")).astimezone(ET_ZONE)
                            c_dt = datetime.datetime.fromisoformat(str(existing_w["closes_at"]).replace("Z", "+00:00")).astimezone(ET_ZONE)
                            open_str, close_str = o_dt.strftime("%Y-%m-%d %H:%M"), c_dt.strftime("%Y-%m-%d %H:%M")
                        except Exception:
                            pass

                    with ui.card().classes("w-full p-3 border border-slate-300 dark:border-slate-700 shadow-none"):
                        ui.label(label_title).classes("text-sm font-extrabold mb-2")
                        op_in = ui.input("Opens At (YYYY-MM-DD HH:MM ET)", value=open_str).classes("w-full mb-2")
                        cl_in = ui.input("Closes At (YYYY-MM-DD HH:MM ET)", value=close_str).classes("w-full mb-2")

                        def save_window(gt=gtype, o_box=op_in, c_box=cl_in):
                            try:
                                o_et = datetime.datetime.strptime(o_box.value.strip(), "%Y-%m-%d %H:%M").replace(tzinfo=ET_ZONE)
                                c_et = datetime.datetime.strptime(c_box.value.strip(), "%Y-%m-%d %H:%M").replace(tzinfo=ET_ZONE)
                                supabase.table("registration_windows").upsert({
                                    "game_type": gt,
                                    "opens_at": o_et.astimezone(datetime.timezone.utc).isoformat(),
                                    "closes_at": c_et.astimezone(datetime.timezone.utc).isoformat(),
                                    "updated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                                }).execute()
                                ui.notify(f"Saved {gt.replace('_', ' ')} registration window!", type="positive")
                            except Exception as err:
                                ui.notify(f"Invalid date format (use YYYY-MM-DD HH:MM): {err}", type="negative")

                        ui.button("Save Window", on_click=save_window, color="primary").props("size=sm").classes("font-bold")
        # ================================================================
        # TAB 5: USER MANAGEMENT (WITH INLINE MASQUERADE BUTTON)
        # ================================================================
        with ui.tab_panel(t_users).classes("px-0"):
            with ui.row().classes("w-full items-center gap-3 mb-3 flex-wrap"):
                pool_filter = ui.select(["Main", "2nd_Chance"], value="Main", label="Pool").classes("w-36")
                enroll_filter = ui.select(["All", "Enrolled", "Not Enrolled"], value="All", label="Enrollment").classes("w-36")
                paid_filter = ui.select(["All", "Paid", "Not Paid"], value="All", label="Payment").classes("w-36")
                bracket_filter = ui.select(["All", "Loser Bracket", "Winner Bracket", "Eliminated"], value="All", label="Bracket Status").classes("w-44")
                search_input = ui.input(label="Search Name / Username / Email / ID / Notes", placeholder="Type to filter...").props("clearable").classes("flex-1 min-w-[200px]")

            def on_pool_change():
                if pool_filter.value == "2nd_Chance":
                    bracket_filter.options = ["All", "Loser Bracket", "Eliminated"]
                    if bracket_filter.value == "Winner Bracket":
                        bracket_filter.value = "All"
                else:
                    bracket_filter.options = ["All", "Loser Bracket", "Winner Bracket", "Eliminated"]
                bracket_filter.update()
                roster_list.refresh()

            pool_filter.on_value_change(on_pool_change)
            enroll_filter.on_value_change(lambda: roster_list.refresh())
            paid_filter.on_value_change(lambda: roster_list.refresh())
            bracket_filter.on_value_change(lambda: roster_list.refresh())
            search_input.on_value_change(lambda: roster_list.refresh())

            @ui.refreshable
            def roster_list():
                users = sorted(cache["users"], key=lambda u: (u.get("username") or "").lower())
                reg_by_uid = {str(r["user_id"]): r for r in cache["regs"] if r.get("game_type") == pool_filter.value}
                status_opts = ["Loser Bracket", "Eliminated"] if pool_filter.value == "2nd_Chance" else ["Loser Bracket", "Winner Bracket", "Eliminated"]
                query_txt = (search_input.value or "").strip().lower()

                filtered_users = []
                for u in users:
                    r = reg_by_uid.get(str(u["id"]))
                    is_enr = bool(r.get("is_enrolled")) if r else False
                    is_pd = bool(r.get("is_paid")) if r else False
                    b_stat = (r.get("bracket_status") or "Loser Bracket") if r else "Not Enrolled"

                    if (enroll_filter.value == "Enrolled" and not is_enr) or (enroll_filter.value == "Not Enrolled" and is_enr):
                        continue
                    if (paid_filter.value == "Paid" and not is_pd) or (paid_filter.value == "Not Paid" and is_pd):
                        continue
                    if bracket_filter.value != "All" and (not r or b_stat != bracket_filter.value):
                        continue
                    if query_txt and query_txt not in " ".join([str(u.get("id") or ""), u.get("username") or "", u.get("first_name") or "", u.get("last_name") or "", u.get("email") or "", u.get("notes") or ""]).lower():
                        continue
                    filtered_users.append(u)

                ui.label(f"Showing {len(filtered_users)} of {len(users)} users").classes("text-xs font-bold opacity-70 mb-2")

                def open_user_editor(u_row: dict):
                    uid = str(u_row["id"])
                    personal_topic = (u_row.get("alert_personal_topic") or "").strip() or f"nflloserpool-{uid[:8]}"
                    with ui.dialog() as dlg, ui.card().classes("w-full max-w-lg p-5"):
                        ui.label(f"Edit User: {u_row.get('username') or 'Player'}").classes("text-lg font-black")
                        ui.label(f"User ID: {uid}").classes("text-[11px] font-mono opacity-60 mb-3 select-all")

                        with ui.grid().classes("w-full grid-cols-1 md:grid-cols-2 gap-2"):
                            ed_user = ui.input("Username", value=u_row.get("username") or "").classes("w-full")
                            ed_email = ui.input("Email", value=u_row.get("email") or "").classes("w-full")
                            ed_first = ui.input("First Name", value=u_row.get("first_name") or "").classes("w-full")
                            ed_last = ui.input("Last Name", value=u_row.get("last_name") or "").classes("w-full")
                            ed_phone = ui.input("Cell Phone", value=u_row.get("cell_phone") or "").classes("w-full")
                            ui.input("ntfy.sh Topic (Read-Only)", value=personal_topic).props("readonly").classes("w-full")
                        def copy_player_welcome(reset_pwd: bool = False):
                            app_url = os.environ.get("APP_URL", "https://nfl-loser-pool-production.up.railway.app").rstrip("/")
                            cur_uname = ed_user.value.strip() or "Player"
                            cur_email = ed_email.value.strip().lower()
                            std_temp = f"Loser{datetime.datetime.now().year}!"

                            if reset_pwd:
                                supabase.auth.admin.update_user_by_id(uid, {"password": std_temp})
                                msg_txt = (
                                    f"Hey {cur_uname},\n\n"
                                    f"Your NFL Loser Pool password has been reset!\n\n"
                                    f"Login Link: {app_url}\n"
                                    f"Email: {cur_email}\n"
                                    f"Temporary Password: {std_temp}\n\n"
                                    f"Please log in and update your password on the Profile page whenever you're ready."
                                )
                                ui.clipboard.write(msg_txt)
                                ui.notify(f"Password reset to {std_temp} & message copied!", type="positive", timeout=6000)
                            else:
                                msg_txt = (
                                    f"Hey {cur_uname},\n\n"
                                    f"Welcome to the NFL Loser Pool!\n\n"
                                    f"Login Link: {app_url}\n"
                                    f"Email: {cur_email}\n"
                                    f"Temporary Password: {std_temp}\n\n"
                                    f"Please log in and update your password on the Profile page whenever you're ready."
                                )
                                ui.clipboard.write(msg_txt)
                                ui.notify("Welcome message with temp password copied!", type="positive")

                        with ui.row().classes("w-full items-center gap-2 mt-3 flex-wrap"):
                            ui.button("Copy Welcome Message", icon="content_copy", on_click=lambda: copy_player_welcome(False), color="secondary").props("outline size=sm").classes("font-bold")
                            ui.button("Reset Password & Copy", icon="lock_reset", on_click=lambda: copy_player_welcome(True), color="amber-8").props("outline size=sm").classes("font-bold")

                        with ui.row().classes("w-full gap-4 mt-2"):
                            ed_a_email = ui.checkbox("Alert Email", value=bool(u_row.get("alert_email", True)))
                            ed_a_sms = ui.checkbox("Alert Push (ntfy)", value=bool(u_row.get("alert_sms", False)))
                            ed_admin = ui.checkbox("Is Admin", value=bool(u_row.get("is_admin", False)))

                        ed_notes = ui.textarea("Commissioner Notes", value=u_row.get("notes") or "").classes("w-full mt-2").props("rows=2")

                        with ui.row().classes("w-full justify-between items-center mt-4 pt-3 border-t border-slate-200 dark:border-slate-700"):
                            def confirm_delete_user():
                                with ui.dialog() as del_dlg, ui.card().classes("p-4"):
                                    ui.label(f"Permanently delete {u_row.get('username')}?").classes("font-bold text-red-600")
                                    with ui.row().classes("w-full justify-end gap-2 mt-3"):
                                        ui.button("Cancel", on_click=del_dlg.close).props("flat")

                                        def execute_delete():
                                            supabase.table("user_picks").delete().eq("user_id", uid).execute()
                                            supabase.table("tournament_registrations").delete().eq("user_id", uid).execute()
                                            supabase.table("users").delete().eq("id", uid).execute()
                                            cache["users"] = [x for x in cache["users"] if str(x["id"]) != uid]
                                            del_dlg.close()
                                            dlg.close()
                                            ui.notify("User deleted.", type="warning")
                                            roster_list.refresh()

                                        ui.button("Confirm Delete", on_click=execute_delete, color="red")
                                del_dlg.open()

                            ui.button("Delete User", on_click=confirm_delete_user, color="red").props("outline size=sm")

                            with ui.row().classes("gap-2"):
                                ui.button("Cancel", on_click=dlg.close).props("flat")

                                def save_user_edits():
                                    updates = {
                                        "username": ed_user.value.strip(),
                                        "email": ed_email.value.strip(),
                                        "first_name": ed_first.value.strip(),
                                        "last_name": ed_last.value.strip(),
                                        "cell_phone": ed_phone.value.strip(),
                                        "alert_email": ed_a_email.value,
                                        "alert_sms": ed_a_sms.value,
                                        "is_admin": ed_admin.value,
                                        "notes": ed_notes.value.strip(),
                                    }
                                    supabase.table("users").update(updates).eq("id", uid).execute()
                                    u_row.update(updates)
                                    dlg.close()
                                    ui.notify("User updated!", type="positive")
                                    roster_list.refresh()

                                ui.button("Save Changes", on_click=save_user_edits, color="primary")
                    dlg.open()

                for u in filtered_users:
                    uid = str(u["id"])
                    uname = u.get("username") or "Unknown"
                    r = reg_by_uid.get(uid)
                    with ui.card().classes("w-full p-2.5 mb-2 border border-slate-200 dark:border-slate-700 shadow-none"):
                        with ui.row().classes("w-full items-start justify-between gap-2"):
                            with ui.column().classes("gap-0.5 flex-1 min-w-0"):
                                with ui.row().classes("items-center gap-2 flex-wrap"):
                                    ui.label(uname).classes("text-sm font-extrabold")
                                    if u.get("is_admin"):
                                        ui.badge("ADMIN", color="purple").classes("text-[10px] font-bold")
                                    if uid != str(user.id):
                                        def start_masquerade(target_id=uid, target_name=uname):
                                            app.storage.user["masquerade_uid"] = target_id
                                            app.storage.user["masquerade_name"] = target_name
                                            app.storage.user["active_route"] = "/"
                                            ui.run_javascript("window.location.href = '/'")

                                        ui.button("Masquerade", on_click=start_masquerade).props("dense outline size=xs color=purple")
                                    ui.button("Edit / Delete", on_click=lambda u_obj=u: open_user_editor(u_obj)).props("dense outline size=xs color=primary")

                                ui.label(f"{u.get('email') or 'No email'}").classes("text-xs opacity-80 truncate")
                                ui.label(f"{uid}").classes("text-[10px] font-mono opacity-60 truncate select-all")
                                if u.get("notes"):
                                    ui.label(f"{u['notes']}").classes("text-xs text-amber-700 dark:text-amber-300 italic mt-0.5")

                            if r:
                                with ui.row().classes("items-center gap-2 shrink-0"):
                                    ui.checkbox("Enrolled", value=bool(r.get("is_enrolled")), on_change=lambda e, rid=r["id"], reg_obj=r: (supabase.table("tournament_registrations").update({"is_enrolled": e.value}).eq("id", rid).execute(), reg_obj.update({"is_enrolled": e.value}), roster_list.refresh())).props("dense")
                                    ui.checkbox("Paid", value=bool(r.get("is_paid")), on_change=lambda e, rid=r["id"], reg_obj=r: (supabase.table("tournament_registrations").update({"is_paid": e.value}).eq("id", rid).execute(), reg_obj.update({"is_paid": e.value}), roster_list.refresh())).props("dense")
                                    cur_st = r.get("bracket_status") if r.get("bracket_status") in status_opts else "Loser Bracket"
                                    ui.select(status_opts, value=cur_st, on_change=lambda e, rid=r["id"], reg_obj=r: (supabase.table("tournament_registrations").update({"bracket_status": e.value}).eq("id", rid).execute(), reg_obj.update({"bracket_status": e.value}), roster_list.refresh())).props("dense outlined").classes("w-36 text-xs")

            refresh_hooks["roster"] = roster_list.refresh
            roster_list()

import os
import csv
import io
import datetime
from zoneinfo import ZoneInfo
from nicegui import ui, app, run
from picks_module import get_current_nfl_week, get_week_label, get_logo_url
from background_cron_reminders import (
    send_smtp_email,
    send_ntfy_push,
    resolve_week_default_info,
    get_required_picks,
)

ET_ZONE = ZoneInfo("America/New_York")

def is_admin_user(supabase, user) -> bool:
    if not user:
        return False
    try:
        res = supabase.table("users").select("is_admin").eq("id", str(user.id)).execute().data
        if res and isinstance(res, list) and len(res) > 0:
            return bool(res[0].get("is_admin", False))
    except Exception:
        pass
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
        if prior:
            default_team = def_map[prior[0]]
            supabase.table("default_picks").upsert({
                "week": target_week,
                "team": default_team,
                "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat()
            }).execute()

    auto_byes, auto_defaults, no_picks = 0, 0, 0

    for r in regs:
        uid = str(r["user_id"])
        gtype = r["game_type"]
        user_pool_picks = [p for p in all_picks if str(p["user_id"]) == uid and p["game_type"] == gtype]
        current_week_picks = [p for p in user_pool_picks if p["week"] == target_week]
        missing_slots = required_count - len(current_week_picks)

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
        uid = str(r["user_id"])
        gtype = r["game_type"]
        losses = sum(1 for p in all_picks if str(p["user_id"]) == uid and p["game_type"] == gtype and p.get("pick_state") == "Incorrect")
        if gtype == "2nd_Chance":
            new_status = "Eliminated" if losses >= 1 else "Loser Bracket"
        else:
            new_status = "Loser Bracket" if losses == 0 else ("Winner Bracket" if losses == 1 else "Eliminated")
        if new_status != r.get("bracket_status"):
            supabase.table("tournament_registrations").update({"bracket_status": new_status}).eq("id", r["id"]).execute()

    return (
        f"Week {target_week} lock complete: {len(confirmed_picks)} finalized, "
        f"{auto_byes} auto-BYEs, {auto_defaults} default picks ({default_team or 'None'}), {no_picks} NO_PICK losses."
    )
def execute_manual_reminders(supabase, target_week: int, admin_only_uid: str | None = None) -> str:
    smtp_user = os.environ.get("SMTP_USER", "")
    smtp_pass = os.environ.get("SMTP_PASS", "")
    app_url = os.environ.get("APP_URL", "https://railway.app")

    if not smtp_user or not smtp_pass:
        raise RuntimeError("Missing SMTP_USER or SMTP_PASS in Railway environment variables.")

    users = supabase.table("users").select(
        "id, username, email, alert_personal_topic, alert_email, alert_sms, is_admin"
    ).execute().data or []
    user_map = {str(u["id"]): u for u in users}

    default_team, is_saved = resolve_week_default_info(supabase, target_week)
    status_note = (
        f"Explicitly saved for Week {target_week}"
        if is_saved
        else f"Inherited from prior week (not yet saved for Week {target_week})"
    )

    target_admins = [
        u for u in users
        if u.get("is_admin") and (not admin_only_uid or str(u["id"]) == admin_only_uid)
    ]
    admin_sent = 0
    for adm in target_admins:
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
            send_ntfy_push(
                adm_topic,
                f"Admin Check: Week {target_week} Default = {default_team}",
                f"Verify Week {target_week} default team ({default_team} - {status_note}) before Sunday at NOON ET.",
                f"{app_url}/admin",
            )
            admin_sent += 1

    regs = supabase.table("tournament_registrations").select(
        "user_id, game_type, is_enrolled, bracket_status"
    ).eq("is_enrolled", True).neq("bracket_status", "Eliminated").execute().data or []

    week_picks = supabase.table("user_picks").select("user_id, game_type").eq("week", target_week).execute().data or []
    matches = supabase.table("nfl_schedule").select("id").eq("week", target_week).execute().data or []
    required_count = get_required_picks(target_week, len(matches))

    missing_by_user = {}
    for r in regs:
        uid = str(r["user_id"])
        if admin_only_uid and uid != admin_only_uid:
            continue
        gtype = r["game_type"]
        user_week_picks = [p for p in week_picks if str(p["user_id"]) == uid and p["game_type"] == gtype]
        if len(user_week_picks) < required_count:
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
            send_ntfy_push(
                personal_topic,
                f"NFL Loser Pool: Week {target_week} Pick Needed",
                f"Hey {uname}, submit your {pools_label} Pool pick before Sunday at NOON ET to avoid being given your BYE (if available) or the highest favored/ranked team that still has yet to play this week.",
                app_url,
            )
            sent_pushes += 1

    scope = "Test (Admin Only)" if admin_only_uid else "All Missing Players"
    return f"Week {target_week} reminders ({scope}): {admin_sent} admin alerts, {sent_emails} player emails, {sent_pushes} push alerts sent."

def render_admin_view(supabase, user):
    if not is_admin_user(supabase, user):
        ui.label("🔒 Access Denied: Commissioner Privileges Required.").classes("text-red-500 font-bold text-lg")
        return

    current_week = get_current_nfl_week()
    ui.label("Commissioner Control Console").classes("text-2xl font-black mb-3")

    regs = supabase.table("tournament_registrations").select("*").eq("is_enrolled", True).execute().data or []
    main_regs = [r for r in regs if r.get("game_type") == "Main"]
    sc_regs = [r for r in regs if r.get("game_type") == "2nd_Chance"]

    with ui.grid().classes("w-full grid-cols-1 md:grid-cols-2 gap-3 mb-4"):
        with ui.card().classes("p-3 border border-blue-500/40 shadow-none"):
            ui.label("Main Pool Summary").classes("font-extrabold text-sm text-blue-600 dark:text-blue-400")
            m_loser = sum(1 for r in main_regs if r.get("bracket_status") == "Loser Bracket")
            m_winner = sum(1 for r in main_regs if r.get("bracket_status") == "Winner Bracket")
            m_elim = sum(1 for r in main_regs if r.get("bracket_status") == "Eliminated")
            ui.label(f"Loser Bracket: {m_loser}  |  Winner Bracket: {m_winner}  |  Eliminated: {m_elim}").classes("text-xs font-bold mt-1")

        with ui.card().classes("p-3 border border-amber-500/40 shadow-none"):
            ui.label("2nd Chance Summary (Single Elimination)").classes("font-extrabold text-sm text-amber-600 dark:text-amber-400")
            sc_loser = sum(1 for r in sc_regs if r.get("bracket_status") == "Loser Bracket")
            sc_elim = sum(1 for r in sc_regs if r.get("bracket_status") == "Eliminated")
            ui.label(f"Loser Bracket: {sc_loser}  |  Eliminated: {sc_elim}").classes("text-xs font-bold mt-1")

    with ui.tabs().classes("w-full") as admin_tabs:
        t_score = ui.tab("Score Games")
        t_default = ui.tab("Deadline Tools")
        t_roster = ui.tab("Users & Roster")
        t_csv = ui.tab("CSV Import")
        t_masq = ui.tab("Masquerade")

    with ui.tab_panels(admin_tabs, value=t_score).classes("w-full bg-transparent"):
        # ================================================================
        # TAB 1: DUAL-POOL GAME SCORING & BRACKET ADVANCEMENT
        # ================================================================
        with ui.tab_panel(t_score).classes("px-0"):
            week_opts = {w: get_week_label(w) for w in range(1, 23)}
            sel_week = ui.select(week_opts, value=current_week, label="Select Week to Score").classes("w-48 mb-1")
            ui.label("Select the LOSER of each matchup (or tie) and select SO if it was a shutout.").classes("text-xs font-semibold opacity-75 mb-3")

            @ui.refreshable
            def scoring_form():
                w_num = sel_week.value
                matches = supabase.table("nfl_schedule").select("*").eq("week", w_num).execute().data or []
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
                                ui.label(f"{time_label}").classes("text-xs font-semibold opacity-75 w-40 shrink-0")
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
                    losers_set, winners_set, shutouts_set, ties_set = set(), set(), set(), set()

                    for mid, item in snapshot.items():
                        res_val = item["res_val"]
                        so_val = item["so_val"]
                        supabase.table("nfl_schedule").update({
                            "winner": None if res_val == "PENDING" else res_val,
                            "is_shutout": so_val
                        }).eq("id", mid).execute()

                        if res_val == "TIE":
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
                        if gtype == "2nd_Chance":
                            new_status = "Eliminated" if losses >= 1 else "Loser Bracket"
                        else:
                            new_status = "Loser Bracket" if losses == 0 else ("Winner Bracket" if losses == 1 else "Eliminated")
                        supabase.table("tournament_registrations").update({"bracket_status": new_status}).eq("id", r["id"]).execute()

                async def process_dual_pool_scores():
                    save_btn.props("loading")
                    progress_notif = ui.notification(f"⏳ Saving Week {w_num} results & recalculating brackets...", spinner=True, timeout=None, type="info")
                    try:
                        snapshot = {
                            mid: {"away": item["away"], "home": item["home"], "res_val": item["state"]["value"], "so_val": item["chk"].value}
                            for mid, item in controls.items()
                        }
                        await run.io_bound(run_db_scoring_batch, w_num, snapshot)
                        progress_notif.message = f"✅ Week {w_num} scored & brackets updated for BOTH pools!"
                        progress_notif.spinner = False
                        progress_notif.type = "positive"
                        progress_notif.timeout = 4.0
                    except Exception as err:
                        progress_notif.message = f"❌ Error scoring Week {w_num}: {str(err)}"
                        progress_notif.spinner = False
                        progress_notif.type = "negative"
                        progress_notif.timeout = 8.0
                    finally:
                        save_btn.props(remove="loading")

                save_btn = ui.button("Save & Process Both Pools", on_click=process_dual_pool_scores, color="primary").classes("w-full mt-3 font-bold")

            sel_week.on_value_change(lambda: scoring_form.refresh())
            scoring_form()
        # ================================================================
        # TAB 2: USERS, FULL PROFILE EDITOR, DELETE & ROSTER MANAGEMENT
        # ================================================================
        with ui.tab_panel(t_roster).classes("px-0"):
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
                users = sorted(supabase.table("users").select("*").execute().data or [], key=lambda u: (u.get("username") or "").lower())
                pool_regs = supabase.table("tournament_registrations").select("*").eq("game_type", pool_filter.value).execute().data or []
                reg_by_uid = {str(r["user_id"]): r for r in pool_regs}
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
                                    supabase.table("users").update({
                                        "username": ed_user.value.strip(), "email": ed_email.value.strip(),
                                        "first_name": ed_first.value.strip(), "last_name": ed_last.value.strip(),
                                        "cell_phone": ed_phone.value.strip(), "alert_email": ed_a_email.value,
                                        "alert_sms": ed_a_sms.value, "is_admin": ed_admin.value, "notes": ed_notes.value.strip(),
                                    }).eq("id", uid).execute()
                                    dlg.close()
                                    ui.notify("User updated!", type="positive")
                                    roster_list.refresh()
                                ui.button("Save Changes", on_click=save_user_edits, color="primary")
                    dlg.open()

                for u in filtered_users:
                    uid = str(u["id"])
                    r = reg_by_uid.get(uid)
                    with ui.card().classes("w-full p-2.5 mb-2 border border-slate-200 dark:border-slate-700 shadow-none"):
                        with ui.row().classes("w-full items-start justify-between gap-2"):
                            with ui.column().classes("gap-0.5 flex-1 min-w-0"):
                                with ui.row().classes("items-center gap-2"):
                                    ui.label(u.get("username") or "Unknown").classes("text-sm font-extrabold")
                                    if u.get("is_admin"):
                                        ui.badge("ADMIN", color="purple").classes("text-[10px] font-bold")
                                    ui.button("Edit / Delete", on_click=lambda u_obj=u: open_user_editor(u_obj)).props("dense outline size=xs color=primary")
                                ui.label(f"{u.get('email') or 'No email'}").classes("text-xs opacity-80 truncate")
                                ui.label(f"{uid}").classes("text-[10px] font-mono opacity-60 truncate select-all")
                                if u.get("notes"):
                                    ui.label(f"{u['notes']}").classes("text-xs text-amber-700 dark:text-amber-300 italic mt-0.5")

                            if r:
                                with ui.row().classes("items-center gap-2 shrink-0"):
                                    ui.checkbox(
                                        "Enrolled",
                                        value=bool(r.get("is_enrolled")),
                                        on_change=lambda e, rid=r["id"]: (
                                            supabase.table("tournament_registrations").update({"is_enrolled": e.value}).eq("id", rid).execute(),
                                            roster_list.refresh(),
                                        ),
                                    ).props("dense")
                                    ui.checkbox(
                                        "Paid",
                                        value=bool(r.get("is_paid")),
                                        on_change=lambda e, rid=r["id"]: (
                                            supabase.table("tournament_registrations").update({"is_paid": e.value}).eq("id", rid).execute(),
                                            roster_list.refresh(),
                                        ),
                                    ).props("dense")
                                    cur_st = r.get("bracket_status") if r.get("bracket_status") in status_opts else "Loser Bracket"
                                    ui.select(
                                        status_opts,
                                        value=cur_st,
                                        on_change=lambda e, rid=r["id"]: (
                                            supabase.table("tournament_registrations").update({"bracket_status": e.value}).eq("id", rid).execute(),
                                            roster_list.refresh(),
                                        ),
                                    ).props("dense outlined").classes("w-36 text-xs")

            roster_list()

        # ================================================================
        # TAB 3: DEADLINE TOOLS (DEFAULT PICK, LOCK & REMINDERS)
        # ================================================================
        with ui.tab_panel(t_default).classes("px-0"):
            ui.label("Weekly Auto-Pick Default Team").classes("text-base font-extrabold mb-1")
            def_week_opts = {w: get_week_label(w) for w in range(1, 23)}

            with ui.row().classes("w-full items-center gap-3 mb-2 flex-wrap"):
                def_week_sel = ui.select(def_week_opts, value=current_week, label="Select Week").classes("w-48")
                team_sel = ui.select([], label="Default Team").classes("w-40")

                def save_default_team():
                    w_num = def_week_sel.value
                    chosen = (team_sel.value or "").strip().upper()
                    if chosen:
                        supabase.table("default_picks").upsert({
                            "week": w_num,
                            "team": chosen,
                            "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                        }).execute()
                        ui.notify(f"Saved {chosen} as Week {w_num} default pick!", type="positive")
                        default_pick_status.refresh()
                        def_week_sel.on_value_change(lambda: (default_pick_status.refresh(), missing_picks_preview.refresh()))

                ui.button("Save Week Default", on_click=save_default_team, color="primary").classes("font-bold")

            @ui.refreshable
            def default_pick_status():
                w_num = def_week_sel.value
                all_defs = supabase.table("default_picks").select("*").order("week", desc=False).execute().data or []
                def_map = {int(d["week"]): d["team"].upper() for d in all_defs}
                saved_exact = def_map.get(w_num)
                prior_weeks = [w for w in sorted(def_map.keys(), reverse=True) if w < w_num]
                inherited = def_map[prior_weeks] if (not saved_exact and prior_weeks) else None
                active_team = saved_exact or inherited or "KC"

                wk_matches = supabase.table("nfl_schedule").select("away_team, home_team").eq("week", w_num).execute().data or []
                teams_set = {t.upper() for m in wk_matches for t in (m.get("away_team"), m.get("home_team")) if t} or {"KC"}
                sorted_teams = sorted(teams_set | {active_team})
                team_sel.options = sorted_teams
                team_sel.value = active_team
                team_sel.update()

                if saved_exact:
                    ui.label(f"✅ Explicitly saved for Week {w_num}: {saved_exact}").classes("text-xs font-bold text-emerald-600 dark:text-emerald-400 mb-2")
                elif inherited:
                    ui.label(f"⚠️ Not yet saved for Week {w_num} — will auto-inherit prior default: {inherited}").classes("text-xs font-bold text-amber-600 dark:text-amber-400 mb-2")
                else:
                    ui.label(f"⚠️ No default saved yet for Week {w_num}.").classes("text-xs font-bold text-red-500 mb-2")

            def_week_sel.on_value_change(lambda: default_pick_status.refresh())
            default_pick_status()
            ui.separator().classes("my-5")
            with ui.card().classes("w-full p-4 border border-amber-500/40 shadow-none"):
                ui.label("🔒 Manual Deadline Lock & Reminder Triggers").classes("text-base font-extrabold mb-2")

                def open_lock_confirm():
                    w_target = def_week_sel.value
                    with ui.dialog() as lock_dlg, ui.card().classes("p-5 max-w-md"):
                        ui.label(f"Run Deadline Lock for {get_week_label(w_target)}?").classes("text-lg font-black")
                        with ui.row().classes("w-full justify-end gap-2 mt-3"):
                            ui.button("Cancel", on_click=lock_dlg.close).props("flat")

                            async def confirm_run_lock():
                                lock_dlg.close()
                                lock_btn.props("loading")
                                notif = ui.notification(f"⏳ Running lock for {get_week_label(w_target)}...", spinner=True, timeout=None, type="info")
                                try:
                                    msg = await run.io_bound(execute_manual_deadline_lock, supabase, w_target)
                                    notif.message, notif.spinner, notif.type, notif.timeout = f"✅ {msg}", False, "positive", 6.0
                                    default_pick_status.refresh()
                                    missing_picks_preview.refresh()
                                except Exception as err:
                                    notif.message, notif.spinner, notif.type, notif.timeout = f"❌ Lock failed: {err}", False, "negative", 8.0
                                finally:
                                    lock_btn.props(remove="loading")

                            ui.button("Confirm & Lock Week", on_click=confirm_run_lock, color="amber-8").classes("font-bold text-white")
                    lock_dlg.open()

                def open_reminder_confirm():
                    w_target = def_week_sel.value
                    with ui.dialog() as rem_dlg, ui.card().classes("p-5 max-w-md"):
                        ui.label(f"Send Reminders for {get_week_label(w_target)}?").classes("text-lg font-black")

                        async def trigger_reminders(only_me: bool):
                            rem_dlg.close()
                            rem_btn.props("loading")
                            notif = ui.notification(f"⏳ Sending Week {w_target} reminders...", spinner=True, timeout=None, type="info")
                            try:
                                msg = await run.io_bound(execute_manual_reminders, supabase, w_target, str(user.id) if only_me else None)
                                notif.message = f"✅ {msg}"
                                notif.spinner = False
                                notif.type = "positive"
                                notif.timeout = 6.0
                            except Exception as err:
                                notif.message = f"❌ Reminder error: {err}"
                                notif.spinner = False
                                notif.type = "negative"
                                notif.timeout = 8.0
                            finally:
                                rem_btn.props(remove="loading")

                        with ui.row().classes("w-full justify-end gap-2 mt-3 flex-wrap"):
                            ui.button("Cancel", on_click=rem_dlg.close).props("flat")
                            ui.button("Test (Only Me)", on_click=lambda: trigger_reminders(True), color="primary").props("outline")
                            ui.button("Send to All Missing", on_click=lambda: trigger_reminders(False), color="primary").classes("font-bold")
                    rem_dlg.open()

                with ui.row().classes("items-center gap-3 flex-wrap"):
                    lock_btn = ui.button("Run Deadline Lock Now", icon="lock_clock", on_click=open_lock_confirm, color="amber-8").classes("font-bold text-white")
                    rem_btn = ui.button("Send Reminders Now", icon="notifications_active", on_click=open_reminder_confirm, color="primary").classes("font-bold")
                    
            ui.separator().classes("my-5")

            # --- MISSING PICKS & AUTO-ASSIGN PREVIEW (MAIN LEFT | 2ND CHANCE RIGHT) ---
            @ui.refreshable
            def missing_picks_preview():
                w_target = def_week_sel.value
                users_rows = supabase.table("users").select("id, username, first_name, last_name").execute().data or []
                user_name_map = {
                    str(u["id"]): f"{u.get('username') or 'Unknown'} ({u.get('first_name') or ''} {u.get('last_name') or ''})".strip()
                    for u in users_rows
                }

                active_regs = (
                    supabase.table("tournament_registrations")
                    .select("user_id, game_type, is_enrolled, bracket_status")
                    .eq("is_enrolled", True)
                    .neq("bracket_status", "Eliminated")
                    .execute()
                    .data or []
                )
                all_picks = supabase.table("user_picks").select("user_id, game_type, week, team_picked").execute().data or []
                matches = supabase.table("nfl_schedule").select("id").eq("week", w_target).execute().data or []
                req_count = get_required_picks(w_target, len(matches))

                active_default, _ = resolve_week_default_info(supabase, w_target)

                def get_pool_missing(pool_name: str) -> list[dict]:
                    pool_regs = [r for r in active_regs if r.get("game_type") == pool_name]
                    missing_list = []
                    for r in pool_regs:
                        uid = str(r["user_id"])
                        u_picks = [p for p in all_picks if str(p["user_id"]) == uid and p["game_type"] == pool_name]
                        wk_picks = [p for p in u_picks if p["week"] == w_target]
                        missing_slots = req_count - len(wk_picks)
                        if missing_slots <= 0:
                            continue

                        bye_used = any((p.get("team_picked") or "").upper().strip() == "BYE" for p in u_picks)
                        if not bye_used and missing_slots == 1:
                            outcome = "BYE Available"
                            is_bye = True
                        elif not bye_used and missing_slots > 1:
                            outcome = f"1 BYE + {missing_slots - 1} Default ({active_default})"
                            is_bye = True
                        else:
                            label_prefix = f"{missing_slots}x " if missing_slots > 1 else ""
                            outcome = f"{label_prefix}Default ({active_default})"
                            is_bye = False

                        missing_list.append({
                            "name": user_name_map.get(uid, uid),
                            "outcome": outcome,
                            "is_bye": is_bye,
                        })
                    return sorted(missing_list, key=lambda x: x["name"].lower())

                main_missing = get_pool_missing("Main")
                sc_missing = get_pool_missing("2nd_Chance")

                ui.label(f"Missing Picks & Auto-Assign Preview ({get_week_label(w_target)})").classes("text-base font-extrabold mb-2")

                with ui.grid().classes("w-full grid-cols-1 md:grid-cols-2 gap-4"):
                    for title, items, accent in [
                        ("Main Pool", main_missing, "border-blue-500/40"),
                        ("2nd Chance Pool", sc_missing, "border-amber-500/40"),
                    ]:
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
                                            ui.badge(
                                                entry["outcome"],
                                                color="green" if entry["is_bye"] else "amber-8",
                                            ).classes("text-[10px] font-bold shrink-0")

            missing_picks_preview()

        # ================================================================
        # TAB 4: CSV HISTORICAL PICK UPLOADER (EMAIL-BASED)
        # ================================================================
        with ui.tab_panel(t_csv).classes("px-0"):
            ui.label("Upload Historical Picks CSV").classes("text-base font-extrabold mb-1")
            ui.label("Required columns: game_type, email, week, team_picked, pick_state").classes("text-xs opacity-75 mb-3")

            status_lbl = ui.label("").classes("text-xs font-bold mt-2")

            async def handle_csv_upload(e):
                status_lbl.text = "⏳ Processing CSV file..."
                try:
                    # Support both NiceGUI file upload event signatures
                    if hasattr(e, "file") and hasattr(e.file, "read"):
                        raw_bytes = await e.file.read()
                    elif hasattr(e, "content"):
                        res = e.content.read()
                        raw_bytes = await res if hasattr(res, "__await__") else res
                    else:
                        raise ValueError("Could not read uploaded file stream.")

                    text = raw_bytes.decode("utf-8-sig")
                    reader = csv.DictReader(io.StringIO(text))

                    # Normalize headers to lowercase/trimmed so minor casing differences work
                    if reader.fieldnames:
                        reader.fieldnames = [h.strip().lower() for h in reader.fieldnames]

                    users_rows = supabase.table("users").select("id, email").execute().data or []
                    email_to_id = {u["email"].strip().lower(): u["id"] for u in users_rows if u.get("email")}

                    imported, skipped = 0, 0
                    skipped_emails = []

                    for row in reader:
                        gtype_raw = (row.get("game_type") or "Main").strip().lower()
                        gtype = "2nd_Chance" if gtype_raw in ["2nd_chance", "2nd chance", "2ndchance"] else "Main"

                        email_val = (row.get("email") or "").strip().lower()
                        uid = email_to_id.get(email_val)
                        if not uid:
                            skipped += 1
                            if email_val:
                                skipped_emails.append(email_val)
                            continue

                        wk = int(str(row["week"]).strip())
                        team = str(row["team_picked"]).strip().upper()
                        state = (row.get("pick_state") or "Finalized").strip()

                        supabase.table("user_picks").delete().eq("user_id", uid).eq("game_type", gtype).eq("week", wk).eq("team_picked", team).execute()
                        supabase.table("user_picks").insert({
                            "user_id": uid,
                            "game_type": gtype,
                            "week": wk,
                            "team_picked": team,
                            "pick_state": state,
                        }).execute()
                        imported += 1

                    msg = f"✅ Imported {imported} picks ({skipped} skipped)."
                    if skipped_emails:
                        msg += f" Unmatched emails: {', '.join(sorted(set(skipped_emails))[:5])}"
                    status_lbl.text = msg
                    ui.notify(msg, type="positive" if imported > 0 else "warning", timeout=8000)
                except Exception as err:
                    err_msg = f"❌ CSV Import Error: {str(err)}"
                    status_lbl.text = err_msg
                    ui.notify(err_msg, type="negative", timeout=10000)

            ui.upload(on_upload=handle_csv_upload, auto_upload=True).props("accept=.csv").classes("w-full max-w-md")

        # ================================================================
        # TAB 5: MASQUERADE
        # ================================================================
        with ui.tab_panel(t_masq).classes("px-0"):
            all_users = sorted(
                supabase.table("users").select("id, username, first_name, last_name").execute().data or [],
                key=lambda u: (u.get("username") or "").lower(),
            )
            user_choices = {
                str(u["id"]): f"{u.get('username') or 'Unknown'} ({u.get('first_name') or ''} {u.get('last_name') or ''})".strip()
                for u in all_users
                if str(u["id"]) != str(user.id)
            }
            target_sel = ui.select(user_choices, label="Select Player to Impersonate").classes("w-full max-w-md mb-3")

            def start_masquerade():
                if target_sel.value:
                    app.storage.user["masquerade_uid"] = target_sel.value
                    app.storage.user["masquerade_name"] = user_choices[target_sel.value]
                    ui.navigate.to("/")

            ui.button("Assume Selected Identity", icon="switch_account", on_click=start_masquerade, color="purple").classes("font-bold")

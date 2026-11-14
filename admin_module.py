import csv
import io
from nicegui import ui, app, run
from picks_module import get_current_nfl_week, get_week_label, get_logo_url
import datetime
from zoneinfo import ZoneInfo

ET_ZONE = ZoneInfo("America/New_York")

CARRIER_OPTIONS = [
    "None / Do Not Use", "AT&T", "Verizon", "T-Mobile", "Sprint",
    "Boost Mobile", "Cricket Wireless", "MetroPCS", "US Cellular",
    "Virgin Mobile", "Google Fi", "Xfinity Mobile", "Visible", "Mint Mobile"
]

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

def render_admin_view(supabase, user):
    if not is_admin_user(supabase, user):
        ui.label("🔒 Access Denied: Commissioner Privileges Required.").classes("text-red-500 font-bold text-lg")
        return

    current_week = get_current_nfl_week()
    ui.label("Commissioner Control Console").classes("text-2xl font-black mb-3")

    # --- POOL SUMMARY METRICS ---
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
            ui.label("2nd Chance Summary").classes("font-extrabold text-sm text-amber-600 dark:text-amber-400")
            sc_loser = sum(1 for r in sc_regs if r.get("bracket_status") == "Loser Bracket")
            sc_elim = sum(1 for r in sc_regs if r.get("bracket_status") == "Eliminated")
            ui.label(f"Loser Bracket: {sc_loser}  |  Eliminated: {sc_elim}").classes("text-xs font-bold mt-1")

    with ui.tabs().classes("w-full") as admin_tabs:
        t_score = ui.tab("Score Games")
        t_roster = ui.tab("Player Management")
        t_csv = ui.tab("CSV Import")
        t_masq = ui.tab("Masquerade")

    with ui.tab_panels(admin_tabs, value=t_score).classes("w-full bg-transparent"):
        # ================================================================
        # TAB 1: DUAL-POOL GAME SCORING & BRACKET ADVANCEMENT
        # ================================================================
        with ui.tab_panel(t_score).classes("px-0"):
            week_opts = {w: get_week_label(w) for w in range(1, 23)}
            sel_week = ui.select(week_opts, value=current_week, label="Select Week to Score").classes("w-48 mb-1")
            ui.label("Select the LOSER of each matchup (or tie) and select SO if it was a shutout.").classes(
                "text-xs font-semibold opacity-75 mb-3"
            )

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

                                # Day, Short Date, & Time placed right next to the TIE button
                                ui.label(f"{time_label}").classes("text-xs font-semibold opacity-75 ml-1")

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
                    progress_notif = ui.notification(
                        f"⏳ Saving Week {w_num} results & recalculating Main and 2nd Chance brackets...",
                        spinner=True,
                        timeout=None,
                        type="info"
                    )
                    try:
                        # Capture current radio/checkbox values safely on the UI thread
                        snapshot = {
                            mid: {"away": item["away"], "home": item["home"], "res_val": item["state"]["value"], "so_val": item["chk"].value}
                            for mid, item in controls.items()
                        }
                        await run.io_bound(run_db_scoring_batch, w_num, snapshot)
                        progress_notif.message = f"Week {w_num} scored & brackets updated for BOTH pools!"
                        progress_notif.spinner = False
                        progress_notif.type = "positive"
                        progress_notif.timeout = 4.0
                    except Exception as err:
                        progress_notif.message = f"Error scoring Week {w_num}: {str(err)}"
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
                bracket_filter = ui.select(
                    ["All", "Loser Bracket", "Winner Bracket", "Eliminated"],
                    value="All",
                    label="Bracket Status"
                ).classes("w-44")
                search_input = ui.input(
                    label="Search Name/Username/Email/ID/Notes",
                    placeholder="Type to filter..."
                ).props("clearable").classes("flex-1 min-w-[200px]")

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
                users = supabase.table("users").select("*").execute().data or []
                users = sorted(users, key=lambda u: (u.get("username") or "").lower())
                pool_regs = supabase.table("tournament_registrations").select("*").eq("game_type", pool_filter.value).execute().data or []
                reg_by_uid = {str(r["user_id"]): r for r in pool_regs}

                status_opts = ["Loser Bracket", "Eliminated"] if pool_filter.value == "2nd_Chance" else ["Loser Bracket", "Winner Bracket", "Eliminated"]
                query_txt = (search_input.value or "").strip().lower()

                # Apply the 3 dropdown filters + live text search
                filtered_users = []
                for u in users:
                    r = reg_by_uid.get(str(u["id"]))
                    is_enr = bool(r.get("is_enrolled")) if r else False
                    is_pd = bool(r.get("is_paid")) if r else False
                    b_stat = (r.get("bracket_status") or "Loser Bracket") if r else "Not Enrolled"

                    if enroll_filter.value == "Enrolled" and not is_enr:
                        continue
                    if enroll_filter.value == "Not Enrolled" and is_enr:
                        continue
                    if paid_filter.value == "Paid" and not is_pd:
                        continue
                    if paid_filter.value == "Not Paid" and is_pd:
                        continue
                    if bracket_filter.value != "All":
                        if not r or b_stat != bracket_filter.value:
                            continue

                    if query_txt:
                        searchable_blob = " ".join([
                            str(u.get("id") or ""),
                            u.get("username") or "",
                            u.get("first_name") or "",
                            u.get("last_name") or "",
                            u.get("email") or "",
                            u.get("notes") or "",
                        ]).lower()
                        if query_txt not in searchable_blob:
                            continue

                    filtered_users.append(u)

                ui.label(f"Showing {len(filtered_users)} of {len(users)} users").classes("text-xs font-bold opacity-70 mb-2")

                def open_user_editor(u_row: dict):
                    uid = str(u_row["id"])
                    with ui.dialog() as dlg, ui.card().classes("w-full max-w-lg p-5"):
                        ui.label(f"Edit User: {u_row.get('username') or 'Player'}").classes("text-lg font-black")
                        ui.label(f"User ID: {uid}").classes("text-[11px] font-mono opacity-60 mb-3 select-all")

                        with ui.grid().classes("w-full grid-cols-1 md:grid-cols-2 gap-2"):
                            ed_user = ui.input("Username", value=u_row.get("username") or "").classes("w-full")
                            ed_email = ui.input("Email", value=u_row.get("email") or "").classes("w-full")
                            ed_first = ui.input("First Name", value=u_row.get("first_name") or "").classes("w-full")
                            ed_last = ui.input("Last Name", value=u_row.get("last_name") or "").classes("w-full")
                            ed_phone = ui.input("Cell Phone", value=u_row.get("cell_phone") or "").classes("w-full")
                            cur_car = u_row.get("cell_carrier") if u_row.get("cell_carrier") in CARRIER_OPTIONS else "None / Do Not Use"
                            ed_carrier = ui.select(CARRIER_OPTIONS, value=cur_car, label="Cell Carrier").classes("w-full")

                        with ui.row().classes("w-full gap-4 mt-2"):
                            ed_a_email = ui.checkbox("Alert Email", value=bool(u_row.get("alert_email", True)))
                            ed_a_sms = ui.checkbox("Alert SMS", value=bool(u_row.get("alert_sms", False)))
                            ed_admin = ui.checkbox("Is Admin", value=bool(u_row.get("is_admin", False)))

                        ed_notes = ui.textarea("Commissioner Notes", value=u_row.get("notes") or "").classes("w-full mt-2").props("rows=2")

                        with ui.row().classes("w-full justify-between items-center mt-4 pt-3 border-t border-slate-200 dark:border-slate-700"):
                            def confirm_delete_user():
                                with ui.dialog() as del_dlg, ui.card().classes("p-4"):
                                    ui.label(f"Permanently delete {u_row.get('username')}?").classes("font-bold text-red-600")
                                    ui.label("This removes their user profile, tournament registrations, and all picks.").classes("text-xs opacity-80 my-1")
                                    with ui.row().classes("w-full justify-end gap-2 mt-3"):
                                        ui.button("Cancel", on_click=del_dlg.close).props("flat")
                                        def execute_delete():
                                            try:
                                                supabase.table("user_picks").delete().eq("user_id", uid).execute()
                                                supabase.table("tournament_registrations").delete().eq("user_id", uid).execute()
                                                supabase.table("users").delete().eq("id", uid).execute()
                                                del_dlg.close()
                                                dlg.close()
                                                ui.notify("User & associated records deleted.", type="warning")
                                                roster_list.refresh()
                                            except Exception as err:
                                                ui.notify(f"Delete error: {str(err)}", type="negative")
                                        ui.button("Confirm Delete", on_click=execute_delete, color="red")
                                del_dlg.open()

                            ui.button("Delete User", on_click=confirm_delete_user, color="red").props("outline size=sm")

                            with ui.row().classes("gap-2"):
                                ui.button("Cancel", on_click=dlg.close).props("flat")
                                def save_user_edits():
                                    try:
                                        supabase.table("users").update({
                                            "username": ed_user.value.strip(),
                                            "email": ed_email.value.strip(),
                                            "first_name": ed_first.value.strip(),
                                            "last_name": ed_last.value.strip(),
                                            "cell_phone": ed_phone.value.strip(),
                                            "cell_carrier": ed_carrier.value,
                                            "alert_email": ed_a_email.value,
                                            "alert_sms": ed_a_sms.value,
                                            "is_admin": ed_admin.value,
                                            "notes": ed_notes.value.strip(),
                                        }).eq("id", uid).execute()
                                        dlg.close()
                                        ui.notify("User updated!", type="positive")
                                        roster_list.refresh()
                                    except Exception as err:
                                        ui.notify(f"Update error: {str(err)}", type="negative")
                                ui.button("Save Changes", on_click=save_user_edits, color="primary")
                    dlg.open()

                for u in filtered_users:
                    uid = str(u["id"])
                    uname = u.get("username") or "Unknown"
                    uemail = u.get("email") or "No email"
                    unotes = u.get("notes") or ""
                    uadmin = bool(u.get("is_admin", False))
                    r = reg_by_uid.get(uid)

                    with ui.card().classes("w-full p-2.5 mb-2 border border-slate-200 dark:border-slate-700 shadow-none"):
                        with ui.row().classes("w-full items-start justify-between gap-2"):
                            with ui.column().classes("gap-0.5 flex-1 min-w-0"):
                                with ui.row().classes("items-center gap-2"):
                                    ui.label(uname).classes("text-sm font-extrabold")
                                    if uadmin:
                                        ui.badge("ADMIN", color="purple").classes("text-[10px] font-bold")
                                    ui.button("Edit / Delete", on_click=lambda u_obj=u: open_user_editor(u_obj)).props("dense outline size=xs color=primary")

                                ui.label(f"Email: {uemail}").classes("text-xs opacity-80 truncate")
                                ui.label(f"ID: {uid}").classes("text-[10px] font-mono opacity-60 truncate select-all")
                                if unotes:
                                    ui.label(f"Notes: {unotes}").classes("text-xs text-amber-700 dark:text-amber-300 italic mt-0.5")

                            if r:
                                with ui.row().classes("items-center gap-2 shrink-0"):
                                    ui.checkbox("Enrolled", value=bool(r.get("is_enrolled")),
                                                on_change=lambda e, rid=r["id"]: (supabase.table("tournament_registrations").update({"is_enrolled": e.value}).eq("id", rid).execute(), roster_list.refresh())).props("dense")
                                    ui.checkbox("Paid", value=bool(r.get("is_paid")),
                                                on_change=lambda e, rid=r["id"]: (supabase.table("tournament_registrations").update({"is_paid": e.value}).eq("id", rid).execute(), roster_list.refresh())).props("dense")
                                    cur_st = r.get("bracket_status") if r.get("bracket_status") in status_opts else "Loser Bracket"
                                    ui.select(status_opts, value=cur_st,
                                              on_change=lambda e, rid=r["id"]: (supabase.table("tournament_registrations").update({"bracket_status": e.value}).eq("id", rid).execute(), roster_list.refresh())).props("dense outlined").classes("w-36 text-xs")

            roster_list()

        # ================================================================
        # TAB 3: CSV HISTORICAL PICK UPLOADER (Accounts for game_type)
        # ================================================================
        with ui.tab_panel(t_csv).classes("px-0"):
            ui.label("Upload Picks CSV").classes("text-base font-extrabold mb-1")
            ui.label("Required columns: game_type, username, week, team_picked, pick_state").classes("text-xs opacity-75 mb-3")

            def handle_csv_upload(e):
                try:
                    raw_bytes = e.content.read()
                    text = raw_bytes.decode("utf-8-sig")
                    reader = csv.DictReader(io.StringIO(text))

                    users = supabase.table("users").select("id, username").execute().data or []
                    name_to_id = {u["username"].strip().lower(): u["id"] for u in users if u.get("username")}

                    imported, skipped = 0, 0
                    for row in reader:
                        gtype_raw = (row.get("game_type") or "Main").strip()
                        gtype = "2nd_Chance" if gtype_raw.lower() in ["2nd_chance", "2nd chance", "2ndchance"] else "Main"
                        uname = (row.get("username") or "").strip().lower()
                        uid = name_to_id.get(uname)
                        if not uid:
                            skipped += 1
                            continue

                        wk = int(row["week"])
                        team = row["team_picked"].strip().upper()
                        state = (row.get("pick_state") or "Finalized").strip()

                        supabase.table("user_picks").delete().eq("user_id", uid).eq("game_type", gtype).eq("week", wk).eq("team_picked", team).execute()
                        supabase.table("user_picks").insert({
                            "user_id": uid, "game_type": gtype, "week": wk,
                            "team_picked": team, "pick_state": state
                        }).execute()
                        imported += 1

                    ui.notify(f"Imported {imported} picks ({skipped} skipped).", type="positive")
                except Exception as err:
                    ui.notify(f"CSV Error: {str(err)}", type="negative", timeout=8000)

            ui.upload(on_upload=handle_csv_upload, auto_upload=True).props("accept=.csv").classes("w-full max-w-md")

        # ================================================================
        # TAB 4: DEVELOPER MASQUERADE MODE
        # ================================================================
        with ui.tab_panel(t_masq).classes("px-0"):
            ui.label("Assume Player Identity").classes("text-base font-extrabold mb-1")
            ui.label("Test picks, brackets, and notifications as any player without needing their password.").classes("text-xs opacity-75 mb-3")

            all_users = supabase.table("users").select("id, username, first_name, last_name, email").execute().data or []
            all_users = sorted(all_users, key=lambda u: (u.get("username") or "").lower())

            user_choices = {
                str(u["id"]): f"{u.get('username') or 'Unknown'} ({u.get('first_name') or ''} {u.get('last_name') or ''})".strip()
                for u in all_users
                if str(u["id"]) != str(user.id)
            }

            if not user_choices:
                ui.label("No other player accounts found.").classes("text-sm opacity-70")
            else:
                target_sel = ui.select(user_choices, label="Select Player to Impersonate").classes("w-full max-w-md mb-3")

                def start_masquerade():
                    chosen_uid = target_sel.value
                    if not chosen_uid:
                        ui.notify("Select a player first.", type="warning")
                        return
                    app.storage.user["masquerade_uid"] = chosen_uid
                    app.storage.user["masquerade_name"] = user_choices[chosen_uid]
                    ui.notify(f"Switched to {user_choices[chosen_uid]}!", type="positive")
                    ui.navigate.to("/")

                ui.button("Assume Selected Identity", icon="switch_account", on_click=start_masquerade, color="purple").classes("font-bold")

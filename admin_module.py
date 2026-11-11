import csv
import io
from nicegui import ui
from picks_module import get_current_nfl_week, get_week_label

# Replace with your exact Supabase User UUID string
MASTER_ADMIN_UID = "3f3a74a6-3725-4a3b-abda-015e73cb6f4b"

def is_admin_user(user) -> bool:
    if not user:
        return False
    return str(user.id).strip() == MASTER_ADMIN_UID

def render_admin_view(supabase, user):
    if not is_admin_user(user):
        ui.label("🔒 Access Denied: Commissioner Privileges Required.").classes("text-red-500 font-bold text-lg")
        return

    current_week = get_current_nfl_week()
    ui.label("🛠️ Commissioner Control Console").classes("text-2xl font-black mb-3")

    # --- POOL SUMMARY METRICS (Main vs. 2nd Chance) ---
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
        t_roster = ui.tab("League Roster & Payments")
        t_csv = ui.tab("CSV Import")

    with ui.tab_panels(admin_tabs, value=t_score).classes("w-full bg-transparent"):
        # ================================================================
        # TAB 1: DUAL-POOL GAME SCORING & BRACKET ADVANCEMENT
        # ================================================================
        with ui.tab_panel(t_score).classes("px-0"):
            week_opts = {w: get_week_label(w) for w in range(1, 23)}
            sel_week = ui.select(week_opts, value=current_week, label="Select Week to Score").classes("w-48 mb-3")

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

                    with ui.card().classes("w-full p-2.5 mb-2 border border-slate-300 dark:border-slate-700 shadow-none"):
                        ui.label(f"{away} @ {home}").classes("text-xs font-extrabold mb-1")
                        with ui.row().classes("w-full items-center justify-between gap-2 no-wrap"):
                            rad = ui.radio(["PENDING", away, home, "TIE"], value=db_loser if db_loser in ["PENDING", away, home, "TIE"] else "PENDING").props("inline dense").classes("text-xs")
                            chk = ui.checkbox("🎯 SO", value=db_so).props("dense").classes("text-xs font-bold shrink-0")
                            controls[mid] = {"away": away, "home": home, "rad": rad, "chk": chk}

                def process_dual_pool_scores():
                    losers_set, winners_set, shutouts_set, ties_set = set(), set(), set(), set()

                    for mid, item in controls.items():
                        res_val = item["rad"].value
                        so_val = item["chk"].value
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

                    # Grade picks across BOTH Main and 2nd_Chance simultaneously
                    week_picks = supabase.table("user_picks").select("*").eq("week", w_num).execute().data or []
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

                    # Recalculate bracket statuses for BOTH pools from full season history
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

                    ui.notify(f"Week {w_num} scored & brackets updated for BOTH pools!", type="positive")

                ui.button("Save & Process Both Pools", on_click=process_dual_pool_scores, color="primary").classes("w-full mt-3 font-bold")

            sel_week.on_value_change(lambda: scoring_form.refresh())
            scoring_form()

        # ================================================================
        # TAB 2: ROSTER, ENROLLMENT & PAYMENT OVERRIDES
        # ================================================================
        with ui.tab_panel(t_roster).classes("px-0"):
            pool_filter = ui.select(["Main", "2nd_Chance"], value="Main", label="Manage Pool Roster").classes("w-48 mb-3")

            @ui.refreshable
            def roster_list():
                users = supabase.table("users").select("id, username, first_name, last_name").execute().data or []
                umap = {u["id"]: u for u in users}
                pool_regs = supabase.table("tournament_registrations").select("*").eq("game_type", pool_filter.value).execute().data or []
                pool_regs = sorted(pool_regs, key=lambda r: (umap.get(r["user_id"], {}).get("username") or "").lower())

                status_opts = ["Loser Bracket", "Eliminated"] if pool_filter.value == "2nd_Chance" else ["Loser Bracket", "Winner Bracket", "Eliminated"]

                for r in pool_regs:
                    u = umap.get(r["user_id"], {})
                    uname = u.get("username") or "Unknown"
                    fname = f"{u.get('first_name') or ''} {u.get('last_name') or ''}".strip()

                    with ui.row().classes("w-full items-center justify-between p-2 border-b border-slate-200 dark:border-slate-700 gap-2"):
                        with ui.column().classes("gap-0"):
                            ui.label(uname).classes("text-xs font-extrabold")
                            ui.label(fname).classes("text-[10px] opacity-70")

                        with ui.row().classes("items-center gap-2"):
                            enr_chk = ui.checkbox("Enrolled", value=bool(r.get("is_enrolled")),
                                                  on_change=lambda e, rid=r["id"]: supabase.table("tournament_registrations").update({"is_enrolled": e.value}).eq("id", rid).execute()).props("dense")
                            paid_chk = ui.checkbox("Paid", value=bool(r.get("is_paid")),
                                                   on_change=lambda e, rid=r["id"]: supabase.table("tournament_registrations").update({"is_paid": e.value}).eq("id", rid).execute()).props("dense")
                            cur_st = r.get("bracket_status") if r.get("bracket_status") in status_opts else "Loser Bracket"
                            ui.select(status_opts, value=cur_st,
                                      on_change=lambda e, rid=r["id"]: supabase.table("tournament_registrations").update({"bracket_status": e.value}).eq("id", rid).execute()).props("dense outlined").classes("w-36 text-xs")

            pool_filter.on_value_change(lambda: roster_list.refresh())
            roster_list()

        # ================================================================
        # TAB 3: CSV HISTORICAL PICK UPLOADER (Accounts for game_type)
        # ================================================================
        with ui.tab_panel(t_csv).classes("px-0"):
            ui.label("Upload Historical Picks CSV").classes("text-base font-extrabold mb-1")
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

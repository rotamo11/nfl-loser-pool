import os
import datetime
from zoneinfo import ZoneInfo
from supabase import create_client, Client

ET_ZONE = ZoneInfo("America/New_York")
SEASON_START_WEDNESDAY = datetime.datetime(2026, 9, 9, 0, 0, 0, tzinfo=ET_ZONE)

def get_current_nfl_week() -> int:
    now_et = datetime.datetime.now(ET_ZONE)
    if now_et < SEASON_START_WEDNESDAY:
        return 1
    return min(22, ((now_et - SEASON_START_WEDNESDAY).days // 7) + 1)

def get_required_picks(week: int, matches_count: int) -> int:
    if week <= 14:
        return 1
    if week <= 18:
        return 2
    return max(1, matches_count)

def get_or_carryover_default_team(supabase: Client, current_week: int) -> str | None:
    """Fetches current_week's default team, or carries over & saves the previous week's default."""
    rows = supabase.table("default_picks").select("week, team").order("week", desc=False).execute().data or []
    def_map = {int(r["week"]): r["team"].upper().strip() for r in rows if r.get("team")}

    if current_week in def_map:
        return def_map[current_week]

    prior_weeks = [w for w in sorted(def_map.keys(), reverse=True) if w < current_week]
    if prior_weeks:
        inherited_team = def_map[prior_weeks]
        supabase.table("default_picks").upsert({
            "week": current_week,
            "team": inherited_team,
            "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat()
        }).execute()
        print(f"Carried over prior default team '{inherited_team}' and saved for Week {current_week}.")
        return inherited_team

    return None

def main():
    now_et = datetime.datetime.now(ET_ZONE)
    if os.environ.get("GITHUB_EVENT_NAME") == "schedule" and now_et.hour != 12:
        print(f"Skipping off-timezone UTC cron slot (Current ET: {now_et.strftime('%I:%M %p %Z')}).")
        return

    supabase_url = os.environ["SUPABASE_URL"]
    supabase_key = os.environ.get("SUPABASE_SERVICE_KEY") or os.environ["SUPABASE_KEY"]
    supabase: Client = create_client(supabase_url, supabase_key)

    current_week = get_current_nfl_week()

    # 1. Upgrade all 'Confirmed' picks for the current week to 'Finalized'
    confirmed_picks = (
        supabase.table("user_picks")
        .select("id")
        .eq("week", current_week)
        .eq("pick_state", "Confirmed")
        .execute()
        .data or []
    )
    for p in confirmed_picks:
        supabase.table("user_picks").update({"pick_state": "Finalized"}).eq("id", p["id"]).execute()

    # 2. Fetch active players, full pick history, schedule, and week default team
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

    matches = supabase.table("nfl_schedule").select("id").eq("week", current_week).execute().data or []
    required_count = get_required_picks(current_week, len(matches))
    default_team = get_or_carryover_default_team(supabase, current_week)

    auto_byes, auto_defaults, no_picks = 0, 0, 0

    for r in regs:
        uid = str(r["user_id"])
        gtype = r["game_type"]

        user_pool_picks = [p for p in all_picks if str(p["user_id"]) == uid and p["game_type"] == gtype]
        current_week_picks = [p for p in user_pool_picks if p["week"] == current_week]
        missing_slots = required_count - len(current_week_picks)

        if missing_slots <= 0:
            continue

        bye_already_used = any((p.get("team_picked") or "").upper().strip() == "BYE" for p in user_pool_picks)

        for _ in range(missing_slots):
            # Priority 1: Award unused Season BYE (1 per pool)
            if not bye_already_used:
                new_row = {
                    "user_id": uid,
                    "game_type": gtype,
                    "week": current_week,
                    "team_picked": "BYE",
                    "pick_state": "Finalized",
                }
                supabase.table("user_picks").insert(new_row).execute()
                user_pool_picks.append(new_row)
                all_picks.append(new_row)
                bye_already_used = True
                auto_byes += 1
                continue

            # Priority 2: Assign the Commissioner's configured default team for the week
            if default_team:
                new_row = {
                    "user_id": uid,
                    "game_type": gtype,
                    "week": current_week,
                    "team_picked": default_team,
                    "pick_state": "Finalized",
                }
                supabase.table("user_picks").insert(new_row).execute()
                user_pool_picks.append(new_row)
                all_picks.append(new_row)
                auto_defaults += 1
            else:
                new_row = {
                    "user_id": uid,
                    "game_type": gtype,
                    "week": current_week,
                    "team_picked": "NO_PICK",
                    "pick_state": "Incorrect",
                }
                supabase.table("user_picks").insert(new_row).execute()
                user_pool_picks.append(new_row)
                all_picks.append(new_row)
                no_picks += 1

    # 3. Recalculate bracket_status across BOTH pools based on total 'Incorrect' picks
    for r in regs:
        uid = str(r["user_id"])
        gtype = r["game_type"]
        losses = sum(
            1 for p in all_picks
            if str(p["user_id"]) == uid and p["game_type"] == gtype and p.get("pick_state") == "Incorrect"
        )
        if gtype == "2nd_Chance":
            new_status = "Eliminated" if losses >= 1 else "Loser Bracket"
        else:
            new_status = "Loser Bracket" if losses == 0 else ("Winner Bracket" if losses == 1 else "Eliminated")

        if new_status != r.get("bracket_status"):
            supabase.table("tournament_registrations").update({"bracket_status": new_status}).eq("id", r["id"]).execute()

    print(
        f"Week {current_week} lock complete: {len(confirmed_picks)} confirmed->finalized, "
        f"{auto_byes} auto-BYEs, {auto_defaults} default picks ({default_team}), {no_picks} NO_PICK losses."
    )

if __name__ == "__main__":
    main()

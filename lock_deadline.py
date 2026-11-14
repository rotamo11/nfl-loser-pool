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

def main():
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

    # 2. Check active players across both Main and 2nd_Chance for missing picks
    regs = (
        supabase.table("tournament_registrations")
        .select("id, user_id, game_type, is_enrolled, bracket_status")
        .eq("is_enrolled", True)
        .neq("bracket_status", "Eliminated")
        .execute()
        .data or []
    )

    week_picks = (
        supabase.table("user_picks")
        .select("id, user_id, game_type, team_picked, pick_state")
        .eq("week", current_week)
        .execute()
        .data or []
    )

    matches = supabase.table("nfl_schedule").select("id").eq("week", current_week).execute().data or []
    required_count = get_required_picks(current_week, len(matches))

    penalized = 0
    for r in regs:
        uid = str(r["user_id"])
        gtype = r["game_type"]
        existing = [p for p in week_picks if str(p["user_id"]) == uid and p["game_type"] == gtype]
        missing_slots = required_count - len(existing)

        for _ in range(max(0, missing_slots)):
            supabase.table("user_picks").insert({
                "user_id": uid,
                "game_type": gtype,
                "week": current_week,
                "team_picked": "NO_PICK",
                "pick_state": "Incorrect",
            }).execute()
            penalized += 1

    # 3. Recalculate bracket_status across BOTH pools based on total 'Incorrect' picks
    all_picks = supabase.table("user_picks").select("user_id, game_type, pick_state").execute().data or []
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

    print(f"Week {current_week} lock complete: {len(confirmed_picks)} finalized, {penalized} missing-pick losses logged.")

if __name__ == "__main__":
    main()

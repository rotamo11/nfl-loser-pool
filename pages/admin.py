def run_sunday_noon_cron_job(week_num, game_slug):
    # 1. Fetch all league registrations for the active pool game mode
    active_players = supabase.table("tournament_registrations").select("*").eq("game_type", game_slug).neq("bracket_status", "Eliminated").execute().data
    
    # 2. Fetch the highest favored team from games that haven't kicked off yet
    # Order your database schedule array by your ESPN Odds tier sequence parameters
    available_matches = supabase.table("nfl_schedule").select("*").eq("week", week_num).order("espn_favored_tier").execute().data
    
    for player in active_players:
        # Check if the player already submitted a pick for this week
        existing = supabase.table("user_picks").select("*").eq("user_id", player["user_id"]).eq("game_type", game_slug).eq("week", week_num).execute().data
        
        if not existing:
            if player["byes_used"] < 1:
                # Fallback Step 2: Burn the user's available single seasonal league bye option
                supabase.table("user_picks").insert({"user_id": player["user_id"], "game_type": game_slug, "week": week_num, "team_picked": "BYE", "pick_state": "Finalized"}).execute()
                supabase.table("tournament_registrations").update({"byes_used": 1}).eq("user_id", player["user_id"]).eq("game_type", game_slug).execute()
            else:
                # Fallback Step 3: Force assign the top unplayed ESPN-favored team (Repeats are allowed!)
                if available_matches:
                    top_favored_team = available_matches[0]["espn_favored_team"]
                    supabase.table("user_picks").insert({
                        "user_id": player["user_id"], 
                        "game_type": game_slug, 
                        "week": week_num, 
                        "team_picked": top_favored_team, 
                        "pick_state": "Finalized"
                    }).execute()

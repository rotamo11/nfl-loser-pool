# background_cron_reminders.py
import datetime
import os
from supabase import create_client, Client

# Database Initialization
supabase: Client = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])

# Reckon Target Active Game Parameters
SEASON_START = datetime.datetime(2026, 9, 9, 0, 0, 0)
current_week = 1 if datetime.datetime.now() < SEASON_START else min(22, ((datetime.datetime.now() - SEASON_START).days // 7) + 1)

for game_slug in ["Main", "2nd_Chance"]:
    # 🔍 Fetch active rosters and existing picks for this specific segment window
    active_regs = supabase.table("tournament_registrations").select("user_id").eq("game_type", game_slug).eq("is_enrolled", True).neq("bracket_status", "Eliminated").execute().data
    weekly_picks = supabase.table("user_picks").select("user_id, pick_state").eq("game_type", game_slug).eq("week", current_week).execute().data
    
    # Filter players who have already submitted an active selection (Confirmed or Finalized)
    safe_player_uids = {p["user_id"] for p in weekly_picks if p.get("pick_state") in ["Confirmed", "Finalized"]}
    late_player_uids = [r["user_id"] for r in active_regs if r["user_id"] not in safe_player_uids]
    
    if late_player_uids:
        # Fetch notification preference flags from user database rows
        users_to_alert = supabase.table("users").select("email", "cell_phone", "alert_email", "alert_sms").in_("id", late_player_uids).execute().data
        
        for u in users_to_alert:
            # 🚀 CHECK PREFERENCE TIERS NATIVELY:
            send_email = u.get("alert_email", True) # Default to true
            send_sms = u.get("alert_sms", False)
            
            if send_email and u.get("email"):
                # Trigger transaction message through Twilio SendGrid or Mailgun API
                print(f"✉️ Queuing Deadline Email Alert to: {u['email']}")
            if send_sms and u.get("cell_phone"):
                # Trigger short-code text message through Twilio SMS API
                print(f"📱 Queuing Deadline SMS Reminder to: {u['cell_phone']}")

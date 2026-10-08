# background_cron_reminders.py
import datetime
import os
import smtplib
from email.mime.text import MIMEText
from supabase import create_client, Client

# Initialize database connections safely
URL, KEY = os.environ.get("SUPABASE_URL"), os.environ.get("SUPABASE_KEY")
if not URL or not KEY: exit(1)
supabase: Client = create_client(URL, KEY)

# Configure free email server parameters (Gmail SMTP Example)
EMAIL_SENDER = os.environ.get("LEAGUE_EMAIL")     # e.g., pool.commish@gmail.com
EMAIL_PASSWORD = os.environ.get("LEAGUE_APP_PWD") # 16-character Google App Password

# Reckon Target active pool game week segment parameters
START = datetime.datetime(2026, 9, 9, 0, 0, 0)
current_week = 1 if datetime.datetime.now() < START else min(22, ((datetime.datetime.now() - START).days // 7) + 1)

def send_free_message(recipient_email, subject, body_text):
    if not EMAIL_SENDER or not EMAIL_PASSWORD: return
    try:
        msg = MIMEText(body_text)
        msg['Subject'] = subject
        msg['From'] = EMAIL_SENDER
        msg['To'] = recipient_email
        
        with smtplib.SMTP_SSL('://gmail.com', 465) as server:
            server.login(EMAIL_SENDER, EMAIL_PASSWORD)
            server.sendmail(EMAIL_SENDER, [recipient_email], msg.as_string())
    except Exception as e: print(f"Mail Exception: {e}")

# Process deadline verification alerts across active tracks
for game_slug in ["Main", "2nd_Chance"]:
    active = supabase.table("tournament_registrations").select("user_id").eq("game_type", game_slug).eq("is_enrolled", True).neq("bracket_status", "Eliminated").execute().data
    picks = supabase.table("user_picks").select("user_id, pick_state").eq("game_type", game_slug).eq("week", current_week).execute().data
    
    safe_uids = {p["user_id"] for p in picks if p.get("pick_state") in ["Confirmed", "Finalized"]}
    late_uids = [r["user_id"] for r in active if r["user_id"] not in safe_uids]
    
    if late_uids:
        late_users = supabase.table("users").select("email", "cell_phone", "cell_carrier", "alert_email", "alert_sms").in_("id", late_uids).execute().data
        
        for u in late_users:
            subject = f"🏈 NFL Loser Pool: Week {current_week} Pick Deadline Alert!"
            body = f"Attention Player!\n\nOur league board shows you have not locked or confirmed your loser selection for Week {current_week} yet. Get your pick in before the deadline crashes!\n\nPortal: https://streamlit.app"
            
            # 🚀 Route free standard email
            if u.get("alert_email", True) and u.get("email"):
                send_free_message(u["email"], subject, body)
                
            # 🚀 Route free SMS via Carrier Gateway
            if u.get("alert_sms", False) and u.get("cell_phone") and u.get("cell_carrier"):
                clean_phone = "".join(filter(str.isdigit, u["cell_phone"]))
                carrier_domains = {"Verizon": "vtext.com", "AT&T": "txt.att.net", "T-Mobile": "tmomail.net", "Sprint": "://sprintpcs.com"}
                domain = carrier_domains.get(u["cell_carrier"])
                if domain and len(clean_phone) == 10:
                    sms_gateway_email = f"{clean_phone}@{domain}"
                    send_free_message(sms_gateway_email, "⏰ DEADLINE ALERT", body)

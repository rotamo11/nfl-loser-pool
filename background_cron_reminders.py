import os
import re
import smtplib
import datetime
from email.message import EmailMessage
from email.utils import formataddr
from zoneinfo import ZoneInfo
from supabase import create_client, Client

ET_ZONE = ZoneInfo("America/New_York")
SEASON_START_WEDNESDAY = datetime.datetime(2026, 9, 9, 0, 0, 0, tzinfo=ET_ZONE)

CARRIER_GATEWAYS = {
    "AT&T": "txt.att.net",
    "Verizon": "vtext.com",
    "T-Mobile": "tmomail.net",
    "Sprint": "messaging.sprintpcs.com",
    "Boost Mobile": "sms.myboostmobile.com",
    "Cricket Wireless": "sms.cricketwireless.net",
    "MetroPCS": "mymetropcs.com",
    "US Cellular": "email.uscc.net",
    "Virgin Mobile": "vmobl.com",
    "Google Fi": "msg.fi.google.com",
    "Xfinity Mobile": "vtext.com",
    "Visible": "vtext.com",
    "Mint Mobile": "tmomail.net",
}

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

def send_smtp_message(smtp_user: str, smtp_pass: str, to_addr: str, subject: str, body: str):
    clean_user = smtp_user.strip()
    clean_pass = smtp_pass.replace(" ", "").strip()
    clean_to = to_addr.strip()

    msg = EmailMessage()
    msg["From"] = formataddr(("NFL Loser Pool", clean_user))
    msg["To"] = clean_to
    if subject:
        msg["Subject"] = subject
    msg.set_content(body)

    # Connect directly to Gmail's SMTP server on port 465
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, local_hostname="localhost", timeout=15) as server:
        server.login(clean_user, clean_pass)
        server.send_message(msg)

def main():
    supabase_url = os.environ["SUPABASE_URL"]
    supabase_key = os.environ.get("SUPABASE_SERVICE_KEY") or os.environ["SUPABASE_KEY"]
    smtp_user = os.environ["SMTP_USER"]
    smtp_pass = os.environ["SMTP_PASS"]
    app_url = os.environ.get("APP_URL", "https://nfl-loser-pool-production.up.railway.app/")

    supabase: Client = create_client(supabase_url, supabase_key)
    current_week = get_current_nfl_week()

    # Fetch users, active registrations, current week picks, and schedule count
    users = supabase.table("users").select(
        "id, username, email, cell_phone, cell_carrier, alert_email, alert_sms"
    ).execute().data or []
    user_map = {str(u["id"]): u for u in users}

    regs = supabase.table("tournament_registrations").select(
        "user_id, game_type, is_enrolled, bracket_status"
    ).eq("is_enrolled", True).neq("bracket_status", "Eliminated").execute().data or []

    week_picks = supabase.table("user_picks").select(
        "user_id, game_type, pick_state"
    ).eq("week", current_week).execute().data or []

    matches = supabase.table("nfl_schedule").select("id").eq("week", current_week).execute().data or []
    required_count = get_required_picks(current_week, len(matches))

    # Track missing pools per user
    missing_by_user = {}
    for r in regs:
        uid = str(r["user_id"])
        gtype = r["game_type"]
        user_week_picks = [p for p in week_picks if str(p["user_id"]) == uid and p["game_type"] == gtype]
        if len(user_week_picks) < required_count:
            missing_by_user.setdefault(uid, []).append(gtype.replace("_", " "))

    sent_emails, sent_sms = 0, 0
    for uid, missing_pools in missing_by_user.items():
        u = user_map.get(uid)
        if not u:
            continue

        uname = u.get("username") or "Player"
        pools_label = " & ".join(missing_pools)

        # 1. Email Reminder
        if u.get("alert_email") and u.get("email"):
            subj = f"NFL Loser Pool Reminder: Week {current_week} Pick Needed ({pools_label})"
            body = (
                f"Hey {uname},\n\n"
                f"You still need to submit your Week {current_week} pick(s) for: {pools_label}.\n\n"
                f"Weekly Deadline: Sunday at 12:00 PM ET (or by kickoff of an earlier game).\n\n"
                f"Submit your pick now:\n{app_url}\n"
            )
            try:
                send_smtp_message(smtp_user, smtp_pass, u["email"], subj, body)
                sent_emails += 1
            except Exception as e:
                print(f"Email failed for {uname}: {e}")

        # 2. SMS Gateway Reminder
        if u.get("alert_sms") and u.get("email"):
            digits = re.sub(r"\D", "", u.get("cell_phone") or "")
            gateway = CARRIER_GATEWAYS.get(u.get("cell_carrier") or "")
            if len(digits) == 10 and gateway:
                sms_addr = f"{digits}@{gateway}"
                sms_body = f"NFL Loser Pool: Week {current_week} pick needed for {pools_label} before Sun 12pm ET!" #removed {app_url}
                subj = f"SMS TEST"
                body = f"{sms_addr}\n{sms_body}
                try:
                    send_smtp_message(smtp_user, smtp_pass, sms_addr, "", sms_body)
                    sent_sms += 1
                    send_smtp_message(smtp_user, smtp_pass, u["email"], subj, body)
                except Exception as e:
                    print(f"SMS failed for {uname}: {e}")

    print(f"Week {current_week} reminders complete: {sent_emails} emails, {sent_sms} texts sent.")

if __name__ == "__main__":
    main()

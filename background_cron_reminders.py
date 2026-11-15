import os
import smtplib
import datetime
import urllib.request
from email.message import EmailMessage
from email.utils import formataddr
from zoneinfo import ZoneInfo
from supabase import create_client, Client

ET_ZONE = ZoneInfo("America/New_York")
SEASON_START_WEDNESDAY = datetime.datetime(2026, 9, 9, 0, 0, 0, tzinfo=ET_ZONE)
DEFAULT_NTFY_TOPIC = "nflloserpool"

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

def send_smtp_email(smtp_user: str, smtp_pass: str, to_addr: str, subject: str, body: str):
    clean_user = smtp_user.strip()
    clean_pass = smtp_pass.replace(" ", "").strip()
    smtp_server = ".".join(["smtp", "gmail", "com"])

    msg = EmailMessage()
    msg["From"] = formataddr(("NFL Loser Pool", clean_user))
    msg["To"] = to_addr.strip()
    msg["Subject"] = subject
    msg.set_content(body)

    with smtplib.SMTP_SSL(smtp_server, 465, local_hostname="localhost", timeout=15) as server:
        server.login(clean_user, clean_pass)
        server.send_message(msg)

def send_ntfy_push(topic: str, title: str, message: str, click_url: str):
    clean_topic = (topic or DEFAULT_NTFY_TOPIC).strip().lstrip("/")
    url = f"https://ntfy.sh{clean_topic}"
    req = urllib.request.Request(
        url,
        data=message.encode("utf-8"),
        headers={
            "Title": title,
            "Priority": "default",
            "Tags": "football,alarm_clock",
            "Click": click_url,
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        resp.read()

def main():
    supabase_url = os.environ["SUPABASE_URL"]
    supabase_key = os.environ.get("SUPABASE_SERVICE_KEY") or os.environ["SUPABASE_KEY"]
    smtp_user = os.environ["SMTP_USER"]
    smtp_pass = os.environ["SMTP_PASS"]
    app_url = os.environ.get("APP_URL", "https://nfl-loser-pool-production.up.railway.app/")

    supabase: Client = create_client(supabase_url, supabase_key)
    current_week = get_current_nfl_week()

    users = supabase.table("users").select(
        "id, username, email, cell_carrier, alert_email, alert_sms"
    ).execute().data or []
    user_map = {str(u["id"]): u for u in users}

    regs = supabase.table("tournament_registrations").select(
        "user_id, game_type, is_enrolled, bracket_status"
    ).eq("is_enrolled", True).neq("bracket_status", "Eliminated").execute().data or []

    week_picks = supabase.table("user_picks").select(
        "user_id, game_type"
    ).eq("week", current_week).execute().data or []

    matches = supabase.table("nfl_schedule").select("id").eq("week", current_week).execute().data or []
    required_count = get_required_picks(current_week, len(matches))

    missing_by_user = {}
    for r in regs:
        uid = str(r["user_id"])
        gtype = r["game_type"]
        user_week_picks = [p for p in week_picks if str(p["user_id"]) == uid and p["game_type"] == gtype]
        if len(user_week_picks) < required_count:
            missing_by_user.setdefault(uid, []).append(gtype.replace("_", " "))

    sent_emails, sent_pushes = 0, 0
    broadcast_needed = False

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
                f"You still need to submit your Week {current_week} pick(s) for the {pools_label} Pool.\n\n"
                f"You have until Sunday at NOON ET (or by kickoff of an earlier game) to avoid being given your BYE (if available) or the highest favored/ranked team that still has yet to play this week.\n\n"
                f"Submit your pick now: \n\n{app_url}\n"
            )
            try:
                send_smtp_email(smtp_user, smtp_pass, u["email"], subj, body)
                sent_emails += 1
            except Exception as e:
                print(f"Email failed for {uname}: {e}")

        # 2. ntfy.sh Push Reminder (Reuses alert_sms toggle + cell_carrier as custom topic if set)
        if u.get("alert_sms"):
            saved_topic = (u.get("cell_carrier") or "").strip()
            if saved_topic and saved_topic != DEFAULT_NTFY_TOPIC and "." not in saved_topic and saved_topic != "None / Do Not Use":
                try:
                    send_ntfy_push(
                        saved_topic,
                        f"NFL Loser Pool: Week {current_week} Pick Needed",
                        f"Hey {uname}, submit your {pools_label} Pool pick before Sunday 12:00 PM ET to avoid being given your BYE (if available) or the highest favored/ranked team that still has yet to play this week.",
                        app_url,
                    )
                    sent_pushes += 1
                except Exception as e:
                    print(f"Push failed for {uname}: {e}")
            else:
                broadcast_needed = True

    # Send one clean broadcast alert to 'nflloserpool' if any subscribed players still need picks
    if broadcast_needed:
        try:
            send_ntfy_push(
                DEFAULT_NTFY_TOPIC,
                f"NFL Loser Pool: Week {current_week} Deadline Reminder",
                f"Reminder: Submit your Week {current_week} pick(s) before Sunday at 12:00 PM ET (or kickoff of an early game)!",
                app_url,
            )
            sent_pushes += 1
        except Exception as e:
            print(f"Broadcast push failed: {e}")

    print(f"Week {current_week} reminders complete: {sent_emails} emails, {sent_pushes} push alerts sent.")

if __name__ == "__main__":
    main()

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
    clean_topic = topic.strip().lstrip("/")
    ntfy_domain = ".".join(["ntfy", "sh"])
    url = f"https://{ntfy_domain}/{clean_topic}"
    req = urllib.request.Request(
        url,
        data=message.encode("utf-8"),
        headers={
            "Title": title,
            "Priority": "default",
            "Icon": f"{click_url.rstrip('/')}/static/loser-logo.png",
            "Click": click_url,
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        resp.read()

def resolve_week_default_info(supabase: Client, current_week: int) -> tuple[str, bool]:
    """Returns (active_team, is_explicitly_saved_for_current_week)."""
    rows = supabase.table("default_picks").select("week, team").order("week", desc=False).execute().data or []
    def_map = {int(r["week"]): r["team"].upper().strip() for r in rows if r.get("team")}
    if current_week in def_map:
        return def_map[current_week], True
    prior = [w for w in sorted(def_map.keys(), reverse=True) if w < current_week]
    if prior:
        return def_map[prior], False
    return "NONE SET", False

def main():
    supabase_url = os.environ["SUPABASE_URL"]
    supabase_key = os.environ.get("SUPABASE_SERVICE_KEY") or os.environ["SUPABASE_KEY"]
    smtp_user = os.environ["SMTP_USER"]
    smtp_pass = os.environ["SMTP_PASS"]
    app_url = os.environ.get("APP_URL", "https://railway.app")

    supabase: Client = create_client(supabase_url, supabase_key)
    current_week = get_current_nfl_week()

    users = supabase.table("users").select(
        "id, username, email, alert_personal_topic, alert_email, alert_sms, is_admin"
    ).execute().data or []
    user_map = {str(u["id"]): u for u in users}

    # --- 1. ADMIN DEFAULT TEAM VERIFICATION REMINDER ---
    default_team, is_saved = resolve_week_default_info(supabase, current_week)
    status_note = (
        f"Explicitly saved for Week {current_week}"
        if is_saved
        else f"Inherited from prior week (not yet saved for Week {current_week})"
    )
    admin_users = [u for u in users if u.get("is_admin")]

    for adm in admin_users:
        adm_name = adm.get("username") or "Admin"
        if adm.get("alert_email") and adm.get("email"):
            adm_subj = f"Admin Check: Week {current_week} Default Pick is {default_team}"
            adm_body = (
                f"Hey {adm_name},\n\n"
                f"Please verify the Week {current_week} auto-pick default team before Sunday at NOON ET.\n\n"
                f"Current Default Team: {default_team} ({status_note})\n\n"
                f"Update or confirm in the Admin Console: \n\n{app_url}/admin\n"
            )
            try:
                send_smtp_email(smtp_user, smtp_pass, adm["email"], adm_subj, adm_body)
            except Exception as e:
                print(f"Admin email failed for {adm_name}: {e}")

        if adm.get("alert_sms"):
            adm_topic = (adm.get("alert_personal_topic") or "").strip() or f"nflloserpool-{str(adm['id'])[:8]}"
            try:
                send_ntfy_push(
                    adm_topic,
                    f"Admin Check: Week {current_week} Default = {default_team}",
                    f"Verify Week {current_week} default team ({default_team} - {status_note}) before Sunday at NOON ET.",
                    f"{app_url}/admin",
                )
            except Exception as e:
                print(f"Admin push failed for {adm_name}: {e}")

    # --- 2. PLAYER MISSING PICK REMINDERS ---
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

    for uid, missing_pools in missing_by_user.items():
        u = user_map.get(uid)
        if not u:
            continue

        uname = u.get("username") or "Player"
        pools_label = " & ".join(missing_pools)

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

        if u.get("alert_sms"):
            personal_topic = (u.get("alert_personal_topic") or "").strip() or f"nflloserpool-{uid[:8]}"
            try:
                send_ntfy_push(
                    personal_topic,
                    f"NFL Loser Pool: Week {current_week} Pick Needed",
                    f"Hey {uname}, submit your {pools_label} Pool pick before Sunday at NOON ET to avoid being given your BYE (if available) or the highest favored/ranked team that still has yet to play this week.",
                    app_url,
                )
                sent_pushes += 1
            except Exception as e:
                print(f"Push failed for {uname}: {e}")

    print(f"Week {current_week} reminders complete: {sent_emails} emails, {sent_pushes} personal push alerts sent.")

if __name__ == "__main__":
    main()

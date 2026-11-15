import os
import datetime
from zoneinfo import ZoneInfo
from background_cron_reminders import send_smtp_email, send_ntfy_push

ET_ZONE = ZoneInfo("America/New_York")

def get_open_registration_pools(supabase) -> dict[str, dict]:
    """Returns dict of {game_type: window_row} for pools whose registration window is currently open."""
    now_utc = datetime.datetime.now(datetime.timezone.utc)
    rows = supabase.table("registration_windows").select("*").execute().data or []
    open_pools = {}
    for r in rows:
        try:
            opens = datetime.datetime.fromisoformat(str(r["opens_at"]).replace("Z", "+00:00"))
            closes = datetime.datetime.fromisoformat(str(r["closes_at"]).replace("Z", "+00:00"))
            if opens <= now_utc <= closes:
                open_pools[r["game_type"]] = r
        except Exception:
            continue
    return open_pools

def notify_admins_of_join_request(supabase, req_data: dict):
    """Notifies all is_admin=True users via email and ntfy.sh with a direct link to approve."""
    smtp_user = os.environ.get("SMTP_USER", "")
    smtp_pass = os.environ.get("SMTP_PASS", "")
    app_url = os.environ.get("APP_URL", "https://nfl-loser-pool-production.up.railway.app").rstrip("/")
    review_url = f"{app_url}/admin"

    pool_label = req_data.get("game_type", "Main").replace("_", " ")
    uname = req_data.get("username") or "Player"
    email = req_data.get("email") or ""
    full_name = f"{req_data.get('first_name', '')} {req_data.get('last_name', '')}".strip()
    is_new = "Brand New Account" if not req_data.get("user_id") else "Existing Player"

    admins = supabase.table("users").select(
        "id, username, email, alert_personal_topic, alert_email, alert_sms"
    ).eq("is_admin", True).execute().data or []

    for adm in admins:
        adm_name = adm.get("username") or "Admin"
        if smtp_user and smtp_pass and adm.get("alert_email") and adm.get("email"):
            try:
                send_smtp_email(
                    smtp_user,
                    smtp_pass,
                    adm["email"],
                    f"NFL Loser Pool: Join Request ({pool_label}) - {uname}",
                    f"Hey {adm_name},\n\n"
                    f"A player has requested to join the {pool_label} Pool:\n\n"
                    f"• Username: {uname}\n"
                    f"• Name: {full_name or 'N/A'}\n"
                    f"• Email: {email}\n"
                    f"• Type: {is_new}\n\n"
                    f"Review and approve this request in the Admin Console:\n{review_url}\n",
                )
            except Exception as e:
                print(f"Admin join-request email failed: {e}")

        if adm.get("alert_sms"):
            adm_topic = (adm.get("alert_personal_topic") or "").strip() or f"nflloserpool-{str(adm['id'])[:8]}"
            try:
                send_ntfy_push(
                    adm_topic,
                    f"Join Request: {uname} ({pool_label})",
                    f"{uname} ({is_new}) requested to join {pool_label}. Tap to review & approve.",
                    review_url,
                )
            except Exception as e:
                print(f"Admin join-request push failed: {e}")

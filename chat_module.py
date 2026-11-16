import datetime
from zoneinfo import ZoneInfo
from nicegui import ui, app

ET_ZONE = ZoneInfo("America/New_York")

def format_chat_timestamp(iso_str: str) -> str:
    if not iso_str:
        return ""
    try:
        dt_utc = datetime.datetime.fromisoformat(str(iso_str).replace("Z", "+00:00"))
        if dt_utc.tzinfo is None:
            dt_utc = dt_utc.replace(tzinfo=datetime.timezone.utc)
        dt_et = dt_utc.astimezone(ET_ZONE)
        return dt_et.strftime("%a %-m/%-d %-I:%M %p ET")
    except Exception:
        return ""

def render_chat_view(supabase, user):
    current_user_id = str(user.id)
    is_dark = app.storage.user.get("dark_mode", False)

    # Safely fetch current user's username and admin flag
    u_rows = supabase.table("users").select("username, is_admin").eq("id", current_user_id).execute().data or []
    first_u = next(iter(u_rows), {})
    current_username = first_u.get("username") or "Player"
    is_admin = bool(first_u.get("is_admin", False))

    # Mark chat as read upon opening
    def mark_chat_read():
        try:
            now_utc = datetime.datetime.now(datetime.timezone.utc).isoformat()
            supabase.table("users").update({"last_read_chat_at": now_utc}).eq("id", current_user_id).execute()
        except Exception:
            pass

    mark_chat_read()

    with ui.row().classes("w-full items-center justify-between mb-3"):
        with ui.column().classes("gap-0"):
            ui.label("League Chat & Trash Talk").classes("text-xl font-black")
            ui.label("Open to all Main & 2nd Chance players, even winners! Be mindful of deadlines when discussing picks.").classes("text-xs opacity-70")
        ui.button("Refresh", icon="refresh", on_click=lambda: message_feed.refresh()).props("flat dense size=sm")

    box_bg = "bg-slate-950/60 border-slate-700" if is_dark else "bg-slate-50 border-slate-200"

    @ui.refreshable
    def message_feed():
        mark_chat_read()
        msgs = (
            supabase.table("pool_chat")
            .select("*")
            .order("created_at", desc=True)
            .limit(75)
            .execute()
            .data or []
        )
        msgs = list(reversed(msgs))

        with ui.scroll_area().classes(f"w-full h-96 p-3 rounded-lg border {box_bg}") as scroll:
            if not msgs:
                ui.label("No messages yet. Kick off the trash talk below!").classes("text-xs opacity-60 italic")
            else:
                for m in msgs:
                    is_mine = (str(m.get("user_id")) == current_user_id)
                    sender = m.get("username") or "Player"
                    body_txt = m.get("message") or m.get("content") or ""
                    ts_label = format_chat_timestamp(m.get("created_at") or "")

                    align_cls = "items-end" if is_mine else "items-start"
                    bubble_cls = (
                        "bg-blue-600 text-white"
                        if is_mine
                        else ("bg-slate-800 text-slate-100 border border-slate-700" if is_dark else "bg-white text-slate-900 border border-slate-200")
                    )

                    with ui.column().classes(f"w-full {align_cls} mb-2.5 gap-0.5"):
                        with ui.row().classes("items-center gap-2 text-[11px] opacity-70"):
                            ui.label(f"{sender} • {ts_label}")
                            if is_mine or is_admin:
                                def delete_msg(mid=m["id"]):
                                    supabase.table("pool_chat").delete().eq("id", mid).execute()
                                    message_feed.refresh()

                                ui.button(icon="delete", on_click=delete_msg).props("flat round dense size=xs color=red")

                        with ui.element("div").classes(f"px-3 py-2 rounded-xl max-w-[82%] text-xs md:text-sm shadow-sm {bubble_cls}"):
                            ui.label(body_txt).classes("whitespace-pre-wrap break-words")

            scroll.scroll_to(percent=1.0)

    message_feed()

    # Auto-refresh chat every 15 seconds while mounted
    with ui.element("div"):
        ui.timer(15.0, message_feed.refresh)

    # Message Input Bar
    with ui.row().classes("w-full items-center gap-2 mt-3 no-wrap"):
        msg_in = ui.input(placeholder="Say something...").classes("flex-1").props("outlined dense")

        def send_message():
            txt = (msg_in.value or "").strip()
            if not txt:
                return
            msg_in.value = ""
            supabase.table("pool_chat").insert({
                "user_id": current_user_id,
                "username": current_username,
                "message": txt,
            }).execute()
            mark_chat_read()
            message_feed.refresh()

        msg_in.on("keydown.enter", send_message)
        ui.button("Send", icon="send", on_click=send_message, color="primary").classes("font-bold px-4")

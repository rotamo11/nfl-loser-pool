import datetime
from zoneinfo import ZoneInfo
from nicegui import ui, app
from admin_module import is_admin_user

ET_ZONE = ZoneInfo("America/New_York")

# Add this helper function right below ET_ZONE in chat_module.py
def get_unread_chat_count(supabase, user) -> int:
    if not user:
        return 0
    try:
        last_read = app.storage.user.get("last_read_chat_ts")
        query = supabase.table("chat_messages").select("id, created_at").neq("user_id", str(user.id))
        if last_read:
            query = query.gt("created_at", last_read)
        rows = query.execute().data or []
        return len(rows)
    except Exception:
        return 0

def render_chat_view(supabase, user, pool_slug: str):
    user_id = str(user.id)
    admin_flag = is_admin_user(supabase, user)
    is_dark = app.storage.user.get("dark_mode", False)

    # Fetch display username
    u_res = supabase.table("users").select("username").eq("id", user_id).execute().data
    my_username = u_res[0].get("username") if (isinstance(u_res, list) and len(u_res) > 0) else "Player"

    with ui.row().classes("w-full items-center justify-between mb-3 pb-2 border-b border-slate-200 dark:border-slate-700"):
        ui.label("💬 League Chat & Trash Talk").classes("text-xl font-black")
        ui.button("Refresh", icon="refresh", on_click=lambda: message_feed.refresh()).props("flat dense size=sm")

    @ui.refreshable
    def message_feed():
        # Fetch recent 100 messages (global or filtered by pool if game_type column exists)
        try:
            msgs = supabase.table("chat_messages").select("*").order("created_at", desc=False).limit(100).execute().data or []
        except Exception as e:
            ui.label(f"Error loading chat: {str(e)}").classes("text-red-500 text-xs")
            return

        if not msgs:
            ui.label("No messages yet. Start the trash talk below!").classes("text-sm opacity-70 italic py-4")
            return

        newest_ts = msgs[-1].get("created_at")
        if newest_ts:
            app.storage.user["last_read_chat_ts"] = newest_ts

        with ui.scroll_area().classes("w-full h-96 p-3 rounded-lg border border-slate-200 dark:border-slate-700"):
            with ui.column().classes("w-full gap-2.5"):
                for m in msgs:
                    m_id = m.get("id")
                    sender = m.get("username") or "Anonymous"
                    body = m.get("message") or m.get("content") or ""
                    is_mine = (str(m.get("user_id")) == user_id)

                    # Format timestamp to Eastern Time
                    time_str = ""
                    if raw_ts := m.get("created_at"):
                        try:
                            dt = datetime.datetime.fromisoformat(str(raw_ts).replace("Z", "+00:00"))
                            time_str = dt.astimezone(ET_ZONE).strftime("%b %-d, %-I:%M %p ET")
                        except Exception:
                            pass

                    if is_mine:
                        bubble_cls = "bg-blue-600 text-white self-end"
                    else:
                        bubble_cls = "bg-slate-800 text-slate-100 self-start" if is_dark else "bg-slate-100 text-slate-900 self-start"

                    with ui.column().classes(f"max-w-[85%] p-2.5 rounded-xl {bubble_cls} gap-0.5"):
                        with ui.row().classes("w-full items-center justify-between gap-3 no-wrap"):
                            ui.label(sender).classes("text-xs font-extrabold")
                            with ui.row().classes("items-center gap-1"):
                                if time_str:
                                    ui.label(time_str).classes("text-[10px] opacity-70")
                                if admin_flag or is_mine:
                                    def del_msg(mid=m_id):
                                        supabase.table("chat_messages").delete().eq("id", mid).execute()
                                        message_feed.refresh()
                                    ui.button(icon="delete", on_click=del_msg).props("flat round dense size=xs color=red-4")

                        ui.label(body).classes("text-sm whitespace-pre-wrap break-words")

    message_feed()

    # --- NEW MESSAGE INPUT BAR ---
    with ui.row().classes("w-full items-center gap-2 mt-3 no-wrap"):
        msg_input = ui.input(placeholder=f"Post as {my_username}...").classes("flex-1").props("outlined dense")

        def send_message():
            txt = (msg_input.value or "").strip()
            if not txt:
                return
            try:
                supabase.table("chat_messages").insert({
                    "user_id": user_id,
                    "username": my_username,
                    "message": txt,
                }).execute()
                msg_input.value = ""
                message_feed.refresh()
            except Exception as err:
                ui.notify(f"Failed to send: {str(err)}", type="negative")

        msg_input.on("keydown.enter", send_message)
        ui.button("Send", icon="send", on_click=send_message, color="primary").props("unelevated")

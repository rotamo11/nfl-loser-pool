import asyncio
import datetime
from zoneinfo import ZoneInfo
from nicegui import ui, app, run

ET_ZONE = ZoneInfo("America/New_York")
REACTION_EMOJIS = [
    "👍", "👎", "😂", "😭", "💀",
    "🔥", "🎯", "🤡", "💩", "😱",
    "🤦", "🙌", "🍻", "🏈", "🏆",
]

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

async def render_chat_view(supabase, user):
    current_user_id = str(user.id)
    is_dark = app.storage.user.get("dark_mode", False)

    def mark_chat_read_sync():
        try:
            now_utc = datetime.datetime.now(datetime.timezone.utc).isoformat()
            supabase.table("users").update({"last_read_chat_at": now_utc}).eq("id", current_user_id).execute()
        except Exception:
            pass

    u_rows, initial_msgs, _ = await asyncio.gather(
        run.io_bound(lambda: supabase.table("users").select("username, is_admin").eq("id", current_user_id).execute().data or []),
        run.io_bound(lambda: supabase.table("pool_chat").select("*").order("created_at", desc=True).limit(75).execute().data or []),
        run.io_bound(mark_chat_read_sync),
    )

    first_u = next(iter(u_rows), {})
    current_username = first_u.get("username") or "Player"
    is_admin = bool(first_u.get("is_admin", False))

    reply_state = {"id": None, "preview": ""}

    with ui.row().classes("w-full items-center justify-between mb-3"):
        with ui.column().classes("gap-0"):
            ui.label("League Trash Talk & Chat").classes("text-xl font-black")
            ui.label("Open to all Main & 2nd Chance players.").classes("text-xs opacity-70")
        ui.button("Refresh", icon="refresh", on_click=lambda: message_feed.refresh()).props("flat dense size=sm")

    box_bg = "bg-slate-950/60 border-slate-700" if is_dark else "bg-slate-50 border-slate-200"
    feed_cache = {"msgs": initial_msgs, "first_load": True}

    @ui.refreshable
    def reply_banner():
        if not reply_state["id"]:
            return
        banner_cls = "bg-slate-800 border-blue-500 text-slate-200" if is_dark else "bg-blue-50 border-blue-600 text-slate-800"
        with ui.row().classes(f"w-full items-center justify-between px-3 py-1.5 mt-2 rounded-lg border-l-4 {banner_cls}"):
            ui.label(f"Replying to {reply_state['preview']}").classes("text-xs font-semibold truncate")
            def clear_reply():
                reply_state["id"] = None
                reply_state["preview"] = ""
                reply_banner.refresh()
            ui.button(icon="close", on_click=clear_reply).props("flat round dense size=xs")

    def toggle_reaction(msg_id: str, current_reactions: dict, emoji: str):
        updated = {k: list(v) for k, v in (current_reactions or {}).items()}
        users_list = updated.get(emoji, [])
        if current_user_id in users_list:
            users_list.remove(current_user_id)
        else:
            users_list.append(current_user_id)
        if users_list:
            updated[emoji] = users_list
        else:
            updated.pop(emoji, None)
        supabase.table("pool_chat").update({"reactions": updated}).eq("id", msg_id).execute()
        message_feed.refresh()
    @ui.refreshable
    def message_feed():
        if feed_cache["first_load"]:
            msgs = feed_cache["msgs"]
            feed_cache["first_load"] = False
        else:
            mark_chat_read_sync()
            msgs = supabase.table("pool_chat").select("*").order("created_at", desc=True).limit(75).execute().data or []

        msgs = list(reversed(msgs))

        with ui.scroll_area().classes(f"w-full h-96 p-3 rounded-lg border {box_bg}") as scroll:
            if not msgs:
                ui.label("No messages yet. Kick off the trash talk below!").classes("text-xs opacity-60 italic")
            else:
                for m in msgs:
                    mid = m["id"]
                    is_mine = (str(m.get("user_id")) == current_user_id)
                    sender = m.get("username") or "Player"
                    body_txt = m.get("message") or m.get("content") or ""
                    ts_label = format_chat_timestamp(m.get("created_at") or "")
                    quoted_txt = (m.get("reply_preview") or "").strip()
                    rx_map = m.get("reactions") or {}

                    align_cls = "items-end" if is_mine else "items-start"
                    bubble_cls = (
                        "bg-blue-600 text-white"
                        if is_mine
                        else ("bg-slate-800 text-slate-100 border border-slate-700" if is_dark else "bg-white text-slate-900 border border-slate-200")
                    )

                    with ui.column().classes(f"w-full {align_cls} mb-3 gap-0.5"):
                        with ui.row().classes("items-center gap-1.5 text-[11px] opacity-75"):
                            ui.label(f"{sender} • {ts_label}")

                            def start_reply(m_id=mid, s_name=sender, txt=body_txt):
                                snippet = txt[:65] + ("..." if len(txt) > 65 else "")
                                reply_state["id"] = m_id
                                reply_state["preview"] = f"{s_name}: {snippet}"
                                reply_banner.refresh()

                            ui.button(icon="reply", on_click=start_reply).props("flat round dense size=xs").tooltip("Quote & Reply")

                            with ui.button(icon="add_reaction").props("flat round dense size=xs").tooltip("React"):
                                with ui.menu():
                                    with ui.grid(columns=5).classes("p-1.5 gap-1"):
                                        for em in REACTION_EMOJIS:
                                            ui.button(
                                                em,
                                                on_click=lambda _e, m_id=mid, r_map=rx_map, emo=em: toggle_reaction(m_id, r_map, emo),
                                            ).props("flat dense size=sm")

                            if is_mine or is_admin:
                                def delete_msg(m_id=mid):
                                    supabase.table("pool_chat").delete().eq("id", m_id).execute()
                                    message_feed.refresh()
                                ui.button(icon="delete", on_click=delete_msg).props("flat round dense size=xs color=red")

                        with ui.element("div").classes(f"px-3 py-2 rounded-xl max-w-[82%] text-xs md:text-sm shadow-sm {bubble_cls}"):
                            if quoted_txt:
                                quote_box = "bg-black/20 border-white/50 text-white/90" if is_mine else (
                                    "bg-slate-900/70 border-blue-400 text-slate-300" if is_dark else "bg-slate-100 border-blue-600 text-slate-600"
                                )
                                with ui.element("div").classes(f"px-2 py-1 mb-1.5 rounded border-l-2 text-[11px] italic {quote_box}"):
                                    ui.label(quoted_txt)
                            ui.label(body_txt).classes("whitespace-pre-wrap break-words")

                        active_rx = [(em, uids) for em, uids in rx_map.items() if uids]
                        if active_rx:
                            with ui.row().classes("items-center gap-1 mt-0.5 flex-wrap"):
                                for em, uids in active_rx:
                                    i_reacted = current_user_id in uids
                                    pill_cls = (
                                        "bg-blue-600/25 border-blue-500 text-blue-400"
                                        if i_reacted
                                        else ("bg-slate-800 border-slate-700 text-slate-300" if is_dark else "bg-white border-slate-300 text-slate-700")
                                    )
                                    ui.button(
                                        f"{em} {len(uids)}",
                                        on_click=lambda _e, m_id=mid, r_map=rx_map, emo=em: toggle_reaction(m_id, r_map, emo),
                                    ).props("flat dense no-caps size=xs").classes(f"px-1.5 py-0 rounded-full border text-[11px] font-bold {pill_cls}")

            scroll.scroll_to(percent=1.0)

    message_feed()
    with ui.element("div"):
        ui.timer(15.0, message_feed.refresh)

    reply_banner()

    with ui.row().classes("w-full items-center gap-2 mt-2 no-wrap"):
        msg_in = ui.input(placeholder="Write a message to the league...").classes("flex-1").props("outlined dense")

        def send_message():
            txt = (msg_in.value or "").strip()
            if not txt:
                return
            msg_in.value = ""
            payload = {
                "user_id": current_user_id,
                "username": current_username,
                "message": txt,
                "reply_to_id": reply_state["id"],
                "reply_preview": reply_state["preview"] or None,
                "reactions": {},
            }
            reply_state["id"] = None
            reply_state["preview"] = ""
            reply_banner.refresh()

            supabase.table("pool_chat").insert(payload).execute()
            mark_chat_read_sync()
            message_feed.refresh()

        msg_in.on("keydown.enter", send_message)
        ui.button("Send", icon="send", on_click=send_message, color="primary").classes("font-bold px-4")

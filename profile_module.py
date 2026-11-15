from nicegui import ui, app

def render_profile_view(supabase, user):
    user_id = str(user.id)
    personal_topic = f"nflloserpool-{user_id[:8]}"

    # Fetch existing player profile from Supabase
    res = supabase.table("users").select("*").eq("id", user_id).execute().data
    profile = res[0] if (isinstance(res, list) and len(res) > 0) else {}

    ui.label("Player Profile & Notification Settings").classes("text-xl font-black mb-1")
    ui.label(f"Account Email: {user.email}").classes("text-xs opacity-70 mb-4")

    # --- TOP SECTION: APPEARANCE / THEME PREFERENCE ---
    is_dark = app.storage.user.get("dark_mode", False)
    with ui.card().classes("w-full p-4 mb-4 border border-slate-300 dark:border-slate-700 shadow-none"):
        with ui.row().classes("w-full items-center justify-between gap-2"):
            with ui.column().classes("gap-0"):
                ui.label("Appearance & Display Theme").classes("text-base font-extrabold")
                ui.label("Switch between Light and Dark mode for content cards.").classes("text-xs opacity-75")

            def on_theme_toggle(e):
                app.storage.user["dark_mode"] = e.value
                try:
                    supabase.table("users").update({"dark_mode": e.value}).eq("id", user_id).execute()
                except Exception:
                    pass
                ui.navigate.reload()

            ui.switch("Dark Mode", value=is_dark, on_change=on_theme_toggle).classes("font-bold")

    with ui.grid().classes("w-full grid-cols-1 md:grid-cols-2 gap-6"):

        # --- LEFT COLUMN: IDENTITY & ALERT SETTINGS ---
        with ui.card().classes("w-full p-4 border border-slate-300 dark:border-slate-700 shadow-none"):
            ui.label("League Identity & Deadline Alerts").classes("text-base font-extrabold mb-3")

            username_in = ui.input(
                "Display Username (Shown on Brackets)",
                value=profile.get("username") or ""
            ).classes("w-full mb-2")

            with ui.row().classes("w-full gap-2 no-wrap mb-2"):
                first_in = ui.input("First Name", value=profile.get("first_name") or "").classes("flex-1")
                last_in = ui.input("Last Name", value=profile.get("last_name") or "").classes("flex-1")

            saved_topic = (profile.get("cell_carrier") or "").strip()
            if not saved_topic or "." in saved_topic or saved_topic in ["None / Do Not Use", "nflloserpool"]:
                saved_topic = personal_topic

            with ui.row().classes("w-full items-center gap-2 no-wrap mb-1"):
                topic_in = ui.input(
                    "Your Personal ntfy.sh Push Topic",
                    value=saved_topic
                ).classes("flex-1")
                ui.button(
                    icon="content_copy",
                    on_click=lambda: (ui.clipboard.write(topic_in.value), ui.notify("Topic copied to clipboard!", type="info"))
                ).props("flat round dense").tooltip("Copy personal topic")

            ui.label(
                f"Free Mobile Push: Install the ntfy app on iOS/Android and subscribe to '{personal_topic}' which is your personal topic for alerts."
            ).classes("text-[11px] opacity-75 mb-3")

            ui.label("Automated Reminder Channels:").classes("text-xs font-bold opacity-80 mt-1")
            email_chk = ui.checkbox(
                "Send Thursday Noon & Sunday 9 AM ET Email Reminders",
                value=bool(profile.get("alert_email", True))
            )
            push_chk = ui.checkbox(
                "Enable Thursday Noon & Sunday 9 AM ET ntfy.sh Push Alerts",
                value=bool(profile.get("alert_sms", False))
            )

            def save_profile_settings():
                clean_user = username_in.value.strip()
                clean_topic = topic_in.value.strip() or personal_topic

                if not clean_user:
                    ui.notify("Username cannot be empty.", type="negative")
                    return

                try:
                    supabase.table("users").update({
                        "username": clean_user,
                        "first_name": first_in.value.strip(),
                        "last_name": last_in.value.strip(),
                        "cell_carrier": clean_topic,
                        "alert_email": email_chk.value,
                        "alert_sms": push_chk.value,
                    }).eq("id", user_id).execute()
                    ui.notify("Profile & alert settings saved!", type="positive")
                except Exception as e:
                    ui.notify(f"Error saving profile: {str(e)}", type="negative")

            ui.button("Save Profile & Alerts", on_click=save_profile_settings, color="primary").classes("w-full mt-4 font-bold")

        # --- RIGHT COLUMN: SECURITY & PASSWORD UPDATE ---
        with ui.card().classes("w-full p-4 border border-slate-300 dark:border-slate-700 shadow-none self-start"):
            ui.label("Account Security & Password").classes("text-base font-extrabold mb-3")
            ui.label("Update your login password below. Passwords must be at least 6 characters long.").classes("text-xs opacity-75 mb-3")

            new_pwd = ui.input(
                "New Password",
                password=True,
                password_toggle_button=True
            ).classes("w-full mb-2")

            confirm_pwd = ui.input(
                "Confirm New Password",
                password=True,
                password_toggle_button=True
            ).classes("w-full mb-3")

            def update_password():
                p1 = new_pwd.value.strip()
                p2 = confirm_pwd.value.strip()

                if len(p1) < 6:
                    ui.notify("Password must be at least 6 characters.", type="negative")
                    return
                if p1 != p2:
                    ui.notify("Passwords do not match.", type="negative")
                    return

                try:
                    supabase.auth.admin.update_user_by_id(user_id, {"password": p1})
                    supabase.table("users").update({"first_login_complete": True}).eq("id", user_id).execute()
                    new_pwd.value = ""
                    confirm_pwd.value = ""
                    ui.notify("Password updated successfully!", type="positive")
                except Exception as e:
                    ui.notify(f"Password update failed: {str(e)}", type="negative")

            ui.button("Update Password", on_click=update_password, color="secondary").classes("w-full mt-2 font-bold")

    # --- BOTTOM SECTION: SIGN OUT ---
    ui.separator().classes("my-6")
    with ui.row().classes("w-full justify-end"):
        def handle_logout():
            saved_theme = app.storage.user.get("dark_mode", False)
            app.storage.user.clear()
            app.storage.user["dark_mode"] = saved_theme
            ui.navigate.to("/")

        ui.button("Log Out", icon="logout", on_click=handle_logout, color="red").props("outline").classes("font-bold px-6")

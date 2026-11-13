import re
from nicegui import ui

# Supported US Carrier Email-to-SMS Gateways
CARRIER_GATEWAYS = {
    "None / Do Not Use": "",
    "AT&T": "txt.att.net",
    "Verizon": "vtext.com",
    "T-Mobile": "tmomail.net",
    "Sprint": "://sprintpcs.com",
    "Boost Mobile": "://myboostmobile.com",
    "Cricket Wireless": "sms.cricketwireless.net",
    "MetroPCS": "mymetropcs.com",
    "US Cellular": "email.uscc.net",
    "Virgin Mobile": "vmobl.com",
    "Google Fi": "://google.com",
    "Xfinity Mobile": "vtext.com",
    "Visible": "vtext.com",
    "Mint Mobile": "tmomail.net",
}

def render_profile_view(supabase, user):
    user_id = str(user.id)

    # Fetch existing player profile from Supabase
    res = supabase.table("users").select("*").eq("id", user_id).execute().data
    profile = res[0] if (isinstance(res, list) and len(res) > 0) else {}

    ui.label("Player Profile & Notification Settings").classes("text-xl font-black mb-1")
    ui.label(f"Account Email: {user.email}").classes("text-xs opacity-70 mb-4")

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

            phone_in = ui.input(
                "10-Digit Cell Phone (Numbers Only)",
                value=profile.get("cell_phone") or "",
                placeholder="e.g., 5551234567"
            ).classes("w-full mb-2")
            
            current_carrier = profile.get("cell_carrier") or "None / Do Not Use"
            if current_carrier not in CARRIER_GATEWAYS:
                current_carrier = "None / Do Not Use"
            
            carrier_sel = ui.select(
                options=list(CARRIER_GATEWAYS.keys()),
                value=current_carrier,
                label="Mobile Wireless Carrier (For Free SMS Reminders)"
            ).classes("w-full mb-3")
            
            ui.label("Automated Reminder Channels:").classes("text-xs font-bold opacity-80 mt-1")
            email_chk = ui.checkbox(
                "Send Thursday Noon & Sunday 9 AM ET Email Reminders",
                value=bool(profile.get("alert_email", True))
            )
            sms_chk = ui.checkbox(
                "Send Thursday Noon & Sunday 9 AM ET Text (SMS) Reminders",
                value=bool(profile.get("alert_sms", False))
            )
            def save_profile_settings():
                clean_user = username_in.value.strip()
                clean_phone = re.sub(r"\D", "", phone_in.value or "")
                chosen_carrier = carrier_sel.value

                if not clean_user:
                    ui.notify("Username cannot be empty.", type="negative")
                    return
                if sms_chk.value and (len(clean_phone) != 10 or chosen_carrier == "None / Do Not Use"):
                    ui.notify("Enter a valid 10-digit phone number and select your carrier to enable SMS alerts.", type="negative")
                    return

                try:
                    supabase_auth.table("users").update({
                        "username": clean_user,
                        "first_name": first_in.value.strip(),
                        "last_name": last_in.value.strip(),
                        "cell_phone": clean_phone,
                        "cell_carrier": chosen_carrier,
                        "alert_email": email_chk.value,
                        "alert_sms": sms_chk.value,
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
                    supabase_auth.auth.update_user({"password": p1})
                    supabase.table("users").update({"first_login_complete": True}).eq("id", user_id).execute()
                    new_pwd.value = ""
                    confirm_pwd.value = ""
                    ui.notify("Password updated successfully!", type="positive")
                except Exception as e:
                    ui.notify(f"Password update failed: {str(e)}", type="negative")

            ui.button("Update Password", on_click=update_password, color="secondary").classes("w-full mt-2 font-bold")

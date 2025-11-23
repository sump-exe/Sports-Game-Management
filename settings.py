"""
DB-backed settings module.

Behavior:
- Settings are persisted into the application's SQLite DB (theDB.mydb).
- open_settings_popup(parent) opens a modal dialog to edit settings.
- When the user saves settings, a messagebox informs them that settings were saved
  and they must log in again. The settings popup is closed and the main UI is reset
  to the login screen by invoking mainGui.show_login_screen(). This makes the login
  screen the only visible UI in the application.

Public API:
- get_settings() -> dict
- save_settings(dict) -> bool
- open_settings_popup(parent) -> CTkToplevel
"""
import customtkinter as ctk
from tkinter import messagebox
from theDB import *

# Default settings
_DEFAULTS = {
    "team_size": 12,           # integer
    "seasons_enabled": True    # boolean
}

_TABLE_NAME = "app_settings"

# -----------------------
# Database helpers
# -----------------------
def ensure_settings_table():
    """Create the settings table if it doesn't exist."""
    cur = mydb.cursor()
    try:
        cur.execute(f"""
            CREATE TABLE IF NOT EXISTS {_TABLE_NAME} (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)
        mydb.commit()
    finally:
        try:
            cur.close()
        except Exception:
            pass

def load_settings_from_db():
    """Return a dict of settings loaded from DB merged with defaults."""
    ensure_settings_table()
    cur = mydb.cursor()
    try:
        cur.execute(f"SELECT key, value FROM {_TABLE_NAME}")
        rows = cur.fetchall()
        out = {}
        for r in rows:
            k = r['key'] if 'key' in r.keys() else r[0]
            v = r['value'] if 'value' in r.keys() else r[1]
            out[k] = v
    finally:
        try:
            cur.close()
        except Exception:
            pass

    # Coerce typed settings and apply defaults
    settings = {}
    # team_size (int)
    ts = out.get("team_size")
    try:
        settings["team_size"] = int(ts) if ts is not None else _DEFAULTS["team_size"]
    except Exception:
        settings["team_size"] = _DEFAULTS["team_size"]
    # seasons_enabled (bool stored as "0"/"1" or "true"/"false")
    se = out.get("seasons_enabled")
    if se is None:
        settings["seasons_enabled"] = _DEFAULTS["seasons_enabled"]
    else:
        if isinstance(se, str):
            s = se.strip().lower()
            settings["seasons_enabled"] = s in ("1", "true", "yes", "on")
        else:
            settings["seasons_enabled"] = bool(se)

    return settings

def save_settings_to_db(settings: dict) -> bool:
    """Persist given settings dict into DB. Returns True on success."""
    ensure_settings_table()
    cur = mydb.cursor()
    try:
        # Use INSERT OR REPLACE for upsert semantics
        if "team_size" in settings:
            cur.execute(f"INSERT OR REPLACE INTO {_TABLE_NAME} (key, value) VALUES (?, ?)", ("team_size", str(int(settings["team_size"]))))
        if "seasons_enabled" in settings:
            cur.execute(f"INSERT OR REPLACE INTO {_TABLE_NAME} (key, value) VALUES (?, ?)", ("seasons_enabled", "1" if settings["seasons_enabled"] else "0"))
        mydb.commit()
        return True
    except Exception as e:
        try:
            mydb.rollback()
        except Exception:
            pass
        print("Failed to save settings to DB:", e)
        return False
    finally:
        try:
            cur.close()
        except Exception:
            pass

# -----------------------
# Public API
# -----------------------
def get_settings():
    """Return current settings dict (typed values)."""
    return load_settings_from_db()

def save_settings(settings: dict) -> bool:
    """Persist settings dict into DB. Returns True on success."""
    # Basic validation/coercion
    s = {}
    if "team_size" in settings:
        try:
            s["team_size"] = int(settings["team_size"])
        except Exception:
            s["team_size"] = _DEFAULTS["team_size"]
    if "seasons_enabled" in settings:
        s["seasons_enabled"] = bool(settings["seasons_enabled"])
    return save_settings_to_db(s)

# -----------------------
# UI: Settings popup
# -----------------------
# Track the last popup so we can close it before opening another (single instance)
_last_popup_window = None

def open_settings_popup(parent=None):
    """
    Open a modal settings dialog (CTkToplevel). Parent should be the main app window.

    When settings are saved:
      - show message "Settings have been saved. Please log in again."
      - close the settings popup
      - call mainGui.show_login_screen() so the login UI becomes the only UI visible
        (this resets the main window contents to the login screen).
    """
    global _last_popup_window

    # If an existing settings popup exists, destroy it first
    try:
        if _last_popup_window is not None:
            try:
                if hasattr(_last_popup_window, "winfo_exists") and _last_popup_window.winfo_exists():
                    _last_popup_window.destroy()
            except Exception:
                pass
            _last_popup_window = None
    except Exception:
        _last_popup_window = None

    # Load current settings (safely)
    try:
        settings = get_settings()
    except Exception:
        settings = dict(_DEFAULTS)

    win = ctk.CTkToplevel(parent) if parent is not None else ctk.CTkToplevel()
    win.title("Settings")
    win.geometry("420x200")
    try:
        win.transient(parent)
    except Exception:
        pass
    try:
        win.grab_set()
    except Exception:
        pass

    # Ensure we clear _last_popup_window when this window is closed by the user (WM close)
    def _on_close():
        global _last_popup_window
        try:
            win.destroy()
        except Exception:
            pass
        _last_popup_window = None

    try:
        win.protocol("WM_DELETE_WINDOW", _on_close)
    except Exception:
        pass

    content = ctk.CTkFrame(win)
    content.pack(fill="both", expand=True, padx=12, pady=12)

    # Team size
    ctk.CTkLabel(content, text="Team size (players per team):").pack(anchor="w", pady=(6,4))
    team_size_var = ctk.StringVar(value=str(settings.get("team_size", _DEFAULTS["team_size"])))
    team_size_entry = ctk.CTkEntry(content, textvariable=team_size_var, width=120)
    team_size_entry.pack(anchor="w", pady=(0,8))

    # Seasons indicator
    seasons_var = ctk.BooleanVar(value=bool(settings.get("seasons_enabled", _DEFAULTS["seasons_enabled"])))
    seasons_chk = ctk.CTkCheckBox(content, text="Enable seasons indicator", variable=seasons_var)
    seasons_chk.pack(anchor="w", pady=(6,8))

    # Validation helper
    def _validate_team_size():
        val = team_size_var.get().strip()
        if not val:
            messagebox.showwarning("Validation", "Team size cannot be empty.")
            return None
        if not val.isdigit():
            messagebox.showwarning("Validation", "Team size must be a positive integer.")
            return None
        ival = int(val)
        if ival <= 0:
            messagebox.showwarning("Validation", "Team size must be greater than zero.")
            return None
        if ival > 500:
            if not messagebox.askyesno("Large value", "Team size is large (>500). Continue?"):
                return None
        return ival

    # Buttons
    btn_frame = ctk.CTkFrame(content, fg_color="#2A2A2A")
    btn_frame.pack(side="bottom", fill="x", pady=(12,0))

    def on_cancel():
        try:
            win.destroy()
        except Exception:
            pass

    def on_save():
        ival = _validate_team_size()
        if ival is None:
            return
        new_settings = {
            "team_size": ival,
            "seasons_enabled": bool(seasons_var.get())
        }
        ok = save_settings(new_settings)
        if ok:
            # Inform user they must log in again
            try:
                messagebox.showinfo("Settings Saved", "Settings have been saved. Please log in again.")
            except Exception:
                pass

            # Close the settings popup
            try:
                win.destroy()
            except Exception:
                pass

            # Clear the tracked popup reference
            global _last_popup_window
            _last_popup_window = None

            # Attempt to reset the main UI to the login screen.
            # Import mainGui here (deferred to avoid circular import at module load time).
            try:
                import mainGui as mg
                # Call the show_login_screen function which rebuilds the main window content to the login screen.
                if hasattr(mg, "show_login_screen"):
                    try:
                        mg.show_login_screen()
                        # bring main window to front if possible
                        try:
                            if hasattr(mg, "app") and mg.app:
                                try:
                                    mg.app.deiconify()
                                    mg.app.lift()
                                    mg.app.focus_force()
                                except Exception:
                                    pass
                        except Exception:
                            pass
                    except Exception:
                        # If calling show_login_screen fails, try to destroy the main window so only a new login may be created by the app restart.
                        try:
                            if hasattr(mg, "app") and mg.app:
                                mg.app.destroy()
                        except Exception:
                            pass
                else:
                    # If mainGui doesn't expose show_login_screen, try to destroy the main window so user will restart app
                    try:
                        if hasattr(mg, "app") and mg.app:
                            mg.app.destroy()
                    except Exception:
                        pass
            except Exception:
                # If we can't import mainGui, notify the user that they should restart the app.
                try:
                    messagebox.showinfo("Restart Required", "Settings saved but the application could not be reset programmatically. Please restart the application to apply changes.")
                except Exception:
                    pass
        else:
            messagebox.showerror("Settings", "Failed to save settings.")

    ctk.CTkButton(btn_frame, text="Save", command=on_save, width=100).pack(side="right", padx=(6,12), pady=8)
    ctk.CTkButton(btn_frame, text="Cancel", command=on_cancel, width=100).pack(side="right", padx=6, pady=8)

    # attach variables for external inspection if needed
    win._settings_vars = {
        "team_size_var": team_size_var,
        "seasons_var": seasons_var
    }

    # store reference so subsequent calls can destroy this window first
    _last_popup_window = win

    return win
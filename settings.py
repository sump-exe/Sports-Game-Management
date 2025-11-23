"""
Minimal DB-backed settings module.

Purpose:
- Persist one setting: team_size (int).
- Provide an open_settings_popup(parent) that:
    * validates and saves the setting to DB
    * closes the settings popup
    * calls any registered on-change callbacks so callers (mainGui/scheduleGameTab)
      can update UI in-place. This avoids importing mainGui inside settings
      and prevents accidental creation of new root windows.
"""
import customtkinter as ctk
from tkinter import messagebox
from theDB import mydb

# Defaults
_DEFAULTS = {
    "team_size": 12
}
_TABLE_NAME = "app_settings"

_last_popup = None

# Callbacks registered by other modules to be invoked after settings are saved.
_on_change_callbacks = []


# -----------------------
# Callback registration API
# -----------------------
def register_on_change(callback):
    """
    Register a zero-argument callback to be invoked when settings are changed.
    Callbacks are best-effort; exceptions are caught and ignored so UI won't crash.
    """
    if callable(callback):
        _on_change_callbacks.append(callback)


def _invoke_on_change_callbacks():
    for cb in list(_on_change_callbacks):
        try:
            cb()
        except Exception:
            # swallow exceptions to avoid crashing the save flow
            pass


# -----------------------
# DB helpers
# -----------------------
def _ensure_table():
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


def _load_all_from_db():
    _ensure_table()
    cur = mydb.cursor()
    try:
        cur.execute(f"SELECT key, value FROM {_TABLE_NAME}")
        rows = cur.fetchall()
        out = {}
        for k, v in rows:
            out[k] = v
        return out
    finally:
        try:
            cur.close()
        except Exception:
            pass


def _save_key_value(key, value):
    _ensure_table()
    cur = mydb.cursor()
    try:
        cur.execute(f"INSERT OR REPLACE INTO {_TABLE_NAME} (key, value) VALUES (?, ?)", (key, str(value)))
        mydb.commit()
        return True
    except Exception:
        try:
            mydb.rollback()
        except Exception:
            pass
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
    raw = _load_all_from_db()
    out = {}
    ts = raw.get("team_size")
    try:
        out["team_size"] = int(ts) if ts is not None else _DEFAULTS["team_size"]
    except Exception:
        out["team_size"] = _DEFAULTS["team_size"]
    return out


def save_settings(settings: dict) -> bool:
    ok = True
    if "team_size" in settings:
        try:
            ts = int(settings["team_size"])
        except Exception:
            ts = _DEFAULTS["team_size"]
        ok = ok and _save_key_value("team_size", ts)
    if ok:
        # If save succeeded, notify registered callbacks so UI can update in-place.
        try:
            _invoke_on_change_callbacks()
        except Exception:
            pass
    return bool(ok)


# -----------------------
# UI: settings popup
# -----------------------
def open_settings_popup(parent=None):
    """Open the Settings popup (team size only).
    Safe version: NO grab_set(), NO grab_release(), avoids logout misfire.
    """

    global _last_popup

    # Close any existing popup
    if _last_popup is not None:
        if hasattr(_last_popup, "winfo_exists") and _last_popup.winfo_exists():
            try:
                _last_popup.destroy()
            except Exception:
                pass
        _last_popup = None

    # Create popup
    win = ctk.CTkToplevel(parent) if parent else ctk.CTkToplevel()
    win.title("Settings")
    win.geometry("320x160")
    win.resizable(False, False)

    # Keep popup above parent but without grab_set()
    try:
        if parent:
            win.transient(parent)     # attach window visually to parent
        win.lift()                    # raise window
        win.attributes("-topmost", True)
        win.after(50, lambda: win.attributes("-topmost", False))
    except Exception:
        pass

    # Store reference
    _last_popup = win

    # ======================================================
    # UI
    # ======================================================
    title = ctk.CTkLabel(win, text="Settings", font=ctk.CTkFont(size=18, weight="bold"))
    title.pack(pady=(12, 6))

    # Frame
    frm = ctk.CTkFrame(win)
    frm.pack(padx=16, pady=8, fill="both", expand=True)

    # Team size
    ctk.CTkLabel(frm, text="Team Size:").grid(row=0, column=0, sticky="w", pady=6)
    team_size_entry = ctk.CTkEntry(frm, width=80)
    team_size_entry.grid(row=0, column=1, sticky="w", pady=6)

    # Load saved settings
    try:
        cur_settings = get_settings()
    except Exception:
        cur_settings = {}
    if cur_settings:
        team_size_entry.insert(0, str(cur_settings.get("team_size", "")))

    # ======================================================
    # Save handler
    # ======================================================
    def _validate_team_size_val(text):
        try:
            ts_val = int(text)
            return ts_val > 0
        except Exception:
            return False

    def _on_save_clicked():
        txt = team_size_entry.get().strip()
        if not _validate_team_size_val(txt):
            messagebox.showerror("Invalid Input", "Team size must be a positive integer.")
            return
        ts_val = int(txt)

        # Persist settings using this module's save_settings
        ok = save_settings({"team_size": ts_val})
        if not ok:
            messagebox.showerror("Settings", "Failed to save settings.")
            return

        # Inform user and close popup
        try:
            messagebox.showinfo("Settings Saved", "Settings have been saved and applied.")
        except Exception:
            pass

        try:
            if hasattr(win, "destroy"):
                win.destroy()
        except Exception:
            pass

        # Clear tracked popup ref
        global _last_popup
        _last_popup = None

    # Footer buttons
    btn_frame = ctk.CTkFrame(win, fg_color="transparent")
    btn_frame.pack(pady=8)

    ctk.CTkButton(btn_frame, text="Save", width=80, command=_on_save_clicked).grid(row=0, column=0, padx=10)
    ctk.CTkButton(btn_frame, text="Cancel", width=80, command=lambda: win.destroy()).grid(row=0, column=1, padx=10)

    return win
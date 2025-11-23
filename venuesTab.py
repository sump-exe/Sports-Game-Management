import customtkinter as ctk
from tkinter import messagebox
from datetime import datetime
from theDB import *

# NOTE: This module doesn't import mainGui or other UI modules to avoid circular imports.
# mainGui.py will set the following attributes on this module after importing it:
#   app, sched_mgr, refs, update_schedule_optionmenus
#
app = None
sched_mgr = None
refs = {}
update_schedule_optionmenus = lambda *a, **k: None

# tab 2 - venues

# Data stores
venues = {}  # { "VenueName": {"address": str, "capacity": int, "available": bool} }

def load_venues_from_db():
    """Populate the in-memory `venues` dict from the DB (venueName -> {address, capacity, available})."""
    venues.clear()
    cur = sched_mgr.mydb.cursor()
    cur.execute("SELECT id, venueName, location, capacity FROM venues ORDER BY venueName")
    rows = cur.fetchall()
    for r in rows:
        venues[r['venueName']] = {"address": r['location'], "capacity": r['capacity'], "available": True}
    cur.close()

def refresh_venue_sidebar(sidebar_scrollable, venue_buttons_list, search_var=None):
    """Rebuild venue buttons in sidebar, with optional filtering"""
    for btn in list(venue_buttons_list):
        try:
            btn.destroy()
        except Exception:
            pass
    venue_buttons_list.clear()

    venue_names = list(venues.keys())
    if search_var and search_var.get().strip():
        query = search_var.get().strip().lower()
        filtered = []
        for v in venue_names:
            data = venues.get(v, {})
            address = str(data.get("address", "")).lower()
            capacity = str(data.get("capacity", ""))
            # match by name, address (location) or capacity (partial match allowed)
            if query in v.lower() or query in address or query in capacity:
                filtered.append(v)
        venue_names = filtered

    # Sort if needed (default alphabetical)
    venue_names.sort()

    for v in venue_names:
        b = ctk.CTkButton(sidebar_scrollable, text=f"🏟️ {v}", width=260, height=35,
                          command=lambda name=v: show_venue_details(name),
                          hover_color="#4A90E2", fg_color="#2E2E2E")
        b.pack(padx=8, pady=4, fill="x")
        venue_buttons_list.append(b)

def show_venue_details(venue_name):
    # clear details area
    frame = refs.get('venue_details_frame')
    if not frame:
        return
    for w in frame.winfo_children():
        w.destroy()

    v = venues.get(venue_name, {"address": "", "capacity": ""})
    ctk.CTkLabel(frame, text=f"🏟️ {venue_name}", font=ctk.CTkFont(size=18, weight="bold")).pack(pady=(8,10))

    ctk.CTkLabel(frame, text=f"Address: {v['address']}", anchor="w").pack(fill="x", padx=12, pady=4)
    ctk.CTkLabel(frame, text=f"Capacity: {v['capacity']}", anchor="w").pack(fill="x", padx=12, pady=4)

    # availability toggle
    avail_var = ctk.BooleanVar(value=v.get("available", True))
    def toggle_avail():
        venues[venue_name]["available"] = avail_var.get()
        update_schedule_optionmenus(refs.get('tab3_team1_opt'), refs.get('tab3_team2_opt'), refs.get('tab3_venue_opt'))
    chk = ctk.CTkCheckBox(frame, text="Available", variable=avail_var, command=toggle_avail)
    chk.pack(pady=12)

    # Edit / Delete buttons
    btn_frame = ctk.CTkFrame(frame, fg_color="#333333")
    btn_frame.pack(pady=10, padx=8, fill="x")

    def edit_venue():
        open_add_venue_popup(prefill_name=venue_name)

    def delete_venue():
        if messagebox.askyesno("Delete Venue", f"Delete '{venue_name}'?"):
            venues.pop(venue_name, None)
            try:
                refresh_venue_sidebar(refs.get('venues_sidebar_scroll'), refs.get('venues_buttons'), refs.get('venues_search_var'))
            except Exception:
                pass
            # clear details
            for w in frame.winfo_children():
                w.destroy()
            update_schedule_optionmenus(refs.get('tab3_team1_opt'), refs.get('tab3_team2_opt'), refs.get('tab3_venue_opt'))

    edit_btn = ctk.CTkButton(btn_frame, text="Edit", command=edit_venue, hover_color="#FFA500")
    edit_btn.pack(side="left", expand=True, padx=8, pady=8)

    delete_btn = ctk.CTkButton(btn_frame, text="Delete", command=delete_venue, hover_color="#FF4500")
    delete_btn.pack(side="right", expand=True, padx=8, pady=8)

def open_add_venue_popup(prefill_name=None):
    win = ctk.CTkToplevel(app)
    win.title("Add / Edit Venue")
    win.geometry("420x260")
    win.transient(app)
    win.grab_set()

    ctk.CTkLabel(win, text="Venue Name:").pack(pady=(12,4), anchor="w", padx=12)
    name_entry = ctk.CTkEntry(win)
    name_entry.pack(fill="x", padx=12)
    ctk.CTkLabel(win, text="Address:").pack(pady=(8,4), anchor="w", padx=12)
    addr_entry = ctk.CTkEntry(win)
    addr_entry.pack(fill="x", padx=12)
    ctk.CTkLabel(win, text="Capacity:").pack(pady=(8,4), anchor="w", padx=12)
    cap_entry = ctk.CTkEntry(win)
    cap_entry.pack(fill="x", padx=12)

    editing = False
    original_name = None
    if prefill_name:
        editing = True
        original_name = prefill_name
        data = venues.get(prefill_name, {})
        name_entry.insert(0, prefill_name)
        addr_entry.insert(0, data.get("address", ""))
        cap_entry.insert(0, str(data.get("capacity", "")))

    def save_venue():
        name = name_entry.get().strip()
        addr = addr_entry.get().strip()
        cap = cap_entry.get().strip()
        if not name or not addr or not cap.isdigit():
            messagebox.showwarning("Error", "Please fill all fields correctly.")
            return
        cap_int = int(cap)

        if editing and original_name and original_name != name:
            # rename: remove old key
            venues.pop(original_name, None)
        # create Venue object and save to DB
        try:
            v = Venue(name, addr, cap_int)
            sched_mgr.addVenue(v)
        except Exception:
            messagebox.showwarning("Error", "Could not save venue (it may already exist).")
            return
        # reload venues from DB and refresh UI
        load_venues_from_db()
        try:
            refresh_venue_sidebar(refs.get('venues_sidebar_scroll'), refs.get('venues_buttons'), refs.get('venues_search_var'))
        except Exception:
            pass
        update_schedule_optionmenus(refs.get('tab3_team1_opt'), refs.get('tab3_team2_opt'), refs.get('tab3_venue_opt'))
        win.destroy()

    ctk.CTkButton(win, text="Save Venue", command=save_venue).pack(pady=12)
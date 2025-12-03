import customtkinter as ctk
from tkinter import messagebox
from datetime import datetime
from theDB import *

app = None
sched_mgr = None
refs = {}
update_schedule_optionmenus = lambda *a, **k: None

venues = {}

def load_venues_from_db():
    venues.clear()
    cur = sched_mgr.mydb.cursor()
    cur.execute("SELECT id, venueName, location, capacity FROM venues ORDER BY venueName")
    rows = cur.fetchall()
    for r in rows:
        venues[r['venueName']] = {"address": r['location'], "capacity": r['capacity']}
    cur.close()

def refresh_venue_sidebar(sidebar_scrollable, venue_buttons_list, search_var=None):
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
            if query in v.lower() or query in address or query in capacity:
                filtered.append(v)
        venue_names = filtered

    venue_names.sort()

    for v in venue_names:
        b = ctk.CTkButton(sidebar_scrollable, text=f"🏟️ {v}", width=260, height=35,
                          command=lambda name=v: show_venue_details(name),
                          hover_color="#4A90E2", fg_color="#2E2E2E")
        b.pack(padx=8, pady=4, fill="x")
        venue_buttons_list.append(b)

def show_venue_details(venue_name):
    frame = refs.get('venue_details_frame')
    if not frame:
        return
    for w in frame.winfo_children():
        w.destroy()

    # --- Scrollable Container ---
    scroll_frame = ctk.CTkScrollableFrame(frame, fg_color="transparent")
    scroll_frame.pack(fill="both", expand=True)

    v = venues.get(venue_name, {"address": "", "capacity": ""})
    
    # --- Venue Info ---
    ctk.CTkLabel(scroll_frame, text=f"🏟️ {venue_name}", font=ctk.CTkFont(size=20, weight="bold")).pack(pady=(12,10))

    info_frame = ctk.CTkFrame(scroll_frame, fg_color="transparent")
    info_frame.pack(fill="x", padx=12, pady=4)
    
    ctk.CTkLabel(info_frame, text=f"📍 Address: {v['address']}", anchor="w", font=ctk.CTkFont(size=14)).pack(fill="x", pady=2)
    ctk.CTkLabel(info_frame, text=f"👥 Capacity: {v['capacity']}", anchor="w", font=ctk.CTkFont(size=14)).pack(fill="x", pady=2)

    # --- Buttons ---
    btn_frame = ctk.CTkFrame(scroll_frame, fg_color="#333333")
    btn_frame.pack(pady=12, padx=12, fill="x")

    def edit_venue():
        open_add_venue_popup(prefill_name=venue_name)

    def delete_venue():
        if messagebox.askyesno("Delete Venue", f"Delete '{venue_name}'?"):
            venues.pop(venue_name, None)
            cur = sched_mgr.mydb.cursor()
            try:
                # Delete from DB by name
                cur.execute("DELETE FROM venues WHERE venueName = ?", (venue_name,))
                sched_mgr.mydb.commit()
            except Exception as e:
                print(f"Error deleting venue: {e}")
            finally:
                cur.close()

            try:
                refresh_venue_sidebar(refs.get('venues_sidebar_scroll'), refs.get('venues_buttons'), refs.get('venues_search_var'))
            except Exception:
                pass
            for w in frame.winfo_children():
                w.destroy()
            update_schedule_optionmenus(refs.get('tab3_team1_opt'), refs.get('tab3_team2_opt'), refs.get('tab3_venue_opt'))

    edit_btn = ctk.CTkButton(btn_frame, text="Edit", command=edit_venue, hover_color="#FFA500", width=100)
    edit_btn.pack(side="left", padx=12, pady=10)

    delete_btn = ctk.CTkButton(btn_frame, text="Delete", command=delete_venue, hover_color="#FF4500", width=100, fg_color="#D9534F")
    delete_btn.pack(side="right", padx=12, pady=10)

    # --- Scheduled Games List ---
    ctk.CTkLabel(scroll_frame, text="Scheduled Games", font=ctk.CTkFont(size=16, weight="bold")).pack(pady=(20, 8), anchor="w", padx=12)

    # Fetch games for this venue
    cur = sched_mgr.mydb.cursor()
    games_list = []
    try:
        query = """
            SELECT 
                t1.teamName as team1, 
                t2.teamName as team2, 
                g.game_date, 
                g.start_time, 
                g.end_time
            FROM games g
            JOIN venues v ON g.venue_id = v.id
            LEFT JOIN teams t1 ON g.team1_id = t1.id
            LEFT JOIN teams t2 ON g.team2_id = t2.id
            WHERE v.venueName = ?
            ORDER BY g.game_date DESC, g.start_time DESC
        """
        cur.execute(query, (venue_name,))
        games_list = cur.fetchall()
    except Exception as e:
        print(f"Error fetching venue games: {e}")
    finally:
        cur.close()

    if not games_list:
        ctk.CTkLabel(scroll_frame, text="No games scheduled here.", text_color="#AAAAAA").pack(pady=10)
    else:
        # Table Header
        header_row = ctk.CTkFrame(scroll_frame, fg_color="#2A2A2A")
        header_row.pack(fill="x", padx=12, pady=(0, 4))
        header_row.grid_columnconfigure(0, weight=2) # Teams
        header_row.grid_columnconfigure(1, weight=1) # Date
        header_row.grid_columnconfigure(2, weight=1) # Time

        ctk.CTkLabel(header_row, text="Matchup", font=ctk.CTkFont(weight="bold")).grid(row=0, column=0, pady=6, padx=8, sticky="w")
        ctk.CTkLabel(header_row, text="Date", font=ctk.CTkFont(weight="bold")).grid(row=0, column=1, pady=6, padx=8, sticky="w")
        ctk.CTkLabel(header_row, text="Time", font=ctk.CTkFont(weight="bold")).grid(row=0, column=2, pady=6, padx=8, sticky="w")

        # Table Rows
        for g in games_list:
            row = ctk.CTkFrame(scroll_frame, fg_color="#1F1F1F")
            row.pack(fill="x", padx=12, pady=2)
            row.grid_columnconfigure(0, weight=2)
            row.grid_columnconfigure(1, weight=1)
            row.grid_columnconfigure(2, weight=1)

            t1 = g['team1'] or "Unknown"
            t2 = g['team2'] or "Unknown"
            date = g['game_date']
            start = g['start_time'] or "00:00"
            end = g['end_time'] or "00:00"

            ctk.CTkLabel(row, text=f"{t1} vs {t2}").grid(row=0, column=0, pady=6, padx=8, sticky="w")
            ctk.CTkLabel(row, text=date).grid(row=0, column=1, pady=6, padx=8, sticky="w")
            ctk.CTkLabel(row, text=f"{start} - {end}").grid(row=0, column=2, pady=6, padx=8, sticky="w")

def open_add_venue_popup(prefill_name=None):
    win = ctk.CTkToplevel(app)
    win.title("Add / Edit Venue")
    win.geometry("420x260")
    win.transient(app)

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
        
        if not name or not addr:
            messagebox.showwarning("Error", "Please fill name and address.")
            return
            
        if not cap.isdigit():
            messagebox.showwarning("Error", "Capacity must be a valid integer.")
            return

        cap_int = int(cap)
        if cap_int <= 0:
            messagebox.showwarning("Invalid Capacity", "Capacity must be greater than 0.")
            return

        cur = sched_mgr.mydb.cursor()
        try:
            if editing:
                # 1. Get ID of the venue we are editing using original_name
                cur.execute("SELECT id FROM venues WHERE venueName = ?", (original_name,))
                row = cur.fetchone()
                if not row:
                    messagebox.showerror("Error", "Original venue not found in DB.")
                    return
                vid = row['id']

                # 2. Check if new name exists (only if name changed)
                if name != original_name:
                    cur.execute("SELECT 1 FROM venues WHERE venueName = ?", (name,))
                    if cur.fetchone():
                        messagebox.showwarning("Error", f"Venue '{name}' already exists.")
                        return

                # 3. Update existing record
                cur.execute("""
                    UPDATE venues 
                    SET venueName = ?, location = ?, capacity = ? 
                    WHERE id = ?
                """, (name, addr, cap_int, vid))
                sched_mgr.mydb.commit()
            
            else:
                # Adding new venue
                # Check for duplicate name
                cur.execute("SELECT 1 FROM venues WHERE venueName = ?", (name,))
                if cur.fetchone():
                    messagebox.showwarning("Error", f"Venue '{name}' already exists.")
                    return

                v = Venue(name, addr, cap_int)
                sched_mgr.addVenue(v)

        except Exception as e:
            messagebox.showerror("Error", f"Database error: {e}")
            return
        finally:
            cur.close()

        load_venues_from_db()
        try:
            refresh_venue_sidebar(refs.get('venues_sidebar_scroll'), refs.get('venues_buttons'), refs.get('venues_search_var'))
            
            if editing and original_name and refs.get('venue_details_frame'):
                show_venue_details(name)

        except Exception:
            pass
        update_schedule_optionmenus(refs.get('tab3_team1_opt'), refs.get('tab3_team2_opt'), refs.get('tab3_venue_opt'))
        win.destroy()

    ctk.CTkButton(win, text="Save Venue", command=save_venue).pack(pady=12)
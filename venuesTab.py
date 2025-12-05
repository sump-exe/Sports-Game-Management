import customtkinter as ctk
from tkinter import messagebox
from theDB import *

app = None
sched_mgr = None
refs = {}
update_schedule_optionmenus = lambda *a, **k: None

venues = {}

class VenueSidebarManager:
    def __init__(self):
        self.buttons_list = []

    def load_data(self):
        venues.clear()
        cur = sched_mgr.mydb.cursor()
        try:
            cur.execute("SELECT id, venueName, location, capacity FROM venues ORDER BY venueName")
            rows = cur.fetchall()
            for r in rows:
                venues[r['venueName']] = {
                    "address": r['location'], 
                    "capacity": r['capacity']
                }
        except Exception as e:
            print(f"Error loading venues: {e}")
        finally:
            cur.close()

    def refresh_sidebar_ui(self, scroll_frame, search_var=None):
        try:
            parent = scroll_frame.master
            add_btn = None
            
            for child in parent.winfo_children():
                if isinstance(child, ctk.CTkButton) and "Add Venue" in child.cget("text"):
                    add_btn = child
                    break
            
            if add_btn:
                add_btn.pack_forget()
                scroll_frame.pack_forget()
                
                add_btn.pack(side="bottom", pady=8, padx=6, fill="x")
                
                scroll_frame.pack(side="top", fill="both", expand=True, padx=6, pady=6)
        except Exception:
            pass
        for btn in list(self.buttons_list):
            try:
                btn.destroy()
            except Exception:
                pass
        self.buttons_list.clear()

        venue_names = sorted(list(venues.keys()))

        if search_var:
            query_text = search_var.get() if hasattr(search_var, 'get') else str(search_var)
            query = query_text.strip().lower()

            if query:
                filtered = []
                for v in venue_names:
                    data = venues.get(v, {})
                    
                    v_name_str = str(v).lower()
                    addr_str = str(data.get("address", "")).lower()
                    cap_str = str(data.get("capacity", ""))
                    
                    if (query in v_name_str) or (query in addr_str) or (query in cap_str):
                        filtered.append(v)
                venue_names = filtered

        for v in venue_names:
            b = ctk.CTkButton(
                scroll_frame, 
                text=f"🏟️ {v}", 
                width=260, 
                height=35,
                command=lambda name=v: _show_details_wrapper(name),
                hover_color="#4A90E2", 
                fg_color="#2E2E2E"
            )
            b.pack(padx=8, pady=4, fill="x")
            self.buttons_list.append(b)

class VenueDetailsViewer:
    def __init__(self, parent_frame):
        self.parent = parent_frame

    def show_details(self, venue_name):
        for w in self.parent.winfo_children():
            w.destroy()

        scroll_frame = ctk.CTkScrollableFrame(self.parent, fg_color="transparent")
        scroll_frame.pack(fill="both", expand=True)

        v_data = venues.get(venue_name, {"address": "", "capacity": ""})
        
        ctk.CTkLabel(scroll_frame, text=f"🏟️ {venue_name}", font=ctk.CTkFont(size=20, weight="bold")).pack(pady=(12,10))

        info_frame = ctk.CTkFrame(scroll_frame, fg_color="transparent")
        info_frame.pack(fill="x", padx=12, pady=4)
        
        ctk.CTkLabel(info_frame, text=f"📍 Address: {v_data['address']}", anchor="w", font=ctk.CTkFont(size=14)).pack(fill="x", pady=2)
        ctk.CTkLabel(info_frame, text=f"👥 Capacity: {v_data['capacity']}", anchor="w", font=ctk.CTkFont(size=14)).pack(fill="x", pady=2)

        btn_frame = ctk.CTkFrame(scroll_frame, fg_color="#333333")
        btn_frame.pack(pady=12, padx=12, fill="x")

        edit_btn = ctk.CTkButton(btn_frame, text="Edit", hover_color="#FFA500", width=100,
                                 command=lambda: open_add_venue_popup(prefill_name=venue_name))
        edit_btn.pack(side="left", padx=12, pady=10)

        delete_btn = ctk.CTkButton(btn_frame, text="Delete", hover_color="#FF4500", width=100, fg_color="#D9534F",
                                   command=lambda: self._delete_venue_logic(venue_name))
        delete_btn.pack(side="right", padx=12, pady=10)

        ctk.CTkLabel(scroll_frame, text="Scheduled Games", font=ctk.CTkFont(size=16, weight="bold")).pack(pady=(20, 8), anchor="w", padx=12)
        self._render_games_list(venue_name, scroll_frame)

    def _render_games_list(self, venue_name, container):
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
            ctk.CTkLabel(container, text="No games scheduled here.", text_color="#AAAAAA").pack(pady=10)
        else:
            header_row = ctk.CTkFrame(container, fg_color="#2A2A2A")
            header_row.pack(fill="x", padx=12, pady=(0, 4))
            header_row.grid_columnconfigure(0, weight=2)
            header_row.grid_columnconfigure(1, weight=1)
            header_row.grid_columnconfigure(2, weight=1)

            ctk.CTkLabel(header_row, text="Matchup", font=ctk.CTkFont(weight="bold")).grid(row=0, column=0, pady=6, padx=8, sticky="w")
            ctk.CTkLabel(header_row, text="Date", font=ctk.CTkFont(weight="bold")).grid(row=0, column=1, pady=6, padx=8, sticky="w")
            ctk.CTkLabel(header_row, text="Time", font=ctk.CTkFont(weight="bold")).grid(row=0, column=2, pady=6, padx=8, sticky="w")

            for g in games_list:
                row = ctk.CTkFrame(container, fg_color="#1F1F1F")
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

    def _delete_venue_logic(self, venue_name):
        if messagebox.askyesno("Delete Venue", f"Delete '{venue_name}'?"):
            venues.pop(venue_name, None)
            cur = sched_mgr.mydb.cursor()
            try:
                cur.execute("DELETE FROM venues WHERE venueName = ?", (venue_name,))
                sched_mgr.mydb.commit()
            except Exception as e:
                print(f"Error deleting venue: {e}")
            finally:
                cur.close()

            try:
                _sidebar_mgr.refresh_sidebar_ui(
                    refs.get('venues_sidebar_scroll'), 
                    refs.get('venues_search_var')
                )
            except Exception:
                pass
            
            for w in self.parent.winfo_children():
                w.destroy()
            
            update_schedule_optionmenus(
                refs.get('tab3_team1_opt'), 
                refs.get('tab3_team2_opt'), 
                refs.get('tab3_venue_opt')
            )

class VenueControlPanel:
    def open_popup(self, prefill_name=None):
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
                    cur.execute("SELECT id FROM venues WHERE venueName = ?", (original_name,))
                    row = cur.fetchone()
                    if not row:
                        messagebox.showerror("Error", "Original venue not found in DB.")
                        return
                    vid = row['id']

                    if name != original_name:
                        cur.execute("SELECT 1 FROM venues WHERE venueName = ?", (name,))
                        if cur.fetchone():
                            messagebox.showwarning("Error", f"Venue '{name}' already exists.")
                            return

                    cur.execute("""
                        UPDATE venues 
                        SET venueName = ?, location = ?, capacity = ? 
                        WHERE id = ?
                    """, (name, addr, cap_int, vid))
                    sched_mgr.mydb.commit()
                
                else:
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

            _sidebar_mgr.load_data()
            try:
                _sidebar_mgr.refresh_sidebar_ui(
                    refs.get('venues_sidebar_scroll'), 
                    refs.get('venues_search_var')
                )
                
                if editing and original_name and refs.get('venue_details_frame'):
                    _show_details_wrapper(name)

            except Exception:
                pass
            
            update_schedule_optionmenus(
                refs.get('tab3_team1_opt'), 
                refs.get('tab3_team2_opt'), 
                refs.get('tab3_venue_opt')
            )
            win.destroy()

        ctk.CTkButton(win, text="Save Venue", command=save_venue).pack(pady=12)

_sidebar_mgr = VenueSidebarManager()
_controls = VenueControlPanel()

def load_venues_from_db():
    _sidebar_mgr.load_data()

def refresh_venue_sidebar(sidebar_scrollable, venue_buttons_list, search_var=None):
    _sidebar_mgr.refresh_sidebar_ui(sidebar_scrollable, search_var)
    
    if isinstance(venue_buttons_list, list):
        venue_buttons_list.clear()
        venue_buttons_list.extend(_sidebar_mgr.buttons_list)

def show_venue_details(venue_name):
    frame = refs.get('venue_details_frame')
    if not frame: return
    viewer = VenueDetailsViewer(frame)
    viewer.show_details(venue_name)

def open_add_venue_popup(prefill_name=None):
    _controls.open_popup(prefill_name)

def _show_details_wrapper(venue_name):
    show_venue_details(venue_name)
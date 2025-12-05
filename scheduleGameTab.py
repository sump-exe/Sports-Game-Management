import customtkinter as ctk
from tkinter import messagebox
from datetime import datetime, date as _date
from theDB import *

app = None
sched_mgr = None
refs = {}
teams = {}
venues = {}
scheduled_games = []

_current_preview_ui = None
_current_loader = None

class GameListLoader:
    def __init__(self, db_manager):
        self.mgr = db_manager

    def fetch_all_games(self):
        if not self.mgr: return []
        
        games_data = []
        cur = self.mgr.mydb.cursor()
        try:
            cur.execute(
                """
                SELECT 
                    g.id, g.team1_id, g.team2_id,
                    t1.teamName AS team1, t2.teamName AS team2,
                    v.venueName AS venue,
                    g.game_date, g.start_time, g.end_time
                FROM games g
                LEFT JOIN teams t1 ON g.team1_id = t1.id
                LEFT JOIN teams t2 ON g.team2_id = t2.id
                LEFT JOIN venues v ON g.venue_id = v.id
                ORDER BY g.game_date, g.start_time
                """
            )
            rows = cur.fetchall()
            for r in rows:
                games_data.append({
                    'id': r['id'],
                    'team1': r['team1'] if 'team1' in r.keys() else 'Unknown',
                    'team2': r['team2'] if 'team2' in r.keys() else 'Unknown',
                    'team1_id': r['team1_id'],
                    'team2_id': r['team2_id'],
                    'venue': r['venue'] if 'venue' in r.keys() else 'Unknown',
                    'date': r['game_date'],
                    'start': r['start_time'] or '00:00',
                    'end': r['end_time'] or '00:00'
                })
        except Exception as e:
            print(f"Error loading games: {e}")
        finally:
            cur.close()
        return games_data

    def get_regular_season_ranks(self, year_str, teams_dict):
        try:
            input_year = int(year_str)
            season_start_year = input_year - 1
        except ValueError:
            return []

        s_helper = Season()
        reg_start, reg_end = s_helper.get_range("Regular Season", season_start_year)
        if not reg_start or not reg_end: return []
        
        start_iso = reg_start.isoformat()
        end_iso = reg_end.isoformat()

        cur = self.mgr.mydb.cursor()
        ranked_teams = []
        try:
            valid_ids = []
            for t_name, t_roster in teams_dict.items():
                if len(t_roster) == 12:
                    cur.execute("SELECT id FROM teams WHERE teamName = ?", (t_name,))
                    r = cur.fetchone()
                    if r: valid_ids.append(r['id'])
            
            if not valid_ids: return []

            placeholders = ','.join(['?'] * len(valid_ids))
            query = f"""
                SELECT 
                    t.id, t.teamName,
                    (SELECT COUNT(*) FROM games g 
                     WHERE g.winner_team_id = t.id AND g.is_final = 1
                     AND g.game_date BETWEEN ? AND ?) as reg_wins,
                    COALESCE((SELECT SUM(
                        CASE WHEN g2.team1_id = t.id THEN COALESCE(g2.team1_score, 0) 
                        ELSE COALESCE(g2.team2_score, 0) END) 
                      FROM games g2 
                      WHERE (g2.team1_id = t.id OR g2.team2_id = t.id) 
                        AND g2.is_final = 1 AND g2.game_date BETWEEN ? AND ?), 0) as season_pts
                FROM teams t
                WHERE t.id IN ({placeholders})
                ORDER BY reg_wins DESC, season_pts DESC
            """
            params = [start_iso, end_iso, start_iso, end_iso] + valid_ids
            cur.execute(query, params)
            for r in cur.fetchall():
                ranked_teams.append({'id': r['id'], 'name': r['teamName']})
        finally:
            cur.close()
        return ranked_teams

    def analyze_playin_pairs(self, year_str, ranks):
        if len(ranks) < 10: return [], []

        try:
            year_val = int(year_str)
        except: return [], []

        s_helper = Season()
        pi_start, pi_end = s_helper.get_range("Play-in", year_val)
        
        seed7, seed8 = ranks[6], ranks[7]
        seed9, seed10 = ranks[8], ranks[9]

        def get_result(id_a, id_b):
            c = self.mgr.mydb.cursor()
            try:
                c.execute("""
                    SELECT winner_team_id FROM games 
                    WHERE ((team1_id=? AND team2_id=?) OR (team1_id=? AND team2_id=?))
                      AND game_date BETWEEN ? AND ? AND is_final=1
                """, (id_a, id_b, id_b, id_a, pi_start.isoformat(), pi_end.isoformat()))
                row = c.fetchone()
                if row: return True, row['winner_team_id'], (id_b if row['winner_team_id'] == id_a else id_a)
                return False, None, None
            finally:
                c.close()

        g78_done, g78_win, g78_lose = get_result(seed7['id'], seed8['id'])
        g910_done, g910_win, _ = get_result(seed9['id'], seed10['id'])

        pairs = []
        if not g78_done: pairs.append((seed7['name'], seed8['name']))
        if not g910_done: pairs.append((seed9['name'], seed10['name']))
        
        if g78_done and g910_done:
            gLast_done, _, _ = get_result(g78_lose, g910_win)
            if not gLast_done:
                l78 = next((t['name'] for t in ranks if t['id'] == g78_lose), "Unknown")
                w910 = next((t['name'] for t in ranks if t['id'] == g910_win), "Unknown")
                pairs.append((l78, w910))

        return pairs

    def check_conflicts(self, t1, t2, v, date_obj, start_dt, end_dt):
        cur = self.mgr.mydb.cursor()
        try:
            # Get IDs
            cur.execute("SELECT id FROM teams WHERE teamName=?", (t1,))
            r1 = cur.fetchone()
            cur.execute("SELECT id FROM teams WHERE teamName=?", (t2,))
            r2 = cur.fetchone()
            cur.execute("SELECT id FROM venues WHERE venueName=?", (v,))
            rv = cur.fetchone()
            
            if not r1 or not r2 or not rv: return "Teams or Venue not found."
            tid1, tid2, vid = r1['id'], r2['id'], rv['id']

            date_iso = date_obj.isoformat()
            
            for tid, tname in [(tid1, t1), (tid2, t2)]:
                cur.execute("""
                    SELECT v.venueName FROM games g JOIN venues v ON g.venue_id=v.id
                    WHERE g.game_date=? AND (g.team1_id=? OR g.team2_id=?) AND g.venue_id!=?
                """, (date_iso, tid, tid, vid))
                row = cur.fetchone()
                if row: return f"Team '{tname}' already playing at '{row['venueName']}' on this day."

            s_time = start_dt.time()
            e_time = end_dt.time()
            
            cur.execute("SELECT start_time, end_time FROM games WHERE game_date=? AND venue_id=?", (date_iso, vid))
            for row in cur.fetchall():
                if self._overlap(s_time, e_time, row['start_time'], row['end_time']):
                    return f"Venue '{v}' is booked during this time."

            for tid, tname in [(tid1, t1), (tid2, t2)]:
                cur.execute("""
                    SELECT start_time, end_time FROM games 
                    WHERE game_date=? AND (team1_id=? OR team2_id=?)
                """, (date_iso, tid, tid))
                for row in cur.fetchall():
                    if self._overlap(s_time, e_time, row['start_time'], row['end_time']):
                        return f"Team '{tname}' has a game during this time."

            return None
        finally:
            cur.close()

    def _overlap(self, s1, e1, db_s_str, db_e_str):
        db_s = datetime.strptime(db_s_str, "%H:%M").time()
        db_e = datetime.strptime(db_e_str, "%H:%M").time()
        return s1 < db_e and db_s < e1

    def save_game(self, t1, t2, v, date_obj, start_dt, end_dt):
        cur = self.mgr.mydb.cursor()
        try:
            cur.execute("SELECT id FROM teams WHERE teamName=?", (t1,))
            tid1 = cur.fetchone()['id']
            cur.execute("SELECT id FROM teams WHERE teamName=?", (t2,))
            tid2 = cur.fetchone()['id']
            cur.execute("SELECT id FROM venues WHERE venueName=?", (v,))
            vid = cur.fetchone()['id']

            gid = self.mgr.scheduleGame(tid1, tid2, vid, date_obj.isoformat())
            self.mgr.updateGame(gid, tid1, tid2, vid, date_obj.isoformat(), 
                                start_dt.strftime("%H:%M"), end_dt.strftime("%H:%M"))
            return True
        finally:
            cur.close()

    def is_date_within_season(self, date_obj, season, year_val):
        """Validates if a date falls within the defined season window."""
        if not season or season == "Select": return True, ""
        valid_ranges = []
        s_obj = Season()
        
        for y in (year_val, year_val - 1):
            start, end = s_obj.get_range(season, y)
            if start and end:
                if start <= date_obj <= end: return True, ""
                valid_ranges.append(f"{start.strftime('%b %d')} -> {end.strftime('%b %d')}")

        msg = "\nOR\n".join(valid_ranges) if valid_ranges else "No ranges found."
        return False, f"Date not in '{season}' window.\nAllowed:\n{msg}"


class GameSchedulePreview:
    def __init__(self, parent_frame, loader):
        self.parent = parent_frame
        self.loader = loader
        self.widgets = {}
        
        global _current_preview_ui
        _current_preview_ui = self

        self._build_ui()

    def _build_ui(self):
        frame = ctk.CTkFrame(self.parent)
        frame.pack(fill="both", expand=False, padx=10, pady=10)
        frame.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(frame, text="Season:").grid(row=0, column=0, sticky="w", pady=3)
        self.widgets['season'] = ctk.CTkOptionMenu(
            frame, values=["Pre-season", "Regular Season", "Play-in", "Playoff", "Finals", "Off-season"],
            command=lambda x: [self.reset_team_selections(), self.update_preview()]
        )
        self.widgets['season'].set("Regular Season")
        self.widgets['season'].grid(row=0, column=1, sticky="ew", pady=3)
        refs["tab3_season_opt"] = self.widgets['season'] # Compatibility

        ctk.CTkLabel(frame, text="Year:").grid(row=1, column=0, sticky="w", pady=3)
        self.widgets['year'] = ctk.CTkEntry(frame, placeholder_text=str(datetime.now().year))
        self.widgets['year'].grid(row=1, column=1, sticky="ew", pady=3)
        self.widgets['year'].bind("<KeyRelease>", lambda e: [self.reset_team_selections(), self.update_preview()])
        refs["tab3_year_entry"] = self.widgets['year']

        ctk.CTkLabel(frame, text="Month-Day (MM-DD):").grid(row=2, column=0, sticky="w", pady=3)
        self.widgets['date'] = ctk.CTkEntry(frame, placeholder_text="MM-DD (e.g. 03-15)")
        self.widgets['date'].grid(row=2, column=1, sticky="ew", pady=3)
        self.widgets['date'].bind("<KeyRelease>", lambda e: self.update_preview())
        refs["tab3_date_entry"] = self.widgets['date']

        ctk.CTkLabel(frame, text="Team 1:").grid(row=3, column=0, sticky="w", pady=3)
        self.widgets['t1'] = ctk.CTkOptionMenu(frame, values=["Select"], command=self.on_team1_select)
        self.widgets['t1'].grid(row=3, column=1, sticky="ew", pady=3)
        refs["tab3_team1_opt"] = self.widgets['t1']

        ctk.CTkLabel(frame, text="Team 2:").grid(row=4, column=0, sticky="w", pady=3)
        self.widgets['t2'] = ctk.CTkOptionMenu(frame, values=["Select"], command=lambda x: self.update_preview())
        self.widgets['t2'].grid(row=4, column=1, sticky="ew", pady=3)
        refs["tab3_team2_opt"] = self.widgets['t2']

        ctk.CTkLabel(frame, text="Venue:").grid(row=5, column=0, sticky="w", pady=3)
        self.widgets['venue'] = ctk.CTkOptionMenu(frame, values=["Select"], command=lambda x: self.update_preview())
        self.widgets['venue'].grid(row=5, column=1, sticky="ew", pady=3)
        refs["tab3_venue_opt"] = self.widgets['venue']

        ctk.CTkLabel(frame, text="Start Time (HH:MM):").grid(row=6, column=0, sticky="w", pady=3)
        self.widgets['start'] = ctk.CTkEntry(frame, placeholder_text="13:00")
        self.widgets['start'].grid(row=6, column=1, sticky="ew", pady=3)
        self.widgets['start'].bind("<KeyRelease>", lambda e: self.update_preview())
        refs["tab3_start_entry"] = self.widgets['start']

        ctk.CTkLabel(frame, text="End Time (HH:MM):").grid(row=7, column=0, sticky="w", pady=3)
        self.widgets['end'] = ctk.CTkEntry(frame, placeholder_text="15:00")
        self.widgets['end'].grid(row=7, column=1, sticky="ew", pady=3)
        self.widgets['end'].bind("<KeyRelease>", lambda e: self.update_preview())
        refs["tab3_end_entry"] = self.widgets['end']

        ctk.CTkButton(frame, text="Schedule Game", command=self.handle_save).grid(row=8, column=0, columnspan=2, pady=10, sticky="ew")

        self.refresh_dropdowns()

    def update_preview(self):
        lines = []
        season = self.widgets['season'].get()
        year = self.widgets['year'].get().strip()
        md = self.widgets['date'].get().strip()
        
        def fmt(l, v): return f"{l:<10} {v}"

        if season or year: lines.append(fmt("SEASON:", f"{season} {year}"))
        if md: lines.append(fmt("DATE:", md))
        
        start = self.widgets['start'].get().strip()
        end = self.widgets['end'].get().strip()
        if start: lines.append(fmt("TIME:", f"{start} - {end}"))
        
        venue = self.widgets['venue'].get()
        if venue and venue != "Select": lines.append(fmt("VENUE:", venue))
        
        t1 = self.widgets['t1'].get()
        t2 = self.widgets['t2'].get()
        matchup = ""
        if t1 and t1 != "Select" and t2 and t2 != "Select":
            matchup = f"\n\n{t1}\n      VS\n{t2}"
        
        final_text = "\n".join(lines) + matchup
        
        lbl = refs.get('game_preview_label') or refs.get('game_preview')
        if lbl:
            lbl.configure(
                text=final_text if final_text.strip() else "Fill details to preview...",
                font=ctk.CTkFont(family="Arial", size=20, weight="bold")
            )

    def on_team1_select(self, choice):
        self.update_preview()
        if not choice or choice == "Select":
            self.refresh_dropdowns(team1_selected=False)
            return

        season = self.widgets['season'].get()
        year = self.widgets['year'].get()
        valid_opponents = []

        if season == "Play-in":
            ranks = self.loader.get_regular_season_ranks(year, teams)
            pairs = self.loader.analyze_playin_pairs(year, ranks)
            for p1, p2 in pairs:
                if p1 == choice: valid_opponents.append(p2)
                if p2 == choice: valid_opponents.append(p1)
        elif season in ["Playoff", "Finals"]:
             curr_vals = self.widgets['t2'].cget("values")
             valid_opponents = [t for t in curr_vals if t != choice and t != "Select"]
        else:
            all_teams = list(teams.keys())
            for t in all_teams:
                if t == choice: continue
                if len(teams.get(t, [])) == 12: valid_opponents.append(t)
            valid_opponents.sort()

        if not valid_opponents:
            self.widgets['t2'].configure(values=["No Match Found"])
            self.widgets['t2'].set("No Match Found")
        else:
            self.widgets['t2'].configure(values=valid_opponents)
            self.widgets['t2'].set("Select")

    def refresh_dropdowns(self, team1_selected=True):
        season = self.widgets['season'].get()
        year = self.widgets['year'].get() or str(datetime.now().year)

        available_t1 = []

        if season == "Play-in":
            ranks = self.loader.get_regular_season_ranks(year, teams)
            pairs = self.loader.analyze_playin_pairs(year, ranks)
            if len(ranks) < 10: available_t1 = ["Need 10+ Teams"]
            elif not pairs: available_t1 = ["All Matches Played"]
            else:
                names = set()
                for a, b in pairs: names.add(a); names.add(b)
                available_t1 = sorted(list(names))
        
        elif season == "Playoff":
             ranks = self.loader.get_regular_season_ranks(year, teams)
             if len(ranks) < 10: available_t1 = ["Need 10+ Teams"]
             else: available_t1 = sorted([r['name'] for r in ranks[6:10]])
        
        elif season == "Finals":
             ranks = self.loader.get_regular_season_ranks(year, teams)
             if len(ranks) < 8: available_t1 = ["Need 8+ Teams"]
             else: available_t1 = sorted([r['name'] for r in ranks[:8]])
        
        else:
            filtered = [t for t, r in teams.items() if len(r) == 12]
            available_t1 = sorted(filtered)

        if hasattr(self, 'widgets'):
            self.widgets['t1'].configure(values=available_t1)
            if not team1_selected: 
                 self.widgets['t2'].configure(values=available_t1)
            
            avail_venues = [v for v, d in venues.items() if d.get("available", True)]
            self.widgets['venue'].configure(values=avail_venues)

            if self.widgets['t1'].get() not in available_t1: self.widgets['t1'].set("Select")

    def reset_team_selections(self):
        self.refresh_dropdowns(team1_selected=False)
        self.widgets['t1'].set("Select")
        self.widgets['t2'].set("Select")
        self.widgets['venue'].set("Select")

    def handle_save(self):
        t1 = self.widgets['t1'].get()
        t2 = self.widgets['t2'].get()
        v = self.widgets['venue'].get()
        md = self.widgets['date'].get().strip()
        year_txt = self.widgets['year'].get().strip()
        start = self.widgets['start'].get().strip()
        end = self.widgets['end'].get().strip()
        season = self.widgets['season'].get()

        if not all([t1, t2, v, md, year_txt, start, end]) or "Select" in (t1, t2, v) or "No Match" in (t1, t2):
            messagebox.showwarning("Missing Info", "Please fill all fields.")
            return
        if t1 == t2:
            messagebox.showwarning("Invalid", "Teams must be different.")
            return

        try:
            y_val = int(year_txt)
            if y_val > 9999: raise ValueError
            pmd = datetime.strptime(md, "%m-%d")
            game_date = _date(y_val, pmd.month, pmd.day)
            
            s_time = datetime.strptime(start, "%H:%M").time()
            e_time = datetime.strptime(end, "%H:%M").time()
            if e_time <= s_time:
                messagebox.showwarning("Invalid Time", "End time must be after start time.")
                return
            
            full_start = datetime.combine(game_date, s_time)
            full_end = datetime.combine(game_date, e_time)

            if full_start < datetime.now():
                messagebox.showwarning("Invalid Date/Time", "Cannot schedule a game for a past date or time.")
                return

        except:
            messagebox.showwarning("Invalid Data", "Check Year (YYYY), Date (MM-DD), and Time (HH:MM).")
            return

        is_valid_season, msg = self.loader.is_date_within_season(game_date, season, y_val)
        if not is_valid_season:
            messagebox.showwarning("Season Mismatch", msg)
            return

        conflict_msg = self.loader.check_conflicts(t1, t2, v, game_date, full_start, full_end)
        if conflict_msg:
            messagebox.showwarning("Scheduling Conflict", conflict_msg)
            return

        success = self.loader.save_game(t1, t2, v, game_date, full_start, full_end)
        if success:
            messagebox.showinfo("Success", f"Game Scheduled:\n{t1} vs {t2}\n{game_date} @ {start}")
            self.reset_team_selections()
            self.update_preview()
            
            load_scheduled_games_from_db()
            try:
                from viewGamesTab import refresh_scheduled_games_table
                refresh_scheduled_games_table(refs.get('scheduled_games_table'))
            except: pass
        else:
            messagebox.showerror("Error", "Database error occurred.")

def load_scheduled_games_from_db():
    """Wrapper to use the Loader class."""
    global _current_loader
    if not sched_mgr: return
    
    if not _current_loader:
        _current_loader = GameListLoader(sched_mgr)
    
    new_games = _current_loader.fetch_all_games()
    
    scheduled_games.clear()
    scheduled_games.extend(new_games)

    try:
        import viewGamesTab as vgt
        if hasattr(vgt, 'scheduled_games'):
            vgt.scheduled_games.clear()
            vgt.scheduled_games.extend(new_games)
    except Exception: pass

def build_schedule_left_ui(parent):
    global _current_loader, _current_preview_ui
    
    if not _current_loader and sched_mgr:
        _current_loader = GameListLoader(sched_mgr)
    
    _current_preview_ui = GameSchedulePreview(parent, _current_loader)

def update_schedule_optionmenus(team1_opt=None, team2_opt=None, venue_opt=None):
    if _current_preview_ui:
        _current_preview_ui.refresh_dropdowns(team1_selected=False)
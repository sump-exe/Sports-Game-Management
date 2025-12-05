import customtkinter as ctk
from tkinter import messagebox
from theDB import *

refs = {}

def _season_windows_for_year(year):
    s_helper = Season()
    start, _ = s_helper.get_range("Pre-season", year)
    _, end = s_helper.get_range("Off-season", year + 1)
    return start, end

def _compute_season_start_years_with_games():
    cur = mydb.cursor()
    try:
        cur.execute("SELECT MIN(substr(game_date,1,4)) as miny, MAX(substr(game_date,1,4)) as maxy FROM games WHERE game_date IS NOT NULL")
        r = cur.fetchone()
        if not r or not r['miny']: return []
        
        years = []
        for y in range(int(r['miny'])-1, int(r['maxy'])+1):
            s, e = _season_windows_for_year(y)
            cur.execute("SELECT 1 FROM games WHERE game_date BETWEEN ? AND ? LIMIT 1", (s.isoformat(), e.isoformat()))
            if cur.fetchone(): years.append(y)
        
        years.sort(reverse=True)
        return years
    finally:
        cur.close()


class StandingsTableViewer:
    def __init__(self, parent_frame):
        self.parent = parent_frame
    
    def refresh(self):
        for w in self.parent.winfo_children():
            w.destroy()

        years = _compute_season_start_years_with_games()
        
        if not years:
            ctk.CTkLabel(self.parent, text="No scheduled games found in database.").pack(pady=20)
            return

        for year in years:
            self._build_season_section(year)

    def _format_header_text(self, year):
        s, e = _season_windows_for_year(year)
        base_text = f"Season {e.year} — {s} → {e}"
        
        cur_mvp = mydb.cursor()
        try:
            cur_mvp.execute("""
                SELECT p.name, t.teamName 
                FROM mvps m 
                JOIN players p ON m.player_id = p.id 
                JOIN teams t ON m.team_id = t.id 
                WHERE m.year = ?
            """, (year,))
            mvp_row = cur_mvp.fetchone()
            if mvp_row:
                base_text += f"   |   👑 MVP: {mvp_row['name']} ({mvp_row['teamName']})"
        except Exception:
            pass
        finally:
            cur_mvp.close()
        return base_text

    def _build_season_section(self, year):
        s, e = _season_windows_for_year(year)
        start_iso, end_iso = s.isoformat(), e.isoformat()
        
        header_frame = ctk.CTkFrame(self.parent, fg_color="#333333")
        header_frame.pack(fill="x", pady=(15, 5))
        ctk.CTkLabel(header_frame, text=self._format_header_text(year), 
                     font=ctk.CTkFont(size=16, weight="bold")).pack(pady=5)
        
        cols = ctk.CTkFrame(self.parent, fg_color="transparent")
        cols.pack(fill="x")
        headers = ["Rank", "Team", "Wins", "Losses", "Points Scored"]
        for i, t in enumerate(headers):
            cols.grid_columnconfigure(i, weight=1)
            ctk.CTkLabel(cols, text=t, font=ctk.CTkFont(weight="bold", underline=True)).grid(row=0, column=i, pady=5)

        teams_data = self._fetch_season_stats(start_iso, end_iso)
        
        if not teams_data:
            ctk.CTkLabel(self.parent, text="No teams active in this season.").pack()
            return

        for idx, row in enumerate(teams_data, 1):
            r = ctk.CTkFrame(self.parent, fg_color="#2A2A2A" if idx % 2 == 0 else "#1F1F1F")
            r.pack(fill="x", pady=1)
            for i in range(5): r.grid_columnconfigure(i, weight=1)
            
            rank_color = "#FFD700" if idx == 1 else "white"
            
            ctk.CTkLabel(r, text=str(idx), text_color=rank_color).grid(row=0, column=0)
            ctk.CTkLabel(r, text=row['teamName'], text_color=rank_color).grid(row=0, column=1)
            ctk.CTkLabel(r, text=str(row['wins'])).grid(row=0, column=2)
            ctk.CTkLabel(r, text=str(row['losses'])).grid(row=0, column=3)
            ctk.CTkLabel(r, text=str(row['total_pts'])).grid(row=0, column=4)

    def _fetch_season_stats(self, start_iso, end_iso):
        cur = mydb.cursor()
        try:
            query = """
                SELECT 
                    t.id, t.teamName,
                    (SELECT COUNT(*) FROM games g 
                     WHERE g.winner_team_id = t.id 
                       AND g.is_final = 1 
                       AND g.game_date BETWEEN ? AND ?) as wins,
                    (SELECT COUNT(*) FROM games g 
                     WHERE (g.team1_id = t.id OR g.team2_id = t.id) 
                       AND g.winner_team_id IS NOT NULL 
                       AND g.winner_team_id != t.id 
                       AND g.is_final = 1 
                       AND g.game_date BETWEEN ? AND ?) as losses,
                    COALESCE((SELECT SUM(
                        CASE WHEN g2.team1_id = t.id THEN COALESCE(g2.team1_score, 0) 
                        ELSE COALESCE(g2.team2_score, 0) END) 
                      FROM games g2 
                      WHERE (g2.team1_id = t.id OR g2.team2_id = t.id) 
                        AND g2.is_final = 1 
                        AND g2.game_date BETWEEN ? AND ?), 0) as total_pts
                FROM teams t
                WHERE EXISTS (
                    SELECT 1 FROM games g3 
                    WHERE (g3.team1_id = t.id OR g3.team2_id = t.id) 
                      AND g3.game_date BETWEEN ? AND ?
                )
                ORDER BY wins DESC, total_pts DESC
            """
            params = (start_iso, end_iso, start_iso, end_iso, start_iso, end_iso, start_iso, end_iso)
            cur.execute(query, params)
            return cur.fetchall()
        finally:
            cur.close()


class MVPSelectorController:
    def __init__(self, parent_frame, refresh_callback):
        self.parent = parent_frame
        self.refresh_callback = refresh_callback 
        
        self.team_map = {}
        self.player_map = {}
        self.year_display_map = {}
        
        self.year_var = ctk.StringVar(value="Select Season")
        self.team_var = ctk.StringVar(value="Select Team")
        self.player_var = ctk.StringVar(value="Select Player")

        self._build_ui()
        self.refresh_options()

    def _build_ui(self):
        for w in self.parent.winfo_children(): w.destroy()
        
        ctk.CTkLabel(self.parent, text="Season MVP Selection", font=ctk.CTkFont(size=16, weight="bold")).pack(pady=(12,12))

        ctk.CTkLabel(self.parent, text="Select Season:").pack(anchor="w", padx=12, pady=(0,2))
        self.year_opt = ctk.CTkOptionMenu(self.parent, variable=self.year_var, values=["Select Season"], 
                                          command=lambda x: self.on_year_change())
        self.year_opt.pack(fill="x", padx=12, pady=(0,10))

        ctk.CTkLabel(self.parent, text="Select Team:").pack(anchor="w", padx=12, pady=(0,2))
        self.team_opt = ctk.CTkOptionMenu(self.parent, variable=self.team_var, values=["Select Team"], 
                                          command=lambda x: self.on_team_change())
        self.team_opt.pack(fill="x", padx=12, pady=(0,10))

        ctk.CTkLabel(self.parent, text="Select Player:").pack(anchor="w", padx=12, pady=(0,2))
        self.player_opt = ctk.CTkOptionMenu(self.parent, variable=self.player_var, values=["Select Player"])
        self.player_opt.pack(fill="x", padx=12, pady=(0,10))
        
        btn_frame = ctk.CTkFrame(self.parent, fg_color="transparent")
        btn_frame.pack(fill="x", padx=12, pady=10)
        ctk.CTkButton(btn_frame, text="Assign MVP", command=self.assign_mvp, fg_color="#4CAF50").pack(side="left", expand=True, padx=(0,4))
        ctk.CTkButton(btn_frame, text="Clear MVP", command=self.clear_mvp, fg_color="#D9534F").pack(side="right", expand=True, padx=(4,0))

        self.mvp_lbl = ctk.CTkLabel(self.parent, text="Current MVP: None", text_color="#FFD700", font=ctk.CTkFont(weight="bold"))
        self.mvp_lbl.pack(pady=20)

    def refresh_options(self):
        self.team_map = {}
        names = []
        cur = mydb.cursor()
        try:
            cur.execute("SELECT id, teamName FROM teams ORDER BY teamName")
            for r in cur.fetchall():
                self.team_map[r['teamName']] = r['id']
                names.append(r['teamName'])
        finally:
            cur.close()
        self.team_opt.configure(values=["Select Team"] + names)

        season_start_years = _compute_season_start_years_with_games()
        self.year_display_map = {}
        display_list = []
        for y in season_start_years:
            s, e = _season_windows_for_year(y)
            end_year = e.year if e else y
            display = f"Season {end_year}"
            display_list.append(display)
            self.year_display_map[display] = y
        self.year_opt.configure(values=["Select Season"] + display_list)
        
        self.on_year_change()

    def on_year_change(self):
        sel = self.year_var.get()
        start_year = self.year_display_map.get(sel)
        
        if start_year:
            cur = mydb.cursor()
            try:
                cur.execute("""
                    SELECT p.name, t.teamName 
                    FROM mvps m 
                    JOIN players p ON m.player_id = p.id 
                    JOIN teams t ON m.team_id = t.id 
                    WHERE m.year = ?
                """, (start_year,))
                r = cur.fetchone()
                if r:
                    self.mvp_lbl.configure(text=f"Current MVP: {r['name']} ({r['teamName']})")
                else:
                    self.mvp_lbl.configure(text="Current MVP: None")
                
                s, e = _season_windows_for_year(start_year)
                cur.execute("""
                    SELECT DISTINCT t.teamName 
                    FROM teams t
                    JOIN games g ON (t.id = g.team1_id OR t.id = g.team2_id)
                    WHERE g.game_date BETWEEN ? AND ?
                    ORDER BY t.teamName
                """, (s.isoformat(), e.isoformat()))
                valid_teams = [row['teamName'] for row in cur.fetchall()]
                
                self.team_opt.configure(values=["Select Team"] + valid_teams)
                
                if self.team_var.get() != "Select Team" and self.team_var.get() not in valid_teams:
                    self.team_var.set("Select Team")
                    self.player_opt.configure(values=["Select Player"])
                    self.player_var.set("Select Player")
            finally:
                cur.close()
        else:
            self.mvp_lbl.configure(text="Current MVP: None")
            all_teams = sorted(list(self.team_map.keys()))
            self.team_opt.configure(values=["Select Team"] + all_teams)

    def on_team_change(self):
        t_name = self.team_var.get()
        t_id = self.team_map.get(t_name)
        
        if not t_id:
            self.player_opt.configure(values=["Select Player"])
            self.player_var.set("Select Player")
            return

        cur = mydb.cursor()
        players = []
        self.player_map = {}
        try:
            cur.execute("SELECT id, name FROM players WHERE team_id = ? ORDER BY name", (t_id,))
            for r in cur.fetchall():
                players.append(r['name'])
                self.player_map[r['name']] = r['id']
        finally:
            cur.close()
        
        self.player_opt.configure(values=["Select Player"] + players)
        self.player_var.set("Select Player")

    def assign_mvp(self):
        season_year = self.year_display_map.get(self.year_var.get())
        if not season_year:
            messagebox.showwarning("Missing", "Please select a season.")
            return
            
        p_name = self.player_var.get()
        p_id = self.player_map.get(p_name)
        if not p_id:
            messagebox.showwarning("Missing", "Please select a valid player.")
            return
            
        t_name = self.team_var.get()
        t_id = self.team_map.get(t_name)
        if not t_id:
            messagebox.showwarning("Missing", "Please select a team.")
            return

        cur = mydb.cursor()
        try:
            cur.execute("DELETE FROM mvps WHERE year = ?", (season_year,))
            cur.execute("INSERT INTO mvps (player_id, team_id, year) VALUES (?, ?, ?)", (p_id, t_id, season_year))
            mydb.commit()
            
            messagebox.showinfo("Success", f"MVP assigned for Season {season_year + 1}.")
            
            self.on_year_change()
            if self.refresh_callback:
                self.refresh_callback()
        except Exception as e:
            messagebox.showerror("Error", str(e))
        finally:
            cur.close()

    def clear_mvp(self):
        season_year = self.year_display_map.get(self.year_var.get())
        if not season_year:
            messagebox.showwarning("Missing", "Please select a season.")
            return

        if not messagebox.askyesno("Confirm", "Clear MVP for this season?"):
            return

        cur = mydb.cursor()
        try:
            cur.execute("DELETE FROM mvps WHERE year = ?", (season_year,))
            mydb.commit()
            
            messagebox.showinfo("Success", "MVP cleared.")
            
            self.on_year_change()
            if self.refresh_callback:
                self.refresh_callback()
        finally:
            cur.close()

def refresh_standings_table(container):
    for w in container.winfo_children(): w.destroy()
    
    content = ctk.CTkFrame(container)
    content.pack(fill="both", expand=True)
    
    standings_frame_container = ctk.CTkScrollableFrame(content, width=700, height=500)
    standings_frame_container.pack(side="left", fill="both", expand=True, padx=8)
    
    mvp_frame_container = ctk.CTkFrame(content, width=300, height=500)
    mvp_frame_container.pack(side="right", fill="y", padx=8)
    
    viewer = StandingsTableViewer(standings_frame_container)
    
    controller = MVPSelectorController(mvp_frame_container, refresh_callback=viewer.refresh)
    
    viewer.refresh()
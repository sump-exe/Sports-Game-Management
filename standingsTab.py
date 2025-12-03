import customtkinter as ctk
from tkinter import messagebox
from datetime import datetime
from theDB import *

refs = {}
_widgets = {}

def _season_windows_for_year(year):
    """
    Returns the start and end date objects for a full season cycle 
    associated with a specific start year (e.g., 2024 season starts late 2023).
    """
    s_helper = Season()
    # "Pre-season" acts as the start boundary
    start, _ = s_helper.get_range("Pre-season", year)
    # "Off-season" acts as the end boundary (of the NEXT calendar year)
    _, end = s_helper.get_range("Off-season", year + 1)
    return start, end

def _compute_season_start_years_with_games():
    """
    Scans the database to find which years actually have scheduled games.
    """
    cur = mydb.cursor()
    try:
        # Find the range of years present in the games table
        cur.execute("SELECT MIN(substr(game_date,1,4)) as miny, MAX(substr(game_date,1,4)) as maxy FROM games WHERE game_date IS NOT NULL")
        r = cur.fetchone()
        if not r or not r['miny']: return []
        
        years = []
        # Check every year in that range to see if it falls into a valid season window
        for y in range(int(r['miny'])-1, int(r['maxy'])+1):
            s, e = _season_windows_for_year(y)
            # Efficiently check if at least 1 game exists in this window
            cur.execute("SELECT 1 FROM games WHERE game_date BETWEEN ? AND ? LIMIT 1", (s.isoformat(), e.isoformat()))
            if cur.fetchone(): years.append(y)
        
        years.sort(reverse=True)
        return years
    finally:
        cur.close()

def _format_season_header(year):
    s, e = _season_windows_for_year(year)
    return f"Season {e.year} — {s} → {e}"

def refresh_standings_table(container):
    """
    Main entry point to rebuild the Standings tab UI.
    """
    _widgets["container"] = container
    for w in container.winfo_children(): w.destroy()
    
    content = ctk.CTkFrame(container)
    content.pack(fill="both", expand=True)
    
    # Left side: Standings Table
    standings_frame = ctk.CTkScrollableFrame(content, width=700, height=500)
    standings_frame.pack(side="left", fill="both", expand=True, padx=8)
    _widgets["standings_frame"] = standings_frame
    
    # Right side: MVP Controls
    mvp_frame = ctk.CTkFrame(content, width=300, height=500)
    mvp_frame.pack(side="right", fill="y", padx=8)
    _widgets["mvp_frame"] = mvp_frame
    
    refresh_standings_rows()
    build_mvp_panel() 

def refresh_standings_rows():
    frame = _widgets.get("standings_frame")
    if not frame: return
    
    for w in frame.winfo_children():
        w.destroy()

    years = _compute_season_start_years_with_games()
    
    if not years:
        ctk.CTkLabel(frame, text="No scheduled games found in database.").pack(pady=20)
        return

    for year in years:
        s, e = _season_windows_for_year(year)
        start_iso, end_iso = s.isoformat(), e.isoformat()
        
        # --- Season Header & MVP Display ---
        header_frame = ctk.CTkFrame(frame, fg_color="#333333")
        header_frame.pack(fill="x", pady=(15, 5))
        
        base_header_text = _format_season_header(year)
        final_header_text = base_header_text

        # Fetch MVP for this specific season year to display in header
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
                final_header_text += f"   |   👑 MVP: {mvp_row['name']} ({mvp_row['teamName']})"
        except Exception:
            pass
        finally:
            cur_mvp.close()

        ctk.CTkLabel(header_frame, text=final_header_text, font=ctk.CTkFont(size=16, weight="bold")).pack(pady=5)
        
        # Table Headers
        cols = ctk.CTkFrame(frame, fg_color="transparent")
        cols.pack(fill="x")
        headers = ["Rank", "Team", "Wins", "Losses", "Points Scored"]
        for i, t in enumerate(headers):
            cols.grid_columnconfigure(i, weight=1)
            ctk.CTkLabel(cols, text=t, font=ctk.CTkFont(weight="bold", underline=True)).grid(row=0, column=i, pady=5)
            
        cur = mydb.cursor()
        
        # --- THE CORE QUERY ---
        query = """
            SELECT 
                t.id, 
                t.teamName,
                
                -- Calculate WINS
                (SELECT COUNT(*) 
                 FROM games g 
                 WHERE g.winner_team_id = t.id 
                   AND g.is_final = 1 
                   AND g.game_date BETWEEN ? AND ?) as wins,
                   
                -- Calculate LOSSES
                (SELECT COUNT(*) 
                 FROM games g 
                 WHERE (g.team1_id = t.id OR g.team2_id = t.id) 
                   AND g.winner_team_id IS NOT NULL 
                   AND g.winner_team_id != t.id 
                   AND g.is_final = 1 
                   AND g.game_date BETWEEN ? AND ?) as losses,
                   
                -- Calculate Total Points Scored
                COALESCE((SELECT SUM(
                    CASE 
                        WHEN g2.team1_id = t.id THEN COALESCE(g2.team1_score, 0) 
                        ELSE COALESCE(g2.team2_score, 0) 
                    END) 
                  FROM games g2 
                  WHERE (g2.team1_id = t.id OR g2.team2_id = t.id) 
                    AND g2.is_final = 1 
                    AND g2.game_date BETWEEN ? AND ?), 0) as total_pts
                            
            FROM teams t
            -- Optimization: Only include teams that have at least one game scheduled in this window
            WHERE EXISTS (
                SELECT 1 FROM games g3 
                WHERE (g3.team1_id = t.id OR g3.team2_id = t.id) 
                  AND g3.game_date BETWEEN ? AND ?
            )
            ORDER BY wins DESC, total_pts DESC
        """
        
        # We must provide the date range parameters 5 times because there are 5 ? pairs in the query
        params = (start_iso, end_iso, start_iso, end_iso, start_iso, end_iso, start_iso, end_iso)
        
        cur.execute(query, params)
        teams_data = cur.fetchall()
        cur.close()
        
        if not teams_data:
            ctk.CTkLabel(frame, text="No teams active in this season.").pack()
            continue

        for idx, row in enumerate(teams_data, 1):
            r = ctk.CTkFrame(frame, fg_color="#2A2A2A" if idx % 2 == 0 else "#1F1F1F")
            r.pack(fill="x", pady=1)
            for i in range(5): r.grid_columnconfigure(i, weight=1)
            
            # Gold color for 1st place
            rank_color = "#FFD700" if idx == 1 else "white"
            
            ctk.CTkLabel(r, text=str(idx), text_color=rank_color).grid(row=0, column=0)
            ctk.CTkLabel(r, text=row['teamName'], text_color=rank_color).grid(row=0, column=1)
            ctk.CTkLabel(r, text=str(row['wins'])).grid(row=0, column=2)
            ctk.CTkLabel(r, text=str(row['losses'])).grid(row=0, column=3)
            ctk.CTkLabel(r, text=str(row['total_pts'])).grid(row=0, column=4)

# --- MVP SECTION HELPERS ---

def load_team_map():
    t_map = {}
    names = []
    cur = mydb.cursor()
    try:
        cur.execute("SELECT id, teamName FROM teams ORDER BY teamName")
        for r in cur.fetchall():
            t_map[r['teamName']] = r['id']
            names.append(r['teamName'])
    finally:
        cur.close()
    return names, t_map

def load_years():
    return _compute_season_start_years_with_games()

def build_mvp_panel():
    parent = _widgets.get("mvp_frame")
    if not parent: return
    
    for w in parent.winfo_children(): w.destroy()
    
    ctk.CTkLabel(parent, text="Season MVP Selection", font=ctk.CTkFont(size=16, weight="bold")).pack(pady=(12,12))

    ctk.CTkLabel(parent, text="Select Season:").pack(anchor="w", padx=12, pady=(0,2))
    year_var = ctk.StringVar(value="Select Season")
    year_opt = ctk.CTkOptionMenu(parent, variable=year_var, values=["Select Season"], command=lambda x: on_year_change())
    year_opt.pack(fill="x", padx=12, pady=(0,10))
    _widgets["year_var"] = year_var
    _widgets["year_opt"] = year_opt

    ctk.CTkLabel(parent, text="Select Team:").pack(anchor="w", padx=12, pady=(0,2))
    team_var = ctk.StringVar(value="Select Team")
    team_opt = ctk.CTkOptionMenu(parent, variable=team_var, values=["Select Team"], command=lambda x: on_team_change())
    team_opt.pack(fill="x", padx=12, pady=(0,10))
    _widgets["team_var"] = team_var
    _widgets["team_opt"] = team_opt

    ctk.CTkLabel(parent, text="Select Player:").pack(anchor="w", padx=12, pady=(0,2))
    player_var = ctk.StringVar(value="Select Player")
    player_opt = ctk.CTkOptionMenu(parent, variable=player_var, values=["Select Player"])
    player_opt.pack(fill="x", padx=12, pady=(0,10))
    _widgets["player_var"] = player_var
    _widgets["player_opt"] = player_opt
    
    btn_frame = ctk.CTkFrame(parent, fg_color="transparent")
    btn_frame.pack(fill="x", padx=12, pady=10)
    ctk.CTkButton(btn_frame, text="Assign MVP", command=assign_mvp, fg_color="#4CAF50").pack(side="left", expand=True, padx=(0,4))
    ctk.CTkButton(btn_frame, text="Clear MVP", command=clear_mvp, fg_color="#D9534F").pack(side="right", expand=True, padx=(4,0))

    _widgets["mvp_display_label"] = ctk.CTkLabel(parent, text="Current MVP: None", text_color="#FFD700", font=ctk.CTkFont(weight="bold"))
    _widgets["mvp_display_label"].pack(pady=20)
    
    _widgets["player_mappings"] = {id(player_opt): {}}

    refresh_mvp_controls()

def refresh_mvp_controls():
    team_names, team_map = load_team_map()
    _widgets["team_map"] = team_map
    
    team_opt = _widgets.get("team_opt")
    if team_opt:
        team_opt.configure(values=["Select Team"] + team_names)

    season_start_years = load_years()
    display_list = []
    display_map = {}
    for y in season_start_years:
        s, e = _season_windows_for_year(y)
        end_year = e.year if e else y
        display = f"Season {end_year}"
        display_list.append(display)
        display_map[display] = y

    _widgets["year_display_map"] = display_map
    
    year_opt = _widgets.get("year_opt")
    if year_opt:
        year_opt.configure(values=["Select Season"] + display_list)

    on_year_change()

def on_year_change():
    y_var = _widgets.get("year_var")
    lbl = _widgets.get("mvp_display_label")
    team_opt = _widgets.get("team_opt")
    team_var = _widgets.get("team_var")
    player_opt = _widgets.get("player_opt")
    player_var = _widgets.get("player_var")

    if not y_var: return
    
    sel = y_var.get()
    display_map = _widgets.get("year_display_map", {})
    start_year = display_map.get(sel)
    
    if start_year:
        # 1. Update MVP Label
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
                lbl.configure(text=f"Current MVP: {r['name']} ({r['teamName']})")
            else:
                lbl.configure(text="Current MVP: None")
            
            # 2. Filter Team Dropdown (Show only teams active in this season)
            s, e = _season_windows_for_year(start_year)
            cur.execute("""
                SELECT DISTINCT t.teamName 
                FROM teams t
                JOIN games g ON (t.id = g.team1_id OR t.id = g.team2_id)
                WHERE g.game_date BETWEEN ? AND ?
                ORDER BY t.teamName
            """, (s.isoformat(), e.isoformat()))
            
            valid_teams = [row['teamName'] for row in cur.fetchall()]
            
            if team_opt:
                team_opt.configure(values=["Select Team"] + valid_teams)
            
            # Reset dropdowns if the currently selected team is invalid for this season
            if team_var and team_var.get() != "Select Team" and team_var.get() not in valid_teams:
                team_var.set("Select Team")
                if player_opt: player_opt.configure(values=["Select Player"])
                if player_var: player_var.set("Select Player")
                
        finally:
            cur.close()
    else:
        lbl.configure(text="Current MVP: None")
        # If no season selected, revert to showing all teams
        all_teams = sorted(list(_widgets.get("team_map", {}).keys()))
        if team_opt:
             team_opt.configure(values=["Select Team"] + all_teams)

def on_team_change():
    t_var = _widgets.get("team_var")
    p_opt = _widgets.get("player_opt")
    p_var = _widgets.get("player_var")
    t_map = _widgets.get("team_map", {})
    
    if not t_var or not p_opt: return
    
    t_name = t_var.get()
    t_id = t_map.get(t_name)
    
    if not t_id:
        p_opt.configure(values=["Select Player"])
        p_var.set("Select Player")
        return

    cur = mydb.cursor()
    players = []
    p_mapping = {}
    try:
        cur.execute("SELECT id, name FROM players WHERE team_id = ? ORDER BY name", (t_id,))
        for r in cur.fetchall():
            players.append(r['name'])
            p_mapping[r['name']] = r['id']
    finally:
        cur.close()
        
    p_opt.configure(values=["Select Player"] + players)
    p_var.set("Select Player")
    _widgets["player_mappings"][id(p_opt)] = p_mapping

def assign_mvp():
    year_var = _widgets.get("year_var")
    player_var = _widgets.get("player_var")
    team_var = _widgets.get("team_var")
    
    if not all([year_var, player_var, team_var]): return
    
    display_map = _widgets.get("year_display_map", {})
    season_year = display_map.get(year_var.get())
    
    if not season_year:
        messagebox.showwarning("Missing", "Please select a season.")
        return
        
    p_name = player_var.get()
    p_opt = _widgets.get("player_opt")
    mappings = _widgets["player_mappings"].get(id(p_opt), {})
    p_id = mappings.get(p_name)
    
    if not p_id:
         messagebox.showwarning("Missing", "Please select a valid player.")
         return
         
    t_name = team_var.get()
    t_map = _widgets.get("team_map", {})
    t_id = t_map.get(t_name)
    
    if not t_id:
         messagebox.showwarning("Missing", "Please select a team.")
         return

    cur = mydb.cursor()
    try:
        cur.execute("DELETE FROM mvps WHERE year = ?", (season_year,))
        cur.execute("INSERT INTO mvps (player_id, team_id, year) VALUES (?, ?, ?)", (p_id, t_id, season_year))
        mydb.commit()
        messagebox.showinfo("Success", f"MVP assigned for Season {season_year + 1}.")
        on_year_change() # Refresh label
        # Also refresh table to show new header immediately
        refresh_standings_rows()
    except Exception as e:
        messagebox.showerror("Error", str(e))
    finally:
        cur.close()

def clear_mvp():
    year_var = _widgets.get("year_var")
    display_map = _widgets.get("year_display_map", {})
    season_year = display_map.get(year_var.get())
    
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
        on_year_change()
        refresh_standings_rows()
    finally:
        cur.close()
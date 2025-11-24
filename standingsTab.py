import customtkinter as ctk
from tkinter import messagebox
from theDB import mydb

# This module provides standings UI helper. mainGui will set refs when wiring.
refs = {}

# Internal widget and state holders for partial refreshes
_widgets = {
    "container": None,
    "content": None,
    "standings_frame": None,
    "mvp_frame": None,
    "team_map": {},        # name -> id
    "player_mappings": {}, # option_widget -> {display: id}
    "team_opt": None,
    "player_opt": None,
    "year_opt": None,
    "team_var": None,
    "player_var": None,
    "year_var": None,
    "current_lbl": None,
    "assign_btn": None,
    "clear_btn": None,
}


def refresh_standings_table(container):
    """
    Build the standings view and MVP controls container (only once per container).
    Subsequent updates to standings counts or MVP controls should call:
      - refresh_standings_rows() to update the left standings list
      - refresh_mvp_controls() to update only the MVP widgets
    This function still serves as the initial entry point used by mainGui.
    """
    # store container ref
    _widgets["container"] = container

    # Clear existing widgets if being rebuilt from scratch
    for w in container.winfo_children():
        try:
            w.destroy()
        except Exception:
            pass

    # Create main content frame with two columns: left = standings, right = MVP controls
    content = ctk.CTkFrame(container, fg_color="#101010")
    content.pack(fill="both", expand=True, padx=8, pady=6)
    try:
        content.grid_columnconfigure(0, weight=3)
        content.grid_columnconfigure(1, weight=1)
        content.grid_rowconfigure(0, weight=1)
    except Exception:
        pass
    _widgets["content"] = content

    # LEFT: a scrollable frame for the standings list
    standings_frame = ctk.CTkScrollableFrame(content, width=700, fg_color="#0F0F0F")
    standings_frame.grid(row=0, column=0, sticky="nsew", padx=(0,8), pady=4)
    _widgets["standings_frame"] = standings_frame

    # RIGHT: MVP controls
    mvp_frame = ctk.CTkFrame(content, fg_color="#1A1A1A", corner_radius=8)
    mvp_frame.grid(row=0, column=1, sticky="nsew", padx=(8,0), pady=4)
    mvp_frame.grid_columnconfigure(0, weight=1)
    _widgets["mvp_frame"] = mvp_frame

    # Populate both parts
    refresh_standings_rows()
    build_mvp_panel()

    # Let callers (mainGui) know where the standings are displayed
    try:
        if isinstance(refs, dict):
            refs['standings_table'] = container
    except Exception:
        pass


def refresh_standings_rows():
    """
    Refresh only the standings rows (left side). This avoids touching the MVP controls.
    """
    standings_frame = _widgets.get("standings_frame")
    if not standings_frame:
        # If not initialized, try to build whole view
        container = _widgets.get("container")
        if container:
            refresh_standings_table(container)
        return

    # Clear existing rows
    for w in standings_frame.winfo_children():
        try:
            w.destroy()
        except Exception:
            pass

    # Header
    header = ctk.CTkFrame(standings_frame, fg_color="#1F1F1F")
    header.pack(fill="x", padx=8, pady=6)
    header.grid_columnconfigure(0, weight=1)
    header.grid_columnconfigure(1, weight=3)
    header.grid_columnconfigure(2, weight=1)
    header.grid_columnconfigure(3, weight=1)

    ctk.CTkLabel(header, text="Rank", font=ctk.CTkFont(size=14, weight="bold")).grid(row=0, column=0, padx=8, pady=6, sticky="w")
    ctk.CTkLabel(header, text="Team", font=ctk.CTkFont(size=14, weight="bold")).grid(row=0, column=1, padx=8, pady=6, sticky="w")
    ctk.CTkLabel(header, text="Wins", font=ctk.CTkFont(size=14, weight="bold")).grid(row=0, column=2, padx=8, pady=6, sticky="w")
    ctk.CTkLabel(header, text="Losses", font=ctk.CTkFont(size=14, weight="bold")).grid(row=0, column=3, padx=8, pady=6, sticky="w")
    ctk.CTkLabel(header, text="Total Points", font=ctk.CTkFont(size=14, weight="bold")).grid(row=0, column=4, padx=8, pady=6, sticky="w")

    # Query teams and compute wins/losses via subqueries (considers only is_final=1 games)
    cursor = mydb.cursor()
    try:
        cursor.execute("""
            SELECT
                t.id,
                t.teamName,
                COALESCE(t.totalPoints, 0) as totalPoints,
                COALESCE((SELECT COUNT(*) FROM games g WHERE g.is_final = 1 AND g.winner_team_id = t.id), 0) AS wins,
                COALESCE((SELECT COUNT(*) FROM games g
                          WHERE g.is_final = 1
                            AND (g.home_team_id = t.id OR g.away_team_id = t.id)
                            AND (g.winner_team_id IS NOT NULL AND g.winner_team_id != t.id)
                         ), 0) AS losses
            FROM teams t
            ORDER BY wins DESC, totalPoints DESC, t.teamName COLLATE NOCASE
        """)
        teams = cursor.fetchall()
    finally:
        try:
            cursor.close()
        except Exception:
            pass

    if not teams:
        ctk.CTkLabel(standings_frame, text="No teams found.", anchor="w").pack(padx=8, pady=8)
        return

    # Data rows
    for idx, row in enumerate(teams, start=1):
        row_frame = ctk.CTkFrame(standings_frame, fg_color="#2A2A2A")
        row_frame.pack(fill="x", padx=8, pady=2)
        # configure columns for consistent layout
        row_frame.grid_columnconfigure(0, weight=1)
        row_frame.grid_columnconfigure(1, weight=3)
        row_frame.grid_columnconfigure(2, weight=1)
        row_frame.grid_columnconfigure(3, weight=1)
        row_frame.grid_columnconfigure(4, weight=1)

        team_name = row["teamName"]
        wins = row["wins"]
        losses = row["losses"]
        total_points = row["totalPoints"] if row["totalPoints"] is not None else 0

        ctk.CTkLabel(row_frame, text=str(idx)).grid(row=0, column=0, padx=8, pady=6, sticky="w")
        ctk.CTkLabel(row_frame, text=team_name).grid(row=0, column=1, padx=8, pady=6, sticky="w")
        ctk.CTkLabel(row_frame, text=str(wins)).grid(row=0, column=2, padx=8, pady=6, sticky="w")
        ctk.CTkLabel(row_frame, text=str(losses)).grid(row=0, column=3, padx=8, pady=6, sticky="w")
        ctk.CTkLabel(row_frame, text=str(total_points)).grid(row=0, column=4, padx=8, pady=6, sticky="w")


def build_mvp_panel():
    """
    Build the MVP panel (right side). This is called once when the standings view is first created.
    After that, call refresh_mvp_controls() to update teams, players, years, and current MVP display.
    """
    mvp_frame = _widgets.get("mvp_frame")
    if not mvp_frame:
        container = _widgets.get("container")
        if container:
            refresh_standings_table(container)
        return

    # Clear existing MVP frame children
    for w in mvp_frame.winfo_children():
        try:
            w.destroy()
        except Exception:
            pass

    # Title
    ctk.CTkLabel(mvp_frame, text="Manual MVP Selector", font=ctk.CTkFont(size=16, weight="bold")).grid(row=0, column=0, padx=12, pady=(12,6), sticky="w")

    # Initialize vars
    team_var = ctk.StringVar(value="Select Team")
    player_var = ctk.StringVar(value="Select Player")
    year_var = ctk.StringVar(value="Select Year")

    _widgets["team_var"] = team_var
    _widgets["player_var"] = player_var
    _widgets["year_var"] = year_var

    # Team dropdown
    ctk.CTkLabel(mvp_frame, text="Team:").grid(row=1, column=0, padx=12, pady=(8,2), sticky="w")
    team_opt = ctk.CTkOptionMenu(mvp_frame, values=["Select Team"], variable=team_var)
    team_opt.grid(row=2, column=0, padx=12, pady=(0,8), sticky="ew")
    _widgets["team_opt"] = team_opt

    # Player dropdown
    ctk.CTkLabel(mvp_frame, text="Player:").grid(row=3, column=0, padx=12, pady=(8,2), sticky="w")
    player_opt = ctk.CTkOptionMenu(mvp_frame, values=["Select Player"], variable=player_var)
    player_opt.grid(row=4, column=0, padx=12, pady=(0,8), sticky="ew")
    _widgets["player_opt"] = player_opt

    # Year dropdown
    ctk.CTkLabel(mvp_frame, text="Year:").grid(row=5, column=0, padx=12, pady=(8,2), sticky="w")
    year_opt = ctk.CTkOptionMenu(mvp_frame, values=["Select Year"], variable=year_var)
    year_opt.grid(row=6, column=0, padx=12, pady=(0,8), sticky="ew")
    _widgets["year_opt"] = year_opt

    # Current MVP label
    current_lbl = ctk.CTkLabel(mvp_frame, text="Current MVP: —", wraplength=220, anchor="w", justify="left")
    current_lbl.grid(row=7, column=0, padx=12, pady=(12,6), sticky="w")
    _widgets["current_lbl"] = current_lbl

    # Buttons
    btn_frame = ctk.CTkFrame(mvp_frame, fg_color="#1F1F1F")
    btn_frame.grid(row=8, column=0, padx=12, pady=8, sticky="ew")
    btn_frame.grid_columnconfigure(0, weight=1)
    btn_frame.grid_columnconfigure(1, weight=1)

    assign_btn = ctk.CTkButton(btn_frame, text="Assign MVP", fg_color="#4CAF50")
    assign_btn.grid(row=0, column=0, padx=6, pady=6, sticky="ew")
    clear_btn = ctk.CTkButton(btn_frame, text="Clear MVP", fg_color="#FF6B6B")
    clear_btn.grid(row=0, column=1, padx=6, pady=6, sticky="ew")

    _widgets["assign_btn"] = assign_btn
    _widgets["clear_btn"] = clear_btn

    # Wire event handlers (use variable trace and optionmenu commands as fallbacks)
    try:
        team_opt.configure(command=lambda *_: on_team_change())
    except Exception:
        team_var.trace_add("write", lambda *_: on_team_change())

    try:
        year_opt.configure(command=lambda *_: on_year_change())
    except Exception:
        year_var.trace_add("write", lambda *_: on_year_change())

    assign_btn.configure(command=assign_mvp)
    clear_btn.configure(command=clear_mvp)

    # Fill initial values
    refresh_mvp_controls()


# --------- Helpers for MVP panel data loading and updates ---------
def load_team_map():
    """Return ordered list of team names and a mapping name->id"""
    cur = mydb.cursor()
    try:
        cur.execute("SELECT id, teamName FROM teams ORDER BY teamName")
        rows = cur.fetchall()
        team_names = []
        mapping = {}
        for r in rows:
            tid = r['id']
            name = r['teamName']
            team_names.append(name)
            mapping[name] = tid
        return team_names, mapping
    finally:
        try:
            cur.close()
        except Exception:
            pass


def load_players_for_team(team_id):
    """Return list of (display, id) for players on team ordered by jersey then name"""
    if not team_id:
        return []
    cur = mydb.cursor()
    try:
        cur.execute("SELECT id, name, jerseyNumber FROM players WHERE team_id = ? ORDER BY jerseyNumber, name", (team_id,))
        rows = cur.fetchall()
        out = []
        for r in rows:
            jid = r['id']
            name = r['name']
            jersey = r['jerseyNumber']
            disp = f"#{jersey} - {name}" if jersey not in (None, '') else name
            out.append((disp, jid))
        return out
    finally:
        try:
            cur.close()
        except Exception:
            pass


def load_years():
    """Return list of years (strings) that have scheduled games, newest first"""
    cur = mydb.cursor()
    try:
        cur.execute("SELECT DISTINCT substr(game_date,1,4) as yr FROM games WHERE game_date IS NOT NULL ORDER BY yr DESC")
        rows = cur.fetchall()
        years = []
        for r in rows:
            y = r['yr']
            if y:
                years.append(str(y))
        return years
    finally:
        try:
            cur.close()
        except Exception:
            pass


# --------- MVP panel event handlers and actions ---------
def on_team_change(*_):
    """Update player dropdown when team changes."""
    team_var = _widgets.get("team_var")
    player_opt = _widgets.get("player_opt")
    team_map = _widgets.get("team_map") or {}
    player_var = _widgets.get("player_var")

    sel = team_var.get() if team_var else None
    # Reset player selection
    if player_var:
        player_var.set("Select Player")
    try:
        if sel == "Select Team" or sel not in team_map:
            if player_opt:
                player_opt.configure(values=["Select Player"])
                _widgets["player_mappings"][id(player_opt)] = {}
            return
        tid = team_map.get(sel)
        players = load_players_for_team(tid)
        if not players:
            if player_opt:
                player_opt.configure(values=["Select Player"])
                _widgets["player_mappings"][id(player_opt)] = {}
            return
        p_display = [p[0] for p in players]
        p_values = ["Select Player"] + p_display
        # set mapping on closure attribute for later lookup
        _widgets["player_mappings"][id(player_opt)] = {p[0]: p[1] for p in players}
        player_opt.configure(values=p_values)
    except Exception:
        try:
            if player_opt:
                player_opt.configure(values=["Select Player"])
                _widgets["player_mappings"][id(player_opt)] = {}
        except Exception:
            pass


def on_year_change(*_):
    """
    Show current MVP for selected year and set team/player selection if present.
    Only updates MVP controls; it does not rebuild standings.
    """
    y = _widgets.get("year_var").get() if _widgets.get("year_var") else None
    current_lbl = _widgets.get("current_lbl")
    team_var = _widgets.get("team_var")
    player_var = _widgets.get("player_var")

    # default label
    if current_lbl:
        current_lbl.configure(text="Current MVP: —")
    # reset team/player selection
    if team_var:
        team_var.set("Select Team")
    if player_var:
        player_var.set("Select Player")
    # refresh player options to placeholder
    try:
        player_opt = _widgets.get("player_opt")
        if player_opt:
            player_opt.configure(values=["Select Player"])
            _widgets["player_mappings"][id(player_opt)] = {}
    except Exception:
        pass

    if not y or y == "Select Year":
        return

    # Query for MVP in that year
    cur = mydb.cursor()
    try:
        cur.execute("""
            SELECT m.player_id, p.name AS player_name, p.jerseyNumber, m.team_id, t.teamName
            FROM mvps m
            JOIN players p ON m.player_id = p.id
            JOIN teams t ON m.team_id = t.id
            WHERE m.year = ?
            """, (y,))
        r = cur.fetchone()
        if r:
            pname = r['player_name']
            jersey = r['jerseyNumber']
            tname = r['teamName']
            display = f"#{jersey} - {pname}" if jersey not in (None, '') else pname
            if current_lbl:
                current_lbl.configure(text=f"Current MVP: {display} ({tname})")
            # set team dropdown and populate players for that team
            try:
                team_map = _widgets.get("team_map") or {}
                player_opt = _widgets.get("player_opt")
                if tname in team_map:
                    # set team, trigger player population
                    if team_var:
                        team_var.set(tname)
                    on_team_change()
                    # ensure mapping exists for player_opt and set player_var
                    mappings = _widgets["player_mappings"].get(id(player_opt), {}) or {}
                    if display in mappings:
                        if player_var:
                            player_var.set(display)
                    else:
                        # attempt to refresh mapping from DB
                        players = load_players_for_team(team_map[tname])
                        p_display = [p[0] for p in players]
                        p_values = ["Select Player"] + p_display
                        if player_opt:
                            player_opt.configure(values=p_values)
                            _widgets["player_mappings"][id(player_opt)] = {p[0]: p[1] for p in players}
                            if display in _widgets["player_mappings"][id(player_opt)]:
                                if player_var:
                                    player_var.set(display)
                else:
                    # team not found - leave defaults
                    pass
            except Exception:
                pass
        else:
            if current_lbl:
                current_lbl.configure(text="Current MVP: —")
    finally:
        try:
            cur.close()
        except Exception:
            pass


def refresh_mvp_controls():
    """
    Refresh only the MVP controls (teams list, years list, and current MVP display).
    This will preserve the container and other UI; used after assign/clear to update only the right panel.
    """
    # Ensure the panel exists
    mvp_frame = _widgets.get("mvp_frame")
    if not mvp_frame:
        container = _widgets.get("container")
        if container:
            refresh_standings_table(container)
        return

    # Load team map and update option values
    team_names, team_map = load_team_map()
    _widgets["team_map"] = team_map
    team_values = ["Select Team"] + team_names
    team_opt = _widgets.get("team_opt")
    if team_opt:
        try:
            team_opt.configure(values=team_values)
        except Exception:
            # fallback: set variable and reconfigure widget
            pass

    # Load years and update option
    years = load_years() or []
    year_values_display = ["Select Year"] + years
    year_opt = _widgets.get("year_opt")
    if year_opt:
        try:
            year_opt.configure(values=year_values_display)
        except Exception:
            pass

    # Clear current label and selections (but keep whatever the user might have selected if they picked year already)
    # If a year is currently selected, re-evaluate and display the MVP for that year.
    try:
        y = _widgets.get("year_var").get()
    except Exception:
        y = None

    # If selected year is no longer valid, reset
    if not y or y == "Select Year" or (y not in years):
        try:
            _widgets.get("year_var").set("Select Year")
        except Exception:
            pass

    # Trigger on_year_change to refresh current MVP and selections
    on_year_change()


def assign_mvp():
    """
    Assign the selected player as MVP for the selected year.
    Only updates DB and then refreshes MVP controls + standings counts.
    """
    year_var = _widgets.get("year_var")
    player_opt = _widgets.get("player_opt")
    player_var = _widgets.get("player_var")
    team_var = _widgets.get("team_var")
    team_map = _widgets.get("team_map") or {}

    y = year_var.get() if year_var else None
    if not y or y == "Select Year":
        messagebox.showwarning("Missing", "Please select a year.")
        return
    pdisp = player_var.get() if player_var else None
    if not pdisp or pdisp == "Select Player":
        messagebox.showwarning("Missing", "Please select a player.")
        return

    # find player id from mappings
    mappings = _widgets["player_mappings"].get(id(player_opt), {}) or {}
    pid = mappings.get(pdisp)
    if not pid:
        messagebox.showwarning("Not Found", "Selected player not found. Try reloading the table.")
        return

    # find team id
    tname = team_var.get() if team_var else None
    if not tname or tname == "Select Team":
        messagebox.showwarning("Missing", "Please select the player's team.")
        return
    tid = team_map.get(tname)
    if not tid:
        messagebox.showwarning("Not Found", "Selected team not found.")
        return

    # Ensure only one MVP per year: remove any existing entries for this year, then insert
    cur = mydb.cursor()
    try:
        cur.execute("DELETE FROM mvps WHERE year = ?", (y,))
        cur.execute("INSERT INTO mvps (player_id, team_id, year) VALUES (?, ?, ?)", (pid, tid, y))
        mydb.commit()
    except Exception as e:
        try:
            cur.close()
        except Exception:
            pass
        messagebox.showerror("Error", f"Failed to assign MVP: {e}")
        return
    finally:
        try:
            cur.close()
        except Exception:
            pass

    messagebox.showinfo("Assigned", f"MVP for {y} set.")
    # Refresh only the MVP controls and the standings counts (not the whole view)
    try:
        refresh_mvp_controls()
        refresh_standings_rows()
    except Exception:
        # fallback: rebuild everything if partial refresh fails
        container = _widgets.get("container")
        if container:
            refresh_standings_table(container)


def clear_mvp():
    """Clear the MVP for the selected year, then refresh MVP controls + standings counts."""
    year_var = _widgets.get("year_var")
    y = year_var.get() if year_var else None
    if not y or y == "Select Year":
        messagebox.showwarning("Missing", "Please select a year.")
        return
    if not messagebox.askyesno("Clear MVP", f"Clear MVP for {y}?"):
        return
    cur = mydb.cursor()
    try:
        cur.execute("DELETE FROM mvps WHERE year = ?", (y,))
        mydb.commit()
    except Exception as e:
        try:
            cur.close()
        except Exception:
            pass
        messagebox.showerror("Error", f"Failed to clear MVP: {e}")
        return
    finally:
        try:
            cur.close()
        except Exception:
            pass

    messagebox.showinfo("Cleared", f"MVP for {y} cleared.")
    try:
        refresh_mvp_controls()
        refresh_standings_rows()
    except Exception:
        container = _widgets.get("container")
        if container:
            refresh_standings_table(container)
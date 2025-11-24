import customtkinter as ctk
from tkinter import messagebox
from datetime import date as _date, datetime
from theDB import mydb

# Reuse season helper from scheduleGameTab to avoid duplicate logic.
# scheduleGameTab defines the canonical _season_range_for_year mapping used elsewhere.
try:
    from scheduleGameTab import _season_range_for_year
except Exception:
    # Fallback: define a minimal copy only if import fails (keeps module robust in tests)
    def _season_range_for_year(season, year):
        mapping = {
            "Pre-season": ((9, 25), (10, 16)),
            "Regular Season": ((10, 17), (4, 16)),
            "Play-in": ((4, 17), (4, 24)),
            "Playoff": ((4, 25), (6, 8)),
            "Finals": ((6, 9), (6, 24)),
            "Off-season": ((6, 25), (9, 24)),
        }
        if season not in mapping:
            return None, None
        (sm, sd), (em, ed) = mapping[season]
        start = _date(year, sm, sd)
        if (em, ed) < (sm, sd):
            end = _date(year + 1, em, ed)
        else:
            end = _date(year, em, ed)
        return start, end


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


# Small helper that uses the canonical _season_range_for_year to create a season window
def _season_windows_for_year(year):
    start, _ = _season_range_for_year("Pre-season", year)
    _, end = _season_range_for_year("Off-season", year + 1)
    return start, end


def _compute_season_start_years_with_games():
    """
    Determine season-start years that have at least one scheduled game within
    their season window (Pre-season of year -> Off-season of year+1).
    Returns list of integers (years), newest first.
    """
    cursor = mydb.cursor()
    try:
        cursor.execute("SELECT MIN(substr(game_date,1,4)) as miny, MAX(substr(game_date,1,4)) as maxy FROM games WHERE game_date IS NOT NULL")
        r = cursor.fetchone()
        if not r:
            return []
        try:
            miny = int(r['miny']) if r and r['miny'] else None
        except Exception:
            miny = None
        try:
            maxy = int(r['maxy']) if r and r['maxy'] else None
        except Exception:
            maxy = None

        if miny is None or maxy is None:
            return []

        years_with_games = []
        # Check season-start candidates from miny-1 .. maxy to account for windows crossing years
        start_candidate = max(1900, miny - 1)
        end_candidate = maxy

        for y in range(start_candidate, end_candidate + 1):
            s, e = _season_windows_for_year(y)
            cursor.execute("SELECT 1 FROM games WHERE game_date BETWEEN ? AND ? LIMIT 1", (s.isoformat(), e.isoformat()))
            if cursor.fetchone():
                years_with_games.append(y)

        years_with_games.sort(reverse=True)
        return years_with_games
    finally:
        try:
            cursor.close()
        except Exception:
            pass


def _format_season_header(year):
    s, e = _season_windows_for_year(year)
    return f"Season {year} — {s.isoformat()} → {e.isoformat()}"


def refresh_standings_table(container):
    """
    Build the standings view and MVP controls container (only once per container).
    Subsequent updates should call refresh_standings_rows() and refresh_mvp_controls().
    """
    _widgets["container"] = container

    for w in container.winfo_children():
        try:
            w.destroy()
        except Exception:
            pass

    content = ctk.CTkFrame(container, fg_color="#101010")
    content.pack(fill="both", expand=True, padx=8, pady=6)
    try:
        content.grid_columnconfigure(0, weight=3)
        content.grid_columnconfigure(1, weight=1)
        content.grid_rowconfigure(0, weight=1)
    except Exception:
        pass
    _widgets["content"] = content

    standings_frame = ctk.CTkScrollableFrame(content, width=700, height=450, fg_color="#0F0F0F")
    standings_frame.grid(row=0, column=0, sticky="nsew", padx=(0,8), pady=4)
    _widgets["standings_frame"] = standings_frame

    mvp_frame = ctk.CTkFrame(content, fg_color="#1A1A1A", corner_radius=8)
    mvp_frame.grid(row=0, column=1, sticky="nsew", padx=(8,0), pady=4)
    mvp_frame.grid_columnconfigure(0, weight=1)
    _widgets["mvp_frame"] = mvp_frame

    refresh_standings_rows()
    build_mvp_panel()

    try:
        if isinstance(refs, dict):
            refs['standings_table'] = container
    except Exception:
        pass


def refresh_standings_rows():
    """
    Refresh only the standings rows (left side).
    Groups standings by season-start year (Pre-season..next year's Off-season),
    newest season first. Only teams that played within the season window are shown.
    """
    standings_frame = _widgets.get("standings_frame")
    if not standings_frame:
        container = _widgets.get("container")
        if container:
            refresh_standings_table(container)
        return

    for w in standings_frame.winfo_children():
        try:
            w.destroy()
        except Exception:
            pass

    years = _compute_season_start_years_with_games()
    if not years:
        ctk.CTkLabel(standings_frame, text="No scheduled seasons found.", anchor="w").pack(padx=8, pady=8)
        return

    for year in years:
        start_dt, end_dt = _season_windows_for_year(year)
        header_frame = ctk.CTkFrame(standings_frame, fg_color="#1E1E1E")
        header_frame.pack(fill="x", padx=8, pady=(12, 6))
        # two columns: left = season header, right = MVP
        header_frame.grid_columnconfigure(0, weight=1)
        header_frame.grid_columnconfigure(1, weight=0)

        header_lbl = ctk.CTkLabel(header_frame, text=_format_season_header(year), font=ctk.CTkFont(size=14, weight="bold"))
        header_lbl.grid(row=0, column=0, sticky="w", padx=8, pady=6)

        # MVP display beside the season header (right aligned)
        mvp_text = "MVP: —"
        cur = mydb.cursor()
        try:
            cur.execute("""
                SELECT p.name AS player_name, p.jerseyNumber, t.teamName
                FROM mvps m
                JOIN players p ON m.player_id = p.id
                JOIN teams t ON m.team_id = t.id
                WHERE m.year = ?
                LIMIT 1
            """, (year,))
            mvpr = cur.fetchone()
            if mvpr:
                pname = mvpr['player_name']
                jersey = mvpr['jerseyNumber']
                tname = mvpr['teamName']
                display = f"#{jersey} - {pname}" if jersey not in (None, '') else pname
                mvp_text = f"MVP: {display} ({tname})"
        finally:
            try:
                cur.close()
            except Exception:
                pass

        mvp_lbl = ctk.CTkLabel(header_frame, text=mvp_text, font=ctk.CTkFont(size=12), text_color="#FFD700")
        mvp_lbl.grid(row=0, column=1, sticky="e", padx=8, pady=6)

        # Column headers for this season block
        cols = ctk.CTkFrame(standings_frame, fg_color="#1F1F1F")
        cols.pack(fill="x", padx=8, pady=(0,4))
        cols.grid_columnconfigure(0, weight=1)
        cols.grid_columnconfigure(1, weight=3)
        cols.grid_columnconfigure(2, weight=1)
        cols.grid_columnconfigure(3, weight=1)
        cols.grid_columnconfigure(4, weight=1)

        ctk.CTkLabel(cols, text="Rank", font=ctk.CTkFont(size=12, weight="bold")).grid(row=0, column=0, padx=8, pady=4, sticky="w")
        ctk.CTkLabel(cols, text="Team", font=ctk.CTkFont(size=12, weight="bold")).grid(row=0, column=1, padx=8, pady=4, sticky="w")
        ctk.CTkLabel(cols, text="Wins", font=ctk.CTkFont(size=12, weight="bold")).grid(row=0, column=2, padx=8, pady=4, sticky="w")
        ctk.CTkLabel(cols, text="Losses", font=ctk.CTkFont(size=12, weight="bold")).grid(row=0, column=3, padx=8, pady=4, sticky="w")
        ctk.CTkLabel(cols, text="Total Points", font=ctk.CTkFont(size=12, weight="bold")).grid(row=0, column=4, padx=8, pady=4, sticky="w")

        cursor = mydb.cursor()
        try:
            cursor.execute("""
                SELECT
                    t.id,
                    t.teamName,
                    COALESCE(t.totalPoints, 0) AS totalPoints,
                    COALESCE((SELECT COUNT(*) FROM games g WHERE g.is_final = 1 AND g.winner_team_id = t.id AND g.game_date BETWEEN ? AND ?), 0) AS wins,
                    COALESCE((SELECT COUNT(*) FROM games g
                              WHERE g.is_final = 1
                                AND (g.home_team_id = t.id OR g.away_team_id = t.id)
                                AND (g.winner_team_id IS NOT NULL AND g.winner_team_id != t.id)
                                AND g.game_date BETWEEN ? AND ?
                             ), 0) AS losses
                FROM teams t
                WHERE EXISTS (
                    SELECT 1 FROM games g2
                    WHERE (g2.home_team_id = t.id OR g2.away_team_id = t.id)
                      AND g2.game_date BETWEEN ? AND ?
                )
                ORDER BY wins DESC, totalPoints DESC, t.teamName COLLATE NOCASE
            """, (start_dt.isoformat(), end_dt.isoformat(),
                  start_dt.isoformat(), end_dt.isoformat(),
                  start_dt.isoformat(), end_dt.isoformat()))
            teams = cursor.fetchall()
        finally:
            try:
                cursor.close()
            except Exception:
                pass

        if not teams:
            empty_lbl = ctk.CTkLabel(standings_frame, text="(No teams played in this season window)", anchor="w", text_color="#BBBBBB")
            empty_lbl.pack(fill="x", padx=16, pady=(6,8))
            continue

        for idx, row in enumerate(teams, start=1):
            row_frame = ctk.CTkFrame(standings_frame, fg_color="#2A2A2A")
            row_frame.pack(fill="x", padx=8, pady=2)
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
    Build the MVP panel (right side). Constructed once; refresh_mvp_controls updates values.
    """
    mvp_frame = _widgets.get("mvp_frame")
    if not mvp_frame:
        container = _widgets.get("container")
        if container:
            refresh_standings_table(container)
        return

    for w in mvp_frame.winfo_children():
        try:
            w.destroy()
        except Exception:
            pass

    ctk.CTkLabel(mvp_frame, text="Manual MVP Selector", font=ctk.CTkFont(size=16, weight="bold")).grid(row=0, column=0, padx=12, pady=(12,6), sticky="w")

    team_var = ctk.StringVar(value="Select Team")
    player_var = ctk.StringVar(value="Select Player")
    year_var = ctk.StringVar(value="Select Year")

    _widgets["team_var"] = team_var
    _widgets["player_var"] = player_var
    _widgets["year_var"] = year_var

    ctk.CTkLabel(mvp_frame, text="Team:").grid(row=1, column=0, padx=12, pady=(8,2), sticky="w")
    team_opt = ctk.CTkOptionMenu(mvp_frame, values=["Select Team"], variable=team_var)
    team_opt.grid(row=2, column=0, padx=12, pady=(0,8), sticky="ew")
    _widgets["team_opt"] = team_opt

    ctk.CTkLabel(mvp_frame, text="Player:").grid(row=3, column=0, padx=12, pady=(8,2), sticky="w")
    player_opt = ctk.CTkOptionMenu(mvp_frame, values=["Select Player"], variable=player_var)
    player_opt.grid(row=4, column=0, padx=12, pady=(0,8), sticky="ew")
    _widgets["player_opt"] = player_opt

    ctk.CTkLabel(mvp_frame, text="Year:").grid(row=5, column=0, padx=12, pady=(8,2), sticky="w")
    year_opt = ctk.CTkOptionMenu(mvp_frame, values=["Select Year"], variable=year_var)
    year_opt.grid(row=6, column=0, padx=12, pady=(0,8), sticky="ew")
    _widgets["year_opt"] = year_opt

    current_lbl = ctk.CTkLabel(mvp_frame, text="Current MVP: —", wraplength=220, anchor="w", justify="left")
    current_lbl.grid(row=7, column=0, padx=12, pady=(12,6), sticky="w")
    _widgets["current_lbl"] = current_lbl

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

    refresh_mvp_controls()


# Data loaders (compact and non-redundant)
def load_team_map():
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
    years = _compute_season_start_years_with_games()
    return [str(y) for y in years]


# MVP handlers (unchanged logic, cleaned to rely on compact helpers)
def on_team_change(*_):
    team_var = _widgets.get("team_var")
    player_opt = _widgets.get("player_opt")
    team_map = _widgets.get("team_map") or {}
    player_var = _widgets.get("player_var")

    sel = team_var.get() if team_var else None
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
        _widgets["player_mappings"][id(player_opt)] = {p[0]: p[1] for p in players}
        player_opt.configure(values=p_values)
    except Exception:
        if player_opt:
            try:
                player_opt.configure(values=["Select Player"])
                _widgets["player_mappings"][id(player_opt)] = {}
            except Exception:
                pass


def on_year_change(*_):
    y = _widgets.get("year_var").get() if _widgets.get("year_var") else None
    current_lbl = _widgets.get("current_lbl")
    team_var = _widgets.get("team_var")
    player_var = _widgets.get("player_var")

    if current_lbl:
        current_lbl.configure(text="Current MVP: —")
    if team_var:
        team_var.set("Select Team")
    if player_var:
        player_var.set("Select Player")
    try:
        player_opt = _widgets.get("player_opt")
        if player_opt:
            player_opt.configure(values=["Select Player"])
            _widgets["player_mappings"][id(player_opt)] = {}
    except Exception:
        pass

    if not y or y == "Select Year":
        return

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
            try:
                team_map = _widgets.get("team_map") or {}
                player_opt = _widgets.get("player_opt")
                if tname in team_map:
                    if team_var:
                        team_var.set(tname)
                    on_team_change()
                    mappings = _widgets["player_mappings"].get(id(player_opt), {}) or {}
                    if display in mappings:
                        if player_var:
                            player_var.set(display)
                    else:
                        players = load_players_for_team(team_map[tname])
                        p_display = [p[0] for p in players]
                        p_values = ["Select Player"] + p_display
                        if player_opt:
                            player_opt.configure(values=p_values)
                            _widgets["player_mappings"][id(player_opt)] = {p[0]: p[1] for p in players}
                            if display in _widgets["player_mappings"][id(player_opt)]:
                                if player_var:
                                    player_var.set(display)
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
    mvp_frame = _widgets.get("mvp_frame")
    if not mvp_frame:
        container = _widgets.get("container")
        if container:
            refresh_standings_table(container)
        return

    team_names, team_map = load_team_map()
    _widgets["team_map"] = team_map
    team_values = ["Select Team"] + team_names
    team_opt = _widgets.get("team_opt")
    if team_opt:
        try:
            team_opt.configure(values=team_values)
        except Exception:
            pass

    years = load_years() or []
    year_values_display = ["Select Year"] + years
    year_opt = _widgets.get("year_opt")
    if year_opt:
        try:
            year_opt.configure(values=year_values_display)
        except Exception:
            pass

    try:
        y = _widgets.get("year_var").get()
    except Exception:
        y = None

    if not y or y == "Select Year" or (y not in years):
        try:
            _widgets.get("year_var").set("Select Year")
        except Exception:
            pass

    on_year_change()


def assign_mvp():
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

    mappings = _widgets["player_mappings"].get(id(player_opt), {}) or {}
    pid = mappings.get(pdisp)
    if not pid:
        messagebox.showwarning("Not Found", "Selected player not found. Try reloading the table.")
        return

    tname = team_var.get() if team_var else None
    if not tname or tname == "Select Team":
        messagebox.showwarning("Missing", "Please select the player's team.")
        return
    tid = team_map.get(tname)
    if not tid:
        messagebox.showwarning("Not Found", "Selected team not found.")
        return

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
    try:
        refresh_mvp_controls()
        refresh_standings_rows()
    except Exception:
        container = _widgets.get("container")
        if container:
            refresh_standings_table(container)


def clear_mvp():
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
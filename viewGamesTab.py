import customtkinter as ctk
from tkinter import messagebox
from datetime import datetime, date as _date
from theDB import *

refs = {}
# keep a local fallback scheduled_games list, but prefer scheduleGameTab.scheduled_games when available
scheduled_games = []

rn = datetime.now()

from scheduleGameTab import show_game_details

try:
    from scheduleGameTab import _season_range_for_year
except Exception:
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


def _season_windows_for_year(year):
    """Return window (start, end) spanning Pre-season of year through Off-season of year+1."""
    start, _ = _season_range_for_year("Pre-season", year)
    _, end = _season_range_for_year("Off-season", year + 1)
    return start, end


def _season_from_iso(date_iso):
    try:
        dt = datetime.strptime(date_iso, "%Y-%m-%d").date()
    except Exception:
        return ""
    seasons = [
        "Pre-season",
        "Regular Season",
        "Play-in",
        "Playoff",
        "Finals",
        "Off-season"
    ]
    for season in seasons:
        for anchor in (dt.year, dt.year - 1):
            start, end = _season_range_for_year(season, anchor)
            if start is None:
                continue
            if start <= dt <= end:
                return season
    return ""


def _parse_iso(date_iso):
    try:
        if not date_iso:
            return None
        return datetime.strptime(date_iso, "%Y-%m-%d").date()
    except Exception:
        return None


def _compute_season_start_years_with_games():
    cur = mydb.cursor()
    try:
        cur.execute("SELECT MIN(substr(game_date,1,4)) as miny, MAX(substr(game_date,1,4)) as maxy FROM games WHERE game_date IS NOT NULL")
        r = cur.fetchone()
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
        start_candidate = max(1900, miny - 1)
        end_candidate = maxy

        for y in range(start_candidate, end_candidate + 1):
            s, e = _season_windows_for_year(y)
            cur.execute("SELECT 1 FROM games WHERE game_date BETWEEN ? AND ? LIMIT 1", (s.isoformat(), e.isoformat()))
            if cur.fetchone():
                years_with_games.append(y)

        years_with_games.sort(reverse=True)
        return years_with_games
    finally:
        try:
            cur.close()
        except Exception:
            pass


def _format_season_header(year):
    s, e = _season_windows_for_year(year)
    end_year = e.year if e is not None else year
    return f"Season {end_year} — {s.isoformat()} → {e.isoformat()}"


def _get_scheduled_games_source():
    """
    Prefer scheduleGameTab.scheduled_games when available (keeps a single source of truth).
    Otherwise fall back to the local scheduled_games list.
    """
    try:
        import scheduleGameTab as sgt
        if hasattr(sgt, 'scheduled_games'):
            return sgt.scheduled_games
    except Exception:
        pass
    return scheduled_games


def on_view_click(index, game):
    # Set selected game
    refs["selected_game"] = {
        "id": game.get("id"),
        "team1_id": game.get("team1_id"),
        "team2_id": game.get("team2_id")
    }

    panel = refs.get("game_details_frame")
    if not panel:
        return

    for w in panel.winfo_children():
        try:
            w.destroy()
        except Exception:
            pass

    details_label = ctk.CTkLabel(
        panel,
        text="Loading...",
        justify="left",
        anchor="nw"
    )
    details_label.pack(fill="both", expand=True, padx=10, pady=10)

    refs["details_content"] = details_label

    show_game_details(index)

    panel.update()

    refs["selected_game"] = {
        "id": game.get("id"),
        "team1_id": game.get("team1_id"),
        "team2_id": game.get("team2_id")
    }


def refresh_scheduled_games_table(table_frame):
    """
    Refresh the table UI using the canonical scheduled games list (from scheduleGameTab if available).
    If the scheduled games list is empty, attempt to load from DB using scheduleGameTab.load_scheduled_games_from_db().
    """
    for widget in table_frame.winfo_children():
        try:
            widget.destroy()
        except Exception:
            pass

    # get canonical source of scheduled games
    src_games = _get_scheduled_games_source()

    # if no games loaded, try to load from DB (best-effort)
    if not src_games:
        try:
            import scheduleGameTab as sgt
            if hasattr(sgt, 'load_scheduled_games_from_db'):
                sgt.load_scheduled_games_from_db()
                src_games = _get_scheduled_games_source()
        except Exception:
            pass

    id_to_index = {}
    for idx, g in enumerate(src_games):
        gid = g.get('id')
        if gid is not None:
            id_to_index[gid] = idx

    years = _compute_season_start_years_with_games()

    if not years:
        header_frame = ctk.CTkFrame(table_frame, fg_color="#1F1F1F")
        header_frame.pack(fill="x", padx=8, pady=4)
        ctk.CTkLabel(header_frame, text="No scheduled seasons found.", font=ctk.CTkFont(size=14, weight="bold")).pack(padx=8, pady=8)
        return

    for year in years:
        start_dt, end_dt = _season_windows_for_year(year)

        header_frame = ctk.CTkFrame(table_frame, fg_color="#1E1E1E")
        header_frame.pack(fill="x", padx=8, pady=(12, 6))
        header_frame.grid_columnconfigure(0, weight=1)
        header_lbl = ctk.CTkLabel(header_frame, text=_format_season_header(year), font=ctk.CTkFont(size=14, weight="bold"))
        header_lbl.grid(row=0, column=0, sticky="w", padx=8, pady=6)

        cols = ctk.CTkFrame(table_frame, fg_color="#1F1F1F")
        cols.pack(fill="x", padx=8, pady=(0, 4))
        for ci in range(10):
            cols.grid_columnconfigure(ci, weight=(1 if ci <= 6 else 0))

        ctk.CTkLabel(cols, text="Team 1", font=ctk.CTkFont(size=14, weight="bold")).grid(row=0, column=0, padx=8, pady=4, sticky="w")
        ctk.CTkLabel(cols, text="Team 2", font=ctk.CTkFont(size=14, weight="bold")).grid(row=0, column=1, padx=8, pady=4, sticky="w")
        ctk.CTkLabel(cols, text="Venue", font=ctk.CTkFont(size=14, weight="bold")).grid(row=0, column=2, padx=8, pady=4, sticky="w")
        ctk.CTkLabel(cols, text="Date", font=ctk.CTkFont(size=14, weight="bold")).grid(row=0, column=3, padx=8, pady=4, sticky="w")
        ctk.CTkLabel(cols, text="Season", font=ctk.CTkFont(size=14, weight="bold")).grid(row=0, column=4, padx=8, pady=4, sticky="w")
        ctk.CTkLabel(cols, text="Time", font=ctk.CTkFont(size=14, weight="bold")).grid(row=0, column=5, padx=8, pady=4, sticky="w")
        ctk.CTkLabel(cols, text="Status", font=ctk.CTkFont(size=14, weight="bold")).grid(row=0, column=6, padx=8, pady=4, sticky="w")
        ctk.CTkLabel(cols, text="View", font=ctk.CTkFont(size=14, weight="bold")).grid(row=0, column=7, padx=8, pady=4, sticky="w")
        ctk.CTkLabel(cols, text="Edit", font=ctk.CTkFont(size=14, weight="bold")).grid(row=0, column=8, padx=8, pady=4, sticky="w")
        ctk.CTkLabel(cols, text="Delete", font=ctk.CTkFont(size=14, weight="bold")).grid(row=0, column=9, padx=8, pady=4, sticky="w")

        group_games = []
        for g in src_games:
            dt = _parse_iso(g.get('date'))
            if dt and start_dt <= dt <= end_dt:
                group_games.append(g)

        def _sort_key(g):
            dt = _parse_iso(g.get('date')) or _date.min
            st = g.get('start') or '00:00'
            return (dt, st)
        group_games.sort(key=_sort_key)

        if not group_games:
            empty_lbl = ctk.CTkLabel(table_frame, text="(No games in this season window)", anchor="w", text_color="#BBBBBB")
            empty_lbl.pack(fill="x", padx=16, pady=(6, 8))
            continue

        for game in group_games:
            gid = game.get('id')
            idx = id_to_index.get(gid, None)
            row_frame = ctk.CTkFrame(table_frame, fg_color="#2A2A2A")
            row_frame.pack(fill="x", padx=8, pady=2)

            for ci in range(10):
                row_frame.grid_columnconfigure(ci, weight=(1 if ci <= 6 else 0))

            ctk.CTkLabel(row_frame, text=game.get('team1')).grid(row=0, column=0, padx=8, pady=4, sticky="w")
            ctk.CTkLabel(row_frame, text=game.get('team2')).grid(row=0, column=1, padx=8, pady=4, sticky="w")
            ctk.CTkLabel(row_frame, text=game.get('venue')).grid(row=0, column=2, padx=8, pady=4, sticky="w")
            ctk.CTkLabel(row_frame, text=game.get('date')).grid(row=0, column=3, padx=8, pady=4, sticky="w")

            season_name = _season_from_iso(game.get('date') or "")
            ctk.CTkLabel(row_frame, text=season_name).grid(row=0, column=4, padx=8, pady=4, sticky="w")

            ctk.CTkLabel(row_frame, text=f"{game.get('start', '00:00')} - {game.get('end', '00:00')}").grid(row=0, column=5, padx=8, pady=4, sticky="w")

            try:
                cursor = mydb.cursor()
                try:
                    cursor.execute("SELECT is_final FROM games WHERE id = ?", (gid,))
                    r = cursor.fetchone()
                    is_final = bool(r['is_final']) if r and 'is_final' in r.keys() else False
                finally:
                    try:
                        cursor.close()
                    except Exception:
                        pass
            except Exception:
                is_final = False

            rn = datetime.now()
            if is_final:
                status_lbl = ctk.CTkLabel(row_frame, text="Ended", text_color="#D9534F")
            elif start_dt <= rn <= end_dt:
                status_lbl = ctk.CTkLabel(row_frame, text="Ongoing", text_color="#FFD700")
            else:
                status_lbl = ctk.CTkLabel(row_frame, text="Active", text_color="#7CFC00")
            status_lbl.grid(row=0, column=6, padx=8, pady=4, sticky="w")

            if idx is not None:
                view_btn = ctk.CTkButton(row_frame, text="View", width=60, height=30,
                                        command=lambda i=idx, g=game: on_view_click(i, g),
                                        hover_color="#4A90E2", fg_color="#1F75FE")
            else:
                view_btn = ctk.CTkButton(row_frame, text="View", width=60, height=30,
                                        command=lambda g=game: on_view_click(src_games.index(g), g),
                                        hover_color="#4A90E2", fg_color="#1F75FE")
            view_btn.grid(row=0, column=7, padx=4, pady=4, sticky="w")

            if idx is not None:
                edit_btn = ctk.CTkButton(row_frame, text="Edit", width=60, height=30,
                                         command=lambda i=idx: edit_scheduled_game(i),
                                         hover_color="#FFA500", fg_color="#4CAF50")
            else:
                edit_btn = ctk.CTkButton(row_frame, text="Edit", width=60, height=30,
                                         command=lambda g=game: edit_scheduled_game(src_games.index(g)),
                                         hover_color="#FFA500", fg_color="#4CAF50")
            edit_btn.grid(row=0, column=8, padx=4, pady=4)

            if idx is not None:
                delete_btn = ctk.CTkButton(row_frame, text="Delete", width=60, height=30,
                                           command=lambda i=idx: delete_scheduled_game(i),
                                           hover_color="#FF4500", fg_color="#F44336")
            else:
                delete_btn = ctk.CTkButton(row_frame, text="Delete", width=60, height=30,
                                           command=lambda g=game: delete_scheduled_game(src_games.index(g)),
                                           hover_color="#FF4500", fg_color="#F44336")
            delete_btn.grid(row=0, column=9, padx=4, pady=4)


def edit_scheduled_game(index):
    src_games = _get_scheduled_games_source()
    if index < 0 or index >= len(src_games):
        return
    game = src_games[index]
    win = ctk.CTkToplevel(refs.get('app') if refs.get('app') else None)
    win.title("Edit Scheduled Game")
    win.geometry("420x350")
    win.transient(refs.get('app') if refs.get('app') else None)

    ctk.CTkLabel(win, text="Team 1:").pack(pady=(12, 4), anchor="w", padx=12)
    team1_entry = ctk.CTkEntry(win)
    team1_entry.insert(0, game.get('team1', ''))
    team1_entry.pack(fill="x", padx=12)

    ctk.CTkLabel(win, text="Team 2:").pack(pady=(8, 4), anchor="w", padx=12)
    team2_entry = ctk.CTkEntry(win)
    team2_entry.insert(0, game.get('team2', ''))
    team2_entry.pack(fill="x", padx=12)

    ctk.CTkLabel(win, text="Venue:").pack(pady=(8, 4), anchor="w", padx=12)
    venue_entry = ctk.CTkEntry(win)
    venue_entry.insert(0, game.get('venue', ''))
    venue_entry.pack(fill="x", padx=12)

    ctk.CTkLabel(win, text="Date (YYYY-MM-DD):").pack(pady=(8, 4), anchor="w", padx=12)
    date_entry = ctk.CTkEntry(win)
    date_entry.insert(0, game.get('date', ''))
    date_entry.pack(fill="x", padx=12)

    def save_edit():
        t1 = team1_entry.get().strip()
        t2 = team2_entry.get().strip()
        v = venue_entry.get().strip()
        d = date_entry.get().strip()
        try:
            from teamsTab import teams as _teams
            from venuesTab import venues as _venues
        except Exception:
            _teams = {}
            _venues = {}
        if not all([t1, t2, v, d]) or t1 == t2 or t1 not in _teams or t2 not in _teams or v not in _venues:
            messagebox.showwarning("Invalid", "Please fill all fields correctly and ensure teams/venue exist.")
            return
        try:
            _ = datetime.strptime(d, "%Y-%m-%d")
        except Exception:
            messagebox.showwarning("Invalid", "Date must be in YYYY-MM-DD format.")
            return
        game = src_games[index]
        game_id = game.get('id')
        start = game.get('start', '00:00')
        end = game.get('end', '00:00')

        cur = ScheduleManager().mydb.cursor()
        try:
            cur.execute("SELECT id FROM teams WHERE teamName = ?", (t1,))
            team1_row = cur.fetchone()
            cur.execute("SELECT id FROM teams WHERE teamName = ?", (t2,))
            team2_row = cur.fetchone()
            cur.execute("SELECT id FROM venues WHERE venueName = ?", (v,))
            venue_row = cur.fetchone()
            if not team1_row or not team2_row or not venue_row:
                messagebox.showwarning("Invalid", "Selected teams or venue not found in DB.")
                return
            team1_id = team1_row['id']
            team2_id = team2_row['id']
            venue_id = venue_row['id']

            sm = ScheduleManager()
            if game_id:
                sm.updateGame(game_id, team1_id, team2_id, venue_id, d, start, end)
            else:
                new_id = sm.scheduleGame(team1_id, team2_id, venue_id, d)
                sm.updateGame(new_id, team1_id, team2_id, venue_id, d, start, end)
        finally:
            try:
                cur.close()
            except Exception:
                pass

        try:
            from scheduleGameTab import load_scheduled_games_from_db as _load
            _load()
            from viewGamesTab import refresh_scheduled_games_table as _refresh
            _refresh(refs.get('scheduled_games_table'))
        except Exception:
            pass
        win.destroy()


def delete_scheduled_game(index):
    src_games = _get_scheduled_games_source()
    if not (0 <= index < len(src_games)):
        return
    if messagebox.askyesno("Delete Game", "Are you sure you want to delete this scheduled game?"):
        game = src_games[index]
        game_id = game.get('id')
        if game_id:
            try:
                sm = ScheduleManager()
                sm.deleteGame(game_id)
            except Exception:
                messagebox.showwarning("Error", "Could not delete game from DB.")
        else:
            try:
                src_games.pop(index)
            except Exception:
                pass
        try:
            from scheduleGameTab import load_scheduled_games_from_db as _load
            _load()
            refresh_scheduled_games_table(refs.get('scheduled_games_table'))
        except Exception:
            pass
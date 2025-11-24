import customtkinter as ctk
from tkinter import messagebox
from datetime import datetime, date as _date
from theDB import *

# This module displays and edits scheduled games.
# mainGui will set:
#   refs, scheduled_games (from file3), show_game_details (from file3),
#   edit and delete functions are contained here.
refs = {}
scheduled_games = []
show_game_details = lambda i: None  # will be set by mainGui to file3.show_game_details

def _season_range_for_year(season, year):
    """
    Return (start_date, end_date) for the given season and season-start year.
    Handles seasons that span calendar years (Regular Season).
    """
    mapping = {
        "Pre-season": ((9, 25), (10, 16)),
        "Regular Season": ((10, 17), (4, 16)),  # crosses year boundary
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

def _season_for_date(dt):
    """
    Determine season name for a given date object.
    Tries interpreting season windows anchored at dt.year and dt.year-1,
    so dates like March 2025 are matched to the 2024-2025 Regular Season if appropriate.
    Returns season string or empty string if unknown.
    """
    seasons = [
        "Pre-season",
        "Regular Season",
        "Play-in",
        "Playoff",
        "Finals",
        "Off-season"
    ]
    for season in seasons:
        # Try anchor at dt.year and dt.year-1
        for anchor in (dt.year, dt.year - 1):
            start, end = _season_range_for_year(season, anchor)
            if start is None:
                continue
            if start <= dt <= end:
                return season
    return ""

def _season_from_iso(date_iso):
    """Safe wrapper to parse ISO date string (YYYY-MM-DD) and return season name."""
    try:
        dt = datetime.strptime(date_iso, "%Y-%m-%d").date()
    except Exception:
        return ""
    return _season_for_date(dt)


def on_view_click(index, game):
    """Called when the View button is pressed."""
    # Set selected game
    refs["selected_game"] = {
        "id": game["id"],
        "team1_id": game["team1_id"],
        "team2_id": game["team2_id"]
    }

    panel = refs.get("game_details_frame")
    if not panel:
        return

    # Clear the panel (we are replacing its contents)
    for w in panel.winfo_children():
        w.destroy()

    # --- RECREATE THE DETAILS LABEL ---
    details_label = ctk.CTkLabel(
        panel,
        text="Loading...",
        justify="left",
        anchor="nw"
    )
    details_label.pack(fill="both", expand=True, padx=10, pady=10)

    # Replace old label reference
    refs["details_content"] = details_label

    # Now show details inside the NEW label
    show_game_details(index)

    # Mark selected game again
    refs["selected_game"] = {
        "id": game["id"],
        "team1_id": game["team1_id"],
        "team2_id": game["team2_id"]
    }

def refresh_scheduled_games_table(table_frame):
    """Refresh the table of scheduled games (now includes Season column)."""
    # Clear existing rows
    for widget in table_frame.winfo_children():
        widget.destroy()

    # Header row (added Season column)
    header_frame = ctk.CTkFrame(table_frame, fg_color="#1F1F1F")
    header_frame.pack(fill="x", padx=8, pady=4)
    ctk.CTkLabel(header_frame, text="Team 1", font=ctk.CTkFont(size=14, weight="bold")).grid(row=0, column=0, padx=8, pady=4, sticky="w")
    ctk.CTkLabel(header_frame, text="Team 2", font=ctk.CTkFont(size=14, weight="bold")).grid(row=0, column=1, padx=8, pady=4, sticky="w")
    ctk.CTkLabel(header_frame, text="Venue", font=ctk.CTkFont(size=14, weight="bold")).grid(row=0, column=2, padx=8, pady=4, sticky="w")
    ctk.CTkLabel(header_frame, text="Date", font=ctk.CTkFont(size=14, weight="bold")).grid(row=0, column=3, padx=8, pady=4, sticky="w")
    ctk.CTkLabel(header_frame, text="Season", font=ctk.CTkFont(size=14, weight="bold")).grid(row=0, column=4, padx=8, pady=4, sticky="w")
    ctk.CTkLabel(header_frame, text="Time", font=ctk.CTkFont(size=14, weight="bold")).grid(row=0, column=5, padx=8, pady=4, sticky="w")
    ctk.CTkLabel(header_frame, text="Status", font=ctk.CTkFont(size=14, weight="bold")).grid(row=0, column=6, padx=8, pady=4, sticky="w")
    ctk.CTkLabel(header_frame, text="View", font=ctk.CTkFont(size=14, weight="bold")).grid(row=0, column=7, padx=8, pady=4, sticky="w")

    # Data rows
    for idx, game in enumerate(scheduled_games):
        row_frame = ctk.CTkFrame(table_frame, fg_color="#2A2A2A")
        row_frame.pack(fill="x", padx=8, pady=2)
        ctk.CTkLabel(row_frame, text=game['team1']).grid(row=0, column=0, padx=8, pady=4, sticky="w")
        ctk.CTkLabel(row_frame, text=game['team2']).grid(row=0, column=1, padx=8, pady=4, sticky="w")
        ctk.CTkLabel(row_frame, text=game['venue']).grid(row=0, column=2, padx=8, pady=4, sticky="w")
        ctk.CTkLabel(row_frame, text=game['date']).grid(row=0, column=3, padx=8, pady=4, sticky="w")

        # Season column (derived from game date)
        season_name = _season_from_iso(game.get('date') or "")
        ctk.CTkLabel(row_frame, text=season_name).grid(row=0, column=4, padx=8, pady=4, sticky="w")

        ctk.CTkLabel(row_frame, text=f"{game.get('start', '00:00')} - {game.get('end', '00:00')}").grid(row=0, column=5, padx=8, pady=4, sticky="w")

        # Status label: query DB for is_final for this game id
        try:
            cursor = mydb.cursor()
            try:
                cursor.execute("SELECT is_final FROM games WHERE id = ?", (game.get('id'),))
                r = cursor.fetchone()
                is_final = bool(r['is_final']) if r and 'is_final' in r.keys() else False
            finally:
                try:
                    cursor.close()
                except Exception:
                    pass
        except Exception:
            is_final = False

        if is_final:
            status_lbl = ctk.CTkLabel(row_frame, text="Ended", text_color="#D9534F")  # red-ish
        else:
            status_lbl = ctk.CTkLabel(row_frame, text="Active", text_color="#7CFC00")  # green-ish
        status_lbl.grid(row=0, column=6, padx=8, pady=4, sticky="w")

        # View button (new)
        view_btn = ctk.CTkButton(row_frame, text="View", width=60, height=30,
                                command=lambda i=idx, g=game: on_view_click(i, g),
                                hover_color="#4A90E2", fg_color="#1F75FE")
        view_btn.grid(row=0, column=7, padx=4, pady=4, sticky="w")

        # Action buttons
        edit_btn = ctk.CTkButton(row_frame, text="Edit", width=60, height=30,
                                 command=lambda i=idx: edit_scheduled_game(i),
                                 hover_color="#FFA500", fg_color="#4CAF50")
        edit_btn.grid(row=0, column=8, padx=4, pady=4)

        delete_btn = ctk.CTkButton(row_frame, text="Delete", width=60, height=30,
                                   command=lambda i=idx: delete_scheduled_game(i),
                                   hover_color="#FF4500", fg_color="#F44336")
        delete_btn.grid(row=0, column=9, padx=4, pady=4)

def edit_scheduled_game(index):
    if index < 0 or index >= len(scheduled_games):
        return
    game = scheduled_games[index]

    # --- NEW: Query all teams and venues for dropdowns
    try:
        from teamsTab import teams as _teams
        from venuesTab import venues as _venues
    except Exception:
        _teams, _venues = {}, {}
    team_names = sorted(list(_teams.keys()))
    venue_names = sorted(list(_venues.keys()))
    # Fallback if not imported
    if not team_names:
        try:
            cur = mydb.cursor()
            cur.execute("SELECT teamName FROM teams ORDER BY teamName")
            team_names = [row[0] for row in cur.fetchall()]
            cur.close()
        except Exception:
            team_names = []
    if not venue_names:
        try:
            cur = mydb.cursor()
            cur.execute("SELECT venueName FROM venues ORDER BY venueName")
            venue_names = [row[0] for row in cur.fetchall()]
            cur.close()
        except Exception:
            venue_names = []

    win = ctk.CTkToplevel(refs.get('app') if refs.get('app') else None)
    win.title("Edit Scheduled Game")
    win.geometry("420x350")
    win.transient(refs.get('app') if refs.get('app') else None)

    ctk.CTkLabel(win, text="Team 1:").pack(pady=(12,4), anchor="w", padx=12)
    team1_opt = ctk.CTkOptionMenu(win, values=team_names)
    team1_opt.pack(fill="x", padx=12)
    team1_opt.set(game['team1'])

    ctk.CTkLabel(win, text="Team 2:").pack(pady=(8,4), anchor="w", padx=12)
    team2_opt = ctk.CTkOptionMenu(win, values=team_names)
    team2_opt.pack(fill="x", padx=12)
    team2_opt.set(game['team2'])

    ctk.CTkLabel(win, text="Venue:").pack(pady=(8,4), anchor="w", padx=12)
    venue_opt = ctk.CTkOptionMenu(win, values=venue_names)
    venue_opt.pack(fill="x", padx=12)
    venue_opt.set(game['venue'])

    ctk.CTkLabel(win, text="Date (YYYY-MM-DD):").pack(pady=(8,4), anchor="w", padx=12)
    date_entry = ctk.CTkEntry(win)
    date_entry.insert(0, game['date'])
    date_entry.pack(fill="x", padx=12)

    def save_edit():
        t1 = team1_opt.get().strip()
        t2 = team2_opt.get().strip()
        v = venue_opt.get().strip()
        d = date_entry.get().strip()
        # validate inputs
        if not all([t1, t2, v, d]) or t1 == t2 or t1 not in team_names or t2 not in team_names or v not in venue_names:
            messagebox.showwarning("Invalid", "Please fill all fields correctly and ensure teams/venue exist.")
            return
        # validate date format
        try:
            _ = datetime.strptime(d, "%Y-%m-%d")
        except Exception:
            messagebox.showwarning("Invalid", "Date must be in YYYY-MM-DD format.")
            return
        # Persist edit to DB if possible
        game_id = game.get('id')
        start = game.get('start', '00:00')
        end = game.get('end', '00:00')

        from theDB import ScheduleManager
        cur = ScheduleManager().mydb.cursor()
        try:
            cur.execute("SELECT id FROM teams WHERE teamName = ?", (t1,))
            home = cur.fetchone()
            cur.execute("SELECT id FROM teams WHERE teamName = ?", (t2,))
            away = cur.fetchone()
            cur.execute("SELECT id FROM venues WHERE venueName = ?", (v,))
            venue_row = cur.fetchone()
            if not home or not away or not venue_row:
                messagebox.showwarning("Invalid", "Selected teams or venue not found in DB.")
                return
            home_id = home['id']
            away_id = away['id']
            venue_id = venue_row['id']

            sm = ScheduleManager()
            if game_id:
                sm.updateGame(game_id, home_id, away_id, venue_id, d, start, end)
            else:
                new_id = sm.scheduleGame(home_id, away_id, venue_id, d)
                sm.updateGame(new_id, home_id, away_id, venue_id, d, start, end)
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

    ctk.CTkButton(win, text="Save Changes", command=save_edit).pack(pady=12)
    
def delete_scheduled_game(index):
    if not (0 <= index < len(scheduled_games)):
        return
    if messagebox.askyesno("Delete Game", "Are you sure you want to delete this scheduled game?"):
        game = scheduled_games[index]
        game_id = game.get('id')
        if game_id:
            try:
                from theDB import ScheduleManager
                sm = ScheduleManager()
                sm.deleteGame(game_id)
            except Exception:
                messagebox.showwarning("Error", "Could not delete game from DB.")
        else:
            # fallback: remove from in-memory list
            try:
                scheduled_games.pop(index)
            except Exception:
                pass
        try:
            from scheduleGameTab import load_scheduled_games_from_db as _load
            _load()
            refresh_scheduled_games_table(refs.get('scheduled_games_table'))
        except Exception:
            pass
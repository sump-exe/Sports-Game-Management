import customtkinter as ctk
from tkinter import messagebox
from datetime import datetime
from theDB import *

# This module provides scheduling functions. It expects mainGui.py to set:
#   app, sched_mgr, refs, teams (from file1), venues (from file2)
app = None
sched_mgr = None
refs = {}
teams = {}
venues = {}

scheduled_games = []  # List of dicts: [{'team1': str, 'team2': str, 'venue': str, 'date': str, 'start': str, 'end': str}]

def load_scheduled_games_from_db():
    """Load scheduled games from DB into `scheduled_games` list."""
    scheduled_games.clear()
    cur = sched_mgr.mydb.cursor()

    cur.execute(
        """
        SELECT 
            g.id,
            g.home_team_id,
            g.away_team_id,
            t1.teamName AS team1,
            t2.teamName AS team2,
            v.venueName AS venue,
            g.game_date,
            g.start_time,
            g.end_time
        FROM games g
        JOIN teams t1 ON g.home_team_id = t1.id
        JOIN teams t2 ON g.away_team_id = t2.id
        JOIN venues v ON g.venue_id = v.id
        ORDER BY g.game_date
        """
    )

    rows = cur.fetchall()
    for r in rows:
        scheduled_games.append({
            'id': r['id'],
            'team1': r['team1'],
            'team2': r['team2'],
            'team1_id': r['home_team_id'],   # <-- ADDED
            'team2_id': r['away_team_id'],   # <-- ADDED
            'venue': r['venue'],
            'date': r['game_date'],
            'start': r['start_time'] or '00:00',
            'end': r['end_time'] or '00:00'
        })

    cur.close()

def update_schedule_optionmenus(team1_opt, team2_opt, venue_opt):
    team_names = list(teams.keys())
    # Protect against None widgets
    if hasattr(team1_opt, "configure"):
        team1_opt.configure(values=team_names)
    if hasattr(team2_opt, "configure"):
        team2_opt.configure(values=team_names)
    available_venues = [v for v, d in venues.items() if d.get("available", True)]
    if hasattr(venue_opt, "configure"):
        venue_opt.configure(values=available_venues)
    # if current selection is no longer valid (or empty), show placeholder "Select"
    try:
        if team1_opt.get() not in team_names:
            team1_opt.set("Select")
    except Exception:
        try:
            team1_opt.set("Select")
        except Exception:
            pass
    try:
        if team2_opt.get() not in team_names:
            team2_opt.set("Select")
    except Exception:
        try:
            team2_opt.set("Select")
        except Exception:
            pass
    try:
        if venue_opt.get() not in available_venues:
            venue_opt.set("Select")
    except Exception:
        try:
            venue_opt.set("Select")
        except Exception:
            pass

def show_game_details(index):
    if index < 0 or index >= len(scheduled_games):
        return
    game = scheduled_games[index]
    details = (
        f"Team 1: {game['team1']}\n"
        f"Team 2: {game['team2']}\n"
        f"Venue:  {game['venue']}\n"
        f"Date:   {game['date']}\n"
        f"Time:   {game['start']} - {game['end']}\n"
        "\n--- Extra Details Here Later ---"
    )
    if refs.get("details_content"):
        refs["details_content"].configure(text=details)

def update_game_preview():
    """Live preview shown on the right side of the Schedule Game tab."""
    team1 = refs.get('tab3_team1_opt').get() if refs.get('tab3_team1_opt') else None
    team2 = refs.get('tab3_team2_opt').get() if refs.get('tab3_team2_opt') else None
    venue = refs.get('tab3_venue_opt').get() if refs.get('tab3_venue_opt') else None
    date = refs.get('tab3_date_entry').get().strip() if refs.get('tab3_date_entry') else ""
    start = refs.get('tab3_start_entry').get().strip() if refs.get('tab3_start_entry') else ""
    end = refs.get('tab3_end_entry').get().strip() if refs.get('tab3_end_entry') else ""

    # Build a simple preview text and show it on the preview label
    lines = []
    if team1 and team1 != "Select":
        lines.append(f"Team 1: {team1}")
        # list players for team1
        players = teams.get(team1, [])
        for p in players:
            if isinstance(p, dict):
                name = p.get('name', '')
                jersey = p.get('jersey')
                if jersey is not None:
                    lines.append(f"#{jersey} - {name}")
                else:
                    lines.append(f"- {name}")
            else:
                lines.append(f"- {p}")
    if team2 and team2 != "Select":
        lines.append(f"Team 2: {team2}")
        # list players for team2
        players2 = teams.get(team2, [])
        for p in players2:
            if isinstance(p, dict):
                name = p.get('name', '')
                jersey = p.get('jersey')
                if jersey is not None:
                    lines.append(f"#{jersey} - {name}")
                else:
                    lines.append(f"- {name}")
            else:
                lines.append(f"- {p}")
    if venue and venue != "Select":
        lines.append(f"Venue:  {venue}")
    if date:
        lines.append(f"Date:   {date}")
    if start or end:
        lines.append(f"Time:   {start or '??:??'} - {end or '??:??'}")

    text = "\n".join(lines) if lines else "Fill out fields to preview..."
    lbl = refs.get('game_preview_label') or refs.get('game_preview')
    if lbl:
        lbl.configure(text=text)

def schedule_game():
    t1 = refs.get('tab3_team1_opt').get()
    t2 = refs.get('tab3_team2_opt').get()
    v = refs.get('tab3_venue_opt').get()
    date = refs.get('tab3_date_entry').get().strip()
    start = refs.get('tab3_start_entry').get().strip()
    end = refs.get('tab3_end_entry').get().strip()

    if not all([t1, t2, v, date, start, end]):
        messagebox.showwarning("Missing", "Please complete all fields including start/end times.")
        return

    if t1 == "Select" or t2 == "Select" or v == "Select":
        messagebox.showwarning("Missing", "Please select teams and venue.")
        return

    if t1 == t2:
        messagebox.showwarning("Invalid", "Teams must be different.")
        return

    try:
        parsed_date = datetime.strptime(date, "%Y-%m-%d").date()
    except Exception:
        messagebox.showwarning("Invalid", "Date must be in YYYY-MM-DD format.")
        return

    try:
        start_time = datetime.strptime(start, "%H:%M").time()
        end_time = datetime.strptime(end, "%H:%M").time()
    except Exception:
        messagebox.showwarning("Invalid", "Times must be in HH:MM (24-hour) format.")
        return

    start_dt = datetime.combine(parsed_date, start_time)
    end_dt = datetime.combine(parsed_date, end_time)
    if end_dt <= start_dt:
        messagebox.showwarning("Invalid", "End time must be after start time.")
        return

    # Persist to DB: find ids for team names and venue
    cur = sched_mgr.mydb.cursor()
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

        # Insert game and then update times
        game_id = sched_mgr.scheduleGame(home_id, away_id, venue_id, parsed_date.isoformat())
        sched_mgr.updateGame(game_id, home_id, away_id, venue_id, parsed_date.isoformat(), start_time.strftime("%H:%M"), end_time.strftime("%H:%M"))
    finally:
        cur.close()

    # reload scheduled games from DB and refresh UI
    load_scheduled_games_from_db()
    try:
        from viewGamesTab import refresh_scheduled_games_table as _refresh_table
        _refresh_table(refs.get('scheduled_games_table'))
    except Exception:
        pass

    update_game_preview()

    messagebox.showinfo("Scheduled", f"Game scheduled: {t1} vs {t2} at {v} on {parsed_date.isoformat()}")
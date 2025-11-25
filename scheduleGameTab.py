import customtkinter as ctk
from tkinter import messagebox
from datetime import datetime, date as _date
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
            'team1_id': r['home_team_id'],
            'team2_id': r['away_team_id'],
            'venue': r['venue'],
            'date': r['game_date'],
            'start': r['start_time'] or '00:00',
            'end': r['end_time'] or '00:00'
        })

    cur.close()


def update_schedule_optionmenus(team1_opt, team2_opt, venue_opt):
    """
    Populate the option menus used when scheduling a game.

    Filtering behavior:
      - Only include teams whose roster size exactly equals 12 players.
        (This is now enforced unconditionally; the settings UI may still exist
         in the codebase but the GUI will only expose 12-player teams.)
    """
    # Enforce exactly 12 players for scheduling UI
    required_size = 12

    # team_names initially all team keys
    team_names_all = list(teams.keys())

    # filter teams that have exact roster length equal to required_size
    filtered = []
    for t in team_names_all:
        roster = teams.get(t, [])
        try:
            if len(roster) == int(required_size):
                filtered.append(t)
        except Exception:
            # skip invalid entries
            continue
    team_names = filtered

    # Protect against None widgets
    if hasattr(team1_opt, "configure"):
        team1_opt.configure(values=team_names)
    if hasattr(team2_opt, "configure"):
        team2_opt.configure(values=team_names)
    available_venues = [v for v, d in venues.items() if d.get("available", True)]
    if hasattr(venue_opt, "configure"):
        venue_opt.configure(values=available_venues)

    # If current selection is no longer valid, reset to placeholder "Select"
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
        f"Team 2: {game['team2']}\n\n"
        f"Venue:  {game['venue']}\n\n"
        f"Date:   {game['date']}\n"
        f"Time:   {game['start']} - {game['end']}\n"
    )
    if refs.get("details_content"):
        refs["details_content"].configure(text=details)


def build_schedule_left_ui(parent):
    """
    Builds the left-side scheduling controls including:
    - Team 1
    - Team 2
    - Venue
    - Season
    - Year (text field placed below Season)
    - Date (now accepts only Month-Day in MM-DD)
    - Start / End Time
    """
    global refs

    frame = ctk.CTkFrame(parent)
    frame.pack(fill="both", expand=False, padx=10, pady=10)

    # ---------- TEAM 1 ----------
    ctk.CTkLabel(frame, text="Team 1:").grid(row=0, column=0, sticky="w", pady=3)
    team1_opt = ctk.CTkOptionMenu(frame, values=["Select"], command=lambda *_: update_game_preview())
    team1_opt.grid(row=0, column=1, sticky="ew", pady=3)
    refs["tab3_team1_opt"] = team1_opt

    # ---------- TEAM 2 ----------
    ctk.CTkLabel(frame, text="Team 2:").grid(row=1, column=0, sticky="w", pady=3)
    team2_opt = ctk.CTkOptionMenu(frame, values=["Select"], command=lambda *_: update_game_preview())
    team2_opt.grid(row=1, column=1, sticky="ew", pady=3)
    refs["tab3_team2_opt"] = team2_opt

    # ---------- VENUE ----------
    ctk.CTkLabel(frame, text="Venue:").grid(row=2, column=0, sticky="w", pady=3)
    venue_opt = ctk.CTkOptionMenu(frame, values=["Select"], command=lambda *_: update_game_preview())
    venue_opt.grid(row=2, column=1, sticky="ew", pady=3)
    refs["tab3_venue_opt"] = venue_opt

    # ---------- SEASON ----------
    ctk.CTkLabel(frame, text="Season:").grid(row=3, column=0, sticky="w", pady=3)
    season_values = [
        "Pre-season",
        "Regular Season",
        "Play-in",
        "Playoff",
        "Finals",
        "Off-season"
    ]
    season_opt = ctk.CTkOptionMenu(frame, values=season_values, command=lambda *_: update_game_preview())
    season_opt.set("Regular Season")
    season_opt.grid(row=3, column=1, sticky="ew", pady=3)
    refs["tab3_season_opt"] = season_opt

    # ---------- YEAR ----------
    ctk.CTkLabel(frame, text="Year:").grid(row=4, column=0, sticky="w", pady=3)
    year_entry = ctk.CTkEntry(frame, placeholder_text=str(datetime.now().year))
    year_entry.grid(row=4, column=1, sticky="ew", pady=3)
    year_entry.bind("<KeyRelease>", lambda e: update_game_preview())
    refs["tab3_year_entry"] = year_entry

    # ---------- DATE (Month-Day only) ----------
    ctk.CTkLabel(frame, text="Month-Day (MM-DD):").grid(row=5, column=0, sticky="w", pady=3)
    date_entry = ctk.CTkEntry(frame, placeholder_text="MM-DD (e.g. 03-15)")
    date_entry.grid(row=5, column=1, sticky="ew", pady=3)
    date_entry.bind("<KeyRelease>", lambda e: update_game_preview())
    refs["tab3_date_entry"] = date_entry

    # ---------- START TIME ----------
    ctk.CTkLabel(frame, text="Start Time (HH:MM):").grid(row=6, column=0, sticky="w", pady=3)
    start_entry = ctk.CTkEntry(frame, placeholder_text="13:00")
    start_entry.grid(row=6, column=1, sticky="ew", pady=3)
    start_entry.bind("<KeyRelease>", lambda e: update_game_preview())
    refs["tab3_start_entry"] = start_entry

    # ---------- END TIME ----------
    ctk.CTkLabel(frame, text="End Time (HH:MM):").grid(row=7, column=0, sticky="w", pady=3)
    end_entry = ctk.CTkEntry(frame, placeholder_text="15:00")
    end_entry.grid(row=7, column=1, sticky="ew", pady=3)
    end_entry.bind("<KeyRelease>", lambda e: update_game_preview())
    refs["tab3_end_entry"] = end_entry

    # ---------- BUTTON ----------
    save_btn = ctk.CTkButton(frame, text="Schedule Game", command=schedule_game)
    save_btn.grid(row=8, column=0, columnspan=2, pady=10, sticky="ew")

    # Make columns stretch properly
    frame.grid_columnconfigure(1, weight=1)

    # Populate menus
    update_schedule_optionmenus(team1_opt, team2_opt, venue_opt)

    return frame


# Backwards-compatible alias for callers expecting build_left_ui
def build_left_ui(parent):
    return build_schedule_left_ui(parent)


def update_game_preview():
    """Live preview shown on the right side of the Schedule Game tab."""
    # initialize lines first
    lines = []

    # prefer showing season and year together when possible
    try:
        season = refs.get('tab3_season_opt').get() if refs.get('tab3_season_opt') else None
    except Exception:
        season = None
    try:
        year_txt = refs.get('tab3_year_entry').get().strip() if refs.get('tab3_year_entry') else ""
    except Exception:
        year_txt = ""

    # Date is now MM-DD; display combined if possible
    try:
        md = refs.get('tab3_date_entry').get().strip() if refs.get('tab3_date_entry') else ""
    except Exception:
        md = ""

    # Compose display date when both year and month-day are present and valid
    display_date = None
    if md:
        try:
            # parse month-day
            parsed_md = datetime.strptime(md, "%m-%d")
            # determine year (use entered year if valid, else current year)
            try:
                year_val = int(year_txt)
                if year_val < 1:
                    raise ValueError()
            except Exception:
                year_val = datetime.now().year
            display_date = _date(year_val, parsed_md.month, parsed_md.day).isoformat()
        except Exception:
            # md invalid; keep raw md for display
            display_date = md

    if season and year_txt:
        lines.append(f"Season: {season} ({year_txt})")
    elif season:
        lines.append(f"Season: {season}")
    elif year_txt:
        lines.append(f"Year: {year_txt}")

    if display_date:
        lines.append(f"Date:   {display_date}")
    if refs.get('tab3_start_entry') and refs.get('tab3_start_entry').get().strip():
        start = refs.get('tab3_start_entry').get().strip()
        end = refs.get('tab3_end_entry').get().strip() if refs.get('tab3_end_entry') else ""
        lines.append(f"Time:   {start or '??:??'} - {end or '??:??'}")
    if refs.get('tab3_venue_opt'):
        venue = refs.get('tab3_venue_opt').get()
        if venue and venue != "Select":
            lines.append(f"Venue:  {venue}")
    if refs.get('tab3_team1_opt'):
        team1 = refs.get('tab3_team1_opt').get()
        if team1 and team1 != "Select":
            lines.append(f"\nTeam 1: {team1}")
            players = teams.get(team1, [])
            for p in players:
                if isinstance(p, dict):
                    name = p.get('name', '')
                    jersey = p.get('jersey')
                    if jersey is not None:
                        lines.append(f"  #{jersey} - {name}")
                    else:
                        lines.append(f"  - {name}")
                else:
                    lines.append(f"  - {p}")
    if refs.get('tab3_team2_opt'):
        team2 = refs.get('tab3_team2_opt').get()
        if team2 and team2 != "Select":
            lines.append(f"\nTeam 2: {team2}")
            players2 = teams.get(team2, [])
            for p in players2:
                if isinstance(p, dict):
                    name = p.get('name', '')
                    jersey = p.get('jersey')
                    if jersey is not None:
                        lines.append(f"  #{jersey} - {name}")
                    else:
                        lines.append(f"  - {name}")
                else:
                    lines.append(f"  - {p}")

    text = "\n".join(lines) if lines else "Fill out fields to preview..."
    lbl = refs.get('game_preview_label') or refs.get('game_preview')
    if lbl:
        try:
            lbl.configure(text=text)
        except Exception:
            pass


# --- New helpers: season ranges validation ---
def _season_range_for_year(season, year):
    """
    Return (start_date, end_date) for the given season and season-start year.
    The 'year' parameter is treated as the season start year. For seasons that
    end in the following calendar year (e.g., Regular Season), end_date will
    be in year+1.
    """
    # mapping: (start_month, start_day), (end_month, end_day)
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
    # if end month/day comes earlier in calendar than start -> it's in year+1
    if (em, ed) < (sm, sd):
        end = _date(year + 1, em, ed)
    else:
        end = _date(year, em, ed)
    return start, end


def _is_date_within_season(parsed_date, season, year_val):
    """
    Flexible check: Accept the parsed_date if it falls into either the season window
    computed for year_val (treating `year_val` as season-start year) OR the window
    computed for year_val-1. This makes the UI tolerant to whether the user supplies
    the season-start year or the calendar year of the date.
    Returns (True, "") when valid; (False, message) when invalid.
    """
    if not season or season == "Select":
        return True, ""

    # Try both interpretations: season starting in year_val, and season starting in year_val-1
    tries = []
    for y in (year_val, year_val - 1):
        start, end = _season_range_for_year(season, y)
        if start is None or end is None:
            continue
        tries.append((start, end))

        if start <= parsed_date <= end:
            return True, ""

    # If none matched, prepare friendly message showing canonical window for display.
    # Prefer showing canonical window where season-start is year_val if mapping exists,
    # otherwise fall back to the first available try.
    if tries:
        start, end = tries[0]
        msg = f"Selected season '{season}' accepts dates between {start.isoformat()} and {end.isoformat()}."
    else:
        msg = f"Unknown season '{season}'."
    return False, msg


def schedule_game():
    t1 = refs.get('tab3_team1_opt').get() if refs.get('tab3_team1_opt') else None
    t2 = refs.get('tab3_team2_opt').get() if refs.get('tab3_team2_opt') else None
    v = refs.get('tab3_venue_opt').get() if refs.get('tab3_venue_opt') else None

    md = refs.get('tab3_date_entry').get().strip() if refs.get('tab3_date_entry') else ""
    year_txt = refs.get('tab3_year_entry').get().strip() if refs.get('tab3_year_entry') else ""

    start = refs.get('tab3_start_entry').get().strip() if refs.get('tab3_start_entry') else ""
    end = refs.get('tab3_end_entry').get().strip() if refs.get('tab3_end_entry') else ""

    if not all([t1, t2, v, md, year_txt, start, end]):
        messagebox.showwarning("Missing", "Please complete all fields: teams, venue, year, month-day (MM-DD), and start/end times.")
        return

    if t1 == "Select" or t2 == "Select" or v == "Select":
        messagebox.showwarning("Missing", "Please select teams and venue.")
        return

    if t1 == t2:
        messagebox.showwarning("Invalid", "Teams must be different.")
        return

    # parse month-day
    try:
        parsed_md = datetime.strptime(md, "%m-%d")
    except Exception:
        messagebox.showwarning("Invalid", "Month-Day must be in MM-DD format (e.g. 03-15).")
        return

    # parse year
    try:
        year_val = int(year_txt)
        if year_val < 1 or year_val > 9999:
            raise ValueError()
    except Exception:
        messagebox.showwarning("Invalid", "Year must be a valid integer (e.g. 2025).")
        return

    # build full date
    try:
        parsed_date = _date(year_val, parsed_md.month, parsed_md.day)
    except Exception:
        messagebox.showwarning("Invalid", "Combined Year and Month-Day produce an invalid date.")
        return

    # --- NEW: Enforce season-based valid date ranges ---
    try:
        season = refs.get('tab3_season_opt').get() if refs.get('tab3_season_opt') else None
    except Exception:
        season = None

    ok, msg = _is_date_within_season(parsed_date, season, year_val)
    if not ok:
        messagebox.showwarning("Invalid Date for Season", msg)
        return

    # parse times
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

    # Enforce exact 12-player teams for scheduling (UI already filters, but double-check here)
    required_size = 12

    # lookup roster lengths (teams dict is wired in by mainGui)
    roster1 = teams.get(t1, [])
    roster2 = teams.get(t2, [])
    len1 = len(roster1) if roster1 is not None else 0
    len2 = len(roster2) if roster2 is not None else 0

    try:
        req = int(required_size)
    except Exception:
        req = None

    if req is not None:
        if len1 != req or len2 != req:
            messagebox.showwarning("Invalid Teams", f"Both teams must have exactly {req} players to schedule a game.\nSelected teams have: {t1}={len1}, {t2}={len2}.")
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

        # Insert game and then update times using the combined date
        game_id = sched_mgr.scheduleGame(home_id, away_id, venue_id, parsed_date.isoformat())
        sched_mgr.updateGame(game_id, home_id, away_id, venue_id, parsed_date.isoformat(), start_time.strftime("%H:%M"), end_time.strftime("%H:%M"))
    finally:
        try:
            cur.close()
        except Exception:
            pass

    # reload scheduled games from DB and refresh UI
    load_scheduled_games_from_db()
    try:
        from viewGamesTab import refresh_scheduled_games_table as _refresh_table
        _refresh_table(refs.get('scheduled_games_table'))
    except Exception:
        pass

    update_game_preview()

    messagebox.showinfo("Scheduled", f"Game scheduled: {t1} vs {t2} at {v} on {parsed_date.isoformat()}")
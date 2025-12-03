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

def load_scheduled_games_from_db():
    """Load scheduled games from DB into `scheduled_games` list."""
    scheduled_games.clear()
    if not sched_mgr: return

    cur = sched_mgr.mydb.cursor()
    try:
        cur.execute(
            """
            SELECT 
                g.id,
                g.team1_id,
                g.team2_id,
                t1.teamName AS team1,
                t2.teamName AS team2,
                v.venueName AS venue,
                g.game_date,
                g.start_time,
                g.end_time
            FROM games g
            LEFT JOIN teams t1 ON g.team1_id = t1.id
            LEFT JOIN teams t2 ON g.team2_id = t2.id
            LEFT JOIN venues v ON g.venue_id = v.id
            ORDER BY g.game_date, g.start_time
            """
        )
        rows = cur.fetchall()
        for r in rows:
            scheduled_games.append({
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

    # Sync with viewGamesTab if loaded
    try:
        import viewGamesTab as vgt
        if hasattr(vgt, 'scheduled_games'):
            vgt.scheduled_games.clear()
            vgt.scheduled_games.extend(scheduled_games)
    except Exception:
        pass

# --- LOGIC: Ranking and Qualification ---

def _get_regular_season_ranks(year_str):
    """
    Returns a list of dicts [{'id': int, 'name': str, 'wins': int, 'pts': int}]
    sorted by Rank (Wins DESC, SeasonPoints DESC).
    
    Includes FIX to sort by Season Points (not Career Points) to match Standings Tab.
    """
    try:
        input_year = int(year_str)
        # Shift back 1 year. If we are scheduling Play-ins for 2026,
        # we need the stats from the season that started in late 2025.
        season_start_year = input_year - 1
    except ValueError:
        return []

    s_helper = Season()
    reg_start, reg_end = s_helper.get_range("Regular Season", season_start_year)
    if not reg_start or not reg_end:
        return []
    
    start_iso = reg_start.isoformat()
    end_iso = reg_end.isoformat()

    cur = sched_mgr.mydb.cursor()
    ranked_teams = []
    try:
        # Filter for valid roster size first (Teams with 12 players)
        valid_ids = []
        for t_name, t_roster in teams.items():
            if len(t_roster) == 12:
                cur.execute("SELECT id FROM teams WHERE teamName = ?", (t_name,))
                r = cur.fetchone()
                if r: valid_ids.append(r['id'])
        
        if not valid_ids: return []

        placeholders = ','.join(['?'] * len(valid_ids))
        
        # --- FIXED QUERY: Calculates Season Points dynamically ---
        query = f"""
            SELECT 
                t.id, t.teamName,
                
                -- Count Wins in Regular Season
                (SELECT COUNT(*) FROM games g 
                 WHERE g.winner_team_id = t.id 
                 AND g.is_final = 1
                 AND g.game_date BETWEEN ? AND ?) as reg_wins,
                 
                -- Calculate Points Scored in Regular Season (Secondary Sort)
                COALESCE((SELECT SUM(
                    CASE 
                        WHEN g2.team1_id = t.id THEN COALESCE(g2.team1_score, 0) 
                        ELSE COALESCE(g2.team2_score, 0) 
                    END) 
                  FROM games g2 
                  WHERE (g2.team1_id = t.id OR g2.team2_id = t.id) 
                    AND g2.is_final = 1 
                    AND g2.game_date BETWEEN ? AND ?), 0) as season_pts

            FROM teams t
            WHERE t.id IN ({placeholders})
            ORDER BY reg_wins DESC, season_pts DESC
        """
        
        # Parameters: [WinStart, WinEnd, PtsStart, PtsEnd, ID1, ID2...]
        params = [start_iso, end_iso, start_iso, end_iso] + valid_ids
        
        cur.execute(query, params)
        rows = cur.fetchall()
        for r in rows:
            ranked_teams.append({
                'id': r['id'],
                'name': r['teamName'],
                'wins': r['reg_wins'],
                'pts': r['season_pts']
            })
    finally:
        cur.close()
    
    return ranked_teams

def _analyze_playin_status(year_str, ranked_teams):
    """
    Analyzes the 'Play-in' tournament state.
    Returns:
       allowed_pairs: list of tuples [(TeamNameA, TeamNameB), ...] 
       qualified_via_playin: list of TeamNames who advanced to playoffs
    """
    
    if len(ranked_teams) < 10:
        return [], [] # Not enough teams for a 7-10 play-in

    # Identify seeds 7, 8, 9, 10
    seed7 = ranked_teams[6] # 0-indexed
    seed8 = ranked_teams[7]
    seed9 = ranked_teams[8]
    seed10 = ranked_teams[9]

    # Check database for results of specific matchups in Play-in window
    s_helper = Season()
    try:
        year_val = int(year_str)
    except: return [], []
    
    pi_start, pi_end = s_helper.get_range("Play-in", year_val)
    
    def get_game_result(id_a, id_b):
        # Returns (is_played, winner_id, loser_id)
        cur = sched_mgr.mydb.cursor()
        try:
            cur.execute("""
                SELECT winner_team_id, is_final FROM games 
                WHERE ((team1_id = ? AND team2_id = ?) OR (team1_id = ? AND team2_id = ?))
                  AND game_date BETWEEN ? AND ?
                  AND is_final = 1
            """, (id_a, id_b, id_b, id_a, pi_start.isoformat(), pi_end.isoformat()))
            row = cur.fetchone()
            if row:
                w = row['winner_team_id']
                l = id_b if w == id_a else id_a
                return True, w, l
            return False, None, None
        finally:
            cur.close()

    # Check 7 vs 8
    g78_done, g78_win, g78_lose = get_game_result(seed7['id'], seed8['id'])
    # Check 9 vs 10
    g910_done, g910_win, g910_lose = get_game_result(seed9['id'], seed10['id'])

    allowed_pairs = []
    qualified = []

    # Logic: 7 vs 8
    if not g78_done:
        allowed_pairs.append((seed7['name'], seed8['name']))
    else:
        # Winner of 7v8 is Playoff Seed 7 -> Qualified
        t_name = next((t['name'] for t in ranked_teams if t['id'] == g78_win), None)
        if t_name: qualified.append(t_name)

    # Logic: 9 vs 10
    if not g910_done:
        allowed_pairs.append((seed9['name'], seed10['name']))
    
    # Logic: Loser(7v8) vs Winner(9v10)
    if g78_done and g910_done:
        # Only schedule this if it hasn't happened yet
        gLast_done, gLast_win, _ = get_game_result(g78_lose, g910_win)
        
        loser78_name = next((t['name'] for t in ranked_teams if t['id'] == g78_lose), "Unknown")
        winner910_name = next((t['name'] for t in ranked_teams if t['id'] == g910_win), "Unknown")

        if not gLast_done:
            allowed_pairs.append((loser78_name, winner910_name))
        else:
            # Winner of this game is Playoff Seed 8 -> Qualified
            t_name = next((t['name'] for t in ranked_teams if t['id'] == gLast_win), None)
            if t_name: qualified.append(t_name)

    return allowed_pairs, qualified

# --- DROPDOWN EVENT HANDLERS ---

def on_team1_select(choice):
    """
    Context-aware Team 2 filtering.
    """
    update_game_preview()
    
    if not choice or choice == "Select":
        update_schedule_optionmenus(None, refs.get("tab3_team2_opt"), None)
        return

    season = refs.get('tab3_season_opt').get()
    year_txt = refs.get('tab3_year_entry').get()

    valid_opponents = []

    if season == "Play-in":
        # Strict Matchups Only
        ranks = _get_regular_season_ranks(year_txt)
        pairs, _ = _analyze_playin_status(year_txt, ranks)
        
        # Find who 'choice' is allowed to play against
        for p1, p2 in pairs:
            if p1 == choice: valid_opponents.append(p2)
            if p2 == choice: valid_opponents.append(p1)
            
    elif season == "Playoff" or season == "Finals":
        # Standard: Can play anyone else in the qualified pool (Top 8 for Finals)
        t2_opt = refs.get("tab3_team2_opt")
        current_values = t2_opt.cget("values") if t2_opt else []
        valid_opponents = [t for t in current_values if t != choice and t != "Select" and t != "No Match Found"]
    
    else:
        # Regular Season / Pre-season: Any other full team
        all_teams = list(teams.keys())
        for t in all_teams:
            if t == choice: continue
            if len(teams.get(t, [])) == 12:
                valid_opponents.append(t)
        valid_opponents.sort()

    # Update Team 2 Dropdown
    t2_opt = refs.get("tab3_team2_opt")
    if t2_opt:
        if not valid_opponents:
            t2_opt.configure(values=["No Match Found"])
            t2_opt.set("No Match Found")
        else:
            t2_opt.configure(values=valid_opponents)
            t2_opt.set("Select")

def update_schedule_optionmenus(team1_opt, team2_opt, venue_opt):
    season = refs.get('tab3_season_opt').get() if refs.get('tab3_season_opt') else "Regular Season"
    year_txt = refs.get('tab3_year_entry').get() if refs.get('tab3_year_entry') else str(datetime.now().year)

    available_t1 = []

    if season == "Play-in":
        # 1. Get Ranks
        ranks = _get_regular_season_ranks(year_txt)
        # 2. Get Valid Matchups
        pairs, _ = _analyze_playin_status(year_txt, ranks)
        
        if len(ranks) < 10:
             available_t1 = ["Need 10+ Teams"]
        elif not pairs:
             available_t1 = ["All Matches Played"]
        else:
             # Extract unique names from pairs
             names = set()
             for a, b in pairs:
                 names.add(a)
                 names.add(b)
             available_t1 = sorted(list(names))

    elif season == "Playoff":
        ranks = _get_regular_season_ranks(year_txt)
        if len(ranks) < 10:
            available_t1 = ["Need 10+ Teams"]
        else:
            # Note: A real playoff system would include top 6 + 2 Play-in winners.
            # For this context, we ensure we at least fetch ranks to prevent errors.
            seeds_7_10 = [r['name'] for r in ranks[6:10]]
            available_t1 = sorted(seeds_7_10)

    # --- NEW: Finals Logic (Top 8 Only) ---
    elif season == "Finals":
        ranks = _get_regular_season_ranks(year_txt)
        if len(ranks) < 8:
             available_t1 = ["Need 8+ Teams"]
        else:
             # Take the top 8 teams from the list
             seeds_top_8 = [r['name'] for r in ranks[:8]]
             available_t1 = sorted(seeds_top_8)
    # --------------------------------------

    else:
        # Standard: All teams with 12 players
        team_names_all = list(teams.keys())
        filtered = []
        for t in team_names_all:
            roster = teams.get(t, [])
            if len(roster) == 12:
                filtered.append(t)
        available_t1 = sorted(filtered) if filtered else []

    # Update Dropdowns
    if team1_opt and hasattr(team1_opt, "configure"):
        team1_opt.configure(values=available_t1)
    
    # Team 2 mirrors Team 1 initially
    if team2_opt and hasattr(team2_opt, "configure"):
        team2_opt.configure(values=available_t1)
    
    # Venue
    available_venues = [v for v, d in venues.items() if d.get("available", True)]
    if venue_opt and hasattr(venue_opt, "configure"):
        venue_opt.configure(values=available_venues)

    # Validation resets
    try:
        if team1_opt and team1_opt.get() not in available_t1: team1_opt.set("Select")
    except: pass
    try:
        if team2_opt and team2_opt.get() not in available_t1: team2_opt.set("Select")
    except: pass
    try:
        if venue_opt and venue_opt.get() not in available_venues: venue_opt.set("Select")
    except: pass

# --- UI BUILDING ---

def build_schedule_left_ui(parent):
    global refs

    frame = ctk.CTkFrame(parent)
    frame.pack(fill="both", expand=False, padx=10, pady=10)

    # 1. Season
    ctk.CTkLabel(frame, text="Season:").grid(row=0, column=0, sticky="w", pady=3)
    season_values = ["Pre-season", "Regular Season", "Play-in", "Playoff", "Finals", "Off-season"]
    season_opt = ctk.CTkOptionMenu(frame, values=season_values, command=lambda *_: [reset_team_selections(), update_game_preview()])
    season_opt.set("Regular Season")
    season_opt.grid(row=0, column=1, sticky="ew", pady=3)
    refs["tab3_season_opt"] = season_opt

    # 2. Year
    ctk.CTkLabel(frame, text="Year:").grid(row=1, column=0, sticky="w", pady=3)
    year_entry = ctk.CTkEntry(frame, placeholder_text=str(datetime.now().year))
    year_entry.grid(row=1, column=1, sticky="ew", pady=3)
    year_entry.bind("<KeyRelease>", lambda e: [reset_team_selections(), update_game_preview()])
    refs["tab3_year_entry"] = year_entry

    # 3. Date
    ctk.CTkLabel(frame, text="Month-Day (MM-DD):").grid(row=2, column=0, sticky="w", pady=3)
    date_entry = ctk.CTkEntry(frame, placeholder_text="MM-DD (e.g. 03-15)")
    date_entry.grid(row=2, column=1, sticky="ew", pady=3)
    date_entry.bind("<KeyRelease>", lambda e: update_game_preview())
    refs["tab3_date_entry"] = date_entry

    # 4. Team 1
    ctk.CTkLabel(frame, text="Team 1:").grid(row=3, column=0, sticky="w", pady=3)
    team1_opt = ctk.CTkOptionMenu(frame, values=["Select"], command=on_team1_select)
    team1_opt.grid(row=3, column=1, sticky="ew", pady=3)
    refs["tab3_team1_opt"] = team1_opt

    # 5. Team 2
    ctk.CTkLabel(frame, text="Team 2:").grid(row=4, column=0, sticky="w", pady=3)
    team2_opt = ctk.CTkOptionMenu(frame, values=["Select"], command=lambda *_: update_game_preview())
    team2_opt.grid(row=4, column=1, sticky="ew", pady=3)
    refs["tab3_team2_opt"] = team2_opt

    # 6. Venue
    ctk.CTkLabel(frame, text="Venue:").grid(row=5, column=0, sticky="w", pady=3)
    venue_opt = ctk.CTkOptionMenu(frame, values=["Select"], command=lambda *_: update_game_preview())
    venue_opt.grid(row=5, column=1, sticky="ew", pady=3)
    refs["tab3_venue_opt"] = venue_opt

    # 7. Start Time
    ctk.CTkLabel(frame, text="Start Time (HH:MM):").grid(row=6, column=0, sticky="w", pady=3)
    start_entry = ctk.CTkEntry(frame, placeholder_text="13:00")
    start_entry.grid(row=6, column=1, sticky="ew", pady=3)
    start_entry.bind("<KeyRelease>", lambda e: update_game_preview())
    refs["tab3_start_entry"] = start_entry

    # 8. End Time
    ctk.CTkLabel(frame, text="End Time (HH:MM):").grid(row=7, column=0, sticky="w", pady=3)
    end_entry = ctk.CTkEntry(frame, placeholder_text="15:00")
    end_entry.grid(row=7, column=1, sticky="ew", pady=3)
    end_entry.bind("<KeyRelease>", lambda e: update_game_preview())
    refs["tab3_end_entry"] = end_entry

    # Button
    save_btn = ctk.CTkButton(frame, text="Schedule Game", command=schedule_game)
    save_btn.grid(row=8, column=0, columnspan=2, pady=10, sticky="ew")

    frame.grid_columnconfigure(1, weight=1)
    
    update_schedule_optionmenus(team1_opt, team2_opt, venue_opt)
    return frame

def reset_team_selections():
    try:
        update_schedule_optionmenus(refs.get("tab3_team1_opt"), refs.get("tab3_team2_opt"), None)
        refs["tab3_team1_opt"].set("Select")
        refs["tab3_team2_opt"].set("Select")
    except:
        pass

def build_left_ui(parent):
    return build_schedule_left_ui(parent)

def update_game_preview():
    lines = []
    season = refs.get('tab3_season_opt').get() if refs.get('tab3_season_opt') else ""
    year = refs.get('tab3_year_entry').get().strip() if refs.get('tab3_year_entry') else ""
    md = refs.get('tab3_date_entry').get().strip() if refs.get('tab3_date_entry') else ""
    
    # Helper to format lines nicely with fixed width key
    def fmt(label, value):
        return f"{label:<10} {value}"

    if season or year: lines.append(fmt("SEASON:", f"{season} {year}"))
    if md: lines.append(fmt("DATE:", md))
    
    start = refs.get('tab3_start_entry').get().strip() if refs.get('tab3_start_entry') else ""
    end = refs.get('tab3_end_entry').get().strip() if refs.get('tab3_end_entry') else ""
    if start: lines.append(fmt("TIME:", f"{start} - {end}"))
    
    venue = refs.get('tab3_venue_opt').get() if refs.get('tab3_venue_opt') else ""
    if venue and venue != "Select": lines.append(fmt("VENUE:", venue))
    
    t1 = refs.get('tab3_team1_opt').get() if refs.get('tab3_team1_opt') else ""
    t2 = refs.get('tab3_team2_opt').get() if refs.get('tab3_team2_opt') else ""
    
    matchup_text = ""
    if t1 and t1 != "Select" and t2 and t2 != "Select":
        # Add some visual separation for the matchup
        matchup_text = f"\n\n{t1}\n      VS\n{t2}"
        
    final_text = "\n".join(lines) + matchup_text
    
    lbl = refs.get('game_preview_label') or refs.get('game_preview')
    if lbl: 
        # Increase size and weight, use clearer text
        lbl.configure(
            text=final_text if final_text.strip() else "Fill details to preview...",
            font=ctk.CTkFont(family="Arial", size=20, weight="bold")
        )

def _is_date_within_season(parsed_date, season, year_val):
    """
    Validates if the parsed_date is within the allowed range for the selected season.
    Returns: (bool, error_message)
    """
    if not season or season == "Select": return True, ""
    
    valid_ranges_info = []

    # Check current year and previous year (to account for seasons spanning across years)
    for y in (year_val, year_val - 1):
        s_obj = Season()
        start, end = s_obj.get_range(season, y)
        if start and end:
            # Check if date is valid
            if start <= parsed_date <= end: 
                return True, ""
            
            # Format readable string for error message (WITHOUT YEAR)
            # e.g., "Oct 17 -> Apr 16"
            range_str = f"{start.strftime('%b %d')} -> {end.strftime('%b %d')}"
            
            # Prevent duplicate ranges from appearing (since day/month are constant across years)
            if range_str not in valid_ranges_info:
                valid_ranges_info.append(range_str)

    if valid_ranges_info:
        msg_details = "\nOR\n".join(valid_ranges_info)
        msg = f"The date {parsed_date} is not within the '{season}' window.\n\nAllowed Dates:\n{msg_details}"
    else:
        msg = f"Date not in {season} window (could not calculate ranges)."
        
    return False, msg

def schedule_game():
    # 1. Gather Inputs
    t1 = refs.get('tab3_team1_opt').get()
    t2 = refs.get('tab3_team2_opt').get()
    v = refs.get('tab3_venue_opt').get()
    md = refs.get('tab3_date_entry').get().strip()
    year_txt = refs.get('tab3_year_entry').get().strip()
    start = refs.get('tab3_start_entry').get().strip()
    end = refs.get('tab3_end_entry').get().strip()

    # 2. Basic Validation
    if not all([t1, t2, v, md, year_txt, start, end]) or "Select" in (t1, t2, v) or "No Match" in (t1, t2) or "Need" in t1 or "Matches Played" in t1:
        messagebox.showwarning("Missing Info", "Please fill all fields and select matching teams.")
        return
    if t1 == t2:
        messagebox.showwarning("Invalid", "Teams must be different.")
        return

    # 3. Parse Date/Time
    try:
        y_val = int(year_txt)

        # --- NEW VALIDATION: Year Limit ---
        if y_val > 9999:
            messagebox.showwarning("Invalid Year", "Year cannot exceed 9999.")
            return
        # ----------------------------------

        pmd = datetime.strptime(md, "%m-%d")
        game_date = _date(y_val, pmd.month, pmd.day)
    except:
        messagebox.showwarning("Invalid Date", "Check Year (YYYY) and Date (MM-DD).")
        return

    try:
        season = refs.get('tab3_season_opt').get()
        ok, msg = _is_date_within_season(game_date, season, y_val)
        if not ok:
            messagebox.showwarning("Season Mismatch", msg)
            return
    except: pass

    try:
        s_time = datetime.strptime(start, "%H:%M").time()
        e_time = datetime.strptime(end, "%H:%M").time()
        if e_time <= s_time:
             messagebox.showwarning("Invalid Time", "End time must be after start time.")
             return
             
        full_start_dt = datetime.combine(game_date, s_time)
        # Note: Past date check removed or can be kept depending on preference
        # if full_start_dt < datetime.now():
        #      messagebox.showwarning("Invalid Date/Time", "Cannot schedule a game in the past.")
        #      return

    except Exception as e:
        messagebox.showwarning("Invalid Time", "Use HH:MM format (24h).")
        return

    # 4. DB Operations
    cur = sched_mgr.mydb.cursor()
    try:
        cur.execute("SELECT id FROM teams WHERE teamName = ?", (t1,))
        r1 = cur.fetchone()
        cur.execute("SELECT id FROM teams WHERE teamName = ?", (t2,))
        r2 = cur.fetchone()
        cur.execute("SELECT id FROM venues WHERE venueName = ?", (v,))
        rv = cur.fetchone()

        if not r1 or not r2 or not rv:
            messagebox.showerror("Error", "Teams or Venue not found in DB.")
            return
            
        tid1, tid2, vid = r1['id'], r2['id'], rv['id']

        # --- EXCEPTION HANDLING FOR CONFLICTS ---

        # 1. CHECK LOCATION CONSISTENCY (Must play at same venue if played on same day)
        # Check Team 1
        cur.execute("""
            SELECT v.venueName FROM games g
            JOIN venues v ON g.venue_id = v.id
            WHERE g.game_date = ? 
              AND (g.team1_id = ? OR g.team2_id = ?)
              AND g.venue_id != ?
            LIMIT 1
        """, (game_date.isoformat(), tid1, tid1, vid))
        row = cur.fetchone()
        if row:
            messagebox.showwarning("Location Conflict", f"Team '{t1}' is already scheduled at '{row['venueName']}' on this day.\nTeams cannot play in different venues on the same day.")
            return

        # Check Team 2
        cur.execute("""
            SELECT v.venueName FROM games g
            JOIN venues v ON g.venue_id = v.id
            WHERE g.game_date = ? 
              AND (g.team1_id = ? OR g.team2_id = ?)
              AND g.venue_id != ?
            LIMIT 1
        """, (game_date.isoformat(), tid2, tid2, vid))
        row = cur.fetchone()
        if row:
            messagebox.showwarning("Location Conflict", f"Team '{t2}' is already scheduled at '{row['venueName']}' on this day.\nTeams cannot play in different venues on the same day.")
            return

        # 2. CHECK TIME OVERLAPS
        
        # Check Venue Conflict
        cur.execute("""
            SELECT start_time, end_time FROM games 
            WHERE game_date = ? AND venue_id = ?
        """, (game_date.isoformat(), vid))
        for row in cur.fetchall():
            db_s = datetime.strptime(row['start_time'], "%H:%M").time()
            db_e = datetime.strptime(row['end_time'], "%H:%M").time()
            if s_time < db_e and db_s < e_time:
                messagebox.showwarning("Conflict", f"Venue '{v}' is already booked for this time slot.")
                return

        # Check Team 1 Time Conflict
        cur.execute("""
            SELECT start_time, end_time FROM games 
            WHERE game_date = ? AND (team1_id = ? OR team2_id = ?)
        """, (game_date.isoformat(), tid1, tid1))
        for row in cur.fetchall():
            db_s = datetime.strptime(row['start_time'], "%H:%M").time()
            db_e = datetime.strptime(row['end_time'], "%H:%M").time()
            if s_time < db_e and db_s < e_time:
                messagebox.showwarning("Conflict", f"Team '{t1}' has another game scheduled during this time.")
                return

        # Check Team 2 Time Conflict
        cur.execute("""
            SELECT start_time, end_time FROM games 
            WHERE game_date = ? AND (team1_id = ? OR team2_id = ?)
        """, (game_date.isoformat(), tid2, tid2))
        for row in cur.fetchall():
            db_s = datetime.strptime(row['start_time'], "%H:%M").time()
            db_e = datetime.strptime(row['end_time'], "%H:%M").time()
            if s_time < db_e and db_s < e_time:
                messagebox.showwarning("Conflict", f"Team '{t2}' has another game scheduled during this time.")
                return

        # --- END EXCEPTION HANDLING ---

        gid = sched_mgr.scheduleGame(tid1, tid2, vid, game_date.isoformat())
        sched_mgr.updateGame(gid, tid1, tid2, vid, game_date.isoformat(), 
                             s_time.strftime("%H:%M"), e_time.strftime("%H:%M"))

        messagebox.showinfo("Success", f"Game Scheduled:\n{t1} vs {t2}\n{game_date} @ {s_time.strftime('%H:%M')}")
        
        reset_team_selections()

    except Exception as e:
        messagebox.showerror("DB Error", f"Failed to schedule game:\n{e}")
        return
    finally:
        cur.close()

    load_scheduled_games_from_db()
    try:
        from viewGamesTab import refresh_scheduled_games_table
        refresh_scheduled_games_table(refs.get('scheduled_games_table'))
    except Exception:
        pass
    
    update_game_preview()
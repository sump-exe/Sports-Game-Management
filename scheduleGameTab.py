import customtkinter as ctk
from tkinter import messagebox
from datetime import datetime, date as _date
from theDB import * # Global references injected by mainGui
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

# --- HELPER: Fetch wins for specific season/year (Generic) ---
def _get_wins_map_for_season(season_name, year_str):
    """Returns a dictionary {team_name: win_count} for the specified season window."""
    wins_map = {name: 0 for name in teams.keys()}
    try:
        year_val = int(year_str)
    except ValueError:
        return wins_map

    s_helper = Season()
    start_date, end_date = s_helper.get_range(season_name, year_val)
    
    if not start_date or not end_date:
        return wins_map

    cur = sched_mgr.mydb.cursor()
    try:
        cur.execute("""
            SELECT t.teamName, COUNT(g.id) as win_count
            FROM games g
            JOIN teams t ON g.winner_team_id = t.id
            WHERE g.is_final = 1 
              AND g.game_date BETWEEN ? AND ?
            GROUP BY t.teamName
        """, (start_date.isoformat(), end_date.isoformat()))
        rows = cur.fetchall()
        for r in rows:
            wins_map[r['teamName']] = r['win_count']
    except Exception as e:
        print(f"Error calculating wins: {e}")
    finally:
        cur.close()
    return wins_map

# --- NEW HELPER: Playoff Logic ---
def _get_playoff_candidates(year_str):
    """
    Returns a list of exactly 2 team names representing the lowest ranking 
    teams that have NOT been eliminated yet.
    """
    try:
        year_val = int(year_str)
    except ValueError:
        return []

    s_helper = Season()
    
    # 1. Identify Eliminated Teams (Anyone who lost a game in THIS Playoff season)
    playoff_start, playoff_end = s_helper.get_range("Playoff", year_val)
    eliminated_ids = set()
    
    cur = sched_mgr.mydb.cursor()
    try:
        # Find losers in finalized playoff games
        if playoff_start and playoff_end:
            cur.execute("""
                SELECT CASE 
                    WHEN winner_team_id = team1_id THEN team2_id
                    WHEN winner_team_id = team2_id THEN team1_id
                END as loser_id
                FROM games
                WHERE is_final = 1 
                  AND winner_team_id IS NOT NULL
                  AND game_date BETWEEN ? AND ?
            """, (playoff_start.isoformat(), playoff_end.isoformat()))
            rows = cur.fetchall()
            for r in rows:
                if r[0]: eliminated_ids.add(r[0])
    except Exception as e:
        print(f"Error checking elimination: {e}")
        cur.close()
        return []

    # 2. Get Regular Season stats for Ranking Non-Eliminated Teams
    reg_start, reg_end = s_helper.get_range("Regular Season", year_val)
    candidates = []
    
    try:
        # We need all teams that are NOT in eliminated_ids and have correct roster size
        # We rank them by Regular Season Wins ASC (lowest first), then Points ASC
        
        # Build placeholder list of valid IDs from memory first (roster check)
        valid_roster_ids = []
        for t_name, t_roster in teams.items():
            if len(t_roster) == 12: # Enforce roster size
                # Get ID from DB
                cur.execute("SELECT id FROM teams WHERE teamName = ?", (t_name,))
                r = cur.fetchone()
                if r and r['id'] not in eliminated_ids:
                    valid_roster_ids.append(r['id'])

        if not valid_roster_ids:
            cur.close()
            return []

        # Query stats for these valid IDs
        # We perform a LEFT JOIN on games to count wins/points in Regular Season
        placeholders = ','.join(['?'] * len(valid_roster_ids))
        query = f"""
            SELECT 
                t.teamName,
                (SELECT COUNT(*) FROM games g WHERE g.winner_team_id = t.id 
                 AND g.game_date BETWEEN ? AND ?) as reg_wins,
                t.totalPoints -- Using aggregate total points as tiebreaker
            FROM teams t
            WHERE t.id IN ({placeholders})
            ORDER BY reg_wins ASC, totalPoints ASC
        """
        
        params = [reg_start.isoformat(), reg_end.isoformat()] + valid_roster_ids
        cur.execute(query, params)
        rows = cur.fetchall()
        
        # 3. Select only the bottom 2 (Lowest Ranking)
        # Since we sorted ASC, the first 2 rows are the lowest ranked
        for r in rows:
            candidates.append(r['teamName'])
            
        # If we have teams, return strictly the bottom 2 (or all if < 2)
        return candidates[:2]

    except Exception as e:
        print(f"Error calculating playoff seeds: {e}")
        return []
    finally:
        cur.close()

# --- Logic to filter Team 2 based on Team 1 ---
def on_team1_select(choice):
    """Triggered when Team 1 is selected."""
    update_game_preview()
    
    # Check if Season is Playoff
    season = refs.get('tab3_season_opt').get()
    year_txt = refs.get('tab3_year_entry').get()

    if season == "Playoff":
        # In Playoff mode, Team 1 list is already restricted to the bottom 2.
        # Team 2 must simply be the *other* team in that pair.
        candidates = _get_playoff_candidates(year_txt)
        valid_opponents = [c for c in candidates if c != choice]
    else:
        # Standard Logic (Same Wins)
        if choice == "Select" or not choice:
            update_schedule_optionmenus(None, refs.get("tab3_team2_opt"), None)
            return

        wins_map = _get_wins_map_for_season(season, year_txt)
        target_wins = wins_map.get(choice, 0)
        
        required_size = 12
        valid_opponents = []
        all_teams = list(teams.keys())
        for t in all_teams:
            if t == choice: continue
            roster = teams.get(t, [])
            if len(roster) != required_size: continue
            
            if wins_map.get(t, 0) == target_wins:
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
    # Determine Context (Season/Year)
    season = refs.get('tab3_season_opt').get() if refs.get('tab3_season_opt') else "Regular Season"
    year_txt = refs.get('tab3_year_entry').get() if refs.get('tab3_year_entry') else str(datetime.now().year)
    
    if season == "Playoff":
        # Playoff Logic: Only lowest ranking teams available
        team_names = _get_playoff_candidates(year_txt)
        # If < 2 teams, we can't schedule a game
        if len(team_names) < 2:
             team_names = ["Not enough teams"]
    else:
        # Standard Logic: All teams with 12 players
        required_size = 12
        team_names_all = list(teams.keys())
        filtered = []
        for t in team_names_all:
            roster = teams.get(t, [])
            if len(roster) == int(required_size):
                filtered.append(t)
        team_names = filtered if filtered else []

    # Update Team 1 Dropdown
    if team1_opt and hasattr(team1_opt, "configure"):
        team1_opt.configure(values=team_names)
    
    # Update Team 2 Dropdown (Reset to matching Team 1 list initially)
    if team2_opt and hasattr(team2_opt, "configure"):
        team2_opt.configure(values=team_names)
    
    available_venues = [v for v, d in venues.items() if d.get("available", True)]
    if venue_opt and hasattr(venue_opt, "configure"):
        venue_opt.configure(values=available_venues)

    # Validation to ensure selected value is still valid
    try:
        if team1_opt and team1_opt.get() not in team_names: team1_opt.set("Select")
    except: pass
    
    try:
        if team2_opt and team2_opt.get() not in team_names: team2_opt.set("Select")
    except: pass
    
    try:
        if venue_opt and venue_opt.get() not in available_venues: venue_opt.set("Select")
    except: pass

def build_schedule_left_ui(parent):
    global refs

    frame = ctk.CTkFrame(parent)
    frame.pack(fill="both", expand=False, padx=10, pady=10)

    # 1. Season (Row 0)
    ctk.CTkLabel(frame, text="Season:").grid(row=0, column=0, sticky="w", pady=3)
    season_values = ["Pre-season", "Regular Season", "Play-in", "Playoff", "Finals", "Off-season"]
    # Trigger reset and update logic when Season changes
    season_opt = ctk.CTkOptionMenu(frame, values=season_values, command=lambda *_: [reset_team_selections(), update_game_preview()])
    season_opt.set("Regular Season")
    season_opt.grid(row=0, column=1, sticky="ew", pady=3)
    refs["tab3_season_opt"] = season_opt

    # 2. Year (Row 1)
    ctk.CTkLabel(frame, text="Year:").grid(row=1, column=0, sticky="w", pady=3)
    year_entry = ctk.CTkEntry(frame, placeholder_text=str(datetime.now().year))
    year_entry.grid(row=1, column=1, sticky="ew", pady=3)
    # Trigger reset and update logic when Year changes
    year_entry.bind("<KeyRelease>", lambda e: [reset_team_selections(), update_game_preview()])
    refs["tab3_year_entry"] = year_entry

    # 3. Date (Month-Day) (Row 2)
    ctk.CTkLabel(frame, text="Month-Day (MM-DD):").grid(row=2, column=0, sticky="w", pady=3)
    date_entry = ctk.CTkEntry(frame, placeholder_text="MM-DD (e.g. 03-15)")
    date_entry.grid(row=2, column=1, sticky="ew", pady=3)
    date_entry.bind("<KeyRelease>", lambda e: update_game_preview())
    refs["tab3_date_entry"] = date_entry

    # 4. Team 1 (Row 3)
    ctk.CTkLabel(frame, text="Team 1:").grid(row=3, column=0, sticky="w", pady=3)
    team1_opt = ctk.CTkOptionMenu(frame, values=["Select"], command=on_team1_select)
    team1_opt.grid(row=3, column=1, sticky="ew", pady=3)
    refs["tab3_team1_opt"] = team1_opt

    # 5. Team 2 (Row 4)
    ctk.CTkLabel(frame, text="Team 2:").grid(row=4, column=0, sticky="w", pady=3)
    team2_opt = ctk.CTkOptionMenu(frame, values=["Select"], command=lambda *_: update_game_preview())
    team2_opt.grid(row=4, column=1, sticky="ew", pady=3)
    refs["tab3_team2_opt"] = team2_opt

    # 6. Venue (Row 5)
    ctk.CTkLabel(frame, text="Venue:").grid(row=5, column=0, sticky="w", pady=3)
    venue_opt = ctk.CTkOptionMenu(frame, values=["Select"], command=lambda *_: update_game_preview())
    venue_opt.grid(row=5, column=1, sticky="ew", pady=3)
    refs["tab3_venue_opt"] = venue_opt

    # 7. Start Time (Row 6)
    ctk.CTkLabel(frame, text="Start Time (HH:MM):").grid(row=6, column=0, sticky="w", pady=3)
    start_entry = ctk.CTkEntry(frame, placeholder_text="13:00")
    start_entry.grid(row=6, column=1, sticky="ew", pady=3)
    start_entry.bind("<KeyRelease>", lambda e: update_game_preview())
    refs["tab3_start_entry"] = start_entry

    # 8. End Time (Row 7)
    ctk.CTkLabel(frame, text="End Time (HH:MM):").grid(row=7, column=0, sticky="w", pady=3)
    end_entry = ctk.CTkEntry(frame, placeholder_text="15:00")
    end_entry.grid(row=7, column=1, sticky="ew", pady=3)
    end_entry.bind("<KeyRelease>", lambda e: update_game_preview())
    refs["tab3_end_entry"] = end_entry

    # Button (Row 8)
    save_btn = ctk.CTkButton(frame, text="Schedule Game", command=schedule_game)
    save_btn.grid(row=8, column=0, columnspan=2, pady=10, sticky="ew")

    frame.grid_columnconfigure(1, weight=1)
    # Initial population
    update_schedule_optionmenus(team1_opt, team2_opt, venue_opt)
    return frame

def reset_team_selections():
    """Helper to reset dropdowns if Season/Year changes, triggering the context-aware filter."""
    try:
        # Pass the widgets explicitly to update them based on new season/year
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
    
    if season or year: lines.append(f"Season: {season} {year}")
    if md: lines.append(f"Date:   {md}")
    
    start = refs.get('tab3_start_entry').get().strip() if refs.get('tab3_start_entry') else ""
    end = refs.get('tab3_end_entry').get().strip() if refs.get('tab3_end_entry') else ""
    if start: lines.append(f"Time:   {start} - {end}")
    
    venue = refs.get('tab3_venue_opt').get() if refs.get('tab3_venue_opt') else ""
    if venue and venue != "Select": lines.append(f"Venue:  {venue}")
    
    t1 = refs.get('tab3_team1_opt').get() if refs.get('tab3_team1_opt') else ""
    t2 = refs.get('tab3_team2_opt').get() if refs.get('tab3_team2_opt') else ""
    
    if t1 and t1 != "Select" and t2 and t2 != "Select":
        lines.append(f"\n{t1} vs {t2}")
        
    lbl = refs.get('game_preview_label') or refs.get('game_preview')
    if lbl: lbl.configure(text="\n".join(lines) if lines else "Fill details to preview...")

# --- Helpers ---
def _season_range_for_year(season, year):
    mapping = Season(year)
    if season not in mapping.season_ranges: return None, None
    (sm, sd), (em, ed) = mapping[season]
    start = _date(year, sm, sd)
    end = _date(year + 1, em, ed) if (em, ed) < (sm, sd) else _date(year, em, ed)
    return start, end

def _is_date_within_season(parsed_date, season, year_val):
    if not season or season == "Select": return True, ""
    tries = []
    for y in (year_val, year_val - 1):
        s_obj = Season()
        start, end = s_obj.get_range(season, y)
        if start and end:
            tries.append((start, end))
            if start <= parsed_date <= end: return True, ""
    return False, f"Date not in {season} window."

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
    if not all([t1, t2, v, md, year_txt, start, end]) or "Select" in (t1, t2, v) or "No Match" in (t1, t2):
        messagebox.showwarning("Missing Info", "Please fill all fields and select matching teams.")
        return
    if t1 == t2:
        messagebox.showwarning("Invalid", "Teams must be different.")
        return

    # 3. Parse Date/Time
    try:
        y_val = int(year_txt)
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
             
        # Check if Date/Time is in the Past
        full_start_dt = datetime.combine(game_date, s_time)
        if full_start_dt < datetime.now():
             messagebox.showwarning("Invalid Date/Time", "Cannot schedule a game in the past.")
             return

    except Exception as e:
        print(e)
        messagebox.showwarning("Invalid Time", "Use HH:MM format (24h).")
        return

    # 4. DB Operations (Fetch IDs -> Check Conflicts -> Insert)
    cur = sched_mgr.mydb.cursor()
    try:
        # A. Fetch IDs
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

        # B. Check Conflicts
        cur.execute("""
            SELECT start_time, end_time 
            FROM games 
            WHERE game_date = ? 
              AND (team1_id IN (?, ?) OR team2_id IN (?, ?) OR venue_id = ?)
        """, (game_date.isoformat(), tid1, tid2, tid1, tid2, vid))
        
        for row in cur.fetchall():
            db_s = datetime.strptime(row['start_time'], "%H:%M").time()
            db_e = datetime.strptime(row['end_time'], "%H:%M").time()
            # Overlap check
            if s_time < db_e and db_s < e_time:
                messagebox.showwarning("Conflict", "Team or Venue booked for this time slot.")
                return

        # C. Insert Game
        gid = sched_mgr.scheduleGame(tid1, tid2, vid, game_date.isoformat())
        sched_mgr.updateGame(gid, tid1, tid2, vid, game_date.isoformat(), 
                             s_time.strftime("%H:%M"), e_time.strftime("%H:%M"))

        messagebox.showinfo("Success", f"Game Scheduled:\n{t1} vs {t2}\n{game_date} @ {s_time.strftime('%H:%M')}")

    except Exception as e:
        messagebox.showerror("DB Error", f"Failed to schedule game:\n{e}")
        return
    finally:
        cur.close()

    # 5. Refresh UI
    load_scheduled_games_from_db()
    try:
        from viewGamesTab import refresh_scheduled_games_table
        refresh_scheduled_games_table(refs.get('scheduled_games_table'))
    except Exception:
        pass
    
    update_game_preview()
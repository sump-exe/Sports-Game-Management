import customtkinter as ctk
from tkinter import messagebox
from theDB import *

app = None
sched_mgr = None
refs = {}
load_scheduled_games_from_db = lambda: None
refresh_scheduled_games_table = lambda *a, **k: None
update_schedule_optionmenus = lambda *a, **k: None

teams = {}

def load_teams_from_db():
    teams.clear()
    cur = sched_mgr.mydb.cursor()
    cur.execute("SELECT id, teamName FROM teams ORDER BY teamName")
    rows = cur.fetchall()
    for r in rows:
        teams[r['teamName']] = []
        pc = sched_mgr.mydb.cursor()
        pc.execute("SELECT id, name, jerseyNumber FROM players WHERE team_id = ? ORDER BY CAST(jerseyNumber AS INTEGER) ASC", (r['id'],))
        players = []
        for p in pc.fetchall():
            pid = p['id'] if 'id' in p.keys() else p[0]
            name = p['name'] if 'name' in p.keys() else p[1]
            jersey = p['jerseyNumber'] if 'jerseyNumber' in p.keys() else p[2]
            players.append({'id': pid, 'name': name, 'jersey': jersey})
        teams[r['teamName']] = players
        pc.close()
    cur.close()

def show_team_players(team_name, players_frame):
    # record currently shown team for other helpers (history popup, etc.)
    try:
        if isinstance(refs, dict):
            refs['current_team'] = team_name
    except Exception:
        pass

    for w in players_frame.winfo_children():
        w.destroy()

    title = ctk.CTkLabel(players_frame, text=f"🏆 Team: {team_name}", font=ctk.CTkFont(size=18, weight="bold"))
    title.pack(pady=(8, 6))

    actions_frame = ctk.CTkFrame(players_frame, fg_color="#1F1F1F")
    actions_frame.pack(fill="x", padx=12, pady=(0,6))

    def delete_team_cmd():
        if not messagebox.askyesno("Delete Team", f"Are you sure you want to delete the team '{team_name}'? This will remove the team and may remove scheduled games."):
            return
        cur = sched_mgr.mydb.cursor()
        try:
            cur.execute("SELECT id FROM teams WHERE teamName = ?", (team_name,))
            row = cur.fetchone()
            if not row:
                messagebox.showwarning("Not found", "Team not found in database.")
                return
            team_id = row['id']
            cur.execute("SELECT COUNT(*) FROM games WHERE team1_id = ? OR team2_id = ?", (team_id, team_id))
            cnt = cur.fetchone()[0]
            if cnt and cnt > 0:
                if not messagebox.askyesno("Team Has Games", f"Team has {cnt} scheduled game(s). Delete those games and the team? This cannot be undone."):
                    return
                cur.execute("DELETE FROM games WHERE team1_id = ? OR team2_id = ?", (team_id, team_id))
            cur.execute("DELETE FROM players WHERE team_id = ?", (team_id,))
            cur.execute("DELETE FROM teams WHERE id = ?", (team_id,))
            sched_mgr.mydb.commit()
        finally:
            cur.close()

        teams.pop(team_name, None)
        try:
            from standingsTab import standings as _standings
            _standings.pop(team_name, None)
        except Exception:
            pass

        load_scheduled_games_from_db()
        refresh_scheduled_games_table(refs.get('scheduled_games_table'))
        try:
            refresh_team_sidebar(refs.get('teams_sidebar_scroll'), refs.get('team_players_area'), refs.get('teams_buttons'), refs.get('teams_search_var'))
        except Exception:
            pass

        for w in players_frame.winfo_children():
            w.destroy()
        return

    edit_btn = ctk.CTkButton(actions_frame, text="Edit Team", width=120, fg_color="#FFA500", hover_color="#FFB86B", command=lambda: open_add_team_popup(prefill_name=team_name))
    edit_btn.pack(side="right", padx=(6,0))

    del_btn = ctk.CTkButton(actions_frame, text="Delete Team", width=120, fg_color="#D9534F", hover_color="#FF6B6B", command=delete_team_cmd)
    del_btn.pack(side="right", padx=(6,0))

    # New: History button in the team actions area
    def open_team_history_cmd():
        open_team_history_popup(team_name)

    history_btn = ctk.CTkButton(actions_frame, text="View Games", width=120, fg_color="#1F75FE", hover_color="#4A90E2", command=open_team_history_cmd)
    history_btn.pack(side="right", padx=(6,0))

    if teams.get(team_name):
        header_row = ctk.CTkFrame(players_frame, fg_color="#222222")
        header_row.pack(fill="x", padx=12, pady=(6,2))
        ctk.CTkLabel(header_row, text="Player", anchor="w").pack(side="left", padx=(6,0))
        ctk.CTkLabel(header_row, text="Jersey", anchor="e").pack(side="right", padx=(0,6))
        for p in teams[team_name]:
            row = ctk.CTkFrame(players_frame, fg_color="#333333")
            row.pack(fill="x", padx=12, pady=2)
            name = p.get('name') if isinstance(p, dict) else str(p)
            jersey = p.get('jersey') if isinstance(p, dict) else None
            pid = p.get('id') if isinstance(p, dict) else None

            ctk.CTkLabel(row, text=(f"#{jersey} " if jersey is not None else ""), anchor="e").pack(side="left", padx=(0,6))

            ctk.CTkLabel(row, text=name, anchor="w").pack(side="left", padx=(6,0))

            btns = ctk.CTkFrame(row, fg_color="#333333")
            btns.pack(side="right", padx=(6,6))

            def make_delete(pid_local, pname):
                def delete_player_cmd():
                    if not messagebox.askyesno("Delete Player", f"Delete player '{pname}'?"):
                        return
                    cur = sched_mgr.mydb.cursor()
                    try:
                        cur.execute("DELETE FROM players WHERE id = ?", (pid_local,))
                        sched_mgr.mydb.commit()
                    finally:
                        cur.close()
                    load_teams_from_db()
                    show_team_players(team_name, players_frame)
                    update_schedule_optionmenus(refs.get('tab3_team1_opt'), refs.get('tab3_team2_opt'), refs.get('tab3_venue_opt'))
                return delete_player_cmd

            def make_edit(pid_local, pname, pjersey):
                def edit_player_cmd():
                    win = ctk.CTkToplevel(app)
                    win.title("Edit Player")
                    win.geometry("360x260")
                    win.transient(app)

                    ctk.CTkLabel(win, text="Player Name:").pack(pady=(12,4), anchor="w", padx=12)
                    name_e = ctk.CTkEntry(win)
                    name_e.insert(0, pname)
                    name_e.pack(fill="x", padx=12)

                    ctk.CTkLabel(win, text="Jersey #:").pack(pady=(8,4), anchor="w", padx=12)
                    jersey_e = ctk.CTkEntry(win)
                    jersey_e.insert(0, str(pjersey) if pjersey is not None else "")
                    jersey_e.pack(fill="x", padx=12)

                    validated = {'ok': False}

                    msg_lbl = ctk.CTkLabel(win, text="", text_color="#FFD700")
                    msg_lbl.pack(pady=(6,0))

                    def validate_inputs():
                        new_name = name_e.get().strip()
                        jersey_txt = jersey_e.get().strip()
                        if not new_name:
                            msg_lbl.configure(text="Player name cannot be empty.")
                            validated['ok'] = False
                            confirm_btn.configure(state="disabled")
                            return
                        if len(new_name) > 50:
                            msg_lbl.configure(text="Player name must be 50 characters or fewer.")
                            validated['ok'] = False
                            confirm_btn.configure(state="disabled")
                            return
                        
                        # --- NEW VALIDATION: No Numbers in Player Name ---
                        if any(char.isdigit() for char in new_name):
                            msg_lbl.configure(text="Player name cannot contain numbers.")
                            validated['ok'] = False
                            confirm_btn.configure(state="disabled")
                            return
                        # ------------------------------------------------

                        if jersey_txt == "":
                            msg_lbl.configure(text="Jersey number is required.")
                            validated['ok'] = False
                            confirm_btn.configure(state="disabled")
                            return
                        if not jersey_txt.isdigit():
                            msg_lbl.configure(text="Jersey number must be an integer.")
                            validated['ok'] = False
                            confirm_btn.configure(state="disabled")
                            return
                        new_jersey = int(jersey_txt)
                        if new_jersey < 1 or new_jersey > 99:
                            msg_lbl.configure(text="Jersey number must be between 1 and 99.")
                            validated['ok'] = False
                            confirm_btn.configure(state="disabled")
                            return

                        cur = sched_mgr.mydb.cursor()
                        try:
                            cur.execute("SELECT id FROM teams WHERE teamName = ?", (team_name,))
                            rowt = cur.fetchone()
                            if not rowt:
                                msg_lbl.configure(text="Team not found in DB.")
                                validated['ok'] = False
                                confirm_btn.configure(state="disabled")
                                return
                            team_id_local = rowt['id']
                            if new_jersey is not None:
                                cur.execute("SELECT COUNT(*) FROM players WHERE team_id = ? AND jerseyNumber = ? AND id != ?", (team_id_local, new_jersey, pid_local))
                                cnt = cur.fetchone()[0]
                                if cnt and cnt > 0:
                                    msg_lbl.configure(text=f"Jersey #{new_jersey} is already used on this team.")
                                    validated['ok'] = False
                                    confirm_btn.configure(state="disabled")
                                    return
                        finally:
                            cur.close()

                        msg_lbl.configure(text="Validation OK — click Confirm to save", text_color="#7CFC00")
                        validated['ok'] = True
                        confirm_btn.configure(state="normal")

                    def save_player_edit():
                        if not validated.get('ok'):
                            messagebox.showwarning("Not Validated", "Please validate changes before confirming.")
                            return
                        new_name = name_e.get().strip()
                        jersey_txt = jersey_e.get().strip()
                        new_jersey = int(jersey_txt)

                        cur = sched_mgr.mydb.cursor()
                        try:
                            cur.execute("UPDATE players SET name = ?, jerseyNumber = ? WHERE id = ?", (new_name, new_jersey, pid_local))
                            sched_mgr.mydb.commit()
                        finally:
                            cur.close()
                        win.destroy()
                        load_teams_from_db()
                        show_team_players(team_name, players_frame)
                        update_schedule_optionmenus(refs.get('tab3_team1_opt'), refs.get('tab3_team2_opt'), refs.get('tab3_venue_opt'))

                    btn_frame2 = ctk.CTkFrame(win, fg_color="#2A2A2A")
                    btn_frame2.pack(side="bottom", pady=12, fill="x")
                    validate_btn = ctk.CTkButton(btn_frame2, text="Validate", command=validate_inputs, hover_color="#4A90E2")
                    validate_btn.pack(side="left", padx=8, pady=6)
                    confirm_btn = ctk.CTkButton(btn_frame2, text="Confirm", command=save_player_edit, hover_color="#7CFC00")
                    confirm_btn.pack(side="left", padx=8, pady=6)
                    confirm_btn.configure(state="disabled")
                return edit_player_cmd

            edit_btn = ctk.CTkButton(btns, text="Edit", width=60, height=26, command=make_edit(pid, name, jersey), hover_color="#FFA500")
            edit_btn.pack(side="left", padx=(0,6))
            del_btn = ctk.CTkButton(btns, text="Del", width=60, height=26, command=make_delete(pid, name), hover_color="#FF6B6B")
            del_btn.pack(side="left")
    else:
        ctk.CTkLabel(players_frame, text="(No players yet)", text_color="#BBBBBB").pack(pady=6)

    add_frame = ctk.CTkFrame(players_frame, fg_color="#333333")
    add_frame.pack(pady=12, padx=8, fill="x")

    jersey_entry = ctk.CTkEntry(add_frame, placeholder_text="Jersey #", width=80)
    jersey_entry.pack(side="left", padx=(6,8), pady=8)

    entry = ctk.CTkEntry(add_frame, placeholder_text="Player name")
    entry.pack(side="left", expand=True, fill="x", padx=(8, 6), pady=8)

    def add_player_cmd():
        name = entry.get().strip()
        if not name:
            messagebox.showwarning("Missing", "Enter a player name.")
            return

        if len(name) > 50:
            messagebox.showwarning("Invalid", "Player name must be 50 characters or fewer.")
            return
            
        # --- NEW VALIDATION: No Numbers in Player Name ---
        if any(char.isdigit() for char in name):
            messagebox.showwarning("Invalid", "Player name cannot contain numbers.")
            return
        # ------------------------------------------------

        jersey_text = jersey_entry.get().strip()
        if jersey_text == "":
            messagebox.showwarning("Missing", "Jersey number is required.")
            return
        if not jersey_text.isdigit():
            messagebox.showwarning("Invalid", "Jersey number must be an integer between 1 and 99.")
            return

        jersey_num = int(jersey_text)
        if jersey_num < 1 or jersey_num > 99:
            messagebox.showwarning("Invalid", "Jersey number must be between 1 and 99.")
            return

        cur = sched_mgr.mydb.cursor()
        try:
            cur.execute("SELECT id FROM teams WHERE teamName = ?", (team_name,))
            row = cur.fetchone()
            if not row:
                messagebox.showwarning("Error", "Team not found in database.")
                return
            team_id = row['id']
        finally:
            cur.close()

        cur2 = sched_mgr.mydb.cursor()
        try:
            cur2.execute("SELECT COUNT(*) FROM players WHERE team_id = ? AND jerseyNumber = ?", (team_id, jersey_num))
            cnt = cur2.fetchone()[0]
            if cnt > 0:
                messagebox.showwarning("Duplicate", f"Jersey number #{jersey_num} is already taken on this team.")
                return
        finally:
            cur2.close()

        try:
            team_obj = Team(team_name, team_id)
            player_obj = Player(name, jersey_num)
            team_obj.addPlayer(player_obj)
        except Exception as e:
            messagebox.showwarning("Error", f"Could not add player: {e}")
            return

        load_teams_from_db()
        entry.delete(0, "end")
        jersey_entry.delete(0, "end")
        show_team_players(team_name, players_frame)
        update_schedule_optionmenus(
            refs.get('tab3_team1_opt'),
            refs.get('tab3_team2_opt'),
            refs.get('tab3_venue_opt')
        )

    add_btn = ctk.CTkButton(add_frame, text="Add Player", command=add_player_cmd, width=100, hover_color="#4A90E2")
    add_btn.pack(side="right", padx=(6, 8), pady=8)

def refresh_team_sidebar(sidebar_scrollable, players_area, team_buttons_list, search_var=None):
    for btn in list(team_buttons_list):
        try:
            btn.destroy()
        except Exception:
            pass
    team_buttons_list.clear()

    team_names = list(teams.keys())

    if search_var and search_var.get().strip():
        query = search_var.get().strip().lower()
        filtered = []
        for t in team_names:
            if query in t.lower():
                filtered.append(t)
                continue

            for p in teams.get(t, []):
                p_name = p['name'] if isinstance(p, dict) else str(p)
                if query in p_name.lower():
                    filtered.append(t)
                    break

        team_names = filtered

    team_names.sort()

    for t in team_names:
        b = ctk.CTkButton(
            sidebar_scrollable,
            text=f"🏆 {t}",
            width=220,
            height=35,
            command=lambda name=t: show_team_players(name, players_area),
            hover_color="#4A90E2",
            fg_color="#2E2E2E"
        )
        b.pack(padx=8, pady=4, fill="x")
        team_buttons_list.append(b)

def open_add_team_popup(prefill_name=None):
    win = ctk.CTkToplevel(app)
    win.title("Add Team")
    win.geometry("360x140")
    win.transient(app)

    ctk.CTkLabel(win, text="New Team Name:").pack(pady=(12,6), anchor="w", padx=12)
    name_entry = ctk.CTkEntry(win)
    name_entry.pack(fill="x", padx=12)

    editing = False
    original_name = None
    if prefill_name:
        editing = True
        original_name = prefill_name
        name_entry.insert(0, prefill_name)

    def save_team():
        name = name_entry.get().strip()
        if not name:
            messagebox.showwarning("Missing", "Team name cannot be empty.")
            return

        # --- NEW VALIDATION: No Numbers in Team Name ---
        if any(char.isdigit() for char in name):
            messagebox.showwarning("Invalid", "Team name cannot contain numbers.")
            return
        # -----------------------------------------------

        if editing and original_name and original_name != name:
            cur = sched_mgr.mydb.cursor()
            try:
                cur.execute("SELECT id FROM teams WHERE teamName = ?", (original_name,))
                row = cur.fetchone()
                if not row:
                    messagebox.showwarning("Not found", "Original team not found in DB.")
                    return
                team_id = row['id']
                try:
                    cur.execute("UPDATE teams SET teamName = ? WHERE id = ?", (name, team_id))
                    sched_mgr.mydb.commit()
                except Exception:
                    messagebox.showwarning("Exists", "A team with that name already exists.")
                    return
            finally:
                cur.close()
        else:
            try:
                t = Team(name)
                sched_mgr.addTeam(t)
            except Exception:
                messagebox.showwarning("Exists", "Team may already exist or could not be added.")
                return

        load_teams_from_db()
        try:
            from standingsTab import standings as _standings
            if editing and original_name and original_name in _standings:
                _standings[name] = _standings.pop(original_name)
            elif name not in _standings:
                _standings[name] = {"mvp": "N/A", "wins": 0}
        except Exception:
            pass

        try:
            refresh_team_sidebar(refs.get('teams_sidebar_scroll'), refs.get('team_players_area'), refs.get('teams_buttons'), refs.get('teams_search_var'))
        except Exception:
            pass

        update_schedule_optionmenus(refs.get('tab3_team1_opt'), refs.get('tab3_team2_opt'), refs.get('tab3_venue_opt'))
        win.destroy()

    btn_text = "Save Changes" if prefill_name else "Add Team"
    ctk.CTkButton(win, text=btn_text, command=save_team, hover_color="#4A90E2").pack(pady=12)

def open_team_history_popup(team_name=None):
    """Show a popup with the selected team's game history.
    If team_name is None, attempts to use refs['current_team'] set by show_team_players.
    """
    sel_team = team_name or (refs.get('current_team') if isinstance(refs, dict) else None)
    if not sel_team:
        messagebox.showwarning("No Team Selected", "No team selected. Open a team first from the sidebar.")
        return

    cur = sched_mgr.mydb.cursor()
    try:
        cur.execute("SELECT id FROM teams WHERE teamName = ?", (sel_team,))
        row = cur.fetchone()
        if not row:
            messagebox.showwarning("Not Found", "Team not found in database.")
            return
        team_id = row['id']

        cur.execute("""
            SELECT
                g.id,
                g.team1_id,
                g.team2_id,
                t1.teamName AS team1_name,
                t2.teamName AS team2_name,
                v.venueName AS venue,
                g.game_date,
                g.start_time,
                g.end_time,
                g.is_final,
                g.winner_team_id,
                COALESCE(g.team1_score, 0) AS team1_score,
                COALESCE(g.team2_score, 0) AS team2_score
            FROM games g
            LEFT JOIN teams t1 ON g.team1_id = t1.id
            LEFT JOIN teams t2 ON g.team2_id = t2.id
            LEFT JOIN venues v ON g.venue_id = v.id
            WHERE g.team1_id = ? OR g.team2_id = ?
            ORDER BY g.game_date DESC, g.start_time DESC
        """, (team_id, team_id))
        games = cur.fetchall()
    finally:
        try:
            cur.close()
        except Exception:
            pass

    win = ctk.CTkToplevel(app)
    win.title(f"Game History — {sel_team}")
    win.geometry("700x420")
    win.transient(app)

    header = ctk.CTkLabel(win, text=f"Game History — {sel_team}", font=ctk.CTkFont(size=16, weight="bold"))
    header.pack(pady=(12,6))

    container = ctk.CTkScrollableFrame(win, width=660, height=320, fg_color="#0F0F0F")
    container.pack(padx=12, pady=(6,12), fill="both", expand=True)

    if not games:
        ctk.CTkLabel(container, text="No games found for this team.", anchor="w", text_color="#BBBBBB").pack(padx=8, pady=8)
        return

    for g in games:
        gid = g['id']
        team1 = g['team1_name'] or "Unknown"
        team2 = g['team2_name'] or "Unknown"
        venue = g['venue'] or "Unknown"
        date = g['game_date'] or ""
        start = g['start_time'] or "00:00"
        end = g['end_time'] or "00:00"
        is_final = bool(g['is_final']) if 'is_final' in g.keys() else False
        t1_score = g['team1_score'] if 'team1_score' in g.keys() else 0
        t2_score = g['team2_score'] if 'team2_score' in g.keys() else 0

        if g['team1_id'] == team_id:
            opponent = team2
            score_display = f"{t1_score} - {t2_score}"
            won = (g['winner_team_id'] == team_id) if g['winner_team_id'] is not None else None
        else:
            opponent = team1
            score_display = f"{t1_score} - {t2_score}"
            won = (g['winner_team_id'] == team_id) if g['winner_team_id'] is not None else None

        status = "Ended" if is_final else "Active"
        result = ""
        if is_final:
            if g['winner_team_id'] is None:
                result = "Tie"
            else:
                result = "W" if won else "L"

        row = ctk.CTkFrame(container, fg_color="#1F1F1F")
        row.pack(fill="x", padx=8, pady=6)
        row.grid_columnconfigure(0, weight=3)
        row.grid_columnconfigure(1, weight=1)
        row.grid_columnconfigure(2, weight=1)
        row.grid_columnconfigure(3, weight=1)

        ctk.CTkLabel(row, text=f"{date} {start}-{end}", anchor="w").grid(row=0, column=0, padx=8, pady=4, sticky="w")
        # show opponent name (no "Home"/"Away" semantics)
        ctk.CTkLabel(row, text=f"vs {opponent}", anchor="w").grid(row=0, column=1, padx=8, pady=4, sticky="w")
        ctk.CTkLabel(row, text=venue, anchor="w").grid(row=0, column=2, padx=8, pady=4, sticky="w")
        ctk.CTkLabel(row, text=f"{status}{(' • ' + result) if result else ''}", anchor="w").grid(row=0, column=3, padx=8, pady=4, sticky="w")

        # small second-line with score when finalized
        if is_final:
            score_lbl = ctk.CTkLabel(row, text=f"Score: {score_display}", text_color="#FFD700")
            score_lbl.grid(row=1, column=0, columnspan=4, sticky="w", padx=8, pady=(0,6))

    btn_frame = ctk.CTkFrame(win, fg_color="#181818")
    btn_frame.pack(fill="x", padx=12, pady=(0,12))
    ctk.CTkButton(btn_frame, text="Close", command=win.destroy, width=100).pack(side="right", padx=8, pady=8)
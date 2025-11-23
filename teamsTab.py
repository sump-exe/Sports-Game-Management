import customtkinter as ctk
from tkinter import messagebox
from datetime import datetime
from theDB import *

# NOTE: This module no longer imports mainGui or the other UI modules to avoid
# circular imports. The mainGui.py file will set the following variables on
# this module after importing it:
#
#   app, sched_mgr, refs
#   load_scheduled_games_from_db (function from file3)
#   refresh_scheduled_games_table (function from file4)
#   update_schedule_optionmenus (function from file3)
#
# Default placeholders so the module can be imported safely during startup.
app = None
sched_mgr = None
refs = {}
load_scheduled_games_from_db = lambda: None
refresh_scheduled_games_table = lambda *a, **k: None
update_schedule_optionmenus = lambda *a, **k: None

# tab 1 - teams

teams = {}   # { "TeamName": ["Player1", ...] }

def load_teams_from_db():
    """Populate the in-memory `teams` dict from the DB (names -> player lists)."""
    teams.clear()
    cur = sched_mgr.mydb.cursor()
    cur.execute("SELECT id, teamName FROM teams ORDER BY teamName")
    rows = cur.fetchall()
    for r in rows:
        teams[r['teamName']] = []
        # load players for each team (include id and jersey number)
        pc = sched_mgr.mydb.cursor()
        pc.execute("SELECT id, name, jerseyNumber FROM players WHERE team_id = ? ORDER BY name", (r['id'],))
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
    # clear players area
    for w in players_frame.winfo_children():
        w.destroy()

    title = ctk.CTkLabel(players_frame, text=f"🏆 Team: {team_name}", font=ctk.CTkFont(size=18, weight="bold"))
    title.pack(pady=(8, 6))

    # Team actions (Edit/Delete) - place to the right of title
    actions_frame = ctk.CTkFrame(players_frame, fg_color="#1F1F1F")
    actions_frame.pack(fill="x", padx=12, pady=(0,6))

    def delete_team_cmd():
        if not messagebox.askyesno("Delete Team", f"Are you sure you want to delete the team '{team_name}'? This will remove the team and may remove scheduled games."):
            return
        # lookup team id
        cur = sched_mgr.mydb.cursor()
        try:
            cur.execute("SELECT id FROM teams WHERE teamName = ?", (team_name,))
            row = cur.fetchone()
            if not row:
                messagebox.showwarning("Not found", "Team not found in database.")
                return
            team_id = row['id']
            # check for scheduled games that reference this team
            cur.execute("SELECT COUNT(*) FROM games WHERE home_team_id = ? OR away_team_id = ?", (team_id, team_id))
            cnt = cur.fetchone()[0]
            if cnt and cnt > 0:
                # confirm cascade delete
                if not messagebox.askyesno("Team Has Games", f"Team has {cnt} scheduled game(s). Delete those games and the team? This cannot be undone."):
                    return
                # delete related games first
                cur.execute("DELETE FROM games WHERE home_team_id = ? OR away_team_id = ?", (team_id, team_id))
            # delete players (FK ON DELETE CASCADE would handle players if configured, but ensure removal)
            cur.execute("DELETE FROM players WHERE team_id = ?", (team_id,))
            # delete the team
            cur.execute("DELETE FROM teams WHERE id = ?", (team_id,))
            sched_mgr.mydb.commit()
        finally:
            cur.close()

        # update in-memory and UI
        teams.pop(team_name, None)
        try:
            from file5 import standings as _standings
            _standings.pop(team_name, None)
        except Exception:
            pass

        # reload scheduled games from db and refresh UI
        load_scheduled_games_from_db()
        refresh_scheduled_games_table(refs.get('scheduled_games_table'))
        # refresh team sidebar (mainGui will have set refs)
        try:
            refresh_team_sidebar(refs.get('teams_sidebar_scroll'), refs.get('team_players_area'), refs.get('teams_buttons'), refs.get('teams_search_var'))
        except Exception:
            # fallback: if refresh_team_sidebar not available, just clear players area
            pass

        # clear players area
        for w in players_frame.winfo_children():
            w.destroy()
        return

    edit_btn = ctk.CTkButton(actions_frame, text="Edit Team", width=120, fg_color="#FFA500", hover_color="#FFB86B", command=lambda: open_add_team_popup(prefill_name=team_name))
    edit_btn.pack(side="right", padx=(6,0))

    del_btn = ctk.CTkButton(actions_frame, text="Delete Team", width=120, fg_color="#D9534F", hover_color="#FF6B6B", command=delete_team_cmd)
    del_btn.pack(side="right", padx=(6,0))

    # players list (show name and jersey in two columns)
    if teams.get(team_name):
        # header for the small roster area
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

            # name label (left)
            ctk.CTkLabel(row, text=name, anchor="w").pack(side="left", padx=(6,0))

            # Jersey label (right-most)
            ctk.CTkLabel(row, text=(f"#{jersey}" if jersey is not None else ""), anchor="e").pack(side="right", padx=(0,6))

            # Buttons for edit/delete
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
                    # reload and refresh UI
                    load_teams_from_db()
                    show_team_players(team_name, players_frame)
                    # update schedule option menus (mainGui will wire this to file3.update_schedule_optionmenus)
                    update_schedule_optionmenus(refs.get('tab3_team1_opt'), refs.get('tab3_team2_opt'), refs.get('tab3_venue_opt'))
                return delete_player_cmd

            def make_edit(pid_local, pname, pjersey):
                def edit_player_cmd():
                    win = ctk.CTkToplevel(app)
                    win.title("Edit Player")
                    win.geometry("360x260")
                    win.transient(app)
                    win.grab_set()

                    ctk.CTkLabel(win, text="Player Name:").pack(pady=(12,4), anchor="w", padx=12)
                    name_e = ctk.CTkEntry(win)
                    name_e.insert(0, pname)
                    name_e.pack(fill="x", padx=12)

                    ctk.CTkLabel(win, text="Jersey #:").pack(pady=(8,4), anchor="w", padx=12)
                    jersey_e = ctk.CTkEntry(win)
                    jersey_e.insert(0, str(pjersey) if pjersey is not None else "")
                    jersey_e.pack(fill="x", padx=12)

                    # validation status
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
                        # Jersey is required and must be a positive integer
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
                        if new_jersey <= 0:
                            msg_lbl.configure(text="Jersey number must be positive.")
                            validated['ok'] = False
                            confirm_btn.configure(state="disabled")
                            return

                        # Lookup team id and check duplicate jersey
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

                        # validation passed
                        msg_lbl.configure(text="Validation OK — click Confirm to save", text_color="#7CFC00")
                        validated['ok'] = True
                        confirm_btn.configure(state="normal")

                    def save_player_edit():
                        # require validation before save
                        if not validated.get('ok'):
                            messagebox.showwarning("Not Validated", "Please validate changes before confirming.")
                            return
                        new_name = name_e.get().strip()
                        jersey_txt = jersey_e.get().strip()
                        # jersey is required and validated already
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

                    # Buttons: Validate + Confirm (Confirm disabled until validation passes)
                    btn_frame2 = ctk.CTkFrame(win, fg_color="#2A2A2A")
                    btn_frame2.pack(side="bottom", pady=12, fill="x")
                    validate_btn = ctk.CTkButton(btn_frame2, text="Validate", command=validate_inputs, hover_color="#4A90E2")
                    validate_btn.pack(side="left", padx=8, pady=6)
                    confirm_btn = ctk.CTkButton(btn_frame2, text="Confirm", command=save_player_edit, hover_color="#7CFC00")
                    confirm_btn.pack(side="left", padx=8, pady=6)
                    confirm_btn.configure(state="disabled")
                return edit_player_cmd

            # pack buttons
            edit_btn = ctk.CTkButton(btns, text="Edit", width=60, height=26, command=make_edit(pid, name, jersey), hover_color="#FFA500")
            edit_btn.pack(side="left", padx=(0,6))
            del_btn = ctk.CTkButton(btns, text="Del", width=60, height=26, command=make_delete(pid, name), hover_color="#FF6B6B")
            del_btn.pack(side="left")
    else:
        ctk.CTkLabel(players_frame, text="(No players yet)", text_color="#BBBBBB").pack(pady=6)

    # add player section
    add_frame = ctk.CTkFrame(players_frame, fg_color="#333333")
    add_frame.pack(pady=12, padx=8, fill="x")

    entry = ctk.CTkEntry(add_frame, placeholder_text="Player name")
    entry.pack(side="left", expand=True, fill="x", padx=(8, 6), pady=8)

    # optional jersey number entry
    jersey_entry = ctk.CTkEntry(add_frame, placeholder_text="Jersey #", width=80)
    jersey_entry.pack(side="left", padx=(6,8), pady=8)

    def add_player_cmd():
        name = entry.get().strip()
        if not name:
            messagebox.showwarning("Missing", "Enter a player name.")
            return

        # -------- JERSEY IS NOW REQUIRED --------
        jersey_text = jersey_entry.get().strip()
        if jersey_text == "":
            messagebox.showwarning("Missing", "Jersey number is required.")
            return
        if not jersey_text.isdigit():
            messagebox.showwarning("Invalid", "Jersey number must be an integer.")
            return

        jersey_num = int(jersey_text)
        if jersey_num <= 0:
            messagebox.showwarning("Invalid", "Jersey number must be a positive integer.")
            return
        # -----------------------------------------

        # find team ID
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

        # check duplicate jersey within same team
        cur2 = sched_mgr.mydb.cursor()
        try:
            cur2.execute("SELECT COUNT(*) FROM players WHERE team_id = ? AND jerseyNumber = ?", (team_id, jersey_num))
            cnt = cur2.fetchone()[0]
            if cnt > 0:
                messagebox.showwarning("Duplicate", f"Jersey number #{jersey_num} is already taken on this team.")
                return
        finally:
            cur2.close()

        # save new player
        try:
            team_obj = Team(team_name, team_id)
            player_obj = Player(name, jersey_num)  # jersey now guaranteed
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
    """Rebuild team buttons in sidebar, with optional filtering by team name or player name"""
    # clear
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
            # match team name
            if query in t.lower():
                filtered.append(t)
                continue

            # match players inside the team
            for p in teams.get(t, []):
                p_name = p['name'] if isinstance(p, dict) else str(p)
                if query in p_name.lower():
                    filtered.append(t)
                    break

        team_names = filtered

    # Sort alphabetically
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
    win.grab_set()

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

        # If editing and the name changed, perform an update
        if editing and original_name and original_name != name:
            cur = sched_mgr.mydb.cursor()
            try:
                # find team id
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
            # create Team object and save to DB
            try:
                t = Team(name)
                sched_mgr.addTeam(t)
            except Exception:
                messagebox.showwarning("Exists", "Team may already exist or could not be added.")
                return

        # reload teams from DB and refresh UI
        load_teams_from_db()
        # update standings key if renamed
        try:
            from file5 import standings as _standings
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
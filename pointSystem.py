import customtkinter as ctk
from tkinter import messagebox
from theDB import mydb, ScheduleManager

def load_point_system_into_frame(parent, game_id, team1_id, team2_id):
    for w in parent.winfo_children():
        try:
            w.destroy()
        except Exception:
            pass

    try:
        parent.grid_columnconfigure(0, weight=1)
        parent.grid_columnconfigure(1, weight=1)
        parent.grid_rowconfigure(1, weight=1)
    except Exception:
        pass

    top_frame = ctk.CTkFrame(parent)
    top_frame.grid(row=0, column=0, columnspan=2, sticky="nsew", padx=12, pady=(8,6))
    top_frame.grid_columnconfigure(0, weight=0)
    top_frame.grid_columnconfigure(1, weight=1)
    top_frame.grid_columnconfigure(2, weight=1)
    top_frame.grid_columnconfigure(3, weight=0)

    def restore_view_tab():
        for w in parent.winfo_children():
            try:
                w.destroy()
            except Exception:
                pass
        try:
            parent.grid_columnconfigure(0, weight=1)
            parent.grid_columnconfigure(1, weight=1)
            parent.grid_rowconfigure(1, weight=1)
        except Exception:
            pass

        ctk.CTkLabel(parent, text="Scheduled Games",
                     font=ctk.CTkFont(size=18, weight="bold")).grid(
            row=0, column=0, padx=10, pady=10, sticky="w"
        )
        games_table_scroll = ctk.CTkScrollableFrame(parent, width=900, height=450)
        games_table_scroll.grid(row=1, column=0, padx=10, pady=10, sticky="nsew")
        game_details_frame = ctk.CTkFrame(parent)
        game_details_frame.grid(row=1, column=1, padx=10, pady=10, sticky="nsew")
        ctk.CTkLabel(game_details_frame, text="Game Details",
                     font=ctk.CTkFont(size=16, weight="bold")).pack(pady=10)
        details_label = ctk.CTkLabel(game_details_frame, text="Select a game to view details.",
                                     justify="left", anchor="nw")
        details_label.pack(fill="both", expand=True, padx=10, pady=10)

        vgt = None
        try:
            import viewGamesTab as vgt_mod
            vgt = vgt_mod
            if not hasattr(vgt, 'refs') or not isinstance(vgt.refs, dict):
                vgt.refs = {}
            vgt.refs['tab4'] = parent
            vgt.refs['game_details_frame'] = game_details_frame
            vgt.refs['details_content'] = details_label
            vgt.refs['scheduled_games_table'] = games_table_scroll
        except Exception:
            vgt = None

        if vgt and hasattr(vgt, 'refresh_scheduled_games_table'):
            try:
                vgt.refresh_scheduled_games_table(games_table_scroll)
            except Exception:
                ctk.CTkLabel(games_table_scroll, text="Unable to load scheduled games.").pack(padx=8, pady=8)
        else:
            ctk.CTkLabel(games_table_scroll, text="Scheduled games unavailable.").pack(padx=8, pady=8)

        def reopen_point_system():
            sel = None
            try:
                sel = (vgt.refs or {}).get("selected_game") if vgt and hasattr(vgt, 'refs') else None
            except Exception:
                sel = None
            if not sel:
                messagebox.showwarning("No Game Selected", "Please select a game first.")
                return
            load_point_system_into_frame(parent, sel.get("id"), sel.get("team1_id"), sel.get("team2_id"))

        ctk.CTkButton(parent, text="Open Point System", command=reopen_point_system).grid(
            row=2, column=1, padx=10, pady=10, sticky="e"
        )

        try:
            if vgt and hasattr(vgt, 'refs') and isinstance(vgt.refs, dict):
                vgt.refs.pop('point_system_active', None)
                vgt.refs.pop('point_system_game_id', None)
        except Exception:
            pass

    back_btn = ctk.CTkButton(top_frame, text="← Back to Games", width=140, command=restore_view_tab)
    back_btn.grid(row=0, column=0, padx=(2,8), pady=6, sticky="w")
    title_lbl = ctk.CTkLabel(top_frame, text=f"Point System — Game #{game_id}", font=ctk.CTkFont(size=18, weight="bold"))
    title_lbl.grid(row=0, column=1, padx=6, sticky="w")
    winner_lbl = ctk.CTkLabel(top_frame, text="", font=ctk.CTkFont(size=13, weight="bold"))
    winner_lbl.grid(row=0, column=2, padx=6, sticky="w")
    interactive_widgets = []

    container = ctk.CTkFrame(parent)
    container.grid(row=1, column=0, columnspan=2, sticky="nsew", padx=12, pady=6)
    container.grid_columnconfigure(0, weight=1)
    container.grid_columnconfigure(1, weight=1)
    container.grid_rowconfigure(0, weight=1)
    left_frame = ctk.CTkScrollableFrame(container)
    left_frame.grid(row=0, column=0, sticky="nsew", padx=(0,6))
    right_frame = ctk.CTkScrollableFrame(container)
    right_frame.grid(row=0, column=1, sticky="nsew", padx=(6,0))

    def get_team_total(team_id):
        cur = mydb.cursor()
        try:
            cur.execute("SELECT SUM(points) as s FROM players WHERE team_id = ?", (team_id,))
            r = cur.fetchone()
            return r['s'] if r and r['s'] is not None else 0
        finally:
            try:
                cur.close()
            except Exception:
                pass

    def update_team_total_in_db(team_id):
        total = get_team_total(team_id)
        cur = mydb.cursor()
        try:
            cur.execute("UPDATE teams SET totalPoints = ? WHERE id = ?", (total, team_id))
            mydb.commit()
        finally:
            try:
                cur.close()
            except Exception:
                pass
        return total

    def add_points(player_id, entry_widget, label_widget, team_id):
        sm = ScheduleManager()
        try:
            if sm.isGameFinal(game_id):
                messagebox.showwarning("Game Ended", "This game has ended. No more points can be added.")
                disable_interactive_widgets()
                return
        except Exception:
            pass

        points_txt = entry_widget.get().strip()
        if not points_txt:
            messagebox.showwarning("Missing", "Enter points to add.")
            return
        try:
            pts = int(points_txt)
            if pts <= 0:
                raise ValueError()
        except Exception:
            messagebox.showerror("Invalid", "Points must be a positive integer.")
            return

        cur = mydb.cursor()
        try:
            cur.execute("UPDATE players SET points = points + ? WHERE id = ?", (pts, player_id))
            mydb.commit()
            cur.execute("SELECT points FROM players WHERE id = ?", (player_id,))
            r = cur.fetchone()
            new_points = r['points'] if r and 'points' in r.keys() else 0
            total = update_team_total_in_db(team_id)
        except Exception as e:
            try:
                cur.close()
            except Exception:
                pass
            messagebox.showerror("Error", f"Failed to add points: {e}")
            return
        finally:
            try:
                cur.close()
            except Exception:
                pass

        name_part = label_widget.cget("text").split(" | Points: ")[0]
        label_widget.configure(text=f"{name_part} | Points: {new_points}")
        if team_id in team_total_labels:
            team_total_labels[team_id].configure(text=f"Total Points: {total}")
        entry_widget.delete(0, "end")

    def disable_interactive_widgets():
        for ent, btn in interactive_widgets:
            try:
                ent.configure(state="disabled")
            except Exception:
                pass
            try:
                btn.configure(state="disabled")
            except Exception:
                pass

    def load_team(team_id):
        cur = mydb.cursor()
        try:
            cur.execute("SELECT teamName FROM teams WHERE id = ?", (team_id,))
            row = cur.fetchone()
            if not row:
                return "Unknown Team", []
            tname = row['teamName']
            cur.execute("SELECT id, name, jerseyNumber, points, team_id FROM players WHERE team_id = ? ORDER BY jerseyNumber", (team_id,))
            rows = cur.fetchall()
            players = []
            for r in rows:
                players.append({
                    'id': r['id'],
                    'name': r['name'],
                    'jerseyNumber': r['jerseyNumber'],
                    'points': r['points'],
                    'team_id': r['team_id']
                })
            return tname, players
        finally:
            try:
                cur.close()
            except Exception:
                pass

    team_total_labels = {}
    def render_team_column(frame, team_id):
        team_name, roster = load_team(team_id)
        hdr = ctk.CTkLabel(frame, text=team_name, font=ctk.CTkFont(size=16, weight="bold"))
        hdr.pack(pady=(8,6), anchor="w", padx=8)
        if not roster:
            ctk.CTkLabel(frame, text="No players", anchor="w").pack(padx=8, pady=4)
        else:
            for p in roster:
                row = ctk.CTkFrame(frame)
                row.pack(fill="x", padx=8, pady=4)
                jersey = f"#{p['jerseyNumber']}" if p.get('jerseyNumber') not in (None, '') else ""
                name_text = f"{jersey + ' - ' if jersey else ''}{p['name']}"
                lbl = ctk.CTkLabel(row, text=f"{name_text} | Points: {p['points']}", anchor="w")
                lbl.pack(side="left", fill="x", expand=True, padx=(6,0))
                ent = ctk.CTkEntry(row, width=80, placeholder_text="Points")
                ent.pack(side="left", padx=(6,4))
                btn = ctk.CTkButton(row, text="Add", width=60,
                                    command=lambda pid=p['id'], e=ent, l=lbl, tid=p.get('team_id', team_id): add_points(pid, e, l, tid))
                btn.pack(side="left", padx=(4,6))
                interactive_widgets.append((ent, btn))
        total = get_team_total(team_id)
        total_label = ctk.CTkLabel(frame, text=f"Total Points: {total}", font=ctk.CTkFont(size=14, weight="bold"))
        total_label.pack(pady=(10,12))
        team_total_labels[team_id] = total_label

    render_team_column(left_frame, team1_id)
    render_team_column(right_frame, team2_id)

    def display_winner_label(winner_team_id):
        if winner_team_id:
            cur = mydb.cursor()
            try:
                cur.execute("SELECT teamName FROM teams WHERE id = ?", (winner_team_id,))
                r = cur.fetchone()
                tname = r['teamName'] if r and 'teamName' in r.keys() else "Unknown"
            finally:
                try:
                    cur.close()
                except Exception:
                    pass
            winner_lbl.configure(text=f"Winner: {tname}")
        else:
            winner_lbl.configure(text="Result: Tie")

    def end_game_action():
        sm = ScheduleManager()
        try:
            if sm.isGameFinal(game_id):
                cur = mydb.cursor()
                try:
                    cur.execute("SELECT winner_team_id FROM games WHERE id = ?", (game_id,))
                    r = cur.fetchone()
                    winner_id = r['winner_team_id'] if r and 'winner_team_id' in r.keys() else None
                finally:
                    try:
                        cur.close()
                    except Exception:
                        pass
                display_winner_label(winner_id)
                disable_interactive_widgets()
                messagebox.showinfo("Game Already Ended", "This game has already been ended.")
                return
        except Exception:
            pass

        if not messagebox.askyesno("End Game", "End this game? No further points can be added."):
            return

        try:
            winner = sm.endGame(game_id)
        except Exception as e:
            messagebox.showerror("Error", f"Could not end game: {e}")
            return
        disable_interactive_widgets()
        display_winner_label(winner)
        try:
            import standingsTab as st
            tbl = st.refs.get('standings_table') if isinstance(st.refs, dict) else None
            if tbl and hasattr(st, 'refresh_standings_table'):
                st.refresh_standings_table(tbl)
        except Exception:
            pass
        try:
            import viewGamesTab as vgt
            tbl = vgt.refs.get('scheduled_games_table') if isinstance(vgt.refs, dict) else None
            if tbl and hasattr(vgt, 'refresh_scheduled_games_table'):
                vgt.refresh_scheduled_games_table(tbl)
        except Exception:
            pass
        messagebox.showinfo("Game Ended", "Game has been marked final.")

    end_btn = ctk.CTkButton(top_frame, text="End Game", width=110, command=end_game_action)
    end_btn.grid(row=0, column=3, padx=6, pady=6, sticky="e")

    try:
        sm = ScheduleManager()
        if sm.isGameFinal(game_id):
            cur = mydb.cursor()
            try:
                cur.execute("SELECT winner_team_id FROM games WHERE id = ?", (game_id,))
                r = cur.fetchone()
                win_id = r['winner_team_id'] if r and 'winner_team_id' in r.keys() else None
            finally:
                try:
                    cur.close()
                except Exception:
                    pass
            display_winner_label(win_id)
            disable_interactive_widgets()
    except Exception:
        pass

def open_point_system_window(game_id, team1_id, team2_id):
    win = ctk.CTkToplevel()
    win.title(f"Point System — Game #{game_id}")
    win.geometry("1100x700")
    load_point_system_into_frame(win, game_id, team1_id, team2_id)
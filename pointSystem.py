import customtkinter as ctk
from tkinter import messagebox
from theDB import *

def load_point_system_into_frame(parent, game_id, team1_id, team2_id):
    # 1. Clear existing widgets
    for w in parent.winfo_children():
        try:
            w.destroy()
        except Exception:
            pass

    # 2. Configure Grid
    try:
        parent.grid_columnconfigure(0, weight=1)
        parent.grid_columnconfigure(1, weight=1)
        parent.grid_rowconfigure(1, weight=1)
    except Exception:
        pass

    # --- Top Bar (Back button, Title, End Game) ---
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

        # Reconstruct View Games Layout
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

        # Attempt to refresh the games table
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
            vgt.refresh_scheduled_games_table(games_table_scroll)
        except Exception:
            ctk.CTkLabel(games_table_scroll, text="Unable to reload games table.").pack(padx=8, pady=8)

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
            row=0, column=1, padx=10, pady=10, sticky="e"
        )

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

    # --- Helper Functions ---

    def get_game_team_total(g_id, t_id):
        # Calculate sum from game_player_stats for this game and team
        cur = mydb.cursor()
        try:
            cur.execute("""
                SELECT SUM(gps.points) 
                FROM game_player_stats gps
                JOIN players p ON gps.player_id = p.id
                WHERE gps.game_id = ? AND p.team_id = ?
            """, (g_id, t_id))
            val = cur.fetchone()[0]
            return val if val is not None else 0
        finally:
            cur.close()

    def modify_points(player_id, entry_widget, label_widget, team_id, multiplier=1):
        """
        multiplier: 1 for ADD, -1 for SUBTRACT
        """
        # 1. Capture and Validate Points
        txt = entry_widget.get().strip()
        if not txt:
            return
        try:
            pts_val = int(txt) 
            # --- NEW VALIDATION: Must be > 0 ---
            if pts_val <= 0:
                messagebox.showwarning("Invalid", "Points input must be greater than 0.")
                entry_widget.delete(0, "end")
                return
        except ValueError:
            messagebox.showwarning("Invalid", "Points must be an integer.")
            entry_widget.delete(0, "end")
            return

        # 2. Check if Game is Final
        sm = ScheduleManager()
        if sm.isGameFinal(game_id):
            messagebox.showwarning("Game Final", "This game has ended. Cannot modify points.")
            entry_widget.delete(0, "end")
            return
        
        # Calculate actual change (+ve or -ve)
        pts_inc = pts_val * multiplier

        # 3. Check for Negative Total (if subtracting)
        cur = mydb.cursor()
        try:
            if multiplier == -1:
                cur.execute("SELECT points FROM game_player_stats WHERE game_id = ? AND player_id = ?", (game_id, player_id))
                row = cur.fetchone()
                current_game_pts = row['points'] if row else 0
                
                if current_game_pts + pts_inc < 0:
                    messagebox.showwarning("Invalid Operation", f"Player only has {current_game_pts} points. Cannot subtract {pts_val}.")
                    entry_widget.delete(0, "end")
                    cur.close()
                    return

            # 4. Update Database
            # A. Update GAME SPECIFIC STATS (game_player_stats)
            # UPSERT: Insert if not exists, else update
            cur.execute("""
                INSERT INTO game_player_stats (game_id, player_id, points) 
                VALUES (?, ?, ?)
                ON CONFLICT(game_id, player_id) 
                DO UPDATE SET points = points + ?
            """, (game_id, player_id, pts_inc, pts_inc)) # For insert, uses pts_inc (e.g. 5 or -5). Note: insert -5 technically possible via SQL but checked above.

            # B. Update Total (Career) Points in Players table
            cur.execute("UPDATE players SET points = points + ? WHERE id = ?", (pts_inc, player_id))
            
            # C. Update GAMES table score (Critical for viewGamesTab)
            # We recalculate the total for the team in this game to be safe
            cur.execute("""
                SELECT SUM(gps.points) FROM game_player_stats gps
                JOIN players p ON gps.player_id = p.id
                WHERE gps.game_id = ? AND p.team_id = ?
            """, (game_id, team_id))
            new_team_score = cur.fetchone()[0] or 0

            cur.execute("SELECT team1_id, team2_id FROM games WHERE id = ?", (game_id,))
            g_row = cur.fetchone()
            
            if g_row and g_row['team1_id'] == team_id:
                cur.execute("UPDATE games SET team1_score = ? WHERE id = ?", (new_team_score, game_id))
            elif g_row and g_row['team2_id'] == team_id:
                cur.execute("UPDATE games SET team2_score = ? WHERE id = ?", (new_team_score, game_id))
                
            mydb.commit()
            
            # D. Get new specific game points for label
            cur.execute("SELECT points FROM game_player_stats WHERE game_id = ? AND player_id = ?", (game_id, player_id))
            r = cur.fetchone()
            new_player_game_points = r['points'] if r else 0
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to modify points: {e}")
            return
        finally:
            cur.close()

        # 5. Update UI
        current_text = label_widget.cget("text")
        # Regex or split might be fragile if name has " | ". Assuming standard format:
        name_part = current_text.split(" | Points: ")[0]
        label_widget.configure(text=f"{name_part} | Points: {new_player_game_points}")
        
        # Update Team Total Header
        new_total = get_game_team_total(game_id, team_id)
        if team_id in team_total_labels:
            team_total_labels[team_id].configure(text=f"Total Points: {new_total}")
        
        entry_widget.delete(0, "end")

    def disable_interactive_widgets():
        for ent, btn_a, btn_s in interactive_widgets:
            try: ent.configure(state="disabled")
            except: pass
            try: btn_a.configure(state="disabled")
            except: pass
            try: btn_s.configure(state="disabled")
            except: pass

    def load_team_game_data(t_id, g_id):
        # Fetch players AND their points for THIS game
        cur = mydb.cursor()
        try:
            cur.execute("SELECT teamName FROM teams WHERE id = ?", (t_id,))
            row = cur.fetchone()
            if not row: return "Unknown Team", []
            tname = row['teamName']
            
            # LEFT JOIN to get stats if they exist, else 0
            query = """
                SELECT p.id, p.name, p.jerseyNumber, p.team_id,
                       COALESCE(gps.points, 0) as game_points
                FROM players p
                LEFT JOIN game_player_stats gps ON p.id = gps.player_id AND gps.game_id = ?
                WHERE p.team_id = ?
                ORDER BY CAST(p.jerseyNumber AS INTEGER) ASC
            """
            cur.execute(query, (g_id, t_id))
            rows = cur.fetchall()
            players = []
            for r in rows:
                players.append({
                    'id': r['id'], 
                    'name': r['name'], 
                    'jerseyNumber': r['jerseyNumber'], 
                    'points': r['game_points'], # This is now game-specific
                    'team_id': r['team_id']
                })
            return tname, players
        finally:
            try: cur.close()
            except: pass

    team_total_labels = {}
    
    def render_team_column(frame, team_id):
        team_name, roster = load_team_game_data(team_id, game_id)
        ctk.CTkLabel(frame, text=team_name, font=ctk.CTkFont(size=16, weight="bold")).pack(pady=(8,6), anchor="w", padx=8)
        
        if not roster:
            ctk.CTkLabel(frame, text="No players", anchor="w").pack(padx=8, pady=4)
        else:
            for p in roster:
                row = ctk.CTkFrame(frame)
                row.pack(fill="x", padx=8, pady=4)
                
                jersey = f"#{p['jerseyNumber']}" if p.get('jerseyNumber') is not None else ""
                name_text = f"{jersey} - {p['name']}" if jersey else p['name']
                
                # Display GAME SPECIFIC POINTS
                lbl = ctk.CTkLabel(row, text=f"{name_text} | Points: {p['points']}", anchor="w")
                lbl.pack(side="left", fill="x", expand=True, padx=(6,0))
                
                ent = ctk.CTkEntry(row, width=60, placeholder_text="Pts")
                ent.pack(side="left", padx=(6,4))
                
                # ADD BUTTON
                btn_add = ctk.CTkButton(row, text="Add", width=50, fg_color="#4CAF50", hover_color="#45a049",
                                    command=lambda pid=p['id'], e=ent, l=lbl, tid=team_id: modify_points(pid, e, l, tid, 1))
                btn_add.pack(side="left", padx=(2,2))

                # SUB BUTTON
                btn_sub = ctk.CTkButton(row, text="Sub", width=50, fg_color="#D9534F", hover_color="#C9302C",
                                    command=lambda pid=p['id'], e=ent, l=lbl, tid=team_id: modify_points(pid, e, l, tid, -1))
                btn_sub.pack(side="left", padx=(2,6))
                
                interactive_widgets.append((ent, btn_add, btn_sub))
        
        total = get_game_team_total(game_id, team_id)
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
                tname = r['teamName'] if r else "Unknown"
            finally:
                try: cur.close()
                except: pass
            winner_lbl.configure(text=f"Winner: {tname}")
        else:
            winner_lbl.configure(text="Result: Tie")

    def end_game_action():
        sm = ScheduleManager()
        try:
            if sm.isGameFinal(game_id):
                messagebox.showinfo("Game Final", "This game has already been ended.")
                return
        except Exception: pass

        if not messagebox.askyesno("End Game", "End this game? This will determine the winner based on current scores."):
            return

        # 2. Determine Winner Explicitly (Robust Logic)
        cur = mydb.cursor()
        winner_id = None
        try:
            # Re-fetch the latest scores from GAMES table (updated by modify_points)
            cur.execute("SELECT team1_score, team2_score, team1_id, team2_id FROM games WHERE id = ?", (game_id,))
            row = cur.fetchone()
            if row:
                # Force 0 if NULL to prevent comparison errors
                s1 = int(row['team1_score'] or 0)
                s2 = int(row['team2_score'] or 0)
                
                if s1 > s2:
                    winner_id = row['team1_id']
                elif s2 > s1:
                    winner_id = row['team2_id']
                else:
                    winner_id = None # Tie
            
            # 3. Update Game as Final with Winner
            cur.execute("UPDATE games SET is_final = 1, winner_team_id = ? WHERE id = ?", (winner_id, game_id))
            
            # Update legacy wins count in teams table if desired
            if winner_id:
                cur.execute("UPDATE teams SET wins = wins + 1 WHERE id = ?", (winner_id,))
                
            mydb.commit()
            
            disable_interactive_widgets()
            display_winner_label(winner_id)
            
            # 4. Refresh Standings Table
            try:
                import standingsTab as st
                tbl = st.refs.get('standings_table')
                if tbl: st.refresh_standings_table(tbl)
            except: pass
            
            # 5. Refresh View Games Table
            try:
                import viewGamesTab as vgt
                tbl = vgt.refs.get('scheduled_games_table')
                if tbl: vgt.refresh_scheduled_games_table(tbl)
            except: pass
            
            messagebox.showinfo("Game Ended", "Game marked as final. Standings updated.")
        except Exception as e:
            messagebox.showerror("Error", f"Could not end game: {e}")
        finally:
            cur.close()

    end_btn = ctk.CTkButton(top_frame, text="End Game", width=110, command=end_game_action)
    end_btn.grid(row=0, column=3, padx=6, pady=6, sticky="e")

    # If game is already final on load, lock UI
    sm = ScheduleManager()
    try:
        if sm.isGameFinal(game_id):
            cur = mydb.cursor()
            cur.execute("SELECT winner_team_id FROM games WHERE id = ?", (game_id,))
            r = cur.fetchone()
            win_id = r['winner_team_id'] if r else None
            cur.close()
            display_winner_label(win_id)
            disable_interactive_widgets()
    except: pass

def open_point_system_window(game_id, team1_id, team2_id):
    win = ctk.CTkToplevel()
    win.title(f"Point System — Game #{game_id}")
    win.geometry("1100x700")
    load_point_system_into_frame(win, game_id, team1_id, team2_id)
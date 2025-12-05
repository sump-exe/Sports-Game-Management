import customtkinter as ctk
from tkinter import messagebox
from theDB import *

class TeamRosterDisplay:
    """
    Responsible solely for fetching a specific team's roster for a game
    and rendering the player rows into the provided frame.
    """
    def __init__(self, parent_frame, team_id, game_id, action_callback, widget_tracker):
        """
        :param parent_frame: The frame where this team's roster will be drawn.
        :param team_id: The ID of the team to display.
        :param game_id: The current game ID (needed to fetch current points).
        :param action_callback: Function to call when Add/Sub is clicked. Signature: (pid, entry, label, tid, multiplier)
        :param widget_tracker: A list to append interactive widgets to (so the controller can disable them later).
        """
        self.parent = parent_frame
        self.team_id = team_id
        self.game_id = game_id
        self.action_callback = action_callback
        self.widget_tracker = widget_tracker
        self.total_label = None
        
        self._build_ui()

    def _load_data(self):
        cur = mydb.cursor()
        try:
            # Get Team Name
            cur.execute("SELECT teamName FROM teams WHERE id = ?", (self.team_id,))
            row = cur.fetchone()
            team_name = row['teamName'] if row else "Unknown Team"
            
            # Get Roster with current game stats
            query = """
                SELECT p.id, p.name, p.jerseyNumber, p.team_id,
                       COALESCE(gps.points, 0) as game_points
                FROM players p
                LEFT JOIN game_player_stats gps ON p.id = gps.player_id AND gps.game_id = ?
                WHERE p.team_id = ?
                ORDER BY CAST(p.jerseyNumber AS INTEGER) ASC
            """
            cur.execute(query, (self.game_id, self.team_id))
            players = []
            for r in cur.fetchall():
                players.append({
                    'id': r['id'], 'name': r['name'], 
                    'jerseyNumber': r['jerseyNumber'], 'points': r['game_points']
                })
            
            # Get Team Total
            cur.execute("""
                SELECT SUM(gps.points) 
                FROM game_player_stats gps
                JOIN players p ON gps.player_id = p.id
                WHERE gps.game_id = ? AND p.team_id = ?
            """, (self.game_id, self.team_id))
            total = cur.fetchone()[0]
            total_points = total if total is not None else 0
            
            return team_name, players, total_points
        finally:
            cur.close()

    def _build_ui(self):
        team_name, players, total_points = self._load_data()
        
        # Header
        ctk.CTkLabel(self.parent, text=team_name, font=ctk.CTkFont(size=16, weight="bold")).pack(pady=(8,6), anchor="w", padx=8)
        
        # Player Rows
        if not players:
            ctk.CTkLabel(self.parent, text="No players", anchor="w").pack(padx=8, pady=4)
        else:
            for p in players:
                self._create_player_row(p)
                
        # Total Score
        self.total_label = ctk.CTkLabel(self.parent, text=f"Total Points: {total_points}", 
                                        font=ctk.CTkFont(size=14, weight="bold"))
        self.total_label.pack(pady=(10,12))

    def _create_player_row(self, p):
        row = ctk.CTkFrame(self.parent)
        row.pack(fill="x", padx=8, pady=4)
        
        jersey = f"#{p['jerseyNumber']}" if p.get('jerseyNumber') is not None else ""
        name_text = f"{jersey} - {p['name']}" if jersey else p['name']
        
        lbl = ctk.CTkLabel(row, text=f"{name_text} | Points: {p['points']}", anchor="w")
        lbl.pack(side="left", fill="x", expand=True, padx=(6,0))
        
        ent = ctk.CTkEntry(row, width=60, placeholder_text="Pts")
        ent.pack(side="left", padx=(6,4))
        
        # Callback wrappers
        cmd_add = lambda pid=p['id'], e=ent, l=lbl, tid=self.team_id: self.action_callback(pid, e, l, tid, 1)
        cmd_sub = lambda pid=p['id'], e=ent, l=lbl, tid=self.team_id: self.action_callback(pid, e, l, tid, -1)

        btn_add = ctk.CTkButton(row, text="Add", width=50, fg_color="#4CAF50", hover_color="#45a049", command=cmd_add)
        btn_add.pack(side="left", padx=(2,2))

        btn_sub = ctk.CTkButton(row, text="Sub", width=50, fg_color="#D9534F", hover_color="#C9302C", command=cmd_sub)
        btn_sub.pack(side="left", padx=(2,6))
        
        self.widget_tracker.extend([ent, btn_add, btn_sub])

    def update_total_label(self, new_total):
        if self.total_label:
            self.total_label.configure(text=f"Total Points: {new_total}")


class PointSystemController:
    """
    Manages the game scoring system, business logic, DB updates, 
    and instantiates TeamRosterDisplay to handle the UI.
    """
    def __init__(self, parent_frame, game_id, team1_id, team2_id):
        self.parent = parent_frame
        self.game_id = game_id
        self.team1_id = team1_id
        self.team2_id = team2_id
        self.sched_mgr = ScheduleManager()
        
        self.interactive_widgets = []
        self.winner_lbl = None
        
        # Render the Interface
        self._setup_main_layout()
        self._build_header()
        
        # Create Content Containers
        container = ctk.CTkFrame(self.parent)
        container.grid(row=1, column=0, columnspan=2, sticky="nsew", padx=12, pady=6)
        container.grid_columnconfigure(0, weight=1)
        container.grid_columnconfigure(1, weight=1)
        container.grid_rowconfigure(0, weight=1)
        
        left_scroll = ctk.CTkScrollableFrame(container)
        left_scroll.grid(row=0, column=0, sticky="nsew", padx=(0,6))
        
        right_scroll = ctk.CTkScrollableFrame(container)
        right_scroll.grid(row=0, column=1, sticky="nsew", padx=(6,0))

        # Instantiate the Loaders/Displayers
        self.t1_display = TeamRosterDisplay(left_scroll, team1_id, game_id, self.modify_points, self.interactive_widgets)
        self.t2_display = TeamRosterDisplay(right_scroll, team2_id, game_id, self.modify_points, self.interactive_widgets)
        
        self._check_initial_state()

    def _setup_main_layout(self):
        for w in self.parent.winfo_children():
            try: w.destroy()
            except: pass
        try:
            self.parent.grid_columnconfigure(0, weight=1)
            self.parent.grid_columnconfigure(1, weight=1)
            self.parent.grid_rowconfigure(1, weight=1)
        except: pass

    def _build_header(self):
        top_frame = ctk.CTkFrame(self.parent)
        top_frame.grid(row=0, column=0, columnspan=2, sticky="nsew", padx=12, pady=(8,6))
        top_frame.grid_columnconfigure(1, weight=1)
        top_frame.grid_columnconfigure(2, weight=1)
        
        ctk.CTkButton(top_frame, text="← Back", width=100, command=self._go_back).grid(row=0, column=0, padx=8, pady=6)
        
        ctk.CTkLabel(top_frame, text=f"Game #{self.game_id}", font=ctk.CTkFont(size=18, weight="bold")).grid(row=0, column=1, sticky="w")
        
        self.winner_lbl = ctk.CTkLabel(top_frame, text="", font=ctk.CTkFont(size=13, weight="bold"))
        self.winner_lbl.grid(row=0, column=2, sticky="w")
        
        btn_end = ctk.CTkButton(top_frame, text="End Game", width=100, command=self._end_game)
        btn_end.grid(row=0, column=3, padx=8, pady=6)
        self.interactive_widgets.append(btn_end)

    def modify_points(self, player_id, entry_widget, label_widget, team_id, multiplier):
        """Logic for updating points in DB and UI."""
        txt = entry_widget.get().strip()
        if not txt: return
        
        try:
            pts_val = int(txt)
            if pts_val <= 0: raise ValueError
        except ValueError:
            messagebox.showwarning("Invalid", "Points must be a positive integer.")
            entry_widget.delete(0, "end")
            return

        if self.sched_mgr.isGameFinal(self.game_id):
            messagebox.showwarning("Final", "Game is over.")
            entry_widget.delete(0, "end")
            return

        pts_inc = pts_val * multiplier
        cur = mydb.cursor()
        try:
            # Prevent negative total score for player
            if multiplier == -1:
                cur.execute("SELECT points FROM game_player_stats WHERE game_id=? AND player_id=?", (self.game_id, player_id))
                r = cur.fetchone()
                curr = r['points'] if r else 0
                if curr + pts_inc < 0:
                    messagebox.showwarning("Error", "Cannot reduce points below zero.")
                    entry_widget.delete(0, "end")
                    return

            # Update Player Game Stats
            cur.execute("""
                INSERT INTO game_player_stats (game_id, player_id, points) VALUES (?, ?, ?)
                ON CONFLICT(game_id, player_id) DO UPDATE SET points = points + ?
            """, (self.game_id, player_id, pts_inc, pts_inc))
            
            # Update Player Career Stats
            cur.execute("UPDATE players SET points = points + ? WHERE id = ?", (pts_inc, player_id))

            # Update Game Team Score
            cur.execute("""
                SELECT SUM(gps.points) FROM game_player_stats gps
                JOIN players p ON gps.player_id = p.id
                WHERE gps.game_id = ? AND p.team_id = ?
            """, (self.game_id, team_id))
            new_team_score = cur.fetchone()[0] or 0
            
            # Write Score to Games table
            col = 'team1_score' if team_id == self.team1_id else 'team2_score'
            cur.execute(f"UPDATE games SET {col} = ? WHERE id = ?", (new_team_score, self.game_id))
            
            mydb.commit()

            # Update UI Elements
            cur.execute("SELECT points FROM game_player_stats WHERE game_id=? AND player_id=?", (self.game_id, player_id))
            final_pts = cur.fetchone()['points']
            
            # Update individual label
            base_txt = label_widget.cget("text").split(" | ")[0]
            label_widget.configure(text=f"{base_txt} | Points: {final_pts}")
            
            # Update Team Total via the Display Class
            if team_id == self.team1_id:
                self.t1_display.update_total_label(new_team_score)
            else:
                self.t2_display.update_total_label(new_team_score)

        except Exception as e:
            messagebox.showerror("Error", str(e))
        finally:
            cur.close()
            entry_widget.delete(0, "end")

    def _end_game(self):
        if self.sched_mgr.isGameFinal(self.game_id):
            messagebox.showinfo("Info", "Game already ended.")
            return

        if not messagebox.askyesno("Confirm", "End Game? This will finalize the score."):
            return

        winner_id = self.sched_mgr.endGame(self.game_id)
        
        # If there is a winner, update their win count
        if winner_id:
            cur = mydb.cursor()
            cur.execute("UPDATE teams SET wins = wins + 1 WHERE id = ?", (winner_id,))
            mydb.commit()
            cur.close()

        self._finalize_ui(winner_id)
        self._trigger_external_refreshes()
        messagebox.showinfo("Success", "Game Finalized.")

    def _finalize_ui(self, winner_id):
        for w in self.interactive_widgets:
            try: w.configure(state="disabled")
            except: pass
        
        txt = "Tie"
        if winner_id:
            cur = mydb.cursor()
            cur.execute("SELECT teamName FROM teams WHERE id=?", (winner_id,))
            r = cur.fetchone()
            txt = r['teamName'] if r else "Unknown"
            cur.close()
        self.winner_lbl.configure(text=f"Winner: {txt}")

    def _check_initial_state(self):
        if self.sched_mgr.isGameFinal(self.game_id):
            cur = mydb.cursor()
            cur.execute("SELECT winner_team_id FROM games WHERE id=?", (self.game_id,))
            r = cur.fetchone()
            cur.close()
            wid = r['winner_team_id'] if r else None
            self._finalize_ui(wid)

    def _trigger_external_refreshes(self):
        # Refresh other tabs if they are loaded in memory
        try:
            import standingsTab as st
            if st.refs.get('standings_table'): st.refresh_standings_table(st.refs['standings_table'])
        except: pass
        try:
            import viewGamesTab as vgt
            if vgt.refs.get('scheduled_games_table'): vgt.refresh_scheduled_games_table(vgt.refs['scheduled_games_table'])
        except: pass

    def _go_back(self):
        # Clears current frame and reloads the default View Games tab content
        # This mimics the restoration logic from the original file
        for w in self.parent.winfo_children(): w.destroy()
        
        # Basic View Games Layout
        self.parent.grid_columnconfigure(0, weight=1)
        self.parent.grid_columnconfigure(1, weight=1)
        
        ctk.CTkLabel(self.parent, text="Scheduled Games", font=ctk.CTkFont(size=18, weight="bold")).grid(row=0, column=0, padx=10, pady=10, sticky="w")
        
        games_scroll = ctk.CTkScrollableFrame(self.parent, width=900, height=450)
        games_scroll.grid(row=1, column=0, padx=10, pady=10, sticky="nsew")
        
        details_frame = ctk.CTkFrame(self.parent)
        details_frame.grid(row=1, column=1, padx=10, pady=10, sticky="nsew")
        
        ctk.CTkLabel(details_frame, text="Game Details", font=ctk.CTkFont(size=16, weight="bold")).pack(pady=10)
        
        # Inject references back into viewGamesTab
        import viewGamesTab as vgt
        vgt.refs['tab4'] = self.parent
        vgt.refs['scheduled_games_table'] = games_scroll
        vgt.refs['details_content'] = ctk.CTkLabel(details_frame, text="Select a game...", justify="left")
        vgt.refs['details_content'].pack(padx=10)
        
        vgt.refresh_scheduled_games_table(games_scroll)
        
        # Restore the "Open Point System" button
        def reopen():
            sel = vgt.refs.get("selected_game")
            if sel: load_point_system_into_frame(self.parent, sel['id'], sel['team1_id'], sel['team2_id'])
            else: messagebox.showwarning("Warning", "Select a game first.")
            
        ctk.CTkButton(self.parent, text="Open Point System", command=reopen).grid(row=0, column=1, padx=10, pady=10, sticky="e")

# --- Entry Points ---
def load_point_system_into_frame(parent, game_id, team1_id, team2_id):
    PointSystemController(parent, game_id, team1_id, team2_id)

def open_point_system_window(game_id, team1_id, team2_id):
    win = ctk.CTkToplevel()
    win.title(f"Point System - {game_id}")
    win.geometry("1000x600")
    PointSystemController(win, game_id, team1_id, team2_id)
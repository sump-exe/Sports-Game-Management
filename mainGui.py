import customtkinter as ctk
from tkinter import messagebox
from datetime import datetime
from theDB import *
import teamsTab as file1
import venuesTab as file2
import scheduleGameTab as file3
import viewGamesTab as file4
import standingsTab as file5
import pointSystem as file6

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("dark-blue")

class LoginScreen:
    def __init__(self, root, on_login_success):
        self.root = root
        self.on_login_success = on_login_success
        self.frame = None

    def show(self):
        for w in self.root.winfo_children():
            w.destroy()

        self.frame = ctk.CTkFrame(self.root, corner_radius=15)
        self.frame.place(relx=0.5, rely=0.5, anchor="center")

        ctk.CTkLabel(
            self.frame,
            text="Basketball Scheduler",
            font=ctk.CTkFont(size=24, weight="bold")
        ).pack(pady=(40, 10), padx=50)

        ctk.CTkLabel(self.frame, text="Login", font=ctk.CTkFont(size=16)).pack(pady=(0, 20))

        ctk.CTkLabel(self.frame, text="Username:", font=ctk.CTkFont(size=13)).pack(pady=(0, 4), anchor="w", padx=40)
        self.user_ent = ctk.CTkEntry(self.frame, width=280, placeholder_text="Username")
        self.user_ent.pack(pady=(0, 15), padx=40)

        ctk.CTkLabel(self.frame, text="Password:", font=ctk.CTkFont(size=13)).pack(pady=(0, 4), anchor="w", padx=40)
        self.pass_ent = ctk.CTkEntry(self.frame, show="*", width=280, placeholder_text="Password")
        self.pass_ent.pack(pady=(0, 25), padx=40)

        self.user_ent.bind("<Return>", self._verify)
        self.pass_ent.bind("<Return>", self._verify)

        ctk.CTkButton(self.frame, text="Login", command=self._verify, width=280, height=35).pack(pady=(0, 40), padx=40)

    def _verify(self, event=None):
        if self.user_ent.get() == "admin" and self.pass_ent.get() == "123":
            self.root.unbind('<Return>')
            self.on_login_success()
        else:
            messagebox.showerror("Login Failed", "Incorrect credentials")


class BasketballAppController:
    def __init__(self):
        self.app = ctk.CTk()
        self.app.title("Basketball Game Scheduler System")
        self.app.geometry("1200x700")
        
        self.sched_mgr = ScheduleManager()
        self.refs = {} 

        for m in (file1, file2, file3, file4, file5):
            setattr(m, 'app', self.app)
            setattr(m, 'sched_mgr', self.sched_mgr)
            setattr(m, 'refs', self.refs)

        file3.teams = file1.teams
        file3.venues = file2.venues
        file4.scheduled_games = file3.scheduled_games

        file1.load_scheduled_games_from_db = file3.load_scheduled_games_from_db
        file1.refresh_scheduled_games_table = file4.refresh_scheduled_games_table
        file1.update_schedule_optionmenus = file3.update_schedule_optionmenus
        file1.refresh_standings_table = file5.refresh_standings_table
        file2.update_schedule_optionmenus = file3.update_schedule_optionmenus
        
        file4.refs = self.refs
        file5.refs = self.refs

        self.login_ui = LoginScreen(self.app, self.show_main_interface)

    def run(self):
        self.login_ui.show()
        self.app.mainloop()

    def show_main_interface(self):
        for w in self.app.winfo_children():
            w.destroy()
            
        print("[Controller] Entering main interface")

        try:
            self._build_header()
            
            print("[Controller] Creating tabview widget...")
            self.tabview = ctk.CTkTabview(self.app, width=980, height=520)
            self.tabview.pack(padx=10, pady=(6, 12), expand=True, fill="both")
            self.refs['tabview'] = self.tabview

            self.tabview.add("Teams & Players")
            self.tabview.add("Venues")
            self.tabview.add("Schedule Game")
            self.tabview.add("View Games")
            self.tabview.add("Standings")
            print("[Controller] Tab headers created.")

            self._build_teams_tab()
            self._build_venues_tab()
            self._build_schedule_tab()
            self._build_view_games_tab()
            self._build_standings_tab()

            try:
                file3.update_schedule_optionmenus(
                    self.refs.get('tab3_team1_opt'),
                    self.refs.get('tab3_team2_opt'),
                    self.refs.get('tab3_venue_opt'),
                )
            except Exception as e:
                print(f"[Controller] update_schedule_optionmenus: {e}")

            try:
                file1.refresh_team_sidebar(
                    self.refs.get('teams_sidebar_scroll'), 
                    self.refs.get('team_players_area'),
                    self.refs.get('teams_buttons')
                )
                file2.refresh_venue_sidebar(
                    self.refs.get('venues_sidebar_scroll'), 
                    self.refs.get('venues_buttons')
                )
            except Exception as e:
                print(f"[Controller] sidebar refresh: {e}")

            self._start_clock()
            print("[Controller] Main UI loaded successfully.")

        except Exception as e:
            print(f"[Controller] CRITICAL EXCEPTION in main interface: {e}")
            messagebox.showerror("Critical Error", f"Main UI failed: {e}")

    def _build_header(self):
        header = ctk.CTkFrame(self.app)
        header.pack(fill="x", padx=8, pady=8)

        ctk.CTkLabel(
            header,
            text="Basketball Game Scheduler System",
            font=ctk.CTkFont(size=18, weight="bold"),
        ).pack(side="left", padx=(10, 12))

        ctk.CTkButton(
            header, text="Logout", command=self._do_logout, width=100
        ).pack(side="right", padx=8)

    def _do_logout(self):
        if messagebox.askokcancel("Logout", "You are about to log out. Continue?"):
            self.login_ui.show()

    def _build_teams_tab(self):
        tab1 = self.tabview.tab("Teams & Players")
        tab1.grid_columnconfigure(1, weight=1)
        try:
            teams_sidebar = ctk.CTkFrame(tab1, width=260)
            teams_sidebar.grid(row=0, column=0, sticky="ns", padx=8, pady=8)
            ctk.CTkLabel(teams_sidebar, text="Teams", font=ctk.CTkFont(size=16, weight="bold")).pack(pady=(8, 6))

            teams_search_var = ctk.StringVar()
            ctk.CTkEntry(
                teams_sidebar,
                placeholder_text="Search teams or players...",
                textvariable=teams_search_var,
                width=220
            ).pack(pady=(0, 8), padx=6)
            
            teams_sidebar_scroll = ctk.CTkScrollableFrame(teams_sidebar, width=240, height=420)
            teams_sidebar_scroll.pack(padx=6, pady=6)
            teams_buttons = []
            ctk.CTkButton(teams_sidebar, text="+ Add Team", command=file1.open_add_team_popup, width=220).pack(pady=8)

            team_players_area = ctk.CTkFrame(tab1)
            team_players_area.grid(row=0, column=1, sticky="nsew", padx=8, pady=8)

            self.refs['teams_sidebar_scroll'] = teams_sidebar_scroll
            self.refs['team_players_area'] = team_players_area
            self.refs['teams_buttons'] = teams_buttons
            self.refs['teams_search_var'] = teams_search_var

            def on_team_search(*args):
                try:
                    file1.refresh_team_sidebar(
                        teams_sidebar_scroll,
                        team_players_area,
                        teams_buttons,
                        teams_search_var,
                    )
                except Exception as e:
                    print(f"[Controller] refresh_team_sidebar error: {e}")

            teams_search_var.trace("w", on_team_search)

            file1.load_teams_from_db()
            file1.refresh_team_sidebar(teams_sidebar_scroll, team_players_area, teams_buttons)
        except Exception as e:
            print(f"[Controller] Exception in Teams & Players tab: {e}")
            ctk.CTkLabel(tab1, text=f"Error: {e}").pack()

    def _build_venues_tab(self):
        tab2 = self.tabview.tab("Venues")
        tab2.grid_columnconfigure(1, weight=1)
        try:
            venues_sidebar = ctk.CTkFrame(tab2, width=280)
            venues_sidebar.grid(row=0, column=0, sticky="ns", padx=8, pady=8)
            ctk.CTkLabel(venues_sidebar, text="Venues", font=ctk.CTkFont(size=16, weight="bold")).pack(pady=(8, 6))

            venues_search_var = ctk.StringVar()
            ctk.CTkEntry(
                venues_sidebar,
                placeholder_text="Search venues...",
                textvariable=venues_search_var,
                width=220
            ).pack(pady=(0, 8), padx=6)
            
            venues_sidebar_scroll = ctk.CTkScrollableFrame(venues_sidebar, width=260, height=420)
            venues_sidebar_scroll.pack(padx=6, pady=6)
            venues_buttons = []
            ctk.CTkButton(venues_sidebar, text="+ Add Venue", command=file2.open_add_venue_popup, width=220).pack(pady=8)

            venue_details_frame = ctk.CTkFrame(tab2)
            venue_details_frame.grid(row=0, column=1, sticky="nsew", padx=8, pady=8)

            self.refs['venues_sidebar_scroll'] = venues_sidebar_scroll
            self.refs['venues_buttons'] = venues_buttons
            self.refs['venues_search_var'] = venues_search_var
            self.refs['venue_details_frame'] = venue_details_frame

            def on_venue_search(*args):
                try:
                    file2.refresh_venue_sidebar(
                        venues_sidebar_scroll, venues_buttons, venues_search_var
                    )
                except Exception as e:
                    print(f"[Controller] refresh_venue_sidebar error: {e}")

            venues_search_var.trace("w", on_venue_search)

            file2.load_venues_from_db()
            file2.refresh_venue_sidebar(venues_sidebar_scroll, venues_buttons)
        except Exception as e:
            print(f"[Controller] Exception in Venues tab: {e}")
            ctk.CTkLabel(tab2, text=f"Error: {e}").pack()

    def _build_schedule_tab(self):
        tab3 = self.tabview.tab("Schedule Game")
        tab3.grid_columnconfigure(0, weight=1)
        tab3.grid_columnconfigure(1, weight=1)
        try:
            ctk.CTkLabel(tab3, text="Schedule a Game", font=ctk.CTkFont(size=18, weight="bold")).grid(row=0, column=0, padx=8, pady=12, sticky="w")

            schedule_frame = ctk.CTkFrame(tab3)
            schedule_frame.grid(row=1, column=0, sticky="nwe", padx=12, pady=8)
            try:
                file3.build_schedule_left_ui(schedule_frame)
            except Exception as e1:
                print(f"[Controller] Schedule Game panel error: {e1}")
                ctk.CTkLabel(schedule_frame, text=f"Failed to load scheduling UI: {e1}").pack(padx=8, pady=8)

            preview_frame = ctk.CTkFrame(tab3)
            preview_frame.grid(row=1, column=1, sticky="nsew", padx=12, pady=8)
            ctk.CTkLabel(preview_frame, text="Game Preview", font=ctk.CTkFont(size=16, weight="bold")).pack(pady=(10, 6))
            preview_label = ctk.CTkLabel(preview_frame, text="Fill out fields to preview...", justify="left")
            preview_label.pack(padx=12, pady=12, anchor="nw")
            
            self.refs["game_preview_label"] = preview_label
            self.refs["game_preview"] = preview_label
        except Exception as e:
            print(f"[Controller] Exception in Schedule Game tab: {e}")
            ctk.CTkLabel(tab3, text=f"Error: {e}").pack()

    def _build_view_games_tab(self):
        tab4 = self.tabview.tab("View Games")
        tab4.grid_columnconfigure(1, weight=1)
        tab4.grid_rowconfigure(1, weight=1)
        try:
            self.refs["tab4"] = tab4

            ctk.CTkLabel(tab4, text="Scheduled Games", font=ctk.CTkFont(size=18, weight="bold")).grid(row=0, column=0, padx=10, pady=10, sticky="w")
            games_table_scroll = ctk.CTkScrollableFrame(tab4, width=900, height=450)
            games_table_scroll.grid(row=1, column=0, padx=10, pady=10, sticky="nsew")

            game_details_frame = ctk.CTkFrame(tab4)
            game_details_frame.grid(row=1, column=1, padx=10, pady=10, sticky="nsew")

            ctk.CTkLabel(game_details_frame, text="Game Details", font=ctk.CTkFont(size=16, weight="bold")).pack(pady=10)
            self.refs["details_content"] = ctk.CTkLabel(game_details_frame, text="Select a game to view details.", justify="left", anchor="nw")
            self.refs["details_content"].pack(fill="both", expand=True, padx=10, pady=10)
            self.refs['scheduled_games_table'] = games_table_scroll

            ctk.CTkButton(tab4, text="Open Point System", command=self._open_point_system).grid(row=0, column=1, padx=10, pady=10, sticky="e")
            
            file3.load_scheduled_games_from_db()
            file4.refresh_scheduled_games_table(games_table_scroll)
        except Exception as e:
            print(f"[Controller] Exception in View Games tab: {e}")
            ctk.CTkLabel(tab4, text=f"Error: {e}").pack()

    def _build_standings_tab(self):
        tab5 = self.tabview.tab("Standings")
        tab5.grid_columnconfigure(0, weight=1)
        tab5.grid_rowconfigure(1, weight=1)
        try:
            ctk.CTkLabel(tab5, text="Team Standings", font=ctk.CTkFont(size=18, weight="bold")).grid(row=0, column=0, padx=10, pady=10, sticky="w")
            standings_scroll = ctk.CTkScrollableFrame(tab5, width=900, height=450)
            standings_scroll.grid(row=1, column=0, padx=10, pady=10, sticky="nsew")
            
            self.refs["standings_table"] = standings_scroll
            file5.refresh_standings_table(standings_scroll)
        except Exception as e:
            print(f"[Controller] Exception in Standings tab: {e}")
            ctk.CTkLabel(tab5, text=f"Error: {e}").pack()

    def _open_point_system(self):
        selected = self.refs.get("selected_game")
        if not selected:
            messagebox.showwarning("No Game Selected", "Please select a game first.")
            return
        
        game_id = selected.get("id")
        team1_id = selected.get("team1_id")
        team2_id = selected.get("team2_id")
        tab4_ref = self.refs.get('tab4')
        
        if not tab4_ref:
            messagebox.showerror("Error", "Could not find the View Games tab to load the Point System.")
            return
            
        for w in tab4_ref.winfo_children():
            try:
                w.destroy()
            except Exception:
                pass
        
        file6.load_point_system_into_frame(tab4_ref, game_id, team1_id, team2_id)
        self.refs['point_system_active'] = True
        self.refs['point_system_game_id'] = game_id

    def _start_clock(self):
        clock_label = ctk.CTkLabel(self.app, text="", font=ctk.CTkFont(size=14))
        clock_label.place(relx=1.0, rely=1.0, anchor="se", x=-15, y=-10)
        self.refs["clock_label"] = clock_label
        self._update_clock_recursive()

    def _update_clock_recursive(self):
        now = datetime.now().strftime("%Y %b %d   %H:%M:%S")
        if self.refs.get("clock_label"):
            try:
                self.refs["clock_label"].configure(text=now)
            except Exception:
                pass
        self.app.after(1000, self._update_clock_recursive)

if __name__ == "__main__":
    controller = BasketballAppController()
    controller.run()
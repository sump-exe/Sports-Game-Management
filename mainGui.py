import customtkinter as ctk
from tkinter import messagebox
from datetime import datetime
from theDB import *

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("dark-blue")

refs = {}

# Root app
app = ctk.CTk()
app.title("Basketball Game Scheduler System")
app.geometry("1200x700")

sched_mgr = ScheduleManager()

import teamsTab as file1
import venuesTab as file2
import scheduleGameTab as file3
import viewGamesTab as file4
import standingsTab as file5
import pointSystem as file6

for m in (file1, file2, file3, file4, file5):
    setattr(m, 'app', app)
    setattr(m, 'sched_mgr', sched_mgr)
    setattr(m, 'refs', refs)

file3.teams = file1.teams
file3.venues = file2.venues

file4.scheduled_games = file3.scheduled_games
file4.show_game_details = file3.show_game_details

load_teams_from_db = file1.load_teams_from_db
load_venues_from_db = file2.load_venues_from_db
load_scheduled_games_from_db = file3.load_scheduled_games_from_db
refresh_team_sidebar = file1.refresh_team_sidebar
refresh_venue_sidebar = file2.refresh_venue_sidebar
refresh_scheduled_games_table = file4.refresh_scheduled_games_table
update_schedule_optionmenus = file3.update_schedule_optionmenus
refresh_standings_table = file5.refresh_standings_table

file1.load_scheduled_games_from_db = load_scheduled_games_from_db
file1.refresh_scheduled_games_table = refresh_scheduled_games_table
file1.update_schedule_optionmenus = update_schedule_optionmenus

file2.update_schedule_optionmenus = update_schedule_optionmenus

file4.refs = refs
file5.refs = refs

def update_clock():
    now = datetime.now().strftime("%Y %b %d   %H:%M:%S")
    if refs.get("clock_label"):
        refs["clock_label"].configure(text=now)
    app.after(1000, update_clock)

def show_login_screen():
    for w in app.winfo_children():
        w.destroy()

    header = ctk.CTkFrame(app)
    header.pack(fill="x", padx=12, pady=12)
    ctk.CTkLabel(
        header,
        text="Basketball Game Scheduler System",
        font=ctk.CTkFont(size=20, weight="bold")
    ).pack(side="left", padx=(6, 12))

    content = ctk.CTkFrame(app)
    content.pack(expand=True, fill="both", padx=16, pady=20)

    ctk.CTkLabel(content, text="Welcome", font=ctk.CTkFont(size=18)).pack(pady=(30, 5))

    login_frame = ctk.CTkFrame(content)
    login_frame.pack(pady=(5, 0))

    ctk.CTkLabel(login_frame, text="Username:").pack(pady=(14, 4), anchor="w", padx=12)
    user_ent = ctk.CTkEntry(login_frame, width=250)
    user_ent.pack(pady=4, padx=12)
    ctk.CTkLabel(login_frame, text="Password:").pack(pady=(8, 4), anchor="w", padx=12)
    pass_ent = ctk.CTkEntry(login_frame, show="*", width=250)
    pass_ent.pack(pady=4, padx=12)

    def verify():
        if user_ent.get() == "admin" and pass_ent.get() == "123":
            show_main_interface()
        else:
            messagebox.showerror("Login Failed", "Incorrect credentials")

    ctk.CTkButton(login_frame, text="Login", command=verify).pack(pady=12)

def show_main_interface():
    for w in app.winfo_children():
        w.destroy()
    print("[mainGui] Entering main interface")

    try:
        # Header
        header = ctk.CTkFrame(app)
        header.pack(fill="x", padx=8, pady=8)

        ctk.CTkLabel(
            header,
            text="Basketball Game Scheduler System",
            font=ctk.CTkFont(size=18, weight="bold"),
        ).pack(side="left", padx=(10, 12))

        def do_logout():
            if messagebox.askokcancel("Logout", "You are about to log out. Continue?"):
                show_login_screen()

        ctk.CTkButton(
            header, text="Logout", command=do_logout, width=100
        ).pack(side="right", padx=8)

        print("[mainGui] Creating tabview widget...")
        tabview = ctk.CTkTabview(app, width=980, height=520)
        tabview.pack(padx=10, pady=(6, 12), expand=True, fill="both")

        # Always add tabs...
        tabview.add("Teams & Players")
        tabview.add("Venues")
        tabview.add("Schedule Game")
        tabview.add("View Games")
        tabview.add("Standings")
        print("[mainGui] Tab headers created.")

        # populate refs for tab views
        refs['tabview'] = tabview

        # --- Teams & Players ---
        tab1 = tabview.tab("Teams & Players")
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

            refs['teams_sidebar_scroll'] = teams_sidebar_scroll
            refs['team_players_area'] = team_players_area
            refs['teams_buttons'] = teams_buttons
            refs['teams_search_var'] = teams_search_var

            def on_team_search(*args):
                try:
                    refresh_team_sidebar(
                        teams_sidebar_scroll,
                        team_players_area,
                        teams_buttons,
                        teams_search_var,
                    )
                except Exception as e:
                    print(f"[mainGui] refresh_team_sidebar error: {e}")

            teams_search_var.trace("w", on_team_search)
            ctk.CTkEntry(
                teams_sidebar,
                placeholder_text="Search teams or players...",
                textvariable=teams_search_var,
                width=220,
            ).pack(pady=(0, 8), padx=6)

            # Load/populate
            load_teams_from_db()
            refresh_team_sidebar(
                teams_sidebar_scroll, team_players_area, teams_buttons
            )
        except Exception as e:
            print(f"[mainGui] Exception in Teams & Players tab: {e}")
            ctk.CTkLabel(tab1, text=f"Error: {e}").pack()

        # --- Venues ---
        tab2 = tabview.tab("Venues")
        tab2.grid_columnconfigure(1, weight=1)
        try:
            venues_sidebar = ctk.CTkFrame(tab2, width=280)
            venues_sidebar.grid(row=0, column=0, sticky="ns", padx=8, pady=8)
            ctk.CTkLabel(venues_sidebar, text="Venues", font=ctk.CTkFont(size=16, weight="bold")).pack(pady=(8, 6))

            venues_search_var = ctk.StringVar()
            ctk.CTkEntry(
                venues_sidebar,
                placeholder_text="Search venues (name, location, capacity)",
                textvariable=venues_search_var,
                width=220
            ).pack(pady=(0, 8), padx=6)
            venues_sidebar_scroll = ctk.CTkScrollableFrame(venues_sidebar, width=260, height=420)
            venues_sidebar_scroll.pack(padx=6, pady=6)
            venues_buttons = []
            ctk.CTkButton(venues_sidebar, text="+ Add Venue", command=file2.open_add_venue_popup, width=220).pack(pady=8)

            venue_details_frame = ctk.CTkFrame(tab2)
            venue_details_frame.grid(row=0, column=1, sticky="nsew", padx=8, pady=8)

            refs['venues_sidebar_scroll'] = venues_sidebar_scroll
            refs['venues_buttons'] = venues_buttons
            refs['venues_search_var'] = venues_search_var
            refs['venue_details_frame'] = venue_details_frame

            def on_venue_search(*args):
                try:
                    refresh_venue_sidebar(
                        venues_sidebar_scroll, venues_buttons, venues_search_var
                    )
                except Exception as e:
                    print(f"[mainGui] refresh_venue_sidebar error: {e}")

            venues_search_var.trace("w", on_venue_search)
            ctk.CTkEntry(
                venues_sidebar,
                placeholder_text="Search venues (name, location, capacity)",
                textvariable=venues_search_var,
                width=220,
            ).pack(pady=(0, 8), padx=6)

            load_venues_from_db()
            refresh_venue_sidebar(venues_sidebar_scroll, venues_buttons)
        except Exception as e:
            print(f"[mainGui] Exception in Venues tab: {e}")
            ctk.CTkLabel(tab2, text=f"Error: {e}").pack()

        # --- Schedule Game ---
        tab3 = tabview.tab("Schedule Game")
        tab3.grid_columnconfigure(0, weight=1)
        tab3.grid_columnconfigure(1, weight=1)
        try:
            ctk.CTkLabel(tab3, text="Schedule a Game", font=ctk.CTkFont(size=18, weight="bold")).grid(row=0, column=0, padx=8, pady=12, sticky="w")

            schedule_frame = ctk.CTkFrame(tab3)
            schedule_frame.grid(row=1, column=0, sticky="nwe", padx=12, pady=8)
            try:
                file3.build_schedule_left_ui(schedule_frame)
            except Exception as e1:
                print(f"[mainGui] Schedule Game panel error: {e1}")
                ctk.CTkLabel(schedule_frame, text=f"Failed to load scheduling UI: {e1}").pack(padx=8, pady=8)

            preview_frame = ctk.CTkFrame(tab3)
            preview_frame.grid(row=1, column=1, sticky="nsew", padx=12, pady=8)
            ctk.CTkLabel(preview_frame, text="Game Preview", font=ctk.CTkFont(size=16, weight="bold")).pack(pady=(10, 6))
            preview_label = ctk.CTkLabel(preview_frame, text="Fill out fields to preview...", justify="left")
            preview_label.pack(padx=12, pady=12, anchor="nw")
            refs["game_preview_label"] = preview_label
            refs["game_preview"] = preview_label
        except Exception as e:
            print(f"[mainGui] Exception in Schedule Game tab: {e}")
            ctk.CTkLabel(tab3, text=f"Error: {e}").pack()

        # --- View Games ---
        tab4 = tabview.tab("View Games")
        tab4.grid_columnconfigure(1, weight=1)
        tab4.grid_rowconfigure(1, weight=1)
        try:
            refs["tab4"] = tab4

            ctk.CTkLabel(tab4, text="Scheduled Games", font=ctk.CTkFont(size=18, weight="bold")).grid(row=0, column=0, padx=10, pady=10, sticky="w")
            games_table_scroll = ctk.CTkScrollableFrame(tab4, width=900, height=450)
            games_table_scroll.grid(row=1, column=0, padx=10, pady=10, sticky="nsew")

            game_details_frame = ctk.CTkFrame(tab4)
            game_details_frame.grid(row=1, column=1, padx=10, pady=10, sticky="nsew")

            ctk.CTkLabel(game_details_frame, text="Game Details", font=ctk.CTkFont(size=16, weight="bold")).pack(pady=10)
            refs["details_content"] = ctk.CTkLabel(game_details_frame, text="Select a game to view details.", justify="left", anchor="nw")
            refs["details_content"].pack(fill="both", expand=True, padx=10, pady=10)
            refs['scheduled_games_table'] = games_table_scroll

            def open_point_system():
                selected = refs.get("selected_game")
                if not selected:
                    messagebox.showwarning("No Game Selected", "Please select a game first.")
                    return
                game_id = selected.get("id")
                team1_id = selected.get("team1_id")
                team2_id = selected.get("team2_id")
                tab4_ref = refs.get('tab4')
                if not tab4_ref:
                    messagebox.showerror("Error", "Could not find the View Games tab to load the Point System.")
                    return
                for w in tab4_ref.winfo_children():
                    try:
                        w.destroy()
                    except Exception:
                        pass
                file6.load_point_system_into_frame(tab4_ref, game_id, team1_id, team2_id)
                refs['point_system_active'] = True
                refs['point_system_game_id'] = game_id

            ctk.CTkButton(tab4, text="Open Point System", command=open_point_system).grid(row=0, column=1, padx=10, pady=10, sticky="e")
            load_scheduled_games_from_db()
            refresh_scheduled_games_table(games_table_scroll)
        except Exception as e:
            print(f"[mainGui] Exception in View Games tab: {e}")
            ctk.CTkLabel(tab4, text=f"Error: {e}").pack()

        # --- Standings ---
        tab5 = tabview.tab("Standings")
        tab5.grid_columnconfigure(0, weight=1)
        tab5.grid_rowconfigure(1, weight=1)
        try:
            ctk.CTkLabel(tab5, text="Team Standings", font=ctk.CTkFont(size=18, weight="bold")).grid(row=0, column=0, padx=10, pady=10, sticky="w")
            standings_scroll = ctk.CTkScrollableFrame(tab5, width=900, height=450)
            standings_scroll.grid(row=1, column=0, padx=10, pady=10, sticky="nsew")
            refs["standings_table"] = standings_scroll
            file5.refs = refs
            refresh_standings_table(standings_scroll)
        except Exception as e:
            print(f"[mainGui] Exception in Standings tab: {e}")
            ctk.CTkLabel(tab5, text=f"Error: {e}").pack()

        try:
            update_schedule_optionmenus(
                refs.get('tab3_team1_opt'),
                refs.get('tab3_team2_opt'),
                refs.get('tab3_venue_opt'),
            )
        except Exception as e:
            print(f"[mainGui] update_schedule_optionmenus: {e}")

        try:
            refresh_team_sidebar(
                refs.get('teams_sidebar_scroll'), refs.get('team_players_area'),
                refs.get('teams_buttons'))
            refresh_venue_sidebar(
                refs.get('venues_sidebar_scroll'), refs.get('venues_buttons'))
        except Exception as e:
            print(f"[mainGui] sidebar refresh: {e}")

        # Bottom right clock
        clock_label = ctk.CTkLabel(app, text="", font=ctk.CTkFont(size=14))
        clock_label.place(relx=1.0, rely=1.0, anchor="se", x=-15, y=-10)
        refs["clock_label"] = clock_label
        update_clock()

        print("[mainGui] Main UI loaded successfully.")
    except Exception as e:
        print(f"[mainGui] CRITICAL EXCEPTION in main interface: {e}")
        messagebox.showerror("Critical Error", f"Main UI failed: {e}")

show_login_screen()

print("final scheduled_games id in main:", id(file3.scheduled_games))
print("final scheduled_games id in view tab:", id(file4.scheduled_games))
print("final refs id in main:", id(refs))
print("final refs id in view tab:", id(file4.refs))

# force unification again (if needed)
file4.refs = refs
file4.scheduled_games = file3.scheduled_games

app.mainloop()
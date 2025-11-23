import customtkinter as ctk
from tkinter import messagebox
from datetime import datetime
from theDB import *

# Configure appearance
ctk.set_appearance_mode("dark")       # "dark" or "light"
ctk.set_default_color_theme("dark-blue")

# central place to store cross-function widget references (avoids many globals)
refs = {}

# Root app
app = ctk.CTk()
app.title("Game Scheduler System")
app.geometry("1200x700")  # Increased size for better layout

# Database-backed schedule manager
sched_mgr = ScheduleManager()

# Import UI modules AFTER creating app, sched_mgr and refs to avoid circular imports.
# Each module is written so mainGui will set module-level attributes to wire them together.
import teamsTab as file1
import venuesTab as file2
import scheduleGameTab as file3
import viewGamesTab as file4
import standingsTab as file5
import pointSystem as file6

# Wire shared references into modules
for m in (file1, file2, file3, file4, file5):
    setattr(m, 'app', app)
    setattr(m, 'sched_mgr', sched_mgr)
    setattr(m, 'refs', refs)

# Wire cross-module variables/functions
# teams and venues data live in file1 and file2 respectively; make them available to file3
file3.teams = file1.teams
file3.venues = file2.venues

# scheduled_games list is file3's responsibility; make it available to file4
file4.scheduled_games = file3.scheduled_games
file4.show_game_details = file3.show_game_details

# Provide convenience local function references for use in this file's UI code
load_teams_from_db = file1.load_teams_from_db
load_venues_from_db = file2.load_venues_from_db
load_scheduled_games_from_db = file3.load_scheduled_games_from_db
refresh_team_sidebar = file1.refresh_team_sidebar
refresh_venue_sidebar = file2.refresh_venue_sidebar
refresh_scheduled_games_table = file4.refresh_scheduled_games_table
update_schedule_optionmenus = file3.update_schedule_optionmenus
refresh_standings_table = file5.refresh_standings_table

# Also expose some functions into modules that call them
file1.load_scheduled_games_from_db = load_scheduled_games_from_db
file1.refresh_scheduled_games_table = refresh_scheduled_games_table
file1.update_schedule_optionmenus = update_schedule_optionmenus

file2.update_schedule_optionmenus = update_schedule_optionmenus

file4.refs = refs
file5.refs = refs

# --- UI and helpers ---

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
    ctk.CTkLabel(header, text="Game Scheduler System", font=ctk.CTkFont(size=20, weight="bold")).pack(side="left", padx=(6,12))

    content = ctk.CTkFrame(app)
    content.pack(expand=True, fill="both", padx=16, pady=20)

    ctk.CTkLabel(content, text="Welcome to the Game Scheduler", font=ctk.CTkFont(size=18)).pack(pady=(30,5))

    login_frame = ctk.CTkFrame(content)
    login_frame.pack(pady=(5,0))

    ctk.CTkLabel(login_frame, text="Username:").pack(pady=(14,4), anchor="w", padx=12)
    user_ent = ctk.CTkEntry(login_frame, width=250)
    user_ent.pack(pady=4, padx=12)
    ctk.CTkLabel(login_frame, text="Password:").pack(pady=(8,4), anchor="w", padx=12)
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

    # header bar (logout + toggle)
    header = ctk.CTkFrame(app)
    header.pack(fill="x", padx=8, pady=8)

    ctk.CTkLabel(header, text="Game Scheduler System", font=ctk.CTkFont(size=18, weight="bold")).pack(side="left", padx=(10,12))

    def do_logout():
        if messagebox.askokcancel("Logout", "You are about to log out. Continue?"):
            show_login_screen()

    ctk.CTkButton(header, text="Logout", command=do_logout, width=100).pack(side="right", padx=8)

    # main area - Tabview
    tabview = ctk.CTkTabview(app, width=980, height=520)
    tabview.pack(padx=10, pady=(6,12), expand=True, fill="both")
    tabview.add("Teams & Players")
    tabview.add("Venues")
    tabview.add("Schedule Game")
    tabview.add("View Games")
    tabview.add("Standings")

    # Tab 1: Teams & Players
    tab1 = tabview.tab("Teams & Players")
    tab1.grid_columnconfigure(1, weight=1)

    # left sidebar with scroll
    teams_sidebar = ctk.CTkFrame(tab1, width=260)
    teams_sidebar.grid(row=0, column=0, sticky="ns", padx=8, pady=8)
    ctk.CTkLabel(teams_sidebar, text="Teams", font=ctk.CTkFont(size=16, weight="bold")).pack(pady=(8,6))

    # Search bar for teams
    teams_search_var = ctk.StringVar()

    def on_team_search(*args):
        refresh_team_sidebar(
            teams_sidebar_scroll,
            team_players_area,
            teams_buttons,
            teams_search_var
        )

    teams_search_var.trace("w", on_team_search)

    ctk.CTkEntry(
        teams_sidebar,
        placeholder_text="Search teams or players...",
        textvariable=teams_search_var,
        width=220
    ).pack(pady=(0,8), padx=6)

    teams_sidebar_scroll = ctk.CTkScrollableFrame(teams_sidebar, width=240, height=420)
    teams_sidebar_scroll.pack(padx=6, pady=6)
    teams_buttons = []  # store buttons so we can destroy on refresh

    ctk.CTkButton(teams_sidebar, text="+ Add Team", command=file1.open_add_team_popup, width=220).pack(pady=8)

    # right players area
    team_players_area = ctk.CTkFrame(tab1)
    team_players_area.grid(row=0, column=1, sticky="nsew", padx=8, pady=8)

    # load data from DB then refresh
    load_teams_from_db()
    load_venues_from_db()
    load_scheduled_games_from_db()
    refresh_team_sidebar(teams_sidebar_scroll, team_players_area, teams_buttons)

    # Tab 2: Venues
    tab2 = tabview.tab("Venues")
    tab2.grid_columnconfigure(1, weight=1)

    venues_sidebar = ctk.CTkFrame(tab2, width=280)
    venues_sidebar.grid(row=0, column=0, sticky="ns", padx=8, pady=8)
    ctk.CTkLabel(venues_sidebar, text="Venues", font=ctk.CTkFont(size=16, weight="bold")).pack(pady=(8,6))

    # Search bar for venues (search by name, location/address, or capacity)
    venues_search_var = ctk.StringVar()

    def on_venue_search(*args):
        refresh_venue_sidebar(
            venues_sidebar_scroll,
            venues_buttons,
            venues_search_var
        )

    venues_search_var.trace("w", on_venue_search)

    ctk.CTkEntry(
        venues_sidebar,
        placeholder_text="Search venues (name, location, capacity)",
        textvariable=venues_search_var,
        width=220
    ).pack(pady=(0,8), padx=6)

    venues_sidebar_scroll = ctk.CTkScrollableFrame(venues_sidebar, width=260, height=420)
    venues_sidebar_scroll.pack(padx=6, pady=6)
    venues_buttons = []

    ctk.CTkButton(venues_sidebar, text="+ Add Venue", command=file2.open_add_venue_popup, width=220).pack(pady=8)

    # right details panel
    venue_details_frame = ctk.CTkFrame(tab2)
    venue_details_frame.grid(row=0, column=1, sticky="nsew", padx=8, pady=8)

    # expose needed refs for modules
    refs['app'] = app
    refs['teams_sidebar_scroll'] = teams_sidebar_scroll
    refs['team_players_area'] = team_players_area
    refs['teams_buttons'] = teams_buttons
    refs['teams_search_var'] = teams_search_var
    refs['venues_sidebar_scroll'] = venues_sidebar_scroll
    refs['venues_buttons'] = venues_buttons
    refs['venues_search_var'] = venues_search_var
    refs['venue_details_frame'] = venue_details_frame

    # refresh venue sidebar
    refresh_venue_sidebar(venues_sidebar_scroll, venues_buttons)

    # Tab 3: Schedule Game
    tab3 = tabview.tab("Schedule Game")
    tab3.grid_columnconfigure(0, weight=1)
    tab3.grid_columnconfigure(1, weight=1)  # column for preview

    ctk.CTkLabel(tab3, text="Schedule a Game",
                font=ctk.CTkFont(size=18, weight="bold")).grid(
                row=0, column=0, padx=8, pady=12, sticky="w")

    schedule_frame = ctk.CTkFrame(tab3)
    schedule_frame.grid(row=1, column=0, sticky="nwe", padx=12, pady=8)

    # Build the scheduling UI using scheduleGameTab helper (delegated)
    try:
        # build_schedule_left_ui will populate shared refs (tab3_team1_opt, tab3_team2_opt, etc.)
        file3.build_schedule_left_ui(schedule_frame)
    except Exception as e:
        # defensive fallback: show an error so user knows why scheduling UI didn't appear
        ctk.CTkLabel(schedule_frame, text=f"Failed to load scheduling UI: {e}").pack(padx=8, pady=8)

    # PREVIEW PANEL (Right Side)
    preview_frame = ctk.CTkFrame(tab3)
    preview_frame.grid(row=1, column=1, sticky="nsew", padx=12, pady=8)

    ctk.CTkLabel(preview_frame, text="Game Preview",
                font=ctk.CTkFont(size=16, weight="bold")).pack(pady=(10,6))

    preview_label = ctk.CTkLabel(preview_frame, text="Fill out fields to preview...",
                                justify="left")
    preview_label.pack(padx=12, pady=12, anchor="nw")

    # Store refs
    refs["game_preview_label"] = preview_label
    refs["game_preview"] = preview_label

    # Tab 4: View Games
    tab4 = tabview.tab("View Games")
    tab4.grid_columnconfigure(1, weight=1)
    tab4.grid_rowconfigure(1, weight=1)

    # store ref to tab4 so we can replace its contents with file6 UI
    refs['tab4'] = tab4

    ctk.CTkLabel(tab4, text="Scheduled Games", 
                 font=ctk.CTkFont(size=18, weight="bold")).grid(
                     row=0, column=0, padx=10, pady=10, sticky="w"
                 )

    # Scrollable table frame
    games_table_scroll = ctk.CTkScrollableFrame(tab4, width=900, height=450)
    games_table_scroll.grid(row=1, column=0, padx=10, pady=10, sticky="nsew")

    # Right-side game details panel
    game_details_frame = ctk.CTkFrame(tab4)
    game_details_frame.grid(row=1, column=1, padx=10, pady=10, sticky="nsew")

    ctk.CTkLabel(game_details_frame, text="Game Details",
                font=ctk.CTkFont(size=16, weight="bold")).pack(pady=10)

    # Placeholder area
    refs["details_content"] = ctk.CTkLabel(game_details_frame, text="Select a game to view details.",
                                        justify="left", anchor="nw")
    refs["details_content"].pack(fill="both", expand=True, padx=10, pady=10)

    # Store reference so refresh works
    refs['scheduled_games_table'] = games_table_scroll

    # --- Button to open Point System (file6) ---
    def open_point_system():
        selected = refs.get("selected_game")   # file4 must set this
        if not selected:
            messagebox.showwarning("No Game Selected", "Please select a game first.")
            return

        game_id = selected["id"]
        team1_id = selected["team1_id"]
        team2_id = selected["team2_id"]

        # Replace the entire View Games tab contents with file6 UI
        tab4_ref = refs.get('tab4')
        if not tab4_ref:
            messagebox.showerror("Error", "Could not find the View Games tab to load the Point System.")
            return

        # Clear tab contents
        for w in tab4_ref.winfo_children():
            try:
                w.destroy()
            except Exception:
                pass

        # Let file6 build its UI directly inside the tab (it will pack into the parent)
        file6.load_point_system_into_frame(tab4_ref, game_id, team1_id, team2_id)

        # Mark in refs that point system is active so other code can guard if needed
        refs['point_system_active'] = True
        refs['point_system_game_id'] = game_id

    # Button placement bottom-right
    ctk.CTkButton(tab4, text="Open Point System", command=open_point_system).grid(
        row=2, column=1, padx=10, pady=10, sticky="e"
    )

    # Initial load of games (file3.scheduled_games already filled earlier)
    refresh_scheduled_games_table(games_table_scroll)

    # Tab 5: Standings
    tab5 = tabview.tab("Standings")
    tab5.grid_columnconfigure(0, weight=1)
    tab5.grid_rowconfigure(1, weight=1)

    ctk.CTkLabel(tab5, text="Team Standings",
                 font=ctk.CTkFont(size=18, weight="bold")).grid(
                    row=0, column=0, padx=10, pady=10, sticky="w"
                 )

    standings_scroll = ctk.CTkScrollableFrame(tab5, width=900, height=450)
    standings_scroll.grid(row=1, column=0, padx=10, pady=10, sticky="nsew")

    # --- Clock (Bottom-Right) ---
    clock_label = ctk.CTkLabel(app, text="", font=ctk.CTkFont(size=14))
    clock_label.place(relx=1.0, rely=1.0, anchor="se", x=-15, y=-10)

    # Store reference
    refs["standings_table"] = standings_scroll

    # let file5 know where refs are
    file5.refs = refs
    refresh_standings_table(standings_scroll)

    # ensure scheduling options reflect current data (use refs populated by schedule builder)
    try:
        update_schedule_optionmenus(
            refs.get('tab3_team1_opt'),
            refs.get('tab3_team2_opt'),
            refs.get('tab3_venue_opt')
        )
    except Exception:
        pass

    # refresh sidebars again to ensure UI is consistent
    refresh_team_sidebar(teams_sidebar_scroll, team_players_area, teams_buttons)
    refresh_venue_sidebar(venues_sidebar_scroll, venues_buttons)

    refs["clock_label"] = clock_label
    update_clock()   # start updating

show_login_screen()
app.mainloop()
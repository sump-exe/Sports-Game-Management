import customtkinter as ctk
from tkinter import messagebox
from theDB import *

def load_point_system_into_frame(parent, game_id, team1_id, team2_id):
    """Embeds the point system UI into the given parent (suitable for a tab).
    The Back button restores the View Games tab contents inside the same parent
    (does NOT open any new window).
    """

    # Clear parent so we fully replace its content
    for w in parent.winfo_children():
        try:
            w.destroy()
        except Exception:
            pass

    # BACK button (restores the View Games UI into the same parent frame)
    def restore_view_tab():
        # Clear parent first
        for w in parent.winfo_children():
            try:
                w.destroy()
            except Exception:
                pass

        # Recreate the View Games layout exactly like mainGui does (minimal version needed
        # for viewGamesTab.refresh_scheduled_games_table to work)
        try:
            # Build left (games table) and right (details) areas using grid as in mainGui
            parent.grid_columnconfigure(0, weight=1)
            parent.grid_columnconfigure(1, weight=1)
            parent.grid_rowconfigure(1, weight=1)
        except Exception:
            pass

        ctk.CTkLabel(parent, text="Scheduled Games",
                     font=ctk.CTkFont(size=18, weight="bold")).grid(
            row=0, column=0, padx=10, pady=10, sticky="w"
        )

        # Scrollable table frame (left)
        games_table_scroll = ctk.CTkScrollableFrame(parent, width=900, height=450)
        games_table_scroll.grid(row=1, column=0, padx=10, pady=10, sticky="nsew")

        # Right-side game details panel
        game_details_frame = ctk.CTkFrame(parent)
        game_details_frame.grid(row=1, column=1, padx=10, pady=10, sticky="nsew")

        ctk.CTkLabel(game_details_frame, text="Game Details",
                     font=ctk.CTkFont(size=16, weight="bold")).pack(pady=10)

        # Placeholder area
        details_label = ctk.CTkLabel(game_details_frame, text="Select a game to view details.",
                                     justify="left", anchor="nw")
        details_label.pack(fill="both", expand=True, padx=10, pady=10)

        # Update shared refs used by viewGamesTab and other modules
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

        # Populate the games table using viewGamesTab's function if available
        if vgt and hasattr(vgt, 'refresh_scheduled_games_table'):
            try:
                vgt.refresh_scheduled_games_table(games_table_scroll)
            except Exception:
                ctk.CTkLabel(games_table_scroll, text="Unable to load scheduled games.").pack(padx=8, pady=8)
        else:
            ctk.CTkLabel(games_table_scroll, text="Scheduled games unavailable.").pack(padx=8, pady=8)

        # Re-add the Open Point System button on the bottom-right (same behaviour as mainGui)
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

        # Clear any point-system-active flags in shared refs if present (use viewGamesTab.refs)
        try:
            if vgt and hasattr(vgt, 'refs') and isinstance(vgt.refs, dict):
                vgt.refs.pop('point_system_active', None)
                vgt.refs.pop('point_system_game_id', None)
        except Exception:
            pass

    # Place Back button at top-left (keeps everything in same tab/frame)
    back_btn = ctk.CTkButton(parent, text="← Back to Games", width=150, command=restore_view_tab)
    back_btn.pack(padx=12, pady=(10, 6), anchor="w")

    # Title
    title = ctk.CTkLabel(parent, text=f"Point System — Game #{game_id}",
                         font=ctk.CTkFont(size=20, weight="bold"))
    title.pack(pady=(6, 6))

    # Use left and right frames that expand to fill the tab area
    container = ctk.CTkFrame(parent)
    container.pack(fill="both", expand=True, padx=10, pady=10)

    # Make two equal columns
    left = ctk.CTkScrollableFrame(container)
    left.pack(side="left", fill="both", expand=True, padx=(0, 6), pady=0)

    right = ctk.CTkScrollableFrame(container)
    right.pack(side="right", fill="both", expand=True, padx=(6, 0), pady=0)

    # Load teams
    team1_name, team1_roster = load_team(team1_id)
    team2_name, team2_roster = load_team(team2_id)

    # LEFT TEAM
    ctk.CTkLabel(left, text=team1_name,
                 font=ctk.CTkFont(size=18, weight="bold")).grid(row=0, column=0, padx=8, pady=6, sticky="w")

    row = 1
    if team1_roster:
        for p in team1_roster:
            txt = f"#{p['jerseyNumber'] or ''}  {p['name']} | Points: {p['points']}"
            ctk.CTkLabel(left, text=txt, anchor="w").grid(row=row, column=0, padx=8, pady=4, sticky="w")
            row += 1
    else:
        ctk.CTkLabel(left, text="No players", anchor="w").grid(row=1, column=0, padx=8, pady=4, sticky="w")

    # RIGHT TEAM
    ctk.CTkLabel(right, text=team2_name,
                 font=ctk.CTkFont(size=18, weight="bold")).grid(row=0, column=0, padx=8, pady=6, sticky="w")

    row = 1
    if team2_roster:
        for p in team2_roster:
            txt = f"#{p['jerseyNumber'] or ''}  {p['name']} | Points: {p['points']}"
            ctk.CTkLabel(right, text=txt, anchor="w").grid(row=row, column=0, padx=8, pady=4, sticky="w")
            row += 1
    else:
        ctk.CTkLabel(right, text="No players", anchor="w").grid(row=1, column=0, padx=8, pady=4, sticky="w")

    # Mark in shared refs that point system is active (use viewGamesTab.refs if available)
    try:
        import viewGamesTab as vgt_mod
        if hasattr(vgt_mod, 'refs') and isinstance(vgt_mod.refs, dict):
            vgt_mod.refs['point_system_active'] = True
            vgt_mod.refs['point_system_game_id'] = game_id
    except Exception:
        # If viewGamesTab not importable, ignore.
        pass


def load_team(team_id):
    cursor = mydb.cursor()
    cursor.execute("SELECT teamName FROM teams WHERE id = ?", (team_id,))
    row = cursor.fetchone()
    if not row:
        cursor.close()
        return "Unknown Team", []

    team_name = row["teamName"]

    cursor.execute("""
        SELECT name, jerseyNumber, points 
        FROM players 
        WHERE team_id = ?
        ORDER BY jerseyNumber
    """, (team_id,))
    players = cursor.fetchall()
    cursor.close()

    # Convert sqlite3.Row objects to simple dicts for predictable access
    player_list = []
    for r in players:
        player_list.append({
            'name': r['name'],
            'jerseyNumber': r['jerseyNumber'],
            'points': r['points']
        })

    return team_name, player_list


# ============================================================
#      BACKWARD-COMPATIBILITY: Toplevel window
# ============================================================
def open_point_system_window(game_id, team1_id, team2_id):
    # Keep a Toplevel helper for other code paths; re-use the embedding function inside it.
    win = ctk.CTkToplevel()
    win.title(f"Point System — Game #{game_id}")
    win.geometry("1200x700")
    load_point_system_into_frame(win, game_id, team1_id, team2_id)
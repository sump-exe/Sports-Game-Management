import customtkinter as ctk
from theDB import *

def load_point_system_into_frame(parent, game_id, team1_id, team2_id):
    """Embeds the point system UI into the given parent (suitable for a tab)."""

    # Clear parent so we fully replace its content
    for w in parent.winfo_children():
        try:
            w.destroy()
        except Exception:
            pass

    # Title
    title = ctk.CTkLabel(parent, text=f"Point System — Game #{game_id}",
                         font=ctk.CTkFont(size=20, weight="bold"))
    title.pack(pady=(10, 6))

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
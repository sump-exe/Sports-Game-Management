import customtkinter as ctk
from tkinter import messagebox
from datetime import datetime
from theDB import *

# This module provides standings UI helper. mainGui will set refs when wiring.
refs = {}

standings = {}   # { "TeamName": {"mvp": "PlayerName", "wins": int} }

def refresh_standings_table(table_frame):
    # Clear old rows
    for w in table_frame.winfo_children():
        w.destroy()

    # Header
    header = ctk.CTkFrame(table_frame, fg_color="#1F1F1F")
    header.pack(fill="x", padx=8, pady=4)
    header.grid_columnconfigure(0, weight=1)
    header.grid_columnconfigure(1, weight=1)
    header.grid_columnconfigure(2, weight=1)

    ctk.CTkLabel(header, text="Rank", font=ctk.CTkFont(size=14, weight="bold")).grid(row=0, column=0, padx=8, pady=4, sticky="w")
    ctk.CTkLabel(header, text="Team", font=ctk.CTkFont(size=14, weight="bold")).grid(row=0, column=1, padx=8, pady=4, sticky="w")
    ctk.CTkLabel(header, text="Wins", font=ctk.CTkFont(size=14, weight="bold")).grid(row=0, column=2, padx=8, pady=4, sticky="w")

    # Sort teams by wins descending
    sorted_standings = sorted(standings.items(), key=lambda x: x[1].get("wins", 0), reverse=True)

    for i, (team, data) in enumerate(sorted_standings, start=1):
        row = ctk.CTkFrame(table_frame, fg_color="#2A2A2A")
        row.pack(fill="x", padx=8, pady=2)
        row.grid_columnconfigure(0, weight=1)
        row.grid_columnconfigure(1, weight=1)
        row.grid_columnconfigure(2, weight=1)

        ctk.CTkLabel(row, text=str(i)).grid(row=0, column=0, padx=8, pady=4, sticky="w")
        ctk.CTkLabel(row, text=team).grid(row=0, column=1, padx=8, pady=4, sticky="w")
        ctk.CTkLabel(row, text=str(data.get("wins", 0))).grid(row=0, column=2, padx=8, pady=4, sticky="w")


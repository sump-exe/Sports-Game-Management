import sqlite3
from pathlib import Path

# Use a local sqlite file for portability
DB_FILE = Path(__file__).with_name('sports_schedule.db')

# Connect and ensure foreign keys enabled
mydb = sqlite3.connect(str(DB_FILE))
mydb.row_factory = sqlite3.Row
cur = mydb.cursor()
cur.execute("PRAGMA foreign_keys = ON")

# Create tables (SQLite types and AUTOINCREMENT)
cur.execute("""
CREATE TABLE IF NOT EXISTS teams (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    teamName TEXT NOT NULL UNIQUE,
    totalPoints INTEGER DEFAULT 0
)
""")
cur.execute("""
CREATE TABLE IF NOT EXISTS players (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    jerseyNumber INTEGER NOT NULL,
    points INTEGER DEFAULT 0,
    team_id INTEGER,
    FOREIGN KEY (team_id) REFERENCES teams(id) ON DELETE CASCADE
)
""")
# Ensure jerseyNumber can be NULL going forward. If the column is declared NOT NULL,
# migrate the table so jerseyNumber becomes nullable (preserving existing data).
cur_m = mydb.cursor()
cols_info = cur_m.execute("PRAGMA table_info(players)").fetchall()
jersey_col = None
for c in cols_info:
    # PRAGMA table_info returns: cid, name, type, notnull, dflt_value, pk
    if c[1] == 'jerseyNumber':
        jersey_col = c
        break
if jersey_col and jersey_col[3] == 1:
    # Perform migration: create new table with jerseyNumber nullable, copy data
    cur_m.execute("""
    CREATE TABLE IF NOT EXISTS players_new (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        jerseyNumber INTEGER,
        points INTEGER DEFAULT 0,
        team_id INTEGER,
        FOREIGN KEY (team_id) REFERENCES teams(id) ON DELETE CASCADE
    )
    """)
    # Copy data, convert 0 -> NULL for jerseyNumber (assumes 0 was previously used as placeholder)
    cur_m.execute("INSERT INTO players_new (id, name, jerseyNumber, points, team_id) SELECT id, name, NULLIF(jerseyNumber, 0), points, team_id FROM players")
    cur_m.execute("DROP TABLE players")
    cur_m.execute("ALTER TABLE players_new RENAME TO players")
    mydb.commit()
cur_m.close()
cur.execute("""
CREATE TABLE IF NOT EXISTS venues (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    venueName TEXT NOT NULL UNIQUE,
    location TEXT NOT NULL,
    capacity INTEGER NOT NULL
)
""")
cur.execute("""
CREATE TABLE IF NOT EXISTS games (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    home_team_id INTEGER,
    away_team_id INTEGER,
    venue_id INTEGER,
    game_date TEXT,
    home_score INTEGER DEFAULT 0,
    away_score INTEGER DEFAULT 0,
    FOREIGN KEY (home_team_id) REFERENCES teams(id),
    FOREIGN KEY (away_team_id) REFERENCES teams(id),
    FOREIGN KEY (venue_id) REFERENCES venues(id)
)
""")
# Ensure start_time and end_time columns exist (added later as TEXT)
cur2 = mydb.cursor()
cols = [r[1] for r in cur2.execute("PRAGMA table_info(games)").fetchall()]
if 'start_time' not in cols:
    cur2.execute("ALTER TABLE games ADD COLUMN start_time TEXT DEFAULT '00:00'")
if 'end_time' not in cols:
    cur2.execute("ALTER TABLE games ADD COLUMN end_time TEXT DEFAULT '00:00'")
cur2.close()
cur.execute("""
CREATE TABLE IF NOT EXISTS mvps (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    player_id INTEGER NOT NULL,
    team_id INTEGER NOT NULL,
    year INTEGER NOT NULL,
    FOREIGN KEY (player_id) REFERENCES players(id) ON DELETE CASCADE,
    FOREIGN KEY (team_id) REFERENCES teams(id) ON DELETE CASCADE,
    UNIQUE(player_id, year)  -- ensure a player is MVP only once per year
)
""")

mydb.commit()
cur.close()

class ScheduleManager:
    def __init__(self):
        self.mydb = mydb  # Use the global connection
        # No need for in-memory lists/dicts; data will be queried from DB as needed
    def addTeam(self, team):
        if isinstance(team, Team):
            cursor = self.mydb.cursor()
            cursor.execute("INSERT INTO teams (teamName, totalPoints) VALUES (?, ?)", (team.teamName, team.totalPoints))
            self.mydb.commit()
            team.id = cursor.lastrowid
            cursor.close()
    def addVenue(self, venue):
        if isinstance(venue, Venue):
            cursor = self.mydb.cursor()
            cursor.execute("INSERT INTO venues (venueName, location, capacity) VALUES (?, ?, ?)", (venue.venueName, venue.location, venue.capacity))
            self.mydb.commit()
            venue.venueID = cursor.lastrowid
            cursor.close()
    def displaySchedule(self):
        cursor = self.mydb.cursor()
        cursor.execute("""
        SELECT g.id, t1.teamName AS home_team, t2.teamName AS away_team, v.venueName, g.game_date, g.home_score, g.away_score
        FROM games g
        JOIN teams t1 ON g.home_team_id = t1.id
        JOIN teams t2 ON g.away_team_id = t2.id
        JOIN venues v ON g.venue_id = v.id
        ORDER BY g.game_date
        """)
        results = cursor.fetchall()
        cursor.close()
        print("Schedule:")
        for row in results:
            print(f"Game ID: {row[0]}, {row[1]} vs {row[2]} at {row[3]} on {row[4]}, Score: {row[5]}-{row[6]}")
    def displayStandings(self):
        cursor = self.mydb.cursor()
        cursor.execute("""
        SELECT t.teamName, 
               SUM(CASE WHEN g.home_team_id = t.id AND g.home_score > g.away_score THEN 1 
                        WHEN g.away_team_id = t.id AND g.away_score > g.home_score THEN 1 ELSE 0 END) AS wins,
               SUM(CASE WHEN g.home_team_id = t.id AND g.home_score < g.away_score THEN 1 
                        WHEN g.away_team_id = t.id AND g.away_score < g.home_score THEN 1 ELSE 0 END) AS losses,
               t.totalPoints
        FROM teams t
        LEFT JOIN games g ON t.id = g.home_team_id OR t.id = g.away_team_id
        GROUP BY t.id, t.teamName, t.totalPoints
        ORDER BY wins DESC, totalPoints DESC
        """)
        results = cursor.fetchall()
        cursor.close()
        print("Standings:")
        for row in results:
            print(f"Team: {row[0]}, Wins: {row[1]}, Losses: {row[2]}, Total Points: {row[3]}")
    def gameResults(self, gameID):
        cursor = self.mydb.cursor()
        cursor.execute("""
        SELECT g.id, t1.teamName AS home_team, t2.teamName AS away_team, v.venueName, g.game_date, g.home_score, g.away_score
        FROM games g
        JOIN teams t1 ON g.home_team_id = t1.id
        JOIN teams t2 ON g.away_team_id = t2.id
        JOIN venues v ON g.venue_id = v.id
        WHERE g.id = ?
        """, (gameID,))
        result = cursor.fetchone()
        cursor.close()
        if result:
            return {
                'gameID': result[0],
                'home_team': result[1],
                'away_team': result[2],
                'venue': result[3],
                'date': result[4],
                'score': f"{result[5]}-{result[6]}"
            }
        return None
    def scheduleGame(self, home_team_id, away_team_id, venue_id, game_date):
        cursor = self.mydb.cursor()
        # Insert with optional start/end fields (use defaults if missing)
        cursor.execute("INSERT INTO games (home_team_id, away_team_id, venue_id, game_date, start_time, end_time) VALUES (?, ?, ?, ?, ?, ?)", 
                       (home_team_id, away_team_id, venue_id, game_date, '00:00', '00:00'))
        self.mydb.commit()
        game_id = cursor.lastrowid
        cursor.close()
        return game_id

    def updateGame(self, game_id, home_team_id, away_team_id, venue_id, game_date, start_time='00:00', end_time='00:00'):
        cursor = self.mydb.cursor()
        cursor.execute("""
            UPDATE games SET home_team_id = ?, away_team_id = ?, venue_id = ?, game_date = ?, start_time = ?, end_time = ?
            WHERE id = ?
        """, (home_team_id, away_team_id, venue_id, game_date, start_time, end_time, game_id))
        self.mydb.commit()
        cursor.close()

    def deleteGame(self, game_id):
        cursor = self.mydb.cursor()
        cursor.execute("DELETE FROM games WHERE id = ?", (game_id,))
        self.mydb.commit()
        cursor.close()

class Venue:
    def __init__(self, venueName, location, capacity, venueID=None):
        self.venueName = venueName
        self.location = location
        self.capacity = capacity
        self.venueID = venueID  # Will be set when added to DB
    def checkAvailability(self, date):
        # Check if venue is booked on a given date
        cursor = mydb.cursor()
        cursor.execute("SELECT COUNT(*) FROM games WHERE venue_id = ? AND game_date = ?", (self.venueID, date))
        count = cursor.fetchone()[0]
        cursor.close()
        return count == 0  # True if available

class Team:
    def __init__(self, teamName, teamID=None):
        self.teamName = teamName
        self.id = teamID
        self.totalPoints = 0  # Initialize to 0
    def addPlayer(self, player):
        if isinstance(player, Player):
            cursor = mydb.cursor()
            cursor.execute("INSERT INTO players (name, jerseyNumber, points, team_id) VALUES (?, ?, ?, ?)", 
                           (player.name, player.jerseyNumber, player.points, self.id))
            mydb.commit()
            player.id = cursor.lastrowid
            cursor.close()
            self.calcTotalPoints()
    def calcTotalPoints(self):
        cursor = mydb.cursor()
        cursor.execute("SELECT SUM(points) FROM players WHERE team_id = ?", (self.id,))
        result = cursor.fetchone()
        self.totalPoints = result[0] if result[0] else 0
        cursor.execute("UPDATE teams SET totalPoints = ? WHERE id = ?", (self.totalPoints, self.id))
        mydb.commit()
        cursor.close()
    def getRoster(self):
        cursor = mydb.cursor()
        cursor.execute("SELECT name, jerseyNumber, points FROM players WHERE team_id = ?", (self.id,))
        results = cursor.fetchall()
        cursor.close()
        roster = []
        for row in results:
            roster.append({'name': row[0], 'jerseyNumber': row[1], 'points': row[2]})
        return roster
    def getRecord(self):
        cursor = mydb.cursor()
        cursor.execute("""
        SELECT 
            SUM(CASE WHEN home_team_id = ? AND home_score > away_score THEN 1 
                     WHEN away_team_id = ? AND away_score > home_score THEN 1 ELSE 0 END) AS wins,
            SUM(CASE WHEN home_team_id = ? AND home_score < away_score THEN 1 
                     WHEN away_team_id = ? AND away_score < home_score THEN 1 ELSE 0 END) AS losses
        FROM games
        WHERE home_team_id = ? OR away_team_id = ?
        """, (self.id, self.id, self.id, self.id, self.id, self.id))
        result = cursor.fetchone()
        cursor.close()
        wins = result[0] if result[0] else 0
        losses = result[1] if result[1] else 0
        return {'wins': wins, 'losses': losses}

class Player:
    def __init__(self, name, jerseyNumber, playerID=None):
        self.name = name
        self.jerseyNumber = jerseyNumber
        self.points = 0  # Initialize to 0
        self.id = playerID
    def addPoints(self, p):
        self.points += p
        cursor = mydb.cursor()
        cursor.execute("UPDATE players SET points = ? WHERE id = ?", (self.points, self.id))
        mydb.commit()
        cursor.close()
        # Note: After updating points, the team's totalPoints should be recalculated, but that's handled in Team.calcTotalPoints

class MVP(Player):
    def __init__(self, name, jerseyNumber, year, playerID):
        super().__init__(name, jerseyNumber, playerID)
        self.year = year
    def addMVP(self, mvp, year):
        if isinstance(mvp, Player):
            cursor = self.mydb.cursor()
            cursor.execute("INSERT INTO mvps (player_id, team_id, year) VALUES (?, ?, ?)", (mvp.name, mvp.jerseyNumber, year))
            self.mydb.commit()
            cursor.close()
        else:
            pass # Handle error appropriately, object is not a Player
    def getMVPsByYear(self, year):
        cursor = self.mydb.cursor()
        cursor.execute("""
        SELECT p.name AS player_name, t.teamName, m.year
        FROM mvps m
        JOIN players p ON m.player_id = p.id
        JOIN teams t ON m.team_id = t.id
        WHERE m.year = ?
        """, (year,))
        results = cursor.fetchall()
        cursor.close()
        return results

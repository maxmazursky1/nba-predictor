"""SQLite helpers for storing game logs, predictions, and results."""

import sqlite3
from config import DB_PATH


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    """Create all tables if they don't exist."""
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS game_logs (
            game_id TEXT NOT NULL,
            game_date TEXT NOT NULL,
            season TEXT NOT NULL,
            team_id INTEGER NOT NULL,
            team_abbr TEXT NOT NULL,
            matchup TEXT NOT NULL,
            is_home INTEGER NOT NULL,
            wl TEXT NOT NULL,
            pts INTEGER NOT NULL,
            fgm INTEGER, fga INTEGER, fg_pct REAL,
            fg3m INTEGER, fg3a INTEGER, fg3_pct REAL,
            ftm INTEGER, fta INTEGER, ft_pct REAL,
            oreb INTEGER, dreb INTEGER, reb INTEGER,
            ast INTEGER, stl INTEGER, blk INTEGER, tov INTEGER,
            plus_minus REAL,
            PRIMARY KEY (game_id, team_id)
        );

        CREATE INDEX IF NOT EXISTS idx_game_logs_team_date
            ON game_logs(team_id, game_date);

        CREATE INDEX IF NOT EXISTS idx_game_logs_season
            ON game_logs(season);

        CREATE TABLE IF NOT EXISTS predictions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            game_id TEXT NOT NULL,
            game_date TEXT NOT NULL,
            home_team_id INTEGER NOT NULL,
            away_team_id INTEGER NOT NULL,
            home_team_abbr TEXT NOT NULL,
            away_team_abbr TEXT NOT NULL,
            pred_home_win_prob REAL,
            pred_spread REAL,
            pred_total REAL,
            vegas_spread REAL,
            vegas_total REAL,
            vegas_home_ml INTEGER,
            vegas_away_ml INTEGER,
            home_injuries TEXT,
            away_injuries TEXT,
            home_elo REAL,
            away_elo REAL,
            created_at TEXT DEFAULT (datetime('now')),
            UNIQUE(game_id)
        );

        CREATE TABLE IF NOT EXISTS results (
            game_id TEXT PRIMARY KEY,
            game_date TEXT NOT NULL,
            home_team_id INTEGER NOT NULL,
            away_team_id INTEGER NOT NULL,
            home_pts INTEGER NOT NULL,
            away_pts INTEGER NOT NULL,
            home_win INTEGER NOT NULL
        );
    """)
    conn.commit()
    conn.close()


def insert_game_logs(rows):
    """Insert game log rows (list of dicts). Skips duplicates."""
    conn = get_db()
    conn.executemany("""
        INSERT OR IGNORE INTO game_logs (
            game_id, game_date, season, team_id, team_abbr, matchup, is_home,
            wl, pts, fgm, fga, fg_pct, fg3m, fg3a, fg3_pct,
            ftm, fta, ft_pct, oreb, dreb, reb, ast, stl, blk, tov, plus_minus
        ) VALUES (
            :game_id, :game_date, :season, :team_id, :team_abbr, :matchup, :is_home,
            :wl, :pts, :fgm, :fga, :fg_pct, :fg3m, :fg3a, :fg3_pct,
            :ftm, :fta, :ft_pct, :oreb, :dreb, :reb, :ast, :stl, :blk, :tov, :plus_minus
        )
    """, rows)
    conn.commit()
    conn.close()


def get_team_game_logs(team_id, before_date=None):
    """Get all game logs for a team, optionally before a date."""
    conn = get_db()
    if before_date:
        rows = conn.execute(
            "SELECT * FROM game_logs WHERE team_id = ? AND game_date < ? ORDER BY game_date",
            (team_id, before_date)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM game_logs WHERE team_id = ? ORDER BY game_date",
            (team_id,)
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_all_game_logs(season=None):
    """Get all game logs, optionally filtered by season."""
    conn = get_db()
    if season:
        rows = conn.execute(
            "SELECT * FROM game_logs WHERE season = ? ORDER BY game_date",
            (season,)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM game_logs ORDER BY game_date"
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_games_on_date(date_str):
    """Get all game log entries for a specific date. Returns pairs (home, away) by game_id."""
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM game_logs WHERE game_date = ? ORDER BY game_id, is_home DESC",
        (date_str,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def insert_prediction(pred):
    """Insert or replace a prediction."""
    conn = get_db()
    conn.execute("""
        INSERT OR REPLACE INTO predictions (
            game_id, game_date, home_team_id, away_team_id,
            home_team_abbr, away_team_abbr,
            pred_home_win_prob, pred_spread, pred_total,
            vegas_spread, vegas_total, vegas_home_ml, vegas_away_ml,
            home_injuries, away_injuries, home_elo, away_elo
        ) VALUES (
            :game_id, :game_date, :home_team_id, :away_team_id,
            :home_team_abbr, :away_team_abbr,
            :pred_home_win_prob, :pred_spread, :pred_total,
            :vegas_spread, :vegas_total, :vegas_home_ml, :vegas_away_ml,
            :home_injuries, :away_injuries, :home_elo, :away_elo
        )
    """, pred)
    conn.commit()
    conn.close()


def insert_result(result):
    """Insert or replace a game result."""
    conn = get_db()
    conn.execute("""
        INSERT OR REPLACE INTO results (
            game_id, game_date, home_team_id, away_team_id,
            home_pts, away_pts, home_win
        ) VALUES (
            :game_id, :game_date, :home_team_id, :away_team_id,
            :home_pts, :away_pts, :home_win
        )
    """, result)
    conn.commit()
    conn.close()


def get_predictions(date_str=None):
    """Get predictions, optionally for a specific date."""
    conn = get_db()
    if date_str:
        rows = conn.execute(
            "SELECT * FROM predictions WHERE game_date = ? ORDER BY game_id",
            (date_str,)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM predictions ORDER BY game_date DESC, game_id"
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_predictions_with_results():
    """Join predictions with results for performance tracking."""
    conn = get_db()
    rows = conn.execute("""
        SELECT p.*, r.home_pts, r.away_pts, r.home_win as actual_home_win
        FROM predictions p
        INNER JOIN results r ON p.game_id = r.game_id
        ORDER BY p.game_date
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def game_log_count():
    """Return total number of game log entries."""
    conn = get_db()
    row = conn.execute("SELECT COUNT(*) as cnt FROM game_logs").fetchone()
    conn.close()
    return row["cnt"]

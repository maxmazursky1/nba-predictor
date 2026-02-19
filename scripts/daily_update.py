#!/usr/bin/env python3
"""Daily cron script: score yesterday's games, update Elo, generate today's predictions."""

import sys
import os
import time
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import API_DELAY
from src.db import init_db, insert_game_logs, insert_result, get_db
from src.data_fetcher import fetch_season_game_logs
from src.predictor import predict_today


def score_yesterday():
    """Fetch yesterday's results and store them."""
    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    print(f"Scoring yesterday's games ({yesterday})...")

    conn = get_db()
    # Find games we predicted but haven't scored yet
    unscored = conn.execute("""
        SELECT p.game_id, p.home_team_id, p.away_team_id
        FROM predictions p
        LEFT JOIN results r ON p.game_id = r.game_id
        WHERE r.game_id IS NULL AND p.game_date <= ?
    """, (yesterday,)).fetchall()
    conn.close()

    if not unscored:
        print("  No unscored predictions found.")
        return

    # Refresh game logs for current season to get final scores
    current_season = _current_season()
    rows = fetch_season_game_logs(current_season)
    insert_game_logs(rows)
    print(f"  Updated {len(rows)} game log entries for {current_season}")

    # Now match results
    conn = get_db()
    scored = 0
    for pred in unscored:
        game_id = pred["game_id"]
        home_row = conn.execute(
            "SELECT pts FROM game_logs WHERE game_id = ? AND team_id = ?",
            (game_id, pred["home_team_id"])
        ).fetchone()
        away_row = conn.execute(
            "SELECT pts FROM game_logs WHERE game_id = ? AND team_id = ?",
            (game_id, pred["away_team_id"])
        ).fetchone()

        if home_row and away_row:
            home_pts = home_row["pts"]
            away_pts = away_row["pts"]
            insert_result({
                "game_id": game_id,
                "game_date": yesterday,
                "home_team_id": pred["home_team_id"],
                "away_team_id": pred["away_team_id"],
                "home_pts": home_pts,
                "away_pts": away_pts,
                "home_win": 1 if home_pts > away_pts else 0,
            })
            scored += 1
    conn.close()
    print(f"  Scored {scored} games.")


def _current_season():
    now = datetime.now()
    year = now.year
    # NBA season spans Oct-Jun. If before October, use previous year's season.
    if now.month < 10:
        return f"{year - 1}-{str(year)[2:]}"
    return f"{year}-{str(year + 1)[2:]}"


def main():
    init_db()
    score_yesterday()
    print()
    predictions = predict_today()
    print(f"\nGenerated {len(predictions)} predictions.")


if __name__ == "__main__":
    main()

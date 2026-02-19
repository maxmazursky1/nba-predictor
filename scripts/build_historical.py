#!/usr/bin/env python3
"""One-time script: fetch all historical game data and store in SQLite."""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import TRAINING_SEASONS
from src.db import init_db, insert_game_logs, game_log_count
from src.data_fetcher import fetch_season_game_logs

def main():
    init_db()
    print(f"Database initialized. Current rows: {game_log_count()}")

    for season in TRAINING_SEASONS:
        rows = fetch_season_game_logs(season)
        insert_game_logs(rows)
        print(f"    {season}: {len(rows)} game-team entries inserted")

    total = game_log_count()
    print(f"\nDone! Total game log entries: {total}")
    print(f"Approximate games: {total // 2}")


if __name__ == "__main__":
    main()

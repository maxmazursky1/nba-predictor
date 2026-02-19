"""Project-wide constants and paths."""

import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
DB_PATH = os.path.join(DATA_DIR, "nba.db")
MODELS_DIR = os.path.join(DATA_DIR, "models")
ELO_PATH = os.path.join(DATA_DIR, "elo_ratings.json")
STAR_PLAYERS_PATH = os.path.join(DATA_DIR, "star_players.json")

# Seasons to use for training (season string format for nba_api)
TRAINING_SEASONS = [
    "2018-19", "2019-20", "2020-21", "2021-22",
    "2022-23", "2023-24", "2024-25",
]

# Feature engineering
ROLLING_WINDOW = 10

# Elo parameters
ELO_INITIAL = 1500
ELO_K = 20
ELO_HOME_ADVANTAGE = 100
ELO_SEASON_REVERT = 0.75  # carry 75% of end-of-season Elo, revert 25% to mean

# nba_api rate limiting
API_DELAY = 0.6

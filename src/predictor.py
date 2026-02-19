"""Orchestrator: fetch today's schedule, build features, run predictions."""

import time
from datetime import datetime, timedelta

import pandas as pd
import numpy as np

from config import ROLLING_WINDOW
from src.db import (
    get_db, get_predictions, insert_prediction, get_team_game_logs,
    insert_result, get_all_game_logs,
)
from src.data_fetcher import fetch_todays_scoreboard, fetch_season_game_logs, NBA_TEAMS
from src.elo import EloSystem
from src.model import load_models, predict_game
from src.odds_fetcher import fetch_nba_odds


def _compute_team_rolling(team_id, before_date):
    """Compute rolling features for a team using games before a given date."""
    logs = get_team_game_logs(team_id, before_date=before_date)
    if len(logs) < 3:
        return None

    df = pd.DataFrame(logs)
    df["game_date"] = pd.to_datetime(df["game_date"])
    df = df.sort_values("game_date")

    df["pts_allowed"] = df["pts"] - df["plus_minus"]
    df["poss"] = df["fga"] - df["oreb"] + df["tov"] + 0.44 * df["fta"]
    df["off_rating"] = np.where(df["poss"] > 0, df["pts"] / df["poss"] * 100, 100.0)
    df["def_rating"] = np.where(df["poss"] > 0, df["pts_allowed"] / df["poss"] * 100, 100.0)
    df["net_rating"] = df["off_rating"] - df["def_rating"]

    last_n = df.tail(ROLLING_WINDOW)

    stats = {}
    for col in ["off_rating", "def_rating", "net_rating", "fg_pct", "fg3_pct",
                 "ft_pct", "reb", "ast", "tov", "pts", "pts_allowed"]:
        stats[f"roll_{col}"] = last_n[col].mean()

    # Win streak
    streak = 0
    for wl in df["wl"].values[::-1]:
        if wl == "W":
            streak = max(streak, 0) + 1
        else:
            streak = min(streak, 0) - 1
        if abs(streak) == 1 and wl != df["wl"].values[-1]:
            break
    # Recalculate properly
    streak = 0
    for wl in reversed(df["wl"].tolist()):
        if streak == 0:
            streak = 1 if wl == "W" else -1
        elif (streak > 0 and wl == "W"):
            streak += 1
        elif (streak < 0 and wl == "L"):
            streak -= 1
        else:
            break
    stats["win_streak"] = streak

    # Season win pct
    wins = (df["wl"] == "W").sum()
    stats["season_win_pct"] = wins / len(df) if len(df) > 0 else 0.5

    # Rest days
    if len(df) >= 1:
        last_game = df["game_date"].iloc[-1]
        today = pd.Timestamp(before_date)
        stats["rest_days"] = (today - last_game).days
    else:
        stats["rest_days"] = 3
    stats["b2b"] = 1 if stats["rest_days"] <= 1 else 0

    return stats


def predict_today():
    """Generate predictions for today's games. Returns list of prediction dicts."""
    today = datetime.now().strftime("%Y-%m-%d")

    # Check if already predicted
    existing = get_predictions(today)
    if existing:
        return existing

    # Get today's schedule
    print("Fetching today's scoreboard...")
    games = fetch_todays_scoreboard()
    if not games:
        print("No games today.")
        return []

    # Load models and Elo
    win_model, spread_model, total_model = load_models()
    elo = EloSystem()
    elo.load()

    # Fetch odds
    print("Fetching odds...")
    odds = fetch_nba_odds()

    from src.feature_engineer import get_feature_names
    feature_names = get_feature_names()

    predictions = []
    for game in games:
        home_id = game["home_team_id"]
        away_id = game["away_team_id"]

        # Compute rolling stats
        home_stats = _compute_team_rolling(home_id, today)
        away_stats = _compute_team_rolling(away_id, today)

        if not home_stats or not away_stats:
            print(f"  Skipping {game['away_team_abbr']} @ {game['home_team_abbr']} (insufficient data)")
            continue

        # Build feature vector
        rolling_cols = [
            "off_rating", "def_rating", "net_rating",
            "fg_pct", "fg3_pct", "ft_pct",
            "reb", "ast", "tov", "pts", "pts_allowed",
        ]

        features = []
        # Differentials
        for col in rolling_cols:
            features.append(home_stats[f"roll_{col}"] - away_stats[f"roll_{col}"])
        # Sums (for total prediction)
        for col in ["pts", "pts_allowed", "off_rating"]:
            features.append(home_stats[f"roll_{col}"] + away_stats[f"roll_{col}"])

        # Elo
        home_elo = elo.get_rating(home_id)
        away_elo = elo.get_rating(away_id)
        features.append(home_elo - away_elo)

        # Context
        features.append(home_stats["rest_days"] - away_stats["rest_days"])
        features.append(home_stats["win_streak"] - away_stats["win_streak"])
        features.append(home_stats["season_win_pct"] - away_stats["season_win_pct"])
        features.append(home_stats["b2b"])
        features.append(away_stats["b2b"])

        # Predict
        pred = predict_game(win_model, spread_model, total_model, features)

        # Match odds
        home_full = NBA_TEAMS.get(home_id, {}).get("full_name", game["home_team_abbr"])
        away_full = NBA_TEAMS.get(away_id, {}).get("full_name", game["away_team_abbr"])
        odds_key = f"{away_full} @ {home_full}"
        game_odds = odds.get(odds_key, {})

        prediction = {
            "game_id": game["game_id"],
            "game_date": today,
            "home_team_id": home_id,
            "away_team_id": away_id,
            "home_team_abbr": game["home_team_abbr"],
            "away_team_abbr": game["away_team_abbr"],
            "pred_home_win_prob": pred["home_win_prob"],
            "pred_spread": pred["spread"],
            "pred_total": pred["total"],
            "vegas_spread": game_odds.get("spread"),
            "vegas_total": game_odds.get("total"),
            "vegas_home_ml": game_odds.get("home_ml"),
            "vegas_away_ml": game_odds.get("away_ml"),
            "home_injuries": "",
            "away_injuries": "",
            "home_elo": round(home_elo, 1),
            "away_elo": round(away_elo, 1),
        }

        insert_prediction(prediction)
        predictions.append(prediction)

        winner = game["home_team_abbr"] if pred["home_win_prob"] > 0.5 else game["away_team_abbr"]
        conf = max(pred["home_win_prob"], 1 - pred["home_win_prob"])
        print(f"  {game['away_team_abbr']} @ {game['home_team_abbr']}: "
              f"{winner} ({conf:.0%}) | Spread: {pred['spread']:+.1f} | O/U: {pred['total']:.0f}")

    return predictions

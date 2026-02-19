"""Compute features for NBA game prediction from raw game logs."""

import pandas as pd
import numpy as np
from config import ROLLING_WINDOW, TRAINING_SEASONS
from src.db import get_all_game_logs
from src.elo import EloSystem


def build_game_features_df():
    """Build a DataFrame of features for every game across all training seasons.

    Each row = one game, with home/away features and differentials.
    Only uses data available BEFORE each game (no leakage).
    """
    all_logs = get_all_game_logs()
    if not all_logs:
        raise ValueError("No game logs found. Run build_historical.py first.")

    df = pd.DataFrame(all_logs)
    df["game_date"] = pd.to_datetime(df["game_date"])
    df = df.sort_values("game_date")

    # Compute opponent points from plus_minus
    df["pts_allowed"] = df["pts"] - df["plus_minus"]

    # Estimate possessions and ratings
    # Simple possession estimate: FGA - OREB + TOV + 0.44*FTA
    df["poss"] = df["fga"] - df["oreb"] + df["tov"] + 0.44 * df["fta"]
    df["off_rating"] = np.where(df["poss"] > 0, df["pts"] / df["poss"] * 100, 100.0)
    df["def_rating"] = np.where(df["poss"] > 0, df["pts_allowed"] / df["poss"] * 100, 100.0)
    df["net_rating"] = df["off_rating"] - df["def_rating"]

    # --- Rolling stats per team ---
    rolling_cols = [
        "off_rating", "def_rating", "net_rating",
        "fg_pct", "fg3_pct", "ft_pct",
        "reb", "ast", "tov", "pts", "pts_allowed",
    ]

    team_rolling = {}
    for team_id, team_df in df.groupby("team_id"):
        team_df = team_df.sort_values("game_date")
        for col in rolling_cols:
            # Shift by 1 so we don't include the current game
            team_df[f"roll_{col}"] = (
                team_df[col]
                .shift(1)
                .rolling(window=ROLLING_WINDOW, min_periods=3)
                .mean()
            )
        # Win streak (signed: positive = wins, negative = losses)
        wins = (team_df["wl"] == "W").astype(int).shift(1)
        streaks = []
        current_streak = 0
        for w in wins:
            if pd.isna(w):
                streaks.append(0)
                continue
            if w == 1:
                current_streak = max(current_streak, 0) + 1
            else:
                current_streak = min(current_streak, 0) - 1
            streaks.append(current_streak)
        team_df["win_streak"] = streaks

        # Season win pct (cumulative, shifted)
        team_df["cum_wins"] = (team_df["wl"] == "W").cumsum().shift(1).fillna(0)
        team_df["cum_games"] = range(len(team_df))
        team_df["season_win_pct"] = np.where(
            team_df["cum_games"] > 0,
            team_df["cum_wins"] / team_df["cum_games"],
            0.5
        )

        # Rest days
        team_df["prev_game_date"] = team_df["game_date"].shift(1)
        team_df["rest_days"] = (
            (team_df["game_date"] - team_df["prev_game_date"]).dt.days.fillna(3)
        )
        team_df["b2b"] = (team_df["rest_days"] <= 1).astype(int)

        team_rolling[team_id] = team_df

    df = pd.concat(team_rolling.values()).sort_values(["game_date", "game_id"])

    # --- Build Elo ratings ---
    elo = EloSystem()
    elo_home_col = {}
    elo_away_col = {}

    # Process games in order, tracking Elo before each game
    home_games = df[df["is_home"] == 1].sort_values("game_date")
    away_games = df[df["is_home"] == 0].set_index(["game_id"])

    current_season = None
    for _, home_row in home_games.iterrows():
        game_id = home_row["game_id"]
        season = home_row["season"]

        # Season reset
        if season != current_season:
            if current_season is not None:
                elo.season_reset()
            current_season = season

        if game_id not in away_games.index:
            continue
        away_row = away_games.loc[game_id]
        if isinstance(away_row, pd.DataFrame):
            away_row = away_row.iloc[0]

        home_id = home_row["team_id"]
        away_id = away_row["team_id"]

        # Record pre-game Elo
        elo_home_col[game_id] = elo.get_rating(home_id)
        elo_away_col[game_id] = elo.get_rating(away_id)

        # Update Elo with result
        elo.update(home_id, away_id, home_row["pts"], away_row["pts"])

    elo.save()

    # --- Pair home/away into game rows ---
    home_df = df[df["is_home"] == 1].copy()
    away_df = df[df["is_home"] == 0].copy()

    # Rename columns with prefix
    home_rename = {c: f"home_{c}" for c in home_df.columns if c not in ["game_id", "game_date", "season"]}
    away_rename = {c: f"away_{c}" for c in away_df.columns if c not in ["game_id", "game_date", "season"]}

    home_df = home_df.rename(columns=home_rename)
    away_df = away_df.rename(columns=away_rename)

    games = home_df.merge(away_df, on=["game_id", "game_date", "season"], how="inner")

    # Add Elo
    games["home_elo"] = games["game_id"].map(elo_home_col)
    games["away_elo"] = games["game_id"].map(elo_away_col)
    games["elo_diff"] = games["home_elo"] - games["away_elo"]

    # --- Build differential features ---
    feature_cols = []
    for col in rolling_cols:
        diff_col = f"diff_{col}"
        games[diff_col] = games[f"home_roll_{col}"] - games[f"away_roll_{col}"]
        feature_cols.append(diff_col)

    # Sum-based features for total prediction
    for col in ["pts", "pts_allowed", "off_rating"]:
        sum_col = f"sum_{col}"
        games[sum_col] = games[f"home_roll_{col}"] + games[f"away_roll_{col}"]
        feature_cols.append(sum_col)

    # Context features
    games["diff_rest_days"] = games["home_rest_days"] - games["away_rest_days"]
    games["diff_win_streak"] = games["home_win_streak"] - games["away_win_streak"]
    games["diff_season_win_pct"] = games["home_season_win_pct"] - games["away_season_win_pct"]
    games["home_b2b"] = games["home_b2b"]
    games["away_b2b"] = games["away_b2b"]

    feature_cols.extend([
        "elo_diff", "diff_rest_days", "diff_win_streak", "diff_season_win_pct",
        "home_b2b", "away_b2b",
    ])

    # --- Target variables ---
    games["home_win"] = (games["home_wl"] == "W").astype(int)
    games["margin"] = games["home_pts"] - games["away_pts"]
    games["total_pts"] = games["home_pts"] + games["away_pts"]

    # Drop rows with missing features (first few games of each season)
    games = games.dropna(subset=feature_cols)

    return games, feature_cols


def get_feature_names():
    """Return the list of feature column names (without building the full df)."""
    rolling_cols = [
        "off_rating", "def_rating", "net_rating",
        "fg_pct", "fg3_pct", "ft_pct",
        "reb", "ast", "tov", "pts", "pts_allowed",
    ]
    feature_cols = [f"diff_{c}" for c in rolling_cols]
    feature_cols += [f"sum_{c}" for c in ["pts", "pts_allowed", "off_rating"]]
    feature_cols += [
        "elo_diff", "diff_rest_days", "diff_win_streak", "diff_season_win_pct",
        "home_b2b", "away_b2b",
    ]
    return feature_cols

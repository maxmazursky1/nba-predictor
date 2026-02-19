#!/usr/bin/env python3
"""Train XGBoost models and run backtests."""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import TRAINING_SEASONS
from src.feature_engineer import build_game_features_df
from src.backtest import expanding_window_backtest, print_backtest_summary
from src.model import (
    train_win_model, train_spread_model, train_total_model, save_models
)


def main():
    print("Building features from game logs...")
    games_df, feature_cols = build_game_features_df()
    print(f"Total games with features: {len(games_df)}")
    print(f"Features: {len(feature_cols)}")
    print(f"Seasons: {games_df['season'].unique().tolist()}")

    # --- Backtest ---
    print("\nRunning expanding-window backtest...")
    results = expanding_window_backtest(games_df, feature_cols, TRAINING_SEASONS)
    summary = print_backtest_summary(results)

    # --- Train final models on ALL data ---
    print("\nTraining final models on all data...")
    X = games_df[feature_cols].values
    y_wl = games_df["home_win"].values
    y_spread = games_df["margin"].values
    y_total = games_df["total_pts"].values

    win_model = train_win_model(X, y_wl)
    spread_model = train_spread_model(X, y_spread)
    total_model = train_total_model(X, y_total)

    save_models(win_model, spread_model, total_model)
    print("\nDone! Models trained and saved.")


if __name__ == "__main__":
    main()

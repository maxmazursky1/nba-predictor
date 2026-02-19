"""Expanding-window backtesting for NBA prediction models."""

import numpy as np
from sklearn.metrics import accuracy_score, log_loss, mean_absolute_error
from src.model import train_win_model, train_spread_model, train_total_model


def expanding_window_backtest(games_df, feature_cols, seasons):
    """Run expanding-window cross-validation.

    Folds:
      Train on seasons[0..i], test on seasons[i+1]
      Starting with at least 3 training seasons.
    """
    results = []

    for i in range(2, len(seasons) - 1):
        train_seasons = seasons[:i + 1]
        test_season = seasons[i + 1]

        train_mask = games_df["season"].isin(train_seasons)
        test_mask = games_df["season"] == test_season

        train_df = games_df[train_mask]
        test_df = games_df[test_mask]

        if len(test_df) == 0:
            continue

        X_train = train_df[feature_cols].values
        X_test = test_df[feature_cols].values

        # Win/Loss
        y_train_wl = train_df["home_win"].values
        y_test_wl = test_df["home_win"].values
        win_model = train_win_model(X_train, y_train_wl)
        wl_probs = win_model.predict_proba(X_test)[:, 1]
        wl_preds = (wl_probs >= 0.5).astype(int)

        # Spread
        y_train_sp = train_df["margin"].values
        y_test_sp = test_df["margin"].values
        spread_model = train_spread_model(X_train, y_train_sp)
        sp_preds = spread_model.predict(X_test)

        # Total
        y_train_tot = train_df["total_pts"].values
        y_test_tot = test_df["total_pts"].values
        total_model = train_total_model(X_train, y_train_tot)
        tot_preds = total_model.predict(X_test)

        fold_result = {
            "test_season": test_season,
            "n_games": len(test_df),
            "wl_accuracy": accuracy_score(y_test_wl, wl_preds),
            "wl_log_loss": log_loss(y_test_wl, wl_probs),
            "spread_mae": mean_absolute_error(y_test_sp, sp_preds),
            "total_mae": mean_absolute_error(y_test_tot, tot_preds),
        }
        results.append(fold_result)

        print(f"  {test_season}: {fold_result['n_games']} games | "
              f"W/L: {fold_result['wl_accuracy']:.1%} | "
              f"Spread MAE: {fold_result['spread_mae']:.1f} | "
              f"Total MAE: {fold_result['total_mae']:.1f}")

    return results


def print_backtest_summary(results):
    """Print aggregate backtest metrics."""
    total_games = sum(r["n_games"] for r in results)
    avg_acc = np.mean([r["wl_accuracy"] for r in results])
    avg_ll = np.mean([r["wl_log_loss"] for r in results])
    avg_sp_mae = np.mean([r["spread_mae"] for r in results])
    avg_tot_mae = np.mean([r["total_mae"] for r in results])

    print(f"\n{'='*50}")
    print(f"BACKTEST SUMMARY ({total_games} total games)")
    print(f"{'='*50}")
    print(f"  W/L Accuracy:   {avg_acc:.1%}")
    print(f"  W/L Log Loss:   {avg_ll:.4f}")
    print(f"  Spread MAE:     {avg_sp_mae:.1f} pts")
    print(f"  Total MAE:      {avg_tot_mae:.1f} pts")
    print(f"{'='*50}")

    return {
        "total_games": total_games,
        "wl_accuracy": round(avg_acc, 4),
        "wl_log_loss": round(avg_ll, 4),
        "spread_mae": round(avg_sp_mae, 1),
        "total_mae": round(avg_tot_mae, 1),
    }

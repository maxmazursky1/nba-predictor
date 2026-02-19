"""XGBoost model training, saving, loading, and prediction."""

import os
import json
import numpy as np
from xgboost import XGBClassifier, XGBRegressor
from config import MODELS_DIR


def train_win_model(X_train, y_train):
    """Train the win/loss classifier."""
    model = XGBClassifier(
        max_depth=5,
        learning_rate=0.05,
        n_estimators=500,
        subsample=0.8,
        colsample_bytree=0.8,
        eval_metric="logloss",
        random_state=42,
    )
    model.fit(X_train, y_train)
    return model


def train_spread_model(X_train, y_train):
    """Train the spread (margin) regressor."""
    model = XGBRegressor(
        max_depth=5,
        learning_rate=0.05,
        n_estimators=500,
        subsample=0.8,
        colsample_bytree=0.8,
        eval_metric="mae",
        random_state=42,
    )
    model.fit(X_train, y_train)
    return model


def train_total_model(X_train, y_train):
    """Train the total points regressor."""
    model = XGBRegressor(
        max_depth=5,
        learning_rate=0.05,
        n_estimators=500,
        subsample=0.8,
        colsample_bytree=0.8,
        eval_metric="mae",
        random_state=42,
    )
    model.fit(X_train, y_train)
    return model


def save_models(win_model, spread_model, total_model):
    """Save all three models."""
    os.makedirs(MODELS_DIR, exist_ok=True)
    win_model.save_model(os.path.join(MODELS_DIR, "win_model.json"))
    spread_model.save_model(os.path.join(MODELS_DIR, "spread_model.json"))
    total_model.save_model(os.path.join(MODELS_DIR, "total_model.json"))
    print(f"Models saved to {MODELS_DIR}")


def load_models():
    """Load all three models."""
    win_model = XGBClassifier()
    win_model.load_model(os.path.join(MODELS_DIR, "win_model.json"))

    spread_model = XGBRegressor()
    spread_model.load_model(os.path.join(MODELS_DIR, "spread_model.json"))

    total_model = XGBRegressor()
    total_model.load_model(os.path.join(MODELS_DIR, "total_model.json"))

    return win_model, spread_model, total_model


def predict_game(win_model, spread_model, total_model, features):
    """Predict a single game. features = 1D array of feature values.

    Returns dict with home_win_prob, spread, total.
    """
    X = np.array(features).reshape(1, -1)
    home_win_prob = float(win_model.predict_proba(X)[0][1])
    spread = float(spread_model.predict(X)[0])
    total = float(total_model.predict(X)[0])

    return {
        "home_win_prob": round(home_win_prob, 3),
        "spread": round(spread, 1),
        "total": round(total, 1),
    }

"""Elo rating system for NBA teams."""

import json
import os
from config import ELO_INITIAL, ELO_K, ELO_HOME_ADVANTAGE, ELO_SEASON_REVERT, ELO_PATH


def expected_score(rating_a, rating_b):
    """Expected win probability for team A vs team B."""
    return 1.0 / (1.0 + 10 ** ((rating_b - rating_a) / 400.0))


def mov_multiplier(margin):
    """Margin-of-victory multiplier to scale Elo updates."""
    return max(abs(margin) ** 0.8 / 10.0, 1.0)


class EloSystem:
    def __init__(self):
        self.ratings = {}

    def get_rating(self, team_id):
        return self.ratings.get(team_id, ELO_INITIAL)

    def update(self, home_id, away_id, home_pts, away_pts):
        """Update Elo after a game. Returns (new_home_elo, new_away_elo)."""
        home_elo = self.get_rating(home_id)
        away_elo = self.get_rating(away_id)

        # Home advantage baked into expectation
        home_expected = expected_score(home_elo + ELO_HOME_ADVANTAGE, away_elo)
        home_actual = 1.0 if home_pts > away_pts else 0.0

        margin = home_pts - away_pts
        mult = mov_multiplier(margin)
        delta = ELO_K * mult * (home_actual - home_expected)

        self.ratings[home_id] = home_elo + delta
        self.ratings[away_id] = away_elo - delta

        return self.ratings[home_id], self.ratings[away_id]

    def season_reset(self):
        """Regress ratings toward the mean at season start."""
        mean_elo = ELO_INITIAL + 5  # slight above since new teams enter at 1500
        for team_id in self.ratings:
            self.ratings[team_id] = (
                ELO_SEASON_REVERT * self.ratings[team_id]
                + (1 - ELO_SEASON_REVERT) * mean_elo
            )

    def save(self):
        with open(ELO_PATH, "w") as f:
            json.dump({str(k): v for k, v in self.ratings.items()}, f, indent=2)

    def load(self):
        if os.path.exists(ELO_PATH):
            with open(ELO_PATH) as f:
                data = json.load(f)
            self.ratings = {int(k): v for k, v in data.items()}

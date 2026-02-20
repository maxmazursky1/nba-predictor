"""Adjust model predictions based on player injuries.

Uses NBA API season stats to quantify missing production (PPG, MPG)
and shifts the predicted spread accordingly.
"""

import time
from nba_api.stats.endpoints import LeagueLeaders
from src.injury_fetcher import fetch_injuries

# Adjustment factor: how much missing PPG shifts the spread.
# A player averaging 25 PPG out doesn't mean -25 pts (backup fills some).
# Research suggests ~0.5x is reasonable.
INJURY_PPG_FACTOR = 0.5

# Cache player stats for the session
_player_cache = None


def _load_player_stats():
    """Load current season per-game stats for all players."""
    global _player_cache
    if _player_cache is not None:
        return _player_cache

    try:
        leaders = LeagueLeaders(
            season="2025-26",
            stat_category_abbreviation="PTS",
            per_mode48="PerGame",
        )
        time.sleep(0.6)
        df = leaders.get_data_frames()[0]
    except Exception:
        # Fallback: try totals and compute per-game
        try:
            leaders = LeagueLeaders(
                season="2025-26",
                stat_category_abbreviation="PTS",
            )
            time.sleep(0.6)
            df = leaders.get_data_frames()[0]
            # Convert totals to per-game
            for col in ["PTS", "MIN", "REB", "AST", "STL", "BLK"]:
                if col in df.columns:
                    df[col] = df[col] / df["GP"].clip(lower=1)
        except Exception:
            _player_cache = {}
            return _player_cache

    # Build lookup: player name -> {ppg, mpg, team_abbr}
    stats = {}
    for _, row in df.iterrows():
        name = row["PLAYER"]
        stats[name.lower()] = {
            "name": name,
            "ppg": float(row["PTS"]),
            "mpg": float(row["MIN"]),
            "team": row["TEAM"],
            "gp": int(row["GP"]),
        }

    _player_cache = stats
    return stats


def _match_player(injury_name, stats):
    """Fuzzy match an injury report name to the stats database."""
    key = injury_name.lower()
    if key in stats:
        return stats[key]

    # Try last name match within same approximate name
    parts = injury_name.lower().split()
    if len(parts) >= 2:
        last = parts[-1]
        # Handle suffixes like III, Jr, Jr.
        if last in ("iii", "jr", "jr.", "ii", "iv"):
            last = parts[-2] if len(parts) > 2 else last
        candidates = []
        for k, v in stats.items():
            if last in k.split():
                candidates.append(v)
        if len(candidates) == 1:
            return candidates[0]
        # Try first + last
        if len(parts) >= 2:
            first = parts[0]
            for c in candidates:
                if first in c["name"].lower():
                    return c
    return None


def compute_injury_adjustment(home_abbr, away_abbr, injuries=None):
    """Compute spread adjustment based on injuries.

    Returns a dict with:
        adjustment: float - add to pred_spread (positive = helps home)
        home_missing_ppg: float
        away_missing_ppg: float
        home_out: list of {name, ppg, mpg}
        away_out: list of {name, ppg, mpg}
    """
    if injuries is None:
        injuries = fetch_injuries()

    stats = _load_player_stats()

    result = {
        "adjustment": 0.0,
        "home_missing_ppg": 0.0,
        "away_missing_ppg": 0.0,
        "home_out": [],
        "away_out": [],
    }

    for side, abbr, key in [("home", home_abbr, "home_out"),
                             ("away", away_abbr, "away_out")]:
        team_injuries = injuries.get(abbr, [])
        missing_ppg = 0.0
        out_players = []

        for inj in team_injuries:
            if inj["status"] != "Out":
                continue
            matched = _match_player(inj["player"], stats)
            if matched:
                out_players.append({
                    "name": matched["name"],
                    "ppg": round(matched["ppg"], 1),
                    "mpg": round(matched["mpg"], 1),
                })
                missing_ppg += matched["ppg"]
            else:
                # Unknown player — assume minimal impact
                out_players.append({
                    "name": inj["player"],
                    "ppg": 0.0,
                    "mpg": 0.0,
                })

        result[key] = out_players
        result["{}_missing_ppg".format(side)] = round(missing_ppg, 1)

    # Adjustment: positive means helps home team
    # If away is missing more PPG, home gets a boost (positive adjustment)
    ppg_diff = result["away_missing_ppg"] - result["home_missing_ppg"]
    result["adjustment"] = round(ppg_diff * INJURY_PPG_FACTOR, 1)

    return result

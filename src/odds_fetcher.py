"""Fetch current Vegas odds from The Odds API."""

import os
import requests
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"))


def fetch_nba_odds():
    """Fetch current NBA odds. Returns dict keyed by 'AWAY @ HOME' with spreads/totals.

    Returns empty dict if API key missing or request fails.
    """
    api_key = os.environ.get("THE_ODDS_API_KEY", "")
    if not api_key or api_key == "your_key_here":
        return {}

    url = "https://api.the-odds-api.com/v4/sports/basketball_nba/odds/"
    params = {
        "apiKey": api_key,
        "regions": "us",
        "markets": "h2h,spreads,totals",
        "oddsFormat": "american",
    }

    try:
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
    except Exception:
        return {}

    odds = {}
    for game in resp.json():
        home = game.get("home_team", "")
        away = game.get("away_team", "")
        key = f"{away} @ {home}"

        entry = {"spread": None, "total": None, "home_ml": None, "away_ml": None}

        for bm in game.get("bookmakers", []):
            for market in bm.get("markets", []):
                mk = market["key"]
                outcomes = market.get("outcomes", [])
                if mk == "spreads":
                    for o in outcomes:
                        if o["name"] == home and entry["spread"] is None:
                            entry["spread"] = o.get("point")
                elif mk == "totals":
                    for o in outcomes:
                        if o["name"] == "Over" and entry["total"] is None:
                            entry["total"] = o.get("point")
                elif mk == "h2h":
                    for o in outcomes:
                        if o["name"] == home and entry["home_ml"] is None:
                            entry["home_ml"] = o.get("price")
                        elif o["name"] == away and entry["away_ml"] is None:
                            entry["away_ml"] = o.get("price")

            if all(v is not None for v in entry.values()):
                break

        odds[key] = entry

    return odds

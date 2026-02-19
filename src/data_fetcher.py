"""Fetch NBA data via nba_api."""

import time
from nba_api.stats.endpoints import LeagueGameLog, ScoreboardV2
from nba_api.stats.static import teams
from config import API_DELAY


NBA_TEAMS = {t["id"]: t for t in teams.get_teams()}


def fetch_season_game_logs(season):
    """Fetch all team-level game logs for a season. Returns list of dicts."""
    print(f"  Fetching {season}...")
    log = LeagueGameLog(
        season=season,
        player_or_team_abbreviation="T",
        season_type_all_star="Regular Season",
    )
    time.sleep(API_DELAY)
    df = log.get_data_frames()[0]

    rows = []
    for _, r in df.iterrows():
        matchup = r["MATCHUP"]
        is_home = 1 if "vs." in matchup else 0
        rows.append({
            "game_id": r["GAME_ID"],
            "game_date": r["GAME_DATE"],
            "season": season,
            "team_id": r["TEAM_ID"],
            "team_abbr": r["TEAM_ABBREVIATION"],
            "matchup": matchup,
            "is_home": is_home,
            "wl": r["WL"],
            "pts": int(r["PTS"]),
            "fgm": int(r["FGM"]),
            "fga": int(r["FGA"]),
            "fg_pct": float(r["FG_PCT"]) if r["FG_PCT"] else None,
            "fg3m": int(r["FG3M"]),
            "fg3a": int(r["FG3A"]),
            "fg3_pct": float(r["FG3_PCT"]) if r["FG3_PCT"] else None,
            "ftm": int(r["FTM"]),
            "fta": int(r["FTA"]),
            "ft_pct": float(r["FT_PCT"]) if r["FT_PCT"] else None,
            "oreb": int(r["OREB"]),
            "dreb": int(r["DREB"]),
            "reb": int(r["REB"]),
            "ast": int(r["AST"]),
            "stl": int(r["STL"]),
            "blk": int(r["BLK"]),
            "tov": int(r["TOV"]),
            "plus_minus": float(r["PLUS_MINUS"]),
        })
    return rows


def fetch_playoff_game_logs(season):
    """Fetch playoff game logs for a season."""
    print(f"  Fetching {season} playoffs...")
    try:
        log = LeagueGameLog(
            season=season,
            player_or_team_abbreviation="T",
            season_type_all_star="Playoffs",
        )
        time.sleep(API_DELAY)
        df = log.get_data_frames()[0]
    except Exception:
        return []

    rows = []
    for _, r in df.iterrows():
        matchup = r["MATCHUP"]
        is_home = 1 if "vs." in matchup else 0
        rows.append({
            "game_id": r["GAME_ID"],
            "game_date": r["GAME_DATE"],
            "season": season,
            "team_id": r["TEAM_ID"],
            "team_abbr": r["TEAM_ABBREVIATION"],
            "matchup": matchup,
            "is_home": is_home,
            "wl": r["WL"],
            "pts": int(r["PTS"]),
            "fgm": int(r["FGM"]),
            "fga": int(r["FGA"]),
            "fg_pct": float(r["FG_PCT"]) if r["FG_PCT"] else None,
            "fg3m": int(r["FG3M"]),
            "fg3a": int(r["FG3A"]),
            "fg3_pct": float(r["FG3_PCT"]) if r["FG3_PCT"] else None,
            "ftm": int(r["FTM"]),
            "fta": int(r["FTA"]),
            "ft_pct": float(r["FT_PCT"]) if r["FT_PCT"] else None,
            "oreb": int(r["OREB"]),
            "dreb": int(r["DREB"]),
            "reb": int(r["REB"]),
            "ast": int(r["AST"]),
            "stl": int(r["STL"]),
            "blk": int(r["BLK"]),
            "tov": int(r["TOV"]),
            "plus_minus": float(r["PLUS_MINUS"]),
        })
    return rows


def fetch_todays_scoreboard():
    """Get today's games from the NBA scoreboard. Returns list of game dicts."""
    sb = ScoreboardV2()
    time.sleep(API_DELAY)
    header = sb.game_header.get_data_frame()
    line_score = sb.line_score.get_data_frame()

    games = []
    for _, row in header.iterrows():
        game_id = row["GAME_ID"]
        home_id = row["HOME_TEAM_ID"]
        away_id = row["VISITOR_TEAM_ID"]
        status = row["GAME_STATUS_TEXT"]

        home_abbr = line_score.loc[
            (line_score["GAME_ID"] == game_id) & (line_score["TEAM_ID"] == home_id),
            "TEAM_ABBREVIATION"
        ]
        away_abbr = line_score.loc[
            (line_score["GAME_ID"] == game_id) & (line_score["TEAM_ID"] == away_id),
            "TEAM_ABBREVIATION"
        ]

        games.append({
            "game_id": game_id,
            "home_team_id": home_id,
            "away_team_id": away_id,
            "home_team_abbr": home_abbr.iloc[0] if len(home_abbr) else "???",
            "away_team_abbr": away_abbr.iloc[0] if len(away_abbr) else "???",
            "status": status,
        })
    return games

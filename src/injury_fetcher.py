"""Fetch current NBA injury data from ESPN's public API."""

import requests

# Map ESPN team display names to nba_api abbreviations
ESPN_TO_ABBR = {
    "Atlanta Hawks": "ATL", "Boston Celtics": "BOS", "Brooklyn Nets": "BKN",
    "Charlotte Hornets": "CHA", "Chicago Bulls": "CHI", "Cleveland Cavaliers": "CLE",
    "Dallas Mavericks": "DAL", "Denver Nuggets": "DEN", "Detroit Pistons": "DET",
    "Golden State Warriors": "GSW", "Houston Rockets": "HOU", "Indiana Pacers": "IND",
    "LA Clippers": "LAC", "Los Angeles Clippers": "LAC",
    "Los Angeles Lakers": "LAL", "LA Lakers": "LAL",
    "Memphis Grizzlies": "MEM", "Miami Heat": "MIA", "Milwaukee Bucks": "MIL",
    "Minnesota Timberwolves": "MIN", "New Orleans Pelicans": "NOP",
    "New York Knicks": "NYK", "Oklahoma City Thunder": "OKC",
    "Orlando Magic": "ORL", "Philadelphia 76ers": "PHI", "Phoenix Suns": "PHX",
    "Portland Trail Blazers": "POR", "Sacramento Kings": "SAC",
    "San Antonio Spurs": "SAS", "Toronto Raptors": "TOR", "Utah Jazz": "UTA",
    "Washington Wizards": "WAS",
}

ESPN_INJURIES_URL = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/injuries"


def fetch_injuries():
    """Fetch current NBA injuries from ESPN.

    Returns dict keyed by team abbreviation, value is list of dicts:
        [{"player": "...", "status": "Out", "detail": "..."}]
    Only includes Out and Day-To-Day players.
    """
    try:
        resp = requests.get(ESPN_INJURIES_URL, timeout=10)
        resp.raise_for_status()
    except Exception:
        return {}

    data = resp.json()
    result = {}

    for team_data in data.get("injuries", []):
        team_name = team_data.get("displayName", "")
        abbr = ESPN_TO_ABBR.get(team_name)
        if not abbr:
            continue

        players = []
        for entry in team_data.get("injuries", []):
            status = entry.get("status", "")
            if status not in ("Out", "Day-To-Day"):
                continue
            athlete = entry.get("athlete", {})
            name = athlete.get("displayName", "Unknown")
            short_comment = entry.get("shortComment", "")
            players.append({
                "player": name,
                "status": status,
                "detail": short_comment,
            })

        if players:
            result[abbr] = players

    return result


def format_injuries_short(players):
    """Format a team's injury list into a short display string."""
    if not players:
        return ""
    parts = []
    for p in players[:5]:
        tag = "OUT" if p["status"] == "Out" else "DTD"
        parts.append("{} ({})".format(p["player"], tag))
    suffix = " +{} more".format(len(players) - 5) if len(players) > 5 else ""
    return ", ".join(parts) + suffix

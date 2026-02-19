#!/usr/bin/env python3
"""Flask app for NBA game predictions."""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from flask import Flask, render_template, jsonify
from src.db import init_db, get_predictions, get_predictions_with_results
from src.predictor import predict_today
from datetime import datetime, timezone, timedelta

app = Flask(__name__)

# US Eastern timezone (UTC-5, or UTC-4 during DST)
ET = timezone(timedelta(hours=-5))


@app.before_request
def setup():
    init_db()


@app.route("/")
def index():
    today = datetime.now(ET).strftime("%Y-%m-%d")
    predictions = get_predictions(today)
    if not predictions:
        try:
            predictions = predict_today()
        except Exception as e:
            predictions = []
            import traceback
            traceback.print_exc()
            print(f"Prediction error: {e}")

    # Enrich predictions for display
    for p in predictions:
        prob = p["pred_home_win_prob"]
        if prob >= 0.5:
            p["pick"] = p["home_team_abbr"]
            p["pick_confidence"] = prob
        else:
            p["pick"] = p["away_team_abbr"]
            p["pick_confidence"] = 1 - prob

        # Format spread for display
        spread = p["pred_spread"]
        if spread > 0:
            p["spread_display"] = f"{p['home_team_abbr']} -{abs(spread):.1f}"
        elif spread < 0:
            p["spread_display"] = f"{p['away_team_abbr']} -{abs(spread):.1f}"
        else:
            p["spread_display"] = "PICK"

        p["total_display"] = f"{p['pred_total']:.0f}"

        # Vegas comparison
        if p.get("vegas_spread") is not None:
            p["vegas_spread_display"] = f"{p['vegas_spread']:+.1f}"
        else:
            p["vegas_spread_display"] = "N/A"
        if p.get("vegas_total") is not None:
            p["vegas_total_display"] = f"{p['vegas_total']:.0f}"
        else:
            p["vegas_total_display"] = "N/A"

        # Value edge vs Vegas (signed: vegas line - model line, for home team)
        # pred_spread = predicted home margin (positive = home wins by X)
        # vegas_spread = home spread (negative = home favored, e.g. -8.0)
        # Model home spread = -pred_spread (e.g. model says home wins by 4.7 → home spread -4.7)
        # Edge = vegas_spread - (-pred_spread) = vegas_spread + pred_spread
        # Positive edge → model more bullish on home → play home side
        # Negative edge → model less bullish on home → play away side
        p["spread_edge"] = None
        p["spread_play"] = None
        p["ou_edge"] = None
        p["ou_play"] = None
        if p.get("vegas_spread") is not None:
            edge = p["vegas_spread"] + p["pred_spread"]
            p["spread_edge"] = round(edge, 1)
            if edge > 0:
                # Model more bullish on home — bet home to cover
                p["spread_play"] = f"{p['home_team_abbr']} {p['vegas_spread']:+.1f}"
            else:
                # Model less bullish on home — bet away to cover
                p["spread_play"] = f"{p['away_team_abbr']} {-p['vegas_spread']:+.1f}"
        if p.get("vegas_total") is not None:
            p["ou_edge"] = round(p["pred_total"] - p["vegas_total"], 1)
            p["ou_play"] = "Over" if p["ou_edge"] > 0 else "Under"
            p["ou_play"] += f" {p['vegas_total']:.0f}"

    # Identify best value plays (|spread edge| >= 3 pts or |O/U edge| >= 4 pts)
    best_spread_plays = sorted(
        [p for p in predictions if p["spread_edge"] is not None and abs(p["spread_edge"]) >= 3],
        key=lambda x: -abs(x["spread_edge"])
    )[:5]
    best_ou_plays = sorted(
        [p for p in predictions if p["ou_edge"] is not None and abs(p["ou_edge"]) >= 4],
        key=lambda x: -abs(x["ou_edge"])
    )[:3]

    # Mark them on the predictions
    best_game_ids = set()
    for p in best_spread_plays + best_ou_plays:
        best_game_ids.add(p["game_id"])
    for p in predictions:
        p["is_value_play"] = p["game_id"] in best_game_ids

    return render_template("index.html", predictions=predictions, date=today,
                           best_spread_plays=best_spread_plays,
                           best_ou_plays=best_ou_plays)


@app.route("/performance")
def performance():
    rows = get_predictions_with_results()

    if not rows:
        return render_template("performance.html", stats=None, rows=[])

    # Compute stats
    total = len(rows)
    correct = sum(
        1 for r in rows
        if (r["pred_home_win_prob"] >= 0.5) == bool(r["actual_home_win"])
    )
    accuracy = correct / total if total else 0

    # ATS record (if vegas spread available)
    ats_wins = 0
    ats_total = 0
    for r in rows:
        if r.get("vegas_spread") is not None:
            actual_margin = r["home_pts"] - r["away_pts"]
            # edge = vegas_spread + pred_spread (positive = model bullish on home)
            model_edge = r["vegas_spread"] + r["pred_spread"]
            # Model picks home to cover if edge > 0
            model_covers = model_edge > 0
            # Home covers if actual margin > -vegas_spread (i.e. beats the spread)
            actual_covers = actual_margin > -r["vegas_spread"]
            if model_covers == actual_covers:
                ats_wins += 1
            ats_total += 1

    # O/U record
    ou_wins = 0
    ou_total = 0
    for r in rows:
        if r.get("vegas_total") is not None:
            actual_total = r["home_pts"] + r["away_pts"]
            model_over = r["pred_total"] > r["vegas_total"]
            actual_over = actual_total > r["vegas_total"]
            if model_over == actual_over:
                ou_wins += 1
            ou_total += 1

    stats = {
        "total_games": total,
        "wl_correct": correct,
        "wl_accuracy": accuracy,
        "ats_wins": ats_wins,
        "ats_total": ats_total,
        "ats_pct": ats_wins / ats_total if ats_total else 0,
        "ou_wins": ou_wins,
        "ou_total": ou_total,
        "ou_pct": ou_wins / ou_total if ou_total else 0,
    }

    # Build cumulative data for chart
    cumulative = []
    running_correct = 0
    for i, r in enumerate(rows):
        is_correct = (r["pred_home_win_prob"] >= 0.5) == bool(r["actual_home_win"])
        running_correct += int(is_correct)
        cumulative.append({
            "game_num": i + 1,
            "accuracy": round(running_correct / (i + 1) * 100, 1),
            "date": r["game_date"],
        })

    return render_template("performance.html", stats=stats, rows=rows, cumulative=cumulative)


@app.route("/methodology")
def methodology():
    return render_template("methodology.html")


@app.route("/debug")
def debug():
    """Temporary debug endpoint to diagnose Render issues."""
    import sqlite3
    from config import DB_PATH
    info = {
        "now_utc": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
        "now_et": datetime.now(ET).strftime("%Y-%m-%d %H:%M:%S"),
        "today_used": datetime.now(ET).strftime("%Y-%m-%d"),
        "db_path": DB_PATH,
        "db_exists": os.path.exists(DB_PATH),
        "db_size": os.path.getsize(DB_PATH) if os.path.exists(DB_PATH) else 0,
    }
    try:
        conn = sqlite3.connect(DB_PATH)
        row = conn.execute("SELECT COUNT(*) FROM predictions").fetchone()
        info["total_predictions"] = row[0]
        row = conn.execute("SELECT game_date, COUNT(*) as cnt FROM predictions GROUP BY game_date ORDER BY game_date DESC LIMIT 5").fetchall()
        info["prediction_dates"] = [{"date": r[0], "count": r[1]} for r in row]
        row = conn.execute("SELECT COUNT(*) FROM game_logs").fetchone()
        info["total_game_logs"] = row[0]
        conn.close()
    except Exception as e:
        info["db_error"] = str(e)
    return jsonify(info)


if __name__ == "__main__":
    app.run(debug=True, port=5050)

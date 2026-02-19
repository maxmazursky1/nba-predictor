#!/usr/bin/env python3
"""Flask app for NBA game predictions."""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from flask import Flask, render_template
from src.db import init_db, get_predictions, get_predictions_with_results
from src.predictor import predict_today
from datetime import datetime

app = Flask(__name__)


@app.before_request
def setup():
    init_db()


@app.route("/")
def index():
    today = datetime.now().strftime("%Y-%m-%d")
    predictions = get_predictions(today)
    if not predictions:
        try:
            predictions = predict_today()
        except Exception as e:
            predictions = []
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

        # Value edge vs Vegas
        p["spread_edge"] = None
        p["spread_play"] = None
        p["ou_edge"] = None
        p["ou_play"] = None
        if p.get("vegas_spread") is not None:
            # Model spread is home margin; vegas_spread is home spread (negative = favored)
            # Edge = how much the model disagrees in absolute terms
            p["spread_edge"] = abs(p["pred_spread"] - p["vegas_spread"])
            # The play: if model thinks home is better than Vegas does, bet home side
            if p["pred_spread"] > p["vegas_spread"]:
                # Model more bullish on home team
                if p["vegas_spread"] <= 0:
                    p["spread_play"] = f"{p['home_team_abbr']} {p['vegas_spread']}"
                else:
                    p["spread_play"] = f"{p['away_team_abbr']} {-p['vegas_spread']:+.1f}"
            else:
                # Model more bullish on away team
                if p["vegas_spread"] >= 0:
                    p["spread_play"] = f"{p['away_team_abbr']} {-p['vegas_spread']:+.1f}"
                else:
                    p["spread_play"] = f"{p['home_team_abbr']} {p['vegas_spread']}"
        if p.get("vegas_total") is not None:
            p["ou_edge"] = abs(p["pred_total"] - p["vegas_total"])
            p["ou_play"] = "Over" if p["pred_total"] > p["vegas_total"] else "Under"
            p["ou_play"] += f" {p['vegas_total']:.0f}"

    # Identify best value plays (spread edge >= 5 pts or O/U edge >= 8 pts)
    best_spread_plays = sorted(
        [p for p in predictions if p["spread_edge"] and p["spread_edge"] >= 5],
        key=lambda x: -x["spread_edge"]
    )[:5]
    best_ou_plays = sorted(
        [p for p in predictions if p["ou_edge"] and p["ou_edge"] >= 8],
        key=lambda x: -x["ou_edge"]
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
            # Model picks home to cover if pred_spread > vegas_spread
            model_covers = r["pred_spread"] > r["vegas_spread"]
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


if __name__ == "__main__":
    app.run(debug=True, port=5050)

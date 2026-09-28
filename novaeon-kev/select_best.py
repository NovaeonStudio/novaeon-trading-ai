"""Pick the live model + strategy thresholds from held-out results (both test sets pooled, 495 items).

Usage: python select_best.py NAME=results/<fixed-test>.json,results/<r2>.json ...  [--json out.json]
Veto: cost = 3*missed bad news + 1*false block (a missed hack costs more than a skipped breakout);
      threshold swept 0.05..0.95; lowest cost wins, ties -> lower Brier, then earlier-listed model (incumbent first).
Leverage: smallest P(clearly_positive) with precision >= 0.80 (2x) / >= 0.90 (3x) over >= 8 calls; else keep live values.
"""
import json
import sys

FN_COST, FP_COST = 3, 1
LIVE = {"veto": 0.6, "lev2": 0.60, "lev3": 0.75}


def load(path):
    rows = json.load(open(path))["rows"]
    out = []
    for r in rows:
        if "y_neg" in r:  # evaluate.py format
            out.append((r["y_neg"], r["p_neg"], r["y_out"], r["probs"]))
        else:  # evaluate6.py format
            out.append((r["major_negative"]["y"], r["major_negative"]["p"], r["outlook"]["y"], r["outlook"]["probs"]))
    return out


def best_lev(rows, prec_min):
    for t in [x / 100 for x in range(50, 96, 5)]:
        calls = [y for _, _, y, p in rows if p.get("clearly_positive", 0) >= t]
        if len(calls) >= 8 and sum(y == "clearly_positive" for y in calls) / len(calls) >= prec_min:
            return t, len(calls), round(sum(y == "clearly_positive" for y in calls) / len(calls), 3)
    return None


argv = sys.argv[1:]
if "--json" in argv:  # drop the flag and its output path
    i = argv.index("--json"); argv = argv[:i] + argv[i + 2:]
args = [a for a in argv if not a.startswith("--")]
report, winner = [], None
for a in args:
    name, files = a.split("=", 1)
    rows = [r for f in files.split(",") for r in load(f)]
    brier = sum((p - (1.0 if y else 0.0)) ** 2 for y, p, _, _ in rows) / len(rows)
    sweep = []
    for t in [x / 100 for x in range(5, 96, 5)]:
        fn = sum(1 for y, p, _, _ in rows if y and p < t)
        fp = sum(1 for y, p, _, _ in rows if not y and p >= t)
        sweep.append((FN_COST * fn + FP_COST * fp, -t, t, fn, fp))
    cost, _, t, fn, fp = min(sweep)
    pos = sum(1 for y, *_ in rows if y)
    live_fn = sum(1 for y, p, _, _ in rows if y and p < LIVE["veto"])
    live_fp = sum(1 for y, p, _, _ in rows if not y and p >= LIVE["veto"])
    rec = {"model": name, "n": len(rows), "bad_news": pos, "brier": round(brier, 4),
           "at_live_0.6": {"caught": pos - live_fn, "false_blocks": live_fp, "cost": FN_COST * live_fn + FP_COST * live_fp},
           "best_veto": {"threshold": t, "caught": pos - fn, "false_blocks": fp, "cost": cost},
           "lev2": best_lev(rows, 0.80), "lev3": best_lev(rows, 0.90)}
    report.append(rec)
    if report[0]["n"] != len(rows):
        rec["skipped"] = f"tested on {len(rows)} items, not {report[0]['n']}: not comparable"
        continue
    if winner is None or (cost, brier) < (winner["best_veto"]["cost"], winner["brier"]):
        winner = rec
for r in report:
    print(json.dumps(r))
w = winner
choice = {"model": w["model"], "VETO_THRESHOLD": w["best_veto"]["threshold"],
          "LEV2_POSITIVE": w["lev2"][0] if w["lev2"] else LIVE["lev2"],
          "LEV3_POSITIVE": max(w["lev3"][0] if w["lev3"] else LIVE["lev3"],
                               round((w["lev2"][0] if w["lev2"] else LIVE["lev2"]) + 0.05, 2))}
print("CHOICE", json.dumps(choice))
if "--json" in sys.argv:
    json.dump({"report": report, "choice": choice}, open(sys.argv[sys.argv.index("--json") + 1], "w"), indent=1)

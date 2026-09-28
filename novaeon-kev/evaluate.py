"""Compare Kev checkpoints against teacher labels on the held-out set, through a running kev.serve endpoint.

Usage: python evaluate.py http://127.0.0.1:8008 data/heldout.jsonl out.json
Metrics: major_negative accuracy / recall / precision / Brier at the live veto threshold (0.6),
         outlook accuracy and 'clearly_positive' precision (drives 2x/3x leverage).
"""
import json
import sys
import urllib.request

url, path, out = sys.argv[1], sys.argv[2], sys.argv[3]
THRESH = 0.6
rows = [json.loads(line) for line in open(path)]
res = []
for r in rows:
    body = {"model": "kev-latest", "state": r["state"],
            "questions": {k: {kk: vv for kk, vv in q.items() if kk != "label"} for k, q in r["questions"].items()}}
    req = urllib.request.Request(url.rstrip("/") + "/v1/systemone", data=json.dumps(body).encode(),
                                 headers={"content-type": "application/json"})
    ans = json.loads(urllib.request.urlopen(req, timeout=120).read())["answers"]
    p_neg = float(ans["major_negative"]["noul"])
    probs = ans["outlook"]["probabilities"]
    res.append({"id": r.get("id"), "y_neg": r["questions"]["major_negative"]["label"], "p_neg": p_neg,
                "y_out": r["questions"]["outlook"]["label"], "p_out": max(probs, key=probs.get), "probs": probs})

tp = sum(1 for x in res if x["y_neg"] and x["p_neg"] >= THRESH)
fp = sum(1 for x in res if not x["y_neg"] and x["p_neg"] >= THRESH)
fn = sum(1 for x in res if x["y_neg"] and x["p_neg"] < THRESH)
tn = len(res) - tp - fp - fn
pos_pred = [x for x in res if x["p_out"] == "clearly_positive"]
metrics = {
    "n": len(res),
    "neg_positives_in_set": tp + fn,
    "neg_accuracy": round((tp + tn) / len(res), 3),
    "neg_recall": round(tp / (tp + fn), 3) if tp + fn else None,
    "neg_precision": round(tp / (tp + fp), 3) if tp + fp else None,
    "neg_brier": round(sum((x["p_neg"] - (1.0 if x["y_neg"] else 0.0)) ** 2 for x in res) / len(res), 4),
    "outlook_accuracy": round(sum(x["y_out"] == x["p_out"] for x in res) / len(res), 3),
    "positive_precision": round(sum(x["y_out"] == "clearly_positive" for x in pos_pred) / len(pos_pred), 3)
    if pos_pred else None,
    "positive_predicted": len(pos_pred),
}
json.dump({"metrics": metrics, "rows": res}, open(out, "w"), indent=1)
print(json.dumps(metrics))

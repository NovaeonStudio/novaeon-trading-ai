"""Per-question metrics for the 6-question v2 test sets through a running kev.serve endpoint.

Usage: python evaluate6.py http://127.0.0.1:8011 data/heldout-r2.jsonl out.json
noul: accuracy @0.5 (major_negative also @0.6 veto) + recall/precision + Brier; choice: accuracy (+ clearly_positive
precision for outlook); score: exact accuracy, within-1 accuracy, MAE of the expected level.
"""
import json
import sys
import urllib.request

url, path, out = sys.argv[1], sys.argv[2], sys.argv[3]
rows = [json.loads(line) for line in open(path)]
res = []
for r in rows:
    body = {"model": "kev-latest", "state": r["state"],
            "questions": {k: {kk: vv for kk, vv in q.items() if kk != "label"} for k, q in r["questions"].items()}}
    req = urllib.request.Request(url.rstrip("/") + "/v1/systemone", data=json.dumps(body).encode(),
                                 headers={"content-type": "application/json"})
    ans = json.loads(urllib.request.urlopen(req, timeout=180).read())["answers"]
    row = {"id": r.get("id")}
    for k, q in r["questions"].items():
        a = ans[k]
        if q["type"] == "noul":
            row[k] = {"y": q["label"], "p": float(a["noul"])}
        elif q["type"] == "choice":
            probs = a["probabilities"]
            row[k] = {"y": q["label"], "pred": max(probs, key=probs.get), "probs": probs}
        else:
            probs = a["probabilities"]
            row[k] = {"y": q["label"], "pred": int(max(probs, key=probs.get)), "exp": float(a["score"])}
    res.append(row)


def noul_metrics(k, th):
    xs = [x[k] for x in res]
    tp = sum(1 for x in xs if x["y"] and x["p"] >= th)
    fp = sum(1 for x in xs if not x["y"] and x["p"] >= th)
    fn = sum(1 for x in xs if x["y"] and x["p"] < th)
    return {"acc": round(sum((x["p"] >= th) == bool(x["y"]) for x in xs) / len(xs), 3), "positives": tp + fn,
            "recall": round(tp / (tp + fn), 3) if tp + fn else None,
            "precision": round(tp / (tp + fp), 3) if tp + fp else None,
            "brier": round(sum((x["p"] - float(bool(x["y"]))) ** 2 for x in xs) / len(xs), 4)}


metrics = {"n": len(res)}
for k, q in rows[0]["questions"].items():
    if q["type"] == "noul":
        metrics[k] = noul_metrics(k, 0.6 if k == "major_negative" else 0.5)
    elif q["type"] == "choice":
        xs = [x[k] for x in res]
        m = {"acc": round(sum(x["y"] == x["pred"] for x in xs) / len(xs), 3)}
        if k == "outlook":
            pp = [x for x in xs if x["pred"] == "clearly_positive"]
            m["positive_precision"] = round(sum(x["y"] == "clearly_positive" for x in pp) / len(pp), 3) if pp else None
            m["positive_predicted"] = len(pp)
        metrics[k] = m
    else:
        xs = [x[k] for x in res]
        metrics[k] = {"acc": round(sum(x["y"] == x["pred"] for x in xs) / len(xs), 3),
                      "within1": round(sum(abs(x["y"] - x["pred"]) <= 1 for x in xs) / len(xs), 3),
                      "mae": round(sum(abs(x["y"] - x["exp"]) for x in xs) / len(xs), 3)}
json.dump({"metrics": metrics, "rows": res}, open(out, "w"), indent=1)
print(json.dumps(metrics))

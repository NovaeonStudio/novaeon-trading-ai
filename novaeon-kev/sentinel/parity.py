"""Compare two Sentinel endpoints answer by answer on the held-out sets (reference = production bf16 path).
Usage: python parity.py <ref_url> <cand_url> out.json"""
import json, sys, time, urllib.request

ref, cand, out = sys.argv[1:4]
rows = [json.loads(l) for f in ("data/heldout.jsonl", "data/heldout-r2.jsonl") for l in open(f)]


def ask(url, r):
    body = {"model": "kev-latest", "state": r["state"],
            "questions": {k: {kk: vv for kk, vv in q.items() if kk != "label"} for k, q in r["questions"].items()}}
    t = time.time()
    req = urllib.request.Request(url + "/v1/systemone", data=json.dumps(body).encode(),
                                 headers={"content-type": "application/json"})
    a = json.loads(urllib.request.urlopen(req, timeout=300).read())["answers"]
    return float(a["major_negative"]["noul"]), a["outlook"]["probabilities"], time.time() - t


res = []
for i, r in enumerate(rows):
    pn0, po0, _ = ask(ref, r)
    pn1, po1, dt = ask(cand, r)
    res.append({"y_neg": r["questions"]["major_negative"]["label"], "y_out": r["questions"]["outlook"]["label"],
                "pn": [pn0, pn1], "cp": [po0.get("clearly_positive", 0), po1.get("clearly_positive", 0)],
                "arg": [max(po0, key=po0.get), max(po1, key=po1.get)], "dt": dt})
    if i % 50 == 0:
        print(f"{i}/{len(rows)}", flush=True)


def m(i, veto=0.3, lev2=0.5):
    lev = [x for x in res if x["cp"][i] >= lev2]
    return {"bad_news_caught": sum(1 for x in res if x["y_neg"] and x["pn"][i] >= veto),
            "bad_news_total": sum(1 for x in res if x["y_neg"]),
            "false_blocks": sum(1 for x in res if not x["y_neg"] and x["pn"][i] >= veto),
            "outlook_acc": round(sum(x["y_out"] == x["arg"][i] for x in res) / len(res), 3),
            "lev2_calls": len(lev),
            "lev2_precision": round(sum(x["y_out"] == "clearly_positive" for x in lev) / len(lev), 3) if lev else None}


summary = {"n": len(res), "ref": m(0), "cand": m(1),
           "max_abs_dp_neg": round(max(abs(x["pn"][0] - x["pn"][1]) for x in res), 4),
           "mean_abs_dp_neg": round(sum(abs(x["pn"][0] - x["pn"][1]) for x in res) / len(res), 4),
           "veto_flips@0.3": sum((x["pn"][0] >= 0.3) != (x["pn"][1] >= 0.3) for x in res),
           "lev2_flips@0.5": sum((x["cp"][0] >= 0.5) != (x["cp"][1] >= 0.5) for x in res),
           "outlook_argmax_flips": sum(x["arg"][0] != x["arg"][1] for x in res),
           "cand_sec_per_call": round(sum(x["dt"] for x in res) / len(res), 2)}
json.dump({"summary": summary, "rows": res}, open(out, "w"), indent=1)
print(json.dumps(summary, indent=1))

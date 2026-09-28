"""Validate teacher labels against their batches and build Kev training files.

Checks: every data/labels-XX.jsonl has one well-formed row per item of data/batch-XX.txt, same ids, same order.
Output: data/train.jsonl + data/heldout.jsonl (kev.data.load_records shape: bundle state/questions + `label`),
split by id (deterministic, ~18% heldout, stratified so heldout keeps its share of the rare classes).
"""
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

D = Path(__file__).parent / "data"
OUTLOOKS = {"clearly_positive", "neutral_or_mixed", "negative"}
HELDOUT_PCT = 18

bundles = {b["id"]: b for b in map(json.loads, open(D / "bundles.jsonl"))}
labels, problems = {}, []
for batch in sorted(D.glob("batch-*.txt")):
    n = batch.stem.split("-")[1]
    ids = [ln.split(" | ", 1)[0].strip() for ln in batch.read_text().splitlines() if ln.strip()]
    lf = D / f"labels-{n}.jsonl"
    if not lf.exists():
        problems.append(f"{lf.name}: missing"); continue
    rows = []
    for i, ln in enumerate(lf.read_text().splitlines()):
        if not ln.strip(): continue
        try: rows.append(json.loads(ln))
        except json.JSONDecodeError as e: problems.append(f"{lf.name}:{i + 1}: bad JSON ({e})")
    got = [r.get("id") for r in rows]
    if got != ids:
        problems.append(f"{lf.name}: {len(got)} rows vs {len(ids)} items; first mismatch "
                        f"{next(((a, b) for a, b in zip(got, ids) if a != b), 'length')}")
    for r in rows:
        if not isinstance(r.get("major_negative"), bool) or r.get("outlook") not in OUTLOOKS:
            problems.append(f"{lf.name}: {r.get('id')}: bad values {r}"); continue
        if r["major_negative"] and r["outlook"] != "negative":
            problems.append(f"{lf.name}: {r['id']}: major_negative=true but outlook={r['outlook']} (guide: must be negative)")
        if r["id"] in bundles: labels[r["id"]] = r
        else: problems.append(f"{lf.name}: unknown id {r['id']}")

print("labeled", len(labels), "of", len(bundles), "bundles")
print("major_negative", Counter(r["major_negative"] for r in labels.values()))
print("outlook", Counter(r["outlook"] for r in labels.values()))
for p in problems: print("PROBLEM", p)
if problems and "--force" not in sys.argv:
    sys.exit("fix the problems above (or --force to build from the valid rows)")


def bucket(i: str) -> int:
    return int(hashlib.sha256(i.encode()).hexdigest(), 16) % 100


train, held = [], []
for i, r in sorted(labels.items()):
    b = bundles[i]
    q = json.loads(json.dumps(b["questions"]))
    q["major_negative"]["label"] = r["major_negative"]
    q["outlook"]["label"] = r["outlook"]
    rec = {"id": i, "state": b["state"], "questions": q}
    (held if bucket(i) < HELDOUT_PCT else train).append(rec)

for name, rows in (("train", train), ("heldout", held)):
    with open(D / f"{name}.jsonl", "w") as f:
        for rec in rows: f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    print(name, len(rows), "neg", sum(r["questions"]["major_negative"]["label"] for r in rows),
          "pos", sum(r["questions"]["outlook"]["label"] == "clearly_positive" for r in rows))

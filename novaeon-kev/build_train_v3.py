"""v3 training data: train-v2-2q.jsonl with major_negative=true records repeated NEG_WEIGHT times in total.
kev.train has no per-record weights, so bad news is upweighted by oversampling (order shuffled, seed 3)."""
import json
import random
from pathlib import Path

D = Path(__file__).parent / "data"
NEG_WEIGHT = 4
rs = [json.loads(l) for l in open(D / "train-v2-2q.jsonl")]
out = []
for r in rs:
    k = NEG_WEIGHT if r["questions"]["major_negative"]["label"] else 1
    out += [r] * k
random.Random(3).shuffle(out)
with open(D / "train-v3-2q.jsonl", "w") as f:
    for r in out:
        f.write(json.dumps(r, ensure_ascii=False) + "\n")
n = sum(r["questions"]["major_negative"]["label"] for r in out)
print(f"train-v3-2q: {len(out)} records, major_negative true {n} ({n/len(out):.1%}); v2 had 115/2181 (5.3%)")

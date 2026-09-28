"""v2 training data: round 1 (labels-00..20 + labels2-00..20) and round 2 (labels-21..44), six questions each.
Question wording = questions_v2.questions(TICKER), identical to what the live strategy sends (ticker only).
Split: round-1 ids keep round 1's hash split (the fixed 248-item test); round-2 ids use the same hash rule.
Output: data/train-v2.jsonl, data/heldout-v2.jsonl (round-1 test, 6 Qs), data/heldout-r2.jsonl (round-2 test, live-shaped).
data/heldout.jsonl (2 Qs) stays untouched for the kev-9b / v1 / v2 comparison."""
import hashlib
import json
from pathlib import Path

from questions_v2 import questions

D = Path(__file__).parent / "data"
HELDOUT_PCT = 18


def bucket(i: str) -> int:
    return int(hashlib.sha256(i.encode()).hexdigest(), 16) % 100


def rows(pattern: str) -> dict:
    return {r["id"]: r for f in sorted(D.glob(pattern)) for r in map(json.loads, filter(str.strip, open(f)))}


lab1, lab1b = rows("labels-[01][0-9].jsonl") | rows("labels-20.jsonl"), rows("labels2-*.jsonl")
lab2 = {i: r for i, r in rows("labels-[2-4][0-9].jsonl").items() if "-v2-" in i}
b1 = {b["id"]: b for b in map(json.loads, open(D / "bundles.jsonl"))}
b2 = {b["id"]: b for b in map(json.loads, open(D / "bundles-v2.jsonl"))}
assert set(lab1) == set(b1) == set(lab1b) and set(lab2) == set(b2), "labels and bundles do not line up"


def record(b: dict, lab: dict) -> dict:
    q = questions(b["coin"])
    q["major_negative"]["label"] = lab["major_negative"]
    q["outlook"]["label"] = lab["outlook"]
    q["event_type"]["label"] = lab["event_type"]
    q["impact"]["label"] = int(lab["impact"])
    q["relevant"]["label"] = lab["relevant"]
    q["stale"]["label"] = lab["stale"]
    return {"id": b["id"], "state": b["state"], "questions": q}


train, held1, held2 = [], [], []
for i, b in sorted(b1.items()):
    (held1 if bucket(i) < HELDOUT_PCT else train).append(record(b, {**lab1[i], **lab1b[i]}))
for i, b in sorted(b2.items()):
    (held2 if bucket(i) < HELDOUT_PCT else train).append(record(b, lab2[i]))
for name, rs in (("train-v2", train), ("heldout-v2", held1), ("heldout-r2", held2)):
    with open(D / f"{name}.jsonl", "w") as f:
        for r in rs:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(name, len(rs))
old = {json.loads(l)["id"] for l in open(D / "heldout.jsonl")}
assert old == {r["id"] for r in held1}, "round-1 test set changed"
print("round-1 test set identical to data/heldout.jsonl:", len(old))

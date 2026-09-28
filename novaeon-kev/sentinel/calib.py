"""Calibration rows for Sentinel quantization, built exactly like the serving path builds them (kev.serve: request ->
kev.api.to_record -> model.encode(max_state=SERVE_MAX_STATE, max_branch=SERVE_MAX_BRANCH) -> kev.model.rows_of).
One calibration row = the state tokens + one question's branch tokens (the row form; kev.mlx_model.forward_rows is the
reference the served prefix form is checked against). TRAINING data only (data/train-v3-2q.jsonl) - never heldout*."""
import json
from kev.api import SystemOneRequest, to_record
from kev.model import SERVE_MAX_BRANCH, SERVE_MAX_STATE, encode, rows_of


def request_of(row):
    return SystemOneRequest(model="kev-latest", state=row["state"],
                            questions={k: {kk: vv for kk, vv in q.items() if kk != "label"} for k, q in row["questions"].items()})


def calib_rows(tok, path="data/train-v3-2q.jsonl"):
    """-> list of {"rid", "q", "keys", "ids", "state_len", "decide", "opts"} (decide/opts index into ids)."""
    out = []
    for i, line in enumerate(open(path)):
        row = json.loads(line)
        assert "heldout" not in path
        rec, meta = to_record(request_of(row))
        enc = encode(tok, rec, max_state=SERVE_MAX_STATE, max_branch=SERVE_MAX_BRANCH, option_isolation=False)
        S, _, rows = rows_of(enc)
        for m, r in zip(meta, rows):
            out.append({"rid": i, "q": m["id"], "keys": m["keys"], "ids": S + r["ids"], "state_len": len(S),
                        "decide": len(S) + r["decide"], "opts": [len(S) + o for o in r["opts"]]})
    return out

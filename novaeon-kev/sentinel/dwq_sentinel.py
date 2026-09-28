"""DWQ for Novaeon Sentinel: tune a quantized package's scales/biases so its FINAL HIDDEN STATES (what the pointer head
reads; the LM head is not used) match the unquantized bf16 merged model on calibration rows built exactly like serving
builds them (sentinel/calib.py; TRAINING data only).

Adapted from mlx_lm/quant/dwq.py (same idea: only the affine scales/biases of the <8-bit layers are trainable, fp32 master
copy, Adam) but with a hidden-state target instead of LM-head logits:
  loss = relMSE(h over all tokens) + w_read * relMSE(h at <decide>/</opt> positions) + w_head * KL(head_T || head_S)
where relMSE = mean ||h_S - h_T||^2 / mean ||h_T||^2 and the head KL uses the checkpoint's frozen pointer head (T = 1).

  targets:  python sentinel/dwq_sentinel.py targets --run runs/novaeon-kev-9b-crypto-v3 --out runs/sentinel-dwq-targets
            (bf16 teacher = base + LoRA merged exactly like kev.checkpoint._load_mlx / production :8010; ~17 GB; run alone)
  train:    python sentinel/dwq_sentinel.py train --student runs/sentinel-mlx-q4 --targets runs/sentinel-dwq-targets
                --out runs/sentinel-mlx-q4dwq [--records 1000 --lr 1e-6 ...]
  eval:     python sentinel/dwq_sentinel.py eval --student <package> --targets runs/sentinel-dwq-targets
            (decision flips vs the teacher on the reserved TRAIN validation records; the held-out sets are for parity.py)
"""
import argparse, json, shutil, sys, time
from pathlib import Path

import mlx.core as mx
import mlx.nn as nn
import mlx.optimizers as optim
import numpy as np
from mlx.utils import tree_flatten, tree_map
from mlx_lm.utils import load_model
from transformers import AutoTokenizer

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import os
if os.environ.get("KEV_DIR"): sys.path.insert(0, os.environ["KEV_DIR"])   # a Kev checkout, if Kev is not installed
try:
    import kev  # noqa: F401
except ImportError:
    sys.exit("Kev is not importable. Install it (git clone https://github.com/jaredpalmer/kev && uv pip install -e ./kev) "
             "or set KEV_DIR=/path/to/kev.")
from kev.checkpoint import read_meta, resolve_run  # noqa: E402
from kev.mlx_model import merge_lora  # noqa: E402
from sentinel.calib import calib_rows  # noqa: E402

import subprocess
import mlx_lm.models.gated_delta as _gd

_ops = _gd.gated_delta_ops
DELTA_CHUNK = 128


def chunked_gated_delta_ops(q, k, v, g, beta, state=None, mask=None):
    """Training path of the Gated DeltaNet recurrence (the Metal kernel has no VJP, so mlx-lm runs a per-token op loop that
    keeps every step's [B, Hv, Dv, Dk] state for the backward pass: ~2 MB per token per row per layer). Same math, cut into
    DELTA_CHUNK-token pieces under mx.checkpoint, so the backward keeps one state per chunk and recomputes the rest."""
    T = q.shape[1]
    if T <= DELTA_CHUNK: return _ops(q, k, v, g, beta, state, mask)
    if state is None:
        state = mx.zeros((q.shape[0], v.shape[-2], v.shape[-1], q.shape[-1]), dtype=mx.float32)
    ys = []
    for t in range(0, T, DELTA_CHUNK):
        sl = slice(t, t + DELTA_CHUNK)
        m = None if mask is None else mask[:, sl]
        y, state = mx.checkpoint(lambda a, b, c, d, e, s: _ops(a, b, c, d, e, s, m))(q[:, sl], k[:, sl], v[:, sl], g[:, sl], beta[:, sl], state)
        ys.append(y)
    return mx.concatenate(ys, axis=1), state


def mem_used():
    """GB in use on this Mac, printed by the command in SENTINEL_MEM_USED_CMD; -1 = unknown (no pausing)."""
    cmd = os.environ.get("SENTINEL_MEM_USED_CMD")
    if not cmd: return -1.0
    try: return float(subprocess.run(cmd.split(), capture_output=True, text=True).stdout.strip())
    except Exception: return -1.0


def mem_guard(limit=88.0, log=print):
    """Pause (sleep + recheck) while the whole Mac is above `limit` GB in use (needs SENTINEL_MEM_USED_CMD)."""
    waited = 0
    while True:
        u = mem_used()
        if u < 0 or u <= limit: return u
        if waited % 300 == 0: log(f"mem-used {u:.1f} GB > {limit} GB: pausing", flush=True)
        time.sleep(30); waited += 30


N_VAL = 120   # records reserved (from TRAINING data) for validation; fixed permutation below


def split(n_records, seed=0):
    perm = np.random.RandomState(seed).permutation(n_records).tolist()
    return perm[N_VAL:], perm[:N_VAL]


def by_record(rows):
    rec = {}
    for r in rows: rec.setdefault(r["rid"], []).append(r)
    return rec


class Head:
    """kev.model.PointerHead in MLX (fp32, eval, temperature T): logits = k(h_opts) . q(h_decide) / sqrt(dp) / T."""
    def __init__(self, sd, temperature=1.0):
        f = lambda t: mx.array(t.float().numpy())
        self.qw, self.qb, self.kw, self.kb = f(sd["q.weight"]), f(sd["q.bias"]), f(sd["k.weight"]), f(sd["k.bias"])
        self.scale = 1 / np.sqrt(self.qw.shape[0]); self.T = temperature

    def __call__(self, h_dec, h_opts):
        q = h_dec.astype(mx.float32) @ self.qw.T + self.qb
        k = h_opts.astype(mx.float32) @ self.kw.T + self.kb
        return (k @ q) * self.scale / self.T


def batch_ids(rows, pad):
    L = max(len(r["ids"]) for r in rows)
    return mx.array([r["ids"] + [pad] * (L - len(r["ids"])) for r in rows], dtype=mx.int32)


def teacher(run):
    meta = read_meta(Path(run))
    base = Path(resolve_run(f"{meta.base}@{meta.base_revision or ''}"))
    lm, _ = load_model(base, lazy=True)
    lm.language_model.lm_head = nn.Identity()
    n = merge_lora(lm, Path(run))
    print(f"teacher: {meta.base} bf16 + {n} merged LoRA tensors", flush=True)
    return lm.language_model.model, meta, base


def cmd_targets(a):
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    text, meta, base = teacher(a.run)
    tok = AutoTokenizer.from_pretrained(base)   # the base tokenizer, as production loads it (kev.checkpoint.load)
    pad = tok.pad_token_id if tok.pad_token_id is not None else 0
    rows = calib_rows(tok, a.data)
    recs = by_record(rows)
    head = Head(meta.head, meta.temperature)
    mx.set_cache_limit(512 * 1024**2)
    t0 = time.time(); probs = {}
    for n, (rid, rr) in enumerate(recs.items()):
        f = out / f"{rid:05d}.safetensors"
        if not f.exists():
            h = text(batch_ids(rr, pad)); mx.eval(h)
            save = {}
            for i, r in enumerate(rr):
                hi = h[i, : len(r["ids"])]
                save[f"h{i}"] = hi
                probs[f"{rid}:{r['q']}"] = np.asarray(mx.softmax(head(hi[r["decide"]], hi[mx.array(r["opts"])]), -1)).tolist()
            mx.save_safetensors(str(f), save)
        if n % 100 == 0: print(f"{n}/{len(recs)} {time.time() - t0:.0f}s", flush=True)
    (out / "teacher_probs.json").write_text(json.dumps(probs))
    (out / "meta.json").write_text(json.dumps({"run": str(a.run), "data": a.data, "records": len(recs), "rows": len(rows)}))
    print("done", flush=True)


def load_student(pkg):
    lm, cfg = load_model(Path(pkg), lazy=True, strict=False)
    lm.language_model.lm_head = nn.Identity()
    mx.eval(lm.parameters())
    return lm, lm.language_model.model


def val_stats(text, head, recs, val, tdir, pad):
    """relMSE, head KL and decision flips (veto@0.3, lev2@0.5, outlook argmax) vs the teacher on the val records."""
    text.eval()
    mse, kl, flips, n = [], [], {"veto": 0, "lev2": 0, "argmax": 0}, 0
    dneg, dcp = [], []
    for rid in val:
        rr = recs[rid]; T = mx.load(str(tdir / f"{rid:05d}.safetensors"))
        h = text(batch_ids(rr, pad))
        for i, r in enumerate(rr):
            hs, ht = h[i, : len(r["ids"])].astype(mx.float32), T[f"h{i}"].astype(mx.float32)
            mse.append(((hs - ht) ** 2).sum(-1).mean().item() / (ht ** 2).sum(-1).mean().item())
            o = mx.array(r["opts"])
            ps, pt = mx.softmax(head(hs[r["decide"]], hs[o]), -1), mx.softmax(head(ht[r["decide"]], ht[o]), -1)
            kl.append((pt * (mx.log(pt + 1e-12) - mx.log(ps + 1e-12))).sum().item())
            ps, pt = np.asarray(ps), np.asarray(pt)
            if r["q"] == "major_negative":
                flips["veto"] += (ps[1] >= .3) != (pt[1] >= .3); dneg.append(abs(ps[1] - pt[1]))
            else:
                j = r["keys"].index("clearly_positive")
                flips["lev2"] += (ps[j] >= .5) != (pt[j] >= .5); dcp.append(abs(ps[j] - pt[j]))
                flips["argmax"] += int(ps.argmax() != pt.argmax())
    text.train()
    return {"relmse": round(float(np.mean(mse)), 5), "head_kl": round(float(np.mean(kl)), 5), **{k: int(v) for k, v in flips.items()},
            "mean_dp_neg": round(float(np.mean(dneg)), 4), "mean_dp_cp": round(float(np.mean(dcp)), 4)}


def setup(a):
    tdir = Path(a.targets)
    lm, text = load_student(a.student)
    tok = AutoTokenizer.from_pretrained(a.student)
    pad = tok.pad_token_id if tok.pad_token_id is not None else 0
    recs = by_record(calib_rows(tok, json.loads((tdir / "meta.json").read_text())["data"]))
    meta = read_meta(Path(json.loads((tdir / "meta.json").read_text())["run"]))
    head = Head(meta.head, 1.0)   # KL on raw logits (the checkpoint temperature is 1.0 anyway)
    train, val = split(len(recs))
    return lm, text, tok, pad, recs, head, train, val, tdir


def cmd_eval(a):
    lm, text, tok, pad, recs, head, train, val, tdir = setup(a)
    print(json.dumps(val_stats(text, head, recs, val, tdir, pad)))


def cmd_train(a):
    mem_guard(a.mem_cap)
    lm, text, tok, pad, recs, head, train, val, tdir = setup(a)
    from mlx_lm.tuner.trainer import grad_checkpoint
    text.freeze()
    def unfreeze(_, m):
        if hasattr(m, "bits") and hasattr(m, "group_size") and getattr(m, "mode", "affine") == "affine" and m.bits < 8:
            m.unfreeze(keys=["scales", "biases"], recurse=False)
    text.apply_to_modules(unfreeze)
    if not a.train_embed: text.embed_tokens.freeze()
    if a.no_bias:
        text.apply_to_modules(lambda _, m: m.freeze(keys=["biases"], recurse=False) if hasattr(m, "bits") and "biases" in m.trainable_parameters() else None)
    text.train()
    grad_checkpoint(text.layers[0])
    p0 = tree_map(lambda x: x.astype(mx.float32), text.trainable_parameters())
    # --param rel: train u with scales = s0 * (1 + u_s), biases = b0 + |s0| * u_b (updates in units of each group's
    # quantization step, so Adam's per-parameter step means the same thing for every group); abs = raw values (mlx-lm DWQ)
    s0 = {}
    for k, v in tree_flatten(p0):
        if k.endswith(".scales"): s0[k[: -len(".scales")]] = mx.abs(v)
    flat0 = dict(tree_flatten(p0))
    def materialize(u):
        if a.param == "abs": return u
        out = []
        for k, v in tree_flatten(u):
            stem, leaf = k.rsplit(".", 1)
            out.append((k, flat0[k] * (1 + v) if leaf == "scales" else flat0[k] + s0[stem] * v))
        from mlx.utils import tree_unflatten
        return tree_unflatten(out)
    params = p0 if a.param == "abs" else tree_map(mx.zeros_like, p0)
    print(f"trainable {sum(v.size for _, v in tree_flatten(params)) / 1e6:.1f}M", flush=True)
    _gd.gated_delta_ops = chunked_gated_delta_ops
    mx.set_memory_limit(int(a.mem_limit * 1024**3)); mx.set_cache_limit(512 * 1024**2)
    order = [train[i] for i in np.random.RandomState(a.seed).permutation(len(train))][: a.records][a.skip:]   # --skip: resume (student = the saved package) past the records already trained on
    if a.batch1:   # one question row per step, rows longer than --max-len skipped (memory: the job must stay <= ~12 GB)
        order = [(rid, j) for rid in order for j in range(len(recs[rid])) if len(recs[rid][j]["ids"]) <= a.max_len]
    else:
        order = [(rid, None) for rid in order]
    order = order[a.skip_rows:]   # resume inside the row order (steps already taken after --skip records)
    steps = a.skip + a.skip_rows + a.epochs * len(order)
    print(f"{len(order)} steps from {a.skip}", flush=True)
    sched = optim.cosine_decay(a.lr, steps, a.lr * 0.1) if a.cosine else a.lr
    opt = optim.Adam(learning_rate=sched, bias_correction=True)

    def loss_fn(p, x, rr, T):
        text.update(tree_map(lambda v: v.astype(mx.bfloat16), materialize(p)))
        h = text(x).astype(mx.float32)
        tot, parts = 0.0, []
        for i, r in enumerate(rr):
            hs, ht = h[i, : len(r["ids"])], T[f"h{i}"].astype(mx.float32)
            assert ht.shape[0] == len(r["ids"])
            norm = (ht ** 2).sum(-1).mean()
            m_all = ((hs - ht) ** 2).sum(-1).mean() / norm
            idx = mx.array([r["decide"], *r["opts"]])
            m_read = ((hs[idx] - ht[idx]) ** 2).sum(-1).mean() / (ht[idx] ** 2).sum(-1).mean()
            zs, zt = head(hs[r["decide"]], hs[idx[1:]]), head(ht[r["decide"]], ht[idx[1:]])
            pt = mx.softmax(zt, -1)
            kl = (pt * (mx.log(pt + 1e-12) - (zs - mx.logsumexp(zs)))).sum()
            tot = tot + m_all + a.w_read * m_read + a.w_head * kl
            lo = lambda z: mx.clip(z[1] - z[0], -6.0, 6.0)
            neg = (lo(zs) - lo(zt)) ** 2 if r["q"] == "major_negative" else mx.array(0.0)
            if r["q"] == "major_negative" and a.w_neg:
                # veto side: squared log-odds error of p(true), both clipped to [-6, 6] (p in [.0025, .9975]) so confidently
                # clear rows cost nothing and rows anywhere near the 0.3 threshold weigh in log-odds, not in probability
                tot = tot + a.w_neg * neg
            if r["q"] != "major_negative" and "clearly_positive" in r["keys"] and a.w_cp:
                # leverage side: the same clipped log-odds error for p(clearly_positive) (2x leverage at >= 0.5)
                j = r["keys"].index("clearly_positive")
                lcp = lambda z: mx.clip(z[j] - mx.logsumexp(mx.concatenate([z[:j], z[j + 1:]])), -6.0, 6.0)
                cp = (lcp(zs) - lcp(zt)) ** 2
                tot = tot + a.w_cp * cp
                neg = neg + cp   # logged in the same column (neg rows: veto log-odds, outlook rows: lev2 log-odds)
            parts.append(mx.stack([m_all, m_read, kl, neg]))
        return tot / len(rr), mx.stack(parts).mean(0)

    vg = mx.value_and_grad(loss_fn)
    from mlx.utils import tree_unflatten
    st = {"t": 0, "m": {}, "v": {}}

    def adam_inplace(p, g, b1=0.9, b2=0.999, eps=1e-8, chunk=24):
        """Adam (bias-corrected, as optim.Adam) applied leaf by leaf, evaluated in chunks, so old and new copies of the
        parameters and moments never coexist in full (optim.apply_gradients briefly doubles ~2.6 GB)."""
        st["t"] += 1; t = st["t"]; lr = a.lr
        c1, c2 = 1 - b1 ** t, 1 - b2 ** t
        flat, gf = dict(tree_flatten(p)), dict(tree_flatten(g))
        keys = list(flat)
        for i in range(0, len(keys), chunk):
            out = []
            for k in keys[i:i + chunk]:
                gk = gf.pop(k)
                m = b1 * st["m"].get(k, mx.zeros_like(gk)) + (1 - b1) * gk
                v = b2 * st["v"].get(k, mx.zeros_like(gk)) + (1 - b2) * gk * gk
                st["m"][k], st["v"][k] = m, v
                flat[k] = flat[k] - lr * (m / c1) / (mx.sqrt(v / c2) + eps)
                out += [m, v, flat[k]]
            mx.eval(out)
        return tree_unflatten(list(flat.items()))
    log = open(a.out + ".trainlog.jsonl", "a")
    v0 = val_stats(text, head, recs, val[: a.val_records], tdir, pad)
    print("val@0", json.dumps(v0), flush=True); log.write(json.dumps({"step": 0, "val": v0}) + "\n"); log.flush()
    best = (v0["relmse"], 0); t0 = time.time(); run = []
    step = a.skip + a.skip_rows; t0s = step
    for ep in range(a.epochs):
        for rid, j in order:
            rr = recs[rid]; T = mx.load(str(tdir / f"{rid:05d}.safetensors"))
            if j is not None: rr, T = [rr[j]], {"h0": T[f"h{j}"]}
            if step % 10 == 0: mem_guard(a.mem_cap)
            (l, parts), g = vg(params, batch_ids(rr, pad), rr, T)
            mx.eval(l, parts, g)
            params = adam_inplace(params, g)
            del g
            run.append(np.asarray(parts)); step += 1
            if step % a.log_every == 0:
                r = np.mean(run, 0); run = []
                print(f"step {step}/{steps} relmse {r[0]:.5f} read {r[1]:.5f} kl {r[2]:.5f} lo2 {r[3]:.4f} "
                      f"{(time.time() - t0) / (step - t0s):.2f}s/step peak {mx.get_peak_memory() / 1e9:.1f}GB mem-used {mem_used():.1f}GB", flush=True)
            if step % a.val_every == 0 or step == steps:
                text.update(tree_map(lambda v: v.astype(mx.bfloat16), materialize(params)))
                v = val_stats(text, head, recs, val[: a.val_records], tdir, pad)
                print(f"val@{step}", json.dumps(v), flush=True)
                log.write(json.dumps({"step": step, "val": v}) + "\n"); log.flush()
                if not a.no_save: save_pkg(lm, text, materialize(params), a, step)
    print("done", flush=True)


def save_pkg(lm, text, params, a, step):
    """Write a complete serveable package (same layout as build_mlx.py) with the tuned scales/biases."""
    text.update(tree_map(lambda v: v.astype(mx.bfloat16), params))
    out, src = Path(a.out), Path(a.student)
    out.mkdir(parents=True, exist_ok=True)
    weights = {k: v for k, v in tree_flatten(lm.parameters()) if k.startswith("language_model.model.")}
    mx.save_safetensors(str(out / "model.safetensors"), weights, metadata={"format": "mlx"})
    cfg = json.loads((src / "config.json").read_text())
    cfg["sentinel"] = {**cfg["sentinel"], "recipe": cfg["sentinel"].get("recipe", "uniform").split("+")[0] + "+dwq-hidden",
                       "dwq": {"student": str(src), "targets": a.targets, "step": step, "records": a.records, "epochs": a.epochs,
                               "skip": a.skip, "skip_rows": a.skip_rows, "lr": a.lr, "param": a.param, "no_bias": a.no_bias, "w_read": a.w_read, "w_head": a.w_head, "w_neg": a.w_neg, "w_cp": a.w_cp, "batch1": a.batch1, "max_len": a.max_len, "train_embed": a.train_embed}}
    (out / "config.json").write_text(json.dumps(cfg, indent=1))
    for f in src.iterdir():
        if f.name not in ("config.json", "model.safetensors") and not (out / f.name).exists(): shutil.copy(f, out / f.name)
    print(f"saved {out} @ step {step}", flush=True)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    sp = ap.add_subparsers(dest="cmd", required=True)
    t = sp.add_parser("targets"); t.add_argument("--run", required=True); t.add_argument("--out", required=True)
    t.add_argument("--data", default="data/train-v3-2q.jsonl")
    for name in ("train", "eval"):
        p = sp.add_parser(name); p.add_argument("--student", required=True); p.add_argument("--targets", required=True)
        p.add_argument("--val-records", type=int, default=N_VAL)
    tr = sp.choices["train"]
    tr.add_argument("--out", required=True); tr.add_argument("--records", type=int, default=1000)
    tr.add_argument("--epochs", type=int, default=1); tr.add_argument("--lr", type=float, default=1e-6)
    tr.add_argument("--cosine", action="store_true"); tr.add_argument("--w-read", type=float, default=1.0)
    tr.add_argument("--w-head", type=float, default=1.0); tr.add_argument("--train-embed", action="store_true")
    tr.add_argument("--val-every", type=int, default=250); tr.add_argument("--seed", type=int, default=0)
    tr.add_argument("--log-every", type=int, default=25)
    tr.add_argument("--param", choices=["abs", "rel"], default="abs"); tr.add_argument("--no-bias", action="store_true")
    tr.add_argument("--no-save", action="store_true"); tr.add_argument("--skip", type=int, default=0)
    tr.add_argument("--skip-rows", type=int, default=0)
    tr.add_argument("--batch1", action="store_true"); tr.add_argument("--max-len", type=int, default=512)
    tr.add_argument("--w-neg", type=float, default=0.0); tr.add_argument("--w-cp", type=float, default=0.0); tr.add_argument("--mem-limit", type=float, default=9.0)
    tr.add_argument("--mem-cap", type=float, default=88.0)
    a = ap.parse_args()
    assert "heldout" not in getattr(a, "data", "")
    {"targets": cmd_targets, "train": cmd_train, "eval": cmd_eval}[a.cmd](a)

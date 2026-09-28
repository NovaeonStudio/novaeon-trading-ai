"""Serve a Novaeon Sentinel MLX package (built by build_mlx.py) with Kev's server (`kev.serve`, same /v1/systemone API).

The package already contains the merged, quantized text backbone, the tokenizer and the pointer head, so nothing else is
downloaded and no LoRA is merged at load time. Usage: python -m sentinel.serve --run <package_dir> --port 8010
"""
import json, os
from pathlib import Path

import kev.checkpoint as ck
import mlx.core as mx
import mlx.nn as nn
from kev.mlx_model import MLXDecisionModel
from kev.model import PointerHead, pad_id, rows_of, rows_per_pass

# opt-in cap on question rows per branch pass on Metal (memory bound for 8 GB Macs). 0 (default) = kev's own split (all
# questions of a request in one pass). Splitting changes batch shapes, so answers can move by float noise (<= ~0.03 on the
# 4-bit build for 6-question requests); 2-question requests (the live bot) are unaffected by a cap of 2.
ROWS_PER_PASS = int(os.environ.get("SENTINEL_ROWS_PER_PASS", "0"))
from mlx_lm.utils import load_model
from transformers import AutoTokenizer


def _is_package(path) -> bool:
    cfg = Path(path) / "config.json"
    return cfg.exists() and "sentinel" in json.loads(cfg.read_text())


class SentinelMLX(MLXDecisionModel):
    """MLXDecisionModel over a text-only (and possibly quantized) package: loads without the vision tower / LM head and
    sizes the pointer head from the config (a quantized embedding's weight is packed, so its shape is not the width)."""

    def __init__(self, package_dir, pad, head_dim=256):
        cfg = json.loads((Path(package_dir) / "config.json").read_text())
        # lazy + drop the LM head before anything is materialized: the package has no head weights, and a freshly
        # initialized one would cost ~4 GB (fp32, 248k vocab) for nothing - Sentinel only reads hidden states.
        self.lm, _ = load_model(Path(package_dir), lazy=True, strict=False)
        self.lm.language_model.lm_head = nn.Identity()
        mx.eval(self.lm.parameters())
        mx.clear_cache()
        mx.set_cache_limit(256 * 1024**2)   # keep freed Metal buffers small (matters on 8 GB Macs)
        self.text = self.lm.language_model.model
        self.pad_id = pad
        self.head = PointerHead(cfg["text_config"]["hidden_size"], dp=head_dim).eval()
        self.bits = cfg.get("quantization", {}).get("bits", 16)

    @property
    def dtype(self):
        return f"mlx-q{self.bits}" if self.bits < 16 else "bf16"

    def _branch_logits(self, enc, cache):
        """kev.mlx_model's branch pass; with SENTINEL_ROWS_PER_PASS=n at most n question rows (and state-cache copies) per
        forward pass. kev runs every question of a request in one pass (budget 16k tokens), so a 6-question request holds
        6 cache copies and 6 rows of activations at once: +1.8 GB transient on the 4-bit build (served peak ~7.6 GB on the
        parity workload; ~0.95 GB with n=2). The rows are independent, so the split only changes float noise."""
        _, _, rows = rows_of(enc)
        chunk = rows_per_pass([r["ids"] for r in rows], enc["seg"].count(0))
        if ROWS_PER_PASS > 0: chunk = max(1, min(ROWS_PER_PASS, chunk))
        out = []
        for start in range(0, len(rows), chunk):
            part = rows[start:start + chunk]
            batch = [type(c).merge([c] * len(part)) for c in cache]
            h = self._hidden([r["ids"] for r in part], batch)
            out += [self._logits(h[i], r["decide"], r["opts"]) for i, r in enumerate(part)]
            del h, batch
        return out


_orig_hybrid, _orig_load, _orig_backend = ck.Checkpoint.hybrid_base, ck.Checkpoint.load, ck.Checkpoint.backend


def hybrid_base(self):
    return True if _is_package(self.path) else _orig_hybrid(self)


def backend(self, device, opts=ck.LoadOptions()):
    return "mlx" if _is_package(self.path) else _orig_backend(self, device, opts)


def load(self, device, opts=ck.LoadOptions()):
    if not _is_package(self.path):
        return _orig_load(self, device, opts)
    tok = AutoTokenizer.from_pretrained(self.path)
    m = SentinelMLX(self.path, pad_id(tok), head_dim=self.meta.head_dim)
    m.head.load_state_dict(self.meta.head); m.eval()
    m.head.temperature = self.meta.temperature if opts.temperature is None else opts.temperature
    return tok, m


ck.Checkpoint.hybrid_base, ck.Checkpoint.backend, ck.Checkpoint.load = hybrid_base, backend, load

if __name__ == "__main__":
    from kev.serve import main
    main()

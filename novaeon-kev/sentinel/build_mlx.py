"""Build the Apple-Silicon package of Novaeon Sentinel 9B: Qwen3.5-9B-Base + the Sentinel LoRA merged (exactly as the
serving path merges it), vision tower and LM head dropped (Sentinel only reads hidden states), linear layers quantized.

Usage: python build_mlx.py <run_dir> <out_dir> --bits 4|8 [--group 64] [--recipe mixed]

--recipe mixed keeps --bits for most layers but gives 8 bits to the parts a 4-bit build hurts most: every layer in the
last eighth (the pointer head reads the final hidden state), the first eighth, and v_proj/down_proj on every third
layer in between (the llama.cpp Q4_K_M pattern, as in mlx-lm's mixed recipes).
"""
import argparse, json, shutil, sys
from pathlib import Path

import mlx.core as mx
import mlx.nn as nn
from mlx.utils import tree_flatten
from mlx_lm.utils import load_model

import os
if os.environ.get("KEV_DIR"): sys.path.insert(0, os.environ["KEV_DIR"])   # a Kev checkout, if Kev is not installed
try:
    import kev  # noqa: F401
except ImportError:
    sys.exit("Kev is not importable. Install it (git clone https://github.com/jaredpalmer/kev && uv pip install -e ./kev) "
             "or set KEV_DIR=/path/to/kev.")
from kev.checkpoint import read_meta, resolve_run  # noqa: E402
from kev.mlx_model import merge_lora  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("run"); ap.add_argument("out")
ap.add_argument("--bits", type=int, default=4); ap.add_argument("--group", type=int, default=64)
ap.add_argument("--recipe", choices=["uniform", "mixed"], default="uniform"); ap.add_argument("--high-bits", type=int, default=8)
a = ap.parse_args()
run, out = Path(a.run), Path(a.out)
meta = read_meta(run)
base = Path(resolve_run(f"{meta.base}@{meta.base_revision or ''}"))
lm, cfg = load_model(base)
n = merge_lora(lm, run)
print(f"merged {n} LoRA tensors into {meta.base}")

# only the text backbone is used: embeddings -> layers -> final norm (kev.mlx_model reads language_model.model)
text_only = lambda p: p.startswith("language_model.model.")
n_layers = len(lm.language_model.model.layers)
per_path = {}
def pred(path, m):
    if not text_only(path) or not hasattr(m, "to_quantized"): return False
    if a.recipe == "uniform": return True
    parts = path.split(".")
    idx = int(parts[3]) if len(parts) > 3 and parts[2] == "layers" and parts[3].isdigit() else None
    if idx is None: return True   # embeddings: plain lookup, low bits are fine
    e = n_layers // 8
    high = idx < e or idx >= n_layers - e or (("v_proj" in path or "down_proj" in path) and (idx - e) % 3 == 2)
    if not high: return True
    per_path[path] = {"group_size": a.group, "bits": a.high_bits}
    return per_path[path]
if a.bits < 16:
    nn.quantize(lm, group_size=a.group, bits=a.bits, class_predicate=pred)
    print(f"{len(per_path)} modules at {a.high_bits} bits" if per_path else "uniform")
weights = {k: v for k, v in tree_flatten(lm.parameters()) if text_only(k)}
out.mkdir(parents=True, exist_ok=True)
mx.save_safetensors(str(out / "model.safetensors"), weights, metadata={"format": "mlx"})
cfg = dict(cfg)
if a.bits < 16:
    cfg["quantization"] = {"group_size": a.group, "bits": a.bits, **per_path}
cfg["sentinel"] = {"text_only": True, "source_run": str(run), "bits": a.bits, "group_size": a.group, "recipe": a.recipe, "base": meta.base}
(out / "config.json").write_text(json.dumps(cfg, indent=1))
for f in base.iterdir():
    if f.name.startswith(("tokenizer", "vocab", "merges", "special_tokens", "chat_template", "generation_config")):
        shutil.copy(f, out / f.name)
shutil.copy(run / "head.pt", out / "head.pt")
size = sum(v.nbytes for v in weights.values()) / 1e9
print(f"wrote {out} ({len(weights)} tensors, {size:.2f} GB)")

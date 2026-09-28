"""Download one Novaeon Sentinel package from Hugging Face, resumable, and verify every file.

  python fetch_model.py --repo NovaeonStudio/novaeon-sentinel-9b --revision main --subfolder mlx-8bit --dest <dir>
  python fetch_model.py --repo Qwen/Qwen3.5-9B-Base --revision <commit> --hf-cache --dest <marker dir>

Files land in <dest>/<subfolder>/ (the package directory, printed as the last line). With --hf-cache the files go into
the Hugging Face cache instead (HF_HOME; the base model of the LoRA build, which Kev loads by repo id), the cache's
"main" ref is pointed at the pinned commit so an offline server finds it, and the snapshot directory is printed. An
interrupted download resumes on the next run. Every file is checked against the size and hash Hugging Face reports (sha256 for LFS/xet files, the
git blob id for small files); --pin-sha256 additionally pins model.safetensors to a hash shipped with the installer.
A verified package is remembered (.novaeon-verified-<subfolder>.json), so re-runs only re-check sizes.
"""
import argparse
import fnmatch
import hashlib
import json
import shutil
import sys
import time
from pathlib import Path

from huggingface_hub import HfApi, hf_hub_download
from huggingface_hub.hf_api import RepoFile


def log(msg):
    print(f"    {msg}", file=sys.stderr, flush=True)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(8 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def git_blob_sha1(path: Path) -> str:
    data = path.read_bytes()
    return hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()


def verify(path: Path, f: RepoFile, pin: str | None) -> str | None:
    """None if the file is intact, else the reason."""
    if not path.exists():
        return "missing"
    if path.stat().st_size != f.size:
        return f"size {path.stat().st_size} != {f.size}"
    if f.lfs is not None:
        got = sha256(path)
        if got != f.lfs.sha256:
            return f"sha256 {got[:12]} != {f.lfs.sha256[:12]}"
        if pin and got != pin:
            return f"sha256 {got[:12]} != pinned {pin[:12]}"
    elif f.blob_id and git_blob_sha1(path) != f.blob_id:
        return "git blob id mismatch"
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", required=True); ap.add_argument("--revision", default="main")
    ap.add_argument("--subfolder", default=""); ap.add_argument("--dest", required=True)
    ap.add_argument("--pin-sha256", default="")
    ap.add_argument("--hf-cache", action="store_true", help="download into the Hugging Face cache (HF_HOME)")
    ap.add_argument("--patterns", default="*.json,*.safetensors,*.pt,*.txt,*.jinja",
                    help="with --hf-cache: files to fetch (the patterns Kev's loader uses)")
    a = ap.parse_args()
    dest = Path(a.dest); dest.mkdir(parents=True, exist_ok=True)
    api = HfApi()
    commit = api.model_info(a.repo, revision=a.revision).sha
    files = [f for f in api.list_repo_tree(a.repo, path_in_repo=a.subfolder or None, revision=commit, recursive=True)
             if isinstance(f, RepoFile)]
    if a.hf_cache:
        pats = [p for p in a.patterns.split(",") if p]
        files = [f for f in files if any(fnmatch.fnmatch(Path(f.path).name, p) for p in pats)]
    if not files:
        sys.exit(f"no files under {a.repo}/{a.subfolder}@{a.revision}")
    if a.hf_cache:
        from huggingface_hub.constants import HF_HUB_CACHE
        repo_cache = Path(HF_HUB_CACHE) / ("models--" + a.repo.replace("/", "--"))
        root = repo_cache / "snapshots" / commit   # hf_hub_download(local_dir=None) puts each file here (symlink to a blob)
        pkg = root
        marker = dest / f".novaeon-verified-{a.repo.replace('/', '_')}-{commit[:12]}.json"
    else:
        root = dest
        pkg = dest / a.subfolder if a.subfolder else dest
        marker = dest / f".novaeon-verified-{a.subfolder or 'root'}.json"
    want = {f.path: f.size for f in files}
    if marker.exists():
        m = json.loads(marker.read_text())
        if m.get("commit") == commit and all((root / p).exists() and (root / p).stat().st_size == s for p, s in want.items()):
            log(f"already downloaded and verified ({commit[:10]})")
            print(pkg)
            return
    total = sum(want.values())
    have = sum((root / p).stat().st_size for p in want if (root / p).exists())
    free = shutil.disk_usage(dest).free
    if free < (total - have) + (1 << 30):
        sys.exit(f"not enough disk space: need {(total - have) / 2**30:.1f} GB + 1 GB headroom, {free / 2**30:.1f} GB free")
    log(f"{len(files)} files, {total / 2**30:.2f} GB ({a.repo}@{commit[:10]}/{a.subfolder})")
    for f in sorted(files, key=lambda f: f.size):
        path = root / f.path
        pin = a.pin_sha256 if f.path.endswith("model.safetensors") else None
        for attempt in range(1, 5):
            if path.exists() and path.stat().st_size == f.size and verify(path, f, pin) is None:
                break
            if path.exists() and path.stat().st_size == f.size:   # complete but corrupt: start this file over
                if path.is_symlink():
                    path.resolve().unlink(missing_ok=True)
                path.unlink()
            try:
                log(f"downloading {f.path} ({f.size / 2**20:.0f} MB)" + (f", attempt {attempt}" if attempt > 1 else ""))
                if a.hf_cache:
                    hf_hub_download(a.repo, f.path, revision=commit)
                else:
                    hf_hub_download(a.repo, f.path, revision=commit, local_dir=dest)
            except Exception as e:  # network hiccup: resume from the partial file
                log(f"download interrupted: {e}")
                time.sleep(min(30, 5 * attempt))
                continue
            reason = verify(path, f, pin)
            if reason is None:
                break
            log(f"{f.path} failed verification ({reason}), retrying")
            if path.is_symlink():
                path.resolve().unlink(missing_ok=True)
            path.unlink(missing_ok=True)
        else:
            sys.exit(f"could not download {f.path} intact; run the installer again to resume")
        log(f"ok {f.path}")
    if a.hf_cache:   # offline loads by repo id (no revision) read refs/main: pin it to the verified commit
        (repo_cache / "refs").mkdir(parents=True, exist_ok=True)
        (repo_cache / "refs" / "main").write_text(commit)
    marker.write_text(json.dumps({"commit": commit, "files": want}, indent=1))
    print(pkg)


if __name__ == "__main__":
    main()

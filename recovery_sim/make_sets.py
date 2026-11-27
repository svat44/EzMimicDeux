"""Build the recovery-demo dataset sets: collect raw episodes, then plan which ones go in.

Runs under recovery_sim/.venv (mujoco, numpy).

Subcommands:
  trial   --tmp <dir> [--frames 100] [--python <py>]
          small image run per mode; measures bytes per saved frame and projects the
          full raw size; writes only under <dir> and removes its own run folders.
  collect --raw <raw> [--python <py>]
          runs trial under <raw>, refuses if free space < 3x projection, then runs
          collect.py once per set with --out <raw>/<set>.
  plan    --raw <raw> --out <json>
          builds the base/control/separate/embedded plan (exact trimming) and writes JSON.
"""
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
COLLECT = HERE / "collect.py"

N_BASE = 50
N_EXTRA = 6000
# set -> (mode, seed, collect.py --frames)
SETS = {"base": ("clean", 1000, 6500), "control": ("clean", 1001, 6000),
        "separate": ("separate", 1002, 6000), "embedded": ("embedded", 1003, 6000)}
EXTRA_SETS = ("control", "separate", "embedded")
BALANCED_SETS = ("separate", "embedded")

TRIAL_MODES = ("clean", "separate", "embedded")
TRIAL_SEED = 1800          # trial seeds 1800-1802: never 100/200/300 or 1000-1003
TRIAL_FRAMES = 100
PROJECTION_MARGIN = 1.2    # covers context frames and the last episode overshooting its budget
MIN_FREE_FACTOR = 3.0


def _env():
    env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
    env["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
    return env


def _run_collect(mode, frames, seed, out, python):
    cmd = [str(python), str(COLLECT), "--mode", mode, "--frames", str(frames),
           "--seed", str(seed), "--out", str(out)]
    subprocess.run(cmd, cwd=str(HERE), env=_env(), check=True)
    return Path(out) / f"{mode}_seed{seed}"


def collect_set(name, raw_root, python=sys.executable, sets=SETS):
    """Run collect.py (with images) for one set; returns the episode folder."""
    mode, seed, frames = sets[name]
    return _run_collect(mode, frames, seed, Path(raw_root) / name, python)


def _episodes(folder):
    files = sorted(Path(folder).glob("episode_*.npz"))
    if not files:
        raise FileNotFoundError(f"no episodes in {folder}")
    return files


def _sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _info(path):
    with np.load(path) as z:
        train = np.asarray(z["train"], dtype=bool)
        shift = str(z["shift_type"])
    return {"T": int(train.shape[0]), "train": train, "shift_type": shift}


def _entry(path, root, n_frames, n_train, trimmed, frames_removed, shift_type):
    return {"file": Path(path).relative_to(root).as_posix(),
            "sha256": _sha256(path),
            "n_frames": int(n_frames),
            "n_train": int(n_train),
            "trimmed": bool(trimmed),
            "frames_removed": int(frames_removed),
            "shift_type": shift_type}


def plan_base(folder, n=N_BASE, raw_root=None):
    """First n saved episodes in name order, all frames kept."""
    root = Path(raw_root or folder)
    files = _episodes(folder)
    if len(files) < n:
        raise ValueError(f"base has {len(files)} episodes in {folder}, need {n}")
    out = []
    for p in files[:n]:
        info = _info(p)
        out.append(_entry(p, root, info["T"], info["train"].sum(), False, 0, info["shift_type"]))
    return out


def plan_extra(folder, n_train=N_EXTRA, raw_root=None):
    """Take episodes in order until their train frames total exactly n_train.

    The last one used is cut after the train frame that makes the total exact;
    context frames before that point stay.
    """
    root = Path(raw_root or folder)
    out, total = [], 0
    for p in _episodes(folder):
        if total == n_train:
            break
        info = _info(p)
        train_idx = np.flatnonzero(info["train"])
        t, T, shift = len(train_idx), info["T"], info["shift_type"]
        need = n_train - total
        if t <= need:
            out.append(_entry(p, root, T, t, False, 0, shift))
            total += t
        else:
            k = int(train_idx[need - 1]) + 1
            out.append(_entry(p, root, k, need, True, T - k, shift))
            print(f"trim: {Path(p).name} keep {k} of {T} frames, removed {T - k}")
            total += need
    if total != n_train:
        raise ValueError(f"{folder} has only {total} train frames, need {n_train}")
    return out


def make_plan(raw_root, n_base=N_BASE, n_extra=N_EXTRA, sets=SETS):
    raw_root = Path(raw_root).resolve()

    def folder(name):
        mode, seed, _ = sets[name]
        return raw_root / name / f"{mode}_seed{seed}"

    plan = {"base": plan_base(folder("base"), n_base, raw_root)}
    for name in EXTRA_SETS:
        plan[name] = plan_extra(folder(name), n_extra, raw_root)
    plan["seeds"] = {name: sets[name][1] for name in sets}

    seen = {}
    for name in ("base", *EXTRA_SETS):
        for e in plan[name]:
            if e["sha256"] in seen:
                raise ValueError(f"{e['file']} repeats {seen[e['sha256']]}")
            seen[e["sha256"]] = e["file"]
    return plan


def _counts(entries):
    return {k: sum(1 for e in entries if e["shift_type"] == k) for k in ("early", "late")}


def trial(tmp_root, frames=TRIAL_FRAMES, python=sys.executable, sets=SETS):
    tmp_root = Path(tmp_root).resolve()
    tmp_root.mkdir(parents=True, exist_ok=True)
    per_mode = {}
    for i, mode in enumerate(TRIAL_MODES):
        out = tmp_root / f"trial_{mode}"
        folder = _run_collect(mode, frames, TRIAL_SEED + i, out, python)
        files = _episodes(folder)
        nbytes = sum(p.stat().st_size for p in files)
        nframes = sum(_info(p)["T"] for p in files)
        if nframes == 0:
            raise RuntimeError(f"trial {mode} saved no frames")
        per_mode[mode] = {"bytes": nbytes, "frames": nframes,
                          "bytes_per_frame": nbytes / nframes}
        shutil.rmtree(out, ignore_errors=True)

    projected = sum(per_mode[mode]["bytes_per_frame"] * n * PROJECTION_MARGIN
                    for mode, _, n in sets.values())
    free = shutil.disk_usage(tmp_root).free
    required = MIN_FREE_FACTOR * projected
    return {"per_mode": per_mode, "projected_bytes": int(projected),
            "required_free_bytes": int(required), "free_bytes": int(free),
            "ok": free >= required}


def collect(raw_root, python=sys.executable, sets=SETS):
    raw_root = Path(raw_root).resolve()
    raw_root.mkdir(parents=True, exist_ok=True)
    trial_dir = raw_root / "_trial_tmp"
    t = trial(trial_dir, python=python, sets=sets)
    shutil.rmtree(trial_dir, ignore_errors=True)
    print(json.dumps(t, indent=2))
    if not t["ok"]:
        raise RuntimeError(f"refusing collect: free {t['free_bytes']} bytes < "
                           f"3x projected {t['projected_bytes']} bytes")
    for name in sets:
        folder = collect_set(name, raw_root, python, sets)
        print(f"collected {name}: {folder}")
    return t


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    tr = sub.add_parser("trial")
    tr.add_argument("--tmp", required=True)
    tr.add_argument("--frames", type=int, default=TRIAL_FRAMES)
    tr.add_argument("--python", default=sys.executable)

    co = sub.add_parser("collect")
    co.add_argument("--raw", required=True)
    co.add_argument("--python", default=sys.executable)

    pl = sub.add_parser("plan")
    pl.add_argument("--raw", required=True)
    pl.add_argument("--out", required=True)
    pl.add_argument("--n-base", type=int, default=N_BASE)
    pl.add_argument("--n-extra", type=int, default=N_EXTRA)

    args = p.parse_args(argv)
    if args.cmd == "trial":
        print(json.dumps(trial(args.tmp, args.frames, args.python), indent=2))
        return 0
    if args.cmd == "collect":
        collect(args.raw, args.python)
        return 0

    plan = make_plan(args.raw, args.n_base, args.n_extra)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(plan, indent=2))
    print(f"base: {len(plan['base'])} episodes")
    ok = True
    for name in EXTRA_SETS:
        entries = plan[name]
        c = _counts(entries)
        train = sum(e["n_train"] for e in entries)
        trimmed = [e for e in entries if e["trimmed"]]
        print(f"{name}: {len(entries)} episodes, train frames {train}, "
              f"early {c['early']}, late {c['late']}")
        for e in trimmed:
            print(f"  trimmed {e['file']}: removed {e['frames_removed']} frames, kept {e['n_frames']}")
        if name in BALANCED_SETS and abs(c["early"] - c["late"]) > 1:
            ok = False
            print(f"  NOT BALANCED: early and late differ by more than one")
    print(f"wrote {out}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())

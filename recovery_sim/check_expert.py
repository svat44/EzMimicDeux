"""Checks the scripted expert over seeded episodes (step 2).

Runs N attempts per mode without images, records every failure with its seed and
reason, checks behaviour rules on successful episodes, and writes one JSON per mode.
"""
import argparse
import json
import math
import statistics
import subprocess
from functools import lru_cache
from pathlib import Path

import mujoco
import numpy as np

from collect import (CARRY_BLOCK_Z, CLEARANCE, CLOSED, CONTEXT, GRIP_EMPTY, HAND_Z0,
                     MODES, OPEN, SHIFT_MAX, SHIFT_MIN, SIM_STEPS, TRIGGER_MAX,
                     TRIGGER_MIN, Episode, episode_rng, in_workspace, make_model, select)

GRIP_THRESHOLD = (OPEN + CLOSED) / 2
PASS_RATE = 0.98
SETTLE_STEPS = 200      # settle loop in Episode.__init__; the hook fires there too
REPO_DIR = Path(__file__).resolve().parent


@lru_cache(maxsize=1)
def _model():
    return make_model()


def _block_hand_contact(data, block_geoms, hand_geoms):
    blk, hand = set(block_geoms), set(hand_geoms)
    for i in range(data.ncon):
        c = data.contact[i]
        if (c.geom1 in blk and c.geom2 in hand) or (c.geom2 in blk and c.geom1 in hand):
            return True
    return False


class CheckedEpisode(Episode):
    """Episode that records block-hand contact at every physics substep and the shift clearance."""

    def __init__(self, model, rng, renderer=None, shift_type="none"):
        # Set before super().__init__: the hook also fires during the settle loop (frame -1).
        self.contacts = []          # (frame_index, substep_index)
        self.shift_clearance = None
        self.hook_calls = 0
        self._cur_frame = None
        self._k = -1
        super().__init__(model, rng, renderer=renderer, shift_type=shift_type)

    def on_substep(self):
        fi = len(self.frames) - 1
        if fi != self._cur_frame:
            self._cur_frame = fi
            self._k = -1
        self._k += 1
        self.hook_calls += 1
        if self._block_contact():
            self.contacts.append((fi, self._k))

    def shift_block(self):
        # Extra sample (len(frames)-1, SIM_STEPS): end state of the frame before the shift,
        # which the hook never sees. Test on a copy so self.data is untouched.
        d2 = mujoco.MjData(self.model)
        mujoco.mj_copyData(d2, self.model, self.data)
        mujoco.mj_forward(self.model, d2)
        real = self.data
        self.data = d2
        try:
            hit = self._block_contact()
        finally:
            self.data = real
        if hit:
            self.contacts.append((len(self.frames) - 1, SIM_STEPS))
        before, after = super().shift_block()
        dists = [mujoco.mj_geomDistance(self.model, self.data, b, h, 0.05, None)
                 for b in self.block_geoms for h in self.hand_geoms]
        self.shift_clearance = float(min(dists)) if dists else None
        return before, after


def _closed_flags(frames):
    return [float(f["action"][3]) > GRIP_THRESHOLD for f in frames]


def _closed_runs(closed):
    runs, i, n = [], 0, len(closed)
    while i < n:
        if closed[i]:
            j = i
            while j + 1 < n and closed[j + 1]:
                j += 1
            runs.append((i, j))
            i = j + 1
        else:
            i += 1
    return runs


def _hand_z(frame):
    return float(frame["state"][2]) + HAND_Z0


def _finger(frame):
    return float(frame["state"][3])


def _separate_window_ok(result, selected, closed, runs, frames):
    sf = int(result["shift_frame"])
    ts = int(selected["train_start"])
    te = int(selected["train_end"])
    if result["shift_type"] == "early":
        exp_ts = sf
    else:
        reopened = [i for i in range(sf + 1, len(closed)) if not closed[i]]
        exp_ts = reopened[0] if reopened else None
    ok = exp_ts is not None and ts == exp_ts
    if runs:
        final = runs[-1][0]
        lifted = [i for i in range(max(ts, final), len(frames))
                  if float(frames[i]["block_pos"][2]) >= CARRY_BLOCK_Z]
        ok = ok and bool(lifted) and te == lifted[0]
    else:
        ok = False
    train = np.asarray(selected["train"], dtype=bool)
    ctx = int(np.sum(~train))
    n = int(np.sum(train))
    ok = (ok and train.tolist() == [False] * ctx + [True] * n
          and ctx == min(CONTEXT, ts) and n == te - ts + 1)
    return ok


def check_behaviour(result, selected, ep, mode):
    """Return the names of violated behaviour checks (empty list if none)."""
    st = result["shift_type"]
    if st == "none":
        return []
    frames = result["frames"]
    sf = int(result["shift_frame"])
    closed = _closed_flags(frames)
    runs = _closed_runs(closed)
    bad = []

    before = np.asarray(result["block_before"], dtype=float)
    after = np.asarray(result["block_after"], dtype=float)
    dist = float(np.linalg.norm(after[:2] - before[:2]))
    if not (SHIFT_MIN <= dist <= SHIFT_MAX):
        bad.append("shift_distance")
    if not in_workspace(after[:2]):
        bad.append("shift_workspace")
    if ep.shift_clearance is None or ep.shift_clearance < CLEARANCE:
        bad.append("shift_clearance")

    if st == "early":
        tz = float(result["trigger_z"])
        crossing = False
        if 1 <= sf < len(frames):
            crossing = _hand_z(frames[sf - 1]) > tz and _hand_z(frames[sf]) <= tz
        if not (TRIGGER_MIN <= tz <= TRIGGER_MAX) or not crossing:
            bad.append("trigger_height")

        redirect_ok = False
        if 1 <= sf < len(frames):
            after_xy = np.asarray(result["block_after"], dtype=float)[:2]
            d_prev = np.linalg.norm(np.asarray(frames[sf - 1]["action"][:2], dtype=float) - after_xy)
            d_now = np.linalg.norm(np.asarray(frames[sf]["action"][:2], dtype=float) - after_xy)
            redirect_ok = bool(d_now < d_prev)
        if not redirect_ok:
            bad.append("early_redirect")

        releases = [i for i in range(1, len(closed)) if closed[i - 1] and not closed[i]]
        release = releases[-1] if releases else len(closed)
        runs_before_release = [r for r in runs if r[0] < release]
        finger_bad = bool(runs) and _finger(frames[runs[0][1]]) > GRIP_EMPTY
        if not runs or len(runs_before_release) > 1 or finger_bad:
            bad.append("early_empty_close")

        grasp_start = runs[0][0] if runs else len(frames)
        if any(sf <= f and (f < grasp_start or (f == grasp_start and k == 0))
               for f, k in ep.contacts):
            bad.append("early_contact_before_grasp")
    else:
        first_closed = runs[0][0] if runs else None
        if first_closed != sf:
            bad.append("late_shift_step")
        if not runs:
            bad.append("late_empty_close")
        else:
            a, b = runs[0]
            finger_bad = _finger(frames[b]) <= GRIP_EMPTY
            contact_bad = any((a <= f <= b) or (f == b + 1 and k == 0) for f, k in ep.contacts)
            reopen_bad = not (b + 1 < len(frames) and not closed[b + 1])
            if finger_bad or contact_bad or reopen_bad:
                bad.append("late_empty_close")

    if any(f < sf for f, _ in ep.contacts):
        bad.append("contact_before_shift")

    if mode == "separate" and not _separate_window_ok(result, selected, closed, runs, frames):
        bad.append("separate_window")
    return bad


def _late_retry_contact(result, ep):
    """Contact between the empty close and the final grasp (info only, not a violation)."""
    closed = _closed_flags(result["frames"])
    runs = _closed_runs(closed)
    if not runs:
        return False
    end = runs[0][1]
    nxt = runs[1][0] if len(runs) > 1 else len(closed)
    return any(end < fi < nxt for fi, _ in ep.contacts)


def _shift_type_for(mode, attempt):
    if mode == "clean":
        return "none"
    return "early" if attempt % 2 == 0 else "late"


def run_episode(seed, mode, attempt, shift_type):
    """One attempt. Never raises: any exception becomes a failure record."""
    base = {"seed": seed, "attempt": attempt, "shift_type": shift_type,
            "success": False, "reason": None, "train_frames": None,
            "violations": [], "trigger_z": None, "shift_hand_z": None,
            "late_retry_contact": False}
    try:
        ep = CheckedEpisode(_model(), episode_rng(seed, mode, attempt), shift_type=shift_type)
        result = ep.run(mode)
        if not result["success"]:
            base["reason"] = "task failed"
            return base
        selected = select(result, mode)
        if selected is None:
            base["reason"] = "select returned None"
            return base
        expected_hook = SETTLE_STEPS + SIM_STEPS * len(result["frames"])
        if ep.hook_calls != expected_hook:
            raise RuntimeError(f"on_substep hook fired {ep.hook_calls} times, expected {expected_hook}")
        violations = check_behaviour(result, selected, ep, mode)
        base["violations"] = violations
        base["train_frames"] = int(np.sum(selected["train"]))
        if shift_type == "early":
            base["trigger_z"] = float(result["trigger_z"])
            sf = int(result["shift_frame"])
            if 0 <= sf < len(result["frames"]):
                base["shift_hand_z"] = _hand_z(result["frames"][sf])
        base["late_retry_contact"] = shift_type == "late" and _late_retry_contact(result, ep)
        base["success"] = True
        return base
    except Exception as exc:  # any checker or expert error is a failure, not a crash
        base.update(success=False, reason=f"exception: {type(exc).__name__}: {exc}",
                    violations=[], train_frames=None, trigger_z=None,
                    shift_hand_z=None, late_retry_contact=False)
        return base


def wilson(k, n, z=1.959964):
    """95% Wilson score interval for k successes in n trials."""
    if n == 0:
        return (0.0, 1.0)
    p = k / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return (max(0.0, centre - half), min(1.0, centre + half))


def _rate_block(recs):
    attempts = len(recs)
    successes = sum(1 for r in recs if r["success"])
    lo, hi = wilson(successes, attempts)
    rate = successes / attempts if attempts else 0.0
    return {"attempts": attempts, "successes": successes, "rate": rate,
            "wilson95": (lo, hi),
            "violation_episodes": sum(1 for r in recs if r["success"] and r["violations"])}


def _public(block):
    out = dict(block)
    out["wilson95"] = [float(out["wilson95"][0]), float(out["wilson95"][1])]
    return out


def _train_summary(recs):
    vals = [r["train_frames"] for r in recs if r["success"]]
    if not vals:
        return {"min": None, "median": None, "max": None}
    return {"min": int(min(vals)), "median": float(statistics.median(vals)), "max": int(max(vals))}


def _commit():
    try:
        out = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=REPO_DIR,
                             capture_output=True, text=True, check=True, timeout=10)
        return out.stdout.strip() or None
    except Exception:
        return None


def _range(vals):
    return {"min": min(vals), "max": max(vals)} if vals else {"min": None, "max": None}


def check_mode(mode, seed, episodes=200):
    """Run one mode and return the JSON payload."""
    if mode not in MODES:
        raise ValueError(f"bad mode: {mode}")
    if mode != "clean" and episodes % 2:
        raise ValueError("embedded/separate need an even number of episodes")
    records = [run_episode(seed, mode, i, _shift_type_for(mode, i)) for i in range(episodes)]

    types = ["none"] if mode == "clean" else ["early", "late"]
    by_type = {}
    for t in types:
        recs = [r for r in records if r["shift_type"] == t]
        block = _rate_block(recs)
        block_out = _public(block)
        block_out["train_frames"] = _train_summary(recs)
        by_type[t] = block_out

    total_raw = _rate_block(records)
    total = _public(total_raw)
    passed = total_raw["successes"] / total_raw["attempts"] >= PASS_RATE \
        if total_raw["attempts"] else False
    passed = passed and total_raw["violation_episodes"] == 0

    failures = [{"seed": r["seed"], "attempt": r["attempt"], "shift_type": r["shift_type"],
                 "reason": r["reason"]} for r in records if not r["success"]]
    violations = [{"seed": r["seed"], "attempt": r["attempt"], "shift_type": r["shift_type"],
                   "checks": r["violations"]} for r in records if r["success"] and r["violations"]]

    early_ok = [r for r in records if r["success"] and r["shift_type"] == "early"]
    info = {
        "late_retry_contact_episodes": sum(1 for r in records if r["late_retry_contact"]),
        "trigger_z": _range([r["trigger_z"] for r in early_ok]),
        "shift_hand_z": _range([r["shift_hand_z"] for r in early_ok]),
    }
    return {"mode": mode, "seed": seed, "episodes": episodes, "commit": _commit(),
            "by_type": by_type, "total": total, "pass": bool(passed),
            "failures": failures, "violations": violations, "info": info}


def _fmt_line(mode, seed, key, block):
    line = (f"{mode} seed={seed} {key}: attempts={block['attempts']} "
            f"successes={block['successes']} rate={block['rate']:.3f} "
            f"wilson95=[{block['wilson95'][0]:.3f}, {block['wilson95'][1]:.3f}] "
            f"violation_episodes={block['violation_episodes']}")
    tf = block.get("train_frames")
    if tf:
        line += f" train_frames min/median/max={tf['min']}/{tf['median']}/{tf['max']}"
    return line


def _print_summary(payload):
    mode, seed = payload["mode"], payload["seed"]
    for key, block in payload["by_type"].items():
        print(_fmt_line(mode, seed, key, block))
    print(_fmt_line(mode, seed, "total", payload["total"]))
    print(f"{mode} seed={seed} pass={payload['pass']} failures={len(payload['failures'])} "
          f"violations={len(payload['violations'])}")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", required=True, choices=[*MODES, "all"])
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--episodes", type=int, default=200)
    parser.add_argument("--out", type=Path, default=Path("results/step2"))
    args = parser.parse_args(argv)

    modes = list(MODES) if args.mode == "all" else [args.mode]
    if args.episodes < 1:
        parser.error("--episodes must be at least 1")
    if any(m != "clean" for m in modes) and args.episodes % 2:
        parser.error("--episodes must be even for embedded/separate")

    args.out.mkdir(parents=True, exist_ok=True)
    for mode in modes:
        payload = check_mode(mode, args.seed, args.episodes)
        path = args.out / f"check_{mode}_seed{args.seed}.json"
        path.write_text(json.dumps(payload, indent=2) + "\n")
        _print_summary(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

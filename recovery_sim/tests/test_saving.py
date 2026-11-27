"""Saving rules for recovery_sim/collect.py, tested against .orchestration/contract.md."""
import json
import math
from pathlib import Path

import numpy as np
import pytest

import collect

SEED = 0
FRAMES = 300
NEAR_BOWL = 0.06  # same radius as the contract's success rule
TOL = 1e-6  # grip constants are stored as float32 in the npz files
_rebuild_cache = {}


@pytest.fixture(scope="module")
def saved(tmp_path_factory):
    out = tmp_path_factory.mktemp("saving")
    summaries = {}
    for mode in collect.MODES:
        summaries[mode] = collect.collect(mode, frames=FRAMES, seed=SEED, out=out, images=False)
    return out, summaries


def mode_dir(out, mode):
    return Path(out) / f"{mode}_seed{SEED}"


def episode_paths(out, mode):
    paths = sorted(mode_dir(out, mode).glob("episode_*.npz"))
    assert paths, f"saving rule broke: no episode_*.npz saved for mode {mode}"
    return paths


def load_npz(path):
    with np.load(path, allow_pickle=False) as z:
        return {k: z[k] for k in z.files}


def scalars(d):
    return {
        "shift_type": str(d["shift_type"][()]),
        "shift_frame": int(d["shift_frame"][()]),
        "shift_frame_full": int(d["shift_frame_full"][()]),
        "trigger_z": float(d["trigger_z"][()]),
        "train_start": int(d["train_start"][()]),
        "train_end": int(d["train_end"][()]),
        "seed": int(d["seed"][()]),
        "attempt": int(d["attempt"][()]),
    }


def rebuild(path, mode):
    """Re-run the full episode from its saved seed and attempt (cached per file)."""
    key = (str(path), mode)
    if key not in _rebuild_cache:
        meta = scalars(load_npz(path))
        rng = collect.episode_rng(meta["seed"], mode, meta["attempt"])
        ep = collect.Episode(collect.make_model(), rng, shift_type=meta["shift_type"])
        _rebuild_cache[key] = ep.run(mode)
    return _rebuild_cache[key]


def full_arrays(res):
    fr = res["frames"]
    return {
        "state": np.stack([np.asarray(f["state"]) for f in fr]),
        "action": np.stack([np.asarray(f["action"]) for f in fr]),
        "block_pos": np.stack([np.asarray(f["block_pos"]) for f in fr]),
        "touch": np.array([bool(f["touch"]) for f in fr]),
    }


def expected_window(mode, res, full):
    """Return (train_start, train_end) in full-episode indices, from the contract."""
    T = len(full["action"])
    if mode in ("clean", "embedded"):
        return 0, T - 1
    grip = full["action"][:, 3]
    sf = res["shift_frame"]
    if res["shift_type"] == "early":
        start = sf
    else:
        opens = [i for i in range(sf + 1, T) if abs(grip[i] - collect.OPEN) < TOL]
        assert opens, "separate rule broke: late episode never reopens the gripper after the shift"
        start = opens[0]
    closed = np.abs(grip - collect.CLOSED) < TOL
    closes = [i for i in range(1, T) if closed[i] and not closed[i - 1]]
    assert closes, "separate rule broke: no close found in the full episode"
    final_close = closes[-1]
    block_z = full["block_pos"][:, 2]
    lifted = [j for j in range(max(start, final_close), T) if block_z[j] >= collect.CARRY_BLOCK_Z]
    assert lifted, "separate rule broke: block never reaches CARRY_BLOCK_Z after the final close"
    return start, lifted[0]


def assert_matches_slice(d, full, lo, hi, name):
    for key in ("state", "action", "block_pos", "touch"):
        want = full[key][lo : hi + 1]
        got = d[key]
        assert got.shape == want.shape and np.array_equal(got, want), (
            f"saving rule broke: saved {key} is not frames {lo}..{hi} of the full episode in {name}"
        )


def assert_delivered(d, name):
    bowl = np.asarray(collect.BOWL, dtype=float)
    last_action = d["action"][-1]
    last_block = d["block_pos"][-1]
    assert abs(float(last_action[3]) - collect.OPEN) < TOL, (
        f"delivery rule broke: last saved frame grip is not OPEN in {name}"
    )
    assert np.linalg.norm(last_action[:2] - bowl[:2]) < NEAR_BOWL, (
        f"delivery rule broke: last saved hand target is not over the bowl in {name}"
    )
    assert np.linalg.norm(last_block[:2] - bowl[:2]) < NEAR_BOWL, (
        f"delivery rule broke: last saved block xy is not in the bowl in {name}"
    )
    assert last_block[2] < 0.06, f"delivery rule broke: last saved block z is not low in {name}"


def check_shift_index(d, m, name, lo):
    expected = m["shift_frame_full"] - lo
    assert m["shift_frame"] == expected, (
        f"shift index rule broke: shift_frame {m['shift_frame']} != "
        f"shift_frame_full - (train_start - n_context) = {expected} in {name}"
    )
    sf = m["shift_frame"]
    assert 0 <= sf < len(d["block_pos"]), (
        f"shift index rule broke: shift_frame {sf} is outside the saved arrays in {name}"
    )
    assert np.allclose(d["block_pos"][sf], d["block_after"], atol=1e-6), (
        f"shift index rule broke: block_pos[shift_frame] != block_after in {name}"
    )


def assert_success(res, name):
    assert bool(res["success"]), f"success rule broke: saved episode rebuilds as a failure in {name}"


# ---------------------------------------------------------------- clean / embedded


def test_clean_saves_whole_episode_without_disturbance(saved):
    out, _ = saved
    for path in episode_paths(out, "clean"):
        d = load_npz(path)
        m = scalars(d)
        n = len(d["train"])
        name = path.name
        assert m["shift_type"] == "none", f"clean rule broke: shift_type {m['shift_type']} in {name}"
        assert m["shift_frame"] == -1 and m["shift_frame_full"] == -1, (
            f"clean rule broke: shift_frame must be -1 in {name}"
        )
        assert d["train"].all(), f"clean rule broke: not all train True in {name}"
        assert np.isnan(d["block_before"]).all() and np.isnan(d["block_after"]).all(), (
            f"clean rule broke: block_before/after must be NaN in {name}"
        )
        assert math.isnan(m["trigger_z"]), f"clean rule broke: trigger_z must be NaN in {name}"
        assert m["train_start"] == 0 and m["train_end"] == n - 1, (
            f"clean rule broke: train window must be the whole episode in {name}"
        )
        assert_delivered(d, name)
        res = rebuild(path, "clean")
        assert_success(res, name)
        full = full_arrays(res)
        assert len(full["action"]) == n, (
            f"clean rule broke: saved {n} frames but the full episode has {len(full['action'])} in {name}"
        )
        assert_matches_slice(d, full, 0, n - 1, name)


@pytest.mark.parametrize("mode", ["embedded"])
def test_embedded_saves_whole_episode_with_delivery(saved, mode):
    out, _ = saved
    for path in episode_paths(out, mode):
        d = load_npz(path)
        m = scalars(d)
        n = len(d["train"])
        name = path.name
        assert m["shift_type"] in ("early", "late"), (
            f"embedded rule broke: shift_type {m['shift_type']} in {name}"
        )
        assert m["shift_frame"] >= 0, f"embedded rule broke: shift_frame must be set in {name}"
        assert d["train"].all(), f"embedded rule broke: not all train True in {name}"
        assert m["train_start"] == 0 and m["train_end"] == n - 1, (
            f"embedded rule broke: train window must be the whole episode in {name}"
        )
        assert_delivered(d, name)
        res = rebuild(path, mode)
        assert_success(res, name)
        full = full_arrays(res)
        assert len(full["action"]) == n, (
            f"embedded rule broke: saved {n} frames but the full episode has {len(full['action'])} in {name}"
        )
        assert_matches_slice(d, full, 0, n - 1, name)
        check_shift_index(d, m, name, lo=0)


# ---------------------------------------------------------------- separate


def test_separate_train_window(saved):
    out, _ = saved
    for path in episode_paths(out, "separate"):
        d = load_npz(path)
        m = scalars(d)
        name = path.name
        res = rebuild(path, "separate")
        assert_success(res, name)
        full = full_arrays(res)
        assert m["shift_type"] in ("early", "late"), (
            f"separate rule broke: shift_type {m['shift_type']} in {name}"
        )
        assert m["shift_frame_full"] == res["shift_frame"], (
            f"separate rule broke: shift_frame_full {m['shift_frame_full']} != rebuilt shift index in {name}"
        )
        start, end = expected_window("separate", res, full)
        assert m["train_start"] == start, (
            f"separate rule broke: train_start {m['train_start']} != expected {start} in {name}"
        )
        assert m["train_end"] == end, (
            f"separate rule broke: train_end {m['train_end']} != expected {end} in {name}"
        )
        if m["shift_type"] == "early":
            assert start == m["shift_frame_full"], (
                f"separate rule broke: early train_start must equal shift_frame_full in {name}"
            )
        else:
            assert start > m["shift_frame_full"], (
                f"separate rule broke: late train_start must come after the shift in {name}"
            )
        assert end - start >= 1, f"separate rule broke: train window has fewer than 2 frames in {name}"
        z = full["block_pos"][:, 2]
        assert z[end] >= collect.CARRY_BLOCK_Z, (
            f"separate rule broke: block z at train_end is below CARRY_BLOCK_Z in {name}"
        )
        assert z[end - 1] < collect.CARRY_BLOCK_Z, (
            f"separate rule broke: block z before train_end is already at CARRY_BLOCK_Z in {name}"
        )


def test_separate_context_frames(saved):
    out, _ = saved
    for path in episode_paths(out, "separate"):
        d = load_npz(path)
        name = path.name
        res = rebuild(path, "separate")
        full = full_arrays(res)
        start, end = expected_window("separate", res, full)
        k = min(collect.CONTEXT, start)
        n = end - start + 1
        expected_mask = np.array([False] * k + [True] * n)
        assert d["train"].shape == expected_mask.shape and np.array_equal(d["train"], expected_mask), (
            f"separate rule broke: train mask is not [False]*min({collect.CONTEXT}, train_start) "
            f"+ [True]*n in {name}"
        )
        assert_matches_slice(d, full, start - k, end, name)


def test_separate_shift_frame_index(saved):
    out, _ = saved
    for path in episode_paths(out, "separate"):
        d = load_npz(path)
        m = scalars(d)
        name = path.name
        res = rebuild(path, "separate")
        full = full_arrays(res)
        start, _ = expected_window("separate", res, full)
        k = min(collect.CONTEXT, start)
        check_shift_index(d, m, name, lo=start - k)


@pytest.mark.parametrize("mode", collect.MODES)
def test_kept_only_if_full_task_succeeds(saved, mode):
    out, _ = saved
    for path in episode_paths(out, mode):
        res = rebuild(path, mode)
        name = path.name
        assert_success(res, name)
        assert collect.select(res, mode) is not None, (
            f"success rule broke: select() returned None for a successful episode in {name}"
        )
        failed = dict(res, success=False)
        assert collect.select(failed, mode) is None, (
            f"success rule broke: select() must return None when success is False ({name})"
        )


# ---------------------------------------------------------------- metadata


@pytest.mark.parametrize("mode", collect.MODES)
def test_npz_fields_dtypes_and_shapes(saved, mode):
    out, _ = saved
    for path in episode_paths(out, mode):
        d = load_npz(path)
        name = path.name
        T = len(d["train"]) if "train" in d else -1
        spec = {
            "state": (np.float32, (T, 5)),
            "action": (np.float32, (T, 4)),
            "block_pos": (np.float32, (T, 3)),
            "touch": (np.bool_, (T,)),
            "train": (np.bool_, (T,)),
            "shift_frame": (np.int64, ()),
            "shift_frame_full": (np.int64, ()),
            "trigger_z": (np.float64, ()),
            "block_before": (np.float64, (3,)),
            "block_after": (np.float64, (3,)),
            "train_start": (np.int64, ()),
            "train_end": (np.int64, ()),
            "seed": (np.int64, ()),
            "attempt": (np.int64, ()),
        }
        for key, (dt, shape) in spec.items():
            assert key in d, f"metadata rule broke: {key} missing in {name}"
            assert d[key].dtype == np.dtype(dt), (
                f"metadata rule broke: {key} dtype {d[key].dtype} != {np.dtype(dt)} in {name}"
            )
            assert d[key].shape == shape, (
                f"metadata rule broke: {key} shape {d[key].shape} != {shape} in {name}"
            )
        assert "shift_type" in d and d["shift_type"].dtype.kind == "U" and d["shift_type"].shape == (), (
            f"metadata rule broke: shift_type must be a str scalar in {name}"
        )
        assert "top" not in d and "wrist" not in d, (
            f"metadata rule broke: top/wrist must be absent with images=False in {name}"
        )
        m = scalars(d)
        assert m["shift_type"] in ("none", "early", "late"), f"metadata rule broke: bad shift_type in {name}"
        assert m["seed"] == SEED, f"metadata rule broke: seed {m['seed']} != {SEED} in {name}"
        if m["shift_type"] == "early":
            assert collect.TRIGGER_MIN <= m["trigger_z"] <= collect.TRIGGER_MAX, (
                f"metadata rule broke: trigger_z {m['trigger_z']} outside the trigger range in {name}"
            )
        else:
            assert math.isnan(m["trigger_z"]), (
                f"metadata rule broke: trigger_z must be NaN unless early in {name}"
            )


@pytest.mark.parametrize("mode", collect.MODES)
def test_json_files_agree_with_npz(saved, mode):
    out, summaries = saved
    paths = episode_paths(out, mode)
    entries = json.loads((mode_dir(out, mode) / "episodes.json").read_text())
    summary = json.loads((mode_dir(out, mode) / "summary.json").read_text())
    assert isinstance(entries, list) and len(entries) == len(paths), (
        f"metadata rule broke: episodes.json has {len(entries)} entries for {len(paths)} npz files"
    )
    by_name = {Path(e["file"]).name: e for e in entries}
    assert sorted(by_name) == sorted(p.name for p in paths), (
        "metadata rule broke: episodes.json file names do not match the npz files"
    )
    per_type = {}
    total_frames = 0
    train_frames = 0
    for p in paths:
        d = load_npz(p)
        m = scalars(d)
        e = by_name[p.name]
        for key, val in m.items():
            if key == "trigger_z":
                ev = float("nan") if e[key] is None else e[key]
                assert (math.isnan(ev) and math.isnan(val)) or ev == val, (
                    f"metadata rule broke: episodes.json trigger_z disagrees with npz in {p.name}"
                )
            else:
                assert e[key] == val, f"metadata rule broke: episodes.json {key} disagrees with npz in {p.name}"
        n_train = int(np.sum(d["train"]))
        n_frames = len(d["train"])
        assert e["n_train"] == n_train, f"metadata rule broke: n_train disagrees with npz in {p.name}"
        assert e["n_frames"] == n_frames, f"metadata rule broke: n_frames disagrees with npz in {p.name}"
        total_frames += n_frames
        train_frames += n_train
        per_type[m["shift_type"]] = per_type.get(m["shift_type"], 0) + 1

    assert summary["mode"] == mode, f"metadata rule broke: summary mode in {mode}"
    assert summary["seed"] == SEED, "metadata rule broke: summary seed"
    assert summary["frames_budget"] == FRAMES, "metadata rule broke: summary frames_budget"
    assert summary["episodes"] == len(paths), "metadata rule broke: summary episodes disagrees with npz files"
    assert summary["train_frames"] == train_frames, "metadata rule broke: summary train_frames disagrees with npz"
    assert summary["total_frames"] == total_frames, "metadata rule broke: summary total_frames disagrees with npz"
    expected_keys = {"none"} if mode == "clean" else {"early", "late"}
    for key in ("episodes_by_type", "attempts", "successes"):
        assert set(summary[key]) == expected_keys, f"metadata rule broke: summary {key} keys are wrong"
    for t in expected_keys:
        assert summary["episodes_by_type"][t] == per_type.get(t, 0), (
            f"metadata rule broke: summary episodes_by_type[{t}] disagrees with npz files"
        )
        assert summary["successes"][t] >= summary["episodes_by_type"][t], (
            f"metadata rule broke: successes[{t}] is below the saved count"
        )
        assert summary["attempts"][t] >= summary["successes"][t], (
            f"metadata rule broke: attempts[{t}] is below successes[{t}]"
        )
    assert summaries[mode] == summary, "metadata rule broke: collect() return value differs from summary.json"


@pytest.mark.parametrize("mode", collect.MODES)
def test_stops_on_whole_episodes_once_budget_reached(saved, mode):
    out, _ = saved
    per = [int(np.sum(load_npz(p)["train"])) for p in episode_paths(out, mode)]
    total = sum(per)
    assert total >= FRAMES, f"collection rule broke: train frames {total} < budget {FRAMES} in {mode}"
    assert total - per[-1] < FRAMES, (
        f"collection rule broke: stopped after the budget was already reached (before last episode) in {mode}"
    )


@pytest.mark.parametrize("mode", ["embedded", "separate"])
def test_next_attempt_type_rule(saved, mode):
    out, _ = saved
    counts = {"early": 0, "late": 0}
    prev_attempt = -1
    for p in episode_paths(out, mode):
        m = scalars(load_npz(p))
        want = "early" if counts["early"] <= counts["late"] else "late"
        assert m["shift_type"] == want, (
            f"collection rule broke: saved {m['shift_type']} but the rule picks {want} "
            f"(counts {counts}) in {mode} {p.name}"
        )
        assert m["attempt"] > prev_attempt, f"collection rule broke: attempt numbers not increasing in {p.name}"
        prev_attempt = m["attempt"]
        counts[m["shift_type"]] += 1
    assert abs(counts["early"] - counts["late"]) <= 1, (
        f"collection rule broke: early/late saved counts {counts} differ by more than one in {mode}"
    )

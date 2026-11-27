"""Tests for the block-shift rules in the recovery_sim contract (.orchestration/contract.md).

These tests exercise only the public interface named in the contract. They are
written before/independently of the implementation and may fail until it exists.
All randomness is seeded, and no test writes output files.
"""

import functools

import numpy as np
import pytest

import collect
from collect import (
    CLOSED,
    HAND_Z0,
    SHIFT_MAX,
    SHIFT_MIN,
    TRIGGER_MAX,
    TRIGGER_MIN,
    WORKSPACE,
)

SHIFT_SEED = 1234
DIST_TOL = 1e-6  # numerical slack on the shift distance bounds
XY_TOL_BLOCK_POS = 1e-5  # frame block_pos (float32) vs block_after (float64)
PRE_SHIFT_XY_TOL = 0.002  # 2 mm: block must not move before the shift
N_SHIFTS = 300


@functools.lru_cache(maxsize=None)
def _model():
    return collect.make_model()


def _fresh_episode(shift_type="none", seed=SHIFT_SEED, mode="clean", attempt=0):
    return collect.Episode(
        _model(), collect.episode_rng(seed, mode, attempt), None, shift_type
    )


def _ks_stat_uniform(x, lo, hi):
    """Kolmogorov-Smirnov statistic of sample x against U(lo, hi)."""
    x = np.sort(np.asarray(x, dtype=float))
    n = len(x)
    cdf = np.clip((x - lo) / (hi - lo), 0.0, 1.0)
    i = np.arange(1, n + 1)
    d_plus = np.max(i / n - cdf)
    d_minus = np.max(cdf - (i - 1) / n)
    return max(d_plus, d_minus)


# ---------------------------------------------------------------- shift_block

def _single_shifts(n=N_SHIFTS):
    """n shifts, each from a fresh episode so every shift starts from the same block."""
    out = []
    for k in range(n):
        ep = _fresh_episode(seed=SHIFT_SEED, mode="clean", attempt=k)
        before, after = ep.shift_block()
        out.append((np.asarray(before, float), np.asarray(after, float)))
    return out


@pytest.fixture(scope="module")
def single_shifts():
    return _single_shifts()


def test_shift_distance_within_bounds(single_shifts):
    d = np.array([np.hypot(a[0] - b[0], a[1] - b[1]) for b, a in single_shifts])
    assert d.min() >= SHIFT_MIN - DIST_TOL, (
        f"shift distance rule broken: min {d.min():.5f} m < SHIFT_MIN {SHIFT_MIN}"
    )
    assert d.max() <= SHIFT_MAX + DIST_TOL, (
        f"shift distance rule broken: max {d.max():.5f} m > SHIFT_MAX {SHIFT_MAX}"
    )


def test_shift_distance_is_uniform(single_shifts):
    d = np.array([np.hypot(a[0] - b[0], a[1] - b[1]) for b, a in single_shifts])
    # Redraws for workspace/contact rejection can bias the accepted sample, so this
    # is a KS check at alpha = 0.001 (critical value ~ 1.95 / sqrt(n)).
    stat = _ks_stat_uniform(d, SHIFT_MIN, SHIFT_MAX)
    crit = 1.95 / np.sqrt(len(d))
    assert stat < crit, (
        f"shift distance rule broken: not U({SHIFT_MIN}, {SHIFT_MAX}); "
        f"KS stat {stat:.4f} >= critical {crit:.4f} (n={len(d)})"
    )


def test_shift_direction_covers_all_four_quadrants(single_shifts):
    quadrants = set()
    for b, a in single_shifts:
        angle = np.arctan2(a[1] - b[1], a[0] - b[0]) % (2 * np.pi)
        quadrants.add(int(angle // (np.pi / 2)) % 4)
    missing = {0, 1, 2, 3} - quadrants
    assert not missing, (
        f"shift direction rule broken: angle quadrants {sorted(missing)} never "
        f"appeared in {len(single_shifts)} shifts (expected random direction)"
    )


def test_shift_keeps_block_inside_workspace(single_shifts):
    for k, (_, a) in enumerate(single_shifts):
        assert collect.in_workspace((a[0], a[1])), (
            f"workspace rule broken: shift {k} placed block at xy "
            f"({a[0]:.4f}, {a[1]:.4f}), outside WORKSPACE {WORKSPACE}"
        )


def test_shift_keeps_block_inside_workspace_over_sequential_shifts():
    ep = _fresh_episode(seed=SHIFT_SEED, mode="clean", attempt=999)
    for k in range(100):
        _, after = ep.shift_block()
        assert collect.in_workspace((after[0], after[1])), (
            f"workspace rule broken: sequential shift {k} left block at "
            f"({after[0]:.4f}, {after[1]:.4f}), outside WORKSPACE {WORKSPACE}"
        )


def test_in_workspace_bounds_are_strict():
    (x0, x1), (y0, y1) = WORKSPACE
    ymid = (y0 + y1) / 2
    xmid = (x0 + x1) / 2
    assert collect.in_workspace((xmid, ymid)), "in_workspace: centre point must be inside"
    assert not collect.in_workspace((x0, ymid)), "workspace rule broken: x lower bound must be excluded (strict)"
    assert not collect.in_workspace((x1, ymid)), "workspace rule broken: x upper bound must be excluded (strict)"
    assert not collect.in_workspace((xmid, y0)), "workspace rule broken: y lower bound must be excluded (strict)"
    assert not collect.in_workspace((xmid, y1)), "workspace rule broken: y upper bound must be excluded (strict)"


def test_shift_leaves_no_block_hand_overlap():
    ep = _fresh_episode(seed=SHIFT_SEED, mode="clean", attempt=500)
    for k in range(100):
        ep.shift_block()
        assert ep.block_touches_hand() is False, (
            f"no-overlap rule broken: after shift {k}, block_touches_hand() is True"
        )


def test_shift_no_overlap_from_fresh_episodes():
    for k in range(N_SHIFTS // 3):
        ep = _fresh_episode(seed=SHIFT_SEED, mode="clean", attempt=k)
        ep.shift_block()
        assert ep.block_touches_hand() is False, (
            f"no-overlap rule broken: fresh-episode shift {k} leaves block touching hand"
        )


def test_shift_keeps_block_height():
    ep = _fresh_episode(seed=SHIFT_SEED, mode="clean", attempt=7)
    z_before = float(ep.block()[2])
    _, after = ep.shift_block()
    assert abs(float(after[2]) - z_before) < 1e-9, (
        "shift rule broken: shift must keep block z (only xy changes)"
    )


# ---------------------------------------------------------------- trigger_z

def test_early_trigger_z_drawn_in_range():
    vals = []
    for k in range(60):
        ep = collect.Episode(_model(), collect.episode_rng(SHIFT_SEED, "embedded", k), None, "early")
        assert ep.trigger_z is not None, "trigger rule broken: early episode must have trigger_z set"
        assert TRIGGER_MIN <= ep.trigger_z <= TRIGGER_MAX, (
            f"trigger rule broken: trigger_z {ep.trigger_z:.4f} outside [{TRIGGER_MIN}, {TRIGGER_MAX}]"
        )
        vals.append(ep.trigger_z)
    mid = (TRIGGER_MIN + TRIGGER_MAX) / 2
    assert any(v < mid for v in vals) and any(v > mid for v in vals), (
        "trigger rule broken: trigger_z draws do not span the range (expected uniform)"
    )


def test_non_early_episode_has_no_trigger_z():
    for shift_type in ("none", "late"):
        ep = _fresh_episode(shift_type=shift_type, seed=SHIFT_SEED, mode="embedded", attempt=0)
        assert ep.trigger_z is None, (
            f"trigger rule broken: shift_type={shift_type!r} must have trigger_z None"
        )


# ---------------------------------------------------------------- run results

RUN_CASES = {
    "none": [("clean", SHIFT_SEED, 0)],
    "early": [("embedded", 0, 0), ("embedded", 1, 0), ("embedded", 2, 0), ("separate", 0, 0)],
    "late": [("embedded", 0, 0), ("embedded", 1, 0), ("embedded", 2, 0), ("separate", 0, 0)],
}


def _run_params(shift_type):
    return [
        pytest.param(shift_type, mode, seed, attempt, id=f"{shift_type}-{mode}-s{seed}-a{attempt}")
        for mode, seed, attempt in RUN_CASES[shift_type]
    ]


@functools.lru_cache(maxsize=None)
def _run(shift_type, mode, seed, attempt):
    ep = collect.Episode(_model(), collect.episode_rng(seed, mode, attempt), None, shift_type)
    return ep.run(mode)


def _hand_z(frame):
    return float(frame["state"][2]) + HAND_Z0


ALL_RUNS = _run_params("none") + _run_params("early") + _run_params("late")
SHIFT_RUNS = _run_params("early") + _run_params("late")


@pytest.mark.parametrize("shift_type,mode,seed,attempt", ALL_RUNS)
def test_run_no_overlap_at_shift_frame(shift_type, mode, seed, attempt):
    res = _run(shift_type, mode, seed, attempt)
    if shift_type == "none":
        pytest.skip("clean episode has no shift")
    s = res["shift_frame"]
    assert s >= 0, f"shift rule broken: {shift_type} episode never shifted (shift_frame={s})"
    assert res["frames"][s]["touch"] == False, (  # noqa: E712 - numpy bool
        f"no-overlap rule broken: frames[{s}]['touch'] is True right after the shift"
    )


@pytest.mark.parametrize("shift_type,mode,seed,attempt", SHIFT_RUNS)
def test_run_block_after_inside_workspace(shift_type, mode, seed, attempt):
    res = _run(shift_type, mode, seed, attempt)
    after = np.asarray(res["block_after"], float)
    assert collect.in_workspace((after[0], after[1])), (
        f"workspace rule broken: block_after xy ({after[0]:.4f}, {after[1]:.4f}) "
        f"outside WORKSPACE {WORKSPACE}"
    )


@pytest.mark.parametrize("shift_type,mode,seed,attempt", SHIFT_RUNS)
def test_run_shift_frame_block_pos_and_pre_shift_block(shift_type, mode, seed, attempt):
    res = _run(shift_type, mode, seed, attempt)
    s = res["shift_frame"]
    assert s >= 1, f"shift rule broken: shift_frame {s} leaves no pre-shift frame"
    after = np.asarray(res["block_after"], float)
    before = np.asarray(res["block_before"], float)
    pos_s = np.asarray(res["frames"][s]["block_pos"], float)
    assert np.max(np.abs(pos_s - after)) <= XY_TOL_BLOCK_POS, (
        f"shift rule broken: frames[{s}]['block_pos'] {pos_s} != block_after {after} "
        f"(tol {XY_TOL_BLOCK_POS})"
    )
    pos_prev = np.asarray(res["frames"][s - 1]["block_pos"], float)
    dxy = np.hypot(pos_prev[0] - before[0], pos_prev[1] - before[1])
    assert dxy <= PRE_SHIFT_XY_TOL, (
        f"shift rule broken: frames[{s - 1}]['block_pos'] xy is {dxy * 1000:.2f} mm from "
        f"block_before (limit 2 mm); block moved before the shift"
    )


@pytest.mark.parametrize("shift_type,mode,seed,attempt", ALL_RUNS)
def test_run_result_fields(shift_type, mode, seed, attempt):
    res = _run(shift_type, mode, seed, attempt)
    assert res["shift_type"] == shift_type, (
        f"result rule broken: shift_type {res['shift_type']!r} != {shift_type!r}"
    )
    assert len(res["frames"]) > 0, "result rule broken: no frames recorded"
    before = np.asarray(res["block_before"], float)
    after = np.asarray(res["block_after"], float)
    assert before.shape == (3,) and after.shape == (3,), (
        "result rule broken: block_before/block_after must have shape (3,)"
    )


# Clean episodes
def test_clean_episode_has_no_shift():
    res = _run("none", "clean", SHIFT_SEED, 0)
    assert res["shift_type"] == "none", "clean rule broken: shift_type must be 'none'"
    assert res["shift_frame"] == -1, (
        f"clean rule broken: shift_frame must be -1, got {res['shift_frame']}"
    )
    assert np.all(np.isnan(np.asarray(res["block_before"], float))), (
        "clean rule broken: block_before must be NaN for a clean episode"
    )
    assert np.all(np.isnan(np.asarray(res["block_after"], float))), (
        "clean rule broken: block_after must be NaN for a clean episode"
    )
    assert np.isnan(float(res["trigger_z"])), (
        "clean rule broken: trigger_z must be NaN for a clean episode"
    )


# Early trigger timing
@pytest.mark.parametrize("mode,seed,attempt", RUN_CASES["early"])
def test_early_trigger_timing(mode, seed, attempt):
    res = _run("early", mode, seed, attempt)
    frames = res["frames"]
    s = res["shift_frame"]
    trig = float(res["trigger_z"])
    assert s >= 2, f"early trigger rule broken: shift_frame {s} too early to check descent"
    assert TRIGGER_MIN <= trig <= TRIGGER_MAX, (
        f"early trigger rule broken: trigger_z {trig:.4f} outside [{TRIGGER_MIN}, {TRIGGER_MAX}]"
    )
    z_s = _hand_z(frames[s])
    z_prev = _hand_z(frames[s - 1])
    z_prev2 = _hand_z(frames[s - 2])
    assert z_s <= trig, (
        f"early trigger rule broken: hand z at shift_frame {s} is {z_s:.4f}, "
        f"should be <= trigger_z {trig:.4f}"
    )
    assert z_prev > trig, (
        f"early trigger rule broken: hand z at frame {s - 1} is {z_prev:.4f}, "
        f"should be > trigger_z {trig:.4f} (shift fired too late)"
    )
    assert z_prev < z_prev2, (
        f"early trigger rule broken: hand not moving down at frame {s - 1} "
        f"(z {z_prev2:.4f} -> {z_prev:.4f})"
    )
    crossed_earlier = [i for i in range(s) if _hand_z(frames[i]) <= trig]
    assert not crossed_earlier, (
        f"early trigger rule broken: hand was already at/below trigger_z before "
        f"shift_frame {s} (frames {crossed_earlier[:5]}); shift must fire on the first descent"
    )


# Late trigger timing
@pytest.mark.parametrize("mode,seed,attempt", RUN_CASES["late"])
def test_late_trigger_timing(mode, seed, attempt):
    res = _run("late", mode, seed, attempt)
    frames = res["frames"]
    s = res["shift_frame"]
    assert s >= 1, f"late trigger rule broken: shift_frame {s} has no pre-shift frame"
    grip = np.array([float(f["action"][3]) for f in frames])
    closed = np.abs(grip - CLOSED) < 1e-6
    assert closed.any(), "late trigger rule broken: no frame has action grip CLOSED"
    first_closed = int(np.flatnonzero(closed)[0])
    assert s == first_closed, (
        f"late trigger rule broken: shift_frame {s} != first CLOSED action frame {first_closed}"
    )
    assert closed[s], (
        f"late trigger rule broken: frames[{s}] action grip is not CLOSED"
    )

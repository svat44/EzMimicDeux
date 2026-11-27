"""Contract tests for check_expert.py (recovery_sim/check_expert.py).

Written from .orchestration/contract.md only. The implementation is not read here,
so these tests describe the contract and may fail until the checker exists.
"""

import json
import math
import os
import statistics
import subprocess
import sys
from pathlib import Path

import pytest

import check_expert
import collect

RECOVERY_DIR = Path(__file__).resolve().parents[1]
SEED_A = 7
SEED_B = 11

ALLOWED_CHECKS = {
    "shift_distance",
    "shift_workspace",
    "shift_clearance",
    "trigger_height",
    "early_empty_close",
    "early_contact_before_grasp",
    "late_shift_step",
    "late_empty_close",
    "contact_before_shift",
    "separate_window",
}
TOP_KEYS = {"mode", "seed", "episodes", "commit", "by_type", "total", "pass",
            "failures", "violations", "info"}
TYPE_KEYS = {"attempts", "successes", "rate", "wilson95", "train_frames", "violation_episodes"}
TOTAL_KEYS = {"attempts", "successes", "rate", "wilson95", "violation_episodes"}
FAILURE_KEYS = {"seed", "attempt", "shift_type", "reason"}
VIOLATION_KEYS = {"seed", "attempt", "shift_type", "checks"}


def _cli_env():
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    return env


def _run_cli(args, out_dir):
    cmd = [sys.executable, "check_expert.py", *args, "--out", str(out_dir)]
    return subprocess.run(cmd, cwd=RECOVERY_DIR, env=_cli_env(),
                          capture_output=True, text=True, timeout=300)


def _strict_load(path):
    def reject(const):
        raise ValueError(f"json rule: non-finite constant {const} found in {path.name}")
    return json.loads(path.read_text(), parse_constant=reject)


# ---------------------------------------------------------------- wilson

def test_wilson_zero_n_gives_full_range():
    assert check_expert.wilson(0, 0) == (0.0, 1.0), \
        "wilson rule: n == 0 must return (0.0, 1.0)"


@pytest.mark.parametrize("k,n", [(0, 5), (5, 5), (3, 5), (1, 20), (19, 20), (10, 20), (100, 100)])
def test_wilson_brackets_rate(k, n):
    lo, hi = check_expert.wilson(k, n)
    rate = k / n
    assert not (math.isnan(lo) or math.isnan(hi)), "json rule: wilson must not be NaN"
    assert 0.0 <= lo <= rate <= hi <= 1.0, \
        f"wilson rule: interval must satisfy 0 <= lo <= rate <= hi <= 1, got ({lo}, {hi}) for {k}/{n}"


def test_wilson_matches_contract_example():
    lo, hi = check_expert.wilson(100, 100)
    # Contract example: 100 of 100 gives lower bound 0.963 and upper bound 1.0.
    assert lo == pytest.approx(0.963, abs=0.0015), \
        f"wilson rule: 100/100 lower bound should be about 0.963, got {lo}"
    assert hi == pytest.approx(1.0, abs=1e-9), \
        f"wilson rule: 100/100 upper bound should be 1.0, got {hi}"


# ---------------------------------------------------------------- payload schema

@pytest.fixture(scope="module")
def embedded_payload():
    return check_expert.check_mode("embedded", SEED_A, episodes=6)


def test_payload_top_level_keys(embedded_payload):
    p = embedded_payload
    assert set(p) == TOP_KEYS, \
        f"json rule: top-level keys must be exactly {sorted(TOP_KEYS)}, got {sorted(p)}"
    assert p["mode"] == "embedded", "json rule: mode must be 'embedded'"
    assert p["seed"] == SEED_A, "json rule: seed must echo the seed given"
    assert p["episodes"] == 6, "json rule: episodes must echo the episodes given"


def test_payload_is_nan_free(embedded_payload):
    try:
        json.dumps(embedded_payload, allow_nan=False)
    except ValueError as exc:
        pytest.fail(f"json rule: payload contains NaN or Infinity: {exc}")


def test_by_type_keys_and_attempt_split(embedded_payload):
    bt = embedded_payload["by_type"]
    assert set(bt) == {"early", "late"}, \
        f"json rule: embedded by_type keys must be 'early' and 'late', got {sorted(bt)}"
    assert bt["early"]["attempts"] == 3 and bt["late"]["attempts"] == 3, \
        "embedded rule: even attempts are early and odd are late, so episodes/2 each"
    for name, t in bt.items():
        assert set(t) == TYPE_KEYS, \
            f"json rule: {name} block keys must be {sorted(TYPE_KEYS)}, got {sorted(t)}"


def test_by_type_values_are_consistent(embedded_payload):
    for name, t in embedded_payload["by_type"].items():
        assert 0 <= t["successes"] <= t["attempts"], \
            f"json rule: {name} successes must be between 0 and attempts"
        assert t["rate"] == pytest.approx(t["successes"] / t["attempts"]), \
            f"json rule: {name} rate must equal successes / attempts"
        lo, hi = t["wilson95"]
        assert lo <= t["rate"] <= hi, \
            f"json rule: {name} wilson95 must bracket rate, got {t['wilson95']} for rate {t['rate']}"
        assert check_expert.wilson(t["successes"], t["attempts"]) == pytest.approx((lo, hi)), \
            f"json rule: {name} wilson95 must equal wilson(successes, attempts)"
        tf = t["train_frames"]
        assert set(tf) == {"min", "median", "max"}, \
            f"json rule: {name} train_frames keys must be min, median, max"
        assert tf["min"] <= tf["median"] <= tf["max"], \
            f"json rule: {name} train_frames must satisfy min <= median <= max, got {tf}"
        assert 0 <= t["violation_episodes"] <= t["attempts"], \
            f"json rule: {name} violation_episodes must be between 0 and attempts"


def test_total_block_matches_types(embedded_payload):
    p = embedded_payload
    total = p["total"]
    bt = p["by_type"]
    assert set(total) == TOTAL_KEYS, \
        f"json rule: total keys must be {sorted(TOTAL_KEYS)}, got {sorted(total)}"
    assert total["attempts"] == 6, "json rule: total attempts must equal episodes (6)"
    assert total["attempts"] == sum(t["attempts"] for t in bt.values()), \
        "json rule: total attempts must equal sum over types"
    assert total["successes"] == sum(t["successes"] for t in bt.values()), \
        "json rule: total successes must equal sum over types"
    assert total["violation_episodes"] == sum(t["violation_episodes"] for t in bt.values()), \
        "json rule: total violation_episodes must equal sum over types"
    assert total["rate"] == pytest.approx(total["successes"] / total["attempts"]), \
        "json rule: total rate must equal successes / attempts"


def test_pass_verdict_follows_rule(embedded_payload):
    p = embedded_payload
    expected = p["total"]["rate"] >= 0.98 and p["total"]["violation_episodes"] == 0
    assert p["pass"] == expected, \
        "json rule: pass must be (total rate >= 0.98 and no violations)"


def test_failures_list_matches_attempts(embedded_payload):
    p = embedded_payload
    assert len(p["failures"]) == p["total"]["attempts"] - p["total"]["successes"], \
        "json rule: one failure entry per unsuccessful attempt"
    for f in p["failures"]:
        assert set(f) == FAILURE_KEYS, \
            f"json rule: failure keys must be {sorted(FAILURE_KEYS)}, got {sorted(f)}"
        assert f["seed"] == SEED_A, "json rule: failure seed must be the run seed"
        assert 0 <= f["attempt"] < 6, "json rule: failure attempt must be in 0..episodes-1"
        expected_shift = "early" if f["attempt"] % 2 == 0 else "late"
        assert f["shift_type"] == expected_shift, \
            "embedded rule: even attempt is early, odd is late (failure entry)"
        r = f["reason"]
        assert r in ("task failed", "select returned None") or r.startswith("exception: "), \
            f"contract rule: failure reason must be 'task failed', 'select returned None' or 'exception: <Type>: <message>', got {r!r}"


def test_violations_list_matches_counts(embedded_payload):
    p = embedded_payload
    failed_attempts = {f["attempt"] for f in p["failures"]}
    assert len(p["violations"]) == p["total"]["violation_episodes"], \
        "json rule: one violation entry per violating episode"
    for shift in ("early", "late"):
        n = sum(1 for v in p["violations"] if v["shift_type"] == shift)
        assert n == p["by_type"][shift]["violation_episodes"], \
            f"json rule: {shift} violation entries must equal its violation_episodes"
    for v in p["violations"]:
        assert set(v) == VIOLATION_KEYS, \
            f"json rule: violation keys must be {sorted(VIOLATION_KEYS)}, got {sorted(v)}"
        assert v["attempt"] not in failed_attempts, \
            "contract rule: behaviour checks run only on successful episodes, so a violation cannot be on a failed attempt"
        assert isinstance(v["checks"], list) and v["checks"], \
            "json rule: a violation entry must list at least one check name"
        unknown = set(v["checks"]) - ALLOWED_CHECKS
        assert not unknown, \
            f"contract rule: violation check names must be exact contract names, unknown: {sorted(unknown)}"


def test_info_block(embedded_payload):
    info = embedded_payload["info"]
    assert isinstance(info.get("late_retry_contact_episodes"), int) and info["late_retry_contact_episodes"] >= 0, \
        "json rule: info.late_retry_contact_episodes must be a non-negative int"
    assert set(info) == {"late_retry_contact_episodes", "trigger_z", "shift_hand_z"}, \
        f"json rule: info keys must be late_retry_contact_episodes, trigger_z, shift_hand_z; got {sorted(info)}"
    early_successes = embedded_payload["by_type"]["early"]["successes"]
    for key in ("trigger_z", "shift_hand_z"):
        rng_block = info[key]
        if early_successes == 0:
            assert rng_block is None, \
                f"json rule: info.{key} must be null when there are no successful early episodes"
        else:
            assert isinstance(rng_block, dict) and set(rng_block) == {"min", "max"}, \
                f"json rule: info.{key} must be a {{min, max}} dict when early episodes succeed"
            assert rng_block["min"] <= rng_block["max"], \
                f"json rule: info.{key} must have min <= max"
    if info["trigger_z"] is not None and info["shift_hand_z"] is not None:
        assert info["shift_hand_z"]["max"] <= info["trigger_z"]["max"], \
            "json rule: info.shift_hand_z.max must be <= info.trigger_z.max (hand at shift frame is at or below trigger)"


# ---------------------------------------------------------------- modes

def test_clean_mode_uses_none_key():
    p = check_expert.check_mode("clean", SEED_B, episodes=4)
    assert set(p["by_type"]) == {"none"}, \
        f"json rule: clean by_type key must be 'none' only, got {sorted(p['by_type'])}"
    assert p["by_type"]["none"]["attempts"] == 4, \
        "contract rule: clean attempts must equal episodes (none are retried or replaced)"


def test_separate_train_frames_count_only_train_mask():
    episodes = 4
    p = check_expert.check_mode("separate", SEED_B, episodes=episodes)
    expected = {"early": [], "late": []}
    for i in range(episodes):
        shift = "early" if i % 2 == 0 else "late"
        rng = collect.episode_rng(SEED_B, "separate", i)
        ep = collect.Episode(collect.make_model(), rng, shift_type=shift)
        res = ep.run("separate")
        if not res["success"]:
            continue
        try:
            sel = collect.select(res, "separate")
        except Exception:
            continue
        if sel is None:
            continue
        expected[shift].append(sum(1 for x in sel["train"] if x))
    for shift in ("early", "late"):
        counts = expected[shift]
        block = p["by_type"][shift]
        assert block["successes"] == len(counts), \
            f"separate rule: {shift} successes must match rebuilt successful attempts"
        if not counts:
            continue
        tf = block["train_frames"]
        assert tf["min"] == min(counts), \
            f"separate rule: {shift} train_frames.min must count only train frames, expected {min(counts)}"
        assert tf["max"] == max(counts), \
            f"separate rule: {shift} train_frames.max must count only train frames, expected {max(counts)}"
        assert tf["median"] == pytest.approx(statistics.median(counts)), \
            f"separate rule: {shift} train_frames.median must count only train frames"


# ---------------------------------------------------------------- determinism and CLI

def test_same_seed_gives_identical_json_except_commit(tmp_path):
    dirs = [tmp_path / "a", tmp_path / "b"]
    for d in dirs:
        d.mkdir()
        r = _run_cli(["--mode", "embedded", "--seed", str(SEED_A), "--episodes", "6"], d)
        assert r.returncode == 0, \
            f"cli rule: embedded run must exit 0, got {r.returncode}\n{r.stderr}"
    a = _strict_load(dirs[0] / "check_embedded_seed7.json")
    b = _strict_load(dirs[1] / "check_embedded_seed7.json")
    a.pop("commit", None)
    b.pop("commit", None)
    assert a == b, "determinism rule: same seed twice must give identical JSON except the commit field"


def test_cli_embedded_writes_one_file(tmp_path):
    r = _run_cli(["--mode", "embedded", "--seed", str(SEED_A), "--episodes", "6"], tmp_path)
    assert r.returncode == 0, \
        f"cli rule: embedded run must exit 0 even with failures, got {r.returncode}\n{r.stderr}"
    assert r.stdout.strip(), "cli rule: checker must print a summary line per mode and shift type"
    assert sorted(p.name for p in tmp_path.iterdir()) == ["check_embedded_seed7.json"], \
        "cli rule: embedded run must write exactly check_embedded_seed7.json"
    payload = _strict_load(tmp_path / "check_embedded_seed7.json")
    assert payload["mode"] == "embedded", "json rule: file mode must be 'embedded'"


def test_cli_all_writes_three_files(tmp_path):
    r = _run_cli(["--mode", "all", "--seed", str(SEED_A), "--episodes", "4"], tmp_path)
    assert r.returncode == 0, \
        f"cli rule: --mode all must exit 0, got {r.returncode}\n{r.stderr}"
    names = sorted(p.name for p in tmp_path.iterdir())
    assert names == ["check_clean_seed7.json", "check_embedded_seed7.json",
                     "check_separate_seed7.json"], \
        f"cli rule: --mode all must write three files, got {names}"


def test_cli_odd_episodes_embedded_is_clear_error(tmp_path):
    r = _run_cli(["--mode", "embedded", "--seed", str(SEED_A), "--episodes", "5"], tmp_path)
    assert r.returncode != 0, \
        "contract rule: odd --episodes for embedded must exit nonzero"
    # Assumption (not stated in contract): the error message should mention "even".
    assert "even" in (r.stdout + r.stderr).lower(), \
        f"contract rule: error for odd episodes should say they must be even, got: {r.stderr!r}"
    assert not (tmp_path / "check_embedded_seed7.json").exists(), \
        "contract rule: no result file may be written for invalid --episodes"


# ---------------------------------------------------------------- per-episode checks

def test_run_episode_returns_a_record():
    rec = check_expert.run_episode(SEED_A, "embedded", 0, "early")
    assert isinstance(rec, dict), "contract rule: run_episode must return one record dict"


def _checked_episode(mode, attempt, shift):
    ep = check_expert.CheckedEpisode(
        collect.make_model(), collect.episode_rng(SEED_A, mode, attempt), shift_type=shift)
    res = ep.run(mode)
    assert res["success"], \
        f"precondition: embedded {shift} attempt {attempt} with seed {SEED_A} must succeed for behaviour checks"
    return ep, res


@pytest.mark.parametrize("attempt,shift", [(0, "early"), (1, "late")])
def test_behaviour_checks_agree_with_raw_data(attempt, shift):
    ep, res = _checked_episode("embedded", attempt, shift)
    sel = collect.select(res, "embedded")
    names = check_expert.check_behaviour(res, sel, ep, "embedded")
    assert isinstance(names, list) and all(isinstance(n, str) for n in names), \
        "contract rule: check_behaviour must return a list of name strings"
    assert set(names) <= ALLOWED_CHECKS, \
        f"contract rule: check_behaviour returned unknown names {sorted(set(names) - ALLOWED_CHECKS)}"

    # shift_distance: xy distance outside [SHIFT_MIN, SHIFT_MAX] iff violation
    b0, b1 = res["block_before"], res["block_after"]
    dist = math.hypot(float(b1[0]) - float(b0[0]), float(b1[1]) - float(b0[1]))
    dist_bad = not (collect.SHIFT_MIN <= dist <= collect.SHIFT_MAX)
    assert dist_bad == ("shift_distance" in names), \
        f"contract rule: shift_distance must be flagged iff distance {dist:.4f} is outside [{collect.SHIFT_MIN}, {collect.SHIFT_MAX}]"

    # shift_workspace: block_after xy not in workspace iff violation
    out_ws = not collect.in_workspace(b1[:2])
    assert out_ws == ("shift_workspace" in names), \
        "contract rule: shift_workspace must be flagged iff block_after xy is not in_workspace"

    # shift_clearance: only meaningful after the shift
    if res["shift_frame"] >= 0:
        assert ep.shift_clearance is not None, \
            "contract rule: CheckedEpisode.shift_clearance must be set after a shift"
        low = ep.shift_clearance < collect.CLEARANCE
        assert low == ("shift_clearance" in names), \
            "contract rule: shift_clearance flagged iff shift_clearance < CLEARANCE"

    # contact_before_shift: any substep contact with frame < shift_frame iff violation
    early_contact = any(f < res["shift_frame"] for f, _ in ep.contacts)
    assert early_contact == ("contact_before_shift" in names), \
        "contract rule: contact_before_shift flagged iff a substep contact has frame_index < shift_frame"

    # trigger_height (early only): trigger_z range and crossing
    if shift == "early":
        tz = res["trigger_z"]
        frames = res["frames"]
        sf = res["shift_frame"]
        in_range = collect.TRIGGER_MIN <= tz <= collect.TRIGGER_MAX
        hand = lambda i: float(frames[i]["state"][2]) + collect.HAND_Z0
        crossing_ok = (sf >= 1 and hand(sf - 1) > tz and hand(sf) <= tz)
        bad = (not in_range) or (not crossing_ok)
        assert bad == ("trigger_height" in names), \
            "contract rule: trigger_height flagged iff trigger_z outside [0.12, 0.16] or crossing is wrong"

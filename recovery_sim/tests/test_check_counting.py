"""Counting, failure-accounting, Wilson and pass-rule tests for check_expert.

Tests the contract in .orchestration/contract.md, not the implementation.
Seeds used: 7, 11, 13, 17 (never 100, 200 or 300).
"""

import check_expert
import collect
import pytest

SEED = 7
EPISODES = 4


# ---------------------------------------------------------------- helpers

def _patch_run(monkeypatch, *, raise_on_call=None, force_success=None):
    """Wrap CheckedEpisode.run (inherited from collect.Episode unless overridden).

    Each call to run() is one attempt; checker runs attempts in order 0..N-1,
    so call index == attempt index when there are no retries.
    """
    cls = check_expert.CheckedEpisode
    orig = cls.run
    calls = {"n": 0}

    def run(self, mode, *args, **kwargs):
        idx = calls["n"]
        calls["n"] += 1
        if raise_on_call is not None and idx == raise_on_call:
            raise RuntimeError("injected failure for counting test")
        result = orig(self, mode, *args, **kwargs)
        if force_success is not None:
            result["success"] = force_success
        return result

    monkeypatch.setattr(cls, "run", run)
    return calls


def _patch_select_none(monkeypatch):
    for mod in (collect, check_expert):
        if hasattr(mod, "select"):
            monkeypatch.setattr(mod, "select", lambda result, mode: None)


# ---------------------------------------------------------------- attempts

def test_clean_counts_every_attempt_under_none():
    out = check_expert.check_mode("clean", SEED, episodes=EPISODES)
    assert set(out["by_type"]) == {"none"}, (
        "clean rule: only the 'none' shift type may appear in by_type")
    assert out["by_type"]["none"]["attempts"] == EPISODES, (
        "every attempt counts: clean by_type['none'].attempts must equal episodes")
    assert out["total"]["attempts"] == EPISODES, (
        "every attempt counts: total.attempts must equal episodes")


@pytest.mark.parametrize("mode", ["embedded", "separate"])
def test_early_late_modes_split_attempts_evenly(mode):
    out = check_expert.check_mode(mode, SEED, episodes=EPISODES)
    assert set(out["by_type"]) == {"early", "late"}, (
        f"{mode} rule: by_type must have exactly 'early' and 'late'")
    assert out["by_type"]["early"]["attempts"] == EPISODES // 2, (
        f"{mode} rule: early attempts must equal episodes/2")
    assert out["by_type"]["late"]["attempts"] == EPISODES // 2, (
        f"{mode} rule: late attempts must equal episodes/2")
    assert out["total"]["attempts"] == EPISODES, (
        f"{mode} rule: every attempt counts: total.attempts must equal episodes")


# ---------------------------------------------------------------- failures

def test_exception_is_failure_and_run_continues(monkeypatch):
    baseline = check_expert.check_mode("clean", SEED, episodes=EPISODES)
    assert not any(f["attempt"] == 2 for f in baseline["failures"]), (
        "precondition: attempt 2 must succeed unpatched for the successes-one-lower check")

    calls = _patch_run(monkeypatch, raise_on_call=2)
    out = check_expert.check_mode("clean", SEED, episodes=EPISODES)

    assert out["total"]["attempts"] == EPISODES, (
        "exception rule: an attempt that raises still counts; attempts must be unchanged")
    assert calls["n"] == EPISODES, (
        "exception rule: no retry; run must be called exactly once per attempt")
    assert out["total"]["successes"] == baseline["total"]["successes"] - 1, (
        "exception rule: successes must be exactly one lower than the unpatched run")

    matches = [f for f in out["failures"] if f["attempt"] == 2]
    assert len(matches) == 1, "exception rule: failure list must contain attempt 2 once"
    assert matches[0]["seed"] == SEED, "exception rule: failure must carry the run seed"
    assert matches[0]["reason"].startswith("exception:"), (
        "exception rule: reason must start with 'exception:'")

    attempts = [f["attempt"] for f in out["failures"]]
    assert len(attempts) == len(set(attempts)), (
        "coverage rule: no attempt index may appear twice in failures")
    assert all(0 <= a < EPISODES for a in attempts), (
        "coverage rule: failure attempt indexes must lie in 0..episodes-1")
    assert out["total"]["successes"] + len(attempts) == EPISODES, (
        "coverage rule: successes + failures must cover 0..episodes-1 exactly once")


def test_task_failed_reason(monkeypatch):
    _patch_run(monkeypatch, force_success=False)
    out = check_expert.check_mode("clean", SEED, episodes=EPISODES)
    assert out["total"]["attempts"] == EPISODES, (
        "every attempt counts: forced task failures must still count as attempts")
    assert out["total"]["successes"] == 0, (
        "task failure rule: success False must not count as a success")
    assert len(out["failures"]) == EPISODES, (
        "task failure rule: every forced-False attempt must be listed as a failure")
    assert all(f["reason"] == "task failed" for f in out["failures"]), (
        "task failure rule: reason must be exactly 'task failed'")


def test_select_none_reason(monkeypatch):
    _patch_select_none(monkeypatch)
    out = check_expert.check_mode("clean", SEED, episodes=EPISODES)
    assert out["total"]["attempts"] == EPISODES, (
        "every attempt counts: select-None attempts must still count")
    assert out["total"]["successes"] == 0, (
        "select rule: select returning None must not count as a success")
    assert len(out["failures"]) == EPISODES, (
        "select rule: every select-None attempt must be listed as a failure")
    assert all(f["reason"] == "select returned None" for f in out["failures"]), (
        "select rule: reason must be exactly 'select returned None'")


# ---------------------------------------------------------------- wilson

def test_wilson_zero_n():
    assert check_expert.wilson(0, 0) == (0.0, 1.0), (
        "wilson rule: wilson(0, 0) must be (0.0, 1.0)")


def test_wilson_all_successes():
    lo, hi = check_expert.wilson(200, 200)
    assert abs(lo - 0.9812) < 1e-3, (
        f"wilson rule: wilson(200, 200) lower bound must be about 0.9812, got {lo}")
    assert abs(hi - 1.0) < 1e-9, (
        f"wilson rule: wilson(200, 200) upper bound must be 1.0, got {hi}")


def test_wilson_196_of_200():
    lo, hi = check_expert.wilson(196, 200)
    assert abs(lo - 0.9497) < 1e-3, (
        f"wilson rule: wilson(196, 200) lower bound must be about 0.9497, got {lo}")
    assert abs(hi - 0.9922) < 1e-3, (
        f"wilson rule: wilson(196, 200) upper bound must be about 0.9922, got {hi}")


@pytest.mark.parametrize("k, n", [(0, 5), (1, 1), (5, 5), (3, 10), (196, 200), (199, 200)])
def test_wilson_contains_point_estimate(k, n):
    lo, hi = check_expert.wilson(k, n)
    p = k / n
    assert lo <= p <= hi, (
        f"wilson rule: must satisfy lo <= k/n <= hi for k={k}, n={n}; got ({lo}, {hi})")


# ---------------------------------------------------------------- rate and pass

def _assert_rate_fields(block, label):
    assert block["attempts"] > 0, f"rate rule: {label} must have attempts > 0 for this test"
    expected = block["successes"] / block["attempts"]
    assert block["rate"] == pytest.approx(expected), (
        f"rate rule: {label} rate must equal successes/attempts ({expected}), got {block['rate']}")


def test_rate_equals_successes_over_attempts_with_failures(monkeypatch):
    _patch_run(monkeypatch, raise_on_call=1)
    out = check_expert.check_mode("clean", SEED, episodes=EPISODES)
    _assert_rate_fields(out["total"], "total")
    for key, block in out["by_type"].items():
        _assert_rate_fields(block, f"by_type[{key!r}]")


def test_rate_equals_successes_over_attempts_embedded():
    out = check_expert.check_mode("embedded", SEED, episodes=EPISODES)
    _assert_rate_fields(out["total"], "total")
    for key, block in out["by_type"].items():
        _assert_rate_fields(block, f"by_type[{key!r}]")


def test_pass_formula_holds_on_clean_run():
    out = check_expert.check_mode("clean", SEED, episodes=EPISODES)
    expected = out["total"]["rate"] >= 0.98 and len(out["violations"]) == 0
    assert out["pass"] == expected, (
        "pass rule: pass must equal (total rate >= 0.98 and no violations)")


def test_pass_false_when_all_attempts_fail(monkeypatch):
    _patch_run(monkeypatch, force_success=False)
    out = check_expert.check_mode("clean", SEED, episodes=EPISODES)
    assert out["total"]["rate"] == 0.0, "pass rule setup: rate must be 0 when all attempts fail"
    assert out["pass"] is False, (
        "pass rule: total rate 0 must give pass False")


def test_pass_false_when_one_of_four_fails(monkeypatch):
    _patch_run(monkeypatch, raise_on_call=1)
    out = check_expert.check_mode("clean", SEED, episodes=EPISODES)
    assert out["total"]["rate"] < 0.98, "pass rule setup: 3/4 must be below 0.98"
    assert out["pass"] is False, (
        "pass rule: total rate below 0.98 must give pass False")

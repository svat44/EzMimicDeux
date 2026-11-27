"""Contract tests for check_expert: substep hook, substep contacts, behaviour checks.

Written from .orchestration/contract.md only (not from the implementation).
conftest.py puts recovery_sim on sys.path.
"""
import math
from functools import lru_cache

import numpy as np
import pytest

import check_expert
import collect

SEEDS = (7, 11, 13)  # deliberately not 100, 200 or 300
SEED = 7


@lru_cache(maxsize=None)
def _model():
    return collect.make_model()


def _find_success(cls, mode, shift_type, seed, attempts=12):
    """Run attempts until one succeeds and select() accepts it. Never retries past `attempts`."""
    for i in range(attempts):
        ep = cls(_model(), collect.episode_rng(seed, mode, i), shift_type=shift_type)
        result = ep.run(mode)
        if not result["success"]:
            continue
        sel = collect.select(result, mode)
        if sel is not None:
            return ep, result, sel
    pytest.fail(
        f"setup: no successful {mode}/{shift_type} episode in {attempts} attempts "
        f"(seed {seed}); the rule-based assertions cannot run"
    )


def _assert_same(a, b, where):
    """Deep equality, NaN-aware for float arrays and floats."""
    msg = f"rule: the hook does not change data ({where})"
    if isinstance(a, dict):
        assert isinstance(b, dict) and a.keys() == b.keys(), msg + ": dict keys differ"
        for k in a:
            _assert_same(a[k], b[k], f"{where}.{k}")
    elif isinstance(a, (list, tuple)):
        assert isinstance(b, (list, tuple)) and len(a) == len(b), msg + ": length differs"
        for i, (x, y) in enumerate(zip(a, b)):
            _assert_same(x, y, f"{where}[{i}]")
    elif isinstance(a, np.ndarray) or isinstance(b, np.ndarray):
        aa, bb = np.asarray(a), np.asarray(b)
        assert aa.shape == bb.shape, msg + f": array shape differs at {where}"
        if aa.dtype.kind in "fc" and bb.dtype.kind in "fc":
            same = np.array_equal(aa, bb, equal_nan=True)
        else:
            same = np.array_equal(aa, bb)
        assert same, msg + f": array values differ at {where}"
    elif isinstance(a, float) and math.isnan(a):
        assert isinstance(b, float) and math.isnan(b), msg + f": NaN vs value at {where}"
    else:
        assert a == b, msg + f": {a!r} != {b!r} at {where}"


class _CountingEpisode(check_expert.CheckedEpisode):
    """Counts how often the substep hook fires, and still runs CheckedEpisode's hook."""

    def __init__(self, *args, **kwargs):
        # Set before super().__init__: the settle loop in Episode.__init__ already fires the hook.
        self._test_hook_calls = 0
        super().__init__(*args, **kwargs)

    def on_substep(self):
        self._test_hook_calls = getattr(self, "_test_hook_calls", 0) + 1
        parent = getattr(super(), "on_substep", None)
        if callable(parent):
            parent()


class _BriefContactEpisode(check_expert.CheckedEpisode):
    """Reports block contact for exactly one substep (not substep 0) of one early frame.

    Substep index is the hook call count within the current control step. The frame
    index is len(self.frames) - 1, the same convention the contacts list uses.
    """

    BRIEF_FRAME = 5
    BRIEF_SUBSTEP = 7

    def __init__(self, *args, **kwargs):
        # Set before super().__init__: the settle loop already fires the hook.
        self._hook_frame = None
        self._hook_k = 0
        self._sub = None
        self._in_hook = False
        self.brief_fired = False
        super().__init__(*args, **kwargs)

    def on_substep(self):
        frame = len(self.frames) - 1
        if frame != self._hook_frame:
            self._hook_frame = frame
            self._hook_k = 0
        self._sub = self._hook_k
        self._hook_k += 1
        self._in_hook = True
        try:
            parent = getattr(super(), "on_substep", None)
            if callable(parent):
                parent()
        finally:
            self._in_hook = False

    def _block_contact(self):
        real = super()._block_contact()
        if (
            self._in_hook
            and not self.brief_fired
            and self._hook_frame == self.BRIEF_FRAME
            and self._sub == self.BRIEF_SUBSTEP
        ):
            self.brief_fired = True
            return True
        return real


# --- hook does not change data -------------------------------------------------

@pytest.mark.parametrize("mode", collect.MODES)
def test_hook_does_not_change_data(mode):
    shift_types = ["none"] if mode == "clean" else ["early", "late"]
    for st in shift_types:
        for i in range(2):
            where = f"mode={mode} shift={st} attempt={i}"
            base = collect.Episode(_model(), collect.episode_rng(SEED, mode, i), shift_type=st)
            r_base = base.run(mode)
            s_base = collect.select(r_base, mode)

            hooked = check_expert.CheckedEpisode(
                _model(), collect.episode_rng(SEED, mode, i), shift_type=st
            )
            r_hook = hooked.run(mode)
            s_hook = collect.select(r_hook, mode)

            _assert_same(r_base, r_hook, f"run result, {where}")
            _assert_same(s_base, s_hook, f"select result, {where}")


# --- substep sampling -----------------------------------------------------------

SETTLE_STEPS = 200  # contract: Episode.__init__ settle loop, hook fires on each of these


def test_hook_runs_sim_steps_per_recorded_frame_plus_settle():
    ep = _CountingEpisode(_model(), collect.episode_rng(SEED, "embedded", 0), shift_type="early")
    result = ep.run("embedded")
    n_frames = len(result["frames"])
    expected = collect.SIM_STEPS * n_frames + SETTLE_STEPS
    assert n_frames > 0, "rule: substep sampling (episode recorded no frames)"
    assert ep._test_hook_calls == expected, (
        f"rule: substep sampling (hook must run SIM_STEPS={collect.SIM_STEPS} times per "
        f"recorded frame plus {SETTLE_STEPS} settle-loop calls; expected {expected}, "
        f"got {ep._test_hook_calls} for {n_frames} frames)"
    )


# --- substep contacts recorded ---------------------------------------------------

def test_substep_contacts_recorded_at_or_after_grasp_start():
    ep, result, sel = _find_success(check_expert.CheckedEpisode, "embedded", "early", SEED)
    grips = [float(f["action"][3]) for f in result["frames"]]
    closed = [i for i, g in enumerate(grips) if np.isclose(g, collect.CLOSED)]
    assert closed, "rule: substep contacts (no CLOSED grip action in a successful episode)"
    grasp_start = closed[0]

    frames_with_contact = [fi for fi, _sub in ep.contacts]
    assert frames_with_contact, "rule: substep contacts (ep.contacts is empty for a successful grasp)"
    assert any(fi >= grasp_start for fi in frames_with_contact), (
        f"rule: substep contacts (no contact entry at or after grasp_start={grasp_start}; "
        f"contacts={ep.contacts[:10]})"
    )

    violations = check_expert.check_behaviour(result, sel, ep, "embedded")
    assert "early_contact_before_grasp" not in violations, (
        "rule: the intended grasp contact is never a violation (early_contact_before_grasp "
        f"reported; violations={violations})"
    )


# --- brief contact caught even when touch misses it -----------------------------

def test_brief_contact_caught_when_touch_misses_it():
    ep, result, sel = _find_success(_BriefContactEpisode, "embedded", "early", SEED)
    assert ep.brief_fired, "setup: the forced single-substep contact was never injected"
    assert result["shift_frame"] > _BriefContactEpisode.BRIEF_FRAME, (
        f"setup: shift_frame={result['shift_frame']} is not after the brief-contact frame "
        f"{_BriefContactEpisode.BRIEF_FRAME}"
    )
    recorded = [tuple(c) for c in ep.contacts]
    assert (_BriefContactEpisode.BRIEF_FRAME, _BriefContactEpisode.BRIEF_SUBSTEP) in recorded, (
        f"rule: substep contacts are recorded (injected contact missing from ep.contacts)"
    )

    touch = result["frames"][_BriefContactEpisode.BRIEF_FRAME]["touch"]
    assert not bool(touch), (
        "rule: touch is a 20 Hz sample and misses a brief substep contact "
        f"(touch at frame {_BriefContactEpisode.BRIEF_FRAME} is {touch!r}, expected False)"
    )

    violations = check_expert.check_behaviour(result, sel, ep, "embedded")
    assert "contact_before_shift" in violations, (
        "rule: any substep contact with frame_index < shift_frame is contact_before_shift "
        f"(violations={violations})"
    )


# --- each named violation is reachable -----------------------------------------

def test_violation_shift_distance_reachable():
    ep, result, sel = _find_success(check_expert.CheckedEpisode, "embedded", "early", SEED)
    ba = np.array(result["block_after"], dtype=float, copy=True)
    ba[0] += 0.2  # moves the block well outside [0.07, 0.10]
    tampered = dict(result, block_after=ba)
    violations = check_expert.check_behaviour(tampered, sel, ep, "embedded")
    assert "shift_distance" in violations, (
        f"rule: shift_distance must fire when block_after moves out of [0.07, 0.10] "
        f"(violations={violations})"
    )


def test_violation_trigger_height_reachable():
    ep, result, sel = _find_success(check_expert.CheckedEpisode, "embedded", "early", SEED)
    tampered = dict(result, trigger_z=0.2)  # outside [0.12, 0.16]
    violations = check_expert.check_behaviour(tampered, sel, ep, "embedded")
    assert "trigger_height" in violations, (
        f"rule: trigger_height must fire when trigger_z is outside [0.12, 0.16] "
        f"(violations={violations})"
    )


def test_violation_late_shift_step_reachable():
    ep, result, sel = _find_success(check_expert.CheckedEpisode, "embedded", "late", SEED)
    tampered = dict(result, shift_frame=int(result["shift_frame"]) + 1)
    violations = check_expert.check_behaviour(tampered, sel, ep, "embedded")
    assert "late_shift_step" in violations, (
        "rule: late_shift_step must fire when shift_frame is not the first CLOSED frame "
        f"(violations={violations})"
    )


def test_violation_separate_window_reachable():
    ep, result, sel = _find_success(check_expert.CheckedEpisode, "separate", "early", SEED)
    tampered_sel = dict(sel, train_start=int(sel["train_start"]) + 1)
    violations = check_expert.check_behaviour(result, tampered_sel, ep, "separate")
    assert "separate_window" in violations, (
        "rule: separate_window must fire when train_start is off by one "
        f"(violations={violations})"
    )


def test_violation_early_redirect_reachable():
    ep, result, sel = _find_success(check_expert.CheckedEpisode, "embedded", "early", SEED)
    sf = int(result["shift_frame"])
    frames = list(result["frames"])
    prev_action = np.asarray(frames[sf - 1]["action"], dtype=float)
    bad = dict(frames[sf])
    bad_action = np.array(frames[sf]["action"], dtype=float, copy=True)
    bad_action[:2] = prev_action[:2]  # same xy as the previous frame: not closer to block_after
    bad["action"] = bad_action
    frames[sf] = bad
    tampered = dict(result, frames=frames)
    violations = check_expert.check_behaviour(tampered, sel, ep, "embedded")
    assert "early_redirect" in violations, (
        "rule: early_redirect must fire when the action xy at shift_frame is not closer to "
        f"block_after than at shift_frame-1 (violations={violations})"
    )


def test_real_early_episode_has_no_early_redirect():
    ep, result, sel = _find_success(check_expert.CheckedEpisode, "embedded", "early", SEED)
    violations = check_expert.check_behaviour(result, sel, ep, "embedded")
    assert "early_redirect" not in violations, (
        f"rule: the expert must redirect at once on a real early episode (violations={violations})"
    )


class _PreShiftContactEpisode(check_expert.CheckedEpisode):
    """Forces the contact test to report True once, during the CheckedEpisode shift_block copy check.

    Arms a flag before calling super().shift_block, so the first _block_contact call made inside
    it (the pre-shift copy check, which the contract says runs before the real shift) is True.
    Assumes the copy-based check calls self._block_contact(). If it does not, the test fails.
    """

    def __init__(self, *args, **kwargs):
        self._armed = False
        self.pre_shift_fired = False
        super().__init__(*args, **kwargs)

    def shift_block(self, *args, **kwargs):
        self._armed = True
        try:
            return super().shift_block(*args, **kwargs)
        finally:
            self._armed = False

    def _block_contact(self):
        real = super()._block_contact()
        if self._armed and not self.pre_shift_fired:
            self.pre_shift_fired = True
            return True
        return real


def test_pre_shift_sample_triggers_contact_before_shift():
    ep, result, sel = _find_success(_PreShiftContactEpisode, "embedded", "early", SEED)
    assert ep.pre_shift_fired, (
        "setup: the pre-shift copy check never called _block_contact (the forced contact was "
        "not injected); check how CheckedEpisode.shift_block tests contact"
    )
    sf = int(result["shift_frame"])
    assert (sf - 1, 25) in [tuple(c) for c in ep.contacts], (
        f"rule: the pre-shift sample (shift_frame-1, 25) must be recorded in ep.contacts "
        f"(sf={sf}, contacts tail={ep.contacts[-5:]})"
    )
    violations = check_expert.check_behaviour(result, sel, ep, "embedded")
    assert "contact_before_shift" in violations, (
        "rule: any contact sample with f < shift_frame, including the pre-shift sample "
        f"(sf-1, 25), is contact_before_shift (violations={violations})"
    )


def _contacts_outside_grasp_window(ep, sf, gs):
    """Real contacts minus those lexicographically in [(sf, 0), (gs, 0)], so the injected
    sample is the only thing that can cause or hide the early_contact_before_grasp violation."""
    return [tuple(c) for c in ep.contacts if not ((sf, 0) <= tuple(c) <= (gs, 0))]


def _grasp_start(result):
    grips = [float(f["action"][3]) for f in result["frames"]]
    closed = [i for i, g in enumerate(grips) if np.isclose(g, collect.CLOSED)]
    assert closed, "rule: grasp_start (no CLOSED grip action in a successful episode)"
    return closed[0]


def test_contact_at_grasp_start_substep0_is_early_contact_before_grasp():
    ep, result, sel = _find_success(check_expert.CheckedEpisode, "embedded", "early", SEED)
    sf, gs = int(result["shift_frame"]), _grasp_start(result)
    assert gs >= sf, f"setup: grasp_start={gs} is before shift_frame={sf}"
    ep.contacts = _contacts_outside_grasp_window(ep, sf, gs) + [(gs, 0)]
    violations = check_expert.check_behaviour(result, sel, ep, "embedded")
    assert "early_contact_before_grasp" in violations, (
        f"rule: a contact sample (grasp_start={gs}, 0) is early_contact_before_grasp "
        f"(violations={violations})"
    )


def test_contact_at_grasp_start_substep1_is_not_early_contact_before_grasp():
    ep, result, sel = _find_success(check_expert.CheckedEpisode, "embedded", "early", SEED)
    sf, gs = int(result["shift_frame"]), _grasp_start(result)
    assert gs >= sf, f"setup: grasp_start={gs} is before shift_frame={sf}"
    ep.contacts = _contacts_outside_grasp_window(ep, sf, gs) + [(gs, 1)]
    violations = check_expert.check_behaviour(result, sel, ep, "embedded")
    assert "early_contact_before_grasp" not in violations, (
        f"rule: a contact sample (grasp_start={gs}, 1) is after (grasp_start, 0) and must not be "
        f"early_contact_before_grasp (violations={violations})"
    )


# --- clean episodes ---------------------------------------------------------------

@pytest.mark.parametrize("seed", SEEDS)
def test_clean_episodes_return_no_violations(seed):
    ep, result, sel = _find_success(check_expert.CheckedEpisode, "clean", "none", seed)
    violations = check_expert.check_behaviour(result, sel, ep, "clean")
    assert violations == [], (
        f"rule: clean episodes return no violations (seed {seed}); got {violations}"
    )

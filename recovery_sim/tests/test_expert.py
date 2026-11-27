"""Behaviour tests for the scripted expert in recovery_sim/collect.py.

These test the interface contract (.orchestration/contract.md), not the
implementation. Episodes are run with fixed seed and attempt indices, and
only successful episodes are used for behaviour asserts.
"""

import numpy as np
import pytest

import collect

SEED = 0
N_EPISODES = 20
MIN_SUCCESS = 15
GRIP_TOL = 1e-4


@pytest.fixture(scope="module")
def runs_by_mode_kind():
    model = collect.make_model()
    out = {}
    for mode in collect.MODES:
        # clean always uses shift_type "none"; embedded/separate use early/late.
        kinds = ("none",) if mode == "clean" else ("early", "late")
        for kind in kinds:
            results = []
            for attempt in range(N_EPISODES):
                rng = collect.episode_rng(SEED, mode, attempt)
                ep = collect.Episode(model, rng, renderer=None, shift_type=kind)
                results.append(ep.run(mode))
            out[(mode, kind)] = results
            n_ok = sum(1 for r in results if r["success"])
            # Report only: success rate is not asserted here.
            print(f"[report] {mode} {kind}: {n_ok}/{N_EPISODES} episodes succeeded")
    return out


def _successful(runs_by_mode_kind, mode, kind):
    results = runs_by_mode_kind[(mode, kind)]
    ok = [r for r in results if r["success"]]
    assert len(ok) >= MIN_SUCCESS, (
        f"{mode}/{kind}: only {len(ok)} of {N_EPISODES} episodes succeeded; "
        f"need at least {MIN_SUCCESS} so the behaviour asserts mean something"
    )
    return ok


def _arrays(res):
    frames = res["frames"]
    state = np.asarray([f["state"] for f in frames], dtype=float)
    action = np.asarray([f["action"] for f in frames], dtype=float)
    block = np.asarray([f["block_pos"] for f in frames], dtype=float)
    touch = np.asarray([bool(f["touch"]) for f in frames])
    return state, action, block, touch


def _dxy(p, q):
    """Distance in the xy plane; works on single points or arrays of points."""
    p = np.asarray(p, dtype=float)
    q = np.asarray(q, dtype=float)
    return np.linalg.norm(p[..., :2] - q[..., :2], axis=-1)


def _closed(action):
    return np.abs(action[:, 3] - collect.CLOSED) < GRIP_TOL


def _open(action):
    return np.abs(action[:, 3] - collect.OPEN) < GRIP_TOL


def _runs(mask, offset=0):
    """Maximal runs of True in mask, as (start, end_inclusive) plus offset."""
    out = []
    i, n = 0, len(mask)
    while i < n:
        if mask[i]:
            j = i
            while j + 1 < n and mask[j + 1]:
                j += 1
            out.append((i + offset, j + offset))
            i = j + 1
        else:
            i += 1
    return out


SHIFT_MODES = ("embedded", "separate")


@pytest.mark.parametrize("mode", SHIFT_MODES)
def test_early_redirect(mode, runs_by_mode_kind):
    for res in _successful(runs_by_mode_kind, mode, "early"):
        assert res["shift_type"] == "early", f"{mode}: early episode has shift_type {res['shift_type']!r}"
        s = res["shift_frame"]
        after = np.asarray(res["block_after"], dtype=float)
        state, action, block, touch = _arrays(res)
        assert s >= 1, f"{mode}: early shift_frame={s} leaves no frame before it to compare with"

        # Redirect at once: action xy at shift_frame closer to block_after than at shift_frame - 1.
        d_now = _dxy(action[s], after)
        d_prev = _dxy(action[s - 1], after)
        assert d_now < d_prev, (
            f"{mode}: early redirect broke: action xy at shift_frame is not closer to "
            f"block_after than at shift_frame-1 ({d_now:.4f} >= {d_prev:.4f})"
        )

        # Exactly one run of CLOSED grip actions from the shift onward.
        closed_runs = _runs(_closed(action[s:]), offset=s)
        assert len(closed_runs) == 1, (
            f"{mode}: early expert must close once after the shift, found {len(closed_runs)} closed runs"
        )
        start, end = closed_runs[0]

        # The close starts within 1 cm of the new block xy (no closing on empty space).
        assert _dxy(action[start], after) < 0.01, (
            f"{mode}: early close starts {_dxy(action[start], after) * 100:.2f} cm from block_after xy (limit 1 cm)"
        )

        # Fingers have closed on the block at the last closed frame.
        assert state[end, 3] < collect.GRIP_EMPTY and state[end, 4] < collect.GRIP_EMPTY, (
            f"{mode}: early close ends with fingers {state[end, 3]:.4f}, {state[end, 4]:.4f}, "
            f"not both below GRIP_EMPTY={collect.GRIP_EMPTY}"
        )

        # No contact and no block movement from the shift up to the start of the close.
        window = slice(s, start + 1)
        assert not touch[window].any(), (
            f"{mode}: early expert touched the block between shift_frame and the start of the close"
        )
        moved = _dxy(block[window], after)
        assert np.all(moved < 0.005), (
            f"{mode}: early block moved {moved.max() * 1000:.2f} mm from block_after before the close (limit 5 mm)"
        )


@pytest.mark.parametrize("mode", SHIFT_MODES)
def test_late_empty_close_then_regrasp(mode, runs_by_mode_kind):
    for res in _successful(runs_by_mode_kind, mode, "late"):
        assert res["shift_type"] == "late", f"{mode}: late episode has shift_type {res['shift_type']!r}"
        s = res["shift_frame"]
        after = np.asarray(res["block_after"], dtype=float)
        state, action, block, touch = _arrays(res)
        closed = _closed(action)
        runs = _runs(closed)
        assert len(runs) >= 2, (
            f"{mode}: late episode needs an empty close and a regrasp close, found {len(runs)} closed runs"
        )

        # First closed run is the empty close and starts at the shift.
        c0, c1 = runs[0]
        assert c0 == s, f"{mode}: first CLOSED run starts at {c0}, expected shift_frame={s}"
        assert c1 - c0 + 1 >= 10, (
            f"{mode}: empty close lasts {c1 - c0 + 1} frames, needs at least 10 to finish closing"
        )
        assert not touch[c0:c1 + 1].any(), f"{mode}: late expert touched the block during the empty close"
        assert state[c1, 3] > collect.GRIP_EMPTY and state[c1, 4] > collect.GRIP_EMPTY, (
            f"{mode}: empty close ends with fingers {state[c1, 3]:.4f}, {state[c1, 4]:.4f}, "
            f"not above GRIP_EMPTY={collect.GRIP_EMPTY} (should be an empty close)"
        )

        # Second close is the regrasp; between them the grip opens and the hand rises.
        c2, c3 = runs[1]
        between = slice(c1 + 1, c2)
        assert _open(action[between]).any(), f"{mode}: grip did not open between the empty close and the regrasp"
        hand_z = state[:, 2] + collect.HAND_Z0
        assert (hand_z[between] >= collect.HIGH_Z - 0.01).any(), (
            f"{mode}: hand never rose to HIGH_Z-0.01 between the two closes "
            f"(max {hand_z[between].max():.4f})"
        )
        assert _dxy(action[c2], after) < 0.01, (
            f"{mode}: regrasp close starts {_dxy(action[c2], after) * 100:.2f} cm from block_after xy (limit 1 cm)"
        )
        assert state[c3, 3] < collect.GRIP_EMPTY and state[c3, 4] < collect.GRIP_EMPTY, (
            f"{mode}: regrasp ends with fingers {state[c3, 3]:.4f}, {state[c3, 4]:.4f}, "
            f"not both below GRIP_EMPTY={collect.GRIP_EMPTY}"
        )


@pytest.mark.parametrize(
    "mode,kind",
    [("clean", "none"), ("embedded", "early"), ("embedded", "late"),
     ("separate", "early"), ("separate", "late")],
)
def test_expert_delivers_to_bowl(mode, kind, runs_by_mode_kind):
    bowl_xy = np.asarray(collect.BOWL, dtype=float)[:2]
    for res in _successful(runs_by_mode_kind, mode, kind):
        state, action, _, _ = _arrays(res)
        tail = slice(-5, None)
        dist = _dxy(state[tail], bowl_xy)
        assert np.all(dist < 0.02), (
            f"{mode}/{kind}: final frames not over the bowl; hand xy is "
            f"{dist.max() * 100:.2f} cm from BOWL at worst (limit 2 cm)"
        )
        assert _open(action[tail]).all(), (
            f"{mode}/{kind}: grip is not OPEN in the final frames of a successful run"
        )


def test_early_no_touch_before_close_300_episodes():
    """Regardless of success: no block contact from shift_frame until the first CLOSED grip action."""
    model = collect.make_model()
    bad = []
    for i in range(300):
        rng = collect.episode_rng(SEED, "embedded", i)
        ep = collect.Episode(model, rng, renderer=None, shift_type="early")
        res = ep.run("embedded")
        s = res["shift_frame"]
        if s < 0:
            bad.append((i, "no shift happened"))
            continue
        _, action, _, touch = _arrays(res)
        closed = np.where(_closed(action))[0]
        end = int(closed[0]) if closed.size else len(action)
        if touch[s:end].any():
            bad.append((i, "touch before first CLOSED"))
    assert not bad, (
        f"early expert touched the block before the first CLOSED grip action in "
        f"{len(bad)} of 300 episodes; first bad (index, reason): {bad[:5]}"
    )

"""S3 tests: action chunks, history frames and episode boundaries.

Synthetic source episodes (the "Source episodes" npz format from the contract)
are written under tmp_path_factory, planned by hand, and built into a small
LeRobot dataset with convert.build(). Nothing outside this file is read.

Run with the LeRobot venv:
  cd recovery_sim && env -u PYTHONPATH PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 \
      .venv-lerobot/bin/python -m pytest tests/test_s3_chunks.py -q
"""

import hashlib
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

ACTION_CHUNK = 40
HISTORY_OFFSETS = (-20, -10, 0)
SET_NAME = "separate"
SEED = 1002


def _action_value(ep, t):
    """Distinct per (episode, frame): the episode index is encoded in the value."""
    return (ep * 10000 + t * 10 + np.arange(4)).astype(np.float32)


def _state_value(ep, t):
    return ((ep * 10000 + t * 10 + np.arange(5)) + 0.5).astype(np.float32)


def _np(x):
    return x.numpy() if hasattr(x, "numpy") else np.asarray(x)


def _expected_actions(ep, t0, count):
    return np.stack([_action_value(ep, t) for t in range(t0, t0 + count)])


def _closest_frame(img, frames):
    """Index of the frame whose pixels are closest (mean abs diff) to img."""
    img = np.asarray(img, dtype=np.float32)
    if img.shape[0] == 3:  # CHW -> HWC
        img = np.transpose(img, (1, 2, 0))
    if img.max() <= 1.0:  # LeRobot returns float in [0, 1]
        img = img * 255.0
    diffs = [float(np.mean(np.abs(img - f.astype(np.float32)))) for f in frames]
    return int(np.argmin(diffs))


def _write_episode(path, ep, length, n_context, shift_type, rng):
    """Write one source episode in the contract's npz layout. Returns (top, wrist)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    t = np.arange(length)
    action = np.stack([_action_value(ep, i) for i in t])
    state = np.stack([_state_value(ep, i) for i in t])
    train = np.ones(length, dtype=bool)
    train[:n_context] = False
    top = rng.integers(0, 256, size=(length, 240, 320, 3), dtype=np.uint8)
    wrist = rng.integers(0, 256, size=(length, 240, 320, 3), dtype=np.uint8)
    np.savez(
        path,
        state=state,
        action=action,
        block_pos=np.zeros((length, 3), dtype=np.float32),
        touch=np.zeros(length, dtype=bool),
        train=train,
        top=top,
        wrist=wrist,
        shift_type=np.array(shift_type),
        shift_frame=np.int64(-1),
        shift_frame_full=np.int64(-1),
        train_start=np.int64(n_context),
        train_end=np.int64(length),
        seed=np.int64(SEED),
        attempt=np.int64(0),
        trigger_z=np.float64(np.nan),
        block_before=np.full(3, np.nan),
        block_after=np.full(3, np.nan),
    )
    return top, wrist


def _plan_entry(raw, rel, n_frames, n_train, trimmed, removed, shift_type):
    sha = hashlib.sha256((raw / rel).read_bytes()).hexdigest()
    return {
        "file": rel,
        "sha256": sha,
        "n_frames": n_frames,
        "n_train": n_train,
        "trimmed": trimmed,
        "frames_removed": removed,
        "shift_type": shift_type,
    }


@pytest.fixture(scope="module")
def chunk_env(tmp_path_factory):
    pytest.importorskip("lerobot")
    import convert

    root = tmp_path_factory.mktemp("s3_chunks")
    raw = root / "raw"
    out = root / "datasets"
    rng = np.random.default_rng(0)

    episodes = []  # dataset episode order: base 0..2, then extras
    start = 0

    # Three base episodes (clean, all frames train).
    plan_base = []
    for i, length in enumerate((60, 50, 40)):
        rel = f"base/clean_seed1000/episode_{i:04d}.npz"
        top, wrist = _write_episode(raw / rel, i, length, 0, "none", rng)
        plan_base.append(_plan_entry(raw, rel, length, length, False, 0, "none"))
        episodes.append(SimpleNamespace(ep=i, start=start, n=length, top=top[:length], wrist=wrist[:length]))
        start += length

    # Extra A: separate-style, 5 context frames then 60 train frames. Kept whole.
    rel_a = f"{SET_NAME}/{SET_NAME}_seed{SEED}/episode_0000.npz"
    top_a, wrist_a = _write_episode(raw / rel_a, 3, 65, 5, "early", rng)
    plan_a = _plan_entry(raw, rel_a, 65, 60, False, 0, "early")
    episodes.append(SimpleNamespace(ep=3, start=start, n=65, top=top_a, wrist=wrist_a))
    start += 65

    # Extra B: 70 train frames, cut to 40 so extra train total is exactly 100.
    rel_b = f"{SET_NAME}/{SET_NAME}_seed{SEED}/episode_0001.npz"
    top_b, wrist_b = _write_episode(raw / rel_b, 4, 70, 0, "none", rng)
    plan_b = _plan_entry(raw, rel_b, 40, 40, True, 30, "none")
    episodes.append(SimpleNamespace(ep=4, start=start, n=40, top=top_b[:40], wrist=wrist_b[:40]))
    start += 40

    plan = {
        "base": plan_base,
        "control": [],
        SET_NAME: [plan_a, plan_b],
        "embedded": [],
        "seeds": {"base": 1000, "control": 1001, SET_NAME: SEED, "embedded": 1003},
    }

    convert.build(SET_NAME, plan, raw, out)
    return SimpleNamespace(convert=convert, out=out, episodes=episodes, total=start)


def _episode(env, ep_index):
    return next(e for e in env.episodes if e.ep == ep_index)


@pytest.fixture(scope="module")
def chunk_ds(chunk_env):
    return chunk_env.convert.load(
        SET_NAME, chunk_env.out, delta_timestamps=chunk_env.convert.chunk_delta_timestamps()
    )


@pytest.fixture(scope="module")
def history_ds(chunk_env):
    return chunk_env.convert.load(
        SET_NAME, chunk_env.out, delta_timestamps=chunk_env.convert.history_delta_timestamps()
    )


# ---------------------------------------------------------------- chunks


def test_chunk_at_last_frame_is_padded_past_episode_end(chunk_env, chunk_ds):
    for ep in chunk_env.episodes:
        item = chunk_ds[ep.start + ep.n - 1]
        action = _np(item["action"])
        pad = _np(item["action_is_pad"]).astype(bool)

        assert action.shape == (ACTION_CHUNK, 4), (
            f"chunk rule: an item must return {ACTION_CHUNK} actions, got shape {action.shape} "
            f"(episode {ep.ep}, last frame)"
        )
        assert not pad[0], (
            f"chunk rule: step 0 is the frame itself and must not be padded (episode {ep.ep})"
        )
        assert pad[1:].all(), (
            f"chunk rule: steps past the episode end must be flagged in action_is_pad (episode {ep.ep})"
        )
        np.testing.assert_array_equal(
            action[~pad],
            _expected_actions(ep.ep, ep.n - 1, 1),
            err_msg=f"chunk rule: non-padded steps must equal the source actions (episode {ep.ep})",
        )

        nxt = next((e for e in chunk_env.episodes if e.ep == ep.ep + 1), None)
        if nxt is not None:
            next_vals = [_action_value(nxt.ep, t) for t in range(nxt.n)]
            for row in action[pad]:
                for v in next_vals:
                    assert not np.array_equal(row, v), (
                        f"chunk rule: padded values must never come from the next episode "
                        f"(episode {ep.ep} leaked from episode {nxt.ep})"
                    )


def test_chunk_far_from_end_has_no_padding(chunk_env, chunk_ds):
    checked = 0
    for ep in chunk_env.episodes:
        t = ep.n - ACTION_CHUNK - 1  # at least 40 frames remain after this one
        if t < 0:
            continue
        checked += 1
        item = chunk_ds[ep.start + t]
        action = _np(item["action"])
        pad = _np(item["action_is_pad"]).astype(bool)
        assert not pad.any(), (
            f"chunk rule: an item 40+ frames from the episode end must have no padding "
            f"(episode {ep.ep}, frame {t})"
        )
        np.testing.assert_array_equal(
            action,
            _expected_actions(ep.ep, t, ACTION_CHUNK),
            err_msg=f"chunk rule: far-from-end chunk must equal source actions (episode {ep.ep}, frame {t})",
        )
    assert checked > 0, "chunk rule: no episode was long enough to test the no-padding case"


# ---------------------------------------------------------------- history


@pytest.mark.parametrize("ep_index", [0, 1, 3])
def test_history_at_episode_start_repeats_first_frame(chunk_env, history_ds, ep_index):
    ep = _episode(chunk_env, ep_index)
    item = history_ds[ep.start]
    state = _np(item["observation.state"])
    assert state.shape[0] == len(HISTORY_OFFSETS), (
        f"history rule: expected {len(HISTORY_OFFSETS)} history steps, got shape {state.shape} "
        f"(episode {ep.ep}, frame 0)"
    )
    first = _state_value(ep.ep, 0)
    for j in (0, 1):
        np.testing.assert_array_equal(
            state[j],
            first,
            err_msg=(
                f"history rule: offset {HISTORY_OFFSETS[j]} at episode frame 0 must return frame 0 "
                f"(episode {ep.ep})"
            ),
        )
    for cam, frames in (("top", ep.top), ("wrist", ep.wrist)):
        img = _np(item[f"observation.images.{cam}"])
        for j in (0, 1):
            assert _closest_frame(img[j], frames) == 0, (
                f"history rule: {cam} image at offset {HISTORY_OFFSETS[j]} at frame 0 must be frame 0 "
                f"(episode {ep.ep})"
            )


def test_history_mid_episode_returns_frames_5_15_25(chunk_env, history_ds):
    ep = _episode(chunk_env, 0)
    item = history_ds[ep.start + 25]
    state = _np(item["observation.state"])
    expected_frames = (5, 15, 25)
    for j, frame in enumerate(expected_frames):
        np.testing.assert_array_equal(
            state[j],
            _state_value(ep.ep, frame),
            err_msg=(
                f"history rule: offset {HISTORY_OFFSETS[j]} at episode frame 25 must return frame {frame}"
            ),
        )
    for cam, frames in (("top", ep.top), ("wrist", ep.wrist)):
        img = _np(item[f"observation.images.{cam}"])
        for j, frame in enumerate(expected_frames):
            assert _closest_frame(img[j], frames) == frame, (
                f"history rule: {cam} image at offset {HISTORY_OFFSETS[j]} at episode frame 25 "
                f"must be closest to frame {frame}"
            )


# ---------------------------------------------------------------- boundaries


def test_episode_index_matches_source_episode_for_every_item(chunk_env):
    ds = chunk_env.convert.load(SET_NAME, chunk_env.out, delta_timestamps=None)
    assert len(ds) == chunk_env.total, (
        f"boundary rule: dataset must hold exactly {chunk_env.total} frames, got {len(ds)}"
    )
    for ep in chunk_env.episodes:
        for t in range(ep.n):
            g = ep.start + t
            got = int(_np(ds[g]["episode_index"]))
            assert got == ep.ep, (
                f"boundary rule: global index {g} (episode {ep.ep}, frame {t}) "
                f"has episode_index {got}"
            )

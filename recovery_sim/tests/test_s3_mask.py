"""S3 mask tests for the LeRobot conversion, written from .orchestration/contract.md.

Tests the public API of recovery_sim/convert.py only (build, load, train_indices,
train_loader, train_stats). Synthetic source episodes are written by this file's
own module-scoped fixture; no shared conftest is used.
"""

import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pytest

RECOVERY_SIM = Path(__file__).resolve().parents[1]
if str(RECOVERY_SIM) not in sys.path:
    sys.path.insert(0, str(RECOVERY_SIM))

NAME = "separate"
N_BASE = 3
BASE_T = 40
EXTRA_T = 30
N_CTX = 5

# (code, shift_type, shift_frame, n_frames kept, n_train kept, trimmed, frames_removed)
# Extras 0 and 1 are used in full (25 train each). Extra 2 is cut so the running
# extra train total is exactly 25 + 25 + 14 = 64. Its kept length k = N_CTX + 14 = 19.
EXTRA_SPECS = [
    (3, "early", 12, EXTRA_T, 25, False, 0),
    (4, "late", 22, EXTRA_T, 25, False, 0),
    (5, "early", 9, N_CTX + 14, 14, True, EXTRA_T - (N_CTX + 14)),
]
NON_FEATURES = [
    "block_pos",
    "touch",
    "shift_type",
    "shift_frame",
    "shift_frame_full",
    "trigger_z",
    "block_before",
    "block_after",
]


def make_episode(rng, T, code, n_ctx, shift_type, shift_frame, seed):
    """One source episode in the contract's npz layout with distinct per-frame values.

    state[:, 0] and action[:, 0] encode code*100 + frame, so each frame is identifiable.
    Context frames (train False) get extreme values 1e3 in state and action.
    """
    state = rng.uniform(-1, 1, (T, 5)).astype(np.float32)
    state[:, 0] = code * 100 + np.arange(T)
    action = rng.uniform(-1, 1, (T, 4)).astype(np.float32)
    action[:, 0] = code * 100 + np.arange(T) + 0.5
    train = np.ones(T, dtype=bool)
    if n_ctx:
        train[:n_ctx] = False
        state[:n_ctx] = 1000.0
        action[:n_ctx] = 1000.0
    return {
        "state": state,
        "action": action,
        "block_pos": rng.uniform(-1, 1, (T, 3)).astype(np.float32),
        "touch": rng.integers(0, 2, T).astype(bool),
        "train": train,
        "top": rng.integers(0, 256, (T, 240, 320, 3), dtype=np.uint8),
        "wrist": rng.integers(0, 256, (T, 240, 320, 3), dtype=np.uint8),
        "shift_type": np.str_(shift_type),
        "shift_frame": np.int64(shift_frame),
        "shift_frame_full": np.int64(shift_frame),
        "train_start": np.int64(n_ctx),
        "train_end": np.int64(T),
        "seed": np.int64(seed),
        "attempt": np.int64(0),
        "trigger_z": np.float64(np.nan),
        "block_before": np.full(3, np.nan),
        "block_after": np.full(3, np.nan),
    }


def write_episode(raw, rel, arrays, n_frames, n_train, trimmed, removed):
    path = raw / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez(path, **arrays)
    sha = hashlib.sha256(path.read_bytes()).hexdigest()
    assert int(arrays["train"][:n_frames].sum()) == n_train, (
        "fixture bug: n_train does not match the source train mask"
    )
    return {
        "file": rel,
        "sha256": sha,
        "n_frames": n_frames,
        "n_train": n_train,
        "trimmed": trimmed,
        "frames_removed": removed,
        "shift_type": str(arrays["shift_type"]),
    }


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    pytest.importorskip("lerobot")
    import convert  # recovery_sim/convert.py, LeRobot environment

    root = tmp_path_factory.mktemp("s3_mask")
    raw = root / "raw"
    out = root / "datasets"
    rng = np.random.default_rng(1234)

    base_entries, extra_entries, kept = [], [], []
    for i in range(N_BASE):
        rel = f"base/clean_seed1000/episode_{i:04d}.npz"
        arrays = make_episode(rng, BASE_T, i, 0, "none", -1, 1000)
        entry = write_episode(raw, rel, arrays, BASE_T, BASE_T, False, 0)
        base_entries.append(entry)
        kept.append((entry, arrays))

    for j, (code, shift, sf, n_frames, n_train, trimmed, removed) in enumerate(EXTRA_SPECS):
        rel = f"{NAME}/{NAME}_seed1002/episode_{j:04d}.npz"
        arrays = make_episode(rng, EXTRA_T, code, N_CTX, shift, sf, 1002)
        entry = write_episode(raw, rel, arrays, n_frames, n_train, trimmed, removed)
        extra_entries.append(entry)
        kept.append((entry, arrays))

    plan = {"base": base_entries, NAME: extra_entries, "seeds": {"base": 1000, NAME: 1002}}
    convert.build(NAME, plan, raw, out)
    ds = convert.load(NAME, out)
    manifest = out / "manifests" / f"{NAME}.json"

    offset = 0
    expected_train, expected_ctx, expected_pairs = [], [], []
    train_state, train_action, all_state = [], [], []
    for ep_idx, (entry, arrays) in enumerate(kept):
        n = entry["n_frames"]
        tr = arrays["train"][:n]
        for t in range(n):
            g = offset + t
            if tr[t]:
                expected_train.append(g)
                expected_pairs.append((ep_idx, t))
            else:
                expected_ctx.append(g)
        train_state.append(arrays["state"][:n][tr])
        train_action.append(arrays["action"][:n][tr])
        all_state.append(arrays["state"][:n])
        offset += n

    expected_train = np.array(expected_train, dtype=np.int64)
    train_state = np.concatenate(train_state)
    train_action = np.concatenate(train_action)
    all_state = np.concatenate(all_state)
    assert len(expected_ctx) == N_CTX * len(EXTRA_SPECS), "fixture bug: context frame count"
    assert len(ds) == offset, (
        "dataset must hold the 3 base episodes plus the trimmed extras, frame for frame"
    )
    assert not np.allclose(all_state.mean(0), train_state.mean(0)), (
        "fixture bug: context frames must make an all-frames mean differ from the train mean"
    )

    return {
        "convert": convert,
        "ds": ds,
        "out": out,
        "raw": raw,
        "plan": plan,
        "manifest": manifest,
        "total": offset,
        "expected_train": expected_train,
        "expected_ctx": expected_ctx,
        "expected_pairs": expected_pairs,
        "train_state": train_state,
        "train_action": train_action,
    }


def test_train_indices_are_exactly_the_train_frames(built):
    pytest.importorskip("lerobot")
    convert = built["convert"]
    got = convert.train_indices(built["ds"])
    assert got.dtype == np.int64, "train_indices must return int64 indices"
    assert np.all(np.diff(got) > 0), "train_indices must be sorted and unique"
    assert np.array_equal(got, built["expected_train"]), (
        "train_indices must return exactly the global indices whose source frame had train True"
    )
    assert not set(got.tolist()) & set(built["expected_ctx"]), (
        "context frames (train False) must be excluded from train_indices"
    )


def test_full_loader_pass_returns_each_train_index_once_and_no_context(built):
    pytest.importorskip("lerobot")
    pytest.importorskip("torch")
    loader = built["convert"].train_loader(built["ds"], batch_size=8, seed=0)
    seen, pairs = [], []
    for batch in loader:
        assert bool(batch["train"].bool().all()), (
            "train_loader must only yield frames whose train flag is True (context frame seen)"
        )
        assert all(v < 1000 for v in batch["observation.state"][:, 0].tolist()), (
            "context frames (state 1e3) must never be sampled by train_loader"
        )
        seen.extend(batch["index"].tolist())
        pairs.extend(zip(batch["episode_index"].tolist(), batch["frame_index"].tolist()))
        assert batch["train"].shape[0] <= 8, "batch larger than batch_size=8"
    assert len(seen) == len(set(seen)), (
        "one full pass must return each train index exactly once (duplicate seen)"
    )
    assert sorted(seen) == built["expected_train"].tolist(), (
        "one full pass must return every train index and no context frame"
    )
    assert sorted(pairs) == sorted(built["expected_pairs"]), (
        "(episode_index, frame_index) of returned frames must match the train frames"
    )
    assert seen != sorted(seen), "train_loader must shuffle when shuffle is on (order was sorted)"


def test_train_stats_use_train_frames_only_and_are_stored(built):
    pytest.importorskip("lerobot")
    convert = built["convert"]
    ds = built["ds"]
    stats = convert.train_stats(ds)
    expected_src = {"observation.state": built["train_state"], "action": built["train_action"]}

    for key, arr in expected_src.items():
        arr64 = arr.astype(np.float64)
        wants = {"mean": arr64.mean(0), "min": arr64.min(0), "max": arr64.max(0)}
        for stat, want in wants.items():
            assert key in stats and stat in stats[key], f"train_stats must provide {key}.{stat}"
            got = np.asarray(stats[key][stat], dtype=np.float64).reshape(-1)
            assert got.size == want.size, f"train_stats {key}.{stat} has wrong size"
            assert np.allclose(got, want.reshape(-1), rtol=1e-4, atol=1e-3), (
                f"train_stats {key}.{stat} must equal numpy over train frames only "
                "(context frames at 1e3 must be excluded)"
            )

    stored = ds.meta.stats
    for key in expected_src:
        for stat in ("mean", "min", "max"):
            s_stored = np.asarray(stored[key][stat], dtype=np.float64).reshape(-1)
            s_train = np.asarray(stats[key][stat], dtype=np.float64).reshape(-1)
            assert np.allclose(s_stored, s_train, rtol=1e-5, atol=1e-6), (
                f"stored dataset stats {key}.{stat} (as LeRobot loads them) must equal train_stats"
            )

    manifest = json.loads(built["manifest"].read_text())
    assert manifest["stats"] == "train_frames_only", "manifest must record stats: train_frames_only"


def test_block_pos_touch_and_shift_are_not_features_but_are_in_manifest(built):
    pytest.importorskip("lerobot")
    ds = built["ds"]
    for k in NON_FEATURES:
        assert k not in ds.features, (
            f"{k} must not be a dataset feature; it belongs only in the manifest"
        )
    item = ds[0]
    for k in NON_FEATURES:
        assert k not in item, f"{k} must not appear in a loaded dataset item"

    manifest = json.loads(built["manifest"].read_text())
    eps = manifest["episodes"]
    assert [e["episode_index"] for e in eps] == list(range(N_BASE + len(EXTRA_SPECS))), (
        "manifest must list every dataset episode in order"
    )
    plan_eps = built["plan"]["base"] + built["plan"][NAME]
    for e, p in zip(eps, plan_eps):
        for k in ("shift_type", "shift_frame", "block_before", "block_after", "trigger_z"):
            assert k in e, (
                f"manifest episode {e['episode_index']} must carry {k} "
                "(shift metadata goes in the manifest)"
            )
        assert e["shift_type"] == p["shift_type"], (
            f"manifest shift_type for episode {e['episode_index']} must match the source"
        )


def test_dataloader_batch_of_8_has_expected_keys_and_shapes(built):
    pytest.importorskip("lerobot")
    pytest.importorskip("torch")
    loader = built["convert"].train_loader(built["ds"], batch_size=8, seed=0)
    batch = next(iter(loader))
    for k in ("observation.images.top", "observation.images.wrist", "observation.state", "action", "train"):
        assert k in batch, f"batch must contain key {k}"
    assert tuple(batch["observation.state"].shape) == (8, 5), "observation.state batch must be (8, 5)"
    assert tuple(batch["action"].shape) == (8, 4), "action batch must be (8, 4)"
    assert tuple(batch["train"].shape) == (8, 1), "train batch must be (8, 1)"
    for cam in ("observation.images.top", "observation.images.wrist"):
        shape = tuple(batch[cam].shape)
        assert shape in {(8, 240, 320, 3), (8, 3, 240, 320)}, (
            f"{cam} batch must be 8 frames of 240x320x3 (HWC or LeRobot CHW layout), got {shape}"
        )

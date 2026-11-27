"""S3 fidelity tests: the LeRobot conversion must copy source episodes faithfully.

Tests the rules in .orchestration/contract.md (Conversion section):
1. observation.state and action are bit-equal to the source npz, frame by frame,
   for every episode, including the trimmed one (only its kept frames).
2. Images: shape and channel order match the source; PSNR is finite and above
   25 dB; cameras are not swapped; frame k decodes closest to source frame k.
3. No hub access: build and load work offline (HF_HUB_OFFLINE=1, no non-loopback
   socket connects).

Synthetic episodes are written in the "Source episodes" format. Nothing here
needs mujoco. The LeRobot tests skip when lerobot is not installed.
"""
import os
import socket
import sys
from collections import Counter
from pathlib import Path

import numpy as np
import pytest

os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["HF_DATASETS_OFFLINE"] = "1"

RECOVERY_SIM = Path(__file__).resolve().parents[1]
if str(RECOVERY_SIM) not in sys.path:
    sys.path.insert(0, str(RECOVERY_SIM))

H, W = 240, 320
CAMS = ("top", "wrist")
PSNR_FLOOR_DB = 25.0
LOOPBACK = ("127.0.0.1", "::1", "localhost")
SET_NAME = "separate"
N_TRAIN_EXTRA = 60  # extras' train frames, so the second episode is trimmed


# ---------------------------------------------------------------- synthetic data

def _frames(T, cam, seed):
    """Smooth gradient background plus a square moving 4 px per frame."""
    rng = np.random.default_rng(seed)
    yy, xx = np.mgrid[0:H, 0:W]
    base = np.zeros((H, W, 3), np.float32)
    if cam == "top":
        base[..., 0] = xx * 255.0 / (W - 1)
        base[..., 1] = yy * 255.0 / (H - 1)
        base[..., 2] = 90.0
        square = (255, 255, 0)
    else:
        base[..., 0] = 60.0
        base[..., 1] = yy * 255.0 / (H - 1)
        base[..., 2] = xx * 255.0 / (W - 1)
        square = (0, 255, 255)
    x_start = int(rng.integers(0, 40))
    out = np.empty((T, H, W, 3), np.uint8)
    for t in range(T):
        img = base.copy()
        x0 = 10 + (x_start + 4 * t) % 200
        img[60:108, x0:x0 + 48] = square
        out[t] = np.clip(np.round(img), 0, 255).astype(np.uint8)
    return out


def _write_episode(path, T, n_context, seed, shift_type, rng):
    train = np.ones(T, dtype=bool)
    train[:n_context] = False
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez(
        path,
        state=rng.standard_normal((T, 5)).astype(np.float32),
        action=rng.standard_normal((T, 4)).astype(np.float32),
        block_pos=rng.standard_normal((T, 3)).astype(np.float32),
        touch=rng.integers(0, 2, T).astype(bool),
        train=train,
        top=_frames(T, "top", seed),
        wrist=_frames(T, "wrist", seed + 1),
        shift_type=np.str_(shift_type),
        shift_frame=np.int64(-1),
        shift_frame_full=np.int64(-1),
        train_start=np.int64(n_context),
        train_end=np.int64(T),
        seed=np.int64(seed),
        attempt=np.int64(0),
        trigger_z=np.float64(np.nan),
        block_before=np.full(3, np.nan),
        block_after=np.full(3, np.nan),
    )


def _sha256(path):
    import hashlib

    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _base_entries(raw, rels):
    """Plan entries for episodes kept whole (the contract's plan_base shape)."""
    entries = []
    for rel in rels:
        with np.load(raw / rel) as z:
            T = len(z["train"])
            n_train = int(z["train"].sum())
            shift = str(z["shift_type"])
        entries.append({
            "file": rel, "sha256": _sha256(raw / rel), "n_frames": T, "n_train": n_train,
            "trimmed": False, "frames_removed": 0, "shift_type": shift,
        })
    return entries


def _extra_entries(raw, rels, n_train_target):
    """Exact trimming as the contract states it: walk episodes in order, keep whole
    episodes until the running train total would pass n_train_target, then keep
    frames 0..k-1 where k is one past the train frame that makes the total exact."""
    entries = []
    running = 0
    for rel in rels:
        if running == n_train_target:
            break
        with np.load(raw / rel) as z:
            train = z["train"]
            T = len(train)
            shift = str(z["shift_type"])
        n_tr = int(train.sum())
        if running + n_tr <= n_train_target:
            keep, kept_train, trimmed = T, n_tr, False
        else:
            need = n_train_target - running
            keep = int(np.flatnonzero(train)[need - 1]) + 1
            kept_train, trimmed = need, True
        running += kept_train
        entries.append({
            "file": rel, "sha256": _sha256(raw / rel), "n_frames": keep, "n_train": kept_train,
            "trimmed": trimmed, "frames_removed": T - keep, "shift_type": shift,
        })
    assert running == n_train_target, (
        f"Rule: extras must add up to exactly n_train={n_train_target} train frames; "
        f"the folder ran out at {running}"
    )
    return entries


def _load_source(path):
    with np.load(path) as z:
        return {k: z[k] for k in ("state", "action", "train", "top", "wrist")}


# ---------------------------------------------------------------- helpers

def _import_convert():
    pytest.importorskip("lerobot")
    import convert  # recovery_sim/convert.py

    return convert


def _np(x):
    if hasattr(x, "detach"):
        x = x.detach().cpu().numpy()
    return np.asarray(x)


def _scalar(x):
    return int(_np(x).reshape(-1)[0])


def _to_hwc_u8(t, cam):
    """LeRobot tensor (CHW float in [0,1], or HWC) back to HWC uint8."""
    a = _np(t)
    if a.shape == (3, H, W):
        a = np.transpose(a, (1, 2, 0))
    assert a.shape == (H, W, 3), (
        f"Rule: {cam} image must decode to shape {(H, W, 3)} (HWC) after layout conversion; "
        f"got {a.shape}"
    )
    if np.issubdtype(a.dtype, np.floating):
        lo, hi = float(a.min()), float(a.max())
        assert lo >= -1e-3 and hi <= 1.0 + 1e-3, (
            f"Rule: {cam} float image must be in [0,1]; got range [{lo}, {hi}]"
        )
        a = np.clip(np.round(a * 255.0), 0, 255).astype(np.uint8)
    assert a.dtype == np.uint8, f"Rule: {cam} image must be uint8 after conversion; got {a.dtype}"
    return a


def _mse(a, b):
    return float(np.mean((a.astype(np.float64) - b.astype(np.float64)) ** 2))


# ---------------------------------------------------------------- fixture

@pytest.fixture(scope="module")
def built(tmp_path_factory):
    """Write synthetic raw episodes, build the dataset offline, load it, and decode
    every kept frame once. Shared by all tests in this module."""
    convert = _import_convert()
    root = tmp_path_factory.mktemp("s3_fidelity")
    raw = root / "raw"
    out = root / "datasets"

    rng = np.random.default_rng(20260401)
    base_rels = []
    for i in range(3):
        rel = f"base/clean_seed1000/episode_{i:04d}.npz"
        _write_episode(raw / rel, T=30, n_context=0, seed=100 + i, shift_type="none", rng=rng)
        base_rels.append(rel)
    sep_specs = [
        ("separate/separate_seed1002/episode_0000.npz", 40, 5, 200, "early"),
        ("separate/separate_seed1002/episode_0001.npz", 40, 5, 300, "late"),
    ]
    sep_rels = []
    for rel, T, n_ctx, seed, shift in sep_specs:
        _write_episode(raw / rel, T=T, n_context=n_ctx, seed=seed, shift_type=shift, rng=rng)
        sep_rels.append(rel)

    plan = {
        "base": _base_entries(raw, base_rels),
        SET_NAME: _extra_entries(raw, sep_rels, N_TRAIN_EXTRA),
    }

    # Block every non-loopback socket connect. Attempts are recorded for the no-hub test.
    attempts = []
    real_connect = socket.socket.connect

    def guarded_connect(self, address):
        host = address[0] if isinstance(address, tuple) else str(address)
        if host not in LOOPBACK:
            attempts.append(host)
            raise OSError(f"blocked network connect to {host!r} (test is offline)")
        return real_connect(self, address)

    mp = pytest.MonkeyPatch()
    mp.setattr(socket.socket, "connect", guarded_connect)
    try:
        convert.build(SET_NAME, plan, raw, out)
        ds = convert.load(SET_NAME, out)
    finally:
        mp.undo()

    # Expected kept frames in dataset order: base episodes, then extras, each trimmed.
    episodes = []
    expected = []  # (episode_index, frame_index, source_dict, n_frames)
    for e, entry in enumerate(plan["base"] + plan[SET_NAME]):
        src = _load_source(raw / entry["file"])
        n = entry["n_frames"]
        episodes.append({**entry, "episode_index": e, "src": src})
        for j in range(n):
            expected.append((e, j, src, n))

    total = len(expected)
    assert len(ds) == total, (
        f"Rule: dataset must hold exactly the kept frames ({total}); got {len(ds)}"
    )

    rows = []
    for g, (e, j, src, n) in enumerate(expected):
        item = ds[g]
        rows.append({
            "ep": _scalar(item["episode_index"]),
            "frame": _scalar(item["frame_index"]),
            "exp_ep": e,
            "exp_frame": j,
            "state": _np(item["observation.state"]).astype(np.float32).reshape(-1),
            "action": _np(item["action"]).astype(np.float32).reshape(-1),
            "decoded": {cam: _to_hwc_u8(item[f"observation.images.{cam}"], cam) for cam in CAMS},
            "src": src,
            "n_frames": n,
            "j": j,
        })

    return {
        "convert": convert,
        "ds": ds,
        "plan": plan,
        "episodes": episodes,
        "rows": rows,
        "total": total,
        "raw": raw,
        "out": out,
        "attempts": attempts,
    }


# ---------------------------------------------------------------- tests

def test_state_and_action_bit_equal_to_source(built):
    rows = built["rows"]
    counts = Counter(r["ep"] for r in rows)
    for ep in built["episodes"]:
        e = ep["episode_index"]
        assert counts[e] == ep["n_frames"], (
            f"Rule: a trimmed or whole episode must contain only its kept frames: episode {e} "
            f"({ep['file']}) expected {ep['n_frames']} frames, got {counts[e]}"
        )

    for g, r in enumerate(rows):
        assert r["ep"] == r["exp_ep"] and r["frame"] == r["exp_frame"], (
            f"Rule: dataset rows must follow plan order (base, then extras, frames in order); "
            f"row {g} is episode {r['ep']} frame {r['frame']}, expected "
            f"episode {r['exp_ep']} frame {r['exp_frame']}"
        )
        src, j = r["src"], r["j"]
        for key, src_key in (("observation.state", "state"), ("action", "action")):
            got = r["state"] if src_key == "state" else r["action"]
            exp = src[src_key][j].astype(np.float32).reshape(-1)
            assert got.shape == exp.shape, (
                f"Rule: {key} shape must match source; episode {r['ep']} frame {j}: "
                f"got {got.shape}, expected {exp.shape}"
            )
            assert np.array_equal(got.view(np.uint32), exp.view(np.uint32)), (
                f"Rule: {key} must equal the source npz exactly (float32 bit-equal); "
                f"episode {r['ep']} frame {j}: got {got.tolist()}, expected {exp.tolist()}"
            )


def test_images_shape_order_and_psnr(built):
    rows = built["rows"]
    metrics = {}
    for cam in CAMS:
        abs_sum = 0.0
        se_sum = 0.0
        n_vals = 0
        max_abs = 0.0
        for r in rows:
            dec = r["decoded"][cam].astype(np.float64)
            src = r["src"][cam][r["j"]].astype(np.float64)
            d = np.abs(dec - src)
            abs_sum += float(d.sum())
            se_sum += float((d ** 2).sum())
            n_vals += d.size
            max_abs = max(max_abs, float(d.max()))
        mse = se_sum / n_vals
        psnr = float("inf") if mse == 0 else 10.0 * np.log10(255.0 ** 2 / mse)
        metrics[cam] = {"mean_abs": abs_sum / n_vals, "max_abs": max_abs, "psnr": psnr}

    built["metrics"] = metrics
    for cam in CAMS:
        psnr = metrics[cam]["psnr"]
        assert np.isfinite(psnr), (
            f"Rule: {cam} PSNR must be finite; got {psnr} (metrics {metrics[cam]})"
        )
        assert psnr > PSNR_FLOOR_DB, (
            f"Rule: {cam} PSNR must be above the {PSNR_FLOOR_DB} dB sanity floor on synthetic "
            f"smooth images; got {psnr:.2f} dB (metrics {metrics[cam]})"
        )


def test_frame_k_is_closest_to_source_frame_k_and_cameras_not_swapped(built):
    rows = built["rows"]
    for g, r in enumerate(rows):
        j, n, src = r["j"], r["n_frames"], r["src"]
        for cam in CAMS:
            dec = r["decoded"][cam]
            cands = [k for k in (j - 1, j, j + 1) if 0 <= k < n]
            dists = {k: _mse(dec, src[cam][k]) for k in cands}
            best = min(dists, key=dists.get)
            assert best == j, (
                f"Rule: frame-k decode must be closest to source frame k among k-1, k, k+1; "
                f"row {g} (episode {r['ep']}, frame {j}) {cam}: closest is source frame {best}; "
                f"mse by frame {dists}"
            )
        for cam, other in (("top", "wrist"), ("wrist", "top")):
            own = _mse(r["decoded"][cam], src[cam][j])
            wrong = _mse(r["decoded"][cam], src[other][j])
            assert own < wrong, (
                f"Rule: images must not be swapped between cameras; row {g} (episode {r['ep']}, "
                f"frame {j}) {cam} decode is closer to source {other} (mse {wrong:.1f}) than to "
                f"source {cam} (mse {own:.1f})"
            )


def test_build_and_load_need_no_hub_access(built):
    assert os.environ.get("HF_HUB_OFFLINE") == "1", (
        "Rule: tests must run with HF_HUB_OFFLINE=1 (network-free settings)"
    )
    assert built["attempts"] == [], (
        f"Rule: no hub access; build/load tried to connect to non-loopback hosts: "
        f"{built['attempts']}"
    )

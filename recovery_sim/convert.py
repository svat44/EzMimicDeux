"""Convert recovery_sim source episodes into local LeRobot 0.7.0 datasets.

Runs under recovery_sim/.venv-lerobot. Does not import collect or make_sets.
The plan is a plain dict (see contract "Sets and seeds"). Nothing is uploaded:
HF_HUB_OFFLINE is forced on before lerobot is imported and push_to_hub is never called.
"""

import os

os.environ["HF_HUB_OFFLINE"] = "1"

import argparse  # noqa: E402
import copy  # noqa: E402
import hashlib  # noqa: E402
import importlib.metadata  # noqa: E402
import json  # noqa: E402
import math  # noqa: E402
from pathlib import Path  # noqa: E402

import numpy as np  # noqa: E402
import torch  # noqa: E402
from torch.utils.data import DataLoader, Subset  # noqa: E402
from torch.utils.data._utils.collate import default_collate  # noqa: E402

from lerobot.configs.video import RGBEncoderConfig  # noqa: E402
from lerobot.datasets.compute_stats import get_feature_stats, sample_indices  # noqa: E402
from lerobot.datasets.io_utils import load_stats, write_stats  # noqa: E402
from lerobot.datasets.lerobot_dataset import LeRobotDataset  # noqa: E402

FPS = 20
TASK = "Pick up the red block and put it in the blue bowl."
FEATURES = {
    "observation.images.top": {"dtype": "video", "shape": (240, 320, 3), "names": ["height", "width", "channels"]},
    "observation.images.wrist": {"dtype": "video", "shape": (240, 320, 3), "names": ["height", "width", "channels"]},
    "observation.state": {"dtype": "float32", "shape": (5,), "names": ["x", "y", "z", "left_finger", "right_finger"]},
    "action": {"dtype": "float32", "shape": (4,), "names": ["x", "y", "z", "grip"]},
    "train": {"dtype": "bool", "shape": (1,), "names": None},
}
ACTION_CHUNK = 40
HISTORY_OFFSETS = (-20, -10, 0)
CAMERAS = ("top", "wrist")
# Near-lossless h264 (API report Q3). Not bit-exact; summary measures the difference.
RGB_ENCODER = RGBEncoderConfig(vcodec="h264", pix_fmt="yuvj444p", crf=0)


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _opt_vec(a):
    a = np.asarray(a, dtype=np.float64)
    return None if np.isnan(a).any() else a.tolist()


def _opt_float(a):
    a = float(np.asarray(a))
    return None if math.isnan(a) else a


def load(name: str, out_root, delta_timestamps=None) -> LeRobotDataset:
    """Open a dataset from local disk only."""
    return LeRobotDataset(
        f"local/{name}",
        root=Path(out_root) / name,
        delta_timestamps=delta_timestamps,
    )


def chunk_delta_timestamps() -> dict:
    return {"action": [i / FPS for i in range(ACTION_CHUNK)]}


def history_delta_timestamps() -> dict:
    return {
        "observation.state": [o / FPS for o in HISTORY_OFFSETS],
        "observation.images.top": [o / FPS for o in HISTORY_OFFSETS],
        "observation.images.wrist": [o / FPS for o in HISTORY_OFFSETS],
    }


def train_indices(ds) -> np.ndarray:
    """Global frame indices whose stored train flag is True, sorted, int64."""
    flags = np.asarray(ds.hf_dataset.with_format("numpy")["train"]).reshape(-1).astype(bool)
    return np.flatnonzero(flags).astype(np.int64)


def _collate(items: list) -> dict:
    """Default collate, but keep the per-frame train flag as shape (B, 1) like the schema."""
    batch = default_collate(items)
    batch["train"] = batch["train"].reshape(len(items), 1)
    return batch


def train_loader(ds, batch_size: int = 8, seed: int = 0) -> DataLoader:
    """Shuffled loader that can only sample train frames (Subset over train_indices)."""
    gen = torch.Generator().manual_seed(seed)
    return DataLoader(
        Subset(ds, train_indices(ds).tolist()),
        batch_size=batch_size,
        shuffle=True,
        generator=gen,
        collate_fn=_collate,
    )


def train_stats(ds) -> dict:
    """Normalisation stats over train frames only, in LeRobot's stats layout.

    Vector and scalar features are computed exactly over every train frame. Image
    features follow LeRobot's own default of sampling frames (sample_indices), but the
    sample is drawn from train frames only. Frames are decoded from the stored video,
    so values are already RGB/255 in [0, 1], as LeRobot's image stats are.
    """
    idx = train_indices(ds)
    if idx.size == 0:
        raise ValueError("no train frames in dataset")
    hf = ds.hf_dataset.with_format("numpy")
    stats = {}
    for key, ft in ds.meta.features.items():
        if ft["dtype"] in ("string", "language"):
            continue
        if ft["dtype"] in ("image", "video"):
            sel = idx[np.asarray(sample_indices(len(idx)), dtype=np.int64)]
            frames = np.stack([ds[int(i)][key].numpy() for i in sel]).astype(np.float32)
            s = get_feature_stats(frames, axis=(0, 2, 3), keepdims=True)
            s = {k: v if k == "count" else np.squeeze(v, axis=0) for k, v in s.items()}
            s["count"] = np.array([idx.size])
            stats[key] = s
        else:
            col = np.asarray(hf[key])[idx]
            stats[key] = get_feature_stats(col, axis=0, keepdims=col.ndim == 1)
    return stats


def _assert_same_stats(a: dict, b: dict) -> None:
    if set(a) != set(b):
        raise AssertionError(f"stats keys differ: {set(a) ^ set(b)}")
    for k in a:
        if set(a[k]) != set(b[k]):
            raise AssertionError(f"stats keys differ for {k}")
        for s in a[k]:
            x, y = np.asarray(a[k][s], dtype=np.float64), np.asarray(b[k][s], dtype=np.float64)
            if x.shape != y.shape or not np.allclose(x, y, rtol=1e-6, atol=1e-8):
                raise AssertionError(f"stats mismatch {k}.{s}: {x.shape} vs {y.shape}")


def build(name: str, plan: dict, raw_root, out_root) -> Path:
    raw_root, out_root = Path(raw_root), Path(out_root)
    if name not in plan:
        raise KeyError(f"plan has no set {name!r}")
    root = out_root / name
    manifest_path = out_root / "manifests" / f"{name}.json"
    if root.exists() or manifest_path.exists():
        raise FileExistsError(f"{root} or {manifest_path} already exists")

    entries = [(e, "base") for e in plan["base"]] + [(e, "extra") for e in plan[name]]
    ds = LeRobotDataset.create(
        repo_id=f"local/{name}",
        fps=FPS,
        features=copy.deepcopy(FEATURES),
        root=root,
        robot_type="recovery_sim",
        use_videos=True,
        rgb_encoder=RGB_ENCODER,
    )

    manifest_eps = []
    for ep_index, (entry, role) in enumerate(entries):
        path = raw_root / entry["file"]
        if _sha256(path) != entry["sha256"]:
            raise ValueError(f"sha256 mismatch for {entry['file']}")
        z = np.load(path)
        n = int(entry["n_frames"])
        n_train = int(entry["n_train"])
        shift_type = str(z["shift_type"])
        if shift_type != entry["shift_type"]:
            raise ValueError(f"shift_type mismatch for {entry['file']}")
        state = z["state"][:n].astype(np.float32)
        action = z["action"][:n].astype(np.float32)
        train = z["train"][:n].astype(bool)
        top = z["top"][:n]
        wrist = z["wrist"][:n]
        if int(train.sum()) != n_train:
            raise ValueError(f"{entry['file']}: train count {int(train.sum())} != plan {n_train}")

        for t in range(n):
            ds.add_frame(
                {
                    "observation.images.top": top[t],
                    "observation.images.wrist": wrist[t],
                    "observation.state": state[t],
                    "action": action[t],
                    "train": np.array([train[t]], dtype=bool),
                    "task": TASK,
                }
            )
        ds.save_episode()

        mode = Path(entry["file"]).parent.name.split("_seed")[0]
        manifest_eps.append(
            {
                "episode_index": ep_index,
                "role": role,
                "file": entry["file"],
                "sha256": entry["sha256"],
                "mode": mode,
                "seed": int(z["seed"]),
                "attempt": int(z["attempt"]),
                "shift_type": shift_type,
                "shift_frame": int(z["shift_frame"]),
                "trigger_z": _opt_float(z["trigger_z"]),
                "block_before": _opt_vec(z["block_before"]),
                "block_after": _opt_vec(z["block_after"]),
                "n_frames": n,
                "n_train": n_train,
                "trimmed": bool(entry["trimmed"]),
                "frames_removed": int(entry["frames_removed"]),
            }
        )
        del top, wrist, z

    ds.finalize()
    del ds

    ds = load(name, out_root)
    stats = train_stats(ds)
    write_stats(stats, ds.root)
    check = load(name, out_root)
    _assert_same_stats(stats, load_stats(ds.root))
    _assert_same_stats(stats, check.meta.stats)

    manifest = {
        "name": name,
        "lerobot_version": importlib.metadata.version("lerobot"),
        "fps": FPS,
        "task": TASK,
        "stats": "train_frames_only",
        "episodes": manifest_eps,
    }
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, indent=2))
    return root


def _read_manifest(name: str, out_root) -> dict:
    return json.loads((Path(out_root) / "manifests" / f"{name}.json").read_text())


def summarize(name: str, out_root, raw_root) -> dict:
    out_root, raw_root = Path(out_root), Path(raw_root)
    manifest = _read_manifest(name, out_root)
    eps = manifest["episodes"]
    ds = load(name, out_root)
    if ds.num_episodes != len(eps):
        raise ValueError(f"dataset has {ds.num_episodes} episodes, manifest {len(eps)}")

    is_train = np.zeros(ds.num_frames, dtype=bool)
    is_train[train_indices(ds)] = True
    starts = np.asarray(ds.meta.episodes["dataset_from_index"], dtype=np.int64)
    ends = np.asarray(ds.meta.episodes["dataset_to_index"], dtype=np.int64)
    ep_train = [int(is_train[starts[i]:ends[i]].sum()) for i in range(len(eps))]
    early = sum(1 for e in eps if e["shift_type"] == "early")
    late = sum(1 for e in eps if e["shift_type"] == "late")
    extra_train = sum(ep_train[e["episode_index"]] for e in eps if e["role"] != "base")
    base_eps = [e for e in eps if e["role"] == "base"]
    trimmed = [e for e in eps if e["trimmed"]]
    trimmed_info = None
    if trimmed:
        t = trimmed[0]
        trimmed_info = {"episode_index": t["episode_index"], "file": t["file"], "frames_removed": t["frames_removed"]}

    # Frame-by-frame comparison against the source npz files.
    diff = {c: {"sum": 0.0, "sq": 0.0, "max": 0, "n": 0} for c in CAMERAS}
    state_action_exact = True
    base_state = {}
    base_action = {}
    cur_ep, src = None, None
    loader = DataLoader(ds, batch_size=64, shuffle=False, num_workers=0)
    for batch in loader:
        for j in range(len(batch["index"])):
            e = int(batch["episode_index"][j])
            f = int(batch["frame_index"][j])
            if e != cur_ep:
                ep = eps[e]
                src = np.load(raw_root / ep["file"])
                cur_ep = e
            d_state = batch["observation.state"][j].numpy().astype(np.float32)
            d_action = batch["action"][j].numpy().astype(np.float32)
            s_state = src["state"][f].astype(np.float32)
            s_action = src["action"][f].astype(np.float32)
            if d_state.tobytes() != s_state.tobytes() or d_action.tobytes() != s_action.tobytes():
                state_action_exact = False
            if eps[e]["role"] == "base":
                base_state.setdefault(e, []).append(d_state)
                base_action.setdefault(e, []).append(d_action)
            for c in CAMERAS:
                img = np.rint(batch[f"observation.images.{c}"][j].numpy().transpose(1, 2, 0) * 255)
                img = np.clip(img, 0, 255).astype(np.int16)
                ref = src[c][f].astype(np.int16)
                d = np.abs(img - ref)
                diff[c]["sum"] += float(d.sum(dtype=np.float64))
                diff[c]["sq"] += float((d.astype(np.float64) ** 2).sum())
                diff[c]["max"] = max(diff[c]["max"], int(d.max()))
                diff[c]["n"] += d.size
    if sum(len(v) for v in base_state.values()) != sum(e["n_frames"] for e in base_eps):
        state_action_exact = False

    image_diff = {}
    for c in CAMERAS:
        n = diff[c]["n"]
        mse = diff[c]["sq"] / n
        image_diff[c] = {
            "mean_abs": diff[c]["sum"] / n,
            "max_abs": diff[c]["max"],
            "psnr": None if mse == 0 else 10 * math.log10(255.0 ** 2 / mse),
        }

    base_sha = []
    for e in base_eps:
        i = e["episode_index"]
        h = hashlib.sha256()
        h.update(np.stack(base_state[i]).astype(np.float32).tobytes())
        h.update(np.stack(base_action[i]).astype(np.float32).tobytes())
        base_sha.append(h.hexdigest())

    shapes = {
        "observation.images.top": (8, 3, 240, 320),
        "observation.images.wrist": (8, 3, 240, 320),
        "observation.state": (8, 5),
        "action": (8, 4),
        "train": (8, 1),
    }
    batch = next(iter(train_loader(ds, batch_size=8, seed=0)))
    batch_ok = all(tuple(batch[k].shape) == s for k, s in shapes.items()) and bool(batch["train"].all())

    return {
        "name": name,
        "episodes": ds.num_episodes,
        "frames": ds.num_frames,
        "base_episodes": len(base_eps),
        "base_sha256": base_sha,
        "extra_train_frames": extra_train,
        "context_frames": int(ds.num_frames - is_train.sum()),
        "early": early,
        "late": late,
        "trimmed": trimmed_info,
        "state_action_exact": state_action_exact,
        "image_diff": image_diff,
        "batch_ok": batch_ok,
    }


def main(argv=None) -> None:
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build")
    b.add_argument("--name", required=True)
    b.add_argument("--plan", required=True)
    b.add_argument("--raw", required=True)
    b.add_argument("--out", required=True)
    s = sub.add_parser("summary")
    s.add_argument("--name", required=True)
    s.add_argument("--raw", required=True)
    s.add_argument("--out", required=True)
    a = p.parse_args(argv)
    if a.cmd == "build":
        plan = json.loads(Path(a.plan).read_text())
        print(build(a.name, plan, a.raw, a.out))
    else:
        print(json.dumps(summarize(a.name, a.out, a.raw), indent=2))


if __name__ == "__main__":
    main()

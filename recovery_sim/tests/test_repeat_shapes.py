"""Contract tests for recovery_sim/collect.py: determinism, image shapes, preview GIFs.

Tested against .orchestration/contract.md only.
"""
import json
import sys
from pathlib import Path

import numpy as np
import pytest
from PIL import Image, ImageSequence

RECOVERY_SIM = Path(__file__).resolve().parents[1]
if str(RECOVERY_SIM) not in sys.path:
    sys.path.insert(0, str(RECOVERY_SIM))

import collect  # noqa: E402

MODES = collect.MODES

SEED = 0
OTHER_SEED = 1
NO_IMAGE_FRAMES = 60   # small budget, images=False
DET_IMAGE_FRAMES = 60  # small budget, images=True determinism pair
PREVIEW_FRAMES = 120   # small budget, images=True with preview (clean)
PREVIEW_FRAMES_BIG = 300  # embedded/separate: one episode is ~120 train frames, so early and late both need this


def _preview_budget(mode):
    return PREVIEW_FRAMES if mode == "clean" else PREVIEW_FRAMES_BIG

GIF_FILES = {
    "clean": ["preview.gif"],
    "embedded": ["preview_early.gif", "preview_late.gif"],
    "separate": ["preview_early.gif", "preview_late.gif"],
}
GIF_TYPE = {"preview.gif": "none", "preview_early.gif": "early", "preview_late.gif": "late"}

# Run cache: each collect() call is made once per key and shared between tests.
_CACHE = {}


def _run(factory, mode, frames, seed, images, preview=False, rep="a"):
    key = (mode, frames, seed, images, preview, rep)
    if key not in _CACHE:
        base = factory.mktemp(f"{mode}_f{frames}_s{seed}_i{int(images)}_p{int(preview)}_{rep}")
        out = base / "out"
        summary = collect.collect(mode, frames, seed=seed, out=str(out), images=images, preview=preview)
        _CACHE[key] = (out, summary)
    return _CACHE[key]


@pytest.fixture(scope="session")
def factory(tmp_path_factory):
    return tmp_path_factory


def _find_one(out, name):
    matches = list(out.rglob(name))
    assert len(matches) == 1, f"expected exactly one {name} under {out}, found {len(matches)}"
    return matches[0]


def _episode_paths(out):
    return sorted(p for p in out.rglob("*.npz") if p.name.startswith("episode_"))


def _tree(out):
    return {p.relative_to(out).as_posix(): p for p in _episode_paths(out)}


def _load(path):
    with np.load(path, allow_pickle=False) as z:
        return {k: z[k] for k in z.files}


def _strip_paths(obj):
    if isinstance(obj, dict):
        return {
            k: _strip_paths(v)
            for k, v in obj.items()
            if not (k == "file" or k.endswith("path") or k.endswith("_path"))
        }
    if isinstance(obj, list):
        return [_strip_paths(v) for v in obj]
    return obj


def _first_episode(out, shift_type):
    """First saved episode (in episodes.json order) whose shift_type matches."""
    episodes = json.loads(_find_one(out, "episodes.json").read_text())
    assert episodes, f"episodes.json lists no episodes under {out}"
    for entry in episodes:
        path = _find_one(out, Path(entry["file"]).name)
        z = _load(path)
        if str(z["shift_type"]) == shift_type:
            return path, z
    raise AssertionError(f"no saved episode with shift_type={shift_type!r} under {out}")


def _assert_same_run(out_a, out_b, label):
    a, b = _tree(out_a), _tree(out_b)
    assert a, f"{label}: no episode npz written"
    assert sorted(a) == sorted(b), (
        f"{label}: equal args wrote different episode files: {sorted(a)} vs {sorted(b)}"
    )
    for rel in sorted(a):
        za, zb = _load(a[rel]), _load(b[rel])
        assert sorted(za) == sorted(zb), f"{label}: {rel} array keys differ between runs"
        for k in za:
            x, y = za[k], zb[k]
            assert x.dtype == y.dtype and x.shape == y.shape and x.tobytes() == y.tobytes(), (
                f"{label}: {rel}[{k}] differs between two runs with the same seed and args "
                "(rule: same args give byte-identical arrays)"
            )
    ja = _strip_paths(json.loads(_find_one(out_a, "episodes.json").read_text()))
    jb = _strip_paths(json.loads(_find_one(out_b, "episodes.json").read_text()))
    assert ja == jb, (
        f"{label}: episodes.json differs between runs with equal args, ignoring path fields "
        "(rule: same args give equal episodes)"
    )


# ---------------------------------------------------------------- determinism

@pytest.mark.parametrize("mode", MODES)
def test_same_seed_same_arrays_no_images(factory, mode):
    out_a, _ = _run(factory, mode, NO_IMAGE_FRAMES, SEED, images=False, rep="a")
    out_b, _ = _run(factory, mode, NO_IMAGE_FRAMES, SEED, images=False, rep="b")
    _assert_same_run(out_a, out_b, f"mode={mode} images=False")


def test_same_seed_same_arrays_with_images(factory):
    out_a, _ = _run(factory, "clean", DET_IMAGE_FRAMES, SEED, images=True, rep="a")
    out_b, _ = _run(factory, "clean", DET_IMAGE_FRAMES, SEED, images=True, rep="b")
    _assert_same_run(out_a, out_b, "mode=clean images=True")


@pytest.mark.parametrize("mode", MODES)
def test_different_seed_gives_different_data(factory, mode):
    out0, _ = _run(factory, mode, NO_IMAGE_FRAMES, SEED, images=False, rep="a")
    out1, _ = _run(factory, mode, NO_IMAGE_FRAMES, OTHER_SEED, images=False)
    p0 = _tree(out0)
    p1 = _tree(out1)
    assert p0 and p1, f"mode={mode}: no episode npz written for seed {SEED} or {OTHER_SEED}"
    z0 = _load(p0[sorted(p0)[0]])
    z1 = _load(p1[sorted(p1)[0]])
    same = all(
        z0[k].tobytes() == z1[k].tobytes() for k in ("state", "block_pos") if k in z0 and k in z1
    )
    assert not same, (
        f"mode={mode}: seed {SEED} and seed {OTHER_SEED} gave identical first-episode "
        "state and block_pos (rule: a different seed gives different data)"
    )


# ---------------------------------------------------------------- image shapes

@pytest.mark.parametrize("mode", MODES)
def test_image_shapes(factory, mode):
    out, _ = _run(factory, mode, PREVIEW_FRAMES, SEED, images=True, preview=True)
    paths = _episode_paths(out)
    assert paths, f"mode={mode}: no episode npz written with images=True"
    for path in paths:
        z = _load(path)
        assert "top" in z and "wrist" in z, f"{path.name}: top/wrist missing with images=True"
        assert "state" in z, f"{path.name}: state missing"
        T = z["state"].shape[0]
        spec = [
            ("state", np.float32, (T, 5)),
            ("action", np.float32, (T, 4)),
            ("block_pos", np.float32, (T, 3)),
            ("touch", np.bool_, (T,)),
            ("train", np.bool_, (T,)),
            ("top", np.uint8, (T, 240, 320, 3)),
            ("wrist", np.uint8, (T, 240, 320, 3)),
            ("shift_frame", np.int64, ()),
            ("shift_frame_full", np.int64, ()),
            ("trigger_z", np.float64, ()),
            ("block_before", np.float64, (3,)),
            ("block_after", np.float64, (3,)),
            ("train_start", np.int64, ()),
            ("train_end", np.int64, ()),
            ("seed", np.int64, ()),
            ("attempt", np.int64, ()),
        ]
        for name, dtype, shape in spec:
            assert name in z, f"{path.name}: array {name} missing (rule: contract saved-episode table)"
            x = z[name]
            assert x.dtype == np.dtype(dtype) and x.shape == shape, (
                f"{path.name}: {name} is {x.dtype} {x.shape}, contract says "
                f"{np.dtype(dtype)} {shape} (T={T})"
            )
        s = z["shift_type"]
        assert s.shape == () and s.dtype.kind == "U", (
            f"{path.name}: shift_type must be a str scalar, got {s.dtype} {s.shape}"
        )
        assert z["top"].shape[0] == len(z["state"]) == z["wrist"].shape[0], (
            f"{path.name}: top/wrist frame count must equal len(state) (rule: T equals len(state))"
        )


# ---------------------------------------------------------------- preview files

def _read_gif(path):
    im = Image.open(path)
    assert im.format == "GIF", f"{path.name} is not a GIF"
    frames, durations = [], []
    for fr in ImageSequence.Iterator(im):
        durations.append(fr.info.get("duration"))
        frames.append(np.asarray(fr.convert("RGB")))
    return frames, durations


def _red_border_fraction(frame):
    """Fraction of the outer 4 px ring (inside the 6 px context border) that is red."""
    mask = np.ones(frame.shape[:2], dtype=bool)
    mask[4:-4, 4:-4] = False
    px = frame[mask].astype(int)
    red = (px[:, 0] > 150) & (px[:, 1] < 80) & (px[:, 2] < 80)
    return red.mean()


@pytest.mark.parametrize("mode", MODES)
def test_preview_files_written_with_size(factory, mode):
    out, _ = _run(factory, mode, _preview_budget(mode), SEED, images=True, preview=True)
    for name in GIF_FILES[mode]:
        path = _find_one(out, name)
        im = Image.open(path)
        assert im.size == (640, 240), (
            f"{mode}: {name} is {im.size}, contract says width 640, height 240 "
            "(top and wrist side by side)"
        )


@pytest.mark.parametrize(
    "mode,name",
    [
        ("clean", "preview.gif"),
        ("embedded", "preview_early.gif"),
        ("embedded", "preview_late.gif"),
        ("separate", "preview_early.gif"),
        ("separate", "preview_late.gif"),
    ],
)
def test_preview_frames_match_saved_episode(factory, mode, name):
    out, _ = _run(factory, mode, _preview_budget(mode), SEED, images=True, preview=True)
    gif = _find_one(out, name)
    _, z = _first_episode(out, GIF_TYPE[name])
    frames, durations = _read_gif(gif)
    T = z["state"].shape[0]
    assert len(frames) == T, (
        f"{name}: {len(frames)} frames, but the first saved {GIF_TYPE[name]} episode has "
        f"{T} saved frames (rule: every saved frame is one GIF frame)"
    )
    for i, fr in enumerate(frames):
        assert fr.shape == (240, 640, 3), f"{name} frame {i} is {fr.shape}, expected (240, 640, 3)"
    assert all(d == 50 for d in durations), (
        f"{name}: frame durations {sorted(set(durations), key=str)} ms, contract says 50 ms per frame"
    )
    train = z["train"]
    for i, fr in enumerate(frames):
        red = _red_border_fraction(fr)
        if not bool(train[i]):
            assert red >= 0.9, (
                f"{name} frame {i} is a context frame (train=False) but has no red border "
                f"(red fraction {red:.2f}; rule: context frames get a 6 px red border)"
            )
        else:
            assert red <= 0.1, (
                f"{name} frame {i} is a train frame (train=True) but shows a red border "
                f"(red fraction {red:.2f}; rule: only context frames get the red border)"
            )


@pytest.mark.parametrize("name", ["preview_early.gif", "preview_late.gif"])
def test_separate_preview_context_marker(factory, name):
    out, _ = _run(factory, "separate", PREVIEW_FRAMES_BIG, SEED, images=True, preview=True)
    gif = _find_one(out, name)
    _, z = _first_episode(out, GIF_TYPE[name])
    frames, _ = _read_gif(gif)
    train_start = int(z["train_start"])
    first_red = _red_border_fraction(frames[0]) >= 0.9
    if train_start > 0:
        assert first_red, (
            f"{name}: first frame has no context marker, but train_start={train_start} > 0 "
            "(rule: separate preview first frame shows the red context border)"
        )
    else:
        assert not first_red, (
            f"{name}: first frame has a context marker, but train_start=0 "
            "(rule: marker only when train_start > 0)"
        )
    train_idx = np.flatnonzero(z["train"])
    assert train_idx.size > 0, f"{name}: saved episode has no train frames"
    red = _red_border_fraction(frames[int(train_idx[0])])
    assert red <= 0.1, (
        f"{name}: first train frame shows the context marker (red fraction {red:.2f}); "
        "rule: a train frame does not"
    )
